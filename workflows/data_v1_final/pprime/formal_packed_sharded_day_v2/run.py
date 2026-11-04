"""Shared zero-QM pairs, assigned original workers, or readonly publication."""
import argparse,concurrent.futures as cf,io,json,multiprocessing as mp,os,pathlib,sys,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.pilot2000_execution_day_v1 import source_boundary
from . import contract as C,io as I,prepare as P,worker,publication as U
Q=C.Q

def fixtures(out):
    from . import test_v1
    test_v1.WORKSPACE=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries)
    C.need(suite.countTestCases()==3,'EXACT3_BEFORE_DATA_NATIVE');stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=Q.write_new(out/'source3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
      'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
      'before_DATA_Native':True,'original_worker_inverse':worker.inverse()})
    C.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED');return ref

def shared_prepare(plan,proof,out,local,b,store,budget):
    pool=U.Pool(plan['shared_pool_root_review_reference'],'PREP');closed=[];unpublished=[];stopped=None
    local_store=I.Store(local,30<<30)
    try:
        for number,(href,h) in enumerate(b['headers']):
            try:budget.check()
            except BaseException as exc:stopped=repr(exc);break
            if budget.roles.bound()+(4<<30)>budget.cap:stopped='LOCAL_OR_PREP_POOL_PARTIAL_KEEP_REMAINING_PENDING';break
            folder=local/('shard_%05d'%number);folder.mkdir()
            actual=dict(plan,output_directory=str(folder),_active_shard_header_reference=href)
            prepared=P.build(actual,proof,folder,b,budget,local_store)
            # Build is zero Native; one original initializer per shard only for
            # real source read/adapt/render/input hashes under original NoInvoke.
            extra={'prepared':prepared,'generation_shard_header_reference':href,'original_protocol_reference':plan['original_protocol_reference'],
              'shared_prepare_plan_reference':Q.pin(plan['plan_path']),'shared_prepare_proof_reference':Q.pin(plan['proof_path'])}
            ready=U.ready(local,[folder],'PREP',proof,'prep_'+str(number),local_store,extra)
            result=U.publish(ready,budget,store,out,pool)
            if not result['published']:unpublished.append(result);stopped='PREP_CLOSED_NODE_INPUTS_NOT_SHARED_KEEP_PENDING';break
            mapping=result['entries'];index=U.relocated(prepared['index'],mapping);sa=U.relocated(prepared['source_audit'],mapping) if prepared['records'] else None
            audit=None;selected=None
            if prepared['records']:
                old_audit=json.loads(I.body(prepared['audit'],[prepared['audit']],budget))
                raw_selected=old_audit['selected_records'];selected=U.relocated({k:raw_selected[k] for k in ('path','bytes','sha256')},mapping)
                old_audit['selected_records']=dict(selected,rows=raw_selected['rows'])
                audit=store.json(out/('audit_membership_%05d.json'%number),old_audit)
            reuse=U.relocated(prepared['reuse'],mapping) if any(x['origin_reference']==prepared['reuse'] for x in mapping) else closed[0]['pilot_reuse_reference']
            header=store.json(out/('prepared_shard_%05d_header.json'%number),{'schema':'PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2',
              'records':prepared['records'],'MIDs':prepared['MIDs'],'index_reference':index,'audit_membership_reference':audit,
              'audit_selected_reference':selected,'source_audit_reference':sa,'pilot_reuse_reference':reuse,
              'generation_shard_header_reference':href,'generation_partition_QA_reference':plan['generation_partition_QA_reference'],
              'shared_prepare_plan_reference':Q.pin(plan['plan_path']),'shared_prepare_proof_reference':Q.pin(plan['proof_path']),
              'publication_manifest_reference':result['publication_manifest_reference'],'source_context_reference':plan['source_context_reference'],
              'original_protocol_reference':plan['original_protocol_reference'],'native_invokes':0,'production_once_written':False,
              'native_physical_IDs_and_original_first2_input_hashes_verified':True,'operational_consumed_records_not_retried':json.loads(I.body(prepared['header'],[prepared['header']],budget))['additional_consumed_physical_records_not_retried'],
              'final_Common_or_training_admission':False})
            closed.append({'prepared_shard_header_reference':header,'pilot_reuse_reference':reuse,'records':prepared['records']})
    finally:P.close_inputs()
    return store.json(out/'receipt.json',{'schema':'PPRIME_SHARED_PAIRS_PREPARATION_RECEIPT_V2','status':'CLOSED_PUBLISHED_SUBSET_PENDING_PARENT_C0_ROOT_ACCEPTANCE',
      'job_id':str(proof['job_id']),'prepared_shards':closed,'unpublished':unpublished,'natural_stop':stopped,
      'requested_header_count':len(b['headers']),'remaining_headers_pending':len(b['headers'])-len(closed),
      'native_invokes':0,'original_pilot_reinvoked':False,'input_hash_worker_closures':P._hash_closures,
      'local_root_preserved':str(local),'resource_report':budget.report()})

def execution(plan,proof,out,local,b,store,budget,event):
    import duckdb
    h=b['prepared'];C.need(h['records']>0,'NO_NATIVE_PARENT_FOR_EMPTY_PREPARED_SHARD')
    budget.scope_forecast_records=h['records'];runtime=dict(plan,prepared2000_reference=plan['prepared_shard_header_reference'])
    runtime_ref=store.json(out/'actual_execution_plan.json',runtime);session=I.source_session(runtime_ref,runtime,proof)
    protocol=C.precision(runtime,C.meta(proof['request']['scope']['review']))
    reproduction=store.json(out/'reproduction_manifest.json',{'schema':'PPRIME_ASSIGNED_PAIR_REPRODUCTION_V2','plan_reference':Q.pin(plan['plan_path']),
      'startup_proof_reference':Q.pin(plan['proof_path']),'prepared_shard_header_reference':plan['prepared_shard_header_reference'],
      'protocol_reference':protocol,'source_context_reference':plan['source_context_reference'],'shared_prep_not_repeated':True,'original_pilot_not_reinvoked':True})
    intent=store.json(out/'generation_intent.json',{'job_id':str(proof['job_id']),'reproduction_reference':reproduction,'physical_once_namespace_unchanged':True})
    for name in ('workers','records','batches'):(local/name).mkdir()
    local_store=I.Store(local,60<<30);pool_publication=U.Pool(plan['shared_pool_root_review_reference'],'EXEC')
    audit=json.loads(I.body(h['source_audit_reference'],plan['data_references'],budget));audit={r['record_id']:r for r in audit}
    guard=I.I.held(h['index_reference'],[Q.ROOT/'artifacts'],plan['data_references']);guard.__enter__()
    db=None;pool=None;processes=[];active={};batch=[];publications=[];pending=[];errors=[];buffer=[];consumed=[]
    completed=successful=dispatched=returns=0;exhausted=False;stop=None
    deadline=time.time()+max(0,C.WALL-budget.elapsed-(time.monotonic()-budget.start)-180)
    def append(row):
        raw=C.O.canonical(row)+b'\n'
        with (out/'closed_records.DATA.jsonl').open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    def flush():
        nonlocal batch,stop
        if not batch:return
        number=len(publications)+len(pending);folder=local/'batches'/('batch_%06d'%number);records=[];valid=[];paths=[]
        for ref,t in batch:
            paths.append(pathlib.Path(ref['path']).parent)
            if t['technical_record_complete']:records.append(I.value(t['record_reference'],[t['record_reference']],budget));valid.append(t)
        family=[];proof_raw=None
        if records:
            engine,_,_,pilot=T.engine(b['context'],C.meta);engine.CONFIG=C.meta(protocol);objects=source_boundary.objects()
            family,_=objects['export'](records,folder,engine,reproduction['sha256'],dict(pilot,max_output_bytes=C.LOCAL_CAP,external_output_root=str(local)))
            proof_raw=objects['prove_raw']([{'raw_container':t['raw_container']} for t in valid if t['raw_container']],
              [audit[r['record_id']] for r in records],records,engine)
            C.need(not proof_raw['missing'],'ORIGINAL_REQUIRED_RAW_READBACK_BEFORE_SHARED_PUBLICATION')
            local_store.json(folder/'original_raw_readback.json',proof_raw);budget.roles.add_export(sum(f['bytes'] for f in family));paths.append(folder)
        ready=U.ready(local,paths,'EXEC',proof,'exec_%06d'%number,local_store,{
          'technical_complete_records':len(records),'UNKNOWN_closed_records':len(batch)-len(records),
          'terminal_references':[r for r,_ in batch],'family_references':family,'original_F64_export_readback':bool(records),
          'required_raw_readback_complete':proof_raw is not None and not proof_raw['missing'],
          'reproduction_reference':reproduction,'prepared_shard_header_reference':plan['prepared_shard_header_reference']})
        result=U.publish(ready,budget,store,out,pool_publication)
        if result['published']:publications.append(result['publication_manifest_reference'])
        else:pending.append(result);stop='CLOSED_NODE_RAW_UNPUBLISHED_STOP_NEW';event.set()
        batch=[]
    try:
        db=duckdb.connect(h['index_reference']['path'],read_only=True);cursor=db.cursor();cursor.execute('SELECT pair,hashes FROM pairs ORDER BY mid,rank')
        count=db.execute('SELECT count(*) FROM pairs').fetchone()[0];C.need(count==h['records'],'EXACT_CLOSED_PREPARED_PAIR_CENSUS')
        pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker.initialize,
          initargs=(session,event,str(local),b['context'],protocol,h['audit_membership_reference'],reproduction['sha256'],deadline))
        while active or not exhausted:
            try:budget.check()
            except BaseException as exc:stop=stop or repr(exc);event.set()
            while not exhausted and not event.is_set() and budget.roles.can_start() and len(active)+len(batch)<128:
                if deadline-time.time()<12*900+120:stop='WHOLE12_ORIGINAL900_DRAIN';event.set();break
                if not buffer:buffer=cursor.fetchmany(128)
                if not buffer:exhausted=True;break
                blob,hashed=buffer.pop(0);pair=json.loads(bytes(blob));hashes=json.loads(bytes(hashed))
                key=C.record_once_key(pair,plan['original_protocol_reference']);ledger=C.ledger(plan)/'physical_records_v1'/(key+'.json')
                if ledger.exists():
                    prior=C.meta(Q.pin(ledger));C.need(prior['record_once_key']==key and prior['pair_sha256']==hashes['original_pair_sha256'],'EXACT_PRIOR_PHYSICAL_ONCE_NO_RETRY')
                    consumed.append({'record_id':pair['record_id'],'once_reference':Q.pin(ledger)});continue
                budget.roles.start(key);target=local/'records'/key
                claim=I.claim_create(ledger,{'record_id':pair['record_id'],'record_once_key':key,'pair_sha256':hashes['original_pair_sha256'],
                  'prepared2000_reference':plan['prepared_shard_header_reference'],'original_protocol_reference':plan['original_protocol_reference'],
                  'selected_protocol_reference':protocol,'job_id':str(proof['job_id']),'uid':1278,'boot_id':proof['boot_id'],
                  'dispatch_slot':dispatched%16,'global_pilot_once':intent,'native_return_claimed':False,'output':str(target)},store)
                future=pool.submit(worker.one,pair,hashes,claim,str(target),reproduction['sha256']);active[future]=(key,pair);dispatched+=1
            if active:
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    key,pair=active.pop(future)
                    try:
                        ref=future.result();t=I.value(ref,[ref],budget);C.need(t['record_id']==pair['record_id'],'CLOSED_RECORD_IDENTITY')
                        budget.roles.settle(key,I.quiescent(local/'records'/key),t['technical_record_complete']);returns+=t['native_return_count'];batch.append((ref,t))
                        append({'origin_terminal_reference':ref,'record_id':pair['record_id'],'physical_once_key':key,'publication_pending':True})
                        if t['technical_record_complete']:
                            r=I.value(t['record_reference'],[t['record_reference']],budget);completed+=1;successful+=int(all(d['scope_status']=='SUCCESS' for d in r['tasks']))
                        else:errors.append({'terminal_reference':ref,'status':'ORIGINAL_TECHNICAL_UNKNOWN_NO_RETRY'});event.set()
                    except BaseException as exc:
                        errors.append({'record_id':pair['record_id'],'error':repr(exc),'status':'CONSUMED_UNKNOWN_NODE_OUTPUT_PRESERVED'});event.set()
                        if key in budget.roles.active:budget.roles.settle(key,0,False)
            if batch and (len(batch)>=128 or not active and (exhausted or event.is_set() or not budget.roles.can_start())):flush()
            if not active and (event.is_set() or not budget.roles.can_start()):break
        processes=list(pool._processes.values())
    finally:
        if pool is not None:pool.shutdown(wait=True,cancel_futures=False)
        if db is not None:db.close()
        guard.__exit__(None,None,None)
    flush();closures=[]
    for process in processes:
        path=local/'workers'/('worker_%d_closed.json'%process.pid)
        if path.exists():
            ref=I.pin(path,[local]);v=I.value(ref,[ref],budget);v['origin_reference']=ref;closures.append(v)
    C.need(len(closures)==len(processes) and all(not p.is_alive() and p.exitcode==0 for p in processes)
      and all(not v.get('close_error') for v in closures),'ALL_ACTUAL_PERSISTENT_WORKERS_JOINED')
    return store.json(out/'receipt.json',{'schema':'PPRIME_ASSIGNED_PAIRS_EXECUTION_RECEIPT_V2','status':'TECHNICAL_SUBSET_CLOSED_PENDING_PARENT_ACCOUNTING' if not errors and not pending else 'PRESERVED_UNKNOWN_OR_UNPUBLISHED_HOLD_NO_RETRY',
      'job_id':str(proof['job_id']),'prepared_shard_header_reference':plan['prepared_shard_header_reference'],'assigned_records':h['records'],
      'dispatched_records':dispatched,'completed_records':completed,'all12_success_records':successful,'observed_native_returns':returns,
      'unprocessed_records_pending':h['records']-dispatched-len(consumed),'publications':publications,'unpublished':pending,
      'consumed_prior_reference':store.json(out/'consumed_prior.DATA.json',consumed),'errors':errors,'natural_stop':stop,'worker_closures':closures,
      'local_root_preserved':str(local),'shared_prep_not_repeated':True,'original_2000_not_reinvoked':True,'new_QA_calls':0,
      'scientific_PASS':False,'final_Common_or_training_admission':False,'resource_report':budget.report(),'signals_sent':False})

def recover(plan,proof,out,b,store,budget):
    h=b['recovery'];review=C.meta(plan['recovery_root_review_reference']);actual=I.recover_terminal(review)
    C.need(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'],'SAME_ORIGINAL_BOOT_NODE_LOCAL_FILES_STILL_AVAILABLE')
    root=pathlib.Path(h['local_root']);C.need(root.parent==pathlib.Path('/tmp') and root.name.startswith('pprime_sharded_'+h['job_id']+'_'),'EXACT_PRODUCER_LOCAL_ROOT')
    budget.local_root=root;result=U.publish(h['ready_reference'],budget,store,out,U.Pool(plan['shared_pool_root_review_reference'],h['kind']))
    return store.json(out/'receipt.json',{'schema':'PPRIME_READONLY_PUBLICATION_RECOVERY_RECEIPT_V2','actual_original_terminal':actual,
      'result':result,'new_native_calls':0,'original_engine_initialized':False,'once_written':False,'not_scientific_or_parent_status_upgrade':True})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.meta(Q.pin(a.plan));C.need(plan['schema']=='PPRIME_FORMAL_SHARDED_DAY_PLAN_V2' and plan['scope_parameters']==C.parameters(plan),'EXACT_SHARDED_PLAN')
    b=C.bootstrap(plan);C.need(plan['data_references']==b['data'],'ALL_PRODUCER_DATA_LOCATORS_EXACT')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof];kind='qm' if plan['mode']=='EXECUTE' else 'analysis'
    proof=require_startup(a.startup_proof,expected_kind=kind,expected_scope_key=C.MODES[plan['mode']],expected_scope_parameters=C.parameters(plan),expected_execution_argv=argv,
      expected_source=C.HERE/'run.py',required_references=[Q.pin(a.plan),*plan['source_references']]);req=proof['request']
    C.need(req['node']==plan['node'] and req['cpus']==16 and req['wall_seconds']==C.WALL and req['pilot'] is False
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['estimated_peak_output_bytes']==plan['output_cap_bytes']
      and req['data_references']==b['data'],'REAL_CURRENT16_DAY_NO_MEM_SHARED_DECLARATIONS')
    C.precision(plan,C.meta(req['scope']['review']));C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py'
      and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'PRIMARY_FULL_ARGV')
    for ref in C.sources(plan):C.need(ref in req['source_references'],'ALL_ORIGINAL_PRIVATE_IO_SOURCES_PINNED')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';out=C.M.fresh(plan['output_directory'],'artifacts');C.need(C.BASE in out.parents,'FRESH_OWN_SHARED_METADATA_ROOT');out.mkdir(parents=True,mode=0o700)
    source_boundary.verify_sources();fixture=fixtures(out);store=I.Store(out,C.ADMIN_CAP);roles=I.Roles(plan['output_cap_bytes'],plan['mode'])
    budget=I.Budget(plan,proof,out,roles,store);event=mp.get_context('spawn').Event();plan=dict(plan,plan_path=a.plan,proof_path=a.startup_proof)
    try:
        budget.check(force=True)
        if plan['mode']=='RECOVER_PUBLISH':ref=recover(plan,proof,out,b,store,budget)
        else:
            local=I.local_stage(proof);budget.local_root=local
            store.json(out/'actual_local_stage.json',{'local_root':str(local),'node':plan['node'],'uid':1278,'job_id':str(proof['job_id']),'boot_id':proof['boot_id'],'no_native_status_implied':True})
            ref=shared_prepare(plan,proof,out,local,b,store,budget) if plan['mode']=='SHARED_PREPARE' else execution(plan,proof,out,local,b,store,budget,event)
        return 0
    except BaseException as exc:
        event.set();store.json(out/'failure.DATA.json',{'error':repr(exc),'traceback':traceback.format_exc(),'local_root_preserved':str(budget.local_root),
          'once_preserved':True,'automatic_native_retry':False});raise
    finally:
        budget.check(dispatch=False,force=True)
        if budget.node_book is not None:budget.node_book.observe(len(roles.unknown),False,closed=True)
if __name__=='__main__':raise SystemExit(main())
