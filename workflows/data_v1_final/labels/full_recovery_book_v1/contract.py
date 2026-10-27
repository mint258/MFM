"""Pure recovery policy; no science, SQLite or data-body IO."""
from __future__ import annotations
import collections
from pathlib import Path
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=REPO/'workflows/data_v1_final/labels/full_recovery_book_v1'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
OLD=RUN/'artifacts/labels/source_status_v1/full_projection_batch0000_v1'
OLDBOOK=RUN/'control/labels_full_bounded32_dispatch_v1.sqlite'
SEED_KEY='labels_recovered_book_seed_v1';CLOSE_KEY='labels_recovered_full_coverage_v1'
RUN_KEY='labels_full_typed_projection_batch_v1'
RESOURCE='ROOT_LABELS_RECOVERED_BOOK_RESOURCE_REVIEW_V1';SELECTION='ROOT_EXPLICIT_LABELS_SEED_PREFIX_SELECTION_V1'
SEED='LABELS_RECOVERED_BOOK_SEED_PLAN_V1';SUMMARY='LABELS_TIMEOUT_COMMITTED_PREFIX_ADOPTION_V1'
ORIGIN='TIMEOUT_ADOPTED_CLOSED_WINDOWS'
FILES=('__init__.py','contract.py','io.py','book.py','seed.py','run.py','coverage.py','metadata.py','test_recovery.py','README.md')


def need(ok,code):
    if not ok:raise ValueError(code)


def inventory_gate(receipt):
    need(receipt['schema']=='LABELS_FULL_TIMEOUT_READONLY_INVENTORY_RECEIPT_V1'
      and receipt['status']=='PARTIAL_TIMEOUT_EVIDENCE_NOT_OLD_C0' and str(receipt['job_id'])=='4522748'
      and receipt['uid']==1278 and receipt['original_parent_c0'] is False
      and receipt['inventory_verification_complete'] is True and receipt['all_old_member_frames_unchanged'] is True
      and not receipt['errors'] and not receipt['quality_hold_fields_verified_windows'],'ACTUAL_COMPLETE_INVENTORY_NOT_JUST_C0')
    p=receipt['original_parent'];need(p['original_parent_state']=='TIMEOUT' and p['original_parent_c0'] is False
      and p['allocated_core_seconds']==230592,'ORIGINAL1904_ALWAYS_TIMEOUT')


def budget(review):
    need(review['schema']=='FULL_LABEL_PROJECTION_ROOT_REVIEW_V1' and review['recovery_schema']==RESOURCE
      and review['status']=='ROOT_APPROVED_FULL_SOURCE_CACHE' and review['reviewer']=='root' and review['reason'].strip(),
      'INDEPENDENT_NEW_ROOT_RESOURCE_REVIEW')
    retained=review['retained_old_logical_ceiling_bytes'];production=review['approved_whole_cache_cap_bytes'];seed=review['seed_output_cap_bytes']
    need(retained==32<<30 and type(production) is int and production>=8<<30 and type(seed) is int and 4<<30<=seed<=8<<30
      and type(review['new_global_logical_cap_bytes']) is int and review['new_global_logical_cap_bytes']>=retained+production+seed+(2<<30),'OLD32_PLUS_SEED_AND_NEW_PRODUCTION_CAP_NO_RESET')
    need(review['budget_basis']=='OLD_RETAINED_SEPARATE_FROM_NEWBOOK_PRODUCTION'
      and review['quota_reserve_bytes']==200000000000 and review['old_unknown_charge_refunded'] is False
      and review['cost_overrun_action']=='REPORT_AND_CONTINUE' and review['final_masks_authorized'] is False
      and review['final_common_D4_authorized'] is False,'EXPLICIT_LOGICAL_PHYSICAL_AND_FUTURE_AXES_NOT_SCIENCE_RELEASE')
    need(type(review['other_storage_scope_unwritten_cap_upper_bound_bytes']) is int
      and review['other_storage_scope_unwritten_cap_upper_bound_bytes']>=0
      and all(type(review[k]) is int for k in ('seed_wall_seconds','softwall_margin_seconds','production_wall_seconds'))
      and 300<=review['seed_wall_seconds']<=172800 and 300<=review['softwall_margin_seconds']<review['production_wall_seconds']<=172800,
      'FINITE_REVIEWED_RESOURCE_WALL_AND_ALL_OTHER_CAPS')
    return {'retained':retained,'production':production,'seed':seed,'global':review['new_global_logical_cap_bytes']}


def prefixes(expected,ranges,tickets,windows,verified,approved,orphan_holds):
    """Every consumed window remains recorded even when Root selects less."""
    starts={r['range_id']:r for r in expected};cur={r['range_id']:r for r in ranges}
    selections={r['file_id']:r['end_physical_row'] for r in approved}
    need(len(selections)==len(approved) and set(selections)<={r['file_id'] for r in expected},'EXACT_UNIQUE_ROOT_PREFIX_SELECTION')
    chosen=[];holds={};cursor={};consumed=[]
    for key,e in starts.items():
        fid=e['file_id'];old=cur[key]['cursor'];end=selections.get(fid,e['physical_row_lo'])
        need(type(end) is int and e['physical_row_lo']<=end<=old,'ROOT_PREFIX_INSIDE_OLD_COMMITTED_RANGE')
        pos=e['physical_row_lo'];selected_end=pos
        for w in sorted((w for w in windows if w['range_id']==key),key=lambda w:w['lo']):
            need(w['lo']==pos<w['hi']<=old,'NO_COMMITTED_GAP_OR_OVERLAP');pos=w['hi']
            k=(key,w['lo']);need(k in verified and verified[k]['status']=='VERIFIED_COMMITTED_WINDOW','ALL_COMMITTED_WINDOWS_ACTUALLY_VERIFIED')
            picked=w['hi']<=end
            need(not(w['lo']<end<w['hi']),'NO_ROOT_CUT_INSIDE_WINDOW')
            consumed.append({'file_id':fid,'range_id':key,'lo':w['lo'],'hi':w['hi'],'adopted':picked,'receipt':w['receipt']})
            if picked:chosen.append(verified[k]);selected_end=w['hi']
        need(pos==old and selected_end==end,'CURSOR_AND_EXACT_SELECTED_WINDOW_BOUNDARY')
        reasons=[]
        if end!=old:reasons.append('OLD_CONSUMED_NOT_ADOPTED_NO_REDO')
        if any(t['range_id']==key and t['status']!='CLOSED' for t in tickets):reasons.append('OLD_UNKNOWN_OR_RESERVED_TICKET_NO_RETRY')
        if fid in orphan_holds:reasons.append('ORPHAN_OR_PARTIAL_PUBLICATION_UNRESOLVED')
        if reasons:holds[fid]=reasons
        cursor[fid]=end
    return chosen,cursor,holds,consumed


def hold_fields(stats):
    return sorted(fid for fid,s in stats.items() if s['newly_masked_fields']/11231854>.01
      or s['new_payload_structural_invalid_records']/11231854>.01
      or s['records'] and (s['newly_masked_fields']/s['records']>.01 or s['new_payload_structural_invalid_records']/s['records']>.01))


def remaining(meta,batches):
    written=sum(b['charged_bytes'] for b in batches if b['state']=='ACTUAL_C0_CLOSED')
    need(0<=written<=meta['cap'],'NEW_PRODUCTION_BUDGET_CONSERVATION')
    need(meta['recovery_budget']['retained']==32<<30 and meta['cap']==meta['recovery_budget']['production'],
      'OLD_RETAINED_NOT_RESET_OR_DOUBLE_RESERVED_AS_FUTURE')
    return meta['cap']-written