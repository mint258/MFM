"""Finite readonly precision/control evidence; no scientific executable or repair."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,io,json,math,os,pathlib,sys,threading,time,traceback,unittest
from workflows.data_v1_final.export.native_body_frame32_v1 import reader as D
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
from . import contract as C,reader as I,precision as P


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries)
    C.need(suite.countTestCases()==3,'EXACT3_NEW_PRECISION_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=C.Q.write_new(out/'source3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
        'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),
        'transcript':stream.getvalue(),'before_DATA_and_resource_observer':True,'synthetic_only':True,'temporary_directories_created':0})
    C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_BEFORE_ANY_BODY')
    return ref


def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    C.need(plan['schema']=='NATIVE_PRECISION384_PLAN_V1' and plan['mode']=='precision'
        and plan['scope_parameters']==C.parameters() and plan['wall_seconds']==C.WALL
        and plan['output_cap_bytes']==C.CAP,'EXACT_FINITE_PRECISION_PLAN')
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    proof=require_startup(proof_path,expected_scope_key=C.SCOPE,expected_scope_parameters=C.parameters(),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',
        required_references=[C.Q.pin(path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    req=proof['request'];C.need(req['cpus']==16 and req['pilot'] is False and req['wall_seconds']==C.WALL
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['estimated_peak_output_bytes']==C.CAP
        and req['data_references']==plan['data_references'] and not req.get('deferred_authority_references'),
        'EXACT16_NO_MEM_FINITE_DECLARED_DATA')
    for ref in plan['source_references']:
        C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'EXACT_SOURCE_CONTEXT_PARENT_PINS')
    result=C.derive(plan);C.need(result[3]==plan['data_references'],'ONLY_ACTUAL_CLOSED1152_DATA')
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_COST_REPORT_CONTINUE')
    return proof,result


def condition_summary(items):
    ok=[r for r in items if r['state']=='OBSERVED_NOT_PHYSICAL_ACCEPTANCE']
    coordinate=[r['_metrics'] for r in ok if r['_metrics'] is not None]
    n=sum(r['components'] for r in coordinate);formulas={}
    for name in sorted({k for r in coordinate for k in r['formula_rounding_observations']}):
        selected=[r['formula_rounding_observations'][name] for r in coordinate if name in r['formula_rounding_observations']]
        formulas[name]={'records':len(selected),'components':sum(r['components'] for r in selected),
            'conditional_interval_contains_zero_components':sum(r['conditional_interval_contains_zero_components'] for r in selected),
            'maximum_conditional_halfwidth_A':max(r['maximum_conditional_halfwidth_A'] for r in selected),
            'minimum_decimal_center_A':min(r['minimum_decimal_center_A'] for r in selected),
            'maximum_decimal_center_A':max(r['maximum_decimal_center_A'] for r in selected),
            'minimum_conditional_lower_A':min(r['minimum_conditional_lower_A'] for r in selected),
            'maximum_conditional_upper_A':max(r['maximum_conditional_upper_A'] for r in selected),
            'display_extrema_are_binary64_only_exact_rational_per_component_retained_in_DATA':True,
            'same_underlying_coordinate_and_printing_mode_proved':False,'physical_or_QC_acceptance':False}
    stats=None
    if n:
        total=math.fsum(r['sum_signed_residual_A'] for r in coordinate)
        squares=math.fsum(r['sum_squared_residual_A2'] for r in coordinate)
        stats={'components':n,'minimum_signed_residual_A':min(r['minimum_signed_residual_A'] for r in coordinate),
            'maximum_signed_residual_A':max(r['maximum_signed_residual_A'] for r in coordinate),
            'maximum_absolute_residual_A':max(r['maximum_absolute_residual_A'] for r in coordinate),
            'component_mean_signed_A':total/n,'component_RMS_A':math.sqrt(squares/n),
            'arithmetic':'original reader binary64 direct subtraction; fixed position order fsum; no fit or adjustment'}
    return {'records':len(items),'completed_keys':len(ok),'held_keys':len(items)-len(ok),
        'geometry_status_counts':dict(collections.Counter(r.get('geometry_state','HOLD') for r in items)),
        'direct_coordinate_records':len(coordinate),'float64_coordinate_exact_records':sum(r['float64_exact'] for r in coordinate),
        'direct_original_reader_residual_statistics':stats,'conditional_printing_formula_observations':formulas,
        'native_coordinate_absence_is_unknown_not_QC_failure':True,'native_units_sign_origin_axes_accepted':False}


def trace_summary(rows):
    qs=[r['_q'] for r in rows if r.get('_q') is not None]
    def exact(r):return P.F(int(r['numerator']),int(r['denominator']))
    values=[exact(r['native_decimal_trace']) for r in qs];hist=collections.Counter(values)
    components=[]
    for i,name in enumerate(P.ORDER):
        v=[P.decimal_token(r['native_tokens'][i]['native_numeric_token'])[0] for r in qs]
        components.append({'component':name,'records':len(v),'minimum_native_decimal':P.rational(min(v)) if v else None,
            'maximum_native_decimal':P.rational(max(v)) if v else None})
    return {'records':len(qs),'component_order':list(P.ORDER),'component_native_decimal_extrema':components,
        'native_decimal_trace_minimum':P.rational(min(values)) if values else None,
        'native_decimal_trace_maximum':P.rational(max(values)) if values else None,
        'native_decimal_trace_histogram':[{'trace':P.rational(v),'records':hist[v]} for v in sorted(hist)],
        'native_decimal_trace_exact_zero_records':sum(v==0 for v in values),'native_decimal_trace_nonzero_records':sum(v!=0 for v in values),
        'all_six_fixed_three_decimal_records':sum(r['all_six_tokens_have_three_fixed_decimals'] for r in qs),
        'within_conditional_f12_3_envelope_records':sum(r['within_conditional_f12_3_trace_envelope'] is True for r in qs),
        'outside_conditional_f12_3_envelope_records':sum(r['within_conditional_f12_3_trace_envelope'] is False for r in qs),
        'unknown_f12_3_lexical_format_records':sum(r['within_conditional_f12_3_trace_envelope'] is None for r in qs),
        'official_f12_3_three_diagonal_nearest_rounding_bound':P.rational(P.F(3,2000)),
        'theoretical_assumptions':'Exactly traceless unrounded tensor and nearest rounding to 0.001; native finite-arithmetic error not bounded',
        'rounding_mode_or_underlying_trace_proved':False,'theoretical_bound_is_authorized_QC':False,
        'original_six_values_masks_and_nonzero_traces_unchanged':True}


def produce(plan,summary,bodyplan,locators,out,check,write):
    barrier=threading.Barrier(16);protocol=C.meta(bodyplan['protocol_reference']);refs=plan['data_references']
    def worker(index):
        barrier.wait(timeout=60);objects=I.originals(index);result=[]
        for row in locators[index::16]:
            check();position=row['position']
            try:
                observed,metrics,q,controls=I.examine(row,refs,check,objects,protocol)
                ref=write(out/('key_%04d.lossless.json'%position),D.scientific_bytes(observed))
                result.append({'position':position,'calc_type':row['calc_type'],'state':'OBSERVED_NOT_PHYSICAL_ACCEPTANCE',
                    'scientific_DATA_reference':ref,'geometry_state':observed['coordinate']['state'],
                    'direct_coordinates_exact':metrics['float64_exact'] if metrics else None,'input_binding_exact':True,
                    '_metrics':metrics,'_q':q,'_control_counts':{'argv_candidates':len(controls['retained_full_process_argv_candidates']),
                        'opaque_command_fields':len(controls['retained_opaque_command_fields']),
                        'control_members':len(controls['retained_control_members']),'preprocessing_fragments':len(controls['retained_preprocessing_text_fragments'])}})
            except Exception as exc:
                ref=write(out/('key_%04d.failure.lossless.json'%position),D.scientific_bytes({'position':position,'key':row['key'],
                    'original_retained_locators':row,'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),
                    'state':'UNKNOWN_HOLD_NOT_SCIENTIFIC_FAILURE','all_old_evidence_retained':True}),failure=True)
                result.append({'position':position,'calc_type':row['calc_type'],'state':'UNKNOWN_HOLD','failure_DATA_reference':ref})
        return {'native_thread_id':threading.get_native_id(),'rows':result}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:reports=list(pool.map(worker,range(16)))
    C.need(len({r['native_thread_id'] for r in reports})==16,'ACTUAL16_READONLY_WORKER_THREADS')
    rows=sorted([r for w in reports for r in w['rows']],key=lambda r:r['position'])
    C.need([r['position'] for r in rows]==list(range(384)),'EXACT384_FIXED_KEY_POSITION_MATRIX')
    per=[];held=sum(r['state']=='UNKNOWN_HOLD' for r in rows)
    for calc in C.S.CALCS:
        items=[r for r in rows if r['calc_type']==calc];C.need(len(items)==32,'EXACT32_PER_CONDITION')
        observed={'condition':calc,**condition_summary(items)}
        if not observed['held_keys']:
            old=next(r for r in summary['per_condition_counts'] if r['condition']==calc)
            C.need(observed['geometry_status_counts']==old['geometry_status_counts']
                and observed['float64_coordinate_exact_records']==old['printed_coordinate_values_float64_exact_records'],
                'ACTUAL3953_GEOMETRY_AVAILABILITY_AND_EXACTNESS_PARITY')
        per.append(observed)
    traces=trace_summary(rows)
    if not held:
        old=next(r for r in summary['per_condition_counts'] if r['condition']=='xtb_singlepoint')
        C.need(traces['records']==32 and traces['native_decimal_trace_exact_zero_records']==old['r674_native_decimal_trace_exactly_zero_records'],
            'ACTUAL3953_ORIGINAL_DECIMAL_TRACE_ZERO_COUNT_PARITY')
    control={k:sum(r.get('_control_counts',{}).get(k,0) for r in rows) for k in ('argv_candidates','opaque_command_fields','control_members','preprocessing_fragments')}
    return {'completed_keys':384-held,'held_keys':held,'per_condition_observations':per,'r674_trace_observations':traces,
        'retained_control_observation_counts':control,'unretained_argv_rc_origin_and_preprocessing':'UNKNOWN_NOT_PROVED_ABSENT',
        'per_key_scientific_DATA_references':[{k:v for k,v in r.items() if not k.startswith('_')} for r in rows],
        'actual_DATA_full_SHA_stable_FD_verified_files':1152 if not held else None,
        'worker_thread_ids':[r['native_thread_id'] for r in reports],
        'old_full_parser_exactness_basis':'actual3953 parent; no complete label parser or engine initialization in this job'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True)
    p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);proof,parents=guard(a.plan,plan,a.startup_proof);summary,bodyplan,locators,_,_=parents
    out=pathlib.Path(plan['output_directory']);allowed=C.ROOT/'artifacts/labels/source_status_v1/native_precision384_v1'
    C.need(out.is_absolute() and allowed in out.parents and not out.exists() and '..' not in out.parts
        and not any(s.is_symlink() for s in (out,*out.parents)),'FRESH_LITERAL_PRECISION_OUTPUT')
    out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for path in (C.S.B.WP5,C.S.B.VECTOR):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    start=time.monotonic();gate=observation=None;error=None;result={};lock=threading.Lock();written=0
    def check():
        R.soft_worker_rss(3<<30)
        if time.monotonic()-start>=C.WALL-300:R.mark_stop('PRECISION384_FINITE_WALL_RESERVE',{'elapsed_seconds':time.monotonic()-start})
        C.need(not R.stop_requested(),'PRECISION384_STOP_NEW_WORK_NATURAL_DRAIN')
    def write(path,data,*,failure=False):
        nonlocal written
        with lock:
            if not failure:check()
            C.need(written+len(data)+C.RESERVE<=C.CAP,'WHOLE_OUTPUT_AND_FAILURE_RESOURCE_DRAIN_RESERVE');written+=len(data)
        return D.bytes_data(path,data)
    try:
        gate=fixtures(out)
        R.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':16<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP})
        check();result=produce(plan,summary,bodyplan,locators,out,check,write);check()
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'ALL_SOURCE_SMALL_PARENT_BYTES_STABLE_AFTER_DATA')
    except BaseException as exc:
        error={'type':type(exc).__name__,'code':'INCOMPLETE_PRECISION384_SEE_RETAINED_FAILURE_DATA'}
        try:write(out/'stage_failure.lossless.json',D.scientific_bytes({'error':str(exc),'traceback':traceback.format_exc()}),failure=True)
        except Exception:pass
    finally:
        if R.MONITOR is not None:
            try:R.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'code':'RESOURCE_CLOSURE_INCOMPLETE'}
    ok=error is None and observation is not None and not R.stop_requested() and result.get('completed_keys')==384 and result.get('held_keys')==0
    report={'schema':'NATIVE_PRECISION384_OBSERVATIONS_V1',
        'status':'COMPLETE384_DIRECT_PRECISION_CONTROL_OBSERVATIONS_PHYSICAL_REVIEW_PENDING' if ok else 'INCOMPLETE_PRECISION384_UNKNOWN_HOLD',
        'mode':'precision','job_id':str(proof['job_id']),'plan_reference':C.Q.pin(a.plan),
        'original_summary_closure_references':plan['summary_closure_references'],'fixtures3_reference':gate,
        'resource_observation_reference':observation,'error':error,**result,
        'native_physical_acceptance':False,'native_units_sign_origin_axes_accepted':False,'D1_jointly_frozen':False,
        'theoretical_printing_envelope_is_authorized_QC':False,'full20k_completed':False,'new_QM_UFF_calls':0,
        'original_DATA_masks_tolerances_or_sources_modified':False,'fit_centering_rotation_permutation_or_repair':False,
        'continuous_physical_memory_observer_not_continuous_scheduler_quota_renewal':True,'elapsed_seconds':time.monotonic()-start}
    C.Q.write_new(out/'manifest.json',report)
    C.need(sum(p.stat().st_size for p in out.rglob('*') if p.is_file())+(16<<20)<=C.CAP,'ACTUAL_WHOLE_PRECISION_OUTPUT_CAP')
    print(json.dumps({'status':report['status'],'manifest':str(out/'manifest.json'),'new_QM_UFF_calls':0}))
    return 0 if ok else 3
if __name__=='__main__':raise SystemExit(main())
