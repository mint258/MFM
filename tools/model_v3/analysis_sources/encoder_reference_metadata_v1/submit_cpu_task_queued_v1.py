"""Explicit queued CPU submission: hardware capacity, original memory/quota gates, no idle claim."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import socket

RUNS = Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--node',choices=['compute-0-'+str(i) for i in (2,*range(8,20))],required=True)
    parser.add_argument('--memory-MiB',type=int,choices=(16384,),required=True)
    parser.add_argument('--script',type=Path,required=True)
    parser.add_argument('--bindings',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('Root login metadata submitter required')
    # JSON content with a nonreceipt suffix: cost discovery must never mistake
    # a presubmission intent for an actual submission receipt.
    intent_path=Path(str(args.output)+'.QUEUE_INTENT')
    stdout_path=Path(str(args.output)+'.sbatch.stdout');stderr_path=Path(str(args.output)+'.sbatch.stderr')
    if any(path.exists() for path in (args.output,intent_path,stdout_path,stderr_path)) or not args.output.absolute().is_relative_to(RUNS):
        raise ValueError('Fresh owned submission receipt required')
    if not args.script.absolute().is_relative_to(RUNS) or not args.script.is_file():
        raise ValueError('An explicitly prepared owned script required')
    extra=json.loads(args.bindings.read_text())
    if not isinstance(extra,dict) or any(not key.startswith('MODEL_V3_') or not isinstance(value,str) for key,value in extra.items()):
        raise ValueError('Only explicit non-secret model-v3 bindings are accepted')
    if any(key in extra for key in ('MODEL_V3_ARCHIVE7_ROOT_RECEIPT','MODEL_V3_ARCHIVE7_ROOT_RECEIPT_SHA')):
        raise ValueError('A prequeue120s archive quota must not be submitted; use the separately prepared allocation-time JIT wrapper')
    observations=[]
    def capture(argv):
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=True)
        observations.append(dict(argv=argv,stdout=result.stdout,stderr=result.stderr,returncode=result.returncode))
        return result.stdout
    raw=capture(['scontrol','show','node',args.node])
    values=dict(re.findall(r'(CPUAlloc|CPUTot|RealMemory|AllocMem)=(\d+)',raw))
    free_cpus_observed=int(values['CPUTot'])-int(values['CPUAlloc'])
    if int(values['CPUTot'])<16:
        raise ValueError('Node hardware capacity below16CPU')
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
    policy=dict(admission_policy='CAPACITY_AT_LEAST16_WITH_ORIGINAL_MEMORY_AND_QUOTA_CHECKS',
        mode='QUEUED_ONLY',hardware_capacity_cpus=int(values['CPUTot']),free_cpus_observed=free_cpus_observed,
        idle16_admission_performed=False,queue_expected_from_snapshot=free_cpus_observed<16,
        Slurm_still_requests16CPU=True,oversubscribe_requested=False,submission_is_not_allocation_or_task_success=True)
    script_ref=dict(path=str(args.script.absolute()),bytes=args.script.stat().st_size,
        sha256=hashlib.sha256(args.script.read_bytes()).hexdigest())
    base=RUNS/'submit_cpu_task_v2.py';base_ref=dict(path=str(base),bytes=base.stat().st_size,
        sha256=hashlib.sha256(base.read_bytes()).hexdigest())
    if args.validate_only:
        print(json.dumps(dict(status='QUEUED_ADMISSION_METADATA_VALID_NO_SBATCH',**policy,
            node=args.node,actual_planned_sbatch_argv=argv,script=script_ref,observations=observations,
            prior_memory_commitment_MiB=prior_commitment,available_memory_MiB=available)));return
    with intent_path.open('x') as stream:
        json.dump(dict(schema='model_v3_queued_CPU_submission_intent_v1',**policy,argv=argv,
            output=str(args.output),script=script_ref,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            captured_utc=datetime.now(timezone.utc).isoformat()),stream,indent=2);stream.write('\n')
    began=time.time();error=None
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,cwd=RUNS.parents[1],
            env={**os.environ,**extra,'MODEL_V3_EXPECTED_NODE':args.node},capture_output=True,timeout=45,check=False)
        code=result.returncode;out_raw=result.stdout;err_raw=result.stderr
    except (subprocess.TimeoutExpired,OSError) as exc:
        code=None;out_raw=getattr(exc,'stdout',None) or b'';err_raw=getattr(exc,'stderr',None) or b''
        error=dict(type=type(exc).__name__,message=str(exc),sbatch_submission_ambiguous=True)
    for path,raw in ((stdout_path,out_raw),(stderr_path,err_raw)):
        with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    def raw_ref(path):
        return dict(path=str(path.absolute()),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    stdout=out_raw.decode('utf-8',errors='strict');stderr=err_raw.decode('utf-8',errors='strict')
    job_id=stdout.strip().split(';')[0]
    receipt=dict(schema='model_v3_queued_CPU_submission_v1',captured_utc=datetime.now(timezone.utc).isoformat(),
        **policy,job_id=job_id if job_id.isdigit() else None,node=args.node,cpus_requested=16,requested_memory_MiB=args.memory_MiB,
        prior_all_user_requested_memory_MiB=requested,prior_AllocMem_MiB=int(values['AllocMem']),
        prior_memory_commitment_check_MiB=prior_commitment,available_memory_MiB=available,actual_sbatch_argv=argv,
        actual_sbatch_script=script_ref,bindings=extra,observations=observations,actual_sbatch_returncode=code,
        raw_submission=dict(stdout=raw_ref(stdout_path),stderr=raw_ref(stderr_path)),stdout=stdout,stderr=stderr,
        exception=error,submission_started_unix=began,submission_finished_unix=time.time(),
        base_helper=base_ref,helper_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        no_automatic_retry_cancel_or_source_rewrite=True)
    with args.output.open('x') as stream:
        json.dump(receipt,stream,indent=2);stream.write('\n')
    if code!=0 or not job_id.isdigit():
        raise RuntimeError('Submission not confirmed; inspect preserved raw receipt before retrying')
    print(json.dumps(dict(job_id=job_id,node=args.node,receipt=str(args.output))))


if __name__=='__main__':main()
