"""Only original TDC/Drugs/Kraken bounded GET probe, never another source/full."""
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from official_get_probe_v1 import contracts as C
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_queue_v16'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
PROTOCOLS={C.KEY:{'plan':C.PLAN_SCHEMA,'proof':C.PROOF_SCHEMA,'stage':C.STAGE,'module':C.MODULE,'pilot':False,
    'scope_mode':C.MODE,'performance_profile':False,'cap':C.CAP,'wall_max':3600}}

def readonly(input_path,deployment_path,node,seconds,**unused):
    Q.need(deployment_path is None,'V16_NO_OLD_QA_OR_ACQUISITION_DEPLOYMENT_WRAPPER')
    plan=Q.load(input_path);wall=plan.get('wall_seconds');refs={}
    Q.need(plan.get('schema')==C.PLAN_SCHEMA and plan.get('scope_key')==plan.get('producer_key')==C.KEY
        and plan.get('stage')==C.STAGE and plan.get('scope_parameters')==C.PARAMETERS and plan.get('scope_mode')==C.MODE
        and plan.get('performance_profile') is False and plan.get('kind')=='analysis' and plan.get('pilot') is False
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and type(wall) is int and wall==seconds and 120<wall<=3600
        and wall%60==0 and plan.get('output_cap_bytes')==256<<20 and plan.get('data_references')==[],
        'V16_ONLY_EXACT_THREE_ORIGINAL_URL_BOUNDED_GET_NO_FULL_OR_NEW_SOURCE')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','EXPLICIT_ROOT_EXACT_GET_PROBE_REVIEW')
    for key in C.REVIEW_FIELDS:Q.need(plan[key]==review[key],'EXACT_ROOT_GET_PROBE_REVIEW_DIFFERS:'+key)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_ROOT_GET_PROBE_SOURCE_SET')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']]:
        Q.normalized(value);Q.verify(value);Q.need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_GET_PROBE_SMALL_PIN');refs[value['path']]=value
    for value in plan['parent_evidence_references']:Q.need(value in plan['source_references'],'GET_PROBE_PARENTS_ONLY_SMALL_APPROVED_METADATA')
    C.metadata(plan)
    for path in HERE.iterdir():
        if path.suffix in ('.py','.md'):Q.need(Q.ref(path) in plan['source_references'],'ALL_ACTUAL_V16_CONTROL_SOURCE_PINS')
    proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory'])
    Q.need(ROOT/'artifacts/official_get_probe_v1' in out.parents and not out.exists(),'FRESH_EXACT_GET_PROBE_OUTPUT_PREFIX')
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_PROBE_PRIMARY_AND_ALL_EIGHT_ARGV')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':[],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':C.CAP,'producer_working_directory':str(ROOT/'code'),
        'proof_schema':C.PROOF_SCHEMA,'request_kind':'analysis','pilot':False,'scope_key':C.KEY,'scope_parameters':C.PARAMETERS,
        'stage':C.STAGE,'scope_mode':C.MODE,'performance_profile':False,
        'fixed_archive_authority':{'original_catalog_reference':plan['origin_locator_catalog_reference'],'source_ids':[s['source_id'] for s in C.SPECS],
            'original_URLs':[s['url'] for s in C.SPECS],'source_entity_caps':[s['cap_bytes'] for s in C.SPECS],
            'maximum_original_sources':3,'automatic_retry':False,'new_UFF_QM_calls':0,'new_full_or_identity_or_training_release_authorized':False}}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    a=request['adapter'];Q.need(a['producer']=='readonly' and a['scope_key']==request['scope_key']==C.KEY
        and request['kind']==a['request_kind']=='analysis' and request['pilot'] is a['pilot'] is False
        and request['scope_parameters']==a['scope_parameters']==C.PARAMETERS and request['stage']==a['stage']==C.STAGE
        and request['scope_mode']==a['scope_mode']==C.MODE and request['performance_profile'] is a['performance_profile'] is False,
        'V16_ONLY_EXACT_OFFICIAL_BOUNDED_GET_REQUEST')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_GET_PROBE_STORAGE_SCOPE7')
    return {'schema':C.PROOF_SCHEMA,'endpoint':ENDPOINT,'uid':UID,'node':request['node'],'boot_id':probe['boot_id'],'job_id':str(jid),
        'observed_unix_seconds':probe['observed_unix_seconds'],'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,'wall_seconds':request['wall_seconds'],'execution_argv':a['producer_argv']},
        'plan_reference':a['producer_plan_reference'],'root_review_reference':a['producer_review_reference'],'account_free_bytes':storage['effective_free_bytes'],
        'effective_free_basis':storage['effective_free_basis'],'storage_observation_reference':storage_reference,'storage_observation':storage,
        'scope_key':C.KEY,'stage':C.STAGE,'scope_mode':C.MODE,'performance_profile':False,'bounded_readonly_scope_only':True,
        'bounded_source_acquisition_scope_only':True,'scientific_population_or_full_SQL_status_coverage_accepted':False,
        'identity_or_new_full_or_pool_or_training_release_authorized':False}
