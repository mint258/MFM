"""Target-free source, electronic-state and descriptor-boundary tests; no xTB call."""
import json
from pathlib import Path
import tempfile
import unittest
from . import worker
from .run import selected_members


class SourceTests(unittest.TestCase):
    def test_xyz_comment_and_extra_atomic_target_column_are_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'qm7_1.xyz'
            path.write_text('2\nnot-a-number target fields are opaque\nH 0 0 0 SECRET\nH 1 0 0 SECRET\n')
            z,coords,smiles=worker.read_xyz(path,'bohr')
            self.assertEqual(z,[1,1]);self.assertIsNone(smiles)
            self.assertAlmostEqual(coords[1][0],0.529177210903)

    def test_sdf_properties_never_reach_graph_parser(self):
        from rdkit import Chem
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'source.sdf'
            block=Chem.MolToMolBlock(Chem.MolFromSmiles('CCO'))
            path.write_text(block+'\n> <PRIVATE_TARGET>\n12345\n\n$$$$\n')
            rows=worker.structure_only_sdf(path)
            self.assertEqual(len(rows),1);self.assertNotIn('PRIVATE_TARGET',rows[0])
            self.assertNotIn('12345',rows[0]);self.assertIn('M  END',rows[0])

    def test_known_charge_and_only_existing_complete_geometry_get_xtb_state(self):
        from rdkit import Chem
        mol=Chem.MolFromSmiles('[NH4+]')
        charge,spin,reason=worker.electronic_state(mol,[7,1,1,1,1],[[0,0,0]]*5)
        self.assertEqual((charge,spin,reason),(1,0,None))
        charge,spin,reason=worker.electronic_state(Chem.MolFromSmiles('CC'),[6,6],[[0,0,0],[1,0,0]])
        self.assertIsNone(spin);self.assertIn('MISSING_H_COORDINATES',reason)
        self.assertEqual(worker.electronic_state(None,[6],[[0,0,0]])[:2],(None,None))

    def test_non_closed_shell_source_is_not_assigned_fake_spin_zero(self):
        from rdkit import Chem
        charge,spin,reason=worker.electronic_state(Chem.MolFromSmiles('[CH3]'),[6,1,1,1],[[0,0,0]]*4)
        self.assertEqual(charge,0);self.assertIsNone(spin);self.assertIn('SPIN',reason)

    def test_record_shards_partition_exactly_and_drop_target_fields(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'members.jsonl'
            path.write_text(''.join(json.dumps({'dataset':'qm9','member_uid':str(i),'source_frame':{},
                'actual_test_score':987654,'label_masks':{'do_not_use':True}})+'\n' for i in range(11)))
            first=list(selected_members(path,shard_index=0,shards=2));second=list(selected_members(path,shard_index=1,shards=2))
            self.assertEqual(sorted([n for n,_ in first+second]),list(range(11)))
            self.assertFalse(set(n for n,_ in first)&set(n for n,_ in second))
            self.assertNotIn('actual_test_score',first[0][1]);self.assertNotIn('label_masks',first[0][1])

    def test_numeric_parser_adaptation_omits_only_legacy_rehash_guard(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'parser.py'
            path.write_text("if True: raise ValueError('FROZEN_PARSER_SOURCE_SHA_DIFFERS')\nVALUE=3\ndef numeric(x):\n    return x*VALUE+1\n")
            module=worker.load_numeric_parser(path)
            self.assertEqual(module.numeric(4),13)

    def test_rdkit_descriptor_names_are_unique_frozen_order_not_a_partial_20(self):
        names=[name for name,_ in worker.descriptor_functions()]
        self.assertEqual(names,sorted(set(names)));self.assertGreaterEqual(len(names),190)
        with self.assertRaisesRegex(ValueError,'UNAVAILABLE'):
            worker.descriptor_functions(['not_an_existing_descriptor'])

    def test_xtb_aggregates_retain_native_values_and_explicit_missing(self):
        values={'energy_Eh':-1.0,'homo_eV':-5.0,'lumo_eV':-2.0,'dipole_Debye':[3.,4.,0.],
            'charges_e':[-0.5,0.5],'D4_atomic_C6_au':None,'D4_atomic_alpha_bohr3':[2.,4.]}
        result=worker.quantum_features(values)
        self.assertEqual(result['gap_eV'],3.0);self.assertEqual(result['dipole_norm_Debye'],5.0)
        self.assertEqual(result['charges_e_sum'],0.0);self.assertEqual(result['charges_e_std'],0.5)
        self.assertIsNone(result['D4_atomic_C6_au_sum'])


if __name__=='__main__':unittest.main()