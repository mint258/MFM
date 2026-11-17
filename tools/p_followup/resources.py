"""Reuse the real-node disk guard, preserving mainline future growth."""
import importlib.util,json,os,pathlib,time
R=pathlib.Path('/share/home/zixiao/descriptor_analysis');REPO=pathlib.Path(__file__).resolve().parents[2]
CONTROL=R/'runs/p_followup_20261116';OLD=R/'runs/p_data_information_20261115_v1'
SIDE=pathlib.Path('/lfshome/zixiao/data_v1_20261025/p_followup_f64_20261116')
MEAN=CONTROL/'D_mean_table'
TRAIN=pathlib.Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/p_followup_20261116')
GIB=1024**3
spec=importlib.util.spec_from_file_location('followup_existing_disk_guard',REPO/'tools/model_v3/v2_diagnosis_disk.py');disk=importlib.util.module_from_spec(spec);spec.loader.exec_module(disk)
_last=0.;_last_capacity=None

def allocated(path):
 if not path.exists():return 0
 seen=set();total=0
 for directory,subdirs,files in os.walk(path):
  for name in files:
   try:s=(pathlib.Path(directory)/name).lstat()
   except FileNotFoundError:continue
   key=(s.st_dev,s.st_ino)
   if key not in seen:total+=s.st_blocks*512;seen.add(key)
 return total

def guard(force=False, lustre=False):
 global _last,_last_capacity
 now=time.monotonic()
 if not force and now-_last<2:return _last_capacity
 main_allocated,main_future=disk.model_growth_forecast()
 own_training=allocated(TRAIN)
 # The old global scanner sees all P_RECIPE children; do not debit its
 # mainline reservation using these separately reserved side-line outputs.
 if TRAIN.exists() and TRAIN.resolve().stat().st_dev==pathlib.Path('/lfshome').stat().st_dev:main_future+=own_training
 lustre_future=max(0,int(1.1*GIB)-allocated(SIDE))
 nfs_future=max(0,18*GIB-allocated(CONTROL)-allocated(REPO))
 # Preserve the head line's current owner-declared total, debiting physical use.
 heads=R/'MFM_p_heads_20261117/configs/p_heads/resources.json'
 heads_policy=load(heads)
 heads_future=max(0,heads_policy['peak_total_bytes']-allocated(pathlib.Path(heads_policy['control_root']))-allocated(pathlib.Path(heads_policy['repository'])))
 # Mainline declared a separate2GiB NFS reserve for the shared M2 seed1.
 noise_future=max(0,2*GIB-allocated(R/'runs/p_recipe_noise_training'))
 nfs_concurrent=disk.remaining_nfs_other()+18_000_000_000+heads_future+noise_future
 checks=[('/',16*1024**2),(R,nfs_future+nfs_concurrent)]
 if lustre:checks.append((pathlib.Path('/lfshome'),main_future+lustre_future+disk.remaining_d6()+6_000_000_000))
 for path,future in checks:
  disk.m.require_capacity(disk.m.filesystem_status(path),future,10000)
 q=disk.CONTROL
 result=dict(lustre=(disk.m.quota_headroom(q/'lustre_quota_available_v2_20261107.json','/lfshome',main_future+lustre_future,disk.remaining_d6()+6_000_000_000) if lustre else None),share=disk.m.quota_headroom(q/'share_quota_available_v3.json','/share',nfs_future,nfs_concurrent),mainline_remaining=main_future,own_lustre_remaining=lustre_future,own_nfs_remaining=nfs_future,other_heads_remaining=heads_future,shared_M2_seed1_remaining=noise_future)
 _last=now;_last_capacity=result;return result

def load(path):return json.loads(pathlib.Path(path).read_text())
def save(path,value):
 guard();path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')