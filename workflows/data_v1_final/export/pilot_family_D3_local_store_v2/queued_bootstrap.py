"""D3 bootstrap for one REAL queued CPU16 sbatch allocation."""
import argparse, datetime, hashlib, json, os, pathlib, shlex, socket, subprocess, sys, time

PY = '/share/home/zixiao/.conda/envs/chemprop/bin/python'
PROJECT = '/share/home/zixiao/descriptor_analysis'
REPO = pathlib.Path(PROJECT) / 'runs/data_v1_20261025/repository'
THREAD_KEYS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def pin(path):
    path = pathlib.Path(path)
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'STABLE_METADATA_OR_SOURCE_FILE')
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()), raw


def load(reference):
    actual, raw = pin(reference['path'])
    need(actual == reference, 'EXACT_METADATA_OR_SOURCE_PIN:' + reference['path'])
    return json.loads(raw)


def proc_argv():
    return [value.decode() for value in pathlib.Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')]


def start_ticks():
    return int(pathlib.Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])


def aware(text):
    value = datetime.datetime.fromisoformat(text)
    need(value.tzinfo is not None and value.utcoffset() is not None, 'ACTUAL_TIMEZONE_AWARE_OBSERVATION')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue-manifest', required=True)
    args = parser.parse_args()
    need(pathlib.Path(args.queue_manifest).is_absolute(), 'LITERAL_ABSOLUTE_QUEUE_MANIFEST')
    manifest_ref, raw = pin(args.queue_manifest)
    manifest = json.loads(raw)
    unlimited = manifest.get('queue_startup_mode') == 'USER_UNLIMITED_CPU21_D3_20261103'
    need(manifest['schema'] == 'D3_QUEUED_SINGLE_EXPORT_V1'
         and manifest['source_policy'] == 'FROZEN_SOURCE_NO_NEW_QM_UFF', 'EXPLICIT_QUEUED_D3_MANIFEST')
    own = str(pathlib.Path(__file__).absolute())
    own_refs = [ref for ref in manifest['frozen_source_references'] if ref['path'] == own]
    need(len(own_refs) == 1 and pin(own)[0] == own_refs[0], 'ACTUAL_BOOTSTRAP_SOURCE_PIN')
    helper_refs = [ref for ref in manifest['frozen_source_references'] if ref['path'] == manifest['prepare_helper_path']]
    need(len(helper_refs) == 1 and pin(manifest['prepare_helper_path'])[0] == helper_refs[0], 'ACTUAL_FROZEN_MAIN_HELPER_CODE')
    job_id = os.environ.get('SLURM_JOB_ID', '')
    node = socket.gethostname().split('.')[0]
    need(os.getuid() == 1278 and job_id.isdecimal() and int(job_id) > 0, 'ACTUAL_MAIN_SLURM_UID_JOB')
    need(node in manifest['allowed_nodes'] and os.environ.get('SLURM_JOB_PARTITION') == manifest.get('partition', 'cpu')
         and os.environ.get('SLURM_CPUS_PER_TASK') == '16', 'ACTUAL_CPU16_ALLOCATION_ENVIRONMENT')
    need(os.environ.get('CUDA_VISIBLE_DEVICES') == ''
         and all(os.environ.get(key) == '1' for key in THREAD_KEYS), 'CPU_ONLY_SINGLE_THREAD_LIBRARIES')
    need(os.getcwd() == PROJECT, 'ACTUAL_DECLARED_PROJECT_WORKDIR')
    # The real sbatch acknowledgement is committed immediately after submission.
    receipt_path = pathlib.Path(manifest['submission_record_path'])
    receipt_deadline = time.monotonic() + 120
    while not receipt_path.is_file() and (unlimited or time.monotonic() < receipt_deadline):
        time.sleep(1)
    need(receipt_path.is_file(), 'ACTUAL_SBATCH_RECEIPT_NOT_YET_COMMITTED')
    receipt = json.loads(receipt_path.read_text())
    need(str(receipt['job_id']) == job_id and receipt['uid'] == 1278
         and receipt['sbatch_returncode'] == 0
         and receipt['bootstrap_script_reference'] == manifest['bootstrap_script_reference'],
         'SAME_REAL_SBATCH_ACKNOWLEDGEMENT')
    # Only the real allocated CPU performs this one DATA pin; Main receives
    # its small exact reference. Never use read-small metadata pin on3.523GB.
    scratch = pathlib.Path('/tmp')
    filesystem = subprocess.run(['findmnt', '-n', '-T', str(scratch), '-o', 'FSTYPE'],
                                capture_output=True, text=True, check=True).stdout.strip()
    need(filesystem in ('xfs', 'ext4', 'btrfs'), 'ACTUAL_NODE_LOCAL_TMP_DISK')
    from . import io as DataIO
    for code in (pathlib.Path(DataIO.__file__).absolute(), pathlib.Path(DataIO.B.S.__file__).absolute()):
        refs = [ref for ref in manifest['frozen_source_references'] if ref['path'] == str(code)]
        need(len(refs) == 1 and pin(code)[0] == refs[0], 'ORIGINAL_FROZEN_DATA_PIN_IMPLEMENTATION')
    old=load(manifest['writer_prior_plan_reference'])
    index_reference=old['direct_source_resume']['geometry_index_reference']
    need(index_reference['path']==manifest['closed_geometry_index_path']
      and index_reference['bytes']==manifest['closed_geometry_index_bytes']==3523170304,'SAME_ALREADY_PINNED_ORIGINAL_GEOMETRY_INDEX')
    local=pathlib.Path(old['direct_source_resume']['local_directory'])
    need(node=='compute-0-8' and local.is_dir() and local.stat().st_uid==1278
      and not any(p.is_symlink() for p in(local,*local.parents)), 'ACTUAL_SAME_NODE_PRIVATE_CLOSED_ROUTE_DIRECTORY')
    frames={}
    for name,size in [('source_routes.sqlite',12073861120),('geometry_index.sqlite',3523170304)]:
        path=local/name
        need(path.is_file()and path.stat().st_uid==1278 and path.stat().st_size==size,'EXACT_EXISTING_CLOSED_NODE_DATABASE')
        frames[name]=DataIO.identity(path)
    observation=dict(uid=os.getuid(),node=node,actual_job_id=job_id,local_database_frames=frames,
      local_directory=str(local),original_routes_reused=True,route_rebuild_performed=False)
    rpc_transport=['-oControlMaster=auto','-oControlPath='+str(local/('ssh_main_'+job_id+'.sock')),'-oControlPersist=600']
    remote = [PY, '-B', manifest['prepare_helper_path'], '--queue-manifest', args.queue_manifest,
              '--job-id', job_id, '--node', node, '--geometry-index-reference-json', json.dumps(index_reference, sort_keys=True),
              '--store-resume-observation-json',json.dumps(observation,sort_keys=True)]
    # Exactly one Main helper invocation. Timeout/failure is never retried.
    remote_env = ['PYTHONPATH=' + str(REPO) + ':/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps',
                  'PYTHONDONTWRITEBYTECODE=1', 'PYTHONUNBUFFERED=1', 'CUDA_VISIBLE_DEVICES=',
                  *[key + '=1' for key in THREAD_KEYS]]
    remote_command = 'cd ' + shlex.quote(str(REPO)) + ' && env ' + shlex.join(remote_env) + ' ' + shlex.join(remote)
    while True:
        helper = subprocess.run(['ssh', '-n', '-oBatchMode=yes', '-oConnectTimeout=12', *rpc_transport, 'sonmi', remote_command],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=None if unlimited else 600, check=False)
        refused = (helper.returncode == 255 and not helper.stdout and
                   helper.stderr.strip() == 'ssh: connect to host sonmi port 22: Connection refused')
        if not refused:
            break
        print(json.dumps(dict(status='WAIT_MAIN_SSH_PRECONNECTION_REFUSED', job_id=job_id,
                              node=node, retry_interval_seconds=600)), flush=True)
        time.sleep(600)
    need(helper.returncode == 0, 'MAIN_PREPARE_HELPER_FAILED_NO_RETRY:' + helper.stderr[-4096:])
    need(helper.stdout.splitlines(), 'MAIN_PREPARE_HELPER_RETURNED_NO_JSON')
    result = json.loads(helper.stdout.splitlines()[-1])
    need(result['request_path'] == result['request_reference']['path'] == manifest['request_path']
         and result['proof_path'] == manifest['proof_path'], 'EXACT_MANIFEST_REQUEST_AND_PROOF_PATHS')
    request = load(result['request_reference'])
    need(result['request_path'] == result['request_reference']['path'], 'EXACT_CREATED_REQUEST_PATH')
    need(request['schema'] == ('D3_QUEUED_CPU16_REQUEST_V2' if unlimited else 'D3_QUEUED_CPU16_REQUEST_V1')
         and request['node'] == node and request['cpus'] == 16 and request['partition'] == manifest.get('partition', 'cpu')
         and str(request['job_id']) == job_id and request['uid'] == 1278, 'SAME_ALLOCATED_REQUEST')
    need(request['queue_manifest_reference'] == manifest_ref
         and request['bootstrap_script_reference'] == manifest['bootstrap_script_reference'], 'SAME_QUEUED_MANIFEST_AND_SBATCH')
    argv = request['execution_argv']
    expected = [PY, '-B', '-m', manifest['producer_module'], '--plan', result['plan_path'], '--startup-proof', result['proof_path']]
    need(argv == expected and request['plan_reference']['path'] == result['plan_path'], 'EXACT_EXPECTED_PRODUCER_ARGV')
    producer_path = str(REPO.joinpath(*manifest['producer_module'].split('.')).with_suffix('.py'))
    producer_refs = [ref for ref in manifest['frozen_source_references'] if ref['path'] == producer_path]
    need(len(producer_refs) == 1 and pin(producer_path)[0] == producer_refs[0], 'ACTUAL_FROZEN_PRODUCER_CODE_BEFORE_EXEC')
    prepared_plan = load(request['plan_reference'])
    need(prepared_plan['direct_source_resume']['geometry_index_reference'] == index_reference
         and index_reference in request['data_references'], 'SAME_ACTUAL_CPU_STREAMING_INDEX_REFERENCE')
    query = subprocess.run(['scontrol', '-o', 'show', 'job', job_id], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=30, check=False)
    need(query.returncode == 0, 'ACTUAL_SCONTROL_STARTUP_OBSERVATION_REQUIRED')
    instant = datetime.datetime.now().astimezone()
    aware(result['root_observed_at'])
    proof = dict(schema='ACTUAL_QUEUED_D3_CPU16_STARTUP_V2' if unlimited else 'ACTUAL_QUEUED_D3_CPU16_STARTUP_V1', request=request,
                 request_reference=result['request_reference'], queue_manifest_reference=manifest_ref,
                 job_id=job_id, uid=os.getuid(), node=node, pid=os.getpid(), start_ticks=start_ticks(),
                 boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 created_unix_seconds=instant.timestamp(), observed_at=instant.isoformat(),
                 root_observed_at=result['root_observed_at'], actual_scontrol_raw=query.stdout, job_metadata=query.stdout,
                 expected_producer_argv=argv, bootstrap_argv=proc_argv(), bootstrap_sys_argv=list(sys.argv),
                 cgroup=pathlib.Path('/proc/self/cgroup').read_text(), bootstrap_source_reference=own_refs[0],
                 allocated_compute_geometry_index_reference=index_reference)
    need(pin(args.queue_manifest)[0] == manifest_ref, 'QUEUED_MANIFEST_UNCHANGED_AFTER_MAIN_HELPER')
    with pathlib.Path(result['proof_path']).open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, sort_keys=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    # Same PID/start_ticks/boot after exec; no original-Q proof or C0 is invented.
    os.execv(PY, argv)


if __name__ == '__main__':
    main()