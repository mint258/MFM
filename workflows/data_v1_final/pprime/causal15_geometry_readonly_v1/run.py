"""Zero-QM shared-file geometry and xTB selection observations for actual15."""
import argparse,importlib,io,json,os,pathlib,stat,sys,traceback,unittest
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as R
from workflows.expansion.marcel_drugs_keys_main_v1 import runtime as B
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from . import contract as C,geometry as G,json_selection as J
Q=C.Q


class Budget(B.Budget):
    def check(self,dispatch=False,force=False):
        # Sequential read-only work has no in-flight worker dispatch to reserve.
        super().check(False,force);Q.need(self.stop_new is None,self.stop_new or 'RESOURCE_STOP')


def body(ref,limit):
    p=pathlib.Path(ref['path']);s=p.lstat();Q.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278,'OWN_REGULAR_SHARED_INPUT')
    return C.P.I.body(ref,limit)


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);Q.need(suite.countTestCases()==3,'EXACT3_PURE_BEFORE_BODY')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    v={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),'before_scientific_bodies':True}
    Q.write_new(out/'fixtures3.json',v);Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_PASS');return v


def actual(row,source,archive,parser,budget):
    from common import read_staging
    import numpy as np
    record=read_staging(body(source['record_reference'],C.P.O.RESULT_CAP));task=json.loads(body(source['task_reference'],1<<20))
    qa=task['qa_id'];Q.need(record['qa_id']==qa and record['condition']==task['condition']==source['condition']
        and record['arm']==task['arm']==source['arm'] and record['rotation_matrix']==task['rotation_matrix']
        and record['case']['symbols']==task['case']['symbols'],'PRODUCER_RECORD_TASK_OUTER_IDENTITY')
    targets={pathlib.Path(r['path']).name:body(r,C.P.O.INPUT_CAP) for r in source['target_input_references']}
    inputs={pathlib.Path(r['path']).name:body(r,C.P.O.INPUT_CAP) for r in source['actual_input_references']}
    Q.need(inputs==targets,'ACTUAL_INPUT_BYTES_EXACTLY_MATCH_ORIGINAL_PREPARED_TARGETS')
    value=G.coordinates(inputs,record['case']['symbols']);stored=np.asarray(record['case']['actual_rendered_coordinates_A'],dtype='<f8')
    info={'qa_id':qa,'condition':record['condition'],'outer_arm':record['arm'],'outer_rotation_matrix':record['rotation_matrix'],
        'nested_case_arm_and_rotation_provenance':{'arm':record['case']['arm'],'rotation_matrix':record['case']['rotation_matrix']},
        'coordinate_source_input':value['name'],'target_and_actual_input_references':{'target':source['target_input_references'],'actual':source['actual_input_references']},
        'actual_input_bytes_equal_target':True,'same_native_symbols_and_atom_order':True,'atoms':len(value['symbols']),
        'T_arrays_binary64_equal_recovered_actual_rendered_coordinates':stored.shape==value['array'].shape and stored.tobytes()==value['array'].tobytes(),
        'native_coordinates_A_surrogate_used':False,'native_input_token_decimals':12,'native_input_token_halfwidth_A':'0.0000000000005',
        'redundant_input_coordinate_checks':value['redundant_coordinate_inputs'],'original_WP5_unknown_preserved':qa in ('qa-02','qa-08')}
    if task['condition']!='pm7_B':
        if 'xtb_json_reference' in source:text=body(source['xtb_json_reference'],C.P.O.RAW_CAP).decode('utf-8')
        else:
            from workflows.data_v1_final.pprime.causal15_readonly_recovery_v1 import reader as D
            rawref=source['raw_snapshot_reference'];path=pathlib.Path(rawref['path']);body(rawref,C.P.O.RAW_CAP+(1<<20));before=D.frame(path.lstat())
            for suffix in ('-journal','-wal','-shm'):Q.need(not pathlib.Path(str(path)+suffix).exists() and not pathlib.Path(str(path)+suffix).is_symlink(),'CLOSED_STABLE_SQLITE_NO_SIDECAR')
            retained,key=D.keyed_raw(path,archive,task,qa,record.get('raw_reference'))
            Q.need(D.frame(path.lstat())==before and all(key[k]==source['raw_key'][k] for k in ('record_id','calc_type','execution_id','raw_sha256','raw_bytes')),'ACTUAL_STABLE_PRODUCED_RAW_KEY_AND_FRAME')
            files=[f for f in retained['output_files'] if pathlib.Path(f['name']).name=='xtbout.json'];Q.need(len(files)==1,'EXACT_ONE_RETAINED_XTB_JSON')
            # Original raw archive returns each native member as {'name','data',...}.
            text=files[0]['data'].decode('utf-8')
        info['xTB_JSON_selection_observation']=J.observe(text,parser,record['independent_raw_readback'].get('xtb_dipole'))
    budget.check();return record,value,info


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=Q.load(a.plan);rp,source,prepared,cases,data,parents=C.parents(plan)
    Q.need(plan['schema']=='PPRIME_CAUSAL15_GEOMETRY_READONLY_PLAN_V1' and plan['scope_parameters']==C.PARAMETERS
        and plan['case_sources']==cases and plan['data_references']==data,'EXACT_ACTUAL_CASE_SOURCE_PLAN')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=R.require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.PARAMETERS,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[Q.pin(a.plan),*parents,plan['cost_decision_reference']])
    req=proof['request'];authority=C.meta(req['queue_authority_reference']);allowed={'compute-0-'+str(n) for n in authority['allowed_nodes']['analysis']}
    Q.need(req['node'] in allowed and req['pilot'] is False and req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP
        and req['wall_seconds']==plan['wall_seconds'] and type(plan['wall_seconds']) is int and 300<=plan['wall_seconds']<=1800
        and plan['wall_seconds']%60==0 and req['data_references']==data and not req.get('deferred_authority_references'),'EXACT_CPU16_NO_MEM_ANALYSIS_BOUND')
    review=C.meta(req['scope']['review']);Q.need(review['actual_input_geometry_and_JSON_selection_only_zero_QM'] is True
        and review['original15FAIL_preserved'] is True and review['full_or2000_release']=='HOLD','ROOT_SCOPE_NO_SCIENCE_RELEASE')
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'CURRENT_COST_AND_SCIENCE_AUTHORITY')
    for path in [*(C.HERE/n for n in C.FILES),*(C.P.HERE/n for n in C.P.FILES),*(C.D.HERE/n for n in C.D.FILES)]:Q.need(Q.pin(path) in req['source_references'],'NEW_AND_REUSED_SOURCE_PINS')
    Q.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'ACTUAL_PRIMARY_COMPLETE_ARGV')
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
    out=pathlib.Path(plan['output_directory']);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'artifacts' in out.parents and not out.exists(),'FRESH_GEOMETRY_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=Budget(plan,proof,out);engine,_,_,_=T.engine(source,C.P.I.read);parser=importlib.import_module('read_outputs_v1');gate=None
    try:
        gate=fixtures(out);budget.check(force=True);records={};observations=[]
        for item in prepared['tasks']:
            budget.check();record,coords,info=actual(item,cases[item['qa_id']],engine.OUTPUT_ARCHIVE,parser,budget)
            key=(record['condition'],record['arm']);Q.need(key not in records,'UNIQUE_OUTER_CASE_MATRIX');records[key]=(record,coords);observations.append(info)
        comparisons=[]
        for condition in C.P.O.CASES:
            for left,right in (('B1','B2'),('P1','P2'),('B1','R1'),('B1','P1'),('B1','P2')):
                budget.check();ar,ax=records[(condition,left)];br,bx=records[(condition,right)]
                matrix=[[1,0,0],[0,1,0],[0,0,1]] if (left,right) in {('B1','B2'),('P1','P2')} else br['rotation_matrix']
                comparisons.append({'condition':condition,'outer_arms':[left,right],**G.compare(ax,bx,matrix)})
        config=C.P.I.read(source['audit_config']);unchanged={k:config[k] for k in ('rendered_coordinate_atol_A','coordinate_atol_A','same_geometry_dipole_atol_au','vector_tolerances','tensor_tolerance')}
        result={'schema':'PPRIME_CAUSAL15_ACTUAL_INPUT_GEOMETRY_AND_JSON_OBSERVATION_V1','job_id':str(proof['job_id']),
            'recovery_parent_job_id':'4521802','observations':observations,'comparisons':comparisons,'fixtures':gate,
            'original_vector_tolerances_and_statuses_unchanged':True,'original_audit_config_reference':source['audit_config'],
            'original_predeclared_tolerances_preserved_not_used_as_new_geometry_limits':unchanged,'new_QM_calls':0,'native_initialize_or_invoke_calls':0,
            'original15FAIL_preserved':True,'original_WP5_unknown_cases':['qa-02','qa-08'],'scientific_PASS':False,
            'cause':'UNKNOWN_REQUIRES_ROOT_REVIEW_OF_ACTUAL_GEOMETRY_AND_SELECTION_EVIDENCE','full_or2000_release':'HOLD'}
        raw=C.P.O.canonical(result)+b'\n';Q.need(len(raw)<=C.PARAMETERS['report_maximum_bytes'],'BOUNDED_REPORT_NO_TRUNCATION')
        writer=B.Writer(out/'geometry_and_JSON_report.jsonl',budget)
        try:writer.write(result)
        finally:writer.close()
        Q.write_new(out/'receipt.json',{'schema':'PPRIME_CAUSAL15_GEOMETRY_READONLY_RECEIPT_V1','status':'EXACT15_INPUT_AND10_JSON_OBSERVATIONS_RECORDED_ROOT_REVIEW_REQUIRED',
            'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','plan_reference':Q.pin(a.plan),
            'startup_proof_reference':Q.pin(a.startup_proof),'report_reference':writer.reference(),'original15FAIL_preserved':True,
            'scientific_PASS':False,'full_or2000_release':'HOLD','new_QM_calls':0,'actual_terminal_cost':'PENDING_ROOT_ACCOUNTING'})
        return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'PPRIME_CAUSAL15_GEOMETRY_READONLY_FAILURE_V1','error':repr(exc),'traceback':traceback.format_exc(),
            'fixtures':gate,'new_QM_calls':0,'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'});raise


if __name__=='__main__':raise SystemExit(main())
