"""Actual1845/1802 parents and shared14 immutable DBs/qa08 output snapshots."""
import copy,pathlib
from workflows.data_v1_final.pprime.causal15_geometry_readonly_v1 import contract as G
from workflows.data_v1_final.pprime.native72_retained_raw_diagnosis_alpha_v1 import analysis as N
Q=G.Q;meta=G.meta;unique=G.unique;HERE=Q.REPO/'workflows/data_v1_final/pprime/causal15_native_electronic_readonly_v1'
FILES=('__init__.py','contract.py','evidence.py','run.py','test_v1.py','metadata.py','README.md')
OLD_PURE=tuple(pathlib.Path(N.__file__).parent/n for n in ('__init__.py','analysis.py','contract.py','frozen_scf.py'))
KEY='pprime_causal15_native_electronic_readonly_v1';MODULE='workflows.data_v1_final.pprime.causal15_native_electronic_readonly_v1.run'
CAP=128<<20;STAGE='PPRIME_EXISTING15_NATIVE_ELECTRONIC_AND_REPRESENTATION_EVIDENCE_ZERO_QM'
PARAMETERS={'actual_geometry_parent_job_id':'4521845','actual_recovery_parent_job_id':'4521802','cases':15,'shared_closed_SQLite':14,
    'qa08_existing_snapshot_outputs_only':True,'original_tmp_dependency':False,'original_SCF_and_vector_parser_function_objects':True,
    'native_tokens_units_line_numbers_member_SHA_and_occurrences':True,'actual_command_keywords_versions_and_unknown_status_preserved':True,
    'xTB_stdout_dipole_components_au_total_Debye_separate':True,'charges_only_not_full_dipole':True,
    'coordinate_frame_fit_uses_own_coordinates_not_vectors_or_companion':True,'new_pure_fixture_methods':3,'all3_before_scientific_bodies':True,
    'new_QM_calls':0,'native_initialize_or_invoke_calls':0,'new_tolerance_or_method_or_return_state':False,
    'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD','report_maximum_bytes':2<<20,'whole_output_cap_bytes':CAP,
    'cause_classification':'HYPOTHESIS_SUPPORT_OR_UNKNOWN_ONLY','cost_overrun_action':'REPORT_AND_CONTINUE'}


def parents(plan):
    frozen=Q.pin(N.SCF.__file__);Q.need({k:frozen[k] for k in ('bytes','sha256')}==N.C.SCF_SOURCE,'EXACT_FROZEN_SCF_METADATA_V2_BYTES')
    r=meta(plan['geometry_receipt_reference']);gp=meta(r['plan_reference']);proof=meta(r['startup_proof_reference'])
    Q.need(r['schema']=='PPRIME_CAUSAL15_GEOMETRY_READONLY_RECEIPT_V1' and r['status']=='EXACT15_INPUT_AND10_JSON_OBSERVATIONS_RECORDED_ROOT_REVIEW_REQUIRED'
        and r['job_id']=='4521845' and r['uid']==1278 and r['endpoint']=='202.38.247.57:22' and r['new_QM_calls']==0
        and r['scientific_PASS'] is False and r['full_or2000_release']=='HOLD' and gp['scope_parameters']==G.PARAMETERS==proof['request']['scope_parameters']
        and proof['uid']==1278 and str(proof['job_id'])=='4521845' and proof['request']['scope_key']==G.KEY
        and r['plan_reference'] in proof['request']['source_references'],'ACTUAL1845_GEOMETRY_DIAGNOSTIC_CLOSURE_NOT_SCIENTIFIC_PASS')
    for p in (G.HERE/n for n in G.FILES):Q.need(Q.pin(p) in proof['request']['source_references'],'EXACT1845_FROZEN_SOURCE')
    _,raw=G.D.account(plan['geometry_accounting_reference'],r)
    rp,source,prepared,cases,data,parents0=G.parents(gp);cases=copy.deepcopy(cases);base=pathlib.Path(rp['output_directory'])
    refs=[*parents0,plan['geometry_receipt_reference'],plan['geometry_accounting_reference'],raw,r['plan_reference'],r['startup_proof_reference']]
    qa08ref=Q.pin(base/'qa-08/scratch_first_SHA_observations.json');qa08=meta(qa08ref);refs.append(qa08ref)
    for item in prepared['tasks']:
        qa=item['qa_id']
        if qa=='qa-08':
            selected=[]
            for entry in qa08['output_manifest']:
                found=[v['new_byte_identical_snapshot_reference'] for v in qa08['files'] if pathlib.Path(v['source_path']).name==entry['name']]
                Q.need(len(found)==1 and (found[0]['bytes'],found[0]['sha256'])==(entry['bytes'],entry['sha256']),'EXACT_PRODUCED_QA08_OUTPUT_MANIFEST')
                selected.append(found[0])
            cases[qa]['output_snapshot_references']=selected;cases[qa]['output_manifest']=qa08['output_manifest'];data.extend(selected)
        elif 'raw_snapshot_reference' not in cases[qa]:
            ref=Q.pin(base/qa/'first_SHA_and_raw_key.json');v=meta(ref);refs.append(ref)
            cases[qa].update(raw_snapshot_reference=v['opaque_copy']['new_byte_identical_snapshot_reference'],raw_key=v['raw_key']);data.append(cases[qa]['raw_snapshot_reference'])
    return gp,source,prepared,cases,unique(data),unique(refs),proof['request']['source_references']
