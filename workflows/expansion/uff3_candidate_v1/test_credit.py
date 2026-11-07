"""Closed-credit safety and incremental-operation tests, no scientific calls."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from .credit import ClosedLedger


class ClosedCreditTests(unittest.TestCase):
    def test_inode_dedup_query_start_and_repeated_no_tree_walk(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);first=root/'closed.bin';first.write_bytes(b'x'*8192)
            alias=root/'alias.bin';os.link(first,alias)
            ledger=ClosedLedger(root/'accounting.sqlite')
            ledger.register(first);ledger.register(alias)
            self.assertEqual(ledger.totals()['closed_logical_bytes'],8192)
            self.assertEqual(ledger.credit_before(0),0)
            with patch('os.walk',side_effect=AssertionError('NO_TREE_WALK')):
                credit=ledger.credit_before(time.time()+1)
                self.assertEqual(credit,first.stat().st_blocks*512)
                self.assertEqual(ledger.promoted_rows_lastcall,1)
                self.assertEqual(ledger.credit_before(time.time()+2),credit)
                self.assertEqual(ledger.promoted_rows_lastcall,0)
            self.assertEqual(ledger.credit_before(0),0)
            self.assertEqual(ledger.credit_before(time.time()+3),credit)
            ledger.close()

    def test_mutable_database_is_never_credited(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);path=root/'index.sqlite';path.write_bytes(b'x'*4096)
            ledger=ClosedLedger(root/'accounting.sqlite')
            self.assertFalse(ledger.register(path))
            self.assertEqual(ledger.credit_before(time.time()+1),0)
            path.write_bytes(b'y'*8192)
            self.assertFalse(ledger.register(path))
            self.assertEqual(ledger.credit_before(time.time()+2),0)
            self.assertEqual(ledger.totals()['closed_allocated_bytes'],0)
            ledger.close()

    def test_reopen_uses_persistent_totals_without_rescanning_files(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);path=root/'closed.bin';path.write_bytes(b'c'*4096)
            ledger=ClosedLedger(root/'accounting.sqlite');ledger.register(path)
            expected=ledger.credit_before(time.time()+1);ledger.close()
            with patch('os.walk',side_effect=AssertionError('NO_RESUME_TREE_WALK')):
                reopened=ClosedLedger(root/'accounting.sqlite')
                self.assertEqual(reopened.credit_before(time.time()+2),expected)
                self.assertEqual(reopened.promoted_rows_lastcall,0)
                reopened.register(path)
                self.assertEqual(reopened.totals()['closed_logical_bytes'],4096)
                reopened.close()

    def test_changed_closed_file_is_rejected_not_recredited(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);path=root/'closed.bin';path.write_bytes(b'a'*4096)
            ledger=ClosedLedger(root/'accounting.sqlite');ledger.register(path);ledger.flush()
            path.write_bytes(b'b'*8192)
            with self.assertRaisesRegex(RuntimeError,'IMMUTABLE_CLOSED_OUTPUT_CHANGED'):
                ledger.register(path)
                ledger.flush()
            # Preserve the failed attempted update; close only the DB handle.
            ledger.db.close()

    def test_scalar_capacity_queries_do_not_commit_per_molecule(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);path=root/'closed.bin';path.write_bytes(b'x'*4096)
            ledger=ClosedLedger(root/'accounting.sqlite');ledger.register(path)
            with patch.object(ledger,'flush',side_effect=AssertionError('NO_PER_MOLECULE_FSYNC')):
                for _ in range(5):
                    self.assertEqual(ledger.totals()['closed_logical_bytes'],4096)
            ledger.close()
