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
    def test_published_inode_keeps_writer_open_and_failed_publish_keeps_current(self):
        import os
        from unittest.mock import patch
        real_open=open;real_replace=os.replace;opened=[];checks=[];allowed=[True]
        def admit(available):
            if not allowed[0]:raise Q.SnapshotUnavailable('TOY_ADMISSION_FAILED')
        def tracked_open(*args,**kwargs):
            handle=real_open(*args,**kwargs)
            if len(args)>1 and args[1]=='w':opened.append(handle)
            return handle
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fresh-quota.json';publisher=Q.AtomicPublisher(path,admit)
            def replace(source,destination):
                candidate=opened[-1]
                self.assertFalse(candidate.closed);self.assertTrue(candidate.writable())
                self.assertEqual(os.fstat(candidate.fileno()).st_ino,os.stat(source).st_ino)
                if publisher.current_file is not None:self.assertFalse(publisher.current_file.closed)
                real_replace(source,destination)
                self.assertFalse(candidate.closed) # remains open through rename
                checks.append(os.stat(destination).st_ino)
            try:
                with patch('builtins.open',side_effect=tracked_open),patch.object(Q.os,'replace',side_effect=replace):
                    publisher.publish({'available_bytes':123,'generation':1})
                    first=publisher.current_file;self.assertFalse(first.closed)
                    self.assertEqual(json.loads(path.read_text())['generation'],1)
                    self.assertEqual(os.fstat(first.fileno()).st_ino,os.stat(path).st_ino)
                    publisher.publish({'available_bytes':123,'generation':2})
                    current=publisher.current_file;self.assertTrue(first.closed);self.assertFalse(current.closed)
                    self.assertEqual(json.loads(path.read_text())['generation'],2)
                    self.assertEqual(os.fstat(current.fileno()).st_ino,os.stat(path).st_ino)
                    before=path.read_bytes()
                    with patch.object(Q.os,'replace',side_effect=OSError('TOY_REPLACE_FAILED')):
                        with self.assertRaisesRegex(OSError,'TOY_REPLACE_FAILED'):publisher.publish({'available_bytes':123,'generation':3})
                    self.assertTrue(opened[-1].closed);self.assertIs(publisher.current_file,current)
                    self.assertFalse(current.closed);self.assertEqual(path.read_bytes(),before)
                    count=len(opened);allowed[0]=False
                    with self.assertRaisesRegex(Q.SnapshotUnavailable,'TOY_ADMISSION_FAILED'):publisher.publish({'available_bytes':123,'generation':4})
                    self.assertEqual(len(opened),count);self.assertFalse(current.closed)
                    self.assertEqual(path.read_bytes(),before)
                self.assertEqual(len(checks),2)
            finally:publisher.close()
            self.assertTrue(current.closed);self.assertIsNone(publisher.current_file)