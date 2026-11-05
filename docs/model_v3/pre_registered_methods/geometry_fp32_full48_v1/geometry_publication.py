"""Exact actual candidate/full/method evidence; stdlib metadata only."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_geometry_fp32_candidate_v1')
HERE=Path(__file__).absolute().parent
BRANCH='model-v3-geometry-fp32-candidate-20261028-v1'
LOCAL='03e26bea6a29ef96ba5611760763329207212741'
PUBLIC='498ecbe7e88b1468067dde5692c10735fcadf2ea'
TREE='2d3b8f17e06d73bc2bc47745ccde982625646dd0'
METHOD_PREFIX='docs/model_v3/pre_registered_methods/geometry_fp32_full48_v1/'
PUBLIC_PATHS=frozenset((
 'current/phychem_mfm/model/v3_geometry_fp32.py',
 'current/phychem_mfm/model/attention.py','current/phychem_mfm/model/backbone.py',
 'current/phychem_mfm/model/shared.py','current/phychem_mfm/model/v3_architecture.py',
 'current/tests/test_model_v3_geometry_fp32.py',
 'docs/model_v3/GEOMETRY_FP32_RESIDUAL_V1.md'))
SCIENCE_NAMES=frozenset(('geometry_adapter.py','run_geometry_matrix.py',
 'test_geometry_matrix.py','tiny_geometry_controls.py',
 'launch_geometry_matrix_GPU_v1.py','run_geometry_matrix_GPU_v1.sbatch'))
METADATA_NAMES=frozenset(('geometry_publication.py','final_binding.py'))

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
         and full['test_file_count']==116 and full['passed']==2816
         and full['counts']==dict(tests=2819,failures=0,errors=0,skipped=3)
         and full['all_runtime_before_after_and_current_verified'] is True
         and full['full_pass_is_not_scientific_adoption_or_D_final_or_recipe_acceptance'] is True,
         'Actual same-code full116 Root certificate required; partial or old-code QA is insufficient')
    job=full['job_id']
    need(type(job) is str and job=='4524576' and full['node']=='compute-0-14',
         'Actual full CPU4576 job/node differs')
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
    need(type(tests) is dict and len(tests)==summary['test_file_count']==116
         and summary['test_source_sha256']==tests,'Full actual test membership differs')
    actual_tests={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (ROOT/'current/tests').glob('test_*.py')}
    need(actual_tests==tests,'Actual complete116 test files differ from full QA')
    files=[name for row in summary['shards'] for name in row['files']]
    need(len(files)==len(set(files))==116 and set(files)==set(tests),
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
    need(total==summary['counts']==full['counts'],'Actual full116 counts differ')
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
            'test_files':116,'counts':total,'optional_CPU_skips':full['actual_skips'],
            'skip_scope':'CPU optional skips do not authorize CUDA or actual native/D3 data',
            'current_runtime_sha256':full['current_runtime_sha256'],
            'scope':'ACTUAL_FULL_CPU_NOT_PHYSICS_ACCEPTANCE'}

def publication(value, *, branch):
    p=bound(value)
    need(p['schema']=='model_v3_exact_tree_publication_actual_v1'
         and p['repository' if branch==BRANCH else 'repository_full_name']=='mint258/MFM' and p['branch']==branch
         and p['public_branch_readback_verified'] is True
         and p['public_Git_API_tree_readback_verified'] is True
         and p['scientific_adoption'] is False and p['GPU_acceptance'] is False,
         'Actual Root exact-tree/double-readback receipt required, never science acceptance')
    for key in ('local_code_sha','public_code_sha','tree_sha'):
        need(type(p[key]) is str and re.fullmatch('[0-9a-f]{40}',p[key]),
             'Complete actual Git identity required')
    need(type(p['files']) is list and len(p['files'])==len({x['path'] for x in p['files']}),
         'Unique actual published file map required')
    return p

def checker(value):
    c=bound(value)
    need(c['schema']=='model_v3_Root_reporting_precommit_checker_closure_v1'
         and type(c['source_count']) is int and c['source_count']>0
         and c['status']=='ACTUAL_C0_ALL_%d_RAW_SOURCES_AND_CHECKER_CLOSED'%c['source_count']
         and c['all_sources_before_and_current_equal'] is True
         and c['checker']['status']=='PASS' and c['checker']['errors']==[]
         and c['checker']['files']==c['source_count'],
         'Actual reporting source/checker C0 closure required')
    parent(c['actual_sacct'],c['job_id'])
    need(reference(c['source_freeze']['path'],maximum=16<<20)==c['source_freeze'],'Checker freeze differs')
    need(reference(c['checker_log']['path'])==c['checker_log'],'Actual checker log differs')
    sup=bound(c['supervisor'])
    need(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['job_id']==c['job_id']
         and sup['first_failure'] is None and sup['remaining']==[]
         and sup['gpu_initialization_permitted'] is False
         and sup['private_storage']['first_sampling_failure'] is None,
         'Actual CPU checker supervisor/private cleanup differs')
    return {'job_id':c['job_id'],'source_count':c['source_count'],'checker_closure':value,
            'science_or_GPU_authority':False}

def verify_metadata_evidence(request):
    need(request['repository']==str(ROOT) and request['execution_branch']==BRANCH
         and request['local_commit']==LOCAL and request['public_commit']==PUBLIC
         and request['exact_shared_tree']==TREE
         and request['mode']=='compensated_fp32_v1'
         and request['attention_aggregation_mode']=='centered_fp32_v1'
         and request['attention_projection_mode']=='blocked_k64_compensated_fp32_v1'
         and request['geometry_mode']=='residual_expansion_fp32_v1'
         and request['all_FP32_residual_geometry_candidate'] is True
         and request['scientific_acceptance'] is False,
         'Only the fixed published all-FP32 residual geometry candidate may execute')
    p=publication(request['publication_receipt'],branch=BRANCH)
    need(p['worktree']==str(ROOT) and p['local_code_sha']==LOCAL
         and p['public_code_sha']==PUBLIC and p['tree_sha']==TREE
         and p['full_CPU_closure']==request['full_cpu_root_closure']
         and p['files']==request['public_files']
         and {x['path'] for x in p['files']}==PUBLIC_PATHS and len(p['files'])==7,
         'Actual candidate source/full/publication mapping differs')
    full=full_cpu_gate(request)
    freeze=bound(request['candidate_source_freeze'])
    authored={x['relative_path']:x for x in freeze['files']}
    need(freeze['schema']=='model_v3_geometry_fp32_candidate_source_freeze_v1'
         and freeze['worktree']==str(ROOT) and freeze['authored_count']==7
         and set(authored)==PUBLIC_PATHS,'Original seven authored source freeze differs')
    refs={x['path']:x for x in request['source_refs']}
    rows=[]
    for leaf in p['files']:
        path=ROOT/leaf['path'];current=reference(path);saved=authored[leaf['path']]
        need(refs.get(str(path))==current and current['bytes']==saved['bytes']
             and current['sha256']==saved['sha256'] and leaf['type']=='blob'
             and leaf['mode'] in ('100644','100755') and git_blob(path.read_bytes())==leaf['sha'],
             'Current candidate source is not exact tested/published raw bytes')
        rows.append({'scope':'CANDIDATE_SOURCE_AND_CPU_NOT_SCIENCE','path':leaf['path'],
                     'working':current,'Git_blob_sha':leaf['sha'],'full_CPU':full})
    method=publication(request['method_publication'],branch='model-v3')
    need(method['public_code_sha']==request['method_public_commit'] and method['tree_sha']==request['method_public_tree']
         and method['method_sources']==request['method_publication_exact_files'],
         'Exact immutable nine-leaf GPU method publication differs')
    sources=method['method_sources']
    need(len(sources)==9 and {Path(x['runtime_path']).name for x in sources}==SCIENCE_NAMES|METADATA_NAMES|{'METHOD.md'}
         and len({x['runtime_path'] for x in sources})==9,
         'All six exact science leaves, two metadata leaves and METHOD are required')
    published={x['path']:x for x in method['files']}
    need({METHOD_PREFIX+name for name in SCIENCE_NAMES|METADATA_NAMES|{'METHOD.md'}}<=set(published),
         'Actual method published paths differ')
    for source in sources:
        runtime=HERE/Path(source['runtime_path']).name
        target=METHOD_PREFIX+runtime.name;current=reference(runtime)
        need(source['runtime_path']==str(runtime) and source['repository_relative_path']==target
             and current==dict(path=str(runtime),bytes=source['bytes'],sha256=source['sha256'])
             and refs.get(str(runtime))==current and published[target]['type']=='blob'
             and git_blob(runtime.read_bytes())==source['git_blob_sha']==published[target]['sha'],
             'Actual runtime method/raw SHA/Git blob projection differs')
        rows.append({'scope':'PUBLISHED_GPU_METHOD_NOT_A_MEASUREMENT','runtime':current,
                     'repository_relative_path':target,'Git_blob_sha':source['git_blob_sha']})
    checker(method['checker_closure'])
    return rows

def metadata_publication_gate(request):
    """New metadata code must itself be archived/read back; no hash self-reference."""
    need(request['metadata_publication']==request['method_publication'],
         'One actual immutable nine-leaf method/metadata publication required')
    p=publication(request['metadata_publication'],branch='model-v3')
    need(p['public_code_sha']==request['metadata_public_commit']
         and p['tree_sha']==request['metadata_public_tree'],
         'Actual metadata publication Git identity differs')
    inventory=bound(request['metadata_inventory'])
    files=inventory['files']
    need(inventory['schema']=='model_v3_geometry_FP32_GPU_metadata_source_inventory_v1'
         and len(files)==2 and {Path(x['path']).name for x in files}==METADATA_NAMES,
         'Exactly frozen verifier and generator sources required')
    published={x['path']:x for x in p['files']}
    required={METHOD_PREFIX+name for name in METADATA_NAMES}
    need(required<=set(published),
         'Metadata receipt must include both exact registered metadata paths')
    refs={x['path']:x for x in request['source_refs']}
    rows=[]
    for expected in files:
        path=HERE/Path(expected['path']).name;current=reference(path)
        item=published[METHOD_PREFIX+path.name]
        need(str(path)==expected['path'] and current==expected
             and refs.get(str(path))==current and item['type']=='blob'
             and git_blob(path.read_bytes())==item['sha'],
             'Metadata runtime source differs from frozen/current/public bytes')
        rows.append({'scope':'PUBLISHED_METADATA_NOT_SCIENCE','runtime':current,
                     'repository_relative_path':item['path'],'Git_blob_sha':item['sha']})
    checker(p['checker_closure'])
    return rows

def verify_publication(request):
    need(request['status']=='FINAL_BOUND_PUBLIC_GEOMETRY_FP32_REQUEST',
         'DRAFT source binding is not GPU admission')
    return verify_metadata_evidence(request)+metadata_publication_gate(request)
