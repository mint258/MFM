"""Validation seam for ACTUAL_QUEUED_D3_CPU16_STARTUP_V1 only.

No C import and no science replay. Source/plan/request/manifest bytes are pinned;
authoritative DATA refs are compared as exact authorized pins, not rehashed.
"""
import datetime, hashlib, json, os, pathlib, re, shlex, socket, stat, subprocess, sys, time

PY = '/share/home/zixiao/.conda/envs/chemprop/bin/python'
PROJECT = '/share/home/zixiao/descriptor_analysis'
REPO = pathlib.Path(PROJECT) / 'runs/data_v1_20261025/repository'
THREAD_KEYS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def reference(value):
    need(isinstance(value, dict) and all(key in value for key in ('path', 'bytes', 'sha256')), 'ACTUAL_THREE_FIELD_REFERENCE')
    need(isinstance(value['path'], str) and pathlib.Path(value['path']).is_absolute()
         and type(value['bytes']) is int and value['bytes'] >= 0
         and isinstance(value['sha256'], str) and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None,
         'LITERAL_PIN_PATH_LENGTH_AND_SHA')
    return {key: value[key] for key in ('path', 'bytes', 'sha256')}


def pin(path):
    path = pathlib.Path(path)
    before = path.stat(); raw = path.read_bytes(); after = path.stat()
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'STABLE_PINNED_METADATA_OR_SOURCE')
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()), raw


def load(value):
    ref = reference(value)
    actual, raw = pin(ref['path'])
    need(actual == ref, 'EXACT_PINNED_METADATA:' + ref['path'])
    return json.loads(raw)


def refmap(values):
    need(type(values) is list, 'EXPLICIT_REFERENCE_LIST')
    result = {}
    for value in values:
        ref = reference(value)
        need(ref['path'] not in result or result[ref['path']] == ref, 'NO_CONFLICTING_PINS_FOR_ONE_PATH')
        result[ref['path']] = ref
    return result


def aware(text):
    value = datetime.datetime.fromisoformat(text)
    need(value.tzinfo is not None and value.utcoffset() is not None, 'ACTUAL_AWARE_OBSERVATION')
    return value


def process_argv():
    return [value.decode() for value in pathlib.Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')]


def allocation(raw, request, manifest, job_id, node):
    fields = dict(token.split('=', 1) for token in shlex.split(raw) if '=' in token)
    uid = re.search(r'\((\d+)\)$', fields.get('UserId', ''))
    need(fields.get('JobId') == job_id and uid is not None and uid.group(1) == '1278'
         and fields.get('JobState') == 'RUNNING' and fields.get('JobName') == manifest['job_name']
         and fields.get('Partition') == manifest.get('partition', 'cpu') and fields.get('NumCPUs') == '16'
         and fields.get('NodeList') == node and fields.get('NumNodes') == '1', 'ACTUAL_SINGLE_NODE_RUNNING_MAIN_CPU16_JOB')
    need(fields.get('Command') == manifest['bootstrap_script_reference']['path'], 'LITERAL_QUEUED_SBATCH_COMMAND')
    need(fields.get('WorkDir') == request['workdir'] == PROJECT, 'ACTUAL_QUEUED_WORKDIR')


def authorized_source(ref, frozen, manifest, manifest_ref):
    """Four exact source categories; only post-allocation JSON is dynamic."""
    path = pathlib.Path(ref['path'])
    if ref['path'] in frozen:
        need(frozen[ref['path']] == ref, 'EXACT_PRE_FROZEN_SOURCE_NOT_DYNAMIC_OVERRIDE')
        return
    if ref['path'] == manifest_ref['path']:
        need(ref == manifest_ref, 'EXACT_QUEUE_MANIFEST_SELF_REFERENCE')
        return
    submission = ref['path'] == manifest['submission_record_path']
    directory = pathlib.Path(manifest['execution_control_directory'])
    inside = path != directory and path.is_relative_to(directory)
    need(submission or (directory.is_absolute() and inside), 'NO_OTHER_NEW_SOURCE_PATH:' + ref['path'])
    need(path.suffix == '.json' and '..' not in path.parts
         and not any(part.is_symlink() for part in (path, *path.parents)), 'DYNAMIC_SOURCE_IS_LITERAL_NONSYMLINK_JSON')
    observed = path.lstat()
    need(observed.st_uid == 1278 and stat.S_ISREG(observed.st_mode), 'ROOT_GENERATED_OWN_REGULAR_METADATA_JSON')
    actual, raw = pin(path)
    need(actual == ref, 'EXACT_ACTUAL_POST_ALLOCATION_METADATA_BYTES_SHA')
    json.loads(raw)  # Data-only JSON; no new executable source is admitted.

def validate(path, proof_path, plan, *, scope_key, parameters):
    proof = json.loads(pathlib.Path(proof_path).read_text(encoding='utf-8'))
    need(proof['schema'] in ('ACTUAL_QUEUED_D3_CPU16_STARTUP_V1','ACTUAL_QUEUED_D3_CPU16_STARTUP_V2'), 'EXPLICIT_ACTUAL_QUEUED_PROOF_ONLY')
    manifest_ref = reference(proof['queue_manifest_reference'])
    manifest = load(manifest_ref)
    unlimited = manifest.get('queue_startup_mode') == 'USER_UNLIMITED_CPU21_D3_20261103'
    need(proof['schema']==('ACTUAL_QUEUED_D3_CPU16_STARTUP_V2'if unlimited else'ACTUAL_QUEUED_D3_CPU16_STARTUP_V1'),'MATCHED_ACTUAL_PROOF_VERSION')
    if unlimited:
        authority=load(manifest['user_resource_policy_reference'])
        need(authority['status']=='USER_APPROVED' and authority['node']=='compute-0-21'and authority['partition']=='all'
          and authority['Slurm_time_limit']is None and authority['software_wall_limit']is None
          and authority['Slurm_memory_request']is None and authority['software_RSS_limit']is None
          and authority['MemAvailable_stop_threshold']is None and authority['account_floor_bytes']==100000000000,'EXPLICIT_CURRENT_USER_UNLIMITED_CPU21_SCOPE')
    need(str(proof_path) == manifest['proof_path']
         and reference(proof['request_reference'])['path'] == manifest['request_path'], 'EXACT_MANIFEST_REQUEST_AND_PROOF_PATHS')
    request = load(proof['request_reference'])
    need(canonical(request) == canonical(proof['request'])
         and request['schema'] == ('D3_QUEUED_CPU16_REQUEST_V2' if unlimited else 'D3_QUEUED_CPU16_REQUEST_V1'), 'EXACT_ACTUAL_CREATED_REQUEST')
    need(manifest['schema'] == 'D3_QUEUED_SINGLE_EXPORT_V1'
         and manifest['source_policy'] == 'FROZEN_SOURCE_NO_NEW_QM_UFF'
         and request['queue_manifest_reference'] == reference(proof['queue_manifest_reference'])
         and request['bootstrap_script_reference'] == manifest['bootstrap_script_reference'], 'EXACT_QUEUED_MANIFEST_CHAIN')
    need(os.getcwd() == request['workdir'] == PROJECT, 'ACTUAL_PRODUCER_WORKDIR')
    need(request['scope_key'] == scope_key and canonical(request['scope_parameters']) == canonical(parameters), 'OWN_DECLARED_SCOPE_AND_PARAMETERS')
    need(request['kind'] == 'analysis' and request['cpus'] == 16 and request['partition'] == manifest.get('partition', 'cpu')
         and request['pilot'] is False and (request['wall_seconds'] is None if unlimited else request['wall_seconds'] == 86400)
         and request['memory_policy'] == 'SLURM_DEFAULT_UNSPECIFIED' and request['exclusive_requested'] is False
         and request['estimated_peak_output_bytes'] == 300000000000, 'EXACT_QUEUED_D3_RESOURCE_REQUEST')
    frozen = refmap(manifest['frozen_source_references'])
    sources = refmap(request['source_references'])
    plan_ref = reference(request['plan_reference'])
    need(sources.get(plan_ref['path']) == plan_ref, 'PRODUCER_PLAN_IS_AN_AUTHORIZED_REQUEST_SOURCE')
    authorized_source(plan_ref, frozen, manifest, manifest_ref)
    actual_plan = load(plan_ref)
    need(str(path) == request['plan_reference']['path'] and canonical(actual_plan) == canonical(plan), 'UNCHANGED_ACTUAL_PRODUCER_PLAN')
    argv = [PY, '-B', '-m', manifest['producer_module'], '--plan', str(path), '--startup-proof', str(proof_path)]
    need(request['execution_argv'] == argv == proof['expected_producer_argv'], 'EXACT_QUEUED_PRODUCER_ARGUMENTS')
    main = sys.modules.get('__main__')
    main_path = pathlib.Path(main.__file__).absolute()
    declared_path = REPO.joinpath(*manifest['producer_module'].split('.')).with_suffix('.py')
    need(main_path == declared_path and getattr(main, '__spec__', None) is not None
         and main.__spec__.name == manifest['producer_module'], 'ACTUAL_OWN_PRODUCER_MAIN_MODULE')
    need(sys.argv == [str(main_path), '--plan', str(path), '--startup-proof', str(proof_path)]
         and process_argv() == argv, 'ACTUAL_POST_EXEC_SYS_AND_PROC_ARGV')
    job_id = os.environ.get('SLURM_JOB_ID', '')
    node = socket.gethostname().split('.')[0]
    need(os.getuid() == proof['uid'] == 1278 and job_id.isdecimal() and int(job_id) > 0
         and str(proof['job_id']) == str(request['job_id']) == job_id and request['uid'] == 1278
         and proof['node'] == request['node'] == node
         and node in manifest['allowed_nodes'], 'SAME_ACTUAL_MAIN_JOB_NODE_AND_UID')
    need(os.environ.get('SLURM_JOB_PARTITION') == manifest.get('partition', 'cpu') and os.environ.get('SLURM_CPUS_PER_TASK') == '16'
         and os.environ.get('CUDA_VISIBLE_DEVICES') == ''
         and all(os.environ.get(key) == '1' for key in THREAD_KEYS), 'ACTUAL_CPU16_SINGLE_THREAD_ENVIRONMENT')
    actual_ticks = int(pathlib.Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
    need(proof['pid'] == os.getpid() and proof['start_ticks'] == actual_ticks
         and proof['boot_id'] == pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
         and proof['cgroup'] == pathlib.Path('/proc/self/cgroup').read_text(), 'SAME_KERNEL_PROCESS_ACROSS_REAL_EXEC')
    if not unlimited:need(0 <= time.time() - proof['created_unix_seconds'] <= 120, 'ACTUAL_STARTUP_PROOF_FRESH_WITHIN120_SECONDS')
    need(abs(aware(proof['observed_at']).timestamp() - proof['created_unix_seconds']) < 1, 'SAME_ACTUAL_COMPUTE_OBSERVATION_TIME')
    aware(proof['root_observed_at'])
    need(proof['job_metadata'] == proof['actual_scontrol_raw'], 'ONE_ACTUAL_STARTUP_JOB_METADATA_OBSERVATION')
    allocation(proof['actual_scontrol_raw'], request, manifest, job_id, node)
    query = subprocess.run(['scontrol', '-o', 'show', 'job', job_id], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=30, check=False)
    need(query.returncode == 0, 'FRESH_ACTUAL_SCONTROL_JOB_OBSERVATION')
    allocation(query.stdout, request, manifest, job_id, node)
    frozen = refmap(manifest['frozen_source_references'])
    sources = refmap(request['source_references'])
    for ref in frozen.values():
        need(pin(ref['path'])[0] == ref, 'EXACT_FROZEN_SOURCE_PIN:' + ref['path'])
    for ref in sources.values():
        authorized_source(ref, frozen, manifest, manifest_ref)
    for own in (str(pathlib.Path(__file__).absolute()), str(main_path)):
        need(own in sources and sources[own] == frozen[own], 'ACTUAL_RUNTIME_AND_PRODUCER_SOURCE_AUTHORITY')
    need(all(sources.get(key) == value for key, value in refmap(actual_plan['source_references']).items()), 'PLAN_SOURCE_PINS_AUTHORIZED_BY_REQUEST')
    authorized_data = refmap(request['data_references'])
    need(all(authorized_data.get(key) == value for key, value in refmap(actual_plan['data_references']).items()), 'PLAN_DATA_PINS_AUTHORIZED_WITHOUT_SCIENCE_REHASH')
    script = reference(manifest['bootstrap_script_reference'])
    need(frozen.get(script['path']) == script, 'LITERAL_PRE_FROZEN_BOOTSTRAP_SBATCH_SOURCE_PIN')
    helper_path = manifest['prepare_helper_path']
    need(helper_path in frozen, 'ACTUAL_PRE_FROZEN_MAIN_HELPER_CODE')
    bootstrap = reference(proof['bootstrap_source_reference'])
    need(frozen.get(bootstrap['path']) == bootstrap, 'ACTUAL_FROZEN_BOOTSTRAP_SOURCE')
    if not unlimited:need(0 <= time.time() - proof['created_unix_seconds'] <= 120, 'QUEUED_PROOF_REMAINS_FRESH_AFTER_SOURCE_BINDING')
    return proof