"""One actual central16CPU parent exporting closed identities, no chemistry calls."""
import argparse,io,os,sys,traceback,unittest
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from . import contract as C,io as I,local as L,tdc as T,supplement as S

def fixtures(out):
    from .test_v1 import Boundaries
    Boundaries.workspace=out
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_IDENTITY_EXPORT_BOUNDARIES')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),
        'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),'before_DATA_and_resource_monitor':True}
    ref=C.Q.write_new(out/'source3.json',value);C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_BEFORE_413_DATA')
    return ref

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=C.HERE/'run.py',expected_kind='analysis',required_references=[C.Q.pin(a.plan),plan['cost_decision_reference'],
        plan['quota_provider_review_reference'],plan['quota_provider_identity_reference'],plan['root_carveout_review_reference']])
    req=proof['request'];C.need(plan['schema']=='LOCAL6_TDC_DECONTAMINATION_DAY_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS
        and req['node']=='compute-0-14' and req['cpus']==16 and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['wall_seconds']==plan['wall_seconds']==C.WALL and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==plan['output_cap_bytes']==C.CAP
        and not req.get('deferred_authority_references'),'EXACT_MAIN14_READONLY20H_32G_NOT_GRAPH_RUN')
    review=C.generic_review(C.meta(req['scope']['review']))
    C.need(req['scope']['mode']=='BOUNDED_METADATA_PREPARATION','REAL_ROOT_EXACT_GENERIC_SCOPE_MODE')
    authority,data,parents=C.derive(plan);C.need(authority==plan['authority'] and data==plan['data_references']==req['data_references'],'EXACT_CLOSED406_DATA_NO_BODY_DISCOVERY')
    for ref in plan['source_references']:C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'ALL_ORIGINAL_SOURCE_AND_CLOSED_SMALL_PARENTS')
    for path in C.sources():C.need(C.Q.pin(path) in req['source_references'],'COMPLETE_ACTUAL_SOURCE_IMPORT_CLOSURE')
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_COST_REPORT_CONTINUE')
    out=Path(plan['output_directory']);C.need(C.BASE in out.parents and '..' not in out.parts and not out.exists()
        and not any(v.is_symlink() for v in (out,*out.parents)),'FRESH_NEW_EXPORT_ONLY_NO_OLD_MUTATION');out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';budget=None;gate=None;resource=None;sections={};sources=[];error=None
    try:
        gate=fixtures(out);budget=I.Budget(plan,proof,out);budget.check()
        sections['repository_check_reference']=S.check_repository(plan,out/'repository_check',budget)
        local=L.run(plan,authority,out/'local',budget);sections['local']=local
        sections['local_manifest_reference']=I.write(out/'local404_projection_manifest.json',local,budget)
        tdc=T.run(authority,out/'tdc',budget);sections['tdc']=tdc
        original=I.write(out/'original_source_authority_and_roles.json',{'schema':'LOCAL6_TDC_ORIGINAL_SOURCE_LINEAGE_V1',
            'local_receipt_reference':plan['local_receipt_reference'],'original_local_authority':authority['local_source_authority'],
            'original_raw_artifacts_not_rehashed_in_this_projection':authority['local_original_raw_body_references'],
            'role_semantics':'ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY','wholeMID_TRAIN_VAL_Common_applied':False,
            'tdc_receipt_reference':plan['tdc_receipt_reference'],'TDC_original_archive_reference':authority['TDC_original_archive_reference'],
            'accepted_foreign_policy_reference':plan['tdc2_policy_reference'],'Alpha_origin_uid':1264,'Main_uid':1278,
            'old4521152_FAILED_and_all_costs_preserved':True,'graph_state_of_two_unknowns':'UNKNOWN'},budget)
        for dataset,value in {**local['primary6'],'tdc_admet':tdc}.items():
            version=('LOCAL_IDENTITY4521192:'+plan['local_receipt_reference']['sha256']+':'+dataset) if dataset!='tdc_admet' else (
                'TDC_ORIGINAL44:'+authority['TDC_original_archive_reference']['sha256']+':IDENTITY4521757:CONSERVATIVE_ALPHA1884865')
            coverage={'schema':'expansion_all_source_identity_coverage_v1','dataset':dataset,'all_splits':True,
                'expected_identity_records':value['records'],'unresolved_without_identity_or_composition':value['unresolved_without_identity_or_composition'],
                'covered_roles':value['required_roles'],'covered_subdatasets':value['required_subdatasets'],'raw_artifacts':value['raw_artifacts'],
                'identities':value['identities'],'role_counts':value['role_counts'],'readback':value['readback'],'version':version,
                'raw_artifact_basis':'CLOSED_PHYSICAL_IDENTITY_PRODUCER_INPUTS_CURRENT_WHOLE_SHA_VERIFIED',
                'original_source_authority_and_raw_origin_reference':original,'original_source_graph_unknowns_not_reclassified':True,
                'original_scope_no_Common_filter':True,'Root_READY_adoption_performed':False}
            C.need(coverage['unresolved_without_identity_or_composition']==0 and coverage['expected_identity_records']>0,'ONLY_COMPLETE_PRIMARY_CANDIDATES')
            c=I.write(out/(dataset+'.coverage.json'),coverage,budget)
            sources.append({'dataset':dataset,'status':'PENDING_ROOT_ACTUAL_C0_ADOPTION','version':version,'raw_artifacts':value['raw_artifacts'],
                'identities':value['identities'],'coverage_evidence':c,'required_roles':value['required_roles'],'required_subdatasets':value['required_subdatasets'],
                'origin_reference':original,'role_basis':'ORIGINAL_SOURCE_PHYSICAL_MEMBERSHIP_NOT_FINAL_TRAINING_ROLE'})
        C.need(len(sources)==7 and sum(v['identities']['rows'] for v in sources)==11469344,'ALL_PRIMARY7_PHYSICAL_ROWS_EXACT')
        sections['candidate_sources_reference']=I.write(out/'primary7_candidates.json',{'schema':'LOCAL6_TDC_STRICT_IDENTITY_CANDIDATES_V1',
            'status':'SEVEN_CLOSED_EXPORTS_PENDING_SEPARATE_ROOT_ACTUAL_C0_ADOPTION','sources':sources,
            'Molnet_partial_not17_source_complete':True,'all11_global_decontamination_or_pool_release':False},budget)
        sections['physical_review_reference']=S.physical(plan,authority,out,budget)
        budget.check()
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'SOURCE_AND_PARENT_BYTES_STABLE_AFTER_EXPORT')
    except BaseException as exc:
        error={'type':type(exc).__name__,'state':'PARTIAL_EXPORT_HOLD_NO_READY_ADOPTION'}
        try:
            if budget:I.write(out/'failure.DATA.json',{'message':str(exc),'traceback':traceback.format_exc(),'completed_sections':list(sections)},budget)
            else:C.Q.write_new(out/'preflight_failure.json',{'error_type':type(exc).__name__,'message':str(exc)})
        except Exception:pass
    finally:
        if budget:
            try:resource=budget.finish()
            except BaseException as exc:error=error or {'type':type(exc).__name__,'state':'RESOURCE_CLOSURE_HOLD'}
    complete=error is None and resource is not None and len(sources)==7 and budget.reason is None
    summary={'schema':'LOCAL6_TDC_DECONTAMINATION_DAY_RECEIPT_V1','status':'PRIMARY7_STRICT_IDENTITIES_COMPLETE_PENDING_ROOT_ADOPTION' if complete else 'INCOMPLETE_STRICT7_EXPORT_HOLD',
        'job_id':str(proof['job_id']),'uid':1278,'node':'compute-0-14','endpoint':'202.38.247.57:22','plan_reference':C.Q.pin(a.plan),
        'startup_proof_reference':C.Q.pin(a.startup_proof),'source3_reference':gate,'resource_reference':resource,'error':error,
        'primary7_candidates':sources,'candidate_manifest_reference':sections.get('candidate_sources_reference'),
        'repository_check_actual_reference':sections.get('repository_check_reference'),'physical_D1_review_reference':sections.get('physical_review_reference'),
        'Molnet6_partial_reference':sections.get('local_manifest_reference'),'local404_rows':11398552 if 'local' in sections else None,
        'original_two_graph_UNKNOWN_rows':2,'new_graph_RDKit_fullkey_UFF_QM_calls':0,'old_failed_parent_upgraded':False,
        'READY_or_global_manifest_modified':False,'pool_or_training_release':False,'actual_terminal_cost_pending_Root_accounting':True}
    if budget:I.write(out/'receipt.json',summary,budget)
    else:C.Q.write_new(out/'receipt.json',summary)
    print({'status':summary['status'],'receipt':str(out/'receipt.json')});return 0 if complete else 3
if __name__=='__main__':raise SystemExit(main())
