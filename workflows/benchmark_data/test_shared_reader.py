import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib
from workflows.benchmark_data.geometry_queue import schema
from workflows.benchmark_data.shared_reader import SharedB0Reader


class SharedReaderTests(unittest.TestCase):
    def test_shared_result_and_pending_keep_source_atom_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'queue.sqlite';db=sqlite3.connect(path);schema(db)
            payload=zlib.compress(json.dumps({'D20':{'values':[1.25,None],'valid_mask':[True,False]},
                'conformers':[{'coordinates_A':[[1.25,0.,0.]]}]}).encode())
            db.execute('INSERT INTO tasks(mid,model_smiles,state,result) VALUES(?,?,?,?)',('mid','CCO','SPRIME_AND_D_READY',payload))
            db.execute('INSERT INTO tasks(mid,model_smiles) VALUES(?,?)',('pending','CCN'))
            db.executemany('INSERT INTO membership VALUES(?,?,?,?)',[
                ('A','row1','mid','[2,0,1]'),('B','row2','mid','[0,1,2]'),('A','row3','pending','[0,1,2]')])
            db.commit()
            with SharedB0Reader(path) as reader:
                self.assertEqual(list(reader.iter_membership('A',batch_size=1)),['row1','row3'])
                a=reader.get('A','row1');b=reader.get('B','row2')
                self.assertEqual(a['result'],b['result'])
                self.assertEqual(a['model_atom_to_source'],[2,0,1])
                self.assertIsNone(reader.get('A','row3')['result'])
                self.assertFalse(a['Pprime_ready'])
                with self.assertRaises(sqlite3.OperationalError):reader.db.execute('DELETE FROM tasks')
                with self.assertRaises(KeyError):reader.get('A','missing')
                # The consumer holds no iterator/transaction over its work.
                db.execute("UPDATE tasks SET state='INTENT' WHERE mid='pending'");db.commit()
            db.close()

if __name__=='__main__':unittest.main()
