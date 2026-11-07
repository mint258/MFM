"""Only the two frozen short readonly diagnoses; login never reads scientific bodies."""
import csv,io,re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_queue_v15'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
PKEY='pprime_native72_print_invariant_intervals_alpha_v1';NKEY='moleculenet_csv6_newline_diagnosis_alpha_v1'
PROTOCOLS={PKEY:{'plan':'SECONDARY_NATIVE72_PRINT_INTERVALS_PLAN_V1','proof':'SECONDARY_NATIVE72_PRINT_INTERVALS_STARTUP_V1',
    'stage':'PPRIME_NATIVE72_PRINT_INTERVAL_INVARIANT_DIAGNOSIS','module':'native72_print_intervals_alpha_v1.run',
    'wall':600,'cap':32<<20,'scope_mode':'BOUNDED_READONLY_ANALYSIS'},
 NKEY:{'plan':'SECONDARY_CSV6_NEWLINE_DIAGNOSIS_PLAN_V1','proof':'SECONDARY_CSV6_NEWLINE_DIAGNOSIS_STARTUP_V1',
    'stage':'SIX_CSV_RETAINED_NEWLINE_BYTE_CENSUS','module':'secondary_csv6_newline_diagnosis_v1.run',
    'wall':1800,'cap':64<<20,'scope_mode':'BOUNDED_SIX_CSV_ORIGINAL_BYTES_DIAGNOSIS'}}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')
PARENT_PLAN={'path':str(ROOT/'control/readonly_specs/pprime_native72_readonly_v2/plan.json'),'bytes':19174,'sha256':'03a7ac62de0146d7cca767e9f230f55aaad4dce752b348d77f937d72129a8e84'}
PARENT_PROOF={'path':str(ROOT/'control/secondary_startup/dv1_pprime_native72_readonly_v2_20261026_v1.json'),'bytes':25376,'sha256':'1c4fa302dc3c79abce4afee38a21d9bc9fa7d410bd3a0ddea52e4184f089ccd6'}
PARENT_ACCOUNT={'path':str(ROOT/'control/secondary_cpu_queue/pprime_native72_readonly_v2/accounting_1792992231501031923.json'),'bytes':1667,'sha256':'7cd03b59dc4658d76f8c6496bf388ca511a002d442bc0f2b191a57bd4c1ea9ae'}
PARENT_RAW={'path':str(ROOT/'control/secondary_cpu_queue/pprime_native72_readonly_v2/sacct_1792992231501031923.txt'),'bytes':273,'sha256':'274061d433c8896e8373721c7666093d6b03ee786e1ef9ad082c3ff364ae14f4'}
PARENT_REVIEW={'path':str(ROOT/'control/readonly_specs/pprime_native72_readonly_v2/root_review.json'),'bytes':17284,'sha256':'36fdf790406b04c6a0c0af1ce21bbcfb4a9bc56a3095fb8889fd2e0ae62fc031'}


def body_locator(value):
    Q.need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'PRODUCER_PINNED_DATA_LOCATOR_ONLY')
    Q.literal(value['path'])  # File bodies are not opened, hashed or parsed here.


def actual_account(reference,job,parents):
    Q.need(reference in parents,'ACTUAL_C0_PARENT_ACCOUNTING_REFERENCE')
    value=Q.load_ref(reference);p=value['actual_parent'];raw=value['raw_sacct_reference']
    Q.need(value['query_returncode']==0 and value['uid']==UID and value['endpoint']==ENDPOINT and p['JobIDRaw']==job
        and p['UID']=='1264' and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['AllocCPUS']=='16'
        and p['Partition']=='cpu' and p['NodeList'] in Q.NODES and raw in parents,'EXACT_CPU16_ALPHA_C0_AND_RAW_PARENT')
    rows=list(csv.DictReader(io.StringIO(Q.read_small(Q.verify(raw)).decode()),delimiter='|'));found=[r for r in rows if r.get('JobIDRaw')==job]
    Q.need(len(found)==1 and all(found[0][k]==p[k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and int(p['ElapsedRaw'])>=0 and value['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,'RAW_C0_STATE_AND_ACTUAL_PARENT_COST')
    return value


def pprime(plan):
    from native72_print_intervals_alpha_v1 import contract as C
    Q.need(C.KEY==PKEY and C.MODULE==PROTOCOLS[PKEY]['module'] and plan['scope_parameters']==C.SCOPE and plan['data_references']==C.DATA,'EXACT_FROZEN_PRINT_INTERVAL_SCOPE_AND_TWO_REPORT_LOCATORS')
    for path in (C.HERE/name for name in C.FILES):Q.need(Q.ref(path) in plan['source_references'],'EVERY_FROZEN_PRINT_INTERVAL_SOURCE')
    for value in (C.CONFIG,C.SMALL_SUMMARY,*C.OLD_HELPERS,*C.PREVIOUS_HELPERS):Q.need(value in plan['source_references'],'EVERY_FROZEN_PRECISION_INVARIANT_HELPER_AND_METADATA')
    for value in (C.SMALL_SUMMARY,PARENT_PLAN,PARENT_PROOF,PARENT_ACCOUNT,PARENT_RAW,PARENT_REVIEW):
        Q.need(value in plan['parent_evidence_references'],'ACTUAL1884773_SMALL_METADATA_PLAN_PROOF_C0_RAW_PARENT')
    small=Q.load_ref(C.SMALL_SUMMARY);old=Q.load_ref(PARENT_PLAN);proof=Q.load_ref(PARENT_PROOF);review=Q.load_ref(PARENT_REVIEW)
    Q.need(small['schema']=='PPRIME_NATIVE72_ALPHA_SMALL_DIAGNOSIS_RECEIPT_V2' and small['runtime']['job_id']=='1884773'
        and small['runtime']['uid']==UID and small['runtime']['endpoint']==ENDPOINT and small['runtime']['allocated_cpus']==16
        and small['status']=='FULL_REPORT_AND_SMALL_SUMMARY_WRITTEN' and small['four_fixtures_actual']['status']=='PASS'
        and small['four_fixtures_actual']['tests_run']==small['four_fixtures_actual']['successful_test_count']==4
        and all(small['four_fixtures_actual'][k]==0 for k in ('failure_count','error_count','skipped_count','expected_failure_count','unexpected_success_count'))
        and small['all72_inputs_closed'] is True and small['actual_cases_read']==72 and small['case_read_errors']['count']==0
        and small['case_read_errors']['short_list']==[] and small['case_read_errors']['omitted_from_small_receipt']==0
        and small['original_failure_count']==15 and small['original_15_failures_unchanged'] is True and small['full_report_reference']==C.DATA[0]
        and small['automatic_PASS_or_QM_release'] is False,'ACTUAL_CLOSED72_WITH15FAIL_NOT_SCIENTIFIC_PASS')
    Q.need(old['scope_key']=='pprime_native_precision72_readonly_alpha_v2' and old['endpoint']==ENDPOINT and old['uid']==UID
        and old['node']==small['runtime']['node'] and old['cpus']==16 and old['root_review_reference']==PARENT_REVIEW
        and old['output_directory']==str(Path(C.DATA[0]['path']).parent) and old['startup_proof_path']==PARENT_PROOF['path']
        and all(old['inputs']['evaluation'][k]==C.DATA[1][k] for k in ('bytes','sha256')),'ORIGINAL_DIAGNOSIS_PLAN_OUTPUT_AND_EVALUATION_PIN')
    Q.need(proof['schema']=='SECONDARY_NATIVE72_READONLY_STARTUP_V2' and str(proof['job_id'])=='1884773' and proof['uid']==UID
        and proof['endpoint']==ENDPOINT and proof['node']==small['runtime']['node'] and proof['plan_reference']==PARENT_PLAN
        and proof['root_review_reference']==PARENT_REVIEW and proof['request']['kind']=='analysis' and proof['request']['pilot'] is False
        and proof['request']['cpus']==16 and review['reviewer']=='root' and review['status']=='APPROVED_FOR_EXACT_STAGE','HISTORICAL1884773_PROOF_NEVER_REUSED_AS_CURRENT')
    account=actual_account(PARENT_ACCOUNT,'1884773',plan['parent_evidence_references'])
    Q.need(account['raw_sacct_reference']==PARENT_RAW and account['actual_parent']['NodeList']==small['runtime']['node'],'EXACT1884773_C0_PARENT_NODE_AND_RAW')
    return {'input_reports':2,'original_covariance_FAILs':15,'original_15FAIL_HOLD_preserved':True,'causal_status':'UNKNOWN',
        'fixtures_required_before_reports':11,'source_parent_job_id':'1884773','new_raw_or_QM_UFF_reads':0}


def newline(plan):
    from secondary_csv6_newline_diagnosis_v1 import contracts as C
    from secondary_moleculenet_csv6_identity_v1 import contracts as CSV
    spec=C.MODES['newline_diagnosis']
    Q.need(spec['key']==NKEY and C.MODULE==PROTOCOLS[NKEY]['module'] and plan['mode']=='newline_diagnosis'
        and plan['scope_parameters']==C.parameters('newline_diagnosis'),'EXACT_FROZEN_NEWLINE_DIAGNOSIS_SCOPE')
    for path in [*(C.HERE/name for name in C.FILES),*(C.AUTHORITY_HERE/name for name in CSV.FILES)]:
        Q.need(Q.ref(path) in plan['source_references'],'EVERY_FROZEN_NEWLINE_AND_CSV_HELPER_SOURCE')
    authority_ref=Q.ref(C.AUTHORITY_HERE/'format792_authority.json')
    Q.need(plan['format_authority_reference']==authority_ref and authority_ref in plan['source_references'],'EXACT_FROZEN792_SIX_CSV_AUTHORITY')
    authority=Q.load_ref(authority_ref)
    Q.need(authority['schema']=='ACTUAL792_SIX_CSV_PHYSICAL_IDENTITY_AUTHORITY_V1' and authority['actual_job_id']=='1884792'
        and [s['source_id'] for s in authority['sources']]==list(C.IDS) and plan['data_references']==[s['payload_reference'] for s in authority['sources']],
        'EXACT_SIX_PRODUCER_PAYLOAD_LOCATORS_NO_IDENTITY_OR_ASSAY_BODY_READ')
    for name in ('format_receipt_reference','format_plan_reference','format_proof_reference'):
        Q.need(authority[name] in plan['parent_evidence_references'],'ACTUAL792_PARENT_PLAN_PROOF_OR_RECEIPT')
    receipt=Q.load_ref(authority['format_receipt_reference']);old=Q.load_ref(authority['format_plan_reference']);proof=Q.load_ref(authority['format_proof_reference'])
    Q.need(receipt['schema']=='MISSING11_IDENTITY_INPUT_FORMAT_PROFILE_RECEIPT_V1' and receipt['status']=='FORMAT_METADATA_PROFILE_COMPLETE_IDENTITY_ACCEPTANCE_PENDING'
        and receipt['job_id']=='1884792' and receipt['endpoint']==ENDPOINT and receipt['uid']==UID and receipt['node'] in Q.NODES
        and receipt['plan_reference']==authority['format_plan_reference'] and receipt['startup_proof_reference']==authority['format_proof_reference']
        and old['scope_key']=='moleculenet_missing11_identity_format_probe_alpha_v1' and old['endpoint']==ENDPOINT and old['uid']==UID
        and old['node']==receipt['node'] and old['cpus']==16,'ACTUAL792_COMPLETED_FORMAT_SCOPE_NOT_IDENTITY_ACCEPTANCE')
    Q.need(proof['schema']=='SECONDARY_MISSING11_IDENTITY_FORMAT_PROFILE_STARTUP_V1'
        and proof['uid']==UID and proof['endpoint']==ENDPOINT and str(proof['job_id'])=='1884792' and proof['node']==receipt['node']
        and proof['plan_reference']==authority['format_plan_reference'] and proof['request']['kind']=='analysis'
        and proof['request']['cpus']==16 and proof['request']['pilot'] is False,'HISTORICAL792_PARENT_PROOF_IDENTITY')
    account=actual_account(plan['format_accounting_reference'],'1884792',plan['parent_evidence_references'])
    Q.need(account['actual_parent']['NodeList']==receipt['node'],'ACTUAL792_C0_PARENT_NODE')
    Q.need(receipt['fixtures_reference'] in plan['parent_evidence_references'],'ACTUAL792_EIGHT_FIXTURE_RECEIPT')
    tested=Q.load_ref(receipt['fixtures_reference']);Q.need(tested['status']=='PASS'
        and tested['counts']=={'run':8,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0}
        and tested['source_reference'] in plan['source_references'],'EXACT_ORIGINAL8_FIXTURE_SOURCE_AND_ACTUAL_PARENT_PASS')
    for source in authority['sources']:
        value=source['format_report_reference'];Q.need(value in plan['source_references'] and any(r['source_id']==source['source_id'] and r['report_reference']==value for r in receipt['reports']),'ACTUAL792_SIX_REPORT_PIN_BINDING')
        observed=Q.load_ref(value)
        Q.need(observed['status']=='CSV_INPUT_METADATA_OBSERVED' and observed['error'] is None and observed['payload_reference']==source['payload_reference']
            and observed['CSV']==source['expected_CSV_summary'] and observed['CSV']['record_counts']['physical_data_records']==C.COUNTS[source['source_id']],
            'ORIGINAL792_LITERAL_HEADERS_AND_PHYSICAL_COUNTS')
    for value in authority['frozen_helper_source_references']:Q.need(value in plan['source_references'],'EVERY_FROZEN_FORMAT_AND_CSV_TRANSITIVE_SOURCE_PIN')
    return {'source_parent_job_id':'1884792','input_payloads':6,'payload_bytes':19961345,'decoded_bytes':135667631,
        'fixtures_required_before_payloads':11,'physical_records_are_effective_molecules':False,'source_newline_cause':'UNKNOWN_PENDING_ACTUAL_DIAGNOSIS',
        'blank_or_no_key_rows_removed':False,'key_or_X_or_QM_UFF_calls':0,'global_release':False}


def readonly(input_path,deployment_path,node,seconds,**unused):
    Q.need(deployment_path is None,'TWO_DIAGNOSES_HAVE_NO_DEPLOYMENT_WRAPPER')
    plan=Q.load(input_path);key=plan.get('scope_key');Q.need(key in PROTOCOLS,'V15_ONLY_TWO_FROZEN_READONLY_DIAGNOSES')
    spec=PROTOCOLS[key];refs={}
    Q.need(plan.get('schema')==spec['plan'] and plan.get('producer_key')==key and plan.get('stage')==spec['stage']
        and plan.get('kind')=='analysis' and plan.get('pilot') is False and plan.get('performance_profile') is False
        and plan.get('scope_mode')==spec['scope_mode'] and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID
        and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES and plan.get('cpus')==16
        and plan.get('memory_policy')==POLICY and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds==spec['wall']
        and plan.get('output_cap_bytes')==spec['cap'],'ONLY_EXACT_SHORT_DIAGNOSIS_STAGE_RESOURCES')
    review=Q.load_ref(plan['root_review_reference'])
    Q.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review['status']=='APPROVED_FOR_EXACT_STAGE'
        and review['reviewer']=='root','EXACT_TWO_DIAGNOSES_ROOT_REVIEW')
    for name in REVIEW_FIELDS:Q.need(plan[name]==review[name],'EXACT_DIAGNOSIS_REVIEW_FIELD_DIFFERS:'+name)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_DIAGNOSIS_SOURCE_SET')
    for value in plan['data_references']:body_locator(value)
    paths={r['path'] for r in plan['data_references']}
    Q.need(len(paths)==len(plan['data_references']) and not any(r['path'] in paths for r in [*plan['source_references'],*plan['parent_evidence_references']]),'SCIENTIFIC_REPORTS_AND_PAYLOADS_NEVER_STARTUP_SOURCE_BODY')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']]:
        value=Q.normalized(value);Q.verify(value);Q.need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_DIAGNOSIS_SOURCE_PIN')
        refs[value['path']]=value
    for path in (HERE/'controller.py',HERE/'adapters.py',ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py'):
        Q.need(Q.ref(path) in plan['source_references'],'EXACT_V15_AND_BASE_SOURCE_PINS')
    for name in ('resource_authority_reference','cost_decision_reference'):Q.need(plan[name] in plan['source_references'],'EXPLICIT_ACTUAL_DIAGNOSIS_AUTHORITY')
    authority=pprime(plan) if key==PKEY else newline(plan)
    proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory']);Q.need(ROOT/'artifacts' in out.parents and not out.exists(),'NEW_DIAGNOSIS_OUTPUT_LEAF')
    argv=[plan['python'],'-B','-m',spec['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_DIAGNOSIS_PRIMARY_AND_ALL_EIGHT_ARGV')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':plan['data_references'],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':spec['cap'],'producer_working_directory':str(ROOT/'code'),
        'proof_schema':spec['proof'],'request_kind':'analysis','pilot':False,'scope_key':key,'scope_parameters':plan['scope_parameters'],
        'stage':spec['stage'],'scope_mode':spec['scope_mode'],'performance_profile':False,'fixed_archive_authority':authority}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    Q.need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] is False and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'] is False,
        'V15_ONLY_TWO_EXACT_READONLY_DIAGNOSIS_REQUESTS')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_CURRENT_DIAGNOSIS_SCOPE7')
    return {'schema':adapter['proof_schema'],'endpoint':ENDPOINT,'uid':UID,'node':request['node'],'boot_id':probe['boot_id'],
        'job_id':str(jid),'observed_unix_seconds':probe['observed_unix_seconds'],'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
        'plan_reference':adapter['producer_plan_reference'],'root_review_reference':adapter['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,'scope_key':adapter['scope_key'],'stage':adapter['stage'],
        'scope_mode':adapter['scope_mode'],'performance_profile':False,'bounded_readonly_scope_only':True,'bounded_source_acquisition_scope_only':False,
        'scientific_population_or_full_SQL_status_coverage_accepted':False,'original15FAIL_or_HOLD_or_unknown_cause_revised':False,
        'blank_or_no_key_rows_claimed_as_effective_molecules':False,'global_release_authorized':False}
