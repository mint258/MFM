"""Run the one pre-merge CPU suite using four pytest processes per partition."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil
import hashlib
import xml.etree.ElementTree as ET

from cpu_bottleneck_step1 import BASE, REPO, capacity
from cpu_perf_concurrency import allocated_cpus
from runtime_monitor import capture_process_identity, owned_process_observation
from run_supervised import IDENTITY_KEYS, stop_recorded
from v2_watch_disk import filesystem_status, require_capacity, quota_headroom

OUTPUT_PEAK = 8_000_000_000
RSS_LIMIT = 24 * 1024**3
PRIVATE = None


def storage(root):
    """Reserve this suite in addition to all existing account forecasts."""
    quota = capacity()
    if PRIVATE is not None:
        require_capacity(filesystem_status('/tmp'), 2*1024**3, 1000)
        PRIVATE.check()
    require_capacity(filesystem_status(root), OUTPUT_PEAK, 10000)
    allocated = 0
    for path in root.rglob('*') if root.exists() else ():
        try:
            if path.is_file():
                allocated += path.stat().st_blocks * 512
        except FileNotFoundError:
            continue  # A removed test temporary file only increases this reservation.
    if allocated >= OUTPUT_PEAK:
        raise OSError('Regression output forecast consumed; preserve output and replan')
    nfs = quota_headroom(BASE/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json',
        '/share', OUTPUT_PEAK-allocated+64*1024**2, 23_179_869_184)
    return dict(existing_forecasts=quota, regression_allocated=allocated,
                nfs_available=nfs['available'], nfs_required=nfs['required'])


def bind(observed, identity):
    if identity.get('status') in ('GONE', 'EXITING'):
        return
    if identity.get('status') != 'ACTIVE':
        raise RuntimeError('Cannot bind a regression child kernel identity')
    key = identity['pid'], identity['start_ticks']
    if key in observed and any(observed[key][k] != identity[k] for k in IDENTITY_KEYS):
        raise RuntimeError('Regression child identity changed')
    observed[key] = identity


def supervise(argv, root, log):
    observed = {}
    cgroup = Path('/proc/self/cgroup').read_text()
    peak_rss = 0
    with log.open('xb') as stream:
        process = subprocess.Popen(argv, cwd=REPO, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            bind(observed, capture_process_identity(process.pid, expected_cgroup=cgroup, expected_argv=argv))
            while process.poll() is None:
                storage(root)
                try:
                    observation = owned_process_observation(process.pid)
                except psutil.NoSuchProcess:
                    if process.poll() is not None:
                        break
                    raise
                peak_rss = max(peak_rss, observation['rss_sum_bytes'])
                for row in observation['processes']:
                    bind(observed, capture_process_identity(row['pid'], expected_cgroup=cgroup))
                if observation['rss_sum_bytes'] > RSS_LIMIT:
                    raise MemoryError('Regression exceeded its 24GiB software RSS budget')
                time.sleep(2)
        except BaseException:
            retirement = stop_recorded(observed)
            (log.with_suffix('.retirement.json')).write_text(json.dumps(retirement, indent=2)+'\n')
            raise
    return dict(returncode=process.returncode, peak_rss_bytes=peak_rss,
                observed_identities=list(observed.values()))


def failed_nodes(xml):
    nodes = []
    for case in ET.parse(xml).getroot().iter('testcase'):
        errors = list(case.findall('failure')) + list(case.findall('error'))
        if not errors:
            continue
        lock_case = (case.attrib['classname']=='tests.test_cpu_perf_concurrency' and case.attrib['name'] in (
            'test_previous_exclusive_launcher_cannot_be_joined',
            'test_new_registered_launchers_can_hold_shared_lock_together'))
        fixture_case = case.attrib['classname']=='tests.test_model_v3_training_execution'
        worker_case = (case.attrib['classname'],case.attrib['name']) in {
            ('tests.test_model_v3_labels','test_node_local_spawn_prefetch_does_not_commit_unconsumed_draws'),
            ('tests.test_phase1_full_corpus_training','test_partial_spawn_prefetch_closes_workers_and_resumes_only_committed_dropout_controller_updates'),
            ('tests.test_model_v3_native_bond_transport','test_spawn_worker_native_transport_matches_direct_and_owned_handles_close')}
        worker_case = worker_case or (case.attrib['classname']=='tests.test_phase1_full_corpus_loader' and
            case.attrib['name'] in ('test_actual_spawn_workers_prefetch_retains_exact_ids_and_committed_cursor[False]',
                                   'test_actual_spawn_workers_prefetch_retains_exact_ids_and_committed_cursor[True]'))
        local_case = case.attrib['classname']=='tests.test_model_v3_wire_provider'
        for error in errors:
            diagnostic = (error.text or '')+' '+error.get('message','')
            if ('8 >= 16' not in diagnostic and not (lock_case and 'Bad file descriptor' in diagnostic)
                    and not (fixture_case and 'Declared C1 configuration/options differ' in diagnostic)):
                if not (worker_case and 'DataLoader timed out after ' in diagnostic) and not (
                        local_case and 'is_relative_to' in diagnostic and '/tmp' in diagnostic):
                    raise RuntimeError('Unreviewed prior failure: '+case.attrib['classname']+'::'+case.attrib['name'])
        parts = case.attrib['classname'].split('.')
        if len(parts)<2 or parts[0]!='tests' or not parts[1].startswith('test_'):
            raise RuntimeError('Unknown failing test module')
        path = REPO/'current/tests'/(parts[1]+'.py')
        if not path.is_file():
            raise RuntimeError('Failing test source missing')
        nodes.append(str(path)+'::'+'::'.join(parts[2:]+[case.attrib['name']]))
    return nodes


def repair_partition(previous, root, index, original):
    repairs = []
    for shard in original['shards']:
        nodes = failed_nodes(previous/f'part{index}/shard_{shard["shard"]:02d}.xml')
        if not nodes:
            continue
        failed_count = len(nodes)
        if any('test_model_v3_training_execution.py::' in node for node in nodes):
            # The fixture changed: retest its complete module, retaining unrelated passes.
            cases = ET.parse(previous/f'part{index}/shard_{shard["shard"]:02d}.xml').getroot().iter('testcase')
            nodes = [str(REPO/'current/tests/test_model_v3_training_execution.py')+'::'+case.attrib['name']
                     for case in cases if case.attrib['classname']=='tests.test_model_v3_training_execution']
        xml = root/f'repair_part{index}_{shard["shard"]:02d}.xml'
        argv = [sys.executable,'-B','-m','pytest',*nodes,'-q','-p','no:cacheprovider',
                f'--junitxml={xml}',f'--basetemp={root/("repair_tmp_"+str(index)+"_"+str(shard["shard"]))}']
        result = supervise(argv,root,root/f'repair_part{index}_{shard["shard"]:02d}.log')
        if result['returncode'] or failed_nodes(xml):
            raise RuntimeError('Targeted failure repair did not pass; preserve all evidence')
        cases = list(ET.parse(xml).getroot().iter('testcase'))
        if len(cases)!=len(nodes) or any(case.find('skipped') is not None for case in cases):
            raise RuntimeError('Resource repair coverage differs')
        repairs.append(dict(nodes=nodes,original_failed_nodes=failed_count,execution=result))
    count = sum(row['original_failed_nodes'] for row in repairs)
    if count != original['counts']['failures']+original['counts']['errors']:
        raise RuntimeError('Repair did not cover every initial resource failure')
    effective = {**original,'status':'PASS','counts':{**original['counts'],'failures':0,'errors':0}}
    update = fixture_update()
    if update and update['path'] in effective['test_source_sha256']:
        effective['test_source_sha256'] = {**effective['test_source_sha256'],update['path']:update['sha256']}
    (root/f'part{index}_repair.json').write_text(json.dumps(dict(
        initial_job=previous.name,initial_status=original['status'],original_counts=original['counts'],
        repaired_nodes=count,repairs=repairs,effective_summary=effective),indent=2)+'\n')
    return effective


def fixture_update():
    name = os.environ.get('MFM_CPU_REGRESSION_FIXTURE_UPDATE')
    if not name:
        return None
    path = REPO/'results/model_v3_perf_20261112/regression_fixture_update.json'
    if Path(name).resolve()!=path.resolve():
        raise RuntimeError('Only the reviewed test-fixture update is allowed')
    value=json.loads(path.read_text())
    if value['schema']!='CPU_PERF_REVIEWED_FIXTURE_UPDATE_V1' or value['path']!='current/tests/test_model_v3_training_execution.py':
        raise RuntimeError('Unknown fixture update')
    return value


def resume_completed(previous, root):
    current = {str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((REPO/'current/tests').glob('test_*.py'))}
    summaries = []
    for index in range(8):
        raw = previous/f'part{index}/summary.json'
        continued = previous/f'continued_part{index}.json'
        old_resource = previous/'part0_resource_repair.json'
        if raw.is_file():
            original = json.loads(raw.read_text())
        elif continued.is_file():
            original = json.loads(continued.read_text())['effective_summary']
        elif index==0 and old_resource.is_file():
            original = json.loads(old_resource.read_text())['effective_summary']
        else:
            break
        expected = dict(original['all_test_file_sha256'])
        update = fixture_update()
        if update and expected.get(update['path'])==update['previous_sha256']:
            expected[update['path']]=update['sha256']
        if current != expected:
            raise RuntimeError('Continuation requires unchanged full-suite test sources')
        if original['status']=='FAIL':
            original = repair_partition(previous,root,index,original)
        if original['status']!='PASS':
            raise RuntimeError('Unknown prior regression status')
        (root/f'continued_part{index}.json').write_text(json.dumps(dict(
            source_directory=str(previous),effective_summary=original),indent=2)+'\n')
        summaries.append(original)
    if not summaries:
        raise RuntimeError('No closed partitions to continue')
    return summaries


def main():
    global PRIVATE
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '' or not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('An actual CPU-only Slurm allocation is required')
    cores = allocated_cpus()
    if len(cores) < 16:
        raise ValueError('Existing CLI integration fixtures require an actual sixteen-core allocation')
    os.sched_setaffinity(0, cores)
    root = BASE/'runs/model_v3_cpu_perf_20261112'/('regression_'+os.environ['SLURM_JOB_ID'])
    admission = storage(root)
    root.mkdir(parents=True, exist_ok=False)
    temporary = root/'private_tmp'; temporary.mkdir()
    os.environ['TMPDIR'] = str(temporary)
    os.environ['XDG_CACHE_HOME'] = str(root/'cache')
    if os.environ.get('MFM_CPU_REGRESSION_LOCAL_TMP')=='1':
        from private_runtime_storage import PrivateStorage, _write_exclusive
        require_capacity(filesystem_status('/tmp'), 2*1024**3, 10000)
        PRIVATE = PrivateStorage(Path('/tmp')/('mv3n_'+os.environ['SLURM_JOB_ID']),budget_bytes=2*1024**3)
        receipt = root/'private_storage.json'
        pin = _write_exclusive(receipt,PRIVATE.bindings)
        os.environ.update(PRIVATE.bindings['environment'])
        os.environ['MODEL_V3_STORAGE_BINDINGS_PATH']=str(receipt)
        os.environ['MODEL_V3_STORAGE_BINDINGS_SHA256']=pin
        PRIVATE.start()
    records = []
    summaries = []
    resume = os.environ.get('MFM_CPU_REGRESSION_RESUME_JOB')
    if resume:
        if not resume.isdigit():
            raise ValueError('One original numeric regression job is required')
        previous = root.parent/('regression_'+resume)
        summaries.extend(resume_completed(previous,root))
    for index in range(len(summaries),8):
        argv = [sys.executable, '-B', '-u', str(REPO/'tools/model_v3/run_regression.py'),
            '--root', str(REPO), '--output', str(root/f'part{index}'),
            '--code-commit', os.environ['MFM_CPU_SOURCE_REVISION'], '--workers', '4',
            '--expected-node', os.environ['MFM_CPU_EXPECTED_NODE'],
            '--partitions', '8', '--partition-index', str(index)]
        if fixture_update():
            argv += ['--fixture-update',os.environ['MFM_CPU_REGRESSION_FIXTURE_UPDATE']]
        record = supervise(argv, root, root/f'part{index}.log')
        records.append(record)
        if record['returncode']:
            print(f'PARTITION_{index}_FAILED_PRESERVED_CONTINUING_UNEXECUTED_GROUPS',flush=True)
        summaries.append(json.loads((root/f'part{index}/summary.json').read_text()))
    actual = [path for row in summaries for path in row['test_source_sha256']]
    expected = {str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((REPO/'current/tests').glob('test_*.py'))}
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise RuntimeError('Full regression source coverage differs')
    counts = {key:sum(row['counts'][key] for row in summaries) for key in ('tests','failures','errors','skipped')}
    covered = {path:sha for row in summaries for path,sha in row['test_source_sha256'].items()}
    if covered != expected:
        raise RuntimeError('Covered test sources differ from final actual test sources')
    passed = all(row['status']=='PASS' for row in summaries) and counts['tests']>0 and not counts['failures'] and not counts['errors']
    result = dict(status='PASS' if passed else 'FAIL', job=os.environ['SLURM_JOB_ID'], node=os.environ['MFM_CPU_EXPECTED_NODE'],
        source_revision=os.environ['MFM_CPU_SOURCE_REVISION'], cpu_affinity=cores,
        continued_from_job=resume,
        pytest_processes=4, test_file_count=len(actual), counts=counts, admission=admission,
        final_capacity=storage(root), partitions=records)
    if PRIVATE is not None:
        result['private_storage']=PRIVATE.check()
    (root/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status','job','node','test_file_count','counts')}), flush=True)
    return int(not passed)


if __name__ == '__main__':
    try:
        code = main()
    finally:
        if PRIVATE is not None:
            PRIVATE.stop()
    raise SystemExit(code)
