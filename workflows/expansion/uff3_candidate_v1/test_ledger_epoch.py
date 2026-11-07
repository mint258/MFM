"""Native stdlib inode/lock/resume boundaries, no geometry or D calculations."""
import hashlib
import os
from pathlib import Path
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from .credit import ClosedLedger,inode_key
from .ledger_resume import assert_registered_writers_gone,locked_scope,rebuild,resume_authority,StartupCensus


class LedgerEpochTests(unittest.TestCase):
    def test_unsigned_ids_roundtrip_and_hardlink_dedup(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);ledger=ClosedLedger(root/'ledger.sqlite')
            value=(inode_key((1<<64)-1),inode_key(10347653768975279404),
                   str(root/'closed'),os.getuid(),16,4096,10,11,11)
            with patch.object(ClosedLedger,'fact',return_value=value):
                ledger.register(root/'closed');ledger.flush()
                ledger.register(root/'alias')
            actual=ledger.db.execute('SELECT dev,ino FROM files').fetchone()
            self.assertEqual(actual,value[:2]);self.assertEqual(ledger.credit_before(1),4096)
            self.assertEqual(ledger.totals()['closed_logical_bytes'],16)
            ledger.close()
            with self.assertRaises(RuntimeError):inode_key(1<<64)

    def test_old_signed_schema_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.sqlite'
            db=sqlite3.connect(path);db.execute('CREATE TABLE old_evidence(value TEXT)')
            db.execute("INSERT INTO old_evidence VALUES('159')");db.commit();db.close()
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError,'NEW_U64_LEDGER_NAMESPACE'):
                ClosedLedger(path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_fresh_native_census_counts_abandoned_and_mutable_outputs(self):
        from .resources import Budget
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);closed=root/'molecules'/'ab'/'mid';closed.mkdir(parents=True)
            data=closed/'candidate_cache.json';data.write_bytes(b'old-coordinate-bits')
            os.link(data,closed/'same-inode.json')
            partial=root/'molecules'/'ab'/'interrupted';partial.mkdir()
            (partial/'events.jsonl').write_bytes(b'never scientifically retried')
            old=root/'output_accounting.sqlite';old.write_bytes(b'old evidence')
            mutable=root/'index.sqlite';mutable.write_bytes(b'mutable')
            before={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (data,partial/'events.jsonl',old,mutable)}
            budget=SimpleNamespace(root=root,ledger=ClosedLedger(root/'new.sqlite'),
                                   mutable_paths=set(),mutable_dirs=set())
            budget.register=lambda path:Budget.register.__wrapped__(budget,path)
            result=rebuild(budget)
            self.assertTrue(result['includes_retained_interrupted_bytes'])
            # Raw totals include immutable file blocks once plus immutable dirs;
            # mutable databases are measured by Budget.used, never old credit.
            expected=data.stat().st_blocks*512+(partial/'events.jsonl').stat().st_blocks*512
            self.assertEqual(budget.ledger.credit_before(time.time()+1),expected)
            self.assertIn(mutable,budget.mutable_paths);self.assertIn(old,budget.mutable_paths)
            self.assertIn(root/'molecules'/'ab',budget.mutable_dirs)
            self.assertEqual(before,{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before})
            with patch('os.walk',side_effect=AssertionError('NO_POLL_RESCAN')):
                budget.ledger.credit_before(time.time()+2)
                budget.ledger.totals()
            budget.ledger.close()

    def test_registered_live_child_blocks_rebuild_unrelated_proc_not_scanned(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'open.json'
            script="import sys; f=open(sys.argv[1],'wb'); print('ready',flush=True); sys.stdin.read(1); f.close()"
            process=subprocess.Popen([sys.executable,'-I','-c',script,str(path)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(),'ready')
                with self.assertRaisesRegex(RuntimeError,'REGISTERED_OLD_WRITER_STILL_ALIVE'):
                    raw=Path('/proc',str(process.pid),'stat').read_text()
                    start=int(raw[raw.rfind(')')+2:].split()[19])
                    writer={'node':socket.gethostname(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                            'pid':process.pid,'start_ticks':start}
                    assert_registered_writers_gone([writer])
            finally:
                process.communicate('x',timeout=10)
            with (root/'parent.lock').open('a+b') as lock:
                with patch.object(Path,'iterdir',side_effect=PermissionError('unrelated process must not be examined')):
                    epoch=locked_scope(root,lock)
                self.assertTrue(epoch['parent_lock_held'])
                self.assertFalse(epoch['cross_node_inode_identity_assumed'])

    def test_related_unreadable_reused_pid_old_boot_and_unknown_resume(self):
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        raw=Path('/proc/self/stat').read_text();start=int(raw[raw.rfind(')')+2:].split()[19])
        writer={'node':socket.gethostname(),'boot_id':boot,'pid':os.getpid(),'start_ticks':start+1}
        assert_registered_writers_gone([writer])  # PID reused; original start ticks differ.
        assert_registered_writers_gone([{**writer,'boot_id':'old-boot'}])
        original=Path.read_text
        def unreadable(path,*args,**kwargs):
            if path==Path('/proc',str(os.getpid()),'stat'):raise PermissionError('related')
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',unreadable):
            with self.assertRaisesRegex(RuntimeError,'REGISTERED_WRITER_LIFETIME_UNREADABLE'):
                assert_registered_writers_gone([writer])
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);self.assertEqual(resume_authority({},root),[])
            (root/'molecules').mkdir()
            with self.assertRaisesRegex(RuntimeError,'ACTUAL_MACHINE_RESUME_BINDING'):resume_authority({},root)

    def test_complete_startup_baseline_and_only_actual_new_ledger_growth(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);old=root/'old.json';old.write_bytes(b'closed'*4096)
            os.link(old,root/'old-hardlink.json')
            mutable=root/'index.sqlite';mutable.write_bytes(b'old sqlite')
            ledger_path=root/'new.sqlite'
            plan={'ledger_rebuild_reserved_bytes':1<<20,'output_cap_bytes':8<<20,
                  'software_rss_budget_bytes':1<<60,'minimum_node_available_bytes':0}
            baseline=StartupCensus(root,ledger_path,plan)
            actual=root.stat().st_blocks*512+old.stat().st_blocks*512+mutable.stat().st_blocks*512
            self.assertEqual(baseline.usage(),actual)
            cutoff=baseline.maximum_eligible_ns
            from decimal import Decimal
            exact=Decimal(cutoff)/Decimal(1000000000)
            self.assertEqual(baseline.credit_before(exact),0)
            self.assertEqual(baseline.credit_before(exact+Decimal('0.000000001')),old.stat().st_blocks*512)
            with patch('os.walk',side_effect=AssertionError('NO_STARTUP_GUARD_TREE_RESCAN')):
                ledger=ClosedLedger(ledger_path,maximum_bytes=plan['ledger_rebuild_reserved_bytes'])
                ledger.register(old);ledger.flush()
                self.assertGreaterEqual(baseline.usage(),actual)
                self.assertEqual(baseline.credit_before(0),0)
                self.assertLessEqual(baseline.peak_growth,plan['ledger_rebuild_reserved_bytes'])
                ledger.close()
    def test_census_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'link').symlink_to('/tmp',target_is_directory=True)
            budget=SimpleNamespace(root=root,ledger=ClosedLedger(root/'ledger.sqlite'),
                                   mutable_dirs=set(),register=lambda p:None)
            with self.assertRaisesRegex(RuntimeError,'OUTPUT_DIRECTORY_SYMLINK'):rebuild(budget)
            budget.ledger.close()


if __name__=='__main__':unittest.main()