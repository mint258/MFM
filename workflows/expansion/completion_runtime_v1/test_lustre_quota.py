"""Boundary checks for the separate Lustre quota authority."""
import copy
import hashlib
import unittest
from . import lustre_quota as Q

RAW = ('Disk quotas for usr zixiao (uid 1278):\n'
       '     Filesystem  kbytes   quota   limit   grace   files   quota   limit   grace\n'
       '/lfshome/zixiao 183436556 0 2147483648 - 32268237 0 0 -\n'
       'uid 1278 is using default file quota setting\n')


class LustreQuotaTests(unittest.TestCase):
    def snapshot(self):
        return dict(schema=Q.SCHEMA, kind='lustre', status='ACTUAL_FRESH_ACCOUNT_QUOTA',
                    endpoint='202.38.247.57:22', uid=1278, username='zixiao',
                    filesystem='/lfshome/zixiao', generated_unix_seconds=1000,
                    quota_query_started_unix_seconds=999,
                    used_bytes=183436556*1024, hard_limit_bytes=2147483648*1024,
                    raw_quota_output=RAW, raw_quota_sha256=hashlib.sha256(RAW.encode()).hexdigest(),
                    actual_quota_command=['lfs', 'quota', '-u', 'zixiao', '/lfshome/zixiao'],
                    quota_returncode=0, publisher={'pid': 1})

    def authority(self):
        return dict(kind='lustre', endpoint='202.38.247.57:22', uid=1278,
                    filesystem='/lfshome/zixiao', publisher={'pid': 1})

    def test_actual_lustre_zero_soft_limit_uses_positive_hard(self):
        result = Q.validate_snapshot(self.snapshot(), self.authority(), now=1001)
        self.assertEqual(result['hard_limit_bytes'], 2*1024**4)
        self.assertEqual(result['free_account_bytes'], (2147483648-183436556)*1024)

    def test_owner_device_duplicates_and_unknown_allowance_rejected(self):
        for raw in (RAW.replace('uid 1278):', 'uid 42):'),
                    RAW.replace('/lfshome/zixiao', '/share/home/zixiao'),
                    RAW + '/lfshome/zixiao 1 0 2147483648 - 0 0 0 -\n',
                    RAW.replace('2147483648', '0')):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                Q.parse_quota(raw, '/lfshome/zixiao', 'zixiao', 1278)

    def test_wrapped_device_and_positive_soft_remain_conservative(self):
        raw = RAW.replace('/lfshome/zixiao 183436556 0 2147483648',
                          '/lfshome/zixiao\n 183436556 1900000000 2147483648')
        self.assertEqual(Q.parse_quota(raw, '/lfshome/zixiao', 'zixiao', 1278),
                         (183436556*1024, 1900000000*1024))

    def test_stale_future_or_changed_provenance_rejected(self):
        for mutate in (lambda s: s.update(generated_unix_seconds=879),
                       lambda s: s.update(generated_unix_seconds=1002),
                       lambda s: s.update(raw_quota_output=RAW+'changed'),
                       lambda s: s.update(hard_limit_bytes=10**20),
                       lambda s: s.update(actual_quota_command=['df', '-P']),
                       lambda s: s.update(publisher={'pid': 2})):
            snapshot = copy.deepcopy(self.snapshot())
            mutate(snapshot)
            with self.subTest(snapshot=snapshot), self.assertRaises(RuntimeError):
                Q.validate_snapshot(snapshot, self.authority(), now=1001)

    def test_share_authority_cannot_credit_lustre(self):
        authority = self.authority()
        authority['kind'] = 'share'
        with self.assertRaises(RuntimeError):
            Q.validate_snapshot(self.snapshot(), authority, now=1001)


if __name__ == '__main__':
    unittest.main()
