"""Truthful endpoint startup and cooperative per-parent bounds; no scientific signals."""
from __future__ import annotations
import importlib,os,pathlib,re,socket,sys,threading,time
from . import contract as C,storage as S


def fields(raw):return dict(re.findall(r'(\w+)=([^\s]+)',raw))
def ticks(pid):return pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
def boot():return pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def duration(text):
    days,clock=(text.split('-',1) if '-' in text else ('0',text));h,m,s=map(int,clock.split(':'))
    return int(days)*86400+h*3600+m*60+s


def admit(plan_path,proof_path,role):
    plan=C.load_path(plan_path);C.review(plan);p=C.load_path(proof_path);spec=C.endpoint(plan['endpoint'])
    need=C.need;r=p['request'];actual=[x.decode() for x in pathlib.Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')]
    nodes=tuple('compute-0-'+str(n) for n in (2,*range(8,20))) if spec['id']=='main' else tuple('compute-0-'+str(n) for n in (1,3,4,5,6))+('sonmi1',)
    need(plan['role']==role and plan['node'] in nodes,'ONLY_ACTUAL_CPU_MENU_AND_DECLARED_ROLE')
    need(p['schema']=='ROOT_PORTABLE_REMAINING_STARTUP_V4' and p['endpoint_id']==spec['id'] and p['uid']==os.getuid()==spec['uid']
         and p['node']==socket.gethostname().split('.')[0]==r['node']==plan['node'] and p['plan_reference']==C.ref(plan_path,2<<20)
         and p['root_review_reference']==plan['root_review_reference'] and 0<=time.time()-p['observed_unix_seconds']<=120,'REAL_ENDPOINT_FRESH120_STARTUP')
    need(os.environ.get('SLURM_JOB_ID')==str(p['job_id']) and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
         and int(os.environ.get('SLURM_CPUS_PER_TASK',0))==r['cpus']==plan['cpus']
         and r['kind']==('conformer' if role=='run' else 'analysis') and r['scope_key']==C.SCOPE
         and r['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and r['wall_seconds']==plan['wall_seconds'],'REAL_CPU_COUNT_ROLE_AND_NO_MEMORY_MASQUERADE')
    need(actual==r['execution_argv']==plan['execution_argv'] and pathlib.Path(sys.executable)==pathlib.Path(actual[0]),'EXACT_LOGICAL_INTERPRETER_AND_OS_ARGV')
    identity=p['parent_identity'];need(identity['pid']==os.getpid() and str(identity['start_ticks'])==ticks(os.getpid()) and identity['boot_id']==boot(),'ACTUAL_PARENT_PID_START_BOOT')
    need(p['boot_id']==identity['boot_id'],'TOP_LEVEL_ORIGINAL_READER_BOOT_CONTEXT')
    stat_fields=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    need(identity['pgid']==int(stat_fields[2]) and identity['sid']==int(stat_fields[3])
        and identity['cgroup_sha256']==C.sha(pathlib.Path('/proc/self/cgroup').read_bytes()),'ACTUAL_PARENT_PROCESS_GROUP_SESSION_CGROUP')
    j=fields(p['job_metadata'])
    need(j['JobId']==str(p['job_id']) and j['JobState']=='RUNNING' and j['NodeList']==r['node']
         and int(j['NumCPUs'])==r['cpus'] and j['Partition']=='cpu' and j['Requeue']=='0'
         and j['NumTasks']=='1' and j['NumNodes']=='1' and j['Command']==r['script_reference']['path']
         and j['UserId']==('zixiao(1278)' if spec['id']=='main' else 'alpha(1264)')
         and duration(j['TimeLimit'])==plan['wall_seconds']
         and not any('gpu' in j.get(k,'').lower() for k in ('TRES','Gres','TresPerNode','TresPerTask')),'REAL_RUNNING_JOB_METADATA')
    need(abs(p['allocation_elapsed_seconds']-duration(j['RunTime']))<=120,'ACTUAL_ALLOCATION_ELAPSED_FROM_SCONTROL')
    need(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'CPU_ONLY_ONE_NATIVE_THREAD')
    pins={x['path']:x for x in r['source_references']}
    for x in [plan['root_review_reference'],C.ref(plan_path,2<<20),*plan['source_references']]:
        need(pins.get(x['path'])==x,'EXACT_SOURCE_AUTHORIZATION');C.verify(x,2<<20)
    main=pathlib.Path(sys.modules['__main__'].__file__).absolute();need(str(main) in pins,'ACTUAL_PRIMARY_SOURCE_PIN')
    script=C.verify(r['script_reference'],2<<20).read_text()
    need(not re.search(r'^#SBATCH\s+--(?:mem(?:-per-cpu)?|exclusive|gres|gpus)(?:=|\s|$)',script,re.M)
         and '#SBATCH --partition=cpu' in script,'NO_MEMORY_EXCLUSIVE_OR_GPU_DIRECTIVE')
    need(p['memory_limits_requested'] is False and p['memory_admission_evaluated'] is False
         and p['account_free_bytes']-plan['total_future_reserved_bytes']>=C.RESERVE,'CURRENT_ALL_FUTURE_QUOTA_RESERVE')
    observation=C.load(p['actual_resource_observations_reference'])
    need(observation['schema']=='ROOT_ACTUAL_PORTABLE_NODE_OBSERVATIONS_V4' and observation['reviewer']=='root'
        and observation['endpoint']==spec['address'] and observation['uid']==spec['uid'] and observation['node']==plan['node']
        and str(observation['job_id'])==str(p['job_id']) and observation['job_metadata']==p['job_metadata']
        and observation['observed_unix_seconds']==p['observed_unix_seconds'],'SAME_ROOT_ACTUAL_RESOURCE_SOURCE')
    return plan,p


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,pathlib.Path(out);self.stop=None;self.failure=None;self.lock=threading.RLock()
        self.written=0;self.reserved={};self.next=0;self.samples=[];self.started=time.monotonic()
        self.initial_elapsed=proof['allocation_elapsed_seconds'];self.client=None
        self.cost_group=None;self.cost_last=-1;self.cost_evidence=None
        S.initialize(self.out,plan['output_cap_bytes'])
        if plan['endpoint']['id']=='main':
            from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1 import quota_provider as Q
            C.need(C.ref(Q.__file__,2<<20) in proof['request']['source_references'],'ACTUAL_UNCHANGED_MAIN_QUOTA_CLIENT_SOURCE')
            self.client=Q.Client(plan['quota_provider_review_reference'],proof['request'])
        if plan['endpoint']['id']=='alpha' and plan['role']=='run':
            from . import cost
            self.cost_group=cost.group(proof,plan)
    def observe(self,children=(),force=False):
        with self.lock:
            if not force and time.monotonic()<self.next:return self.stop
            self.next=time.monotonic()+30
            try:
                C.need(os.getuid()==self.plan['endpoint']['uid'] and str(os.environ['SLURM_JOB_ID'])==str(self.proof['job_id']),'SAME_NATIVE_PARENT')
                pids={os.getpid(),*children};rss=0
                for pid in pids:
                    try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    except FileNotFoundError:pass
                mem=next(int(x.split()[1])*1024 for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
                total=next(int(x.split()[1])*1024 for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:'))
                limit=64<<30 if self.plan['endpoint']['id']=='main' else 48<<30
                available_min=4<<30 if self.plan['endpoint']['id']=='main' else max(4<<30,int(total*.15))
                if rss>=limit or mem<available_min:self.stop=self.stop or 'MEMORY_STOP_NEW_NATIVE'
                if self.initial_elapsed+time.monotonic()-self.started>=self.plan['wall_seconds']-self.plan['stop_dispatch_before_wall_seconds']:
                    self.stop=self.stop or 'WALL_STOP_NEW_NATIVE_NATURAL_DRAIN'
                if self.client is not None:
                    q=self.client.observe();C.need(q['identity_reference']==self.plan['quota_provider_identity_reference'],'UNCHANGED_FINITE_PROVIDER')
                    C.need(q['publisher_expires_unix_seconds']>=time.time()+max(0,self.plan['wall_seconds']-self.initial_elapsed-(time.monotonic()-self.started))+300,'FINITE_PROVIDER_COVERS_PARENT_AND_DRAIN')
                    free=q['free_bytes']
                else:
                    from secondary_cpu_queue_v1 import common as Q
                    C.need(C.ref(Q.__file__,2<<20) in self.proof['request']['source_references'],'ACTUAL_EXISTING_ALPHA_STORAGE_CLIENT_SOURCE')
                    observed=Q.storage_observation()
                    value=Q.effective_storage(observed,self.plan['storage_scope_review_reference']['path'],self.plan['output_cap_bytes'])
                    free=value['effective_free_bytes']
                    C.need(self.plan['total_future_reserved_bytes']>=value['whole_output_caps_reserved_bytes'],'ALL_ALPHA_REGISTERED_FUTURE_CAPS')
                future=self.plan['total_future_reserved_bytes']
                if free-future<C.RESERVE:self.stop=self.stop or 'ACCOUNT200GB_STOP_NEW_NATIVE'
                if self.cost_group is not None:
                    from . import cost
                    observed_cost=cost.observe(self.cost_group)
                    C.need(observed_cost['actual_aggregate_allocated_core_seconds']>=self.cost_last,'ACTUAL_AGGREGATE_COST_CANNOT_ROLL_BACK')
                    self.cost_last=observed_cost['actual_aggregate_allocated_core_seconds'];self.cost_evidence=observed_cost
                    if observed_cost['stop_new']:self.stop=self.stop or 'USER_TWO_TIMES_COMPARABLE_ALLOCATED_COST_STOP_NEW_NATURAL_DRAIN'
                state=S.read(self.out);self.written=state['written'];self.reserved=state['reserved']
                workspace=sum((self.out/n).stat().st_size for n in ('census.sqlite','census.sqlite-journal','census.sqlite-wal','census.sqlite-shm') if (self.out/n).exists())
                if self.plan.get('role')=='freeze' and workspace>self.plan['metadata_cap_bytes']-(2<<30):self.stop=self.stop or 'FREEZE_METADATA_CAP_STOP'
                if self.written+workspace+sum(self.reserved.values())+C.ADMIN>self.plan['output_cap_bytes']:self.stop=self.stop or 'OUTPUT_CAP_STOP_NEW_NATIVE'
                self.samples.append({'unix':time.time(),'rss':rss,'available':mem,'account_free':free,'stop':self.stop})
                self.samples=self.samples[-1024:]
            except Exception as e:self.failure=repr(e);self.stop=self.stop or 'RESOURCE_UNKNOWN_STOP_NEW_NATIVE'
            return self.stop
    def check(self):C.need(self.observe() is None,self.stop or 'RESOURCE_STOP')
    def reserve(self,key,n):
        with self.lock:
            if self.observe() is not None:return False
            if not S.reserve(self.out,key,n):self.stop=self.stop or 'OUTPUT_RESERVATION_STOP_NEW_NATIVE';return False
            return True
    def release(self,key):
        S.release(self.out,key)
    def write(self,path,raw,key=None):
        return S.write(self.out,path,raw,key)
    def report(self):
        state=S.read(self.out)
        return {'stop_new_native':self.stop,'failure':self.failure,'tail_observations':self.samples,'written_bytes':state['written'],
            'reserved_bytes':sum(state['reserved'].values()),'signals_sent':False,'natural_drain':True,'actual_cost':'ROOT_REAL_PARENT_SACCT_REQUIRED',
            'last_actual_aggregate_allocated_cost':self.cost_evidence}
