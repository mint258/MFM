"""Actual-target storage admission and recoverable write/transport protection."""
import argparse,json,os,pathlib,signal,subprocess,time
P=pathlib.Path
GIB=1<<30


class DiskUnavailable(RuntimeError):pass


def existing(path):
    path=P(path).resolve()
    while not path.exists():
        if path==path.parent:raise DiskUnavailable('TARGET_CAPACITY_UNKNOWN:'+str(path))
        path=path.parent
    return path


def command(argv):return subprocess.check_output(argv,text=True)


def inspect(path):
    path=existing(path)
    # Trigger autofs before examining the stacked mount metadata. A real NFS
    # mount can coexist in findmnt JSON with its systemd-1 autofs placeholder.
    device=os.stat(path).st_dev
    mount=json.loads(command(['findmnt','--json','-T',str(path),'-o','TARGET,SOURCE,FSTYPE']))['filesystems']
    candidates={}
    for entry in mount:
        if entry.get('fstype')=='autofs' or not all(entry.get(k) for k in ('target','source','fstype')):continue
        root=P(entry['target']).resolve()
        if (path==root or root in path.parents) and os.stat(root).st_dev==device:
            candidates[(entry['target'],entry['source'],entry['fstype'])]=entry
    if len(candidates)!=1:raise DiskUnavailable('TARGET_MOUNT_UNKNOWN_OR_AMBIGUOUS:'+str(path))
    row=next(iter(candidates.values()));space=command(['df','-B1','--output=size,avail',str(path)]).splitlines()[-1].split()
    inode=command(['df','-Pi',str(path)]).splitlines()[-1].split()
    total,available=map(int,space);free_inodes=int(inode[3])
    stat=os.statvfs(path)
    if total<=0 or available<0 or free_inodes<0 or stat.f_frsize<=0:raise DiskUnavailable('TARGET_CAPACITY_UNKNOWN:'+str(path))
    return {'path':str(path),'mount':row,'device':device,'total':total,'available':min(available,stat.f_bavail*stat.f_frsize),'inodes':min(free_inodes,stat.f_favail),
            'root_filesystem':device==os.stat('/').st_dev}


def nonnegative(spec,key):
    value=spec[key]
    if type(value)is not int or value<0:raise DiskUnavailable('EXPLICIT_DISK_BUDGET_REQUIRED:'+key)
    return value


class Guard:
    def __init__(self,config,admit=True):
        if not config or not config.get('targets'):raise DiskUnavailable('EXPLICIT_DISK_PROTECTION_PLAN_REQUIRED')
        self.targets=[];seen=set();self.poll=float(config.get('poll_seconds',1))
        if not 0<self.poll<=5:raise DiskUnavailable('DISK_MONITOR_POLL_MUST_BE_POSITIVE_AT_MOST_5S')
        for spec in config['targets']:
            paths=[P(p).resolve() for p in spec['paths']]
            if not paths:raise DiskUnavailable('DISK_TARGET_PATHS_REQUIRED')
            facts=[inspect(path) for path in paths];fact=facts[0]
            key=(fact['device'],fact['mount']['source'],fact['mount']['fstype'])
            if fact['device'] in seen or key in seen:raise DiskUnavailable('SAME_FILESYSTEM_BUDGET_MUST_BE_COMBINED')
            seen.add(key);seen.add(fact['device'])
            if any((f['device'],f['mount']['source'],f['mount']['fstype'])!=key for f in facts):raise DiskUnavailable('TARGET_PATHS_CROSS_FILESYSTEMS')
            budget={k:nonnegative(spec,k) for k in ('peak_additional_bytes','peak_additional_inodes','reserve_bytes','reserve_inodes','concurrent_bytes','concurrent_inodes','runtime_margin_bytes','runtime_margin_inodes')}
            if budget['runtime_margin_bytes']==0 or budget['runtime_margin_inodes']==0:raise DiskUnavailable('CONCURRENT_WRITE_BURST_MARGIN_REQUIRED')
            if fact['root_filesystem']:budget['reserve_bytes']=max(budget['reserve_bytes'],10*GIB,(fact['total']+9)//10)
            quota=spec.get('quota_scope')
            if quota not in ('limited','not_applicable'):raise DiskUnavailable('EXPLICIT_QUOTA_SCOPE_REQUIRED')
            if quota=='limited':
                if spec.get('quota_available_reference'):
                    age=spec['quota_max_age_seconds']
                    if type(age) not in (int,float) or not 0<age<=5:raise DiskUnavailable('QUOTA_SNAPSHOT_MAX_AGE_MUST_BE_AT_MOST_5S')
                    if type(spec['quota_expected_uid'])is not int or not spec['quota_expected_filesystem']:raise DiskUnavailable('EXPLICIT_QUOTA_SNAPSHOT_IDENTITY_REQUIRED')
                else:
                    argv=spec['quota_probe_argv']
                    if not isinstance(argv,list) or not argv or not all(isinstance(s,str) for s in argv):raise DiskUnavailable('ACTUAL_QUOTA_PROBE_REQUIRED')
                for k in ('quota_peak_additional_bytes','quota_concurrent_bytes','quota_reserve_bytes'):budget[k]=nonnegative(spec,k)
                budget['quota_reserve_bytes']=max(100_000_000_000,budget['quota_reserve_bytes'])
            target={'paths':paths,'probe':P(fact['path']),'facts':fact,'spec':spec,'budget':budget};self.targets.append(target)
            self.check_target(target,admission=admit)

    def target(self,path):
        path=P(path).resolve()
        matches=[t for t in self.targets if any(path==root or root in path.parents for root in t['paths'])]
        if len(matches)!=1:raise DiskUnavailable('WRITE_TARGET_NOT_UNIQUELY_BUDGETED:'+str(path))
        target=matches[0]
        if os.stat(existing(path)).st_dev!=target['facts']['device']:raise DiskUnavailable('TARGET_FILESYSTEM_CHANGED:'+str(path))
        return target

    def check_target(self,target,bytes_needed=0,inodes_needed=0,admission=False):
        b=target['budget'];stat=os.statvfs(target['probe']);free=stat.f_bavail*stat.f_frsize;inodes=stat.f_favail
        if admission:free=min(free,target['facts']['available']);inodes=min(inodes,target['facts']['inodes'])
        needed=max(b['peak_additional_bytes'],b['runtime_margin_bytes']) if admission else b['runtime_margin_bytes']+bytes_needed
        count=max(b['peak_additional_inodes'],b['runtime_margin_inodes']) if admission else b['runtime_margin_inodes']+inodes_needed
        if free<b['reserve_bytes']+b['concurrent_bytes']+needed or inodes<b['reserve_inodes']+b['concurrent_inodes']+count:
            raise DiskUnavailable('DISK_RESERVE_REACHED:'+str(target['probe']))
        spec=target['spec']
        if spec['quota_scope']=='limited':
            if spec.get('quota_available_reference'):
                try:
                    from .quota_snapshot import read_available
                    available=read_available(spec['quota_available_reference'],expected_uid=spec['quota_expected_uid'],
                        expected_filesystem=spec['quota_expected_filesystem'],max_age_seconds=spec['quota_max_age_seconds'])
                except Exception as exc:raise DiskUnavailable('ACCOUNT_QUOTA_SNAPSHOT_UNKNOWN:'+repr(exc)) from exc
            else:
                now=time.monotonic()
                if admission or now-target.get('quota_time',float('-inf'))>=self.poll:
                    target['quota_available']=int(command(spec['quota_probe_argv']).strip());target['quota_time']=now
                available=target['quota_available']
            needed=max(b['quota_peak_additional_bytes'],b['runtime_margin_bytes']) if admission else b['runtime_margin_bytes']+bytes_needed
            if available<0 or available<b['quota_reserve_bytes']+b['quota_concurrent_bytes']+needed:raise DiskUnavailable('ACCOUNT_QUOTA_RESERVE_REACHED:'+str(target['probe']))

    def check(self,path,bytes_needed=0,inodes_needed=0):
        try:self.check_target(self.target(path),bytes_needed,inodes_needed)
        except DiskUnavailable:raise
        except Exception as exc:raise DiskUnavailable('TARGET_CAPACITY_UNKNOWN:'+repr(exc)) from exc

    def wait(self,path,bytes_needed=0,inodes_needed=0):
        announced=False
        while True:
            try:self.check(path,bytes_needed,inodes_needed)
            except DiskUnavailable as exc:
                if not announced:print(json.dumps({'phase':'DISK_WAIT','path':str(path),'reason':str(exc),'closed_outputs_preserved':True}),flush=True);announced=True
                time.sleep(self.poll);continue
            if announced:print(json.dumps({'phase':'DISK_RESUMED','path':str(path)}),flush=True)
            return

    def run(self,argv,path,bytes_needed=0,inodes_needed=0):
        """Pause this owned process group before reserves; retain its partials."""
        self.wait(path,bytes_needed,inodes_needed)
        process=subprocess.Popen(argv,start_new_session=True);paused=False
        try:
            while process.poll() is None:
                try:self.check(path)
                except DiskUnavailable as exc:
                    if not paused:
                        try:os.killpg(process.pid,signal.SIGSTOP)
                        except ProcessLookupError:continue
                        paused=True;print(json.dumps({'phase':'DISK_TRANSPORT_PAUSED','reason':str(exc),'pid':process.pid}),flush=True)
                else:
                    if paused:
                        os.killpg(process.pid,signal.SIGCONT);paused=False
                        print(json.dumps({'phase':'DISK_TRANSPORT_RESUMED','pid':process.pid}),flush=True)
                time.sleep(self.poll)
            if process.returncode:raise subprocess.CalledProcessError(process.returncode,argv)
        except BaseException:
            # Preserve an owned interrupted subprocess/partial; Root decides its
            # continuation. Never delete data or signal unrelated processes.
            if process.poll() is None and not paused:
                try:os.killpg(process.pid,signal.SIGSTOP)
                except ProcessLookupError:pass
            raise


def from_plan(plan,required=False,admit=True):
    config=plan.get('disk_protection')
    return Guard(config,admit) if config is not None or required else None


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    sub=parser.add_subparsers(dest='action',required=True);sub.add_parser('preflight')
    transport=sub.add_parser('transport');transport.add_argument('--destination',required=True)
    transport.add_argument('--remaining-bytes',type=int,required=True);transport.add_argument('--new-inodes',type=int,required=True);transport.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args();plan=json.loads(P(args.plan).read_text(encoding='utf-8-sig'));guard=from_plan(plan,required=True)
    if args.action=='preflight':print(json.dumps({'phase':'DISK_ADMITTED','targets':[t['facts'] for t in guard.targets]}),flush=True)
    else:
        argv=args.command[1:] if args.command[:1]==['--'] else args.command
        if not argv or args.remaining_bytes<0 or args.new_inodes<0:parser.error('explicit command and nonnegative remaining physical growth required')
        guard.run(argv,args.destination,args.remaining_bytes,args.new_inodes)


if __name__=='__main__':main()
