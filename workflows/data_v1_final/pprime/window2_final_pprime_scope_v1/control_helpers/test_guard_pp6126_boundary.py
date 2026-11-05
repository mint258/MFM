"""One new proc-mock case: child-free is insufficient if a call timer exists."""
import contextlib,importlib.util,io,json,signal,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('guard_under_test',HERE/'guard_pp6126_ram.py')
G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)

class GuardBoundary(unittest.TestCase):
    def test_never_park_native_timer_or_child_and_resume_exact_own_park(self):
        parent={'pid':100,'start':1,'uids':(G.H.UID,)*4,'job':G.H.JOB,'argv':('python','-m',G.H.MODULE),'cgroup':'exact','state':'S','ppid':1}
        worker=dict(parent,pid=200,start=2,ppid=100,argv=('python','-c','from multiprocessing.spawn import spawn_main; spawn_main()','--multiprocessing-fork'))
        class Fake:
            def __init__(self):self.state='S';self.events=[];self.child=[];self.race=None
            def identity(self,pid):return dict(parent) if pid==100 else dict(worker,state=self.state)
            def children(self,pid):return self.child
            def unsafe_paths(self,pid,base):return []
            def send(self,bound,number):
                self.events.append(number);self.state='T' if number==signal.SIGSTOP else 'S'
                if number==signal.SIGSTOP and self.race:self.race()
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);call=base/('wp4native_%s_%s_toy'%(G.H.UID,G.H.JOB));call.mkdir()
            parked={};proc=Fake();self.assertFalse(G.try_park(proc,parent,worker,base,parked));self.assertEqual(proc.events,[])
            # Remove only this fixture's freshly created empty directory.
            call.rmdir();proc.child=[300];self.assertFalse(G.try_park(proc,parent,worker,base,parked));self.assertEqual(proc.events,[])
            proc.child=[];self.assertTrue(G.try_park(proc,parent,worker,base,parked));self.assertEqual(proc.events,[signal.SIGSTOP]);self.assertIn(200,parked)
            good=types.SimpleNamespace(f_blocks=(G.THRESHOLD+4*G.H.GIB)//4096,f_files=G.INODES+10,f_bavail=(G.THRESHOLD+2*G.H.GIB)//4096,f_frsize=4096,f_favail=G.INODES+1)
            bad=types.SimpleNamespace(f_blocks=100,f_files=G.INODES+10,f_bavail=1,f_frsize=4096,f_favail=G.INODES+1)
            state=base/'parked_recovery.json'
            with patch.object(G.os,'statvfs',return_value=good):
                self.assertTrue(G.safe_exit(proc,parent,base,parked,state))
            self.assertEqual(proc.events,[signal.SIGSTOP,signal.SIGCONT]);self.assertEqual(parked,{})
            proc=Fake();proc.race=lambda:call.mkdir()
            self.assertFalse(G.try_park(proc,parent,worker,base,{}));self.assertEqual(proc.events,[signal.SIGSTOP,signal.SIGCONT])
            call.rmdir();proc=Fake();parked={};self.assertTrue(G.try_park(proc,parent,worker,base,parked))
            output=io.StringIO()
            with contextlib.redirect_stdout(output),patch.object(G.os,'statvfs',return_value=bad):
                self.assertFalse(G.safe_exit(proc,parent,base,parked,state))
            self.assertEqual(proc.events,[signal.SIGSTOP]);saved=json.loads(state.read_text())
            self.assertEqual(saved['parked_workers'][0]['pid'],200);self.assertEqual(saved['parked_workers'][0]['start'],2)
            self.assertTrue(G.H.worker_ok(G.restored(saved['parked_workers'][0])))
            self.assertIn('--resume-state',output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()),patch.object(G.os,'statvfs',side_effect=OSError('unknown')):
                self.assertFalse(G.safe_exit(proc,parent,base,parked,state))
            self.assertEqual(proc.events,[signal.SIGSTOP]);self.assertIn('CAPACITY_UNKNOWN',json.loads(state.read_text())['reason'])
            with patch.object(G.os,'statvfs',return_value=good):
                self.assertTrue(G.safe_exit(proc,parent,base,parked,state))
            self.assertEqual(proc.events,[signal.SIGSTOP,signal.SIGCONT]);self.assertEqual(json.loads(state.read_text())['parked_workers'],[])

if __name__=='__main__':unittest.main()
