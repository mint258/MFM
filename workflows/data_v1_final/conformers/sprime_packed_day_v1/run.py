"""One real24h parent, long-lived native worker pool, durable original once."""
import argparse,concurrent.futures as cf,io,json,multiprocessing as mp,os,pathlib,time,traceback,unittest
from workflows.data_v1_final.execution.sprime_wave2_controller_v3.capacity_gate import serialization_lock
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OLD
from . import contract as C,runtime as I,census as Z,prepare as P,worker as W,history as H,operational as O


def preflight(out):
    from .test_boundaries import Boundaries
    from workflows.data_v1_final.execution.cpu_packed_day_v2.test_v1 import Boundaries as Resources
    suites=[unittest.defaultTestLoader.loadTestsFromTestCase(k) for k in (Boundaries,Resources)]
    C.need([s.countTestCases() for s in suites]==[6,3],'EXACT_ONCE_PACKED6_PLUS_RESOURCE3_BEFORE_DATA')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(suites))
    from workflows.data_v1_final.conformers import selection
    proof={'kernel_full_file_reference':C.F.sources()['science'],'original_packet_reader_is_direct':OLD.read_packet.__module__==OLD.__name__,
        'original_selection_source_reference':C.F.sources()['selection'],'native_worker_load_function':
        {'module':OLD.load_science.__module__,'filename':OLD.load_science.__code__.co_filename,'line':OLD.load_science.__code__.co_firstlineno},
        'scientific_process_task_source_not_copied_or_modified':True,'packet_readback_source':OLD.read_packet.__code__.co_filename,
        'old_geometry_preservation_and_fallback_math_unchanged':True,'per_native_threads':1,'packed_resource_contract_version':2,'resource_hardware_full_source_inverse_in_resource3':True}
    for ref in C.F.sources().values():C.need(C.small_pin(ref['path'])==ref,'UNCHANGED_FROZEN_ORIGINAL_SOURCE_BEFORE_DATA')
    value={'schema':'PACKED_SINGLE_PARENT_ONCE_PREFLIGHT_V1','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),
        'transcript':stream.getvalue(),'source_proof':proof,'DATA_opened':False,'new_SCI_calls':0}
    ref=I.save(out/'preflight9.json',value)
    C.need(result.wasSuccessful() and result.testsRun==9 and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'PACKED_SINGLE_PREFLIGHT_PASS_BEFORE_DATA')
    return ref


def claim(task,prepared_reference,plan_reference,proof,out,budget,bid):
    meta=task['meta'];key=meta['task_key'];mid=meta['molecule_id'];C.need(key==C.F.task_key(mid,meta['cohort']),'ORIGINAL_SHARED_ONCE_KEY')
    budget.reserve(key,budget.plan['packet_compressed_limit_bytes']+(1<<20))
    row={'schema':'SPRIME_DISPATCH_INTENT_V3','task_key':key,'molecule_id':mid,'cohort':meta['cohort'],'task_sha256':C.F.sha_value(task),
        'seed':C.F.seed_for(mid,meta['cohort']=='retry_once'),'kernel_sha256':C.F.KERNEL_SHA,'recipe_config':budget.plan['recipe_config'],
        'prepared_reference':prepared_reference,'plan_reference':budget.plan['original_plan_reference'],'packed_plan_reference':plan_reference,
        'job_id':str(proof['job_id']),'uid':os.getuid(),'node':proof['node'],'parent_pid':os.getpid(),'parent_start_ticks':I.ticks(os.getpid()),
        'boot_id':proof['boot_id'],'observed_unix_seconds':time.time(),'worker_started':False,'science_result_observed':False,
        'resource_scope':C.KEY,'single_real_parent':True,'internal_batch_id':bid,'child_parent_or_child_C0':False}
    try:ref=I.exclusive(C.F.ledger_path(key),C.F.canonical(row)+b'\n')
    except BaseException:budget.release(key);raise
    budget.write(out/'dispatch'/(key+'.json'),C.F.canonical({'ledger_reference':ref,'record':row})+b'\n',key)
    return ref


def export_index(census,budget,out,proof,plan_ref):
    import pyarrow as pa,pyarrow.parquet as pq
    rows=[]
    for key,mid,meta,bid,candidate,state,evidence in census.db.execute('SELECT k,mid,meta,bid,candidate,state,evidence FROM metas ORDER BY mid'):
        m=json.loads(meta);rows.append({'molecule_id':mid,'task_key':key,'cohort':m['cohort'],'expected_conformers':m['expected_conformers'],
            'original_batch_id':bid,'within_root_remainder_descriptor_scope':bool(candidate),'resolution':state,'evidence_json':evidence,
            'original_effective_role':m.get('effective_role',m.get('split_role')),'packed_readback_parent_job_id':str(proof['job_id']),
            'packed_plan_reference_json':C.F.canonical(plan_ref).decode()})
    sink=pa.BufferOutputStream();pq.write_table(pa.Table.from_pylist(rows),sink,compression='zstd')
    ref=budget.write(out/'original_deficit_resolution_index.parquet',sink.getvalue().to_pybytes())
    # CPU readback of the actual whole exported index; no login numerical/data parsing.
    I.verify(ref);table=pq.read_table(ref['path']);C.need(table.num_rows==len(rows) and table.column('task_key').to_pylist()==[r['task_key'] for r in rows],'ACTUAL_PACKED_RESOLUTION_INDEX_REOPEN')
    error_rows=[{'phase':p,'task_key':k,'error_and_traceback':e} for p,k,e in census.db.execute('SELECT phase,k,error FROM errors ORDER BY n')]
    raw=b''.join(C.F.canonical(r)+b'\n' for r in error_rows)
    errors=budget.write(out/'complete_errors.jsonl',raw or b'\n')
    return ref,errors,dict(census.db.execute('SELECT state,count(*) FROM metas GROUP BY state'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.G.load(a.plan);proof=I.admit(a,plan);plan_ref=C.small_pin(a.plan);plan['_plan_path']=str(a.plan)
    out=pathlib.Path(plan['output_directory']);C.need(out.is_absolute() and C.ROOT/'artifacts/conformers' in out.parents and '..' not in out.parts
        and not out.exists() and not any(q.is_symlink() for q in (out,*out.parents)),'FRESH_PACKED_OUTPUT_NO_OLD_ARTIFACT_CHANGED')
    out.mkdir(parents=True,mode=0o700)
    for n in ('packets','dispatch','starts','errors','internal_prepared','internal_checkpoints'):(out/n).mkdir()
    budget=None;census=None;gate=None;active={};all_finished=False;started=time.monotonic();run_error=None
    try:
        with serialization_lock(C.ROOT/'control/sprime_wave2_controller_v1/wave2_single_instance.lock'):
            gate=preflight(out);C.need('packed_history_review_reference' in plan,'CONTINUATION_R2_REQUIRES_REAL_TERMINAL_HISTORY_AND_NEW_ROOT_INPUT_REVIEW')
            value,original,review,parents=C.input_metadata(plan)
            I.authorized(proof,parents);I.authorized(proof,C.data_locators(plan,value,original,review))
            budget=I.Budget(plan,proof,out);C.need(budget.observe(force=True) is None,'REAL_PACKED_RESOURCE_OBSERVATION_BEFORE_DATA')
            census=Z.Census(plan,value,original,review,proof,out,budget)
            census.load_metas();census.old_baselines();census.historical_imports();census.registered_origins()
            history,consumed=H.ingest(census);history_ref=budget.write(out/'terminal_packed_history_readback.json',C.F.canonical(history)+b'\n')
            observed=census.classify()
            H.anti_join([r[0] for r in census.db.execute("SELECT k FROM metas WHERE state='ELIGIBLE_UNCLAIMED_AFTER_ORDINARY_SOURCE_CENSUS'")],consumed)
            budget.write(out/'actual_ordinary_census.json',C.F.canonical(observed)+b'\n')
            prep=P.Prepare(plan,value,original,census,proof,out,budget)
            context={'proof':proof,'config_reference':plan['original_config_reference'],'plan_reference':plan_ref,'out':str(out),
                'cap':plan['output_cap_bytes'],'parent_pid':os.getpid(),'parent_start_ticks':I.ticks(os.getpid())}
            def collect(pool,wait_all=False):
                while active:
                    children=[proc.pid for proc in pool._processes.values() if proc.pid]
                    budget.observe(children)
                    done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        key,mid,bid=active.pop(future)
                        try:
                            result=future.result();ref=result['package_reference'];packet=OLD.read_packet(ref,value)
                            C.need(packet['summary']['molecule_id']==mid and result['actual_single_parent_job_id']==str(proof['job_id']),'PARENT_PACKET_SOURCE_READBACK')
                            evidence={'origin':'NEW_PACKED_NATIVE_RESULT','packed_parent_job_id':str(proof['job_id']),'package_reference':ref,
                                'scientific_status':result['scientific_status'],'science_result_observed':True,'internal_batch_id':bid,
                                'parent_terminal_accounting':'PENDING_REAL_ROOT_SACCT_NOT_A_CHILD_C0','original_float64_packet_reader_used':True}
                            census.db.execute("UPDATE metas SET state='NEW_DURABLE_RESULT',evidence=? WHERE k=?",(C.F.canonical(evidence).decode(),key))
                        except BaseException as exc:
                            census.error('PACKED_NATIVE_RESULT_UNKNOWN',key,exc);budget.stop=budget.stop or 'NATIVE_EXECUTOR_ERROR_STOP_NEW_TASKS'
                        finally:budget.release(key)
                        census.db.commit()
                    if done and not wait_all:return
            # One persistent pool for the entire parent, not one pool/job per500.
            with cf.ProcessPoolExecutor(max_workers=plan['cpus'],mp_context=mp.get_context('spawn'),initializer=W.initialize,initargs=(context,)) as pool:
                for bid in review['candidate_batch_ids']:
                    if budget.observe([p.pid for p in pool._processes.values() if p.pid]) is not None:break
                    header,tasks=prep.batch(bid)
                    if header is None:continue
                    for task in tasks:
                        while len(active)>=plan['cpus']:collect(pool)
                        if budget.observe() is not None:break
                        meta=task['meta'];key=meta['task_key'];mid=meta['molecule_id']
                        try:
                            dispatch=claim(task,header,plan_ref,proof,out,budget,bid)
                            # Claim persists before submit; submission uncertainty
                            # is consumedUNKNOWN and never retried.
                            future=pool.submit(W.one,task,dispatch,bid);active[future]=(key,mid,bid)
                            census.db.execute("UPDATE metas SET state='NEW_DISPATCH_CONSUMED_PENDING' WHERE k=?",(key,));census.db.commit()
                        except BaseException as exc:
                            census.error('PACKED_DISPATCH_CONSUMED_OR_UNKNOWN',key,exc);budget.stop=budget.stop or 'DISPATCH_ERROR_STOP_NEW_TASKS';break
                    budget.write(out/'internal_checkpoints'/(bid+'.json'),C.F.canonical({'schema':'PACKED_INTERNAL_CHECKPOINT_V1','batch_id':bid,
                        'actual_single_parent_job_id':str(proof['job_id']),'prepared_reference':header,'child_C0_claimed':False,
                        'status':'DISPATCH_CHECKPOINT_NATIVE_TASKS_MAY_STILL_BE_IN_FLIGHT'})+b'\n')
                    if budget.stop is not None:break
                collect(pool,True) # resource stop always drains; no cancel/shutdown signal.
            all_finished=True;index,errors,states=export_index(census,budget,out,proof,plan_ref)
            summary={'schema':'SPRIME_PACKED_DAY_RECEIPT_V1','status':'PACKED_PARENT_NATIVE_TASKS_DRAINED_ROOT_TERMINAL_ACCOUNTING_REQUIRED',
                'actual_single_parent_job_id':str(proof['job_id']),'uid':1278,'node':proof['node'],'allocated_cpus':proof['request']['cpus'],
                'plan_reference':plan_ref,'startup_proof_reference':C.small_pin(a.startup_proof),'preflight_reference':gate,
                'original_plan_reference':plan['original_plan_reference'],'inputs_review_reference':plan['inputs_review_reference'],
                'resolution_index_reference':index,'complete_errors_reference':errors,'state_counts':states,'resource_report':budget.report(),
                'terminal_packed_history_readback_reference':history_ref,'continuation_revision':3,
                'all_started_native_tasks_drained':True,'scientific_status_is_not_resource_parent_C0':True,
                'new_parent_C0_or_Common_quality_release_claimed':False,'old_parent_C0_FAILED_TIMEOUT_UNKNOWN_preserved':True,
                'old_geometries_and_seed_recipe_graph_stereo_RMSD_unchanged':True,'child_Slurm_jobs_created':0,'new_QM_calls':0,
                'original500_are_only_internal_checkpoints':True,'provider_renewals':0,'signals_sent_by_resource_monitor':False,
                'elapsed_monotonic_seconds':time.monotonic()-started,'actual_parent_allocated_cost':'PENDING_REAL_ROOT_TERMINAL_SACCT'}
            full_receipt=budget.write(out/'receipt.json',C.F.canonical(summary)+b'\n')
            header=O.produced_header(summary,full_receipt,{'job_id':str(proof['job_id']),'plan_reference':plan_ref,'startup_proof_reference':C.small_pin(a.startup_proof)})
            budget.write(out/'receipt_header.json',C.F.canonical(header)+b'\n')
            return 0
    except BaseException as exc:
        run_error={'schema':'SPRIME_PACKED_DAY_FAILURE_V1','error':repr(exc),'traceback':traceback.format_exc(),'preflight_reference':gate,
            'actual_single_parent_job_id':str(proof['job_id']),'plan_reference':plan_ref,'started_native_drained':all_finished,
            'budget':None if budget is None else budget.report(),'shared_once_never_reset':True,'unknown_consumed_not_retried':True,
            'no_fake_child_C0':True,'actual_cost':'PENDING_REAL_ROOT_SACCT'}
        if budget is None:I.save(out/'failure.json',run_error)
        else:budget.write(out/'failure.json',C.F.canonical(run_error)+b'\n')
        raise
    finally:
        if census is not None:census.db.commit();census.db.close()


if __name__=='__main__':raise SystemExit(main())
