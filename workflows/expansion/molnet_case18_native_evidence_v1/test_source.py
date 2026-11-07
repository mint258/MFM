"""Small stdlib fixtures for source grouping and exact bound field bytes."""
import hashlib
import unittest
from .parse import atom_groups,cif,formula_field,exact


class SourceTests(unittest.TestCase):
    def row(self,seq,atom,element='C',alt='.',model='1',chain='D'):
        return dict(label_entity_id='2',label_asym_id=chain,auth_asym_id='P',label_seq_id=str(seq),
            label_comp_id='PHE',label_atom_id=atom,label_alt_id=alt,type_symbol=element,
            pdbx_PDB_model_num=model,_source_line1=1)

    def test_shared_alternatives_and_models_are_never_summed(self):
        rows=[self.row(1,'CA'),self.row(1,'CB',alt='A'),self.row(1,'CB',alt='B'),
              self.row(1,'CA',model='2'),self.row(1,'CB',model='2',alt='A')]
        observed=atom_groups(rows,{'1':'PHE'})
        self.assertEqual([(x['model'],x['alternative'],x['observed_nonH_sites']) for x in observed],
                         [('1','A',2),('1','B',2),('2','A',2)])
        self.assertTrue(all(x['shared_dot_counted_once'] for x in observed))
        with self.assertRaisesRegex(ValueError,'UNIQUE_SITES'):
            atom_groups(rows+[self.row(1,'CA')],{'1':'PHE'})

    def test_incomplete_atoms_and_cif_width_remain_explicit(self):
        observed=atom_groups([self.row(1,'CA')],{'1':'PHE'})[0]
        self.assertFalse(observed['all_seven_declared_residue_positions_observed'])
        self.assertFalse(observed['observed59_nonH_and_seven_positions'])
        self.assertFalse(observed['complete_chemical_graph_claimed'])
        _,tables,_=cif(b'data_X\nloop_\n_entity_poly.entity_id\n_entity_poly.type\n2 "loop_"\n')
        self.assertEqual(tables['_entity_poly'][0]['type'],'loop_')
        with self.assertRaisesRegex(ValueError,'COMPLETE_CIF_LOOP_ROWS'):
            cif(b'data_X\nloop_\n_entity_poly.entity_id\n_entity_poly.type\n2\n')

    def test_whole_formula_field_not_prefix_or_first_line_only(self):
        raw=b'title\n> <MOLECULAR_FORMULA>\nC36H51N11O12\n\n$$$$\n'
        observed=formula_field(raw)
        self.assertEqual(observed['whole_value'],'C36H51N11O12')
        for wrong in [raw.replace(b'O12',b'O120'),raw.replace(b'O12\n',b'O12\nUNEXPECTED\n'),
                      raw.replace(b'$$$$',b'> <MOLECULAR_FORMULA>\nC36H51N11O12\n\n$$$$')]:
            with self.assertRaisesRegex(ValueError,'EXACT_WHOLE_FORMULA'):formula_field(wrong)

    def test_binding_rejects_wrong_whole_hash_or_length(self):
        raw=b'captured official evidence\n';ref=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(exact(raw,ref),raw)
        for bad in [dict(ref,bytes=len(raw)-1),dict(ref,sha256='0'*64)]:
            with self.assertRaisesRegex(ValueError,'EXACT_BOUND_BYTES_AND_SHA'):exact(raw,bad)


if __name__=='__main__':unittest.main()
