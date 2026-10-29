"""Root metadata plans: bind actual20k closure, never read SDK/journal bodies."""
from __future__ import annotations
import argparse
from panel_common import *
from prepare_sync import capture_C0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('audit','sync'))
    parser.add_argument('--pins-sha256',required=True)
    parser.add_argument('--plan-output',type=Path,required=True);parser.add_argument('--job-output',type=Path,required=True)
    parser.add_argument('--GPU-closure',type=Path);parser.add_argument('--GPU-closure-sha256')
    parser.add_argument('--verification',type=Path);parser.add_argument('--audit-result',type=Path);parser.add_argument('--audit-supervisor',type=Path)
    args=parser.parse_args();root_only();pin=verify(args.pins_sha256)
    require(args.plan_output.absolute().parent==HERE.parent and args.job_output.absolute().parent==HERE.parent
        and not args.plan_output.exists() and not args.job_output.exists(),'Explicit fresh direct model-owned plan/output required')
    if args.mode=='audit':
        require(args.GPU_closure is not None and args.GPU_closure_sha256
            and args.verification is args.audit_result is args.audit_supervisor is None,
            'Actual Root5060 closure only; no future SDK proof')
        actual=ref(args.GPU_closure);require(actual['sha256']==args.GPU_closure_sha256,'Actual Root GPU closure SHA differs')
        inputs=read(ref(HERE/'inputs.template.json'));require(inputs['refs']['closure'] is None,'Frozen template must not contain a future proof')
        inputs={**inputs,'Root_Closure_NOT_YET_PRODUCED':False,'refs':{**inputs['refs'],'closure':actual}}
        metadata={name:read(item) for name,item in inputs['refs'].items()}
        metadata_gate(inputs,metadata['closure'],metadata['result'],metadata['guard'],metadata['request'],metadata['spec'])
        args.plan_output.mkdir(mode=0o700);input_ref=write(args.plan_output/'inputs.json',inputs);bound_inputs(input_ref)
    else:
        require(args.GPU_closure is args.GPU_closure_sha256 is None and all(x is not None for x in
            (args.verification,args.audit_result,args.audit_supervisor)),'Actual audit certificate/result/supervisor required')
        certificate=read(ref(args.verification));input_ref=certificate['inputs'];bound_inputs(input_ref)
        args.plan_output.mkdir(mode=0o700)
    bindings=dict(MODEL_V3_PANEL_SOURCE_SHA=pin['sha256'],MODEL_V3_PANEL_OUTPUT=str(args.job_output.absolute()))
    if args.mode=='audit':
        bindings.update(MODEL_V3_PANEL_INPUTS=input_ref['path'],MODEL_V3_PANEL_INPUTS_SHA=input_ref['sha256'])
    else:
        result_ref=ref(args.audit_result);result=read(result_ref);job=result['actual_job_id']
        require(type(job) is str and job.isdigit(),'Actual audit jobID required')
        terminal=capture_C0(job,args.plan_output/'audit_actual_C0')
        manifest=dict(schema='native_S20000_panel_sync_manifest_v1',run_ids=[RUN],verification=ref(args.verification),
            audit_result=result_ref,audit_supervisor=ref(args.audit_supervisor),actual_audit_C0=terminal,
            original_SDK_and_journal_bodies_opened_by_prepare=False,scientific_acceptance=False)
        manifest['runs']=[row_from_proof(manifest)];raw=write(args.plan_output/'explicit_manifest.json',manifest)
        os.environ['MODEL_V3_PANEL_MANIFEST']=raw['path'];os.environ['MODEL_V3_PANEL_MANIFEST_SHA']=raw['sha256']
        request=dict(schema='native_S20000_panel_selective_sync_request_v1',mode='pilot',selected_run_ids=[RUN],eligible_manifest=raw,
            source_manifest=pin,job_output=str(args.job_output.absolute()),child_seconds=3000,CLI_timeout_seconds=600,
            API_verification_seconds=180,maximum_batch_runs=1,scientific_acceptance=False,original_model_status_unchanged=True)
        request_gate(request);request_ref=write(args.plan_output/'request.json',request)
        bindings.update(MODEL_V3_PANEL_MANIFEST=raw['path'],MODEL_V3_PANEL_MANIFEST_SHA=raw['sha256'],
            MODEL_V3_PANEL_REQUEST=request_ref['path'],MODEL_V3_PANEL_REQUEST_SHA=request_ref['sha256'])
    output=write(args.plan_output/'bindings.json',bindings)
    print(json.dumps(dict(bindings=output,source_pins=pin,mode=args.mode,run_ids=[RUN],SDK_opened=False,online_sync=False)))
    return 0
if __name__=='__main__':raise SystemExit(main())