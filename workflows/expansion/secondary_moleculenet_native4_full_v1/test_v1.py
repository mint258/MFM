"""Three new full-scope, reuse/once and unknown-boundary pure methods only."""
import collections,unittest
from . import contracts as C,full as F
K='AAAAAAAAAAAAAA-BBBBBBBBBB-C';L='CCCCCCCCCCCCCC-DDDDDDDDDD-E'


def row(ordinal=0,kind='SDF'):
    return {'source_id':'pdbbind_core','format':kind,'source_format_ordinal':ordinal,'role':'ALL_ORIGINAL_SOURCE_MEMBERS',
        'native_non_H_composition_evidence':[[6,2]],'native_PDB_path_ID':'0000'}


def result(source,keys=None,unknown=False):
    return {'source':source,'observed_full_key_union':keys or [],'WP5_key_union':['literalWP5'] if keys else [],
        'variant_observations':[],'has_unknown':unknown,'native_graph_errors':[{'axis':'native_SDF_graph','error':'SOURCE_SDF_PARSER_NONE_UNKNOWN'}] if unknown else []}


class Boundaries(unittest.TestCase):
    def test_full_physical_census_and_same_ID_conformers_never_entity_dedup(self):
        # Regression: producer DATA triples must not inherit Q.SMALL's ceiling.
        good={'path':str(C.ROOT/'artifacts/__synthetic_native4_locator_not_created__/blob.bin'),'bytes':(2<<20)+1,'sha256':'a'*64}
        self.assertEqual(C.data_locator(good),good)
        with self.assertRaises(ValueError):C.Q.normalized(good)
        for bad in ({**good,'sha256':'a'*65},{**good,'extra':'not-a-triple'},{**good,'bytes':-1},{**good,'bytes':0},
                    {**good,'bytes':True},{**good,'bytes':False},{**good,'bytes':3.0},
                    {**good,'path':str(C.ROOT/'inputs/synthetic.bin')},{**good,'path':'/tmp/synthetic.bin'}):
            with self.assertRaises(ValueError):C.data_locator(bad)
        census={s:{'SDF':C.SDF[s],'MOL2':0,'IDs':C.SDF[s]} for s in C.IDS};observed={(s,'SDF'):C.SDF[s] for s in C.IDS}
        F.coverage(census,observed,C.SDF,C.REUSED);self.assertEqual(sum(C.SDF.values()),39633);self.assertEqual(sum(C.NEW.values()),36438)
        bad=dict(observed);bad[('pdbbind_core','SDF')]-=1
        with self.assertRaises(ValueError):F.coverage(census,bad,C.SDF,C.REUSED)
        a=row(0);b=row(1);v=F.aggregate([(a,result(a,[K])),(b,result(b,[L]))]);self.assertEqual(v['physical_record_count'],2)
        self.assertEqual(v['all_observed_full_key_union'],[K,L]);self.assertFalse(v['same_ID_implies_same_graph'])

    def test_success_UNKNOWN_reuse_and_unfinished_claim_never_retry(self):
        reused={11,12};claimed=set();self.assertEqual(F.route(11,reused,claimed),'PROFILE_REUSE');self.assertEqual(F.route(12,reused,claimed),'PROFILE_REUSE')
        self.assertEqual(F.route(13,reused,claimed),'NEW_CALL');claimed.add(13)
        with self.assertRaises(ValueError):F.route(13,reused,claimed)
        with self.assertRaises(ValueError):F.route(11,reused,{11})
        self.assertEqual(C.NEW['pdbbind_core'],0);self.assertEqual(C.REUSED['pdbbind_core'],C.SDF['pdbbind_core'])

    def test_quality_unknown_MOL2_and_native_source_key_axes_stay_separate(self):
        a=row(0);b=row(1);m=row(0,'MOL2');v=F.aggregate([(a,result(a,[K])),(b,result(b,unknown=True)),(m,None)])
        self.assertEqual(v['all_observed_full_key_union'],[K]);self.assertEqual(len(v['unresolved_variant_composition_evidence']),2)
        self.assertFalse(v['MOL2_partial_charge_is_formal_charge']);self.assertFalse(v['automatic_composition_exclusion_for_known_key_entity'])
        self.assertFalse(v['full_or_pool_acceptance'])
        with self.assertRaises(ValueError):F.aggregate([(a,result(a)),(a,result(a))])
        source={'original_native_source':a};native_only=result(a,[K]);observation=F.view_observation(source,native_only,'PROFILE_REUSE',{}, {'wp5_key':lambda k:'literalWP5'})
        self.assertEqual(observation['SMILES_derived_full_keys'],[]);self.assertEqual(observation['all_native_and_source_key_union'],[K])
        self.assertFalse(observation['native_union_missing']);self.assertTrue(observation['missing_full_key']);self.assertEqual(observation['native_result'],native_only)
