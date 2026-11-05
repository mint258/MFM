"""One small in-memory projection/batch-resume fixture; no Native or real data."""
import json
import unittest
from .run import project_coordinates,batch_tasks,refresh_batches


class FinalizeTailTests(unittest.TestCase):
    def test_needed_projection_preserves_selected_tasks_and_only_unclosed_batches_resume(self):
        import duckdb
        db=duckdb.connect(':memory:')
        db.execute('CREATE SCHEMA source')
        db.execute('''CREATE TABLE source.uff(molecule_id VARCHAR,sprime_conf_idx BIGINT,source_record_id VARCHAR,
            coordinates DOUBLE[][],uff_energy_kcal_mol DOUBLE)''')
        db.executemany('INSERT INTO source.uff VALUES (?,?,?,?,?)',[
            ('B',9,'B-native',[[9.25,1.,2.]],-9.5),('A',1,'A-native',[[100.,1.,2.]],-1.),
            ('B',3,'B-native',[[3.25,1.,2.]],-3.5),('C',2,'C-native',[[2.25,1.,2.]],-2.5),
            ('D',1,'D-native',[[200.,1.,2.]],-1.)])
        db.execute('CREATE TABLE keep(molecule_id VARCHAR,sprime_conf_idx BIGINT)')
        db.execute("INSERT INTO keep VALUES ('A',1),('B',9),('B',3),('C',2),('D',1)")
        db.execute('''CREATE TABLE fresh(molecule_id VARCHAR,sprime_conf_idx BIGINT,coordinates DOUBLE[][],
            uff_energy_kcal_mol DOUBLE)''')
        db.executemany('INSERT INTO fresh VALUES (?,?,?,?)',[
            ('B',12,[[12.25,2.,3.]],-12.5),('C',6,[[6.25,2.,3.]],-6.5),('D',8,[[800.,2.,3.]],-8.5)])
        db.execute('CREATE TABLE formal(molecule_id VARCHAR,record_id VARCHAR,source_path VARCHAR,real_index BIGINT)')
        db.execute("INSERT INTO formal VALUES ('B','B9','/mock/B.lmdb',9),('C','C8','/mock/C.lmdb',8),('B','B1','/mock/B.lmdb',1),('C','C0','/mock/C.lmdb',0)")
        # Exact original all-MID projection and appended fresh coordinates.
        db.execute('CREATE TABLE full_coordinates AS SELECT u.* FROM source.uff u JOIN keep k USING(molecule_id,sprime_conf_idx)')
        db.execute('INSERT INTO full_coordinates SELECT molecule_id,sprime_conf_idx,NULL,coordinates,uff_energy_kcal_mol FROM fresh')
        changed=['B','C']
        expected=batch_tasks(db,changed,'full_coordinates')
        project_coordinates(db,'source','fresh',changed,'needed_coordinates')
        actual=batch_tasks(db,changed,'needed_coordinates')
        self.assertEqual(actual,expected)  # every selected original anchor/F64 row and input order
        self.assertEqual(db.execute('SELECT DISTINCT molecule_id FROM needed_coordinates ORDER BY molecule_id').fetchall(),[('B',),('C',)])
        self.assertLess(db.execute('SELECT count(*) FROM needed_coordinates').fetchone()[0],db.execute('SELECT count(*) FROM full_coordinates').fetchone()[0])
        bymid={job['molecule_id']:job for job in actual}
        self.assertEqual(bymid['B']['anchor']['record_id'],'B1')
        self.assertEqual(bymid['C']['anchor']['record_id'],'C0')
        def result(jobs):
            return [(job['molecule_id'],json.dumps({'fixture_ids':[row['sprime_conf_idx'] for row in job['uff']],
                'fixture_coordinates':[row['coordinates'] for row in job['uff']]})) for job in jobs]
        expected_result=dict(result(expected));loads=[];published=[]
        closed={0:{'batch':0,'result':[('B',expected_result['B'])]}}
        def load(mids):loads.append(mids);return batch_tasks(db,mids,'needed_coordinates')
        def publish(index,values):published.append(index);return {'batch':index,'result':values}
        references=refresh_batches(changed,closed,load,result,publish,batch_size=1)
        self.assertEqual(loads,[['C']]);self.assertEqual(published,[1])
        self.assertEqual(references,[{'batch':0,'result':[('B',expected_result['B'])]},
            {'batch':1,'result':[('C',expected_result['C'])]}])
        loads.clear();published.clear()
        self.assertEqual(refresh_batches(changed,closed,load,result,publish,batch_size=1),references)
        self.assertEqual(loads,[]);self.assertEqual(published,[])
        db.close()


if __name__=='__main__':unittest.main()