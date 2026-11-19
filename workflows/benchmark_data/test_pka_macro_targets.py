import unittest
from workflows.benchmark_data.pka_macro_targets import endpoint,full_key,strongest

class MacroTargets(unittest.TestCase):
    def test_strongest_means_within_transition_then_acid_minimum_base_maximum(self):
        rows=[dict(transition=s,value=v) for s,v in [('0>>-1',4.),('0>>-1',6.),
              ('-1>>-2',9.),('1>>0',10.),('2>>1',3.)]]
        result=strongest(rows)
        self.assertEqual(result['acid'][:2],(5.,(0,-1)))
        self.assertEqual(result['base'][:2],(10.,(1,0)))

    def test_unknown_transition_is_not_reclassified(self):
        self.assertIsNone(endpoint(None));self.assertIsNone(endpoint((2,0)))
        self.assertEqual(strongest([dict(transition='unknown',value=3.)]),{})

    def test_full_inchikey_keeps_stereochemistry_block(self):
        left=full_key('C[C@H](O)C(=O)O');right=full_key('C[C@@H](O)C(=O)O')
        self.assertEqual(left.split('-')[0],right.split('-')[0])
        self.assertNotEqual(left,right)
        self.assertEqual(full_key('C[C@H](O)C(=O)O',left),left)

if __name__=='__main__':unittest.main()
