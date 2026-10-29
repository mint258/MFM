#!/usr/bin/env python3
"""Root metadata-only closure for the actual Native seed0/fp32/20k panel.

No model/test/Torch/NumPy/WandB import, tensor/payload/SDK/target read, mutation,
reservation release, sync, submission or cancellation. Root runs this source.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

B = Path('/share/home/zixiao/descriptor_analysis')
N = B/'runs/model_v3_20261026'
DEFAULT_BASE = N/'Native_S20000_seed0_fp32_dev9_auto_v1/panel'
JOB = '4525060'
LIMIT = 2 << 30
META = 2 << 20
DATASETS = ('cyp_isoform', 'expansionrx', 'qm9')
TASKS = {'cyp.3A4','cyp.2D6','exp.LogD','exp.LogS','exp.Log_HLM_CLint','qm9.U0','qm9.homo','qm9.lumo','qm9.alpha'}
FORBIDDEN = ('torch','numpy','wandb','phychem_mfm')


def need(value, reason):
    if not value:
        raise ValueError(reason)


def clean_imports():
    need(not any(key == prefix or key.startswith(prefix+'.') for prefix in FORBIDDEN for key in sys.modules),
         'Metadata closure imported a forbidden scientific/SDK namespace')


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def ordinary(path):
    path = Path(path).absolute()
    need('..' not in path.parts and not path.is_symlink(), 'Ordinary unaliased path required')
    value = path.lstat()
    need(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid() and value.st_nlink == 1,
         'Owned ordinary single-link file required: '+str(path))
    return path, value


class Book:
    def __init__(self):
        self.refs = {}
        self.stats = {}

    def ref(self, path, *, expected=None, maximum=META):
        path, before = ordinary(path)
        need(path.suffix.lower() not in {'.pt','.npz','.npy','.bin','.wandb','.pkl','.pickle'},
             'Payload/array/native SDK bytes are outside Root metadata scope')
        need(path.suffix != '.jsonl', 'Root journal bodies are explicitly forbidden')
        need(0 <= before.st_size <= maximum, 'Metadata/source size limit: '+str(path))
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                h.update(block)
        after = path.stat()
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), 'Metadata changed during read')
        ref = {'path':str(path),'bytes':before.st_size,'sha256':h.hexdigest()}
        if expected is not None:
            need(ref['path'] == expected['path'] and ref['sha256'] == expected['sha256']
                 and ('bytes' not in expected or ref['bytes'] == expected['bytes']), 'Raw reference differs: '+str(path))
        old = self.refs.get(str(path))
        need(old is None or old == ref, 'Input changed during Root closure')
        self.refs[str(path)] = ref
        return ref

    def json(self, path, *, expected=None):
        ref = self.ref(path, expected=expected)
        def pairs(items):
            result = {}
            for key,value in items:
                need(key not in result, 'Duplicate JSON key')
                result[key] = value
            return result
        def bad(_):
            raise ValueError('Nonfinite JSON metadata')
        raw = Path(path).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Metadata changed before parse')
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)

    def bound(self, ref):
        return self.json(ref['path'], expected=ref)

    def opaque_stat(self, path, *, expected_bytes=None):
        path, value = ordinary(path)
        need(value.st_size > 0 and (expected_bytes is None or value.st_size == expected_bytes), 'Opaque artifact size differs')
        record = {'path':str(path),'bytes':value.st_size,'inode':value.st_ino,'mtime_ns':value.st_mtime_ns,
            'uid':value.st_uid,'nlink':value.st_nlink,'read_kind':'STAT_ONLY_NO_CONTENT_OR_SHA_READ'}
        self.stats[str(path)] = record
        return record

    def finish(self):
        # Repeat only the explicitly bounded metadata/source refs. Never recurse
        # data roots, open H0 tensors, or convert producer SHA into a Root SHA.
        for ref in list(self.refs.values()):
            self.ref(ref['path'], expected=ref, maximum=max(META,ref['bytes']))
        for path,old in self.stats.items():
            _, value = ordinary(path)
            need((value.st_size,value.st_ino,value.st_mtime_ns) ==
                 (old['bytes'],old['inode'],old['mtime_ns']), 'Opaque artifact changed during Root stat closure')


def equal_ref(left, right, *, state_key=None):
    need(left['path'] == right['path'] and left['sha256'] == right['sha256']
         and ('bytes' not in left or left['bytes'] == right['bytes']), 'Semantic reference path/SHA/bytes differ')
    if state_key is not None:
        need(left.get('state_key') == state_key, 'Checkpoint state-key differs')


def source_refs(value, book):
    """Recheck explicit Python implementation refs, never artifact refs."""
    if isinstance(value, dict):
        if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str) and Path(value['path']).suffix == '.py':
            book.ref(value['path'],expected=value)
        for child in value.values():
            source_refs(child,book)
    elif isinstance(value,list):
        for child in value:
            source_refs(child,book)

def load_metadata_module(reference, name, book):
    book.ref(reference['path'], expected=reference)
    spec = importlib.util.spec_from_file_location(name, reference['path'])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    clean_imports()
    return module


def fresh_sacct(job, node):
    argv = ['sacct','-X','-n','-P','-j',job,
        '--format=JobIDRaw,User,State,ExitCode,AllocCPUS,NodeList,ElapsedRaw,Submit,Start,End']
    before = time.time()
    raw = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    receipt = {'argv':argv,'started_unix':before,'completed_unix':time.time(),
        'returncode':raw.returncode,'stdout':raw.stdout,'stderr':raw.stderr}
    need(raw.returncode == 0 and raw.stderr == '', 'Fresh accounting capture failed')
    names = argv[-1].split('=',1)[1].split(',')
    rows = [dict(zip(names,line.split('|'))) for line in raw.stdout.splitlines() if line.strip()]
    parents = [r for r in rows if r.get('JobIDRaw') == job]
    need(len(parents) == 1, 'One exact actual Slurm parent required')
    row = parents[0]
    need(row['User'] == 'zixiao' and row['State'] == 'COMPLETED' and row['ExitCode'] == '0:0'
         and row['AllocCPUS'] == '16' and row['NodeList'] == node
         and 0 < int(row['ElapsedRaw']) <= 3600, 'Actual parent C0/UID/CPU/node/inclusive allocation budget differs')
    return receipt, row


def identity(value, command, job, cgroup):
    need(value['status'] == 'ACTIVE' and value['uid'] == 1278 and str(value['slurm_job_id']) == job
         and value['argv'] == command and value['cgroup'] == cgroup,
         'Recorded owned kernel launch identity differs')
    need(all(type(value[k]) is int and value[k] > 0 for k in ('pid','pgid','sid','start_ticks'))
         and value['pid'] == value['pgid'] == value['sid']
         and re.fullmatch(r'[0-9a-fA-F-]{36}',value['boot_id'])
         and '/job_'+job+'/' in cgroup, 'Kernel UID/boot/start/group/cgroup binding differs')
    expected = hashlib.sha256(b'\0'.join(x.encode('utf-8','surrogateescape') for x in command)+b'\0').hexdigest()
    need(value['argv_sha256'] == expected, 'Recorded argv SHA differs')


def guard_command(command, spec, admission_ref, spec_ref, guard_dir, *, child):
    need(command[:4] == [spec['python_entry'],'-u','-B',spec['external_guard']['path']],
         'Actual guard interpreter/source differs')
    arguments = list(command[4:])
    if child:
        need(arguments and arguments[-1] == '--child', 'Actual owned evaluation child discriminator missing')
        arguments.pop()
    expected = {'--spec':spec_ref['path'],'--spec-sha256':spec_ref['sha256'],'--node':spec['node'],
        '--gpu-uuid':spec['gpu_uuid'],'--root-admission':admission_ref['path'],
        '--root-admission-sha256':admission_ref['sha256'],'--guard-output':str(guard_dir)}
    need(len(arguments) == 2*len(expected), 'Unexpected guard command arguments')
    observed = {}
    for index in range(0,len(arguments),2):
        key = arguments[index]
        need(key not in observed, 'Repeated guard argument')
        observed[key] = arguments[index+1]
    need(observed == expected, 'Actual owned guard request/admission arguments differ')

def close(base):
    clean_imports()
    need(os.getuid() == 1278 and base == DEFAULT_BASE and not base.is_symlink(), 'Explicit actual Native20000 Root scope required')
    book = Book()
    closer_source = book.ref(__file__)
    control, guard_dir = base/'control', base/('guard_'+JOB)
    submission = book.json(control/'Root_submission_attempt001.json')
    need(submission['schema'] == 'native_S20000_panel_auto_Root_submission_v1'
         and submission['status'] == 'SUBMITTED' and submission['job_id'] == JOB
         and submission['actual_sbatch']['returncode'] == 0
         and submission['actual_sbatch']['stdout'].strip().split(';',1)[0] == JOB
         and submission['automatic_retry'] is False, 'Actual unique20k submission differs')
    spec = book.bound(submission['spec'])
    admission = book.bound(submission['admission'])
    request = book.bound(spec['request'])
    result = book.json(Path(request['output_root'])/'result.json')
    guard = book.json(guard_dir/'guard_result.json')
    sup = book.json(base/('supervisor_'+JOB+'.json'))
    cpu_binding = submission['CPU_preparation'];cpu_ref = cpu_binding['receipt']
    cpu_result = book.bound(cpu_ref);cpu_sup = book.bound(cpu_binding['supervisor'])
    need(cpu_result['status'] == 'CPU_PREPARED_FULL9_NATIVE20K_SOURCE_AND_PAYLOAD_CHECKS_COMPLETED'
         and cpu_result['actual_job_id'] == str(cpu_sup['job_id']) == '4525059'
         and cpu_result['prepared_spec'] == submission['spec']
         and cpu_result['source_before'] == cpu_result['source_after']
         and type(cpu_result['source_before']) is dict
         and cpu_result['payload_SHA_checked_by_allocated_CPU'] is True
         and cpu_result['Root_login_payload_read'] is False,
         'Actual5059 source/payload CPU preparation required')
    need(cpu_sup['status'] == 'COMPLETED' and cpu_sup['exit_code'] == 0 and cpu_sup['first_failure'] is None
         and cpu_sup['remaining'] == [] and cpu_sup['gpu_initialization_permitted'] is False
         and cpu_sup['private_storage']['first_sampling_failure'] is None
         and cpu_sup['private_storage']['budget_bytes'] == LIMIT
         and cpu_sup['command'] == cpu_result['actual_argv'], 'Actual5059 CPU supervisor/cleanup differs')
    saved_cpu = cpu_binding['actual_sacct'];saved_cpu_rows = [line.split('|') for line in saved_cpu['stdout'].splitlines() if line.strip()]
    need(len(saved_cpu_rows) == 1 and len(saved_cpu_rows[0]) == 7
         and saved_cpu_rows[0][:4] == ['4525059','zixiao','COMPLETED','0:0']
         and saved_cpu_rows[0][5] == '16' and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',saved_cpu_rows[0][6]),
         'Original actual CPU preparation accounting differs')
    cpu_fresh,cpu_parent = fresh_sacct('4525059',saved_cpu_rows[0][6])
    need(int(cpu_parent['ElapsedRaw']) <= 900 and cpu_sup['elapsed_seconds'] < 900,'Original CPU900s budget differs')
    for path,sha in cpu_result['source_before'].items():
        need(book.ref(path)['sha256'] == sha,'CPU source-before/after/current source differs')
    for path,sha in cpu_sup['sources_sha256'].items():
        need(book.ref(path)['sha256'] == sha,'Original actual CPU supervisor source differs')
    need(cpu_result['inline_metadata_controls'] == {'actual_QA_or_GPU_claimed':False,'negative_controls':11,
         'positive_controls':3,'scope':'INLINE_SYNTHETIC_METADATA_ONLY','separate_QA_parent_claimed':False},
         'Original14 actual CPU inline controls differ')
    need(spec['schema'] == 'model_v3_native_S_dev9_external_launch_v1'
         and spec['output_base'] == str(base) and spec['code_sha'] == '17f975bb094c9c3ec010d7f8134c5700adcc85e4'
         and spec['producer_code_sha'] == '3d9b1cc0c580dacc9398a5570b0c2fff3e257618'
         and spec['preregistration_sha'] == request['preregistration_sha'] == '39cf4929299cd227a3c361183a4b26c8b1405900'
         and spec['expected_tasks'] == 9 and spec['expected_comparison_cells'] == 18
         and spec['fresh_cache_required'] is True and spec['formal_pretraining_complete'] is False
         and spec['architecture_selection_claimed'] is False, 'Frozen Native/source/panel scope differs')
    need(spec['maximum_child_wall_seconds'] == 3500 and spec['maximum_process_group_rss_bytes'] == 28 << 30
         and spec['maximum_output_and_cache_bytes'] == LIMIT and spec['requested_memory_bytes'] is None and spec['software_memory_budget_bytes'] == 32 << 30
         and spec['Slurm_memory_mode'] == 'automatic_default'
         and spec['total_allocation_target_seconds'] == 3600 and spec['maximum_global_gpu_memory_fraction'] == .85,
         'Original runtime/resource budgets changed')
    equal_ref(admission['spec'],submission['spec'])
    equal_ref(admission['actual_sbatch'],spec['prepared_sbatch'])
    script = Path(spec['prepared_sbatch']['path'])
    book.ref(script,expected=spec['prepared_sbatch'])
    text = script.read_text()
    for token in ('#SBATCH --cpus-per-task=16','#SBATCH --time=01:00:00',
        '--rss-limit-bytes 30064771072 --wall-seconds 3590','--output-budget-bytes 2147483648',
        '--private-storage-budget-bytes 2147483648'):
        need(token in text, 'Actual wrapper budget differs: '+token)
    need(not re.search(r'^#SBATCH\s+--(?:mem|exclusive)',text,re.M), 'Automatic Slurm memory wrapper must not request fixed/zero/exclusive memory')
    module = load_metadata_module(spec['native_admission_implementation'],'native_S20000_Root_metadata_admission',book)
    # This helper is stdlib-only and revalidates the actual full CPU/public/source
    # graph, including metadata/JUnit and fixed Git metadata. Its native_admission,
    # same_reference and guard verify_sources functions are deliberately NOT called:
    # they hash payload.pt, outside this Root closer's stat-only role.
    bridge = module.bridge_admission(spec['bridge_validation'])
    clean_imports()
    need(bridge['evaluation_code_sha'] == spec['code_sha'] and bridge['public_code_sha'] == spec['public_code_sha']
         and bridge['tree_sha'] == spec['bridge_tree_sha'], 'Actual tested/public bridge identity differs')
    need(cpu_result['source_before'] == cpu_result['source_after'], 'CPU operational source maps differ')
    for path,sha in bridge['source_inventory'].items():
        need(book.ref(path,maximum=16 << 20)['sha256'] == sha, 'Current full tested source graph differs: '+path)
    for row in request['source_files']:
        path = Path(spec['repository_root'])/row['path']
        need(path.resolve().is_relative_to(Path(spec['repository_root']).resolve())
             and book.ref(path)['sha256'] == row['sha256'], 'Current evaluator source differs')
    for key in ('external_guard','external_preparer','native_admission_implementation','runtime_monitor',
        'Root_resource_guard_source','supervisor_source','protected_dependencies','sbatch_template'):
        book.ref(spec[key]['path'],expected=spec[key])
    for row in book.bound(spec['protected_dependencies'])['files']:
        book.ref(row['path'],expected=row)
    for row in spec['identity_dependencies'].values():
        book.ref(row['path'],expected=row)
    sys.path.insert(0,str(Path(spec['Root_resource_guard_source']['path']).parent))
    auto = load_metadata_module(spec['Root_resource_guard_source'],'Native20k_Root_auto_metadata',book)
    need(auto.verify_sources() == spec['operations_source_pins'] == submission['source_pins'], 'Actual0324 operations package differs')
    auto.verify_publication(spec['method_publication'])
    pins = book.bound(spec['operations_source_pins']);ops_root = Path(spec['operations_source_pins']['path']).parent
    expected_cpu_map = {str(ops_root/item['relative_path']):item['sha256'] for item in pins['files']}
    expected_cpu_map[spec['operations_source_pins']['path']] = spec['operations_source_pins']['sha256']
    for item in book.bound(pins['dependencies'])['files']:
        expected_cpu_map[item['path']] = item['sha256'];book.ref(item['path'],expected=item)
    need(cpu_result['source_before'] == expected_cpu_map, 'Complete exact operational CPU source map differs')
    immutable = book.bound(submission['immutable_GPU_submission_binding'])
    need(immutable['status'] == 'SUBMITTED' and immutable['job_id'] == JOB
         and immutable['actual_sbatch'] == submission['actual_sbatch'] and immutable['spec'] == submission['spec'],
         'Original immutable actual GPU budget/submission binding differs')
    need(guard['schema'] == 'model_v3_native_S_panel_guard_result_v1' and guard['status'] == 'COMPLETED'
         and guard['child_returncode'] == 0 and guard['job_id'] == JOB
         and guard['request_sha256'] == spec['request']['sha256']
         and guard['spec_sha256'] == submission['spec']['sha256'], 'Actual guard failed/scope differs')
    book.ref(guard['result']['path'],expected=guard['result'])
    need(guard['source'] == spec['external_guard'] and guard['code_sha'] == spec['code_sha']
         and guard['producer_code_sha'] == spec['producer_code_sha']
         and guard['node'] == spec['node'] and guard['gpu_uuid'] == spec['gpu_uuid'], 'Actual source/hardware binding differs')
    need(guard['inline_metadata_controls'] == {'actual_QA_or_GPU_claimed':False,'negative_controls':11,
         'positive_controls':3,'scope':'INLINE_SYNTHETIC_METADATA_ONLY','separate_QA_parent_claimed':False},
         'Actual inline metadata controls differ')
    worker = guard['worker_admission'];assessment = worker['assessment'];root_frame = admission['Root_resources']
    need(worker['origin'] == 'ACTUAL_WORKER_LIVE_SCHEDULER_AND_MEMAVAILABLE'
         and worker['Slurm_memory_mode'] == 'automatic_default' and worker['fixed_memory_allocation_claimed'] is False
         and all(type(age) in (int,float) and math.isfinite(age) and 0 <= age <= 120 for age in worker['Root_frame_ages'].values())
         and worker['current_GPU']['gpu_uuid'] == spec['gpu_uuid'] and worker['current_GPU']['foreign_applications'] == [],
         'Actual live worker auto admission/GPU/freshness differs')
    need(root_frame['schema'] == 'native_S_panel_auto_Root_resource_frame_v1'
         and root_frame['origin'] == 'ROOT_PRE_SUBMISSION_NOT_WORKER_LIVE'
         and canonical({k:v for k,v in root_frame.items() if k != 'body_sha256'}) == root_frame['body_sha256']
         and root_frame['source_pins'] == spec['operations_source_pins'] and root_frame['method_publication'] == spec['method_publication']
         and 0 <= root_frame['resource_capture_seconds'] <= 30, 'Exact actual historical Root resource frame differs')
    require_assessment = (lambda value,job: value['schema'] == 'model_v3_GPU_auto_memory_assessment_v1'
         and value['software_budget_bytes'] == 32 << 30 and value['rss_limit_bytes'] == 28 << 30
         and value['Slurm_memory_mode'] == 'automatic_default'
         and value['Slurm_finite_physical_allocation_guarantee_claimed'] is False
         and value['unknown_foreign_finite_guarantee_claimed'] is False and value['self_counted_exactly_once'] is True
         and value['current_job_id'] == job and value['current_reservation_id'] == spec['storage']['reservation_id']
         and value['with_new_software_bytes']*100 < (value['RealMemory_MiB'] << 20)*85
         and value['MemAvailable_bytes']*100 >= (32 << 30)*100+(value['RealMemory_MiB'] << 20)*15)
    need(require_assessment(root_frame['assessment'],None) and require_assessment(assessment,JOB),
         'Original software32G/RSS28G/85percent/MemAvailable-plus15percent arithmetic differs')
    api = auto.policy();api.validate_registration(assessment['caller_registration'])
    need(assessment['caller_registration']['job_id'] == JOB
         and assessment['caller_registration']['actual_submission'] == submission['immutable_GPU_submission_binding'],
         'Actual worker SUBMITTED software registration differs')
    raw_helper = auto.original();wanted = raw_helper.resource_observation_argv()
    need(set(root_frame['observations']) == set(wanted),'Exact historical Root raw roles required')
    for role,argv in wanted.items():
        raw_helper.checked_observation(raw_helper.enrich_observation(root_frame['observations'][role]),argv)
    replay = auto.recorded_assessment(root_frame['registry_snapshot'],root_frame['observations']['node']['stdout'],
        root_frame['observations']['queue']['stdout'],root_frame['observations']['memory']['stdout'],spec['storage']['reservation_id'])
    need(replay == root_frame['assessment'],'Exact source-bound historical Root memory assessment differs')
    expected_worker = [
        ['scontrol','show','node',spec['node']],
        ['squeue','-h','-w',spec['node'],'-o','%i|%u|%t|%m|%C'],
        ['head','-n','5','/proc/meminfo'],
        ['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits'],
        ['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader,nounits']]
    need(len(guard['actual_worker_observations']) == len(expected_worker),'Exact actual five live worker observations required')
    for observed,argv in zip(guard['actual_worker_observations'],expected_worker):
        raw_helper.checked_observation(raw_helper.enrich_observation(observed),argv)
    fresh, parent = fresh_sacct(JOB,spec['node'])
    module.validate_supervisor_record(sup,JOB,kind='GPU')
    need(sup['foreign_gpu_processes_signalled'] is False and sup['retirement'] is None
         and sup['private_storage_final']['first_sampling_failure'] is None
         and sup['private_storage_final']['budget_bytes'] == LIMIT
         and sup['private_storage_final']['sampled_max_bytes'] <= LIMIT
         and sup['output_budget_bytes'] == LIMIT and sup['child_output_budget_bytes'] == LIMIT-(96 << 20)
         and sup['supervisor_source_sha256'] == spec['supervisor_source']['sha256'], 'Outer cleanup/private/limits differ')
    need(guard['retirement'] == {'actions':[],'remaining':[]} and guard['independent_WandB_SDK_verification_complete'] is False
         and guard['architecture_selection_claimed'] is False and guard['formal_pretraining_complete'] is False,
         'Guard cleanup/scope or pending SDK state differs')
    guard_command(sup['command'],spec,submission['admission'],submission['spec'],guard_dir,child=False)
    guard_command(guard['launch_identity']['argv'],spec,submission['admission'],submission['spec'],guard_dir,child=True)
    identity(sup['launch_identity'],sup['command'],JOB,sup['supervisor_slurm_cgroup'])
    need(sup['launch_identity']['pid'] == sup['child_pid'], 'Outer child PID differs')
    identity(guard['launch_identity'],guard['launch_identity']['argv'],JOB,sup['supervisor_slurm_cgroup'])
    allocation = guard['actual_allocation']
    need(allocation['uid'] == 1278 and allocation['job_id'] == JOB and allocation['node'] == spec['node']
         and allocation['cpus_per_task'] == 16 and allocation['software_memory_budget_bytes'] == 32 << 30
         and allocation['RSS_limit_bytes'] == 28 << 30 and allocation['actual_memory_reserved_bytes_claimed'] is None
         and worker['actual_allocation'] == allocation
         and allocation['cgroup'] == sup['supervisor_slurm_cgroup'], 'Actual allocation identity differs')
    private = book.json(sup['private_storage_bindings_path'])
    observed_private = guard['actual_private_storage_binding']
    need({key:observed_private[key] for key in private} == private
         and observed_private['receipt_path'] == sup['private_storage_bindings_path']
         and observed_private['receipt_sha256'] == book.refs[sup['private_storage_bindings_path']]['sha256']
         and private['private_storage_budget_bytes'] == LIMIT and private['job_id'] == JOB and private['uid'] == 1278,
         'Original private receipt/observation binding differs')
    runtime = book.json(guard_dir/'child_runtime_finish.json')
    start = book.json(guard_dir/'child_runtime_start.json')
    need(runtime == guard['child_runtime'] and runtime['returncode'] == 0 and runtime['actual_argv'] == spec['request_argv']
         and runtime['policy_unchanged'] is True and runtime['policy_before'] == runtime['policy_after'] == start['policy_before']
         and runtime['H0_export_precision'] == 'fp32_noAMP_declared_base_options'
         and runtime['request_sha256'] == spec['request']['sha256'], 'Actual evaluator runtime/precision differs')
    need(result['schema'] == 'model_v3_dev_evaluation_result_v1' and result['status'] == 'COMPLETED'
         and result['request_sha256'] == spec['request']['sha256'] and result['job_id'] == JOB
         and result['code_sha'] == spec['code_sha'] and result['reference_kind'] == 'primary'
         and result['wandb_history_independently_verified'] is False and type(result['journal_records']) is int
         and result['journal_records'] > 0,
         'Original complete result or pending independent SDK state differs')
    pair, endpoint = result['encoder_pair'],spec['native_endpoint']
    equal_ref(pair['checkpoint'],spec['source_checkpoint'],state_key='model')
    equal_ref(request['checkpoint'],spec['source_checkpoint'],state_key='model')
    equal_ref(pair['original_configuration'],spec['original_configuration'])
    equal_ref(pair['training_completion'],spec['checkpoint_complete'])
    member = book.bound(spec['original_configuration'])
    marker = book.bound(spec['checkpoint_complete'])
    contract = member['member_contract']
    need(member['schema'] == 'existing_native_S_precision_member_v1'
         and member['seed'] == endpoint['seed'] == request['pretraining_seed'] == pair['pretraining_seed'] == 0
         and member['precision'] == endpoint['precision'] == 'fp32'
         and member['optimizer_updates'] == marker['optimizer_updates'] == endpoint['optimizer_updates'] == 20000
         and member['samples_consumed'] == marker['samples_consumed'] == endpoint['samples_consumed'] == 8151040
         and contract['code_sha'] == spec['producer_code_sha'] and canonical(contract) == endpoint['contract_sha256'],
         'Closed actual Native20k member/clock/source differs')
    need(marker['payload_sha256'] == spec['source_checkpoint']['sha256']
         and marker['payload_bytes'] == spec['source_checkpoint']['bytes'], 'COMPLETE/producer payload reference differs')
    expected_bindings = {'code_sha':contract['code_sha'],'configuration_sha256':canonical(contract),
        'registry_sha256':contract['source_files']['current/phychem_mfm/phase1/v3_native_s_precision_data.py'],
        'normalization_sha256':canonical({}),'data_version':contract['data_version'],
        'source_inventory_sha256':canonical(contract['source_files'])}
    need(marker['schema'] == 'model_v3_training_checkpoint_v1' and marker['bindings'] == expected_bindings
         and type(member['seed']) is int and type(marker['samples_consumed']) is int
         and type(marker['optimizer_updates']) is int and contract['seed'] == member['seed']
         and contract['precision'] == member['precision'] and member['D5_authority'] is False
         and contract['D5_authority'] is False and member['scientific_acceptance'] is False
         and member['scope'] == contract['source_scope'] == 'existing_native_S_original_TRAIN_record_sampler_not_D5',
         'Original six Native bindings/typed cursors/descriptive authority differ')
    producer_closure = book.bound(spec['native_authority']['segment_closure'])
    producer_submission = book.bound(producer_closure['submission'])
    need(producer_closure['schema'] == 'native_S_long_segment_Root_closure_v1'
         and producer_closure['status'] == 'OUTER_C0_SEGMENT_CLOSED_SDK_PENDING'
         and producer_closure['failure'] is None and producer_closure['member_result'] == spec['original_configuration']
         and producer_closure['checkpoint_directory'] == str(Path(spec['checkpoint_complete']['path']).parent)
         and producer_closure['optimizer_updates'] == 20000, 'Actual closed producing segment metadata differs')
    producer_job = str(producer_submission['actual_sbatch_job_id'])
    module.terminal(producer_closure['actual_terminal'],producer_job)
    module.supervisor(producer_closure['supervisor'],producer_job,kind='GPU')
    need(producer_submission['seed'] == 0 and producer_submission['precision'] == 'fp32'
         and producer_submission['start_update'] < 20000 <= producer_submission['target_update'],
         'Actual Native producing member range differs')
    payload_stat = book.opaque_stat(spec['source_checkpoint']['path'],expected_bytes=spec['source_checkpoint']['bytes'])
    native = pair['native_checkpoint']
    need(pair['H0_dimension'] == 512 and pair['checkpoint_schema'] == 'model_v3_native_S_immutable_checkpoint'
         and pair['random_reference_seed'] == result['random_reference_initialization_seed'] == 20261025
         and result['readout_seed'] == 0 and pair['downstream_target_records_read'] == 0
         and pair['checkpoint_encoder_state_sha256'] != pair['random_encoder_state_sha256']
         and native['native_contract_sha256'] == endpoint['contract_sha256']
         and native['pretraining_code_sha'] == endpoint['producer_code_sha']
         and native['pretraining_precision'] == 'fp32' and native['optimizer_updates'] == 20000
         and native['samples_consumed'] == 8151040 and native['H0_export_precision'] == 'fp32_noAMP_declared_base_options'
         and native['BF16_training_forward_bitwise_replay_claimed'] is False and native['D5_authority'] is False,
         'Actual typed Native candidate/random provenance differs')
    source_refs(pair,book)
    for key,reference in (('panel_sha256',request['panel']),('training_store_sha256',request['training_store'])):
        need(result[key] == reference['sha256'], 'Frozen panel/store result binding differs')
    for name,methods in (('primary_18_cells',('ridge','linear64_relu')),('ridge',('ridge',)),('linear64_relu',('linear64_relu',))):
        item = result['summaries'][name]
        need(item['complete'] is True and set(item['tasks']) == {task+'@'+m for task in TASKS for m in methods}
             and item['bootstrap_samples'] == item['bootstrap_defined'] == 1000 and item['bootstrap_unit'] == 'molecule',
             'Incomplete frozen task/readout/bootstrap population')
    need(set(result['h0_caches']) == {label+'/'+dataset for label in ('candidate','reference') for dataset in DATASETS},
         'Exactly six matched native H0 cache manifests required')
    packing = book.bound(spec['packing_plans'])
    cache_proofs = {}
    for dataset in DATASETS:
        left,right = (result['h0_caches'][label+'/'+dataset] for label in ('candidate','reference'))
        for key in ('architecture_sha256','membership_sha256','geometry_sha256','dimension',
            'packing_plan_sha256','packing_budget_sha256','effective_runtime_sha256'):
            need(left['binding'][key] == right['binding'][key], 'Matched cache binding differs')
        # The original exporter and target-free CPU planner both retain source
        # inventory but encode only source-declared geometry_ready records.
        for key in ('molecules','atoms','unavailable_geometry_records'):
            need(left[key] == right[key], 'Candidate/random geometry availability population differs')
        for label,cache in (('candidate',left),('reference',right)):
            binding = cache['binding']
            cache_key = cache['cache_key']
            need(type(cache_key) is str and re.fullmatch('[a-f0-9]{64}',cache_key)
                 and cache_key == canonical(binding), 'H0 cache key differs from the original canonical binding rule')
            expected_manifest = Path(request['cache_root']).absolute()/cache_key/'manifest.json'
            need(cache['manifest'] == str(expected_manifest), 'H0 manifest path differs from original cache_root/key/manifest.json rule')
            manifest = book.json(expected_manifest)
            common_keys = {'atoms','molecules','binding','packing_plan','targets_cached','tensor_sha256'}
            need(set(manifest) == common_keys and all(manifest[k] == cache[k] for k in common_keys),
                 'Saved H0 manifest/result six-field metadata differs')
            need(binding['schema'] == 'model_v3_train_h0_cache_v3' and binding['dimension'] == 512
                 and canonical(binding) == cache['cache_key'] and binding['architecture_sha256'] == result['architecture_sha256']
                 and binding['membership_sha256'] == result['membership_sha256'][dataset]
                 and cache['targets_cached'] is False
                 and type(cache['unavailable_geometry_records']) is int and cache['unavailable_geometry_records'] >= 0
                 and type(cache['molecules']) is int and cache['molecules'] > 0
                 and cache['molecules'] == packing[dataset]['records_retained']
                 and cache['molecules']+cache['unavailable_geometry_records'] == spec['counts'][dataset]
                 and type(cache['atoms']) is int and cache['atoms'] > 0
                 and cache['atoms'] == packing[dataset]['native_atoms_retained'],
                 'Target-free512 cache available population differs from the original selected TRAIN and frozen CPU packing')
            need(cache['packing_plan'] == packing[dataset] and cache['packing_plan']['oversized_singleton_ordinals'] == []
                 and binding['packing_plan_sha256'] == request['h0_packing_plan_sha256'][dataset]
                 and binding['packing_budget_sha256'] == request['h0_packing_budget_sha256']
                 and binding['packing_budget'] == request['h0_packing'], 'Frozen target-free packing changed')
            need(canonical(binding['effective_runtime']) == binding['effective_runtime_sha256'] == result['h0_effective_runtime_sha256']
                 and canonical(binding['execution_source']) == binding['execution_source_sha256'], 'Cache runtime/source canonical digest differs')
            effective = binding['effective_runtime']
            need(effective['H0_output_dtype'] == 'torch.float32'
                 and effective['H0_autocast'] == 'locally_disabled_without_changing_global_policy'
                 and effective['device']['uuid'] == spec['gpu_uuid']
                 and effective['cuda_matmul_allow_tf32'] == runtime['policy_before']['cuda_matmul_allow_tf32']
                 and effective['cudnn_allow_tf32'] == runtime['policy_before']['cudnn_allow_tf32'],
                 'Actual same-policy FP32 H0 runtime differs')
            source_refs(effective,book)
            source = binding['execution_source']
            need(source['native_checkpoint'] == native and source['training_completion'] == pair['training_completion']
                 and source['code_sha'] == spec['code_sha'] and source['configuration'] == request['model_configuration']
                 and source['source_inventory_sha256'] == canonical(request['source_files']), 'Cache original Native/source projection differs')
            expected_origin = (request['checkpoint'] if label == 'candidate' else
                {'initialization_seed':20261025,'architecture_sha256':request['architecture_sha256']})
            need(source['weights_origin'] == expected_origin, 'Candidate/random original weight origin differs')
            expected_encoder = pair['checkpoint_encoder_state_sha256' if label == 'candidate' else 'random_encoder_state_sha256']
            need(binding['encoder_sha256'] == expected_encoder, 'Cache encoder state differs')
            opaque = book.opaque_stat(Path(cache['manifest']).parent/'h0.pt')
            cache_proofs[label+'/'+dataset] = {'manifest':book.refs[cache['manifest']],
                'cache_key':cache['cache_key'],'molecules':cache['molecules'],'atoms':cache['atoms'],
                'original_selected_TRAIN_records':spec['counts'][dataset],
                'unavailable_geometry_records':cache['unavailable_geometry_records'],
                'geometry_available_record_order_sha256':packing[dataset]['record_order_sha256'],
                'frozen_geometry_available_packing_plan_sha256':packing[dataset]['plan_sha256'],
                'dimension':512,'targets_cached':False,'producer_tensor_sha256':cache['tensor_sha256'],
                'Root_tensor_stat':opaque,'Root_tensor_SHA_reverified':False}
    # Root does NOT open/hash/parse resource/step journals. The exact successful
    # published guard control flow enforced each sample, then saved these summaries.
    resource_stat = book.opaque_stat(guard_dir/'resource_samples.jsonl')
    need(guard['final_census']['whole_output_base_bytes'] <= LIMIT
         and guard['final_census']['child_bytes'] <= LIMIT-(96 << 20)
         and guard['final_census']['management_unique_bytes'] == guard['final_census']['whole_output_base_bytes']-guard['final_census']['child_bytes']
         and guard['final_census']['physical_unique_root'] == str(base)
         and guard['final_census']['includes_control_guard_outer_stdio'] is True
         and guard['elapsed_seconds_including_cleanup'] < 3500 and sup['elapsed_seconds'] < 3590,
         'Actual final whole census/inclusive guard/outer summaries differ')
    monitor = load_metadata_module(spec['runtime_monitor'],'Native_S20000_Root_closed_output_monitor',book)
    current_whole = module.whole_output_bytes(base,monitor)
    need(current_whole <= LIMIT and sup['last_output_bytes'] <= LIMIT, 'Current complete output family exceeds original2GiB')
    principal = book.bound(guard['storage']['principal'])
    need(principal['schema'] == 'model_v3_Root_one_job_output_reservation_v1' and principal['authority'] == 'ROOT_ACTUAL'
         and principal['phase'] == str(base) and principal['max_bytes'] == LIMIT
         and principal['reserved_additional_bytes'] == LIMIT and principal['uid'] == 1278
         and principal['initial_existing_bytes'] == 0 and principal['scientific_acceptance'] is False
         and guard['storage']['registrar_or_existing_hold_modified'] is False
         and guard['storage']['reservation_id'] == principal['reservation_id'], 'Original independent storage principal differs')
    # The previous large TRAIN metadata refs remain references only, authenticated
    # by CPU5059 + original guard + the actual result. Do not open42MiB inputs.
    book.finish();clean_imports()
    return {'schema':'model_v3_Native_S20000_panel_GPU_Root_metadata_closure_v1',
        'status':'ACTUAL_GPU_C0_NATIVE20000_FULL9_18CELL_H0_SOURCE_RESOURCE_CLOSED_SDK_PENDING',
        'actual_unix':time.time(),'closer_source':closer_source,'job_id':JOB,'actual_parent':fresh,'actual_parent_fields':parent,
        'spec':submission['spec'],'request':spec['request'],'actual_submission':book.refs[str(control/'Root_submission_attempt001.json')],
        'CPU_preparation_metadata':{'receipt':cpu_ref,'supervisor':cpu_binding['supervisor'],'fresh_actual_parent':cpu_fresh,
             'actual_parent_fields':cpu_parent,'source_before_after_current_equal':True,'bridge_before_after_kind':'PINNED_PREPARER_CONTROL_FLOW_NOT_SEPARATE_SAVED_FULL_BRIDGE_MAP'},'bridge_identity':{k:bridge[k] for k in ('evaluation_code_sha','public_code_sha','tree_sha','qa_job_id')},
        'request_source_count':len(request['source_files']),'Root_current_bridge_QA_source_count':len(bridge['source_inventory']),
        'Root_current_bridge_QA_sources_sha256':canonical(bridge['source_inventory']),
        'worker_source_before_after_evidence':{'kind':'SUCCESSFUL_PINNED_PRODUCER_CONTROL_FLOW_NOT_SEPARATE_SAVED_PER_FILE_MAP',
            'guard_source':spec['external_guard'],'guard_result':book.refs[str(guard_dir/'guard_result.json')],
            'child_start':book.refs[str(guard_dir/'child_runtime_start.json')],
            'child_finish':book.refs[str(guard_dir/'child_runtime_finish.json')],
            'calls':'Pinned verify_sources at guard entry, child entry, and post-child before COMPLETED; Root independently rechecks current source maps'},
        'result':guard['result'],'supervisor':book.refs[str(base/('supervisor_'+JOB+'.json'))],
        'panel':{'tasks':9,'comparison_cells':18,'bootstrap_draws_each_summary':1000,'H0_dimension':512,
            'matched_caches':cache_proofs,'TRAIN_only_frozen_preregistration':request['preregistration_sha'],
            'geometry_population_scope':'Original source inventory retained; both encoders/readouts use exactly the frozen geometry_ready subset, not every originally selected record',
            'source_declared_geometry_unavailability':{dataset:{
                'selected_records':spec['counts'][dataset],
                'geometry_available_records':result['h0_caches']['candidate/'+dataset]['molecules'],
                'unavailable_geometry_records':result['h0_caches']['candidate/'+dataset]['unavailable_geometry_records'],
                'candidate_reference_population_exactly_matched':True,
                'CPU_frozen_geometry_available_record_order_sha256':packing[dataset]['record_order_sha256']}
                for dataset in DATASETS},
            'geometry_exclusion_policy_sources':{
                'exporter':{'path':str(Path(spec['repository_root'])/'tools/model_v3/evaluate_dev_panel.py'),
                    'rule':'geometry_ready false increments unavailable and skips before H0, then reports unavailable count'},
                'planner':{'path':str(Path(spec['repository_root'])/'current/phychem_mfm/phase1/v3_h0_packing.py'),
                    'rule':'packing_plans_for_views uses native_geometry_metadata geometry_ready only; fixed pre-encoding record order hash'},
                'readouts':{'path':str(Path(spec['repository_root'])/'current/phychem_mfm/phase1/v3_dev_evaluation.py'),
                    'rule':'task_rows retains source inventory but skips source-unavailable geometry without rebuilding it'}},
            'zero_missing_geometry_or_full_selected_record_coverage_claimed':False},
        'Native_endpoint':{'seed':0,'precision':'fp32','optimizer_updates':20000,'samples_consumed':8151040,
            'producer_code_sha':spec['producer_code_sha'],'producer_authenticated_payload_ref':spec['source_checkpoint'],
            'Root_payload_stat':payload_stat,'Root_payload_SHA_reverified':False},
        'resource_closure':{'Root_resource_journal_read':False,'Root_independent_sample_count_or_maxima_claimed':False,
             'resource_journal_stat_only':resource_stat,'sampling_enforcement_kind':'ACTUAL_COMPLETED_PINNED_GUARD_CONTROL_FLOW_NOT_ROOT_ROW_REAGGREGATION',
             'recorded_live_worker_assessment':{'software_memory_budget_bytes':32 << 30,'RSS_limit_bytes':28 << 30,
                 'Slurm_memory_mode':'automatic_default','finite_physical_allocation_guarantee_claimed':False,
                 'foreign_unknown_finite_guarantee_claimed':False},
            'current_whole_family_bytes':current_whole,'recorded_guard_final_census':guard['final_census'],
            'inclusive_guard_wall_seconds':guard['elapsed_seconds_including_cleanup'],'inclusive_outer_wall_seconds':sup['elapsed_seconds'],
            'actual_allocated_seconds':int(parent['ElapsedRaw']),'inclusive_one_GPU_hour_target_met':True,
            'private_storage_final':sup['private_storage_final'],'remaining_owned_processes':[],
            'private_cleanup_errors':[],'foreign_processes_signalled':False,
            'torch_result_or_child_peak_is_not_claimed_global':True},
        'metadata_and_source_refs':list(book.refs.values()),
        'large_TRAIN_metadata_not_reopened':{k:spec[k] for k in ('selection_request','selected_store','selected_store_manifest','materialization_result')},
        'independent_WandB_SDK_verification_complete':False,'wandb_run_id':result['wandb_run_id'],
        'journal_records_as_saved_not_SDK_record_count':result['journal_records'],
        'reservation_released_by_this_script':False,'model_adopted':False,'D5_or_B_acceptance':False,
        'pretraining_seed_SD_claimed':False,'formal_pretraining_complete':False,'guide_complete':False,
        'Root_scope':'Only metadata/raw source hashes+opaque artifact stats; payload/H0 SHA and values come from actual CPU/GPU producer, no Root tensor/SDK/target read'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=DEFAULT_BASE)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    need(not args.output.exists() and args.output.parent == N and args.output.suffix == '.json', 'Fresh N Root closure output required')
    value = close(args.base)
    raw = (json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    need(len(raw) <= META,'Root metadata output exceeds original2MiB')
    with args.output.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'status':value['status'],'output':{'path':str(args.output),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}))


if __name__ == '__main__':
    main()
