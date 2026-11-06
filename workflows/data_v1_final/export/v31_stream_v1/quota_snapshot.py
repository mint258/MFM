"""One login-host XFS quota probe shared by compute-side disk guards."""
import argparse,json,math,os,re,subprocess,time
from pathlib import Path

SCHEMA='XFS_USER_QUOTA_AVAILABLE_V1'
UID=1278
FILESYSTEM='/share'
COMMAND=['/usr/sbin/xfs_quota','-c','quota -u -b zixiao',FILESYSTEM]

class SnapshotUnavailable(RuntimeError):pass


def parse_xfs(text):
    """Parse the actual non-human-readable KiB quota format, never infer unlimited."""
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if len(lines)!=3 or lines[0]!='Disk quotas for User zixiao (1278)' or lines[1].split()!=['Filesystem','Blocks','Quota','Limit','Warn/Time','Mounted','on']:
        raise SnapshotUnavailable('XFS_QUOTA_HEADER_OR_RECORD_COUNT')
    match=re.fullmatch(r'(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(/share)',lines[2])
    if match is None:raise SnapshotUnavailable('XFS_QUOTA_ROW_OR_MOUNT')
    used,soft,hard=map(int,match.group(2,3,4))
    if hard<=0:raise SnapshotUnavailable('XFS_EXPLICIT_POSITIVE_HARD_LIMIT_REQUIRED')
    return {'used_KiB':used,'soft_KiB':soft,'hard_KiB':hard,'available_bytes':max(0,hard-used)*1024}


def number(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False


def observation_times(source_probe_time,clock_safety_bias_seconds=0):
    """Publish an older bound; never extend the reader's five-second lifetime."""
    bias=clock_safety_bias_seconds
    if not number(bias) or not 0<=bias<5:
        raise SnapshotUnavailable('CLOCK_SAFETY_BIAS_MUST_BE_FINITE_NONNEGATIVE_BELOW_5S')
    if not number(source_probe_time) or source_probe_time-bias<=0:
        raise SnapshotUnavailable('SOURCE_PROBE_TIME_MUST_BE_FINITE_AND_POSITIVE')
    return {'source_probe_time':source_probe_time,'clock_safety_bias_seconds':bias,'observed_time':source_probe_time-bias}

def read_available(reference,*,expected_uid,expected_filesystem,max_age_seconds,now=None):
    """Read and validate freshness on every call; no subprocess or cached age."""
    try:
        if type(expected_uid)is not int or expected_uid!=UID or expected_filesystem!=FILESYSTEM:
            raise SnapshotUnavailable('EXPLICIT_SNAPSHOT_UID_AND_FILESYSTEM_REQUIRED')
        if not number(max_age_seconds) or not 0<max_age_seconds<=5:
            raise SnapshotUnavailable('SNAPSHOT_MAX_AGE_MUST_BE_AT_MOST_5S')
        path=reference['path'] if isinstance(reference,dict) else reference
        if not isinstance(path,(str,Path)):raise SnapshotUnavailable('SNAPSHOT_REFERENCE_PATH_REQUIRED')
        with open(path,'r',encoding='utf-8') as handle:
            data=handle.read(4097)
        if len(data)>4096:raise SnapshotUnavailable('SNAPSHOT_TOO_LARGE')
        value=json.loads(data)
        if not isinstance(value,dict) or value.get('schema')!=SCHEMA:
            raise SnapshotUnavailable('SNAPSHOT_SCHEMA')
        if type(value.get('uid'))is not int or value['uid']!=expected_uid or value.get('filesystem')!=expected_filesystem:
            raise SnapshotUnavailable('SNAPSHOT_UID_OR_FILESYSTEM')
        available=value.get('available_bytes');observed=value.get('observed_time');current=time.time() if now is None else now
        if type(available)is not int or available<0:raise SnapshotUnavailable('SNAPSHOT_AVAILABLE_BYTES')
        if not number(observed) or observed<=0 or not number(current):raise SnapshotUnavailable('SNAPSHOT_TIME')
        age=current-observed
        if age<0 or age>max_age_seconds:raise SnapshotUnavailable('SNAPSHOT_FUTURE_OR_STALE')
        return available
    except SnapshotUnavailable:raise
    except (OSError,ValueError,TypeError,KeyError) as error:
        raise SnapshotUnavailable('SNAPSHOT_UNREADABLE:'+repr(error)) from error


class AtomicPublisher:
    """Keep each new inode open for write before and throughout publication.

    Linux3.10 fs/locks.c generic_add_lease rejects READ leases while a local
    writer is open; newer NFSD checks conflicting local opens itself. Holding
    this FD prevents a newly published snapshot acquiring a READ delegation.
    An existing old target may already have a delegation: the first replace
    can still wait for that old lease. Root may select a fresh metadata path;
    this helper neither removes the old target nor changes NFS settings.
    """
    def __init__(self,path,admit):self.path=Path(path);self.admit=admit;self.current_file=None
    def publish(self,value):
        data=json.dumps(value,separators=(',',':'))+'\n'
        if len(data.encode('utf-8'))>4096:raise SnapshotUnavailable('SNAPSHOT_TOO_LARGE')
        self.admit(value['available_bytes'])
        partial=self.path.with_name('.'+self.path.name+'.'+str(os.getpid())+'.partial')
        candidate=open(partial,'w',encoding='utf-8')
        try:
            candidate.write(data);candidate.flush()
            # Do not close before rename or reopen only after publication: that
            # would expose a window for the NFS reader's READ delegation.
            os.replace(partial,self.path)
        except BaseException:
            candidate.close() # The still-current published FD remains owned.
            raise
        previous=self.current_file;self.current_file=candidate
        if previous is not None:previous.close() # Only after successful replace.
    def close(self):
        if self.current_file is not None:self.current_file.close();self.current_file=None
    def __enter__(self):return self
    def __exit__(self,*unused):self.close()


def atomic_write(path,value,admit):
    """Compatibility for one-shot callers; recurring publishers retain the object."""
    with AtomicPublisher(path,admit) as publisher:publisher.publish(value)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--reserve-bytes',type=int,default=100_000_000_000)
    parser.add_argument('--clock-safety-bias-seconds',type=float,default=0);args=parser.parse_args()
    observation_times(time.time(),args.clock_safety_bias_seconds)
    if os.getuid()!=UID:raise SnapshotUnavailable('ACTUAL_MAIN_UID_REQUIRED')
    path=Path(args.output).absolute()
    if not path.parent.is_dir() or not path.is_relative_to(Path(FILESYSTEM)) or args.reserve_bytes<100_000_000_000:
        raise SnapshotUnavailable('EXISTING_SHARE_CONTROL_DIRECTORY_AND_SITE_RESERVE_REQUIRED')
    from .disk_guard import inspect
    facts=inspect(path.parent)
    if os.stat(FILESYSTEM).st_dev!=facts['device']:raise SnapshotUnavailable('CONTROL_TARGET_FILESYSTEM_MISMATCH')
    reserve=args.reserve_bytes
    if facts['root_filesystem']:reserve=max(reserve,10*(1<<30),(facts['total']+9)//10)
    def admit(available):
        stat=os.statvfs(path.parent)
        if os.stat(path.parent).st_dev!=facts['device'] or stat.f_bavail*stat.f_frsize<reserve+65536 or stat.f_favail<10 or available<args.reserve_bytes+65536:
            raise SnapshotUnavailable('SNAPSHOT_CONTROL_DISK_OR_QUOTA_RESERVE')
    print(json.dumps({'phase':'QUOTA_SNAPSHOT_PUBLISHER','uid':UID,'filesystem':FILESYSTEM,'output':str(path),'interval_seconds':2,'clock_safety_bias_seconds':args.clock_safety_bias_seconds}),flush=True)
    with AtomicPublisher(path,admit) as publisher:
        while True:
            started=time.monotonic()
            try:
                text=subprocess.check_output(COMMAND,text=True,timeout=2)
                value={'schema':SCHEMA,'uid':UID,'filesystem':FILESYSTEM,**parse_xfs(text),**observation_times(time.time(),args.clock_safety_bias_seconds)}
                publisher.publish(value)
            except (SnapshotUnavailable,OSError,subprocess.SubprocessError) as error:
                print(json.dumps({'phase':'QUOTA_SNAPSHOT_UNAVAILABLE','reason':repr(error),'previous_snapshot_not_refreshed':True}),flush=True)
            time.sleep(max(0,2-(time.monotonic()-started)))


if __name__=='__main__':main()