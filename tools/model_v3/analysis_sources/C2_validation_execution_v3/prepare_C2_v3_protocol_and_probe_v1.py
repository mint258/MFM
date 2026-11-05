"""Register the fixed identity verifier, then bind a geometry-free preflight."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
BASE=Path('/share/home/zixiao/descriptor_analysis');RUNS=BASE/'runs/model_v3_20261025';REPO=BASE/'MFM_model_v3'
REL='configs/model_v3/c2_prior_TRAIN_artifact_v3_adopted.json'
def ref(path):
    raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    path.chmod(0o644)
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args],timeout=45)
def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['protocol','probe-inputs']);a=p.parse_args()
    src=RUNS/'c2_train_artifact_loader_v3_source'
    pins=json.loads((src/'FROZEN_CPU_TEST_REQUEST.json').read_text())
    for row in pins['source_files']:
        actual=ref(src/row['path'])
        if any(actual[k]!=row[k] for k in ('bytes','sha256')):raise ValueError('Frozen v3 source drift')
    if a.stage=='protocol':
        summary=json.loads((RUNS/'frozen_units_4520599/summary.json').read_text())
        u,=summary['units']
        if summary['status']!='PASS' or u['returncode'] or not u['sources_unchanged'] or u['counts']!=dict(tests=40,failures=0,errors=0,skipped=0):raise ValueError('Actual40 full tests including real559 metadata required')
        protocol=json.loads((src/'prior_TRAIN_artifact_v2_protocol.json').read_text())
        if protocol['adoption_status']!='PREPARED_CONDITIONAL_NOT_ADOPTED':raise ValueError('Preserve prepared source template')
        closure=ref(RUNS/'C2_TRAIN_artifact_closure_v1.json')
        protocol.update(adoption_status='ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC',TRAIN_closure_raw_sha256=closure['sha256'],
            prior_TRAIN_closure=closure,actual_CPU_unit_jobs=['4520575','4520591','4520599'],
            identity_validation_revision='v3_local_execution_ref_distinct_from_public_same_tree_registration',
            earlier_v2_VAL_entry_job_4520595_remains_FAILED_before_any_native_geometry=True,
            adoption_basis='Same fixed TRAIN559 coefficients and original scientific method; v3 repairs local/public/tree identity validation only, before any VAL result')
        write(REPO/REL,protocol)
        for folder,files,target_name in [
            ('c2_train_artifact_loader_v3_source',[r['path'] for r in pins['source_files']]+['FROZEN_CPU_TEST_REQUEST.json'],'c2_train_artifact_loader_v3'),
            ('archive_closed_v10_source',['archive_closed_runs_v10.py','test_archive_v10.py','README.md','source_pins_v10.json'],'archive_closed_v10')]:
            target=REPO/'tools/model_v3/analysis_sources'/target_name
            target.mkdir(parents=True,exist_ok=False)
            for name in files:shutil.copyfile(RUNS/folder/name,target/name);(target/name).chmod(0o644)
        print(json.dumps(dict(status='NEW_v3_PROTOCOL_PREPARED_NO_VAL',protocol=ref(REPO/REL))))
    else:
        commit=git('rev-parse','HEAD').decode().strip();raw=git('show',commit+':'+REL)
        if raw!=(REPO/REL).read_bytes():raise ValueError('Commit actual prepared v3 protocol first')
        inputs=json.loads((RUNS/'C2_prior_TRAIN_first_VAL_inputs_v1.json').read_text())
        inputs.update(protocol_registration=dict(repository=str(REPO),commit=commit,path=REL,sha256=hashlib.sha256(raw).hexdigest()),
            public_registration=None,preflight_only=True)
        out=RUNS/'C2_v3_TRAIN_artifact_preflight_inputs_v1.json';write(out,inputs)
        write(RUNS/'C2_v3_TRAIN_artifact_preflight_bindings_v1.json',dict(MODEL_V3_C2_ARTIFACT_INPUTS=str(out),MODEL_V3_C2_ARTIFACT_INPUTS_SHA=ref(out)['sha256']))
        print(json.dumps(dict(status='LOCAL_PROTOCOL_BOUND_TRAIN_ARRAYS_ONLY_NO_GEOMETRY',inputs=ref(out))))
if __name__=='__main__':main()
