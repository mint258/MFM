"""Short-lived login-node quota metadata publisher; no scientific computation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

p=argparse.ArgumentParser()
p.add_argument("--output",type=Path,required=True)
p.add_argument("--generation",required=True)
p.add_argument("--stop",type=Path,required=True)
p.add_argument("--lifetime-seconds",type=int,default=900)
a=p.parse_args()
started=time.monotonic()
while time.monotonic()-started<a.lifetime_seconds and not a.stop.exists():
    try:
        r=subprocess.run(["quota","-v","-u","zixiao"],capture_output=True,text=True,timeout=25)
        record={"uid":os.getuid(),"pid":os.getpid(),"generation":a.generation,
                "observed_epoch":time.time(),"returncode":r.returncode,
                "raw":r.stdout,"stderr":r.stderr,"state":"RUNNING"}
    except subprocess.TimeoutExpired:
        record={"uid":os.getuid(),"pid":os.getpid(),"generation":a.generation,
                "observed_epoch":time.time(),"returncode":-1,"raw":"",
                "state":"QUOTA_TIMEOUT"}
    temp=a.output.with_suffix(".pending")
    temp.write_text(json.dumps(record))
    os.replace(temp,a.output)
    time.sleep(10)
