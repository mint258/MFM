"""Read-only true old/new parent index; never invent500 childC0 or attempt."""
import csv,io,json,pathlib
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import identity as OLD_ID
from . import contract as C

def positive_ticks(v):
    C.need((type(v) is int and v>0) or (type(v) is str and v.isdecimal() and int(v)>0 and str(int(v))==v),'EXACT_POSITIVE_STORED_PROC_TICKS')
    return int(v)

def binding(ctx,packet,value,imports):
    start=packet.get('formal_start')
    if not isinstance(start,dict) or start.get('resource_scope')!='sprime_packed_day_v1':return OLD_ID.attempt_binding(packet,value,imports)
    mid=packet['molecule_id'];key=OLD_ID.require_task_key(start['task_key']);ledger=C.F.ledger_path(key);lr=ctx.reference(ledger);claim=ctx.read(lr)
    root=pathlib.Path(ctx.packed_plan['output_directory']);source=packet['source'];header=ctx.read(claim['prepared_reference'])
    C.need(source['path']==str(root/'packets'/(key+'.json.gz')) and ctx.read(ctx.reference(root/'starts'/(key+'.json')))==start
      and claim['schema']=='SPRIME_DISPATCH_INTENT_V3' and claim['resource_scope']=='sprime_packed_day_v1'
      and claim['packed_plan_reference']==ctx.packed_receipt['plan_reference']==header['packed_plan_reference']
      and header['schema']=='SPRIME_PACKED_INTERNAL_PREPARED_V1' and header['actual_single_parent_job_id']==ctx.packed_receipt['actual_single_parent_job_id']
      and header['actual_allocated_cpus']==64 and header['native_task_keys_and_seed_domains_changed'] is False
      and claim['job_id']==start['job_id']==header['actual_single_parent_job_id'] and claim['uid']==start['uid']==1278
      and claim['boot_id']==start['boot_id'] and claim['task_key']==key and claim['molecule_id']==start['molecule_id']==mid
      and claim['task_sha256']==start['task_sha256'] and claim['seed']==start['seed']==packet['summary']['seed']
      and claim['prepared_reference']['path']==str(root/'internal_prepared'/start['internal_batch_id']/'prepared.json')
      and start['dispatch_reference']==lr and type(start['pid']) is int and start['pid']>0,'REAL_PACKED64_PACKET_START_CLAIM_SOURCE_AND_ORIGINAL_SEED')
    positive_ticks(start['pid_start_ticks']) # Stored original string is not rewritten.
    C.need(claim['boot_id']==C.meta(ctx.packed_receipt['startup_proof_reference'])['boot_id'],'REAL_PACKED64_BOOT_SOURCE')
    if getattr(ctx,'_task_header',None)!=claim['prepared_reference']:
        ctx._task_header=claim['prepared_reference'];ref=header['tasks_reference'];ctx.require(ref)
        with pathlib.Path(ref['path']).open() as f:ctx._task_rows={t['meta']['task_key']:t for t in (json.loads(line) for line in f)}
        C.need(len(ctx._task_rows)==header['molecules'],'EXACT_INTERNAL_TASK_UNION')
    C.need(key in ctx._task_rows and C.F.sha_value(ctx._task_rows[key])==claim['task_sha256'],'ORIGINAL_EXACT_TASK_PAYLOAD_AND_NEW_PARENT_BINDING')
    return {'task_key':key,'once_ledger_path':str(ledger),'once_ledger_sha256':lr['sha256'],'once_ledger_bytes':lr['bytes']}

def accounting(ctx,required):
    review=C.meta(ctx.plan['related_parent_review_reference']);accounted={}
    for ref in review['accounting_references']:
        C.need(C.G.meta_pin(ref['path'])==ref,'EXACT_REAL_ACCOUNTING_PIN');_,value,parents=C.G.account(ref['path'])
        for jid,row in parents.items():C.need(jid not in accounted or accounted[jid]==row,'PARENT_ACCOUNTING_CONFLICT');accounted[jid]=row
    master=C.meta(review['owned_master_reference']);rows={str(r['JobIDRaw']):r for r in master['actual_parents']}
    classes={str(r['job_id']):r for r in review['parent_classifications']}
    C.need(master['query_returncode']==0 and len(rows)==len(master['actual_parents']) and set(classes)==set(rows)
      and len(classes)==len(review['parent_classifications']),'EVERY_OWNED_PARENT_HAS_EXPLICIT_ROOT_COST_CLASSIFICATION')
    related=set()
    for jid,r in classes.items():
        C.need(r['decision'] in ('RELATED_TERMINAL','RELATED_ACTIVE_APPEND_PENDING','UNRELATED_ROOT_REVIEWED') and r['reason'],'NO_NAME_OR_MISSING_ARGV_COST_FALLBACK')
        if r['decision']=='RELATED_TERMINAL':related.add(jid)
    C.need(set(accounted)==related==set(review['related_parent_ids']) and set(required)<=related,'ALL_REQUIRED_PARENTS_AND_ALL_RELATED_COSTS_INCLUDED')
    for jid,r in accounted.items():
        a=rows[jid];C.need(r['state']==a['State'].split()[0] and r['exit_code']==a['ExitCode'] and r['alloc_cpus']==int(a['AllocCPUS'])
          and r['elapsed_raw_seconds']==int(a['ElapsedRaw']),'COST_ROWS_MATCH_COMPLETE_INDEPENDENT_MASTER')
    return accounted,sum(r['alloc_cpus']*r['elapsed_raw_seconds'] for r in accounted.values())

def build(ctx,receipt,packed_plan,original):
    import pyarrow.parquet as pq
    ctx.packed_receipt,ctx.packed_plan=receipt,packed_plan;ctx.attempt_binding=lambda packet,value,imports:binding(ctx,packet,value,imports)
    ref=receipt['resolution_index_reference'];table=pq.read_table(ctx.require(ref));rows=table.to_pylist()
    expected=pq.read_table(ctx.require(original['original_deficits'])).to_pylist();by_key={r['task_key']:r for r in expected}
    C.need(len(rows)==len(by_key)==99351 and {r['task_key'] for r in rows}==set(by_key),'EXACT99351_SUPPORTED_PLUS_UNSUPPORTED_INDEX_UNION')
    outcomes=[];unstarted=[];states={};parents={str(receipt['actual_single_parent_job_id'])}
    for row in sorted(rows,key=lambda r:(r.get('original_batch_id') or '',r['molecule_id'])):
        ctx.check();key=row['task_key'];meta=by_key[key];C.need(row['molecule_id']==meta['molecule_id'] and row['cohort']==meta['cohort']
          and row['expected_conformers']==meta['expected_conformers'],'ORIGINAL_INDEX_MOLECULE_COHORT_N_UNCHANGED')
        states[row['resolution']]=states.get(row['resolution'],0)+1
        if meta['cohort']=='unsupported':continue
        ledger=C.F.ledger_path(key)
        if not ledger.exists():unstarted.append({'task_key':key,'molecule_id':meta['molecule_id'],'resolution':row['resolution']});continue
        lr=ctx.reference(ledger);claim=ctx.read(lr);e=json.loads(row['evidence']) if row['evidence'] else {}
        owner=claim.get('job_id')
        if owner is not None:parents.add(str(owner))
        parents.update(map(str,claim.get('historical_parent_ids',[])))
        observed=e.get('science_result_observed') is True;package=e.get('package_reference') if observed else None
        C.need(not observed or package is not None,'OBSERVED_PACKAGE_MUST_HAVE_REAL_REFERENCE')
        outcome={'molecule_id':meta['molecule_id'],'task_key':key,'cohort':meta['cohort'],'expected_conformers':meta['expected_conformers'],
          'seed':C.F.seed_for(meta['molecule_id'],meta['cohort']=='retry_once'),'ledger_reference':lr,'owner_job_id':None if owner is None else str(owner),
          'science_result_observed':observed,'package_reference':package,'scientific_status':e.get('scientific_status') if observed else None,
          'execution_resolution':'DURABLE_PACKAGE_VALIDATED' if observed else 'EXECUTION_UNRESOLVED','truthful_origin_resolution':row['resolution']}
        C.need(claim.get('molecule_id')==meta['molecule_id'] and claim.get('task_key')==key and claim.get('seed')==outcome['seed'],'ONCE_TASK_MID_SEED_UNCHANGED')
        outcomes.append(outcome)
    cost,coresec=accounting(ctx,parents)
    orf=ctx.write_json_new(ctx.out/'exact_outcomes.json',outcomes);urf=ctx.write_json_new(ctx.out/'proven_unstarted_or_unresolved.json',unstarted)
    status='ALL_SPRIME_ATTEMPTS_TERMINAL' if len(outcomes)==90069 and not unstarted else 'PARTIAL_NO_COMMON_FINALIZATION'
    result={'schema':'PACKED_SPRIME_EXACT_OUTCOME_INDEX_V1','status':status,'config':ctx.plan['original_config_reference'],
      'consumed_count':len(outcomes),'expected_deficits':90069,'unsupported_count':9282,'root_draft':original['root_draft'],
      'outcomes':orf,'pilot_imports':original['pilot_imports'],'actual_parent_rows':cost,'actual_accounted_core_seconds':coresec,
      'packed_true64_parent_receipt':ctx.plan['packed_receipt_reference'],'original_state_counts':states,'unstarted_reference':urf,
      'current_postprocess_parent_cost':'PENDING_ACTUAL_ROOT_TERMINAL_ACCOUNTING','old_PARENT_states_unchanged':True,'Common_release':False}
    return ctx.write_json_new(ctx.out/'exact_outcome_index.json',result),result
