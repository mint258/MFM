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


def atomic_write(path,value,admit):
    """Only the sole publisher replaces its JSON; failed probes leave it unchanged."""
    data=json.dumps(value,separators=(',',':'))+'\n'
    if len(data.encode('utf-8'))>4096:raise SnapshotUnavailable('SNAPSHOT_TOO_LARGE')
    admit(value['available_bytes'])
    path=Path(path);partial=path.with_name('.'+path.name+'.'+str(os.getpid())+'.partial')
    with open(partial,'w',encoding='utf-8') as handle:handle.write(data)
    os.replace(partial,path)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--reserve-bytes',type=int,default=100_000_000_000);args=parser.parse_args()
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
    print(json.dumps({'phase':'QUOTA_SNAPSHOT_PUBLISHER','uid':UID,'filesystem':FILESYSTEM,'output':str(path),'interval_seconds':2}),flush=True)
    while True:
        started=time.monotonic()
        try:
            text=subprocess.check_output(COMMAND,text=True,timeout=2)
            value={'schema':SCHEMA,'uid':UID,'filesystem':FILESYSTEM,**parse_xfs(text),'observed_time':time.time()}
            atomic_write(path,value,admit)
        except (SnapshotUnavailable,OSError,subprocess.SubprocessError) as error:
            print(json.dumps({'phase':'QUOTA_SNAPSHOT_UNAVAILABLE','reason':repr(error),'previous_snapshot_not_refreshed':True}),flush=True)
        time.sleep(max(0,2-(time.monotonic()-started)))


if __name__=='__main__':main()