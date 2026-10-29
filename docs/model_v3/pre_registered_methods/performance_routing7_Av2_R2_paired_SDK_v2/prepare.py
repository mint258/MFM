"""One actual routing7 pair; Root captures true C0 and only stats original SDKs."""
from __future__ import annotations
import argparse
from paired_common import *
from prepare_sync import capture_C0
from routing_metadata import numeric_bundle,stat_saved

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('audit','sync'));p.add_argument('--pins-sha256',required=True)
    p.add_argument('--plan-output',type=Path,required=True);p.add_argument('--job-output',type=Path,required=True)
    p.add_argument('--r2-closure',type=Path);p.add_argument('--r2-closure-sha256');p.add_argument('--old-job-id')
    p.add_argument('--audit-result',type=Path);p.add_argument('--audit-supervisor',type=Path);p.add_argument('--runs',nargs='+')
    a=p.parse_args();root_only();pin=verify(a.pins_sha256)
    require(a.plan_output.absolute().parent==HERE.parent and a.job_output.absolute().parent==HERE.parent
        and not a.plan_output.exists() and not a.job_output.exists(),'Explicit fresh owned plan/output required')
    if a.mode=='audit':
        require(a.r2_closure is not None and a.r2_closure_sha256 is not None and a.old_job_id is not None
            and a.audit_result is a.audit_supervisor is a.runs is None,'Actual numeric Root closure and one old selector required')
        root_ref=ref(a.r2_closure);require(root_ref['sha256']==a.r2_closure_sha256,'Actual numeric Root rawSHA differs')
        root,result,row,planned,plan,_=numeric_bundle(root_ref)
        require(root['old_job_id']==a.old_job_id,'Explicit selector differs from actual Root numeric closure')
        a.plan_output.mkdir(mode=0o700)
        model_C0=capture_C0(root['job_id'],a.plan_output/'model_actual_C0')
        cpu_C0=capture_C0(result['allocation']['job_id'],a.plan_output/'metadata_CPU_actual_C0')
        require(terminal_C0(model_C0)['job_id']==root['job_id']
            and terminal_C0(cpu_C0)['job_id']==result['allocation']['job_id'],'Actual original GPU and metadata CPU C0 required')
        saved_ref=stat_saved(root_ref,a.plan_output);saved=read(saved_ref)
        refs={key:row['closed_metadata'][name] for key,name in
            (('configuration','configuration'),('summary','summary'),('status','run_status'),('supervisor','supervisor'))}
        submission=read(row['submission'])
        refs.update(root=root_ref,metadata_CPU_result=root['metadata_CPU_result'],metadata_CPU_supervisor=root['metadata_CPU_supervisor'],
            metadata_GPU_sacct=result['actual_parent_sacct'],saved_sdk_descriptors=saved_ref,submission=row['submission'],
            operations_publication=submission['operations_publication'],original_configuration=planned['original_configuration'],
            candidate_options=planned['candidate_options'])
        case=dict(job_id=root['job_id'],old_job_id=root['old_job_id'],refs=refs,journals=saved['journals'],sdks=saved['sdks'],
            actual_model_C0=model_C0,actual_metadata_CPU_C0=cpu_C0)
        metadata_case(case)
        inputs=dict(schema='performance_routing7_Av2_R2_paired_log_inputs_v1',scope=SCOPE,cases=[case],
            source_pins=pin,scientific_acceptance=False,original_descriptors_only=True)
        input_ref=write(a.plan_output/'inputs.json',inputs);bound_inputs(input_ref)
        bindings=dict(MODEL_V3_PAIRED_SOURCE_SHA=pin['sha256'],MODEL_V3_PAIRED_OUTPUT=str(a.job_output.absolute()),
            MODEL_V3_PAIRED_INPUTS=input_ref['path'],MODEL_V3_PAIRED_INPUTS_SHA=input_ref['sha256'])
    else:
        require(a.r2_closure is a.r2_closure_sha256 is a.old_job_id is None
            and a.audit_result is not None and a.audit_supervisor is not None and a.runs is not None,
            'Actual audit refs and explicit two IDs required; no replacement producer inputs')
        batch_ref=ref(a.audit_result);batch=read(batch_ref);bound_inputs(batch['inputs'])
        require(len(a.runs)==len(set(a.runs))==2 and set(a.runs)==IDS,'This once-only batch selects exactly both audited SDKs')
        job=batch['actual_job_id'];require(type(job) is str and job.isdigit(),'Actual audit job required')
        a.plan_output.mkdir(mode=0o700)
        manifest=dict(schema='performance_routing7_Av2_R2_paired_sync_manifest_v1',verifications=batch['verifications'],
            audit_result=batch_ref,audit_supervisor=ref(a.audit_supervisor),
            actual_audit_C0=capture_C0(job,a.plan_output/'audit_actual_C0'))
        manifest['runs']=proof_rows(manifest);raw=write(a.plan_output/'explicit_manifest.json',manifest)
        os.environ['MODEL_V3_PAIRED_MANIFEST']=raw['path'];os.environ['MODEL_V3_PAIRED_MANIFEST_SHA']=raw['sha256']
        gate=dict(result=ref(HERE.parent/'WandB_sync50_pilot_actual_v3/RESULT.json'),
            supervisor=ref(HERE.parent/'WandB_sync50_pilot_actual_v3.supervisor.json'),
            actual_terminal=capture_C0('4521412',a.plan_output/'method_actual_C0'),
            native_exit_code=1,actual_replay_verified=True)
        request=dict(schema='performance_routing7_Av2_R2_paired_selective_sync_request_v1',mode='batch',
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
