"""Three meaningful synthetic methods, no DATA/monitor/RDKit calls."""
import io,json,sqlite3,unittest
from workflows.expansion.common_molecular_fp_main_v1 import scan as S,io as I
from . import finalize as F
from workflows.expansion.common_molecular_fp_candidate_v1 import contracts as P

class Boundaries(unittest.TestCase):
    def test_actual_segment_record_mass_and_cross_segment_duplicate_guard(self):
        S.validate_segment_count(('TRAIN',3,1),3,'m')
        with self.assertRaises(ValueError):S.validate_segment_count(('TRAIN',3,1),2,'m')
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE seen(mid TEXT PRIMARY KEY,n INTEGER)')
        S.begin_segment(db,'m');S.begin_segment(db,'other')
        with self.assertRaisesRegex(ValueError,'REAPPEARED'):S.begin_segment(db,'m')
        db.close()

    def test_strict5_roundtrip_same_graph_two_MIDs_empty_scaffold_and_targets_rejected(self):
        def row(mid):return {'molecule_id':mid,'full_key':'AAAAAAAAAAAAAA-BBBBBBBBBB-C','ecfp4_2048_hex':'00'*256,
                             'generic_murcko':'','generic_ring_systems':['C1CC1','C1CC1']}
        raw=b''.join((json.dumps(row(mid))+'\n').encode() for mid in ('m1','m2'))
        count,census=I.read_strict5_rows(io.BytesIO(raw),lambda mid:('TRAIN' if mid=='m1' else 'VAL',7))
        self.assertEqual(count,2);self.assertEqual(census['molecules_by_role'],{'TRAIN':1,'VAL':1})
        self.assertEqual(set(row('m1')),P.PROJECTION_FIELDS)
        with self.assertRaises(ValueError):I.read_strict5_rows(io.BytesIO((json.dumps({**row('m1'),'target':1})+'\n').encode()),lambda mid:('TRAIN',7))
        with self.assertRaises(ValueError):I.read_strict5_rows(io.BytesIO(raw+raw.splitlines(keepends=True)[0]),lambda mid:('TRAIN',7))

    def test_profile_or_unknown_cannot_publish_and_final_Root_graph_authority_required(self):
        census={'molecules':2,'molecules_by_role':{'TRAIN':1,'VAL':1}}
        result={'HOLD_MIDs':0,'selected_MIDs':2,'strict5_rows':2,'expected_all_common_census':census,
                'selected_census':census,'all_common_observed_census':census,'strict5_independent_parsed_census':census}
        receipt={'mode':'full','status':'SELECTED_MOLECULAR_GRAPH_AUDIT_COMPLETE_PENDING_ROOT_FINAL_REVIEW','result':result}
        review={'schema':'ROOT_COMMON_FP_FINAL_GRAPH_REVIEW_V1','status':'APPROVED_EXACT_COMMON_REFERENCE_PROJECTION','reviewer':'root',
                'all_actual_graph_variants_UNKNOWN_conflicts_and_accepted_differences_reviewed':True,
                'no_representative_graph_no_FP_OR_no_historical_key_equality_gate':True,'NN_1M_pool_training_release_authorized':False}
        F.release_gate(receipt,review)
        with self.assertRaises(ValueError):F.release_gate({**receipt,'mode':'profile'},review)
        with self.assertRaises(ValueError):F.release_gate({**receipt,'result':{**result,'HOLD_MIDs':1}},review)
        with self.assertRaises(ValueError):F.release_gate(receipt,{**review,'status':'PENDING_ROOT_REVIEW'})
        self.assertEqual(S.profile_hash('m'),S.profile_hash('m'));self.assertNotEqual(S.profile_hash('m'),S.profile_hash('other'))
