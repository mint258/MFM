"""Native development runner for the user's node20-22 <=30% rule."""
import argparse,csv,fcntl,importlib.util,json,os,signal,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2]

def identity(pid):
 path=Path('/proc')/str(pid);fields=(path/'stat').read_text().rsplit(')',1)[1].split()
 return dict(pid=pid,uid=path.stat().st_uid,start_ticks=int(fields[19]),pgid=os.getpgid(pid))

def record_gpu_telemetry(configuration):
 """Actual running-arm throughput context and whole-card power; no benchmark."""
 c=configuration;output=Path(c['output']);samples=0;elapsed=None
 try:
  with (output/'losses.csv').open('rb') as source:
   source.seek(max(0,source.seek(0,2)-8192));lines=source.read().decode().splitlines()
  row=next(row for row in reversed(list(csv.reader(lines))) if len(row)==6 and row[0].isdigit())
  samples=int(row[0]);elapsed=float(row[5])
 except (FileNotFoundError,StopIteration,ValueError):pass
 if samples<=0 or samples>=c['training_budget']:return
 query=['nvidia-smi','--id='+c['gpu_uuid'],'--query-gpu=uuid,name,power.draw,utilization.gpu,memory.used','--format=csv,noheader,nounits']
 gpu=next(csv.reader(subprocess.check_output(query,text=True,timeout=10).splitlines()))
 path=REPO/'results/p_recipe/training'/c['run']/'gpu_telemetry.csv';path.parent.mkdir(parents=True,exist_ok=True)
 exists=path.exists()
 with path.open('a',newline='') as stream:
  writer=csv.writer(stream)
  if not exists:writer.writerow(['timestamp_utc_epoch','run','gpu_uuid','gpu_name','batch_size','samples','training_seconds','power_watts','utilization_percent','memory_used_mib'])
  writer.writerow([time.time(),c['run'],gpu[0].strip(),gpu[1].strip(),c['batch_size'],samples,elapsed,*[v.strip() for v in gpu[2:]]])

def main():
 p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args();c=json.loads(Path(a.configuration).read_text())
 node=socket.gethostname().split('.')[0]
 if node!=c['node'] or node not in ('compute-0-20','compute-0-21','compute-0-22'):raise ValueError('Native rule is limited to the actual configured node20-22')
 gpu=c['gpu_uuid'];rows=csv.reader(subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.used,memory.total','--format=csv,noheader,nounits'],text=True).splitlines())
 card=next(row for row in rows if row[0].strip()==gpu);used,total=map(lambda x:float(x.strip()),card[1:])
 if used/total>.30:raise RuntimeError('GPU occupancy exceeds user30% native-start rule')
 locks=R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'
 lock=None
 if c.get('gpu_work',True):
  lock=(locks/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 spec=importlib.util.spec_from_file_location('disk',REPO/'tools/model_v3/v2_diagnosis_disk.py');disk=importlib.util.module_from_spec(spec);spec.loader.exec_module(disk)
 def capacity():
  allocated,remaining=disk.model_growth_forecast()
  future=c.get('root_future_bytes',0)
  disk.m.require_capacity(disk.m.filesystem_status('/'),future,2000)
  disk.m.require_capacity(disk.m.filesystem_status(c['output']),remaining,10000)
  disk.m.require_capacity(disk.m.filesystem_status(R/'runs/model_v31_20261105'),67108864,1000)
  disk.m.quota_headroom(disk.CONTROL/'lustre_quota_available_v2_20261107.json','/lfshome',remaining,disk.remaining_d6()+6000000000)
  disk.m.quota_headroom(disk.CONTROL/'share_quota_available_v3.json','/share',67108864,disk.remaining_nfs_other())
 capacity()
 environment=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,P_RECIPE_RUN_ID=c['run'],PYTHONDONTWRITEBYTECODE='1',PYTORCH_ALLOC_CONF='expandable_segments:True',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONPATH=str(REPO/'current')+':'+str(R/'runs/data_v1_20261025/repository')+':'+str(R/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'))
 environment.update(c.get('environment',{}))
 if not c.get('gpu_work',True):environment['CUDA_VISIBLE_DEVICES']=''
 for key in list(environment):
  if key.startswith('SLURM_'):environment.pop(key)
 child=subprocess.Popen(c['command'],cwd=REPO,env=environment,start_new_session=True)
 bound=identity(child.pid);record=dict(started_at=time.time(),run=c['run'],execution='native_SSH',node=node,gpu_uuid=gpu,admission_used_mib=used,admission_total_mib=total,admission_fraction=used/total,**bound)
 state=R/'runs/p_recipe_20261113'/(c['run']+'_native.json')
 def save(**values):
  record.update(values)
  try:state.write_text(json.dumps(record,indent=2)+'\n')
  except OSError as error:record['state_write_error']=str(error)
 save(status='RUNNING');print(json.dumps(record),flush=True);paused=False
 while child.poll() is None:
  try:capacity();ok=True
  except (OSError,ValueError,KeyError,TypeError) as e:ok=False;save(status='DISK_PAUSED',disk_reason=str(e))
  if ok==paused and child.poll() is None:
   try:
    if identity(child.pid)!=bound:raise RuntimeError('Own native process identity changed')
    os.killpg(bound['pgid'],signal.SIGCONT if ok else signal.SIGSTOP);paused=not ok
    save(status='RUNNING' if ok else 'DISK_PAUSED')
   except ProcessLookupError:pass
  time.sleep(5)
 code=child.wait();save(status='COMPLETED' if code==0 else 'FAILED',exit_code=code,ended_at=time.time(),elapsed_seconds=time.time()-record['started_at']);return code
if __name__=='__main__':raise SystemExit(main())
