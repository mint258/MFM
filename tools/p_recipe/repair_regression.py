"""Repair only failed test nodes from the single full regression."""
import concurrent.futures,json,os,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
BASE=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/regression_pR1')
def main():
 original=json.loads((BASE/'summary.json').read_text());out=BASE/'repair1';out.mkdir()
 local=Path('/tmp/mp_pR1/r');local.mkdir(exist_ok=True)
 for key,name in (('TMPDIR','/tmp/mp_pR1/tmp'),('XDG_CACHE_HOME','/tmp/mp_pR1/cache')):os.environ[key]=name
 work=[]
 for row in original['failed_modules']:
  stem=Path(row['module']).stem;nodes=[]
  for case in ET.parse(BASE/(stem+'.xml')).getroot().iter('testcase'):
   if case.find('failure') is None and case.find('error') is None:continue
   cls=case.attrib['classname'];prefix=cls.split(stem+'.',1)[1].replace('.','::')+'::' if stem+'.' in cls else ''
   nodes.append(str(REPO/'current/tests'/row['module'])+'::'+prefix+case.attrib['name'])
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
 result=dict(status='PASS' if passed else 'FAIL',original_result_preserved=str(BASE/'summary.json'),original_counts=original['counts'],repaired_nodes=sum(r['requested_failed_nodes'] for r in rows),rows=rows,seconds=time.monotonic()-started,scope='Only original failure/error nodes; completed passes retained')
 if passed:result['effective_counts']={**original['counts'],'failures':0,'errors':0}
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
 return int(not passed)
if __name__=='__main__':raise SystemExit(main())