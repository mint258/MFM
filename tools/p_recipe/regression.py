"""One full core regression after PR6, using four isolated CPU pytest workers."""
import concurrent.futures,json,os,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
def main(*, output=None, scratch=None, workers=4, modules=None, preserve_storage_environment=False):
 run_id=os.environ.get('SLURM_JOB_ID') or os.environ.get('P_RECIPE_RUN_ID')
 root=Path(output) if output is not None else Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113')/('regression_'+run_id);root.mkdir()
 local=Path(scratch) if scratch is not None else Path('/tmp')/('mp_'+run_id)
 sys.path.insert(0,str(REPO/'tools/model_v3'))
 local.mkdir(mode=0o700);(local/"t").mkdir()
 for key,name in ([] if preserve_storage_environment else [('TMPDIR','tmp'),('XDG_CACHE_HOME','cache'),('TORCHINDUCTOR_CACHE_DIR','inductor')]):
  target=local/name;target.mkdir();os.environ[key]=str(target)
 files=sorted((REPO/'current/tests').glob('test_*.py'))
 if modules is not None:
  wanted=set(modules);files=[p for p in files if p.name in wanted]
  if {p.name for p in files}!=wanted:raise ValueError('Requested regression modules are missing')
 started=time.monotonic()
 def run(index_path):
  index,path=index_path;key=path.stem;xml=root/(key+'.xml');argv=[sys.executable,'-B','-m','pytest',str(path),'-q','-p','no:cacheprovider','--junitxml='+str(xml),'--basetemp='+str(local/'t'/str(index))]
  with (root/(key+'.log')).open('wb') as stream:r=subprocess.run(argv,cwd=REPO/'current',stdout=stream,stderr=subprocess.STDOUT)
  counts={k:0 for k in ('tests','failures','errors','skipped')}
  if xml.exists():
   for suite in ET.parse(xml).getroot().iter('testsuite'):
    for k in counts:counts[k]+=int(suite.get(k,0))
  row=dict(module=path.name,returncode=r.returncode,counts=counts)
  (root/(key+'.json')).write_text(json.dumps(row)+'\n');print(json.dumps(row),flush=True);return row
 with concurrent.futures.ThreadPoolExecutor(workers) as pool:rows=list(pool.map(run,enumerate(files)))
 counts={k:sum(r['counts'][k] for r in rows) for k in ('tests','failures','errors','skipped')}
 result=dict(status='PASS' if all(r['returncode']==0 for r in rows) else 'FAIL',counts=counts,modules=len(rows),seconds=time.monotonic()-started,reason='Full current/tests CPU regression with isolated modules',workers=workers,failed_modules=[r for r in rows if r['returncode']])
 (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
 return int(result['status']!='PASS')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--scratch');p.add_argument('--workers',type=int,default=4);p.add_argument('--modules',nargs='+');p.add_argument('--preserve-storage-environment',action='store_true');a=p.parse_args()
 raise SystemExit(main(output=a.output,scratch=a.scratch,workers=a.workers,modules=a.modules,preserve_storage_environment=a.preserve_storage_environment))