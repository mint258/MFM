"""Create an immutable original-code reference after actual NFS admission."""
import json,os,subprocess,time
from pathlib import Path
base=Path('/share/home/zixiao/descriptor_analysis')
repo=base/'MFM_model_v3_cpu_perf_20261112';ref=base/'MFM_model_v3_cpu_reference_20261112'
if ref.exists():
    print('REFERENCE_EXISTS',ref)
else:
    stats=os.statvfs(base)
    assert stats.f_bavail*stats.f_frsize>=100_000_000_000+128*1024**2 and stats.f_favail>5000
    quota=json.loads((base/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json').read_text())
    assert quota['uid']==os.getuid() and 0<=time.time()-quota['observed_time']<=5
    assert quota['available_bytes']>=100_000_000_000+23_179_869_184+8*1024**3+128*1024**2
    subprocess.run(['git','-C',str(repo),'worktree','add','--detach',str(ref),'1e73edf6284784f9c20d594955bb439d85826fdd'],check=True)
