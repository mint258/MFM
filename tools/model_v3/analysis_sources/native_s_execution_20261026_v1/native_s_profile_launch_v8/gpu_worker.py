"""Allocated GPU worker. No SSH, sbatch, quota producer or accounting DB call."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from common import *
sys.dont_write_bytecode=True

def supervisor_command(phase,precision,submission,contract,job):
    management=Path(phase)/f'job_{job}'/'management';child=Path(phase)/f'job_{job}'/'child'
    record=management/'supervisor.json'
    return [str(PYTHON),'-u','-B',str(RUNTIME/'tools/model_v3/run_supervised.py'),
        '--output-root',str(child),'--record',str(record),'--gpu-uuid',GPU,'--wall-seconds',str(WALL),
        '--rss-limit-bytes',str(RSS),'--output-budget-bytes',str(OUTER),
        '--private-scratch-root','/tmp/mv3n_'+str(job),'--private-storage-budget-bytes',str(PRIVATE),'--',
        str(PYTHON),'-u','-B',str(HERE/'short_profile.py'),'--runtime-contract',str(contract),
        '--output',str(child),'--precision',precision,'--updates','20','--expected-gpu','5090',
        '--code-sha',CODE,'--prereg-sha',PUBLIC,'--wall-seconds',str(CHILD_WALL),'--phase',str(phase),
        '--submission',submission['path'],'--submission-sha256',submission['sha256'],
        '--observations',str(record)+'.jsonl']

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',type=Path,required=True)
    p.add_argument('--precision',choices=('fp32','bf16'),required=True);p.add_argument('--pins-sha256',required=True)
    a=p.parse_args();verify_package(expected=a.pins_sha256);verify_package(V2,V2_PIN)
    import resources
    job=os.environ['SLURM_JOB_ID'];process=resources.process_allocation(job)
    phase=a.phase.absolute();require(phase.parent==N,'Only an immediate Root-created phase admitted')
    deadline=time.monotonic()+15;path=phase/'control/submission.json'
    while not path.exists() and time.monotonic()<deadline:time.sleep(.2)
    ref=binding(path);frame=read_ref(ref)
    require(frame['status']=='SUBMITTED' and frame['actual_sbatch_job_id']==job and frame['phase']==str(phase)
        and frame['precision']==a.precision and frame['package_manifest']['sha256']==a.pins_sha256,
        'Actual Root submission/job/package mismatch')
    read_ref(frame['package_manifest']);read_ref(frame['candidate_ready'])
    if frame['operational_source_status']=='UNPUBLISHED_CANDIDATE':
        require(frame['launch_validation_mode']=='PROFILE_LAUNCH_VALIDATION' and frame['protocol_publication'] is None
            and frame['usable_scientific_result'] is False,'Unpublished operations scope differs')
        from operations import verify_source_snapshot
        verify_source_snapshot(frame['operational_source_snapshot'],frame['package_manifest'])
    else:
        require(frame['operational_source_status']=='PUBLISHED_VERIFIED','Unknown operational source state')
        read_ref(frame['protocol_publication'])
    script=binding(frame['copied_script']['path']);require(script==frame['copied_script'] and
        script['sha256']==binding(HERE/'native_s_profile_gpu.sbatch')['sha256'],'Copied script changed')
    require(frame['actual_sbatch']['returncode']==0 and frame['actual_sbatch']['argv']==frame['actual_sbatch_argv']
        and frame['actual_sbatch']['stdout'].split(';',1)[0].strip()==job,'Root actual sbatch raw binding differs')
    argv=frame['actual_sbatch_argv']
    for option in ('--nodelist='+NODE,'--cpus-per-task=16','--mem=32G','--time=00:20:00'):
        require(argv.count(option)==1,'Root resource argv differs')
    # Scheduler fallback uses sealed Root observations only after an actual
    # known-unavailable worker call; kernel/NVML observations remain live.
    observations=resources.observe(worker=True,root_frame=frame)
    own=actual(['scontrol','show','job',job],check=False)
    if own['returncode']==0:
        require(('JobId='+job) in own['stdout'] and re.search(r'NumCPUs=16(?:\s|$)',own['stdout'])
            and NODE in own['stdout'],'Own live controller allocation differs')
        process['own_controller_scope']='actual_live_scontrol'
    else:
        require(resources.unavailable(own),'Unexpected own-job scheduler error')
        process['own_controller_scope']='backend_unavailable; Root_actual_request_plus_current_proc_env_not_controller_readback'
    management=phase/f'job_{job}'/'management'
    management.mkdir(mode=0o700,parents=True,exist_ok=False)
    contract=frame['candidate_contract'];read_ref(contract)
    check=actual([PYTHON,'-B',HERE/'candidate_probe.py','--contract',contract['path']],
        env=runtime_environment(cpu=True),timeout=120)
    command=supervisor_command(phase,a.precision,ref,contract['path'],job)
    prelaunch=write(management/'prelaunch.json',dict(schema='native_S_profile_worker_prelaunch_v1',
        status='PRELAUNCH_ADMITTED',submission=ref,process=process,resource_observations=observations,
        own_job_controller_observation=own,candidate_probe=check,actual_planned_supervisor_argv=command,
        worker_source=binding(__file__),accounting_scope='sealed_source_bound_Root_QA_raw_C0_not_compute_sacct',
        whole_job_budget_bytes=OUTER,private_budget_bytes=PRIVATE,production_20k_allowed=False))
    env=runtime_environment(contract=contract['path'])
    env['MODEL_V3_PROFILE_PRELAUNCH_REF']=json.dumps(prelaunch,sort_keys=True)
    # stdout/stderr are inherited regular Slurm files; child captures the real
    # supervisor parent argv/fds. No invented execution receipt is written.
    completed=subprocess.run(command,stdin=subprocess.DEVNULL,env=env)
    return completed.returncode

if __name__=='__main__':raise SystemExit(main())
