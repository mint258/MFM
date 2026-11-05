"""Root metadata-only preparation; never opens SDK/steps or calls W&B API."""
from __future__ import annotations
import argparse
from max_common import *
from prepare_sync import capture_C0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('audit','sync'),required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--plan-output',type=Path,required=True)
    parser.add_argument('--job-output',type=Path,required=True)
    parser.add_argument('--audit-result',type=Path);parser.add_argument('--audit-supervisor',type=Path)
    args=parser.parse_args();root_only();pin=verify(args.pins_sha256)
    require(not os.environ.get('SLURM_JOB_ID') and args.plan_output.absolute().parent==HERE.parent
        and args.job_output.absolute().parent==HERE.parent and not args.plan_output.exists()
        and not args.job_output.exists(),'Root metadata-only fresh external plan/output required')
    scope=read(HERE/'scope.json')
    if args.mode=='audit':
        require(args.audit_result is args.audit_supervisor is None,'No future audit result can qualify audit preparation')
        root=read(scope['root_closure']);model_C0(root['actual_sacct'])
        names=('configuration','summary','run_status','supervisor','submission','selection','source_package','method_publication')
        inputs=dict(schema='native_max_R1_log_inputs_v1',scope=SCOPE,run_id=RUN,model_job_id=JOB,
            root_closure=scope['root_closure'],refs={k:root[k] for k in names},
            expected_summary=root['SDK_expected_summary'],SDK={k:root['SDK'][k] for k in ('path','bytes')},
            step_journal=descriptor(CHILD/'steps.jsonl',16<<20),SDK_or_steps_body_opened=False)
        metadata_inputs(inputs)
    else:
        require(args.audit_result is not None and args.audit_supervisor is not None,'Actual audit result/supervisor required')
        batch_ref=ref(args.audit_result);batch=read(batch_ref);bound_inputs(batch['inputs'])
    args.plan_output.mkdir(mode=0o700)
    bindings=dict(MODEL_V3_MAX_SOURCE_SHA=pin['sha256'],MODEL_V3_MAX_OUTPUT=str(args.job_output.absolute()))
    if args.mode=='audit':
        raw=write(args.plan_output/'inputs.json',inputs);bound_inputs(raw)
        bindings.update(MODEL_V3_MAX_INPUTS=raw['path'],MODEL_V3_MAX_INPUTS_SHA=raw['sha256'])
    else:
        job=batch['actual_job_id'];require(type(job) is str and job.isdigit(),'Actual CPU audit job required')
        manifest=dict(schema='native_max_R1_sync_manifest_v1',verifications=batch['verifications'],
            audit_result=batch_ref,audit_supervisor=ref(args.audit_supervisor),
            actual_audit_C0=capture_C0(job,args.plan_output/'audit_actual_C0'))
        manifest['runs']=proof_rows(manifest);raw=write(args.plan_output/'explicit_manifest.json',manifest)
        os.environ['MODEL_V3_MAX_MANIFEST']=raw['path'];os.environ['MODEL_V3_MAX_MANIFEST_SHA']=raw['sha256']
        gate=dict(result=ref(HERE.parent/'WandB_sync50_pilot_actual_v3/RESULT.json'),
            supervisor=ref(HERE.parent/'WandB_sync50_pilot_actual_v3.supervisor.json'),
            actual_terminal=capture_C0('4521412',args.plan_output/'method_actual_C0'),native_exit_code=1,actual_replay_verified=True)
        request=dict(schema='native_max_R1_selective_sync_request_v1',mode='batch',selected_run_ids=[RUN],
            eligible_manifest=raw,source_manifest=pin,pilot_gate=gate,job_output=str(args.job_output.absolute()),
            child_seconds=3000,CLI_timeout_seconds=600,API_verification_seconds=180,maximum_batch_runs=3,
            scientific_acceptance=False)
        request_gate(request);rr=write(args.plan_output/'request.json',request)
        bindings.update(MODEL_V3_MAX_MANIFEST=raw['path'],MODEL_V3_MAX_MANIFEST_SHA=raw['sha256'],
            MODEL_V3_MAX_REQUEST=rr['path'],MODEL_V3_MAX_REQUEST_SHA=rr['sha256'])
    result=write(args.plan_output/'bindings.json',bindings)
    print(json.dumps(dict(bindings=result,source_pins=pin,mode=args.mode,SDK_opened=False,steps_opened=False,online_action=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
