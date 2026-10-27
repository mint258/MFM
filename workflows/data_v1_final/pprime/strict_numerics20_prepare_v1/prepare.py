"""Fresh central CPU preparation: original readers,1200 renders,zero invocations."""
import argparse,concurrent.futures as cf,io,json,os,pathlib,socket,sys,tempfile,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.common_molecular_fp_main_v1.resources import Budget
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.io import Store
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from . import contract as C,inputs as I
from .proposal import proposal
Q=C.Q

def fixtures(out,store):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_NEW_PURE_METHODS')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    ref=store.json(out/'fixtures3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),
        'before_DATA_Budget_original_initialize_or_invoke':True,'new_QM_calls':0})
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_MUST_PASS_BEFORE_DATA');return ref

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);old,new,diff,source,prepared,pair_ref,sprime,data,parents=C.parents(plan)
    Q.need(plan['schema']=='PPRIME_NEW20_ALL12_ZERO_INVOKE_PREPARE_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS
        and plan['data_references']==data and plan['wall_seconds']==7200 and plan['output_cap_bytes']==C.PREP_CAP,'EXACT_ZERO_INVOKE_NEW20_PREPARE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];Q.need(req['node']=='compute-0-13' and req['pilot'] is False and req['wall_seconds']==7200
        and req['estimated_peak_output_bytes']==C.PREP_CAP and req['data_references']==data and not req.get('deferred_authority_references'),'ACTUAL_CPU13_FINITE_PROVIDER_NO_MEM_ANALYSIS')
    Q.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'prepare.py' and sys.argv==[str(C.HERE/'prepare.py'),*argv[4:]],'PRIMARY_FULL_ARGV_NO_WRAPPER')
    for path in C.sources():Q.need(Q.pin(path) in req['source_references'],'ALL_IMPORTED_SOURCE_BYTES_PINNED')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_AUTHORITY_NOT_NUMERICAL_QA_APPROVAL')
    out=pathlib.Path(plan['output_directory']);base=Q.ROOT/'artifacts/pprime_strict20_zero_invoke_prepare_v1'
    Q.need(out.is_absolute() and '..' not in out.parts and base in out.parents and not out.exists()
        and not any(v.is_symlink() for v in (out,*out.parents)),'FRESH_INDEPENDENT_PREPARE_OUTPUT')
    out.mkdir(parents=True,mode=0o700);store=Store(out,C.PREP_CAP);fixture=None;budget=None;engine=None;scratch=None;guard=None;init_calls=0;closed=None
    try:
        fixture=fixtures(out,store);budget=Budget(plan,proof,out);budget.check(True,True)
        rows,pair_verification=I.pairs(pair_ref,budget);chosen,selection=C.choose20(rows)
        selected_ref=store.json(out/'selected20_source_pairs.DATA.json',chosen)
        by_mid,source_frames=I.selected_conformers(sprime,chosen,rows,budget)
        science=I.load_science(plan);engine,legacy,_,pilot=T.engine(source,C.meta)
        # Original worker initialization is authorized preprocessing, not a QM call.
        # Candidate protocol is NEVER passed to initialize_worker in this entry.
        import pyarrow as pa,pyarrow.parquet as pq
        audit_rows=[{'record_id':pair['record_id'],'file_group':pair['source']['file_group'],'size_stratum':pair['source']['size_stratum']} for pair in chosen]
        buffer=pa.BufferOutputStream();pq.write_table(pa.Table.from_pylist(audit_rows),buffer,compression='zstd')
        audit_ref=store.write(out/'audit_selected20.parquet',buffer.getvalue().to_pybytes())
        audit_manifest=store.json(out/'audit_membership.json',{'schema':'WP5_STRATIFIED_RECORD_AUDIT_V1','status':'AUDIT_MEMBERSHIP_CLOSED',
            'selected_records':dict(audit_ref,rows=20),'fraction':1.0,'seed':C.SEED,'lineage':'independent NEW20 all-call QA; original production audit unchanged'})
        scratch=pathlib.Path(tempfile.mkdtemp(prefix='pprime20_readers_'+str(proof['job_id'])+'_',dir='/tmp'));guard=I.NoInvoke(old)
        with guard:
            init_calls+=1;engine.initialize_worker(pilot['source_plan']['path'],protocol=plan['original_protocol_reference']['path'],node_scratch_root=str(scratch),
                audit_membership=audit_manifest['path'],reproduction_package=legacy['reproduction_package']['path'])
            Q.need(pathlib.Path(engine.NATIVE.invoke.__code__.co_filename).absolute()==guard.path,'TRACE_BINDS_ORIGINAL_INVOKE_FILENAME_NO_REPLACEMENT')
            sources=[];orders=[];lmdb_frames=I.lmdb_frames(chosen,data)
            for pair in chosen:
                budget.check(True);native,provenance,ordering=I.source_native(pair,by_mid[pair['molecule_id']],engine,science)
                sources.append((pair,native));orders.append(ordering)
                store.json(out/'source_provenance'/('mid%02d.DATA.json'%(len(sources)-1)),provenance)
            I.check_lmdb_frames(lmdb_frames)
            order_ref=store.json(out/'original_Sprime_three_orders.DATA.json',orders)
            tasks=[];thread_ids=set()
            # 20 bounded independent render jobs, <=20 pending,16 threads. Readers
            # and initialization stay in parent; all writes stay in parent.
            import threading
            barrier=threading.Barrier(16)
            def render(index,item):
                if index<16:barrier.wait(timeout=60)
                values=I.render_one(item[0],item[1],old,new,engine);return threading.get_native_id(),values
            with cf.ThreadPoolExecutor(max_workers=16) as pool:
                active={pool.submit(render,i,item):i for i,item in enumerate(sources)}
                for future in cf.as_completed(active):
                    budget.check(True);tid,values=future.result();thread_ids.add(tid);mid_index=active[future]
                    for local,value in enumerate(values):
                        qa='qa20-%02d-%02d'%(mid_index,local);original=value.pop('original_inputs');candidate=value.pop('candidate_inputs')
                        value['case']['case_id']=qa
                        original_refs=[store.write(out/'original_targets'/qa/name,b) for name,b in sorted(original.items())]
                        targets=[store.write(out/'candidate_targets'/qa/name,b) for name,b in sorted(candidate.items())]
                        value.update(schema='PPRIME_NEW20_ALL12_RENDERED_TASK_V1',qa_id=qa,original_target_input_references=original_refs,
                            target_input_references=targets,original_protocol_reference=plan['original_protocol_reference'],candidate_protocol_reference=plan['candidate_protocol_reference'],
                            original_prepared_reference=plan['original_prepared_reference'],new_QM_calls=0,scientific_PASS=False,full_or2000_release='HOLD')
                        ref=store.json(out/'tasks'/(qa+'.DATA.json'),value)
                        tasks.append({'qa_id':qa,'molecule_id':value['molecule_id'],'condition':value['condition'],'arm':value['arm'],'task_reference':ref})
            Q.need(len(thread_ids)==16 and len(tasks)==1200 and len({t['qa_id'] for t in tasks})==1200
                and len({t['molecule_id'] for t in tasks})==20,'ACTUAL16_RENDER_THREADS_EXACT20_TIMES12_TIMES5_NO_SUBSTITUTION')
            closed=engine.close_worker();engine=None
        Q.need(guard.attempts==0,'NO_INVOKE_ATTEMPT_ALLOWED');budget.check(False,True)
        store.json(out/'prepared20.json',{'schema':'PPRIME_NEW20_ALL12_ZERO_INVOKE_PREPARED_V1','status':'ACTUAL_NEW20_1200_INPUTS_PREPARED_NOT_EXECUTION_AUTHORITY',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
            'fixtures_reference':fixture,'original_prepared_reference':plan['original_prepared_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],
            'original_protocol_reference':plan['original_protocol_reference'],'protocol_diff':diff,'selection':selection,'selected20_DATA_reference':selected_ref,
            'original_Sprime_QA_three_orders_reference':order_ref,'original_pair_verification':pair_verification,'old5_Sprime_inherited_authority_current_frames':source_frames,
            'selected_LMDB_inherited_authority_current_frames':lmdb_frames,
            'audit_membership_reference':audit_manifest,'tasks':sorted(tasks,key=lambda t:t['qa_id']),'actual_input_sets':len(tasks),'actual_render_native_thread_ids':sorted(thread_ids),
            'original_protocol_initialize_calls':init_calls,'candidate_protocol_initialize_calls':0,'native_invoke_attempts':guard.attempts,'new_QM_calls':0,'new_UFF_calls':0,
            'engine_close':closed,'budget':budget.receipt(),'owned_bytes_before_manifest':budget.used(),'execution_proposal':proposal(),
            'user_decision_reference':None,'new_explicit_user_authorization_required_for1200':True,'production_once_opened':False,'old15_once_opened':False,
            'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD','terminal_cost':'PENDING_ROOT_ACTUAL_ACCOUNTING'})
        return 0
    except BaseException as exc:
        store.json(out/'failure.json',{'schema':'PPRIME_NEW20_ZERO_INVOKE_PREPARE_FAILURE_V1','status':'INCOMPLETE_NO_READY_NO_RESAMPLING',
            'error':repr(exc),'traceback':traceback.format_exc(),'fixtures_reference':fixture,'original_protocol_initialize_calls':init_calls,
            'candidate_protocol_initialize_calls':0,'native_invoke_attempts':0 if guard is None else guard.attempts,'new_QM_calls':0,
            'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'})
        raise
    finally:
        if engine is not None:closed=engine.close_worker()
        if scratch is not None and scratch.exists() and not any(scratch.iterdir()):scratch.rmdir()

if __name__=='__main__':raise SystemExit(main())
