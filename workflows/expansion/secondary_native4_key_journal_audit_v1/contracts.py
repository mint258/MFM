"""Single producer-pinned closed journal, exact actual856 parent metadata."""
import re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_moleculenet_csv6_identity_v1.guard import account
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_native4_key_journal_audit_v1'
FILES=('__init__.py','contracts.py','guard.py','reducer.py','run.py','test_v1.py','README.md')
OLD=ROOT/'code/secondary_moleculenet_native4_identity_v1'
OLD_FILES=('__init__.py','contracts.py','guard.py','native.py','run.py','test_v1.py','README.md','authority792.json')
KEY='moleculenet_native4_existing_key_journal_audit_alpha_v1';MODULE='secondary_native4_key_journal_audit_v1.run'
PLAN='SECONDARY_NATIVE4_KEY_JOURNAL_AUDIT_PLAN_V1';PROOF='SECONDARY_NATIVE4_KEY_JOURNAL_AUDIT_STARTUP_V1'
STAGE='NATIVE4_CLOSED3195_KEY_RESULTS_ZERO_PARSE_CAUSE_AUDIT';SCOPE='ONE_CLOSED_JOURNAL_NO_NEW_GRAPH_OR_IDENTITY_COMPUTATION'
CAP=2<<30;WALL=600;LINE_CAP=16<<20
COUNTS={'qm8_sdf':1000,'pdbbind_core':195,'pdbbind_general':1000,'pdbbind_refined':1000}
KEY_COUNTS={'qm8_sdf':999,'pdbbind_core':184,'pdbbind_general':57,'pdbbind_refined':79}
UNKNOWN_COUNTS={'qm8_sdf':1,'pdbbind_core':11,'pdbbind_general':943,'pdbbind_refined':921}
JOURNAL={'path':str(ROOT/'artifacts/moleculenet_native4_identity_profile_v1/v1/key_events.jsonl'),'bytes':13613492,
    'sha256':'52bf49f849c51850a245cdcdc1fdb17e9c1f46c17dd34b7dbe3d30c42f08bbb7'}
PARAMETERS={'producer_job':'1884856','producer_elapsed_seconds':677,'producer_allocated_cpus':16,'selected_by_source':COUNTS,
    'producer_any_observed_full_key_union_counts':KEY_COUNTS,'producer_selected_has_unknown_counts':UNKNOWN_COUNTS,
    'input_journal_files':1,'input_journal_bytes':JOURNAL['bytes'],'events':6390,'source_events':3195,'result_events':3195,
    'maximum_pending_pairs':32,'source_before_result_and_literal_source_pair_equality':True,'unique_physical_selected_ordinals':True,
    'complete_current_SHA_same_FD_fstat_EOF':True,'new_pure_methods':3,'all3_before_DATA_and_Budget':True,
    'native_keys_source_variant_keys_union_unknowns_and_errors_separate_axes':True,'cause_classification':'ONLY_RECORDED_EXPLICIT_TOKENS_ELSE_UNKNOWN_SUBPHASE',
    'maximum_example_pairs_per_source_axis_cause':3,'examples_are_DATA_not_summary_SMILES':True,'same_pair_example_persisted_once':True,
    'EOF_no_delimiter_candidate_is_proven_cause':False,'boundary_flag_changed':False,'new_SDF_MOL2_parses':0,
    'new_full_key_generation':0,'new_network_UFF_QM_calls':0,'old_fixtures_reexecuted':False,'old_results_or_kwargs_modified':False,
    'allocated_cpus':16,'reader_processes':1,'whole_output_cap_bytes':CAP,'wall_seconds':WALL,'Budget':'DIRECT_UNCHANGED_CSV6_BUDGET',
    'original_UNKNOWN_is_graph_unavailable_or_profile_ACCEPTANCE':False,'automatic_policy_full_pool_decontamination_release':False,
    'cost_overrun_action':'REPORT_AND_CONTINUE'}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def unique(refs):
    result={}
    for r in refs:Q.normalized(r);Q.need(r['path'] not in result or result[r['path']]==r,'CONFLICTING_SMALL_SOURCE_PIN');result[r['path']]=r
    return [result[k] for k in sorted(result)]


def small_parent(ref,*,receipt=False):
    Q.normalized(ref);p=Q.literal(ref['path'])
    Q.need(0<ref['bytes']<=2<<20 and (p==ROOT/'artifacts/moleculenet_native4_identity_profile_v1/v1/receipt.json' if receipt else ROOT/'control' in p.parents),
        'ONLY_FIXED_RECEIPT_OR_BOUNDED_CONTROL_METADATA_NOT_A_BODY_ALIAS')
    return ref


def inputs(plan):
    rr=plan['native_profile_receipt_reference'];ar=plan['native_profile_accounting_reference'];parents=plan['parent_evidence_references']
    small_parent(rr,receipt=True);small_parent(ar)
    Q.need(rr in parents and ar in parents and rr['path']==str(ROOT/'artifacts/moleculenet_native4_identity_profile_v1/v1/receipt.json'),
        'ONLY_REAL856_SMALL_RECEIPT_NOT_A_SCIENTIFIC_JOURNAL')
    r=Q.load_ref(rr);Q.need(r['schema']=='SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_RECEIPT_V1'
        and r['status']=='ALL_PHYSICAL_NATIVE_CONTEXT_AND_BOUNDED_KEYS_RECORDED_UNKNOWNS_RETAINED'
        and r['job_id']=='1884856' and r['endpoint']==Q.ENDPOINT and r['uid']==1264 and r['node']=='compute-0-6'
        and r['scope_key']=='moleculenet_native4_identity_profile_alpha_v1' and r['full_or_pool_or_decontamination_release'] is False,
        'ACTUAL856_CLOSED_PROFILE_IS_NOT_SCIENTIFIC_ACCEPTANCE')
    p=r['profile'];Q.need(p['actual_profile_counts']==COUNTS and p['selected_rows_with_unknown_by_source']==UNKNOWN_COUNTS
        and p['selected_rows_with_observed_full_keys_by_source']==KEY_COUNTS and p['full_identity_or_pool_release'] is False
        and p['key_result_journal_reference']==JOURNAL and plan['data_references']==[JOURNAL],'EXACT_SINGLE_PRODUCER_PINNED_CLOSED_JOURNAL')
    fx=r['fixtures'];Q.need(fx['tests_run']==3 and all(fx[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL_OLD3_PASS_REFERENCED_NOT_REEXECUTED')
    for ref in (r['plan_reference'],r['startup_proof_reference']):small_parent(ref);Q.need(ref in parents,'ACTUAL856_PLAN_PROOF_PARENT')
    op=Q.load_ref(r['plan_reference']);s=Q.load_ref(r['startup_proof_reference'])
    Q.need(s['endpoint']==Q.ENDPOINT and s['uid']==1264 and str(s['job_id'])=='1884856' and s['node']==r['node']
        and s['plan_reference']==r['plan_reference'] and s['scope_key']==op['scope_key']==r['scope_key']
        and op['scope_parameters']==r['scope_parameters'] and op['pilot'] is True and op['performance_profile'] is True
        and s['request']['kind']=='analysis' and s['request']['pilot'] is True and s['request']['cpus']==16,'REAL_ALPHA856_ORIGINAL_PLAN_PROOF')
    declared={v['path']:{k:v[k] for k in ('path','bytes','sha256')} for v in s['source_target_verification']}
    Q.need(declared.get(r['plan_reference']['path'])==r['plan_reference'],'ORIGINAL_PLAN_ATTESTED_BY856_PROOF')
    for name in OLD_FILES:
        ref=Q.ref(OLD/name);Q.need(ref in op['source_references'] and ref in plan['source_references'] and declared.get(ref['path'])==ref,
            'ALL_ORIGINAL_NATIVE4_BYTES_UNMODIFIED_SOURCE_PROVENANCE')
    accounting=Q.load_ref(ar);small_parent(accounting['raw_sacct_reference'])
    a=account(ar,'1884856',parents);Q.need(a['actual_parent']['ElapsedRaw']=='677' and a['allocated_core_seconds_observed']==10832,'REAL856_677SECONDS_AND10832CORESECONDS')
    populations={v['source_id']:v['native_record_counts']['SDF'] for v in r['projection']}
    Q.need(set(populations)==set(COUNTS) and all(type(n) is int and n>=COUNTS[k] for k,n in populations.items()),'ACTUAL_FULL_SOURCE_POPULATIONS_FROM856_NOT_NEW_SAMPLE')
    return r,populations
