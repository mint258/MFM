"""Verify one Root-frozen cost snapshot; never scan submissions created later."""
from __future__ import annotations
import csv,io,pathlib
from datetime import datetime
from workflows.data_v1_final.conformers.recovery_auto_memory_v1 import owned_costs as OLD


TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}


def need(ok,message):
    if not ok:raise ValueError(message)


def triples(values):
    result={}
    for value in values:
        value=OLD.normalized(value)
        need(value['path'] not in result,'DUPLICATE_FROZEN_SNAPSHOT_REFERENCE')
        result[value['path']]=value
    return result


def verify_snapshot(owned_ref,selection_ref,*,classification_ref=None,current_job_id=None):
    """Recompute scope/cost for exactly Master rows and their pinned receipts."""
    master=OLD.load_pin(owned_ref);frozen=OLD.load_pin(selection_ref)
    need(master['schema']=='DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2' and master['query_returncode']==0,
        'ACTUAL_POINT_IN_TIME_MASTER_REQUIRED')
    observed=datetime.fromisoformat(master['observed_at']);need(observed.tzinfo is not None,'TIMEZONE_AWARE_SNAPSHOT_ASOF_REQUIRED')
    need(frozen['owned_raw_sacct_reference']==master['raw_sacct_reference']
        and frozen['legacy_scope_classification_reference']==(OLD.normalized(classification_ref) if classification_ref is not None else None),
        'EXACT_FROZEN_RAW_AND_CLASSIFICATION_BINDINGS_REQUIRED')
    need(frozen['current_validator_or_closure_job_excluded_only_as_pending_self'] is None,
        'FROZEN_PRIOR_SELECTION_MUST_NOT_HIDE_A_SNAPSHOT_PARENT')
    raw=OLD.read(OLD.verify(master['raw_sacct_reference'])).decode()
    reader=csv.DictReader(io.StringIO(raw),delimiter='|')
    need(reader.fieldnames is not None and {'JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS'}<=set(reader.fieldnames),
        'EXACT_ACTUAL_RAW_PARENT_HEADER_REQUIRED')
    rawparents={}
    for row in reader:
        jid=row['JobIDRaw']
        if not jid.isdecimal():continue
        need(jid not in rawparents,'DUPLICATE_FROZEN_RAW_PARENT');rawparents[jid]=row
    rows={row['JobIDRaw']:row for row in master['actual_parents']}
    need(len(rows)==len(master['actual_parents'])==frozen['owned_snapshot_parent_count'] and set(rows)==set(rawparents),
        'FROZEN_MASTER_RAW_ACTUAL_PARENT_SET_DIFFERS')
    argv=master['command_argv']
    need(isinstance(argv,list) and pathlib.Path(argv[0]).name=='sacct' and argv.count('-j')==1,
        'ACTUAL_FROZEN_SACCT_QUERY_ARGV_REQUIRED')
    requested=argv[argv.index('-j')+1].split(',')
    need(len(requested)==len(set(requested)) and set(requested)==set(rows),'FROZEN_QUERY_PARENT_SET_DIFFERS')
    if current_job_id is not None:need(str(current_job_id) not in rows,'NEW_CLOSURE_PARENT_CANNOT_ALREADY_BE_IN_PRIOR_SNAPSHOT')
    snapshot_refs=triples(frozen['all_snapshot_receipt_references'])
    master_refs=triples(row['receipt_reference'] for row in rows.values())
    need(snapshot_refs==master_refs,'FROZEN_RECEIPT_REFERENCE_SET_DIFFERS_FROM_MASTER')
    need(set(frozen['all_owned_scope_decisions'])==set(rows),'FROZEN_SCOPE_DECISIONS_MUST_COVER_EXACT_SNAPSHOT')
    classified,evidence=OLD._legacy_scope_review(classification_ref)
    need(set(classified)<=set(rows),'LEGACY_CLASSIFICATION_OUTSIDE_APPROVED_SNAPSHOT')
    need(evidence==frozen['legacy_scope_evidence_references'],'FROZEN_LEGACY_EVIDENCE_SET_CHANGED')
    applied=set();scopes={};reasons={};receipts={};parsed_rows={}
    for jid in sorted(rows,key=int):
        row=rows[jid];observed_row=rawparents[jid]
        need(all(str(row[key])==str(observed_row[key]) for key in ('State','ExitCode','ElapsedRaw','AllocCPUS')),
            'FROZEN_MASTER_ROW_DIFFERS_FROM_ACTUAL_RAW:'+jid)
        elapsed,cpus=int(row['ElapsedRaw']),int(row['AllocCPUS'])
        need(elapsed>=0 and cpus>=0 and row['allocated_core_seconds_observed']==elapsed*cpus,
            'FROZEN_ACTUAL_PARENT_COST_DIFFERS:'+jid)
        receipt_ref=OLD.normalized(row['receipt_reference']);body=OLD.load_pin(receipt_ref)
        need(str(body.get('job_id',''))==jid and body.get('sbatch_returncode')==0 and body.get('uid')==1278
            and isinstance(body.get('request'),dict),'EXACT_FROZEN_ACTUAL_SUBMISSION_RECEIPT_REQUIRED:'+jid)
        related,reason=OLD._related(body,pathlib.Path(receipt_ref['path']))
        if jid in classified:
            classification=classified[jid]
            need(related is None and OLD.normalized(classification['submission_reference'])==receipt_ref,
                'EXACT_LEGACY_CLASSIFICATION_MAY_ONLY_RESOLVE_FROZEN_OPAQUE_RECEIPT:'+jid)
            related=classification['related_to_sprime_pilot'];reason='root_pinned_legacy_scope_classification: '+classification['reason'];applied.add(jid)
        scopes[jid]={'related':related,'reason':reason}
        need(scopes[jid]==frozen['all_owned_scope_decisions'][jid],'FROZEN_SCOPE_DECISION_REPLAY_DIFFERS:'+jid)
        need(related is not None,'UNCLASSIFIED_RECEIPT_WITHIN_APPROVED_SNAPSHOT:'+jid)
        receipts[jid]=receipt_ref
        parsed_rows[jid]={'job_id':jid,'state':row['State'].split()[0],'exit_code':row['ExitCode'],
            'elapsed_raw_seconds':elapsed,'alloc_cpus':cpus,'allocated_core_seconds':elapsed*cpus}
        if related:reasons[jid]=reason
    need(set(classified)==applied,'FROZEN_LEGACY_CLASSIFICATION_NOT_FULLY_APPLIED')
    selected_ids=sorted(reasons,key=int)
    need(selected_ids==frozen['related_parent_ids'] and reasons==frozen['selection_reasons'],
        'ROOT_FROZEN_RELATED_PARENT_SET_OR_REASONS_DIFFERS')
    selected_rows=[parsed_rows[jid] for jid in selected_ids];selected_refs=[receipts[jid] for jid in selected_ids]
    need(selected_rows==frozen['selected_parent_rows'] and selected_refs==frozen['selected_receipt_references'],
        'FROZEN_SELECTED_PARENT_COST_OR_RECEIPT_DIFFERS')
    need(all(row['state'] in TERMINAL for row in selected_rows),'KNOWN_RELATED_SNAPSHOT_PARENTS_MUST_BE_TERMINAL_AS_CAPTURED')
    need(not frozen['unclassified_scope_parent_ids_for_root_review'],'FROZEN_ROOT_SELECTION_HAS_UNRESOLVED_SCOPE')
    # These are frozen failed-submission refs, not a new scan for later attempts.
    rejected=triples(frozen['known_rejected_related_submission_references'])
    for ref in rejected.values():
        body=OLD.load_pin(ref);related,_=OLD._related(body,pathlib.Path(ref['path']))
        need(body.get('sbatch_returncode') not in (None,0) and related is True,
            'FROZEN_REJECTED_SUBMISSION_REFERENCE_DIFFERS')
    total=sum(row['allocated_core_seconds'] for row in selected_rows)
    need({'4520335','4520364','4520527','4521110'}<=set(selected_ids),'REQUIRED_ORIGINAL_PREPARATION_AND_TIMEOUT_COST_MISSING')
    return dict(frozen,cost_basis='ROOT_APPROVED_POINT_IN_TIME_SNAPSHOT_ONLY',
        approved_snapshot_observed_at=master['observed_at'],approved_master_reference=OLD.normalized(owned_ref),
        approved_prior_selection_reference=OLD.normalized(selection_ref),snapshot_verified_actual_parent_count=len(rows),
        snapshot_verified_related_parent_count=len(selected_ids),snapshot_verified_related_core_seconds=total,
        scope_decisions_recomputed_for_snapshot_only=True,future_registry_scanned=False,
        future_submission_or_parent_state_required=False,not_final_data_line_total=True,
        current_closure_parent_outside_snapshot=str(current_job_id) if current_job_id is not None else None,
        current_closure_and_later_tasks_require_Root_terminal_master_append=True)