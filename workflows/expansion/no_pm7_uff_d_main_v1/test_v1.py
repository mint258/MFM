"""Three synthetic source/seam/order methods;no embed,optimize,QM or DATA read."""
import copy,pathlib,tempfile,unittest
from . import contract as C,source as S,core,closure as X

class Boundaries(unittest.TestCase):
    def test_identity_sampling_large_locator_and_one_mode_independent_claim(self):
        source={'pubchem_version':'release/with:unsafe/path','cid':123,'full_key':'AAAAAAAAAAAAAA-BBBBBBBBBB-C','source_row_sha256':'b'*64}
        mid=C.new_mid(source['pubchem_version'],source['cid'],source['full_key']);self.assertIn(source['pubchem_version'],mid)
        key=C.once('a'*64,'c'*64,source);self.assertRegex(key,r'^[0-9a-f]{64}$')
        self.assertEqual(key,C.once('a'*64,'c'*64,dict(source)))
        self.assertNotEqual(key,C.once('a'*64,'c'*64,{**source,'source_row_sha256':'d'*64}))
        with self.assertRaises(ValueError):C.new_mid('v',True,source['full_key'])
        ref={'path':str(C.BASE/'synthetic_large_DATA.bin'),'bytes':10<<30,'sha256':'e'*64}
        self.assertEqual(C.triple(ref),ref)
        with self.assertRaises(ValueError):C.meta(ref) # small-meta shape rejects BEFORE any DATA open
        ordinals=S.pilot_ordinals();self.assertEqual(len(ordinals),len(set(ordinals)));self.assertEqual(len(ordinals),10000)
        self.assertTrue(all(0<=i<C.EACH for i in ordinals[:5000]));self.assertTrue(all(C.EACH<=i<C.TARGET for i in ordinals[5000:]))
        self.assertEqual(sum(S.selected('compat',i) for i in ordinals[:16]+ordinals[5000:5016]),32)
        from .io import Store,claim_create
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);path=root/(key+'.json');store=Store(root,4<<20)
            claim_create(path,{'once_key':key,'mode_not_in_once':True},store)
            with self.assertRaises(FileExistsError):claim_create(path,{'once_key':key},store)

    def test_original_D_float64_wire_and_missing_stereo_without_PM7(self):
        import numpy as np,torch
        from rdkit import Chem
        _,_,unassigned=core.graph('FC(Cl)Br');self.assertTrue(unassigned)
        _,_,specified=core.graph('F[C@H](Cl)Br');self.assertFalse(specified)
        isotope,_,_=core.graph('[13CH3]O');self.assertEqual(isotope.GetAtomWithIdx(0).GetIsotope(),13)
        template,mol,unresolved=core.graph('CO');self.assertFalse(unresolved);value,shell,flags=core.d20(template)
        self.assertEqual(len(value['values']),20);self.assertEqual(shell.dtype,torch.float64)
        self.assertNotIn('Kappa1',value['names']);z=np.asarray([a.GetAtomicNum() for a in mol.GetAtoms()],dtype='<i8')
        xyz=np.asarray([[0.,0.,0.],[1.4,0.,0.],[-.5,.8,.2],[-.5,-.6,.7],[-.5,-.2,-.9],[1.8,.7,.2]],dtype='<f8')
        d3,issues,wire=core.descriptors({'isomeric_smiles':'CO'},template,mol,z,xyz,shell,flags)
        self.assertFalse(issues);self.assertEqual(np.asarray(value['values'],dtype='<f8').tobytes(),np.asarray(wire['values'],dtype='<f8').tobytes())
        self.assertEqual(set(d3),{'PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2'})
        self.assertEqual(len(d3['SASA_atom_A2']),len(z));self.assertTrue(all(type(v)is float for v in d3['SASA_atom_A2']))
        result={'conformers':[{'coordinates':xyz.tolist(),'D3':d3}]};comp=core.compatibility({'isomeric_smiles':'CO'},template,mol,z,shell,flags,result)
        self.assertTrue(comp['direct_original_D3_functions_vs_original_corrected_base_bits_equal'])
        self.assertFalse(comp['original_PM7_dependent_process_task_equivalence_claimed'])

    def test_original_fallback_three_orders_and_exact_geometry_alias_not_independent(self):
        import numpy as np
        from workflows.data_v1_final.conformers import selection
        xyz=np.asarray([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]],dtype='<f8');z=np.asarray([6,6,8],dtype='<i8')
        candidates=[{'candidate_key':'c'+str(i),'candidate_id':i,'coordinates':(xyz if i<2 else xyz+np.asarray([[0.,0.,0.],[0.,0.,0.],[0.,.01,0.]])).tolist(),'energy':float(i)} for i in range(3)]
        distance=lambda a,b:float(np.sqrt(np.mean((np.asarray(a['coordinates'])-np.asarray(b['coordinates']))**2)))
        chosen=selection.select_fill([],candidates,10,distance,.5);self.assertEqual(len(chosen),3)
        self.assertTrue(all(r['below_dedup_threshold'] for r in chosen[1:]))
        distinct,aliases=core.distinct_selected(chosen,z);self.assertEqual(len(distinct),2);self.assertEqual(len(aliases),1)
        rows=[dict(r,conformer_id=i) for i,r in enumerate(distinct)]
        orders=selection.conformer_orders(rows,distance,'syntheticMID','uff_sprime',C.SEED)
        self.assertTrue(all(sorted(v)==[0,1] for v in orders.values()))
        self.assertEqual(orders['fixed_random'],sorted([0,1],key=lambda i:(selection.stable_key(C.SEED,'syntheticMID','uff_sprime',i),str(i))))
        packed=[]
        for row in rows:
            coords=np.asarray(row['coordinates'],dtype='<f8');packed.append({**row,'geometry_sha256':C.sha(z.tobytes()+coords.tobytes()),'coordinate_sha256':C.sha(coords.tobytes())})
        packet={'conformers':packed,'orders':orders,'order_seed':C.SEED,'atomic_numbers':z.tolist(),'atom_order_sha256':C.sha(z.tobytes())}
        self.assertFalse(X.packet_structure(packet));bad=copy.deepcopy(packet);bad['orders']['energy']=[0,0]
        self.assertIn('ORIGINAL_THREE_ORDER_PERMUTATIONS_UNAVAILABLE_OR_INVALID',X.packet_structure(bad))
        from rdkit import Chem
        mol=Chem.AddHs(Chem.MolFromSmiles('CCCO'));points=np.zeros((mol.GetNumAtoms(),3),dtype='<f8')
        points[:4]=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
        rotation=np.asarray([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
        self.assertLess(core.load()['science'].rmsd(mol,points,points@rotation.T+np.asarray([4.,-2.,3.])),1e-12)
        mirror=points.copy();mirror[:,0]*=-1
        self.assertGreater(core.load()['science'].rmsd(mol,points,mirror),1e-3)

if __name__=='__main__':unittest.main()
