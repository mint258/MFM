"""One real16CPU day: current-ready preparation and original persistent workers."""
import argparse,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,pathlib,sys,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.pilot2000_execution_day_v1 import source_boundary
from . import contract as C,prepare as P
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as I,worker
Q=C.Q

def fixtures(out):
    from workflows.data_v1_final.pprime.formal_packed_day_v1 import test_v1
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);C.need(suite.countTestCases()==3,'EXACT3_BEFORE_DATA_OR_NATIVE')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=Q.write_new(out/'source3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
      'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'before_DATA_or_native':True,'worker_inverse':worker.inverse()})
    C.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED_NO_SCIENCE');return ref

def execute(plan,proof,out,store,budget,roles,event,b):
    import duckdb
    prepared=P.build(plan,proof,out,b,budget,store)
    if prepared['records']==0:
        return store.json(out/'receipt.json',{'schema':'PPRIME_FORMAL_PACKED_DAY_RECEIPT_V1','status':'NO_NEW_AVAILABLE_PHYSICAL_RECORDS_NOT_FINAL_COMMON',
          'job_id':str(proof['job_id']),'prepared_header_reference':prepared['header'],'failures':[],'new_native_invokes':0,
          'N1_unavailable_pending_MIDs':prepared['pending_MIDs'],'scientific_PASS':False,'final_Common_or_training_admission':False})
    runtime=dict(plan,prepared2000_reference=prepared['header'],actual_ready_records=prepared['records'])
    runtime_ref=store.json(out/'actual_ready_execution_plan.json',runtime)
    session=I.source_session(runtime_ref,runtime,proof);review=C.meta(proof['request']['scope']['review'])
    protocol=C.precision(runtime,review)
    reproduction=store.json(out/'reproduction_manifest.json',{'schema':'PPRIME_FORMAL_DAY_REPRODUCTION_V1','actual_parent_job_id':str(proof['job_id']),
      'Root_plan_reference':Q.pin(plan['plan_path']),'actual_ready_plan_reference':runtime_ref,'prepared_header_reference':prepared['header'],
      'original_protocol_reference':protocol,'source_context_reference':plan['source_context_reference'],'pilot_reuse_reference':prepared['reuse'],
      'user_release_reference':plan['user_release_reference'],'versions_keywords_precision_seed_timeout_unchanged':True,'final_Common_or_training_admission':False})
    intent=store.json(out/'formal_day_intent.json',{'job_id':str(proof['job_id']),'reproduction_reference':reproduction,'scientific_once_is_original_per_physical_record':True})
    (out/'workers').mkdir();(out/'records').mkdir();(out/'batches').mkdir()
    deadline=time.time()+max(0,C.WALL-budget.elapsed-(time.monotonic()-budget.start)-180)
    index_guard=I.I.held(prepared['index'],[out],[prepared['index']]);index_guard.__enter__()
    try:db=duckdb.connect(str(prepared['index']['path']),read_only=True)
    except BaseException:
        index_guard.__exit__(*sys.exc_info());raise
    cursor=db.cursor();cursor.execute('SELECT pair,hashes FROM pairs ORDER BY mid,rank')
    pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker.initialize,
      initargs=(session,event,str(out),b['context'],protocol,prepared['audit'],reproduction['sha256'],deadline))
    active={};buffer=[];batch=[];all_batches=[];observed=0;completed=0;successful=0;dispatched=0;consumed=[];failures=[];stopped=None;exhausted=False
    audit=json.loads(I.body(prepared['source_audit'],[prepared['source_audit']],budget));audit={r['record_id']:r for r in audit}
    progress=out/'closed_record_index.DATA.jsonl'
    def append(value):
        raw=C.O.canonical(value)+b'\n'
        with progress.open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    def flush_batch():
        nonlocal batch
        if not batch:return
        number=len(all_batches);folder=out/'batches'/('batch_%06d'%number)
        records=[I.value(t['record_reference'],[t['record_reference']],budget) for _,t in batch]
        engine,_,_,pilot=T.engine(b['context'],C.meta);engine.CONFIG=C.meta(protocol);objects=source_boundary.objects()
        families,qc=objects['export'](records,folder,engine,reproduction['sha256'],dict(pilot,max_output_bytes=C.CAP,external_output_root=str(C.BASE)))
        workers=[{'raw_container':t['raw_container']} for _,t in batch if t['raw_container']]
        raw=objects['prove_raw'](workers,[audit[r['record_id']] for r in records],records,engine)
        C.need(not raw['missing'],'ORIGINAL_STABLE_AUDIT_AND_FAILED_RAW_READBACK')
        roles.add_export(sum(f['bytes'] for f in families))
        report=store.json(out/'batches'/('batch_%06d_closed.json'%number),{'schema':'PPRIME_FORMAL_DAY_INTERNAL_BATCH_CLOSED_V1',
          'parent_job_id':str(proof['job_id']),'records':len(records),'terminal_references':[r for r,_ in batch],
          'family_parquets':families,'raw_proof':raw,'child_Slurm_job_created':False,'not_independent_parent_C0':True})
        all_batches.append(report);batch=[]
    processes=[]
    try:
        while active or not exhausted:
            try:budget.check()
            except BaseException as exc:stopped=stopped or repr(exc);event.set()
            while not exhausted and not event.is_set() and roles.can_start() and len(batch)+len(active)<128:
                if deadline-time.time()<12*900+120:stopped='WHOLE12_900_DRAIN_ADMISSION_CLOSED';event.set();break
                if not buffer:buffer=cursor.fetchmany(128)
                if not buffer:exhausted=True;break
                blob,h=buffer.pop(0);pair=json.loads(bytes(blob));hashes=json.loads(bytes(h));key=C.record_once_key(pair,plan['original_protocol_reference'])
                ledger=C.ledger(plan)/'physical_records_v1'/(key+'.json')
                if ledger.exists():
                    claim=C.meta(Q.pin(ledger));C.need(claim['record_once_key']==key and claim['pair_sha256']==hashes['original_pair_sha256'],'EXISTING_PHYSICAL_ONCE_IDENTITY_NO_ESCAPE')
                    consumed.append({'record_id':pair['record_id'],'once_reference':Q.pin(ledger),'state':'CONSUMED_PRIOR_OUTCOME_NOT_RETRIED_OR_UPGRADED'});continue
                roles.start(key);slot=dispatched%16
                claim=I.claim_create(ledger,{'record_id':pair['record_id'],'record_once_key':key,'pair_sha256':hashes['original_pair_sha256'],
                  'prepared2000_reference':prepared['header'],'original_protocol_reference':plan['original_protocol_reference'],
                  'selected_protocol_reference':protocol,'job_id':str(proof['job_id']),'uid':1278,'boot_id':proof['boot_id'],
                  'dispatch_slot':slot,'global_pilot_once':intent,'native_return_claimed':False,'output':str(out/'records'/key)},store)
                future=pool.submit(worker.one,pair,hashes,claim,str(out/'records'/key),reproduction['sha256']);active[future]=(key,pair);dispatched+=1
            if active:
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    key,pair=active.pop(future)
                    try:
                        ref=future.result();terminal=I.value(ref,[ref],budget)
                        C.need(terminal['record_id']==pair['record_id'],'ACTUAL_RECORD_TERMINAL_BINDING')
                        roles.settle(key,I.quiescent(out/'records'/key),terminal['technical_record_complete'])
                        append({'terminal_reference':ref,'record_id':pair['record_id'],'physical_once_key':key})
                        observed+=terminal['native_return_count']
                        if not terminal['technical_record_complete']:
                            failures.append({'terminal_reference':ref,'status':'TECHNICAL_OR_UNOBSERVED_NO_RETRY'});event.set();continue
                        record=I.value(terminal['record_reference'],[terminal['record_reference']],budget)
                        successful+=int(len(record['tasks'])==12 and all(d['scope_status']=='SUCCESS' for d in record['tasks']));completed+=1;batch.append((ref,terminal))
                    except BaseException as exc:
                        event.set();failures.append({'record_id':pair['record_id'],'error':repr(exc),'status':'UNKNOWN_CONSUMED_NO_RETRY'})
                        if key in roles.active:roles.settle(key,0,False)
            if batch and (len(batch)>=128 or (not active and (exhausted or event.is_set() or not roles.can_start()))):flush_batch()
            if not active and (event.is_set() or not roles.can_start()):
                if not roles.can_start():stopped=stopped or 'PREPAID_OUTPUT_ROLES_NO_NEW_DISPATCH'
                break
        processes=list(pool._processes.values())
    finally:
        pool.shutdown(wait=True,cancel_futures=False);cursor.close();db.close();index_guard.__exit__(None,None,None)
    flush_batch()
    closure=[{'pid':p.pid,'exitcode':p.exitcode,'alive':p.is_alive()} for p in processes]
    workers=[]
    for p in processes:
        path=out/'workers'/('worker_%d_closed.json'%p.pid)
        if path.exists():
            ref=C.M.I.data_pin(path,[out]);value=I.value(ref,[ref],budget);workers.append(dict(value,reference=ref))
    joined=bool(processes) and 1<=len(workers)==len(processes)<=16 and all(not r['alive'] and r['exitcode']==0 for r in closure) and all(not w.get('close_error') for w in workers)
    C.need(joined,'ALL_ACTUAL_ORIGINAL_PERSISTENT_WORKERS_JOINED_NO_FAKE_UNUSED_TAIL_PIDS')
    return store.json(out/'receipt.json',{'schema':'PPRIME_FORMAL_PACKED_DAY_RECEIPT_V1',
      'status':'ACTUAL_FORMAL_DAY_TECHNICALLY_CLOSED_PENDING_PARENT_ACCOUNTING' if not failures else 'FORMAL_DAY_UNKNOWN_HOLD_PRESERVED',
      'job_id':str(proof['job_id']),'uid':1278,'node':plan['node'],'cpus':16,'plan_reference':Q.pin(plan['plan_path']),
      'startup_proof_reference':Q.pin(plan['proof_path']),'prepared_header_reference':prepared['header'],'pilot_reuse_reference':prepared['reuse'],
      'requested_ready_records':prepared['records'],'dispatched_records':dispatched,'completed_records':completed,'all12_success_records':successful,
      'success_fraction':successful/completed if completed else None,'success_floor_9945_observed':C.fraction_ok(successful,completed) if completed else None,
      'observed_native_returns':observed,'unprocessed_ready_records':prepared['records']-dispatched-len(consumed),
      'N1_unavailable_pending_MIDs':prepared['pending_MIDs'],'consumed_prior_records_reference':store.json(out/'consumed_prior_records.DATA.json',consumed),
      'internal_batch_references':all_batches,'closed_record_index_reference':C.M.I.data_pin(progress,[out]) if progress.exists() else None,
      'process_closure':closure,'worker_closures':workers,'maximum_worker_slots':16,'actual_initialized_worker_count':len(workers),
      'failures':failures,'natural_stop_reason':stopped,'resource_report':budget.report(),
      'all2000_original_pilot_records_reused':True,'original_pilot_failures_not_retried':11,'default_WP5_precision':True,
      'new_QA_calls':0,'scientific_PASS':False,'final_Common_or_training_admission':False,'global_outlier_and_P_vs_Pprime_review_pending':True,
      'legacy_original_exporter_wire_dataset_tag':'v1_pprime_pilot','generation_population_scope_is_this_actual_parent_not_the_legacy_wire_tag':True,
      'original1pct_mask_gate_unchanged':True,'actual_allocated_record_cost_pending_parent_accounting':True,
      'original_WP5_per_record_allocated_gate_seconds':11.7,'parent_allocated_cost_gate_not_predeclared_PASS':True,'forced_signals_sent':False})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.meta(Q.pin(a.plan));C.need(plan['schema']=='PPRIME_FORMAL_PACKED_DAY_PLAN_V1' and plan['scope_parameters']==C.parameters(plan['node']),'EXACT_FORMAL_DAY_PLAN')
    b=C.bootstrap(plan);C.need(plan['data_references']==b['data'],'EXACT_INITIAL_DECLARED_SCI_DATA')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof]
    proof=require_startup(a.startup_proof,expected_kind='qm',expected_scope_key=C.KEY,expected_scope_parameters=C.parameters(plan['node']),expected_execution_argv=argv,
      expected_source=C.HERE/'run.py',required_references=[Q.pin(a.plan),*plan['source_references']])
    req=proof['request'];C.need(req['node']==plan['node'] and req['cpus']==16 and req['wall_seconds']==C.WALL and req['pilot'] is False
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['estimated_peak_output_bytes']==C.CAP and req['data_references']==b['data'],'EXACT_CURRENT_NODE_FINITE16_DAY64G_NO_MEM')
    C.precision(plan,C.meta(req['scope']['review']))
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'PRIMARY_FULL_ARGV')
    for r in C.sources(plan):C.need(r in req['source_references'],'ALL_EXACT_SCIENCE_SOFTWARE_IO_SOURCE_PINS')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';out=C.M.fresh(plan['output_directory'],'artifacts');C.need(C.BASE in out.parents,'FRESH_FORMAL_OUTPUT');out.mkdir(parents=True,mode=0o700)
    source_boundary.verify_sources();fixture=fixtures(out);store=I.Store(out,4<<30);roles=I.Roles();event=mp.get_context('spawn').Event();budget=I.Budget(plan,proof,out,roles,store)
    plan=dict(plan,plan_path=a.plan,proof_path=a.startup_proof)
    try:budget.check(force=True);result=execute(plan,proof,out,store,budget,roles,event,b);report=C.meta(result);return 0 if not report['failures'] else 3
    except BaseException as exc:
        event.set();store.json(out/'failure.DATA.json',{'error':repr(exc),'traceback':traceback.format_exc(),'preserve_all_partial_and_once':True,'automatic_native_retry':False});raise
    finally:budget.check(dispatch=False,force=True)
if __name__=='__main__':raise SystemExit(main())
