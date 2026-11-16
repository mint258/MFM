"""Inspect candidate extra GPU lanes once at the scheduled root check; no job mutation."""
import csv,datetime,json,re,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
candidates=['compute-0-1','compute-0-3','compute-0-4','compute-0-21','compute-0-22']
def call(argv):
 try:
  p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
  return dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
 except subprocess.TimeoutExpired as error:
  return dict(returncode=124,stdout=str(error.stdout or ''),stderr='Resource observation timed out; availability unknown')
def remote(node,command):
 return call(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes',node,command])
rows=[];eligible=[]
for node in candidates:
 controller=call(['scontrol','show','node',node,'-o'])
 row=dict(node=node,controller=controller);rows.append(row)
 if controller['returncode']:continue
 text=controller['stdout']
 total=re.search(r'\bCPUTot=(\d+)',text);allocated=re.search(r'\bCPUAlloc=(\d+)',text)
 if not total or not allocated or int(total[1])-int(allocated[1])<16:
  row['status']='NO_IDLE_16CPU';continue
 if any(x in text for x in ('DRAIN','DOWN','NO_RESPOND','NOT_RESPOND')):
  row['status']='NODE_UNAVAILABLE';continue
 row['idle_CPUs']=int(total[1])-int(allocated[1])
 gpu=remote(node,'nvidia-smi --query-gpu=uuid,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits')
 row['GPU']=gpu
 if gpu['returncode']:row['status']='GPU_OBSERVATION_UNAVAILABLE';continue
 contexts=remote(node,'nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader,nounits')
 row['contexts']=contexts
 if contexts['returncode']:row['status']='CONTEXT_OBSERVATION_UNAVAILABLE';continue
 busy={values[0].strip() for values in csv.reader(contexts['stdout'].splitlines()) if values}
 devices=list(csv.reader(gpu['stdout'].splitlines()))
 for uuid,name,memory,used,utilization in devices:
  uuid,name=uuid.strip(),name.strip()
  if uuid in busy or float(utilization.strip())>0:continue
  python=('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
   if '5090' in name else '/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python')
  capacity=remote(node,'df -B1 / /lfshome/zixiao /share/home/zixiao/descriptor_analysis')
  inodes=remote(node,'df -Pi / /lfshome/zixiao /share/home/zixiao/descriptor_analysis')
  mount=remote(node,'findmnt -T /lfshome/zixiao')
  memory_state=remote(node,'head -3 /proc/meminfo')
  interpreter=remote(node,'test -x '+python)
  entry=dict(node=node,gpu=uuid,GPU_name=name,memory_total_MiB=memory.strip(),
   memory_used_MiB=used.strip(),idle_CPUs=row['idle_CPUs'],python=python,
   capacity=capacity,inodes=inodes,mount=mount,memory=memory_state,interpreter=interpreter)
  row.setdefault('empty_devices',[]).append(entry)
  if not any(x['returncode'] for x in (capacity,inodes,mount,memory_state,interpreter)):eligible.append(entry)
 row['status']='RESOURCE_OBSERVATIONS_RECORDED'
value=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 nodes=rows,empty_GPU_candidates=eligible,jobs_changed=False)
path=C/('MODEL_V3_extra_GPU_scan_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M')+'.json')
path.write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(dict(path=str(path),empty_GPU_candidates=eligible,
 statuses=[dict(node=r['node'],status=r.get('status')) for r in rows])))
