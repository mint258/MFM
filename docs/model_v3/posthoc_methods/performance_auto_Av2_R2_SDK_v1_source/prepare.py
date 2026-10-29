"""Root one-pair preparation; all future closed refs supplied explicitly, SDK stat only."""
from __future__ import annotations
import argparse
from paired_common import *
from prepare_sync import capture_C0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('audit','sync'));p.add_argument('--pins-sha256',required=True)
    p.add_argument('--plan-output',type=Path,required=True);p.add_argument('--job-output',type=Path,required=True)
    p.add_argument('--r2-closure',type=Path);p.add_argument('--r2-closure-sha256')
    p.add_argument('--saved-sdk-refs',type=Path);p.add_argument('--saved-sdk-refs-sha256')
    p.add_argument('--audit-result',type=Path);p.add_argument('--audit-supervisor',type=Path)
    p.add_argument('--runs',nargs='+')
    a=p.parse_args();root_only();pin=verify(a.pins_sha256)
    require(a.plan_output.absolute().parent==HERE.parent and a.job_output.absolute().parent==HERE.parent
        and not a.plan_output.exists() and not a.job_output.exists(),'Explicit fresh owned plan/output required')
    if a.mode=='audit':
        require(a.r2_closure is not None and a.saved_sdk_refs is not None
            and a.r2_closure_sha256 is not None and a.saved_sdk_refs_sha256 is not None
            and a.audit_result is a.audit_supervisor is a.runs is None,'Actual closed model and saved descriptors required')
        root_ref=ref(a.r2_closure);saved_ref=ref(a.saved_sdk_refs)
        require(root_ref['sha256']==a.r2_closure_sha256 and saved_ref['sha256']==a.saved_sdk_refs_sha256,
            'Explicit current Root closure/saved-descriptor rawSHA differs')
        root=read(root_ref);saved=read(saved_ref)
        require(root['job_id']=='4524745' and root['actual_code_sha']==CODE
            and saved['schema']=='performance_auto_Av2_R2_saved_sdk_descriptors_v1'
            and saved['job_id']==root['job_id'] and saved['Root_closure']==root_ref and len(saved['sdks'])==2,
            'One actual auto-profile job/two original saved SDK descriptors required')
        deps=read(HERE/'dependencies.json')
        closed={Path(raw['path']).name:raw for raw in root['closed_metadata']}
        refs={key:closed[name] for key,name in
            (('configuration','configuration.json'),('summary','summary.json'),('status','run_status.json'))}
        refs.update(root=root_ref,supervisor=closed['supervisor.json'],saved_sdk_descriptors=saved_ref,
            selection_profile=deps['sources']['selection_profile'],profile_donor_Root=deps['sources']['profile_donor_Root'],
            profile_consumer_result=deps['sources']['profile_consumer_result'],profile_consumer_supervisor=deps['sources']['profile_consumer_supervisor'],
            auto_execution_request=deps['sources']['auto_execution_request'],auto_candidate_options=deps['sources']['auto_candidate_options'],
            submission=deps['sources']['model_submission'],model_source_package=deps['sources']['model_source_package'],
            operations_publication=deps['sources']['operations_publication'],rule_publication=deps['sources']['A_rule_publication'])
        child=HERE.parent/'performance_auto_R2_Av2_v1/child'
        require(all(Path(refs[key]['path'])==child/name for key,name in
            (('configuration','configuration.json'),('summary','summary.json'),('status','run_status.json'))),
            'Producer metadata must belong to the exact current auto-profile family')
        require(set(saved['journals'])=={'reference','candidate'}
            and all(Path(saved['journals'][role]['path'])==child/(role+'_history.jsonl')
                    for role in ('reference','candidate')),'Exact actual saved role-journal locations required')
        case=dict(job_id=root['job_id'],refs=refs,journals=saved['journals'],sdks=saved['sdks'])
        metadata_case(case)
        a.plan_output.mkdir(mode=0o700)
        actual=capture_C0(root['job_id'],a.plan_output/'model_actual_C0')
        require(terminal_C0(actual)['job_id']==root['job_id'],'Fresh actual model C0 differs')
        case['actual_model_C0']=actual
        inputs=dict(schema='performance_auto_Av2_R2_paired_log_inputs_v1',scope=SCOPE,cases=[case],
            source_pins=pin,scientific_acceptance=False,original_descriptors_only=True)
        input_ref=write(a.plan_output/'inputs.json',inputs);bound_inputs(input_ref)
        bindings=dict(MODEL_V3_PAIRED_SOURCE_SHA=pin['sha256'],MODEL_V3_PAIRED_OUTPUT=str(a.job_output.absolute()),
            MODEL_V3_PAIRED_INPUTS=input_ref['path'],MODEL_V3_PAIRED_INPUTS_SHA=input_ref['sha256'])
    else:
        require(a.r2_closure is a.r2_closure_sha256 is a.saved_sdk_refs is a.saved_sdk_refs_sha256 is None
            and a.audit_result is not None and a.audit_supervisor is not None and a.runs is not None,
            'Actual audit refs and explicit two IDs required; no replacement producer inputs')
        batch_ref=ref(a.audit_result);batch=read(batch_ref);bound_inputs(batch['inputs'])
        require(len(a.runs)==len(set(a.runs))==2 and set(a.runs)==IDS,'This once-only batch selects exactly both audited SDKs')
        job=batch['actual_job_id'];require(type(job) is str and job.isdigit(),'Actual audit job required')
        a.plan_output.mkdir(mode=0o700)
        manifest=dict(schema='performance_auto_Av2_R2_paired_sync_manifest_v1',verifications=batch['verifications'],
            audit_result=batch_ref,audit_supervisor=ref(a.audit_supervisor),
            actual_audit_C0=capture_C0(job,a.plan_output/'audit_actual_C0'))
        manifest['runs']=proof_rows(manifest);raw=write(a.plan_output/'explicit_manifest.json',manifest)
        os.environ['MODEL_V3_PAIRED_MANIFEST']=raw['path'];os.environ['MODEL_V3_PAIRED_MANIFEST_SHA']=raw['sha256']
        gate=dict(result=ref(HERE.parent/'WandB_sync50_pilot_actual_v3/RESULT.json'),
            supervisor=ref(HERE.parent/'WandB_sync50_pilot_actual_v3.supervisor.json'),
            actual_terminal=capture_C0('4521412',a.plan_output/'method_actual_C0'),
            native_exit_code=1,actual_replay_verified=True)
        request=dict(schema='performance_auto_Av2_R2_paired_selective_sync_request_v1',mode='batch',
            selected_run_ids=a.runs,eligible_manifest=raw,source_manifest=pin,pilot_gate=gate,
            job_output=str(a.job_output.absolute()),child_seconds=3000,CLI_timeout_seconds=600,
            API_verification_seconds=180,maximum_batch_runs=3,scientific_acceptance=False)
        request_gate(request);request_ref=write(a.plan_output/'request.json',request)
        bindings=dict(MODEL_V3_PAIRED_SOURCE_SHA=pin['sha256'],MODEL_V3_PAIRED_OUTPUT=str(a.job_output.absolute()),
            MODEL_V3_PAIRED_MANIFEST=raw['path'],MODEL_V3_PAIRED_MANIFEST_SHA=raw['sha256'],
            MODEL_V3_PAIRED_REQUEST=request_ref['path'],MODEL_V3_PAIRED_REQUEST_SHA=request_ref['sha256'])
    result=write(a.plan_output/'bindings.json',bindings)
    print(json.dumps(dict(bindings=result,source_pins=pin,mode=a.mode,SDK_opened=False,online_action=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())