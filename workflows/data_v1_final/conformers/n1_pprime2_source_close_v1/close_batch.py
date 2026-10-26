"""Read a real terminal source parent's durable evidence, without running UFF."""
from __future__ import annotations
import argparse,collections,hashlib,pathlib,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.n1_pprime2_source_close_v1 import contract as C,io as I
F=I.F;V=I.V
OPTIONS=('prepared','batch','batch-review','pilot-review','request','submission','accounting','root-preflight','quota-provider-review','output')


def receipt_evidence(observation,key,registration,prepared_reference,batch_reference):
    """A missing receipt is fine; malformed/unattributable receipt is never absence."""
    if not observation['exists']:return False,[]
    try:
        value=observation['value']
        C.need(not observation['error'] and value['schema']=='N1_SOURCE_FULL_FINITE_BATCH_RECEIPT_V1'
            and str(value['job_id'])==registration['job_id'] and value['prepared_reference']==prepared_reference
            and value['batch_reference']==batch_reference,'PRODUCER_RECEIPT_CONFLICT')
        mentioned={r['task_key'] for name in ('claims','packets') for r in value[name]}
        for name in ('unknown_consumed_task_keys','preexisting_consumed_keys'):mentioned.update(value[name])
        return key in mentioned,[]
    except Exception as exc:return True,['UNATTRIBUTABLE_OR_INVALID_PRODUCER_RECEIPT:'+repr(exc)]


def inspect_task(row,task,registration,prepared_reference,prepared,batch_reference,parents,producer_receipt):
    """Observe only deterministic paths under the actual registered output root.

    Even invalid files retain their physical locator, observed SHA and parse
    error. Valid science is copied only with a real once/dispatch/start chain.
    """
    key=C.key_shape(row['task_key']);jid=registration['job_id'];out=registration['output_root']
    packet_stem=hashlib.sha256(row['molecule_id'].encode()).hexdigest()
    paths={'claim':V.LEDGER/(key+'.json'),'dispatch':out/'dispatch_intents'/(key+'.json'),
        'start':out/'worker_starts'/(key+'.json'),'finished':out/'finished'/(key+'.json'),
        'packet':out/'packets'/(packet_stem+'.json.gz'),'worker_failure':out/'worker_failures'/(key+'.json')}
    observations={name:I.observe(path,decode=name!='packet') for name,path in paths.items()}
    conflicts=[name+':'+obs['error'] for name,obs in observations.items() if obs['error']]
    events=[];directory=out/'events'/key
    if directory.exists() or directory.is_symlink():
        if directory.is_symlink() or not directory.is_dir():
            conflicts.append('INVALID_EVENT_DIRECTORY');events.append({'path':str(directory),'exists':True,'error':'NOT_REGULAR_DIRECTORY'})
        else:
            names=sorted(directory.iterdir());C.need(len(names)<=256,'BOUNDED_ORIGINAL_EVENT_COUNT_EXCEEDED')
            events=[I.observe(path) for path in names]
            conflicts.extend('event:'+item['error'] for item in events if item['error'])
    partial=[];packet_directory=out/'packets'
    if packet_directory.exists() and not packet_directory.is_symlink():
        partial=[I.observe(path) for path in sorted(packet_directory.glob(packet_stem+'*')) if path!=paths['packet']]
        C.need(len(partial)<=16,'BOUNDED_PARTIAL_PACKET_COUNT_EXCEEDED')
        if partial:conflicts.append('ADDITIONAL_PARTIAL_PACKET_EVIDENCE_REQUIRES_REVIEW')
    mentioned,receipt_errors=receipt_evidence(producer_receipt,key,registration,prepared_reference,batch_reference)
    conflicts.extend(receipt_errors)
    evidence={name:obs['exists'] for name,obs in observations.items()}
    evidence.update(events=bool(events),partial_packet=bool(partial),producer_receipt_entry=mentioned)
    valid={'claim':False,'dispatch':False,'start':False,'packet':False};packet=None;missing_accounting=[]
    claim=observations['claim']['value'];dispatch=observations['dispatch']['value'];start=observations['start']['value']
    if isinstance(claim,dict):
        owner=str(claim.get('job_id',''))
        if not owner.isdecimal() or owner not in parents:missing_accounting.append(owner or 'UNPARSEABLE_CLAIM_OWNER')
        else:C.require_parents([owner],parents)
    elif observations['claim']['exists']:missing_accounting.append('UNPARSEABLE_CLAIM_OWNER')
    def check(name,function):
        if not observations[name]['exists'] or observations[name]['error']:return
        try:function();valid[name]=True
        except Exception as exc:conflicts.append(name+':'+repr(exc))
    check('claim',lambda:I.identity_claim(claim,key,task,jid,out))
    if valid['claim']:
        check('dispatch',lambda:I.identity_dispatch(dispatch,key,row['task_reference'],observations['claim']['reference'],batch_reference,jid,claim))
    if valid['claim'] and valid['dispatch']:
        check('start',lambda:I.identity_start(start,key,task,observations['claim']['reference'],observations['dispatch']['reference'],jid,claim))
    if observations['packet']['exists'] and not observations['packet']['error'] and valid['start']:
        try:
            packet=I.validate_packet(task,observations['packet']['reference'],prepared_reference,prepared,jid,start)
            C.need(packet['startup_proof_reference']['path']==registration['request']['startup_proof_path'],
                'ORIGINAL_PACKET_PROOF_LOCATOR_MUST_MATCH_REGISTERED_PRODUCER_NOT_REUSED_AS_FRESH_CLOSE_PROOF')
            valid['packet']=True
        except Exception as exc:conflicts.append('packet:'+repr(exc))
    finished=observations['finished']['value']
    if observations['finished']['exists'] and not observations['finished']['error']:
        try:
            C.need(finished['schema']=='N1_SOURCE_FULL_ATTEMPT_DURABLE_V1' and finished['task_key']==key
                and finished['automatic_retry'] is False and finished['once_claim_reference']==observations['claim']['reference']
                and finished['record']['reference']==observations['packet']['reference']
                and finished['record']['worker_start_reference']==observations['start']['reference']
                and finished['record']['task_key']==key and finished['record']['molecule_id']==row['molecule_id'],
                'FINISHED_RECORD_DOES_NOT_MATCH_ACTUAL_PACKET_CLAIM_AND_START')
            C.need(valid['packet'],'FINISHED_RECORD_CANNOT_REPLACE_PACKET_READBACK')
        except Exception as exc:conflicts.append('finished:'+repr(exc))
    if observations['worker_failure']['exists'] and valid['packet']:conflicts.append('SIMULTANEOUS_WORKER_FAILURE_AND_VALID_PACKET')
    result=C.classify(evidence,claim_valid=valid['claim'],dispatch_valid=valid['dispatch'],start_valid=valid['start'],
        packet_valid=valid['packet'],has_second=bool(valid['packet'] and packet['supplement'] is not None and packet['summary']['Pprime_actual_records']==2),
        conflicts=conflicts)
    copy=result['scientific_status_may_be_copied']
    result.update(molecule_id=row['molecule_id'],task_key=key,task_reference=row['task_reference'],baseline_reference=row['baseline_reference'],
        original_baseline_geometry_id=row['baseline_geometry_id'],observations=observations,event_observations=events,
        partial_packet_observations=partial,producer_receipt_observation={k:v for k,v in producer_receipt.items() if k!='value'},producer_receipt_mentions_consumption=mentioned,
        identity_validation=valid,conflicts=conflicts,missing_actual_terminal_claim_parents=missing_accounting,
        actual_producer_job_id=jid,actual_producer_terminal=registration['actual_parent'],worker_start_observed=valid['start'],
        packet_reference=observations['packet']['reference'],scientific_summary=packet['summary'] if copy else None,
        native_extra_conformer_id=packet['supplement']['native_extra_conformer_id'] if copy and packet['supplement'] else None,
        geometry_id=packet['supplement']['geometry_id'] if copy and packet['supplement'] else None,
        geometry_sha256=packet['supplement']['geometry_sha256'] if copy and packet['supplement'] else None,
        common=False,pilot_membership=False,production_membership=False,final_common_reference=None,physical_extra_int64_id=None)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:parser.add_argument('--'+name,type=pathlib.Path,required=True)
    args=parser.parse_args();refs={name:I.request_ref(args.root_preflight,getattr(args,name.replace('-','_')))
        for name in ('prepared','batch','batch-review','pilot-review','request','submission','accounting')}
    proof,catalog,admission=I.admit(__file__,args,OPTIONS,'close',list(refs.values()))
    out=I.new_output(args.output);budget=I.Budget(proof,out,quota_provider_review_reference=admission['quota_provider_review_reference'])
    tests=I.tests();tests_ref=I.json_new(out/'fixtures_before_bodies.json',tests,budget.roots)
    C.need(tests['status']=='PASS','ALL_INHERITED16_AND_NEW8_BOUNDARIES_REQUIRED_BEFORE_SCIENTIFIC_BODIES')
    prepared=I.prepared_inputs(proof,refs['prepared'],refs['pilot-review']);batch=I.read(refs['batch'])
    account,parents,raw=I.accounts(refs['accounting'],prepared['job_id'],proof)
    registration=I.registration(refs['request'],refs['submission'],refs['prepared'],refs['batch'],refs['batch-review'],refs['pilot-review'],prepared,batch,parents)
    index=I.read(prepared['batch_index']);imports=I.read(prepared['imported32'])
    C.need(sum(row['reference']==refs['batch'] for row in index['batches'])==1 and index['batch_count']==72
        and index['task_count']==4599 and index['imported_count']==32,'EXACT_FROZEN_BATCH_INDEX_REQUIRED')
    C.need(batch['schema']=='N1_SOURCE_FULL_FINITE_BATCH_V1' and batch['status']=='FROZEN_UNCONSUMED_KEYS_REQUIRES_INDEPENDENT_ROOT_REVIEW'
        and batch['source_preparation_job_id']==prepared['job_id'] and 0<batch['task_count']==len(batch['tasks'])<=64,'EXACT_FINITE_BATCH')
    F.check_batch_partition(batch,{row['task_key'] for row in imports['imports']})
    I.authorized(proof,[r[n] for r in batch['tasks'] for n in ('task_reference','baseline_reference')])
    producer_receipt=I.observe(registration['output_root']/'receipt.json',decode=True);rows=[]
    for row in batch['tasks']:
        if budget.observe(reserve=V.ADMIN_RESERVE) is not None:break
        task=I.frozen_task(row,refs['prepared'],prepared)
        rows.append(inspect_task(row,task,registration,refs['prepared'],prepared,refs['batch'],parents,producer_receipt))
    missing=sorted({j for row in rows for j in row['missing_actual_terminal_claim_parents']})
    complete=len(rows)==batch['task_count'] and not missing and budget.stop is None
    report={'schema':'N1_SOURCE_REGISTERED_TERMINAL_BATCH_CLOSED_V1',
        'status':'ALL_FROZEN_BATCH_KEYS_TERMINALLY_INSPECTED' if complete else 'TERMINAL_INSPECTION_HELD_OR_PARTIAL_NO_AUTORETRY',
        'job_id':str(proof['job_id']),'endpoint':C.ENDPOINT,'uid':C.UID,'node':C.NODE,
        'prepared_reference':refs['prepared'],'batch_reference':refs['batch'],'finite_batch_review_reference':refs['batch-review'],
        'pilot_review_reference':refs['pilot-review'],'producer_request_reference':refs['request'],'producer_submission_reference':refs['submission'],
        'actual_producer_job_id':registration['job_id'],'actual_producer_terminal':registration['actual_parent'],
        'registered_output_root':str(registration['output_root']),'actual_parent_accounting_reference':refs['accounting'],
        'actual_all_provided_parent_cost_core_seconds':C.parent_cost(parents),'close_parent_cost_pending_terminal_accounting':True,
        'fixtures_reference':tests_ref,'startup_proof_reference':I.ref(args.root_preflight),'closure_source_references':[I.ref(I.HERE/name) for name in I.FILES],
        'producer_receipt_observation':{k:v for k,v in producer_receipt.items() if k!='value'},'producer_receipt_required':False,'producer_receipt_or_C0_fabricated':False,
        'expected':batch['task_count'],'inspected':len(rows),'uninspected_keys':[r['task_key'] for r in batch['tasks'][len(rows):]],
        'outcomes':rows,'outcome_counts':dict(collections.Counter(row['state'] for row in rows)),
        'missing_actual_terminal_claim_parents':missing,'budget':budget.report(),'new_UFF_calls':0,'new_QM_calls':0,
        'automatic_retry_authorized':False,'common':False,'production_membership':False,'source_population_release':False,
        'physical_int64_integration_frozen':False,'scientific_quality_release':False}
    reference=I.json_new(out/'closed_batch.json',report,budget.roots)
    print({'status':report['status'],'closed_batch':reference,'counts':report['outcome_counts']});return 0 if complete else 3


if __name__=='__main__':raise SystemExit(main())
