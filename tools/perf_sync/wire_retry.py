"""Retry only the legacy wire cases whose fixture required physical /tmp."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from regression import REPO, OUTPUT, SCRATCH, LIMIT, capacity, counts


def main():
    job = os.environ['SLURM_JOB_ID']
    if not job.isdigit():raise ValueError('Actual Slurm job ID required')
    local = Path('/tmp')/('perf_sync_wire_'+job)
    capacity()
    sys.path.insert(0,str(REPO.parent/'MFM_p_recipe/tools/model_v3'))
    import v2_diagnosis_disk as disk

    def guard():
        capacity()
        disk.m.require_capacity(disk.m.filesystem_status('/tmp'),512*1024**2,1000)
        roots = (SCRATCH, REPO/'results/perf_sync/scratch', local)
        allocated = sum(p.stat().st_blocks*512 for root in roots if root.exists()
                        for p in root.rglob('*') if p.is_file())
        if allocated > LIMIT:raise OSError('Combined NFS and node-local scratch exceeded 20 GiB')
    guard()
    if local.parent != Path('/tmp') or local.exists():raise ValueError('Fresh owned /tmp directory required')
    local.mkdir(mode=0o700)
    original = OUTPUT/'test_model_v3_wire_provider.xml'
    failed = [case.attrib['name'] for case in ET.parse(original).getroot().iter('testcase')
              if case.find('error') is not None]
    if len(failed) != 25:raise ValueError('Inspect changed wire failure set before retrying')
    xml = OUTPUT/('wire_retry_'+job+'.xml')
    nodes = [str(REPO/'current/tests/test_model_v3_wire_provider.py')+'::'+name for name in failed]
    command = [sys.executable,'-B','-m','pytest',*nodes,'-q','-p','no:cacheprovider',
               '--basetemp='+str(SCRATCH/('wire_closure_'+job)),'--junitxml='+str(xml)]
    environment = dict(os.environ,TMPDIR=str(local),CUDA_VISIBLE_DEVICES='',
        OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',XDG_CACHE_HOME=str(SCRATCH/'cache'))
    with (OUTPUT/('wire_retry_'+job+'.log')).open('w') as log:
        child = subprocess.Popen(command,cwd=REPO/'current',env=environment,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while child.poll() is None:
                guard()
                time.sleep(5)
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM);child.wait()
            raise
    result = dict(returncode=child.returncode,counts=counts(xml),selected_cases=failed,
                  original_passed_cases_retained=1,job_id=int(job),local_scratch=str(local))
    (REPO/'results/perf_sync/wire_retry_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return child.returncode


if __name__ == '__main__':
    raise SystemExit(main())
