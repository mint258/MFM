"""Finite15 read-only native evidence using shared actual producer snapshots."""
import argparse,importlib,io,json,os,pathlib,sys,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.data_v1_final.pprime.causal15_geometry_readonly_v1 import run as V
from workflows.data_v1_final.pprime.causal15_readonly_recovery_v1 import reader as D
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from . import contract as C,evidence as E
Q=C.Q


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_PURE_BOUNDARIES')
    s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(suite);value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':s.getvalue(),'before_scientific_bodies':True}
    Q.write_new(out/'fixtures3.json',value);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_BEFORE_BODY');return value


def raw(case,record,task,archive):
    if 'output_snapshot_references' in case:
        files=[{'name':pathlib.Path(r['path']).name,'data':V.body(r,C.G.P.O.RAW_CAP),'role':'output'} for r in case['output_snapshot_references']]
        bundle,manifest=archive.bundle(files);Q.need(manifest==case['output_manifest'],'EXACT_QA08_STABLE_OUTPUT_MEMBER_MANIFEST');return files,{'source':'ACTUAL1802_STABLE_QA08_MEMBER_SNAPSHOTS','manifest':manifest}
    ref=case['raw_snapshot_reference'];p=pathlib.Path(ref['path']);V.body(ref,C.G.P.O.RAW_CAP+(1<<20));before=D.frame(p.lstat())
    for suffix in ('-journal','-wal','-shm'):Q.need(not pathlib.Path(str(p)+suffix).exists() and not pathlib.Path(str(p)+suffix).is_symlink(),'IMMUTABLE_SHARED_SNAPSHOT_NO_SIDECAR')
    retained,key=D.keyed_raw(p,archive,task,task['qa_id'],record.get('raw_reference'))
    Q.need(D.frame(p.lstat())==before and all(key[k]==case['raw_key'][k] for k in ('record_id','calc_type','execution_id','raw_sha256','raw_bytes')),'ORIGINAL_RAW_KEY_FRAME_AND_SHA')
    return retained['output_files'],{'source':'ACTUAL1802_SHARED_IMMUTABLE_DB','snapshot_reference':ref,'raw_key':key,'actual_raw_metadata':retained['metadata']}


def comparison(a,b):
    ca,cb=a['electronic']['original_SCF_extractor'],b['electronic']['original_SCF_extractor'];counts=(ca['scf_iterations'],cb['scf_iterations'])
    ea=a['electronic']['same_named_native_energy_tokens_all_occurrences'];eb=b['electronic']['same_named_native_energy_tokens_all_occurrences'];energies=[]
    for key,unit in sorted({(v['field'],v['units']) for v in ea}&{(v['field'],v['units']) for v in eb}):
        x=[v for v in ea if (v['field'],v['units'])==(key,unit)];y=[v for v in eb if (v['field'],v['units'])==(key,unit)]
        energies.append({'field':key,'units':unit,'base_tokens_all_occurrences':[v['token'] for v in x],'variant_tokens_all_occurrences':[v['token'] for v in y],
            'all_cross_occurrence_native_print_intervals_overlap':all(E.overlap(u['token'],v['token']) for u in x for v in y),
            'no_convenient_occurrence_selected':True,'energy_equality_proves_property_accuracy':False})
    return {'arms':[a['outer_arm'],b['outer_arm']],'SCF_iteration_counts':list(counts),
        'different_explicit_iteration_count_support':counts[0]!=counts[1] if None not in counts else 'UNKNOWN',
        'converged_markers':[ca['converged'],cb['converged']],'same_named_energy_native_print_comparisons':energies,
        'both_explicitly_converged_proves_same_solution_or_property_precision':False,
        'SCF_cause':'UNKNOWN','field_choice_or_unit_cause':'UNKNOWN','source_geometry_amplification_cause':'UNKNOWN',
        'original15FAIL_preserved':True,'new_numeric_tolerance_or_scientific_PASS':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);gp,source,prepared,cases,data,parents,prior_sources=C.parents(plan)
    Q.need(plan['schema']=='PPRIME_CAUSAL15_NATIVE_ELECTRONIC_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS and plan['case_sources']==cases and plan['data_references']==data,'EXACT_NATIVE_EVIDENCE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',
        required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];auth=C.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in auth['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP
        and req['wall_seconds']==plan['wall_seconds'] and type(plan['wall_seconds']) is int and 300<=plan['wall_seconds']<=1800 and plan['wall_seconds']%60==0
        and req['data_references']==data and not req.get('deferred_authority_references'),'EXACT_CPU16_NO_MEM_BOUNDED_READONLY')
    review=C.meta(req['scope']['review']);Q.need(review['native_electronic_evidence_only_zero_QM'] is True and review['full_or2000_release']=='HOLD','ROOT_EXACT_SCOPE')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_QUALITY_AUTHORITY')
    for ref in [*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(p) for p in C.OLD_PURE),*prior_sources]:Q.need(ref in req['source_references'],'ALL_CURRENT_NEW_AND_REUSED_FROZEN_SOURCE_PINS')
    Q.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_PRIMARY_FULL_ARGV')
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[k]='1'
    out=pathlib.Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_OUTPUT_ONLY');out.mkdir(parents=True,mode=0o700)
    budget=V.Budget(plan,proof,out);engine,legacy,protocol,_=T.engine(source,C.G.P.I.read);parser=importlib.import_module('read_outputs_v1');evaluation=importlib.import_module('evaluate_v1');gate=None
    from common import read_staging,staging_bytes
    try:
        gate=fixtures(out);budget.check(force=True);rows=[];by={};config=C.G.P.I.read(source['audit_config'])
        for item in prepared['tasks']:
            budget.check();case=cases[item['qa_id']];record=read_staging(V.body(case['record_reference'],C.G.P.O.RESULT_CAP));task=json.loads(V.body(case['task_reference'],1<<20))
            Q.need(record['qa_id']==task['qa_id']==item['qa_id'] and record['arm']==task['arm']==item['arm'] and record['condition']==task['condition']==item['condition']
                and record['rotation_matrix']==task['rotation_matrix'],'ORIGINAL_OUTER_IDENTITY_AND_MATRIX')
            targets={pathlib.Path(r['path']).name:V.body(r,C.G.P.O.INPUT_CAP) for r in case['target_input_references']};inputs={pathlib.Path(r['path']).name:V.body(r,C.G.P.O.INPUT_CAP) for r in case['actual_input_references']}
            Q.need(inputs==targets,'EXACT_ACTUAL_PROGRAM_INPUT_BYTES');actual=T.arrays(inputs,record['case']['symbols'])
            import numpy as np
            Q.need(actual.shape==np.asarray(record['case']['actual_rendered_coordinates_A']).shape and actual.astype('<f8').tobytes()==np.asarray(record['case']['actual_rendered_coordinates_A'],dtype='<f8').tobytes(),'ORIGINAL_ACTUAL_INPUT_COORDINATES_NOT_SURROGATE')
            files,provenance=raw(case,record,task,engine.OUTPUT_ARCHIVE);parsed=parser.parse_outputs(files,record['case']['calc_type'],record['case']['symbols'])
            Q.need(staging_bytes(parsed)==staging_bytes(record['independent_raw_readback']),'UNCHANGED_ORIGINAL_PARSER_MATCHES_ACTUAL1802_READBACK')
            measurement=evaluation.measurement(record,config);electronic=E.observe(files,record,parser,config)
            row={'qa_id':record['qa_id'],'condition':record['condition'],'outer_arm':record['arm'],'outer_rotation_matrix':record['rotation_matrix'],
                'declared_frozen_task_keywords_or_args':task['original_task'],'actual_raw_context_and_command_provenance':provenance,
                'original_producer_WP5_provenance_if_retained':record.get('parsed_wp5_result',{}).get('provenance'),
                'native_full_command_or_returncode_not_synthesized_if_absent':True,
                'own_output_coordinate_frame':measurement['coordinates'],'frozen_vector_stored_raw_checks':measurement['stored_raw_checks'],
                'electronic':electronic,'original_WP5_status_unknown_preserved':record['qa_id'] in ('qa-02','qa-08'),
                'new_QM_calls':0,'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'}
            rows.append(row);by[(row['condition'],row['outer_arm'])]=row
        checks=[{'condition':condition,**comparison(by[(condition,a)],by[(condition,b)])} for condition in C.G.P.O.CASES
            for a,b in (('B1','B2'),('P1','P2'),('B1','R1'),('B1','P1'),('B1','P2'))]
        result={'schema':'PPRIME_CAUSAL15_NATIVE_ELECTRONIC_EVIDENCE_V1','job_id':str(proof['job_id']),'cases':rows,'comparisons':checks,'fixtures':gate,
            'geometry_parent_reference':plan['geometry_receipt_reference'],'original_predeclared_tolerances':{k:config[k] for k in ('coordinate_atol_A','vector_tolerances','rendered_coordinate_atol_A')},
            'hypothesis_support_only':True,'cause':'UNKNOWN_NO_AUTOMATIC_SCF_UNIT_FRAME_OR_AMPLIFICATION_CLAIM','new_QM_calls':0,'native_initialize_or_invoke_calls':0,
            'original15FAIL_preserved':True,'original_WP5_unknown_cases':['qa-02','qa-08'],'scientific_PASS':False,'full_or2000_release':'HOLD'}
        rawbytes=staging_bytes(result)+b'\n';Q.need(len(rawbytes)<=C.PARAMETERS['report_maximum_bytes'],'BOUNDED_REPORT_NO_TRUNCATION')
        writer=V.B.Writer(out/'native_electronic_evidence.jsonl',budget)
        try:writer.write(json.loads(staging_bytes(result)))
        finally:writer.close()
        Q.write_new(out/'receipt.json',{'schema':'PPRIME_CAUSAL15_NATIVE_ELECTRONIC_RECEIPT_V1','status':'EXACT15_RETAINED_NATIVE_EVIDENCE_RECORDED_UNKNOWN_CAUSE_HOLD',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
            'report_reference':writer.reference(),'new_QM_calls':0,'scientific_PASS':False,'original15FAIL_preserved':True,'full_or2000_release':'HOLD','actual_terminal_cost':'PENDING_ROOT_ACCOUNTING'})
        return 0
    except BaseException as exc:Q.write_new(out/'failure.json',{'schema':'PPRIME_CAUSAL15_NATIVE_ELECTRONIC_FAILURE_V1','error':repr(exc),'traceback':traceback.format_exc(),'fixtures':gate,
        'new_QM_calls':0,'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'});raise


if __name__=='__main__':raise SystemExit(main())
