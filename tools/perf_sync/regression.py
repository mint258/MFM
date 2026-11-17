"""One final module-by-module regression with owned scratch bounded to 20 GiB."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
OUTPUT = REPO/'results/perf_sync/regression'
SCRATCH = REPO/'results/perf_sync/scratch'
LIMIT = 20*1024**3


def capacity():
    sys.path.insert(0,str(REPO.parent/'MFM_p_recipe/tools/model_v3'))
    import v2_diagnosis_disk as disk
    allocated = sum(p.stat().st_blocks*512 for p in SCRATCH.rglob('*') if p.is_file()) if SCRATCH.exists() else 0
    if allocated > LIMIT:
        raise OSError('Owned scratch exceeded 20 GiB')
    remaining = LIMIT-allocated
    disk.m.require_capacity(disk.m.filesystem_status('/'),0,0)
    disk.m.require_capacity(disk.m.filesystem_status(REPO),remaining+1024**3,10000)
    disk.m.quota_headroom(disk.CONTROL/'share_quota_available_v3.json','/share',
                         remaining+1024**3,70*1024**3)


def counts(path):
    result = dict(tests=0,failures=0,errors=0,skipped=0)
    if path.exists():
        for suite in ET.parse(path).getroot().iter('testsuite'):
            for key in result:
                result[key] += int(suite.get(key,0))
    return result


def main():
    capacity()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    SCRATCH.mkdir(parents=True,exist_ok=True)
    modules = sorted((REPO/'current/tests').glob('test_*.py'))
    modules.append(REPO/'tools/perf_sync/test_execution.py')
    environment = dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
        PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(REPO/'current')+':'+str(REPO.parent/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'),
        TMPDIR=str(SCRATCH),XDG_CACHE_HOME=str(SCRATCH/'cache'),
        TORCHINDUCTOR_CACHE_DIR=str(SCRATCH/'inductor'),TRITON_CACHE_DIR=str(SCRATCH/'triton'))
    started = time.time()
    rows = []
    for index,module in enumerate(modules):
        destination = OUTPUT/module.stem
        xml = destination.with_suffix('.xml')
        if xml.exists():
            # Infrastructure resumption reuses completed modules, including failures.
            row = dict(module=module.name,returncode=int(bool(counts(xml)['failures']+counts(xml)['errors'])),
                       counts=counts(xml),retained=True)
        else:
            capacity()
            temporary = SCRATCH/('pytest_'+str(index))
            command = [sys.executable,'-B','-m','pytest',str(module),'-q','-p','no:cacheprovider',
                       '--junitxml='+str(xml),'--basetemp='+str(temporary)]
            with destination.with_suffix('.log').open('w') as log:
                child = subprocess.Popen(command,cwd=REPO/'current',env=environment,
                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    while child.poll() is None:
                        capacity()
                        time.sleep(5)
                except BaseException:
                    if child.poll() is None:
                        os.killpg(child.pid,signal.SIGTERM)
                        child.wait()
                    raise
            row = dict(module=module.name,returncode=child.returncode,counts=counts(xml))
            if temporary.exists():
                resolved = temporary.resolve()
                if resolved.parent != SCRATCH.resolve() or resolved.is_symlink():
                    raise RuntimeError('Scratch cleanup escaped owned scope')
                shutil.rmtree(resolved)
        rows.append(row)
        print(json.dumps(row),flush=True)
    result = dict(status='PASS' if all(row['returncode']==0 for row in rows) else 'FAIL',
        started_at=started,elapsed_seconds=time.time()-started,modules=rows,
        counts={key:sum(row['counts'][key] for row in rows) for key in ('tests','failures','errors','skipped')},
        gpu_acceptance=False)
    (REPO/'results/perf_sync/regression_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return int(result['status']!='PASS')


if __name__ == '__main__':
    raise SystemExit(main())
