"""Real SQLite/inode facts remain coherent across the Alpha guard callback."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import time
import unittest
from .credit import ClosedLedger


class ConcurrentLedgerTests(unittest.TestCase):
    def test_guard_thread_and_parent_registration_share_one_closed_frontier(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);paths=[]
            for i in range(32):
                path=root/(str(i)+'.json');path.write_bytes(b'closed');paths.append(path)
            ledger=ClosedLedger(root/'ledger.sqlite');cutoff=time.time()+1
            def parent():
                for path in paths:ledger.register(path)
            def guard():
                for _ in range(50):ledger.totals();ledger.credit_before(cutoff)
            with ThreadPoolExecutor(2) as workers:
                a=workers.submit(parent);b=workers.submit(guard);a.result();b.result()
            expected=sum(p.stat().st_blocks*512 for p in paths)
            self.assertEqual(ledger.credit_before(cutoff),expected)
            self.assertEqual(ledger.totals()['closed_allocated_bytes'],expected)
            self.assertEqual(ledger.db.execute('SELECT count(*) FROM files').fetchone()[0],32)
            ledger.close()

    def test_closed_directory_bytes_count_without_becoming_quota_file_credit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);closed=root/'closed';closed.mkdir();data=closed/'cache.json';data.write_bytes(b'closed')
            ledger=ClosedLedger(root/'ledger.sqlite');ledger.register(data);ledger.register_directory(closed)
            expected=data.stat().st_blocks*512;directory=closed.stat().st_blocks*512
            self.assertEqual(ledger.totals()['closed_allocated_bytes'],expected+directory)
            self.assertEqual(ledger.credit_before(time.time()+1),expected)
            self.assertEqual(ledger.totals()['closed_directory_allocated_bytes'],directory)
            ledger.close();ledger=ClosedLedger(root/'ledger.sqlite')
            self.assertEqual(ledger.totals()['closed_allocated_bytes'],expected+directory);ledger.close()


if __name__=='__main__':unittest.main()
