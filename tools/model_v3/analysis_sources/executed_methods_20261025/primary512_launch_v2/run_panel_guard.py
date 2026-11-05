#!/usr/bin/env python3
"""External root-owned wall/resource guard around the unchanged evaluation CLI.

No submission or GPU selection. Root supplies the admitted physical UUID/node
and Slurm resources. The evaluator itself holds the existing UUID lock; this
guard does not acquire a second lock or claim scheduler GRES isolation.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
import traceback
from export_admission import read_validated_export, require_same_reference, EVALUATION_CODE_SHA


FIXED_RUNTIME_MONITOR = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py')


def require(value, reason):
    if not value: raise RuntimeError(reason)


def binding(path):
    path = Path(path).absolute(); require(path.is_file() and not path.is_symlink(), 'Ordinary bound file required')
    digest = hashlib.sha256(); size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block); size += len(block)
    return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': size}


def read_bound(ref):
    actual = binding(ref['path'])
    require(actual['sha256'] == ref['sha256'] and ('bytes' not in ref or actual['bytes'] == ref['bytes']), 'Physical launch/source SHA differs')
    return json.loads(Path(ref['path']).read_text())


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def checked_reference(candidate, authority, *, state_key=None):
    try:
        require_same_reference(candidate, authority, state_key=state_key)
    except (ValueError, KeyError, OSError) as exc:
        require(False, 'READY reference admission failed: '+str(exc))


def verify_sources(spec, request):
    root = Path(spec['repository_root'])
    for relative, ref in spec['bridge_pins'].items():
        require(binding(root / relative) == ref, 'Tested primary bridge/configuration changed')
    for ref in request['source_files']:
        path = root / ref['path']
        require(path.resolve().is_relative_to(root.resolve()) and binding(path)['sha256'] == ref['sha256'], 'Executed source inventory changed')
    require(binding(__file__) == spec['external_guard'], 'External guard implementation changed')
    require(binding(Path(__file__).with_name('export_admission.py')) == spec['export_admission_implementation'],
        'Export terminal-admission implementation changed')
    exported = read_validated_export(spec['export_ready'], spec['export_terminal_admission'], check_freshness=False)
    require(exported['checkpoint'] == spec['source_checkpoint']
        and exported['model_configuration'] == spec['original_configuration']
        and exported['export_code_sha'] == spec['export_code_sha']
        and exported['architecture_sha256'] == request['architecture_sha256'], 'Original exported bundle binding drifted')
    checked_reference(request['checkpoint'], spec['source_checkpoint'], state_key='model_state')
    checked_reference(request['model_configuration'], spec['original_configuration'])
    require(request['reference_kind'] == 'primary' and request['historical_reference'] is None,
        'Before model execution the request must select exactly the original primary READY bundle')
    require(Path(spec['runtime_monitor']['path']).absolute() == FIXED_RUNTIME_MONITOR,
        'Use only the Root-validated fixed profiler_v2 monitor')
    require(binding(FIXED_RUNTIME_MONITOR) == spec['runtime_monitor'], 'Fixed runtime monitor bytes changed')


def accounting_module(reference):
    require(Path(reference['path']).absolute() == FIXED_RUNTIME_MONITOR and binding(FIXED_RUNTIME_MONITOR) == reference,
        'Bound fixed profiler accounting implementation differs')
    name = 'root_fixed_profiler_output_'+reference['sha256']
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, reference['path'])
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def precision(torch):
    return {'default_dtype': str(torch.get_default_dtype()), 'matmul_precision': torch.get_float32_matmul_precision(),
        'cuda_matmul_allow_tf32': bool(torch.backends.cuda.matmul.allow_tf32),
        'cudnn_allow_tf32': bool(torch.backends.cudnn.allow_tf32),
        'cudnn_deterministic': bool(torch.backends.cudnn.deterministic),
        'cudnn_benchmark': bool(torch.backends.cudnn.benchmark),
        'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
        'deterministic_warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
        'NVIDIA_TF32_OVERRIDE': os.environ.get('NVIDIA_TF32_OVERRIDE'),
        'CUBLAS_WORKSPACE_CONFIG': os.environ.get('CUBLAS_WORKSPACE_CONFIG')}


def child(spec, guard_output):
    request = read_bound(spec['request']); verify_sources(spec, request)
    root = Path(spec['repository_root']); sys.path.insert(0, str(root / 'current'))
    import torch
    before = precision(torch)
    require(before['default_dtype'] == 'torch.float32', 'FP32 default required; launcher will not change caller policy')
    state = {'schema': 'model_v3_primary512_panel_child_runtime_v1', 'policy_before': before,
        'launcher_changes_precision_policy': False, 'request_sha256': spec['request']['sha256'],
        'torch': str(torch.__version__), 'torch_cuda': torch.version.cuda,
        'actual_argv': spec['request_argv'], 'cuda_uuid': os.environ['CUDA_VISIBLE_DEVICES'],
        'torch_allocator_peak_scope': 'evaluator process allocator since last reset; not device-global'}
    write(guard_output / 'child_runtime_start.json', state)
    rc = 1
    try:
        path = root / 'tools/model_v3/evaluate_dev_panel.py'
        loader = importlib.util.spec_from_file_location('root_guarded_original_evaluation_cli', path)
        runner = importlib.util.module_from_spec(loader); loader.loader.exec_module(runner)
        # Execute the unchanged parser/main in this process so the recorded
        # ambient precision settings are the settings the actual evaluator sees.
        sys.argv = spec['request_argv'][3:]
        rc = runner.main()
        return rc
    finally:
        after = precision(torch); state.update(policy_after=after, policy_unchanged=before == after, returncode=rc)
        if torch.cuda.is_initialized():
            state.update(torch_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                         torch_peak_reserved_bytes=torch.cuda.max_memory_reserved())
        import resource
        state['process_peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        verify_sources(spec, request)
        write(guard_output / 'child_runtime_finish.json', state)
        require(before == after, 'Effective TF32/matmul/default precision policy changed during evaluation')


def gpu_snapshot(uuid):
    result = subprocess.run(['nvidia-smi', '--id='+uuid,
        '--query-gpu=uuid,name,memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits'],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10, check=False)
    rows = list(csv.reader(result.stdout.splitlines()))
    require(result.returncode == 0 and len(rows) == 1 and len(rows[0]) == 5 and rows[0][0].strip() == uuid,
            'The actual admitted GPU UUID/memory could not be measured')
    row = rows[0]
    return {'uuid': uuid, 'model': row[1].strip(), 'total_bytes': int(float(row[2])*1024**2),
            'used_bytes': int(float(row[3])*1024**2), 'utilization_percent': float(row[4])}


def process_group_rss(pgid):
    rows = []; owner = os.getuid()
    for directory in Path('/proc').iterdir():
        if not directory.name.isdecimal(): continue
        try:
            raw = (directory / 'stat').read_text(); fields = raw[raw.rfind(')')+2:].split()
            if int(fields[2]) != pgid: continue
            status = (directory / 'status').read_text().splitlines()
            uid = next(int(line.split()[1]) for line in status if line.startswith('Uid:'))
            if uid != owner: continue
            rss = next((int(line.split()[1])*1024 for line in status if line.startswith('VmRSS:')), 0)
            rows.append({'pid': int(directory.name), 'start_ticks': int(fields[19]), 'rss_bytes': rss})
        except (OSError, ValueError, StopIteration):
            continue
    return {'rss_bytes': sum(row['rss_bytes'] for row in rows), 'processes': rows,
        'scope': 'owned newly-created process group; Root aggregate supervisor also covers detached SDK descendants'}


def independent_output_roots(request, guard_output):
    roots = sorted({Path(path).absolute() for path in (request['output_root'], request['cache_root'], guard_output)},
                   key=lambda path: (len(path.parts), str(path)))
    selected = []
    for root in roots:
        require('..' not in root.parts, 'Unsafe owned output root')
        if not any(root.is_relative_to(parent) for parent in selected):
            selected.append(root)
    return selected


def output_bytes(request, guard_output, monitor_reference):
    monitor = accounting_module(monitor_reference)
    # The validated dirfd helper accepts exactly the canonical SDK links, never
    # follows arbitrary links, and checks hard-link ownership. Count each
    # maximal root once so eval/h0_cache is not charged for a second time.
    return sum(monitor.owned_output_bytes(root) for root in independent_output_roots(request, guard_output))


def terminate_owned_group(process, grace):
    # Popen starts a new session whose pgid is its owned leader PID. Never
    # signal any inherited/common shell process group or other user's PID.
    if process.poll() is None:
        require(os.getpgid(process.pid) == process.pid, 'Child process-group identity changed')
        os.killpg(process.pid, signal.SIGTERM)
        try: process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                require(os.getpgid(process.pid) == process.pid, 'Child group no longer belongs to this launch')
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)


def verify_primary_result(spec, request, result):
    require(result.get('status') == 'COMPLETED' and result['request_sha256'] == spec['request']['sha256']
        and result['reference_kind'] == request['reference_kind'] == 'primary', 'Primary result/request scope differs')
    require(result['code_sha'] == request['code_sha'] == spec['code_sha'] == EVALUATION_CODE_SHA,
        'Actual executed evaluator code differs')
    pair = result['encoder_pair']
    for ref in (request['checkpoint'], pair['checkpoint']):
        checked_reference(ref, spec['source_checkpoint'], state_key='model_state')
    for ref in (request['model_configuration'], pair['original_configuration']):
        checked_reference(ref, spec['original_configuration'])
    require(pair['H0_dimension'] == 512 and pair['reference_kind'] == 'primary'
        and pair['checkpoint_schema'] == 'source_training_checkpoint_v1',
        'Actual primary512 candidate source/configuration differs')
    require(pair['architecture_sha256'] == result['architecture_sha256'] == request['architecture_sha256']
        and pair['random_reference_seed'] == result['random_reference_initialization_seed'] == 20261025
        and pair['pretraining_seed'] == request['pretraining_seed'] == result['pretraining_seed']
        and result['readout_seed'] == 0, 'Candidate/random full configuration or seeds differ')
    require(pair['checkpoint_encoder_state_sha256'] != pair['random_encoder_state_sha256'], 'Candidate and random weights must differ')
    tasks = {'cyp.3A4', 'cyp.2D6', 'exp.LogD', 'exp.LogS', 'exp.Log_HLM_CLint', 'qm9.U0', 'qm9.homo', 'qm9.lumo', 'qm9.alpha'}
    for name, expected in (('primary_18_cells', {task+'@'+readout for task in tasks for readout in ('ridge', 'linear64_relu')}),
        ('ridge', {task+'@ridge' for task in tasks}), ('linear64_relu', {task+'@linear64_relu' for task in tasks})):
        summary = result['summaries'][name]
        require(summary['complete'] is True and set(summary['tasks']) == expected
            and summary['bootstrap_samples'] == summary['bootstrap_defined'] == 1000, 'Incomplete frozen18cell/paired bootstrap result')
    caches = result['h0_caches']
    require(set(caches) == {label+'/'+dataset for label in ('candidate', 'reference')
        for dataset in ('cyp_isoform', 'expansionrx', 'qm9')}, 'Both primary512 native H0 inventories required')
    for dataset in ('cyp_isoform', 'expansionrx', 'qm9'):
        candidate, reference = (caches[label+'/'+dataset] for label in ('candidate', 'reference'))
        left, right = candidate['binding'], reference['binding']
        for key in ('architecture_sha256', 'membership_sha256', 'geometry_sha256', 'dimension',
                    'packing_plan_sha256', 'packing_budget_sha256', 'effective_runtime_sha256'):
            require(left[key] == right[key], 'Candidate/random primary H0 bindings differ')
        require(left['dimension'] == 512 and candidate['targets_cached'] is reference['targets_cached'] is False
            and candidate['molecules'] == reference['molecules'] and candidate['atoms'] == reference['atoms'],
            'Primary H0 dimension/target-free native inventory differs')
        require(left['encoder_sha256'] == pair['checkpoint_encoder_state_sha256']
            and right['encoder_sha256'] == pair['random_encoder_state_sha256'], 'Primary paired H0 weight-state binding differs')


def main():
    main_started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--gpu-uuid', required=True)
    parser.add_argument('--guard-output', type=Path, required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    spec = read_bound({'path': str(args.spec), 'sha256': args.spec_sha256})
    require(spec.get('schema') == 'model_v3_primary512_dev9_external_launch_v2'
        and spec['preregistration_sha'] == '39cf4929299cd227a3c361183a4b26c8b1405900', 'Frozen published panel specification required')
    require(os.getuid() == 1278 and os.environ.get('SLURM_JOB_ID')
        and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16
        and int(os.environ.get('SLURM_MEM_PER_NODE', '0')) >= 32768, 'Root-owned >=16CPU/32GiB Slurm allocation required')
    require(spec['requested_memory_bytes'] == 32*1024**3
        and spec['maximum_process_group_rss_bytes'] == 28*1024**3
        and spec['maximum_output_and_cache_bytes'] == 2*1024**3, 'Reviewed v2 memory/output budgets required')
    require(re.fullmatch(r'compute-0-(?:[0-7]|20|21|22)', args.node)
        and socket.gethostname().split('.')[0] == args.node, 'The actual node must match Root admission')
    require(re.fullmatch(r'GPU-[0-9a-fA-F-]{16,64}', args.gpu_uuid)
        and os.environ.get('CUDA_VISIBLE_DEVICES') == args.gpu_uuid, 'The measured full UUID must be bound by Root')
    require(Path(sys.executable).absolute() == Path(spec['python_entry']).absolute(), 'Use the verified logical interpreter')
    guard_output = args.guard_output.absolute()
    request = read_bound(spec['request']); verify_sources(spec, request)
    read_validated_export(spec['export_ready'], spec['export_terminal_admission'], check_freshness=True)
    require(spec['reference_kind'] == 'primary' and spec['H0_dimension'] == 512
        and spec['architecture_selection_claimed'] is False and spec['formal_pretraining_complete'] is False,
        'This short500 export validates primary512 tooling/timing only')
    if args.child:
        return child(spec, guard_output)
    root = Path(spec['repository_root'])
    require(not guard_output.exists() and not guard_output.resolve().is_relative_to(root.resolve()), 'Fresh external supervision output required')
    require(not guard_output.is_relative_to(Path(request['output_root']))
        and not guard_output.is_relative_to(Path(request['cache_root'])), 'Supervision output must not precreate evaluator/cache roots')
    require(not Path(request['output_root']).exists() and not Path(request['cache_root']).exists(), 'This first performance closure requires fresh evaluation output and cold cache')
    guard_output.mkdir(parents=True, exist_ok=False)
    start = main_started; process = None
    outcome = {'status': 'FAILED', 'job_id': os.environ['SLURM_JOB_ID'], 'node': args.node, 'gpu_uuid': args.gpu_uuid,
        'spec_sha256': args.spec_sha256, 'request_sha256': spec['request']['sha256'],
        'code_sha': spec['code_sha'], 'preregistration_sha': spec['preregistration_sha'],
        'root_admission_required': True, 'GPU_GRES_isolation_claimed': False, 'cache_started_cold': True,
        'guard_implementation': binding(__file__), 'independent_WandB_SDK_verification_complete': False}
    try:
        gpu = gpu_snapshot(args.gpu_uuid)
        require(gpu['used_bytes'] <= spec['maximum_global_gpu_memory_fraction']*gpu['total_bytes'], 'Root GPU admission memory baseline exceeds 85%')
        write(guard_output / 'admission_snapshot.json', {'gpu': gpu,
            'allocated_cpus': int(os.environ['SLURM_CPUS_PER_TASK']), 'allocated_memory_MiB': int(os.environ['SLURM_MEM_PER_NODE']),
            'core_owns_UUID_lock': True, 'guard_changes_precision_policy': False})
        argv = [str(spec['python_entry']), '-u', '-B', str(Path(__file__).absolute()),
            '--spec', str(args.spec.absolute()), '--spec-sha256', args.spec_sha256,
            '--node', args.node, '--gpu-uuid', args.gpu_uuid, '--guard-output', str(guard_output), '--child']
        with (guard_output / 'child.log').open('xb') as log, (guard_output / 'resource_samples.jsonl').open('x') as samples:
            process = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
            deadline = start+spec['maximum_child_wall_seconds']; next_sample = 0.
            while process.poll() is None:
                now = time.monotonic()
                require(now < deadline, 'Whole-panel wall budget exhausted, including H0/cache, both readouts, bootstrap and W&B finish')
                if now >= next_sample:
                    gpu = gpu_snapshot(args.gpu_uuid); group = process_group_rss(process.pid)
                    size = output_bytes(request, guard_output, spec['runtime_monitor'])
                    record = {'elapsed_seconds': now-start, 'gpu': gpu, 'owned_group': group, 'output_bytes': size}
                    samples.write(json.dumps(record, allow_nan=False)+'\n'); samples.flush(); os.fsync(samples.fileno())
                    require(gpu['used_bytes'] <= spec['maximum_global_gpu_memory_fraction']*gpu['total_bytes'], 'Observed global GPU memory exceeded 85%')
                    require(group['rss_bytes'] <= spec['maximum_process_group_rss_bytes'], 'Observed owned process-group RSS exceeded bound')
                    require(size <= spec['maximum_output_and_cache_bytes'], 'Owned cache/output byte cap exceeded')
                    print(json.dumps({'status': 'RUNNING', 'elapsed_seconds': round(now-start, 1),
                        'GPU_memory_MiB': gpu['used_bytes']//1024**2, 'owned_group_RSS_MiB': group['rss_bytes']//1024**2}), flush=True)
                    next_sample = now+30
                time.sleep(1)
            outcome['child_returncode'] = process.returncode
        verify_sources(spec, request)
        runtime = json.loads((guard_output / 'child_runtime_finish.json').read_text())
        require(runtime.get('policy_unchanged') is True and runtime['process_peak_rss_bytes'] <= spec['maximum_process_group_rss_bytes'],
            'Final precision/process peak-RSS validation failed')
        result_path = Path(request['output_root']) / 'result.json'
        result = json.loads(result_path.read_text()) if result_path.exists() else {}
        require(process.returncode == 0 and result.get('status') == 'COMPLETED', 'The full original panel did not complete successfully')
        verify_primary_result(spec, request, result)
        final_output_bytes = output_bytes(request, guard_output, spec['runtime_monitor'])
        require(final_output_bytes <= spec['maximum_output_and_cache_bytes']-(64 << 10),
            'Final cache/output plus guard-finalization reserve exceeds the shared2GiB cap')
        elapsed = time.monotonic()-start
        require(elapsed <= spec['total_allocation_target_seconds'], 'Inclusive whole-panel one-GPU-hour target was not met')
        outcome.update(status='COMPLETED', result=binding(result_path), child_runtime=runtime,
            inclusive_panel_wall_seconds=elapsed, inclusive_one_GPU_hour_target_met=True,
            SDK_files=[binding(path) for path in Path(request['output_root']).rglob('*.wandb')],
            readouts=['ridge', 'linear64_relu'], reference_kind='primary', H0_dimension=512,
            final_output_bytes_before_guard_receipt=final_output_bytes,
            checkpoint_scope=spec['checkpoint_scope'], architecture_selection_claimed=False, formal_pretraining_complete=False)
    except BaseException as exc:
        outcome.update(status='FAILED', exception_type=type(exc).__name__, reason=str(exc), exception_chain=traceback.format_exc())
        if process is not None:
            terminate_owned_group(process, spec['termination_grace_seconds'])
    finally:
        outcome['elapsed_seconds_including_cleanup'] = time.monotonic()-start
        write(guard_output / 'guard_result.json', outcome)
    return 0 if outcome['status'] == 'COMPLETED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
