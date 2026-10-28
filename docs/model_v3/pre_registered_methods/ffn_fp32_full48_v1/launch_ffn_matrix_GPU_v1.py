#!/usr/bin/env python3
"""One Root submission and one source-bound C4 GPU preflight; no model changes."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
B = Path('/share/home/zixiao/descriptor_analysis')
R = B/'runs/model_v3_20261025'
HERE = Path(__file__).absolute().parent
C4 = HERE
EQ = B/'MFM_model_v3_ffn_fp32_candidate_v1'
GUARD = B/'runs/model_v3_20261026/gpu_runtime_retry_v4/submit_composed_eq_gpu_runtime_retry_v4.py'
GUARD_SHA = 'd3cba6a8610e6bd55fa21873be5c770efbe30be73b7b16d4f1cbdfa6ccb1c193'
# Final request SHA is obtained only from final source pins after Root commit/QA/publication.
NODE = 'compute-0-21'
GPU = 'GPU-c35f2434-9137-9723-1af5-dc69b6295243'
PREFIX = 'model_v3_ffn_FP32_complete48_GPU_launch_'
CONTROL_CAP = 2*1024**2
ENV_PINS = 'MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA'
FRAME_ENV = 'MODEL_V3_NUMERIC_GPU_ADMISSION_FRAME'
FRAME_SHA_ENV = 'MODEL_V3_NUMERIC_GPU_ADMISSION_SHA'
RECEIPT_ENV = 'MODEL_V3_NUMERIC_GPU_SUBMISSION_RECEIPT'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def reference(path, expected=None):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'Ordinary source/control required: '+str(path))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(expected is None or digest == expected, 'Raw SHA mismatch: '+str(path))
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest}


def bounded_json(path, expected=None):
    ref = reference(path, expected)
    require(ref['bytes'] <= CONTROL_CAP, 'Control metadata exceeds2MiB')
    raw = Path(path).read_bytes()
    require(len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Metadata changed while reading')
    return json.loads(raw), ref


def audit(expected):
    require(type(expected) is str and re.fullmatch(r'[0-9a-f]{64}', expected), 'Explicit machine launch manifest SHA required')
    pins, pins_ref = bounded_json(HERE/'source_pins_v1.json', expected)
    require(pins['schema'] == PREFIX+'source_pins_v1', 'Independent launch manifest required')
    for leaf in pins['files']:
        require(Path(leaf['path']).parent == HERE and reference(leaf['path']) == leaf, 'Launch source leaf drift')
    for leaf in pins['protected_dependencies']:
        require(reference(leaf['path']) == leaf, 'Protected dependency drift')
    expected_request = pins['execution_request']
    require(expected_request['path'] == str(C4/'execution_request_v1.json'), 'Final request location differs')
    c4, c4_ref = bounded_json(C4/'execution_request_v1.json', expected_request['sha256'])
    require(c4_ref == expected_request, 'Final request raw binding differs')
    require(c4['schema'] == 'model_v3_ffn_FP32_complete48_GPU_request_v1'
            and c4['expected_case_count'] == 48 and c4['mode'] == 'compensated_fp32_v1'
            and c4['attention_aggregation_mode'] == 'centered_fp32_v1' and c4['status'] == 'FINAL_BOUND_PUBLIC_FFN_FP32_REQUEST',
            'Preregistered full48 numeric request required')
    require(c4['attention_projection_mode'] == 'blocked_k64_compensated_fp32_v1'
            and c4['all_FP32_fixed_FFN_projection_candidate'] is True and c4['scientific_acceptance'] is False
            and c4['geometry_mode'] == 'residual_expansion_fp32_v1'
            and c4['ffn_projection_mode'] == 'blocked_k64_compensated_fp32_v1',
            'Registered fixed all-FP32 candidate required; no prior model adoption')
    for leaf in c4['source_refs']:
        require(reference(leaf['path']) == leaf, 'Frozen numeric candidate source/dependency drift')
    child_spec = importlib.util.spec_from_file_location('numeric_v2_public_blob_metadata_only', C4/'run_ffn_matrix.py')
    child = importlib.util.module_from_spec(child_spec); child_spec.loader.exec_module(child)
    public_rows = child.verify_publication(c4)
    selfcheck = child.metadata_selfcheck()
    reference(GUARD, GUARD_SHA)
    spec = importlib.util.spec_from_file_location('frozen_actual_1160_C4_resource_guard', GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    require(guard.NODE == NODE and guard.MEMORY_MIB == 32768 and guard.RSS_BYTES == 30064771072
            and guard.OUTPUT_BYTES == 2147483648 and guard.WALL_SECONDS == 1100, 'Original1160 limits must remain fixed')
    inputs = {'node': NODE, 'gpu_uuid': GPU, 'launch_source_pins': pins_ref,
        'diagnostic_source_pins': c4_ref, 'launch_source': reference(__file__),
        'sbatch': reference(HERE/'run_ffn_matrix_GPU_v1.sbatch'),
        'resource_guard': reference(GUARD, GUARD_SHA), 'public_blob_preflight': public_rows, 'metadata_selfcheck': selfcheck}
    return guard, inputs


def save(guard, path, value, *, first=False):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False, indent=2)+'\n').encode()
    require(len(raw) <= CONTROL_CAP, 'New control receipt exceeds declared2MiB limit')
    guard.write_state(path, value, first=first)


def sbatch_argv():
    return ['sbatch', '--parsable', '--export=ALL', '--nodelist='+NODE,
        str(HERE/'run_ffn_matrix_GPU_v1.sbatch')]


def submission_job(guard, submission):
    require(submission['schema'] == PREFIX+'submission_v1' and submission['status'] == 'SUBMITTED', 'Actual submitted receipt required')
    rows = [row for row in submission['observations'] if row.get('argv') == sbatch_argv()]
    require(len(rows) == 1, 'One actual sbatch raw observation required')
    guard.checked_observation(rows[0], sbatch_argv())
    match = re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?', rows[0]['stdout'].strip())
    require(match is not None and submission['job_id'] == match[1], 'Actual sbatch raw job ID mismatch')
    return match[1]


def submit(args, guard, inputs):
    require(not os.environ.get('SLURM_JOB_ID') and socket.gethostname().split('.')[0] != NODE,
        'Root login-side submission only; worker is a separate action')
    path = args.submission_receipt.absolute()
    require(path.parent == R and path.suffix == '.json', 'Fresh owned RUNS receipt required')
    frame_path = path.with_suffix('.admission.json')
    require(not path.exists() and not frame_path.exists(), 'Fresh attempt only; never auto-retry')
    recorder = guard.Recorder()
    record = {'schema': PREFIX+'submission_v1', 'status': 'ADMISSION_STARTED', 'job_id': None,
        'started_utc': guard.utc(), 'inputs': inputs, 'observations': recorder.rows,
        'old_1160_and_frozen_C4_v1_preserved': True, 'GPU_GRES_isolation_claimed': False}
    save(guard, path, record, first=True)
    started = time.monotonic()
    try:
        quota = guard.quota_reserve(recorder.capture(['quota', '-v', '-u', 'zixiao']))
        resources = guard.resource_frame(recorder, GPU, local=False, new_allocation=True)
        lock = guard.LOCK_ROOT/(GPU+'.lock')
        recorder.capture(['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o',
            'UserKnownHostsFile='+str(R/'compute21_known_hosts_v1'), NODE, 'flock -n '+str(lock)+' true'])
        require(time.monotonic()-started <= 120, 'Fresh Root admission became stale; no submission')
        root_frame = guard.root_resource_evidence(recorder.rows, inputs, resources, quota)
        guard.verify_root_resources(root_frame, inputs)
        frame = {'schema': PREFIX+'admission_v1', 'captured_utc': guard.utc(), 'inputs': inputs,
            'Root_resources': root_frame, 'worker_must_not_claim_snapshot_is_live': True,
            'no_prepared_or_old_QA_dependency': True}
        save(guard, frame_path, frame, first=True)
        frame_ref = reference(frame_path)
        env = {'MODEL_V3_EXPECTED_NODE': NODE, 'MODEL_V3_GPU_UUID': GPU,
            'MODEL_V3_NUMERIC_GPU_REQUEST_SHA': inputs['diagnostic_source_pins']['sha256'], ENV_PINS: inputs['launch_source_pins']['sha256'],
            FRAME_ENV: str(frame_path), FRAME_SHA_ENV: frame_ref['sha256'], RECEIPT_ENV: str(path)}
        record.update(status='SUBMISSION_INTENT_PERSISTED', admission_frame=frame_ref,
            bindings=env, argv=sbatch_argv(), intent_utc=guard.utc())
        save(guard, path, record)
        # Existing Recorder captures exact argv/returncode/raw stdout/stderr + hashes.
        previous = {key: os.environ.get(key) for key in env}
        try:
            os.environ.update(env)
            raw = recorder.capture(sbatch_argv(), timeout=45)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        match = re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?', raw.strip())
        require(match is not None, 'Submission outcome unknown; inspect receipt, never auto-retry')
        record.update(status='SUBMITTED', job_id=match[1], sbatch_completed_utc=guard.utc())
        submission_job(guard, record)
    except Exception as error:
        record.update(status='FAILED_OR_UNKNOWN_DO_NOT_AUTORETRY', exception=type(error).__name__,
            message=str(error), traceback=traceback.format_exc())
        raise
    finally:
        record['finished_utc'] = guard.utc()
        save(guard, path, record)
    print(json.dumps({'job_id': record['job_id'], 'submission_receipt': reference(path),
        'admission_frame': record['admission_frame'], 'gpu_uuid': GPU}))
    return 0


def final_output_census(guard, receipt, frame, worker, job):
    """One final census using the original helper, not a new polling monitor."""
    monitor_path = B/'MFM_model_v3/tools/model_v3/runtime_monitor.py'
    reference(monitor_path, guard.PINS[str(monitor_path)])
    spec = importlib.util.spec_from_file_location('frozen_1160_output_census', monitor_path)
    monitor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    output = R/('ffn_fp32_e2e_GPU_v1_'+job)
    sup = R/('ffn_fp32_e2e_GPU_v1_supervisor_'+job+'.json')
    files = [receipt, frame, sup, sup.with_suffix(sup.suffix+'.jsonl'),
        sup.with_suffix(sup.suffix+'.storage.json'), R/('ffn_fp32_e2e_GPU_v1_launch_v1_'+job+'.log')]
    seen, rows = set(), []
    total = monitor.owned_output_bytes(output) if output.exists() else 0
    for path in files:
        if path.exists():
            require(path.is_file() and not path.is_symlink() and not path.is_relative_to(output),
                'Disjoint ordinary external control/log file required')
            st = path.stat()
            if (st.st_dev, st.st_ino) not in seen:
                seen.add((st.st_dev, st.st_ino))
                total += st.st_size
                rows.append({'path': str(path), 'bytes': st.st_size})
    require(worker.stat().st_size <= CONTROL_CAP, 'Worker receipt exceeds2MiB')
    total += CONTROL_CAP  # Honest conservative allowance for this final receipt update.
    require(total <= 2147483648, 'Whole output plus external controls exceeds original2GiB')
    return {'scope': 'One child-root census plus distinct external files; private storage separately original2GiB',
        'output_root': str(output), 'external_files': rows, 'conservative_worker_receipt_allowance_bytes': CONTROL_CAP,
        'conservative_total_bytes': total, 'cap_bytes': 2147483648,
        'is_live_monitor': False, 'uses_original_owned_output_bytes': True}

def worker(args, guard, inputs):
    require(os.environ.get('MODEL_V3_EXPECTED_NODE') == NODE and os.environ.get('CUDA_VISIBLE_DEVICES') == GPU
        and os.environ.get('MODEL_V3_GPU_UUID') == GPU and os.environ.get('MODEL_V3_NUMERIC_GPU_REQUEST_SHA') == inputs['diagnostic_source_pins']['sha256'],
        'Exact original3env assignment required')
    allocation = guard.actual_allocation_identity()
    job = allocation['job_id']
    path = R/('ffn_fp32_e2e_GPU_v1_launch_v1_worker_'+job+'.json')
    recorder = guard.Recorder()
    record = {'schema': PREFIX+'worker_v1', 'status': 'PREFLIGHT', 'job_id': job,
        'started_utc': guard.utc(), 'inputs': inputs, 'actual_allocation_identity': allocation,
        'observations': recorder.rows, 'worker_sacct_queries': 0, 'worker_quota_queries': 0,
        'is_scientific_acceptance': False}
    save(guard, path, record, first=True)
    try:
        deadline = time.monotonic()+30
        while True:
            submission, submission_ref = bounded_json(args.submission_receipt)
            if submission.get('status') == 'SUBMITTED':
                break
            require(submission.get('status') == 'SUBMISSION_INTENT_PERSISTED' and time.monotonic() < deadline,
                'Matching actual submission not finalized; no model launch')
            time.sleep(.2)
        require(submission_job(guard, submission) == job and submission['inputs'] == inputs,
            'Root actual submission job/source differs')
        frame, frame_ref = bounded_json(os.environ[FRAME_ENV], os.environ[FRAME_SHA_ENV])
        require(frame['schema'] == PREFIX+'admission_v1' and frame['inputs'] == inputs
            and submission['admission_frame'] == frame_ref
            and args.submission_receipt.absolute() == Path(os.environ[RECEIPT_ENV])
            and all(os.environ.get(key) == value for key, value in submission['bindings'].items()),
            'Exact this-attempt Root frame/receipt/source/env binding required')
        lock_proof = guard.actual_public_lock(GPU)
        require(os.get_inheritable(lock_proof['fd']), 'Public lock must survive supervisor/child lifetime')
        resource_proof = guard.worker_resource_evidence(recorder, inputs, frame['Root_resources'], allocation)
        output = R/('ffn_fp32_e2e_GPU_v1_'+job)
        supervisor = R/('ffn_fp32_e2e_GPU_v1_supervisor_'+job+'.json')
        require(not output.exists() and not supervisor.exists(), 'Original fresh-output guard is retained')
        argv = [str(guard.PYTHON), '-u', '-B', str(B/'MFM_model_v3/tools/model_v3/run_supervised.py'),
            '--output-root', str(output), '--record', str(supervisor), '--gpu-uuid', GPU,
            '--wall-seconds', '1100', '--rss-limit-bytes', '30064771072', '--output-budget-bytes', '2147483648',
            '--private-scratch-root', '/tmp/mv3n_'+job, '--private-storage-budget-bytes', '2147483648', '--',
            str(guard.PYTHON), '-u', '-B', str(C4/'run_ffn_matrix.py'),
            '--request', str(C4/'execution_request_v1.json'), '--request-sha256', inputs['diagnostic_source_pins']['sha256'],
            '--output-root', str(output)]
        record.update(status='PRELAUNCH_ADMITTED', submission_receipt=submission_ref,
            immutable_admission_frame=frame_ref, public_GPU_lock=lock_proof, resources=resource_proof,
            argv=argv, old_prepared_and_75QA_not_used=True)
        save(guard, path, record)
        # No new monitor: the original1160 supervisor owns all runtime checks.
        result = subprocess.run(argv, cwd=EQ, pass_fds=(lock_proof['fd'],))
        record.update(status='CHILD_RETURNED', child_exit_code=result.returncode)
        return result.returncode
    except Exception as error:
        record.update(status='FAILED_PREFLIGHT_OR_SUPERVISOR', exception=type(error).__name__,
            message=str(error), traceback=traceback.format_exc())
        raise
    finally:
        record['finished_utc'] = guard.utc()
        save(guard, path, record)
        record['closed_control_output_census'] = final_output_census(guard, args.submission_receipt.absolute(),
            Path(os.environ[FRAME_ENV]), path, job)
        save(guard, path, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('audit', 'submit', 'worker'))
    parser.add_argument('--source-pins-sha', default=os.environ.get(ENV_PINS))
    parser.add_argument('--submission-receipt', type=Path)
    args = parser.parse_args()
    guard, inputs = audit(args.source_pins_sha)
    if args.action == 'audit':
        print(json.dumps({'status': 'SOURCE_AUDIT_ONLY_NO_SUBMISSION', 'inputs': inputs}))
        return 0
    require(args.submission_receipt is not None, 'Explicit fresh submission receipt required')
    if args.action == 'submit':
        return submit(args, guard, inputs)
    return worker(args, guard, inputs)


if __name__ == '__main__':
    raise SystemExit(main())
