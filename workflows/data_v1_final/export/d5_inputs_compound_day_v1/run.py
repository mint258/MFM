"""One actual day Parent: prepare, bounded bases, original readback, inputs, D5."""
from __future__ import annotations
import argparse,io,json,os,pathlib,time,traceback,unittest
from workflows.data_v1_final.export.d5_inputs_builder_v1 import io as I
from . import contract as C,resources as R,prepare as P,executor as E,verify as V,canonical_children as W


def fixtures(out):
    from .test_boundaries import Boundaries
    from workflows.data_v1_final.export.d5_inputs_builder_v1.test_v1 import Boundaries as OldInputs
    from workflows.data_v1_final.export.d5_materialize_cpu_v1.test_boundaries import Boundaries as OldLists
    from workflows.data_v1_final.execution.cpu_analysis_day_v2.test_v1 import Boundaries as Resource
    suites=[]
    for cls in (Boundaries,OldInputs,OldLists,Resource):
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(cls);C.need(suite.countTestCases()==3,'EXACT3_PER_UNCHANGED_PREFLIGHT_GROUP');suites.append(suite)
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(suites))
    from .source_inverse import proof
    inverse=proof() if r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses) else None
    ref=C.Q.write_new(out/'source12.json',{'schema':'D5_COMPOUND_SOURCE12_V1','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
        'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),
        'source_inverse':inverse,'transcript':stream.getvalue(),'before_DATA_and_resource_observer':True})
    C.need(r.testsRun==12 and r.wasSuccessful() and inverse is not None and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'ACTUAL_ALL12_AND_INVERSE_BEFORE_DATA')
    return ref


def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_analysis_day_v2.runtime import require_startup
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    required=[C.Q.pin(path),*(plan[k] for k in ('resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference','cost_decision_reference'))]
    proof=require_startup(proof_path,expected_scope_key='d5_inputs_compound_day_v1',expected_scope_parameters=C.parameters(plan),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',required_references=required)
    req=proof['request'];C.need(req['cpus']==plan['cpus'] and req['node']==plan['node'] and req['wall_seconds']==86400
        and req['estimated_peak_output_bytes']==plan['output_cap_bytes'] and req['data_references']==plan['data_references']
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['pilot'] is False,'REAL_ALLOCATED_ANALYSIS_DAY_NOT_OLD16_SCOPE')
    for ref in plan['source_references']:C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'FROZEN_SOURCE_AND_SMALL_AUTHORITY_PINS')
    parents=C.inputs(plan);C.need(parents[3]==plan['data_references'],'EXACT_ROOT_DECLARED_DATA_AND_TRANSITIVE_PREPARED_LOCATORS')
    return proof,parents


def append(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    C.need(len(raw)<=I.ROW_CAP,'COMPLETE_PARTITION_CATALOGUE_ROW_NO_TRUNCATION')
    with path.open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=pathlib.Path,required=True)
    parser.add_argument('--startup-proof',type=pathlib.Path,required=True);a=parser.parse_args();plan=C.Q.load(a.plan)
    proof,(common,formal,hof,_,_)=guard(a.plan,plan,a.startup_proof)
    out=R.literal(plan['output_directory']);C.need(C.OUTPUT in out.parents and not out.exists(),'FRESH_COMPOUND_OUTPUT_OLD_PREFIX_READONLY')
    out.mkdir(parents=True,mode=0o700)
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';start=time.monotonic();gate=budget=authority=postdb=observation=None
    error=None;result={};verified=[];cursor=0;target=None;active=None;technical_closed=False;catalogue=out/'verified_partitions.jsonl';catalogue.touch(exist_ok=False)
    prior_catalogues=[];unresolved=0;unverified=None;child_census=None;sample=None
    try:
        gate=fixtures(out)
        I.OBS.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':512<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':plan['output_cap_bytes']})
        budget=R.Budget(plan,proof,out);authority=R.Authority(out/'derived_DATA_authority.sqlite',plan['data_references'])
        postdb=E.post_catalogue(plan,out,budget,authority)
        prep=out/'prepare';budget.set_active(prep);prepared=P.run(plan,common,formal,hof,prep,budget,proof['job_id'])
        with E.R.source_fd(formal,authority,budget.check) as (_,fd,current_frame):
            frame_ref=C.Q.write_new(prep/'actual_canonical_source_frame.json',{'schema':'D5_ACTUAL_SHARED_CANONICAL_SOURCE_FRAME_V1',
                'reference':formal,'actual_current_frame':list(current_frame),'actual_parent_job_id':str(proof['job_id']),
                'node':proof['request']['node'],'uid':1278,'whole_SHA_verified_CPU':True,'current_path_FD_device_stable':True,
                'historical_node13_device_not_replaced':True,'Root_frame_review_reference':plan['native_source_frame_review_reference']})
        prepared['actual_canonical_source_frame_reference']=frame_ref
        prepared_ref=C.Q.write_new(prep/'prepared.json',prepared);prepared_db=I.actual_ref(prep/'prepare.duckdb');authority.add(prepared_db)
        budget.retire(prep);target=prepared['logical_range'][1]
        for chain in plan.get('previous_compound_closures',[]):
            prior=C.meta(chain['receipt']);pref=prior['verified_partition_catalogue_reference'];prior_catalogues.append(pref)
            rows=list(I.jsonl(pref,authority,budget.check));C.need(E.validate_prefix(rows)==prior['molecules'],'REAL_PRIOR_VERIFIED_PREFIX_END')
            # A later prefix may already contain earlier adopted partitions.
            # Exact per-interval equality is required, never count-deduplicate.
            for row in rows:
                old=next((v for v in verified if v['logical_range']==row['logical_range']),None)
                C.need(old is None or old==row,'NO_CONFLICTING_PREVIOUS_PREFIX_ROWS')
                if old is None:verified.append(row);E.add_refs(authority,row)
        verified.sort(key=lambda v:v['logical_range']);cursor=E.validate_prefix(verified)
        for row in verified:append(catalogue,row)
        with E.Executor(budget) as pool:
            for locref,range_meta in E.source_ranges(prepared):
                lo,hi=range_meta['logical_range']
                if hi<=cursor:continue
                C.need(lo==cursor,'NO_CURSOR_SKIP_WITHOUT_VERIFIED_PARTITION_COVERAGE')
                # Boundary resource stop closes the already verified prefix;
                # an active partition failure remains UNKNOWN/non-C0.
                try:budget.check(force=True)
                except Exception:
                    if cursor>0 and active is None:break
                    raise
                active=out/'partitions'/('part_%08d'%lo);budget.set_active(active)
                started=C.Q.write_new(active/'started.json',{'schema':'D5_SAME_PARENT_PARTITION_STARTED_V1','actual_parent_job_id':str(proof['job_id']),
                    'logical_range':[lo,hi],'prepared_range_reference':locref,'not_a_child_Slurm_job':True})
                value=E.packet_tables(plan,range_meta,active,budget,pool,postdb,authority)
                C.need(value['held_molecules']==0,'UNKNOWN_MOLECULE_RETAINED_NO_AUTOMATIC_RETRY')
                expected=E.expected_physical(prepared_db,lo,hi,active,budget,authority)
                bounded_common=dict(common,physical_geometry_tables=[expected]);vp=dict(plan,logical_range=[lo,hi],data_references=authority)
                readback=active/'readback';readback.mkdir();value=V.run(vp,value,bounded_common,readback,budget,pool,E.CachedIO)
                value.update(worker_packet_references=[I.actual_ref(p) for p in sorted((active/'workers').glob('*.lossless.json'))],
                    actual_origin_parent_job_id=str(proof['job_id']),prepared_range_reference=locref,expected_original_physical_reference=expected,
                    actual_started_reference=started,not_an_independent_child_C0=True)
                E.add_refs(authority,value);append(catalogue,value);verified.append(value);cursor=hi;budget.retire(active);active=None
                C.Q.write_new(out/('cursor_%08d.json'%cursor),{'schema':'D5_VERIFIED_PREFIX_CURSOR_V1','cursor':cursor,
                    'actual_parent_job_id':str(proof['job_id']),'coverage_is_catalogue_not_cursor_alone':True})
            if cursor>0 and cursor<target:
                result={'logical_range':[0,cursor],'molecules':cursor,'held_molecules':0,'full_typed_source_order_identity_parity':True,
                    'whole_true_Common_coverage_verified':False,'safe_prefix_catalogue_only_no_global_tables':True}
            if cursor==target and cursor>0:
                cr=I.actual_ref(catalogue);authority.add(cr);mergeout=out/'merged';budget.set_active(mergeout)
                vp=dict(plan,logical_range=[0,cursor],data_references=authority)
                result=V.merge(vp,verified,mergeout,budget)
                E.add_refs(authority,result);result=E.whole_union(plan,result,common,[cr],mergeout,budget,authority)
                budget.retire(mergeout)
                if cursor==target and plan['phase']!='ordinary_base':
                    childout=out/'canonical_WP5_children';budget.set_active(childout)
                    actual=W.run(plan,result,prepared_db,childout,budget,authority,pool);child_census=actual['canonical_child_census']
                    # Every generated child is independently geometry/parent/
                    # table read back by the complete original verify body.
                    childverify=childout/'readback';childverify.mkdir();checked=V.run(vp,actual,common,childverify,budget,pool,E.CachedIO)
                    checked.update(canonical_child_census=child_census,ordinary_WP5_child_domain_only=True,
                        Pprime_independent_domain_acceptance=False);budget.retire(childout);result=checked
                    if plan['phase']=='all_actual_children_and_D5' and actual['all_actual_children_closed']:
                        extraout=out/'actual_Pprime_inputs';budget.set_active(extraout)
                        extra=E.children(plan,result,extraout,budget,authority)
                        extra_verify=extraout/'readback';extra_verify.mkdir();result=V.run(vp,extra,common,extra_verify,budget,pool,E.CachedIO);budget.retire(extraout)

                technical_closed=True
        if cursor==target and plan['purpose']=='full' and plan['phase']!='ordinary_base' and result.get('all_actual_children_closed') is True and result.get('whole_true_Common_coverage_verified') is True:
            lists=out/'D5';budget.set_active(lists);sample=E.sampler(plan,result,common,lists,budget,authority);budget.retire(lists)
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'ALL_SOURCE_AND_SMALL_REVIEW_BYTES_STABLE')
    except BaseException as exc:
        error={'type':type(exc).__name__,'reason':str(exc)};unverified=str(active) if active is not None else None
        if active is not None:unresolved=1
        try:
            from .core import encode
            raw=encode({'error':error,'traceback':traceback.format_exc(),'original_outputs_or_once_modified':False})
            with (out/'failure.lossless.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        except BaseException:pass
    finally:
        if postdb is not None:postdb.close()
        if authority is not None:authority.close()
        if budget is not None:
            try:budget.finish()
            except BaseException as exc:error=error or {'type':type(exc).__name__,'reason':'RESOURCE_THREAD_CLOSURE'}
        if I.OBS.MONITOR is not None:
            try:I.OBS.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'reason':'RESOURCE_OBSERVER_CLOSURE'}
    final_cap_ok=False
    try:
        C.need(I.R.used(out)+(512<<20)<plan['output_cap_bytes'],'FINAL_ACTUAL_WHOLE_OUTPUT_CAP_WITH_RESOURCE_AND_METADATA');final_cap_ok=True
    except BaseException as exc:error=error or {'type':type(exc).__name__,'reason':'FINAL_WHOLE_CAP_INVENTORY:'+str(exc)}
    complete=final_cap_ok and error is None and technical_closed and target is not None and cursor==target and result.get('full_typed_source_order_identity_parity') is True
    # A failed auxiliary projection does not erase already independently
    # verified base intervals. It cannot approve child/list components.
    if error is not None and active is None and cursor>0 and E.validate_prefix(verified)==cursor:
        result={'logical_range':[0,cursor],'molecules':cursor,'held_molecules':0,'full_typed_source_order_identity_parity':True,
            'whole_true_Common_coverage_verified':False,'safe_prefix_catalogue_only_no_global_tables':True,
            'auxiliary_phase_error_retained':error};technical_closed=False
    safe=final_cap_ok and cursor>0 and active is None and observation is not None and gate is not None and result.get('full_typed_source_order_identity_parity') is True
    status='COMPLETE_TECHNICAL_COMPOUND_REQUIRES_ROOT_REVIEW' if complete else 'PARTIAL_SAFE_PREFIX_REQUIRES_ROOT_CONTINUATION_REVIEW' if safe else 'UNKNOWN_INCOMPLETE_COMPOUND_HOLD'
    try:resource_summary=budget.receipt() if budget is not None else None
    except BaseException as exc:resource_summary={'observation_failed':True,'type':type(exc).__name__,'reason':str(exc),'logical_bytes_not_assumed_zero':True}
    receipt={'schema':'D5_COMPOUND_DAY_RECEIPT_V1','status':status,'job_id':str(proof['job_id']),'node':proof['request']['node'],
        'actual_allocated_cpus':proof['request']['cpus'],'mathematical_workers':16,'uid':1278,'purpose':plan['purpose'],'phase':plan['phase'],
        'plan_reference':C.Q.pin(a.plan),'startup_proof_reference':C.Q.pin(a.startup_proof),'source12_reference':gate,
        'resource_observation_reference':observation,'error':error,**result,'molecules':cursor,'target_molecules':target,
        'verified_partition_catalogue_reference':I.actual_ref(catalogue) if cursor else None,'unresolved_molecules':unresolved,
        'unverified_partition_reference':unverified,'canonical_child_census':child_census,'D5_sampling_and_readback':sample,
        'technical_phase_closed':technical_closed,'original_guide_counts':C.COUNTS,'D5_jointly_frozen':False,'original_parent_cost_append_required':True,
        'Pprime_N1_extra_independent_domain_unchanged':True,'no_child_Slurm_jobs':True,'no_new_QM_UFF':True,
        'resource_summary':resource_summary,'elapsed_seconds':time.monotonic()-start}
    C.Q.write_new(out/'receipt.json',receipt);print(json.dumps({'status':status,'molecules':cursor,'new_QM_UFF_calls':0}))
    return 0 if complete or safe else 3
if __name__=='__main__':raise SystemExit(main())
