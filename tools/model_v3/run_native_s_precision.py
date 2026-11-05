"""Opt-in existing-native-S four-member precision lifecycle; never submits jobs.

The original authoritative-D5 B CLI remains unchanged. Production requires a
separately pinned Root long-run storage hook, not a data-line/D5 adapter.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

REPO = Path(__file__).absolute().parents[2]
PLAN = REPO / 'current/configs/model_v3/performance/b_existing_native_s_plan_v1.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def production_protocol(path=PLAN):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    expected = {'schema': 'existing_native_S_precision_protocol_v1',
        'input_scope': 'existing_native_S_original_TRAIN_record_sampler_not_D5',
        'updates': 20000, 'pretraining_seeds': [0, 1], 'precisions': ['fp32', 'bf16'],
        'sample_budget': 10240000, 'warmup_samples': 0,
        'validation_updates': {'start': 0, 'interval': 500, 'end_inclusive': 20000},
        'checkpoint_updates': [10000, 20000], 'validation_role': 'PRETRAIN_VAL',
        'validation_records': 1024, 'validation_atoms': 55650, 'validation_noise_seed': 0, 'validation_epoch': 0,
        'validation_selection_sha256': '9ef81dcd5d3a84411328a76c5fbe7ccf123bc032e72e87a580d0b4c0bdf11e67',
        'TRAIN_records': 11104772, 'same_physical_GPU_environment_for_four_runs': True,
        'precision_only_model_execution_difference': True, 'D5_authority': False,
        'TRAIN_UNSEEN_CONFORMATION': 'NOT_PROVIDED',
        'acceptance': {'every_bf16_metric_point_within_two_true_fp32_seed_envelope': True,
                       'paired_component_RMSE_relative_max': .02}}
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise ValueError('Existing native-S production protocol differs from runtime scientific contract')
    return value


def collect_native_sources():
    from run_precision_experiment import collect_sources
    extra = ['tools/model_v3/run_native_s_precision.py', 'tools/model_v3/s_input_stream.py',
        'tools/model_v3/native_runtime_bindings.py', 'workflows/sprime_s/scripts/s_native_adapter_v1.py',
        'workflows/sprime_s/scripts/s_native_adapter_v2.py', 'workflows/sprime_s/scripts/s_loader_recovery_v2.py',
        'workflows/sprime_s/scripts/s_loader_recovery_v1.py',
        'workflows/sprime_s/formal_s/B1_seed0_v2.json', 'workflows/s_denoise/configs/A4_seed0_v3.json']
    return {**collect_sources(), **{name: digest(REPO / name) for name in extra}}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    report = commands.add_parser('report')
    report.add_argument('--members', type=Path, nargs=4, required=True)
    report.add_argument('--output', type=Path, required=True)
    member = commands.add_parser('member')
    member.add_argument('--input', choices=('existing_native_S', 'synthetic_native_fixture'), required=True)
    member.add_argument('--precision', choices=('fp32', 'bf16'), required=True)
    member.add_argument('--seed', type=int, choices=(0, 1), required=True)
    member.add_argument('--updates', type=int, default=20000)
    member.add_argument('--until-update', type=int)
    member.add_argument('--output', type=Path, required=True)
    member.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    member.add_argument('--expected-gpu', choices=('3090', '4090', '5090'))
    member.add_argument('--code-sha', required=True)
    member.add_argument('--prereg-sha', required=True)
    member.add_argument('--deterministic-controls', action='store_true')
    member.add_argument('--resume-checkpoint', type=Path)
    member.add_argument('--resume-output-root', type=Path)
    member.add_argument('--storage-hook', type=Path)
    member.add_argument('--storage-hook-sha256')
    member.add_argument('--wall-seconds', type=int, default=6900)
    return result


def load_storage_hook(args, request):
    if args.storage_hook is None or not re.fullmatch(r'[a-f0-9]{64}', args.storage_hook_sha256 or ''):
        raise ValueError('Root long-run total-storage hook and exact source SHA required; this is not a D5 dependency')
    if args.storage_hook.is_symlink() or digest(args.storage_hook) != args.storage_hook_sha256:
        raise ValueError('Root storage-hook source differs')
    spec = importlib.util.spec_from_file_location('native_S_root_storage_' + args.storage_hook_sha256[:16], args.storage_hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bind = getattr(module, 'bind_native_s_precision_storage', None)
    if not callable(bind):
        raise ValueError('Root storage adapter lacks explicit bind_native_s_precision_storage(request)')
    value = bind(request)
    if (not callable(getattr(value, 'guard', None)) or not callable(getattr(value, 'close', None))
            or not isinstance(getattr(value, 'binding', None), dict) or not value.binding):
        raise ValueError('Root storage hook must return bound guard/close and immutable policy binding')
    json.dumps(value.binding, allow_nan=False)
    return value


def run_member(args):
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) < 16:
        raise ValueError('Owned>=16CPU Slurm allocation required')
    if args.output.exists() or args.output.resolve().is_relative_to(REPO.resolve()):
        raise FileExistsError('Fresh outside-Git output required')
    if not all(re.fullmatch(r'[a-f0-9]{40}', value) for value in (args.code_sha, args.prereg_sha)):
        raise ValueError('Full actual and public prereg commits required')
    real = args.input == 'existing_native_S'
    if real and (args.updates != 20000 or args.device != 'cuda' or not args.deterministic_controls):
        raise ValueError('Real existing-S requires20000 CUDA updates and explicit common deterministic controls')
    if real:
        production_protocol()
    if not 60 <= args.wall_seconds <= 6900 or (args.resume_checkpoint is None) != (args.resume_output_root is None):
        raise ValueError('Bounded segment wall and complete explicit resume source required')
    cap = int(os.environ.get('MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES', str(2 * 1024**3)))
    if not 128 * 1024**2 <= cap <= 2 * 1024**3:
        raise ValueError('Original bounded output cap required')
    os.environ['MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES'] = str(cap)
    from a_execution_runtime import prepare_deterministic_controls, apply_deterministic_controls
    preimport = prepare_deterministic_controls(args.deterministic_controls)
    import torch
    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    deterministic = apply_deterministic_controls(preimport)
    from run_precision_experiment import PersistentOfflineTracker
    from phychem_mfm.phase1.v3_native_s_precision import NativeSPrecisionPlan, NativeSPrecisionExperiment
    from phychem_mfm.phase1.v3_native_s_precision_data import ExistingNativeSInputs, SCOPE
    from phychem_mfm.phase1.v3_native_s_precision_fixture import SyntheticNativeSInputs
    from phychem_mfm.phase1.v3_precision_experiment import write_new_json
    from runtime_monitor import owned_output_bytes, owned_process_observation
    from private_runtime_storage import load_storage_bindings
    uuid, lock = os.environ.get('CUDA_VISIBLE_DEVICES', ''), None
    environment = {'torch': str(torch.__version__), 'cuda': torch.version.cuda, 'logical_python': sys.executable,
                   'device': args.device, 'deterministic_execution_sha256': deterministic['execution_sha256']}
    if args.device == 'cuda':
        if not re.fullmatch(r'GPU-[a-fA-F0-9-]+', uuid) or torch.cuda.device_count() != 1 or not args.expected_gpu:
            raise ValueError('One explicit physical GPU UUID/type required')
        from runtime_monitor import gpu_observation
        import fcntl
        lock = (Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks') / (uuid + '.lock')).open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gpu = gpu_observation(uuid, own_pids=(os.getpid(),))
        if gpu['foreign_processes'] or args.expected_gpu not in torch.cuda.get_device_name(0):
            raise RuntimeError('Selected GPU is foreign-occupied or differs from requested type')
        environment.update(gpu_uuid=uuid, gpu_name=torch.cuda.get_device_name(0), driver=gpu['driver_version'])
        storage = load_storage_bindings()
    else:
        if real or torch.cuda.is_available():
            raise ValueError('CPU mode is synthetic-only and must hide GPUs')
        storage = {'scope': 'CPU_fixture_no_CUDA'}
    grid = tuple(range(0, args.updates + 1, 500)) if real else tuple(sorted({0, args.updates // 2, args.updates}))
    plan = NativeSPrecisionPlan(SCOPE if real else args.input, args.updates,
        10240000 if real else 3 * args.updates, grid, (10000, 20000) if real else (args.updates,))
    sources = collect_native_sources()
    if real:
        # Bind the operational adapter before giving it the final request.
        if not re.fullmatch(r'[a-f0-9]{64}', args.storage_hook_sha256 or ''):
            raise ValueError('Exact Root total-storage adapter SHA required')
        sources['external_Root_total_storage_hook'] = args.storage_hook_sha256
    request = {'scope': plan.input_scope, 'plan': asdict(plan), 'code_sha': args.code_sha,
        'prereg_sha': args.prereg_sha, 'seed': args.seed, 'precision': args.precision,
        'output_root': str(args.output), 'resume_checkpoint': str(args.resume_checkpoint) if args.resume_checkpoint else None,
        'resume_output_root': str(args.resume_output_root) if args.resume_output_root else None,
        'sources': sources, 'runtime': environment, 'max_segment_bytes': cap,
        'private_storage': storage, 'wall_seconds': args.wall_seconds,
        'fixed_checkpoint_updates': list(plan.checkpoint_updates)}
    storage_hook = load_storage_hook(args, request) if real else None
    args.output.mkdir(mode=0o700, parents=True)
    os.environ.update(WANDB_MODE='offline', WANDB_CACHE_DIR=str(args.output / 'cache'),
                      WANDB_DATA_DIR=str(args.output / 'wandb_data'))
    import wandb
    inputs, run, engine, outcome, failure, cleanup = None, None, None, None, None, []
    started = time.monotonic()
    def guard(action, experiment):
        if time.monotonic() - started > args.wall_seconds - 30:
            raise TimeoutError('Native precision segment reached finalization reserve; resume only last complete checkpoint')
        if args.device == 'cuda':
            from a_execution_runtime import guard_resources
            resource = guard_resources(args.output, uuid)
        else:
            process = owned_process_observation(os.getpid())
            resource = {'process_rss_sum_bytes': process['rss_sum_bytes'], 'output_bytes': owned_output_bytes(args.output)}
            if resource['process_rss_sum_bytes'] > 56 * 1024**3 or resource['output_bytes'] > cap - 32 * 1024**2:
                raise MemoryError('Synthetic segment exceeded original RSS/output reserve')
        if storage_hook:
            storage_hook.guard(action, experiment)
        with (args.output / 'resources.jsonl').open('a') as log:
            log.write(json.dumps({'action': action, 'updates': experiment.clock.optimizer_updates,
                'samples': experiment.clock.samples_consumed, **resource}, allow_nan=False) + '\n')
    try:
        inputs = ExistingNativeSInputs(seed=args.seed) if real else SyntheticNativeSInputs(seed=args.seed)
        run = wandb.init(project='mfm_model_v3_development', mode='offline', dir=str(args.output),
            name=f'nativeS_B_{args.precision}_seed{args.seed}_{os.environ["SLURM_JOB_ID"]}',
            config={**request, 'deterministic_controls': deterministic,
                'Root_storage_binding': storage_hook.binding if storage_hook else None})
        engine = NativeSPrecisionExperiment(inputs, plan, seed=args.seed, precision=args.precision,
            tracker=PersistentOfflineTracker(run, args.output / 'history.jsonl'), source_bindings=sources,
            code_sha=args.code_sha, prereg_sha=args.prereg_sha, device=args.device, runtime_binding=environment,
            storage_policy_binding=storage_hook.binding if storage_hook else None)
        if args.resume_checkpoint:
            engine.load(args.resume_checkpoint.absolute(), output_root=args.resume_output_root.absolute())
        write_new_json(args.output / 'configuration.json', {'contract': engine.contract, 'source_inputs': inputs.bindings,
            'plan_file': {'path': str(PLAN), 'sha256': digest(PLAN)}, 'tracker': engine.tracker_identity,
            'resume_parent': engine.resume_parent, 'private_storage': storage,
            'Root_storage_binding': storage_hook.binding if storage_hook else None})
        outcome = engine.run(args.output, until_update=args.until_update, guard=guard,
            pause_requested=lambda: time.monotonic() - started >= args.wall_seconds - min(300, args.wall_seconds // 2))
        if {**collect_native_sources(),
                **({'external_Root_total_storage_hook': digest(args.storage_hook)} if real else {})} != sources:
            raise RuntimeError('Scientific source bytes changed during native-S member')
    except BaseException as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        for name, close in (('native_inputs', None if inputs is None else inputs.close),
                ('Root_storage_hook', None if storage_hook is None else storage_hook.close),
                ('offline_SDK', None if run is None else lambda: run.finish(exit_code=1 if failure or cleanup else 0))):
            if close:
                try:
                    close()
                except BaseException as exc:
                    cleanup.append({'component': name, 'type': type(exc).__name__, 'message': str(exc)})
        final_bytes = None
        try:
            final_bytes = owned_output_bytes(args.output)
            if final_bytes > cap - 1024**2:
                raise MemoryError('Final SDK/checkpoint output exceeds bounded finalization reserve')
        except BaseException as exc:
            cleanup.append({'component': 'final_output_census', 'type': type(exc).__name__, 'message': str(exc)})
        write_new_json(args.output / 'run_status.json', {'status': 'CHILD_COMPLETED_PENDING_OUTER_TERMINAL' if failure is None and not cleanup else 'FAILED',
            'failure': failure, 'cleanup_errors': cleanup, 'elapsed_seconds': time.monotonic() - started,
            'member_endpoint': None if outcome is None else outcome['optimizer_updates'],
            'tracker_id': None if run is None else run.id, 'offline_unsynced': True, 'scientific_acceptance': False,
            'D5_authority': False, 'original_sources_written': False, 'final_output_bytes_before_status': final_bytes})
        if lock:
            lock.close()
        if cleanup and failure is None:
            raise RuntimeError('Native-S precision cleanup failed')


def main():
    args = parser().parse_args()
    if args.command == 'member':
        return run_member(args)
    from phychem_mfm.phase1.v3_native_s_precision import compare_native_s_members
    from phychem_mfm.phase1.v3_precision_experiment import write_new_json
    if args.output.exists() or args.output.resolve().is_relative_to(REPO.resolve()):
        raise FileExistsError('Fresh outside-Git numeric audit output required')
    write_new_json(args.output, compare_native_s_members([json.loads(path.read_text()) for path in args.members]))


if __name__ == '__main__':
    main()
