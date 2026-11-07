"""Single exact TDC2 evidence protocol; unchanged v13 controller is imported relatively."""
import re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_tdc_exact2_composition_v1 import contracts as C
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_tdc2_v1';FILES=('controller.py','adapters.py','materialize.py')
V13=ROOT/'code/secondary_cpu_readonly_queue_v13/controller.py'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
TDC_KEY='tdc_exact2_composition_evidence_alpha_v1'
PROTOCOLS={TDC_KEY:{'plan':'SECONDARY_TDC_EXACT2_COMPOSITION_EVIDENCE_PLAN_V1','proof':'SECONDARY_TDC_EXACT2_COMPOSITION_EVIDENCE_STARTUP_V1',
    'module':'secondary_tdc_exact2_composition_v1.run','stage':'TDC_EXACT2_ORIGINAL_UNKNOWN_SOURCE_ATOMS_ONLY','wall':600,'cap':2<<30}}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def unique(refs):
    result={}
    for r in refs:Q.normalized(r);Q.need(r['path'] not in result or result[r['path']]==r,'CONFLICTING_SMALL_SOURCE_PIN');result[r['path']]=r
    return [result[k] for k in sorted(result)]


def body_locator(value):
    Q.need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_PRODUCER_BODY_TRIPLE_ONLY');Q.literal(value['path'])


def source_review(reference):
    r=Q.load_ref(reference);old=Q.ref(V13);current=Q.ref(HERE/'controller.py')
    Q.need(r['schema']=='ROOT_SECONDARY_TDC2_THIN_SOURCE_REVIEW_V1' and r['status']=='APPROVED_FOR_EXACT_METADATA_ADAPTER' and r['reviewer']=='root'
        and r['endpoint']==ENDPOINT and r['uid']==1264 and r['run_root']==str(ROOT) and r['only_TDC_exact2_atoms_only_protocol'] is True
        and r['new_queue_algorithm'] is False and r['v13_controller_reference']==old and r['controller_reference']==current
        and (old['bytes'],old['sha256'])==(current['bytes'],current['sha256']),'ROOT_SOURCE_REVIEW_AND_V13_CONTROLLER_BYTE_IDENTITY')
    Q.need(r['source_references']==[Q.ref(HERE/n) for n in FILES],'EXACT_ALL_THREE_ADAPTER_SOURCES')
    manifest=Q.load_ref(r['source_manifest_reference']);entries=manifest['entries']
    for ref in r['source_references']:
        matches=[v for v in entries if v.get('alpha_target_path')==ref['path']]
        Q.need(len(matches)==1 and (matches[0]['bytes'],matches[0]['sha256'])==(ref['bytes'],ref['sha256']),'SOURCE_BUNDLE_TO_ACTUAL_ALPHA_TARGET_BYTES')
    return r


def parents(plan):
    d,values,by,m=C.inputs(plan)
    return {'original_Main_uid':1278,'original_Main_jobs':['4521689','4521757','4521907'],'original_UNKNOWN_rows':2,'new_atoms_only_evidence_seam':True,'automatic_policy_acceptance':False,'full_or_pool_release':False}


def readonly(input_path,deployment_path,node,seconds,**unused):
    Q.need(deployment_path is None,'TDC2_HAS_NO_DEPLOYMENT_WRAPPER');plan=Q.load(input_path);key=plan.get('scope_key')
    exact=PROTOCOLS[TDC_KEY];Q.need(C.KEY==TDC_KEY and C.PLAN==exact['plan'] and C.PROOF==exact['proof'] and C.MODULE==exact['module']
        and C.STAGE==exact['stage'] and C.CAP==exact['cap'],'FROZEN_LITERAL_TDC2_PROTOCOL_NO_ARBITRARY_MODULE')
    Q.need(key==C.KEY and key in PROTOCOLS and plan.get('schema')==C.PLAN and plan.get('producer_key')==key and plan.get('stage')==C.STAGE
        and plan.get('scope_parameters')==C.PARAMETERS and plan.get('scope_mode')==C.SCOPE and plan.get('mode')=='evidence'
        and plan.get('kind')=='analysis' and plan.get('pilot') is False and plan.get('performance_profile') is False
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID==1264 and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and type(plan.get('wall_seconds')) is int
        and plan['wall_seconds']==seconds==600 and plan.get('output_cap_bytes')==C.CAP==2<<30,'ONLY_EXACT_ALPHA_TDC2_PROFILE_PROTOCOL')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','EXACT_ROOT_TDC2_SCOPE_APPROVAL')
    for k in REVIEW_FIELDS:Q.need(plan[k]==review[k],'EXACT_TDC2_REVIEW_FIELD:'+k)
    Q.need(plan['source_references']==review['approved_source_references'] and review['new_SMILES_atoms_only_evidence_seam_reviewed'] is True and review['automatic_policy_acceptance'] is False
        and review['full_or_pool_release'] is False,'EXACT_REVIEWED_TDC2_SOURCE_SET_AND_LIMITS')
    for ref in plan['data_references']:body_locator(ref)
    paths={v['path'] for v in plan['data_references']};Q.need(len(paths)==3 and not paths.intersection(v['path'] for v in [*plan['source_references'],*plan['parent_evidence_references']]),'BODY_LOCATORS_NEVER_LOGIN_SOURCE_BODIES')
    refs=unique([*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']])
    for ref in refs:Q.verify(ref)
    for path in [*(C.HERE/n for n in C.FILES),*(HERE/n for n in FILES),ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'ALL_TDC2_AND_NEW_ADAPTER_BASE_SOURCE_PINS')
    for k in ('resource_authority_reference','cost_decision_reference','adapter_source_review_reference'):Q.need(plan[k] in plan['source_references'],'EXPLICIT_APPROVED_SOURCE_AUTHORITY:'+k)
    Q.authority(plan['resource_authority_reference']['path']);cost=Q.load_ref(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED'
        and cost['schema']=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_QUALITY_UNCHANGED')
    sr=source_review(plan['adapter_source_review_reference']);Q.need(sr['source_manifest_reference'] in plan['source_references'] and sr['v13_controller_reference'] in plan['source_references'],'ACTUAL_SOURCE_MANIFEST_AND_V13_PIN')
    facts=parents(plan);proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory'])
    Q.need(ROOT/'artifacts' in out.parents and not out.exists() and not proof.exists(),'FRESH_NATIVE_PROFILE_OUTPUT_AND_PROOF')
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_TDC2_MODULE_AND_ALL_EIGHT_ARGV')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':refs,'data_reference_locators_only':plan['data_references'],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':C.CAP,'producer_working_directory':str(ROOT/'code'),
        'proof_schema':C.PROOF,'request_kind':'analysis','pilot':False,'scope_key':key,'scope_parameters':C.PARAMETERS,
        'stage':C.STAGE,'scope_mode':C.SCOPE,'performance_profile':False,'fixed_archive_authority':facts}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    a=request['adapter'];Q.need(a['producer']=='readonly' and a['scope_key']==C.KEY and request['scope_key']==C.KEY and a['proof_schema']==C.PROOF
        and request['kind']==a['request_kind']=='analysis' and request['pilot'] is a['pilot'] is False and request['performance_profile'] is a['performance_profile'] is False
        and request['scope_parameters']==a['scope_parameters']==C.PARAMETERS and request['stage']==a['stage']==C.STAGE
        and request['scope_mode']==a['scope_mode']==C.SCOPE and request['wall_seconds']==600 and a['output_cap_bytes']==C.CAP,'ONLY_TDC2_PROFILE_FRESH_PROOF')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_CURRENT_SCOPE7')
    return {'schema':C.PROOF,'endpoint':ENDPOINT,'uid':UID,'node':request['node'],'boot_id':probe['boot_id'],'job_id':str(jid),
        'observed_unix_seconds':probe['observed_unix_seconds'],'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,'wall_seconds':600,'execution_argv':a['producer_argv']},
        'plan_reference':a['producer_plan_reference'],'root_review_reference':a['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,'scope_key':C.KEY,'stage':C.STAGE,'scope_mode':C.SCOPE,
        'performance_profile':False,'bounded_readonly_scope_only':True,'bounded_source_acquisition_scope_only':False,
        'root_reviewed_TDC2_atoms_only_evidence':True,'automatic_fallback_policy_acceptance':False,
        'scientific_source_identity_population_accepted':False,'global_pool_release_authorized':False}
