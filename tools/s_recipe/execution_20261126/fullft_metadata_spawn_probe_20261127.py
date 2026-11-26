"""Trace only this child's real small metadata subprocesses, never GPU fitting."""
import json
import os
import resource
import subprocess
import sys
commands=[['/usr/bin/scontrol','show','node','compute-0-11','-o'],
    [sys.executable,'-I','/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools/shared_guard.py',
     'check','s-recipe','node_ram',str(4*1024**3)]]
for command in commands:
    child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
        stdin=subprocess.DEVNULL)
    out,err=child.communicate(timeout=20)
    if child.returncode:raise ValueError('Metadata probe failed: '+err)
print(json.dumps(dict(pid=os.getpid(),python=sys.executable,version=sys.version,
    use_vfork=getattr(subprocess,'_USE_VFORK',False),commands=commands,
    metadata_peak_RSS_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)),flush=True)
