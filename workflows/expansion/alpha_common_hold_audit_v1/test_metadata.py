"""Two exact metadata diagnostics, without RDKit or production data."""
import unittest
from .core import diagnose


def variant(name,smiles='C',key='key1',**features):
    return dict(phase='GRAPH_RESULT',variant_id=name,status='FEATURES_DERIVED',
      features=dict(isomeric_smiles=smiles,full_key=key,source_smiles=name,cid=None,ordinal=0,**features))


def reduction(reasons):return dict(phase='MID_REDUCTION',status='HOLD',hold_reasons=reasons,strict5_projection=None)


class Metadata(unittest.TestCase):
    def test_same_canonical_exact_float_and_ring_order_diagnosed(self):
        a=variant('v1',molecular_weight_Da=30.1,generic_ring_systems=['b','a'])
        b=variant('v2',molecular_weight_Da=30.100000000000005,generic_ring_systems=['a','b'])
        result=diagnose([a,b,reduction(['SAME_GRAPH_FEATURE_VALUES_DISAGREE'])])
        self.assertTrue(result['same_canonical_pair'])
        differences=result['exact_feature_field_differences']
        self.assertEqual(set(differences),{'molecular_weight_Da','generic_ring_systems'})
        floats=differences['molecular_weight_Da']['variants']
        self.assertNotEqual(floats[0]['binary64_hex'],floats[1]['binary64_hex'])
        self.assertTrue(differences['generic_ring_systems']['same_multiset_despite_order_difference'])
        self.assertTrue(result['reduced_projection_remains_HOLD'])
        self.assertFalse(result['graph_selected']);self.assertFalse(result['tolerance_introduced'])

    def test_true_graph_and_unresolved_remain_separate_and_held(self):
        a=variant('v1');b=variant('v2',smiles='N',key='key2')
        missing=dict(phase='GRAPH_RESULT',variant_id='v3',status='FEATURE_COMPUTE_UNRESOLVED',features=None,error={'type':'synthetic'})
        result=diagnose([a,b,missing,reduction(['MULTIPLE_LEGITIMATE_CANONICAL_GRAPHS_OR_FULL_KEYS','ONE_OR_MORE_SOURCE_GRAPH_VARIANTS_UNRESOLVED'])])
        self.assertEqual(len(result['distinct_canonical_isomeric_SMILES_fullkey_pairs']),2)
        self.assertEqual(result['unresolved_variants'],1)
        self.assertFalse(result['same_canonical_pair']);self.assertFalse(result['strict5_projection_created'])
        self.assertEqual(result['graph_variant_results'],[a,b,missing])
        with self.assertRaises(ValueError):diagnose([a])


if __name__=='__main__':unittest.main()
