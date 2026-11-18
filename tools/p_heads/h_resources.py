"""Shared actual-node NFS capacity guard for H/T; no writes to Lustre."""
import importlib.util,json,os,pathlib,socket,time,threading,tempfile
R=pathlib.Path('/share/home/zixiao/descriptor_analysis')
REPO=pathlib.Path(__file__).resolve().parents[2]
CONTROL=R/'runs/p_heads_20261117'
FOLLOWUP=R/'runs/p_followup_20261116'
GIB=1024**3
spec=importlib.util.spec_from_file_location('p_heads_existing_disk',REPO/'tools/model_v3/v2_diagnosis_disk.py')
disk=importlib.util.module_from_spec(spec);spec.loader.exec_module(disk)
_last=0.;_capacity=None

def load(path):return json.loads(pathlib.Path(path).read_text())

def allocated(path):
 total=0;seen=set()
 if not path.exists():return 0
 for directory,_,files in os.walk(path):
  for name in files:
   try:s=(pathlib.Path(directory)/name).lstat()
   except FileNotFoundError:continue
   key=(s.st_dev,s.st_ino)
   if key not in seen:seen.add(key);total+=s.st_blocks*512
 return total

def guard(force=False):
 global _last,_capacity
 now=time.monotonic()
 if not force and now-_last<2:return _capacity
 host=socket.gethostname().split('.')[0]
 if not host.startswith('compute-') or host=='compute-0-21':raise OSError('Only permitted actual compute nodes may execute H/T')
 policy=load(REPO/'configs/p_heads/resources.json')
 own=allocated(CONTROL)+allocated(REPO)
 if own>policy['peak_total_bytes']:raise OSError('p-heads total peak budget exceeded')
 future=max(0,policy['peak_total_bytes']-own)
 other=max(0,policy['other_followup_nfs_peak_bytes']-allocated(FOLLOWUP)-allocated(R/'MFM_p_followup_20261117'))
 concurrent=disk.remaining_nfs_other()+18_000_000_000+other
 root=disk.m.filesystem_status('/');target=disk.m.filesystem_status(R)
 disk.m.require_capacity(root,16*1024**2,1000)
 disk.m.require_capacity(target,future+concurrent,10000)
 quota=disk.m.quota_headroom(disk.CONTROL/'share_quota_available_v3.json','/share',future,concurrent)
 _capacity=dict(node=host,root=root,target=target,quota=quota,own_allocated=own,own_remaining=future,other_followup_remaining=other)
 _last=now;return _capacity

def save(path,value):
 guard();path=pathlib.Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
 payload=json.dumps(value,indent=2,allow_nan=False)+'\n';pending=None
 try:mode=path.stat().st_mode&0o777
 except FileNotFoundError:mode=None
 try:
  with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='.'+path.name+'.',suffix='.tmp',delete=False) as stream:
   pending=pathlib.Path(stream.name);stream.write(payload)
  if mode is not None:os.chmod(pending,mode)
  os.replace(pending,path)
 finally:
  if pending is not None:pending.unlink(missing_ok=True)

def watchdog(interval=2):
 """Stop only this worker on failed admission, before subsequent writes."""
 guard(force=True)
 def watch():
  while True:
   time.sleep(interval)
   try:guard(force=True)
   except BaseException as e:
    print('P_HEADS_DISK_STOP',str(e),flush=True);os._exit(75)
 thread=threading.Thread(target=watch,daemon=True);thread.start();return thread
