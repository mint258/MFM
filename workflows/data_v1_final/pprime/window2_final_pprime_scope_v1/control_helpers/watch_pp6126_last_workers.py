"""Root-run fast quiescent watcher for the last two already bound pool workers.

Preparation only; default preview sends no signals and copies no bytes.
All actual rotation safeguards stay in the previously tested helper.
"""
import argparse,fcntl,importlib.util,json,os,subprocess,time
from pathlib import Path

HERE=Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('rotation_helper',HERE/'rotate_pp6126_scratch_quiescent.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
WATCH=(2867698,2867713)

class NoChildrenProc:
    def __init__(self,proc):self.proc=proc
    def __getattr__(self,name):return getattr(self.proc,name)
    def descendants(self,pid):
        # Treat a zombie as occupied too; never STOP at an in-flight reap edge.
        if self.proc.children(pid):raise H.Skip('CHILD_OR_ZOMBIE_AT_QUIESCENT_BOUNDARY')
        return self.proc.descendants(pid)

def aliased(worker,target):
    prefix='wp5engine_%s_%s_%s_'%(H.UID,H.JOB,worker['pid'])
    for source in Path('/tmp').glob('dv1_ppfill_'+H.JOB+'_*'):
        if not source.is_symlink() or source.lstat().st_uid!=H.UID:continue
        resolved=source.resolve()
        if not H.below(str(resolved),target.resolve()):continue
        if any(child.name.startswith(prefix) for child in resolved.iterdir()):return True
    return False

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-pid',type=int,required=True);parser.add_argument('--target-root',required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    H.require(os.getuid()==H.UID,'MAIN_UID_REQUIRED')
    H.require(hasattr(os,'pidfd_open') and hasattr(__import__('signal'),'pidfd_send_signal'),'SYSTEM_PYTHON_PIDFD_REQUIRED')
    target=Path(args.target_root).absolute()
    H.require(target.is_dir() and not target.is_symlink() and target.lstat().st_uid==H.UID,'EXISTING_OWNED_RAM_TARGET_REQUIRED')
    mount=subprocess.check_output(['findmnt','-n','-T',str(target),'-o','TARGET,FSTYPE,SOURCE'],text=True)
    H.require('tmpfs' in mount.split() and H.below(str(target.resolve()),Path('/dev/shm')),'ACTUAL_RAM_FILESYSTEM_REQUIRED')
    for command in (['findmnt','-T',str(target)],['df','-B1','-P',str(target)],['df','-Pi',str(target)]):
        print(subprocess.check_output(command,text=True),flush=True)
    proc=H.Proc();strict=NoChildrenProc(proc);parent=proc.identity(args.parent_pid)
    H.require(H.parent_ok(parent),'EXACT_FINAL_NATIVE_PARENT_REQUIRED')
    workers={};origins={}
    for pid in WATCH:
        worker=proc.identity(pid)
        H.require(H.worker_ok(worker) and worker['ppid']==parent['pid'] and worker['cgroup']==parent['cgroup'],'EXACT_FOCUSED_WORKER_REQUIRED')
        if not aliased(worker,target):
            try:origins[pid]=H.scratch_for(worker,Path('/tmp'));workers[pid]=worker
            except H.Skip:
                if not aliased(worker,target):raise
    print(json.dumps({'preview':not args.execute,'exact_parent':parent['pid'],'remaining':list(workers),'poll_ms':5}),flush=True)
    if not args.execute or not workers:return
    # Bound source copies to the rotation helper's64MiB limit per worker.
    # Existing RAM usage/partial copies already reduce real available capacity.
    guard=H.Capacity(target,len(workers)*64*1024**2,len(workers)*65536);guard.check()
    previous={}
    with Path('/dev/shm/window2_scratch_rotation_4526126.lock').open('a') as lock:
        while workers:
            if not H.same(parent,proc.identity(parent['pid'])):
                print(json.dumps({'status':'PARENT_EXITED_OR_CHANGED_NO_ACTION'}),flush=True);return
            for pid,worker in list(workers.items()):
                if origins[pid].is_symlink() and H.below(str(origins[pid].resolve()),target.resolve()):
                    del workers[pid];print(json.dumps({'worker':pid,'status':'ALREADY_ALIASED'}),flush=True);continue
                if not H.same(worker,proc.identity(pid)):
                    del workers[pid];print(json.dumps({'worker':pid,'status':'EXITED_OR_CHANGED_NO_SIGNAL'}),flush=True);continue
                if proc.children(pid):continue
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:continue
                try:
                    if proc.children(pid):continue
                    guard.check();current=proc.identity(pid)
                    H.require(H.same(worker,current),'FOCUSED_WORKER_CHANGED_BEFORE_ROTATION')
                    result=H.rotate_one(strict,parent,current,origins[pid],target,guard)
                    if result['status']=='ROTATED':del workers[pid]
                    if result['status']=='ROTATED' or previous.get(pid)!=result.get('reason'):
                        print(json.dumps(result),flush=True);previous[pid]=result.get('reason')
                except (H.Skip,OSError) as error:
                    if previous.get(pid)!=str(error):print(json.dumps({'worker':pid,'status':'SKIP','reason':str(error)}),flush=True);previous[pid]=str(error)
                finally:fcntl.flock(lock,fcntl.LOCK_UN)
            if workers:time.sleep(0.005)
    print(json.dumps({'status':'BOTH_FOCUSED_WORKERS_ALIASED'}),flush=True)

if __name__=='__main__':main()
