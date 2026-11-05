"""Explicit repaired fullCommon authority; old alpha_common validator is untouched."""
import argparse
import json
from pathlib import Path
from ..common import load,reference,dump_new,require
from ..portable_sources_v1.transport import verify
from .engine import RECIPE

PRODUCER='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1'
STATUS='COMPLETE_ALPHA_FULL_COMMON_GENERIC_REPRESENTATION_REPAIRED_REFERENCE'
VERSION='GENERIC_ALLC_SINGLE_HEAVY_ADJACENCY_DEFERRED_VALENCE_V1'
COUNT=1196122
ROLES={'TRAIN':1188592,'VAL':7530}
RECORDS={'TRAIN':10973084,'VAL':71884}


def read(ref):return load(verify(ref))


def c0(receipt,review):
    p=review['actual_parent'];account=read(review['actual_accounting_reference'])
    require(p.get('endpoint',account.get('endpoint'))=='218.192.171.238:22'
      and str(p.get('UID',p.get('uid')))=='1264' and str(p.get('JobIDRaw',p.get('job_id')))==str(receipt['job_id'])
      and p.get('State')=='COMPLETED' and p.get('ExitCode')=='0:0' and p in account['actual_parents'],
      'Actual independent Alpha C0/accounting required, never Main/old HOLD impersonation')
    return p


def validated(validation_ref,review_ref):
    v=read(validation_ref);review=read(review_ref)
    require(v['schema']=='ALPHA_GENERIC_REPRESENTATION_REPAIR_VALIDATION_PRODUCER_V1'
      and v['status']=='COMPLETE_PENDING_ACTUAL_ALPHA_C0_AND_ROOT_TECHNICAL_REVIEW'
      and v['uid']==1264 and v['HOLD_MIDs_repaired']==119 and v['native_records_repaired']==352
      and v['original_kernel_passed_for_repaired119'] is False and v['original_failures_preserved'] is True
      and v['all_non_generic_values_exactly_equal'] is True and v['all_normal_success_feature_bytes_unchanged'] is True
      and v['representation_version']==VERSION and v['chemical_rules_changed'] is False
      and v['original_graph_changed'] is False and v['frozen_or_installed_code_modified'] is False
      and v['Common_reference_emitted'] is False,'Actual complete119 repair validation, never claimed old-kernel success')
    require(review['schema']=='ROOT_GENERIC_REPRESENTATION_REPAIR_VALIDATION_ACTUAL_ACCEPTANCE_V1'
      and review['status']=='APPROVED_TECHNICAL_GENERIC_REPRESENTATION_REPAIR_V1' and review['reviewer']=='root'
      and review['producer_receipt']==validation_ref and review['scientific_policy_unchanged'] is True
      and review['frozen_or_installed_modules_modified'] is False,'Independent actual technical repair acceptance required')
    c0(v,review)
    tests=read(v['metadata_tests']);normal=read(v['normal8_all_original_feature_bytes'])
    require(tests['tests']==2 and tests['failures']==tests['errors']==tests['skips']==0
      and len(normal['cases'])==8 and all(r['normal_original_all_feature_bytes_equal'] for r in normal['cases'])
      and len(v['actual_worker_proofs'])==16,'Actual metadata2,8 full-original feature controls and16 workers required')
    for ref in v['actual_worker_proofs']:
        worker=read(ref);scope=worker['source_proof']
        require(worker['uid']==1264 and str(worker['job_id'])==str(v['job_id']) and scope['version']==VERSION
          and scope['chemical_flags_function_object_unchanged'] is True and scope['original_non_generic_AST_and_functions_unchanged'] is True
          and len(scope['private_function_proofs'])==3 and all(p['exact_inverse_AST_equal'] and p['original_module_globals_not_modified'] for p in scope['private_function_proofs']),
          'Every real worker must attest exact AST scope/original function objects')
    return v,review


def component_ready(p):
    require(p.get('schema')==PRODUCER and p.get('uid')==1264 and p.get('mode')=='full_common_completion',
      'Explicit independent fullCommon representation-repair completion producer required')
    admission=p['profile_admission'];plan=read(p['plan']);proof=read(p['startup_proof'])
    require(admission['endpoint']=='218.192.171.238:22' and admission['uid']==1264 and admission['workers']==16
      and str(admission['job_id'])==str(p['job_id'])
      and plan['schema']=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PLAN_V1'
      and proof['request']['producer_plan_reference']==p['plan'] and str(proof['job_id'])==str(p['job_id'])
      and p['old_artifacts_modified'] is False and p['Main_origin_parent_C0_claimed'] is False,
      'Actual new allocation/plan/startup, original artifacts and Main identity remain honest')
    c=p['result'];old=read(p['original_full_source_receipt_reference'])
    require(old['schema']=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1' and str(old['job_id'])=='1885153'
      and old['uid']==1264 and old['result']['HOLD_MIDs']==119 and old['result']['strict5_rows']==1196003
      and old['Main_origin_parent_state']=='STOPPED' and old['Main_origin_parent_C0_claimed'] is False,
      'Retain original actual119 HOLD and honest Main STOPPED lineage')
    old_review=read(p['original_full_source_actual_accounting_reference'])
    require(old_review['schema']=='ROOT_ALPHA_FULL_COMMON_ACTUAL_TERMINAL_HOLD_V1'
      and old_review['status']=='ACTUAL_C0_SOURCE_GRAPH_HOLD_REVIEW_REQUIRED' and old_review['reviewer']=='root'
      and old_review['producer_receipt_reference']==p['original_full_source_receipt_reference']
      and old_review['full_reference_accepted'] is False,'Original C0/HOLD evidence, never retroactive reference approval')
    c0(old,dict(actual_parent=old_review['actual_parent'],actual_accounting_reference=p['original_full_source_actual_accounting_reference']))
    v,review=validated(p['repair_validation_receipt_reference'],p['repair_validation_review_reference'])
    expected=old['result']['expected_all_common_census']
    require(expected['molecules']==COUNT and expected['molecules_by_role']==ROLES and expected['native_records_by_role']==RECORDS
      and c['schema']=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_COMPONENT_V1'
      and c['status']=='COMPLETE_PENDING_ACTUAL_ALPHA_C0_AND_ROOT_TECHNICAL_REVIEW'
      and c['HOLD_MIDs']==0 and c['historical_HOLD_MIDs']==119 and c['strict5_rows']==COUNT
      and c['expected_all_common_census']==c['observed_projection_census']==c['membership_census']==expected,
      'Whole1196122 original MID/role/native-record census and zero current HOLD required')
    require(c['merge_counts']=={'original_rows_reused':1196003,'single_variant_repaired_rows':119,'final_rows':COUNT}
      and c['original_successful_row_bytes_preserved'] is True and c['all_repaired119_source_bound'] is True
      and c['new_UFF_QM_calls']==0 and c['old_HOLDs_and_old_receipts_preserved'] is True,
      'Exact additive119 completion without representative graph or old row modification')
    readbacks=c['all_output_journals_current_SHA_readback']
    key=lambda ref:tuple(ref[k] for k in ('path','bytes','sha256'))
    require(len(readbacks)==2 and {key(r['reference']) for r in readbacks}=={key(c['projection']),key(c['structural_features'])}
      and len(c['membership_input_current_SHA_frames'])==16 and len(c['reused_source_current_SHA_frames'])==2,
      'Both complete output readbacks and exact16 membership/2 old source FDs required')
    for row in [*readbacks,*c['membership_input_current_SHA_frames'],*c['reused_source_current_SHA_frames']]:
        frame=row['frame'];ref=row['reference']
        require(len(frame)==7 and frame[2]==1264 and frame[3]==1 and frame[4]==ref['bytes'], 'Actual Alpha heldFD source/readback provenance')
    require(c['common_population_manifest']==old['result']['Alpha_common_manifest_copy']
      and c['fingerprint_recipe']==RECIPE and c['representation_version']==VERSION,'Original population and fingerprint recipe remain bound')
    common=read(c['common_population_manifest'])
    require(common['denominator_molecules']==1214218 and common['excluded_molecules']==18096
      and common['execution_unresolved_molecules']==3436 and common['orders_frozen'] is False and common['pilot_only'] is False,
      'Original denominator/exclusions/UNKNOWN/orders policy retained')
    return c


def accepted(producer_ref,review_ref):
    p=read(producer_ref);c=component_ready(p);review=read(review_ref)
    require(review['schema']=='ROOT_ALPHA_FULL_COMMON_GENERIC_REPRESENTATION_REPAIR_ACTUAL_ACCEPTANCE_V1'
      and review['status']=='APPROVED_EXACT_FULL_COMMON_GENERIC_REPRESENTATION_REPAIRED_REFERENCE'
      and review['reviewer']=='root' and review['producer_receipt']==producer_ref
      and review['original_HOLD119_and_representation_repair_reviewed'] is True
      and review['full_source_membership_and_new_readbacks_reviewed'] is True,'Independent actual new fullCommon technical acceptance required')
    c0(p,review);return p,c,review


def validate_manifest(m):
    require(m.get('producer_schema')==PRODUCER and m.get('status')==STATUS,'Explicit repaired fullCommon manifest, no old gate weakening')
    p,c,review=accepted(m['actual_full_receipt_reference'],m['final_Root_graph_review_reference'])
    for key in ('projection','structural_features'):
        require(all(m[key][k]==c[key][k] for k in ('path','bytes','sha256')) and m[key]['rows']==COUNT,'Exact complete repaired output reference')
    require(m['original_full_source_receipt_reference']==p['original_full_source_receipt_reference']
      and m['generic_representation_repair_review_reference']==p['repair_validation_review_reference']
      and m['common_population_manifest']==c['common_population_manifest'] and m['exact_common_census']==c['expected_all_common_census']
      and m['common_molecules']==COUNT and m['denominator_molecules']==1214218 and m['excluded_molecules']==18096
      and m['Main_parent_C0_claimed'] is False,'Exact old source lineage/new actual completion/population census')
    return m


def finalize(producer_path,review_path,output):
    producer_ref=reference(producer_path);review_ref=reference(review_path);p,c,review=accepted(producer_ref,review_ref)
    result=dict(schema='expansion_common_v1_structure_projection_v1',producer_schema=PRODUCER,status=STATUS,
      fingerprint_recipe=RECIPE,targets_present=False,downstream_features_present=False,population_roles=['TRAIN','VAL'],
      one_row_per_common_molecule=True,projection={**c['projection'],'rows':COUNT},structural_features={**c['structural_features'],'rows':COUNT},
      common_molecules=COUNT,exact_common_census=c['expected_all_common_census'],common_population_manifest=c['common_population_manifest'],
      denominator_molecules=1214218,excluded_molecules=18096,original_execution_UNKNOWN_excluded=3436,
      actual_full_receipt_reference=producer_ref,actual_full_accounting_reference=review['actual_accounting_reference'],
      final_Root_graph_review_reference=review_ref,original_full_source_receipt_reference=p['original_full_source_receipt_reference'],
      generic_representation_repair_review_reference=p['repair_validation_review_reference'],
      original_HOLD_molecules=119,current_HOLD_molecules=0,representation_version=VERSION,
      Main_origin_parent_state='STOPPED',Main_parent_C0_claimed=False,NN_1M_pool_training_release_authorized=False,D7_or_orders_release=False)
    dump_new(output,result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer',required=True,type=Path)
    parser.add_argument('--root-review',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=finalize(args.producer,args.root_review,args.output)
    print(json.dumps(dict(manifest=reference(args.output),status=result['status']),sort_keys=True))


if __name__=='__main__':main()
