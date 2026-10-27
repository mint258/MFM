"""One actual day: remaining numeric cache, full coverage and exact TRAIN passes."""
import argparse,concurrent.futures as cf,copy,io,json,multiprocessing as mp,os,subprocess,sys,time,traceback,unittest
from pathlib import Path
from . import contract as C,io as I,lineage as L,project as P,coverage as V,statistics as T
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import runtime as OLD
from workflows.data_v1_final.execution.cpu_analysis_day_v1.runtime import require_startup
ROUTES=('element_reference','normalization_quantiles','normalization_moments','diagnostic_median_MAD')

def next_route(index,result):
    purpose=ROUTES[index];C.need(result['statistics_purpose']==purpose,'EXACT_DAY_ROUTE_RESULT')
    if result['next_query_stage'] is not None:return index,result['next_query_stage']
    key={'element_reference':'element_reference_models_reference','normalization_quantiles':'exact_tail_reference',
         'normalization_moments':'winsorized_statistics_reference','diagnostic_median_MAD':'diagnostic_median_MAD_reference'}[purpose]
    C.need(result[key] is not None,'NO_ADVANCE_ON_UNRESOLVED_SOURCE_TRAIN_PHASE');return index+1,None

def fixtures(root):
    from . import test_boundaries,source_inverse
    from workflows.data_v1_final.execution.cpu_analysis_day_v1 import test_v1
    original=OLD.fixtures(root)
    transcript=io.StringIO();suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (test_boundaries.Boundaries,test_v1.Boundaries)])
    C.need(suite.countTestCases()==6,'SIX_ONCE_DAY_AND_RESOURCE_BOUNDARIES_IN_PARENT');r=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
    ref=I.save(root/'day_fixture_gate.json',{'status':'PASS' if r.wasSuccessful() and r.testsRun==6 and not r.skipped else 'FAIL_NO_DATA',
      'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'transcript':transcript.getvalue(),'original_compact3_reference':original,
      'inverse':source_inverse.proof(),'scientific_DATA_read':False});C.need(r.wasSuccessful() and r.testsRun==6 and not r.skipped,'DAY_SOURCE_BOUNDARIES_FAIL_BEFORE_DATA');return ref

def repository_check(plan,root):
    manifest=C.meta(plan['native_git_assets_manifest_reference']);assets=[]
    for row in manifest['files']:
        I.require(row['origin_reference']);assets.append(row['origin_reference'])
    wrapper=I.require(plan['native_git_wrapper_reference']);env={**os.environ,'PATH':str(wrapper.parent)+os.pathsep+os.environ.get('PATH','')}
    version=subprocess.run([str(wrapper),'--version'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,env=env)
    C.need(version.returncode==0 and version.stdout.strip()=='git version 2.39.3','EXACT_ORIGINAL_NATIVE_GIT_ACTUAL_CPU')
    output=root/'repository_check.json';argv=[C.A.PY,'-B',str(C.REPO/'tools/check_repository.py'),'--root',str(C.REPO),'--output',str(output)]
    with (root/'repository_check.stdout').open('xb') as out,(root/'repository_check.stderr').open('xb') as err:
        r=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err,cwd=C.REPO,env=env,timeout=600)
    report=I.load(output);C.need(r.returncode==0 and report['status']=='PASS' and report['export_verification_required'] is False,'WHOLE_CURRENT_REPOSITORY_ORIGINAL_CHECKER_FAIL_NO_SCIENTIFIC_DATA')
    return I.save(root/'repository_check_actual.json',{'status':'PASS','argv':argv,'returncode':r.returncode,'result_reference':I.pin(output),
      'software_assets_whole_SHA_CPU_verified':assets,'wrapper_reference':plan['native_git_wrapper_reference'],'actual_git_version':version.stdout.strip(),
      'scientific_DATA_read':False,'server_sources_verified_is_frozen_source_matches_not_unit_tests':True})

def checked_state(state,plan,roots):
    allowed={r['path']:r for r in plan['data_references']+plan['source_references']}
    def visit(v):
        if isinstance(v,dict):
            if {'path','bytes','sha256'}<=set(v):
                C.reference(v);p=Path(v['path']);C.need(allowed.get(v['path'])==v or any(root in p.parents for root in roots),'ONLY_REGISTERED_ACTUAL_OUTPUT_TRANSITIVE_STATE_DATA')
            else:
                for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(state);C.need(state['schema']=='COMPACT_NUMERIC_DAY_CHECKPOINT_V1' and 0<=state['route_index']<=len(ROUTES),'EXACT_FINITE_DAY_CHECKPOINT_SCHEMA');return state

def execute(plan,proof,root,gate,check,budget):
    cfg=I.load(I.require(plan['scientific_config_reference']));cfg['workers']=plan['requested_cpus'];book=C.meta(cfg['source_inventory_reference']);files=book['files']
    L.bind(proof,C.A.Q.pin(plan['plan_path']),root,cfg);projections=[];registered=[];state={'schema':'COMPACT_NUMERIC_DAY_CHECKPOINT_V1','route_index':0,
      'coverage_reference':None,'element_models_reference':None,'exact_tail_reference':None,'query_reference':None,'pending_group_reports':[],
      'pending_group_errors':[],'completed_statistics':[],'pass_number':0}
    roots=[root]
    for parent in plan['previous_day_parents']:
        row=C.actual_day(parent);oldroot=Path(parent['manifest']['path']).parent;roots.append(oldroot)
        for ref in row['projection_outputs']:registered.append(L.register(ref,prior_root=oldroot))
        state=checked_state(I.load_data(row['checkpoint_reference'],512<<20),plan,roots)
    history=[*plan['batch_history'],*registered];cursor={}
    for parent in history:
        m,_=L.actual(parent);cursor=C.advance(files,cursor,m['closed_physical_intervals'])
    sequence=0;latest=None;held=False;errors=[]
    def checkpoint():
        nonlocal sequence,latest
        sequence+=1;latest=I.save(root/('checkpoint_%06d.json'%sequence),state);return latest
    checkpoint()
    def finish(status):
        for ref in plan['source_references']:I.require(ref)
        used=I.unique_bytes(root);C.need(used+(64<<20)<=plan['whole_output_cap_bytes'],'WHOLE_DAY_WITH_RESOURCE_SIDECAR_CAP')
        checkpoint();m={'schema':'COMPACT_NUMERIC_DAY_PARENT_RECEIPT_V1','status':status,'job_id':str(proof['job_id']),
          'plan_reference':C.A.Q.pin(plan['plan_path']),'fixture_gate':gate,'repository_check_actual_reference':check,'checkpoint_reference':latest,
          'projection_outputs':projections,'closed_physical_cursors':cursor,'held':held,'errors':errors,'quality_hold_fields':[],
          'UNKNOWN_promoted':False,'old1904_state':'TIMEOUT','old_reserved_unknown_and_all_costs_retained':True,
          'single_actual_parent_no_fake_stage_job_or_C0':True,'actual_cpus':proof['request']['cpus'],'execution_mode':plan['execution_mode'],'resource_stop':I.stop_requested(),
          'new_QM_UFF_calls':0,'final_Common_D4':False,'D3_D4_frozen':False,'normalization_completed':False,
          'native_unit_sign_frame_policy_or_Pprime_released':False,'charged_current_output_bytes_including_observer_reserve':used+(64<<20)}
        I.save(root/'manifest.json',m);return 1 if held else 0
    if not state['coverage_reference'] and any(cursor.get(str(s['file_id']),0)<s['rows'] for s in files):
        if I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
        target=root/'projection';target.mkdir();selector=I.save(root/'current_selector.json',{'sources':[{'file_id':s['file_id'],'physical_row_lo':cursor.get(str(s['file_id']),0),
          'physical_row_hi':s['rows']} for s in sorted(files,key=lambda s:s['file_id']) if cursor.get(str(s['file_id']),0)<s['rows']]})
        pcfg=copy.deepcopy(cfg);pcfg.update(selector_reference=selector,whole_output_cap_bytes=plan['projection_cap_bytes'],config_path=str(root/'projection_config.json'))
        I.save(pcfg['config_path'],pcfg)
        try:P.execute(pcfg,proof,None,target,gate,budget)
        except BaseException as exc:
            if not (target/'manifest.json').exists():raise
            m=I.load(target/'manifest.json')
            if m['errors'] or m['quality_hold_fields'] or m['unpublished_tickets']:raise
            if not m['verified_window_receipts'] and I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            raise
        ref=I.pin(target/'manifest.json');registered.append(L.register(ref));projections.append(ref);history=[*plan['batch_history'],*registered]
        m=I.load(I.require(ref));cursor=C.advance(files,cursor,m['closed_physical_intervals']);budget.attach_ledger(None);checkpoint()
        if any(cursor.get(str(s['file_id']),0)<s['rows'] for s in files):return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
    if not state['coverage_reference']:
        if I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
        target=root/'coverage';target.mkdir();vcfg=copy.deepcopy(cfg);vcfg.update(batch_history=history,whole_output_cap_bytes=plan['coverage_cap_bytes'],config_path=str(root/'coverage_config.json'))
        I.save(vcfg['config_path'],vcfg)
        try:V.execute(vcfg,proof,target,gate)
        except BaseException as exc:
            if str(exc)=='DAY_RESOURCE_STOP_COVERAGE_NO_ACCEPTANCE' and I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            raise
        state['coverage_reference']=I.pin(target/'manifest.json');checkpoint()
    if plan['execution_mode']=='PROJECT_AND_COVERAGE_ONLY':return finish('EXACT_ALL_SOURCE_NUMERIC_CACHE_COMPLETE_FINAL_COMMON_STATISTICS_PENDING')
    statsroot=root/'statistics';statsroot.mkdir();ctx=mp.get_context('spawn');barrier=ctx.Barrier(cfg['workers'])
    with cf.ProcessPoolExecutor(max_workers=cfg['workers'],mp_context=ctx,initializer=T.pool_initialize,initargs=(barrier,)) as pool:
        while state['route_index']<len(ROUTES):
            if I.stop_requested():return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            used=I.unique_bytes(statsroot);remaining=plan['statistics_cap_bytes']-used
            if remaining<max(256<<20,cfg['workers']*(130<<20)):
                I.R.mark_stop('DAY_STATISTICS_OUTPUT_NEXT_WAVE_CAP',{'remaining':remaining});return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            state['pass_number']+=1;target=statsroot/('pass_%04d'%state['pass_number']);target.mkdir()
            scfg=copy.deepcopy(cfg);scfg.update(coverage_reference=state['coverage_reference'],statistics_purpose=ROUTES[state['route_index']],
              query_stage_reference=state['query_reference'],element_models_reference=state['element_models_reference'],exact_tail_reference=state['exact_tail_reference'],
              resume_group_reports=state['pending_group_reports'],whole_output_cap_bytes=remaining,config_path=str(target/'config.json'))
            I.save(scfg['config_path'],scfg)
            def progress(refs,group_errors):
                state['pending_group_reports']=refs;state['pending_group_errors']=group_errors;checkpoint()
            T.PROGRESS_CALLBACK=progress
            try:T.execute(scfg,proof,target,gate,pool)
            except T.DayDrain:return finish('DAY_CLEAN_CHECKPOINTS_PENDING')
            finally:T.PROGRESS_CALLBACK=None
            result=I.load(target/'manifest.json');state['completed_statistics'].append(I.pin(target/'manifest.json'))
            state['route_index'],state['query_reference']=next_route(state['route_index'],result)
            if result['statistics_purpose']=='element_reference':state['element_models_reference']=result['element_reference_models_reference']
            if result['statistics_purpose']=='normalization_quantiles' and result['exact_tail_reference']:state['exact_tail_reference']=result['exact_tail_reference']
            state['pending_group_reports']=[];state['pending_group_errors']=[];checkpoint()
    return finish('SOURCE_TRAIN_DESCRIPTIVE_COMPLETE_NOT_D4')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.plan(C.meta(C.A.Q.pin(a.plan)));raw=C.A.Q.load(a.startup_proof);req=raw['request']
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=C.KEY,expected_scope_parameters=plan['scope_parameters'],
      expected_execution_argv=[C.A.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof],expected_source=Path(__file__),required_references=[C.A.Q.pin(a.plan),*plan['source_references']])
    C.need(req['cpus']==plan['requested_cpus'] and req['estimated_peak_output_bytes']>=plan['whole_output_cap_bytes']
      and {r['path']:r for r in req['data_references']}=={r['path']:r for r in plan['data_references']},'EXACT_REAL_PARENT_CPUS_CAP_DECLARED_DATA')
    C.need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'SINGLE_THREAD_LIBRARIES_INSIDE_ACTUAL_CPU_ALLOCATION')
    root=I.new_root(plan['output_directory']);budget=None
    try:
        gate=fixtures(root);check=repository_check(plan,root);plan['plan_path']=a.plan
        budget=I.Budget(plan,proof,root);return execute(plan,proof,root,gate,check,budget)
    except BaseException as exc:
        I.failed(root,exc);raise
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':raise SystemExit(main())
