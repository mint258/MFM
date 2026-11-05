"""Eight synthetic boundaries; no actual LMDB/Parquet/task/packet body reads."""
import json,pathlib,unittest
from . import contract as C,inheritance as H,core


class CacheBoundaries(unittest.TestCase):
    def test_source_bytes_ast_and_original_helpers(self):
        self.assertEqual(H.proof()['status'],'EXACT_FROZEN_FUNCTION_BYTES_AND_AST_INHERITED')
        source=(C.PROFILE/'run_profile.py').read_text();current=pathlib.Path(core.__file__).read_text()
        with self.assertRaisesRegex(ValueError,'FUNCTION_BYTES_OR_AST_CHANGED'):H.prove_functions(source,current.replace('threshold=0.5','threshold=0.4'))

    def test_0p5_boundary_and_explicit_greedy_order_dependence(self):
        rows=[dict(conformer_id=k,coordinate=x,energy=0) for k,x in (('a',0),('b',.5),('c',.49))]
        distance=lambda left,right:abs(left['coordinate']-right['coordinate'])
        self.assertEqual(core.unique_representatives(rows,['a','b','c'],distance),['a','b'])
        self.assertEqual(core.unique_representatives(rows,['c','b','a'],distance),['c'])

    def test_missing_hof_keeps_geometry_random_not_zero(self):
        rows=[dict(conformer_id='native:A',energy=None),dict(conformer_id='native:B',energy=0)]
        orders=core.geometry_orders(rows,lambda a,b:1,'m','pm7')
        self.assertEqual(set(orders['fixed_random']),{'native:A','native:B'});self.assertIsNone(orders['energy']);self.assertIsNone(orders['diversity'])
        missing=C.missing_hof('UNVERIFIED');C.validate_hof(missing)
        with self.assertRaisesRegex(ValueError,'NO_FAKE_ZERO'):C.validate_hof(dict(missing,value_kcal_mol=0))

    def test_native_record_random_order_is_input_population_independent(self):
        rows=[dict(conformer_id=k,energy=i) for i,k in enumerate(('lmdb:2','lmdb:20','lmdb:1'))]
        a=core.geometry_orders(rows,lambda a,b:1,'m','pm7');b=core.geometry_orders(list(reversed(rows)),lambda a,b:1,'m','pm7')
        self.assertEqual(a,b)
        expected=sorted((r['conformer_id'] for r in rows),key=lambda k:(core.SELECTION.stable_key(20261025,'m','pm7',k),str(k)))
        self.assertEqual(a['fixed_random'],expected)

    def test_original_proper_kabsch_no_reflection_or_permutation(self):
        import numpy as np
        from rdkit import Chem
        pc=H.profile_common();science=pc.IO.load_science({'science_source_pins':[C.SCIENCE_SOURCE,C.SCIENCE_PREPARE]})
        mol=Chem.RWMol()
        for _ in range(4):mol.AddAtom(Chem.Atom(6))
        xyz=np.array([[0,0,0],[1.2,0,0],[.2,1.4,0],[.3,.4,1.7]],dtype=np.float64)
        rotation=np.array([[0,-1,0],[1,0,0],[0,0,1]],dtype=np.float64)
        self.assertLess(science.rmsd(mol,xyz,xyz@rotation+11),1e-12)
        mirror=xyz.copy();mirror[:,0]*=-1
        self.assertGreater(science.rmsd(mol,xyz,mirror),.01)
        self.assertGreater(science.rmsd(mol,xyz,xyz[[1,0,2,3]]),.01)

    def test_selected_software_bound_does_not_rewrite_N_or_membership(self):
        row=C.software_bound(301,10);self.assertTrue(row['status'].startswith('PENDING'));self.assertEqual(row['records'],301)
        self.assertFalse(row['scientific_N_truncated']);self.assertFalse(row['replacement_member_selected'])
        rows=[dict(molecule_id=str(i)) for i in range(256)]
        self.assertEqual(C.pick_golden(rows),C.pick_golden(list(reversed(rows))));self.assertEqual(len(C.pick_golden(rows)),16)
        with self.assertRaises(ValueError):C.pick_golden(rows[:-1]+[rows[0]])

    def test_frozen_canonical_scalar_qc_and_no_native_fallback(self):
        pc=H.profile_common();row=dict(values=[dict(registry_id=60,kind=1,f64=0)],calc_type='pm7_B',status='PROPERTY_FAILED',
            numeric_issues=[],converged=None,energy_raw=-999999)
        actual=pc.decode_hof(row);self.assertTrue(actual['valid']);self.assertEqual(actual['value_kcal_mol'],0);self.assertTrue(actual['convergence_null_review'])
        self.assertFalse(pc.decode_hof(dict(row,converged=False))['valid'])
        absent=pc.decode_hof(dict(row,values=[]));self.assertFalse(absent['valid']);self.assertIsNone(absent['value_kcal_mol'])
        self.assertEqual(absent['reason'],'HOF_CELL_ABSENT')

    def test_original_float64_geometry_sha_survives_json_and_tracks_atom_order(self):
        pc=H.profile_common();z=[6,1];xyz=[[-0.0,1.125,2.5],[3,4,5]]
        digest=pc.IO.geometry_sha(z,xyz);self.assertEqual(digest,pc.IO.geometry_sha(z,json.loads(json.dumps(xyz))))
        self.assertNotEqual(digest,pc.IO.geometry_sha(list(reversed(z)),xyz))
        other=[list(row) for row in xyz];other[0][0]=0.0;self.assertNotEqual(digest,pc.IO.geometry_sha(z,other))
