"""Two bounded readonly protocols; immutable v1 gate/probe/storage are reused."""
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,need,ref,load,load_ref,verify,normalized,literal

PROTOCOLS={
 'coconut_sql_format_schema_probe_v1':{
  'plan':'SECONDARY_COCONUT_SQL_FORMAT_PROBE_PLAN_V1','proof':'SECONDARY_COCONUT_SQL_READONLY_STARTUP_V1',
  'stage':'SQL_FORMAT_SCHEMA_PROBE','module':'secondary_coconut_sql_inventory_v1.probe','files':1},
 'uff_control16_independent_readback_alpha_v1':{
  'plan':'SECONDARY_UFF_CONTROL16_READONLY_PLAN_V1','proof':'SECONDARY_UFF_CONTROL16_READONLY_STARTUP_V1',
  'stage':'UFF_CONTROL16_INDEPENDENT_READBACK','module':'secondary_uff_readback_alpha_v1.readback','files':32}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v2'

def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'READONLY_PLAN_HAS_NO_FAKE_ACQUISITION_DEPLOYMENT')
    plan=load(input_path);refs={}
    producer_key=plan.get('producer_key');need(producer_key in PROTOCOLS,'ONLY_TWO_EXACT_READONLY_PROTOCOLS_ALLOWED')
    protocol=PROTOCOLS[producer_key]
    need(plan.get('schema')==protocol['plan'] and plan.get('scope_key')==producer_key and
         plan.get('stage')==protocol['stage'] and plan.get('endpoint')==ENDPOINT and
         plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node and
         plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and plan.get('pilot') is False and
         plan.get('wall_seconds')==seconds==600 and 0<plan.get('output_cap_bytes',0)<=64*1024**2,
         'EXACT_BOUNDED_CPU16_SQL_FORMAT_READONLY_PLAN_REQUIRED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and
         review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root',
         'EXACT_READONLY_ROOT_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus',
                'memory_policy','pilot','wall_seconds','output_cap_bytes','execution_argv',
                'data_references','parent_evidence_references'):
        need(plan[key]==review[key],'EXACT_READONLY_ROOT_SCOPE_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],
         'EXACT_REVIEWED_READONLY_SOURCES_REQUIRED')
    for value in plan['source_references']+plan['parent_evidence_references']+[ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_READONLY_SOURCE_REFERENCE')
        refs[value['path']]=value
    for name in ('controller.py','adapters.py'):
        value=ref(HERE/name);need(value in plan['source_references'],'NEW_READONLY_CONTROLLER_SOURCE_MUST_BE_PINNED')
    need(ref(Path(__file__).absolute()) in plan['source_references'],'ACTUAL_READONLY_ADAPTER_SOURCE_REQUIRED')
    primary=ROOT/'code'/Path(protocol['module'].replace('.','/')+'.py')
    need(ref(primary) in plan['source_references'],'ACTUAL_READONLY_PRIMARY_SOURCE_REQUIRED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(ROOT/'artifacts' in out.parents,'NEW_ALPHA_READONLY_ARTIFACT_CHILD_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],
          '--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_READONLY_PRIMARY_FULL_ARGV_REQUIRED')
    bodies=plan['data_references'];need(isinstance(bodies,list) and len(bodies)==protocol['files'] and
        len({v['path'] for v in bodies})==len(bodies),'EXACT_UNIQUE_READONLY_DATA_LOCATOR_COUNT_REQUIRED')
    for value in bodies:
        need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and
             type(value['bytes']) is int and value['bytes']>=0 and isinstance(value['sha256'],str) and
             len(value['sha256'])==64 and set(value['sha256'])<=set('0123456789abcdef'),
             'LARGE_DATA_LOCATOR_TRIPLE_REQUIRED_WITHOUT_SMALL_METADATA_CAP')
        path=literal(value['path'])
        need(value['path'] not in refs,'DATA_LOCATORS_MUST_BE_DISJOINT_FROM_SMALL_SOURCE_REFS')
        if producer_key=='coconut_sql_format_schema_probe_v1':
            need(ROOT/'artifacts/source_acquisition' in path.parents and value['bytes']==37876914074,
                 'ONLY_COMPLETE_SQL_DATA_LOCATOR_NOT_LOGIN_BODY_READ')
        else:
            need((ROOT/'inputs' in path.parents or ROOT/'outputs/software_control16_v1/reproduction' in path.parents)
                 and path.name.endswith('.json.gz') and 0<value['bytes']<=2*1024**2,
                 'ONLY_SIXTEEN_ORIGINAL_ALPHA_PLUS_SIXTEEN_MAIN_BASELINE_PACKET_LOCATORS')
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof']}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter'];need(adapter['producer']=='readonly','ONLY_NEW_READONLY_ADAPTER_ALLOWED')
    return {'schema':adapter['proof_schema'],'endpoint':ENDPOINT,'uid':UID,'node':request['node'],
        'boot_id':probe['boot_id'],'job_id':str(jid),'observed_unix_seconds':probe['observed_unix_seconds'],
        'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,
        'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,
        'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,
                   'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
        'plan_reference':adapter['producer_plan_reference'],'root_review_reference':adapter['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,
        'bounded_readonly_scope_only':True,'scientific_population_or_full_SQL_status_coverage_accepted':False}
