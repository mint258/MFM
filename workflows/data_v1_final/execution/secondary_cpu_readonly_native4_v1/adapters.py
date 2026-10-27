"""Single exact native4 protocol; unchanged v13 scheduling is imported relatively."""
import re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_moleculenet_native4_identity_v1 import contracts as C
from secondary_moleculenet_csv6_identity_v1.guard import account
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_native4_v1';FILES=('controller.py','adapters.py','materialize.py')
V13=ROOT/'code/secondary_cpu_readonly_queue_v13/controller.py'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
NATIVE_KEY='moleculenet_native4_identity_profile_alpha_v1'
PROTOCOLS={NATIVE_KEY:{'plan':'SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_PLAN_V1','proof':'SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_STARTUP_V1',
    'module':'secondary_moleculenet_native4_identity_v1.run','stage':'MOLECULENET_NATIVE4_ALL_PHYSICAL_RELATIONSHIPS_AND_BOUNDED_SDF_KEY_PROFILE','wall':14400,'cap':2<<30}}
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
    Q.need(r['schema']=='ROOT_SECONDARY_NATIVE4_THIN_SOURCE_REVIEW_V1' and r['status']=='APPROVED_FOR_EXACT_METADATA_ADAPTER' and r['reviewer']=='root'
        and r['endpoint']==ENDPOINT and r['uid']==1264 and r['run_root']==str(ROOT) and r['only_native4_profile_protocol'] is True
        and r['new_queue_algorithm'] is False and r['v13_controller_reference']==old and r['controller_reference']==current
        and (old['bytes'],old['sha256'])==(current['bytes'],current['sha256']),'ROOT_SOURCE_REVIEW_AND_V13_CONTROLLER_BYTE_IDENTITY')
    Q.need(r['source_references']==[Q.ref(HERE/n) for n in FILES],'EXACT_ALL_THREE_ADAPTER_SOURCES')
    manifest=Q.load_ref(r['source_manifest_reference']);entries=manifest['entries']
    for ref in r['source_references']:
        matches=[v for v in entries if v.get('alpha_target_path')==ref['path']]
        Q.need(len(matches)==1 and (matches[0]['bytes'],matches[0]['sha256'])==(ref['bytes'],ref['sha256']),'SOURCE_BUNDLE_TO_ACTUAL_ALPHA_TARGET_BYTES')
    return r


def parents(plan):
    a=C.authority(plan);p=plan['parent_evidence_references']
    for k in ('format_receipt_reference','format_plan_reference','format_proof_reference','format_fixture_reference'):Q.need(a[k] in p,'EXACT792_PARENT:'+k)
    r=Q.load_ref(a['format_receipt_reference']);fp=Q.load_ref(a['format_plan_reference']);fproof=Q.load_ref(a['format_proof_reference'])
    Q.need(r['schema']=='MISSING11_IDENTITY_INPUT_FORMAT_PROFILE_RECEIPT_V1' and r['status']=='FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING'
        and r['job_id']=='1884792' and r['endpoint']==ENDPOINT and r['uid']==1264 and r['plan_reference']==a['format_plan_reference'] and r['startup_proof_reference']==a['format_proof_reference']
        and fp['uid']==1264 and fp['endpoint']==ENDPOINT and fp['scope_key']=='moleculenet_missing11_identity_format_probe_alpha_v1'
        and fproof['uid']==1264 and fproof['endpoint']==ENDPOINT and str(fproof['job_id'])=='1884792' and fproof['plan_reference']==a['format_plan_reference'],'ACTUAL792_HISTORICAL_SCOPE_NOT_FRESH_OR_IDENTITY_ACCEPTANCE')
    fx=Q.load_ref(a['format_fixture_reference']);Q.need(fx['status']=='PASS' and fx['counts']=={'run':8,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0},'ACTUAL792_FORMAT8_NOT_B3')
    account(plan['format_accounting_reference'],'1884792',p)
    for s in a['sources']:
        ref=s['format_report_reference'];Q.need(ref in plan['source_references'] and any(v['source_id']==s['source_id'] and v['report_reference']==ref for v in r['reports']),'EXACT792_FOUR_REPORT_PINS')
        report=Q.load_ref(ref);Q.need(report['payload_reference']==s['payload_reference'] and report['inventory']['inventory_reference']==s['inventory_reference']
            and report['inventory']['category_counts']==s['category_counts'],'EXACT_FOUR_PAYLOAD_INVENTORY_LOCATORS_ONLY')
    kr=plan['kernel_profile_receipt_reference'];Q.need(kr in p,'ACTUAL_OLD_B3_RECEIPT');b=Q.load_ref(kr)
    Q.need(b['schema']=='SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_RECEIPT_V1' and b['status']=='SAMPLED_FROZEN_IDENTITY_KEY_OBSERVATIONS_COMPLETE'
        and b['job_id']=='1884785' and b['uid']==1264 and b['endpoint']==ENDPOINT
        and b['fixtures']=={'tests_run':3,'failures':0,'errors':0,'skips':0,'before_A_body_IO':True},'ACTUAL1884785_B3_PASS_NO_RERUN')
    for ref in (b['plan'],b['startup_proof']):Q.need(ref in p,'ACTUAL_B3_PLAN_PROOF')
    bp=Q.load_ref(b['plan']);bs=Q.load_ref(b['startup_proof']);Q.need(bp['frozen_identity_source_references']==plan['frozen_identity_source_references']
        and bs['uid']==1264 and bs['endpoint']==ENDPOINT and str(bs['job_id'])=='1884785' and bs['plan_reference']==b['plan'],'SAME_ACTUAL_B3_FROZEN_FUNCTION_SOURCES')
    for name in ('__init__.py','contracts.py','runtime.py','run.py'):
        ref=Q.ref(ROOT/'code/secondary_coconut_identity_norm_profile_v1'/name);Q.need(ref in bp['source_references'] and ref in plan['source_references'],'UNCHANGED_B4_EXECUTION_CORE')
    for ref in plan['frozen_identity_source_references'].values():Q.need(ref in plan['source_references'] and ref in bp['source_references'],'EXACT_OLD_FROZEN_HELPER_PINS')
    account(plan['kernel_profile_accounting_reference'],'1884785',p)
    return {'native_TAR_inputs':4,'scientific_body_locators':8,'physical_SDF_N':'UNKNOWN_UNTIL_THIS_CPU_JOB','maximum_SDF_keys_per_source':1000,
        'only_new3_fixtures_run':True,'old_B3_job_id':'1884785','old_B3_reexecuted':False,'MOL2_graph_charge_stereo':'UNKNOWN','full_or_pool_release':False}


def readonly(input_path,deployment_path,node,seconds,**unused):
    Q.need(deployment_path is None,'NATIVE4_HAS_NO_DEPLOYMENT_WRAPPER');plan=Q.load(input_path);key=plan.get('scope_key')
    exact=PROTOCOLS[NATIVE_KEY];Q.need(C.KEY==NATIVE_KEY and C.PLAN==exact['plan'] and C.PROOF==exact['proof'] and C.MODULE==exact['module']
        and C.STAGE==exact['stage'] and C.CAP==exact['cap'],'FROZEN_LITERAL_NATIVE4_PROTOCOL_NO_ARBITRARY_MODULE')
    Q.need(key==C.KEY and key in PROTOCOLS and plan.get('schema')==C.PLAN and plan.get('producer_key')==key and plan.get('stage')==C.STAGE
        and plan.get('scope_parameters')==C.PARAMETERS and plan.get('scope_mode')==C.SCOPE and plan.get('mode')=='profile'
        and plan.get('kind')=='analysis' and plan.get('pilot') is True and plan.get('performance_profile') is True
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID==1264 and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and type(plan.get('wall_seconds')) is int
        and plan['wall_seconds']==seconds==14400 and plan.get('output_cap_bytes')==C.CAP==2<<30,'ONLY_EXACT_ALPHA_NATIVE4_PROFILE_PROTOCOL')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','EXACT_ROOT_NATIVE4_SCOPE_APPROVAL')
    for k in REVIEW_FIELDS:Q.need(plan[k]==review[k],'EXACT_NATIVE4_REVIEW_FIELD:'+k)
    Q.need(plan['source_references']==review['approved_source_references'] and review['source_only_PDB_seam_and_MOL2_unknowns_reviewed'] is True
        and review['full_or_pool_release'] is False,'EXACT_REVIEWED_NATIVE4_SOURCE_SET_AND_LIMITS')
    for ref in plan['data_references']:body_locator(ref)
    paths={v['path'] for v in plan['data_references']};Q.need(len(paths)==8 and not paths.intersection(v['path'] for v in [*plan['source_references'],*plan['parent_evidence_references']]),'BODY_LOCATORS_NEVER_LOGIN_SOURCE_BODIES')
    refs=unique([*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']])
    for ref in refs:Q.verify(ref)
    for path in [*(C.HERE/n for n in C.FILES),*(HERE/n for n in FILES),ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'ALL_NATIVE4_AND_NEW_ADAPTER_BASE_SOURCE_PINS')
    for k in ('resource_authority_reference','cost_decision_reference','adapter_source_review_reference'):Q.need(plan[k] in plan['source_references'],'EXPLICIT_APPROVED_SOURCE_AUTHORITY:'+k)
    Q.authority(plan['resource_authority_reference']['path']);cost=Q.load_ref(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED'
        and cost['schema']=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_QUALITY_UNCHANGED')
    sr=source_review(plan['adapter_source_review_reference']);Q.need(sr['source_manifest_reference'] in plan['source_references'] and sr['v13_controller_reference'] in plan['source_references'],'ACTUAL_SOURCE_MANIFEST_AND_V13_PIN')
    facts=parents(plan);proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory'])
    Q.need(ROOT/'artifacts' in out.parents and not out.exists() and not proof.exists(),'FRESH_NATIVE_PROFILE_OUTPUT_AND_PROOF')
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_NATIVE4_MODULE_AND_ALL_EIGHT_ARGV')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':refs,'data_reference_locators_only':plan['data_references'],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':C.CAP,'producer_working_directory':str(ROOT/'code'),
        'proof_schema':C.PROOF,'request_kind':'analysis','pilot':True,'scope_key':key,'scope_parameters':C.PARAMETERS,
        'stage':C.STAGE,'scope_mode':C.SCOPE,'performance_profile':True,'fixed_archive_authority':facts}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    a=request['adapter'];Q.need(a['producer']=='readonly' and a['scope_key']==C.KEY and request['scope_key']==C.KEY and a['proof_schema']==C.PROOF
        and request['kind']==a['request_kind']=='analysis' and request['pilot'] is a['pilot'] is True and request['performance_profile'] is a['performance_profile'] is True
        and request['scope_parameters']==a['scope_parameters']==C.PARAMETERS and request['stage']==a['stage']==C.STAGE
        and request['scope_mode']==a['scope_mode']==C.SCOPE and request['wall_seconds']==14400 and a['output_cap_bytes']==C.CAP,'ONLY_NATIVE4_PROFILE_FRESH_PROOF')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_CURRENT_SCOPE7')
    return {'schema':C.PROOF,'endpoint':ENDPOINT,'uid':UID,'node':request['node'],'boot_id':probe['boot_id'],'job_id':str(jid),
        'observed_unix_seconds':probe['observed_unix_seconds'],'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':True,'cpus':16,'memory_policy':POLICY,'wall_seconds':14400,'execution_argv':a['producer_argv']},
        'plan_reference':a['producer_plan_reference'],'root_review_reference':a['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,'scope_key':C.KEY,'stage':C.STAGE,'scope_mode':C.SCOPE,
        'performance_profile':True,'bounded_readonly_scope_only':True,'bounded_source_acquisition_scope_only':False,
        'root_reviewed_native4_bounded_profile_only':True,'scientific_source_identity_population_accepted':False,'global_pool_release_authorized':False}
