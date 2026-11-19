"""Test new resource admission and once-only continuation, never real QM."""
import argparse
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from . import pprime_tmpfs_queue as q
from workflows.benchmark_data.testing_workers import pprime_container_worker as synthetic_container_worker

GiB=1024**3

def filesystem(free,total=400*GiB,inodes=100000):
    return SimpleNamespace(f_bavail=free,f_blocks=total,f_frsize=1,f_favail=inodes)

class TmpfsTests(unittest.TestCase):
    def guard(self,free=200*GiB,memory=350*GiB,rootfree=60*GiB):
        stats=lambda path:filesystem(rootfree,75*GiB) if str(path)=='/tmp' else filesystem(free,188*GiB)
        mem='MemTotal: '+str(375*GiB//1024)+' kB\nMemAvailable: '+str(memory//1024)+' kB\n'
        with patch.object(q.os,'statvfs',side_effect=stats),patch.object(q.Path,'read_text',return_value=mem):
            q.tmpfs_capacity('/dev/shm',16)

    def test_admits_only_when_tmpfs_ram_and_root_reserves_all_fit(self):
        self.guard()
        with self.assertRaisesRegex(RuntimeError,'tmpfs bytes'):self.guard(free=150*GiB)
        with self.assertRaisesRegex(RuntimeError,'available RAM'):self.guard(memory=180*GiB)
        with self.assertRaisesRegex(RuntimeError,'Root filesystem'):self.guard(rootfree=9*GiB)
        with self.assertRaises(ValueError):q.tmpfs_capacity('/tmp',16)

    def test_continuation_preserves_closed_and_interrupted_rows_without_recompute(self):
        with tempfile.TemporaryDirectory(prefix='b0-tmpfs-fixture-') as tmp:
            root=Path(tmp);folder=root/'labels/Pprime/shared_v1';folder.mkdir(parents=True)
            path=folder/'queue.sqlite';db=sqlite3.connect(path);q.schema(db)
            db.executemany('INSERT INTO tasks(record_id,mid,conformer_id,state) VALUES(?,?,?,?)',[
                ('m:sprime:0','m',0,'PPRIME_READY'),('m:sprime:1','m',1,'INTENT'),
                ('m:sprime:2','m',2,'PENDING'),('m:sprime:3','m',3,'PENDING')])
            db.execute('INSERT INTO metadata VALUES(?,?)',('ready','true'));db.commit();db.close()
            args=argparse.Namespace(root=root,quota_snapshot=root/'synthetic',workers=2,wall_seconds=86400)
            with patch.dict(q.os.environ,{'SLURM_JOB_PARTITION':'cpu','SLURM_CPUS_PER_TASK':'2',
                    'SLURM_JOB_ID':'SYNTHETIC_CONTINUATION_NOT_REAL_ALLOCATION'}), \
                 patch.object(q,'capacity'),patch.object(q,'worker',synthetic_container_worker):q.run(args)
            db=sqlite3.connect(path)
            states=dict(db.execute('SELECT record_id,state FROM tasks'))
            self.assertEqual(states['m:sprime:0'],'PPRIME_READY')
            self.assertEqual(states['m:sprime:1'],'UNKNOWN_INTERRUPTED_NO_RETRY')
            self.assertEqual([states['m:sprime:'+str(i)] for i in (2,3)],['SYNTHETIC_CLOSED']*2)
            self.assertEqual(db.execute('SELECT worker_pid FROM tasks WHERE conformer_id=0').fetchone(),(None,))
            db.close()

    def test_followup_after_full_closure_exits_without_opening_or_restarting_queue(self):
        with tempfile.TemporaryDirectory(prefix='b0-closed-fixture-') as tmp:
            root=Path(tmp);folder=root/'labels/Pprime/shared_v1';folder.mkdir(parents=True)
            manifest=folder/'producer_previous.json';manifest.write_text(json.dumps({'status':'ALL_QUEUED_PPRIME_TERMINAL'}))
            (folder/'access.json').write_text(json.dumps({'immutable':True,'writers_closed':True,
                'producer_job':'SYNTHETIC_PREVIOUS','producer_manifest':str(manifest)}))
            with patch.object(q,'capacity') as admit,patch.object(q,'_run') as produce:
                q.run(argparse.Namespace(root=root))
            admit.assert_not_called();produce.assert_not_called()
            self.assertFalse((folder/'queue.sqlite').exists())

if __name__=='__main__':unittest.main()