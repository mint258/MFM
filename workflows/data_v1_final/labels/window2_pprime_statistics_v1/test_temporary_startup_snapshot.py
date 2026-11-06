"""One focused startup-only regression; no real disk, env or sleep operations."""
import io,json,unittest
from pathlib import Path
from unittest.mock import patch
from . import temporary as T

class StartupSnapshot(unittest.TestCase):
    def test_stale_future_wait_before_writes_then_fresh_and_invalid_policy_raises(self):
        from workflows.data_v1_final.export.v31_stream_v1 import disk_guard as D,quota_snapshot as Q
        env_writes=[];directories=[];waits=[];attempts=[]
        class Environment(dict):
            def __setitem__(self,key,value):env_writes.append((key,value));super().__setitem__(key,value)
        names=('TMPDIR','TMP','TEMP','SQLITE_TMPDIR');environment=Environment({name:'original' for name in names})
        root=Path('/share/synthetic-approved-temporary')
        plan={'temporary_root':str(root),'temporary_spill_limit_bytes':1024,'disk_protection':{'poll_seconds':1,'targets':['synthetic']}}
        def untouched():
            self.assertEqual(env_writes,[]);self.assertEqual(directories,[])
            self.assertEqual(dict(environment),{name:'original' for name in names});self.assertEqual(T.tempfile.tempdir,'original-temp-cache')
        class Guard:
            def target(self,path):return {'facts':{'root_filesystem':False},'budget':{'peak_additional_bytes':4096}}
            def wait(self,path,**kwargs):untouched();waits.append((str(path),kwargs))
        guard=Guard();stamps=iter((1000.0,1007.0,1005.0))
        def from_plan(spec,required,admit):
            untouched();self.assertTrue(required);self.assertFalse(admit)
            stamp=next(stamps);attempts.append(stamp)
            snapshot={'schema':Q.SCHEMA,'uid':1278,'filesystem':'/share','available_bytes':123456,'observed_time':stamp}
            try:
                with patch('builtins.open',side_effect=lambda *args,**kwargs:io.StringIO(json.dumps(snapshot))):
                    Q.read_available('synthetic-quota.json',expected_uid=1278,expected_filesystem='/share',max_age_seconds=5,now=1006.0)
            except Q.SnapshotUnavailable as error:
                raise D.DiskUnavailable('ACCOUNT_QUOTA_SNAPSHOT_UNKNOWN:'+repr(error)) from error
            return guard
        def mkdir(path,*args,**kwargs):
            self.assertEqual(waits,[(str(root),{'inodes_needed':1})]);untouched();directories.append(str(path))
        with patch.object(T.os,'environ',environment),patch.object(T.tempfile,'tempdir','original-temp-cache'),patch.object(T.Path,'mkdir',autospec=True,side_effect=mkdir),patch.object(T.time,'sleep',side_effect=lambda delay:untouched()) as sleep,patch.object(D,'from_plan',side_effect=from_plan),patch('builtins.print'):
            runtime=T.activate(plan,admit=False)
            self.assertIs(runtime.guard,guard);self.assertEqual(attempts,[1000.0,1007.0,1005.0])
            self.assertEqual(sleep.call_count,2);self.assertEqual(directories,[str(root)])
            self.assertEqual(env_writes,[(name,str(root)) for name in names]);self.assertEqual(T.tempfile.tempdir,str(root))
            before=(list(env_writes),list(directories),sleep.call_count,T.tempfile.tempdir)
            with patch.object(D,'from_plan',side_effect=D.DiskUnavailable('EXPLICIT_QUOTA_SCOPE_REQUIRED')):
                with self.assertRaisesRegex(D.DiskUnavailable,'EXPLICIT_QUOTA_SCOPE_REQUIRED'):T.activate(plan,admit=False)
            self.assertEqual((env_writes,directories,sleep.call_count,T.tempfile.tempdir),before)