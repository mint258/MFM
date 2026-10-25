"""Read-only admission, then one explicit Root CPU-task submission."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

RUNS = Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--node',choices=['compute-0-'+str(i) for i in (2,*range(8,20))],required=True)
    parser.add_argument('--memory-MiB',type=int,choices=(16384,32768,65536),required=True)
    parser.add_argument('--script',type=Path,required=True)
    parser.add_argument('--bindings',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or not args.output.absolute().is_relative_to(RUNS):
        raise ValueError('Fresh owned submission receipt required')
    if not args.script.absolute().is_relative_to(RUNS) or not args.script.is_file():
        raise ValueError('An explicitly prepared owned script required')
    extra=json.loads(args.bindings.read_text())
    if not isinstance(extra,dict) or any(not key.startswith('MODEL_V3_') or not isinstance(value,str) for key,value in extra.items()):
        raise ValueError('Only explicit non-secret model-v3 bindings are accepted')
    observations=[]
    def capture(argv):
        result=subprocess.run(argv,capture_output=True,text=True,timeout=45,check=True)
        observations.append(dict(argv=argv,stdout=result.stdout,stderr=result.stderr,returncode=result.returncode))
        return result.stdout
    raw=capture(['scontrol','show','node',args.node])
    values=dict(re.findall(r'(CPUAlloc|CPUTot|RealMemory|AllocMem)=(\d+)',raw))
    if int(values['CPUTot'])-int(values['CPUAlloc'])<16:
        raise ValueError('No actual16CPU headroom')
    requested=0.
    for line in capture(['squeue','-h','-w',args.node,'-o','%i|%u|%t|%m|%C']).splitlines():
        fields=line.split('|')
        if fields[2] not in ('R','CG'):continue
        match=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)([cn]?)',fields[3])
        if not match:raise ValueError('Unrecognized memory request')
        value=float(match[1])*{'':1,'K':1/1024,'M':1,'G':1024,'T':1024**2}[match[2]]
        requested+=value*(int(fields[4]) if match[3]=='c' else 1)
    prior_commitment=max(requested,float(values['AllocMem']))
    if prior_commitment+args.memory_MiB>=.85*int(values['RealMemory']):
        raise ValueError('All-user declared requests exceed85%')
    raw=capture(['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',args.node,'head -n 5 /proc/meminfo'])
    available=int(re.search(r'MemAvailable:\s+(\d+) kB',raw)[1])/1024
    if available-args.memory_MiB<.15*int(values['RealMemory']):
        raise ValueError('Available-memory headroom insufficient')
    quota=capture(['quota','-v','-u','zixiao'])
    row,=[line.split() for line in quota.splitlines() if line.split() and line.split()[0]=='/dev/sda1']
    used,soft,hard=[int(row[index].rstrip('*')) for index in (1,2,3)]
    limits=[value for value in (soft,hard) if value>0]
    if not limits or (min(limits)-used)*1024<64*1024**3:
        raise ValueError('User quota headroom insufficient')
    argv=['sbatch','--parsable','--partition=cpu','--nodelist='+args.node,'--cpus-per-task=16',
          '--mem='+str(args.memory_MiB)+'M',str(args.script.absolute())]
    result=subprocess.run(argv,cwd=RUNS.parents[1],env={**os.environ,**extra,'MODEL_V3_EXPECTED_NODE':args.node},
        capture_output=True,text=True,timeout=45,check=False)
    job_id=result.stdout.strip().split(';')[0]
    receipt=dict(schema='model_v3_single_CPU_submission_v1',captured_utc=datetime.now(timezone.utc).isoformat(),
        job_id=job_id if job_id.isdigit() else None,node=args.node,cpus=16,requested_memory_MiB=args.memory_MiB,
        prior_all_user_requested_memory_MiB=requested,prior_AllocMem_MiB=int(values['AllocMem']),
        prior_memory_commitment_check_MiB=prior_commitment,available_memory_MiB=available,argv=argv,
        script_sha256=hashlib.sha256(args.script.read_bytes()).hexdigest(),bindings=extra,
        observations=observations,sbatch_returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    with args.output.open('x') as stream:
        json.dump(receipt,stream,indent=2);stream.write('\n')
    if result.returncode or not job_id.isdigit():
        raise RuntimeError('Submission not confirmed; inspect preserved raw receipt before retrying')
    print(json.dumps(dict(job_id=job_id,node=args.node,receipt=str(args.output))))


if __name__=='__main__':main()
