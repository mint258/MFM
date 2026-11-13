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


def storage(root):
    """Reserve this suite in addition to all existing account forecasts."""
    quota = capacity()
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
        if any('8 >= 16' not in ((error.text or '')+' '+error.get('message','')) for error in errors):
            raise RuntimeError('Prior failure is not the reviewed eight-core resource assertion')
        parts = case.attrib['classname'].split('.')
        if len(parts)<2 or parts[0]!='tests' or not parts[1].startswith('test_'):
            raise RuntimeError('Unknown failing test module')
        path = REPO/'current/tests'/(parts[1]+'.py')
        if not path.is_file():
            raise RuntimeError('Failing test source missing')
        nodes.append(str(path)+'::'+'::'.join(parts[2:]+[case.attrib['name']]))
    return nodes


def resume_first_partition(previous, root):
    original = json.loads((previous/'part0/summary.json').read_text())
    current = {str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((REPO/'current/tests').glob('test_*.py'))}
    if current != original['all_test_file_sha256'] or original['status']!='FAIL':
        raise RuntimeError('Continuation requires the exact unchanged full-suite test sources')
    repairs = []
    for shard in original['shards']:
        nodes = failed_nodes(previous/f'part0/shard_{shard["shard"]:02d}.xml')
        if not nodes:
            continue
        xml = root/f'repair_{shard["shard"]:02d}.xml'
        argv = [sys.executable,'-B','-m','pytest',*nodes,'-q','-p','no:cacheprovider',
                f'--junitxml={xml}',f'--basetemp={root/("repair_tmp_"+str(shard["shard"]))}']
        result = supervise(argv,root,root/f'repair_{shard["shard"]:02d}.log')
        if result['returncode'] or failed_nodes(xml):
            raise RuntimeError('Resource repair did not pass; preserve all evidence')
        cases = list(ET.parse(xml).getroot().iter('testcase'))
        if len(cases)!=len(nodes) or any(case.find('skipped') is not None for case in cases):
            raise RuntimeError('Resource repair coverage differs')
        repairs.append(dict(nodes=nodes,execution=result))
    count = sum(len(row['nodes']) for row in repairs)
    if count != original['counts']['failures']+original['counts']['errors']:
        raise RuntimeError('Repair did not cover every initial resource failure')
    effective = {**original,'status':'PASS','counts':{**original['counts'],'failures':0,'errors':0}}
    (root/'part0_resource_repair.json').write_text(json.dumps(dict(
        initial_job=previous.name,initial_status=original['status'],original_counts=original['counts'],
        repaired_nodes=count,repairs=repairs,effective_summary=effective),indent=2)+'\n')
    return effective


def main():
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
    records = []
    summaries = []
    resume = os.environ.get('MFM_CPU_REGRESSION_RESUME_JOB')
    if resume:
        if not resume.isdigit():
            raise ValueError('One original numeric regression job is required')
        previous = root.parent/('regression_'+resume)
        summaries.append(resume_first_partition(previous,root))
    for index in range(1 if resume else 0,8):
        argv = [sys.executable, '-B', '-u', str(REPO/'tools/model_v3/run_regression.py'),
            '--root', str(REPO), '--output', str(root/f'part{index}'),
            '--code-commit', os.environ['MFM_CPU_SOURCE_REVISION'], '--workers', '4',
            '--expected-node', os.environ['MFM_CPU_EXPECTED_NODE'],
            '--partitions', '8', '--partition-index', str(index)]
        record = supervise(argv, root, root/f'part{index}.log')
        records.append(record)
        if record['returncode']:
            raise RuntimeError(f'Full regression partition {index} failed; preserve evidence')
        summaries.append(json.loads((root/f'part{index}/summary.json').read_text()))
    actual = [path for row in summaries for path in row['test_source_sha256']]
    expected = summaries[0]['all_test_file_sha256']
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise RuntimeError('Full regression source coverage differs')
    counts = {key:sum(row['counts'][key] for row in summaries) for key in ('tests','failures','errors','skipped')}
    if any(row['status'] != 'PASS' for row in summaries) or not counts['tests'] or counts['failures'] or counts['errors']:
        raise RuntimeError('Full regression did not pass')
    result = dict(status='PASS', job=os.environ['SLURM_JOB_ID'], node=os.environ['MFM_CPU_EXPECTED_NODE'],
        source_revision=os.environ['MFM_CPU_SOURCE_REVISION'], cpu_affinity=cores,
        continued_from_job=resume,
        pytest_processes=4, test_file_count=len(actual), counts=counts, admission=admission,
        final_capacity=storage(root), partitions=records)
    (root/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status','job','node','test_file_count','counts')}), flush=True)


if __name__ == '__main__':
    main()
