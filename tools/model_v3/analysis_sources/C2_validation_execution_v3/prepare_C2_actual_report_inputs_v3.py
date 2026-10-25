"""Bind only an actually successful fixed VAL job for independent reporting."""
import hashlib
import json
from pathlib import Path
import subprocess
BASE=Path('/share/home/zixiao/descriptor_analysis');RUNS=BASE/'runs/model_v3_20261025';REPO=BASE/'MFM_model_v3'
def ref(path):
    raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    path.chmod(0o644)
def main():
    job=json.loads((RUNS/'C2_prior_TRAIN_first_VAL_submission_v2.json').read_text())['job_id']
    argv=['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS']
    raw=subprocess.check_output(argv,text=True,timeout=45);rows=[r.split('|') for r in raw.splitlines() if r]
    if len(rows)!=1 or rows[0][:3]!=[job,'COMPLETED','0:0']:raise ValueError('Actual current VAL job must be C0 before report binding')
    supervisor=RUNS/('C2_first_VAL_supervisor_'+job+'.json');guard=json.loads(supervisor.read_text())
    if guard['status']!='COMPLETED' or guard['exit_code'] or guard['remaining'] or guard['first_failure'] is not None or guard['private_storage']['first_sampling_failure'] is not None:raise ValueError('Successful full source/SDK/cleanup closure required')
    closure_path=RUNS/'C2_artifact_v3_actual_VAL_root_closure_v1.json'
    write(closure_path,dict(schema='model_v3_C2_artifact_v3_root_closure_v1',source_job=dict(job_id=job,state=rows[0][1],exit_code=rows[0][2],elapsed_seconds=int(rows[0][3])),raw_sacct=dict(argv=argv,stdout=raw,stdout_sha256=hashlib.sha256(raw.encode()).hexdigest()),supervisor=ref(supervisor)))
    inputs_path=RUNS/'C2_prior_TRAIN_first_VAL_inputs_v2.json';inputs=json.loads(inputs_path.read_text())
    output=RUNS/('C2_prior_TRAIN_first_VAL_'+job);sdks=list(output.glob('wandb/offline-run-*/run-*.wandb'))
    if len(sdks)!=1:raise ValueError('Exactly one original offline SDK required')
    protocol=REPO/inputs['protocol_registration']['path']
    if ref(protocol)['sha256']!=inputs['protocol_registration']['sha256']:raise ValueError('Actual committed v3 protocol drift')
    manifest=dict(schema='model_v3_C2_artifact_v3_report_inputs_v1',expected_job_id=job,root_closure=ref(closure_path),
        source_request=ref(Path(inputs['source_request']['path'])),selection_plan=ref(Path(inputs['selection_plan']['path'])),
        artifact_inputs=ref(inputs_path),protocol=ref(protocol),protocol_registration=inputs['protocol_registration'],SDK_file=ref(sdks[0]))
    for key,suffix in [('input_binding','INPUT_BINDING'),('fit_receipt','FIT_RECEIPT'),('completion','COMPLETE'),('result','RESULT')]:manifest[key]=ref(output/('BASELINE_v2_ARTIFACT_'+suffix+'.json'))
    path=RUNS/'C2_artifact_v3_report_inputs_v1.json';write(path,manifest)
    write(RUNS/'C2_artifact_v3_report_bindings_v1.json',dict(MODEL_V3_C2_REPORT_INPUTS=str(path),MODEL_V3_C2_REPORT_INPUTS_SHA=ref(path)['sha256']))
    print(json.dumps(dict(status='ACTUAL_SUCCESSFUL_VAL_BOUND_FOR_INDEPENDENT_SDK_REPORT',job_id=job,inputs=ref(path))))
if __name__=='__main__':main()
