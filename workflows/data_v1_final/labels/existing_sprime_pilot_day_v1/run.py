"""One bounded pilot parent: immutable prefix, geometry, typed labels and TRAIN statistics."""
import argparse,concurrent.futures as cf,copy,io,json,multiprocessing as mp,os,sys,traceback,unittest
from pathlib import Path
from . import contract as C,io as I,bindings as B,coverage as V,geometry as G,eligibility as E,statistics as T,loss as L
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity
ROUTES=('element_reference','normalization_quantiles','normalization_moments','diagnostic_median_MAD')

def references(value):
    if isinstance(value,dict):
        if {'path','bytes','sha256'}<=set(value):yield C.reference(value,source=value.get('bytes')==0)
        else:
            for v in value.values():yield from references(v)
    elif isinstance(value,list):
        for v in value:yield from references(v)

def fixtures(root):
    from . import test_boundaries,source_inverse
    from workflows.data_v1_final.labels.common_train_normalization_day_v1 import test_boundaries as original
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (original.Boundaries,test_boundaries.Boundaries)])
    C.need(suite.countTestCases()==6,'EXACT_ORIGINAL3_AND_NEW3_IN_ONE_PARENT_BEFORE_DATA_AND_BUDGET')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=I.save(root/'preflight.json',{'schema':'EXISTING_SPRIME_PILOT_SIX_BOUNDARIES_V1',
        'status':'PASS' if result.wasSuccessful() and result.testsRun==6 and not result.skipped else 'FAIL_NO_DATA',
        'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'transcript':stream.getvalue(),
        'source_inverse':source_inverse.proof(),'original_objects':B.verify(),'scientific_DATA_read':False})
    C.need(result.wasSuccessful() and result.testsRun==6 and not result.skipped,'SIX_BOUNDARIES_FAILED_NO_DATA');return ref

def numeric_state():
    return {'route_index':0,'query_reference':None,'element_models_reference':None,'exact_tail_reference':None,
        'winsorized_statistics_reference':None,'diagnostic_median_MAD_reference':None,'pending_group_reports':[],'pending_group_errors':[]}

def next_route(state,result):
    purpose=ROUTES[state['route_index']];C.need(result['statistics_purpose']==purpose,'EXACT_ORIGINAL_STATISTICS_PHASE')
    if result['next_query_stage'] is not None:state['query_reference']=result['next_query_stage'];return
    key={'element_reference':'element_reference_models_reference','normalization_quantiles':'exact_tail_reference',
        'normalization_moments':'winsorized_statistics_reference','diagnostic_median_MAD':'diagnostic_median_MAD_reference'}[purpose]
    C.need(result[key] is not None,'NO_ADVANCE_ON_MISSING_ORIGINAL_STATISTICS')
    state['element_models_reference' if purpose=='element_reference' else key]=result[key]
    state.update(route_index=state['route_index']+1,query_reference=None,pending_group_reports=[],pending_group_errors=[])

def canonical_numeric(state):
    models=I.load_data(state['element_models_reference']);tail=I.load_data(state['exact_tail_reference'])
    moments=I.load_data(state['winsorized_statistics_reference']);diagnostic=I.load_data(state['diagnostic_median_MAD_reference'])
    return {'models':models,'exact_tails':{'catalog':tail['catalog'],'quantiles':tail['quantiles']},
        'winsorized_component_and_invariant_audit':moments,'diagnostic_median_MAD':diagnostic['fields']}

def execute(plan,proof,root,gate,budget):
    state={'schema':'EXISTING_SPRIME_PILOT_DAY_CHECKPOINT_V1','phase':'PREFIX','prefix_reference':None,
        'coverage_reference':None,'geometry_reference':None,'eligibility_reference':None,'population_reference':None,
        'typed_reader_config_reference':None,
        'numeric_repetitions':[],'numeric_state':numeric_state(),'pass_number':0,'r674_report_reference':None}
    sequence=0;errors=[];latest=None
    def checkpoint():
        nonlocal sequence,latest
        sequence+=1;latest=I.save(root/('checkpoint_%06d.json'%sequence),state);return latest
    def finish(status,*,held=False):
        checkpoint()
        for ref in plan['source_references']:I.require(ref)
        return I.save(root/'receipt.json',{'schema':'EXISTING_COMPLETE_SPRIME_PILOT_DAY_RECEIPT_V1','status':status,
            'job_id':str(proof['job_id']),'actual_cpus':proof['request']['cpus'],'actual_node':proof['request']['node'],
            'plan_reference':C.P.pin(plan['plan_path']),'startup_proof_reference':C.P.pin(plan['startup_proof_path']),
            'fixture_gate':gate,'checkpoint_reference':latest,'held':held,'errors':errors,'resource_soft_stop':I.stop_requested(),
            **{k:state[k] for k in ('prefix_reference','coverage_reference','geometry_reference','eligibility_reference','population_reference','typed_reader_config_reference','numeric_repetitions','r674_report_reference')},
            'independent_numeric_replay_equal':len(state['numeric_repetitions'])==2,'one_actual_parent_no_internal_child_C0':True,
            'original_failed_TIMEOUT_UNKNOWN_and_costs_preserved':True,'new_QM_UFF_calls':0,
            'temporary_complete_old_Sprime_domain_only':True,'pilot_counts':C.PILOT_COUNTS,
            'original_global_population_counts':C.GLOBAL_SOURCE_COUNTS,'not_yet_complete_Sprime_is_pending_availability_not_new_failure':True,
            'full_Common_D2_D3_D4_D5_D6_release':False,'Model_joint_ACK_claimed':False,
            'Pprime_independent_domain_status':'NOT_IMPUTED_FROM_ORDINARY_PM7_OR_SPRIME',
            'Root_actual_C0_limited_acceptance_required':True,'whole_current_output_bytes':I.unique_bytes(root)})
    try:
        prefix_ref,prefix,old,oldproof=I.discover_prefix(plan);state['prefix_reference']=prefix_ref;checkpoint()
        pre,members,diagnostic=V.cohort(prefix,old)
        coverage_ref,coverage,_=V.build(plan,proof,root/'typed_coverage',budget,members)
        state.update(phase='GEOMETRY',coverage_reference=coverage_ref);checkpoint()
        C.need(not coverage['quality_hold_fields'] and not coverage['errors'],'ORIGINAL_ONE_PERCENT_QUALITY_HOLD_NO_LOSS_SCALE_FALLBACK')
        plan=dict(plan,resolved_coverage_catalog_reference=coverage['parts_catalog'])
        base=G.build(plan,proof,root/'ordinary_geometry',budget,prefix,old,oldproof,members)
        geometry=G.metadata_children(plan,proof,root/'actual_input_children',budget,base,diagnostic)
        state['geometry_reference']=geometry['manifest_reference'];checkpoint()
        population=I.save(root/'temporary_population.json',{'schema':'PROVISIONAL_EXISTING_COMPLETE_SPRIME_PILOT_POPULATION_V1',
            'status':'ACTUAL_SAME_PARENT_BOUNDED_GEOMETRY_ROLE_ORDER_CLOSED_PENDING_ROOT_NOT_FINAL_COMMON',
            'pilot_counts':C.PILOT_COUNTS,'seed':20261025,'preselection_reference':prefix['preselection_reference'],
            'actual_prefix_reference':prefix_ref,'actual_geometry_reference':geometry['manifest_reference'],
            'typed_coverage_reference':coverage_ref,'pilot_input_review_reference':plan['pilot_input_review_reference'],
            'ordinary_old_complete_Sprime_mother_only':True,'not_yet_complete_is_pending_availability_not_scientific_exclusion':True,
            'original_population_counts':C.GLOBAL_SOURCE_COUNTS,'full_Common_or_D3_D4_D5_D6_release':False})
        state['population_reference']=population;checkpoint()
        er=E.build(plan,root/'eligibility',coverage,geometry);eligibility=I.load_data(er,8<<20)
        state.update(phase='STATISTICS',eligibility_reference=eligibility['eligibility_reference']);checkpoint()
        cfg=copy.deepcopy(plan);cfg.update(mode='bounded_pilot55k',coverage_reference=coverage_ref,
            eligibility_reference=state['eligibility_reference'],input_release_reference=plan['pilot_input_review_reference'],
            catalog_frame=identity(coverage['parts_catalog']['path']))
        cfg['cache_transitive_output_origins']=[*cfg['cache_transitive_output_origins'],
            {'manifest_reference':coverage['current_parent_typed_origin_reference'],'output_root':str(root/'typed_coverage')}]
        cfg['data_references']=C.unique([*cfg['data_references'],*I.ALLOWED.values()]);I.configure(cfg)
        state['typed_reader_config_reference']=I.save(root/'selected_reader_config.DATA.json',cfg);checkpoint()
        groups=C.logical(I.load_data(plan['logical_group_plan_reference'],2<<20)['groups']);statsroot=root/'statistics';statsroot.mkdir()
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=T.pool_initialize,initargs=(barrier,)) as pool:
            while len(state['numeric_repetitions'])<2:
                numeric=state['numeric_state']
                while numeric['route_index']<len(ROUTES):
                    if I.stop_requested():return finish('DAY_DURABLE_PARTIAL_PENDING_EXPLICIT_ROOT_CONTINUATION')
                    budget.check();state['pass_number']+=1;target=statsroot/('pass_%04d'%state['pass_number']);target.mkdir()
                    scfg=copy.deepcopy(cfg);scfg.update(statistics_purpose=ROUTES[numeric['route_index']],
                        query_stage_reference=numeric['query_reference'],element_models_reference=numeric['element_models_reference'],
                        exact_tail_reference=numeric['exact_tail_reference'],resume_group_reports=numeric['pending_group_reports'],
                        statistics_stage_cap_bytes=plan['whole_output_cap_bytes']-I.unique_bytes(root),config_path=str(target/'config.json'))
                    scfg['data_references']=C.unique([*scfg['data_references'],*I.ALLOWED.values()]);I.save(target/'config.json',scfg)
                    def progress(refs,group_errors):
                        numeric['pending_group_reports']=refs;numeric['pending_group_errors']=group_errors;checkpoint()
                    T.PROGRESS_CALLBACK=progress
                    try:T.execute(scfg,proof,target,gate,pool)
                    except T.DayDrain:return finish('DAY_DURABLE_PARTIAL_PENDING_EXPLICIT_ROOT_CONTINUATION')
                    finally:T.PROGRESS_CALLBACK=None
                    result=I.load(target/'manifest.json');next_route(numeric,result);checkpoint()
                values=canonical_numeric(numeric);nr=I.save(root/('numeric_repetition_%d.json'%len(state['numeric_repetitions'])),values)
                state['numeric_repetitions'].append(nr);checkpoint()
                if len(state['numeric_repetitions'])==1:state['numeric_state']=numeric_state();checkpoint()
                else:C.need(K_bytes(I.load_data(state['numeric_repetitions'][0],256<<20))==K_bytes(values),'INDEPENDENT_PROVISIONAL_NUMERIC_REPLAY_EXACT_NO_TOLERANCE')
        state['phase']='LOSS_ELIGIBILITY_AND_ORIGINAL_RHO';checkpoint();auditroot=root/'loss_and_size';auditroot.mkdir()
        plan=dict(plan,resolved_numeric_reference=state['numeric_repetitions'][0]);cfg['data_references']=C.unique([*cfg['data_references'],*I.ALLOWED.values()]);I.configure(cfg)
        state['r674_report_reference']=L.audit(plan,cfg,groups,geometry,population,values,auditroot);state['phase']='COMPLETE';checkpoint()
        return finish('PROVISIONAL55K_GEOMETRY_D5_ANTI_JOIN_AND_TRAIN_D4_STATISTICS_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL')
    except BaseException as exc:
        if isinstance(exc,ValueError) and str(exc).startswith('SOFT_RESOURCE_STOP_') and I.stop_requested():
            state['resource_drain_note']={'error':str(exc),'durable_parts_retained':True,'incomplete_phase_not_accepted':True}
            return finish('DAY_DURABLE_PARTIAL_PENDING_EXPLICIT_ROOT_CONTINUATION')
        errors.append({'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
        finish('HOLD_PARTIAL_EVIDENCE_NO_AUTORETRY_OR_SOURCE_FAILURE_TO_LOSS_FALLBACK',held=True);raise

def K_bytes(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);parser.add_argument('--startup-proof',required=True);args=parser.parse_args()
    plan=C.plan(C.meta(C.P.pin(args.plan)));plan=dict(plan,plan_path=args.plan,startup_proof_path=args.startup_proof)
    proof=require_startup(args.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=plan['scope_parameters'],expected_kind='analysis',
        expected_source=Path(__file__),expected_execution_argv=[C.PY,'-B','-m',C.MODULE,'--plan',args.plan,'--startup-proof',args.startup_proof],
        required_references=[C.P.pin(args.plan),*plan['source_references']])
    C.need(proof['request']['cpus']==16 and proof['request']['node']==plan['node'] and proof['request']['wall_seconds']==86400
        and proof['request']['estimated_peak_output_bytes']==plan['whole_output_cap_bytes'] and proof['request']['pilot']is False
        and proof['request']['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and {r['path']:r for r in proof['request']['data_references']}=={r['path']:r for r in plan['data_references']},'TRUE_GENERIC16_DAY_NO_MEM_EXACT_DATA')
    C.need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'SINGLE_THREAD_PER_WORKER_LIBRARIES')
    I.configure(plan);root=I.new_root(plan['output_directory']);budget=None
    try:
        gate=fixtures(root);I.configure(plan);budget=I.Budget(plan,proof,root);budget.check(force=True)
        result=execute(plan,proof,root,gate,budget);receipt=I.load_data(result,8<<20)
        return 1 if receipt['held'] else 0
    except BaseException as exc:
        if not (root/'failure.json').exists():I.save(root/'failure.json',{'schema':'EXISTING_SPRIME_PILOT_FAILURE_V1','error':repr(exc),'traceback':traceback.format_exc(),'new_QM_UFF_calls':0,'no_old_source_or_book_changed':True})
        raise
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':raise SystemExit(main())
