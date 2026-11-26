"""The final full regression, once, using the existing four-process policy."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]


def main():
    job = os.environ['SLURM_JOB_ID']
    output = REPO/'results/perf_step_overhead_20261114'/('regression_'+job)
    output.mkdir()
    local = Path('/tmp')/('step_reg_'+job)
    local.mkdir(mode=0o700)
    os.environ['TMPDIR'] = str(local)
    os.environ['XDG_CACHE_HOME'] = str(local/'cache')
    modules = sorted((REPO/'current/tests').glob('test_*.py'))
    started = time.monotonic()
    previous = Path(os.environ['STEP_REG_RESUME']) if os.environ.get('STEP_REG_RESUME') else None

    def counts_from(xml):
        counts = {key:0 for key in ('tests','failures','errors','skipped')}
        for suite in ET.parse(xml).getroot().iter('testsuite'):
            for key in counts:
                counts[key] += int(suite.get(key,0))
        return counts

    def run(item):
        index, path = item
        prior_xml = None if previous is None else previous/(path.stem+'.xml')
        if prior_xml is not None and prior_xml.exists():
            counts = counts_from(prior_xml)
            failed = counts['failures']+counts['errors']
            if not failed or path.name=='test_p_recipe_exclusion.py':
                row = dict(module=path.name,returncode=int(bool(failed)),counts=counts,
                           retained_from=str(prior_xml))
                print(json.dumps(row),flush=True)
                return row
        xml = output/(path.stem+'.xml')
        command = [sys.executable,'-B','-m','pytest',str(path),'-q','-p','no:cacheprovider',
                   '--junitxml='+str(xml),'--basetemp='+str(local/str(index))]
        with (output/(path.stem+'.log')).open('w') as log:
            result = subprocess.run(command,cwd=REPO/'current',stdout=log,stderr=subprocess.STDOUT)
        counts = {key:0 for key in ('tests','failures','errors','skipped')}
        if xml.exists():
            counts = counts_from(xml)
        row = dict(module=path.name,returncode=result.returncode,counts=counts)
        print(json.dumps(row),flush=True)
        return row

    with ThreadPoolExecutor(4) as pool:
        rows = list(pool.map(run,enumerate(modules)))
    counts = {key:sum(row['counts'][key] for row in rows) for key in ('tests','failures','errors','skipped')}
    result = dict(status='PASS' if all(row['returncode']==0 for row in rows) else 'FAIL',
        modules=rows,counts=counts,seconds=time.monotonic()-started,job=job,
        continued_from=None if previous is None else str(previous))
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return int(result['status']!='PASS')


if __name__=='__main__':
    raise SystemExit(main())
