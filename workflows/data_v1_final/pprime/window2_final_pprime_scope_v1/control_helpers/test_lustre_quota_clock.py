"""One metadata-only Lustre quota clock-bound regression."""
import unittest
from . import lustre_non_native_writer_guard as G
from workflows.data_v1_final.export.v31_stream_v1.quota_snapshot import SnapshotUnavailable

class LustreQuotaClock(unittest.TestCase):
    def test_real_parse_default_and_biased_time_keep_strict_freshness(self):
        text='Disk quotas for usr zixiao (uid 1278):\nFilesystem kbytes quota limit grace files quota limit grace\n/lfshome 1098705652 0 2147483648 - 38481903 0 0 -\nuid 1278 is using default file quota setting\n'
        plain=G.quota_observation({},text,100.0)
        biased=G.quota_observation({'quota_clock_safety_bias_seconds':1.25},text,100.0)
        for value in (plain,biased):
            self.assertEqual(value['schema'],'LUSTRE_USER_QUOTA_AVAILABLE_V1')
            self.assertEqual((value['uid'],value['filesystem']),(1278,'/lfshome'))
            self.assertEqual((value['used_KiB'],value['hard_KiB']),(1098705652,2147483648))
            self.assertEqual(value['available_bytes'],(2147483648-1098705652)*1024)
            self.assertEqual(value['source_probe_time'],100.0)
        self.assertEqual((plain['clock_safety_bias_seconds'],plain['observed_time']),(0,100.0))
        self.assertEqual((biased['clock_safety_bias_seconds'],biased['observed_time']),(1.25,98.75))
        G.fresh(biased,'LUSTRE_USER_QUOTA_AVAILABLE_V1',100.0-0.35,5)
        with self.assertRaisesRegex(G.Unsafe,'FUTURE_OR_STALE'):G.fresh(plain,'LUSTRE_USER_QUOTA_AVAILABLE_V1',100.0-0.35,5)
        with self.assertRaisesRegex(G.Unsafe,'FUTURE_OR_STALE'):G.fresh(biased,'LUSTRE_USER_QUOTA_AVAILABLE_V1',100.0+5.001-0.35,5)
        for invalid in (-0.1,float('nan'),float('inf'),5,True):
            with self.assertRaises(SnapshotUnavailable):G.quota_observation({'quota_clock_safety_bias_seconds':invalid},text,100.0)