"""One tiny in-memory source fixture; only toy SQLite is written/copied."""
import copy,json,os,shutil,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import identities as A,local_metadata as L


class LocalMetadataCheck(unittest.TestCase):
    def test_fields_conflicts_transaction_resume_and_shared_authority(self):
        refs={name:{'path':'memory:'+name,'bytes':1} for name in ('members_a','members_b','geometry_a','geometry_b','extra','orders','held')}
        p={'molecule_id':'m','geometry_source':'pm7','native_record_id':'opaque-p','geometry_id':'gp','source_path':'original/native','real_index':17,'unused_pointer_metadata':{'keep':1.125}}
        u={'molecule_id':'m','geometry_source':'uff_sprime','native_record_id':None,'sprime_conf_idx':7,'geometry_id':'gu','source_path':'original/uff','source_row_index':3}
        n={'molecule_id':'n','geometry_source':'pm7','native_record_id':'opaque-n','geometry_id':'gn'}
        extra={'molecule_id':'m','geometry_source':'uff_sprime','native_record_id':None,'sprime_conf_idx':7,'geometry_id':'gd','storage_physical_alias':'diagnostic:gd','diagnostic_only':True,'excluded_from_all_training':True}
        tables={
            'members_a':[{'molecule_id':'m','effective_role':'TRAIN','common_population':True,'unused_large_column':'not projected'}],
            'members_b':[{'molecule_id':'n','effective_role':'FULL','common_population':False,'unused_large_column':'not projected'}],
            'geometry_a':[p,u],'geometry_b':[n],'extra':[extra],
            'orders':[{'molecule_id':'m','pm7_orders_json':'{"fixed_random":["opaque-p"]}'},{'molecule_id':'n','pm7_orders_json':'{"fixed_random":["opaque-n"]}'}],
            'held':[{'molecule_id':'m','geometry_source':'uff_sprime','sprime_conf_idx':7,'geometry_id':'gd'}]}
        common={'membership_tables':[refs['members_a'],refs['members_b']],'physical_geometry_tables':[refs['geometry_a'],refs['geometry_b']]}
        documents={'memory:common':common,'memory:orders':{'order_tables':[refs['orders']]},'memory:d5':{'diagnostic_base_reference':refs['held']}}
        original_load=A.I.load;visits=[];blocked=set();fail=False
        def load(path):return copy.deepcopy(documents[str(path)]) if str(path) in documents else original_load(path)
        def rows(ref,columns=None):
            name=ref['path'].split(':',1)[1]
            if name in blocked:raise AssertionError('committed metadata ref replayed: '+name)
            if name.startswith('members'):self.assertEqual(columns,['molecule_id','effective_role','common_population'])
            visits.append(name)
            for row in copy.deepcopy(tables[name]):yield {k:row[k] for k in columns} if columns else row
            if fail and name=='geometry_b':raise RuntimeError('unit interruption before ref commit')
        copied=[]
        def rsync(argv,check):
            self.assertEqual(argv[:4],['rsync','-a','--sparse','--']);self.assertTrue(check)
            source,destination=map(Path,argv[-2:]);self.assertTrue(destination.name.endswith('.partial'))
            shutil.copyfile(source,destination);copied.append((source,destination))
        def table(index,key,name):
            db=sqlite3.connect(A.database_path(index,key))
            try:return sorted(db.execute('SELECT * FROM '+name).fetchall())
            finally:db.close()
        with tempfile.TemporaryDirectory() as temporary,patch.dict(os.environ):
            root=Path(temporary)
            def plan(name,local=True):
                value={'source_working_root':str(root/name),'common':'memory:common','orders':'memory:orders','d5':'memory:d5','extra_geometry_tables':[refs['extra']]}
                if local:value['metadata_working_root']=str(root/'local')
                return value
            with patch.object(A.I,'load',side_effect=load),patch.object(A,'rows',side_effect=rows),patch.object(L.subprocess,'run',side_effect=rsync):
                baseline=A.prepare(plan('baseline',False));self.assertEqual(copied,[])
                fail=True
                with self.assertRaisesRegex(RuntimeError,'unit interruption'):A.prepare(plan('shared'),geometry_only=True)
                state=original_load(root/'local/shared/geometry_identities.build.json')
                db=sqlite3.connect(state['physical_path'])
                try:
                    self.assertEqual(db.execute("SELECT count(*) FROM geometries WHERE gid='gn'").fetchone()[0],0)
                    self.assertIsNone(db.execute("SELECT 1 FROM build_progress WHERE stage='geometry_ordinary' AND ref_ordinal=1").fetchone())
                finally:db.close()
                fail=False;blocked={'members_a','members_b','geometry_a'}
                actual=A.prepare(plan('shared'))
                self.assertEqual(actual['selected_molecules'],baseline['selected_molecules'])
                self.assertEqual(actual['expected_conformers'],baseline['expected_conformers'])
                for name in ('members','geometries'):self.assertEqual(table(actual,'database',name),table(baseline,'database',name))
                for name in ('orders','held'):self.assertEqual(table(actual,'orders_database',name),table(baseline,'orders_database',name))
                self.assertEqual(table(actual,'orders_database','held'),[('uff_sprime','m','diagnostic:gd')])
                pointer=json.loads(next(row[-1] for row in table(actual,'database','geometries') if row[3]=='gp'))
                self.assertEqual(pointer,p)
                self.assertEqual(len(copied),2)
                for key in ('database','orders_database'):
                    self.assertTrue(actual[key]['path'].startswith(str(root/'shared')))
                    self.assertTrue(A.database_path(actual,key).startswith(str(root/'local')))
                persisted=original_load(root/'shared/identities.json');self.assertNotIn(L.RUNTIME_KEY,persisted)
                blocked=set(tables)
                restored=A.prepare(plan('shared'))
                self.assertEqual(restored,actual);self.assertEqual(len(copied),2)
                Path(A.database_path(actual)).unlink()
                fallback=A.prepare(plan('shared'));self.assertEqual(A.database_path(fallback),fallback['database']['path'])
                self.assertTrue(Path(fallback['database']['path']).is_file())
                blocked=set()
                for name,row,message in (
                    ('bad_gid',dict(n,geometry_id='gp'),'GEOMETRY_ID_OWNER_CONFLICT'),
                    ('bad_physical',dict(p,geometry_id='other-gid'),'PHYSICAL_ID_GEOMETRY_ALIAS_DIFFERS')):
                    prior=tables['geometry_b'];tables['geometry_b']=[row]
                    try:
                        with self.assertRaisesRegex(ValueError,message):A.prepare(plan(name),geometry_only=True)
                    finally:tables['geometry_b']=prior

        # Actual publisher shape: typed F64 geometry and original N1 declarations
        # in metadata_json. Exercise owned G.physical, with only a memory Arrow row.
        from types import SimpleNamespace
        import numpy as np,pyarrow as pa
        from . import physical as G
        metadata={'molecule_id':'n1-mid','geometry_id':'n1-gid','sprime_conf_idx':8,'geometry_source':'uff_sprime',
                  'status':'SUCCESS','converged':True,'source_record_id':'actual-native-anchor',
                  'ordinary_sprime_member':False,'usage_domain':'pprime_extra','atom_order_sha256':'existing-witness'}
        typed={'molecule_id':'n1-mid','geometry_id':'n1-gid','sprime_conf_idx':8,'atomic_numbers':[6,1],
               'coordinates':[[0.,-0.,1.125],[1.,0.,0.]],'metadata_json':json.dumps(metadata)}
        pointer={'molecule_id':'n1-mid','geometry_id':'n1-gid','source_format':'parquet','source_path':'memory:n1-typed',
                 'source_row_index':0,'accepted_component_kind':'CURRENT_CANONICAL_N1_PHYSICAL_ACCEPTED'}
        current=[typed]
        class Parquet:
            num_row_groups=1
            metadata=SimpleNamespace(row_group=lambda _:SimpleNamespace(num_rows=1))
            def __init__(self,filename,**kwargs):self_outer.assertEqual(filename,'memory:n1-typed')
            def iter_batches(self,**kwargs):yield pa.RecordBatch.from_pylist([current[0]])
            def close(self):pass
        self_outer=self
        with patch('pyarrow.parquet.ParquetFile',Parquet):
            before=copy.deepcopy(typed);declared,xyz=G.physical(pointer)
            self.assertEqual(typed,before);self.assertEqual(declared['source_record_id'],'actual-native-anchor')
            self.assertIs(declared['ordinary_sprime_member'],False);self.assertEqual(declared['usage_domain'],'pprime_extra')
            self.assertEqual(xyz.dtype,np.dtype('<f8'));self.assertEqual(xyz.tobytes(),np.asarray(typed['coordinates'],dtype='<f8').tobytes())
            for state in (False,None):
                current[0]=dict(typed,metadata_json=json.dumps(dict(metadata,converged=state)))
                with self.assertRaisesRegex(ValueError,'GEOMETRY_NOT_ACTUALLY_USABLE'):G.physical(pointer)
            current[0]=dict(typed,source_record_id='conflicting-anchor')
            with self.assertRaisesRegex(ValueError,'LEGACY_GEOMETRY_METADATA_CONFLICT'):G.physical(pointer)
            current[0]=typed
            with self.assertRaisesRegex(ValueError,'N1_EXTRA_CANNOT_BECOME_ORDINARY'):G.physical(dict(pointer,usage_domain='ordinary'))

if __name__=='__main__':unittest.main()