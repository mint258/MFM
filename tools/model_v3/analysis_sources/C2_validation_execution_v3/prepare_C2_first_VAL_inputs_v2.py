"""Root actual public protocol and prior-TRAIN source closure for first fixed VAL."""
import hashlib
import json
from pathlib import Path
import subprocess

BASE=Path('/share/home/zixiao/descriptor_analysis');RUNS=BASE/'runs/model_v3_20261025';REPO=BASE/'MFM_model_v3'
OUT=RUNS/'C2_prior_TRAIN_first_VAL_inputs_v2.json'
def ref(path):
    raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
    if OUT.exists():raise FileExistsError('Preserve actual bound VAL inputs')
    probe_job=json.loads((RUNS/'C2_v3_TRAIN_artifact_preflight_submission_v1.json').read_text())['job_id']
    actual=subprocess.check_output(['sacct','-X','-n','-P','-j',probe_job,'--format=JobIDRaw,State,ExitCode'],text=True,timeout=45)
    probe=json.loads((RUNS/('C2_artifact_probe_'+probe_job)/'PREFLIGHT.json').read_text())
    if actual.strip()!=probe_job+'|COMPLETED|0:0' or probe['status']!='PASS_NO_NATIVE_GEOMETRY_NO_EVALUATION' or probe['current_job_TRAIN_geometry_reads'] or probe['current_job_PRETRAIN_VAL_geometry_reads'] or probe['native_geometry_reader_imported']:raise ValueError('Actual real TRAIN artifact-only probe required')
    public=json.loads((RUNS/'publication_C2_identity_v3_public_receipt_v1.json').read_text())
    if not public['published_head_readback_verified'] or not public['exact_tree_verified']:raise ValueError('Actual public registration required before VAL')
    commit=public['local_code_sha']
    tree=subprocess.check_output(['git','-C',str(REPO),'rev-parse',commit+'^{tree}'],text=True).strip()
    if tree!=public['tree_sha']:raise ValueError('Public and actual method tree differ')
    relative='configs/model_v3/c2_prior_TRAIN_artifact_v3_adopted.json'
    raw=subprocess.check_output(['git','-C',str(REPO),'show',commit+':'+relative]);protocol=json.loads(raw)
    if protocol['adoption_status']!='ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC':raise ValueError('Adopted analysis protocol required')
    source=RUNS/'c2_train_artifact_loader_v3_source'
    inventory=json.loads((source/'FROZEN_CPU_TEST_REQUEST.json').read_text())
    for row in inventory['source_files']:
        actual=ref(source/row['path'])
        if any(actual[k]!=row[k] for k in ('bytes','sha256')):raise ValueError('Tested artifact loader drifted')
    diagnostic=RUNS/'C2_train_diagnostic_4520559'
    inputs=dict(schema='model_v3_C2_prior_TRAIN_artifact_v2_inputs_v1',source_repository=str(BASE/'MFM_model_v3_c2'),
        source_request=ref(RUNS/'c2_bind_4520475/source_request.json'),selection_plan=ref(RUNS/'c2_prepare_4520477/selection_plan.json'),
        TRAIN_diagnostic_result=ref(diagnostic/'DIAGNOSTIC_RESULT.json'),TRAIN_diagnostic_done=ref(diagnostic/'DIAGNOSTIC_DONE.json'),
        TRAIN_diagnostic_input_binding=ref(diagnostic/'input_binding.json'),TRAIN_closure=ref(RUNS/'C2_TRAIN_artifact_closure_v1.json'),
        TRAIN_artifact=ref(diagnostic/'active_coefficients_and_support.npz'),
        runtime_monitor={k:v for k,v in ref(BASE/'MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py').items() if k!='bytes'},
        protocol_registration=dict(repository=str(REPO),commit=commit,path=relative,sha256=hashlib.sha256(raw).hexdigest()),
        public_registration=dict(commit=public['github_commit_sha'],tree=tree),new_parameter_estimation_requested=False)
    for key,protocol_key in [('source_request','source_request_raw_sha256'),('selection_plan','selection_plan_raw_sha256'),
        ('TRAIN_diagnostic_result','TRAIN_diagnostic_result_raw_sha256'),('TRAIN_diagnostic_done','TRAIN_diagnostic_done_raw_sha256'),
        ('TRAIN_diagnostic_input_binding','TRAIN_diagnostic_input_binding_raw_sha256'),('TRAIN_closure','TRAIN_closure_raw_sha256'),
        ('TRAIN_artifact','TRAIN_artifact_raw_sha256')]:
        if inputs[key]['sha256']!=protocol[protocol_key]:raise ValueError('Registered original TRAIN input changed: '+key)
    with OUT.open('x') as stream:json.dump(inputs,stream,indent=2);stream.write('\n')
    with (RUNS/'C2_prior_TRAIN_first_VAL_bindings_v2.json').open('x') as stream:
        json.dump(dict(MODEL_V3_C2_ARTIFACT_INPUTS=str(OUT),MODEL_V3_C2_ARTIFACT_INPUTS_SHA=ref(OUT)['sha256']),stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status='PUBLICLY_ADOPTED_INPUTS_BOUND_FOR_FIRST_VAL',inputs=ref(OUT),public_commit=public['github_commit_sha'])))
if __name__=='__main__':main()
