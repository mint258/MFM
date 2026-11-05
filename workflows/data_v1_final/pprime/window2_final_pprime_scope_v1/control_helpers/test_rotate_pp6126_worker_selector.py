"""New selector-only case; do not rerun the already passed rotation fixture."""
import importlib.util,unittest
from pathlib import Path

HERE=Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('rotation_under_test',HERE/'rotate_pp6126_scratch_quiescent.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)

class WorkerSelector(unittest.TestCase):
    def test_direct_spawn_workers_without_reading_racing_native_grandchildren(self):
        parent={'pid':2866924,'cgroup':'/slurm/job_'+R.JOB}
        base={'uids':(R.UID,)*4,'job':R.JOB,'ppid':parent['pid'],'cgroup':parent['cgroup']}
        entries={pid:dict(base,pid=pid,argv=('python','-c',
            'from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=8, pipe_handle=20)','--multiprocessing-fork')) for pid in range(2867694,2867726)}
        entries[2867690]=dict(base,pid=2867690,argv=('python','-c','from multiprocessing.resource_tracker import main; main(7)'))
        entries[2867689]=None  # another direct child already exited
        class FakeProc:
            def children(self,pid):self_parent=parent['pid'];assert pid==self_parent;return list(entries)
            def identity(self,pid):return entries[pid]
            def descendants(self,pid):raise AssertionError('DISCOVERY_MUST_NOT_RECURSE_INTO_NATIVE_RACES')
        selected=R.direct_workers(FakeProc(),parent)
        self.assertEqual(len(selected),32);self.assertEqual({row['pid'] for row in selected},set(range(2867694,2867726)))
        self.assertTrue(all(R.worker_ok(row) for row in selected))

if __name__=='__main__':unittest.main()
