"""One exact strict5 adapter, retaining the original v7 held/probe protocol."""
import csv,io
from pathlib import Path
from secondary_cpu_queue_v1 import common as q
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,NODES,need,ref,load,load_ref,verify,normalized,literal,read_small
from . import contracts as C
KEY=C.KEY;HERE=C.HERE
PROTOCOLS={KEY:{'plan':C.SCHEMA,'proof':C.PROOF,'stage':C.STAGE,'module':C.MODULE}}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy',
    'pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')

def triple(value):
    from secondary_coconut_strict5_day_v1.io import triple as exact
    return exact(value)

def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'EXACT_V7_READONLY_PLAN_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=load(input_path);refs={};key=plan.get('producer_key')
    need(key in PROTOCOLS,'ONLY_EXACT_COCONUT_STRICT5_PROTOCOL_ALLOWED')
    protocol=PROTOCOLS[key]
    need(plan.get('schema')==protocol['plan'] and plan.get('scope_key')==key and plan.get('stage')==protocol['stage']
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and plan.get('kind','analysis')=='analysis' and plan.get('pilot') is False
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds and seconds==C.WALL and seconds%60==0,
        'EXACT_ALPHA_CPU16_NO_MEMORY_V7_READONLY_RESOURCE_PLAN_REQUIRED')
    need(plan.get('mode')=='diagnostic735' and plan.get('scope_parameters')==C.parameters(plan) and plan['output_cap_bytes']==C.CAP,'EXACT_COCONUT_STRICT5_SCOPE_AND_FINITE_CAP')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root'
        and review.get('kind','analysis')=='analysis','EXACT_V7_READONLY_ROOT_REVIEW_REQUIRED')
    for field in REVIEW_FIELDS:need(plan[field]==review[field],'EXACT_V7_ROOT_SCOPE_DIFFERS:'+field)
    need(plan['source_references']==review['approved_source_references'],'EXACT_V7_REVIEWED_SOURCE_SET_REQUIRED')
    bodies=plan['data_references'];need(isinstance(bodies,list) and len(bodies)==len(C.parents(plan)[1]),'EXACT_COCONUT46_NORM_PLUS_FORMULA47_DATA_LOCATORS')
    body_paths={triple(value)['path'] for value in bodies}
    need(len(body_paths)==len(bodies) and not any(value['path'] in body_paths for value in
        [*plan['source_references'],*plan['parent_evidence_references']]),'NO_BODY_MAY_BE_READ_AS_STARTUP_SOURCE_OR_PARENT_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_V7_SMALL_SOURCE_REFERENCE')
        refs[value['path']]=value
    for name in ('controller.py','adapters.py'):
        need(ref(HERE/name) in plan['source_references'],'ACTUAL_V7_CONTROLLER_AND_ADAPTER_SOURCES_MUST_BE_APPROVED')
    need(ref(Path(__file__).absolute()) in plan['source_references'],'ACTUAL_V7_ADAPTER_SOURCE_REQUIRED')
    primary=ROOT/'code'/Path(protocol['module'].replace('.','/')+'.py')
    for path in primary.parent.iterdir():
        if path.is_file() and path.suffix in {'.py','.json','.md'}:
            need(ref(path) in plan['source_references'],'EVERY_NEW_V7_CONSUMER_SOURCE_MUST_BE_APPROVED:'+path.name)
    for path in (primary,ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py'):
        need(ref(path) in plan['source_references'],'EXACT_V7_PRIMARY_AND_IMPORTED_BASE_SOURCES_REQUIRED')
    need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_ALPHA_RESOURCE_AUTHORITY_MUST_BE_APPROVED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(ROOT/'artifacts' in out.parents,'NEW_ALPHA_V7_READONLY_ARTIFACT_CHILD_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_V7_MODULE_AND_COMPLETE_EIGHT_ARGV_REQUIRED')
    archive=C.parents(plan)[0]['receipt']['norm_parent']['A_receipt']
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],
        'request_kind':'analysis','pilot':False,'scope_key':key,'scope_parameters':plan['scope_parameters'],
        'stage':plan['stage'],'scope_mode':'BOUNDED_READONLY_ANALYSIS','performance_profile':False,'fixed_archive_authority':archive}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_EXACT_NORM_FULL_OR_NATIVE2_INVARIANTS_REQUEST_PROTOCOL_ALLOWED')
    return {'schema':adapter['proof_schema'],'endpoint':ENDPOINT,'uid':UID,'node':request['node'],
        'boot_id':probe['boot_id'],'job_id':str(jid),'observed_unix_seconds':probe['observed_unix_seconds'],
        'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,
        'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,
        'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':adapter['pilot'],'cpus':16,'memory_policy':POLICY,
                   'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
        'plan_reference':adapter['producer_plan_reference'],'root_review_reference':adapter['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,
        'scope_key':adapter['scope_key'],'stage':adapter['stage'],'scope_mode':adapter['scope_mode'],
        'performance_profile':adapter['performance_profile'],'bounded_readonly_scope_only':True,
        'bounded_source_acquisition_scope_only':False,'scientific_population_or_full_SQL_status_coverage_accepted':False}

