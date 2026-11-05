"""Metadata-only freeze for one complete114-module/four-pytest candidate parent.

No test import/collection, model, target, submission or monitor. Reuses the
exact tested numeric-v1 identity/fixture/worker/supervisor/control in place.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys

P=Path('/share/home/zixiao/descriptor_analysis');N=P/'runs/model_v3_20261026';O=P/'runs/model_v3_20261025'
HERE=Path(__file__).resolve().parent
OLD=N/'numeric_full_regression_v1_source'
WRAPPER=O/'run_attention_centering_full_regression_v1.sbatch'
TREE=P/'MFM_model_v3_attention_centering_v1'

def require(ok,message):
    if not ok:raise ValueError(message)
def raw_ref(path):
    import hashlib,stat
    path=Path(path).absolute();before=path.lstat()
    require(path==path.resolve(strict=True) and stat.S_ISREG(before.st_mode)
        and before.st_uid==1278 and before.st_nlink==1 and before.st_size<=16<<20,'Physical bounded owned source required')
    data=path.read_bytes();after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Source changed during binding')
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def json_file(path):
    return json.loads(Path(path).read_bytes())
def prepared(sha):
    own=raw_ref(HERE/'prepared_source_pins_v1.json');require(own['sha256']==sha,'Prepared source manifest differs')
    pins=json_file(own['path'])
    require(pins['schema']=='model_v3_attention_centering_full_regression_prepared_sources_v1','Prepared schema differs')
    for row in pins['files']:
        require(Path(row['file']).name==row['file'] and raw_ref(HERE/row['file'])==
            dict(path=str(HERE/row['file']),bytes=row['bytes'],sha256=row['sha256']),'Prepared leaf changed')
    deps=json_file(HERE/'dependencies.json')
    for value in deps.values():require(raw_ref(value['path'])==value,'Frozen original source/policy dependency changed')
    require(deps['legacy_pins']['path']==str(OLD/'source_pins_v1.json')
        and deps['legacy_spec']['path']==str(OLD/'request_spec_v1.json')
        and deps['wrapper']['path']==str(WRAPPER),'Only declared old v4 implementation/new wrapper admitted')
    original=Path(deps['legacy_wrapper']['path']).read_bytes()
    require(original.count(b'--job-name=model_v3_identity_regression_v4')==1
        and original.count(b'$task_revision/source_pins_v1.json')==2,'Original thin-wrapper edit points changed')
    wanted=original.replace(b'--job-name=model_v3_identity_regression_v4',b'--job-name=model_v3_attention_centering_full_v1')
    anchor=b'task_revision=/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/numeric_full_regression_v1_source'
    require(wanted.count(anchor)==1,'Original fixed supervisor path changed')
    wanted=wanted.replace(anchor,anchor+b'\ntask_source_inventory='+str(HERE).encode())
    wanted=wanted.replace(b'$task_revision/source_pins_v1.json',b'$task_source_inventory/source_pins_v1.json')
    require(WRAPPER.read_bytes()==wanted,'Wrapper must be exact original body plus declared job name/new inventory path')
    sys.path.insert(0,str(OLD))
    spec=importlib.util.spec_from_file_location('identity_revision_v4',OLD/'identity_revision_v4.py')
    identity=importlib.util.module_from_spec(spec);sys.modules[spec.name]=identity;spec.loader.exec_module(identity)
    legacy=identity.verify_source_pins(Path(deps['legacy_pins']['path']),deps['legacy_pins']['sha256'])
    control=identity.load_fixed_control(legacy)
    require(control.CONTROL==OLD and control.RUNS==O,'Legacy control namespaces must remain original')
    return own,pins,deps,identity,legacy,control
def add_ref(mapping,value):
    previous=mapping.get(value['path'])
    require(previous is None or previous==value,'Repeated source path has different raw identity')
    mapping[value['path']]=value
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-source-pins-sha256',required=True)
    parser.add_argument('--code-commit',required=True)
    parser.add_argument('--new-test-relative',required=True)
    parser.add_argument('--candidate-source-pins',type=Path,required=True)
    parser.add_argument('--candidate-source-pins-sha256',required=True)
    parser.add_argument('--candidate-source-relative',action='append',default=[])
    parser.add_argument('--label',required=True)
    args=parser.parse_args()
    require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','Root login metadata freeze only')
    own,prepared_pins,deps,identity,legacy,control=prepared(args.prepared_source_pins_sha256)
    policy=control.json_file(HERE/'policy_v1.json')
    require(policy['schema']=='model_v3_attention_centering_full_regression_policy_v1'
        and policy['tree']==str(TREE) and policy['parent_count']==1 and policy['pytest_children']==4
        and policy['test_file_count']==114,'Exact new complete-suite policy required')
    require(re.fullmatch('[A-Za-z0-9_]{1,64}',args.label) and control.COMMIT.fullmatch(args.code_commit),
        'Fresh simple label/actual committed SHA required')
    relative=Path(args.new_test_relative)
    require(relative.parts[:2]==('current','tests') and len(relative.parts)==3
        and relative.name.startswith('test_') and relative.suffix=='.py','Explicit new direct test module required')
    # Metadata Git only. Compute-side regression receives this same fixed Git path from wrapper.
    os.environ['PATH']=str(O/'cpu_git_tools_v1/bin')+os.pathsep+os.environ.get('PATH','')
    actual=control.git_clean_snapshot(TREE)
    require(actual['head']==args.code_commit,'Actual clean candidate HEAD differs from Root machine commit')
    old_spec=control.json_file(deps['legacy_spec']['path'],deps['legacy_spec']['sha256'])
    scope=control.source_scope(old_spec['source_scope']['external_python'],old_spec['source_scope']['workflow_config_files'])
    require(scope==old_spec['source_scope'],'Original complete v4 runtime/external/workflow scope must remain exact')
    sources=control.capture_sources(TREE,scope,args.code_commit)
    tests={name:sha for name,sha in sources['runtime']['project_source_sha256'].items()
        if Path(name).parent==Path('current/tests') and Path(name).name.startswith('test_')}
    all_recursive={str(p.relative_to(TREE)) for p in (TREE/'current/tests').rglob('test_*.py')}
    old_tests=old_spec['all_test_file_sha256']
    require(len(old_tests)==old_spec['test_file_count']==113 and args.new_test_relative not in old_tests
        and set(tests)==set(old_tests)|{args.new_test_relative}==all_recursive and len(tests)==114,
        'Exactly all original113 test modules plus explicit new module required; no omission/nested test')
    require(all(tests[name]==sha for name,sha in old_tests.items()),
        'Original113 test bytes changed; explicit protocol review needed, never silently weaken a test')
    candidate_manifest=raw_ref(args.candidate_source_pins)
    require(candidate_manifest['sha256']==args.candidate_source_pins_sha256,'Actual frozen candidate metadata SHA differs')
    candidate_json=control.json_file(candidate_manifest['path'],candidate_manifest['sha256'])
    require(type(candidate_json.get('source_refs')) is list and candidate_json['source_refs']
        and type(candidate_json.get('protected_unchanged_refs')) is list,'Actual candidate source-freeze field interface required')
    candidate_refs={};changes=[]
    for value in candidate_json['source_refs']+candidate_json['protected_unchanged_refs']:
        current=raw_ref(value['path'])
        require(current['bytes']==value['bytes'] and current['sha256']==value['sha256'],'Declared frozen/protected candidate source drift')
        candidate_refs[current['path']]=dict(path=current['path'],sha256=current['sha256'])
    original_root=Path(old_spec['tree'])
    for value in old_spec['candidate_frozen_sources']:
        original=Path(value['path'])
        if original.is_relative_to(original_root):
            mapped=TREE/original.relative_to(original_root);current=raw_ref(mapped)
            if current['sha256']!=value['sha256']:
                changes.append(dict(path=str(mapped),original_SHA=value['sha256'],actual_committed_SHA=current['sha256']))
        else:
            current=raw_ref(original);require(current['sha256']==value['sha256'],'Original external frozen source changed')
        candidate_refs[current['path']]=dict(path=current['path'],sha256=current['sha256'])
    for name in [args.new_test_relative,*args.candidate_source_relative]:
        path=TREE/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and path.is_file(),'Explicit candidate source path escaped/missing')
        current=raw_ref(path);candidate_refs[current['path']]=dict(path=current['path'],sha256=current['sha256'])
    candidate_refs[candidate_manifest['path']]=dict(path=candidate_manifest['path'],sha256=candidate_manifest['sha256'])
    spec_path=HERE/'request_spec_v1.json';pins_path=HERE/'source_pins_v1.json'
    runs=control.RUNS
    paths={key:runs/(args.label+suffix) for key,suffix in (
        ('assignment','_assignment_v1.json'),('plan','_control_v1.json'),('binding','_part0_bindings_v1.json'),
        ('launch','_part0_launch_v1.json'),('receipt','_part0_submission_v4.json'))}
    require(not any(p.exists() for p in [spec_path,pins_path,*paths.values()]),'Fresh freeze artifacts/label required; keep previous partial evidence')
    spec_value=dict(schema='model_v3_numeric_single_parent_spec_v1',status='ACTUAL_COMMITTED_SOURCE_FROZEN_NOT_EXECUTED',
        tree=str(TREE),parent_count=1,pytest_children=4,test_file_count=114,all_test_file_sha256=tests,
        planning_only_expected_collection=None,historic_full_certificate=old_spec['historic_full_certificate'],
        historic_counts=old_spec['historic_counts'],new_actual_counts=None,new_actual_reader_acceptance_not_claimed=True,
        source_scope=scope,candidate_frozen_sources=[candidate_refs[k] for k in sorted(candidate_refs)],
        candidate_original_manifest=candidate_manifest,legacy_spec=deps['legacy_spec'],
        additional_test_module=args.new_test_relative,actual_local_commit_required_at_freeze=True,
        actual_code_commit=args.code_commit,old_test_bytes_preserved=True,
        original_runtime_and_external_scope_preserved=True,Root_fresh_resource_admission_required=True,
        source_only_no_submit_or_model=True,changed_committed_base_candidate_sources=changes)
    spec_sha=control.write_exclusive(spec_path,spec_value)
    runtime={}
    for value in legacy['runtime_sources']:add_ref(runtime,value)
    for value in (raw_ref(__file__),raw_ref(spec_path),raw_ref(WRAPPER),raw_ref(HERE/'policy_v1.json'),
                  own,deps['legacy_pins'],candidate_manifest):add_ref(runtime,value)
    require(len(runtime)<=32,'Original bounded32-entry v4 runtime inventory exceeded; do not relax')
    new_pins=dict(schema=identity.PINS_SCHEMA,status='FROZEN_NOT_EXECUTED',
        runtime_sources=[runtime[k] for k in sorted(runtime)],identity_protocol=legacy['identity_protocol'],
        test_file_count=114,planned_collection_only=None,actual_code_commit=args.code_commit,
        complete_runtime_scope=scope['schema'],prepared_source_manifest=own,legacy_source_manifest=deps['legacy_pins'],
        old_identity_fixture_worker_supervisor_control_reused_in_place=True,
        new_actual_counts=None,source_inventory_not_execution_or_scientific_acceptance=True)
    pins_sha=control.write_exclusive(pins_path,new_pins)
    pins=identity.verify_source_pins(pins_path,pins_sha)
    names=sorted(tests)
    assignment=dict(schema=control.ASSIGNMENT_SCHEMA,code_sha=args.code_commit,partitions=1,all_test_file_sha256=tests,
        assignments=[dict(index=0,files=names)],per_job_output_budget_bytes=2*1024**3,
        planning_only_expected_collection=None,historic_full_certificate=old_spec['historic_full_certificate'],
        skip_scope='All ordinary/optional tests selected; actual skip evidence only; no historical reader upgrade',
        capacity_is_a_conservative_plan_not_peak_proof=True)
    control.validate_assignment(assignment,args.code_commit)
    assignment_sha=control.write_exclusive(paths['assignment'],assignment)
    controls={value['path']:value['sha256'] for value in pins['runtime_sources']}
    for row in prepared_pins['files']:
        controls[str(HERE/row['file'])]=row['sha256']
    controls.update({r['path']:r['sha256'] for r in spec_value['candidate_frozen_sources']})
    controls[str(pins_path)]=pins_sha;controls[str(spec_path)]=spec_sha
    runner=OLD/'run_regression_worker_identity_v4.py'
    contract=dict(tree=str(TREE),code_sha=args.code_commit,runs=str(runs),control_root=str(control.CONTROL),
        plan_path=str(paths['plan']),python='/share/home/zixiao/.conda/envs/chemprop/bin/python',runtime=sources['runtime'],
        assignment=dict(path=str(paths['assignment']),sha256=assignment_sha),
        runner=dict(path=str(runner),sha256=control.file_sha(runner)),
        scheduler_script=dict(path=str(WRAPPER),sha256=control.file_sha(WRAPPER)),
        control_files=[dict(path=path,sha256=sha) for path,sha in sorted(controls.items())],
        binding_paths=[str(paths['binding'])],receipt_paths=[str(paths['receipt'])],
        capacity_is_a_conservative_plan_not_peak_proof=True)
    values=control.base_bindings(contract,0)
    binding_sha=control.write_exclusive(paths['binding'],values)
    plan=dict(schema=control.PLAN_SCHEMA,contract=contract,contract_sha256=control.digest_bytes(control.canonical(contract)),
        bindings=[dict(path=str(paths['binding']),sha256=binding_sha,values=values)])
    plan_sha=control.write_exclusive(paths['plan'],plan)
    control.verify_frozen_plan(paths['plan'],plan_sha)
    launch=control.launch_bindings(plan,plan_sha,0)
    launch_sha=control.write_exclusive(paths['launch'],launch)
    require(control.json_file(paths['launch'],launch_sha)==launch,'Fresh launch binding differs')
    prepared(args.prepared_source_pins_sha256)
    print(json.dumps(dict(status='FROZEN_NOT_EXECUTED',plan=str(paths['plan']),plan_sha256=plan_sha,
        code_commit=args.code_commit,source_scope=scope['schema'],test_file_count=114,parent_count=1,workers=4,
        planning_only_expected_collection=None,request_spec=dict(path=str(spec_path),sha256=spec_sha),
        source_pins=dict(path=str(pins_path),sha256=pins_sha),runtime_inventory_count=len(runtime),
        launch_bindings=str(paths['launch']),launch_bindings_sha256=launch_sha,
        scheduler_script=contract['scheduler_script'],submission_receipt=str(paths['receipt']),
        old_implementation_modules_unchanged=True,actual_collection_or_QA_not_claimed=True),sort_keys=True))
if __name__=='__main__':main()

