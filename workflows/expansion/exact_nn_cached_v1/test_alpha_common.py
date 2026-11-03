"""Pure metadata boundaries: never infer a full reference from source mode."""
import copy
import unittest
from .alpha_common import component_ready,MOLECULES,ROLES,RECORDS


def fixture():
    census={'molecules':MOLECULES,'molecules_by_role':dict(ROLES),'native_records_by_role':dict(RECORDS),
        'sorted_length_prefixed_MID_role_sha256':'a'*64}
    refs=[{'path':'/fixture-not-actual/'+str(i),'bytes':1,'sha256':'a'*64} for i in range(4)]
    return {'schema':'ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1','mode':'full','full_population_graph_computed':True,
        'full_reference_candidate':True,'uid':1264,'job_id':'FIXTURE_NOT_AN_ACTUAL_JOB','Main_origin_parent_state':'STOPPED',
        'Main_origin_parent_C0_claimed':False,'common_scientific_membership_rules_changed':False,'new_UFF_QM_calls':0,
        'profile_admission':{'endpoint':'218.192.171.238:22','uid':1264,'job_id':'FIXTURE_NOT_AN_ACTUAL_JOB','workers':16},
        'result':{'schema':'ALPHA_FULL_COMMON_GRAPH_COMPONENT_V1','status':'COMPLETE_PENDING_ALPHA_C0_AND_ROOT_ACCEPTANCE',
        'HOLD_MIDs':0,'strict5_rows':MOLECULES,'expected_all_common_census':census,'observed_projection_census':copy.deepcopy(census),
        'scan':{'selected_MIDs':MOLECULES,'all_common_observed_census':copy.deepcopy(census),'formal_MIDs_contiguous_with_no_recurrence':True},
        'fingerprint_recipe':'ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5','source_kind':'v1_common_structure_projection',
        'graph_selector':'ORIGINAL_CREATOR_SMILES_STRIP_TEMPLATE_V1','original_multiple_graph_HOLD_semantics_unchanged':True,
        'reference_is_not_55k_or_all_TRAIN_proxy':True,
        'input_current_SHA_frames':[{'destination_reference':{'bytes':1},'current_Alpha_frame':[1,i,1264,1,1,1,1]} for i in range(33)],
        'all_output_journals_current_SHA_readback':[{'reference':refs[i],'frame':[1,i,1264,1,1,1,1]} for i in range(4)],
        **dict(zip(('source_journal','graph_results','projection','structural_features'),refs)),
        'actual_worker_proofs':[None]*16,
        'worker_MID_counts':{str(i):MOLECULES//16+int(i<MOLECULES%16) for i in range(16)}}}


class AlphaCommonBoundaries(unittest.TestCase):
    def test_candidate_header_retains_exact_train_val_native_census(self):
        p=fixture();self.assertEqual(component_ready(p)['strict5_rows'],1196122)

    def test_source_only_cannot_pass_even_with_copied_full_counts(self):
        p=fixture();p['mode']='source';p['full_population_graph_computed']=False
        with self.assertRaises(ValueError):component_ready(p)

    def test_graph_hold_never_releases_a_subset_reference(self):
        p=fixture();p['result']['HOLD_MIDs']=1;p['result']['status']='SOURCE_GRAPH_HOLD_NOT_A_SUBSET_REFERENCE'
        with self.assertRaises(ValueError):component_ready(p)

    def test_wrong_scope_or_fake_Main_C0_never_substitutes_for_Alpha(self):
        for mutate in (lambda p:p['result']['expected_all_common_census'].update(molecules=55000),
                lambda p:p.update(Main_origin_parent_C0_claimed=True),lambda p:p.update(uid=1278),
                lambda p:p['result']['observed_projection_census']['molecules_by_role'].update(VAL=0)):
            p=fixture();mutate(p)
            with self.assertRaises(ValueError):component_ready(p)


if __name__=='__main__':unittest.main()
