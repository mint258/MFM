"""Unexecuted stdlib-only final metadata builder. Never trains or submits.

assemble() returns metadata only. The explicit Root --write-final CLI calls the
separate writer after actual CPU/publication checks; the author invokes neither.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime,timezone

B = Path('/share/home/zixiao/descriptor_analysis')
HERE = Path(__file__).absolute().parent
ROOT = B/'MFM_model_v3_attention_centering_v1'
OLD_ROOT = B/'MFM_model_v3_numeric_stability_v1'
LOCAL = 'cf8ce66d97cd518ebf279b40ee20294919bb95e1'
TREE = '2389ab046ee23f2ba92fcb61179d853dfdee8357'
BASE = '4068623cc455915a34a4aacae4f0df5c56f691b7'
PARENT = '5cdb2772dfa51e1cc72098c659fb741440219772'
BRANCH = 'model-v3-attention-centering-20261027-v1'
FIXTURE = B/'MFM_model_v3_composed_equivariance_runtime_v3/current/phychem_mfm/phase1/v3_composed_equivariance.py'
FIXTURE_SHA = '0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8'
GUARD = B/'runs/model_v3_20261026/gpu_runtime_retry_v4/submit_composed_eq_gpu_runtime_retry_v4.py'
GUARD_SHA = 'd3cba6a8610e6bd55fa21873be5c770efbe30be73b7b16d4f1cbdfa6ccb1c193'
SCIENCE_FILES = ('centered_adapter.py','centered_publication.py','run_centered_matrix.py',
    'test_centered_matrix.py','tiny_candidate_controls.py','launch_centered_matrix_GPU_v1.py',
    'run_centered_matrix_GPU_v1.sbatch')
CRITICAL = frozenset(('current/phychem_mfm/model/attention.py','current/phychem_mfm/model/backbone.py',
    'current/phychem_mfm/model/shared.py','current/phychem_mfm/model/v3_architecture.py',
    'current/phychem_mfm/model/v3_attention_numerics.py','current/phychem_mfm/model/v3_numeric_stability.py',
    'current/phychem_mfm/model/v3_heads.py','current/phychem_mfm/model/v3_performance.py'))

def need(value,message):
    if not value:raise ValueError(message)

def ref(path,maximum=None):
    path = Path(path).absolute()
    if maximum is None:
        exact_QA_XML = re.fullmatch(re.escape(str(B/'runs/model_v3_20261025'))+
            r'/integration_tests_\d+/shard_0[0-3]\.xml',str(path)) is not None
        maximum = 16<<20 if exact_QA_XML else 2<<20
    need(path.is_relative_to(B) and path.suffix.lower() not in
         ('.wandb','.npz','.npy','.pt','.pth','.safetensors','.pkl','.jsonl','.lmdb','.mdb'),
         'Project source/metadata only; no SDK/tensor/data payload')
    before = path.lstat()
    need(path == path.resolve(strict=True) and stat.S_ISREG(before.st_mode)
         and before.st_uid == os.getuid() and before.st_nlink == 1 and before.st_size <= maximum,
         'Owned physical bounded source/metadata required')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):digest.update(block)
    after = path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'File changed while binding')
    return {'path':str(path),'bytes':before.st_size,'sha256':digest.hexdigest()}

def bound(value):
    need(set(value) == {'path','bytes','sha256'} and ref(value['path']) == value,'Actual metadata rawref differs')
    def unique(pairs):
        result = {}
        for key,item in pairs:
            need(key not in result,'Duplicate metadata key');result[key] = item
        return result
    value_read = json.loads(Path(value['path']).read_bytes(),object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))
    need(ref(value['path']) == value,'Metadata changed during decode')
    return value_read

def command(argv):
    result = subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=False)
    need(result.returncode == 0 and len(result.stdout)+len(result.stderr) <= 2<<20,'Metadata command failed')
    return {'argv':argv,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
        'stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),
        'stderr_sha256':hashlib.sha256(result.stderr.encode()).hexdigest()}

def unchanged_scientific_bodies():
    inventory = bound(ref(HERE/'DRAFT_SOURCE_INVENTORY.json'))
    previous = {x['file']:x for x in inventory['files']}
    for name in SCIENCE_FILES:
        need(ref(HERE/name) == {key:previous[name][key] for key in ('path','bytes','sha256')},
             'A Root-reviewed scientific/launch body drifted; report and re-review, do not silently rebind: '+name)

def _load_control(value):
    bound_source = ref(value['path']);need(bound_source == value,'Frozen QA control source differs')
    path = Path(value['path'])
    # No sys.modules removal/path extension/canonical model imports. The old
    # control is stdlib-only and the worker namespace remains entirely separate.
    for name in ('regression_identity_v4','regression_fixture_policy_v1'):
        if name in sys.modules:
            need(Path(sys.modules[name].__file__).absolute().parent == path.parent,'Foreign metadata helper namespace')
    sys.path.insert(0,str(path.parent))
    spec = importlib.util.spec_from_file_location('centered_final_actual_QA_control',path)
    module = importlib.util.module_from_spec(spec);sys.modules[spec.name] = module;spec.loader.exec_module(module)
    return module

def actual_cpu_qa(*,summary_ref,supervisor_ref,submission_ref,plan_ref,assignment_ref,control_module_ref):
    """No planned73/114 case count. Parse actual four JUnits and actual sacct."""
    summary,supervisor,submission = bound(summary_ref),bound(supervisor_ref),bound(submission_ref)
    plan,assignment = bound(plan_ref),bound(assignment_ref)
    control = _load_control(control_module_ref)
    control.validate_submission_metadata(plan,plan_ref['sha256'],submission,summary,supervisor,assignment)
    need(summary['code_commit'] == LOCAL and summary['test_file_count'] == 114
         and summary['workers'] == 4 and len(summary['shards']) == 4,
         'Actual whole114-file/four-pytest candidate QA required (114 is files, not collected cases)')
    job = str(summary['job_id'])
    need(job.isdigit() and Path(summary_ref['path']).parent == B/'runs/model_v3_20261025'/('integration_tests_'+job),
         'Actual QA artifact path/job identity differs')
    xml_refs,counts = [],{key:0 for key in ('tests','failures','errors','skipped')}
    new_file_counts = {key:0 for key in counts}
    for index in range(4):
        value = ref(Path(summary_ref['path']).parent/('shard_%02d.xml' % index))
        xml = ET.parse(value['path']).getroot()
        for suite in xml.iter('testsuite'):
            for key in counts:counts[key] += int(suite.attrib.get(key,0))
        for case in xml.iter('testcase'):
            if 'test_model_v3_attention_centering' in case.attrib.get('classname','').split('.'):
                new_file_counts['tests'] += 1
                for child,key in (('failure','failures'),('error','errors'),('skipped','skipped')):
                    new_file_counts[key] += int(case.find(child) is not None)
        xml_refs.append(value)
    need(counts == summary['counts'] and counts['tests'] > 0 and counts['failures'] == counts['errors'] == 0,
         'Actual four JUnit totals differ or failed; no invented collection/skip count')
    need(new_file_counts['tests'] > 0,'Actual new attention testcase coverage missing from JUnit')
    raw = command(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    rows = [x.split('|') for x in raw['stdout'].splitlines() if x.strip()]
    need(len(rows) == 1 and len(rows[0]) == 7 and rows[0][:4] == [job,'zixiao','COMPLETED','0:0']
         and rows[0][4].isdigit() and rows[0][5] == '16' and rows[0][6] == summary['expected_node'],
         'Actual candidate QA parent C0/16CPU/node missing')
    need(summary['sources_before'] == summary['sources_after'],'Actual source observations changed')
    for value in (summary['identity_registration_manifest'],summary['identity_source_inventory']):bound(value)
    return summary,{'schema':'model_v3_centered_actual_CPU_QA_binding_v1','status':'ACTUAL_QA_METADATA_VERIFIED',
        'job_id':job,'summary':summary_ref,'supervisor':supervisor_ref,'submission':submission_ref,
        'control_plan':plan_ref,'assignment':assignment_ref,'control_source':control_module_ref,
        'actual_XML':xml_refs,'actual_counts':counts,'actual_test_file_count':114,'actual_pytest_processes':4,
        'actual_new_attention_file_counts':new_file_counts,
        'raw_sacct':raw,'source_before_after_equal':True,'planned73_is_not_actual_collection':True,
        'scientific_GPU_acceptance':False}

def assemble(*,local_commit_proof_ref,source_freeze_ref,publication_receipt_ref,qa_inputs):
    """Return verified in-memory metadata only; writes no request/pins or reservation."""
    need(os.getuid() == 1278 and socket.gethostname().split('.')[0] == 'sonmi','Root login metadata context required')
    unchanged_scientific_bodies()
    local,freeze,publication = bound(local_commit_proof_ref),bound(source_freeze_ref),bound(publication_receipt_ref)
    need(local['local_commit'] == LOCAL and local['local_tree'] == TREE and local['files'] == 8
        and local['base_local_commit'] == BASE and local['parent_public_commit'] == PARENT
        and local['experimental_branch'] == BRANCH and local['source_manifest'] == source_freeze_ref,
        'Actual candidate local commit/freeze provenance differs')
    changed = {x['relative_path'] for x in freeze['source_refs']}
    need(len(changed) == 8 and len(changed|CRITICAL) == 10,'Exact eight changed/ten public-critical source set required')
    git_rows = [command(['git','-C',str(ROOT),'rev-parse','HEAD']),
                command(['git','-C',str(ROOT),'rev-parse','HEAD^{tree}']),
                command(['git','-C',str(ROOT),'status','--porcelain=v1','--untracked-files=all']),
                command(['git','-C',str(ROOT),'diff','--name-only',BASE,LOCAL])]
    need(git_rows[0]['stdout'].strip() == LOCAL and git_rows[1]['stdout'].strip() == TREE
        and git_rows[2]['stdout'] == '' and set(git_rows[3]['stdout'].splitlines()) == changed,
        'Current clean committed candidate differs from actual eight-file commit')
    for leaf in freeze['source_refs']+freeze['protected_unchanged_refs']:
        need(ref(leaf['path']) == {key:leaf[key] for key in ('path','bytes','sha256')},'Candidate freeze bytes changed')
    need(publication['schema'] == 'model_v3_numeric_candidate_publication_actual_v1'
        and publication['status'] == 'PUBLISHED_INDEPENDENT_PREREGISTRATION_BRANCH_READ_BACK'
        and publication['local_commit'] == LOCAL and publication['exact_shared_tree'] == TREE
        and publication['branch'] == BRANCH and publication['base_local_commit'] == BASE
        and publication['parent_public_commit'] == PARENT
        and publication['actual_ref_readback'] == publication['public_commit']
        and publication['changed_files'] == 8 and publication['explicit_critical_and_changed_public_files'] == 10
        and publication['public_commit'] != PARENT and len(publication['public_commit']) == 40,
        'Actual NEW independent experiment publication required; historical parent is not current publication')
    public = publication['files']
    need(len(public) == 10 and {x['path'] for x in public} == changed|CRITICAL,
        'Public blob table must contain CRITICAL8 union changed8 =10; API payload remains only changed8')
    sources = {}
    def add(value):
        need(ref(value['path']) == value,'Binding source changed')
        if value['path'] in sources:need(sources[value['path']] == value,'Conflicting duplicate source ref')
        sources[value['path']] = value
    summary,qa = actual_cpu_qa(**qa_inputs)
    runtime = summary['sources_before']['runtime']
    for name,digest in runtime['project_source_sha256'].items():
        path = Path(name) if Path(name).is_absolute() else ROOT/name
        need(path.is_relative_to(ROOT),'QA project source leaves independent candidate tree')
        actual = ref(path);need(actual['sha256'] == digest,'Current candidate differs from actually tested source')
        add(actual)
    external = runtime['external_source_refs']
    need(isinstance(external,dict),'Actual v4 external_source_refs NAME mapping required')
    for name,value in external.items():
        need(type(name) is str and set(value) == {'path','sha256'},'Actual external source descriptor differs')
        actual = ref(value['path'])
        need(actual['sha256'] == value['sha256'],'Actual external source bytes differ from tested SHA')
        add(actual)  # bytes comes from the actual file, never a guessed absent field.
    draft = bound(ref(HERE/'execution_request_DRAFT.json'))
    request = dict(draft)
    request.update(status='FINAL_BOUND_PUBLIC_EXPERIMENT_REQUEST',executable=True,local_commit=LOCAL,
        public_commit=publication['public_commit'],exact_shared_tree=TREE,publication_receipt=publication_receipt_ref,
        public_files=public,required_public_paths=sorted(changed|CRITICAL))
    for value in public:
        path = ROOT/value['path'];raw = path.read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        need(len(raw) == value['bytes'] and blob == value['git_blob_sha'],'Ten critical files require exact raw Git blob identities')
        add(ref(path))
    for value in (local_commit_proof_ref,source_freeze_ref,publication_receipt_ref,request['original_capture_manifest'],
                  request['UUID_admission_source'],request['supervisor_source']):add(value)
    fixture = ref(FIXTURE);need(fixture['sha256'] == FIXTURE_SHA,'Actual original complete48 fixture source differs')
    add(fixture)
    guard_ref = ref(GUARD);need(guard_ref['sha256'] == GUARD_SHA,'Frozen resource guard source differs')
    add(guard_ref)
    spec = importlib.util.spec_from_file_location('centered_final_original_resource_guard',GUARD)
    guard = importlib.util.module_from_spec(spec);sys.modules[spec.name] = guard;spec.loader.exec_module(guard)
    need(guard.NODE == 'compute-0-21' and guard.MEMORY_MIB == 32768
        and guard.RSS_BYTES == 30064771072 and guard.OUTPUT_BYTES == 2147483648
        and guard.WALL_SECONDS == 1100,'Original resource limits changed')
    for path,digest in guard.PINS.items():
        actual = ref(path);need(actual['sha256'] == digest,'Imported resource dependency differs');add(actual)
    actual = ref(guard.CLI);need(actual['sha256'] == guard.CLI_SHA,'Frozen CUuuid/CLI source differs');add(actual)
    capture = bound(request['original_capture_manifest'])
    need(capture['job_id'] == '4521492' and capture['status'] == 'CAPTURE_COMPLETE'
        and [x['case_id'] for x in capture['cases']] == request['expected_case_ids'],'Original complete48/capture order differs')
    for item in capture['cases']:add(item['capture_case'])
    for key in ('summary_ref','supervisor_ref','submission_ref','plan_ref','assignment_ref','control_module_ref'):
        add(qa_inputs[key])
    for value in qa['actual_XML']:add(value)
    for value in (summary['identity_registration_manifest'],summary['identity_source_inventory']):add(value)
    inventory = bound(summary['identity_source_inventory'])
    need(len(inventory['runtime_sources']) == 31,'Actual QA runtime dependency inventory differs')
    for value in inventory['runtime_sources']:add(value)
    evidence = publication['candidate_QA_evidence']
    need(len(evidence) == 2,'Actual candidate CPU and ordinary checker Root closures required')
    cpu,checker = [bound(value) for value in evidence]
    need(cpu['schema'] == 'model_v3_attention_candidate_full_CPU_Root_closure_v1'
        and cpu['status'] == 'ROOT_CLOSED_FULL114_CPU_C0_SOURCE_STABLE'
        and cpu['actual_job_id'] == summary['job_id'] and cpu['code_commit'] == LOCAL
        and cpu['summary'] == qa_inputs['summary_ref'] and cpu['supervisor'] == qa_inputs['supervisor_ref']
        and cpu['plan'] == qa_inputs['plan_ref'] and cpu['submission'] == qa_inputs['submission_ref']
        and cpu['counts'] == qa['actual_counts'] and cpu['test_file_count'] == 114
        and cpu['new_attention_tests'] == qa['actual_new_attention_file_counts']['tests']
        and cpu['new_attention_zero_skip_failure_error'] is True
        and qa['actual_new_attention_file_counts']['skipped'] == 0
        and cpu['old_three_skip_identities_unchanged'] is True
        and cpu['all_runtime_before_after_and_current_verified'] is True,
        'Actual Root CPU closure is not this summary/source scope')
    need(checker['schema'] == 'model_v3_attention_candidate_repository_checker_Root_closure_v1'
        and checker['status'] == 'ROOT_CLOSED_REPOSITORY_CHECKER_C0' and checker['code_commit'] == LOCAL
        and checker['source_manifest'] == source_freeze_ref,'Actual ordinary checker closure differs')
    for value in evidence:add(value)
    for key in ('sources_before','sources_after','source_inventory'):add(cpu[key])
    qa['Root_actual_CPU_closure'],qa['Root_actual_checker_closure'] = evidence
    need(CRITICAL <= {str(Path(x).relative_to(ROOT)) for x in sources if Path(x).is_relative_to(ROOT)},
         'Actual runtime source inventory misses critical implementation')
    request['source_refs'] = sorted(sources.values(),key=lambda x:x['path'])
    # Writing the actual QA binding and adding its rawref to candidate_QA_evidence
    # is deliberately a separate final freeze step, not a fabricated input here.
    request['candidate_QA_evidence'] = evidence
    return {'request':request,'actual_qa_binding':qa,'local_Git_observations':git_rows,
        'new_final_files_written':False,'reservation_or_job_submitted':False,
        'candidate_scientific_adoption':False}

def _write_new(path,value):
    raw = (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw) <= 2<<20,'Bounded final control document required')
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)

def finalize_from_inputs(inputs_ref):
    """Root-only explicit write step; the source author does NOT invoke this."""
    inputs = bound(inputs_ref)
    need(inputs['schema'] == 'model_v3_centered_final_binding_inputs_v1','Actual explicit binding input schema required')
    targets = [HERE/name for name in ('ACTUAL_CPU_QA_BINDING.json','execution_request_v1.json',
                                     'source_pins_v1.json','FINAL_BINDING_RESULT.json')]
    need(not any(path.exists() for path in targets),'Never overwrite an earlier final/partial binding')
    package = assemble(local_commit_proof_ref=inputs['local_commit_proof_ref'],
        source_freeze_ref=inputs['source_freeze_ref'],publication_receipt_ref=inputs['publication_receipt_ref'],
        qa_inputs=inputs['qa_inputs'])
    qa_ref = _write_new(targets[0],package['actual_qa_binding'])
    request = package['request']
    request['candidate_QA_evidence'].append(qa_ref)
    request['source_refs'].extend([qa_ref,inputs_ref])
    request['source_refs'] = sorted({x['path']:x for x in request['source_refs']}.values(),key=lambda x:x['path'])
    request_ref = _write_new(targets[1],request)
    names = list(SCIENCE_FILES)+['README.md','final_binding.py','FINAL_BINDING_INPUTS.md',
        'DRAFT_SOURCE_INVENTORY.json','execution_request_DRAFT.json','FINAL_BINDING_INPUTS_ACTUAL.json',
        'ACTUAL_CPU_QA_BINDING.json','execution_request_v1.json']
    files = [ref(HERE/name) for name in names]
    own = {x['path'] for x in files}
    protected = [x for x in request['source_refs'] if x['path'] not in own]
    for value in files+protected:need(ref(value['path']) == value,'Source changed before final freeze')
    pins = {'schema':'model_v3_centered_attention_complete48_GPU_launch_source_pins_v1',
        'status':'FINAL_SOURCE_BOUND_CANDIDATE_PUBLIC_CPU_VERIFIED_RUNNER_PREREGISTRATION_PENDING',
        'files':files,'protected_dependencies':protected,'execution_request':request_ref,
        'candidate_local_commit':LOCAL,'candidate_public_commit':request['public_commit'],'candidate_tree':TREE,
        'execution_branch':BRANCH,'reporting_tree_is_not_execution_runtime':True,
        'case_count':48,'scientific_encoder_forwards':192,'FP64_encoder_forwards':0,
        'candidate_count':1,'ordinary_numeric_mode':'compensated_fp32_v1',
        'attention_aggregation_mode':'centered_fp32_v1','whole_output_bytes':2147483648,
        'private_bytes':2147483648,'RSS_bytes':30064771072,'wall_seconds':1100,
        'scientific_GPU_executed':False,'candidate_adopted':False}
    pin_ref = _write_new(targets[2],pins)
    outcome = {'schema':'model_v3_centered_final_metadata_binding_result_v1',
        'status':'FINAL_METADATA_BOUND_PENDING_RUNNER_PREREGISTRATION_AND_GPU',
        'created_UTC':datetime.now(timezone.utc).isoformat(),'binding_source':ref(__file__),'inputs':inputs_ref,
        'execution_request':request_ref,'source_pins':pin_ref,'actual_QA_binding':qa_ref,
        'actual_QA_counts':package['actual_qa_binding']['actual_counts'],
        'actual_new_attention_file_counts':package['actual_qa_binding']['actual_new_attention_file_counts'],
        'local_Git_observations':package['local_Git_observations'],'public_files':10,'changed_API_files':8,
        'runtime_sources':len(request['source_refs']),'own_runtime_leaves':len(files),
        'candidate_publication_verified':True,'new_runner_protocol_publication_still_required':True,
        'scientific_GPU_executed':False,'reservation_or_job_submitted':False,'candidate_adopted':False}
    result_ref = _write_new(targets[3],outcome)
    return {'result':result_ref,'execution_request':request_ref,'source_pins':pin_ref,
            'status':outcome['status']}

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--write-final',action='store_true',required=True)
    args = parser.parse_args()
    raw_inputs = ref(args.inputs)
    need(raw_inputs['sha256'] == args.inputs_sha256,'Actual final-binding input SHA differs')
    print(json.dumps(finalize_from_inputs(raw_inputs),sort_keys=True))
