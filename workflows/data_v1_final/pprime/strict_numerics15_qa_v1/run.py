"""User-authorized independent strict-numerics15 QA; never production release."""
import argparse,concurrent.futures as cf,io,json,multiprocessing as mp,os,pathlib,socket,sys,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.data_v1_final.pprime.causal15_main_v1 import analysis as A,render as T
from workflows.data_v1_final.pprime.causal15_geometry_readonly_v1.run import body
from workflows.data_v1_final.pprime.common import read_staging,staging_bytes
from . import contract as C,io as W,prepare as P,worker
Q=C.Q


def fixtures(out,store):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_SYNTHETIC_METHODS')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),
        'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),'before_scientific_bodies':True,'native_initialize_calls':0,'native_invoke_calls':0}
    ref=store.json(out/'fixtures3.json',value)
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS_BEFORE_BODY_OR_INITIALIZE');return ref


def evaluate(records,config,evidence,controls):
    import numpy as np
    from evaluate_v1 import measurement,compare_stored
    from math_v1 import covariance
    result=A.analyze(records,config,evidence);measured={r['qa_id']:measurement(r,config) for r in records};by={(r['condition'],r['arm']):r for r in records}
    old_checks=[];fields={'pm7_B':{'pm7_dipole_Debye','pm7_gradient_kcal_mol_A'},'xtb_perturbed_gradient':{'xtb_dipole_Debye','xtb_gradient_Eh_bohr'},
        'xtb_singlepoint_noisy_companion':{'xtb_dipole_Debye'}}
    for record in records:
        new=measured[record['qa_id']];old=measurement(controls[record['qa_id']],config);checks={}
        for name in sorted(set(old['vectors'])&set(new['vectors'])):
            x,y=old['vectors'][name],new['vectors'][name];checks[name]=covariance(x['values'],y['values'],x['rounding_halfwidth'],y['rounding_halfwidth'],config['vector_tolerances'][name],np.eye(3).tolist())
        old_checks.append({'qa_id':record['qa_id'],'original_qa_id':record['original_qa_id'],'same_actual_arm_comparisons':checks,
            'original_WP5_status_unknown_preserved':record['original_qa_id'] in ('qa-02','qa-08'),'changed_settings_agreement_is_not_a_new_acceptance_gate':True})
    companions=[]
    for arm in C.O.ARMS:
        g=by.get(('xtb_perturbed_gradient',arm));s=by.get(('xtb_singlepoint_noisy_companion',arm))
        if g is None or s is None:companions.append({'arm':arm,'pass':False,'status':'COMPANION_UNAVAILABLE'});continue
        gm,sm=measured[g['qa_id']],measured[s['qa_id']]
        same=bool(np.max(np.abs(np.asarray(g['case']['actual_rendered_coordinates_A'])-np.asarray(s['case']['actual_rendered_coordinates_A'])))<=config['rendered_coordinate_atol_A'])
        dip=compare_stored(gm.get('dipole_au'),sm.get('dipole_au'),config['same_geometry_dipole_atol_au'])
        companions.append({'arm':arm,'same_actual_input_geometry':same,'SP_gradient_raw_dipole_agreement':dip,'gradient_own_output_frame':gm['coordinates'],
            'SP_has_no_independent_coordinate_block':True,'pass':same and gm['coordinates']['supports_input_axes'] and dip['pass']})
    own=[]
    for record in records:
        m=measured[record['qa_id']];expected=fields[record['condition']]
        checks={'exact_requested_vectors_present':expected<=set(m['vectors']),'source_scope_SUCCESS':m['QM_scope_status']=='SUCCESS',
            'actual_postcall_inputs_match':bool(record.get('actual_postcall_input_references')) and m['postcall_inputs_match_prepared'],
            'stored_raw_fields_agree':bool(m['stored_raw_checks']) and all(x['pass'] for x in m['stored_raw_checks'].values()),
            'own_axes_and_order':m['coordinates']['supports_input_axes'] and m['coordinates'].get('atom_order_matches',False) if record['condition']!='xtb_singlepoint_noisy_companion' else None,
            'force_relation':m.get('force_relation',{}).get('pass') if record['condition']=='xtb_perturbed_gradient' else None}
        own.append({'qa_id':record['qa_id'],'checks':checks,'pass':all(v is True for v in checks.values() if v is not None),'own_coordinate_evidence':m['coordinates']})
    rotation_ok=len(result['comparisons'])==15 and all(set(v['checks'])==fields[v['condition']] and all(c['pass'] for c in v['checks'].values()) for v in result['comparisons'])
    passed=len(records)==15 and rotation_ok and len(own)==15 and all(v['pass'] for v in own) and all(v['pass'] for v in companions)
    result.update(original1766_1802_same_arm_control_comparisons=old_checks,own_output_and_readback_checks=own,same_geometry_companion_checks=companions,
        limited_new15_predeclared_QA_checks_all_pass=passed,original_predeclared_tolerances={k:config[k] for k in ('coordinate_atol_A','vector_tolerances','rendered_coordinate_atol_A','same_geometry_dipole_atol_au')},
        no_automatic20_molecule_or_full_gate=True,new_QA_parameter_effect_cause='UNKNOWN_ROOT_REVIEW_REQUIRED')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);C.require_user(plan)  # Deliberately before parent traversal, DATA or initialize.
    old,new,diff,source,prepared,prepared_ref,cases,data,parents,prior=C.parents(plan)
    Q.need(plan['schema']=='PPRIME_STRICT_NUMERICS15_QA_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS and plan['original_prepared_reference']==prepared_ref
        and plan['case_sources']==cases and plan['data_references']==data,'EXACT_PROPOSED15_AND_ACTUAL_CONTROL_CHAIN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,expected_source=__file__,expected_kind='qm',
        required_references=[Q.pin(a.plan),plan['user_decision_reference'],*parents,plan['cost_decision_reference']])
    req=proof['request'];auth=C.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in auth['allowed_nodes']['qm']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP
        and req['wall_seconds']==plan['wall_seconds']==7200 and req['data_references']==data and not req.get('deferred_authority_references'),'EXACT_QM_CPU16_NO_MEM_2H2GiB')
    review=C.meta(req['scope']['review']);Q.need(review['user_limited15_numerical_QA_only'] is True and review['user_decision_reference']==plan['user_decision_reference']
        and review['original15FAIL_preserved'] is True and review['full_or2000_release']=='HOLD','ROOT_EXACT_AUTHORIZED15_QA_SCOPE')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'COST_AUTHORITY_DOES_NOT_REPLACE_NUMERICAL_USER_DECISION')
    source_refs=C.unique([*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(C.P.HERE/n) for n in C.P.FILES),*prior])
    for ref in source_refs:Q.need(ref in req['source_references'],'ALL_NEW_AND_ORIGINAL_SOURCE_BYTES_PINNED')
    Q.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_PRIMARY_FULL_ARGV_NOT_WRAPPER')
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[k]='1'
    Q.need(C.WORKER_CAP*15+C.PARENT_CAP<C.CAP,'PARTITIONED_WHOLE_OUTPUT_MATH')
    out=pathlib.Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and C.BASE in out.parents and C.LEDGER not in out.parents and out!=C.LEDGER
        and not any(v.is_symlink() for v in (out,*out.parents)) and not out.exists(),'NEW_INDEPENDENT_QA_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    store=W.Store(out,C.PARENT_CAP);budget=W.Budget(plan,proof);records=[];errors=[];claims=[];processes=[];index=0;fixture_ref=None
    try:
        Q.need(budget.observe() is None,'FRESH_OBSERVED_RESOURCES_BEFORE_FIXTURES_OR_BODY');fixture_ref=fixtures(out,store)
        engine,_,_,_=T.engine(source,C.N.G.P.I.read)  # Import and frozen metadata only. Never initialize in parent.
        Q.need(budget.observe() is None,'FRESH_OBSERVED_RESOURCES_BEFORE_BODY');tasks,evidence,controls=P.all_tasks(plan,source,prepared,cases,old,new,engine,out,store)
        manifest=store.json(out/'prepared15.json',{'schema':'PPRIME_STRICT_NUMERICS15_EXACT_PREPARED_V1','tasks':tasks,'original_prepared_reference':prepared_ref,
            'candidate_protocol_reference':plan['candidate_protocol_reference'],'user_decision_reference':plan['user_decision_reference'],'protocol_diff':diff,'new_QM_calls':0})
        C.LEDGER.mkdir(parents=True,mode=0o700,exist_ok=True);Q.need(not any(v.is_symlink() for v in (C.LEDGER,*C.LEDGER.parents)),'NEW_LEDGER_NO_SYMLINK')
        paths=[C.LEDGER/(C.once_key(plan,prepared_ref,v['original_qa_id'])+'.json') for v in tasks]
        Q.need(not any(v.exists() or v.is_symlink() for v in paths),'NEW_PROTOCOL_CLAIM_ALREADY_CONSUMED_NEVER_RETRY')
        session={'parent_pid':os.getpid(),'parent_ticks':W.ticks(os.getpid()),'job_id':str(proof['job_id']),'node':req['node'],'boot_id':proof['boot_id'],
            'plan_reference':Q.pin(a.plan),'source_references':C.unique([*req['source_references'],req['script_reference'],Q.pin(a.startup_proof)])}
        deadline=time.time()+plan['wall_seconds']-budget.initial_elapsed-(time.monotonic()-budget.start)-60
        active={};pool=cf.ProcessPoolExecutor(max_workers=15,mp_context=mp.get_context('spawn'))
        try:
            while active or index<15:
                budget.observe()
                while index<15 and len(active)<15 and budget.observe() is None:
                    row=tasks[index];claim={'schema':'PPRIME_STRICT_NUMERICS15_QA_DISPATCH_INTENT_V1','qa_id':row['qa_id'],'original_qa_id':row['original_qa_id'],
                        'task_reference':row['task_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],'original_prepared_reference':prepared_ref,
                        'user_decision_reference':plan['user_decision_reference'],'job_id':session['job_id'],'uid':1278,'boot_id':session['boot_id'],
                        'startup_proof_reference':Q.pin(a.startup_proof),'state':'SUBMIT_INTENT_NOT_NATIVE_RETURN','automatic_retry':False}
                    claim_ref=W.claim_create(paths[index],claim,store);claims.append(claim_ref);index+=1
                    active[pool.submit(worker.one,row['task_reference'],claim_ref,source,session,str(out),deadline)]=row['qa_id']
                if not active:break
                done,_=cf.wait(active,timeout=.25,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    qa=active.pop(future)
                    try:records.append(future.result())
                    except BaseException as exc:errors.append({'qa_id':qa,'error':repr(exc),'state':'CONSUMED_UNKNOWN_NO_RETRY'})
        except BaseException as exc:
            errors.append({'phase':'parent_dispatch','error':repr(exc),'existing_claims_remain_consumed':True})
            for future,qa in list(active.items()):
                try:records.append(future.result())
                except BaseException as exc:errors.append({'qa_id':qa,'error':repr(exc),'state':'CONSUMED_UNKNOWN_NO_RETRY'})
        finally:
            processes=list((pool._processes or {}).values());pool.shutdown(wait=True,cancel_futures=False)
        values=[read_staging(body(ref,C.O.RESULT_CAP)) for ref in records]
        Q.need(len({v['qa_id'] for v in values})==len(values) and all(v['candidate_protocol_reference']==plan['candidate_protocol_reference'] for v in values),'EXACT_NEW_QA_RESULT_IDENTITY')
        config=C.N.G.P.I.read(source['audit_config']);findings=evaluate(values,config,evidence,controls)
        analysis_ref=store.write(out/'strict15_analysis.json',staging_bytes(findings)+b'\n')
        complete=len(values)==15 and not errors and all(not v.get('error') and not v.get('raw_close_error') and not v.get('engine_close_error')
            and v.get('raw_reference',{}).get('raw_call_durable') and v.get('closed_raw_container_reference') for v in values)
        receipt={'schema':'PPRIME_STRICT_NUMERICS15_QA_RECEIPT_V1','status':'ACTUAL15_TECHNICALLY_CLOSED_REQUIRES_ROOT_REVIEW' if complete else 'CONSUMED_OR_UNDISPATCHED_UNKNOWN_HOLD',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
            'user_decision_reference':plan['user_decision_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],'prepared_reference':manifest,
            'fixtures_reference':fixture_ref,'result_references':records,'claims':claims,'maximum_new_QM_calls':15,
            'known_calls_attempted_from_returned_records':sum(v['QM_call_attempted'] for v in values),'consumed_call_upper_bound':len(claims),
            'proven_not_dispatched':[r['qa_id'] for r in tasks[index:]],'dispatched_without_return':sorted({r['qa_id'] for r in tasks[:index]}-{v['qa_id'] for v in values}),
            'original_timeout_seconds':900,'unknown_or_failed_call_replacement':False,'errors':errors,'analysis_reference':analysis_ref,
            'limited_new15_predeclared_QA_checks_all_pass':complete and findings['limited_new15_predeclared_QA_checks_all_pass'],
            'process_closure':[{'pid':p.pid,'exitcode':p.exitcode,'alive':p.is_alive()} for p in processes],'budget':budget.report(),
            'production_once_opened':False,'original15_once_opened':False,'original15FAIL_preserved':True,'original_WP5_unknown_cases':['qa-02','qa-08'],
            'scientific_PASS':False,'full_or2000_release':'HOLD','new20molecule_all12task_QA_requires_separate_gate':True,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING'}
        store.json(out/'receipt.json',receipt);return 0 if complete else 3
    except BaseException as exc:
        store.json(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'fixtures_reference':fixture_ref,'claims':claims,'returned_result_references':records,
            'known_dispatched_claims':index,'automatic_retry':False,'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD','budget':budget.report()});raise


if __name__=='__main__':raise SystemExit(main())
