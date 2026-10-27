"""Actual1802 closure -> exact retained records/inputs/shared raw snapshots."""
import pathlib
from workflows.data_v1_final.pprime.causal15_readonly_recovery_v1 import contract as P
from workflows.expansion.marcel_drugs_keys_main_v1 import contract as D
Q=P.Q;HERE=Q.REPO/'workflows/data_v1_final/pprime/causal15_geometry_readonly_v1'
FILES=('__init__.py','contract.py','geometry.py','json_selection.py','run.py','test_v1.py','metadata.py','README.md')
KEY='pprime_causal15_actual_input_geometry_readonly_v1';MODULE='workflows.data_v1_final.pprime.causal15_geometry_readonly_v1.run'
CAP=128<<20;STAGE='PPRIME_CAUSAL15_EXISTING_RENDERED_INPUT_GEOMETRY_AND_JSON_SELECTION_ZERO_QM'
PARAMETERS={'actual_parent_job_id':'4521802','original_execute_job_id':'4521766','original_prepare_job_id':'4521765',
    'cases':15,'conditions':3,'comparisons_per_condition':5,'actual_input_parser':'ORIGINAL_T.arrays_AND_T.rows',
    'coordinate_source':'ACTUAL_TARGET_MATCHING_INPUT_BYTES_NOT_NATIVE_COORDINATE_SURROGATE',
    'rotation_and_arm_source':'OUTER_RECORD_ONLY_NESTED_ORIGIN_CASE_UNCHANGED',
    'coordinate_Gram_squared_distance_and_distance_interval_observations':True,
    'native_decimal_input_token_halfwidth_propagation':'EXACT_Fraction_Decimal_AND_BINARY64_R_NO_NEW_ATOL_RTOL',
    'xTB_JSON_duplicate_scope_regex_first_vs_top_last_observation_only':True,'xTB_raw_sources':10,
    'shared_artifacts_only_no_original_tmp_dependency':True,'new_pure_fixture_methods':3,'all3_before_scientific_bodies':True,
    'new_QM_calls':0,'native_initialize_or_invoke_calls':0,'original_parser_or_tolerances_modified':False,
    'original15FAIL_preserved':True,'original_WP5_unknown_cases':['qa-02','qa-08'],'scientific_PASS':False,'full_or2000_release':'HOLD',
    'report_maximum_bytes':2<<20,'whole_output_cap_bytes':CAP,'cost_overrun_action':'REPORT_AND_CONTINUE'}
meta=P.meta;unique=P.unique


def parents(plan):
    s=meta(plan['recovery_summary_reference']);rp=meta(plan['recovery_plan_reference']);proof=meta(plan['recovery_startup_proof_reference'])
    Q.need(s['schema']=='PPRIME_CAUSAL15_READONLY_RECOVERY_SUMMARY_V1' and s['status']=='ALL15_READONLY_OUTPUT_OBSERVATIONS_AVAILABLE_ROOT_REVIEW_REQUIRED'
        and s['job_id']=='4521802' and s['original_job_id']=='4521766' and len(s['observations'])==15 and s['failures']==[]
        and s['new_QM_calls']==s['native_initialize_or_invoke_calls']==s['once_ledger_writes']==0
        and s['original_WP5_status_unknown_cases']==['qa-02','qa-08'] and s['original15FAIL_preserved'] is True
        and s['scientific_PASS'] is False and s['full_or2000_release']=='HOLD','ACTUAL1802_READONLY_CLOSURE_NOT_SCIENTIFIC_PASS')
    _,prepared,source,_,_,_,oldparents=P.parents(rp)
    Q.need(rp['schema']=='PPRIME_CAUSAL15_READONLY_RECOVERY_PLAN_V1' and rp['scope_parameters']==P.PARAMETERS==proof['request']['scope_parameters']
        and proof['uid']==1278 and str(proof['job_id'])=='4521802' and proof['request']['scope_key']==P.KEY
        and plan['recovery_plan_reference'] in proof['request']['source_references']
        and pathlib.Path(plan['recovery_summary_reference']['path']).parent==pathlib.Path(rp['output_directory']),
        'EXACT1802_PLAN_PROOF_OUTPUT_BINDING')
    for path in [*(P.HERE/n for n in P.FILES)]:Q.need(Q.pin(path) in proof['request']['source_references'],'FROZEN1802_PRODUCER_SOURCE')
    account=meta(plan['recovery_accounting_reference']);_,raw=D.account(plan['recovery_accounting_reference'],{'job_id':'4521802','node':proof['request']['node']})
    refs=[*oldparents,plan['recovery_summary_reference'],plan['recovery_plan_reference'],plan['recovery_startup_proof_reference'],plan['recovery_accounting_reference'],raw]
    observations={r['qa_id']:r for r in s['observations']};Q.need(set(observations)=={'qa-%02d'%i for i in range(15)},'EXACT15_PRODUCED_RECORDS')
    cases={};data=[];base=pathlib.Path(rp['output_directory'])
    qa08ref=Q.pin(base/'qa-08/scratch_first_SHA_observations.json');qa08=meta(qa08ref);refs.append(qa08ref)
    for item in prepared['tasks']:
        qa=item['qa_id'];actual=[];target=item['target_input_references'];row={'record_reference':observations[qa]['record_reference'],
            'task_reference':item['task_reference'],'target_input_references':target,'actual_input_references':actual,
            'condition':item['condition'],'arm':item['arm']}
        for r in target:
            name=pathlib.Path(r['path']).name
            if qa=='qa-08':
                found=[f['new_byte_identical_snapshot_reference'] for f in qa08['files'] if pathlib.Path(f['source_path']).name==name]
                Q.need(len(found)==1,'EXACT_PRODUCED_QA08_INPUT_SNAPSHOT');a=found[0]
            else:a={'path':str(P.BASE/qa/'actual_postcall_inputs'/name),'bytes':r['bytes'],'sha256':r['sha256']};Q.need(a in rp['data_references'],'ACTUAL_INPUT_ALREADY_BOUND_IN1802_PLAN')
            Q.need((a['bytes'],a['sha256'])==(r['bytes'],r['sha256']) and pathlib.Path(a['path']).is_absolute()
                and Q.ROOT/'artifacts' in pathlib.Path(a['path']).parents,'ONLY_EXACT_SHARED_ACTUAL_INPUTS_NO_TMP');actual.append(a)
        if item['condition']!='pm7_B':
            if qa=='qa-08':
                found=[f['new_byte_identical_snapshot_reference'] for f in qa08['files'] if pathlib.Path(f['source_path']).name=='xtbout.json']
                Q.need(len(found)==1,'EXACT_PRODUCED_XTB_JSON_SNAPSHOT');row['xtb_json_reference']=found[0];data.extend(found)
            else:
                ref=Q.pin(base/qa/'first_SHA_and_raw_key.json');v=meta(ref);refs.append(ref)
                row['raw_snapshot_reference']=v['opaque_copy']['new_byte_identical_snapshot_reference'];row['raw_key']=v['raw_key']
                Q.need(Q.ROOT/'artifacts' in pathlib.Path(row['raw_snapshot_reference']['path']).parents,'STABLE_SHARED_DB_SNAPSHOT_ONLY');data.append(row['raw_snapshot_reference'])
        data.extend([row['record_reference'],row['task_reference'],*target,*actual]);cases[qa]=row
    return rp,source,prepared,cases,unique(data),unique(refs)
