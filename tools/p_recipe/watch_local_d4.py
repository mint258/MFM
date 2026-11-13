"""Protect actual node-local D4 output while retaining all generated files."""
import argparse,importlib.util,json,os,stat,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/MFM_p_recipe')
spec=importlib.util.spec_from_file_location('disk',R/'tools/model_v3/v2_watch_disk.py')
disk=importlib.util.module_from_spec(spec);spec.loader.exec_module(disk)

def remaining(root,peak):
    allocated=0
    if root.exists():
        for path in root.rglob('*'):
            try:info=path.lstat()
            except FileNotFoundError:continue  # producer atomically renamed its own metadata
            if stat.S_ISREG(info.st_mode):allocated+=info.st_blocks*512
    return max(1024**3,peak-allocated)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--peak',type=int,required=True)
    p.add_argument('--job',required=True);p.add_argument('--once',action='store_true');a=p.parse_args()
    root=Path(a.root)
    while True:
        future=remaining(root,a.peak)
        try:disk.require_capacity(disk.filesystem_status(root),future,20000)
        except OSError as error:
            print(json.dumps(dict(status='LOCAL_DISK_PAUSED',reason=str(error))),flush=True)
            if a.once:raise
            subprocess.run(['scancel','--signal=STOP','--full',a.job],check=True)
        if a.once:
            print(json.dumps(dict(status='LOCAL_DISK_ADMITTED',future_bytes=future,
                filesystem=disk.filesystem_status(root))),flush=True);return
        time.sleep(5)

if __name__=='__main__':main()
