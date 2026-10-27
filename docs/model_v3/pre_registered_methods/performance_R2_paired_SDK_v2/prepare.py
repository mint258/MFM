"""Root exact paired metadata preparation; no SDK/journal/API bodies opened."""
from __future__ import annotations
import argparse
from paired_common import *
from prepare_sync import capture_C0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('audit','sync'));p.add_argument('--pins-sha256',required=True)
    p.add_argument('--plan-output',type=Path,required=True);p.add_argument('--job-output',type=Path,required=True)
    p.add_argument('--audit-result',type=Path);p.add_argument('--audit-supervisor',type=Path)
    p.add_argument('--runs',nargs='+')
    a=p.parse_args();root_only();pin=verify(a.pins_sha256);input_ref=ref(HERE/'inputs.json');bound_inputs(input_ref)
    require(a.plan_output.absolute().parent==HERE.parent and a.job_output.absolute().parent==HERE.parent
        and not a.plan_output.exists() and not a.job_output.exists(),'Explicit fresh owned plan/output required')
    a.plan_output.mkdir(mode=0o700)
    bindings=dict(MODEL_V3_PAIRED_SOURCE_SHA=pin['sha256'],MODEL_V3_PAIRED_OUTPUT=str(a.job_output.absolute()))
    if a.mode=='audit':
        require(a.audit_result is a.audit_supervisor is a.runs is None,'Do not prefill future audit proof')
        bindings.update(MODEL_V3_PAIRED_INPUTS=input_ref['path'],MODEL_V3_PAIRED_INPUTS_SHA=input_ref['sha256'])
    else:
        require(a.audit_result is not None and a.audit_supervisor is not None and a.runs is not None
            and 1<=len(a.runs)<=3 and len(set(a.runs))==len(a.runs) and set(a.runs)<=IDS,'One to three explicit fixed IDs required')
        batch_ref=ref(a.audit_result);batch=read(batch_ref);job=batch['actual_job_id']
        require(type(job) is str and job.isdigit(),'Actual completed audit job required')
        manifest=dict(schema='performance_R2_paired_sync_manifest_v1',verifications=batch['verifications'],audit_result=batch_ref,
            audit_supervisor=ref(a.audit_supervisor),actual_audit_C0=capture_C0(job,a.plan_output/'audit_actual_C0'))
        manifest['runs']=proof_rows(manifest)
        raw=write(a.plan_output/'explicit_manifest.json',manifest)
        os.environ['MODEL_V3_PAIRED_MANIFEST']=raw['path'];os.environ['MODEL_V3_PAIRED_MANIFEST_SHA']=raw['sha256']
        gate=dict(result=ref(HERE.parent/'WandB_sync50_pilot_actual_v3/RESULT.json'),
            supervisor=ref(HERE.parent/'WandB_sync50_pilot_actual_v3.supervisor.json'),
            actual_terminal=capture_C0('4521412',a.plan_output/'method_actual_C0'),native_exit_code=1,actual_replay_verified=True)
        request=dict(schema='performance_R2_paired_selective_sync_request_v1',mode='batch',selected_run_ids=a.runs,
            eligible_manifest=raw,source_manifest=pin,pilot_gate=gate,job_output=str(a.job_output.absolute()),
            child_seconds=3000,CLI_timeout_seconds=600,API_verification_seconds=180,maximum_batch_runs=3,scientific_acceptance=False)
        request_gate(request);request_ref=write(a.plan_output/'request.json',request)
        bindings.update(MODEL_V3_PAIRED_MANIFEST=raw['path'],MODEL_V3_PAIRED_MANIFEST_SHA=raw['sha256'],
            MODEL_V3_PAIRED_REQUEST=request_ref['path'],MODEL_V3_PAIRED_REQUEST_SHA=request_ref['sha256'])
    result=write(a.plan_output/'bindings.json',bindings)
    print(json.dumps(dict(bindings=result,source_pins=pin,mode=a.mode,SDK_opened=False,online_action=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
