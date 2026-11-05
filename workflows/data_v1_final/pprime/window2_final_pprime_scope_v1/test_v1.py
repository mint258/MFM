"""New identity/claim logic only; no Native process or trial geometry generation."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from .prepare import prepare,selected_rows,save,info,old_closed_keys,supplemental_keys
from .run import checked_conformer,recover

class ScopeTests(unittest.TestCase):
    def test_final_scope_reuses_actual_keys_and_preserves_unknown_and_n1(self):
        import pyarrow as pa,pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            def table(name,rows):
                filename=root/name;pq.write_table(pa.Table.from_pylist(rows),filename);return info(filename,len(rows))
            def document(name,value):
                filename=root/name;save(filename,value);return info(filename)
            # Deliberately nonnumeric-looking MID; no record ID splitting.
            mids=['old:literal','new:literal','unknown:literal','N1:literal','supp:literal']
            raw=[]
            for i,mid in enumerate(mids):
                raw.append({'molecule_id':mid,'sprime_conf_idx':9+i,'status':'SUCCESS','converged':True,
                    'atomic_numbers':[6,1],'coordinates':[[0.,0.,0.],[1.0000000000000002,0.,0.]],'source_record_id':'anchor'+str(i),'geometry_sha256':'existing-geometry-'+str(i)})
            rawref=table('actual.parquet',raw)
            selected=[]
            for i,mid in enumerate(mids):
                selected.append({'molecule_id':mid,'sprime_conf_idx':100+i,'geometry_id':'G'+str(i),
                    'source_path':rawref['path'],'source_row_index':i,'source_format':'parquet',
                    'usage_domain':'registered_pprime_extra' if i==3 else 'ordinary',
                    'effective_role':'VAL' if i==3 else 'TRAIN','source_role':'FULL','common_population':True,'fixed_random_rank':0})
            first2=document('first2.json',{'selected_geometry_table':table('selected.parquet',selected),
                'record_level_state_table':table('states.parquet',[{'effective_role':'TRAIN','common_population':True,'selected_first2':1,'missing_to_two':1,'reason':'ONE_REAL_ONLY'}])})
            ids=root/'ids.sqlite';db=sqlite3.connect(ids)
            db.execute('CREATE TABLE pprime_records(ordinal INTEGER,record_id TEXT,mid TEXT)')
            db.execute('INSERT INTO pprime_records VALUES(0,?,?)',('unparsed-original-record-id',mids[0]));db.commit();db.close()
            pointers=root/'pointer.sqlite';db=sqlite3.connect(pointers)
            db.execute('CREATE TABLE pointers(ordinal INTEGER,domain INTEGER,file INTEGER,locator TEXT)')
            db.execute('INSERT INTO pointers VALUES(0,1,1,?)',(json.dumps({'sprime_conf_idx':100,'source_record_id':'anchor0','uff_geometry_sha256':'existing-geometry-0'}),));db.commit();db.close()
            index=document('index.json',{'schema':'D6_FULL_ORIGINAL_PHYSICAL_LOCATOR_INDEX_V1','identity_database':info(ids),'QC_locations':info(pointers),'partitions':[]})
            supplemental=root/'supp';supplemental.mkdir()
            qc=table('QC.parquet',[{'record_id':'old-supp-label','molecule_id':mids[4]}])
            base=table('base.parquet',[{'record_id':'old-supp-label','molecule_id':mids[4],'sprime_conf_idx':104,'source_record_id':'anchor4','uff_geometry_sha256':'existing-geometry-4'}])
            save(supplemental/'manifest.json',{'original_native_recipe_900s_unchanged':True,'no_Pprime_rank_ge_2':True,
                'batches':[{'files':[dict(qc,family='QC'),dict(base,family='base_geometry')]}]})
            db=sqlite3.connect(supplemental/'claims.sqlite');db.execute('CREATE TABLE claims(record_id TEXT,status TEXT)')
            db.execute('INSERT INTO claims VALUES(?,?)',('pprime:'+mids[2]+':102','NATIVE_INTENT'));db.commit();db.close()
            sources=table('native-index.parquet',[{'record_id':'anchor'+str(i),'molecule_id':mid,'source_path':'native'+str(i),'heavy_atoms':1} for i,mid in enumerate(mids)])
            shards=document('sourceplan.json',{'sources':[{'path':'native'+str(i),'shard_id':i} for i in range(11)]})
            common=document('common.json',{'membership_tables':[table('members.parquet',[{'molecule_id':mid,'file_group':7} for mid in mids])]})
            result=prepare({'scope_output':str(root/'output'),'first2':first2,'source_index':index,
                'additional_pprime_roots':[str(supplemental)],'native_record_index':sources,'source_plan':shards,'common':common,'workers':1})
            self.assertEqual((result['actual_first2_records'],result['reused_closed_records'],result['unknown_native_intents'],result['needed_records']),(5,2,1,2))
            tasks=pq.read_table(result['tables']['tasks']['path']).to_pylist()
            self.assertEqual({row['molecule_id'] for row in tasks},{mids[1],mids[3]})
            n1=next(row for row in tasks if row['molecule_id']==mids[3])
            self.assertEqual((n1['usage'],n1['sprime_conf_idx'],n1['original_sprime_conf_idx']),('PprimeOnly',103,12))
            self.assertEqual(json.loads(n1['physical_geometry_json'])['coordinates'][1][0],1.0000000000000002)
            self.assertEqual(n1['file_group'],7)
            self.assertEqual(result['shortfall_counts']['actual_shortfall_to_two'],1)

    def test_rank_two_and_missing_rank_zero_rejected(self):
        import pyarrow as pa,pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temporary:
            filename=Path(temporary)/'selected.parquet'
            for rank,expected in [(2,'RANK_GE_2'),(1,'FIRST_MIN_TWO')]:
                pq.write_table(pa.Table.from_pylist([{'molecule_id':'M','sprime_conf_idx':9,'common_population':True,'effective_role':'TRAIN','fixed_random_rank':rank}]),filename)
                with self.assertRaisesRegex(ValueError,expected):selected_rows({'selected_geometry_table':info(filename)})

    def test_missing_witness_uses_actual_ordered_z_and_preserves_source_id(self):
        raw={'source_record_id':'a','molecule_id':'M','sprime_conf_idx':5,'status':'SUCCESS','converged':True,
            'atomic_numbers':[6,1],'coordinates':[[0.,0.,0.],[1.,0.,0.]]}
        row={'molecule_id':'M','sprime_conf_idx':99,'original_sprime_conf_idx':5,'native_anchor_record_id':'a','physical_geometry_json':json.dumps(raw)}
        native={'z':[6,1],'native_atom_order_sha256':'original-native-witness'}
        result=checked_conformer(row,native)
        self.assertEqual((result['sprime_conf_idx'],result['atom_order_sha256']),(99,'original-native-witness'))
        with self.assertRaisesRegex(ValueError,'ORDERED_Z_DIFFERS'):checked_conformer(row,dict(native,z=[1,6]))

    def test_recovery_closes_only_persisted_publication_not_unknown_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);folder=root/'batch_000001';folder.mkdir()
            db=sqlite3.connect(':memory:');db.execute('CREATE TABLE claims(molecule_id TEXT,sprime_conf_idx INTEGER,status TEXT)')
            db.executemany('INSERT INTO claims VALUES(?,?,?)',[('A',1,'NATIVE_INTENT'),('B',2,'NATIVE_INTENT')])
            outcomes=folder/'record_outcomes.json';save(outcomes,[{'molecule_id':'A','sprime_conf_idx':1,'status':'CLOSED_TWELVE_OUTCOMES'}])
            save(folder/'checkpoint.json',{'record_outcomes':info(outcomes)})
            recover(db,root)
            self.assertEqual(dict(db.execute('SELECT molecule_id,status FROM claims')),{'A':'CLOSED_TWELVE_OUTCOMES','B':'NATIVE_INTENT'})
            db.close()

if __name__=='__main__':unittest.main()
