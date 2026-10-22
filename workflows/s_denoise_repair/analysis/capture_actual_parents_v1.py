"""Sonmi-only read-only actual Slurm accounting capture; no submissions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phases',nargs='+',required=True)
    parser.add_argument('--include-tests',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert args.output.is_absolute() and args.output.is_relative_to(ROOT/'control/accounting_snapshots')
    assert not args.output.exists()
    ids=set();inputs=[]
    for phase in args.phases:
        path=ROOT/'control'/phase/'jobs.json'
        jobs=json.loads(path.read_text());inputs.append(dict(path=str(path),sha256=sha(path)))
        ids.update(j['job_id'] for j in jobs.values())
    if args.include_tests:
        path=ROOT/'configs/D3_source_binding_v4.json'
        binding=json.loads(path.read_text());inputs.append(dict(path=str(path),sha256=sha(path)))
        ids.update(j['job_id'] for j in binding['C6_actual_job_closure'].values())
    assert ids and all(i.isdecimal() for i in ids)
    command=['sacct','-X','-j',','.join(sorted(ids)),'-n','-P','-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS']
    attempts=[]
    for attempt in range(3):
        result=subprocess.run(command,stdin=subprocess.DEVNULL,text=True,capture_output=True,timeout=60)
        attempts.append(dict(returncode=result.returncode,stderr=result.stderr))
        if result.returncode==0:break
        if attempt<2:time.sleep(2*(attempt+1))
    assert result.returncode==0,attempts
    rows={r[0]:r[1:] for r in (line.split('|') for line in result.stdout.splitlines()) if r[0] in ids}
    assert set(rows)==ids and all(len(row)==4 for row in rows.values())
    output=dict(status='ACTUAL_SONMI_SACCT_SNAPSHOT',host=socket.gethostname(),uid=os.getuid(),
        timestamp_unix=time.time(),columns=['State','ExitCode','ElapsedRaw','AllocCPUS'],rows=rows,
        raw_stdout=result.stdout,attempts=attempts,inputs=inputs,source_sha256=sha(__file__),
        scope='Immutable point-in-time actual parents, no inferred steps or multiplied accounting')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(output,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=output['status'],parents=len(rows),path=str(args.output),sha256=sha(args.output))))


if __name__=='__main__':main()
