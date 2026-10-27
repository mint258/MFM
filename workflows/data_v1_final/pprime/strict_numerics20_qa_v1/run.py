"""Max1200 explicitly authorized native calls,unique once,stop-new/natural-drain."""
import argparse,concurrent.futures as cf,copy,io,multiprocessing as mp,os,pathlib,sys,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.common import read_staging,staging_bytes
from . import contract as C,io as W,resources as B,worker,analysis as A
Q=C.Q
def fixtures(out,store):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_NEW_EXECUTION_PURE_METHODS')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    ref=store.json(out/'fixtures3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),'before_DATA_native_initialize_invoke_or_monitor':True})
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_REQUIRED_BEFORE_DATA_OR_QM');return ref
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);C.require_user(plan)  # FIRST: no parent traversal,DATA or initialization without new20 permission.
    old,new,diff,prepared,source,audit,tasks,data,parents=C.inputs(plan)
    Q.need(plan['schema']=='PPRIME_NEW20_ALL12_USER_AUTHORIZED_QA_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS and plan['data_references']==data
        and plan['audit_membership_reference']==audit and plan['wall_seconds']==86400 and plan['output_cap_bytes']==C.CAP,'EXACT_NEW20_PROTOCOL_MATRIX_AND_ROLE_CAPS')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,expected_source=__file__,expected_kind='qm',
        required_references=[Q.pin(a.plan),plan['user_decision_reference'],*parents,plan['cost_decision_reference']])
    req=proof['request'];Q.need(req['node']=='compute-0-13' and req['pilot'] is False and req['wall_seconds']==86400
        and req['estimated_peak_output_bytes']==C.CAP and req['data_references']==data and not req.get('deferred_authority_references'),'REAL_CURRENT_PROVIDER_CPU13_16_NO_MEM24H31GIB')
    Q.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_PRIMARY_COMPLETE_ARGV_NOT_WRAPPER')
    for path in C.sources():Q.need(Q.pin(path) in req['source_references'],'ALL_FROZEN_AND_NEW_IMPORTED_SOURCE_PINS')
    review=C.meta(req['scope']['review']);Q.need(review['new20_only_user_decision_reference']==plan['user_decision_reference']
        and review['prepared20_reference']==plan['prepared20_reference'] and review['unsupported_semantics_remain_UNKNOWN'] is True
        and review['full_or2000_release']=='HOLD','ROOT_APPROVED_EXACT_PREPARED20_USER_SCOPE_NOT_PRODUCTION')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_DOES_NOT_AUTHORIZE_NEW_PARAMETERS')
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
    out=pathlib.Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and C.BASE in out.parents
        and C.LEDGER not in out.parents and out!=C.LEDGER and not out.exists() and not any(v.is_symlink() for v in (out,*out.parents)),'FRESH_OWN_QA_OUTPUT_NOT_OLD_ONCE')
    out.mkdir(parents=True,mode=0o700);store=W.Store(out,C.PARENT_CAP);fixture=None;budget=None;claims=[];terminals=[];errors=[];processes=[];index=0
    ordered=[tasks[k] for k in sorted(tasks)];pending={};cache={};own_checks={};pair_checks={};counts={'QM_call_attempted':0,'native_return_observed':0};ctx=mp.get_context('spawn');event=ctx.Event();roles=B.Roles()
    try:
        fixture=fixtures(out,store);budget=B.Budget(plan,proof,store,roles,event);Q.need(budget.check(True,True),'FRESH_REAL_RESOURCE_BEFORE_DATA')
        config=C.meta(source['audit_config']);engine,_,_,_=T.engine(source,C.meta)  # import only,never parent initialize/invoke
        C.LEDGER.mkdir(parents=True,mode=0o700,exist_ok=True);Q.need(not any(v.is_symlink() for v in (C.LEDGER,*C.LEDGER.parents)),'OWN_NEW_LEDGER_NO_SYMLINK')
        paths=[C.LEDGER/(C.once_key(plan,r['qa_id'])+'.json') for r in ordered]
        Q.need(not any(v.exists() or v.is_symlink() for v in paths),'ANY_PREVIOUS_CONSUMED_NEW20_ONCE_HOLD_NO_RETRY')
        session={'parent_pid':os.getpid(),'parent_ticks':W.ticks(os.getpid()),'job_id':str(proof['job_id']),'node':req['node'],'boot_id':proof['boot_id'],
            'plan_reference':Q.pin(a.plan),'source_references':C.unique([*req['source_references'],req['script_reference'],Q.pin(a.startup_proof)])}
        deadline=time.time()+86400-budget.initial-(time.monotonic()-budget.start)-60
        pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=worker.init,initargs=(event,))
        def collect(future,row):
            qa=row['qa_id'];valid=False;size=C.WORKER_CAP
            try:
                terminal_ref=future.result();terminal=C.meta(terminal_ref);Q.need(terminal['schema']=='PPRIME_NEW20_CALL_TERMINAL_V1' and terminal['qa_id']==qa,'EXACT_WORKER_TERMINAL')
                size,inventory=W.quiescent(out/qa);Q.need(size<=C.WORKER_CAP,'PRIVATE112M_PHYSICAL_CLOSURE');terminals.append(terminal_ref)
                for name in counts:counts[name]+=int(terminal[name] is True)
                if terminal['result_reference'] is not None:
                    record=read_staging(W.body(terminal['result_reference'],C.O.RESULT_CAP))
                    Q.need(record['qa_id']==qa and record['task_reference']==row['task_reference'] and record['prepared20_reference']==plan['prepared20_reference']
                        and record['candidate_protocol_reference']==plan['candidate_protocol_reference'],'ACTUAL_RESULT_CELL_PROTOCOL_ANCESTRY')
                    check,_=A.own(record,config);own_checks[qa]=check;valid=terminal['call_technical_readback_complete'] and terminal['closed25M_role_eligible'] and check['defined_QC_pass']
                    key=(record['molecule_id'],record['condition']);cache.setdefault(key,{})[record['arm']]=record
                    for comparison in A.completed_group(list(cache[key].values()),config):
                        ckey=(*key,*comparison['arms']);pair_checks[ckey]=comparison
                        if not comparison['defined_QC_pass']:valid=False;budget.halt('ORIGINAL_DEFINED_VECTOR_GATE_FAIL_OR_UNAVAILABLE')
                    # A condition cache never exceeds5*8MiB; all1200 bodies are
                    # never retained in memory. Persist group evidence then free.
                    if len(cache[key])==5:
                        store.write(out/'group_checks'/(qa[:7]+'_'+record['condition']+'.DATA.json'),staging_bytes({'own':[own_checks[r['qa_id']] for r in cache[key].values()],
                            'pairs':A.completed_group(list(cache[key].values()),config)})+b'\n');del cache[key]
                else:budget.halt('RESULT_BYTES_UNKNOWN_OR_OVERSIZED_NO_TRUNCATION')
            except BaseException as exc:errors.append({'qa_id':qa,'error':repr(exc),'once_consumed':True,'automatic_retry':False});budget.halt('WORKER_OR_READBACK_UNKNOWN')
            roles.settle(qa,size,valid)
            if not valid:budget.halt('TECHNICAL_OR_DEFINED_QC_UNKNOWN_FAIL_OR_CLOSED_ROLE_OVER25M')
        try:
            while pending or index<1200:
                budget.check()
                while index<1200 and len(pending)<16 and budget.check():
                    row=ordered[index];qa=row['qa_id'];roles.start(qa)
                    claim={'schema':'PPRIME_NEW20_QA_DISPATCH_INTENT_V1','qa_id':qa,'task_reference':row['task_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],
                        'prepared20_reference':plan['prepared20_reference'],'user_decision_reference':plan['user_decision_reference'],'job_id':session['job_id'],'uid':1278,
                        'boot_id':session['boot_id'],'startup_proof_reference':Q.pin(a.startup_proof),'state':'INTENT_NOT_NATIVE_RETURN','automatic_retry':False}
                    claim_ref=W.claim_create(paths[index],claim,store);claims.append(claim_ref);index+=1
                    pending[pool.submit(worker.one,row,claim_ref,source,session,str(out),deadline)]=row
                if not pending:break
                done,_=cf.wait(pending,timeout=.25,return_when=cf.FIRST_COMPLETED)
                for future in done:collect(future,pending.pop(future))
        except BaseException as exc:
            budget.halt('PARENT_DISPATCH_UNKNOWN');errors.append({'phase':'dispatch','error':repr(exc),'no_automatic_retry':True})
            for future,row in list(pending.items()):collect(future,row)
            pending.clear()
        finally:
            processes=list((pool._processes or {}).values());pool.shutdown(wait=True,cancel_futures=False)
        unresolved_roles=sorted(roles.active)
        for qa in unresolved_roles:roles.settle(qa,C.WORKER_CAP,False)
        # Write all partial defined evidence. Shared interpretation UNKNOWN never
        # pretends to be a coordinate/basis/tensor PASS or a stop of all16 tasks.
        analysis_ref=store.write(out/'defined_QA_checks.DATA.json',staging_bytes({'schema':'PPRIME_NEW20_DEFINED_QA_CHECKS_V1','own_call_checks':list(own_checks.values()),
            'pair_checks':list(pair_checks.values()),'original_predeclared_tolerances':{k:config[k] for k in ('coordinate_atol_A','vector_tolerances','rendered_coordinate_atol_A','same_geometry_dipole_atol_au')},
            'unverified_basis_tensor_other_axes':'UNKNOWN','SP_independent_output_coordinate':'UNKNOWN_NO_COORDINATE_BLOCK','new_companion_calls':0,
            'old15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'})+b'\n')
        closed=len(terminals)==1200 and not errors and len(roles.closed)==1200 and not roles.unknown and len(processes)==16 and all(not p.is_alive() and p.exitcode==0 for p in processes)
        complete=closed and len(own_checks)==1200 and all(v['defined_QC_pass'] for v in own_checks.values()) and len(pair_checks)==1200 and all(v['defined_QC_pass'] for v in pair_checks.values())
        store.json(out/'receipt.json',{'schema':'PPRIME_NEW20_ALL12_QA_RECEIPT_V1','status':'ALL1200_TECHNICALLY_CLOSED_DEFINED_QA_RECORDED_SEMANTICS_UNKNOWN_ROOT_REVIEW' if complete else 'PARTIAL_OR_DEFINED_FAIL_UNKNOWN_HOLD_NO_RETRY',
            'job_id':session['job_id'],'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
            'prepared20_reference':plan['prepared20_reference'],'user_decision_reference':plan['user_decision_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],
            'fixtures_reference':fixture,'maximum_new_QM_calls':1200,'consumed_dispatch_intents':index,'claim_references':claims,'terminal_references':terminals,
            'known_actual_native_counts_from_returned_terminals':counts,'native_counts_for_missing_terminals':'UNKNOWN_NOT_BACKFILLED',
            'attempt_count_definition':'flag immediately before original native invoke;not an independently observed Popen or PID count',
            'proven_not_dispatched':[r['qa_id'] for r in ordered[index:]],'returned_terminals':len(terminals),'verified_closed25M_roles':len(roles.closed),
            'preserved112M_UNKNOWN_roles':sorted(roles.unknown),'analysis_reference':analysis_ref,'all1200_defined_diagnostic_checks_complete':complete,
            'parent_error_without_returned_future_roles':unresolved_roles,
            'original_vector_comparison_checks':sum(len(v['defined_vector_checks']) for v in pair_checks.values()),'errors':errors,'budget':budget.report(),
            'process_closure':[{'pid':p.pid,'exitcode':p.exitcode,'alive':p.is_alive()} for p in processes],
            'new_once_domain':'independent-strict-numerics20-all12-QA-v1','old_once_modified_or_opened':False,'automatic_retry':False,
            'unsupported_semantics_remain_UNKNOWN':True,'SCF_cause':'UNKNOWN','original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD',
            'terminal_actual_cost':'PENDING_ROOT_ACTUAL_ACCOUNTING'})
        return 0 if complete else 3
    except BaseException as exc:
        event.set();store.json(out/'failure.json',{'schema':'PPRIME_NEW20_QA_FAILURE_V1','error':repr(exc),'traceback':traceback.format_exc(),'fixtures_reference':fixture,
            'claim_references':claims,'terminal_references':terminals,'consumed_intents':index,'automatic_retry':False,'scientific_PASS':False,'old15FAIL_preserved':True,'full_or2000_release':'HOLD',
            'budget':budget.report() if budget is not None else None});raise
if __name__=='__main__':raise SystemExit(main())
