"""One toy-filesystem/proc-mock fixture. Never signals an actual process."""
import importlib.util,signal,tempfile,types,unittest
from pathlib import Path

HERE=Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('rotation_under_test',HERE/'rotate_pp6126_scratch_quiescent.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)

class RotationToy(unittest.TestCase):
    def test_quiescent_alias_preserves_bytes_and_races_always_continue(self):
        class FakeProc:
            def __init__(self,race=False):
                self.parent={'pid':100,'ppid':1,'start':10,'uids':(R.UID,)*4,'job':R.JOB,'state':'S','argv':('python','-m',R.MODULE),'cgroup':'/slurm/'+R.JOB}
                self.worker={'pid':200,'ppid':100,'start':20,'uids':(R.UID,)*4,'job':R.JOB,'state':'S',
                    'argv':('python','-c','from multiprocessing.spawn import spawn_main; spawn_main()','--multiprocessing-fork'),'cgroup':self.parent['cgroup']}
                self.events=[];self.race=race
            def identity(self,pid):return dict(self.parent if pid==100 else self.worker)
            def descendants(self,pid):
                return [dict(self.worker,pid=300,state='S')] if self.race and self.worker['state']=='T' else []
            def unsafe_paths(self,pid,source):return []
            def send(self,bound,number):
                self.events.append(number);self.worker['state']='T' if number==signal.SIGSTOP else 'S'
        class Guard:
            def __init__(self,fail=False):self.calls=0;self.fail=fail
            def check(self):
                self.calls+=1
                if self.fail and self.calls>1:raise R.Skip('TOY_CAPACITY_RESERVE_REACHED')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source_parent=root/'rootfs';source_parent.mkdir();target=root/'ram';target.mkdir()
            def make_source(suffix):
                source=source_parent/('dv1_ppfill_'+R.JOB+'_'+suffix);source.mkdir()
                work=source/('wp5engine_%s_%s_200_owned'%(R.UID,R.JOB));work.mkdir()
                (work/'closed.dat').write_bytes(b'unchanged\x00\x01native bytes')
                return source,work.name
            source,workname=make_source('toy00000');proc=FakeProc()
            result=R.rotate_one(proc,dict(proc.parent),dict(proc.worker),source,target,Guard(),max_seconds=30)
            self.assertEqual(result['status'],'ROTATED');self.assertEqual(proc.events,[signal.SIGSTOP,signal.SIGCONT])
            self.assertTrue(source.is_symlink());preserved=Path(result['preserved_root'])
            self.assertTrue(preserved.is_dir());self.assertFalse(preserved.is_symlink())
            self.assertEqual((source/workname/'closed.dat').read_bytes(),(preserved/workname/'closed.dat').read_bytes())
            self.assertEqual((source/workname).parent,source)  # frozen lexical-parent cleanup rule
            (source/'new_call.dat').write_bytes(b'RAM new call')
            self.assertTrue((Path(result['ram_path'])/'new_call.dat').exists());self.assertFalse((preserved/'new_call.dat').exists())
            racing,_=make_source('toy11111');proc=FakeProc(race=True)
            skipped=R.rotate_one(proc,dict(proc.parent),dict(proc.worker),racing,target,Guard(),max_seconds=30)
            self.assertEqual(skipped['status'],'SKIPPED');self.assertIn('RACE_CHILD',skipped['reason'])
            self.assertEqual(proc.events,[signal.SIGSTOP,signal.SIGCONT]);self.assertFalse(racing.is_symlink())
            # Same worker has two original roots now; remove nothing. Use a fresh
            # toy source parent to test a copy-stage capacity failure separately.
            other=root/'rootfs2';other.mkdir();failed=other/('dv1_ppfill_'+R.JOB+'_toy22222');failed.mkdir()
            (failed/('wp5engine_%s_%s_200_owned'%(R.UID,R.JOB))).mkdir()
            proc=FakeProc();skipped=R.rotate_one(proc,dict(proc.parent),dict(proc.worker),failed,target,Guard(True),max_seconds=30)
            self.assertEqual(skipped['status'],'SKIPPED');self.assertEqual(proc.events,[signal.SIGSTOP,signal.SIGCONT])
            self.assertFalse(failed.is_symlink());self.assertEqual(proc.worker['state'],'S')

if __name__=='__main__':unittest.main()
