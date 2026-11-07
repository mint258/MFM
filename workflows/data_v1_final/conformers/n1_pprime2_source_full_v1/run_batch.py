"""One independently reviewed finite source batch; no queue, retry or release."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,multiprocessing as mp,os,pathlib,socket,sys,time,traceback
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.n1_pprime2_source_full_v1 import contract as C,core,io as I,planning

def worker_attempt(item):
    task,claim_ref,intent_ref=item;out=pathlib.Path(core.CTX['checkpoint_output_root']);key=task['task_key']
    runtime=dict(core.CTX['runtime']);start={'schema':'N1_SOURCE_FULL_WORKER_STARTED_V1','task_key':key,
        'molecule_id':task['meta']['molecule_id'],'once_claim_reference':claim_ref,'dispatch_intent_reference':intent_ref,
        'runtime':runtime,'parent_pid':os.getppid(),'observed_unix_seconds':time.time(),'common':False,'production_membership':False}
    reference=I.json_new(out/'worker_starts'/(key+'.json'),start,[out,I.LEDGER]);I.fsync_directory(out/'worker_starts')
    try:
        packet=core.process_task(task)
        return {'packet':packet,'worker_start_reference':reference}
    except BaseException as exc:
        I.json_new(out/'worker_failures'/(key+'.json'),dict(start,status='UNKNOWN_CONSUMED_NO_AUTORETRY',error=repr(exc),traceback=traceback.format_exc()),[out,I.LEDGER]);raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    options=('prepared','prepare-accounting','batch','batch-review','pilot-review','root-preflight','quota-provider-review','ledger-root','output')
    for name in options:p.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args();refs={name:I.request_ref(a.root_preflight,getattr(a,name.replace('-','_'))) for name in ('prepared','prepare-accounting','batch','batch-review','pilot-review')}
    proof,catalog,admission=I.admit(__file__,a,options,C.SCOPE_KEY,C.SCOPE,'conformer',list(refs.values()))
    C.need(a.ledger_root==I.LEDGER,'ONE_ORIGINAL_N1_ONCE_LEDGER_ONLY');out=I.new_output(a.output)
    for name in ('packets','dispatch_intents','worker_starts','worker_failures','finished'): (out/name).mkdir()
    I.fsync_directory(out);budget=I.Budget(proof,out,a.ledger_root,quota_provider_review_reference=admission['quota_provider_review_reference'])
    started=time.monotonic();tests=I.test10();tests_ref=I.json_new(out/'synthetic10_and_full_boundaries.json',tests,budget.roots)
    C.need(tests['status']=='PASS','ORIGINAL10_AND_NEW_BOUNDARIES_MUST_PASS_BEFORE_ANY_SOURCE_BODY')
    prepared=I.read(refs['prepared']);batch=I.read(refs['batch']);science_review=C.source_review(refs['pilot-review'])
    C.need(prepared['schema']=='N1_PPRIME2_SOURCE_FULL_PREPARED_V1' and prepared['status']=='ACTUAL_FULL_SOURCE_TASKS_FROZEN_NO_GENERATION'
        and prepared['mother_count']==5105 and prepared['eligible_count']==prepared['selected_count']==4631
        and prepared['imported_count']==32 and prepared['new_attempt_count']==4599 and prepared['batch_count']==72
        and prepared['common'] is False and prepared['pilot_membership'] is False and prepared['production_membership'] is False
        and prepared['physical_int64_integration_frozen'] is False and prepared['catalog']==I.ref(I.HERE/'frozen_sources.json'),'EXACT_FROZEN_FULL_SOURCE_ROSTER_NOT_FINAL_COMMON')
    C.need(prepared['science_cost_review_reference']==refs['pilot-review'] and prepared['once_ledger_root']==str(I.LEDGER),'ACTUAL32_IMPORT_AND_SAME_ONCE_LEDGER')
    account=I.read(refs['prepare-accounting']);I.authorized(proof,[account['raw_sacct_reference']]);terminal=I.terminal_c0(refs['prepare-accounting'],prepared['job_id'])
    I.authorized(proof,[prepared['batch_index'],prepared['source_population_authority'],prepared['imported32']])
    index=I.read(prepared['batch_index']);authority=I.read(prepared['source_population_authority']);imported=I.read(prepared['imported32'])
    C.need(len([row for row in index['batches'] if row['reference']==refs['batch']])==1 and index['batch_count']==72
        and index['task_count']==4599 and index['imported_count']==32,'BATCH_IN_FROZEN_MUTUALLY_DISJOINT_PARTITION')
    C.need(batch['schema']=='N1_SOURCE_FULL_FINITE_BATCH_V1' and batch['status']=='FROZEN_UNCONSUMED_KEYS_REQUIRES_INDEPENDENT_ROOT_REVIEW'
        and batch['source_preparation_job_id']==prepared['job_id'] and batch['source_population_authority']==prepared['source_population_authority']
        and batch['source_task_roster']==prepared['source_task_roster'] and 0<batch['task_count']==len(batch['tasks'])<=64,'EXACT_REVIEWED_FINITE_SOURCE_BATCH')
    C.need(authority['schema']=='N1_PPRIME2_SOURCE_FULL_POPULATION_AUTHORITY_V1' and authority['status']=='ORIGINAL_SOURCE_FULL_POPULATION_CLOSED_NO_FINAL_MEMBERSHIP'
        and authority['mother_count']==authority['expected_mother_count']==5105 and authority['eligible_source_baselines']==4631
        and authority['common'] is False and authority['production_membership'] is False,'ORIGINAL_SOURCE_AUTHORITY_NO_POPULATION_RELEASE')
    review=C.finite_batch_review(refs['batch-review'],refs['prepared'],refs['batch'],batch,admission['quota_provider_review_reference'],refs['pilot-review'])
    C.need(science_review['formal_full_source_job_authorized_by_this_review'] is False and review['new_optimizer_attempts_authorized_for_exact_keys'] is True,'IMPLEMENTATION_REVIEW_NOT_SUBSTITUTED_FOR_FINITE_WAVE_AUTHORITY')
    imported_keys={row['task_key'] for row in imported['imports']};C.check_batch_partition(batch,imported_keys);tasks=[];task_refs={}
    I.authorized(proof,[*[row['task_reference'] for row in batch['tasks']],*[row['baseline_reference'] for row in batch['tasks']]])
    for row in batch['tasks']:
        C.need(row['state']=='UNCONSUMED_NEW_ATTEMPT_NOT_AUTHORIZED_UNTIL_FINITE_ROOT_REVIEW' and row['task_key'] not in imported_keys,'IMPORTED32_CANNOT_ENTER_OPTIMIZER_BATCH')
        task=I.read(row['task_reference']);C.validate_task(task,prepared['source_population_authority']);base=I.read(row['baseline_reference'])
        C.need(task['task_key']==row['task_key'] and task['meta']['molecule_id']==row['molecule_id'] and task['baseline_geometry_id']==row['baseline_geometry_id']
            and base['original_row']==task['existing_conformers'][0] and base['validation']['status']=='ORIGINAL_SOURCE_AND_BASELINE_VALIDATED_NO_NEW_UFF'
            and base['validation']['atomic_numbers']==task['source_atomic_numbers'],'FROZEN_TASK_AND_ORIGINAL_BASELINE_BYTES_IDENTITY')
        I.reserve_task(task);tasks.append(task);task_refs[task['task_key']]=row['task_reference']
    C.need(len(tasks)==len({task['task_key'] for task in tasks})==batch['task_count'],'EXACT_UNIQUE_BATCH_KEYS')
    consumed=[task['task_key'] for task in tasks if (I.LEDGER/(task['task_key']+'.json')).exists()]
    if consumed:budget.stop='EXISTING_OR_UNKNOWN_CONSUMED_KEYS_NO_AUTOMATIC_RETRY'
    claims=[];records=[];errors=[];index_next=0;active={};summaries=[]
    try:
        if not consumed:
            with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=core.worker_init,
                    initargs=(I.ref(I.HERE/'frozen_sources.json'),prepared['source_population_authority'],refs['prepared'],admission)) as pool:
                while active or index_next<len(tasks):
                    budget.observe(list(pool._processes.values()),reserve=sum(I.reserve_task(task) for task in active.values()))
                    while budget.stop is None and index_next<len(tasks) and len(active)<16:
                        task=tasks[index_next];key=task['task_key'];reserve=sum(I.reserve_task(item) for item in active.values())+I.reserve_task(task)
                        if budget.observe(list(pool._processes.values()),reserve=reserve) is not None:break
                        try:
                            claim=I.claim(task,I.LEDGER,out,proof);I.fsync_directory(I.LEDGER)
                            claims.append({'task_key':key,'once_claim_reference':claim});index_next+=1
                            intent=I.json_new(out/'dispatch_intents'/(key+'.json'),{'schema':'N1_SOURCE_FULL_DISPATCH_INTENT_V1',
                                'task_key':key,'task_reference':task_refs[key],'once_claim_reference':claim,'batch_reference':refs['batch'],
                                'job_id':str(proof['job_id']),'pid':os.getpid(),'observed_unix_seconds':time.time(),
                                'state':'CLAIM_CONSUMED_BEFORE_SUBMIT_WORKER_NOT_YET_OBSERVED','automatic_retry':False},budget.roots)
                            I.fsync_directory(out/'dispatch_intents');claims[-1]['dispatch_intent_reference']=intent
                            future=pool.submit(worker_attempt,(task,claim,intent));active[future]=task
                        except Exception as exc:
                            if (I.LEDGER/(key+'.json')).exists() and key not in {row['task_key'] for row in claims}:
                                claims.append({'task_key':key,'once_claim_reference':None,'once_claim_path':str(I.LEDGER/(key+'.json')),
                                    'state':'EXISTS_AFTER_CLAIM_ERROR_UNKNOWN_CONSUMED_NO_RETRY'})
                                index_next+=1
                            errors.append({'phase':'claim_intent_or_submit','task_key':key,'error':repr(exc),'traceback':traceback.format_exc()})
                            budget.stop='DISPATCH_FAILURE_NO_AUTORETRY';break
                    if not active:break
                    done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        task=active.pop(future);key=task['task_key']
                        try:
                            result=future.result();packet=result['packet'];worker_start=I.read(result['worker_start_reference'])
                            C.need(worker_start['runtime']==packet['runtime'] and worker_start['task_key']==key,'ACTUAL_WORKER_START_AND_PACKET_PID_IDENTITY')
                            record=I.packet_new(out,task,packet,I.LEDGER);record['worker_start_reference']=result['worker_start_reference'];records.append(record);summaries.append(packet['summary'])
                            I.json_new(out/'finished'/(key+'.json'),{'schema':'N1_SOURCE_FULL_ATTEMPT_DURABLE_V1','task_key':key,'record':record,
                                'once_claim_reference':next(row['once_claim_reference'] for row in claims if row['task_key']==key),'automatic_retry':False},budget.roots)
                        except Exception as exc:
                            errors.append({'phase':'started_worker_or_packet_readback','task_key':key,'error':repr(exc),'traceback':traceback.format_exc()})
                            budget.stop=budget.stop or 'UNKNOWN_CONSUMED_WORKER_OR_READBACK_FAILURE'
    except BaseException as exc:
        errors.append({'phase':'pool_or_parent','error':repr(exc),'traceback':traceback.format_exc()});budget.stop=budget.stop or 'UNKNOWN_CONSUMED_PARENT_FAILURE'
    claimed={row['task_key'] for row in claims};done_keys={row['task_key'] for row in records};pending=sum(row['Pprime_actual_records']!=2 for row in summaries)
    closed=len(records)==len(tasks) and not(errors or consumed) and not pending
    receipt={'schema':'N1_SOURCE_FULL_FINITE_BATCH_RECEIPT_V1','status':'ALL_BATCH_REAL_SECOND_PACKETS_CLOSED_ROOT_REVIEW_REQUIRED' if closed else 'INCOMPLETE_SOURCE_BATCH_CONSUMED_KEYS_NEVER_RETRIED',
        'job_id':str(proof['job_id']),'prepared_reference':refs['prepared'],'prepare_actual_terminal':terminal,'batch_reference':refs['batch'],
        'finite_batch_review_reference':refs['batch-review'],'science_cost_review_reference':refs['pilot-review'],'test10_and_boundaries_reference':tests_ref,
        'startup_proof_reference':I.ref(a.root_preflight),'source_population_authority':prepared['source_population_authority'],
        'expected':len(tasks),'claimed':len(claims),'completed_packets':len(records),'packets':records,'claims':claims,'errors':errors,
        'preexisting_consumed_keys':consumed,'unknown_consumed_task_keys':sorted(claimed-done_keys),
        'unstarted_task_keys':[task['task_key'] for task in tasks[index_next:] if task['task_key'] not in set(consumed)|claimed],
        'statistics':{'real_second_molecules':sum(row['Pprime_actual_records']==2 for row in summaries),'pending_geometry_packets':pending,
            'actual_optimizer_calls_attempted':sum(row['optimizer_calls_attempted'] for row in summaries),'actual_optimizer_calls_finished':sum(row['optimizer_calls_finished'] for row in summaries),
            'below_threshold_fallback':sum(bool(row['below_dedup_threshold']) for row in summaries),'status_counts':dict(collections.Counter(row['status'] for row in summaries))},
        'budget':budget.report(),'elapsed_seconds':time.monotonic()-started,'configured_workers':16,'common':False,'pilot_membership':False,'production_membership':False,
        'physical_int64_integration_frozen':False,'final_common_reference':None,'new_QM_calls':0,'automatic_retry':False,
        'source_population_release':False,'actual_terminal_accounting_required':True,'actual_parent_allocated_core_seconds':None}
    final=I.json_new(out/'receipt.json',receipt,budget.roots);print({'receipt':final,'status':receipt['status']});return 0 if closed else 3
if __name__=='__main__':raise SystemExit(main())
