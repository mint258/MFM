"""Root metadata preparation only; sync occurs only in the explicit CPU job."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import time
from sync_common import *


def capture_C0(job,output):
    argv=['sacct','-X','-n','-P','-j',str(job),'--format=JobIDRaw,State,ExitCode']
    started=time.time();result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
    require(result.returncode==0 and result.stdout.strip()==str(job)+'|COMPLETED|0:0',
        'Root actual parent is not exact C0')
    raw=write(output/'raw_sacct.json',dict(argv=argv,returncode=result.returncode,stdout=result.stdout,
        stderr=result.stderr,started_unix=started,completed_unix=time.time()))
    return write(output/'actual_terminal.json',dict(schema='model_v3_sync_Root_terminal_v1',
        job_id=str(job),status='COMPLETED',exit_code='0:0',raw_sacct=raw))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('pilot','batch'),required=True)
    p.add_argument('--runs',nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--job-output',type=Path,required=True);p.add_argument('--pins-sha256',required=True)
    p.add_argument('--pilot-result',type=Path);p.add_argument('--pilot-supervisor',type=Path);p.add_argument('--pilot-job')
    a=p.parse_args();root_only();manifest=verify(a.pins_sha256);_,rows=eligible_rows()
    require(len(a.runs)==len(set(a.runs)) and all(value in rows for value in a.runs),'Only explicit unique eligible IDs allowed')
    require((a.mode=='pilot' and len(a.runs)==1) or (a.mode=='batch' and 1<=len(a.runs)<=3),
        'One real pilot or at most three sequential runs per bounded CPU job')
    require(not a.output.exists() and not a.job_output.exists(),'Fresh plan and job-output roots required')
    a.output.mkdir(mode=0o700,parents=True)
    integrity_terminal=capture_C0('4521403',a.output/'integrity_C0')
    supervisor=ref(HERE.parent/'native_sdk_integrity57_supervisor_4521403.json');sup=read(supervisor)
    require(str(sup['job_id'])=='4521403' and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining']==[],'Original integrity supervisor/process closure required')
    gate=None
    if a.mode=='batch':
        require(a.pilot_result and a.pilot_supervisor and a.pilot_job,'Actual reviewed single-run parent proof required')
        pilot_ref=ref(a.pilot_result);pilot=read(pilot_ref);pilot_sup=ref(a.pilot_supervisor);s=read(pilot_sup)
        require(pilot['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' and len(pilot['records'])==1
            and pilot['mode']=='pilot' and pilot['source_manifest']==manifest
            and str(pilot['job_id'])==str(a.pilot_job)
            and str(s['job_id'])==str(a.pilot_job)
            and s['status']=='COMPLETED' and s['exit_code']==0 and s['first_failure'] is None and s['remaining']==[],
            'Pilot source/job/readback and actual closed supervisor must match')
        terminal=capture_C0(a.pilot_job,a.output/'pilot_C0')
        gate=dict(result=pilot_ref,supervisor=pilot_sup,actual_terminal=terminal,
            native_exit_code=pilot['records'][0]['native_exit_code'],
            actual_replay_verified=pilot['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED')
    request=write(a.output/'request.json',dict(schema='model_v3_selective_WandB_sync_request_v1',
        status='ROOT_PREPARED_EXPLICIT_SYNC',mode=a.mode,selected_run_ids=a.runs,source_manifest=manifest,
        eligible_manifest=ref(HERE/'explicit50.json'),integrity_terminal=integrity_terminal,
        integrity_supervisor=supervisor,pilot_gate=gate,job_output=str(a.job_output.absolute()),
        child_seconds=3000,CLI_timeout_seconds=600,API_verification_seconds=180,
        maximum_batch_runs=3,online_mutation_scope='exact_selected_original_runIDs_only; no_finish_or_summary_API',
        expected_method='installed0.28.1 official core replay via plain sync beta reroute',
        original_SDKs_are_read_only=True,scientific_acceptance=False))
    bindings={key:str(value) for key,value in dict(MODEL_V3_SYNC_SOURCE_PINS=HERE/'source_pins.json',
        MODEL_V3_SYNC_SOURCE_PINS_SHA=manifest['sha256'],MODEL_V3_SYNC_REQUEST=request['path'],
        MODEL_V3_SYNC_REQUEST_SHA=request['sha256'],MODEL_V3_SYNC_OUTPUT=a.job_output.absolute()).items()}
    write(a.output/'bindings.json',bindings)
    print(json.dumps(dict(request=request,bindings=ref(a.output/'bindings.json'),online_sync_executed=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
