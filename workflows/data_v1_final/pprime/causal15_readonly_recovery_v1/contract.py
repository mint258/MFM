"""Exact actual failed1766 authority, deferred first-SHA source locators only."""
import pathlib,stat
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
from workflows.data_v1_final.pprime.causal15_main_v1 import contract as O,io as I
HERE=Q.REPO/'workflows/data_v1_final/pprime/causal15_readonly_recovery_v1'
FILES=('__init__.py','contract.py','io.py','reader.py','run.py','test_v1.py','metadata.py','README.md')
KEY='pprime_causal15_readonly_recovery_v1';MODULE='workflows.data_v1_final.pprime.causal15_readonly_recovery_v1.run'
CAP=512<<20;STAGE='PPRIME_EXISTING1766_CAUSAL15_READONLY_RECOVERY_ZERO_QM'
BASE=O.BASE/'execute15_v1';SCRATCH=pathlib.Path('/tmp/causal15_4521766_qa-08_g8xf0izc')
PARAMETERS={'original_job_id':'4521766','original_parent_state':'FAILED','original_parent_exit_code':'3:0',
    'original_prepare_job_id':'4521765','qa_cases':15,'existing_valid_results':13,'source_result_refs':14,
    'closed_SQLite_sources':14,'qa02_missing_result_recovery':'COMMITTED_RAW_PHASE_ONLY_NO_ORIGINAL_WP5_STATUS_INVENTED',
    'qa08_source':'EXACT_PRESERVED_SCRATCH_WITH_NATIVE_RETURN_OBSERVED_IN_PARTIAL_RESULT',
    'first_source_whole_SHA_after_fixtures':True,'original_SQLite_sidecars_must_be_absent':True,
    'original_data_readonly_new_stable_opaque_copies':True,'maximum_source_raw_bytes_per_call':O.RAW_CAP,
    'new_pure_fixture_methods':3,'all3_before_any_scientific_body':True,'actual_node':'compute-0-13','cpus':16,
    'new_QM_calls':0,'native_invoke_initialize_worker_or_once_write_calls':0,'original_results_or_scratch_deleted':False,
    'original_WP5_status_unknown_cases':['qa-02','qa-08'],'original15FAIL_preserved':True,'scientific_PASS':False,
    'full_or2000_release':'HOLD','budget_basis':'CUMULATIVE_CHARGED_BYTES_NO_TRANSIENT_TREE_SCAN',
    'cost_overrun_action':'REPORT_AND_CONTINUE'}


def meta(ref):Q.need(Q.pin(ref['path'])==ref,'ACTUAL_SMALL_METADATA_PIN');return Q.load(ref['path'])


def unique(refs):
    by={}
    for ref in refs:Q.need(ref['path'] not in by or by[ref['path']]==ref,'CONFLICTING_PIN');by[ref['path']]=ref
    return [by[k] for k in sorted(by)]


def locators(reference):
    obs=meta(reference);Q.need(obs['schema']=='CPU13_PPRIME15_READONLY_RECOVERY_LSTAT_V1' and obs['node']=='compute-0-13'
        and obs['uid']==1278 and obs['original_job_id']=='4521766' and obs['actual_ssh_returncode']==0
        and obs['scientific_body_opened_or_hashed'] is obs['QM_or_native_invoke_or_signal'] is False
        and obs['closed_SQLite_count']==14 and obs['scratch_file_count']==10
        and obs['original_worker_pid_observation']=={'pid':2163802,'exists':False},'ACTUAL_EXACT_CPU13_METADATA_OBSERVER')
    rows=obs['observations'];Q.need(len({r['path'] for r in rows})==len(rows),'UNIQUE_SOURCE_OBSERVATIONS')
    dbs={str(BASE/('qa-%02d'%i)/'all_output_raw.sqlite') for i in range(15) if i!=8};files=[]
    for row in rows:
        p=pathlib.Path(row['path']);Q.need(p.is_absolute() and '..' not in p.parts and row['uid']==1278 and row['body_opened_or_hashed'] is False
            and (str(p) in dbs or p==SCRATCH or SCRATCH in p.parents),'EXACT_OWN_DB_OR_QA08_OBSERVED_SCRATCH_ONLY')
        if stat.S_ISREG(row['mode']):
            Q.need(0<row['bytes']<=O.RAW_CAP,'BOUNDED_EXISTING_OPAQUE_FILE');files.append(row)
        else:Q.need(stat.S_ISDIR(row['mode']),'NO_LINK_OR_SPECIAL_SOURCE')
    Q.need({r['path'] for r in files if r['path'] in dbs}==dbs and len(files)==24,'14_DATABASES_AND10_SCRATCH_FILES')
    return obs,[{'schema':'PPRIME_CAUSAL15_EXISTING_FILE_FIRST_SHA_LOCATOR_V1','authority_reference':reference,
        'path':r['path'],'bytes':r['bytes'],'expected_sha256':None,'hash_basis':'FIRST_ACTUAL_CPU_SHA_AFTER_PURE_FIXTURES_AND_EXACT_LSTAT'} for r in files]


def parents(plan):
    receipt=meta(plan['execution_receipt_reference']);prepared=meta(receipt['prepared_reference']);source=meta(receipt['plan_reference']);proof=meta(receipt['startup_proof_reference'])
    Q.need(receipt['schema']=='PPRIME_CAUSAL15_EXECUTION_RECEIPT_V1' and receipt['status']=='QA_CONSUMED_UNKNOWN_OR_INCOMPLETE_NO_RETRY'
        and receipt['job_id']=='4521766' and len(receipt['results'])==14 and len(receipt['claims'])==15
        and receipt['dispatched_without_return_qa_ids']==['qa-02'] and all(not p['alive'] for p in receipt['process_closure'])
        and receipt['original15FAIL_preserved'] is True and receipt['scientific_PASS'] is False and receipt['full_or2000_release']=='HOLD',
        'REAL_FAILED1766_CONSUMED15_NOT_SUCCESS_OR_RETRY')
    Q.need(prepared['job_id']=='4521765' and prepared['status']=='ACTUAL15_EXACT_INPUTS_PREPARED_ZERO_QM'
        and prepared['plan_reference']==receipt['plan_reference'] and len(prepared['tasks'])==15
        and [r['qa_id'] for r in prepared['tasks']]==['qa-%02d'%i for i in range(15)]
        and proof['uid']==1278 and str(proof['job_id'])=='4521766' and proof['request']['node']=='compute-0-13'
        and proof['request']['scope_key']=='pprime_causal15_main_v1_execute'
        and receipt['plan_reference'] in proof['request']['source_references'],'EXACT_PREPARED15_AND_ORIGINAL_EXECUTION_PROOF')
    account=meta(plan['execution_accounting_reference']);row=I.F.accounting(plan['execution_accounting_reference'],['4521766'])['4521766']
    Q.need(account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and row['state']=='FAILED'
        and row['exit_code']=='3:0' and row['alloc_cpus']==16 and row['node']=='compute-0-13','REAL_FAILED1766_TERMINAL_ACCOUNTING')
    pa=meta(receipt['prepare_accounting_reference']);pr=I.F.accounting(receipt['prepare_accounting_reference'],['4521765'])['4521765']
    Q.need(pa['endpoint']=='202.38.247.57:22' and pa['uid']==1278 and pr['state']=='COMPLETED' and pr['exit_code']=='0:0'
        and pr['alloc_cpus']==16 and pr['node']=='compute-0-13','REAL1765_PREPARE_C0_DISTINCT_FROM_FAILED1766')
    obs,locations=locators(plan['source_lstat_reference']);Q.need(obs['actual_terminal_accounting_reference']==plan['execution_accounting_reference']
        and obs['boot_id']==proof['boot_id'],'OBSERVED_SOURCE_OLD_JOB_BOOT_AND_ACCOUNTING_CHAIN')
    refs=[plan['execution_receipt_reference'],plan['execution_accounting_reference'],account['raw_sacct_reference'],receipt['prepared_reference'],
        receipt['plan_reference'],receipt['startup_proof_reference'],receipt['prepare_accounting_reference'],pa['raw_sacct_reference'],
        receipt['execute_review_reference'],plan['source_lstat_reference'],obs['observer_source_reference']]
    return receipt,prepared,source,proof,obs,locations,unique(refs)
