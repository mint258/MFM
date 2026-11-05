"""Six fixed routing7 cohorts: source/actual metadata gates, no model/SDK reads."""
from __future__ import annotations
from copy import deepcopy
import hashlib,importlib.util,json,math,os,re,stat
from pathlib import Path
B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1';HERE=Path(__file__).absolute().parent
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50';PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
TREE='8f9530415034bdb885c1c765aee434797c70e7c7';LIMIT=2<<30
PREFIX='docs/model_v3/pre_registered_methods/performance_remaining_Av2_R1_ABBA_v3/'
FILES={'Root_submit.py','admission.py','run_R1_ABBA.sbatch','PLAN.json','METHODS.md','dependencies.json','source_pins.json'}
ROLES=('reference','candidate','candidate','reference');META=2<<20

def need(ok,message):
    if not ok:raise ValueError(message)
def exact(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b
def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def digest(value): return hashlib.sha256(encoded(value)).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def reference(path,maximum=META):
    p=Path(path).absolute();a=p.lstat()
    need(p.resolve()==p and p.is_relative_to(B) and stat.S_ISREG(a.st_mode) and a.st_uid==1278 and a.st_nlink==1
        and 0<a.st_size<=maximum,'Owned canonical bounded source/metadata required: '+str(p))
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    z=p.lstat();need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns),'File changed while hashing')
    return dict(path=str(p),bytes=a.st_size,sha256=h.hexdigest())
def read(path,maximum=META):
    ref=reference(path,maximum)
    value=json.loads(Path(path).read_bytes(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(reference(path,maximum)==ref,'JSON changed during parse');return value
def bound(ref,parse=True,maximum=META):
    need(type(ref) is dict and set(ref)=={'path','bytes','sha256'} and type(ref['bytes']) is int
        and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256'])
        and exact(reference(ref['path'],maximum),ref),'Exact rawref changed')
    return read(ref['path'],maximum) if parse else ref

def load(ref,name):
    bound(ref,False);spec=importlib.util.spec_from_file_location(name,ref['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def verify_package(expected):
    pin=reference(HERE/'source_pins.json');need(pin['sha256']==expected,'Explicit frozen source pins SHA required')
    p=read(pin['path']);need(p['schema']=='model_v3_remaining_Av2_R1_sources_v1' and p['source_revision']==3
        and {Path(x['path']).name for x in p['files']}==FILES-{'source_pins.json'} and len(p['files'])==6,'Exact seven source leaves required')
    for row in p['files']:need(Path(row['path']).parent==HERE,'Own source path differs');bound(row,False)
    for row in read(HERE/'dependencies.json')['raw_refs'].values():bound(row,False)
    return pin

def policy():
    deps=read(HERE/'dependencies.json')['raw_refs'];m=load(deps['GPU_auto_policy'],'remaining_R1_shared_memory')
    m.verify_package(deps['GPU_auto_policy_pins']['sha256']);return m

def verify_method(ref):
    value=bound(ref);need(value['schema']=='model_v3_exact_tree_publication_actual_v1'
        and value['repository_full_name']=='mint258/MFM' and value['branch']=='model-v3'
        and value['public_branch_readback_verified'] is True and value['public_Git_API_tree_readback_verified'] is True,'Actual new exact-tree publication required')
    rows={x['path']:x for x in value['files']};need(len(rows)==len(value['files']),'Duplicate publication path')
    for name in FILES:
        raw=(HERE/name).read_bytes();row=rows[PREFIX+name]
        need(row['type']=='blob' and row['sha']==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'Own public method blob differs')
    deps=read(HERE/'dependencies.json')['raw_refs'];audit_pins=bound(deps['routing_audit_pins'])
    prefix=read(HERE/'PLAN.json')['routing_audit_publication_prefix']
    for item in [*audit_pins['files'],deps['routing_audit_pins']]:
        raw=Path(item['path']).read_bytes();row=rows[prefix+Path(item['path']).name]
        need(row['type']=='blob' and row['sha']==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
            'Exact published source-only v3 metadata auditor blob required')
    policy().verify_publication(ref)
    return value

def routing(cohort):
    template=read(HERE/'PLAN.json');deps=read(HERE/'dependencies.json')['raw_refs']
    need(cohort in template['cohorts'],'Only the exact six routing7 selectors')
    plan=bound(deps['routing_plan']);need(plan['routing_version']==7 and plan['source_directory']==str(N/'performance_remaining_Av2_20261029_routing_v7')
        and plan['current_source']==dict(local_commit=CODE,public_commit=PUBLIC,tree=TREE,worktree=str(W)),'Original routing7/current source differs')
    rows=[x for x in plan['cases'] if x['old_job_id']==cohort];need(len(rows)==1,'One exact original cohort required');case=rows[0]
    declared=template['cohorts'][cohort]
    need(case['expected_node']==declared['node'] and case['gpu_uuid']==declared['gpu_uuid'] and case['expected_gpu']==declared['gpu_type']
        and case['performance_execution_request'] is None,'Frozen cohort card or unintegrated scope differs')
    old=bound(case['original_configuration'])
    auditor=load(deps['routing_audit_entry'],'remaining_R1_original_v3_model_projection')
    need(auditor.planned_model_equal(old['model'],case['model']),
        'Only source-bound v3 four declared finite float model representations may differ in PLAN')
    for left,right in (('candidate','candidate'),('reference','reference_options'),('data_version','original_data_version')):
        need(exact(old[left],case[right]),'Original cohort exact integer/value identity differs: '+left)
    need(exact(bound(case['candidate_options']),case['candidate']),'Original candidate option bytes differ')
    guard=load(deps['current_source_guard'],'remaining_R1_original_full_source_guard');guard.validate_sources()
    return case,plan,declared

def parents(raw,expected):
    need(raw['returncode']==0 and raw['stderr']=='','Actual successful seven-column sacct required')
    need(raw['argv'][0]=='sacct' and '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList' in raw['argv'],'Explicit parent columns required')
    rows=[x.split('|') for x in raw['stdout'].splitlines() if x.strip()]
    need(len(rows)==len(expected) and {x[0] for x in rows}==set(expected),'Exact parent population differs')
    for row in rows:
        need(len(row)==7 and row[1:4]==['zixiao','COMPLETED','0:0'] and row[4].isdigit() and int(row[4])>0
            and row[5]=='16' and row[6]==expected[row[0]],'Owned C0/16CPU/node/positive elapsed required')
    return rows

def cpu_supervisor(ref,*,job,entry):
    s=bound(ref);need(str(s['job_id'])==job and s['status']=='COMPLETED' and s['exit_code']==0 and s['first_failure'] is None
        and s['remaining']==[] and s['gpu_initialization_permitted'] is False
        and s['private_storage']['first_sampling_failure'] is None and s['private_storage']['budget_bytes']==LIMIT,'Actual CPU supervisor/private closure required')
    need(s['command'].count(str(entry))==1,'CPU must actually invoke the frozen audit entry')
    deps=read(HERE/'dependencies.json')['raw_refs']
    expected={deps[key]['path']:deps[key]['sha256'] for key in ('cpu_supervisor','cpu_runtime_monitor','cpu_identity_supervisor','cpu_private_runtime_storage')}
    need(s['sources_sha256']==expected,'Original four-source CPU supervision map required')
    for path,sha in expected.items():need(reference(path)['sha256']==sha,'Original CPU supervision source changed')
    return s

def contains_ref(value,ref):
    if isinstance(value,dict):
        if all(key in value for key in ('path','bytes','sha256')) and exact({key:value[key] for key in ('path','bytes','sha256')},ref):return True
        return any(contains_ref(item,ref) for item in value.values())
    if isinstance(value,list):return any(contains_ref(item,ref) for item in value)
    return False
def qualify(cohort,input_ref):
    case,plan,declared=routing(cohort);q=bound(input_ref)
    need(set(q)=={'schema','cohort','metadata_audit_result','metadata_audit_supervisor','metadata_audit_parent_sacct',
        'Root_numeric_closure','SDK_closure','SDK_verifications','SDK_sync_results','SDK_CPU_supervisors','SDK_parent_sacct'}
        and q['schema']=='model_v3_remaining_Av2_R1_qualification_inputs_v1' and q['cohort']==cohort,
        'Exact explicit same-cohort metadata request required')
    # Root's explicit positive document contract is a required future input,
    # never an author-generated proof. The original producers remain decisive.
    Root_numeric=bound(q['Root_numeric_closure']);Root_SDK=bound(q['SDK_closure'])
    need(contains_ref(Root_numeric,q['metadata_audit_result']),'Root numeric closure must actually bind this CPU audit result')
    audit=bound(q['metadata_audit_result']);deps=read(HERE/'dependencies.json')['raw_refs']
    need(audit['schema']=='model_v3_remaining_routing7_closed_metadata_audit_v1'
        and audit['status']=='ALL_SELECTED_ROUTING7_FULL20_AND500_METADATA_VERIFIED_PENDING_ROOT_CPU_C0'
        and audit['failure'] is None and exact(audit['source_package'],deps['routing_audit_pins'])
        and exact(audit['plan'],deps['routing_plan']),'Actual frozen aa4b72df v3 routing7 audit result required')
    checks=audit['inline_metadata_selfchecks']
    need(checks['scope']=='PURE_METADATA_ONLY_NO_TENSORS_OR_SCIENTIFIC_REEXECUTION'
        and type(checks['count']) is int and checks['count']==15 and len(checks['checks'])==15
        and len(set(checks['checks']))==15,'Actual original v3 fifteen metadata selfchecks must be recorded')
    matches=[x for x in audit['cases'] if x['old_job_id']==cohort];need(len(matches)==1,'Selected cohort absent/duplicate in actual CPU audit');row=matches[0]
    job=row['job_id'];allocation=audit['allocation'];cpu_job=allocation['job_id'];cpu_node=allocation['node']
    need(row['node']==case['expected_node'] and row['gpu_uuid']==case['gpu_uuid'] and row['trajectory_updates']==500
        and row['fixed20']['passed'] is True and row['original_data_version_exact_integer_identity'] is True
        and row['SDK_audit_or_online_sync_accepted'] is False,'CPU full20/500 actual cohort/card scope differs')
    need(re.fullmatch(r'compute-0-(?:[2-9]|1[0-9])',cpu_node) and allocation['uid']==1278,'Actual CPU audit node/UID differs')
    sup=cpu_supervisor(q['metadata_audit_supervisor'],job=cpu_job,entry=Path(deps['routing_audit_entry']['path']))
    cmd=sup['command'];need('--old-job-id' in cmd and cohort in cmd and '--source-pins-sha256' in cmd
        and cmd[cmd.index('--source-pins-sha256')+1]==deps['routing_audit_pins']['sha256']
        and '--output-root' in cmd and Path(cmd[cmd.index('--output-root')+1])==Path(q['metadata_audit_result']['path']).parent,'Actual CPU command/input/result relation differs')
    parents(bound(q['metadata_audit_parent_sacct']),{cpu_job:cpu_node})
    metadata=row['closed_metadata']
    for name,ref in metadata.items():bound(ref,False,maximum=(16<<20 if name=='fixed_batch_gate' else META))
    cfg=bound(metadata['configuration']);summary=bound(metadata['summary']);status=bound(metadata['run_status'])
    need(cfg['job_id']==job and cfg['gpu_uuid']==case['gpu_uuid'] and cfg['node'].split('.')[0]==case['expected_node']
        and cfg['code_sha']==CODE and cfg['prereg_sha']==PUBLIC and cfg['acceptance_scope']=='V2_FULL20_AND500'
        and cfg['fixed_batches']==20 and cfg['trajectory_updates']==500 and cfg['smoke'] is False,'Current full20/500 actual configuration differs')
    need('performance_execution' not in cfg and 'performance_execution_request' not in cfg,'Six cohorts must retain original unintegrated execution')
    old_model=bound(case['original_configuration'])['model']
    need(exact(cfg['model'],old_model),'Actual new numeric model must remain TYPE-EXACT to original model, not PLAN projection')
    for left,right in (('candidate','candidate'),('reference','reference_options'),('data_version','original_data_version')):
        need(exact(cfg[left],case[right]),'Current numeric/original cohort exact identity differs: '+left)
    need(cfg['seed']==0 and cfg['input']=='native_s' and cfg['candidate_options_sha256']==case['candidate_options']['sha256']
        and cfg['configuration_sha256']==summary['configuration_sha256']==canonical({k:v for k,v in cfg.items() if k!='configuration_sha256'})
        and summary['full_A_numeric_acceptance'] is True and summary['status']==status['status']=='PAIRED_GATES_PASS'
        and status['failure'] is None and status['cleanup_errors']==[],'Actual current complete numeric configuration/finish differs')
    need(row['current_runtime_source_count']==len(cfg['source_sha256']),'Actual CPU/current runtime source population differs')
    for path,sha in cfg['source_sha256'].items():
        rel=Path(path);need(not rel.is_absolute() and '..' not in rel.parts and rel.suffix=='.py'
            and reference(W/rel)['sha256']==sha,'Actual saved current runtime source differs')
    need(Root_numeric['schema']=='model_v3_routing7_current_full_A_v2_Root_closure_v1'
        and Root_numeric['status']=='CURRENT_SOURCE_FULL20_AND500_V2_PASS_ROOT_CLOSED'
        and Root_numeric['failure'] is None and Root_numeric['full_A_numeric_acceptance'] is True
        and Root_numeric['job_id']==job and Root_numeric['old_job_id']==cohort and Root_numeric['actual_code_sha']==CODE
        and Root_numeric['configuration_sha256']==cfg['configuration_sha256']
        and exact(Root_numeric['metadata_CPU_result'],q['metadata_audit_result'])
        and exact(Root_numeric['metadata_CPU_supervisor'],q['metadata_audit_supervisor'])
        and exact(Root_numeric['fixed'],row['fixed20']) and Root_numeric['trajectory_updates']==500
        and type(Root_numeric['maximum_loss_difference']) in (int,float)
        and math.isfinite(Root_numeric['maximum_loss_difference']) and 0<=Root_numeric['maximum_loss_difference']<=1e-3
        and Root_numeric['maximum_loss_difference']==row['maximum_trajectory_relative_difference'],
        'Actual positive same-cohort Root full20/500 numeric/resource closure required; negative/pending is HOLD')
    need(all(any(exact(ref,saved) for saved in Root_numeric['closed_metadata']) for ref in metadata.values()),
        'Root numeric closure must include every original CPU-verified metadata rawref')
    for ref in Root_numeric['closed_metadata']:
        cap=16<<20 if ref['path']==metadata['fixed_batch_gate']['path'] else META
        bound(ref,False,maximum=cap)
    raw=Root_numeric['actual_sacct'];need(raw['returncode']==0 and raw['stderr']=='','Actual Root numeric parent capture required')
    matching=[x.split('|') for x in raw['stdout'].splitlines() if x.split('|')[0]==job]
    need(len(matching)==1 and len(matching[0])==7 and matching[0][1:4]==['zixiao','COMPLETED','0:0']
        and matching[0][4].isdigit() and int(matching[0][4])>0 and matching[0][5:] == ['16',case['expected_node']],
        'Actual Root-owned positive elapsed same-card GPU C0 required')
    roles={};expected_parents={job:case['expected_node'],cpu_job:cpu_node};cert_refs=q['SDK_verifications'];sync_refs=q['SDK_sync_results']
    need(len(cert_refs)==len(sync_refs)==len(q['SDK_CPU_supervisors'])==2,'Exactly two paired certificates/readbacks and CPU parents required')
    for ref in cert_refs:
        v=bound(ref);h=v['history'];rid=v['run_id'];role=v['paired_role']
        need(v['schema']=='performance_R2_paired_log_verification_v1' and v['status']=='ALL_SAVED_PAIRED_LOG_FIELDS_MATCHED'
            and v['model_job_id']==job and role in ('reference','candidate') and rid not in roles
            and exact(v['history_reader_source'],deps['SDK_literal749']) and exact(v['tap_source'],deps['SDK_tap2'])
            and v['full_config_summary_typed_exact'] is True and v['raw_before_after_binding_closed'] is True
            and v['expected_config_sha256']==digest({**cfg,'paired_role':role})
            and v['native_RunRecord']['run_id']==rid and v['native_RunRecord']['project']=='mfm_model_v3_development'
            and v['native_RunRecord']['display_name']=='A_'+role+'_'+job
            and h['schema']=='model_v3_native_mirror_verification_v7' and h['status']=='VERIFIED_COMMITTED_HISTORY'
            and h['history_rows']==500 and h['first_explicit_step']==1 and h['last_explicit_step']==500
            and h['clean_eof'] is h['native_closed'] is True and h['decode_error'] is None
            and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
            and h['sdk_exit_codes']==[0] and h['sdk_run_ids']==[rid],'Actual500 full-typed-config/summary/history/CRC+EOF/exit0 proof differs')
        roles[rid]=role
    need(sorted(roles.values())==['candidate','reference'],'One independently decoded role each required')
    synced=set()
    for ref in sync_refs:
        v=bound(ref);r=v['actual_remote_metadata'];rid=v['run_id']
        need(v['schema']=='model_v3_one_WandB_sync_readback_v1' and v['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED'
            and v['failure'] is None and v['native_exit_code']==0 and v['source_hash_before_after_equal'] is True
            and v['original_SDK_repaired_or_deleted'] is False and exact(r,v['expected_remote_metadata'])
            and rid in roles and rid not in synced and r['run_id']==rid and r['project']=='mfm_model_v3_development' and r['state']=='finished'
            and r['history_rows']==500 and r['first_step']==1 and r['last_step']==500,'Original official selective sync/readback differs')
        synced.add(rid)
    need(synced==set(roles),'Both exact SDK IDs must be synced')
    need(all(contains_ref(Root_SDK,ref) for ref in [q['Root_numeric_closure'],*cert_refs,*sync_refs]),
        'Root SDK closure must join the same numeric closure and both actual verification/readback refs')
    for ref in q['SDK_CPU_supervisors']:
        s=bound(ref);j=str(s['job_id']);need(j not in expected_parents and s['status']=='COMPLETED' and s['exit_code']==0
            and s['first_failure'] is None and s['remaining']==[] and s['private_storage']['first_sampling_failure'] is None
            and s['private_storage']['budget_bytes']==LIMIT,'Actual independent SDK CPU closure required')
        identity=s['launch_identity'];need(identity['uid']==1278,'SDK CPU UID differs')
        # Scheduler node comes from the exact owned saved seven-column observation.
        raw=bound(q['SDK_parent_sacct']);found=[x.split('|') for x in raw['stdout'].splitlines() if x.split('|')[0]==j]
        need(len(found)==1 and re.fullmatch(r'compute-0-(?:[2-9]|1[0-9])',found[0][-1]),'SDK actual CPU node required');expected_parents[j]=found[0][-1]
    need(Root_SDK['schema']=='model_v3_routing7_current_paired_SDK_Root_closure_v1'
        and Root_SDK['status']=='NATIVE_FULL500_AND_OFFICIAL_SELECTIVE_SYNC_CLOUD_READBACK_CLOSED'
        and Root_SDK['failure'] is None and Root_SDK['job_id']==job and Root_SDK['old_job_id']==cohort
        and exact(Root_SDK['numeric_Root_closure'],q['Root_numeric_closure']),
        'Actual positive same-cohort Root SDK closure required; false scientific acceptance is the proper SDK scope')
    for key in ('audit_result','audit_supervisor','sync_result','sync_supervisor'):bound(Root_SDK[key])
    need(all(any(exact(ref,Root_SDK[key]) for key in ('audit_supervisor','sync_supervisor')) for ref in q['SDK_CPU_supervisors']),
        'Root SDK supervisors must be the actual independently closed two CPU parents')
    need(type(Root_SDK['runs']) is list and len(Root_SDK['runs'])==2,'Root must close exactly the selected two runs')
    proof_refs={bound(ref)['run_id']:ref for ref in cert_refs};readback_refs={bound(ref)['run_id']:ref for ref in sync_refs};seen=set()
    for item in Root_SDK['runs']:
        rid=item['run_id'];need(rid in roles and rid not in seen and item['role']==roles[rid] and item['history_rows']==500
            and exact(item['verification'],proof_refs[rid]) and exact(item['sync_result'],readback_refs[rid]),
            'Root SDK role/history/certificate/readback identity differs')
        seen.add(rid)
    need(seen==set(roles),'Both actual Root SDK roles must close')
    sdk_raw=bound(q['SDK_parent_sacct']);sdk_rows=[x.split('|') for x in sdk_raw['stdout'].splitlines() if x.strip()]
    sdk_expected={key:value for key,value in expected_parents.items() if key!=cpu_job}
    parents(sdk_raw,sdk_expected);parents(Root_SDK['actual_sacct'],sdk_expected)
    return dict(cohort=cohort,case=deepcopy(case),declared=deepcopy(declared),numeric_configuration=cfg,
        numeric_job_id=job,numeric_metadata=metadata,qualification_input=input_ref,qualification=deepcopy(q),
        actual_parent_nodes=expected_parents,native_run_roles=roles,current_runtime_source_count=len(cfg['source_sha256']))