"""Root-only metadata closure of the explicit manual head-off R2.

No models, Torch, arrays, SDK or scientific history bodies. The fixed gate
contains private input identities; these are checked in memory and not exported.
Saved trajectory differences are checked, not independently recomputed losses.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
B = Path('/share/home/zixiao/descriptor_analysis')
N = B/'runs/model_v3_20261026'
O = B/'runs/model_v3_20261025'
W = B/'MFM_model_v3_performance_integration_v1'
S = N/'performance_head_off_R2_GPU_v1_source'
FAMILY = N/'performance_head_off_R2_v1'
CHILD, CONTROL = FAMILY/'child', FAMILY/'control'
JOB = '4524580'
NODE = 'compute-0-21'
GPU = 'GPU-c35f2434-9137-9723-1af5-dc69b6295243'
CODE = '9e16d4c5a15c558051499d3dc0c55c9bd3787734'
PUBLIC = '8147f44baa1ea1ecc3822af7affd0a95401ed248'
TREE = '98b3b4bd8bc083a4150f536024e4dc81e6fb6108'
SCHEMA = 'model_v3_Root_head_off_R2_full_A_numeric_closure_v1'
STATUS = 'ACTUAL_GPU_C0_HEAD_OFF_R2_FULL20_500_NUMERIC_SOURCE_RESOURCE_CLOSED'
WHOLE, RSS = 2 << 30, 56 << 30
FLAGS = {'distance': True, 'backbone': True, 'head': False}
OUTPUT_NAMES = ('output/atom_repr', 'output/bond/existence', 'output/bond/existence_target',
                'output/bond/order', 'output/coordinate_pred', 'output/element_logits',
                'output/graph_repr', 'output/noise_pred')
ARTIFACT_NAMES = ('configuration.json', 'summary.json', 'fixed_batch_gate.json',
                  'trajectory_gate.json', 'run_status.json')
SEEN = {}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def projection(ref):
    need(type(ref) is dict and {'path', 'bytes', 'sha256'} <= set(ref)
         and type(ref['path']) is str and type(ref['bytes']) is int and ref['bytes'] >= 0
         and sha(ref['sha256']), 'Typed raw reference required')
    return {k: ref[k] for k in ('path', 'bytes', 'sha256')}


def rawref(path, *, remember=True):
    path = Path(path).absolute()
    need(path.is_relative_to(B) and '..' not in path.parts, 'Project-owned absolute path required')
    need(path.suffix.lower() not in {'.npz', '.pt', '.pth', '.wandb', '.lmdb', '.pkl',
                                    '.bin', '.parquet', '.jsonl'}, 'No scientific payload/journal access')
    limit = (4 << 20) if path == CHILD/'fixed_batch_gate.json' else (2 << 20)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 1278 and before.st_nlink == 1
         and not path.is_symlink() and 0 <= before.st_size <= limit,
         'Bounded owned ordinary source/metadata required: '+str(path))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    after = path.lstat()
    keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_uid', 'st_nlink')
    need(all(getattr(before, k) == getattr(after, k) for k in keys), 'Read-time metadata drift')
    ref = dict(path=str(path), bytes=before.st_size, sha256=digest.hexdigest())
    if remember:
        need(SEEN.setdefault(str(path), ref) == ref, 'Bound metadata changed during closure')
    return ref


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def read(path, expected=None):
    ref = rawref(path)
    if expected is not None:
        need(ref == projection(expected), 'Exact metadata raw binding differs')
    value = json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(rawref(path) == ref, 'Metadata changed while parsing')
    return value, ref


def bound(ref):
    return read(projection(ref)['path'], ref)[0]


def command(argv):
    observed = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, timeout=45)
    need(len(observed.stdout)+len(observed.stderr) <= 2 << 20
         and observed.returncode == 0 and observed.stderr == '', 'Read-only metadata command failed')
    return dict(argv=[str(x) for x in argv], returncode=observed.returncode,
                stdout=observed.stdout, stderr=observed.stderr)


def terminal():
    result = command(['sacct', '-X', '-n', '-P', '-j', JOB,
                      '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    rows = [x.split('|') for x in result['stdout'].splitlines() if x.strip()]
    need(len(rows) == 1 and len(rows[0]) == 7, 'One actual parent accounting row required')
    row = rows[0]
    need(row[:4] == [JOB, 'zixiao', 'COMPLETED', '0:0'] and row[5:] == ['16', NODE]
         and row[4].isdigit() and 0 < int(row[4]) <= 7200, 'Actual owned16CPU/C35 parent C0 required')
    return result


def metric(value, tolerance, gradient=False):
    need(type(value) is dict and type(value.get('name')) is str and value['name'], 'Named metric required')
    if set(value) == {'name', 'pass', 'reason'}:
        need(gradient and value['pass'] is True and value['reason'] == 'both_disabled',
             'Only original both-disabled named-gradient rule is accepted')
        return None
    need(set(value) == {'name', 'relative_l2', 'max_absolute', 'pass'}
         and finite(value['relative_l2']) and value['relative_l2'] >= 0
         and finite(value['max_absolute']) and value['max_absolute'] >= 0
         and type(value['pass']) is bool and value['pass'] == (value['relative_l2'] <= tolerance)
         and value['pass'], 'Original numeric metric failed')
    return value['relative_l2']


def numeric(configuration, summary, fixed, trajectory, status, reset):
    need(set(fixed) == {'gate', 'batches', 'pass', 'results'}
         and fixed['gate'] == 'A_fixed_batch_equivalence'
         and type(fixed['batches']) is int and fixed['batches'] == 20
         and fixed['pass'] is True and len(fixed['results']) == 20, 'Complete original20 gate required')
    maxima, none_count, gradient_names, receipts = [0.0, 0.0], 0, None, []
    for index, row in enumerate(fixed['results']):
        need(set(row) == {'batch', 'record_keys', 'input_receipt', 'forward', 'gradient', 'pass'}
             and type(row['batch']) is int and row['batch'] == index and row['pass'] is True,
             'Fixed-batch membership/order differs')
        receipt = row['input_receipt']
        need(type(receipt) is dict and sha(receipt.get('receipt_sha256'))
             and type(receipt.get('base_records')) is int and receipt['base_records'] > 0
             and type(receipt.get('native_atoms')) is int and receipt['native_atoms'] > 0
             and row['record_keys'] == receipt['record_keys']
             and len(row['record_keys']) == receipt['base_records'], 'Bound input receipt/count differs')
        receipts.append(receipt['receipt_sha256'])
        for position, (key, tolerance) in enumerate((('forward', 1e-5), ('gradient', 1e-4))):
            report = row[key]
            need(set(report) == {'pass', 'tolerance', 'tensors'} and report['pass'] is True
                 and type(report['tolerance']) is float and report['tolerance'] == tolerance
                 and type(report['tensors']) is list, 'Original relative-L2 rule differs')
            names = [x['name'] for x in report['tensors']]
            need(len(names) == len(set(names)) and names == sorted(names), 'Unique sorted names required')
            if key == 'forward':
                need(tuple(names) == OUTPUT_NAMES, 'Complete original8 output-port population differs')
            elif gradient_names is None:
                gradient_names = names
                need(len(names) == 329, 'Original6x512 full329 named-gradient population differs')
            else:
                need(names == gradient_names, 'Named-gradient population changed between batches')
            for item in report['tensors']:
                number = metric(item, tolerance, gradient=(key == 'gradient'))
                if number is None:
                    none_count += 1
                else:
                    maxima[position] = max(maxima[position], number)
    need(set(trajectory) == {'gate', 'updates', 'pass', 'results'}
         and trajectory['gate'] == 'A_500_update_loss_trajectory'
         and type(trajectory['updates']) is int and trajectory['updates'] == 500
         and trajectory['pass'] is True and len(trajectory['results']) == 500, 'Complete original500 gate required')
    trajectory_max = 0.0
    for index, row in enumerate(trajectory['results'], 1):
        need(set(row) == {'step', 'relative_difference', 'pass'}
             and type(row['step']) is int and row['step'] == index
             and finite(row['relative_difference']) and row['relative_difference'] >= 0
             and type(row['pass']) is bool and row['pass'] == (row['relative_difference'] <= 1e-3)
             and row['pass'], 'Original500 saved relative-loss gate failed')
        trajectory_max = max(trajectory_max, row['relative_difference'])
    need(reset['workers_closed_before_reset'] is True and reset['same_first_input_sha256'] == receipts[0]
         and type(reset['committed_state_after_reset_before_update']['committed_base_samples']) is int
         and reset['committed_state_after_reset_before_update']['committed_base_samples'] == 0,
         'Original worker-close/zero-committed reset/first trajectory input differs')
    need(summary['status'] == 'PAIRED_GATES_PASS'
         and all(summary[k] is True for k in ('full_A_numeric_acceptance', 'fixed_batch_pass', 'trajectory_pass'))
         and summary['configuration_sha256'] == configuration['configuration_sha256']
         and summary['candidate_options_sha256'] == configuration['candidate_options_sha256']
         and summary['code_sha'] == CODE and summary['prereg_sha'] == PUBLIC and summary['gpu_uuid'] == GPU
         and summary['input'] == 'native_s' and summary['smoke'] is False and summary['resume_supported'] is False
         and summary['fixed_input_receipts_sha256'] == canonical(receipts)
         and type(summary['consumed_trajectory_base_records']) is int and summary['consumed_trajectory_base_records'] > 0
         and summary['timing_kind'] == 'paired_two_resident_models_diagnostic_not_standalone_speed',
         'Saved actual R2 summary/input digest differs')
    need(status['status'] == 'PAIRED_GATES_PASS' and status['job_id'] == JOB and status['failure'] is None
         and status['cleanup_errors'] == [] and status['stream_cleanup'] == {'input_descriptors_closed': True, 'errors': []}
         and status['checkpoint_export'] is None and status['resume_supported'] is False
         and all(finite(status[k]) and status[k] >= 0 for k in
                 ('elapsed_seconds', 'scientific_elapsed_seconds', 'finalization_elapsed_seconds'))
         and status['elapsed_seconds'] <= 6900, 'Actual input/SDK finish/final cleanup failed')
    return dict(maximum_forward_relative_l2=maxima[0], maximum_gradient_relative_l2=maxima[1],
                maximum_trajectory_relative_difference=trajectory_max, both_disabled_gradient_records=none_count,
                consumed_trajectory_base_records=summary['consumed_trajectory_base_records'])


def configuration_check(cfg, refs):
    expected, old = bound(refs['candidate_options']), bound(refs['all_on_R2_configuration'])
    need(cfg['candidate'] == expected and all(type(expected[k]) is bool and expected[k] is v for k, v in
         (('distance_checkpointing', True), ('backbone_checkpointing', True), ('head_checkpointing', False))),
         'Exact manual head-off options required')
    original = deepcopy(old['candidate'])
    need(all(original[k] is True for k in ('distance_checkpointing', 'backbone_checkpointing', 'head_checkpointing')),
         'Original all-on source/data anchor differs')
    original['head_checkpointing'] = False
    need(expected == original, 'Candidate changed more than the head checkpoint option')
    for key in ('model', 'reference', 'optimizer', 'schedule', 'loss_policy', 'loss_weights', 'gradient_clip_norm',
                'dynamic_balancer', 'supervision', 'reference_configuration', 'a4_configuration'):
        need(cfg[key] == old[key], 'Original model/loss/optimizer/source identity differs: '+key)
    need(cfg['model']['backbone']['layers'] == 6 and cfg['model']['backbone']['dim'] == 512
         and cfg['job_id'] == JOB and cfg['node'] == NODE and cfg['gpu_uuid'] == GPU and '5090' in cfg['gpu_name']
         and cfg['code_sha'] == CODE and cfg['prereg_sha'] == PUBLIC and type(cfg['seed']) is int and cfg['seed'] == 0
         and cfg['input'] == 'native_s' and cfg['smoke'] is False and cfg['fixed_batches'] == 20
         and cfg['trajectory_updates'] == 500 and cfg['tracking_mode'] == 'offline'
         and cfg['downstream_data_read'] is False and cfg['original_lmdb_written'] is False
         and cfg['checkpoint_export']['requested'] is False and cfg['checkpoint_export']['destination'] is None,
         'Actual source/seed/full6x512/two-resident identity differs')
    data, prior = deepcopy(cfg['data_version']), deepcopy(old['data_version'])
    snapshot, old_snapshot = data.pop('original_shard_snapshot'), prior.pop('original_shard_snapshot')
    need(data == prior and snapshot['sha256'] == old_snapshot['sha256'] == refs['S_original_snapshot']['sha256']
         and snapshot['path'] == refs['S_original_snapshot']['path']
         and cfg['original_shard_snapshot_prejob_sha256'] == refs['S_original_snapshot']['sha256']
         and data['sampler']['max_padded_cost'] == 8000000 and data['sampler']['padded_cost_multiplier'] == 3
         and data['loader']['num_workers'] == 8 and data['input_kind'] == 'native_s' and data['seed'] == 0,
         'Original population/data/sampler/three-view/workers/8M binding differs')
    need(rawref(data['manifest_path'])['sha256'] == data['manifest_sha256'], 'Original small input manifest binding differs')
    need(cfg['candidate_options_sha256'] == refs['candidate_options']['sha256'], 'Candidate raw options binding differs')
    need(bound(refs['manual_execution']) == {'schema': 'model_v3_performance_execution_v1', 'checkpoint_policy': 'manual'}
         and cfg['performance_execution_request'] == refs['manual_execution'], 'Explicit manual request differs')
    execution = cfg['performance_execution']
    requested = execution['requested']
    need(execution['schema'] == 'model_v3_performance_execution_receipt_v1'
         and execution['resolved_options'] == expected and execution['selection'] is None
         and execution['scientific_acceptance'] is False and execution['OOM_fallback_or_unmeasured_capacity_claimed'] is False
         and requested['schema'] == 'model_v3_performance_execution_v1' and requested['checkpoint_policy'] == 'manual'
         and requested['resident_models'] == 2 and requested['capacity_profile'] is None and requested['padding'] is None
         and requested['batch_padded_cost'] == 8000000 and sha(requested['workload_sha256'])
         and execution['implementation_sha256'] == cfg['source_sha256'], 'Manual full implementation binding differs')
    controls, actual = cfg['deterministic_controls'], cfg['deterministic_controls']['actual']
    need(controls['schema'] == 'model_v3_deterministic_controls_v1' and controls['requested'] is True
         and controls['scope'] == 'both_reference_and_candidate' and controls['cuda_initialized_before_apply'] is False
         and controls['torch_imported_before_binding'] is False and actual['cublas_workspace_config'] == ':4096:8'
         and actual['cudnn_benchmark'] is False and actual['cudnn_deterministic'] is True
         and actual['deterministic_algorithms'] is True and actual['deterministic_warn_only'] is False
         and actual['matmul_tf32_before_role_context'] is False and actual['cudnn_tf32_before_role_context'] is False
         and actual['float32_matmul_precision_before_role_context'] == 'highest', 'Actual FP32 deterministic controls differ')
    body = deepcopy(cfg)
    need(body.pop('configuration_sha256') == canonical(body), 'Complete canonical configuration binding differs')


def publication_check(operations, pins, driver):
    need(operations['schema'] == 'model_v3_exact_tree_publication_actual_v1'
         and operations['repository_full_name'] == 'mint258/MFM' and operations['branch'] == 'model-v3'
         and operations['public_branch_readback_verified'] is True and operations['public_Git_API_tree_readback_verified'] is True
         and all(re.fullmatch('[0-9a-f]{40}', operations[k]) for k in ('local_code_sha', 'public_code_sha', 'tree_sha')),
         'Actual exact-tree method publication required')
    rows = {r['path']: r for r in operations['files']}
    need(len(rows) == len(operations['files']), 'Duplicate published member')
    files = {Path(r['path']).name: Path(r['path']) for r in pins['files']}
    files.update({'source_pins.json': S/'source_pins.json', 'Root_submit_v1.py': Path(driver['path'])})
    need(set(files) == {'METHODS_README.md', 'R1_registration_DRAFT.json', 'dependencies.json',
                        'run_head_off_R2.sbatch', 'source_pins.json', 'Root_submit_v1.py'}, 'Exact six published source leaves required')
    prefix = 'docs/model_v3/pre_registered_methods/performance_head_off_R2_v1/'
    for name, path in files.items():
        raw = path.read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        need(rows[prefix+name]['type'] == 'blob' and rows[prefix+name]['sha'] == blob, 'Published operation blob differs: '+name)


def validate_closed_gate(reference, *, require_current_sources=True):
    """Strict metadata R1 consumer; grants no single-resident capacity or speed claim."""
    proof = bound(reference)
    need(proof['schema'] == SCHEMA and proof['status'] == STATUS and proof['job_id'] == JOB
         and proof['code_sha'] == CODE and proof['public_prereg_sha'] == PUBLIC and proof['GPU_uuid'] == GPU
         and proof['layers'] == 6 and proof['H0_dim'] == 512 and proof['resident_models'] == 2
         and proof['fixed_batches'] == 20 and proof['trajectory_updates'] == 500
         and proof['manual_checkpoint_policy'] == 'manual' and proof['resolved_checkpoint_flags'] == FLAGS
         and proof['current_source_counts'] == {'full_tested': 2131, 'mandatory_saved': 305}
         and proof['all_current_source_maps_equal_saved'] is True and proof['private_cleanup_errors'] == []
         and proof['foreign_processes_signalled'] is False and proof['current_family_census_bytes'] <= proof['family_cap_bytes'] == WHOLE
         and proof['independent_SDK_or_online_sync_complete'] is False
         and proof['single_resident_R1_or_A5_or_ABBA_or_all_card_speed_acceptance'] is False,
         'Actual complete head-off R2 qualification required')
    need(rawref(__file__) == proof['closure_source'], 'This strengthened consumer requires its exact v2 closure producer')
    need(set(proof['artifact_refs']) == set(ARTIFACT_NAMES), 'Exact five R2 artifacts required')
    artifacts = {}
    for name, ref in proof['artifact_refs'].items():
        need(Path(ref['path']) == CHILD/name, 'Gate artifact path differs')
        artifacts[name] = bound(ref)
    for key in ('supervisor', 'submission', 'source_package', 'operations_publication'):
        bound(proof[key])
    numbers = numeric(artifacts['configuration.json'], artifacts['summary.json'], artifacts['fixed_batch_gate.json'],
                      artifacts['trajectory_gate.json'], artifacts['run_status.json'], bound(proof['stream_reset']))
    need(all(proof[k] == v for k, v in numbers.items()), 'Closed metrics differ from actual gate scalars')
    row = proof['actual_sacct']['stdout'].strip().split('|')
    need(proof['actual_sacct']['returncode'] == 0 and len(row) == 7
         and row[:4] == [JOB, 'zixiao', 'COMPLETED', '0:0'] and row[5:] == ['16', NODE], 'Actual R2 accounting missing')
    if require_current_sources:
        pins = bound(proof['source_package'])
        for item in pins['files']:
            need(rawref(item['path']) == projection(item), 'Source package changed')
        refs = bound(next(x for x in pins['files'] if Path(x['path']).name == 'dependencies.json'))['raw_refs']
        for ref in refs.values():
            need(rawref(ref['path']) == projection(ref), 'Bound dependency changed')
        configuration_check(artifacts['configuration.json'], refs)
        full = bound(refs['packaging_Root_closure'])['full_current_source_map']
        need(len(full) == 2131, 'Tested source scope differs')
        for path, expected in full.items():
            need(rawref(path)['sha256'] == expected, 'Current complete source drift')
        for path, expected in artifacts['configuration.json']['source_sha256'].items():
            need(rawref(W/path)['sha256'] == expected, 'Saved implementation source drift')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    cli = parser.parse_args()
    need(os.getuid() == 1278 and socket.gethostname().split('.')[0] == 'sonmi'
         and not os.environ.get('SLURM_JOB_ID'), 'Root login metadata execution only')
    own = rawref(__file__)
    need(sha(cli.source_sha256) and own['sha256'] == cli.source_sha256, 'Explicit closure source SHA differs')
    output = cli.output.absolute()
    need(output.parent == N and not output.exists() and not output.is_symlink()
         and output.name.endswith('.json'), 'Fresh independent N metadata output required')
    git = {}
    for label, args, expected in [('code', ['rev-parse', 'HEAD'], CODE), ('tree', ['rev-parse', 'HEAD^{tree}'], TREE),
                                  ('clean', ['status', '--porcelain=v1', '--untracked-files=all'], '')]:
        observed = command([str(O/'cpu_git_tools_v1/bin/git'), '-C', str(W), *args])
        need(observed['stdout'].strip() == expected, 'Exact clean tested code/tree required')
        git[label] = observed
    submission, submission_ref = read(CONTROL/'Root_submission_actual_v1.json')
    need(submission['schema'] == 'model_v3_head_off_R2_Root_single_submission_v1'
         and submission['status'] == 'SUBMITTED' and submission['job_id'] == JOB
         and submission['automatic_retry'] is False and submission['GPU_GRES_isolation_claimed'] is False,
         'Actual unambiguous head-off submission required')
    pins = bound(submission['source_package'])
    need(Path(submission['source_package']['path']) == S/'source_pins.json' and len(pins['files']) == 4,
         'Original five-leaf head-off package required')
    for item in pins['files']:
        need(rawref(item['path']) == projection(item), 'Frozen operation leaf differs')
    refs = bound(next(x for x in pins['files'] if Path(x['path']).name == 'dependencies.json'))['raw_refs']
    for ref in refs.values():
        need(rawref(ref['path']) == projection(ref), 'Frozen dependency differs')
    need(rawref(submission['Root_driver']['path']) == submission['Root_driver'], 'Submitted Root driver drift')
    need(rawref(submission['installed_sbatch']['path']) == submission['installed_sbatch']
         and submission['installed_sbatch']['sha256'] == rawref(S/'run_head_off_R2.sbatch')['sha256'], 'Installed wrapper differs')
    publication_check(bound(submission['operations_publication']), pins, submission['Root_driver'])
    qa, pack, public = bound(refs['CPU_99_Root_closure']), bound(refs['packaging_Root_closure']), bound(refs['publication'])
    need(qa['status'] == 'ACTUAL_C0_99_TESTS_FOUR_GROUPS_AND_REPOSITORY_CHECKER'
         and qa['counts'] == {'tests': 99, 'passed': 99, 'failures': 0, 'errors': 0, 'skipped': 0}
         and pack['status'] == 'ACTUAL_C0_METADATA_ATTRIBUTE_ONLY_MODEL13_SOURCES_AND99_TESTS_PRESERVED'
         and pack['CPU_99_test_closure'] == refs['CPU_99_Root_closure']
         and (public['local_code_sha'], public['public_commit_sha'], public['tree_sha']) == (CODE, PUBLIC, TREE)
         and public['actual_readback']['model-v3-performance-integration-20261027-v1'] == PUBLIC
         and public['actual_public_git_tree'] == TREE, 'Actual tested/public runtime closure differs')
    full = pack['full_current_source_map']
    need(type(full) is dict and len(full) == 2131, 'Exact full tested2131 source map required')
    for path, expected in full.items():
        need(sha(expected) and rawref(path)['sha256'] == expected, 'Current full tested source differs')
    artifacts, artifact_refs = {}, {}
    for name in ARTIFACT_NAMES:
        artifacts[name], artifact_refs[name] = read(CHILD/name)
    cfg = artifacts['configuration.json']
    configuration_check(cfg, refs)
    need(len(cfg['source_sha256']) == 305, 'Exact mandatory305 producer source scope required')
    for path, expected in cfg['source_sha256'].items():
        need(sha(expected) and rawref(W/path)['sha256'] == expected and full[str(W/path)] == expected,
             'Producer/full-tested source projection differs')
    reset, reset_ref = read(CHILD/'stream_reset.json')
    numbers = numeric(cfg, artifacts['summary.json'], artifacts['fixed_batch_gate.json'],
                      artifacts['trajectory_gate.json'], artifacts['run_status.json'], reset)
    admission, quota, hold = bound(submission['admission']), bound(submission['quota']), bound(submission['hold'])
    need(admission['schema'] == 'model_v3_head_off_R2_Root_actual_admission_v1'
         and admission['authority'] == quota['authority'] == hold['authority'] == 'ROOT_ACTUAL'
         and admission['node'] == NODE and admission['gpu_uuid'] == GPU and admission['cpus'] == 16
         and admission['requested_memory_MiB'] == 65536
         and admission['prior_commitment_MiB'] == max(admission['prior_all_user_declared_MiB'], admission['prior_AllocMem_MiB'])
         and admission['prior_commitment_MiB']+65536 < .85*admission['RealMemory_MiB']
         and admission['MemAvailable_MiB'] >= 65536+.15*admission['RealMemory_MiB']
         and admission['selected_compute_processes'] == [] and admission['UUID_lock_checked_and_released'] is True
         and admission['quota'] == submission['quota'] and admission['hold'] == submission['hold']
         and quota['hold'] == submission['hold'] and quota['additional_reserve_bytes'] == 64 << 30
         and quota['available_bytes'] >= quota['remaining_all_registered_bytes']+(64 << 30)
         and hold['reserved_additional_bytes'] == WHOLE and hold['Native_S_principal_or_counters_changed'] is False,
         'Actual original all-user85%/MemAvailable/quota/hold admission differs')
    need(submission['argv'] == ['sbatch', '--parsable', '--partition=all', '--nodelist='+NODE, '--cpus-per-task=16',
         '--mem=65536M', '--time=02:00:00', '--output='+str(CONTROL/'slurm_%j.log'), submission['installed_sbatch']['path']],
         'Actual original Slurm request differs')
    env = submission['bindings']
    for key, ref in [('MODEL_V3_ROOT_ADMISSION', submission['admission']), ('MODEL_V3_QUOTA', submission['quota']),
                     ('MODEL_V3_HOLD', submission['hold']), ('MODEL_V3_METHOD_PUBLICATION', submission['operations_publication'])]:
        need(env[key+'_PATH'] == ref['path'] and env[key+'_SHA256'] == ref['sha256'], 'Wrapper raw environment differs')
    need(env['MODEL_V3_OUT'] == str(CHILD) and env['MODEL_V3_RECORD'] == str(FAMILY/'supervisor.json')
         and env['MODEL_V3_GPU_UUID'] == GPU and env['MODEL_V3_EXPECTED_NODE'] == NODE
         and env['MODEL_V3_PACKAGE_PINS_SHA256'] == submission['source_package']['sha256'], 'Wrapper output/source/GPU binding differs')
    accounting = terminal()
    sup, sup_ref = read(FAMILY/'supervisor.json')
    invocation, ident = cfg['performance_execution_invocation'], sup['launch_identity']
    expected_child = [invocation['logical_python'], '-u', '-B', *invocation['argv']]
    argv_bytes = b'\0'.join(x.encode() for x in expected_child)+b'\0'
    need(invocation['cwd'] == invocation['source_root'] == str(W) and sup['status'] == 'COMPLETED'
         and sup['exit_code'] == 0 and sup['job_id'] == JOB and sup['first_failure'] is None and sup['retirement'] is None
         and sup['remaining_recorded_processes_before_retirement'] == [] and sup['private_storage_cleanup_errors'] == []
         and sup['foreign_gpu_processes_signalled'] is False and sup['gpu_uuid'] == GPU
         and sup['output_budget_bytes'] == WHOLE and sup['child_output_budget_bytes'] == WHOLE-(96 << 20)
         and finite(sup['elapsed_seconds']) and 0 < sup['elapsed_seconds'] <= 6900
         and sup['supervisor_source_sha256'] == refs['supervisor_source']['sha256']
         and sup['command'] == ident['argv'] == expected_child and ident['uid'] == 1278 and ident['status'] == 'ACTIVE'
         and ident['slurm_job_id'] == JOB and ident['pid'] == ident['pgid'] == ident['sid']
         and ident['argv_sha256'] == hashlib.sha256(argv_bytes).hexdigest()
         and ident['cgroup'] == sup['supervisor_slurm_cgroup'] and '/uid_1278/job_'+JOB+'/' in ident['cgroup'],
         'Actual supervisor/child identity/cleanup/budgets differ')
    args = invocation['argv']
    need(args[0] == 'tools/model_v3/paired_a_acceptance.py', 'Original paired producer entry required')
    for key, expected in [('--candidate-options', 'current/configs/model_v3/performance/a03_head_off.json'),
                          ('--performance-execution', 'current/configs/model_v3/performance/a1_manual_capacity_observation_v1.json'),
                          ('--performance-execution-sha256', refs['manual_execution']['sha256']), ('--input', 'native_s'),
                          ('--seed', '0'), ('--workers', '8'), ('--max-padded-cost', '8000000'), ('--expected-gpu', '5090'),
                          ('--code-sha', CODE), ('--prereg-sha', PUBLIC), ('--output', str(CHILD))]:
        need(args.count(key) == 1 and args[args.index(key)+1] == expected, 'Actual producer CLI differs: '+key)
    need(args.count('--deterministic-controls') == 1 and '--smoke' not in args
         and '--export-candidate-checkpoint' not in args, 'Full deterministic non-export invocation required')
    private = sup['private_storage_final']
    need(private['first_sampling_failure'] is None and private['budget_bytes'] == WHOLE
         and private['sampled_max_bytes'] <= WHOLE and private['last']['bytes'] <= WHOLE, 'Private sample/finalization failed')
    storage, storage_ref = read(FAMILY/'supervisor.json.storage.json')
    declared_storage = deepcopy(cfg['private_storage_bindings'])
    need(declared_storage.pop('receipt_path') == storage_ref['path']
         and declared_storage.pop('receipt_sha256') == storage_ref['sha256']
         and storage == declared_storage and storage['job_id'] == JOB and storage['uid'] == 1278
         and storage['node'] == NODE and storage['private_storage_budget_bytes'] == WHOLE, 'Private receipt binding differs')
    # This is the resource-only monitor journal, not either scientific history.
    resource = FAMILY/'supervisor.json.jsonl'
    before = resource.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 1278 and before.st_nlink == 1
         and before.st_size <= 32 << 20, 'Bounded owned resource journal required')
    samples = peak_rss = peak_output = peak_gpu = 0
    digest = hashlib.sha256()
    with resource.open('rb') as stream:
        for line in stream:
            need(len(line) <= 1 << 20 and samples < 10000, 'Resource journal line/count cap')
            digest.update(line)
            row = json.loads(line, object_pairs_hook=pairs)
            gpu = row['gpu']
            need(type(gpu['total_bytes']) is int and gpu['total_bytes'] > 0
                 and type(gpu['compute_processes']) is list,
                 'Unknown/nonpositive GPU capacity cannot close resources')
            for process in gpu['compute_processes']:
                need(type(process) is dict and type(process['own']) is bool
                     and type(process['used_memory_bytes']) is int and process['used_memory_bytes'] >= 0,
                     'Unknown/invalid NVML process ownership or bytes: resources HOLD')
            need(gpu['foreign_processes'] == [x for x in gpu['compute_processes'] if x['own'] is False],
                 'Foreign-process population differs from typed ownership')
            own_gpu = sum(x['used_memory_bytes'] for x in gpu['compute_processes'] if x['own'] is True)
            need(finite(row['elapsed_seconds']) and 0 <= row['elapsed_seconds'] < 6870
                 and row['processes']['rss_sum_bytes'] <= RSS and row['output_bytes'] <= WHOLE-(16 << 20)
                 and gpu['uuid'] == GPU and gpu['foreign_processes'] == [] and own_gpu <= .85*gpu['total_bytes']
                 and row['private_storage']['first_sampling_failure'] is None, 'Sampled wall/RSS/output/GPU/private guard differs')
            samples += 1
            peak_rss = max(peak_rss, row['processes']['rss_sum_bytes'])
            peak_output = max(peak_output, row['output_bytes'])
            peak_gpu = max(peak_gpu, own_gpu)
    after = resource.lstat()
    need(samples > 0 and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Resource journal unstable/empty')
    resource_ref = dict(path=str(resource), bytes=before.st_size, sha256=digest.hexdigest())
    monitor_path = W/'tools/model_v3/runtime_monitor.py'
    monitor_ref = rawref(monitor_path)
    need(monitor_ref['sha256'] == full[str(monitor_path)], 'Original output census source differs')
    spec = importlib.util.spec_from_file_location('head_off_R2_original_metadata_census', monitor_path)
    monitor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    child_bytes, control_bytes = monitor.owned_output_bytes(CHILD), monitor.owned_output_bytes(CONTROL)
    external, external_bytes = [], 0
    for path in sorted(FAMILY.iterdir()):
        if path in (CHILD, CONTROL):
            continue
        st = path.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_uid == 1278 and st.st_nlink == 1
             and not path.is_symlink(), 'Only ordinary disjoint family sidecars allowed')
        external_bytes += st.st_size
        external.append(dict(path=str(path), bytes=st.st_size))
    total = child_bytes+control_bytes+external_bytes+private['last']['bytes']+(2 << 20)
    need(total <= WHOLE, 'Whole family plus private final snapshot/closure allowance exceeds2GiB')
    for path, before_ref in list(SEEN.items()):
        need(rawref(path, remember=False) == before_ref, 'Final source/metadata binding drift')
    need(not any(x == blocked or x.startswith(blocked+'.') for blocked in
                 ('torch', 'numpy', 'wandb', 'rdkit', 'phychem_mfm') for x in sys.modules), 'Scientific imports forbidden')
    result = dict(schema=SCHEMA, status=STATUS, actual_unix=time.time(), job_id=JOB, actual_sacct=accounting,
                  code_sha=CODE, public_prereg_sha=PUBLIC, GPU_uuid=GPU, layers=6, H0_dim=512, resident_models=2,
                  fixed_batches=20, trajectory_updates=500, manual_checkpoint_policy='manual', resolved_checkpoint_flags=FLAGS,
                  **numbers, current_source_counts=dict(full_tested=2131, mandatory_saved=305), all_current_source_maps_equal_saved=True,
                  current_family_census_bytes=total, family_cap_bytes=WHOLE, private_cleanup_errors=[], foreign_processes_signalled=False,
                  single_resident_R1_or_A5_or_ABBA_or_all_card_speed_acceptance=False,
                  automatic_optimality_or_new_runtime_training_capacity_claimed=False, independent_SDK_or_online_sync_complete=False,
                  formal_FP32_physics_or_D5_or_B_or_recipe_accepted=False, artifact_refs=artifact_refs, supervisor=sup_ref,
                  submission=submission_ref, source_package=submission['source_package'], operations_publication=submission['operations_publication'],
                  closure_source=own, stream_reset=reset_ref, current_Git=git,
                  original_initial_state_control='Bound original paired producer checks every state_dict tensor before configuration; Root reads no model state',
                  source_data_anchor_role='3976 all-on supplies identical code/data/options only; the4580 numeric gates are checked independently',
                  saved_numeric_scope='All20 saved8-output/329-named-gradient records and500 relative-loss records; no independent journal loss recomputation',
                  current_census=dict(child_bytes=child_bytes, control_bytes=control_bytes, family_sidecars=external,
                      family_sidecar_bytes=external_bytes, private_final_snapshot_bytes=private['last']['bytes'],
                      new_closure_allowance_bytes=2 << 20, original_census_source=monitor_ref, private_peak_exact=False),
                  sampled_resources=dict(samples=samples, maximum_rss_bytes=peak_rss, maximum_output_bytes=peak_output,
                      maximum_own_gpu_bytes=peak_gpu, original_resource_journal=resource_ref, wall_seconds=6900,
                      RSS_limit_bytes=RSS, private_limit_bytes=WHOLE, no_foreign_GPU_observed_in_samples=True,
                      no_exact_continuous_peak_claimed=True), raw_source_metadata_refs=list(SEEN.values()),
                  SDK_or_scientific_journal_or_model_or_array_opened=False)
    raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    need(len(raw) <= 2 << 20, 'Small metadata closure bound exceeded')
    with output.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(dict(status=STATUS, closure=rawref(output), job_id=JOB), sort_keys=True))


if __name__ == '__main__':
    main()
