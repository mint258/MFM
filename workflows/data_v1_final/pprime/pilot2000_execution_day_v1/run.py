"""A bounded original2000 pilot. No submitter, retry, full launch or new QA arms."""
import argparse,collections,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,pathlib,sys,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.expansion.common_molecular_fp_main_v1.io import Body
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from . import contract as C,io as I,worker,source_boundary
Q=C.Q
def fixtures(out):
    from . import test_v1
    test_v1.WORKSPACE=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);C.need(suite.countTestCases()==3,'EXACT3_BEFORE_DATA_CLAIM_OR_INITIALIZE')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=Q.write_new(out/'source3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
      'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'before_DATA_claim_initialize':True})
    C.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED_NO_SCIENCE');return ref
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.meta(Q.pin(a.plan));old,new,diff,context,pilot,prepared,pair_ref,data,parents=C.inputs(plan);params=C.parameters(plan['node'],plan['precision_mode'])
    C.need(plan['schema']=='PPRIME2000_FORMAL_PILOT_DAY_PLAN_V1' and plan['scope_parameters']==params and plan['data_references']==data,'EXACT_FORMAL2000_FROZEN_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=require_startup(a.startup_proof,expected_kind='qm',expected_scope_key=C.KEY,expected_scope_parameters=params,expected_execution_argv=argv,
      expected_source=C.HERE/'run.py',required_references=[Q.pin(a.plan),*plan['source_references']]);req=proof['request'];review=C.meta(req['scope']['review'])
    C.need(req['node']==plan['node'] and req['cpus']==16 and req['pilot'] is False and req['wall_seconds']==plan['wall_seconds']==C.WALL
      and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==plan['output_cap_bytes']==C.CAP and req['data_references']==data
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','EXACT16_NO_MEM_DAY32G_QM_PILOT_NOT_FULL')
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'PRIMARY_FULL_ARGV_NOT_WRAPPER')
    selected_protocol=C.precision(plan,review)  # before DATA, claim, initialize
    for ref in C.sources(plan):C.need(ref in req['source_references'],'ALL_DIRECT_OLD_SCIENCE_AND_NEW_IO_SOURCE_PINS')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';out=C.M.fresh(plan['output_directory'],'artifacts');C.need(C.BASE in out.parents,'FRESH_OWN_PILOT_OUTPUT');out.mkdir(parents=True,mode=0o700)
    source_gate=source_boundary.verify_sources();fixture=fixtures(out);roles=I.Roles();event=mp.get_context('spawn').Event();store=I.Store(out,C.PARENT_CAP)
    budget=I.Budget(plan,proof,out,roles,store)
    failures=[];terminals=[];processes=[];global_claim=None;reproduction=None;record_rows=[];worker_rows=[];gate_proof=None;pool=None;started=time.monotonic();stopped=None
    try:
        budget.check(force=True);prepared=I.prepared_body(plan,prepared,data,budget)
        pairs,pair_check=C.P.OriginalInputs.pairs(pair_ref,budget);grouped=C.P.pairs_matrix(pairs)
        hash_rows=[row for row,_ in I.I.json_rows(prepared['record_input_hashes_reference'],budget)];expected=I.record_hashes(hash_rows)
        C.need(set(expected)=={p['record_id'] for p in pairs},'EVERY_ACTUAL_SELECTED_RECORD_HAS_FROZEN_PRECALL_HASHES')
        source_audit=json.loads(I.body(prepared['stable_source_audit_reference'],data,budget));C.need(len(source_audit)==2000,'ACTUAL_STABLE_RAW_AUDIT_CENSUS')
        C.need(len({row['record_id'] for row in source_audit})==2000
          and {row['record_id'] for row in source_audit}==set(expected),'EXACT_SAME2000_SOURCE_AUDIT_IDS_NOT_NEW_SELECTION')
        software_specs=C.P.software_original_specs(context);software_checks=[]
        for ref in context['execution_asset_references']:
            if ref['path'] in software_specs:
                software_checks.append(I.Preparation.hash_software_original(C.P.triple(ref),software_specs[ref['path']],budget));continue
            body=Body(C.P.triple(ref),budget)
            try:body.check()
            finally:body.close()
        C.need(len(software_checks)==14 and len(context['execution_asset_references'])==446,'EXACT_R2_14_SOFTWARE_AND432_ORDINARY_ASSETS')
        reproduction=store.json(out/'reproduction_manifest.json',{'schema':'PPRIME2000_FORMAL_PILOT_REPRODUCTION_V1','prepared2000_reference':plan['prepared2000_reference'],
          'original_pairs_reference':pair_ref,'pair_SHA_checked_in_this_CPU':pair_check,'source_context_reference':plan['source_context_reference'],
          'original_protocol_reference':plan['original_protocol_reference'],'selected_protocol_reference':selected_protocol,'precision_mode':plan['precision_mode'],
          'candidate_only3_differences':diff if plan['precision_mode']!='ORIGINAL_WP5' else [],'software_versions_changed':False,
          'scientific_numerics_changed':plan['precision_mode']!='ORIGINAL_WP5','root_stage_review_reference':req['scope']['review'],
          'user_precision_decision_reference':plan.get('user_precision_decision_reference'),'audit_membership_reference':prepared['audit_membership_reference'],
          'software_original_CPU_verifications':software_checks,'ordinary_declared_asset_count':432,'direct_original_sources':source_gate,
          'stable_source_audit_reference':prepared['stable_source_audit_reference'],'source_references':plan['source_references'],'new_QA_arms':0,'full_authorized':False})
        ledger=C.ledger(plan);ledger.mkdir(parents=True,mode=0o700,exist_ok=True);physical=ledger/'physical_records_v1';physical.mkdir(mode=0o700,exist_ok=True)
        budget.check()  # Budget approval must still hold before consuming the pilot once.
        global_claim=I.claim_create(ledger/(C.legacy_once_key(pair_ref,plan['original_protocol_reference'])+'.json'),{'status':'PILOT_STARTED_OUTCOME_UNKNOWN_UNTIL_CLOSED',
          'job_id':str(proof['job_id']),'uid':1278,'boot_id':proof['boot_id'],'original_pairs':pair_ref,'protocol':plan['original_protocol_reference'],
          'selected_protocol_reference':selected_protocol,'prepared2000_reference':plan['prepared2000_reference'],'output':str(out),'reproduction':reproduction},store)
        session=I.source_session(Q.pin(a.plan),plan,proof);deadline=time.time()+max(0,C.WALL-budget.elapsed-(time.monotonic()-budget.start)-180)
        (out/'workers').mkdir();(out/'records').mkdir();todo=iter(sorted(pairs,key=lambda p:(p['molecule_id'],p['random_order_rank'])));active={};ordinal=0;exhausted=False
        pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker.initialize,
          initargs=(session,event,str(out),context,selected_protocol,prepared['audit_membership_reference'],reproduction['sha256'],deadline))
        while active or not exhausted:
            try:budget.check()
            except BaseException as exc:stopped=stopped or repr(exc);event.set()
            while not exhausted and not event.is_set() and roles.can_start():
                if deadline-time.time()<12*900+120:stopped='WHOLE12_ORIGINAL900_DRAIN_ADMISSION_CLOSED';event.set();break
                try:pair=next(todo)
                except StopIteration:exhausted=True;break
                key=C.record_once_key(pair,plan['original_protocol_reference']);roles.start(key);slot=ordinal%16
                claim=I.claim_create(physical/(key+'.json'),{'record_id':pair['record_id'],'record_once_key':key,'pair_sha256':hashlib.sha256(C.O.canonical(pair)).hexdigest(),
                  'prepared2000_reference':plan['prepared2000_reference'],'original_protocol_reference':plan['original_protocol_reference'],
                  'selected_protocol_reference':selected_protocol,'job_id':str(proof['job_id']),'uid':1278,'boot_id':proof['boot_id'],
                  'dispatch_slot':slot,'global_pilot_once':global_claim,'native_return_claimed':False,'output':str(out/'records'/key)},store)
                future=pool.submit(worker.one,pair,expected[pair['record_id']],claim,str(out/'records'/key),reproduction['sha256']);active[future]=(key,pair);ordinal+=1
            if not active:
                if event.is_set() or not roles.can_start():break
                continue
            completed,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in completed:
                key,pair=active.pop(future)
                try:
                    ref=future.result();terminal=I.value(ref,[ref],budget);C.need(terminal['record_id']==pair['record_id'],'ACTUAL_RETURNED_RECORD_BINDING')
                    actual=I.quiescent(out/'records'/key);roles.settle(key,actual,terminal['technical_record_complete']);terminals.append((ref,terminal))
                    if not terminal['technical_record_complete']:event.set();failures.append({'record_id':pair['record_id'],'status':'PARTIAL_OR_FAILED_UNKNOWN_NO_RETRY','terminal_reference':ref})
                except BaseException as exc:
                    event.set();failures.append({'record_id':pair['record_id'],'status':'WORKER_FUTURE_UNKNOWN_NO_RETRY','error':repr(exc)});roles.settle(key,0,False)
        processes=list(pool._processes.values());pool.shutdown(wait=True,cancel_futures=False);pool=None
        process_closure=[{'pid':p.pid,'exitcode':p.exitcode,'alive':p.is_alive()} for p in processes]
        joined=len(process_closure)==16 and all(not r['alive'] and r['exitcode']==0 for r in process_closure)
        for process in processes:
            path=out/'workers'/('worker_%d_closed.json'%process.pid)
            if path.exists():
                ref=I.I.data_pin(path,[out]);row=I.value(ref,[ref],budget);worker_rows.append(dict(row,actual_reference=ref))
        joined=joined and len(worker_rows)==16 and all(not r.get('close_error') for r in worker_rows)
        # Only closed producer outputs are opened. Original portable staging
        # restores nonfinite float64 bits; no float32 or value repair.
        for ref,t in terminals:
            if t['record_reference'] is not None:record_rows.append(I.value(t['record_reference'],[t['record_reference']],budget))
        record_rows.sort(key=lambda r:r['record_id']);families=[];qc=[]
        engine,legacy,protocol,pilot=T.engine(context,C.meta);engine.CONFIG=C.meta(selected_protocol);originals=source_boundary.objects()
        if len(record_rows)==2000 and len(terminals)==2000 and joined and not failures:
            # Original exporter remains unchanged. Its whole-tree cap is set
            # to the already-closed record bytes plus the prepaid parent role,
            # leaving512MiB for fixtures/worker closure/quota/drain metadata.
            export_limit=min(C.CAP,sum(roles.closed.values())+C.PARENT_CAP-(512<<20))
            resource_config=dict(pilot,max_output_bytes=export_limit,external_output_root=str(C.BASE))
            families,qc=originals['export'](record_rows,out/'parquet',engine,reproduction['sha256'],resource_config)
            store.limit=C.PARENT_CAP-sum(f['bytes'] for f in families)-(512<<20)
            C.need(store.limit>store.charged+(16<<20),'ACTUAL_FAMILY_FILES_FIT_PREPAID_PARENT_AND_DRAIN')
        sys.path[:0]=[str(Q.REPO/'workflows/data_v1_final/pprime/retention_v1'),str(Q.REPO/'workflows/data_v1_final/pprime')]
        workers=[{'raw_container':t['raw_container']} for _,t in terminals if t['raw_container']]
        try:proof_raw=originals['prove_raw'](workers,source_audit,record_rows,engine)
        except BaseException as exc:
            proof_raw={'status':'ORIGINAL_RAW_PROOF_FAILED_PARTIAL_EVIDENCE_PRESERVED','missing':['ORIGINAL_PROOF_NOT_CLOSED'],
              'error_type':type(exc).__name__,'error':str(exc),'all_original_containers_retained':workers,'no_raw_or_parser_repair':True}
        gate_proof=store.json(out/'stable_raw_all12_proof.json',proof_raw)
        if proof_raw['missing']:failures.append({'status':'STABLE_ALL12_OR_FAILED_RAW_READBACK_INCOMPLETE'})
        if not joined:failures.append({'status':'ALL16_ACTUAL_WORKERS_CLOSED_JOINED_NOT_PROVEN'})
        successful=sum(r['all_twelve_tasks_success'] for r in qc) if qc else sum(len(r['tasks'])==12 and all(d['scope_status']=='SUCCESS' for d in r['tasks']) for r in record_rows)
        completed=len(record_rows);native_observed=sum(t['native_return_count'] for _,t in terminals)
        report={'status':'PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING' if families and joined and completed==2000 and not failures else 'PPRIME_PILOT_FAILED_NO_FULL_AUTHORITY',
          'runtime':{'job_id':str(proof['job_id']),'node':req['node'],'allocated_cpus':16,'workers':16},'config':context['pilot_config'],
          'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),'prepared':plan['prepared2000_reference'],'original_pairs_reference':pair_ref,
          'source3_reference':fixture,'direct_original_source_boundary':source_gate,
          'reproduction_manifest':reproduction,'selected_protocol_reference':selected_protocol,'precision_mode':plan['precision_mode'],
          'root_stage_review_reference':req['scope']['review'],'user_precision_decision_reference':plan.get('user_precision_decision_reference'),
          'requested_records':2000,'completed_records':completed,'all_twelve_tasks_success_records':successful,'record_success_rate':successful/2000,
          'dispatched_records':ordinal,'maximum_native_calls':24000,'actual_observed_native_returns':native_observed,
          'unobserved_attempts_unknown':bool(failures),'all_workers_joined':joined,'process_closure':process_closure,'worker_closure_references':[r['actual_reference'] for r in worker_rows],
          'failures':failures,'family_parquets':families,'stable_raw_retention_proof':gate_proof,'legacy_pilot_once_reference':global_claim,
          'roles':{'active':len(roles.active),'closed':len(roles.closed),'UNKNOWN':len(roles.unknown),'reserved_bytes':roles.bound()},
          'stop_new_dispatch_reason':stopped,'forced_signals_sent':False,'parent_wall_seconds_within_CLI':time.monotonic()-started,
          'allocated_core_seconds_per_conformer':None,'actual_parent_accounting_pending':True,'startup_export_retention_failures_not_deducted':True,
          'separate_zero_invoke_preparation_cost_must_also_be_reported':plan['prepare_accounting_reference'],
          'Pprime_outlier_scan_completed':False,'P_vs_Pprime_comparison_completed':False,'scientific_PASS':False,'full_run_authorized':False,
          'original_atomic_array_nonfinite_scope_status_gates_unchanged':True,'original_one_percent_quality_mask_gate_not_waived':True,
          'anomaly_or_distribution_acceptance_not_inferred_from_technical_record_complete':True,
          'resource_report':budget.report(),'quota_guard_event_references':budget.quota_guard_event_references,
          'old15FAIL_and_precision_diagnostics_preserved':True,'original_LMDB_WP5_or_Sprime_modified':False}
        costrows=[{'record_id':t['record_id'],'terminal_reference':r,'record_worker_elapsed_seconds':t['record_worker_elapsed_seconds'],
          'original_scientific_elapsed_seconds':t['scientific_elapsed_seconds'],'technical_record_complete':t['technical_record_complete'],
          'observed_native_returns':t['native_return_count'],'unobserved_attempts_UNKNOWN':t['UNKNOWN_attempts_retained'],
          'actual_allocated_core_seconds_per_this_record':None,
          'cost_basis':'ORIGINAL_ELAPSED_AND_REAL_WORKER_WALL_NOT_FAKE_PARENT_ALLOCATION_ATTRIBUTION'} for r,t in terminals]
        report['per_record_cost_observations_reference']=store.json(out/'per_record_cost_observations.DATA.json',costrows)
        report['record_terminals_reference']=store.json(out/'record_terminals.DATA.json',[{'terminal_reference':r,**t} for r,t in terminals])
        store.json(out/'result.json',report)
        budget.check(dispatch=False,force=True);return 0 if report['status']=='PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING' else 3
    except BaseException as exc:
        event.set();store.json(out/'failure.DATA.json',{'error_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'partial_retained':True,
          'global_once_reference':global_claim,'new_precision_not_inferred_from_diagnostics':True,'scientific_PASS':False,'full_run_authorized':False});raise
    finally:
        if pool is not None:pool.shutdown(wait=True,cancel_futures=False)
        budget.check(dispatch=False,force=True)
if __name__=='__main__':raise SystemExit(main())
