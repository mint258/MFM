"""Exactly three synthetic/source boundaries; no Parquet, LMDB, QM or tempdirs."""
import copy,sqlite3,unittest
from . import contract as C
from .produce import originals
from .readback import same_value


def selection_fixture():
    M,_,_,_,_=originals();db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    for kind,definition in M.SCHEMA.items():db.execute('CREATE TABLE '+kind+'('+definition+')')
    for mid in ('train-a','train-b','train-c','train-n1','val-a','val-b'):
        role='VAL' if mid.startswith('val') else 'TRAIN'
        db.execute('INSERT INTO roles VALUES(?,?,?)',(mid,role,'FULL' if role=='VAL' else 'TRAIN'))
        db.execute('INSERT INTO common VALUES(?,1)',(mid,))
        for src in ('pm7','uff_sprime'):
            n=1 if mid=='train-n1' else 2
            ids=[]
            for rank in range(n):
                gid=mid+':'+src+':'+str(rank);ids.append(gid)
                native=mid+':native:'+str(rank) if src=='pm7' else None;idx=None if src=='pm7' else 10+rank*10
                base=(gid,mid,src,native,idx,None,None)
                db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?)',base)
                for view in ('actual-gradient','actual-other-child'):
                    db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?)',(gid+':'+view,mid,src,native,idx,gid,view))
            for kind in ('fixed_random','energy','diversity'):
                ordered=ids if kind=='fixed_random' else list(reversed(ids))
                for rank,gid in enumerate(ordered):db.execute('INSERT INTO orders VALUES(?,?,?,?,?)',(mid,src,kind,rank,gid))
    db.commit();return db


class Boundaries(unittest.TestCase):
    def test_01_missing_actual_parents_never_create_stage_or_small_limit_large_DATA(self):
        r={'path':'/absolute/authority.parquet','bytes':12<<30,'sha256':'a'*64}
        self.assertEqual(C.reference(r)['bytes'],12<<30)
        for size in (True,False,0,-1):
            bad={**r,'bytes':size}
            with self.assertRaises(ValueError):C.reference(bad)
        bad={**r,'sha256':'a'*65}
        with self.assertRaises(ValueError):C.reference(bad)
        empty={**r,'bytes':0,'sha256':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
        self.assertEqual(C.reference(empty,source=True)['bytes'],0)
        value=C.pending({'mode':'materialize','parent_references':{},'seed':None})
        self.assertEqual(value['status'],'NONEXECUTABLE_PENDING_ACTUAL_PARENTS')
        self.assertFalse(value['stage_spec_generated']);self.assertFalse(value['D5_jointly_frozen'])
        self.assertIn('N1_policy',value['missing_parents']);self.assertIn('order_manifest',value['missing_parents'])
        self.assertIn('independently_reviewed_fixed_seed',value['missing_parents'])
        with self.assertRaises(ValueError):C.unique([r,{**r,'sha256':'b'*64}])

    def test_02_original_selection_keeps_seen_MID_excludes_both_held_bases_and_all_children(self):
        M,_,I,_,_=originals();db=selection_fixture()
        try:
            result=M.selection(db,2711,(2,3,4),1,1,1)
            self.assertEqual(result['pilot_train'],1);self.assertEqual(result['pilot_val'],1)
            self.assertEqual(I.scalar(db,'SELECT count(*) FROM diagnostic_targets'),6)
            selected=db.execute('SELECT molecule_id FROM diagnostic_molecules').fetchone()[0]
            self.assertNotEqual(selected,'train-n1')
            self.assertEqual(I.scalar(db,"SELECT count(*) FROM subset_members WHERE subset='train_all' AND molecule_id=?",(selected,)),1)
            self.assertEqual(I.scalar(db,'SELECT count(*) FROM training_geometry g JOIN diagnostic_targets d ON g.geometry_id=d.geometry_id OR g.parent_geometry_id=d.geometry_id'),0)
            self.assertEqual(I.scalar(db,"SELECT count(*) FROM training_orders WHERE molecule_id=? AND order_type='energy' AND rank=1 AND training_rank=0",(selected,)),2)
            self.assertEqual(I.scalar(db,"SELECT count(*) FROM subset_members WHERE subset='pilot_train' AND molecule_id NOT IN(SELECT molecule_id FROM subset_members WHERE subset='train_2')"),0)
        finally:db.close()

    def test_03_original_codec_pins_projection_identity_and_typed_lossless_readback(self):
        C.original_source_check();M,V,I,_,P=originals()
        self.assertIs(V.baseline,M);self.assertIs(V._BASE_VALIDATE,M.validate)
        self.assertTrue(M.selection.__code__.co_filename.endswith('/pipeline_v1/materialize.py'))
        db=selection_fixture()
        try:
            M.selection(db,2711,(2,3,4),1,1,1);mid=db.execute('SELECT molecule_id FROM diagnostic_molecules').fetchone()[0]
            geometry=[dict(r) for r in db.execute('SELECT * FROM training_geometry WHERE molecule_id=?',(mid,))]
            orders=[dict(r) for r in db.execute('SELECT * FROM training_orders WHERE molecule_id=?',(mid,))]
            exclusion=[dict(r) for r in db.execute('SELECT * FROM diagnostic_targets WHERE molecule_id=?',(mid,))]
            args={'effective_role':'TRAIN','training_geometries':geometry,'training_orders':orders,'diagnostic_targets':exclusion,
                'native_atom_counts':{r['geometry_id']:4 for r in geometry if r['parent_geometry_id'] is None},
                'group_mask':{'S':False,'D':False,'P':False},'family_mask':{'audit':False}}
            value=P.project_training_sources(mid,**args)
            self.assertEqual(set(value['source_entries']),{'pm7','uff_sprime'})
            for source,entry in value['source_entries'].items():
                expected=next(r['geometry_id'] for r in orders if r['geometry_source']==source and r['order_type']=='energy' and r['training_rank']==0)
                self.assertEqual(entry['minimum_energy_conformer_id'],expected)
            bad=copy.deepcopy(args);bad['effective_role']='VAL'
            with self.assertRaises(ValueError):P.project_training_sources(mid,**bad)
            self.assertFalse(same_value(0.0,-0.0));self.assertFalse(same_value(False,0));self.assertTrue(same_value(None,None))
        finally:db.close()

if __name__=='__main__':unittest.main()
