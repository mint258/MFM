"""Explicit independent technical reprojection authority; no old-book acceptance."""
import math
from pathlib import Path
from workflows.data_v1_final.labels.normalization_typed_cache_v1.contract import reference,need
from workflows.data_v1_final.labels.full_projection_v1.control import source_contract
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=REPO/'workflows/data_v1_final/labels/normalization_compact_runtime_v3'
SCHEMA='COMPACT_D4_NUMERIC_VIEW_CONFIG_V3';REVIEW='ROOT_COMPACT_NUMERIC_TECHNICAL_REPROJECTION_REVIEW_V1'
BATCH='COMPACT_NUMERIC_SOURCE_BATCH_V1';COVERAGE='COMPACT_NUMERIC_ORIGINAL_SOURCE_COVERAGE_V1'
FILES=('__init__.py','contract.py','codec.py','bindings.py','project.py','runtime.py','run.py','coverage.py','reader.py','statistics.py','metadata.py','source_inverse.py','test_boundaries.py','README.md')
KEYS={'project':'compact_numeric_original_source_project_v3','coverage':'compact_numeric_original_source_coverage_v3','statistics':'compact_numeric_provisional_train_statistics_v3'}
COUNTS={'canonical_records':11231854,'canonical_molecules':1220466,'task_slots':14,'label_files':2024,'base_files':184,'label_physical_rows':157254650,'base_physical_rows':11232475,'label_shadow_rows':8694,'base_shadow_rows':621}


def validate_config(cfg):
    need(cfg['schema']==SCHEMA and cfg['stage'] in KEYS and cfg['scope_key']==KEYS[cfg['stage']], 'EXACT_COMPACT_STAGE_CONFIG')
    need(cfg['codec_schema']=='COMPACT_TYPED_BINARY_JSON_V3' and cfg['row_size_rule']=='RAW_BINARY_FRAMED_BYTES_V3','EXPLICIT_V3_BINARY_ROW_IO_POLICY')
    need(cfg['mode'] in ('pilot512','full') and cfg['workers']==16 and cfg['geometry_source']=='pm7'
      and cfg['final_Common_D4'] is False and cfg['new_UFF_QM_calls']==0 and cfg['old_books_modified'] is False,'SOURCE_PM7_VIEW_ONLY_NOT_COMMON_OR_PPRIME')
    need(cfg['row_serialized_cap_bytes']==64<<20 and cfg['worker_rss_stop_bytes']==3<<30 and cfg['typed_part_cap_bytes']==128<<20
      and cfg['max_physical_window_rows']==4096 and cfg['window_soft_target_bytes']==32<<20,'FROZEN_BOUNDED_VIEW_LIMITS')
    need(type(cfg['whole_output_cap_bytes']) is int and 2<<30<=cfg['whole_output_cap_bytes']<=128<<30
      and type(cfg['wall_seconds']) is int and 600<=cfg['wall_seconds']<=172800,'EXPLICIT_FINITE_OUTPUT_AND_MAX48H_NOT_FORECAST')
    if cfg['stage']=='project':need(cfg['whole_output_cap_bytes']>=8<<30,'ATOMIC16_WORKER_TICKET_WAVE_REQUIRES_AT_LEAST8GIB_PROJECT_CAP')
    if cfg['mode']=='full':reference(cfg['logical_group_plan_authority_reference'],source=True)
    else:need(cfg['logical_group_plan_authority_reference'] is None,'PILOT_NOT_FAKE_FULL_AUTHORITY')
    need(cfg['quality_new_mask_fraction']==.01 and cfg['TSQR_chunk']==256 and cfg['QR_reduction']=='ORIGINAL_ORDERED_LEFT_FOLD','NO_NEW_NUMERICAL_OR_QUALITY_CONVENTION')
    if cfg['stage']=='statistics':
        need(cfg['statistics_purpose'] in ('legacy512','diagnostic_median_MAD','element_reference','normalization_quantiles','normalization_moments')
          and cfg['scope_parameters']['statistics_purpose']==cfg['statistics_purpose'],'EXACT_DISTINCT_DIAGNOSTIC_AND_D4_STATISTICAL_ROUTE')
    for r in cfg['data_references']:reference(r)
    for r in cfg['small_references']:reference(r,source=True)
    return cfg


def technical_review(cfg,review):
    need(review['schema']==REVIEW and review['status']=='ROOT_APPROVED_INDEPENDENT_NUMERIC_REPROJECTION'
      and review['reviewer']=='root' and review['reason'].strip(),'EXPLICIT_ROOT_TECHNICAL_REPROJECTION_AUTHORITY')
    need(review['old1904_state']=='TIMEOUT' and review['old1904_core_seconds']==230592 and review['old_RESERVED_or_UNKNOWN_promoted'] is False
      and review['old_book_lease_cache_or_source_modified'] is False and review['technical_Parquet_reread_is_not_QM_once_retry'] is True,
      'OLD_TIMEOUT_UNKNOWN_AND_COSTS_RETAINED_NOT_CLEARED')
    for name in ('old_TIMEOUT_accounting','inventory13_actual_C0','seed_history','source_footer_actual_C0','original_logical_group_plan','storage_review','resource_authority'):
        reference(review['evidence'][name])
    need(review['evidence']['resource_authority']==cfg['resource_authority_reference']
      and review['evidence']['original_logical_group_plan']==cfg['logical_group_plan_reference'],'EXACT_RESOURCE_AND_LOGICAL_ORDER_EVIDENCE')
    need(review['source_view_scope']==cfg['mode'] and review['new_UFF_QM_calls']==0 and review['quality_new_mask_fraction']==.01
      and review['source_files_immutable'] is True and review['native_text_recovery_claimed'] is False and review['transitive_actual_C0_numeric_output_authority'] is True,'UNCHANGED_SCIENCE_READONLY_NUMERIC_VIEW')
    need(type(review['other_unwritten_output_cap_bytes']) is int and review['other_unwritten_output_cap_bytes']>=0
      and type(review['remaining_numeric_cache_reserve_bytes']) is int and review['remaining_numeric_cache_reserve_bytes']>=cfg['whole_output_cap_bytes']
      and review['retained_old32GiB_logical_charge_bytes']==32<<30 and review['quota_headroom_bytes']==200000000000,'SEPARATE_RETAINED_CHARGE_FUTURE_CAP_AND_REAL_QUOTA')
    return review


def advance_cursors(sources,prior,windows):
    """Pure immutable continuation. Actual C0 is required separately by metadata."""
    byid={s['file_id']:s for s in sources};current={s['file_id']:int(prior.get(str(s['file_id']),0)) for s in sources};seen=set()
    for window in sorted(windows,key=lambda r:(r['file_id'],r['lo'])):
        fid,lo,hi=window['file_id'],window['lo'],window['hi'];need(type(fid) is int and fid in current and type(lo) is int and type(hi) is int,'EXACT_COMMITTED_PHYSICAL_CURSOR')
        need((fid,lo) not in seen and lo==current[fid] and lo<hi<=byid[fid]['rows'],'NO_GAP_OVERLAP_OR_UNKNOWN_CURSOR_JUMP')
        need(window['all_part_reopen_bits_verified'] is True,'CURRENT_REOPEN_VERIFIED_WINDOW_ONLY');seen.add((fid,lo));current[fid]=hi
    return {str(k):v for k,v in current.items()}

def actual_c0(account,jid):
    need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and account['query_returncode']==0 and account['uid']==1278,'STANDARD_ACTUAL_MAIN_ACCOUNTING_REQUIRED')
    rows=[r for r in account['parents'] if str(r['job_id'])==str(jid)]
    need(len(rows)==1 and rows[0]['state']=='COMPLETED' and rows[0]['exit_code']=='0:0'
      and type(rows[0]['alloc_cpus']) is int and rows[0]['alloc_cpus']==16,'ACTUAL_C0_ONLY_NEVER_TIMEOUT_0_0')
    return rows[0]
def parent_evidence(review,denied_paths=()):
    """Signed Root small-parent facts, never numeric DATA reclassified as Source."""
    need(review['reviewer']=='root' and review['status']=='ROOT_APPROVED_INDEPENDENT_NUMERIC_REPROJECTION','ROOT_TECHNICAL_PARENT_AUTHORITY')
    need(review.get('actual_source_inverse3_review_reference') and review.get('verified_current_small_metadata_references'),'ACTUAL_SOURCE3_AND_VERIFIED_SMALL_PARENT_CHAIN')
    refs=[*review['evidence'].values(),*review['verified_current_small_metadata_references'],review['actual_source_inverse3_review_reference']];out={}
    for r in refs:
        reference(r,source=True);need(r['bytes']<=2<<20 and r['path'] not in denied_paths and Path(r['path']).suffix in ('.json','.txt'),'SMALL_PARENT_METADATA_NOT_NUMERIC_OR_PARQUET_DATA')
        need(r['path'] not in out or out[r['path']]==r,'NO_CONFLICTING_ACTUAL_PARENT_LOCATORS');out[r['path']]=r
    need(out,'NONEMPTY_ACTUAL_PARENT_EVIDENCE_EVEN_FRESH_PILOT');return list(out.values())
