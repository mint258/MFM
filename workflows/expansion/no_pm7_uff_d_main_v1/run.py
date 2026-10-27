"""Actual-source preparation,compat32,10k,finite fullbatch,resume or coverage."""
import argparse,collections,concurrent.futures as cf,io,multiprocessing as mp,os,pathlib,platform,sys,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from . import contract as C,io as I,source as S,worker,closure as X,families
Q=C.Q
def fixtures(out,store):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_NO_PM7_NEW_SEAM_METHODS')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    ref=store.json(out/'fixtures3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),
        'before_DATA_monitor_embedding_or_UFF':True,'new_UFF_QM_calls':0})
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_REQUIRED_BEFORE_ACTUAL_DATA_OR_NATIVE');return ref
def execute(plan,manifest,catalog,proof,budget,out,store):
    mode=plan['mode'];recipe=C.fingerprint(catalog);population=plan['ranking_receipt_reference']['sha256'];domain=C.sha(C.canonical([population,recipe]));root=C.CACHE/domain
    root.mkdir(parents=True,exist_ok=True,mode=0o700);Q.need(not any(p.is_symlink() for p in (root,*root.parents)),'OWN_HASHED_CACHE_DOMAIN_NO_SYMLINK')
    snapshot=C.meta(plan['reuse_snapshot_reference']) if plan.get('reuse_snapshot_reference') else None;reuse=X.reuse_rows(snapshot,budget,out)
    ctx=mp.get_context('spawn');event=budget.event;barrier=ctx.Barrier(16);initializations=ctx.Queue();pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=worker.init,initargs=(event,catalog,barrier,initializations))
    session={'parent_pid':os.getpid(),'parent_ticks':I.ticks(os.getpid()),'job_id':str(proof['job_id']),'node':proof['request']['node'],'boot_id':proof['boot_id'],
        'plan_reference':Q.pin(plan['_plan_path']),'startup_proof_reference':Q.pin(plan['_proof_path']),
        'sources':C.unique([*proof['request']['source_references'],proof['request']['script_reference'],Q.pin(plan['_proof_path'])])}
    journal=I.Writer(out/'molecule_results.DATA.jsonl',budget);family_manifest=I.Writer(out/'family_manifest.DATA.jsonl',budget);pending={};items=[];item_bytes=0;family_refs=[];states=collections.Counter();label_states=collections.Counter();errors=[];new_bytes=0;referenced_cache_bytes=0;returned=0;new_calls=0;reused=0;unknown_old=0;warm_pids=[];checked=0;mismatch=0;usable=0;native_stats=collections.Counter();new_native_stats=collections.Counter()
    def flush():
        nonlocal item_bytes
        if items:
            folder=out/'families'/('part_%06d'%len(family_refs));folder.mkdir(parents=True)
            refs=families.export_packets(items,folder,budget,session['job_id']);family_refs.extend(refs)
            for ref in refs:family_manifest.write(ref)
            items.clear();item_bytes=0
    def queue_item(ref,packet):
        nonlocal item_bytes
        size=len(I.staging_bytes(packet))
        if items and item_bytes+size>32<<20:flush()
        items.append((ref,packet));item_bytes+=size
        if len(items)>=128 or item_bytes>=32<<20:flush()
    def accept(row,packet_ref,packet,old):
        nonlocal returned,reused,checked,mismatch,usable,referenced_cache_bytes
        Q.need(packet['source']==row and packet['once_key']==C.once(population,recipe,row) and packet['recipe_fingerprint']==recipe,'SOURCE_CID_RANK_GRAPH_VERSION_AND_PACKET_MATCH')
        returned+=1;reused+=int(old);states[packet['state']]+=1;label_states[packet['label_state']]+=1;usable+=len(packet['conformers'])
        for name in ('candidate_requested','candidate_embedded','embedding_calls','optimizer_attempted','optimizer_returned','candidate_converged_stereo_valid'):
            value=packet.get(name)
            if type(value)is int:
                native_stats[name]+=value
                if not old:new_native_stats[name]+=value
            else:
                native_stats[name+'_UNKNOWN']+=1
                if not old:new_native_stats[name+'_UNKNOWN']+=1
        for name in ('worker_cpu_seconds','elapsed_seconds'):
            value=packet.get(name)
            if type(value)in (int,float):native_stats[name]+=value
            else:native_stats[name+'_UNKNOWN']+=1
        # All referenced permanent bytes,including compat reuse,form the10000
        # profile projection denominator;they are distinct from this job's new bytes.
        refroot=pathlib.Path(packet_ref['path']).parent
        referenced_cache_bytes+=sum(p.stat().st_size for p in refroot.iterdir() if p.is_file())+packet['claim_reference']['bytes']
        comp=packet.get('compatibility')
        if comp:
            checked+=comp['conformers_checked'];mismatch+=int(not comp['direct_original_D3_functions_vs_original_corrected_base_bits_equal'])
            if not comp['direct_original_D3_functions_vs_original_corrected_base_bits_equal']:event.set();errors.append({'ordinal':row['ordinal'],'error':'ORIGINAL_DESCRIPTOR_SEAM_BITS_MISMATCH'})
        if packet.get('source_or_descriptor_contract_HOLD'):event.set();errors.append({'ordinal':row['ordinal'],'error':'SOURCE_OR_DESCRIPTOR_CONTRACT_HOLD','original_error':packet.get('error')})
        journal.write({'ordinal':row['ordinal'],'once_key':packet['once_key'],'packet_reference':packet_ref,'state':packet['state'],'reused_no_new_UFF':old,
            'actual_conformers':len(packet['conformers']),'producer_job_id':packet['producer_job_id'],'source_row_sha256':row['source_row_sha256']})
        queue_item(packet_ref,packet)
    def collect(future,row,key):
        nonlocal new_bytes
        size=256<<20
        try:
            terminal=future.result();size=terminal['new_cache_bytes'];packet=I.read_packet(terminal['packet_reference'],budget)
            new_bytes+=size;accept(row,terminal['packet_reference'],packet,False)
        except BaseException as exc:errors.append({'ordinal':row['ordinal'],'once_key':key,'error':repr(exc),'consumed_no_retry':True});event.set()
        finally:budget.close_role(key,size)
    try:
        warms=[pool.submit(worker.warm) for _ in range(32)];initialized=[initializations.get(timeout=180) for _ in range(16)]
        warm_pids=sorted({r['pid'] for r in initialized});Q.need(len(warm_pids)==16 and all(r['uid']==1278 and r['job_id']==session['job_id'] for r in initialized),'ACTUAL16_INITIALIZED_ORIGINAL_KERNEL_WORKERS')
        for future in warms:future.result()
        for row in S.rows(manifest,mode,budget,plan['lower_inclusive'],plan['upper_exclusive']):
            budget.check(True);key=C.once(population,recipe,row);old=reuse.get(key)
            if old:
                Q.need(old['source_row_sha256']==row['source_row_sha256'],'REUSE_SOURCE_ROW_IDENTITY')
                if old['packet_reference'] is not None:accept(row,old['packet_reference'],I.read_packet(old['packet_reference'],budget),True)
                else:
                    unknown_old+=1;returned+=1;states['CONSUMED_WITHOUT_VALIDATED_PACKET']+=1;label_states['NO_VALIDATED_PACKET_UNKNOWN']+=1
                    journal.write({'ordinal':row['ordinal'],'once_key':key,'state':'CONSUMED_WITHOUT_VALIDATED_PACKET','actual_conformers':None,
                        'claim_reference':old['claim_reference'],'reused_no_new_UFF':True,'source':row})
                    queue_item(None,{'source':row,'molecule_id':C.new_mid(row['pubchem_version'],row['cid'],row['full_key']),
                        'producer_job_id':old['producer_job_id'],'once_key':key,'D20':None,'conformers':[],'orders':{},'generation_count_unknown':True,
                        'state':'CONSUMED_WITHOUT_VALIDATED_PACKET','error':'ORIGINAL_CLAIM_TERMINAL_BUT_NO_VALIDATED_PACKET_NO_RETRY'})
                    continue
                continue
            claim_path=root/'claims'/key[:2]/(key+'.json');claim_path.parent.mkdir(parents=True,exist_ok=True)
            Q.need(not claim_path.exists() and not claim_path.is_symlink(),'EXISTING_UNREVIEWED_OR_ACTIVE_ONCE_HOLD_USE_CPU_RESUME_NO_NATIVE_RETRY')
            budget.reserve(key);claim={'schema':'NO_PM7_UFF_D_NATIVE_DISPATCH_INTENT_V1','once_key':key,'source_ordinal':row['ordinal'],'source_row_sha256':row['source_row_sha256'],
                'cid':row['cid'],'full_key':row['full_key'],'pubchem_version':row['pubchem_version'],'job_id':session['job_id'],'uid':1278,'node':session['node'],
                'recipe_fingerprint':recipe,'ranking_receipt_reference':plan['ranking_receipt_reference'],'source_preparation_receipt_reference':plan['source_preparation_receipt_reference'],
                'plan_reference':session['plan_reference'],'startup_proof_reference':session['startup_proof_reference'],'boot_id':session['boot_id'],'intent_not_native_return':True}
            # Claims live outside the stage output but are prepaid in256M roles.
            claim_store=I.Store(claim_path.parent,256<<20);claim_ref=I.claim_create(claim_path,claim,claim_store);new_calls+=1
            pending[pool.submit(worker.one,row,claim_ref,session,domain)]=(row,key)
            if len(pending)>=32:
                done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                while not done:budget.check(True);done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:r,k=pending.pop(future);collect(future,r,k)
        while pending:
            budget.check(False);done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in done:r,k=pending.pop(future);collect(future,r,k)
    except BaseException as exc:
        event.set();errors.append({'phase':'parent_dispatch','error':repr(exc),'already_claimed_preserved':True})
        for future,(row,key) in list(pending.items()):collect(future,row,key)
        pending.clear()
    finally:
        processes=list((pool._processes or {}).values());pool.shutdown(wait=True,cancel_futures=False);flush();journal.close();family_manifest.close();reuse.close();initializations.close();initializations.join_thread()
    requested=32 if mode=='compat' else 10000 if mode=='profile' else plan['upper_exclusive']-plan['lower_inclusive']
    complete=returned==requested and not errors and not budget.active
    quality=X.audit_result_journal(plan,budget,out,store,journal.reference()) if complete else {'status':'PARTIAL_NATIVE_STAGE_QUALITY_NOT_CLAIMED','DATA_bytes':0,'new_mask_stop_fields':[]}
    if quality['new_mask_stop_fields']:complete=False
    result={'schema':'NO_PM7_UFF_D_COMPUTE_RECEIPT_V1','status':'ALL_SELECTED_MOLECULES_TERMINAL_RECORDED_NO_RELEASE' if complete else 'PARTIAL_OR_CONTRACT_UNKNOWN_HOLD_NO_RETRY',
        'mode':mode,'requested':requested,'returned_terminal_molecules':returned,'molecule_states':dict(states),'label_states':dict(label_states),'actual_unique_geometry_records':usable,
        'new_molecule_dispatch_intents':new_calls,'reused_closed_packets':reused,'prior_consumed_without_validated_packet':unknown_old,'actual_new_cache_bytes':new_bytes,
        'all_referenced_closed_cache_bytes':referenced_cache_bytes,'native_source_statistics':dict(native_stats),
        'native_statistics_scope':'all selected unique source packets,including closed reuse;new_molecule_dispatch_intents reported separately',
        'actual_new_native_statistics':dict(new_native_stats),'native_counts_are_known_lower_bounds_if_claimed_packet_lost':bool(errors),
        'original_D_quality_review':quality,
        'family_output_bytes':sum(r['bytes'] for r in family_refs),'family_manifest_reference':family_manifest.reference(),'family_file_count':len(family_refs),'result_journal_reference':journal.reference(),
        'compatibility_checked_conformers':checked,'compatibility_mismatches':mismatch,'actual_initialized_worker_pids':warm_pids,
        'worker_process_closure':[{'pid':p.pid,'exitcode':p.exitcode,'alive':p.is_alive()} for p in processes],
        'errors':errors,'source_preparation_receipt_reference':plan['source_preparation_receipt_reference'],'recipe_fingerprint':recipe,
        'new_QM_calls':0,'dataset_version':'v2_candidate','training_eligible':False,'D_1p5_full_scan_required_before_acceptance':True,
        'source_chemistry_exclusions_added':0,'budget':budget.receipt(),'actual_stage_terminal_cost':'PENDING_ROOT_ACCOUNTING'}
    observed=referenced_cache_bytes+result['family_output_bytes']+journal.bytes+family_manifest.bytes+quality['DATA_bytes']
    result['profile_variable_output_bytes']=observed
    result['descriptive_storage_projection']={'basis_molecules':returned,'basis_cache_family_and_streamed_review_bytes':observed,
        'first2p5M_variable_bytes_linear':None if not returned else (observed*C.TARGET+returned-1)//returned,
        'both5M_queues_variable_bytes_linear':None if not returned else (observed*10000000+returned-1)//returned,
        'source_preparation_and_resume_fixed_outputs_excluded':True,'actual_current_mask_review_DATA_included':True,
        'worst_case_proven':False,'raw_failure_fraction_and_stereo_UNKNOWN_may_change':True}
    result['descriptive_per_known_conformer']={'known_unique_geometry_records':usable,
        'worker_CPU_seconds_per_known_conformer':native_stats['worker_cpu_seconds']/usable if usable else None,
        'sum_molecule_wall_seconds_per_known_conformer':native_stats['elapsed_seconds']/usable if usable else None,
        'all_attempted_source_failures_in_numerator':not errors and not native_stats['worker_cpu_seconds_UNKNOWN'],
        'allocation_CPU_cost_requires_actual_terminal_sacct':True,'not_native_call_time_only':True}
    return result,complete
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);Q.need(platform.python_version()=='3.11.14','FROZEN_PILOT_SAMPLE_PYTHON');mode=plan['mode'];params=C.parameters(mode,plan['lower_inclusive'],plan['upper_exclusive'],plan['output_cap_bytes'])
    Q.need(plan['schema']=='NO_PM7_UFF_D_STAGE_PLAN_V1' and plan['scope_parameters']==params,'EXACT_PHASE_BOUNDARIES_AND_RECIPE')
    manifest,catalog,graph,data,parents=C.input_parents(plan);Q.need(plan['data_references']==data,'EXACT_REAL_DATA_LOCATORS_NOT_FUTURE_PINS')
    kind='conformer' if mode in ('compat','profile','full') else 'analysis';argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.key(mode),expected_scope_parameters=params,expected_execution_argv=argv,expected_source=__file__,expected_kind=kind,
        required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];Q.need(req['data_references']==data and req['wall_seconds']==plan['wall_seconds'] and req['estimated_peak_output_bytes']==plan['output_cap_bytes']
        and req['pilot'] is (mode in ('compat','profile')),'HONEST_KIND_PILOT_WALL_AND_CAP')
    Q.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_PRIMARY_COMPLETE_ARGV')
    for path in C.sources():Q.need(Q.pin(path) in req['source_references'],'ALL_IMPORTED_CODE_AND_SCIENCE_PINS')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_REPORT_CONTINUE_QUALITY_UNCHANGED')
    quota=C.meta(plan['quota_reuse_reference']);Q.need(quota['compute_node']==req['node'],'CURRENT_ACTUAL_PROVIDER_MAPPING_NODE_NOT_FABRICATED11TO19')
    out=pathlib.Path(plan['output_directory']);Q.need(C.BASE in out.parents and C.CACHE not in out.parents and out!=C.CACHE and not out.exists()
        and '..' not in out.parts and not any(v.is_symlink() for v in (out,*out.parents)),'FRESH_STAGE_DIRECTORY_NOT_CACHE_OR_OLD_SOURCE')
    out.mkdir(parents=True,mode=0o700);store=I.Store(out,plan['output_cap_bytes']);fixture=None;budget=None;event=mp.get_context('spawn').Event();started=time.monotonic()
    try:
        fixture=fixtures(out,store);budget=I.Budget(plan,proof,out,event);budget.check(True,True)
        runtime_plan=dict(plan,_plan_path=str(a.plan),_proof_path=str(a.startup_proof))
        if mode=='source':
            result={'status':'ORDERED_SOURCE_PREPARATION_COMPLETE_NO_UFF','mode':mode,'source_manifest_reference':S.prepare(plan,budget,out,store,proof),'new_UFF_calls':0};complete=True
        elif mode=='resume':result={'status':'CLOSED_CACHE_SNAPSHOT_COMPLETE_NO_UFF','mode':mode,'snapshot_reference':X.resume(runtime_plan,manifest,catalog,budget,out,store,proof),'new_UFF_calls':0};complete=True
        elif mode=='coverage':result={'status':'COVERAGE_RECORDED_NO_UFF_NO_ACCEPTANCE','mode':mode,'coverage_reference':X.coverage(plan,manifest,catalog,budget,out,store),'new_UFF_calls':0};complete=True
        else:result,complete=execute(runtime_plan,manifest,catalog,proof,budget,out,store)
        import numpy,pyarrow,torch
        from rdkit import rdBase
        result.update(job_id=str(proof['job_id']),node=req['node'],uid=1278,endpoint='202.38.247.57:22',plan_reference=Q.pin(a.plan),startup_proof_reference=Q.pin(a.startup_proof),
            fixtures_reference=fixture,wall_seconds_observed=time.monotonic()-started,budget=budget.receipt(),scientific_acceptance=False,pool_or_training_release=False)
        result['actual_environment']={'python':platform.python_version(),'RDKit':rdBase.rdkitVersion,'numpy':numpy.__version__,'torch':torch.__version__,'pyarrow':pyarrow.__version__,
            'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'CPU_only':True}
        store.json(out/'receipt.json',result);return 0 if complete else 3
    except BaseException as exc:
        event.set();store.json(out/'failure.json',{'schema':'NO_PM7_UFF_D_FAILURE_V1','status':'HOLD_EVIDENCE_AND_ONCE_PRESERVED','error':repr(exc),'traceback':traceback.format_exc(),
            'fixtures_reference':fixture,'new_QM_calls':0,'old_sources_or_ledgers_modified':False,'budget':budget.receipt() if budget else None});raise
if __name__=='__main__':raise SystemExit(main())
