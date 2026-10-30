"""Only actual full cache plus final Common/D5 may define fitting population."""
import re
from pathlib import Path
from workflows.data_v1_final.labels.normalization_typed_cache_v1.contract import need,reference
from workflows.data_v1_final.execution.cpu_analysis_day_v2 import contract as A
RUN=A.ROOT;REPO=A.REPO;HERE=REPO/'workflows/data_v1_final/labels/common_train_normalization_day_v1'
KEY='common_train_normalization_day_v1';MODULE='workflows.data_v1_final.labels.common_train_normalization_day_v1.run'
SCHEMA='COMMON_TRAIN_NORMALIZATION_DAY_PLAN_V1'
FILES=('__init__.py','contract.py','bindings.py','io.py','memory.py','authority.py','eligibility.py','reader.py','statistics.py','audit.py','run.py','metadata.py','source_inverse.py','test_boundaries.py','inverse_rules.json','README.md')
meta=A.meta
COUNTS={'records':11231854,'molecules':1220466,'task_rows':157245956,'fields':146,'groups':171}
PARENTS=('full_cache','common','D5')

def actual(parent):
    """No old16 fiction: actual allocated CPU count is copied from its own proof."""
    for k in ('manifest','proof','accounting','raw'):A.O.pin(parent[k])
    proof=meta(parent['proof']);acct=meta(parent['accounting']);jid=str(proof['job_id']);req=proof['request']
    need(acct['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and acct['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
         and acct['endpoint']=='202.38.247.57:22' and acct['uid']==1278 and acct['query_returncode']==0
         and acct['raw_sacct_reference']==parent['raw'],'ACTUAL_MAIN_C0_RAW_ACCOUNT_CHAIN')
    rows=[r for r in acct['parents'] if str(r['job_id'])==jid]
    need(len(rows)==1 and rows[0]['state']=='COMPLETED' and rows[0]['exit_code']=='0:0'
         and type(rows[0]['alloc_cpus'])is int and rows[0]['alloc_cpus']==req['cpus']>=16,'REAL_ACTUAL_C0_ALLOCATION_NOT_TIMEOUT_OR_SOURCE')
    raw=A.O.pin_bytes(parent['raw'],A.Q.read_small).decode('utf-8-sig').splitlines();head=raw[0].split('|')
    rr=[dict(zip(head,line.split('|'))) for line in raw[1:] if line.split('|')[0]==jid]
    need(len(rr)==1 and rr[0]['UID']=='1278' and rr[0]['State']=='COMPLETED' and rr[0]['ExitCode']=='0:0'
         and rr[0]['AllocCPUS']==str(req['cpus']),'RAW_C0_PARENT_IDENTITY')
    need(meta(proof['request_reference'])==req and req['producer_plan_reference'] in req['source_references'],'PARENT_REQUEST_PROOF_PLAN_PIN')
    return proof

def release(obj):
    need(obj['schema']=='ROOT_FINAL_COMMON_TRAIN_NORMALIZATION_INPUT_RELEASE_V1' and obj['status']=='APPROVED_ACTUAL_INPUTS_FOR_NUMERIC_AUDIT_AND_FIT'
         and obj['reviewer']=='root' and set(obj['actual_parents'])==set(PARENTS),'ROOT_ACTUAL_FULL_CACHE_COMMON_D5_RELEASE_REQUIRED')
    need(obj['final_Common_population_accepted'] is True and obj['ROUTINE_is_whole_VAL'] is True
         and obj['D5_base_and_all_actual_direct_children_exclusion_accepted'] is True
         and obj['source_cache_all_roles_and_values_preserved'] is True
         and obj['no_UNKNOWN_or_old_TIMEOUT_promoted'] is True and obj['Pprime_formal_statistics_released'] is False,
         'REAL_FINAL_POPULATION_AND_DIAGNOSTIC_NOT_PROVISIONAL_OR_SOURCE')
    for p in obj['actual_parents'].values():actual(p)
    fs=obj['field_scope'];active=fs['active_field_ids'];closed=fs['closed_exposure_field_ids']
    need(fs['applicability_rule']=='ORIGINAL_ENABLED_FIELD_OWN_TASK_ALL_CANONICAL_RECORDS'
         and fs['unknown_record_applicability_fields']==[] and all(type(i)is int for i in active+closed)
         and len(active)==len(set(active)) and len(closed)==len(set(closed)) and not set(active)&set(closed)
         and set(active)|set(closed)==set(range(146)),'EXACT146_ORIGINAL_TASK_SCOPES_NO_NA_REMOVED_UNRELATED_TASK_OR_UNKNOWN_SCOPE')
    reference(fs['source_field_map_reference'])
    if closed:
        er=meta(fs['closed_exposure_review_reference'])
        need(er['schema']=='ROOT_EXACT_FIELD_EXPOSURE_SCOPE_REVIEW_V1' and er['status']=='ROOT_CLOSED_EXPOSURE_FIELDS_FOR_RELEASE'
          and er['reviewer']=='root' and er['field_map_reference']==fs['source_field_map_reference'] and er['closed_field_ids']==closed,
          'REAL_EXPOSURE_SCOPE_DECISION_NOT_QUALITY_WAIVER_OR_MISSING_VALUE_INFERENCE')
    for r in obj['accepted_parent_review_references']:meta(r)
    need(obj['accepted_parent_review_references'] and obj['cache_transitive_output_origins'],'ACTUAL_INDEPENDENT_PARENT_ACCEPTANCE_AND_CLOSED_CACHE_OUTPUT_ROOTS')
    for o in obj['cache_transitive_output_origins']:
        need(Path(o['output_root']).is_absolute() and o['manifest_reference'] in obj['accepted_cache_manifest_references']
             and o['origin_type'] in ('ACTUAL_C0_BATCH','ACTUAL_C0_DAY_OUTPUT','TIMEOUT_ADOPTED_CLOSED_WINDOWS'),
             'EXACT_ACCEPTED_CACHE_ORIGIN_NO_DYNAMIC_OLD_BOOK_ADOPTION')
        reference(o['manifest_reference'])
        if o['origin_type']=='TIMEOUT_ADOPTED_CLOSED_WINDOWS':
            need(o['old_parent_state']=='TIMEOUT' and o['actual_inventory_C0_reference'] and o['actual_seed_C0_reference']
                 and o['root_adoption_reference'],'KEEP_OLD_TIMEOUT_AND_REAL_ADOPTION_CHAIN')
    return obj

def scope(p):
    return {'purpose':'FINAL_COMMON_EFFECTIVE_TRAIN_COMPONENT_STATISTICS_AND_ALL_POPULATION_GUIDE1_5',
      'input_release_reference':p['input_release_reference'],'authority':p['authority'],'coverage_reference':p['coverage_reference'],
      'd5_components_acceptance_reference':p['d5_components_acceptance_reference'],'geometry_source':'pm7','label_group':'P_D',
      'field_scope':p['field_scope'],
      'requested_cpus':p['requested_cpus'],'wall_seconds':86400,'softwall_drain_seconds':900,'whole_output_cap_bytes':p['whole_output_cap_bytes'],
      'TSQR_chunk':256,'logical_group_count':171,'QR_reduction':'ORIGINAL_ORDERED_LEFT_FOLD','quality_new_mask_fraction':.01,
      'independent_numeric_replay_required':True,'whole_population_raw_mask_parity_required':True,
      'new_QM_UFF_calls':0,'one_actual_parent_no_child_Slurm':True,'physical_joint_policy_pending':True,'Pprime_pending':True}

def plan(p):
    need(p['schema']==SCHEMA and p['scope_key']==KEY and p['status']=='EXECUTABLE_ACTUAL_PARENTS_BOUND'
         and type(p['requested_cpus'])is int and p['requested_cpus']>=16 and p['wall_seconds']==86400
         and p['softwall_drain_seconds']==900,'ONE_REAL_DAY_EXACT_FINAL_COMMON_INPUT_PLAN')
    need(p['geometry_source']=='pm7' and p['label_group']=='P_D','PM7_P_D_ONLY_NOT_PPRIME_SUBSTITUTION')
    need(all(type(p[k])is int and p[k]>=0 for k in ('eligibility_cap_bytes','statistics_cap_bytes','audit_cap_bytes','spill_cap_bytes','admin_cap_bytes'))
         and type(p['whole_output_cap_bytes'])is int and 8<<30<=p['whole_output_cap_bytes']<=512<<30
         and sum(p[k] for k in ('eligibility_cap_bytes','statistics_cap_bytes','audit_cap_bytes','spill_cap_bytes','admin_cap_bytes'))==p['whole_output_cap_bytes'],
         'EXPLICIT_WHOLE_FINITE_COMPONENT_CAPS_COUNTED_ONCE')
    need(type(p['audit_group_cap_bytes'])is int and 128<<20<=p['audit_group_cap_bytes']<=p['audit_cap_bytes']
         and p['admin_cap_bytes']>=128<<20,'REAL_COMPLETE_GROUP_AND_OBSERVER_ADMIN_CAPS')
    need(p['TSQR_chunk']==256 and p['QR_reduction']=='ORIGINAL_ORDERED_LEFT_FOLD' and p['quality_new_mask_fraction']==.01
         and p['independent_numeric_replay_required'] is True and p['new_QM_UFF_calls']==0
         and p['raw_source_audit_seed']==20261025 and p['raw_source_audit_basis_points']==100,'UNCHANGED_MATH_THRESHOLDS_1PCT_AUDIT_AND_SEED')
    need(p['scope_parameters']==scope(p),'EXACT_PRODUCER_SCOPE_DICTIONARY')
    for r in p['source_references']:A.O.pin(r)
    for r in p['data_references']:reference(r)
    need(not {r['path'] for r in p['source_references']}&{r['path'] for r in p['data_references']},'LARGE_DATA_NOT_SMALL_SOURCE')
    need(set(p['authority'])=={'common','roles','geometry_map','diagnostic'},'REAL_COMMON_ROLES_D5_MAP_DIAGNOSTIC')
    need(Path(p['output_directory']).parent==RUN/'artifacts/labels/source_status_v1/common_train_normalization_day_v1','FRESH_THIS_PRODUCER_OUTPUT_ONLY')
    return p

def logical(groups):
    need(len(groups)==171 and [g['group_index'] for g in groups]==list(range(171))
         and len({g['source_job_id'] for g in groups})==171,'EXACT_ORIGINAL171_GROUPS_NOT_WORKER_OR_PART_BASED')
    return groups

def unique(refs):
    out={}
    for r in refs:
        r=reference(r,source=r.get('bytes')==0)
        need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_INPUT_REFERENCE');out[r['path']]=r
    return list(out.values())
