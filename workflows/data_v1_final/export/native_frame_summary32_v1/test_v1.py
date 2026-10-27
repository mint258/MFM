"""Three pure retained-codec/native-slot/tensor-order boundaries, no filesystem."""
import json,math,struct,unittest
from workflows.data_v1_final.export.native_body_frame32_v1 import reader as D,observe as O
from . import contract as C,reader as I,analysis as A


class Boundaries(unittest.TestCase):
    def test_original_lossless_f64_signature_and_undeclared_DATA_fail_before_open(self):
        data=D.scientific_bytes({'signed_zero':-0.,'nan':float('nan'),'tuple':(1,'literal')})
        value=I.decode_evidence(data)
        self.assertEqual(struct.pack('<d',value['signed_zero']).hex(),'0000000000000080');self.assertTrue(math.isnan(value['nan']))
        self.assertEqual(value['tuple'],(1,'literal'))
        corrupted=json.loads(data);corrupted['values_float64_bits_little_endian'][0]='0000000000000000'
        with self.assertRaisesRegex(ValueError,'SCIENTIFIC_TREE_FULL_BIT_SIGNATURE'):I.decode_evidence(json.dumps(corrupted).encode())
        ref={'path':'/never_open_undeclared_retained_native_DATA','bytes':1,'sha256':'a'*64}
        with self.assertRaisesRegex(ValueError,'DECLARED_BEFORE_ANY_OPEN'):I.read(ref,[],lambda:None,8<<20)
        for n in (True,0,-1):
            with self.assertRaises(ValueError):C.triple({**ref,'bytes':n})

    def test_double_channel_native_print_slots_preserve_onsite_duplicates_without_AO_mapping(self):
        text='SIGMA-PI BOND-ORDER MATRIX\n S-SIGMA P-SIGMA\n S-SIGMA C 1 1.00\n P-SIGMA C 1 2.00 3.00\n P-SIGMA C 1 2.00 3.00\nTOTAL ENERGY PARTITIONING\n'
        keys,rows=A.basis_indices(text);old=O.sigma_tokens(text)
        self.assertEqual(keys,[(0,'S-SIGMA'),(0,'P-SIGMA')]);self.assertEqual(len(rows),5)
        self.assertEqual([r['entry_ordinal'] for r in rows],list(range(5)))
        self.assertEqual([r['source_native_row_basis_slot'] for r in rows],[0,1,1,1,1])
        self.assertEqual([r['source_native_column_basis_slot'] for r in rows],[0,0,1,0,1])
        self.assertTrue(all(r['atom_i']==r['atom_j']==0 and r['AO_index_or_global_xyz_map'] is False for r in rows))
        self.assertEqual(len({(r['atom_i'],r['atom_j'],r['basis_i'],r['basis_j']) for r in rows}),3)
        self.assertEqual([r['native_numeric_token'] for r in rows],[r['native_numeric_token'] for r in old])
        self.assertEqual([r['source_line'] for r in rows],[r['source_line'] for r in old])

    def test_six_component_native_trace_and_printed_zero_never_become_physical_acceptance(self):
        names=['xx','xy','yy','xz','yz','zz'];numbers=['1.001','0.000','2.002','0.000','0.000','-3.003']
        rows=[{'component':c,'native_numeric_token':n} for c,n in zip(names,numbers)]
        observed=A.trace(rows,float)
        self.assertTrue(observed['native_decimal_trace_exactly_zero']);self.assertEqual(observed['native_decimal_trace_numerator'],'0')
        self.assertTrue(observed['no_trace_subtraction_or_tensor_projection_performed'])
        self.assertTrue(observed['trace_is_descriptive_no_new_tolerance_or_physical_acceptance'])
        with self.assertRaisesRegex(ValueError,'SIX_SEQUENCE'):A.trace(rows[:5],float)
        wrong=[rows[0],rows[2],rows[1],*rows[3:]]
        with self.assertRaisesRegex(ValueError,'SIX_SEQUENCE'):A.trace(wrong,float)
        invalid=[dict(r) for r in rows];invalid[0]['native_numeric_token']='1E10000'
        with self.assertRaisesRegex(ValueError,'EXPONENT'):A.trace(invalid,float)
