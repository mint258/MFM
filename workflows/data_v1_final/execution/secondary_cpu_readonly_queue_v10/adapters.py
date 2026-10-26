"""Exact existing official missing11 format metadata; body locators remain unread."""
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,need,ref,load,load_ref,verify,normalized,literal
from secondary_missing11_identity_format_probe_v1 import contracts as C
from secondary_missing11_identity_format_probe_v1.formats import TAR_IDS
KEY=C.KEY
PROTOCOLS={KEY:{'plan':'SECONDARY_MISSING11_IDENTITY_FORMAT_PROFILE_PLAN_V1','proof':'SECONDARY_MISSING11_IDENTITY_FORMAT_PROFILE_STARTUP_V1','stage':C.STAGE,'module':C.MODULE}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v10'
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')

def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'EXACT_MISSING11_FORMAT_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=load(input_path);protocol=PROTOCOLS[KEY]
    need(plan.get('schema')==protocol['plan'] and plan.get('producer_key')==plan.get('scope_key')==KEY
      and plan.get('stage')==C.STAGE and plan.get('scope_parameters')==C.PARAMETERS and plan.get('mode')=='format_profile'
      and plan.get('kind')=='analysis' and plan.get('pilot') is False and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID
      and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in C.q.NODES and plan.get('cpus')==16
      and plan.get('memory_policy')==POLICY and type(seconds) is int and seconds==plan.get('wall_seconds')==3600
      and plan.get('output_cap_bytes')==64<<20,'EXACT_ELEVEN_FORMAT_ONLY_CPU16_NO_MEM_1H64MIB_SCOPE')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE'
      and review.get('reviewer')=='root','EXACT_NEW_FORMAT_ROOT_REVIEW_REQUIRED')
    for key in REVIEW_FIELDS:need(plan[key]==review[key],'EXACT_FORMAT_ROOT_SCOPE_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'EXACT_FORMAT_APPROVED_SOURCES')
    body_paths={C.body_reference(row)['path'] for row in plan['data_references']}
    need(len(body_paths)==15 and not body_paths&{row['path'] for row in plan['source_references']},'EXACT15_UNIQUE_BODY_LOCATORS_NOT_SOURCE')
    refs={}
    for row in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        row=normalized(row);need(row['bytes']<=2<<20,'ONLY_BOUNDED_SMALL_SOURCES');verify(row)
        need(row['path'] not in refs or refs[row['path']]==row,'CONFLICTING_FORMAT_SMALL_PIN');refs[row['path']]=row
    for row in plan['parent_evidence_references']:need(row in plan['source_references'],'EVERY_FORMAT_PARENT_APPROVED_SOURCE')
    for package in ('secondary_missing11_identity_format_probe_v1','secondary_cpu_readonly_queue_v10','secondary_external_sources_acquisition_v1'):
        for path in (ROOT/'code'/package).iterdir():
            if path.is_file() and path.suffix in {'.py','.json','.md'}:need(ref(path) in plan['source_references'],'EVERY_FORMAT_NEW_AND_REUSED_SOURCE_REQUIRED:'+str(path))
    for path in (ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py'):
        need(ref(path) in plan['source_references'],'ACTUAL_IMPORTED_BASE_SOURCE_REQUIRED')
    for key in ('resource_authority_reference','cost_decision_reference','locator_catalog_reference','identity_input_contract_reference'):
        need(plan[key] in plan['source_references'],'EXACT_FORMAT_SMALL_AUTHORITY:'+key)
    expected={}
    for key,jid in (('acquisition_accounting_reference','1884784'),('reused_sider_accounting_reference','1884783')):
        value=C.prior.actual_account(plan[key],jid);need(plan[key] in plan['parent_evidence_references'] and value['raw_sacct_reference'] in plan['parent_evidence_references'],'EXACT_ACTUAL_FORMAT_C0_ACCOUNTING_PARENT')
        expected[jid]=value
    for key in ('acquisition_receipt_reference','reused_sider_receipt_reference'):need(plan[key] in plan['parent_evidence_references'],'EXACT_ACTUAL_FORMAT_RECEIPT_PARENT')
    full=load_ref(plan['acquisition_receipt_reference']);single=load_ref(plan['reused_sider_receipt_reference'])
    need(full['job_id']=='1884784' and full['status']=='OFFICIAL_ELEVEN_SOURCE_CONTAINER_ACQUISITION_COMPLETE'
      and single['job_id']=='1884783' and single['status']=='OFFICIAL_SINGLE_SOURCE_CONTAINER_PROFILE_COMPLETE','ACTUAL_CLOSED_OFFICIAL_SOURCE_PARENTS')
    rows={row['source_id']:row for row in full['sources']};need(len(rows)==len(full['sources'])==11 and set(rows)==set(C.IDS),'ONLY_EXACT_ELEVEN_OFFICIAL_SOURCES')
    need(all(row['status']=='COMPLETE_CONTAINER_OBSERVED' and row['full_file_disk_SHA_verified'] is True for row in rows.values()),'ALL11_ACTUAL_CONTAINER_PARENT_SHA')
    bodies=[rows[key]['payload_reference'] for key in C.IDS]+[rows[key]['container']['inventory_reference'] for key in TAR_IDS]
    need(plan['data_references']==bodies and sum(row['bytes'] for row in bodies)==2526531443,'EXACT_PARENT_DERIVED15_LOCATORS_AND_BYTES')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(out==ROOT/'artifacts/moleculenet_missing11_identity_format_probe_v1/v1','EXACT_NEW_FORMAT_OUTPUT')
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_FORMAT_PRIMARY_AND_ARGV')
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
      'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
      'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
      'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,'startup_proof_path':str(proof),
      'science_output':str(out),'output_cap_bytes':64<<20,'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],
      'request_kind':'analysis','pilot':False,'scope_key':KEY,'scope_parameters':C.PARAMETERS,'stage':C.STAGE,
      'scope_mode':'BOUNDED_READONLY_ANALYSIS','performance_profile':False,'fixed_archive_authority':{'acquisition_parent':'1884784','reused_sider_parent':'1884783','body_full_rehash_claimed':False,'identity_or_pool_acceptance':False}}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key']==request['scope_key']==KEY
      and request['kind']==adapter['request_kind']=='analysis' and request['pilot'] is adapter['pilot'] is False
      and request['scope_parameters']==adapter['scope_parameters']==C.PARAMETERS and request['stage']==adapter['stage']==C.STAGE
      and request['scope_mode']==adapter['scope_mode']=='BOUNDED_READONLY_ANALYSIS'
      and request['performance_profile'] is adapter['performance_profile'] is False,'EXACT_FORMAT_REQUEST_PROTOCOL')
    return {'schema':adapter['proof_schema'],'endpoint':ENDPOINT,'uid':UID,'node':request['node'],
      'boot_id':probe['boot_id'],'job_id':str(jid),'observed_unix_seconds':probe['observed_unix_seconds'],
      'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
      'script_reference':request['script_reference'],'controller_evidence':controller_evidence,
      'source_target_verification':request['verified_target_references'],'actual_gate_process':probe['gate_process'],
      'actual_memory_environment':probe['actual_memory_environment'],'scheduler_memory_is_recorded_not_an_admission_threshold':True,
      'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
      'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
      'plan_reference':adapter['producer_plan_reference'],'root_review_reference':adapter['producer_review_reference'],
      'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
      'storage_observation_reference':storage_reference,'storage_observation':storage,'scope_key':KEY,'stage':C.STAGE,
      'scope_mode':'BOUNDED_READONLY_ANALYSIS','performance_profile':False,'bounded_readonly_scope_only':True,
      'bounded_source_acquisition_scope_only':False,'scientific_population_or_full_SQL_status_coverage_accepted':False}