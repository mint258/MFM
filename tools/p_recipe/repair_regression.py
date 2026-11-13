"""Repair only failed test nodes from the single full regression."""
import argparse,concurrent.futures,json,os,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
BASE=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/regression_pR1')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source',default='original',choices=('original','repair1'));parser.add_argument('--destination');args=parser.parse_args()
 source=BASE if args.source=='original' else BASE/'repair1'
 original=json.loads((source/'summary.json').read_text());out=BASE/(args.destination or ('repair1' if args.source=='original' else 'repair2'));out.mkdir()
 storage=None
 if os.environ.get('SLURM_JOB_ID'):
  project=Path('/share/home/zixiao/descriptor_analysis')
  os.environ['PATH']=str(project/'runs/model_v3_20261025/cpu_git_tools_v1/bin')+':'+os.environ.get('PATH','')
  os.environ.setdefault('PHASE1_NATIVE_TRANSPORT_PATH',str(project/'docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py'))
  os.environ.setdefault('PHASE1_JOINT_REFERENCE_PATH',str(project/'docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py'))
  sys.path.insert(0,str(REPO/'tools/model_v3'))
  from private_runtime_storage import PrivateStorage,_write_exclusive
  storage=PrivateStorage(Path('/tmp')/('mv3n_'+os.environ['SLURM_JOB_ID']),budget_bytes=2*1024**3)
  pin=_write_exclusive(out/'private_storage.json',storage.bindings);os.environ.update(storage.bindings['environment'])
  os.environ['MODEL_V3_STORAGE_BINDINGS_PATH']=str(out/'private_storage.json');os.environ['MODEL_V3_STORAGE_BINDINGS_SHA256']=pin;storage.start()
  local=Path('/tmp')/('mpTests_'+os.environ['SLURM_JOB_ID']);local.mkdir(mode=0o700)
 else:
  local=Path('/tmp/mp_pR1/r');local.mkdir(exist_ok=True)
 if storage is None:
  for key,name in (('TMPDIR','/tmp/mp_pR1/tmp'),('XDG_CACHE_HOME','/tmp/mp_pR1/cache')):os.environ[key]=name
 work=[]
 pending=original['failed_modules'] if args.source=='original' else [r for r in original['rows'] if r['returncode']]
 for row in pending:
  stem=Path(row['module']).stem;module=stem+'.py';nodes=[]
  for case in ET.parse(source/(stem+'.xml')).getroot().iter('testcase'):
   if case.find('failure') is None and case.find('error') is None:continue
   cls=case.attrib['classname'];prefix=cls.split(stem+'.',1)[1].replace('.','::')+'::' if stem+'.' in cls else ''
   nodes.append(str(REPO/'current/tests'/module)+'::'+prefix+case.attrib['name'])
  work.append((stem,nodes))
 def run(index_work):
  index,(stem,nodes)=index_work;xml=out/(stem+'.xml')
  with (out/(stem+'.log')).open('wb') as stream:
   r=subprocess.run([sys.executable,'-B','-m','pytest',*nodes,'-q','-p','no:cacheprovider','--junitxml='+str(xml),'--basetemp='+str(local/str(index))],cwd=REPO/'current',stdout=stream,stderr=subprocess.STDOUT)
  counts={k:0 for k in ('tests','failures','errors','skipped')}
  if xml.exists():
   for suite in ET.parse(xml).getroot().iter('testsuite'):
    for k in counts:counts[k]+=int(suite.get(k,0))
  row=dict(module=stem,requested_failed_nodes=len(nodes),returncode=r.returncode,counts=counts)
  print(json.dumps(row),flush=True);return row
 started=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(4) as pool:rows=list(pool.map(run,enumerate(work)))
 passed=all(r['returncode']==0 and r['counts']['tests']==r['requested_failed_nodes'] and not r['counts']['skipped'] for r in rows)
 result=dict(status='PASS' if passed else 'FAIL',original_result_preserved=str(BASE/'summary.json'),original_counts=original.get('counts',original.get('original_counts')),repaired_nodes=sum(r['requested_failed_nodes'] for r in rows),rows=rows,seconds=time.monotonic()-started,scope='Only original failure/error nodes; completed passes retained')
 if passed:result['effective_counts']={**result['original_counts'],'failures':0,'errors':0}
 if storage is not None:
  try:storage.stop()
  except ValueError as error:result['post_test_observer_error']=str(error)
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
 return int(not passed)
if __name__=='__main__':raise SystemExit(main())