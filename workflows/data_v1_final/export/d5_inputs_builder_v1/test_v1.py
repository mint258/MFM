"""Three new source/synthetic boundaries, no source corpus/LMDB/native call."""
import copy,json,pathlib,unittest
from . import contract as C,geometry as G,build as B


class Boundaries(unittest.TestCase):
    def test_native_source_physical_identity_not_rank_or_equal_coordinate_clone(self):
        p={'molecule_id':'m','geometry_id':'opaque-p','geometry_source':'pm7','native_record_id':'native:r9','sprime_conf_idx':None}
        u={'molecule_id':'m','geometry_id':'opaque-u','geometry_source':'uff_sprime','native_record_id':'anchor-provenance','sprime_conf_idx':42}
        self.assertEqual(G.physical_key(p),('pm7','m','native:r9'));self.assertEqual(G.physical_key(u),('uff_sprime','m',42))
        self.assertEqual(G.physical_key(dict(u,native_record_id='another-anchor')),G.physical_key(u))
        for bad in (True,False,-1,2**63,'42'):
            with self.assertRaises(ValueError):G.physical_key(dict(u,sprime_conf_idx=bad))
        with self.assertRaises(ValueError):G.physical_key(dict(p,sprime_conf_idx=0))
        first=G.child_identity(u,'actual-record','xtb_perturbed_gradient','actual-execution','a'*64)
        second=G.child_identity(dict(u,geometry_id='another-real-parent'),'actual-record','xtb_perturbed_gradient','actual-execution','a'*64)
        self.assertNotEqual(first[0],second[0]);self.assertNotEqual(first[1],'pprime_parent_expanded_v1')
        ref={'path':'/actual/large-source.parquet','bytes':12<<30,'sha256':'b'*64}
        self.assertEqual(C.reference(ref)['bytes'],12<<30)
        with self.assertRaises(ValueError):C.reference(dict(ref,bytes=True))
        value={'f64':[-0.0,1.0+2**-52],'physical_idx':42,'flag':False}
        restored=B.decode(B.encode(value));self.assertEqual(restored['f64'][0].hex(),'-0x0.0p+0');self.assertIs(restored['flag'],False)
        self.assertFalse(C.pending({'mode':'final','purpose':'full'})['stage_spec_generated'])

    def test_real_parent_all_child_antijoin_stays_original_selection_before_ranking(self):
        from workflows.data_v1_final.export.d5_materialize_cpu_v1.test_boundaries import selection_fixture
        from workflows.data_v1_final.export.d5_materialize_cpu_v1.produce import originals
        M,_,I,_,_=originals();db=selection_fixture()
        try:
            M.selection(db,2711,(2,3,4),1,1,1)
            mid=db.execute('SELECT molecule_id FROM diagnostic_molecules').fetchone()[0]
            self.assertNotEqual(mid,'train-n1')
            self.assertEqual(I.scalar(db,'SELECT count(*) FROM diagnostic_targets'),6)
            self.assertEqual(I.scalar(db,'SELECT count(*) FROM training_geometry g JOIN diagnostic_targets d ON g.geometry_id=d.geometry_id OR g.parent_geometry_id=d.geometry_id'),0)
            self.assertEqual(I.scalar(db,"SELECT count(*) FROM training_orders WHERE molecule_id=? AND order_type='energy' AND rank=1 AND training_rank=0",(mid,)),2)
            self.assertEqual(I.scalar(db,"SELECT count(*) FROM subset_members WHERE subset='train_all' AND molecule_id=?",(mid,)),1)
        finally:db.close()

    def test_three_orders_call_true_original_selection_kabsch_seed_and_dual_columns(self):
        refs=C.source_check();native,science,_=G.originals(initialize=False)
        self.assertEqual(pathlib.Path(G.SEL.conformer_orders.__code__.co_filename),pathlib.Path(refs['selection']['path']))
        self.assertEqual(pathlib.Path(native.rmsd.__code__.co_filename),pathlib.Path(refs['proper_Kabsch']['path']))
        self.assertEqual(pathlib.Path(science.seed_for.__code__.co_filename),pathlib.Path(refs['science']['path']))
        self.assertNotEqual(science.seed_for('synthetic',False),science.seed_for('synthetic',True))
        from rdkit import Chem
        mol=Chem.MolFromSmiles('CO');bases=[]
        for source in ('pm7','uff_sprime'):
            for i,idx in enumerate((9,42,107)):
                bases.append({'molecule_id':'synthetic','geometry_source':source,'geometry_id':source+':'+str(idx),
                    'native_record_id':'r'+str(idx) if source=='pm7' else None,'sprime_conf_idx':idx if source=='uff_sprime' else None,
                    'parent_geometry_id':None,'view_id':None,'order_energy':float(2-i),
                    'positions_A':[[0.0,0.0,0.0],[float(i+1),0.0,0.0]]})
        result=G.order_rows('synthetic',bases,mol,native)
        self.assertEqual(len(result),18)
        for source in ('pm7','uff_sprime'):
            subset=[r for r in bases if r['geometry_source']==source]
            ids=[r['native_record_id'] if source=='pm7' else r['sprime_conf_idx'] for r in subset]
            expected=sorted(ids,key=lambda key:(G.SEL.stable_key(20261025,'synthetic',source,key),str(key)))
            actual=[r['geometry_id'] for r in result if r['geometry_source']==source and r['order_type']=='fixed_random']
            by={G.physical_key(r)[2]:r['geometry_id'] for r in subset};self.assertEqual(actual,[by[k] for k in expected])
            for kind in ('fixed_random','energy','diversity'):
                rows=[r for r in result if r['geometry_source']==source and r['order_type']==kind]
                self.assertEqual([r['rank'] for r in rows],[0,1,2]);self.assertEqual({r['geometry_id'] for r in rows},set(by.values()))
                self.assertTrue(all(r['method']==r['order_type'] for r in rows))
            self.assertEqual(next(r['geometry_id'] for r in result if r['geometry_source']==source and r['order_type']=='energy' and r['rank']==0),source+':107')
            self.assertEqual(next(r['geometry_id'] for r in result if r['geometry_source']==source and r['order_type']=='diversity' and r['rank']==0),source+':107')


if __name__=='__main__':unittest.main()
