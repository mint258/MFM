"""Final population retains real exhausted shortfalls without promoting unknowns."""
import unittest
from .run import original_membership_functions
from .finalize import final_member


class FinalMemberTests(unittest.TestCase):
    def setUp(self):
        self.membership,_=original_membership_functions()
        self.row={'molecule_id':'short','effective_role':'TRAIN','S_usable_conformers':3,
            'S_conformers':3,'records':3,'Sprime_status':'INSUFFICIENT_CONVERGED_CANDIDATES',
            'merged_uff_count':1,'fill_status':'INSUFFICIENT_CONVERGED_CANDIDATES',
            'common_population':False,'elements_atomic_numbers':[1,6]}
        self.state={'status':'EXHAUSTED_N_NO_NEW','source_valid':True,'insufficient':True,
            'final_unique_count':1,'consecutive_no_new':3}

    def test_real_exhaustion_retains_actual_shortfall(self):
        result=final_member(self.row,self.state,self.membership)
        self.assertTrue(result['common_population'])
        self.assertEqual(result['merged_uff_count'],1)
        self.assertTrue(result['Sprime_insufficient'])
        self.assertFalse(result['complete_Sprime_for_D5'])

    def test_unproven_or_unknown_not_promoted(self):
        with self.assertRaisesRegex(ValueError,'UNPROVEN'):
            final_member(self.row,dict(self.state,consecutive_no_new=2),self.membership)
        result=final_member(self.row,dict(self.state,status='EXECUTION_UNRESOLVED',source_valid=False,final_unique_count=None),self.membership)
        self.assertFalse(result['common_population'])
        self.assertIn('EXECUTION_UNRESOLVED',result['exclusion_reasons'])

    def test_unsupported_and_other_pm7_reasons_remain(self):
        result=final_member(dict(self.row,Sprime_status='UFF_UNSUPPORTED'),self.state,self.membership)
        self.assertFalse(result['common_population'])
        self.assertIn('UFF_UNSUPPORTED',result['exclusion_reasons'])
        result=final_member(dict(self.row,S_usable_conformers=2),self.state,self.membership)
        self.assertFalse(result['common_population'])
        self.assertIn('INCOMPLETE_PM7_GEOMETRY_OR_IDENTITY',result['exclusion_reasons'])

    def test_full_role_kept_outside_common_without_losing_full_mapping(self):
        result=final_member(dict(self.row,effective_role='FULL'),self.state,self.membership)
        self.assertFalse(result['common_population'])
        self.assertEqual(result['effective_role'],'FULL')


class PprimeFirstTwoTests(unittest.TestCase):
    def fixture(self):
        import duckdb
        db=duckdb.connect(':memory:')
        db.execute('''CREATE TABLE members(molecule_id VARCHAR,effective_role VARCHAR,source_role VARCHAR,
            common_population BOOLEAN,Sprime_final_status VARCHAR,S_conformers BIGINT)''')
        db.execute('''INSERT INTO members VALUES
            ('zero','TRAIN','ROUTINE',true,'EXHAUSTED_N_NO_NEW',3),
            ('one','VAL','VAL',true,'EXHAUSTED_N_NO_NEW',1),
            ('n1','FULL','FULL',false,'ALREADY_COMPLETE',1),
            ('many','TRAIN','ROUTINE',true,'ALREADY_COMPLETE',3)''')
        db.execute('''CREATE TABLE uff_map(molecule_id VARCHAR,sprime_conf_idx BIGINT,geometry_id VARCHAR,
            source_path VARCHAR,source_row_index BIGINT,source_format VARCHAR)''')
        db.executemany('INSERT INTO uff_map VALUES (?,?,?,?,?,?)',[
            ('one',0,'one-0','ordinary.parquet',0,'parquet'),
            ('n1',0,'n1-0','ordinary.parquet',1,'parquet'),
            ('many',0,'many-0','ordinary.parquet',2,'parquet'),
            ('many',1,'many-1','ordinary.parquet',3,'parquet'),
            ('many',2,'many-2','ordinary.parquet',4,'parquet')])
        return db

    def test_actual_min_two_n1_component_merge_and_role_flags(self):
        import hashlib
        import json
        from pathlib import Path
        import tempfile
        import pyarrow.parquet as pq
        from .finalize import write_pprime_first2
        db=self.fixture()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)
            # Physical locator only: no native geometry or label is read by scope SQL.
            accepted=out/'accepted.json'
            accepted.write_text(json.dumps({'geometry_table':{'path':'registered-extra.parquet'},
                'records':[{'molecule_id':'n1','sprime_conf_idx':100,'geometry_id':'n1-extra'}]}))
            config=out/'components.json'
            config.write_text(json.dumps({'components':[{'accepted_extra_index_reference':{'path':str(accepted)}}]}))
            write_pprime_first2(db,{'n1_component_config':{'path':str(config)}},out)
            selected=pq.read_table(out/'Pprime_first2_available.parquet').to_pylist()
            states={r['molecule_id']:r for r in pq.read_table(out/'Pprime_first2_scope_states.parquet').to_pylist()}
            self.assertEqual({mid:r['selected_first2'] for mid,r in states.items()},
                {'zero':0,'one':1,'n1':2,'many':2})
            self.assertEqual(states['zero']['missing_to_two'],2)
            self.assertEqual(states['zero']['reason'],'EXHAUSTED_N_NO_NEW_ACTUAL_SHORTFALL')
            self.assertEqual(states['one']['reason'],'ORIGINAL_N1_ONLY_ONE_REAL_GEOMETRY_NO_REGISTERED_SECOND')
            self.assertEqual(states['many']['actual_available_geometries'],3)
            many=sorted([r for r in selected if r['molecule_id']=='many'],key=lambda r:r['fixed_random_rank'])
            expected=sorted(range(3),key=lambda i:(hashlib.sha256(
                ('data-v1-conformer-order:20261025:many:uff_sprime:'+str(i)).encode()).hexdigest(),str(i)))[:2]
            self.assertEqual([r['sprime_conf_idx'] for r in many],expected)
            extra=next(r for r in selected if r['geometry_id']=='n1-extra')
            self.assertEqual((extra['usage_domain'],extra['source_path'],extra['source_row_index']),
                ('registered_pprime_extra','registered-extra.parquet',0))
            self.assertEqual((extra['effective_role'],extra['source_role'],extra['common_population']),('FULL','FULL',False))
            val=next(r for r in selected if r['molecule_id']=='one')
            self.assertEqual((val['effective_role'],val['source_role'],val['common_population']),('VAL','VAL',True))
            manifest=json.loads((out/'Pprime_first2_scope.json').read_text())
            self.assertEqual(manifest['status'],'PHYSICAL_SCOPE_ONLY_NOT_LABEL_COMPUTATION')
            self.assertFalse(manifest['duplicate_or_padding_geometry'])
        db.close()

    def test_ordinary_registered_extra_collision_rejected(self):
        import json
        from pathlib import Path
        import tempfile
        from .finalize import write_pprime_first2
        db=self.fixture()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root);extra=out/'extra.jsonl'
            extra.write_text(json.dumps({'molecule_id':'n1','sprime_conf_idx':0,'geometry_id':'collision',
                'source_path':'extra.parquet','source_row_index':0,'source_format':'parquet'})+'\n')
            with self.assertRaisesRegex(ValueError,'ORDINARY_AND_EXTRA_PHYSICAL_ID_COLLISION'):
                write_pprime_first2(db,{'registered_extra_geometry_map_tables':[{'path':str(extra)}]},out)
            self.assertFalse((out/'Pprime_first2_available.parquet').exists())
        db.close()

    def test_registered_extra_conflicting_geometry_binding_rejected(self):
        import json
        from pathlib import Path
        import tempfile
        from .finalize import write_pprime_first2
        db=self.fixture()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root);extra=out/'extra.jsonl'
            rows=[{'molecule_id':'n1','sprime_conf_idx':100,'geometry_id':name,
                'source_path':'extra.parquet','source_row_index':i,'source_format':'parquet'}
                for i,name in enumerate(('first','conflicting'))]
            extra.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'REGISTERED_EXTRA_ID_BINDING_CONFLICT'):
                write_pprime_first2(db,{'registered_extra_geometry_map_tables':[{'path':str(extra)}]},out)
        db.close()

class FinalD5FreezeTests(unittest.TestCase):
    def test_final_complete_pool_uses_original_uniform_rank_and_nested_prefixes(self):
        import hashlib
        import json
        from .finalize import final_nested_lists
        complete={'kept-old','new-complete','b','c','d','e','f','g'}
        def original_key(mid):
            payload=json.dumps(['D5-SHA256-uniform-order-v1',20261025,'TRAIN',mid],sort_keys=True,
                separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
            return hashlib.sha256(payload).hexdigest(),mid
        expected=sorted(complete,key=original_key)
        actual=final_nested_lists(complete,sizes=(2,4,6))
        self.assertEqual(actual['train_all'],expected)
        self.assertEqual(actual['train_2'],expected[:2])
        self.assertEqual(actual['train_4'],expected[:4])
        self.assertEqual(actual['train_6'],expected[:6])
        self.assertEqual(final_nested_lists(list(reversed(expected)),sizes=(2,4,6)),actual)
        self.assertNotIn('old-now-shortfall',actual['train_all'])
        self.assertIn('new-complete',actual['train_all'])

    def test_final_pool_shortage_is_not_silently_downsized(self):
        from .finalize import final_nested_lists
        with self.assertRaisesRegex(ValueError,'ACTUAL_COMPLETE_FINAL_D5_POOL_TOO_SMALL'):
            final_nested_lists({'a','b','c'},sizes=(2,4,6))


class DiagnosticAddressableTests(unittest.TestCase):
    def fixture(self,root,bad_retained_binding=False):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        db=duckdb.connect(':memory:')
        db.execute('CREATE TABLE members(molecule_id VARCHAR,effective_role VARCHAR,source_role VARCHAR,common_population BOOLEAN)')
        db.execute("INSERT INTO members VALUES ('retained','TRAIN','ROUTINE',true),('missing','TRAIN','ROUTINE',true),('collision','TRAIN','ROUTINE',true)")
        db.execute('CREATE TABLE uff_map(molecule_id VARCHAR,sprime_conf_idx BIGINT,geometry_id VARCHAR)')
        db.execute("INSERT INTO uff_map VALUES (?,0,'held-retained'),('collision',1,'other-ordinary')",
            ['wrong-member' if bad_retained_binding else 'retained'])
        rows=[]
        for gid,mid,source,idx,parent in [
            ('pm7','retained','pm7',None,None),('held-retained','retained','uff_sprime',0,None),
            ('child','missing','uff_sprime',4,'held-missing'),('held-missing','missing','uff_sprime',4,None),
            ('held-collision','collision','uff_sprime',1,None)]:
            rows.append({'geometry_id':gid,'molecule_id':mid,'geometry_source':source,'sprime_conf_idx':idx,
                'parent_geometry_id':parent,'view_id':None,'native_anchor_record_id':'native-'+mid,
                'atomic_numbers':[6,1],'positions_A':[[0.,0.,0.],[1.,0.,0.]]})
        geometry=root/'frozen_actual.parquet';pq.write_table(pa.Table.from_pylist(rows),geometry)
        ids=root/'frozen_ids.parquet';pq.write_table(pa.table({'geometry_id':['pm7','held-retained','held-missing','held-collision']}),ids)
        return db,{'components':{'actual_heldout_geometry_reference':{'path':str(geometry)},
            'diagnostic_base_reference':{'path':str(ids)},'heldout_ordinary_Sprime_bases':3}},geometry

    def test_missing_holdout_gets_pointer_retained_ordinary_not_duplicated(self):
        from pathlib import Path
        import tempfile
        import pyarrow.parquet as pq
        from .finalize import write_diagnostic_addressable
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);db,prior,geometry=self.fixture(root)
            before=db.execute('SELECT * FROM uff_map ORDER BY molecule_id').fetchall()
            reference=write_diagnostic_addressable(db,prior,root)
            rows={r['geometry_id']:r for r in pq.read_table(reference['path']).to_pylist()}
            self.assertEqual(set(rows),{'held-missing','held-collision'})
            row=rows['held-missing']
            self.assertEqual((row['source_path'],row['source_row_index'],row['source_format']),(str(geometry),3,'parquet'))
            self.assertEqual(row['sprime_conf_idx'],4)
            self.assertEqual(row['accepted_component_kind'],'frozen_d5_actual_heldout_geometry')
            self.assertTrue(row['diagnostic_only']);self.assertTrue(row['excluded_from_all_training'])
            self.assertFalse(row['ordinary_physical_id_collision'])
            collision=rows['held-collision']
            self.assertTrue(collision['ordinary_physical_id_collision'])
            self.assertEqual(collision['sprime_conf_idx'],1)
            self.assertEqual(collision['storage_physical_alias'],'d5-diagnostic:held-collision')
            self.assertEqual(db.execute('SELECT * FROM uff_map ORDER BY molecule_id').fetchall(),before)
            self.assertNotIn('positions_A',row)
            db.close()

    def test_matching_geometry_id_with_changed_scientific_binding_is_rejected(self):
        from pathlib import Path
        import tempfile
        from .finalize import write_diagnostic_addressable
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);db,prior,_=self.fixture(root,bad_retained_binding=True)
            with self.assertRaisesRegex(ValueError,'ORDINARY_GEOMETRY_ID_BINDING_CONFLICT'):
                write_diagnostic_addressable(db,prior,root)
            self.assertFalse((root/'diagnostic_addressable_uff_geometry.parquet').exists())
            db.close()

if __name__=='__main__':unittest.main()