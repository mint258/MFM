import unittest
from unittest.mock import patch
from . import ppe_reference_d3 as d

class BoundD3Tests(unittest.TestCase):
    def test_missing_map_stays_explicit_and_never_calls_science(self):
        frame={'record_id':'a','source_reference':'source','source_reference_row':0,
            'binding':{'model_smiles':None,'model_to_reference':None,'issues':['original mapping failed']}}
        with patch.object(d,'geometry_descriptors') as compute:
            result=d.one(frame)
        compute.assert_not_called()
        self.assertEqual(result['state'],'REFERENCE_MAPPING_UNRESOLVED')
        self.assertEqual(result['D3_valid_mask'],[False]*7)

    def test_bound_source_indices_restore_atomic_result(self):
        frame={'record_id':'a','source_reference':'source','source_reference_row':0,
            'atomic_numbers':[8,6,8],'coordinates_A':[[9,0,0],[8,0,0],[7,0,0]],'D20':{'fixture':1},
            'binding':{'model_smiles':'O=C=O','model_to_reference':[2,1,0],'issues':[]}}
        values={k:1. for k in d.SCALARS};values['SASA_atom_A2']=[10.,20.,30.]
        with patch.object(d,'geometry_descriptors',return_value=(values,[])) as compute:
            result=d.one(frame)
        self.assertEqual(result['state'],'D3_READY')
        self.assertEqual(result['SASA_atom_A2'],[30.,20.,10.])
        self.assertEqual(compute.call_args.args[3],[[7,0,0],[8,0,0],[9,0,0]])

if __name__=='__main__':unittest.main()