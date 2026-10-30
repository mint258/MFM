"""Actual allocation identity, same-FD input reads, finite own output, natural drain."""
import contextlib,fcntl,hashlib,json,os,pathlib,socket,stat,threading,time,types
from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
from workflows.data_v1_final.conformers.sprime_packed_day_v1 import runtime as PIO
from . import contract as C
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OLD

def frame(v):return (v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns,v.st_uid)
def pin(path,check=lambda:None):return PIO.sha_file(path,check=check)
def save(path,value):return PIO.save(path,value)
def read(ref,maximum=2<<20):
    path=pathlib.Path(ref['path']);C.need(ref['bytes']<=maximum,'EXPLICIT_CPU_JSON_BYTE_BOUND');verify(ref);return json.loads(path.read_bytes())
def verify(ref,check=lambda:None):return PIO.verify(ref,check)
def identity(proof):
    req=proof['request'];C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]==req['node']
      and req['node'] in ('compute-0-14','compute-0-18') and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
      and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==req['cpus']
      and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==proof['boot_id'],'REAL_ANALYSIS_DAY_CPU_IDENTITY')

class Context:
    def __init__(self,p,proof,plan_ref,out):
        self.plan,self.proof,self.plan_ref,self.out=p,proof,plan_ref,pathlib.Path(out);self.cpus=p['cpus'];self.value=C.F.config(p['original_config_reference'])
        self.common_out=self.out/'common';self.common_out.mkdir();self.cap=p['output_cap_bytes'];self.written=0;self.reserved={};self.lock=threading.RLock()
        self.clock=wall_clock(proof,86400);self.stop=None;self.failure=None;self.next=0;self.samples=[];self.verified={}
        from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
        self.client=Client(p['quota_provider_review_reference'],proof['request']);self.carve=C.meta(p['root_carveout_review_reference'])
        self.job_id=str(proof['job_id']);self.args=types.SimpleNamespace(config=pathlib.Path(p['original_config_reference']['path']),completion_index=None)
        save(self.out/'wall_clock_budget.json',self.clock);self._done=threading.Event();self._thread=None
    def authorized(self,refs):
        allowed=self.proof['request']['source_references']+self.proof['request']['data_references']
        for ref in refs:
            path=pathlib.Path(ref['path']);own=self.out in path.parents
            C.need(C.F.triple(ref) in allowed or (own and self.reference(path)==C.F.triple(ref)),'EXACT_DECLARED_INPUT_OR_ACTUAL_OWN_DERIVATION:'+ref['path'])
    def require(self,ref,drain=False):
        key=(ref['path'],ref['bytes'],ref['sha256']);path=pathlib.Path(ref['path'])
        if key not in self.verified:
            verify(ref,(lambda:None) if drain else self.check);self.verified[key]=frame(path.stat())
        C.need(frame(path.stat())==self.verified[key],'CURRENT_VERIFIED_SOURCE_FRAME_CHANGED');return path
    def read(self,ref,limit=2<<20):
        C.need(ref['bytes']<=limit,'CPU_JSON_EXPLICIT_BOUND');return json.loads(self.require(ref).read_bytes())
    def check(self):C.need(self.observe() is None,self.stop or 'ANALYSIS_DAY_RESOURCE_STOP')
    def workspace(self):
        for attempt in range(3):
            paths=[p for p in self.out.iterdir() if p.name.endswith(('.duckdb','.wal','.sqlite','.sqlite-journal'))]
            paths.extend((self.out/'duckdb_tmp').iterdir())
            try:
                rows=[(p,p.stat()) for p in paths]
                C.need(all(stat.S_ISREG(s.st_mode) and s.st_uid==1278 for p,s in rows),'ONLY_OWN_PRIVATE_DATABASE_AND_SPILL_FILES')
                after=[p for p in self.out.iterdir() if p.name.endswith(('.duckdb','.wal','.sqlite','.sqlite-journal'))];after.extend((self.out/'duckdb_tmp').iterdir())
                if set(after)==set(paths):return sum(s.st_size for p,s in rows)
            except FileNotFoundError:pass # Retry the complete inventory; never use a partial sum.
        raise ValueError('PRIVATE_WORKSPACE_INVENTORY_UNSTABLE_RESOURCE_UNKNOWN')
    def reserve(self,key,n):
        with self.lock:
            self.check();C.need(key not in self.reserved and self.written+self.workspace()+sum(self.reserved.values())+n+(64<<20)<=self.cap,'FULL_MOLECULE_DRAIN_OUTPUT_RESERVATION')
            self.reserved[key]=n
    def release(self,key):
        with self.lock:self.reserved.pop(key,None)
    def write(self,path,raw,key=None):
        path=pathlib.Path(path)
        with self.lock:
            C.need(self.out in path.parents and not path.exists() and self.written+self.workspace()+sum(v for k,v in self.reserved.items() if k!=key)+len(raw)+(64<<20)<=self.cap,'OWN_EXACT_OUTPUT_CEILING')
            ref=PIO.exclusive(path,raw);self.written+=len(raw);return ref
    def write_json_new(self,path,value):return self.write(path,C.canonical(value)+b'\n')
    def write_parquet_new(self,path,table):
        import pyarrow as pa,pyarrow.parquet as pq
        sink=pa.BufferOutputStream();pq.write_table(table,sink,compression='zstd',row_group_size=4096);return self.write(path,sink.getvalue().to_pybytes())
    require_pin=require
    reference=staticmethod(pin)
    geometry_sha=staticmethod(OLD.common().geometry_sha)
    def roles(self,value):
        authority=C.meta(value['roles_authority']);ref=authority['source_role_manifest'];self.authorized([ref]);manifest=C.meta(ref)
        C.need(authority['validation_source']=='ROUTINE' and manifest['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN','ORIGINAL_FROZEN_ROUTINE_VAL_ROLES')
        refs=[C.F.triple(r) for r in manifest['outputs'] if '/molecule_roles/' in r['path']];C.need(len(refs)==16,'ALL16_FROZEN_ROLE_PARTS');self.authorized(refs)
        for r in refs:self.require(r)
        return ref,refs
    def observe(self,children=(),force=False):
        with self.lock:
            if not force and time.monotonic()<self.next:return self.stop
            self.next=time.monotonic()+30
            try:
                identity(self.proof);pids={os.getpid(),*children};rss=0
                for thread in pathlib.Path('/proc/self/task').iterdir():
                    try:pids.update(int(v) for v in (thread/'children').read_text().split())
                    except FileNotFoundError:pass
                for p in pids:
                    try:rss+=int(pathlib.Path('/proc',str(p),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    except FileNotFoundError:pass
                available=next(int(s.split()[1])*1024 for s in pathlib.Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))
                remaining=remaining_wall(self.clock,time.monotonic());quota=self.client.observe()
                C.need(self.client.identity==self.plan['quota_provider_identity_reference'],'EXACT_FINITE_PROVIDER_IDENTITY')
                future=self.carve['total_future_reserved_bytes'];C.need(type(future) is int and future>=self.cap and self.carve['parent_included_exactly_once'] is True,'ONE_PARENT_IN_CURRENT_FUTURE_RESERVATION')
                C.need(quota['publisher_expires_unix_seconds']>=self.clock['cpu_wall_at_anchor']+self.clock['remaining_at_anchor_seconds']+300,'REAL_FINITE_LEASE_COVERS_ALLOCATION')
                if quota['free_bytes']-future<200000000000:self.stop=self.stop or 'ACCOUNT200GB_STOP_NEW_WORK'
                if remaining<=900:self.stop=self.stop or 'DAY_WALL_STOP_NEW_WORK_NATURAL_DRAIN'
                if rss>=self.plan['algorithm_rss_soft_cap_bytes'] or available<self.plan['minimum_MemAvailable_bytes']:self.stop=self.stop or 'MEMORY_STOP_NEW_WORK'
                if self.written+self.workspace()+sum(self.reserved.values())+(64<<20)>self.cap:self.stop=self.stop or 'OUTPUT_STOP_NEW_WORK'
                self.samples.append({'unix_seconds':time.time(),'rss_bytes':rss,'MemAvailable':available,'remaining_wall_seconds':remaining,'quota':quota,'stop':self.stop})
                C.need(len(self.samples)<=6400,'FINITE_RESOURCE_OBSERVATION_BUDGET')
            except Exception as exc:self.failure={'error':repr(exc),'last_quota':self.client.last};self.stop=self.stop or 'RESOURCE_OBSERVATION_UNKNOWN_STOP_NEW_WORK'
            return self.stop
    def start(self):
        def loop():
            while not self._done.wait(30):self.observe(force=True)
        self._thread=threading.Thread(target=loop,daemon=True);self._thread.start()
    def finish(self):
        self._done.set()
        if self._thread:self._thread.join()
    def report(self):return {'stop':self.stop,'observation_failure':self.failure,'last_observation':self.samples[-1] if self.samples else None,'observation_count':len(self.samples),'written_bytes':self.written,'reserved_bytes':sum(self.reserved.values()),'clock':self.clock,'signals_sent':False,'automatic_provider_renewal':False}

def admit(args,p):
    from workflows.data_v1_final.execution.cpu_analysis_day_v1.runtime import require_startup
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(args.plan),'--startup-proof',str(args.startup_proof)]
    proof=require_startup(args.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.parameters(p),expected_execution_argv=argv,
      expected_source=C.HERE/'run.py',expected_kind='analysis',required_references=(C.G.meta_pin(args.plan),*C.sources()))
    req=proof['request'];C.need(req['cpus']==p['cpus'] and req['node']==p['node'] and req['wall_seconds']==86400 and req['pilot'] is False
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['producer_plan_reference']==C.G.meta_pin(args.plan)
      and all(req[k]==p[k] for k in ('resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')),
      'REAL_NEW_ANALYSIS_DAY_REQUEST');identity(proof);return proof
