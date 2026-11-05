"""One memory-only real-shaped autofs/NFS stack and quota-dispatch fixture."""
import copy,json,pathlib,sys,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from . import disk_guard as D


class AutofsGuardCheck(unittest.TestCase):
    def test_real_nfs_stack_unique_device_and_fresh_snapshot_dispatch(self):
        autofs={'target':'/share/home','source':'systemd-1','fstype':'autofs'}
        nfs={'target':'/share/home','source':'nfs:/share/home','fstype':'nfs4'}
        mounts=[autofs,nfs];events=[]
        def stat(path):events.append(('stat',str(path)));return SimpleNamespace(st_dev=0 if str(path)=='/' else 42)
        def command(argv):
            events.append(('command',argv[0]))
            if argv[0]=='findmnt':return json.dumps({'filesystems':mounts})
            if argv[:2]==['df','-B1']:return 'Size Avail\n200000000000 100000000000\n'
            if argv[:2]==['df','-Pi']:return 'Filesystem Inodes IUsed IFree IUse% Mounted on\nnfs 10000 1000 9000 10% /share/home\n'
            raise AssertionError(argv)
        filesystem=SimpleNamespace(f_frsize=4096,f_bavail=100000000000//4096,f_favail=9000)
        reader=Mock(return_value=200000000000)
        fake_snapshot=SimpleNamespace(read_available=reader)
        with patch.object(D,'existing',side_effect=lambda p:pathlib.Path(p)),patch.object(D.P,'resolve',lambda p:p),patch.object(D.os,'stat',side_effect=stat),patch.object(D.os,'statvfs',return_value=filesystem),patch.object(D,'command',side_effect=command),patch.dict(sys.modules,{'workflows.data_v1_final.export.v31_stream_v1.quota_snapshot':fake_snapshot}):
            result=D.inspect('/share/home/toy')
            self.assertEqual(result['mount'],nfs);self.assertEqual(events[0],('stat','/share/home/toy'))
            self.assertFalse(result['root_filesystem'])
            mounts[:]=[autofs]
            with self.assertRaisesRegex(D.DiskUnavailable,'TARGET_MOUNT_UNKNOWN'):D.inspect('/share/home/toy')
            mounts[:]=[autofs,nfs,dict(nfs,source='different:/share/home')]
            with self.assertRaisesRegex(D.DiskUnavailable,'AMBIGUOUS'):D.inspect('/share/home/toy')
            mounts[:]=[autofs,dict(nfs,target='/different')]
            with self.assertRaisesRegex(D.DiskUnavailable,'TARGET_MOUNT_UNKNOWN'):D.inspect('/share/home/toy')
            mounts[:]=[autofs,nfs]
            spec={'paths':['/share/home/toy'],'peak_additional_bytes':4096,'peak_additional_inodes':2,
                  'reserve_bytes':4096,'reserve_inodes':2,'concurrent_bytes':4096,'concurrent_inodes':2,
                  'runtime_margin_bytes':4096,'runtime_margin_inodes':2,'quota_scope':'limited',
                  'quota_available_reference':{'path':'memory:quota.json'},'quota_max_age_seconds':5,
                  'quota_expected_uid':1278,'quota_expected_filesystem':'/share',
                  'quota_peak_additional_bytes':4096,'quota_concurrent_bytes':4096,'quota_reserve_bytes':100000000000}
            guard=D.Guard({'targets':[spec]});self.assertEqual(reader.call_count,1)
            guard.check('/share/home/toy/file');self.assertEqual(reader.call_count,2)
            reader.assert_called_with({'path':'memory:quota.json'},expected_uid=1278,expected_filesystem='/share',max_age_seconds=5)
            reader.side_effect=RuntimeError('toy stale snapshot')
            with self.assertRaisesRegex(D.DiskUnavailable,'ACCOUNT_QUOTA_SNAPSHOT_UNKNOWN'):guard.check('/share/home/toy/file')


if __name__=='__main__':unittest.main()
