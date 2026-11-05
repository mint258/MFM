"""Finite reviewed metadata epoch, preserving every original physical parent."""
import argparse,csv,io,json,os,sys,time,traceback
from pathlib import Path
from types import SimpleNamespace
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_continuation_alpha_v3 import contracts as A
from pubchem_c_metadata_recovery_v4 import controller as R
from . import epoch as E,policy as P
S=R.S;V=R.V;C=R.C;CONTROL=R.CONTROL
close_new=R.close_new;account_row=R.account_row;materialize_one=R.materialize_one;actual_imports=R.actual_imports
data_locator=R.data_locator;meta=R.meta;pin=R.pin;available_controller_lock=R.available_controller_lock


def registry(state_dir,root,grant,partition,initial,initial_attempts,roots,old_states,capture=False):
    rows=[];folders={};seen=set();legacy_seen=set();cached={};attempted=set();claims=set()
    for state in [*old_states,*([state_dir] if state_dir and Path(state_dir).exists() else [])]:
        state=E.own_state(state)
        for p in state.glob('attempt_*.json'):
            row=meta(pin(p));i=row['shard_index'];Q.need(type(i) is int and 52<=i<=499,'ONLY_ORIGINAL_PARTITION_INTENT');attempted.add(i)
        for p in state.glob('terminal_*.json'):
            row=meta(pin(p));i=row['shard_index'];Q.need(i not in cached or cached[i]==row,'CONFLICTING_HISTORICAL_TERMINAL_CACHE');cached[i]=row
    for p in sorted((CONTROL/'claims').glob('*.json')):
        registration=meta(pin(p));rr=registration['queue_request_reference'];req=meta(rr);key=req.get('scope_key')
        if key not in (R.OLD_KEY,R.REPAIR_KEY,A.KEY):continue
        plan=meta(req['adapter']['input_reference']);i=plan['shard_index'];folder=Path(rr['path']).parent
        token=(key,i);Q.need(token not in legacy_seen,'NO_DUPLICATE_PHYSICAL_REGISTRATION');legacy_seen.add(token)
        if key==R.OLD_KEY:
            Q.need(i<=51,'NO_OLD_PROTOCOL_NEW_SHARD');sub=Q.load(folder/'submission.json')
            expected='1884853' if i==51 else initial[i]['job_id'];Q.need(sub['job_id']==expected and expected in initial_attempts,'EXACT_IMPORTED_LEGACY_PARENT');continue
        if key==R.REPAIR_KEY:
            Q.need(i==51 and Q.load(folder/'submission.json')['job_id']=='1884855','EXACT_OLD_REPAIRED51');continue
        Q.need(i not in seen and type(i) is int and 52<=i<=499,'ONLY_ONE_ORIGINAL52_499_REGISTRATION');seen.add(i)
        origin=plan['continuation_range_review_reference'];Q.need(origin['path'] in roots,'NO_UNREVIEWED_ORIGIN_GRANT')
        original=roots[origin['path']];Q.need(Q.ref(origin['path'])==origin and original['source_references']==A.sources(),'UNCHANGED_ORIGIN_GRANT_AND13')
        A.validate(plan);Q.need(req['adapter']['producer_plan_reference']==req['adapter']['input_reference'] and req['endpoint']==Q.ENDPOINT
          and req['uid']==1264 and req['cpus']==16 and req['memory_policy']==Q.POLICY and req['node']==plan['node']
          and req['wall_seconds']==28800 and req['kind']=='analysis' and req['pilot'] is False,'EXACT_REGISTERED_PRODUCER_PLAN_AND_ACTUAL_RESOURCE_IDENTITY')
        folders[i]=(folder,req)
        for ref in req['adapter']['data_reference_locators_only']:data_locator(ref)
        if not (folder/'submission.json').exists():row={'shard_index':i,'status':'UNKNOWN','root_range_review_reference':origin,'queue_control_directory':str(folder)}
        else:
            sub=Q.load(folder/'submission.json');jid=sub.get('job_id')
            Q.need(sub.get('sbatch_returncode')==0 and type(jid) is str and jid.isdecimal() and sub['queue_request_reference']==rr,'ACTUAL_EXISTING_SUBMISSION_NO_RETRY')
            q=Q.query(['sacct','-j',jid,'--format=JobIDRaw,UID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition','-P'])
            observed=[r for r in csv.DictReader(io.StringIO(q['stdout']),delimiter='|') if r.get('JobIDRaw')==jid]
            Q.need(q['returncode']==0 and len(observed)==1 and observed[0]['UID']=='1264','ACTUAL_REGISTERED_PARENT_STATE')
            status=Q.state(observed[0]['State'])
            if status not in S.TERMINAL:
                row={'shard_index':i,'status':status,'job_id':jid,'queue_control_directory':str(folder),
                  'queue_request_reference':rr,'submission_reference':pin(folder/'submission.json'),'root_range_review_reference':origin}
            else:
                if i in cached:account_ref=cached[i]['accounting_reference']
                else:
                    before=set(folder.glob('accounting_*.json'));V.account(folder);after=set(folder.glob('accounting_*.json'))-before
                    Q.need(len(after)==1,'ONE_NEW_REAL_ACCOUNTING');account_ref=pin(after.pop())
                row=close_new(folder,req,sub,account_ref,original,origin,partition)
                Q.need(meta(account_ref)['actual_parent']['NodeList']==req['node'],'ACTUAL_PARENT_NODE_EQUALS_REGISTERED_PLAN')
                if i in cached:Q.need(row==cached[i],'ORIGINAL_TERMINAL_CLOSURE_EXACT_REVALIDATION')
                if state_dir is not None:
                    target=Path(state_dir)/('terminal_%04d.json'%i)
                    if target.exists():Q.need(meta(pin(target))==row,'IMMUTABLE_NEW_TERMINAL_CACHE')
                    else:R.durable(target,row,Path(state_dir))
        rows.append(row)
    Q.need(set(cached)<=seen,'NO_ORPHAN_HISTORICAL_TERMINAL_CACHE')
    population,attempts=P.merge_rows(initial,rows,initial_attempts)
    # A physical ordinal claim without registration/closed population is never free.
    claim_dir=C.ROOT/'control/pubchem_ordinal_claims'/C.RAW_SHA
    for p in claim_dir.glob('shard_*.json'):
        c=meta(pin(p));i=c['range']['shard_index'];Q.need(type(i) is int and 0<=i<=499 and i not in claims,'ONE_EXACT_NATIVE_ORDINAL_CLAIM');claims.add(i)
        Q.need(i in population and c['uid']==1264 and c['range']==partition['shards'][i]
          and c['manifest_reference']==root['full_shard_manifest_reference'] and c['job_id']==population[i].get('job_id'),'ALL_ACTUAL_CLAIMS_MATCH_ACTUAL_REGISTERED_PARENT')
        if i in folders:
            request=folders[i][1];Q.need(c['plan_reference']==request['adapter']['input_reference'] and c['node']==request['node'],'CLAIM_SOURCE_PLAN_JOB_NODE_EXACT')
        else:Q.need(pin(p)==meta(population[i]['receipt_reference'])['claim_reference'],'EXACT_IMPORTED_CLAIM_REFERENCE')
    for i in attempted|claims:
        Q.need(i in population,'HOLD_CONSUMED_INTENT_OR_CLAIM_WITHOUT_ACTUAL_PARENT')
    return population,attempts,folders


def run(args):
    Q.login();Q.need(args.root_run_reviewed_manual_epoch and args.reason.strip(),'ROOT_MANUAL_INVOCATION_ONLY')
    review,root,roots,identity,cut=E.require_review(Q.ref(args.epoch_review));grant=review['new_grant_reference'];effective_cap=P.effective_cap(root)
    def decision(population,attempted,free,now,deadline):return P.resource_decision(population,attempted,free,now,deadline,effective_cap)
    # Check identity/lock before mkdir, binding, state or any dispatch intent.
    if E.live(identity):print('WAIT_PREDECESSOR_LIVE_ZERO_INTENT');return 2
    fd=E.lock_global()
    if fd is None:print('WAIT_GLOBAL_OWNER_ZERO_INTENT');return 2
    try:
        gate=P.transition_gate(E.live(identity),True,cut['old_deadline_unix_seconds'],time.time(),root['deadline_unix_seconds'],
          cut['stable_state_inventory']==E.state_inventory(cut['predecessor_state_directory'])
          and all(inv==E.state_inventory(inv['directory']) for inv in cut['earlier_state_inventories']))
        if gate!='ROOT_REVIEWED_NEW_EPOCH_CAN_OBSERVE':print(gate);return 2
        state=E.own_state(review['new_state_directory']);Q.need(str(state)==root['manual_resource_epoch']['new_state_directory'],'EXACT_NEW_REVIEWED_STATE')
        Q.need(str(state)!=cut['predecessor_state_directory'],'NEVER_WRITE_OLD_STATE');state.mkdir(parents=True,exist_ok=True,mode=0o700)
        binding={'root_range_review_reference':grant,'epoch_review_reference':Q.ref(args.epoch_review),
          'predecessor_cutover_reference':review['cutover_reference'],'deadline_unix_seconds':root['deadline_unix_seconds'],
          'effective_max_nonterminal_C_parents':effective_cap,'reserved_non_C_cpus':16,
          'old_deadline_unix_seconds_unchanged':cut['old_deadline_unix_seconds'],'scientific_source13_references':A.sources()}
        if (state/'binding.json').exists():Q.need(meta(pin(state/'binding.json'))==binding,'SAME_IMMUTABLE_MANUAL_EPOCH_NO_RENEWAL')
        else:R.durable(state/'binding.json',binding,state)
        R.durable(state/('launch_%020d.json'%time.time_ns()),{'actual_identity':E.process(os.getpid()),'epoch_review_reference':Q.ref(args.epoch_review),
          'new_grant_reference':grant,'effective_max_nonterminal_C_parents':effective_cap,'reserved_non_C_cpus':16,
          'reason':args.reason,'metadata_source_references':E.sources(),'exit_code_not_yet_known':True},state)
        frozen,partition,initial,initial_attempts,base=actual_imports(root,grant)
        adoption=meta(review['adoption_reference']);adopted=adoption['registered_requests'];old_states=[cut['predecessor_state_directory'],*review.get('earlier_state_directories',[])]
        last=None
        while True:
            population,attempts,folders=registry(state,root,grant,partition,initial,initial_attempts,roots,old_states)
            for key,reference in adopted.items():Q.need(int(key) in folders and pin(folders[int(key)][0]/'request.json')==reference,'ALL_ADOPTED_PARENTS_STILL_EXACT')
            attempted={int(p.stem.split('_')[-1]) for p in state.glob('attempt_*.json')}
            for prior in old_states:attempted.update(int(p.stem.split('_')[-1]) for p in Path(prior).glob('attempt_*.json'))
            for i,(folder,req) in folders.items():
                Q.need(str(i) in adopted or (state/('attempt_%04d.json'%i)).exists(),'NO_UNREVIEWED_EXTERNAL_REGISTRATION')
            free={n:Q.free_cpus({'node':n})['free_cpus'] for n in S.NODES}
            action,index,node=P.safe_next(population,attempted,set(population),decision,free,time.time(),root['deadline_unix_seconds'])
            totals={k:sum(v.get('counts',{}).get(k,0) for v in population.values() if v['status']=='CLOSED') for k in ('accepted','chemReject','technicalUnresolved')}
            cost_scope=P.exact_union([*({'endpoint':Q.ENDPOINT,'uid':1264,'job_id':r['job_id'],'allocated_core_seconds':r['actual_allocated_core_seconds']} for r in attempts.values()),
              {k:review['source3_actual_evidence'][k] for k in ('endpoint','uid','job_id','allocated_core_seconds')}])
            compact={'action':action,'index':index,'node':node,'closed':sum(v['status']=='CLOSED' for v in population.values()),
              'counts':totals,'active_or_unknown':{str(i):{'status':v['status'],'job_id':v.get('job_id')} for i,v in population.items() if v['status']!='CLOSED'},
              'all_actual_parent_ids':sorted(attempts),'actual_unique_C_parent_core_seconds':sum(v['actual_allocated_core_seconds'] for v in attempts.values()),
              'reported_cost_scope':'C_PRODUCTION_PLUS_QA0_PLUS_THIS_EPOCH_SOURCE3_NOT_A_GLOBAL_LEDGER_TOTAL',
              'this_reported_scope_core_seconds':sum(r['allocated_core_seconds'] for r in cost_scope),
              'effective_max_nonterminal_C_parents':effective_cap,'actual_known_nonterminal_C_parents':P.known_nonterminal_count(population),
              'counted_nonterminal_or_opaque_C_slots':P.nonterminal_count(population),'reserved_non_C_cpus':16,
              'historical_base_v3_cap6_is_not_the_effective_cap':True,
              'source3_actual_evidence':review['source3_actual_evidence'],'global_owned_cost_checkpoint_reference':review['global_owned_cost_checkpoint_reference'],
              'old_deadline_unix_seconds_unchanged':cut['old_deadline_unix_seconds'],'new_fixed_deadline':root['deadline_unix_seconds'],'pool_release_authorized':False}
            encoded=Q.canonical(compact)
            if encoded!=last:R.event(state,'ACTUAL_STATE_SNAPSHOT',**compact);last=encoded
            if action.startswith(('HOLD','ALL500','FINITE_')):return 0 if action.startswith('ALL500') else 2
            for i,(folder,req) in folders.items():
                row=population[i]
                if args.observe_only or row['status'] in S.TERMINAL or row['status']=='CLOSED' or Path(req['ready_path']).exists():continue
                old=req['adapter']['producer_plan_reference'];origin=meta(old)['continuation_range_review_reference']
                if origin!=grant:
                    expected={'shard_index':i,'job_id':row['job_id'],'queue_request_reference':pin(folder/'request.json'),
                      'submission_reference':pin(folder/'submission.json'),'origin_grant_reference':origin}
                    Q.need(expected in review['explicit_old_held_admissions'],'OLD_HELD_AFTER_DEADLINE_REQUIRES_EXPLICIT_ROOT_ADOPTION')
                current={n:Q.free_cpus({'node':n})['free_cpus'] for n in S.NODES};after=dict(current);after[req['node']]-=16
                if P.nonterminal_count(population)<=effective_cap and current[req['node']]>=16 and max(after.values())>=16:
                    locked=available_controller_lock()
                    if locked is not None:
                        try:
                            if origin!=grant:R.event(state,'ROOT_EXPLICIT_EXISTING_HELD_RESOURCE_ADOPTION',adoption=expected,epoch_review_reference=Q.ref(args.epoch_review))
                            Q.need(P.nonterminal_count(population)==P.known_nonterminal_count(population),'NO_OPAQUE_PARENT_COUNT_MASQUERADING_AS_ACTUAL_CAPACITY')
                            resource_proof=R.durable(state/('effective_resource_proof_%020d.json'%time.time_ns()),{
                              'schema':'ACTUAL_PUBCHEM_EFFECTIVE_RESOURCE_PROOF_V2','endpoint':Q.ENDPOINT,'uid':1264,
                              'observed_unix_seconds':time.time(),'gate_stage':'PRE_OBSERVER_CPU_ADMISSION_NOT_CHILD_STARTUP',
                              'child_startup_proof_pending':True,'fresh_storage_admission_delegated_to_unchanged_observer':True,
                              'root_epoch_review_reference':Q.ref(args.epoch_review),'actual_effective_authority_reference':grant,
                              'effective_max_nonterminal_C_parents':effective_cap,'actual_nonterminal_C_parents':P.known_nonterminal_count(population),
                              'original_producer_origin_grant_reference':origin,'registered_queue_request_reference':pin(folder/'request.json'),
                              'submission_reference':pin(folder/'submission.json'),'all_user_observed_free_CPUs':current,'post_allocation_free_CPUs':after,
                              'reserved_non_C_cpus':16,'base_v3_frame6_overridden_only_for_resource_coordination':True,
                              'actual_metadata_identity':E.process(os.getpid()),'scientific13_and_base8_not_modified':True},state)
                            R.event(state,'ACTUAL_EFFECTIVE_CAP_BEFORE_HELD_ACTIVATION',effective_max_nonterminal_C_parents=effective_cap,
                              actual_nonterminal_C_parents=P.known_nonterminal_count(population),registered_queue_request_reference=pin(folder/'request.json'),
                              actual_effective_resource_proof_reference=resource_proof,
                              proof_bound_effective_authority_reference=grant,original_producer_origin_grant_reference=origin,
                              old_origin_is_not_relabelled_as_new_authority=True,actual_free_CPUs=current,reserved_non_C_cpus=16)
                            V.observe(folder,folder/'request.json',req,Q.load(folder/'submission.json'),30)
                            proof_path=Path(req['adapter']['startup_proof_path'])
                            if proof_path.exists():R.event(state,'ACTUAL_PROOF_CHAIN_AND_RESOURCE_AUTHORITY',producer_startup_proof_reference=pin(proof_path),
                              actual_effective_resource_authority_reference=grant,effective_max_nonterminal_C_parents=effective_cap,
                              actual_effective_resource_proof_reference=resource_proof,
                              original_producer_origin_grant_reference=origin,base_producer_proof_not_rewritten=True)
                        finally:os.close(locked)
            if action=='ELIGIBLE' and not args.observe_only:
                locked=available_controller_lock()
                if locked is not None:
                    try:
                        fresh,fees,_=registry(state,root,grant,partition,initial,initial_attempts,roots,old_states)
                        cpus={n:Q.free_cpus({'node':n})['free_cpus'] for n in S.NODES};a2,i2,n2=P.safe_next(fresh,attempted,set(fresh),decision,cpus,time.time(),root['deadline_unix_seconds'])
                        if a2=='ELIGIBLE':
                            claim=C.ROOT/'control/pubchem_ordinal_claims'/C.RAW_SHA/('shard_%06d.json'%i2)
                            Q.need(not claim.exists(),'EXISTING_ORDINAL_CLAIM_NO_RETRY')
                            Q.need(P.nonterminal_count(fresh)==P.known_nonterminal_count(fresh)<effective_cap,'REAL_REGISTERED_PARENT_COUNT_BEFORE_NEW_SUBMISSION')
                            R.event(state,'ROOT_EFFECTIVE_RESOURCE_DISPATCH_DECISION',shard_index=i2,node=n2,
                              actual_effective_authority_reference=grant,epoch_review_reference=Q.ref(args.epoch_review),
                              effective_max_nonterminal_C_parents=effective_cap,actual_nonterminal_C_parents_before_submission=P.known_nonterminal_count(fresh),
                              observed_free_CPUs=cpus,reserved_non_C_cpus=16,old_base6_is_not_new_resource_authority=True)
                            R.durable(state/('attempt_%04d.json'%i2),{'shard_index':i2,'root_range_review_reference':grant,'node':n2,'status':'INTENT_BEFORE_PLAN_SUBMISSION'},state)
                            tag,folder,plan_path,queue=materialize_one(root,grant,base,partition,i2,n2,time.time())
                            call=SimpleNamespace(reviewer='root',controller_review=Path(root['base_controller_review_reference']['path']),authority=Path(root['resource_authority_reference']['path']),
                              storage_review=R.SCOPE7,producer='readonly',deployment=None,input=plan_path,node=n2,wall_seconds=28800,job_name='dv1_pubchem_cont_v3_%04d'%i2,output=queue)
                            qfolder,rp,req=V.prepare(call);sub=V.submit_held(qfolder,rp,req)
                            R.event(state,'ACTUAL_HELD_SUBMISSION_NO_RETRY',shard_index=i2,submission_reference=pin(qfolder/'submission.json'),
                              actual_effective_authority_reference=grant,effective_max_nonterminal_C_parents=effective_cap,
                              actual_nonterminal_C_parents_before_submission=P.known_nonterminal_count(fresh),new_actual_registered_submission_count=1)
                    finally:os.close(locked)
            if args.single_cycle:return 0
            time.sleep(min(30,max(0,root['deadline_unix_seconds']-time.time())))
    except Exception as exc:
        if 'state' in locals() and state.exists():R.event(state,'HOLD_EXCEPTION_NO_RETRY_NO_RENEWAL_NO_SIGNALS',error=repr(exc),traceback=traceback.format_exc())
        raise
    finally:os.close(fd)


def main():
    Q.login();Q.need(Path(__file__).absolute()==Path(sys.modules['__main__'].__file__).absolute()==E.HERE/'controller.py','EXACT_NEW_METADATA_CONTROLLER_PRIMARY')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch-review',type=Path,required=True)
    p.add_argument('--root-run-reviewed-manual-epoch',action='store_true');p.add_argument('--reason',required=True)
    p.add_argument('--single-cycle',action='store_true');p.add_argument('--observe-only',action='store_true');return run(p.parse_args())

if __name__=='__main__':raise SystemExit(main())
