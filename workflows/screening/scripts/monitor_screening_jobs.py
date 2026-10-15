"""Root's hourly batched scheduler/quota metadata snapshot for registered jobs."""
import datetime,json,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
def query(argv):
    p=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=45)
    return {'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
receipts=[]
for path in sorted((ROOT/'logs').glob('*_submission.json')):
    r=json.loads(path.read_text());receipts.append({'job_id':r['job_id'],'name':r.get('name',path.name.split('_2026')[0]),'node':r['node'],'script':r['script'],'receipt':str(path)})
ids=sorted({r['job_id'] for r in receipts},key=int)
r={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'registered_jobs':receipts,
   'accounting':query(['sacct','-X','-j',','.join(ids),'-n','-P','-o','JobID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']),
   'own_queue':query(['squeue','-u','zixiao','-h','-o','%i|%j|%T|%M|%C|%N|%R']),
   'quota':query(['quota','-v','-u','zixiao'])}
path=ROOT/'reports'/('job_snapshot_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
path.write_text(json.dumps(r,indent=2)+'\n');(ROOT/'reports/latest_job_snapshot.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'UTC':r['UTC'],'accounting':r['accounting']['stdout'],'own_queue':r['own_queue']['stdout'],'quota':r['quota']['stdout'],'snapshot':str(path)}))
