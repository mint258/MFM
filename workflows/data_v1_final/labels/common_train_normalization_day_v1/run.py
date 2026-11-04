"""One real analysis parent, fixed logical math, raw audit and independent replay."""
import argparse,concurrent.futures as cf,copy,io,json,multiprocessing as mp,os,sys,traceback,unittest
from pathlib import Path
from . import contract as C,io as I,bindings as B,eligibility as E,statistics as T,audit as U
from workflows.data_v1_final.execution.cpu_analysis_day_v2.runtime import require_startup
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity
ROUTES=('element_reference','normalization_quantiles','normalization_moments','diagnostic_median_MAD')

def fixtures(root):
    from . import test_boundaries,source_inverse
    from workflows.data_v1_final.execution.cpu_analysis_day_v2 import test_v1
    stream=io.StringIO();suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(x) for x in (test_boundaries.Boundaries,test_v1.Boundaries)])
    C.need(suite.countTestCases()==6,'D4_AND_SHARED_V2_SIX_ONCE_BOUNDARIES_IN_SAME_PARENT')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    payload={'status':'PASS' if result.wasSuccessful() and result.testsRun==6 and not result.skipped else 'FAIL_NO_DATA',
      'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'transcript':stream.getvalue(),
      'original_objects':B.verify(),'source_inverse':source_inverse.proof(),'scientific_DATA_read':False}
    ref=I.save(Path(root)/'fixture_gate.json',payload)
    C.need(payload['status']=='PASS','D4_SOURCE_BOUNDARIES_FAIL_BEFORE_DATA');return ref

def references(value):
    if isinstance(value,dict):
        if {'path','bytes','sha256'}<=set(value):yield C.reference(value,source=value.get('bytes')==0)
        else:
            for v in value.values():yield from references(v)
    elif isinstance(value,list):
        for v in value:yield from references(v)

def empty_state():
    return {'schema':'COMMON_TRAIN_NORMALIZATION_DAY_CHECKPOINT_V1','eligibility_manifest_reference':None,
      'eligibility_reference':None,'repetition':0,'route_index':0,'pass_number':0,'query_reference':None,
      'element_models_reference':None,'exact_tail_reference':None,'winsorized_statistics_reference':None,
      'diagnostic_median_MAD_reference':None,'pending_group_reports':[],'pending_group_errors':[],
      'numeric_repetitions':[],'audit_group_reports':[],'audit_reference':None}

def next_route(state,result):
    purpose=ROUTES[state['route_index']];C.need(result['statistics_purpose']==purpose,'EXACT_STATISTIC_PHASE')
    if result['next_query_stage'] is not None:state['query_reference']=result['next_query_stage'];return
    key={'element_reference':'element_reference_models_reference','normalization_quantiles':'exact_tail_reference',
      'normalization_moments':'winsorized_statistics_reference','diagnostic_median_MAD':'diagnostic_median_MAD_reference'}[purpose]
    C.need(result[key] is not None,'NO_PHASE_ADVANCE_ON_MISSING_NUMERIC_OUTPUT')
    target='element_models_reference' if purpose=='element_reference' else key
    state[target]=result[key];state['route_index']+=1;state['query_reference']=None

def canonical_numeric(state):
    """Compare outputs, not filenames or fresh timing. No numerical rounding/tolerance."""
    models=I.load_data(state['element_models_reference']);tail=I.load_data(state['exact_tail_reference'])
    moments=I.load_data(state['winsorized_statistics_reference']);diag=I.load_data(state['diagnostic_median_MAD_reference'])
    return {'models':models,'exact_tails':{'catalog':tail['catalog'],'quantiles':tail['quantiles']},
      'winsorized_component_and_invariant_audit':moments,'diagnostic_median_MAD':diag['fields']}

def execute(plan,proof,root,gate,budget):
    cfg=copy.deepcopy(plan);coverage=I.load_data(plan['coverage_reference'],8<<20)
    release=C.release(C.meta(plan['input_release_reference']));cacheproof=C.actual(release['actual_parents']['full_cache'])
    C.need(str(coverage['job_id'])==str(cacheproof['job_id']),'FULL_CACHE_COVERAGE_FROM_THE_REAL_ACCEPTED_ACTUAL_PARENT')
    C.need(coverage['schema']=='COMPACT_NUMERIC_ORIGINAL_SOURCE_COVERAGE_V1' and coverage['status']=='EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS'
      and coverage['mode']=='full' and coverage['records']==11231854 and coverage['task_rows']==157245956 and coverage['base_rows']==11231854
      and coverage['molecules']==1220466 and coverage['all14task_and_base_exact_once'] is True
      and coverage['quality_hold_fields']==[] and coverage['errors']==[],'REAL_FULL_14_TASK_CACHE_NO_PARTIAL_OR_PROVISIONAL_ACCEPTANCE')
    for k in ('canonical_index','field_map_reference','logical_group_plan_reference','source_inventory_reference'):
        C.need(coverage[k]==plan[k],'CACHE_EXACT_ORIGINAL_PARENT:'+k)
    catalog=I.require(coverage['parts_catalog']);cfg['catalog_frame']=identity(catalog);I.require(plan['canonical_index'])
    groups=C.logical(I.load_data(plan['logical_group_plan_reference'],2<<20)['groups']);state=empty_state()
    if plan['previous_parent'] is not None:
        previous=C.meta(plan['previous_parent']['manifest']);state=I.load_data(previous['checkpoint_reference'],512<<20)
        C.need(state['schema']=='COMMON_TRAIN_NORMALIZATION_DAY_CHECKPOINT_V1','REAL_PRIOR_C0_STATE_SCHEMA')
        for ref in references(state):
            if ref['path'] not in I.ALLOWED:I.register_prior(ref)
    sequence=0;latest=None;errors=[];held=False;quality=[]
    def checkpoint():
        nonlocal sequence,latest
        sequence+=1;latest=I.save(root/('checkpoint_%06d.json'%sequence),state);return latest
    def finish(status):
        checkpoint()
        for ref in plan['source_references']:I.require(ref)
        returncode=1 if held else 0
        I.save(root/'manifest.json',{'schema':'COMMON_TRAIN_NORMALIZATION_DAY_RECEIPT_V1','status':status,
          'job_id':str(proof['job_id']),'actual_cpus':proof['request']['cpus'],'plan_reference':C.A.Q.pin(plan['plan_path']),
          'input_release_reference':plan['input_release_reference'],'fixture_gate':gate,'checkpoint_reference':latest,
          'held':held,'errors':errors,'quality_hold_fields':quality,'resource_stop':I.stop_requested(),
          'eligibility_manifest_reference':state['eligibility_manifest_reference'],'numeric_repetition_references':state['numeric_repetitions'],
          'all_population_audit_reference':state['audit_reference'],'independent_full_numeric_replay_equal':state['repetition']==2,
          'one_actual_parent_no_internal_child_C0':True,'new_QM_UFF_calls':0,'old_costs_masks_values_and_UNKNOWN_preserved':True,
          'numeric_component_stats_not_joint_physical_head_normalizer':True,'physical_unit_sign_basis_axes_accepted':False,
          'Pprime_status':'PENDING_REAL_INDEPENDENT_FORMAL_SOURCE','D4_published':False,'joint_Model_signoff':False,
          'whole_current_output_bytes':I.unique_bytes(root),'no_automatic_retry_or_threshold_waiver':True})
        return returncode
    checkpoint()
    if state['eligibility_reference'] is None:
        if I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
        try:er=E.build(plan,root/'eligibility')
        except ValueError as e:
            if str(e).startswith('SOFT_RESOURCE_STOP_') and I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            raise
        em=I.load_data(er,8<<20)
        state['eligibility_manifest_reference']=er;state['eligibility_reference']=em['eligibility_reference'];checkpoint()
    cfg['eligibility_reference']=state['eligibility_reference'];I.require(cfg['eligibility_reference'])
    # Worker processes receive only actual CPU-observed prior references, bound to accepted C0 roots.
    cfg['data_references']=C.unique([*cfg['data_references'],*references(state)])
    ctx=mp.get_context('spawn');barrier=ctx.Barrier(plan['requested_cpus']);statsroot=root/'statistics';statsroot.mkdir()
    with cf.ProcessPoolExecutor(max_workers=plan['requested_cpus'],mp_context=ctx,initializer=T.pool_initialize,initargs=(barrier,)) as pool:
        while state['repetition']<2:
            while state['route_index']<len(ROUTES):
                if I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
                used=I.unique_bytes(statsroot);remaining=plan['statistics_cap_bytes']-used
                if remaining<plan['requested_cpus']*(130<<20)+(256<<20):
                    I.R.mark_stop('COMMON_TRAIN_NEXT_EXACT_STATISTIC_WAVE_OUTPUT_CAP',{'remaining':remaining});return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
                state['pass_number']+=1;target=statsroot/('pass_%04d'%state['pass_number']);target.mkdir()
                scfg=copy.deepcopy(cfg);scfg.update(statistics_purpose=ROUTES[state['route_index']],query_stage_reference=state['query_reference'],
                  element_models_reference=state['element_models_reference'],exact_tail_reference=state['exact_tail_reference'],
                  resume_group_reports=state['pending_group_reports'],whole_output_cap_bytes=plan['whole_output_cap_bytes'],statistics_stage_cap_bytes=remaining,config_path=str(target/'config.json'))
                scfg['data_references']=C.unique([*scfg['data_references'],*references(state)])
                I.save(target/'config.json',scfg)
                def progress(refs,group_errors):
                    state['pending_group_reports']=refs;state['pending_group_errors']=group_errors;checkpoint()
                T.PROGRESS_CALLBACK=progress
                try:T.execute(scfg,proof,target,gate,pool)
                except T.DayDrain:return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
                finally:T.PROGRESS_CALLBACK=None
                result=I.load(target/'manifest.json');next_route(state,result);state['pending_group_reports']=[];state['pending_group_errors']=[];checkpoint()
            values=canonical_numeric(state);nr=I.save(root/('numeric_repetition_%d.json'%state['repetition']),values)
            state['numeric_repetitions'].append(nr);state['repetition']+=1;checkpoint()
            if state['repetition']==1:
                # Independent new model/tail/moment/median/MAD states: no reuse of fitted numbers.
                state.update(route_index=0,query_reference=None,element_models_reference=None,exact_tail_reference=None,
                  winsorized_statistics_reference=None,diagnostic_median_MAD_reference=None);checkpoint()
            else:
                first=I.load_data(state['numeric_repetitions'][0],256<<20)
                C.need(K_bytes(first)==K_bytes(values),'INDEPENDENT_FULL_NUMERIC_REPLAY_BYTE_DIFFERENCE_NO_TOLERANCE')
        if state['audit_reference'] is None:
            if I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            auditroot=root/'audit';auditroot.mkdir();cfg.update(audit_root=str(auditroot),diagnostic_median_MAD_reference=state['diagnostic_median_MAD_reference'])
            cfg['data_references']=C.unique([*cfg['data_references'],*references(state)])
            saved={}
            for r in state['audit_group_reports']:
                m=I.load_data(r,16<<20);C.need(m['group_index'] not in saved,'NO_DUPLICATE_PRIOR_AUDIT_GROUP');saved[m['group_index']]=r
            todo=iter(g for g in groups if g['group_index'] not in saved);pending={};audit_errors=[]
            def fill():
                if I.stop_requested():return
                while len(pending)<plan['requested_cpus']:
                    if I.unique_bytes(auditroot)+(len(pending)+1)*cfg['audit_group_cap_bytes']>plan['audit_cap_bytes']:
                        if not pending:I.R.mark_stop('COMMON_TRAIN_AUDIT_COMPONENT_CAP_NATURAL_DRAIN',{})
                        return
                    try:g=next(todo)
                    except StopIteration:return
                    pending[pool.submit(U.day_group,(cfg,g))]=g['group_index']
            fill()
            while pending:
                done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for f in done:
                    k=pending.pop(f)
                    try:saved[k]=f.result()
                    except BaseException as e:audit_errors.append({'group_index':k,'error_type':type(e).__name__,'message':str(e)[:500]})
                    state['audit_group_reports']=[saved[k] for k in sorted(saved)];checkpoint()
                fill()
            if audit_errors:
                if all(e['message'].startswith('SOFT_RESOURCE_STOP_') for e in audit_errors):return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
                errors.extend(audit_errors);held=True;return finish('AUDIT_ERROR_HOLD_NO_RETRY')
            if len(saved)!=171:return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            state['audit_reference']=U.reduce([saved[k] for k in range(171)],auditroot,I.load_data(plan['field_map_reference'],2<<20),plan['field_scope'],coverage['field_stats']);ar=I.load_data(state['audit_reference'],16<<20)
            quality=ar['quality_hold_fields'];held=bool(quality);checkpoint()
            if held:return finish('QUALITY_STOP_REPORT_AWAIT_USER')
    return finish('COMMON_TRAIN_NUMERIC_COMPONENT_STATISTICS_AND_GUIDE1_5_COMPLETE_PENDING_ROOT_AND_JOINT_POLICY')

def K_bytes(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.plan(C.meta(C.A.Q.pin(a.plan)));release=C.release(C.meta(plan['input_release_reference']))
    C.need(plan['field_scope']==release['field_scope'] and plan['authority']==release['authority']
      and plan['coverage_reference']==release['coverage_reference'],'EXACT_RELEASE_ROLE_GEOMETRY_AND_FIELD_APPLICABILITY_BINDING')
    proof=require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=plan['scope_parameters'],expected_kind='analysis',expected_source=Path(__file__),
      expected_execution_argv=[C.A.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof],required_references=[C.A.Q.pin(a.plan),*plan['source_references']])
    req=proof['request'];C.need(req['cpus']==plan['requested_cpus'] and req['estimated_peak_output_bytes']>=plan['whole_output_cap_bytes']
      and {r['path']:r for r in req['data_references']}=={r['path']:r for r in plan['data_references']},'EXACT_REAL_ALLOCATION_CAP_AND_DECLARED_DATA')
    C.need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ORIGINAL_SINGLE_THREAD_WORKER_LIBRARIES')
    I.configure(plan);root=I.new_root(plan['output_directory']);budget=None;plan['plan_path']=a.plan
    try:
        gate=fixtures(root);I.configure(plan);budget=I.Budget(plan,proof,root);return execute(plan,proof,root,gate,budget)
    except BaseException as e:
        I.save(root/'failure.json',{'schema':'COMMON_TRAIN_NORMALIZATION_FAILURE_V1','status':'HOLD_PARTIAL_EVIDENCE_NO_AUTORETRY',
          'error':repr(e),'traceback':traceback.format_exc(),'values_masks_unknown_costs_preserved':True,'D4_published':False});raise
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':raise SystemExit(main())
