"""Synthetic orchestration only: no RDKit generation, QM or Slurm submission."""
import argparse
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from workflows.benchmark_data import geometry_queue as q


def container_only_worker(connection):
    connection.send({'event':'ready'})
    while True:
        task=connection.recv()
        if task is None:return
        time.sleep(.05)
        connection.send({'event':'result','mid':task['mid'],
            'result':{'state':'SYNTHETIC_CONTAINER_READY','value':task['model_smiles']}})


class CapacityWaitTests(unittest.TestCase):
    def test_unavailable_quota_holds_results_and_never_repeats_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'queue.sqlite';db=sqlite3.connect(path);q.schema(db)
            db.executemany('INSERT INTO tasks(mid,model_smiles) VALUES (?,?)',[('a','fixture-a'),('b','fixture-b')])
            db.executemany('INSERT INTO metadata VALUES (?,?)',[('ready','true'),('storage_forecast_bytes','1048576')])
            db.commit();db.close();calls=[0];claimed=[];finished=[];failures=[0];admitted=[True]
            original_claim,original_finish=q.claim,q.finish
            def admission(*args,**kwargs):
                calls[0]+=1
                if claimed and failures[0]<3:
                    failures[0]+=1;admitted[0]=False
                    raise RuntimeError('SYNTHETIC temporarily unavailable quota')
                admitted[0]=True
            def claim(*args):
                self.assertTrue(admitted[0]);claimed.append(args[1]);return original_claim(*args)
            def finish(*args):
                self.assertTrue(admitted[0]);finished.append(args[1]);return original_finish(*args)
            args=argparse.Namespace(queue=path,workers=1,quota_snapshot=root/'synthetic-observation.json')
            with patch.dict(q.os.environ,{'SLURM_CPUS_PER_TASK':'1','SLURM_JOB_PARTITION':'cpu',
                    'SLURM_JOB_ID':'SYNTHETIC_CONTAINER_TEST_NOT_AN_ALLOCATION'}), \
                 patch.object(q,'worker',container_only_worker),patch.object(q,'protect',admission), \
                 patch.object(q,'GUARD_INTERVAL_SECONDS',.05),patch.object(q,'claim',claim),patch.object(q,'finish',finish):
                q.run(args)
            self.assertEqual(failures[0],3)
            self.assertEqual(claimed,['a','b']);self.assertEqual(finished,['a','b'])
            manifest=json.loads(next(root.glob('producer_*.json')).read_text())
            self.assertEqual(manifest['status'],'ALL_QUEUED_MOLECULES_TERMINAL')
            self.assertEqual(manifest['states'],{'SYNTHETIC_CONTAINER_READY':2})

if __name__=='__main__':unittest.main()
