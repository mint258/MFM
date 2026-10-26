"""Metadata census on the exact original compute host; retain the original identity gate."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
from long_common import *


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=Path,required=True)
    parser.add_argument('--submission',type=Path,required=True)
    parser.add_argument('--submission-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True)
    args=parser.parse_args();manifest,_=verify(args.pins_sha256)
    require(os.getuid()==1278 and socket.gethostname()==NODE,'Census must run as original UID on original compute host')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','Metadata-only census must hide CUDA')
    source=binding(args.submission);require(source['sha256']==args.submission_sha256,'Submission bytes changed')
    frame=read_ref(source);require(frame['phase']==str(args.phase),'Census phase differs')
    argv=frame['actual_sbatch']['argv']
    require(argv.count('--nodelist='+NODE)==1,'Original actual node differs')
    management=slot_layout(args.phase,frame['slot'])['management']
    baseline=read(management/'ledger_baseline.json')
    stdio=read(management/'actual_supervisor_launch.json')['stdio']
    # Exactly the same baseline device+inode check as inside this job, on
    # exactly its host. Root/login st_dev is never substituted or compared.
    import sys
    sys.path.insert(0,str(RUNTIME/'tools/model_v3'))
    import runtime_monitor,long_frames
    current=long_frames.whole_census(args.phase,frame['actual_sbatch_job_id'],stdio,baseline,runtime_monitor)
    print(json.dumps(dict(schema='native_S_same_host_census_observation_v1',
        host=socket.gethostname(),uid=os.getuid(),submission=source,operational_manifest=manifest,
        actual_census_source=binding(HERE/'long_frames.py'),baseline=binding(management/'ledger_baseline.json'),
        current=current,model_or_payload_read=False),allow_nan=False,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
