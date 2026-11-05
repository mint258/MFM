"""Honest Alpha full-Common readiness; source-only/Main-STOPPED is never C0."""
import argparse
import re
from pathlib import Path
from ..common import load,reference,dump_new,require
from ..portable_sources_v1.transport import verify
from .engine import RECIPE

MOLECULES=1196122
ROLES={'TRAIN':1188592,'VAL':7530}
RECORDS={'TRAIN':10973084,'VAL':71884}


def component_ready(producer):
    require(producer.get('schema')=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1' and producer.get('mode')=='full'
        and producer.get('full_population_graph_computed') is True and producer.get('full_reference_candidate') is True,
        'Actual full Alpha graph producer required; source-only never releases a reference')
    require(producer.get('uid')==1264 and producer.get('Main_origin_parent_state')=='STOPPED'
        and producer.get('Main_origin_parent_C0_claimed') is False and producer.get('common_scientific_membership_rules_changed') is False
        and producer.get('new_UFF_QM_calls')==0,'Honest separate Alpha producer identity/source lineage required')
    admission=producer['profile_admission']
    require(admission.get('endpoint')=='218.192.171.238:22' and admission.get('uid')==1264
        and str(admission.get('job_id'))==str(producer['job_id']) and admission.get('workers')==16,
        'Actual Alpha worker allocation identity required')
    c=producer['result'];expected=c['expected_all_common_census']
    require(c.get('schema')=='ALPHA_FULL_COMMON_GRAPH_COMPONENT_V1' and c.get('status')=='COMPLETE_PENDING_ALPHA_C0_AND_ROOT_ACCEPTANCE'
        and type(c.get('HOLD_MIDs'))is int and c['HOLD_MIDs']==0 and c.get('strict5_rows')==MOLECULES,
        'Any graph HOLD or partial projection prevents the complete reference')
    require(expected.get('molecules')==MOLECULES and expected.get('molecules_by_role')==ROLES
        and expected.get('native_records_by_role')==RECORDS
        and re.fullmatch('[0-9a-f]{64}',expected.get('sorted_length_prefixed_MID_role_sha256','')) is not None,
        'Exact Common1196122/role/native-record census required, never a proxy')
    require(c['scan']['selected_MIDs']==MOLECULES and c['scan']['all_common_observed_census']==expected
        and c['observed_projection_census']==expected and c['scan']['formal_MIDs_contiguous_with_no_recurrence'] is True,
        'Full scanner/strict5 molecular membership and record conservation required')
    require(c.get('fingerprint_recipe')==RECIPE and c.get('source_kind')=='v1_common_structure_projection'
        and c.get('graph_selector')=='ORIGINAL_CREATOR_SMILES_STRIP_TEMPLATE_V1'
        and c.get('original_multiple_graph_HOLD_semantics_unchanged') is True
        and c.get('reference_is_not_55k_or_all_TRAIN_proxy') is True,'Unchanged original molecular graph/reducer recipe required')
    require(len(c['input_current_SHA_frames'])==33 and len(c['all_output_journals_current_SHA_readback'])==4
        and len(c['actual_worker_proofs'])==16 and len(c['worker_MID_counts'])==16
        and sum(c['worker_MID_counts'].values())==MOLECULES,
        'Full33 held input views,4 journal readbacks and16 real workers required')
    for entry in c['input_current_SHA_frames']:
        frame=entry['current_Alpha_frame'];ref=entry['destination_reference']
        require(len(frame)==7 and frame[2]==1264 and frame[3]==1 and frame[4]==ref['bytes']>0,
            'Actual Alpha single-link held input FD provenance required')
    for entry in c['all_output_journals_current_SHA_readback']:
        frame=entry['frame'];ref=entry['reference']
        require(len(frame)==7 and frame[2]==1264 and frame[3]==1 and frame[4]==ref['bytes']>0,
            'Actual Alpha single-link closed output readback provenance required')
    key=lambda r:tuple(r[k] for k in ('path','bytes','sha256'))
    require({key(row['reference']) for row in c['all_output_journals_current_SHA_readback']}
        =={key(c[name]) for name in ('source_journal','graph_results','projection','structural_features')},
        'All four exact producer journals must be independently read back')
    return c


def accepted(producer_reference,review_reference):
    p=load(verify(producer_reference));c=component_ready(p);review=load(verify(review_reference))
    require(review.get('schema')=='ROOT_ALPHA_FULL_COMMON_GRAPH_ACTUAL_ACCEPTANCE_V1'
        and review.get('status')=='APPROVED_EXACT_FULL_COMMON_REFERENCE' and review.get('reviewer')=='root'
        and review.get('producer_receipt')==producer_reference and review.get('Main_parent_C0_claimed') is False
        and review.get('original_graph_variants_and_HOLD_reviewed') is True,'Independent actual Alpha full graph acceptance required')
    parent=review['actual_parent']
    require(parent.get('endpoint')=='218.192.171.238:22' and parent.get('uid')==1264
        and str(parent.get('JobIDRaw'))==str(p['job_id']) and parent.get('State')=='COMPLETED'
        and parent.get('ExitCode')=='0:0','Actual Alpha parent C0 required; Main STOPPED is not substituted')
    account=load(verify(review['actual_accounting_reference']))
    require(parent in account['actual_parents'],'Independent actual Alpha accounting must contain this exact parent')
    source=load(verify(p['source_tests']))
    require(source['tests']==6 and source['failures']==source['errors']==source['skips']==0
        and source['fresh_spawn_workers']==16 and source['synthetic_tasks']==64,'Original+transport source and actual fresh-worker fixtures required')
    plan=load(verify(p['plan']));proof=load(verify(p['startup_proof']))
    require(plan['mode']=='full' and plan['schema']=='ALPHA_COMMON_GRAPH_CONTINUATION_PLAN_V1'
        and str(proof['job_id'])==str(p['job_id']) and proof['request']['producer_plan_reference']==p['plan'],
        'Actual full Alpha plan/startup source binding required')
    common=load(verify(c['Alpha_common_manifest_copy']))
    require(common['denominator_molecules']==1214218 and common['excluded_molecules']==18096
        and common['execution_unresolved_molecules']==3436 and common['pilot_only'] is False
        and common['orders_frozen'] is False,'Original denominator/exclusions/UNKNOWN provenance retained')
    role_rows={r['effective_role']:r for r in common['roles']}
    require(set(role_rows)==set(ROLES) and all(role_rows[r]['molecules']==ROLES[r]
        and role_rows[r]['pm7_records']==RECORDS[r] for r in ROLES),'Original frozen TRAIN/VAL role header required')
    for ref in c['actual_worker_proofs']:
        worker=load(verify(ref));require(worker['uid']==1264 and str(worker['job_id'])==str(p['job_id'])
            and worker['original_function_objects_checked_in_this_worker'] is True,'Actual independent Alpha worker source proof required')
    return p,c,review


def validate_manifest(m):
    require(m.get('producer_schema')=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1'
        and m.get('status')=='COMPLETE_ALPHA_FULL_COMMON_REFERENCE' and m.get('common_molecules')==MOLECULES,
        'Explicit accepted Alpha Common consumer manifest required')
    p,c,review=accepted(m['actual_full_receipt_reference'],m['final_Root_graph_review_reference'])
    same=lambda a,b:all(a[k]==b[k] for k in ('path','bytes','sha256'))
    require(same(m['projection'],c['projection']) and same(m['structural_features'],c['structural_features'])
        and m['projection']['rows']==MOLECULES and m['structural_features']['rows']==MOLECULES
        and m['common_population_manifest']==c['Alpha_common_manifest_copy']
        and m['exact_common_census']==c['expected_all_common_census']
        and m['denominator_molecules']==1214218 and m['excluded_molecules']==18096
        and m.get('Main_parent_C0_claimed') is False,'Exact accepted outputs/census/origin must stay bound')
    return m


def finalize(producer_path,review_path,output):
    producer_ref=reference(producer_path);review_ref=reference(review_path);p,c,review=accepted(producer_ref,review_ref)
    result={'schema':'expansion_common_v1_structure_projection_v1','producer_schema':p['schema'],
        'status':'COMPLETE_ALPHA_FULL_COMMON_REFERENCE','fingerprint_recipe':RECIPE,'targets_present':False,
        'downstream_features_present':False,'population_roles':['TRAIN','VAL'],'one_row_per_common_molecule':True,
        'projection':{**c['projection'],'rows':MOLECULES},'structural_features':{**c['structural_features'],'rows':MOLECULES},'common_molecules':MOLECULES,
        'common_population_manifest':c['Alpha_common_manifest_copy'],'exact_common_census':c['expected_all_common_census'],
        'denominator_molecules':1214218,'excluded_molecules':18096,'original_execution_UNKNOWN_excluded':3436,
        'actual_full_receipt_reference':producer_ref,'actual_full_accounting_reference':review['actual_accounting_reference'],
        'final_Root_graph_review_reference':review_ref,'producer_source':reference(Path(__file__)),
        'origin_Main_common_manifest_reference':c['original_Main_common_manifest_reference'],
        'Main_origin_parent_state':'STOPPED','Main_parent_C0_claimed':False,
        'NN_1M_pool_training_release_authorized':False,'D7_or_orders_release':False}
    dump_new(output,result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('producer','root-review','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();finalize(a.producer,a.root_review,a.output)


if __name__=='__main__':main()
