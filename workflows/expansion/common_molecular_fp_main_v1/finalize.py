"""Root-only metadata finalization after actual full C0 and final graph review."""
from pathlib import Path
from . import contract as C
Q=C.Q

def release_gate(receipt,review):
    r=receipt['result'];expected=r['expected_all_common_census']
    Q.need(receipt['mode']=='full' and receipt['status']=='SELECTED_MOLECULAR_GRAPH_AUDIT_COMPLETE_PENDING_ROOT_FINAL_REVIEW'
        and r['HOLD_MIDs']==0 and r['selected_MIDs']==r['strict5_rows']==expected['molecules']
        and r['selected_census']==r['all_common_observed_census']==r['strict5_independent_parsed_census']==expected,
        'FULL_NO_UNKNOWN_EXACT_ALL_COMMON_GRAPH_AND_STRICT5_CENSUS')
    Q.need(review['schema']=='ROOT_COMMON_FP_FINAL_GRAPH_REVIEW_V1' and review['status']=='APPROVED_EXACT_COMMON_REFERENCE_PROJECTION'
        and review['reviewer']=='root' and review['all_actual_graph_variants_UNKNOWN_conflicts_and_accepted_differences_reviewed'] is True
        and review['no_representative_graph_no_FP_OR_no_historical_key_equality_gate'] is True
        and review['NN_1M_pool_training_release_authorized'] is False,'EXPLICIT_FINAL_ROOT_GRAPH_AUTHORITY')

def finalize(receipt_reference,accounting_reference,review_reference,output):
    receipt=C.meta(receipt_reference);review=C.meta(review_reference);release_gate(receipt,review)
    Q.need(review['receipt_reference']==receipt_reference and review['accounting_reference']==accounting_reference
        and review['strict5_projection_reference']==receipt['result']['strict5_projection_reference']
        and review['common_manifest_reference']==receipt['common_manifest_reference'],'EXACT_FINAL_GRAPH_REVIEW_REFS')
    _,raw=C.account(accounting_reference,receipt['job_id'],receipt['node']);plan=C.meta(receipt['plan_reference']);proof=C.meta(receipt['startup_proof_reference'])
    Q.need(Path(receipt_reference['path'])==Path(plan['output_directory'])/'receipt.json' and
        Path(receipt['result']['strict5_projection_reference']['path'])==Path(plan['output_directory'])/'strict5_projection.DATA.jsonl',
        'ACTUAL_FULL_RECEIPT_AND_PROJECTION_OUTPUT_TREE')
    *_,data,parents=C.inputs(plan)
    Q.need(proof['request']['scope_key']==C.key('full') and proof['request']['scope_parameters']==plan['scope_parameters']==C.parameters('full',plan['output_cap_bytes'])
        and receipt['data_references']==proof['request']['data_references']==data
        and str(proof['job_id'])==str(receipt['job_id']) and proof['uid']==1278
        and proof['request']['node']==receipt['node'] and receipt['plan_reference'] in proof['request']['source_references'],'FULL_ACTUAL_STARTUP_PLAN_AND_INPUTS')
    for path in C.source_paths():Q.need(Q.pin(path) in proof['request']['source_references'],'UNCHANGED_ACTUAL_FULL_PRODUCER_SOURCE')
    projection=receipt['result']['strict5_projection_reference'];C.P.data_reference({k:projection[k] for k in ('path','bytes','sha256')})
    output=Path(output);Q.need(Q.ROOT/'control' in output.parents and not output.exists() and '..' not in output.parts,'FRESH_FINAL_MANIFEST_PATH')
    return Q.write_new(output,{'schema':C.P.PROJECTION_SCHEMA,'fingerprint_recipe':C.P.FINGERPRINT_RECIPE,
        'targets_present':False,'downstream_features_present':False,'population_roles':['TRAIN','VAL'],'one_row_per_common_molecule':True,
        'projection':projection,'common_molecules':receipt['result']['expected_all_common_census']['molecules'],
        'common_population_manifest':receipt['common_manifest_reference'],'producer_source':Q.pin(C.HERE/'run.py'),
        'actual_full_receipt_reference':receipt_reference,'actual_full_accounting_reference':accounting_reference,'actual_raw_accounting_reference':raw,
        'final_Root_graph_review_reference':review_reference,'exact_common_census':receipt['result']['expected_all_common_census'],
        'baseline1M_authority':None,'NN_1M_pool_training_release_authorized':False})
