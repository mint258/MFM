"""Prepared control for two exact non-Native writers; no action on import."""
import argparse,json,math,os,re,socket,subprocess,time
from pathlib import Path

UID=1278
JOBS={
 '4526117':{'job_id':'4526117','name':'dv1_window2_full_TRAIN_D4','start_time':'2026-11-05T22:55:09','node':'compute-0-20'},
 '4526127':{'job_id':'4526127','name':'window2_uff_d3','start_time':'2026-11-06T02:36:27','node':'compute-0-19'}}
TERMINAL={'COMPLETED','CANCELLED','FAILED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}
class Unsafe(RuntimeError):pass


def parse_quota(text):
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    header=['Filesystem','kbytes','quota','limit','grace','files','quota','limit','grace']
    if len(lines)!=4 or lines[0]!='Disk quotas for usr zixiao (uid 1278):' or lines[1].split()!=header or lines[3]!='uid 1278 is using default file quota setting':
        raise Unsafe('LUSTRE_QUOTA_HEADER_OR_FOOTER')
    row=lines[2].split()
    if len(row)!=9 or row[0]!='/lfshome' or not all(re.fullmatch(r'\d+',row[i]) for i in (1,2,3,5,6,7)):
        raise Unsafe('LUSTRE_QUOTA_ROW')
    used,hard=int(row[1]),int(row[3])
    if hard<=0:raise Unsafe('LUSTRE_POSITIVE_EXPLICIT_HARD_LIMIT_REQUIRED')
    return {'used_KiB':used,'hard_KiB':hard,'available_bytes':max(0,hard-used)*1024}


def quota_observation(profile,text,source_probe_time):
    from workflows.data_v1_final.export.v31_stream_v1.quota_snapshot import observation_times
    return {'schema':'LUSTRE_USER_QUOTA_AVAILABLE_V1','uid':UID,'filesystem':'/lfshome',**parse_quota(text),
        **observation_times(source_probe_time,profile.get('quota_clock_safety_bias_seconds',0))}

def control_admission(path):
    path=Path(path)
    # Root reserves1GiB CONTROL budget. Only fixed-size own JSON and partial are
    # written; no data, hashes or new unbounded event log is produced here.
    stat=os.statvfs(path.parent);reserve=1<<30
    if os.stat(path.parent).st_dev==os.stat('/').st_dev:reserve=max(10*(1<<30),(stat.f_blocks*stat.f_frsize+9)//10)
    if stat.f_bavail*stat.f_frsize<reserve+131072 or stat.f_favail<10:raise Unsafe('CONTROL_CAPACITY_UNKNOWN_OR_LOW')


def atomic(path,value):
    path=Path(path);data=json.dumps(value,separators=(',',':'))+'\n'
    if len(data)>131072:raise Unsafe('CONTROL_METADATA_SIZE_LIMIT')
    control_admission(path)
    partial=path.with_name('.'+path.name+'.'+str(os.getpid())+'.partial')
    with open(partial,'w',encoding='utf-8') as handle:handle.write(data)
    os.replace(partial,path)


def load(path):
    with open(path,encoding='utf-8') as handle:return json.load(handle)


def fresh(value,schema,now,max_age):
    if type(max_age) not in (int,float) or not 0<max_age<=5:raise Unsafe('FRESHNESS_AT_MOST_5S_REQUIRED')
    stamp=value.get('observed_time')
    if value.get('schema')!=schema or type(value.get('uid'))is not int or value['uid']!=UID:
        raise Unsafe('SNAPSHOT_SCHEMA_OR_UID')
    if type(stamp) not in (int,float) or not math.isfinite(stamp) or not 0<=now-stamp<=max_age:
        raise Unsafe('SNAPSHOT_UNKNOWN_FUTURE_OR_STALE')


def validate_profile(profile):
    if profile.get('jobs')!=JOBS:raise Unsafe('ONLY_TWO_EXACT_FROZEN_NON_NATIVE_JOB_WITNESSES_ALLOWED')
    if any(type(profile.get(key))is not int for key in ('quota_reserve_bytes','runtime_margin_bytes','runtime_margin_inodes')):raise Unsafe('EXPLICIT_INTEGER_RESERVES_REQUIRED')
    if profile.get('quota_reserve_bytes',0)<100_000_000_000 or profile.get('runtime_margin_bytes',0)<8*(1<<30):raise Unsafe('QUOTA_RESERVE_AND_8GIB_BURST_REQUIRED')
    if profile.get('runtime_margin_inodes',0)<=0:raise Unsafe('POSITIVE_INODE_BURST_REQUIRED')
    if not 0<profile.get('max_age_seconds',0)<=5:raise Unsafe('FRESHNESS_AT_MOST_5S_REQUIRED')
    for node in {v['node'] for v in JOBS.values()}:
        spec=profile['nodes'][node]
        if not spec['targets'] or not spec['reference']:raise Unsafe('ACTUAL_NODE_TARGET_PROFILE_REQUIRED')
        for target in spec['targets']:
            if not Path(target['path']).is_absolute() or not all(target['mount'].get(k) for k in ('target','source','fstype')):raise Unsafe('EXPLICIT_ACTUAL_TARGET_MOUNT_REQUIRED')
            for key in ('reserve_bytes','reserve_inodes','concurrent_bytes','concurrent_inodes'):
                if type(target[key])is not int or target[key]<0:raise Unsafe('EXPLICIT_TARGET_RESERVE_REQUIRED')


def capacity(profile,node,inspector,now):
    rows=[]
    for spec in profile['nodes'][node]['targets']:
        facts=inspector(spec['path'])
        if facts['mount']!=spec['mount']:raise Unsafe('ACTUAL_TARGET_MOUNT_CHANGED')
        rows.append({'path':spec['path'],**{key:facts[key] for key in ('mount','total','available','inodes','root_filesystem')}})
    return {'schema':'NODE_WRITER_CAPACITY_V1','uid':UID,'node':node,'observed_time':now,'targets':rows}


class CapacitySampler:
    """Full startup inspection, then cheap actual statvfs/device samples only."""
    def __init__(self,profile,node,inspector,statvfs=os.statvfs,stat=os.stat,clock=time.time):
        self.node=node;self.statvfs=statvfs;self.stat=stat;self.clock=clock;self.targets=[]
        self.clock_safety_bias_seconds=profile['nodes'][node].get('clock_safety_bias_seconds',0)
        for spec in profile['nodes'][node]['targets']:
            facts=inspector(spec['path'])
            if facts['mount']!=spec['mount']:raise Unsafe('ACTUAL_TARGET_MOUNT_CHANGED')
            if self.stat(spec['path']).st_dev!=facts['device']:raise Unsafe('ACTUAL_TARGET_DEVICE_CHANGED')
            self.targets.append((spec['path'],facts['device'],dict(facts['mount']),facts['root_filesystem']))
    def sample(self):
        rows=[];completed=[]
        try:
            for path,device,mount,root in self.targets:
                if self.stat(path).st_dev!=device:raise Unsafe('ACTUAL_TARGET_DEVICE_CHANGED')
                value=self.statvfs(path)
                if self.stat(path).st_dev!=device:raise Unsafe('ACTUAL_TARGET_DEVICE_CHANGED')
                if any(type(getattr(value,key))is not int for key in ('f_frsize','f_blocks','f_bavail','f_favail')) or value.f_frsize<=0 or value.f_blocks<=0 or value.f_bavail<0 or value.f_favail<0:
                    raise Unsafe('CAPACITY_BYTE_OR_INODE_UNKNOWN')
                observed=self.clock()
                if type(observed) not in (int,float) or not math.isfinite(observed) or observed<=0:raise Unsafe('CAPACITY_OBSERVATION_TIME_UNKNOWN')
                completed.append(observed)
                rows.append({'path':path,'mount':mount,'total':value.f_blocks*value.f_frsize,'available':value.f_bavail*value.f_frsize,'inodes':value.f_favail,'root_filesystem':root})
        except OSError as error:raise Unsafe('ACTUAL_TARGET_STATVFS_UNKNOWN:'+repr(error)) from error
        if not completed:raise Unsafe('ACTUAL_TARGET_PROFILE_EMPTY')
        from workflows.data_v1_final.export.v31_stream_v1.quota_snapshot import observation_times
        return {'schema':'NODE_WRITER_CAPACITY_V1','uid':UID,'node':self.node,**observation_times(min(completed),self.clock_safety_bias_seconds),'targets':rows}

def safe(profile,job,reader=load,now=None):
    now=time.time() if now is None else now
    try:
        quota=reader(profile['quota_reference']);fresh(quota,'LUSTRE_USER_QUOTA_AVAILABLE_V1',now,profile['max_age_seconds'])
        available=quota.get('available_bytes')
        if quota.get('filesystem')!='/lfshome' or type(available)is not int or available<profile['quota_reserve_bytes']+profile['runtime_margin_bytes']:raise Unsafe('LUSTRE_QUOTA_UNKNOWN_OR_RESERVE')
        node=job['node'];spec=profile['nodes'][node];value=reader(spec['reference']);fresh(value,'NODE_WRITER_CAPACITY_V1',now,profile['max_age_seconds'])
        if value.get('node')!=node or len(value['targets'])!=len(spec['targets']):raise Unsafe('CAPACITY_NODE_OR_TARGETS_MISMATCH')
        for target,row in zip(spec['targets'],value['targets']):
            if target['path']!=row.get('path') or target['mount']!=row.get('mount'):raise Unsafe('CAPACITY_TARGET_MISMATCH')
            if any(type(row.get(k))is not int or row[k]<0 for k in ('total','available','inodes')) or row['total']<=0 or type(row.get('root_filesystem'))is not bool:raise Unsafe('CAPACITY_BYTE_OR_INODE_UNKNOWN')
            reserve=target['reserve_bytes']
            if row['root_filesystem']:reserve=max(reserve,10*(1<<30),(row['total']+9)//10)
            if row['available']<reserve+target['concurrent_bytes']+profile['runtime_margin_bytes'] or row['inodes']<target['reserve_inodes']+target['concurrent_inodes']+profile['runtime_margin_inodes']:raise Unsafe('TARGET_BYTE_OR_INODE_RESERVE')
        return True,'FRESH_SAFE'
    except Exception as error:return False,str(error)


def show_job(job_id):
    text=subprocess.check_output(['scontrol','show','job','-o',job_id],text=True,timeout=2)
    return dict(token.split('=',1) for token in text.split() if '='in token)


def witness(job,actual):
    if actual.get('JobId')!=job['job_id'] or actual.get('JobName')!=job['name'] or actual.get('UserId')!='zixiao(1278)' or actual.get('StartTime')!=job['start_time']:
        raise Unsafe('EXACT_JOB_OWNER_NAME_STARTTIME_MISMATCH')
    if actual.get('JobState') not in TERMINAL and actual.get('NodeList')!=job['node']:raise Unsafe('EXACT_JOB_NODE_MISMATCH')
    status=actual.get('JobState')
    if status not in TERMINAL|{'RUNNING','COMPLETING','SUSPENDED','STOPPED'}:raise Unsafe('UNEXPECTED_JOB_STATE')
    return status


def signal_job(job,name):
    # --full is confirmed in this cluster's scancel help: batch shell+all steps.
    subprocess.run(['scancel','--full','--signal='+name,'--user=1278','--name='+job['name'],job['job_id']],check=True,timeout=2)


class Controller:
    def __init__(self,profile,state,save,lookup=show_job,send=signal_job,evaluate=None):
        validate_profile(profile);self.profile=profile;self.state=state;self.save=save;self.lookup=lookup;self.send=send;self.evaluate=evaluate or (lambda job:safe(profile,job))
        if state.get('schema')!='TWO_NON_NATIVE_WRITER_RECOVERY_V1' or state.get('uid')!=UID or state.get('jobs')!=JOBS:raise Unsafe('SAME_FROZEN_JOB_WITNESSES_FOR_RECOVERY')
        state.setdefault('parked',{})
    def visit(self,job,exit_only=False):
        key=job['job_id'];actual=self.lookup(key);status=witness(job,actual);record=self.state['parked'].get(key)
        if status in TERMINAL:
            if record:record['status']='TERMINAL';self.save(self.state)
            return
        allowed,reason=self.evaluate(job)
        if record and record.get('job')!=job:raise Unsafe('RECOVERY_PARK_JOB_WITNESS_MISMATCH')
        if record and record['status']=='STOP_ACKNOWLEDGED':
            if status=='SUSPENDED':record['last_unsafe_reason']='SCHEDULER_SUSPENSION_IS_NOT_OURS';self.save(self.state);return
            if allowed:
                witness(job,self.lookup(key));allowed,reason=self.evaluate(job)
                if allowed:self.send(job,'CONT');del self.state['parked'][key];self.save(self.state)
                else:record['last_unsafe_reason']=reason;self.save(self.state)
            else:record['last_unsafe_reason']=reason;self.save(self.state)
        elif not exit_only and not allowed and status in ('RUNNING','COMPLETING'):
            self.state['parked'][key]={'job':job,'status':'STOP_REQUESTED','reason':reason};self.save(self.state)
            witness(job,self.lookup(key));self.send(job,'STOP')
            self.state['parked'][key]['status']='STOP_ACKNOWLEDGED';self.save(self.state)
    def tick(self,exit_only=False):
        errors=[]
        for job in JOBS.values():
            try:self.visit(job,exit_only)
            except Exception as error:errors.append({'job_id':job['job_id'],'reason':repr(error)})
        return errors
    def finish(self):
        errors=self.tick(exit_only=True)
        unresolved={key:record for key,record in self.state['parked'].items() if record['status']!='TERMINAL'}
        try:self.save(self.state)
        except Exception as error:errors.append({'recovery_state_write_error':repr(error)})
        return {'phase':'WRITER_GUARD_EXIT','parked_or_uncertain':unresolved,'errors':errors,'safe_exit_continued_only_fresh_owned_parks':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',required=True)
    sub=parser.add_subparsers(dest='mode',required=True)
    quota=sub.add_parser('quota');quota.add_argument('--output',required=True)
    cap=sub.add_parser('capacity');cap.add_argument('--node',required=True)
    for name in ('watch','resume'):
        command=sub.add_parser(name);command.add_argument('--state',required=True);command.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if os.getuid()!=UID:raise Unsafe('ACTUAL_MAIN_UID_REQUIRED')
    profile=load(args.profile);validate_profile(profile)
    if args.mode in ('quota','capacity'):
        if args.mode=='capacity':
            if socket.gethostname().split('.')[0]!=args.node or args.node not in profile['nodes']:raise Unsafe('ACTUAL_TARGET_NODE_REQUIRED')
            from workflows.data_v1_final.export.v31_stream_v1.disk_guard import inspect
            sampler=CapacitySampler(profile,args.node,inspect)
        publisher=None
        if args.mode=='quota':
            from workflows.data_v1_final.export.v31_stream_v1.quota_snapshot import AtomicPublisher
            publisher=AtomicPublisher(args.output,lambda unused:control_admission(args.output))
        try:
            while True:
                started=time.monotonic()
                try:
                    if args.mode=='quota':
                        observed=time.time();text=subprocess.check_output(['lfs','quota','-u','zixiao','/lfshome'],text=True,timeout=2)
                        value=quota_observation(profile,text,observed);path=args.output
                    else:value=sampler.sample();path=profile['nodes'][args.node]['reference']
                    if publisher is not None:publisher.publish(value)
                    else:atomic(path,value)
                except Exception as error:print(json.dumps({'phase':'WRITER_CAPACITY_SNAPSHOT_UNKNOWN','reason':repr(error),'previous_timestamp_unchanged':True}),flush=True)
                time.sleep(max(0,2-(time.monotonic()-started)))
        finally:
            if publisher is not None:publisher.close()
    else:
        if args.execute:
            import fcntl
            lock=open(args.state+'.lock','a')
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=load(args.state) if Path(args.state).exists() else {'schema':'TWO_NON_NATIVE_WRITER_RECOVERY_V1','uid':UID,'jobs':JOBS,'parked':{}}
        control=Controller(profile,state,lambda value:atomic(args.state,value))
        if not args.execute:
            print(json.dumps({'phase':'PREVIEW_ONLY','signals_sent':False,'capacity':{key:safe(profile,job) for key,job in JOBS.items()}}));return
        try:
            while True:
                errors=control.tick(exit_only=args.mode=='resume')
                if errors:print(json.dumps({'phase':'WRITER_GUARD_IDENTITY_OR_CONTROL_ERROR','errors':errors}),flush=True)
                if args.mode=='resume':break
                time.sleep(2)
        finally:
            report=control.finish();report['recovery_command']='python -B '+__file__+' --profile '+args.profile+' resume --state '+args.state+' --execute'
            print(json.dumps(report),flush=True)


if __name__=='__main__':main()