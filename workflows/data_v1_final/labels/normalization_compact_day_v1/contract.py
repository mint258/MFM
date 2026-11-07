"""Day packing is an execution change; mathematical groups and old history stay."""
import hashlib,json,os
from pathlib import Path
from workflows.data_v1_final.labels.normalization_typed_cache_v1.contract import need,reference
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import contract as OLD,metadata as M
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import contract as A
RUN=OLD.RUN;REPO=OLD.REPO;HERE=REPO/'workflows/data_v1_final/labels/normalization_compact_day_v1'
KEY='normalization_compact_day_v1';MODULE='workflows.data_v1_final.labels.normalization_compact_day_v1.run';SCHEMA='COMPACT_NUMERIC_DAY_PLAN_V1'
FILES=('__init__.py','contract.py','io.py','memory.py','lineage.py','project.py','coverage.py','statistics.py','run.py','metadata.py','source_inverse.py','test_boundaries.py','inverse_rules.json','README.md','recovery.py','prior_hash_stage.py')
meta=A.meta

def plan(p):
    need(p['execution_mode'] in ('PROJECT_AND_COVERAGE_ONLY','PROVISIONAL_SOURCE_TRAIN_DESCRIPTIVE_REVIEWED'),'FINAL_COMMON_STATS_NONEXECUTABLE_UNTIL_REAL_COMMON_D5_MASK_NATIVE_JOINT_RELEASE')
    need(p['schema']==SCHEMA and p['scope_key']==KEY and p['wall_seconds']==86400 and p['softwall_drain_seconds']==900
        and type(p['requested_cpus'])is int and p['requested_cpus']>=16,'EXACT_FINITE_REAL_ANALYSIS_DAY_CPUS')
    keys=('projection_cap_bytes','coverage_cap_bytes','statistics_cap_bytes')
    need(all(type(p[k])is int and p[k]>=0 for k in keys) and type(p['whole_output_cap_bytes'])is int
        and sum(p[k] for k in keys)==p['whole_output_cap_bytes'] and p['whole_output_cap_bytes']<=512<<30
        and p['projection_cap_bytes']>=8<<30 and p['coverage_cap_bytes']>=2<<30 and (p['statistics_cap_bytes']==0 if p['execution_mode']=='PROJECT_AND_COVERAGE_ONLY' else p['statistics_cap_bytes']>=2<<30),'ROOT_FINITE_FULL_DAY_COMPONENT_CAPS_NO_OLD8GIB_REUSE')
    need(p['new_QM_UFF_calls']==0 and p['final_Common_D4_authorized'] is False and p['TSQR_chunk']==256
        and p['QR_reduction']=='ORIGINAL_ORDERED_LEFT_FOLD' and p['quality_new_mask_fraction']==.01
        and p['cache_preserves_all_roles'] is True and p['statistics_fit_role']=='TRAIN_ONLY','NO_QUALITY_ROLE_MATHEMATICAL_OR_NATIVE_CHANGE')
    for r in p['data_references']:reference(r)
    for r in p['source_references']:A.O.pin(r)
    need(not {r['path'] for r in p['data_references']}&{r['path'] for r in p['source_references']},'DAY_DATA_NOT_SOURCE')
    need(p['scope_parameters']==scope(p),'PLAN_DERIVED_EXACT_SCOPE_PARAMETERS')
    if p.get('failed_prefix_recovery_reference'):
        from . import recovery
        recovery.authority(p['failed_prefix_recovery_reference'])
        need(p['execution_mode']=='PROJECT_AND_COVERAGE_ONLY','ONLY_EXACT_FAILED_PREFIX_PROJECT_COVERAGE_RECOVERY')
        if p.get('prior_hash_stage_reference'):
            from . import prior_hash_stage
            prior_hash_stage.authority(p['prior_hash_stage_reference'],p['failed_prefix_recovery_reference'])
        else:need(p['requested_cpus']==64,'ORIGINAL_FIRST_HASH_RECOVERY_REMAINS_EXACT64')
    return p

def scope(p):
    value={'dataset':'PM7_P_D_NUMERIC_VIEW','execution_mode':p['execution_mode'],'requested_cpus':p['requested_cpus'],'wall_seconds':86400,'softwall_drain_seconds':900,
      'whole_output_cap_bytes':p['whole_output_cap_bytes'],'projection_cap_bytes':p['projection_cap_bytes'],'coverage_cap_bytes':p['coverage_cap_bytes'],
      'statistics_cap_bytes':p['statistics_cap_bytes'],'logical_group_plan_authority_reference':p['logical_group_plan_authority_reference'],
      'single_real_parent_no_child_Slurm':True,'TSQR_chunk':256,'ordered_left_fold':True,'quality_new_mask_fraction':.01,'new_QM_UFF_calls':0,'final_Common_D4':False}
    if p.get('failed_prefix_recovery_reference'):value.update(failed_prefix_recovery_reference=p['failed_prefix_recovery_reference'],
      recovery_old_job_id='4524575',recovery_old_state='FAILED',recovery_old_core_seconds=603392,
      readonly_failed_prefix_first_whole_SHA_then_original_typed_readback=True,no_reprojection_of_verified_old_intervals=True)
    if p.get('prior_hash_stage_reference'):value.update(prior_hash_stage_reference=p['prior_hash_stage_reference'],
      reuse_complete_actual_C0_hash_stage_only_current_FD_unchanged=True,original_typed_readback_and_quality_still_required=True)
    return value

def sources(cfg):
    refs=M.sources(cfg)
    refs.extend(M.M.pin(HERE/n) for n in FILES)
    refs.extend(M.M.pin(p) for p in A.sources())
    refs.extend([M.M.pin(REPO/'tools/check_repository.py'),M.M.pin(REPO/'docs/SOURCE_MANIFEST.json')])
    from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as G
    refs.append(M.M.pin(REPO/G.SOURCE_RELATIVE_PATH))
    return M.M.unique(refs)

def actual_day(parent):
    """Small real day closure/account authority. Numeric manifests remain DATA."""
    for k in ('manifest','proof','accounting','raw'):A.O.pin(parent[k])
    m=meta(parent['manifest']);proof=meta(parent['proof']);a=meta(parent['accounting']);req=proof['request'];jid=str(proof['job_id'])
    need(m['schema']=='COMPACT_NUMERIC_DAY_PARENT_RECEIPT_V1' and m['job_id']==jid and m['status'] in ('DAY_CLEAN_CHECKPOINTS_PENDING','EXACT_ALL_SOURCE_NUMERIC_CACHE_COMPLETE_FINAL_COMMON_STATISTICS_PENDING','SOURCE_TRAIN_DESCRIPTIVE_COMPLETE_NOT_D4')
        and m['held'] is False and m['errors']==[] and m['quality_hold_fields']==[] and m['UNKNOWN_promoted'] is False,'ACTUAL_CLEAN_DAY_ONLY_NO_AUTORETRY_HOLD')
    need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and a['endpoint']=='202.38.247.57:22'
        and a['query_returncode']==0 and a['uid']==1278 and a['raw_sacct_reference']==parent['raw'],'REAL_MAIN_DAY_RAW_ACCOUNT_CHAIN')
    rows=[r for r in a['parents'] if str(r['job_id'])==jid]
    need(len(rows)==1 and rows[0]['state']=='COMPLETED' and rows[0]['exit_code']=='0:0' and type(rows[0]['alloc_cpus'])is int
        and rows[0]['alloc_cpus']==req['cpus']>=16,'ACTUAL_DAY_CPU_C0_NOT_FAKE16')
    raw=A.O.pin_bytes(parent['raw'],A.Q.read_small).decode('utf-8-sig').splitlines();head=raw[0].split('|')
    records=[dict(zip(head,line.split('|'))) for line in raw[1:] if line.split('|')[0]==jid]
    need(len(records)==1 and records[0]['UID']=='1278' and records[0]['AllocCPUS']==str(req['cpus']) and records[0]['State']=='COMPLETED' and records[0]['ExitCode']=='0:0','EXACT_DAY_RAW_ACCOUNT_ROW')
    need(req['schema']==A.REQUEST and req['scope_key']==KEY and req['kind']=='analysis' and meta(proof['request_reference'])==req
        and req['execution_argv']==[A.PY,'-B','-m',MODULE,'--plan',m['plan_reference']['path'],'--startup-proof',parent['proof']['path']]
        and req['producer_plan_reference']==m['plan_reference'],'ACTUAL_SINGLE_DAY_PRIMARY_ALL_ARGV_SOURCE_PLAN')
    p=plan(meta(m['plan_reference']));need(p['output_directory']==str(Path(parent['manifest']['path']).parent),'ACTUAL_DAY_OUTPUT_BINDING')
    r=meta(parent['root_limited_acceptance_review_reference']);need(r['schema']=='ROOT_ACTUAL_COMPACT_DAY_CHECKPOINT_ACCEPTANCE_V1'
        and r['status']=='APPROVED_ACTUAL_C0_CLEAN_CHECKPOINTS_NOT_D4' and r['reviewer']=='root' and r['actual_parent']=={k:parent[k] for k in ('manifest','proof','accounting','raw')},'EXPLICIT_ACTUAL_DAY_CHECKPOINT_ADOPTION')
    return m

def advance(sources,prior,windows):return OLD.advance_cursors(sources,prior,windows)

def exact_logical_groups(groups):
    need(len(groups)==171 and len({g['source_job_id'] for g in groups})==171,'EXACT_FROZEN171_OWNER_GROUPS_NOT_PHYSICAL_OR_CPU_GROUPS')
    need([g['group_index'] for g in groups]==list(range(171)),'ORIGINAL_GROUP_LIST_ORDER')
    return groups
