"""Fixed actual diagnostic publication/QA metadata; no network or model import."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_attention_core64_diagnostic_v1')
BRANCH='model-v3-attention-core64-diagnostic-20261027-v1'
LOCAL='0f1cfb725dfe97a183ab5173fc5e4d0347228e41'
PUBLIC='b88f07d1628e53d7f78e1232397fab0568ffd823'
TREE='b94944d57a3751ccde9d89bbf4a8a747c1d69539'
PUBLIC_PATHS=frozenset((
 'current/phychem_mfm/model/v3_attention_numerics.py',
 'current/phychem_mfm/model/attention.py','current/phychem_mfm/model/backbone.py',
 'current/phychem_mfm/model/shared.py','current/phychem_mfm/model/v3_architecture.py',
 'current/tests/test_model_v3_attention_core64_diagnostic.py',
 'docs/model_v3/ATTENTION_CORE64_DIAGNOSTIC_V1.md'))


def need(ok,message):
    if not ok:raise ValueError(message)


def reference(path,maximum=2<<20):
    path=Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=maximum,
         'Bounded ordinary source/metadata required')
    raw=path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def bound(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'},
         'Actual rawref required; a pending full-CPU value is not admission')
    need(reference(value['path'])==value,'Raw publication/QA metadata differs')
    return json.loads(Path(value['path']).read_bytes())


def git_blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest()


def parent(raw,job):
    need(raw['returncode']==0 and type(raw['returncode']) is int and raw['stderr']==''
         and raw['argv']==['sacct','-X','-n','-P','-j',job,
          '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],
         'Actual raw parent accounting command differs')
    rows=[line.split('|') for line in raw['stdout'].splitlines() if line.strip()]
    need(len(rows)==1 and len(rows[0])==7 and rows[0][0]==job
         and rows[0][1:4]==['zixiao','COMPLETED','0:0'] and rows[0][4].isdigit()
         and int(rows[0][4])>0 and rows[0][5]=='16'
         and rows[0][6] in ['compute-0-'+str(i) for i in (2,*range(8,20))],
         'Actual owned CPU16 terminal C0 required')


def full_cpu_gate(request):
    full=bound(request['full_cpu_root_closure'])
    need(full['schema']=='model_v3_candidate_single_parent_full_Root_closure_v1'
         and full['status']=='ACTUAL_C0_FULL_CORE_SUITE_SOURCE_AND_V2_OPERATIONAL_CLOSED'
         and full['code_commit']==LOCAL and full['tree']==str(ROOT)
         and full['test_file_count']==115 and full['passed']==2745
         and full['counts']==dict(tests=2748,failures=0,errors=0,skipped=3)
         and full['all_runtime_before_after_and_current_verified'] is True
         and full['full_pass_is_not_scientific_adoption_or_D_final_or_recipe_acceptance'] is True,
         'Actual same-code full115 Root certificate required; related156 is insufficient')
    job=full['job_id']
    need(type(job) is str and job=='4524207' and full['node']=='compute-0-12',
         'Actual full CPU4207 job/node differs')
    parent(full['actual_sacct'],job)
    summary=bound(full['summary'])
    need(summary['status']=='PASS' and summary['failure'] is None
         and summary['job_id']==job and summary['code_commit']==LOCAL
         and summary['workers']==4 and len(summary['shards'])==4
         and summary['sources_before']==summary['sources_after'],
         'Actual mature same-code full-runtime summary differs')
    before,after=bound(full['source_before']),bound(full['source_after'])
    need(before==after==summary['sources_before']==summary['sources_after']
         and before['runtime_sha256']==full['current_runtime_sha256'],
         'Actual full source snapshots/current runtime fingerprint differ')
    refs={r['path']:r for r in request['source_refs']}
    for name,sha in before['runtime']['project_source_sha256'].items():
        need(refs.get(str(ROOT/name),{}).get('sha256')==sha,
             'GPU bound code does not cover the actual complete full-CPU project scope')
    for external in before['runtime']['external_source_refs'].values():
        need(refs.get(external['path'],{}).get('sha256')==external['sha256'],
             'GPU bound code does not cover actual full-CPU external interpretation sources')
    tests=summary['all_test_file_sha256']
    need(type(tests) is dict and len(tests)==summary['test_file_count']==115
         and summary['test_source_sha256']==tests,'Full actual test membership differs')
    actual_tests={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (ROOT/'current/tests').glob('test_*.py')}
    need(actual_tests==tests,'Actual complete115 test files differ from full QA')
    files=[name for row in summary['shards'] for name in row['files']]
    need(len(files)==len(set(files))==115 and set(files)==set(tests),
         'Full shards not exhaustive/disjoint')
    total=dict(tests=0,failures=0,errors=0,skipped=0)
    skipped=[]
    need(len(full['XML'])==4,'Exactly four actual JUnit refs required')
    for index,(ref,shard) in enumerate(zip(full['XML'],summary['shards'])):
        need(reference(ref['path'],maximum=16<<20)==ref,'Actual full JUnit rawref differs')
        document=ET.fromstring(Path(ref['path']).read_bytes())
        counts={key:sum(int(s.get(key,'0')) for s in document.iter('testsuite')) for key in total}
        need(shard['shard']==index and shard['returncode']==0 and counts==shard['counts'],
             'Actual full JUnit/shard differs')
        for case in document.iter('testcase'):
            element=case.find('skipped')
            if element is not None:
                skipped.append((case.get('classname'),case.get('name'),element.get('message','')))
        for key in total:total[key]+=counts[key]
    need(total==summary['counts']==full['counts'],'Actual full115 counts differ')
    declared=[(r['classname'],r['name'],r['message']) for r in full['actual_skips']]
    allowed={('tests.test_model_v3_native_s_source_interop',
              'test_actual_native_TRAIN_and_fixed_PRETRAIN_VAL_reader_bridge_and_close'),
             ('tests.test_model_v3_transfer','test_custom_batch_pin_protocol_and_nonblocking_cuda_transfer'),
             ('tests.test_model_v3_native_bond_transport','test_pinned_bond_arrays_and_nonblocking_cuda_transfer')}
    need(len(skipped)==len(declared)==3 and sorted(skipped)==sorted(declared)
         and {(a,b) for a,b,_ in skipped}==allowed,
         'The actual three optional CPU skip identities differ')
    supervisor=bound(full['supervisor'])
    need(supervisor['status']=='COMPLETED' and supervisor['exit_code']==0
         and supervisor['job_id']==job and supervisor['first_failure'] is None
         and supervisor['remaining']==[] and supervisor['gpu_initialization_permitted'] is False
         and supervisor['private_storage']['first_sampling_failure'] is None,
         'Actual full CPU supervision/private closure differs')
    receipts=full['actual_four_exec_receipts']
    need(set(receipts)=={'pytest_shard_%02d'%i for i in range(4)},
         'Four real pytest exec receipt roles required')
    for ref in receipts.values():bound(ref)
    return {'job_id':job,'root_closure':request['full_cpu_root_closure'],
            'test_files':115,'counts':total,'optional_CPU_skips':full['actual_skips'],
            'skip_scope':'CPU optional skips do not authorize CUDA or actual native/D3 data',
            'current_runtime_sha256':full['current_runtime_sha256'],
            'scope':'ACTUAL_FULL_CPU_NOT_PHYSICS_ACCEPTANCE'}

def verify_metadata_evidence(request):
    need(request['repository']==str(ROOT) and request['execution_branch']==BRANCH
         and request['local_commit']==LOCAL and request['public_commit']==PUBLIC
         and request['exact_shared_tree']==TREE and request['mixed_precision_diagnostic_only'] is True
         and request['formal_FP32_gate_satisfied'] is False and request['model_freeze_candidate'] is False,
         'Only fixed mixed-core diagnostic source may execute; never a formal FP32/freeze gate')
    publication=bound(request['publication_receipt'])
    need(publication['schema']=='model_v3_Root_exact_tree_publication_receipt_v1'
         and publication['status']=='PUBLISHED_EXACT_LOCAL_TREE_SEVEN_CPU_RELATED_TESTED_DIAGNOSTIC_SOURCES_READ_BACK'
         and publication['branch']==BRANCH and publication['public_commit_sha']==PUBLIC
         and publication['local_code_sha']==LOCAL and publication['tree_sha']==publication['actual_public_git_tree']==TREE
         and publication['actual_readback'][BRANCH]==PUBLIC
         and publication['formal_FP32_gate'] is False and publication['model_freeze_candidate'] is False,
         'Actual diagnostic same-tree readback differs')
    need(publication['Root_CPU_closure']==request['related_cpu_root_closure'],
         'Publication related-CPU raw chain differs')
    related=bound(request['related_cpu_root_closure'])
    need(related['schema']=='model_v3_attention_core64_related_CPU_Root_closure_v1'
         and related['status']=='ACTUAL_C0_156_RELATED_TESTS_THREE_GROUPS_AND_REPOSITORY_CHECKER'
         and related['counts']==dict(tests=156,passed=156,failures=0,errors=0,skipped=0)
         and related['all_sources_before_after_and_current_equal'] is True
         and related['current_source_count']==2136
         and related['source_freeze']==request['candidate_source_freeze'],
         'Actual related156 source/QA evidence differs')
    parent(related['actual_parent'],related['job_id'])
    full=full_cpu_gate(request)
    leaves=publication['source_files']
    need(leaves==request['public_files'] and {x['path'] for x in leaves}==PUBLIC_PATHS
         and len(leaves)==7,'All seven published diagnostic leaves required')
    source_refs={r['path']:r for r in request['source_refs']}
    rows=[]
    for item in leaves:
        path=ROOT/item['path'];raw=path.read_bytes();actual=reference(path)
        need(source_refs.get(str(path))==actual and actual['bytes']==item['bytes']
             and actual['sha256']==item['sha256'] and git_blob(raw)==item['blob_sha'],
             'Current runtime leaf differs from tested/public diagnostic blob')
        rows.append({'path':item['path'],'working':actual,'Git_blob_sha':item['blob_sha'],
                     'Git_projection':'exact_raw','full_CPU':full})
    return rows


def verify_publication(request):
    need(request['status']=='FINAL_BOUND_PUBLIC_CORE64_DIAGNOSTIC_REQUEST',
         'DRAFT metadata/source binding is not GPU admission')
    return verify_metadata_evidence(request)
