"""Copy only the closed step-1 profiling artifacts with actual-target disk guards."""
import importlib.util,json,os,shutil,time
from pathlib import Path
repo=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112')
root=Path('/lfshome/zixiao/model_v3_perf_20261112/step1_4530262')
output=repo/'results/model_v3_perf_20261112/profiling_4530262'
spec=importlib.util.spec_from_file_location('disk',repo/'current/phychem_mfm/phase1/v2_disk.py')
disk=importlib.util.module_from_spec(spec);spec.loader.exec_module(disk)
files=('segments/summary.csv','segments/segments.csv','flame.svg','baseline_telemetry.csv','profile_telemetry.csv','baseline/losses.csv')
peak=sum((root/name).stat().st_size for name in files)
def check(remaining):
    disk.require_capacity(disk.filesystem_status('/'),0,0)
    disk.require_capacity(disk.filesystem_status(output),remaining,32)
    path=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json')
    value=json.loads(path.read_text())
    assert value['uid']==os.getuid() and value['filesystem']=='/share'
    if not 0<=time.time()-value['observed_time']<=5: raise OSError('Unknown fresh NFS quota')
    if value['available_bytes']<100_000_000_000+23_179_869_184+8*1024**3+remaining: raise OSError('NFS quota forecast insufficient')
check(peak)
for name in files:
    source=root/name;target=output/name
    if target.exists(): continue
    check(peak)
    target.parent.mkdir(parents=True,exist_ok=True)
    with source.open('rb') as inp,target.open('xb') as out:
        while chunk:=inp.read(128*1024):
            check(peak)
            out.write(chunk);peak-=len(chunk)
    print(name,target.stat().st_size,flush=True)
