"""Only six original CSV physical identity profile/full; login never reads payloads."""
import re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_moleculenet_csv6_identity_v1 import contracts as C
from secondary_moleculenet_csv6_identity_v1.guard import account
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_queue_v12'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
PROTOCOLS={C.MODES[mode]['key']:{**C.MODES[mode],'mode':mode,'module':C.MODULE} for mode in ('profile','full')}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def body_locator(value):
    Q.need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_SOURCE_PRODUCER_DATA_LOCATOR_ONLY')
    Q.literal(value['path'])  # No payload open/stat/hash/parse on login.


def readonly(input_path,deployment_path,node,seconds,**unused):
    Q.need(deployment_path is None,'SIX_CSV_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=Q.load(input_path);mode=plan.get('mode');Q.need(mode in ('profile','full'),'V12_ONLY_EXACT_SIX_CSV_PHASES')
    spec=C.MODES[mode];key=spec['key'];params=C.parameters(mode);refs={};wall=plan['wall_seconds'];cap=plan['output_cap_bytes']
    Q.need(plan.get('schema')==spec['plan'] and plan.get('producer_key')==plan.get('scope_key')==key
        and plan.get('stage')==spec['stage'] and plan.get('scope_parameters')==params and plan.get('kind')=='analysis'
        and plan.get('pilot') is spec['pilot'] and plan.get('scope_mode')==spec['scope_mode']
        and plan.get('performance_profile') is spec['performance_profile'] and plan.get('endpoint')==ENDPOINT
        and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and type(wall) is int and wall==seconds
        and 0<wall<=spec['wall_max'] and wall%60==0 and type(cap) is int
        and (cap==spec['cap'] if mode=='profile' else (2<<30)<=cap<=(64<<30)),'ONLY_EXACT_SIX_CSV_SCOPE_RESOURCES')
    review=Q.load_ref(plan['root_review_reference'])
    Q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE'
        and review.get('reviewer')=='root','EXACT_SIX_CSV_ROOT_REVIEW')
    for name in REVIEW_FIELDS:Q.need(plan[name]==review[name],'SIX_CSV_ROOT_REVIEW_DIFFERS:'+name)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_SIX_CSV_APPROVED_SOURCE_SET')
    for value in plan['data_references']:body_locator(value)
    body_paths={r['path'] for r in plan['data_references']}
    Q.need(len(body_paths)==len(plan['data_references'])==6 and not any(r['path'] in body_paths for r in
        [*plan['source_references'],*plan['parent_evidence_references']]),'SIX_PAYLOADS_NOT_PRE_FIXTURE_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']]:
        value=Q.normalized(value);Q.verify(value);Q.need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_SIX_CSV_SOURCE_PIN')
        refs[value['path']]=value
    for path in [*(C.HERE/name for name in C.FILES),HERE/'controller.py',HERE/'adapters.py',
                 ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'ALL_ACTUAL_SIX_CSV_AND_V12_SOURCES_APPROVED')
    for name in ('resource_authority_reference','cost_decision_reference','format_authority_reference'):
        Q.need(plan[name] in plan['source_references'],'EXPLICIT_SIX_CSV_AUTHORITY:'+name)
    authority=Q.load_ref(plan['format_authority_reference'])
    Q.need(plan['format_authority_reference']==Q.ref(C.HERE/'format792_authority.json')
        and authority['schema']=='ACTUAL792_SIX_CSV_PHYSICAL_IDENTITY_AUTHORITY_V1' and authority['actual_job_id']=='1884792'
        and [s['source_id'] for s in authority['sources']]==list(C.IDS),'ACTUAL792_EXACT_SIX_CSV_AUTHORITY')
    for name in ('format_receipt_reference','format_plan_reference','format_proof_reference'):
        Q.need(authority[name] in plan['parent_evidence_references'],'ACTUAL792_PARENT_REFERENCE:'+name)
    receipt=Q.load_ref(authority['format_receipt_reference']);old_plan=Q.load_ref(authority['format_plan_reference']);old_proof=Q.load_ref(authority['format_proof_reference'])
    Q.need(receipt['schema']=='MISSING11_IDENTITY_INPUT_FORMAT_PROFILE_RECEIPT_V1'
        and receipt['status']=='FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING' and receipt['job_id']=='1884792'
        and receipt['endpoint']==ENDPOINT and receipt['uid']==UID and receipt['node'] in Q.NODES
        and receipt['plan_reference']==authority['format_plan_reference'] and receipt['startup_proof_reference']==authority['format_proof_reference']
        and old_plan['producer_key']=='moleculenet_missing11_identity_format_probe_alpha_v1' and old_plan['endpoint']==ENDPOINT
        and old_plan['uid']==UID and old_plan['cpus']==16 and old_plan['node']==receipt['node']
        and str(old_proof['job_id'])=='1884792' and old_proof['endpoint']==ENDPOINT and old_proof['uid']==UID
        and old_proof['node']==receipt['node'] and old_proof['plan_reference']==authority['format_plan_reference'],'ACTUAL792_FORMAT_PLAN_PROOF_BINDING')
    accounting=account(plan['format_accounting_reference'],'1884792',plan['parent_evidence_references'])
    Q.need(accounting['actual_parent']['NodeList']==receipt['node'],'FORMAT_PARENT_NODE_ACCOUNTING_MATCH')
    Q.need(receipt['fixtures_reference'] in plan['parent_evidence_references'],'ACTUAL792_EIGHT_FIXTURE_REFERENCE')
    tested=Q.load_ref(receipt['fixtures_reference'])
    Q.need(tested['status']=='PASS' and tested['counts']=={'run':8,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0},'ACTUAL792_EIGHT_PASS_FIXTURES')
    for source in authority['sources']:
        value=source['format_report_reference']
        Q.need(value in plan['source_references'] and any(r['source_id']==source['source_id'] and r['report_reference']==value for r in receipt['reports']),'ACTUAL792_CSV_REPORT_PRODUCER_PIN')
        report=Q.load_ref(value)
        Q.need(report['status']=='CSV_INPUT_METADATA_OBSERVED' and report['error'] is None and report['payload_reference']==source['payload_reference']
            and report['CSV']==source['expected_CSV_summary'] and report['CSV']['record_counts']['physical_data_records']==C.COUNTS[source['source_id']],
            'ACTUAL792_ORIGINAL_HEADER_AND_PHYSICAL_COUNTS')
    Q.need(plan['data_references']==[s['payload_reference'] for s in authority['sources']],'EXACT_SIX_PAYLOADS_IN_FROZEN_IDS_ORDER')
    for value in authority['frozen_helper_source_references']:Q.need(value in plan['source_references'],'EVERY_UNCHANGED_FORMAT_B_OR_IDENTITY_HELPER_REQUIRED')
    if mode=='full':
        Q.need(review.get('actual_profile_identity_quality_and_cost_reviewed') is True and review.get('all_physical_blank_invalid_ID_rows_authorized') is True,'FULL_ACTUAL_PROFILE_ROOT_REVIEW')
        Q.need(plan['accepted_profile_receipt_reference'] in plan['parent_evidence_references'],'ACTUAL_PROFILE_RECEIPT_PARENT')
        profile=Q.load_ref(plan['accepted_profile_receipt_reference'])
        Q.need(profile['schema']=='MOLECULENET_CSV6_IDENTITY_RECEIPT_V1' and profile['mode']=='profile'
            and profile['status']=='SIX_CSV_PROFILE_PHYSICAL_IDENTITY_OBSERVATIONS_COMPLETE' and profile['observed_rows']==C.PROFILE_N
            and profile['scope_parameters']==C.parameters('profile') and profile['pipeline']['observed_rows_by_source']=={k:min(n,10000) for k,n in C.COUNTS.items()}
            and len(profile['pipeline']['actual_nonempty_workers'])==16 and profile['global_identity_or_decontamination_coverage_accepted'] is False
            and profile['format_authority_reference']==plan['format_authority_reference'] and profile['endpoint']==ENDPOINT and profile['uid']==UID
            and profile['full_payload_sha_crc_eof_reverified'] is True and profile['fixtures']['tests_run']==7 and profile['fixtures']['status']=='PASS','ACTUAL_COMPLETE_SIX_CSV_PROFILE_C0_SCOPE')
        for path in (C.HERE/name for name in C.FILES):Q.need(Q.ref(path) in profile['source_references'],'FULL_SAME_ACTUAL_PROFILE_EXECUTION_SOURCES')
        account(plan['accepted_profile_accounting_reference'],profile['job_id'],plan['parent_evidence_references'])
        Q.need(plan['profile_output_budget_reference'] in plan['source_references'],'ROOT_PROFILE_DERIVED_FULL_BUDGET_PIN')
        budget=Q.load_ref(plan['profile_output_budget_reference'])
        Q.need(budget['schema']=='SIX_CSV_IDENTITY_FULL_OUTPUT_BUDGET_V1' and budget['profile_receipt_reference']==plan['accepted_profile_receipt_reference']
            and budget['output_cap_bytes']==cap and budget['wall_seconds']==wall and budget['worst_case_record_output_bound_proven'] is False,'ACTUAL_PROFILE_DERIVED_CAP_WALL_NO_WORST_CASE_CLAIM')
    proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory'])
    Q.need(ROOT/'artifacts' in out.parents and not out.exists(),'NEW_SIX_CSV_OUTPUT_LEAF')
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_SIX_CSV_MAIN_AND_COMPLETE_EIGHT_ARGV')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':plan['data_references'],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':cap,
        'producer_working_directory':str(ROOT/'code'),'proof_schema':spec['proof'],'request_kind':'analysis','pilot':spec['pilot'],
        'scope_key':key,'scope_parameters':params,'stage':spec['stage'],'scope_mode':spec['scope_mode'],
        'performance_profile':spec['performance_profile'],'fixed_archive_authority':{'format_job_id':'1884792','source_payloads':6,
            'source_payload_bytes':19961345,'decoded_bytes':135667631,'physical_records':1162144,
            'processed_rows':params['processed_rows'],'physical_records_are_valid_molecules_claimed':False,'global_release':False}}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    Q.need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'V12_ONLY_EXACT_SIX_CSV_REQUEST_PROTOCOL')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_CURRENT_SIX_CSV_SCOPE7')
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
        'bounded_source_acquisition_scope_only':False,'scientific_population_or_full_SQL_status_coverage_accepted':False,
        'physical_csv_records_are_valid_molecules_claimed':False,'global_identity_decontamination_pool_release_authorized':False}
