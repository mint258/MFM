"""Reconcile source-only outcomes, including failed/unknown once-consumed work."""
from __future__ import annotations
import argparse,collections,json,os,pathlib,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.n1_pprime2_source_full_v1 import contract as C,io as I,planning

def main():
    p=argparse.ArgumentParser(description=__doc__);options=('prepared','accounting','root-preflight','quota-provider-review','output')
    for name in options:p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--batch-receipt',type=pathlib.Path,action='append',required=True);a=p.parse_args()
    # Repeatable literal receipt options are included in the exact primary argv.
    expanded=[]
    for name in options:expanded.extend(['--'+name,str(getattr(a,name.replace('-','_')))])
    for path in a.batch_receipt:expanded.extend(['--batch-receipt',str(path)])
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    refs={name:I.request_ref(a.root_preflight,getattr(a,name.replace('-','_'))) for name in ('prepared','accounting')}
    receipts=[I.request_ref(a.root_preflight,path) for path in a.batch_receipt]
    # I.admit handles its ordered standard options; it also accepts this explicit
    # argv tail for a metadata reduction with repeatable, reviewed receipt pins.
    proof,catalog,admission=I.admit(__file__,a,options,C.REDUCE_SCOPE_KEY,C.REDUCE_SCOPE,'analysis',[*refs.values(),*receipts],
        execution_argv=[PY,'-B',str(pathlib.Path(__file__).absolute()),*expanded])
    out=I.new_output(a.output);budget=I.Budget(proof,out,I.LEDGER,quota_provider_review_reference=admission['quota_provider_review_reference'])
    tests=I.test10();tests_ref=I.json_new(out/'synthetic10_and_full_boundaries.json',tests,budget.roots)
    C.need(tests['status']=='PASS','ORIGINAL10_AND_NEW_BOUNDARIES_REQUIRED_BEFORE_SOURCE_REDUCTION')
    prepared=I.read(refs['prepared']);account=I.read(refs['accounting']);I.authorized(proof,[account['raw_sacct_reference']])
    terminal=I.terminal_c0(refs['accounting'],prepared['job_id']);parents={str(row['job_id']):row for row in account['parents']}
    C.need(prepared['status']=='ACTUAL_FULL_SOURCE_TASKS_FROZEN_NO_GENERATION' and prepared['eligible_count']==4631
        and prepared['mother_count']==5105 and prepared['imported_count']==32 and prepared['new_attempt_count']==4599,'ACTUAL_FULL_SOURCE_PREPARATION_REQUIRED')
    I.authorized(proof,[prepared['source_task_roster'],prepared['imported32'],prepared['mother_inventory'],prepared['role_status_usable_audit'],prepared['batch_index']])
    roster=list(planning.roster_rows(prepared['source_task_roster']));by_key={row['task_key']:row for row in roster}
    C.need(len(roster)==len(by_key)==4631,'FULL_SOURCE_UNIQUE_TASK_ROSTER')
    imports=I.read(prepared['imported32']);imported={row['task_key']:row for row in imports['imports']}
    C.need(len(imported)==32 and all(by_key[k]['state']=='IMPORTED_ALREADY_CONSUMED_NO_RETRY' for k in imported),'EXACT32_ALREADY_CONSUMED_IMPORT_COVERAGE')
    mother_count=0;mother_ids=[];mother_reasons=collections.Counter()
    I.source_check(prepared['mother_inventory'])
    with pathlib.Path(prepared['mother_inventory']['path']).open('rb') as stream:
        for raw in stream:
            C.need(len(raw)<=64<<10,'BOUNDED_ALL_MOTHER_ROW');row=json.loads(raw);mother_count+=1;mother_ids.append(row['molecule_id']);mother_reasons[row['reason'] or 'SOURCE_BASELINE_READY']+=1
    audit=I.read(prepared['role_status_usable_audit'])
    C.need(mother_count==len(set(mother_ids))==5105 and C.sha_value(sorted(mother_ids))==audit['all_mother_ids_sha256']
        and dict(mother_reasons)==prepared['reason_counts'],'ALL5105_MOTHER_ROWS_AND_EXCLUSION_REASONS_PRESERVED')
    packet_records={key:{'reference':row['packet_reference'],'origin':'IMPORTED32','job_id':'4521418'} for key,row in imported.items()}
    observed_batches=[];claimed_keys=set();unknown=set();unstarted=set();duplicate_batches=set();batch_index=I.read(prepared['batch_index'])
    expected_batches={row['reference']['path']:row for row in batch_index['batches']}
    for reference in receipts:
        report=I.read(reference);jid=report['job_id'];C.need(jid in parents,'EVERY_BATCH_PARENT_REQUIRES_ACTUAL_TERMINAL_ACCOUNTING')
        C.need(report['schema']=='N1_SOURCE_FULL_FINITE_BATCH_RECEIPT_V1' and report['prepared_reference']==refs['prepared']
            and report['source_population_authority']==prepared['source_population_authority'],'EXACT_PINNED_SOURCE_BATCH_RECEIPT')
        batch_ref=report['batch_reference'];C.need(batch_ref['path'] in expected_batches and expected_batches[batch_ref['path']]['reference']==batch_ref,'BATCH_IN_FROZEN_SOURCE_INDEX')
        C.need(batch_ref['path'] not in duplicate_batches,'DUPLICATE_INITIAL_BATCH_RECEIPT');duplicate_batches.add(batch_ref['path'])
        batch=I.read(batch_ref);allowed={row['task_key'] for row in batch['tasks']}
        claims={row['task_key'] for row in report['claims']};C.need(claims<=allowed and not(claims&claimed_keys),'ACTUAL_DISPATCH_KEYS_MUTUALLY_EXCLUSIVE')
        claimed_keys|=claims;unknown.update(report['unknown_consumed_task_keys']);unstarted.update(report['unstarted_task_keys'])
        for row in report['packets']:
            key=row['task_key'];C.need(key in claims and key not in packet_records,'DUPLICATE_OR_UNCLAIMED_SOURCE_PACKET')
            packet_records[key]={'reference':row['reference'],'origin':'NEW_SOURCE_WAVE','job_id':jid,
                'terminal_parent_state':parents[jid]['state'],'worker_start_reference':row['worker_start_reference']}
        observed_batches.append({'receipt_reference':reference,'job_id':jid,'actual_terminal_state':parents[jid]['state'],
            'actual_terminal_exit_code':parents[jid]['exit_code'],'batch_reference':batch_ref,'claimed':len(claims),'packets':len(report['packets'])})
    coverage=[];status=collections.Counter();optimizer_attempted=optimizer_finished=packet_readbacks=0
    ledger_keys={path.stem for path in I.LEDGER.glob('*.json')};unexpected_ledger_keys=sorted(ledger_keys-set(by_key))
    for key,row in by_key.items():
        if budget.observe(reserve=I.ADMIN_RESERVE) is not None:break
        # Transitive inputs are confined to the frozen roster's own preparation
        # namespace and immutable, pinned terminal receipt packet paths.
        task_path=pathlib.Path(row['task_reference']['path']);C.need(task_path.parent.parent==pathlib.Path(refs['prepared']['path']).parent,'TASK_LEAF_FROM_FROZEN_PREPARATION_ONLY')
        task=I.read(row['task_reference']);C.validate_task(task,prepared['source_population_authority'])
        claim_path=I.LEDGER/(key+'.json');consumed=claim_path.exists();record=packet_records.get(key);packet=None
        claim_reference=I.ref(claim_path) if consumed else None;claim=I.read(claim_reference) if consumed else None
        if consumed:C.need(claim['task_key']==key and claim['molecule_id']==row['molecule_id'] and claim['seed']==C.proposed_seed(row['molecule_id'])
            and claim['automatic_retry'] is False,'SAME_IMMUTABLE_ONCE_KEY_SEED_AND_MOLECULE')
        if record is not None:
            packet_path=pathlib.Path(record['reference']['path']);base=I.V.BASE if record['origin']=='IMPORTED32' else I.BASE
            C.need(base in packet_path.parents and packet_path.parent.name=='packets','PACKET_FROM_APPROVED_SOURCE_NAMESPACE_ONLY')
            packet=planning.packet_readback(task,record['reference']);C.need(packet['runtime']['job_id']==record['job_id'],'ACTUAL_PACKET_PARENT_IDENTITY')
            packet_readbacks+=1
            C.need(consumed,'DURABLE_SOURCE_PACKET_REQUIRES_ONCE_CLAIM')
            C.need(claim['job_id']==packet['runtime']['job_id'],'ONCE_CLAIM_AND_ACTUAL_PACKET_PARENT_MATCH')
            if record['origin']=='NEW_SOURCE_WAVE':
                worker=I.read(record['worker_start_reference']);C.need(worker['runtime']==packet['runtime'] and worker['task_key']==key,'INDEPENDENT_CURRENT_WORKER_START_PID_READBACK')
            optimizer_attempted+=packet['summary']['optimizer_calls_attempted'];optimizer_finished+=packet['summary']['optimizer_calls_finished']
        actual=C.source_outcome(consumed,packet is not None,bool(packet and packet['supplement'] is not None and packet['summary']['Pprime_actual_records']==2))
        status[actual]+=1;coverage.append({'molecule_id':row['molecule_id'],'task_key':key,'status':actual,'once_consumed':consumed,
            'packet_reference':record['reference'] if record else None,'once_claim_reference':claim_reference,'origin':record['origin'] if record else None,
            'native_extra_conformer_id':packet['supplement']['native_extra_conformer_id'] if packet and packet['supplement'] else None,
            'geometry_id':packet['supplement']['geometry_id'] if packet and packet['supplement'] else None,
            'original_baseline_geometry_id':row['baseline_geometry_id'],'physical_extra_int64_id':None,
            'common':False,'pilot_membership':False,'production_membership':False})
    lines=I.write(out/'source_outcomes.jsonl',b''.join(C.canonical(row)+b'\n' for row in coverage),budget.roots)
    complete=len(coverage)==4631 and status['REAL_SECOND_PACKET_SOURCE_ONLY']==4631 and not(unknown or unexpected_ledger_keys) and budget.stop is None
    report={'schema':'N1_SOURCE_FULL_OUTCOME_REDUCTION_V1','status':'ALL4631_SOURCE_REAL_SECOND_PACKETS_PRESENT_NO_FINAL_MEMBERSHIP' if complete else 'SOURCE_OUTCOMES_PENDING_OR_UNKNOWN_NO_AUTORETRY',
        'job_id':str(proof['job_id']),'prepared_reference':refs['prepared'],'actual_all_terminal_accounting':terminal,'test10_and_boundaries_reference':tests_ref,
        'mother_count':5105,'eligible_count':4631,'imported32_count':32,'new_attempt_roster_count':4599,'all_mother_reason_counts':dict(mother_reasons),
        'source_outcomes':lines,'outcome_counts':dict(status),'observed_batches':observed_batches,'unobserved_initial_batches':72-len(observed_batches),
        'actual_optimizer_calls_attempted_including_import32':optimizer_attempted,'actual_optimizer_calls_finished_including_import32':optimizer_finished,
        'current_source_packet_float64_SHA_readback_completed':packet_readbacks,'unexpected_once_ledger_keys':unexpected_ledger_keys,
        'current_once_ledger_key_count':len(ledger_keys),'budget':budget.report(),'common':False,'pilot_membership':False,'production_membership':False,
        'source_population_release':False,'final_common_reference':None,'physical_int64_integration_frozen':False,
        'physical_int64_mapping_and_formal_Sprime_materialization':'PENDING_INDEPENDENT_FINAL_EXPORT_AUTHORITY',
        'new_UFF_calls':0,'new_QM_calls':0,'automatic_retry':False,'actual_terminal_accounting_required':True}
    I.json_new(out/'receipt.json',report,budget.roots);print({'status':report['status'],'counts':dict(status)});return 0 if complete else 3
if __name__=='__main__':raise SystemExit(main())
