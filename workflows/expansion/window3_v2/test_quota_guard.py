"""Synthetic account-quota protection only; no real quota query or signals."""
import json
from pathlib import Path
import tempfile
import unittest

from .quota_guard import parse_quota,inspect_quota


class QuotaTests(unittest.TestCase):
    def test_real_native_format_uses_hard_limit_and_kibibytes(self):
        text='Disk quotas for user zixiao (uid 1278):\nFilesystem blocks quota limit grace files quota limit grace\n/dev/sda1 3962554700 0 4294967296 142150874 0 0\n'
        self.assertEqual(parse_quota(text,'zixiao',1278,'/dev/sda1')['available_bytes'],340390498304)
        with self.assertRaises(ValueError): parse_quota(text,'alpha',1264,'/dev/sda1')

    def test_quota_bytes_and_staleness_protect_the_account(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'quota.json'
            config=dict(path=str(path),uid=1278,reserve_bytes=100,planned_bytes=20,max_age_seconds=20)
            for free,safe in [(120,True),(119,False)]:
                path.write_text(json.dumps(dict(status='KNOWN',uid=1278,available_bytes=free,observed_unix_seconds=100)))
                self.assertEqual(inspect_quota(config,now=110)['safe'],safe)
            self.assertFalse(inspect_quota(config,now=121)['safe'])

    def test_unknown_wrong_identity_or_missing_capacity_never_allows_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'quota.json'
            config=dict(path=str(path),uid=1278,reserve_bytes=100,planned_bytes=20,max_age_seconds=20)
            for value in [dict(status='UNKNOWN'),dict(status='KNOWN',uid=1264),
                          dict(status='KNOWN',uid=1278,observed_unix_seconds=100)]:
                path.write_text(json.dumps(value))
                self.assertFalse(inspect_quota(config,now=110)['safe'])


if __name__ == '__main__':
    unittest.main()
