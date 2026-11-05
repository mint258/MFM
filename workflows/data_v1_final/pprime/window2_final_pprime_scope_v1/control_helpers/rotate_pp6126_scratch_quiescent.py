"""Root-only emergency scratch alias rotation. Default is metadata-only preview.

No Native process is signalled. Only an exact idle spawn worker can briefly
stop; every stopped worker is resumed in finally. Original trees are retained.
Run on the actual node after Root reviews fresh mount/capacity/process evidence.
"""
import argparse,fcntl,json,os,re,shutil,signal,stat,subprocess,time
from pathlib import Path

UID=1278
JOB='4526126'
MODULE='workflows.data_v1_final.pprime.window2_final_pprime_scope_v1.run'
GIB=1024**3

class Skip(Exception):pass
def require(ok,reason):
    if not ok:raise Skip(reason)
def below(path,root):
    try:Path(path.removesuffix(' (deleted)')).relative_to(root);return True
    except ValueError:return False
def same(a,b):
    return b is not None and all(a[key]==b[key] for key in ('pid','start','uids','job','argv','cgroup'))

class Proc:
    def identity(self,pid):
        try:
            directory=Path('/proc')/str(pid);text=(directory/'stat').read_text();tail=text[text.rfind(')')+2:].split()
            status=(directory/'status').read_text();uids=tuple(map(int,next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1:]))
            if uids!=(UID,)*4:return None
            env=(directory/'environ').read_bytes().split(b'\0')
            job=next((item.split(b'=',1)[1].decode() for item in env if item.startswith(b'SLURM_JOB_ID=')),None)
            return {'pid':pid,'ppid':int(tail[1]),'state':tail[0],'start':int(tail[19]),'uids':uids,'job':job,
                'argv':tuple(part.decode() for part in (directory/'cmdline').read_bytes().split(b'\0') if part),
                'cgroup':(directory/'cgroup').read_text()}
        except (OSError,ValueError,StopIteration):return None
    def children(self,pid):
        result=set()
        try:
            for task in (Path('/proc')/str(pid)/'task').iterdir():
                try:result.update(map(int,(task/'children').read_text().split()))
                except FileNotFoundError:continue
        except FileNotFoundError:return []
        return sorted(result)
    def descendants(self,pid):
        found=[];todo=self.children(pid);seen=set()
        while todo:
            child=todo.pop()
            if child in seen:continue
            seen.add(child);entry=self.identity(child)
            if entry is None:
                if (Path('/proc')/str(child)).exists():raise Skip('UNKNOWN_DESCENDANT_IDENTITY')
                continue
            found.append(entry);todo.extend(self.children(child))
        return found
    def unsafe_paths(self,pid,source):
        directory=Path('/proc')/str(pid);unsafe=[]
        if below(os.readlink(directory/'cwd'),source):unsafe.append('cwd')
        for descriptor in (directory/'fd').iterdir():
            try:
                target=os.readlink(descriptor)
                if not below(target,source):continue
                text=(directory/'fdinfo'/descriptor.name).read_text()
                flags=int(next(line.split()[1] for line in text.splitlines() if line.startswith('flags:')),8)
                if flags&os.O_ACCMODE or flags&os.O_DIRECTORY:unsafe.append('fd:'+descriptor.name)
            except FileNotFoundError:continue
        for line in (directory/'maps').read_text().splitlines():
            pieces=line.split(None,5)
            if len(pieces)==6 and 'w' in pieces[1] and below(pieces[5],source):unsafe.append('writable_mapping')
        return unsafe
    def send(self,bound,number):
        # pidfd prevents accidental signalling of a reused PID.
        fd=os.pidfd_open(bound['pid'],0)
        try:
            require(same(bound,self.identity(bound['pid'])),'PROCESS_IDENTITY_CHANGED_BEFORE_SIGNAL')
            signal.pidfd_send_signal(fd,number)
        finally:os.close(fd)

def parent_ok(entry):
    return entry and entry['uids']==(UID,)*4 and entry['job']==JOB and any(
        entry['argv'][i:i+2]==('-m',MODULE) for i in range(len(entry['argv'])-1))
def worker_ok(entry):
    return entry and entry['uids']==(UID,)*4 and entry['job']==JOB and '--multiprocessing-fork' in entry['argv'] and any(
        'from multiprocessing.spawn import spawn_main' in value for value in entry['argv'])

def direct_workers(proc,parent):
    # Discover only stable pool children. Native grandchildren may exit between
    # /proc reads; they remain checked conservatively inside rotate_one.
    result=[]
    for pid in proc.children(parent['pid']):
        entry=proc.identity(pid)
        if worker_ok(entry) and entry['ppid']==parent['pid'] and entry['cgroup']==parent['cgroup']:result.append(entry)
    return result

def tree(source):
    frames=[];size=0;inodes=0;device=source.lstat().st_dev
    for item in [source,*source.rglob('*')]:
        entry=item.lstat();require(entry.st_uid==UID and (stat.S_ISDIR(entry.st_mode) or stat.S_ISREG(entry.st_mode)),'NONOWNED_OR_NONREGULAR_SCRATCH')
        require(entry.st_dev==device,'NESTED_FILESYSTEM_IN_SCRATCH')
        frames.append((str(item.relative_to(source)),entry.st_dev,entry.st_ino,entry.st_mode,entry.st_size,entry.st_mtime_ns))
        size+=((entry.st_size+4095)//4096)*4096 if stat.S_ISREG(entry.st_mode) else 4096;inodes+=1
    return frames,size,inodes

def scratch_for(worker,source_parent):
    matching=[];prefix='wp5engine_%s_%s_%s_'%(UID,JOB,worker['pid'])
    for source in source_parent.glob('dv1_ppfill_'+JOB+'_*'):
        if source.is_symlink() or '_root_preserved_' in source.name or not source.is_dir():continue
        require(source.lstat().st_uid==UID,'SCRATCH_BASE_OWNER_DIFFERS')
        children=[child for child in source.iterdir() if child.name.startswith('wp5engine_')]
        ours=[child for child in children if child.name.startswith(prefix) and child.is_dir() and not child.is_symlink()]
        if ours:
            require(len(ours)==len(children)==1,'SCRATCH_BASE_NOT_EXCLUSIVE_TO_WORKER')
            matching.append(source)
    require(len(matching)==1,'NO_UNIQUE_ENGINE_WORKER_SCRATCH_BASE')
    return matching[0]

class Capacity:
    def __init__(self,target,copy_bytes,copy_inodes,workers=32):
        self.target=target;self.bytes=workers*GIB+20*GIB+copy_bytes
        self.inodes=workers*65536+1_000_000+copy_inodes
    def check(self):
        value=os.statvfs(self.target)
        require(value.f_blocks>0 and value.f_files>0,'UNKNOWN_DESTINATION_CAPACITY')
        require(value.f_bavail*value.f_frsize>self.bytes and value.f_favail>self.inodes,'DESTINATION_RESERVE_OR_INODE_BUDGET')

def rotate_one(proc,parent,worker,source,target,guard,max_bytes=64*1024**2,max_seconds=2):
    stopped=False;renamed=False;switched=False;preserved=None;destination=None
    try:
        require(parent_ok(proc.identity(parent['pid'])) and same(parent,proc.identity(parent['pid'])),'PARENT_IDENTITY_DIFFERS')
        require(worker_ok(proc.identity(worker['pid'])) and same(worker,proc.identity(worker['pid'])),'WORKER_IDENTITY_DIFFERS')
        require(proc.identity(worker['pid'])['ppid']==parent['pid'] and worker['cgroup']==parent['cgroup'],'WORKER_NOT_DIRECT_OWNED_POOL_DESCENDANT')
        require(worker['state'] not in ('T','t','Z','D') and proc.identity(worker['pid'])['state'] not in ('T','t','Z','D'),'WORKER_NOT_AVAILABLE_FOR_QUIESCENT_ROTATION')
        require(not [child for child in proc.descendants(worker['pid']) if child['state']!='Z'],'ACTIVE_CHILD_SKIP_NO_SIGNAL')
        require(not proc.unsafe_paths(worker['pid'],source),'SCRATCH_IN_USE_SKIP_NO_SIGNAL')
        guard.check();deadline=time.monotonic()+max_seconds
        stopped=True;proc.send(worker,signal.SIGSTOP)
        while True:
            now=proc.identity(worker['pid']);require(same(worker,now),'WORKER_CHANGED_AFTER_STOP')
            if now['state']=='T':break
            require(time.monotonic()<deadline,'STOP_NOT_CONFIRMED');time.sleep(0.005)
        require(same(parent,proc.identity(parent['pid'])),'PARENT_CHANGED_AFTER_STOP')
        require(not [child for child in proc.descendants(worker['pid']) if child['state']!='Z'],'RACE_CHILD_CONT_AND_SKIP')
        require(not proc.unsafe_paths(worker['pid'],source),'RACE_WRITABLE_SCRATCH_CONT_AND_SKIP')
        require(scratch_for(worker,source.parent)==source,'SCRATCH_BINDING_CHANGED')
        frames,size,inodes=tree(source);require(size<=max_bytes,'QUIESCENT_COPY_TOO_LARGE_SKIP')
        stamp=str(time.time_ns());destination=target/(source.name+'_worker_'+str(worker['pid'])+'_'+stamp)
        def check_copy():
            require(time.monotonic()<deadline,'QUIESCENT_COPY_BUDGET_EXCEEDED_CONT')
            guard.check()
        def copy_file(left,right):
            check_copy();result=shutil.copy2(left,right);check_copy();return result
        check_copy();shutil.copytree(source,destination,copy_function=copy_file);check_copy()
        require(tree(source)[0]==frames,'SCRATCH_CHANGED_DURING_COPY_CONT_AND_SKIP')
        require(same(worker,proc.identity(worker['pid'])) and proc.identity(worker['pid'])['state']=='T','WORKER_NOT_STOPPED_BEFORE_SWITCH')
        require(not [child for child in proc.descendants(worker['pid']) if child['state']!='Z'],'RACE_CHILD_BEFORE_SWITCH')
        require(not proc.unsafe_paths(worker['pid'],source),'SCRATCH_REOPENED_BEFORE_SWITCH')
        require(same(parent,proc.identity(parent['pid'])),'PARENT_CHANGED_BEFORE_SWITCH')
        check_copy()
        preserved=source.with_name(source.name+'_root_preserved_'+str(worker['pid'])+'_'+stamp)
        require(source.lstat().st_dev==source.parent.stat().st_dev,'SOURCE_RENAME_NOT_SAME_FILESYSTEM')
        os.rename(source,preserved);renamed=True
        os.symlink(destination,source,target_is_directory=True);switched=True
        return {'worker':worker['pid'],'status':'ROTATED','original_path':str(source),'ram_path':str(destination),'preserved_root':str(preserved),'copied_bytes_bound':size,'inodes':inodes}
    except (Skip,OSError) as error:
        return {'worker':worker['pid'],'status':'SKIPPED','reason':str(error),'partial_ram_retained':str(destination) if destination else None}
    finally:
        try:
            # Inspect namespace, not just Python flags: interruption may occur
            # immediately after rename/symlink returns, before its flag update.
            if preserved is not None and preserved.exists() and not os.path.lexists(source):
                os.rename(preserved,source)
        finally:
            if stopped:
                current=proc.identity(worker['pid'])
                if same(worker,current):
                    try:proc.send(worker,signal.SIGCONT)
                    except ProcessLookupError:pass  # the exact process exited

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--parent-pid',type=int,required=True)
    parser.add_argument('--target-root',required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();require(os.getuid()==UID,'MAIN_UID_REQUIRED')
    require(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'PIDFD_SUPPORT_REQUIRED')
    source_parent=Path('/tmp');target=Path(args.target_root).absolute()
    existing=target if target.exists() else target.parent
    require(existing.is_dir() and below(str(existing.resolve()),Path('/dev/shm')),'VERIFIED_RAM_TARGET_REQUIRED')
    mount=subprocess.check_output(['findmnt','-n','-T',str(existing),'-o','TARGET,FSTYPE,SOURCE'],text=True)
    require('tmpfs' in mount.split(),'DESTINATION_NOT_TMPFS')
    for place in (source_parent,existing):
        for command in (['findmnt','-T',str(place)],['df','-B1','-P',str(place)],['df','-Pi',str(place)]):
            print(subprocess.check_output(command,text=True),flush=True)
    proc=Proc();parent=proc.identity(args.parent_pid);require(parent_ok(parent),'EXACT_FINAL_PPRIME_PARENT_REQUIRED')
    workers=direct_workers(proc,parent)
    require(0<len(workers)<=32,'EXPECTED_ORIGINAL_32_WORKER_POOL')
    pairs=[];bytes_to_copy=0;inodes_to_copy=0
    for worker in workers:
        try:
            source=scratch_for(worker,source_parent);_,size,inodes=tree(source)
            pairs.append((worker,source));bytes_to_copy+=size;inodes_to_copy+=inodes
        except (Skip,OSError) as error:print(json.dumps({'worker':worker['pid'],'status':'PREVIEW_SKIP','reason':str(error)}),flush=True)
    guard=Capacity(existing,bytes_to_copy,inodes_to_copy);guard.check()
    print(json.dumps({'preview':not args.execute,'parent':parent['pid'],'workers':len(workers),'eligible_roots':len(pairs),'copy_bytes_bound':bytes_to_copy,'reserved_bytes':guard.bytes,'reserved_inodes':guard.inodes}),flush=True)
    if not args.execute:return
    target.mkdir(mode=0o700,parents=False,exist_ok=True)
    require(target.lstat().st_uid==UID and not target.is_symlink(),'OWNED_RAM_DIRECTORY_REQUIRED')
    guard.target=target
    with (target.parent/('window2_scratch_rotation_'+JOB+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for worker,source in pairs:
            guard.check();print(json.dumps(rotate_one(proc,parent,worker,source,target,guard)),flush=True)

if __name__=='__main__':main()
