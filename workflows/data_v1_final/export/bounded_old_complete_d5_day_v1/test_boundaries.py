"""Exactly three actual-CPU synthetic boundaries, no real Source DATA."""
import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from . import contract as C,produce as P
from workflows.data_v1_final.conformers import selection
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import core as Cache

class Boundaries(unittest.TestCase):
    def test_real_random_SQL_native_ID_source_and_no_distance_or_HOF(self):
        import duckdb
        db=duckdb.connect();db.execute('CREATE TABLE native_selected(molecule_id VARCHAR,record_id VARCHAR,source_path VARCHAR,real_index BIGINT)')
        db.execute('CREATE TABLE uff_ids(mid VARCHAR,idx BIGINT,source VARCHAR,physical_row BIGINT)')
        ids=['native:02','native:10','native:01']
        db.executemany('INSERT INTO native_selected VALUES(?,?,?,?)',[('m',r,'/synthetic/native',i) for i,r in enumerate(ids)])
        db.executemany('INSERT INTO uff_ids VALUES(?,?,?,?)',[('m',i,'/synthetic/old.parquet',i) for i in (10,2,1)])
        db.create_function('original_stable_order',lambda mid,source,key:selection.stable_key(20261025,mid,source,key),['VARCHAR','VARCHAR','VARCHAR'],'VARCHAR')
        db.execute(P.BASE_INDEX_SQL)
        for source,keys in (('pm7',ids),('uff_sprime',[10,2,1])):
            ordered=sorted(keys,key=lambda x:(selection.stable_key(20261025,'m',source,x),str(x)))
            rows=db.execute('SELECT native_record_id,sprime_conf_idx,geometry_id FROM base_index WHERE geometry_source=? ORDER BY rank',[source]).fetchall()
            self.assertEqual([r[0] if source=='pm7' else r[1] for r in rows],ordered)
            self.assertEqual([r[2] for r in rows],[P.G.gid(source,'m',key) for key in ordered])
            self.assertEqual(C.random_last('m',source,keys),ordered[-1])
            def no_distance(*a):raise AssertionError('RMSD_MUST_NOT_BE_CALLED')
            self.assertEqual(Cache.geometry_orders([{'conformer_id':x,'energy':None} for x in keys],no_distance,'m',source)['fixed_random'],ordered)
        with self.assertRaises(ValueError):C.random_last('m','pm7',['same','same'])
        db.close()

    def test_original_nested_selection_and_real_child_antijoin_before_first_k(self):
        from workflows.data_v1_final.export.d5_materialize_cpu_v1.produce import originals
        M,_,_,_,_=originals()
        db=sqlite3.connect(':memory:')
        for kind,text in M.SCHEMA.items():db.execute('CREATE TABLE '+kind+'('+text+')')
        for i in range(10):
            mid='m'+str(i);role='TRAIN' if i<8 else 'VAL'
            db.execute('INSERT INTO roles VALUES(?,?,?)',(mid,role,'physical-original-'+str(i)))
            db.execute('INSERT INTO common VALUES(?,1)',(mid,))
            for source in ('pm7','uff_sprime'):
                keys=[mid+':r0',mid+':r1',mid+':r2'] if source=='pm7' else [0,1,2]
                for rank,key in enumerate(sorted(keys,key=lambda k:(selection.stable_key(20261025,mid,source,k),str(k)))):
                    gid=P.G.gid(source,mid,key)
                    db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?)',(gid,mid,source,str(key) if source=='pm7' else None,key if source=='uff_sprime' else None,None,None))
                    db.execute('INSERT INTO orders VALUES(?,?,?,?,?)',(mid,source,'fixed_random',rank,gid))
                    child=gid+':actual-synthetic-child'
                    db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?)',(child,mid,source,None,None,gid,'synthetic-input-bound-child'))
        counts=M.selection(db,20261025,(2,4,6),3,2,2)
        self.assertEqual(counts['train_6'],6)
        self.assertEqual(db.execute('SELECT count(*) FROM diagnostic_base').fetchone()[0],4)
        self.assertEqual(db.execute('SELECT count(*) FROM diagnostic_targets').fetchone()[0],8)
        self.assertEqual(db.execute('SELECT count(*) FROM training_geometry g JOIN diagnostic_targets d USING(geometry_id)').fetchone()[0],0)
        excluded={r[0] for r in db.execute('SELECT geometry_id FROM diagnostic_targets')}
        base=db.execute('SELECT geometry_id FROM diagnostic_base LIMIT 1').fetchone()[0]
        self.assertFalse(C.keep_target({'geometry_id':base,'parent_geometry_id':None},excluded))
        self.assertFalse(C.keep_target({'geometry_id':'unlisted-new-view','parent_geometry_id':base},excluded))
        self.assertTrue(C.keep_target({'geometry_id':'other','parent_geometry_id':'other-parent'},excluded))
        self.assertEqual(C.NESTED,(120000,240000,600000));db.close()

    def test_full_source_inverses_and_float64_geometry_reopen_without_fake_authority(self):
        import pyarrow as pa,pyarrow.parquet as pq
        from . import source_inverse
        proof=source_inverse.proof();self.assertFalse(proof['new_QM_UFF_or_RMSD_HOF_called'])
        self.assertIs(P.G.metadata_children,source_inverse.ORIGINAL_GEOMETRY.metadata_children)
        self.assertIs(P.WORKER.d7,P.G.OriginalWorker.d7)
        schema=P.Wire.schemas()['geometries']
        row={'geometry_id':'synthetic-geometry','molecule_id':'synthetic-mid','geometry_source':'pm7','native_record_id':'native-opaque',
            'sprime_conf_idx':None,'parent_geometry_id':None,'view_id':None,'positions_A':[[-0.0,1.0000000000000002,2.0]],'atomic_numbers':[6],
            'order_energy':None,'atom_order_sha256':'1'*64,'geometry_sha256':'2'*64,'source_provenance_json':'{}'}
        table=pa.Table.from_pylist([row],schema=schema);expected=table.to_pylist()[0]
        with tempfile.TemporaryDirectory(prefix='bounded_D5_synthetic3_') as directory:
            path=Path(directory)/'f64.parquet';pq.write_table(table,path);actual=pq.read_table(path).to_pylist()[0]
            self.assertEqual(P.Wire.encode(actual),P.Wire.encode(expected))
            self.assertEqual(P.Wire.decode(P.Wire.encode(actual)),actual)
        from . import resume
        good={'molecule_id':'m','elements_atomic_numbers':[1,6,8],'heavy_atoms':2,'generic_scaffold':'','scaffold_status':'ACYCLIC'}
        self.assertEqual(resume.feature(good,good),'m')
        with self.assertRaises(ValueError):resume.feature(dict(good,heavy_atoms=3),good)
        with self.assertRaises(ValueError):resume.feature(dict(good,elements_atomic_numbers=[6,6]),good)
        self.assertFalse(resume.needs_work('m',{'m'},{'m'},{'m'}))
        self.assertTrue(resume.needs_work('m',{'m'},{'m'},set()))
        self.assertTrue(resume.needs_work('n',set(),{'m'},set()))
        with tempfile.TemporaryDirectory(prefix='D5_original_locator_') as d:
            target=Path(d)/'native.bin';target.write_bytes(b'synthetic-only-not-native')
            (Path(d)/'sub').mkdir();(Path(d)/'alias').symlink_to(target)
            for path in (target,Path(d)/'sub'/'..'/'native.bin',Path(d)/'alias'):
                pointer={'source_path':str(path),'record_id':'r','molecule_id':'m'}
                self.assertEqual(P.canonical_native_path(pointer).resolve(strict=True),target)
        self.assertNotEqual(C.KEY,'d5_inputs_compound_day_v1')
        self.assertIn('BOUND',C.PLAN);self.assertEqual(len(C.FILES),12)

if __name__=='__main__':unittest.main()
