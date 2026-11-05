"""Optional Root-owned RAM boundary guard; never park a Native timer phase.

Default preview performs metadata reads only. Execute only while Root owns
monitoring. Exit resumes only with capacity confirmed; otherwise exact parked
identities are saved atomically to CONTROL for Root's explicit safe recovery.
"""
import argparse,fcntl,importlib.util,json,os,shlex,signal,subprocess,time
from pathlib import Path

HERE=Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('rotation_helper',HERE/'rotate_pp6126_scratch_quiescent.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
THRESHOLD=52*H.GIB
INODES=32*65536+1_000_000

def no_call_directory(base):
    return not any(path.name.startswith('wp4native_%s_%s_'%(H.UID,H.JOB)) for path in base.iterdir())

def try_park(proc,parent,worker,base,parked_workers):
    stopped=False;parked=False
    try:
        current=proc.identity(worker['pid'])
        H.require(H.same(parent,proc.identity(parent['pid'])) and H.same(worker,current),'EXACT_IDENTITY_REQUIRED')
        H.require(current['state'] not in ('T','t','Z','D') and current['ppid']==parent['pid'],'ONLY_OWN_RUNNING_POOL_WORKER')
        H.require(not proc.children(worker['pid']) and no_call_directory(base),'NOT_BETWEEN_NATIVE_CALLS')
        H.require(not proc.unsafe_paths(worker['pid'],base),'SCRATCH_STILL_IN_USE')
        stopped=True;proc.send(worker,signal.SIGSTOP);deadline=time.monotonic()+0.25
        while True:
            current=proc.identity(worker['pid']);H.require(H.same(worker,current),'WORKER_CHANGED_AFTER_STOP')
            if current['state']=='T':break
            H.require(time.monotonic()<deadline,'STOP_NOT_CONFIRMED');time.sleep(0.002)
        H.require(H.same(parent,proc.identity(parent['pid'])),'PARENT_CHANGED_AFTER_STOP')
        H.require(not proc.children(worker['pid']) and no_call_directory(base),'RACE_NATIVE_OR_TIMER_PHASE_CONTINUE')
        H.require(not proc.unsafe_paths(worker['pid'],base),'RACE_SCRATCH_FD_CONTINUE')
        # Register before returning, so an INT between return and caller code
        # cannot strand a stopped worker outside the outer finally registry.
        parked_workers[worker['pid']]=worker;parked=True;return True
    except (H.Skip,OSError):return False
    finally:
        if stopped and not parked and H.same(worker,proc.identity(worker['pid'])):
            try:proc.send(worker,signal.SIGCONT)
            except ProcessLookupError:pass

def resume(proc,worker):
    if H.same(worker,proc.identity(worker['pid'])):
        try:proc.send(worker,signal.SIGCONT);return True
        except ProcessLookupError:return True  # exact old process has exited
    return False

def resume_capacity(target):
    try:
        value=os.statvfs(target)
        if value.f_blocks<=0 or value.f_files<=0:return False,'UNKNOWN_FILESYSTEM_CAPACITY'
        available=value.f_bavail*value.f_frsize
        if available<THRESHOLD+H.GIB or value.f_favail<=INODES:
            return False,'RAM_OR_INODES_BELOW_RESUME_RESERVE:bytes=%s,inodes=%s'%(available,value.f_favail)
        return True,'RESUME_RESERVE_CONFIRMED'
    except OSError as error:return False,'CAPACITY_UNKNOWN:'+str(error)

def safe_exit(proc,parent,target,parked,state_path):
    """Never resume writers on an unsafe/unknown filesystem just to exit."""
    reason='NO_PARKED_WORKERS'
    for pid,worker in list(parked.items()):
        allowed,reason=resume_capacity(target)
        if not allowed:break
        try:
            if resume(proc,worker):del parked[pid]
            else:reason='OWNED_WORKER_IDENTITY_CHANGED_OR_UNAVAILABLE_NO_SIGNAL'
        except (H.Skip,OSError) as error:reason='OWNED_RESUME_NOT_CONFIRMED:'+str(error)
    state_path=Path(state_path)
    if parked or state_path.exists():
        fields=('pid','ppid','start','uids','job','argv','cgroup')
        state={'schema':'WINDOW2_RAM_SAFE_BOUNDARY_RECOVERY_V1','job':H.JOB,'target_root':str(target),
            'status':'PARKED_PENDING_CAPACITY_RECOVERY' if parked else 'RESUMED_WITH_CAPACITY_CONFIRMED',
            'reason':reason,'parent':{key:parent[key] for key in fields},
            'parked_workers':[{key:worker[key] for key in fields} for worker in parked.values()],
            'resume_bytes':THRESHOLD+H.GIB,'resume_inodes_strictly_above':INODES,
            'confirmed_no_native_or_timer_at_park':True}
        temporary=state_path.with_name(state_path.name+'.writing')
        temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');os.replace(temporary,state_path)
    if parked:
        command='/usr/bin/python3 -B '+shlex.quote(str(HERE/'guard_pp6126_ram.py'))+' --resume-state '+shlex.quote(str(state_path))+' --execute'
        print(json.dumps({'status':'LEFT_SAFELY_PARKED_NO_CONT','reason':reason,'state_file':str(state_path),'root_recovery_command':command}),flush=True)
    return not parked

def restored(entry):
    return dict(entry,uids=tuple(entry['uids']),argv=tuple(entry['argv']))

def owned_ram_base(worker,target):
    prefix='wp5engine_%s_%s_%s_'%(H.UID,H.JOB,worker['pid'])
    matches=[]
    for source in Path('/tmp').glob('dv1_ppfill_'+H.JOB+'_*'):
        if not source.is_symlink() or source.lstat().st_uid!=H.UID:continue
        base=source.resolve()
        if H.below(str(base),target.resolve()) and any(path.name.startswith(prefix) for path in base.iterdir()):matches.append(base)
    H.require(len(matches)==1,'EXACT_ALREADY_ROTATED_RAM_BASE_REQUIRED')
    return matches[0]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--target-root');parser.add_argument('--resume-state');parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    H.require(os.getuid()==H.UID,'MAIN_UID_REQUIRED')
    H.require(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'SYSTEM_PYTHON_PIDFD_REQUIRED')
    recovery=json.loads(Path(args.resume_state).read_text()) if args.resume_state else None
    if recovery:H.require(recovery['schema']=='WINDOW2_RAM_SAFE_BOUNDARY_RECOVERY_V1' and recovery['job']==H.JOB,'EXACT_RECOVERY_STATE_REQUIRED')
    else:H.require(args.parent_pid and args.target_root,'PARENT_AND_RAM_TARGET_REQUIRED')
    target=Path(recovery['target_root'] if recovery else args.target_root).absolute()
    H.require(target.is_dir() and not target.is_symlink() and target.lstat().st_uid==H.UID,'OWNED_RAM_TARGET_REQUIRED')
    mount=subprocess.check_output(['findmnt','-n','-T',str(target),'-o','TARGET,FSTYPE,SOURCE'],text=True)
    H.require('tmpfs' in mount.split() and H.below(str(target.resolve()),Path('/dev/shm')),'ACTUAL_RAM_REQUIRED')
    for command in (['findmnt','-T',str(target)],['df','-B1','-P',str(target)],['df','-Pi',str(target)]):print(subprocess.check_output(command,text=True),flush=True)
    proc=H.Proc()
    if recovery:
        parent=restored(recovery['parent']);parked={entry['pid']:restored(entry) for entry in recovery['parked_workers']}
        H.require(all(H.worker_ok(worker) for worker in parked.values()),'EXACT_OWNED_RECOVERY_WORKERS_REQUIRED')
        if args.execute:safe_exit(proc,parent,target,parked,args.resume_state)
        else:print(json.dumps({'preview':True,'parked_workers':list(parked),'capacity':resume_capacity(target)}),flush=True)
        return
    parent=proc.identity(args.parent_pid);H.require(H.parent_ok(parent),'EXACT_NATIVE_PARENT_REQUIRED')
    print(json.dumps({'preview':not args.execute,'reserve_bytes':THRESHOLD,'resume_bytes':THRESHOLD+H.GIB,'reserve_inodes':INODES}),flush=True)
    if not args.execute:return
    parked={};bases={}
    def exit_requested(number,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGINT,exit_requested);signal.signal(signal.SIGTERM,exit_requested)
    try:
        with Path('/dev/shm/window2_scratch_rotation_4526126.lock').open('a') as lock:
            while H.same(parent,proc.identity(parent['pid'])):
                capacity=os.statvfs(target);available=capacity.f_bavail*capacity.f_frsize
                H.require(capacity.f_blocks>0 and capacity.f_files>0,'CAPACITY_UNKNOWN_ROOT_MUST_TAKE_OVER')
                if available>=THRESHOLD+H.GIB and capacity.f_favail>INODES:
                    for pid,worker in list(parked.items()):
                        allowed,_=resume_capacity(target)
                        if not allowed:break
                        if resume(proc,worker):del parked[pid];print(json.dumps({'worker':pid,'status':'CONT_CAPACITY_RESTORED'}),flush=True)
                elif available<THRESHOLD or capacity.f_favail<=INODES:
                    for worker in H.direct_workers(proc,parent):
                        pid=worker['pid']
                        if pid in parked or proc.children(pid):continue
                        try:
                            if pid not in bases:bases[pid]=owned_ram_base(worker,target)
                            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        except (H.Skip,OSError):continue
                        try:
                            if try_park(proc,parent,worker,bases[pid],parked):print(json.dumps({'worker':pid,'status':'PARKED_AT_CONFIRMED_NO_TIMER_BOUNDARY'}),flush=True)
                        finally:fcntl.flock(lock,fcntl.LOCK_UN)
                time.sleep(0.005 if available<THRESHOLD else 0.1)
    finally:
        signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN)
        safe_exit(proc,parent,target,parked,HERE/'pp6126_ram_guard_parked_state.json')

if __name__=='__main__':main()
