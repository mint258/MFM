"""One compact stdout stream, private guarded chunks, resumable byte concat."""
import argparse,contextlib,json,os,pathlib,re,shlex,shutil,socket,subprocess,sys,uuid
from .disk_guard import from_plan,DiskUnavailable
P=pathlib.Path
MODULE='workflows.data_v1_final.export.v31_stream_v1.chunk_compaction'
BUFFER=1<<20


def save(path,value,guard=None):
    path=P(path)
    if guard:guard.wait(path,inodes_needed=2)
    path.parent.mkdir(parents=True,exist_ok=True);pending=path.with_name(path.name+'.writing')
    pending.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n',encoding='utf-8');os.replace(pending,path)


def read(path):return json.loads(P(path).read_text(encoding='utf-8-sig'))


def remote(target,action,*args):
    host=target['node']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',host) or host.startswith('-'):raise ValueError('EXPLICIT_SAFE_TARGET_HOST_REQUIRED')
    repository=target['repository'];python=target['python']
    argv=['env','PYTHONDONTWRITEBYTECODE=1','PYTHONPATH='+repository+'/current:'+repository,python,'-B','-m',MODULE,action,*map(str,args)]
    # Binary stdin is required; never add ssh -n.
    return ['ssh','-T','-o','BatchMode=yes',host,shlex.join(argv)]


def process_witness(pid):
    try:return P('/proc/%d/stat'%pid).read_text().split(') ',1)[1].split()[19]
    except FileNotFoundError:return None


def owner_path(path,attempt):
    path=P(path)
    if not isinstance(attempt,str) or not re.fullmatch(r'[0-9a-f]{32}',attempt):raise ValueError('OWNED_ATTEMPT_TOKEN_REQUIRED')
    if path.is_symlink():raise ValueError('OWNED_CHUNK_CANNOT_BE_A_SYMLINK')
    if path.parent.name!='D6_compact_'+attempt or not re.fullmatch(r'chunk_[0-9]{7}\.bin',path.name):raise ValueError('ONLY_OWNED_CHUNK_PATH_ALLOWED')
    return path


def receive(stream,path,limit,guard,attempt):
    path=owner_path(path,attempt);partial=path.with_name(path.name+'.partial')
    with contextlib.redirect_stdout(sys.stderr):guard.wait(path,limit,4)
    if path.exists():raise ValueError('EXISTING_CHUNK_MUST_NEVER_BE_OVERWRITTEN')
    path.parent.mkdir(parents=True,exist_ok=True);size=0
    with partial.open('xb') as output:
        while size<limit:
            data=stream.read(min(BUFFER,limit-size))
            if not data:break
            with contextlib.redirect_stdout(sys.stderr):guard.wait(path,len(data),1)
            output.write(data);size+=len(data)
        output.flush();os.fsync(output.fileno())
    if size==0:raise ValueError('EMPTY_CHUNK_NOT_CLOSED')
    os.replace(partial,path)
    return {'path':str(path),'bytes':size}


def preflight(target,guard,chunk_size,attempt):
    directory=P(target['directory'])/('D6_compact_'+attempt);budget=target['capacity_bytes']
    if type(budget)is not int or budget<=0:raise DiskUnavailable('EXPLICIT_POSITIVE_CHUNK_CAPACITY_REQUIRED')
    count=(budget+chunk_size-1)//chunk_size+4
    if target.get('node'):
        response=json.loads(subprocess.check_output(remote(target,'admit','--plan',target['guard_plan'],'--path',directory,'--limit',budget,'--inodes',count),text=True))
        if response.get('admitted') is not True or response.get('path')!=str(directory) or response.get('bytes')!=budget:raise ValueError('ACTUAL_RECEIVER_ADMISSION_PROTOCOL_DIFFERS')
    else:guard.wait(directory,budget,count)


def compact(plan,source,catalog_path,guard):
    """Closed full streams are reused. An interrupted prefix is never C0."""
    source=P(source);catalog_path=P(catalog_path);config=plan.get('chunk_compaction',{})
    previous=read(catalog_path) if catalog_path.is_file() else None
    if previous and previous['phase'] in ('CHUNKS_CLOSED','CONCATENATING','COMPLETE'):
        if previous['source']!=str(source):raise ValueError('CLOSED_COMPACT_SOURCE_CHANGED')
        return previous
    if previous:
        recovery=config.get('recover_incomplete_attempt',{})
        alive=previous.get('host')==socket.gethostname() and previous.get('pid') and previous.get('pid_start') is not None and process_witness(previous['pid'])==previous['pid_start']
        if alive or recovery.get('attempt')!=previous['attempt'] or recovery.get('confirmed_old_pid_dead') is not True:raise ValueError('INCOMPLETE_COMPACT_PREFIX_REQUIRES_ROOT_CONFIRMED_DEAD_ATTEMPT')
        save(catalog_path.with_name(catalog_path.stem+'_incomplete_'+previous['attempt']+'.json'),previous,guard)
    if not (source/'data.mdb').is_file():raise ValueError('CLOSED_RAW_LMDB_REQUIRED')
    upper=(source/'data.mdb').stat().st_size;targets=config['targets'];chunk_size=config.get('chunk_bytes',4<<30)
    if type(chunk_size)is not int or chunk_size<=0:raise ValueError('POSITIVE_CHUNK_SIZE_REQUIRED')
    if sum(t['capacity_bytes'] for t in targets)<upper:raise DiskUnavailable('ADMITTED_CHUNK_CAPACITY_MUST_COVER_RAW_FILE_UPPER_BOUND')
    attempt=uuid.uuid4().hex
    for target in targets:preflight(target,guard,chunk_size,attempt)
    catalog={'schema':'D6_SINGLE_COMPACT_STREAM_CHUNKS_V1','phase':'COMPACTING','attempt':attempt,'source':str(source),
             'raw_file_bytes_upper_bound':upper,'chunks':[],'total_bytes':0,'host':socket.gethostname()}
    binary=shutil.which('mdb_copy') or '/share/apps/softwares/anaconda3/bin/mdb_copy'
    save(catalog_path,catalog,guard)
    process=subprocess.Popen([binary,'-c',str(source)],stdout=subprocess.PIPE,start_new_session=True)
    catalog.update(pid=process.pid,pid_start=process_witness(process.pid));save(catalog_path,catalog,guard)
    used=[0]*len(targets);target_index=0
    try:
        while True:
            first=process.stdout.read(1)
            if not first:break
            while target_index<len(targets) and used[target_index]>=targets[target_index]['capacity_bytes']:target_index+=1
            if target_index==len(targets):raise DiskUnavailable('COMPACT_EXCEEDED_CLOSED_RAW_UPPER_BOUND')
            target=targets[target_index];limit=min(chunk_size,target['capacity_bytes']-used[target_index]);number=len(catalog['chunks'])
            path=P(target['directory'])/('D6_compact_'+attempt)/('chunk_%07d.bin'%number)
            if target.get('node'):
                receiver=subprocess.Popen(remote(target,'receive','--plan',target['guard_plan'],'--path',path,'--limit',limit,'--attempt',attempt),stdin=subprocess.PIPE,stdout=subprocess.PIPE)
                try:
                    receiver.stdin.write(first);written=1
                    while written<limit:
                        data=process.stdout.read(min(BUFFER,limit-written))
                        if not data:break
                        receiver.stdin.write(data);written+=len(data)
                    receiver.stdin.close();response=receiver.stdout.read();returncode=receiver.wait()
                    if returncode:raise subprocess.CalledProcessError(returncode,receiver.args)
                    ref=json.loads(response)
                    if ref['path']!=str(path) or ref['bytes']!=written:raise ValueError('RECEIVER_CLOSED_CHUNK_BYTES_DIFFER')
                finally:
                    if not receiver.stdin.closed:receiver.stdin.close()
                    receiver.stdout.close()
            else:
                class Prefix:
                    def __init__(self):self.first=first
                    def read(self,n):
                        if self.first:
                            value=self.first;self.first=b'';return value
                        return process.stdout.read(n)
                ref=receive(Prefix(),path,limit,guard,attempt)
            used[target_index]+=ref['bytes'];ref.update(ordinal=number,target=target)
            catalog['chunks'].append(ref);catalog['total_bytes']+=ref['bytes'];save(catalog_path,catalog,guard)
        process.stdout.close();returncode=process.wait()
        if returncode:raise subprocess.CalledProcessError(returncode,process.args)
        if not catalog['chunks'] or catalog['total_bytes']>upper:raise ValueError('COMPACT_STREAM_SIZE_INVALID')
        catalog['phase']='CHUNKS_CLOSED';save(catalog_path,catalog,guard);return catalog
    except BaseException as exc:
        process.stdout.close()
        catalog['phase']='INCOMPLETE';catalog['error']=repr(exc);save(catalog_path,catalog,guard)
        # No partial/chunk deletion and no automatic new compact attempt.
        raise


def chunk_reader(ref):
    target=ref['target']
    if target.get('node'):
        process=subprocess.Popen(remote(target,'read','--path',ref['path'],'--limit',ref['bytes']),stdout=subprocess.PIPE)
        return process.stdout,process
    path=P(ref['path'])
    if path.stat().st_size!=ref['bytes']:raise ValueError('CLOSED_CHUNK_SIZE_DIFFERS')
    return path.open('rb'),None


def concatenate(catalog_path,destination,guard):
    catalog=read(catalog_path);destination=P(destination)
    if catalog['phase']=='COMPLETE':
        if catalog['concat']['destination']!=str(destination) or destination.stat().st_size!=catalog['total_bytes']:raise ValueError('CLOSED_CONCAT_DESTINATION_DIFFERS')
        return catalog
    if catalog['phase'] not in ('CHUNKS_CLOSED','CONCATENATING'):raise ValueError('FULL_C0_CHUNKS_REQUIRED_BEFORE_CONCAT')
    if 'concat' not in catalog:
        catalog['concat']={'destination':str(destination),'partial':str(destination)+'.partial','next_chunk':0,'bytes':0}
        catalog['phase']='CONCATENATING';save(catalog_path,catalog,guard)
    state=catalog['concat'];partial=P(state['partial'])
    if state['destination']!=str(destination):raise ValueError('CONCAT_DESTINATION_CHANGED')
    if destination.exists():
        if partial.exists() or state['next_chunk']!=len(catalog['chunks']) or destination.stat().st_size!=catalog['total_bytes']:raise ValueError('UNKNOWN_EXISTING_CONCAT_DESTINATION')
        catalog['phase']='COMPLETE';save(catalog_path,catalog,guard);return catalog
    guard.wait(destination,catalog['total_bytes']-state['bytes'],4);destination.parent.mkdir(parents=True,exist_ok=True)
    if not partial.exists() and state['bytes']:raise ValueError('CHECKPOINTED_CONCAT_PARTIAL_MISSING')
    if partial.exists() and partial.stat().st_size<state['bytes']:raise ValueError('CONCAT_PARTIAL_SHORTER_THAN_CHECKPOINT')
    with partial.open('r+b' if partial.exists() else 'xb') as output:
        output.truncate(state['bytes']);output.seek(state['bytes'])
        for ref in catalog['chunks'][state['next_chunk']:]:
            stream,process=chunk_reader(ref);size=0
            try:
                while True:
                    data=stream.read(BUFFER)
                    if not data:break
                    if size+len(data)>ref['bytes']:raise ValueError('CHUNK_EXCEEDS_CLOSED_SIZE')
                    guard.wait(destination,len(data),1);output.write(data);size+=len(data)
            finally:stream.close()
            if process is not None and process.wait():raise subprocess.CalledProcessError(process.returncode,process.args)
            if size!=ref['bytes']:raise ValueError('CHUNK_SHORTER_THAN_CLOSED_SIZE')
            output.flush();os.fsync(output.fileno())
            state['bytes']+=size;state['next_chunk']+=1;save(catalog_path,catalog,guard)
        if state['bytes']!=catalog['total_bytes']:raise ValueError('CONCAT_TOTAL_BYTES_DIFFER')
        output.flush();os.fsync(output.fileno())
    os.replace(partial,destination);catalog['phase']='COMPLETE';save(catalog_path,catalog,guard);return catalog


def cleanup(catalog_path,guard=None):
    """Only this attempt's private chunks, after the full concat is closed."""
    catalog=read(catalog_path)
    if catalog['phase']!='COMPLETE':raise ValueError('CLOSED_CONCAT_REQUIRED_FOR_CHUNK_LIFECYCLE')
    for ref in catalog['chunks']:
        target=ref['target']
        if target.get('node'):
            subprocess.run(remote(target,'cleanup','--path',ref['path'],'--limit',ref['bytes'],'--attempt',catalog['attempt']),check=True)
        else:remove_chunk(ref['path'],ref['bytes'],catalog['attempt'])
    catalog['chunks_consumed']=True;save(catalog_path,catalog,guard)


def remove_chunk(path,size,attempt):
    path=owner_path(path,attempt)
    if not path.exists():return
    if path.stat().st_size!=size:raise ValueError('PRIVATE_CHUNK_CHANGED_BEFORE_LIFECYCLE_END')
    path.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('admit','receive','read','cleanup'))
    parser.add_argument('--plan');parser.add_argument('--path',required=True);parser.add_argument('--limit',type=int,required=True)
    parser.add_argument('--inodes',type=int,default=4);parser.add_argument('--attempt');args=parser.parse_args()
    if args.limit<0:raise ValueError('NONNEGATIVE_STORAGE_BYTES_REQUIRED')
    if args.action=='read':
        if P(args.path).stat().st_size!=args.limit:raise ValueError('CLOSED_REMOTE_CHUNK_SIZE_DIFFERS')
        with P(args.path).open('rb') as stream:shutil.copyfileobj(stream,sys.stdout.buffer,BUFFER)
    elif args.action=='cleanup':remove_chunk(args.path,args.limit,args.attempt)
    else:
        with contextlib.redirect_stdout(sys.stderr):guard=from_plan(read(args.plan),required=True,admit=False)
        if args.action=='admit':
            with contextlib.redirect_stdout(sys.stderr):guard.wait(args.path,args.limit,args.inodes)
            print(json.dumps({'admitted':True,'path':args.path,'bytes':args.limit}),flush=True)
        else:print(json.dumps(receive(sys.stdin.buffer,args.path,args.limit,guard,args.attempt)),flush=True)


if __name__=='__main__':main()
