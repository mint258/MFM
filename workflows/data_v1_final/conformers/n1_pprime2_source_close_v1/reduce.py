"""Readonly union of imported32 and every registered terminal source batch."""
from __future__ import annotations
import argparse,collections,json,pathlib,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.n1_pprime2_source_close_v1 import contract as C,io as I,close_batch as B
F=I.F;V=I.V
OPTIONS=('prepared','pilot-review','closed-index','accounting','root-preflight','quota-provider-review','output')


def imported_packet(row,roster_row,prepared,parents):
    """Read the real old task/packet, not a fabricated new-authority packet."""
    C.require_parents(['4521418'],parents);C.need(row['status']=='IMPORTED_EXISTING_PACKET_FLOAT64_SHA_READBACK_NO_NEW_UFF'
        and row['new_optimizer_calls']==0,'ORIGINAL32_IMPORT_MUST_NOT_GENERATE_NEW_UFF')
    old_task_ref=row['original_task_reference'];path=pathlib.Path(old_task_ref['path'])
    C.need(F.V4.name in path.parts and 'prepared_v1' in path.parts,'ONLY_ORIGINAL_V4_PREPARED32_IMPORT_TASKS')
    task=I.read(old_task_ref);current=I.read(roster_row['task_reference'])
    C.need(row['source_task_reference']==roster_row['task_reference'] and task['task_key']==current['task_key']==row['task_key']
        and task['meta']['molecule_id']==current['meta']['molecule_id']==row['molecule_id']
        and all(task[k]==current[k] for k in ('records','existing_conformers','source_atomic_numbers','baseline_row_sha256','baseline_geometry_id')),
        'IMPORTED32_ORIGINAL_TASK_BASELINE_SOURCE_RECORD_AND_ATOMS_MUST_MATCH')
    F.validate_task(current,prepared['source_population_authority']);F.validate_task(task,row['original_source_population_authority'])
    C.same_sha(row['once_claim_reference'],I.actual_file(V.LEDGER/(row['task_key']+'.json')))
    claim=I.read(row['once_claim_reference']);packet_path=pathlib.Path(row['packet_reference']['path'])
    C.same_sha(claim['core_reference'],I.ref(F.V4/'core.py'))
    C.need(F.V4.name in packet_path.parts and packet_path.parent.name=='packets','ONLY_REAL_ORIGINAL_V4_PACKET_NAMESPACE')
    packet=I.planning.packet_readback(task,row['packet_reference']);runtime=packet['runtime']
    C.need(claim['schema']=='N1_PPRIME2_ONCE_ATTEMPT_STARTED_V2' and claim['task_key']==row['task_key']
        and claim['molecule_id']==row['molecule_id'] and claim['uid']==1278 and str(claim['job_id'])=='4521418'
        and claim['node'].split('.')[0]==C.NODE and claim['seed']==F.proposed_seed(row['molecule_id']) and claim['automatic_retry'] is False
        and str(runtime['job_id'])=='4521418' and runtime['uid']==1278 and runtime['node']==C.NODE
        and runtime==row['packet_runtime'] and packet['source_population_authority_reference']==row['original_source_population_authority']
        and packet['supplement'] is not None and packet['summary']['Pprime_actual_records']==2
        and packet['supplement']['geometry_id']==row['geometry_id'] and packet['supplement']['geometry_sha256']==row['geometry_sha256']
        and packet['supplement']['native_extra_conformer_id']==row['native_extra_conformer_id'],'EXACT_OLD32_PHYSICAL_MAIN_PACKET_AND_ONCE_IDENTITY')
    C.require_parents([str(claim['job_id'])],parents)
    return {'molecule_id':row['molecule_id'],'task_key':row['task_key'],'state':'IMPORTED32_REAL_SECOND_SOURCE_PACKET',
        'safety_consumed':True,'science_result_observed':True,'real_second':True,'scientific_summary':packet['summary'],
        'once_claim_reference':row['once_claim_reference'],'packet_reference':row['packet_reference'],
        'native_extra_conformer_id':row['native_extra_conformer_id'],'geometry_id':row['geometry_id'],
        'geometry_sha256':row['geometry_sha256'],'original_baseline_geometry_id':row['baseline_geometry_id'],
        'new_optimizer_calls_during_import':0,'automatic_retry_authorized':False,'common':False,'production_membership':False,'physical_extra_int64_id':None}


def checked_close(reference,prepared_reference,registration,batch_reference,parents):
    path=pathlib.Path(reference['path']);C.need(C.BASE in path.parents and path.name=='closed_batch.json','ONLY_OWN_READONLY_CLOSED_BATCH_OUTPUT')
    report=I.read(reference,64<<20);jid=str(report['job_id']);C.require_parents([jid],parents)
    C.need(report['schema']=='N1_SOURCE_REGISTERED_TERMINAL_BATCH_CLOSED_V1' and report['endpoint']==C.ENDPOINT and report['uid']==1278
        and report['node']==C.NODE and report['prepared_reference']==prepared_reference and report['batch_reference']==batch_reference
        and report['producer_request_reference']==registration['request_reference'] and report['producer_submission_reference']==registration['submission_reference']
        and report['actual_producer_job_id']==registration['job_id'] and report['registered_output_root']==str(registration['output_root'])
        and report['producer_receipt_or_C0_fabricated'] is False and report['new_UFF_calls']==report['new_QM_calls']==0,
        'CLOSED_BATCH_MUST_BIND_REAL_REGISTRATION_AND_MAIN_IDENTITY')
    C.need(report['closure_source_references']==[I.ref(I.HERE/name) for name in I.FILES],'EXACT_READONLY_CLOSER_SOURCE_PINS')
    proof=I.read(report['startup_proof_reference']);request=proof['request']
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    C.need(str(proof['job_id'])==jid and proof['uid']==1278 and request['scope_key']==C.KEY_CLOSE
        and request['scope_parameters']==C.scope('close') and request['kind']=='analysis' and request['pilot'] is False
        and request['node']==C.NODE and request['cpus']==16 and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and request['execution_argv'][:3]==[PY,'-B',str(I.HERE/'close_batch.py')],
        'ACTUAL_HISTORICAL_CLOSE_PRIMARY_AND_SCOPE_NOT_REUSED_AS_FRESH_REDUCER_PROOF')
    argv=request['execution_argv'];C.need(len(argv)==3+2*len(B.OPTIONS),'COMPLETE_HISTORICAL_CLOSE_ARGV_REQUIRED')
    values={}
    for i,name in enumerate(B.OPTIONS):
        C.need(argv[3+2*i]=='--'+name,'EXACT_HISTORICAL_CLOSE_OPTION_ORDER');values[name]=argv[4+2*i]
    C.need(values['prepared']==prepared_reference['path'] and values['batch']==batch_reference['path']
        and values['request']==registration['request_reference']['path'] and values['submission']==registration['submission_reference']['path']
        and values['batch-review']==report['finite_batch_review_reference']['path'] and values['pilot-review']==report['pilot_review_reference']['path']
        and values['accounting']==report['actual_parent_accounting_reference']['path']
        and values['root-preflight']==report['startup_proof_reference']['path'] and values['output']==str(path.parent),
        'HISTORICAL_CLOSE_EXACT_INPUT_AND_OUTPUT_OPTION_BINDING')
    for source in report['closure_source_references']:C.same_sha(I.request_pin(request,source['path']),source)
    fixtures=I.read(report['fixtures_reference']);C.need(fixtures['status']=='PASS' and fixtures['new_close_tests_run']==8
        and fixtures['executed_before_scientific_bodies'] is True,'REAL_CLOSE_BOUNDARIES_RECEIPT_REQUIRED')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:parser.add_argument('--'+name,type=pathlib.Path,required=True)
    args=parser.parse_args();refs={name:I.request_ref(args.root_preflight,getattr(args,name.replace('-','_')))
        for name in ('prepared','pilot-review','closed-index','accounting')}
    proof,catalog,admission=I.admit(__file__,args,OPTIONS,'reduce',list(refs.values()))
    out=I.new_output(args.output);budget=I.Budget(proof,out,quota_provider_review_reference=admission['quota_provider_review_reference'])
    fixtures=I.tests();fixture_ref=I.json_new(out/'fixtures_before_bodies.json',fixtures,budget.roots)
    C.need(fixtures['status']=='PASS','INHERITED16_AND_NEW8_BEFORE_ANY_SCIENTIFIC_BODY')
    prepared=I.prepared_inputs(proof,refs['prepared'],refs['pilot-review']);account,parents,raw=I.accounts(refs['accounting'],prepared['job_id'],proof)
    review=F.source_review(refs['pilot-review']);old_account_ref=review['terminal_all_known_accounting_reference']
    I.authorized(proof,[old_account_ref]);old_account=I.read(old_account_ref);I.authorized(proof,[old_account['raw_sacct_reference']])
    I.accounts(old_account_ref,'4521417',proof)
    known={'4521326':('FAILED',123),'4521407':('FAILED',39),'4521415':('COMPLETED',60),'4521417':('COMPLETED',100),'4521418':('COMPLETED',90)}
    C.require_parents(known,parents)
    for jid,(state,seconds) in known.items():C.need(parents[jid]['state']==state and int(parents[jid]['alloc_cpus'])==16
        and int(parents[jid]['elapsed_raw_seconds'])==seconds,'ALL_REAL_PRIOR_PREPARE_FAILURE_RESOURCE_AND_PILOT_COSTS_RETAINED')
    for old in old_account['parents']:
        new=parents[str(old['job_id'])]
        C.need(all(new[k]==old[k] for k in ('state','exit_code','alloc_cpus','elapsed_raw_seconds')),'ORIGINAL_ACTUAL_COST_ACCOUNTING_CHANGED')
    roster=list(I.planning.roster_rows(prepared['source_task_roster']));by_key={r['task_key']:r for r in roster}
    imports=I.read(prepared['imported32'])['imports'];union=C.union_source(roster,imports,[])
    imported_keys={r['task_key'] for r in imports};source_index=I.read(prepared['batch_index'])
    expected_batches={r['reference']['path']:r['reference'] for r in source_index['batches']}
    C.need(len(expected_batches)==72 and source_index['task_count']==4599 and source_index['imported_count']==32,'ALL72_FROZEN_BATCHES_REQUIRED')
    index=I.read(refs['closed-index'])
    C.need(index['schema']=='ROOT_N1_SOURCE_TERMINAL_CLOSE_INDEX_V1' and index['reviewer']=='root' and index['endpoint']==C.ENDPOINT
        and index['uid']==1278 and index['prepared_reference']==refs['prepared'] and index['all_known_source_submissions_included'] is True
        and index['all_known_related_terminal_cost_parents_included'] is True
        and index['automatic_retry_authorized'] is False,'ROOT_COMPLETE_ACTUAL_SUBMISSION_INDEX_REQUIRED_NOT_INFERRED_FROM_RECEIPTS')
    registrations=index['registrations'];I.authorized(proof,[r[name] for r in registrations for name in ('request_reference','submission_reference','closed_batch_reference')])
    coverage=[];seen_keys=set();seen_batches=set();registered_parents=set();observed=[];errors=[]
    for item in registrations:
        if budget.observe(reserve=V.ADMIN_RESERVE) is not None:break
        closed_raw=I.read(item['closed_batch_reference'],64<<20);batch_ref=closed_raw['batch_reference'];batch=I.read(batch_ref)
        C.need(expected_batches.get(batch_ref['path'])==batch_ref and batch_ref['path'] not in seen_batches,'EXACT_UNIQUE_INITIAL_BATCH_REGISTRATION')
        seen_batches.add(batch_ref['path']);I.authorized(proof,[batch_ref,closed_raw['finite_batch_review_reference']])
        reg=I.registration(item['request_reference'],item['submission_reference'],refs['prepared'],batch_ref,closed_raw['finite_batch_review_reference'],refs['pilot-review'],prepared,batch,parents)
        C.need(reg['job_id'] not in registered_parents,'ONE_ACTUAL_REGISTRATION_PER_PARENT');registered_parents.add(reg['job_id'])
        closed=checked_close(item['closed_batch_reference'],refs['prepared'],reg,batch_ref,parents)
        prior={r['task_key']:r for r in closed['outcomes']};C.need(len(prior)==len(closed['outcomes']),'NO_DUPLICATE_KEYS_INSIDE_CLOSE_REPORT')
        F.check_batch_partition(batch,imported_keys);allowed={r['task_key'] for r in batch['tasks']}
        C.need(set(prior)<=allowed and not(allowed&seen_keys),'ALL_REGISTERED_BATCH_KEYS_MUTUALLY_EXCLUSIVE')
        receipt=I.observe(reg['output_root']/'receipt.json',decode=True)
        for row in batch['tasks']:
            if budget.observe(reserve=V.ADMIN_RESERVE) is not None:break
            key=row['task_key'];C.need(key in by_key and row==by_key[key],'EXACT_FROZEN_ROSTER_ROW_IN_REGISTERED_BATCH')
            task=I.frozen_task(row,refs['prepared'],prepared)
            actual=B.inspect_task(row,task,reg,refs['prepared'],prepared,batch_ref,parents,receipt)
            if key in prior:
                C.need(all(actual[k]==prior[key][k] for k in actual if k!='actual_producer_terminal'),
                    'TERMINAL_DURABLE_EVIDENCE_CHANGED_AFTER_READONLY_CLOSE')
            coverage.append(actual);seen_keys.add(key)
        observed.append({'request_reference':item['request_reference'],'submission_reference':item['submission_reference'],
            'closed_batch_reference':item['closed_batch_reference'],'job_id':reg['job_id'],'actual_terminal':parents[reg['job_id']],
            'batch_reference':batch_ref,'producer_receipt_required':False})
    C.union_source(roster,imports,coverage)
    for row in imports:
        if budget.observe(reserve=V.ADMIN_RESERVE) is not None:break
        coverage.append(imported_packet(row,by_key[row['task_key']],prepared,parents));seen_keys.add(row['task_key'])
    registered_keys={r['task_key'] for item in observed for r in I.read(item['batch_reference'])['tasks']}
    for key in sorted(set(by_key)-seen_keys):
        if budget.observe(reserve=V.ADMIN_RESERVE) is not None:break
        if key in registered_keys:
            coverage.append(dict(molecule_id=by_key[key]['molecule_id'],task_key=key,state='UNINSPECTED_REGISTERED_KEY_NO_AUTORETRY',
                safety_consumed=True,science_result_observed=False,real_second=False,automatic_retry_authorized=False));continue
        claim=I.observe(V.LEDGER/(key+'.json'),decode=True);missing=[]
        if claim['exists']:
            owner=I.claim_owner(claim)
            if owner not in parents:missing.append(owner or 'UNPARSEABLE_CLAIM_OWNER')
            else:C.require_parents([owner],parents)
            errors.append({'task_key':key,'reason':'CLAIM_WITHOUT_CLOSED_REGISTERED_BATCH','owner':owner,'missing_actual_terminal_parents':missing})
        actual=C.classify({'claim':claim['exists']},conflicts=['ORPHAN_CLAIM_REQUIRES_ROOT_REGISTRATION_REVIEW'] if claim['exists'] else [])
        if not claim['exists']:actual['state']='UNREGISTERED_KEY_NO_CANONICAL_CLAIM_NOT_PHYSICALLY_INSPECTED'
        actual.update(molecule_id=by_key[key]['molecule_id'],task_key=key,once_claim_observation=claim,missing_actual_terminal_claim_parents=missing,
            absence_basis='NO_CANONICAL_CLAIM_AND_ROOT_ATTESTED_NO_OTHER_SOURCE_REGISTRATION' if not claim['exists'] else None,
            common=False,production_membership=False,physical_extra_int64_id=None)
        coverage.append(actual);seen_keys.add(key)
    ledger_keys={p.stem for p in V.LEDGER.glob('*.json')};unexpected=sorted(ledger_keys-set(by_key))
    for key in unexpected:
        observation=I.observe(V.LEDGER/(key+'.json'),decode=True);owner=I.claim_owner(observation)
        if owner in parents:C.require_parents([owner],parents)
        errors.append({'task_key':key,'reason':'UNEXPECTED_CANONICAL_ONCE_KEY','observation':observation,
            'missing_actual_terminal_parents':[] if owner in parents else [owner or 'UNPARSEABLE_CLAIM_OWNER']})
    C.need(len(coverage)==len({r['task_key'] for r in coverage}),'EVERY_SOURCE_KEY_COUNTED_AT_MOST_ONCE')
    mother_ids=[];mother_reasons=collections.Counter();I.source_check(prepared['mother_inventory'])
    with pathlib.Path(prepared['mother_inventory']['path']).open('rb') as stream:
        for line in stream:
            C.need(len(line)<=64<<10,'BOUNDED_MOTHER_METADATA_ROW');row=json.loads(line)
            mother_ids.append(row['molecule_id']);mother_reasons[row['reason'] or 'SOURCE_BASELINE_READY']+=1
    audit=I.read(prepared['role_status_usable_audit'])
    C.need(len(mother_ids)==len(set(mother_ids))==5105 and F.sha_value(sorted(mother_ids))==audit['all_mother_ids_sha256']
        and dict(mother_reasons)==prepared['reason_counts'],'ALL5105_SOURCE_MOTHER_AND_EXCLUSION_REASONS_CONSERVED')
    counts=collections.Counter(r['state'] for r in coverage);missing=sorted({j for r in coverage for j in r.get('missing_actual_terminal_claim_parents',[])}
        |{j for error in errors for j in error.get('missing_actual_terminal_parents',[])})
    complete=len(coverage)==4631 and sum(bool(r['real_second']) for r in coverage)==4631 and not(errors or missing or unexpected or budget.stop)
    outcomes=I.write(out/'source_outcomes.jsonl',b''.join(C.canonical(row)+b'\n' for row in coverage),budget.roots)
    summary={'schema':'N1_REGISTERED_TERMINAL_SOURCE_REDUCTION_V1',
        'status':'ALL4631_REAL_SECOND_SOURCE_PACKETS_CLOSED_NO_FINAL_MEMBERSHIP' if complete else 'SOURCE_PENDING_UNKNOWN_OR_CONFLICT_NO_AUTORETRY',
        'job_id':str(proof['job_id']),'endpoint':C.ENDPOINT,'uid':1278,'node':C.NODE,'prepared_reference':refs['prepared'],
        'closed_index_reference':refs['closed-index'],'accounting_reference':refs['accounting'],'raw_sacct_reference':account['raw_sacct_reference'],
        'actual_all_provided_terminal_parent_cost_core_seconds':C.parent_cost(parents),'provided_terminal_parent_ids':sorted(parents),
        'current_reducer_parent_cost_pending_terminal_accounting':True,'cost_is_final_pipeline_total':False,
        'mother_count':5105,'eligible_count':4631,'imported32_expected':32,'new_source_expected':4599,'coverage_count':len(coverage),
        'imported32_observed':counts['IMPORTED32_REAL_SECOND_SOURCE_PACKET'],'outcome_counts':dict(counts),'observed_registered_batches':observed,
        'unregistered_frozen_batch_count':72-len(seen_batches),'uninspected_keys':sorted(set(by_key)-{r['task_key'] for r in coverage}),
        'missing_actual_terminal_claim_parents':missing,'registration_errors':errors,'unexpected_once_ledger_keys':unexpected,
        'mother_reason_counts':dict(mother_reasons),'source_outcomes':outcomes,'fixtures_reference':fixture_ref,
        'startup_proof_reference':I.ref(args.root_preflight),'closure_source_references':[I.ref(I.HERE/name) for name in I.FILES],
        'observed_optimizer_calls_attempted_in_validated_packets_including_import32':sum(r.get('scientific_summary',{}).get('optimizer_calls_attempted',0) for r in coverage if r.get('scientific_summary')),
        'observed_optimizer_calls_finished_in_validated_packets_including_import32':sum(r.get('scientific_summary',{}).get('optimizer_calls_finished',0) for r in coverage if r.get('scientific_summary')),
        'optimizer_calls_in_unknown_or_invalid_packets':None,'optimizer_counts_are_complete_all_attempt_totals':complete,
        'budget':budget.report(),'new_UFF_calls':0,'new_QM_calls':0,'automatic_retry_authorized':False,
        'common':False,'pilot_membership':False,'production_membership':False,'final_common_reference':None,
        'source_population_release':False,'scientific_quality_release':False,'physical_int64_integration_frozen':False}
    reference=I.json_new(out/'reduction.json',summary,budget.roots);print({'status':summary['status'],'reduction':reference,'counts':dict(counts)})
    return 0 if complete else 3


if __name__=='__main__':raise SystemExit(main())
