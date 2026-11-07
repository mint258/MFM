"""Reject optimistic, stale, and mismatched real quota evidence."""
import copy
import hashlib
import unittest
import os
from pathlib import Path
import tempfile
import time
from .quota import parse_quota, validate_snapshot, observed_old_own_blocks, budget_check, SCHEMA

RAW = 'Disk quotas for user zixiao (uid 1278):\n Filesystem blocks quota limit files\n /dev/sda1 3846655732 0 4294967296 140048294\n'


class QuotaEvidence(unittest.TestCase):
    def setUp(self):
        used, limit = parse_quota(RAW, '/dev/sda1')
        self.expected = dict(endpoint='202.38.247.57:22', uid=1278, filesystem='/dev/sda1')
        self.snapshot = dict(schema=SCHEMA, status='ACTUAL_FRESH_ACCOUNT_QUOTA',
            **self.expected, generated_unix_seconds=1000, username='zixiao',
            raw_quota_output=RAW, raw_quota_sha256=hashlib.sha256(RAW.encode()).hexdigest(),
            actual_quota_command=['quota', '-v', '-u', 'zixiao'], quota_returncode=0,
            used_bytes=used, hard_limit_bytes=limit)

    def test_zero_soft_limit_does_not_erase_real_hard_limit(self):
        self.assertEqual(validate_snapshot(self.snapshot, self.expected, now=1010)['free_account_bytes'],
                         (4294967296 - 3846655732) * 1024)
        self.assertEqual(parse_quota('/dev/sda1\n 10* 20 30\n', '/dev/sda1'), (10240, 20480))
        for raw in ('/dev/sda1 10 0 0', '/dev/sda1 10 0', RAW + RAW):
            with self.assertRaises(RuntimeError):
                parse_quota(raw, '/dev/sda1')

    def test_modified_account_numbers_and_wrong_account_are_rejected(self):
        for key, value in [('used_bytes', 0), ('uid', 0), ('endpoint', 'other'),
                           ('quota_returncode', 1), ('raw_quota_output', RAW + 'changed')]:
            value_snapshot = copy.deepcopy(self.snapshot)
            value_snapshot[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                validate_snapshot(value_snapshot, self.expected, now=1010)

    def test_stale_and_future_snapshots_never_admit_new_work(self):
        for now in (999, 1121):
            with self.assertRaises(RuntimeError):
                validate_snapshot(self.snapshot, self.expected, now=now)

    def test_pre_query_credit_deduplicates_inodes_and_ignores_new_writes(self):
        with tempfile.TemporaryDirectory(prefix='pubchem_quota_credit_') as name:
            root = Path(name)
            one = root / 'one'
            one.write_bytes(b'x' * 8192)
            os.link(one, root / 'alias')
            info = one.stat()
            root_info = root.stat()
            expected = info.st_blocks * 512 + root_info.st_blocks * 512
            self.assertEqual(observed_old_own_blocks(root, time.time() + 1), expected)
            self.assertEqual(observed_old_own_blocks(root, 0), 0)
            self.assertEqual(observed_old_own_blocks(root, None), 0)

    def test_large_output_ledger_receives_query_start_and_unknown_cutoff_gets_zero_credit(self):
        with tempfile.TemporaryDirectory(prefix='pubchem_quota_ledger_') as name:
            root = Path(name)
            path = root / 'snapshot.json'
            snapshot = copy.deepcopy(self.snapshot)
            snapshot['generated_unix_seconds'] = time.time()
            cutoff = snapshot['generated_unix_seconds'] - 1
            snapshot['quota_query_started_unix_seconds'] = cutoff
            path.write_text(__import__('json').dumps(snapshot))
            plan = dict(quota_snapshot=str(path), quota_authority=self.expected,
                        output_cap_bytes=1000000, other_future_reserved_bytes=0, minimum_free_bytes=0)
            observed = []
            def ledger(stamp):
                observed.append(stamp)
                return 4000
            value = budget_check(plan, 5000, root, ledger)
            self.assertEqual(observed, [cutoff])
            self.assertEqual(value['account_credited_own_pre_query_blocks_bytes'], 4000)
            del snapshot['quota_query_started_unix_seconds']
            path.write_text(__import__('json').dumps(snapshot))
            self.assertEqual(budget_check(plan, 5000, root, ledger)['account_credited_own_pre_query_blocks_bytes'], 0)
            self.assertEqual(observed, [cutoff])


if __name__ == '__main__':
    unittest.main()
