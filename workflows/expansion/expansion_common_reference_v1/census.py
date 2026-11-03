"""Adapt actual closed4525199 outcomes, never a stale pre-completion census."""
import json,sqlite3
from collections import Counter
from pathlib import Path
from .runtime import need,pin,read,verify,stamp

COUNTS={'OLD_DURABLE_RESULT':86633,'CONSUMED_UNKNOWN_NO_RETRY':3436,'EXCLUDED_ORIGINAL_UFF_UNSUPPORTED':9282}


def derive(ctx):
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
