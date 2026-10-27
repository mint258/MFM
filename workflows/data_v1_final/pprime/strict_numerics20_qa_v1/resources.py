"""Role reservations, actual account/physical/RSS and soft scratch observations."""
import os,pathlib,socket,stat,time
from . import contract as C
Q=C.Q
class Roles:
    def __init__(self):self.active=set();self.closed={};self.unknown=set();self.stop=None
    def start(self,qa):
        Q.need(self.stop is None and len(self.active)<16 and qa not in self.active|set(self.closed)|self.unknown,'BOUNDED_UNIQUE_UNCONSUMED_CALL_ROLE')
        self.active.add(qa);Q.need(self.bound()<=C.CAP,'RESERVED_WHOLE_EXECUTION_CAP')
    def settle(self,qa,actual,valid):
        Q.need(qa in self.active and type(actual)is int and 0<=actual<=C.WORKER_CAP,'EXACT_PRIVATE_ROLE_SETTLEMENT')
        self.active.remove(qa)
        if valid and actual<=C.CLOSED_CAP:self.closed[qa]=actual
        else:self.unknown.add(qa);self.stop=self.stop or 'UNCOMPACTED_UNKNOWN_OR_DEFINED_QC_FAILURE_NO_NEW_DISPATCH'
        Q.need(self.bound()<=C.CAP,'PRESERVED_UNKNOWN112M_AND_CLOSED25M_WITHIN31GIB')
    def bound(self):return C.PARENT_CAP+len(self.active|self.unknown)*C.WORKER_CAP+sum(self.closed.values())
class Budget:
    def __init__(self,plan,proof,parent_store,roles,event):
        self.plan=plan;self.proof=proof;self.parent_store=parent_store;self.roles=roles;self.event=event;self.last=0;self.start=time.monotonic();self.peak=0;self.minimum=None;self.observations=0;self.stop=None;self.last_quota=None
        review=C.meta(plan['quota_reuse_reference']);self.wave=review['whole_wave_output_reserve_bytes'];self.client=C.F.Provider.Client(review['provider_review_reference'],proof['request'])
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata'];text=job['RunTime'];d,text=text.split('-',1) if '-' in text else ('0',text)
        h,m,s=map(int,text.split(':'));self.initial=int(d)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def halt(self,why):self.stop=self.stop or why;self.event.set()
    def check(self,dispatch=True,force=False):
        now=time.monotonic()
        if self.roles.stop:self.halt(self.roles.stop)
        if self.event.is_set():self.stop=self.stop or 'WORKER_SOFT_RESOURCE_OR_QC_STOP_NEW_DISPATCH'
        if force or now-self.last>=1:
            self.last=now;Q.need(os.getuid()==1278 and socket.gethostname().split('.')[0]==self.proof['request']['node']
                and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id']) and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_ADMITTED_PARENT_RESOURCE_OBSERVATION')
            try:
                rss=0;stack=[os.getpid()];seen=set()
                while stack:
                    pid=stack.pop()
                    if pid in seen:continue
                    seen.add(pid);Q.need(len(seen)<=256,'BOUNDED_OWN_RESOURCE_PROCESS_TREE')
                    try:
                        p=pathlib.Path('/proc/'+str(pid));Q.need(p.stat().st_uid==1278,'ONLY_OWN_RESOURCE_PROCESS_TREE')
                        rss+=int((p/'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE');stack.extend(map(int,(p/'task'/str(pid)/'children').read_text().split()))
                    except FileNotFoundError:pass
                mem={v.split(':')[0]:int(v.split()[1])*1024 for v in pathlib.Path('/proc/meminfo').read_text().splitlines() if v.startswith(('MemAvailable:','MemTotal:'))}
                self.peak=max(self.peak,rss);self.minimum=mem['MemAvailable'] if self.minimum is None else min(self.minimum,mem['MemAvailable'])
                if rss>=16<<30 or mem['MemAvailable']<max(4<<30,.15*mem['MemTotal']):self.halt('ACTUAL_RSS_MEMAVAILABLE_SOFT_STOP')
                if self.initial+now-self.start>=self.plan['wall_seconds']-1080:self.halt('ORIGINAL900_PLUS180_DRAIN_RESERVE_STOP')
                # No parent traversal/stat of active output folders, ever.
                reserved=self.roles.bound();Q.need(reserved<=C.CAP and self.parent_store.charged<C.PARENT_CAP,'RESERVED_ROLE_CAPS')
                remaining=C.CAP-sum(self.roles.closed.values());v=os.statvfs(Q.ROOT)
                if v.f_bavail*v.f_frsize-self.wave-remaining<200000000000:self.halt('PHYSICAL_WHOLE_WAVE_PLUS_OWN_REMAINING_PLUS200GB_STOP')
                if force or self.observations==0 or now-getattr(self,'quota_poll',0)>=60:
                    self.quota_poll=now;obs=self.client.observe();self.last_quota=obs;self.observations+=1
                    if obs['free_bytes']-self.wave-remaining<200000000000:self.halt('ACCOUNT_WHOLE_WAVE_PLUS_OWN_REMAINING_PLUS200GB_STOP')
            except BaseException as exc:self.halt('RESOURCE_OBSERVATION_UNKNOWN:'+repr(exc))
        return not(self.stop or self.event.is_set()) if dispatch else True
    def report(self):return {'stop_new_dispatch':self.stop,'RSS_peak_bytes':self.peak,'minimum_MemAvailable_bytes':self.minimum,'actual_quota_observations':self.observations,
        'last_actual_account_quota_observation':self.last_quota,'whole_wave_reserved_bytes':self.wave,'parent_active_output_tree_stat_calls':0,
        'reserved_role_bytes':self.roles.bound(),'resource_event_passed_to_original_native':False,'forced_signals_sent':False,'account_quota_is_not_statvfs':True}
class Scratch:
    def __init__(self,root,event):self.root=pathlib.Path(root);self.event=event;self.peak=0;self.minimum=None;self.errors=[];self.samples=0;self.races=0
    def observe(self):
        try:
            n=0;count=0
            for p in self.root.rglob('*'):
                count+=1;Q.need(count<=4096,'BOUNDED_OWN_SCRATCH_OBSERVATION')
                try:
                    st=p.lstat();Q.need(st.st_uid==1278 and not stat.S_ISLNK(st.st_mode),'OWN_NON_SYMLINK_SCRATCH_OBSERVATION')
                    if stat.S_ISREG(st.st_mode):n+=st.st_size
                except FileNotFoundError:self.races+=1
            v=os.statvfs(self.root);free=v.f_bavail*v.f_frsize;self.peak=max(self.peak,n);self.minimum=free if self.minimum is None else min(self.minimum,free);self.samples+=1
            if n>=2<<30 or free<4<<30:self.event.set()
        except FileNotFoundError:
            if self.root.exists():self.races+=1
            else:self.errors.append('OWN_SCRATCH_ROOT_UNEXPECTEDLY_MISSING');self.event.set()
        except BaseException as exc:
            if len(self.errors)<8:self.errors.append(repr(exc))
            self.event.set()
    def report(self):return {'samples':self.samples,'observed_peak_bytes':self.peak,'observed_minimum_tmp_available_bytes':self.minimum,'observation_errors':self.errors,
        'transient_file_disappearances':self.races,'soft_STOP_threshold_bytes':2<<30,'threshold_not_hard_total_scratch_limit':True,'original_RLIMIT_FSIZE_per_file_bytes':134217728,'signals_sent':False}
