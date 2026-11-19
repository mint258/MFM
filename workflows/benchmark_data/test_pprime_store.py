import argparse
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib
from workflows.benchmark_data.pprime_store import pack,unpack,LaneStore
from workflows.benchmark_data import pprime_queue as q
from workflows.benchmark_data.geometry_queue import schema as geometry_schema
from workflows.benchmark_data.pprime_reader import PprimeReader


from workflows.benchmark_data.testing_workers import pprime_container_worker as synthetic_container_worker


class PprimeStorageTests(unittest.TestCase):
    def test_float64_signed_zero_and_exceptional_bits_survive(self):
        nan=struct.unpack('<d',bytes.fromhex('010000000000f87f'))[0]
        values=[-0.,1.25,float('inf'),nan,None]
        actual=unpack(pack(values))
        for expected,observed in zip(values[:-1],actual[:-1]):
            self.assertEqual(struct.pack('<d',expected),struct.pack('<d',observed))
        self.assertIsNone(actual[-1])

    def test_lane_call_is_unique_and_raw_inputs_are_never_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lane.sqlite';sink=LaneStore(path)
            metadata={'record_id':'m:sprime:0','calc_type':'pm7_B','scope_status':'PROPERTY_FAILED',
                'parsed_detail':{'task':'pm7_B','values':{'charge':[1.25,None]}}}
            f={'name':'input.out','role':'output','data':b'original output'}
            sink(metadata,[f],True,lambda needed:None)
            with self.assertRaises(sqlite3.IntegrityError):sink(metadata,[f],True,lambda needed:None)
            with self.assertRaises(ValueError):sink(metadata,[dict(f,name='input.xyz')],True,lambda needed:None)
            with self.assertRaises(ValueError):sink(metadata,[f],False,lambda needed:None)
            sink.close()
            queue=Path(tmp)/'queue.sqlite';db=sqlite3.connect(queue);q.schema(db)
            db.execute('INSERT INTO tasks(record_id,mid,conformer_id,state,result) VALUES(?,?,?,?,?)',
                ('m:sprime:0','m',0,'PPRIME_PARTIAL_WITH_RECORDED_OUTCOMES',pack({'lane_store':str(path)})))
            db.commit();db.close()
            with PprimeReader(queue) as reader:
                result=reader.get('m',0)
                self.assertFalse(result['Pprime_ready']);self.assertIsNone(result['tasks'][0]['values']['charge'][1])
                self.assertEqual(reader.raw_outputs('m',0,'pm7_B')[0]['data'],b'original output')
                self.assertEqual(reader.get('missing',0)['state'],'NOT_YET_QUEUED')

    def test_preparation_is_idempotent_and_only_actual_conformers_are_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source_root=root/'geometry/shared_v1';source_root.mkdir(parents=True)
            db=sqlite3.connect(source_root/'queue.sqlite');geometry_schema(db)
            result={'molecule_id':'m','conformers':[{'conformer_id':0},{'conformer_id':2}]}
            db.execute('INSERT INTO tasks(mid,model_smiles,state,result) VALUES(?,?,?,?)',
                ('m','fixture','SPRIME_AND_D_READY',zlib.compress(json.dumps(result).encode())))
            db.execute('INSERT INTO tasks(mid,model_smiles) VALUES(?,?)',('pending','fixture2'))
            db.commit();db.close();a=argparse.Namespace(root=root,quota_snapshot=root/'synthetic')
            with patch.object(q,'capacity'):
                q.prepare(a);q.prepare(a)
            db=sqlite3.connect(root/'labels/Pprime/shared_v1/queue.sqlite')
            self.assertEqual(db.execute('SELECT conformer_id FROM tasks ORDER BY conformer_id').fetchall(),[(0,),(2,)])
            q.claim(db,'m:sprime:0',123,'SYNTHETIC_TEST_NOT_AN_ALLOCATION')
            q.finish(db,'m:sprime:0',{'state':'SYNTHETIC_CLOSED'})
            with self.assertRaises(RuntimeError):q.claim(db,'m:sprime:0',123,'SYNTHETIC_TEST_NOT_AN_ALLOCATION')
            db.close()

    def test_real_process_scheduler_closes_each_synthetic_intent_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'labels/Pprime/shared_v1';folder.mkdir(parents=True)
            path=folder/'queue.sqlite';db=sqlite3.connect(path);q.schema(db)
            db.executemany('INSERT INTO tasks(record_id,mid,conformer_id) VALUES(?,?,?)',
                [('m:sprime:'+str(i),'m',i) for i in range(4)])
            db.execute('INSERT INTO metadata VALUES(?,?)',('ready','true'));db.commit();db.close()
            args=argparse.Namespace(root=root,quota_snapshot=root/'synthetic',workers=2,wall_seconds=86400)
            with patch.dict(q.os.environ,{'SLURM_JOB_PARTITION':'cpu','SLURM_CPUS_PER_TASK':'2',
                    'SLURM_JOB_ID':'SYNTHETIC_CONTAINER_TEST_NOT_AN_ALLOCATION'}), \
                 patch.object(q,'capacity'),patch.object(q,'worker',synthetic_container_worker):q.run(args)
            db=sqlite3.connect(path)
            self.assertEqual(db.execute('SELECT state,count(*) FROM tasks GROUP BY state').fetchall(),[('SYNTHETIC_CLOSED',4)])
            self.assertEqual(len({x[0] for x in db.execute('SELECT worker_pid FROM tasks')}),2)
            db.close()

if __name__=='__main__':unittest.main()
