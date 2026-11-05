"""One in-memory task-input equivalence test; no real sources or benchmark."""
import unittest
from .run import tasks
from workflows.data_v1_final.conformers.window2_population_v1 import d7


class FillTaskLoaderTests(unittest.TestCase):
    def test_only_unused_hof_and_prior_are_omitted_all_formal_uff_fields_and_order_match(self):
        import duckdb
        db=duckdb.connect(':memory:')
        db.execute('''CREATE TABLE formal(molecule_id VARCHAR,record_id VARCHAR,source_path VARCHAR,
            real_index BIGINT,original_metadata VARCHAR)''')
        db.executemany('INSERT INTO formal VALUES (?,?,?,?,?)',[
            ('B','B9','/mock/B.lmdb',91,'b9-original'),('A','A2','/mock/A.lmdb',24,'a2-original'),
            ('B','B1','/mock/B.lmdb',13,'b1-original'),('A','A0','/mock/A.lmdb',5,'a0-original')])
        db.execute('CREATE TABLE hof(record_id VARCHAR,value_json VARCHAR,duplicate BOOLEAN)')
        db.executemany('INSERT INTO hof VALUES (?,?,?)',[
            ('A0','unused-json-A0',False),('A2','unused-json-A2',True),
            ('B1','unused-json-B1',False),('B9','unused-json-B9',True)])
        db.execute('''CREATE TABLE uff(molecule_id VARCHAR,sprime_conf_idx BIGINT,coordinates DOUBLE[][],
            uff_energy_kcal_mol DOUBLE,source_record_id VARCHAR,seed BIGINT,status VARCHAR)''')
        db.executemany('INSERT INTO uff VALUES (?,?,?,?,?,?,?)',[
            ('B',19,[[1.,2.,3.],[4.,5.,6.]],-7.25,'B1',17,'SUCCESS'),
            ('A',8,[[9.,8.,7.],[6.,5.,4.]],-3.5,'A0',23,'SUCCESS'),
            ('B',2,[[0.,1.,2.],[3.,4.,5.]],-2.25,'B9',17,'SUCCESS'),
            ('A',1,[[2.,3.,4.],[5.,6.,7.]],-1.5,'A2',23,'SUCCESS')])
        db.execute('CREATE TABLE prior(molecule_id VARCHAR,packet VARCHAR)')
        db.execute("INSERT INTO prior VALUES ('A','unused-prior-A'),('B','unused-prior-B')")
        metas=[{'molecule_id':'B','S_conformers':3},{'molecule_id':'A','S_conformers':2}]
        expected=d7.tasks(db,metas)
        class NoUnusedReads:
            def __init__(self,connection):self.connection=connection;self.queries=[]
            def register(self,*args):return self.connection.register(*args)
            def unregister(self,*args):return self.connection.unregister(*args)
            def execute(self,sql):
                upper=sql.upper()
                if ' HOF ' in upper or ' PRIOR ' in upper:raise AssertionError('UNUSED_SOURCE_QUERY')
                self.queries.append(sql)
                return self.connection.execute(sql)
        guarded=NoUnusedReads(db)
        actual=tasks(guarded,metas)
        self.assertEqual(len(guarded.queries),2)
        self.assertEqual([j['meta']['molecule_id'] for j in actual],['B','A'])
        self.assertEqual([[r['record_id'] for r in j['records']] for j in actual],[['B1','B9'],['A0','A2']])
        self.assertEqual([[r['sprime_conf_idx'] for r in j['uff']] for j in actual],[[2,19],[1,8]])
        for old,new,meta in zip(expected,actual,metas):
            self.assertIs(new['meta'],meta)
            self.assertEqual(new['meta'],old['meta'])
            self.assertEqual(new['uff'],old['uff'])  # every original F64 value, all IDs/metadata
            self.assertIsNone(new['prior_packet']);self.assertIsNotNone(old['prior_packet'])
            for left,right in zip(old['records'],new['records']):
                self.assertEqual(set(left)-set(right),{'value_json','duplicate'})
                self.assertEqual(right,{k:v for k,v in left.items() if k not in ('value_json','duplicate')})
                self.assertEqual({k:right[k] for k in ('record_id','source_path','real_index')},
                    {k:left[k] for k in ('record_id','source_path','real_index')})
        # Exercise the private runtime injection without touching global d7.tasks
        # or invoking a native worker in this input-only fixture.
        from unittest.mock import Mock
        from .run import part_values, original
        pool=Mock()
        pool.map.side_effect=lambda function,jobs,chunksize:[{'molecule_id':j['meta']['molecule_id']} for j in jobs]
        statistics=[{'molecule_id':m['molecule_id'],'status':'NOT_COMPLETE','sprime_unique_ids_json':'[]'} for m in metas]
        values=part_values(guarded,metas,statistics,{},pool)
        self.assertEqual(values,[{'molecule_id':'B'},{'molecule_id':'A'}])
        self.assertIs(pool.map.call_args.args[0],original.safe_fill)
        self.assertEqual(len(guarded.queries),4)
        self.assertIs(d7.tasks,original.d7.tasks)
        db.close()


if __name__=='__main__':unittest.main()