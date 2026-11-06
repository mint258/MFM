"""One metadata-only fixture for the shared quota publisher and reader."""
import json,tempfile,unittest
from pathlib import Path
from . import quota_snapshot as Q

class QuotaSnapshot(unittest.TestCase):
    def test_exact_kib_parse_atomic_failure_and_fail_closed_reader(self):
        text='Disk quotas for User zixiao (1278)\nFilesystem              Blocks      Quota      Limit  Warn/Time      Mounted on\n/dev/sda1           3806059840          0 4294967296   00 [--------] /share\n'
        parsed=Q.parse_xfs(text);self.assertEqual(parsed['available_bytes'],(4294967296-3806059840)*1024)
        for bad in (text.replace('(1278)','(1)'),text.replace('/share','/other'),text.replace('4294967296','0'),text+'another row\n'):
            with self.assertRaises(Q.SnapshotUnavailable):Q.parse_xfs(bad)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'quota.json';value={'schema':Q.SCHEMA,'uid':1278,'filesystem':'/share',**parsed,'observed_time':1000.0}
            Q.atomic_write(path,value,lambda available:self.assertEqual(available,parsed['available_bytes']))
            def read(**changes):
                args={'expected_uid':1278,'expected_filesystem':'/share','max_age_seconds':5,'now':1005};args.update(changes)
                return Q.read_available({'path':str(path)},**args)
            self.assertEqual(read(),parsed['available_bytes']);self.assertEqual(read(now=1000),parsed['available_bytes'])
            for args in ({'now':1005.001},{'now':999.999},{'max_age_seconds':5.1},{'expected_uid':1},{'expected_filesystem':'/other'}):
                with self.assertRaises(Q.SnapshotUnavailable):read(**args)
            before=path.read_bytes()
            def deny(unused):raise Q.SnapshotUnavailable('TOY_CAPACITY_UNKNOWN')
            with self.assertRaises(Q.SnapshotUnavailable):Q.atomic_write(path,dict(value,observed_time=1004),deny)
            self.assertEqual(path.read_bytes(),before)
            for changes in ({'uid':True},{'available_bytes':True},{'available_bytes':-1},{'observed_time':float('nan')},{'schema':'other'}):
                path.write_text(json.dumps(dict(value,**changes)))
                with self.assertRaises(Q.SnapshotUnavailable):read()
            path.write_text('{bad json')
            with self.assertRaises(Q.SnapshotUnavailable):read()
            with self.assertRaises(Q.SnapshotUnavailable):Q.read_available(str(path.parent/'missing'),expected_uid=1278,expected_filesystem='/share',max_age_seconds=5,now=1000)
    def test_conservative_clock_bias_preserves_strict_freshness(self):
        import io
        from unittest.mock import patch
        source=1000.0;offset=0.995
        plain={'schema':Q.SCHEMA,'uid':1278,'filesystem':'/share','available_bytes':123,**Q.observation_times(source)}
        biased=dict(plain,**Q.observation_times(source,1.25))
        self.assertEqual((biased['source_probe_time'],biased['observed_time']),(1000.0,998.75))
        self.assertEqual(plain['observed_time'],source)
        def read(value,now):
            with patch('builtins.open',side_effect=lambda *args,**kwargs:io.StringIO(json.dumps(value))):
                return Q.read_available('metadata-only.json',expected_uid=1278,expected_filesystem='/share',max_age_seconds=5,now=now)
        with self.assertRaisesRegex(Q.SnapshotUnavailable,'FUTURE_OR_STALE'):read(plain,source-offset)
        self.assertEqual(read(biased,source-offset),123)
        self.assertEqual(read(biased,biased['observed_time']+5),123)
        with self.assertRaisesRegex(Q.SnapshotUnavailable,'FUTURE_OR_STALE'):read(biased,biased['observed_time']+5.001)
        with self.assertRaisesRegex(Q.SnapshotUnavailable,'FUTURE_OR_STALE'):read(biased,source+5.001-offset)
        for invalid in (-0.001,float('nan'),float('inf'),float('-inf'),5,6,10**1000,True,'1.25'):
            with self.assertRaisesRegex(Q.SnapshotUnavailable,'CLOCK_SAFETY_BIAS'):Q.observation_times(source,invalid)