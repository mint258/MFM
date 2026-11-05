"""One toy FS/subprocess fixture; no dataset, Native or scientific replay."""
import copy,json,os,pathlib,signal,subprocess,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from . import disk_guard as D,run as R


class DiskGuardCheck(unittest.TestCase):
    def test_admission_reserves_pause_resume_and_closed_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);gib=1<<30;state={'bytes':100*gib,'inodes':1000,'quota':500_000_000_000};commands=[]
            def statvfs(path):
                return SimpleNamespace(f_frsize=4096,f_bavail=state['bytes']//4096,f_favail=state['inodes'])
            def command(argv):
                commands.append(argv)
                if argv[0]=='findmnt':return json.dumps({'filesystems':[{'target':'/','source':'toy-device','fstype':'toyfs'}]})
                if argv[:2]==['df','-B1']:return 'Size Avail\n%d %d\n'%(200*gib,state['bytes'])
                if argv[:2]==['df','-Pi']:return 'Filesystem Inodes IUsed IFree IUse%% Mounted on\ntoy 10000 9000 %d 90%% /\n'%state['inodes']
                if argv==['toy-quota']:return str(state['quota'])
                raise AssertionError(argv)
            spec={'paths':[str(root)],'peak_additional_bytes':20*gib,'peak_additional_inodes':20,
                  'reserve_bytes':gib,'reserve_inodes':5,'concurrent_bytes':2*gib,'concurrent_inodes':3,
                  'runtime_margin_bytes':gib,'runtime_margin_inodes':4,'quota_scope':'limited',
                  'quota_probe_argv':['toy-quota'],'quota_peak_additional_bytes':30*gib,
                  'quota_concurrent_bytes':gib,'quota_reserve_bytes':1}
            config={'targets':[spec],'poll_seconds':1}
            signals=[];spawned=[];outer=self
            class Process:
                pid=43210;returncode=0
                def __init__(self,argv,**kwargs):
                    outer.assertEqual(kwargs,{'start_new_session':True});spawned.append(argv);self.calls=0
                def poll(self):
                    self.calls+=1
                    if self.calls==1:state['bytes']=21*gib;return None
                    if self.calls==2:state['bytes']=100*gib;return None
                    return 0
            original_inspect=D.inspect
            def inspect(path):return dict(original_inspect(path),root_filesystem=True)
            with patch.object(D,'inspect',side_effect=inspect),patch.object(D,'command',side_effect=command),patch.object(D.os,'statvfs',side_effect=statvfs),patch.object(D.time,'sleep'),patch.object(D.time,'monotonic',side_effect=lambda:len(commands)*10),patch.object(D.subprocess,'Popen',Process),patch.object(D.os,'killpg',side_effect=lambda pid,sig:signals.append((pid,sig))):
                guard=D.Guard(config)
                self.assertEqual(guard.targets[0]['budget']['reserve_bytes'],20*gib)
                self.assertEqual(guard.targets[0]['budget']['quota_reserve_bytes'],100_000_000_000)
                self.assertTrue(any(c[:3]==['findmnt','--json','-T'] for c in commands))
                self.assertTrue(any(c[:2]==['df','-B1'] for c in commands));self.assertTrue(any(c[:2]==['df','-Pi'] for c in commands))
                guard.check(root/'new.partial',gib,1)
                state['bytes']=21*gib
                with self.assertRaisesRegex(D.DiskUnavailable,'DISK_RESERVE_REACHED'):guard.check(root)
                state['bytes']=100*gib;state['inodes']=10
                with self.assertRaisesRegex(D.DiskUnavailable,'DISK_RESERVE_REACHED'):guard.check(root)
                state['inodes']=1000;state['quota']=100_000_000_000
                with self.assertRaisesRegex(D.DiskUnavailable,'ACCOUNT_QUOTA'):guard.check(root)
                state['quota']=500_000_000_000
                with self.assertRaisesRegex(D.DiskUnavailable,'NOT_UNIQUELY_BUDGETED'):guard.check(root.parent/'unbudgeted')
                bad=copy.deepcopy(config);bad['targets']*=2
                with self.assertRaisesRegex(D.DiskUnavailable,'MUST_BE_COMBINED'):D.Guard(bad)
                bad=copy.deepcopy(config);bad['targets'][0]['peak_additional_bytes']=150*gib
                with self.assertRaisesRegex(D.DiskUnavailable,'DISK_RESERVE_REACHED'):D.Guard(bad)
                with self.assertRaisesRegex(D.DiskUnavailable,'EXPLICIT_DISK_PROTECTION'):D.from_plan({},required=True)
                guard.run(['toy-rsync','--sparse','source','owned.partial'],root/'owned.partial',gib,1)
                self.assertEqual(spawned,[['toy-rsync','--sparse','source','owned.partial']])
                self.assertEqual(signals,[(43210,signal.SIGSTOP),(43210,signal.SIGCONT)])
                partial=root/'preserved.partial';partial.write_text('toy existing partial')
                state['bytes']=21*gib
                with self.assertRaisesRegex(D.DiskUnavailable,'DISK_RESERVE_REACHED'):D.Guard(config)
                self.assertEqual(partial.read_text(),'toy existing partial')
            # The producer check result closes once; a storage-only continuation
            # loads it rather than calling the numerical checker again.
            with patch.object(R,'sample_check',return_value={'toy':'closed'}) as checker:
                roots={'TRAIN':root/'toy-compact'}
                self.assertEqual(R.closed_sample_check([],roots,root),{'toy':'closed'})
                self.assertEqual(R.closed_sample_check([],roots,root),{'toy':'closed'});checker.assert_called_once()
                with self.assertRaisesRegex(ValueError,'CHECK_ROOTS_CHANGED'):R.closed_sample_check([],{'TRAIN':root/'different'},root)


if __name__=='__main__':unittest.main()
