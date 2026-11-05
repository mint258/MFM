"""Adapt actual closed4525199 outcomes, never a stale pre-completion census."""
import json,sqlite3
from collections import Counter
from pathlib import Path
from .runtime import need,pin,read,verify,stamp

COUNTS={'OLD_DURABLE_RESULT':86633,'CONSUMED_UNKNOWN_NO_RETRY':3436,'EXCLUDED_ORIGINAL_UFF_UNSUPPORTED':9282}


def reuse_closed(ctx):
    """Reuse closed source metadata, never the failed parent's final status."""
    p=ctx.plan;ref=p['closed_outcome_index_reference'];review_ref=p['closed_outcome_index_reuse_authority_reference'];review=read(review_ref)
    need(review['schema']=='ROOT_EXPANSION_CLOSED_OUTCOME_INDEX_REUSE_V1' and review['reviewer']=='root'
      and review['status']=='APPROVED_CLOSED_SOURCE_METADATA_FROM_FAILED_PARENT'
      and review['source_index_reference']==ref and review['freeze_manifest_reference']==p['freeze_manifest_reference']
      and review['failed_parent_state_preserved'] is True,'EXACT_ROOT_FAILED_METADATA_REUSE_AUTHORITY')
    from .accounting import failed_metadata_parent,closed_freeze
    failed,raw_failed=failed_metadata_parent(review['failed_parent_accounting_reference'],review['failed_parent_job_id'])
    closed_freeze(p['freeze_accounting_reference'])
    index=read(ref);need(index['schema']=='PACKED_SPRIME_EXACT_OUTCOME_INDEX_V1' and index['status']=='ALL_SPRIME_ATTEMPTS_TERMINAL'
      and index['config']==p['original_config_reference'] and index['freeze_manifest_reference']==p['freeze_manifest_reference']
      and index['consumed_count']==index['expected_deficits']==90069 and index['unsupported_count']==9282
      and index['execution_unknown_original_count']==3436,'EXACT_CLOSED_ORIGINAL90069_INDEX')
    loc=p['census_locator'];census=index['original_census_reference'];need(census==review['original_census_reference']
      and census['path']==loc['path'] and census['bytes']==loc['bytes'] and loc['producer_job_id']=='4525199','SAME_ACTUAL_CLOSED_CENSUS_SOURCE')
    path=verify(census,ctx.check)
    for suffix in ('-wal','-shm','-journal'):need(not Path(str(path)+suffix).exists(),'CLOSED_CENSUS_NO_SIDECARS')
    first=stamp(path.stat());ctx.trust([ref,index['outcomes'],index['root_draft'],index['pilot_imports'],census])
    outcomes=ctx.read(index['outcomes'],ctx.F.CAP);need(len(outcomes)==90069,'WHOLE_CLOSED_OUTCOME_BODY')
    bymid={o['molecule_id']:o for o in outcomes};need(len(bymid)==90069,'UNIQUE_CLOSED_SOURCE_OUTCOMES')
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True);ctx.evidence={};seen=set()
    try:
        need(dict(db.execute('SELECT state,count(*) FROM metas GROUP BY state'))==COUNTS
          and db.execute('SELECT count(*) FROM errors').fetchone()[0]==0,'EXACT_CLOSED_CENSUS_COUNTS_NO_ERRORS')
        for key,mid,meta_raw,state,evidence_raw in db.execute("SELECT k,mid,meta,state,evidence FROM metas WHERE state<>'EXCLUDED_ORIGINAL_UFF_UNSUPPORTED'"):
            ctx.check();meta=json.loads(meta_raw);e=json.loads(evidence_raw);o=bymid[mid];observed=state=='OLD_DURABLE_RESULT'
            need(o['task_key']==key==meta['task_key'] and o['original_census_state']==state
              and o['science_result_observed'] is observed and o['ledger_reference']==e['ledger_reference']
              and o['package_reference']==(e.get('package_reference') if observed else None)
              and o['scientific_status']==(e.get('scientific_status') if observed else None)
              and o['original_census_reference']==census,'EXACT_OUTCOME_TO_IMMUTABLE_SOURCE_ROW_BINDING')
            refs=[e['ledger_reference']]
            if observed:ctx.evidence[mid]=dict(e,original_meta=meta);refs.append(e['package_reference'])
            ctx.trust(refs);seen.add(mid)
    finally:db.close()
    need(seen==set(bymid) and first==stamp(path.stat()),'COMPLETE_CLOSED_INDEX_READBACK')
    ctx.reused_index_provenance=ctx.write_json_new(ctx.out/'reused_closed_source_index.json',dict(source_index=ref,
      Root_reuse_authority=review_ref,failed_parent_accounting=review['failed_parent_accounting_reference'],
      failed_parent_raw_accounting=raw_failed,failed_parent_job_id=failed['JobIDRaw'],failed_parent_state=failed['State'],
      current_parent_C0_pending=True,new_UFF_QM_calls=0,current_ledger_and_package_recheck_in_original_common_build=True))
    return ref,index


def derive(ctx):
    if ctx.plan.get('closed_outcome_index_reference'):return reuse_closed(ctx)
    p=ctx.plan;freeze=read(p['freeze_manifest_reference'])
    from .accounting import closed_freeze
    freeze_actual,freeze_raw_accounting=closed_freeze(p['freeze_accounting_reference'])
    need(freeze['schema']=='FROZEN_DISJOINT_REMAINING_ASSIGNMENTS_V4' and freeze['actual_freeze_job_id']=='4525199'
        and freeze['remaining_molecules']==0 and freeze['new_UFF_QM_calls']==0 and freeze['ordinary_census']['complete'] is True
        and freeze['ordinary_census']['state_counts']==COUNTS,'ACTUAL_FULL_TERMINAL_SOURCE_CENSUS')
    need(freeze['original_config_reference']==p['original_config_reference'],'EXACT_SAME_ORIGINAL_CONFIG')
    loc=p['census_locator'];path=Path(loc['path']);need(str(path)==str(Path(p['freeze_manifest_reference']['path']).parent/'census.sqlite')
        and loc['producer_job_id']=='4525199','EXACT_CLOSED4525199_SQLITE_LOCATOR')
    authority=read(loc['root_authority_reference'])
    need(authority['schema']=='ROOT_EXPANSION_CLOSED_CENSUS_SOURCE_V1' and authority['reviewer']=='root'
        and authority['status']=='APPROVED_FIRST_CPU_SHA_OF_ACTUAL_CLOSED_SOURCE' and authority['producer_job_id']=='4525199'
        and authority['path']==str(path) and authority['bytes']==loc['bytes']==path.stat().st_size
        and authority['actual_terminal_accounting_reference']==p['freeze_accounting_reference'],'ROOT_CLOSED_SOURCE_FIRST_SHA_AUTHORITY')
    for suffix in ('-wal','-shm','-journal'):need(not Path(str(path)+suffix).exists(),'NO_ACTIVE_CENSUS_SQLITE_SIDECAR')
    first=stamp(path.stat());ref=pin(path,ctx.check);ctx.trust([ref]);db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        need(db.execute('SELECT count(*) FROM errors').fetchone()[0]==0,'ORIGINAL_CENSUS_ERRORS_NOT_IGNORED')
        counts=Counter();outcomes=[];ctx.evidence={};parents={}
        # The actual4525199 manifest deliberately summarizes ordinary_census and
        # does not serialize Census.parents. Re-read its exact registered-run
        # authority with the unchanged original accounting function instead.
        legacy=read(freeze['legacy_census_basis_reference']);review=read(legacy['inputs_review_reference'])
        from workflows.data_v1_final.conformers.sprime_packed_day_v1 import contract as Packed
        for entry in review['registered_runs']:
            submission=read(entry['submission_reference']);jid=str(submission['job_id'])
            verify(entry['accounting_reference'],ctx.check)
            ar,av,actual=Packed.G.account(entry['accounting_reference']['path'],[jid])
            parents[jid]=dict(actual=actual[jid],accounting_reference=ar,raw_reference=av['raw_sacct_reference'])
        for key,mid,raw,state,evidence in db.execute('SELECT k,mid,meta,state,evidence FROM metas ORDER BY mid'):
            ctx.check();counts[state]+=1;meta=json.loads(raw)
            need(meta['molecule_id']==mid and meta['task_key']==key,'EXACT_ORIGINAL_META_MID_TASK_KEY')
            if state=='EXCLUDED_ORIGINAL_UFF_UNSUPPORTED':
                need(meta['cohort']=='unsupported','EXACT_ORIGINAL_UNSUPPORTED');continue
            need(state in ('OLD_DURABLE_RESULT','CONSUMED_UNKNOWN_NO_RETRY'),'NO_UNSTARTED_OR_UNKNOWN_CLASS_DROPPED')
            e=json.loads(evidence);observed=state=='OLD_DURABLE_RESULT'
            need(e.get('science_result_observed',False) is observed and (not observed or e.get('package_reference') is not None),'TRUE_DURABLE_OR_UNKNOWN_EVIDENCE')
            ledger=e['ledger_reference'];verify(ledger,ctx.check);refs=[ledger]
            if observed:refs.append(e['package_reference']);ctx.evidence[mid]=dict(e,original_meta=meta)
            ctx.trust(refs);owner=e.get('owner_parent',{}).get('actual',{}).get('job_id',e.get('owner'))
            outcomes.append(dict(molecule_id=mid,task_key=key,cohort=meta['cohort'],expected_conformers=meta['expected_conformers'],
                seed=ctx.F.seed_for(mid,meta['cohort']=='retry_once'),ledger_reference=ledger,owner_job_id=owner,
                science_result_observed=observed,package_reference=e.get('package_reference') if observed else None,
                scientific_status=e.get('scientific_status') if observed else None,execution_resolution=e.get('execution_resolution','EXECUTION_UNRESOLVED'),
                original_census_state=state,original_census_reference=ref))
        need(dict(counts)==COUNTS and len(outcomes)==90069 and len({o['task_key'] for o in outcomes})==90069,'COMPLETE99351_SUPPORTED_PLUS_UNSUPPORTED_ROSTER')
    finally:db.close()
    need(stamp(path.stat())==first,'ORIGINAL_CLOSED_CENSUS_CHANGED')
    original=read(freeze['original_plan_reference']);ctx.trust([original['root_draft'],original['pilot_imports']])
    actual=freeze['terminal_owner_lock_authority']['actual_owner'];parent_rows={jid:v['actual'] for jid,v in parents.items()}
    for row in freeze['historical_readback']['parents']:parent_rows[row['actual_parent_job_id']]=row['actual_terminal']['actual']
    parent_rows['4525135']=actual['actual'];parent_rows['4525199']=freeze_actual
    core_seconds=sum(int(v['alloc_cpus'])*int(v['elapsed_raw_seconds']) for v in parent_rows.values())
    outcomes_ref=ctx.write_json_new(ctx.out/'exact_original90069_outcomes.DATA.json',outcomes)
    index=dict(schema='PACKED_SPRIME_EXACT_OUTCOME_INDEX_V1',status='ALL_SPRIME_ATTEMPTS_TERMINAL',config=p['original_config_reference'],
        consumed_count=90069,expected_deficits=90069,unsupported_count=9282,root_draft=original['root_draft'],outcomes=outcomes_ref,
        pilot_imports=original['pilot_imports'],actual_parent_rows=parent_rows,actual_accounted_core_seconds=core_seconds,
        producer='EXPANSION_ACTUAL4525199_CLOSED_CENSUS_ADAPTER_V1',original_census_reference=ref,
        freeze_manifest_reference=p['freeze_manifest_reference'],freeze_accounting_reference=p['freeze_accounting_reference'],
        freeze_raw_accounting_reference=freeze_raw_accounting,execution_unknown_original_count=3436,new_UFF_QM_calls=0,
        no_child_Slurm_jobs=True,science_original_objects_unmodified=True,current_parent_accounting_pending=True)
    return ctx.write_json_new(ctx.out/'exact_outcome_index.json',index),index
