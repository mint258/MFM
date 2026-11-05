"""Generic16 admission, original packet APIs and explicit new-parent bridge."""
import collections,contextlib,fcntl,gzip,hashlib,json,os,pathlib,socket,stat,threading,time,types
from . import metadata as M
from workflows.data_v1_final.conformers import postprocess_day_v1 as POST
from workflows.data_v1_final.conformers.postprocess_day_v1 import io as PI,cache as CACHE,worker as WORKER,statistics as STATISTICS
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import contract as PC,io as POPIO,run as POP
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import io as BI,contract as B
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as Q
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as QUOTA
need=M.need
DAY_LEDGER=M.BASE/'claims'
TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}

def identity(proof):
    req=proof['request'];need(os.getuid()==1278 and socket.gethostname().split('.')[0]==req['node'] and req['node'] in ('compute-0-14','compute-0-18')
        and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
        and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==proof['boot_id'],'REAL_GENERIC_MAIN_CPU13_16_PARENT')
def ref(path):return PI.pin(path)
def sources():return sorted(M.unique([*(M.pin(path) for path in M.source_paths()),QUOTA.source_reference()]),key=lambda r:r['path'])
def admit(args):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    p=M.meta(M.pin(args.plan));base,origins=M.inputs(p)
    argv=[M.PY,'-B','-m',M.MODULE,'--plan',str(args.plan),'--root-preflight',str(args.root_preflight),'--output',str(args.output)]
    proof=require_startup(args.root_preflight,expected_scope_key=M.KEY,expected_scope_parameters=M.parameters(p),expected_execution_argv=argv,
        expected_source=M.HERE/'run.py',expected_kind='analysis',required_references=(M.pin(args.plan),*p['source_references'],*p['data_references']))
    req=proof['request'];need(req['cpus']==16 and req['node']==p['node'] and req['wall_seconds']==86400 and req['pilot']is False
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and req['estimated_peak_output_bytes']==M.CAP and str(args.output)==p['output_directory'],'EXACT_NEW_DAY_GENERIC_SCOPE_NO_OLD_C0')
    identity(proof);need(all(r in req['source_references'] for r in sources()),'ALL_UNCHANGED_SCIENCE_AND_NEW_IO_SOURCES')
    review=Q.load_review(p['provider_review_reference']);publisher=Q.pinned(p['provider_identity_reference'])
    need(set(review['compute_mount_by_node'])=={p['node']} and review['maximum_runtime_seconds']==90000
        and publisher['review_reference']==p['provider_review_reference'] and publisher['expires_unix_seconds']-time.time()>=86700,
        'ACTUAL_CPU13_FINITE25H_STORAGE_PROVIDER_NOT_NEW_SERVICE')
    return p,base,origins,proof
@contextlib.contextmanager
def single_parent():
    path=PC.BASE/'independent_day_single_parent.lock';path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1,'OWN_PM7_ONLY_SINGLE_PARENT_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield fd
    finally:os.close(fd)

class Context(PI.Context):
    """Original public bounded readers/writers; only real13 resource binding differs."""
    def __init__(self,p,proof,plan_ref,out):
        self.plan,self.proof,self.plan_ref,self.out=p,proof,plan_ref,pathlib.Path(out);self.cpus=16;self.value={};self.cap=M.CAP
        self.written=0;self.reserved={};self.lock=threading.RLock();self.clock=PI.wall_clock(proof,86400)
        self.stop=None;self.failure=None;self.next=0;self.samples=[];self.verified={};self._done=threading.Event();self._thread=None
        self.client=Q.Client(p['provider_review_reference'],proof['request']);self.carve=M.meta(p['resource_carveout_reference'])
        need(self.carve['schema']=='ROOT_PM7_PRECACHE_DAY_CURRENT_FUTURE_REVIEW_V1' and self.carve['status']=='APPROVED'
            and self.carve['reviewer']=='root' and self.carve['scope_key']==M.KEY and self.carve['node']==p['node']
            and self.carve['parent_output_cap_bytes']==M.CAP and self.carve['parent_included_exactly_once']is True
            and self.carve['old_jobs_costs_and_unknown_preserved']is True,'ACTUAL_EXACT_NEW64GIB_CURRENT_FUTURE_CARVEOUT')
        fields=('parent_output_cap_bytes','other_future_reserved_bytes','quota_provider_future_reserve_bytes','admin_future_reserve_bytes')
        need(all(type(self.carve[k])is int and self.carve[k]>=0 for k in fields)
            and self.carve['total_future_reserved_bytes']==sum(self.carve[k] for k in fields)
            and self.carve['total_future_reserved_bytes']<=self.carve['previous_total_future_reserved_bytes']
            and self.carve['quota_provider_future_reserve_bytes']==self.carve['admin_future_reserve_bytes']==64<<20,
            'CURRENT_FUTURE64_FROM_RETIRED_UNUSED_BUDGET_NO_DOUBLE_RESERVATION')
        self.job_id=str(proof['job_id']);self.events=[];self.event_bytes=0
        self.write_json_new(self.out/'wall_clock_budget.json',self.clock)
    def usage(self):return POPIO.usage(self.out)
    def reserve(self,key,n):
        with self.lock:
            self.check();need(key not in self.reserved and self.usage()+self.workspace()+sum(self.reserved.values())+n+(64<<20)<=self.cap,'FULL_MOLECULE_OUTPUT_AND_DRAIN_RESERVATION')
            self.reserved[key]=n
    def write(self,path,raw,key=None):
        with self.lock:
            need(self.usage()+self.workspace()+sum(v for k,v in self.reserved.items() if k!=key)+len(raw)+(64<<20)<=self.cap,'OWN_DAY64GIB_AND_WORKSPACE_PREWRITE')
            result=POPIO.write(path,raw,self.out);self.written=self.usage();return result
    def record_quota(self,event):
        raw=M.canonical({'actual_parent_job_id':self.job_id,'node':self.plan['node'],'event':event})+b'\n'
        need(len(raw)<=256<<10 and len(self.events)<6400 and self.event_bytes+len(raw)<=64<<20,'FINITE_PERSISTENT_RESOURCE_EVENTS')
        r=self.write(self.out/'quota_events'/('%05d_%d.json'%(len(self.events),time.time_ns())),raw);self.events.append(r);self.event_bytes+=len(raw)
    def observe(self,children=(),force=False):
        with self.lock:
            if not force and time.monotonic()<self.next:return self.stop
            self.next=time.monotonic()+30
            try:
                identity(self.proof);pids={os.getpid(),*children};rss=0
                for thread in pathlib.Path('/proc/self/task').iterdir():
                    try:pids.update(map(int,(thread/'children').read_text().split()))
                    except FileNotFoundError:pass
                for pid in pids:
                    try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    except FileNotFoundError:pass
                available=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
                remaining=PI.remaining_wall(self.clock,time.monotonic())
                quota=QUOTA.observe(self.client,expected_identity_reference=self.plan['provider_identity_reference'],record=self.record_quota)
                need(self.client.identity==self.plan['provider_identity_reference'],'SAME_FIXED_FINITE_PROVIDER_IDENTITY')
                need(quota['publisher_expires_unix_seconds']>=self.clock['cpu_wall_at_anchor']+self.clock['remaining_at_anchor_seconds']+300,'ACTUAL_LEASE_COVERS_FULL_PARENT')
                if quota['free_bytes']-self.carve['total_future_reserved_bytes']<200000000000:self.stop=self.stop or 'QUOTA200GB_STOP_NEW_MOLECULES'
                if remaining<=900:self.stop=self.stop or 'WALL900_STOP_NEW_MOLECULES_NATURAL_DRAIN'
                if rss>=64<<30 or available<4<<30:self.stop=self.stop or 'ORIGINAL_RSS64GIB_OR_AVAILABLE4GIB_STOP'
                if self.usage()+self.workspace()+sum(self.reserved.values())+(64<<20)>self.cap:self.stop=self.stop or 'DAY64GIB_STOP_NEW_MOLECULES'
                self.samples.append({'unix':time.time(),'rss_bytes':rss,'MemAvailable':available,'remaining_wall_seconds':remaining,'quota':quota,'stop':self.stop})
                need(len(self.samples)<=6400,'FINITE_DAY_OBSERVATIONS')
            except Exception as exc:self.failure={'error':repr(exc),'last_quota':self.client.last};self.stop=self.stop or 'RESOURCE_UNKNOWN_STOP_NEW_MOLECULES'
            return self.stop
    def report(self):return {'stop':self.stop,'failure':self.failure,'last_observation':self.samples[-1] if self.samples else None,'observation_count':len(self.samples),
        'quota_event_references':self.events,'whole_output_cap_bytes':self.cap,'effective_owned_output_soft_stop_bytes':self.cap,
        'legacy_batch8GIB_budget_not_modified_or_used':True,'charged_bytes_not_physical_inventory':self.usage(),
        'signals_sent':False,'provider_renewed':False,'scientific_retry':False}

def own_setup(out):
    out=pathlib.Path(out);need(M.BASE in out.parents and not out.exists() and '..' not in out.parts and not any(p.is_symlink() for p in (out,*out.parents)),'FRESH_DAY_OUTPUT_WITH_ORIGINAL_FIXED_PREFIX')
    out.mkdir(mode=0o700,parents=True)
    for name in ('tasks','starts','molecules','finished','progress','duckdb_tmp','catalog_parts','checkpoints','quota_events'):(out/name).mkdir()
    DAY_LEDGER.mkdir(mode=0o700,parents=True,exist_ok=True);return out
def actual_parent(origin,proof):
    POPIO.authorized(proof,[origin['account']['raw_sacct_reference']]);parents=POPIO.F.accounting(origin['entry']['accounting_reference'],[origin['job_id']])
    need(parents[origin['job_id']]==origin['actual'] and origin['actual']['state'] in TERMINAL,'ACTUAL_RAW_TERMINAL_ACCOUNT_NOT_RECEIPT_INFERENCE')
def canonical_source(ctx,base,original):
    from workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as OLD_MAP
    review=M.meta(ctx.plan['source_mapping_review_reference']);old=M.meta(review['historical_node13_source_mapping_reference'])
    need(review['schema']=='ROOT_SPRIME_PACKED_MULTINODE_SOURCE_MOUNT_MAPPING_V2' and review['status']=='APPROVED_EXACT_CANONICAL_SOURCE_MAPPING'
        and review['reviewer']=='root' and review['uid']==1278 and review['endpoint']=='202.38.247.57:22'
        and review['node']==ctx.proof['node']==ctx.plan['node'] and review['current_physical_device_is_endpoint_local_not_source_identity']is True,
        'ROOT_ACTUAL_THIS_NODE_CANONICAL_MAPPING_NOT_A_NODE13_PROOF')
    need(old['schema']=='ROOT_SPRIME_NODE13_SOURCE_MOUNT_MAPPING_V1' and old['status']=='APPROVED_EXACT_CANONICAL_SOURCE_MAPPING'
        and old['reviewer']=='root' and old['node']=='compute-0-13' and old['canonical_reference']==base['formal_source']==original['formal_source']==OLD_MAP.EXPECTED
        and all(review[k]==old[k] for k in ('formal_source_receipt','prior_cpu_source_validation','historical_frame')),
        'EXACT_UNMODIFIED_CANONICAL_SOURCE_IDENTITY_AND_OLD_SOURCE13_WITNESS')
    provider=Q.load_review(ctx.plan['provider_review_reference'])
    need(review['same_storage_mapping']==provider['probe_reference'] and review['quota_provider_review']==ctx.plan['provider_review_reference']
        and set(provider['compute_mount_by_node'])=={ctx.plan['node']},'ACTUAL_THIS_NODE_PROVIDER_AND_SHARED_STORAGE_PROBE')
    source=base['formal_source'];before=pathlib.Path(source['path']).stat()
    need(OLD_MAP.source_frame(before)==OLD_MAP.expected_frame(old['historical_frame']),'ORIGINAL_INODE_SIZE_MTIME_UID_NOT_REPAIRED')
    ctx.require(source);after=pathlib.Path(source['path']).stat();need(OLD_MAP.stable_frame(before)==OLD_MAP.stable_frame(after),'WHOLE_SHA_CURRENT_DEVICE_FRAME_STABLE')
    ctx.write_json_new(ctx.out/'canonical_current_node_frame.json',{'reference':source,'actual_node':ctx.plan['node'],
        'mapping_reference':ctx.plan['source_mapping_review_reference'],'historical_node13_reference':review['historical_node13_source_mapping_reference'],
        'current_device_inode_size_mtime_uid':list(OLD_MAP.stable_frame(after)),'full_SHA_verified_in_this_parent':True})
def new_claim(ctx,task,task_ref):
    key=task['cache_key'];value={'schema':'PM7_PRECACHE_DAY_CLAIM_V1','resource_scope':M.KEY,'cache_key':key,'molecule_id':task['meta']['molecule_id'],
        'job_id':ctx.job_id,'uid':1278,'node':ctx.plan['node'],'output_root':str(ctx.out),'plan_reference':ctx.plan_ref,'task_reference':task_ref,
        'source_fingerprint':PC.digest(sources()),'proof_reference':M.pin(ctx.proof['request']['execution_argv'][ctx.proof['request']['execution_argv'].index('--root-preflight')+1]),
        'action':'COMPUTE','automatic_retry':False,'old_PC_ledger_written':False}
    raw=M.canonical(value)+b'\n'
    with POPIO.R.lock(ctx.out):
        POPIO.charge_locked(ctx.out,len(raw))
        try:return PI.PIO.exclusive(DAY_LEDGER/(key+'.json'),raw)
        except FileExistsError:return None
def charge_worker(ctx,key):
    n=0
    for name,suffix in (('starts','.json'),('progress','.jsonl'),('molecules','.json.gz')):
        p=ctx.out/name/(key+suffix)
        if p.exists():
            s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and not p.is_symlink(),'OWN_RESERVED_WORKER_OUTPUTS');n+=s.st_size
    with POPIO.R.lock(ctx.out):POPIO.charge_locked(ctx.out,n)
    ctx.written=ctx.usage();return n
def check_claim(task,claim,claim_ref,origins):
    jid=str(claim.get('job_id'));need(jid in origins,'UNDECLARED_CONSUMED_CACHE_OWNER_HOLD_NO_REDISPATCH')
    origin=origins[jid];need(claim['uid']==1278 and claim['node']==origin['request']['node'] and claim['cache_key']==task['cache_key']
        and claim['molecule_id']==task['meta']['molecule_id'] and claim['output_root']==origin['root'],'TRUE_REGISTERED_CACHE_CLAIM_SOURCE_ROOT')
    req=origin['request'];declared=req['source_references']
    old_sources=POPIO.sources() if origin['kind']=='legacy' else sorted([r for r in declared if r['path'] in {str(p) for p in M.source_paths()}],key=lambda r:r['path'])
    need(claim['source_fingerprint']==PC.digest(old_sources),'ORIGINAL_OWNER_SOURCE_FINGERPRINT')
    if origin['kind']=='day':need(claim['resource_scope']==M.KEY and claim['schema']=='PM7_PRECACHE_DAY_CLAIM_V1','TRUTHFUL_NEW_DAY_CLAIM_NOT_LEGACY_SCOPE')
    return origin
def packet_from_claim(ctx,task,claim,claim_ref,origins):
    origin=check_claim(task,claim,claim_ref,origins)
    if origin['kind']=='day':
        root=pathlib.Path(origin['root']);packet_ref=transfer_ref(root,root/'molecules'/(task['cache_key']+'.json.gz'))
        value=STATISTICS.packet(ctx,packet_ref);start=ctx.read(value['worker_start_reference']);old_task=ctx.read(claim['task_reference'])
        need(value['molecule_id']==task['meta']['molecule_id'] and value['claim_reference']==start['claim_reference']==claim_ref
            and value['worker_start_reference']['path']==str(root/'starts'/(task['cache_key']+'.json'))
            and value['runtime']['job_id']==start['job_id']==origin['job_id'] and value['runtime']['uid']==start['uid']==1278
            and value['runtime']['node']==start['node']==origin['request']['node'] and value['d7']is None and value['common']is False
            and old_task['cache_key']==task['cache_key'] and old_task['records']==task['records'] and old_task['hof']==task['hof'],
            'TRUE_NEW_DAY_WRAPPER_TASK_CLAIM_START_PARENT_WITHOUT_FAKE_LEGACY_SCHEMA')
        need(start['boot_id']==origin['proof']['boot_id'] and type(start['pid'])is int and start['pid']>0
            and str(start['pid_start_ticks']).isdecimal() and int(start['pid_start_ticks'])>0,'ACTUAL_OWN_SOURCE_WORKER_BOOT_PID_TICKS')
        packet=value['cache'];need(packet['cache_key']==task['cache_key'] and packet['source_records']==task['records']
            and packet['hof_by_record']==task['hof'] and packet['new_QM_calls']==packet['new_UFF_calls']==0,'EXACT_NEW_DAY_ORIGINAL_CACHE_AND_FLOAT64_HOF')
        return {'molecule_id':task['meta']['molecule_id'],'records':len(task['records']),'cache_key':task['cache_key'],'claim_reference':claim_ref,
            'geometry_packet_reference':packet_ref,'orders_and_HOF_reference':packet_ref,'packet_reference':packet_ref,
            'geometry_status':packet['status'],'origin_job_id':origin['job_id'],'cache_layout':'NEW_DAY_WRAPPER_WITH_UNCHANGED_PM7_CACHE',
            **POP.geometry_diagnostics(packet)},packet
    if claim['action']=='IMPORT32':
        need(origin['kind']=='legacy','ONLY_REAL_OLD32_IMPORT_ACTION');g,h=ctx.controls;packet=control32_packet(ctx,task)
        return {'geometry_packet_reference':g[task['meta']['molecule_id']]['packet_reference'],'orders_and_HOF_reference':h[task['meta']['molecule_id']]['packet_reference'],
            'cache_layout':'ORIGINAL_GEOMETRY_WITH_CANONICAL_HOF_ATTACHMENT','cache_key':task['cache_key'],'geometry_status':packet['status'],
            'molecule_id':task['meta']['molecule_id'],'records':len(task['records']),'claim_reference':claim_ref,'origin_job_id':origin['job_id']},packet
    if getattr(ctx,'cache_plan',None)is not None and ctx.db.execute('SELECT 1 FROM prior_cache WHERE molecule_id=?',[task['meta']['molecule_id']]).fetchone():
        packet=CACHE.reuse(ctx,ctx.db,task,ctx.cache_plan);finished=BI.read(ref(pathlib.Path(claim['output_root'])/'finished'/(task['cache_key']+'.json')))
    else:finished,packet=POP.validate_packet(task,claim,claim_ref)
    need(finished['runtime']['job_id']==origin['job_id'],'OLD_PACKET_KEEPS_REAL_PARENT_NOT_CURRENT_DAY')
    return {'molecule_id':task['meta']['molecule_id'],'records':len(task['records']),'cache_key':task['cache_key'],'claim_reference':claim_ref,
        'geometry_packet_reference':finished['packet_reference'],'orders_and_HOF_reference':finished['packet_reference'],
        'packet_reference':finished['packet_reference'],'geometry_status':packet['status'],'origin_job_id':origin['job_id'],
        'cache_layout':'SINGLE_GEOMETRY_AND_HOF_PACKET',**POP.geometry_diagnostics(packet)},packet
def registered_origins(p,proof):
    _,rows=M.inputs(p);result={}
    for row in rows:actual_parent(row,proof);result[row['job_id']]=row
    return result
def control32_packet(ctx,task):
    g,h=ctx.controls;mid=task['meta']['molecule_id'];POP.imported32(task,g[mid],h[mid],ctx.out)
    packet=dict(BI.read_packet(g[mid]['packet_reference']));extra=ctx.read(h[mid]['packet_reference'],128<<20)
    packet.update(orders=extra['orders'],hof_by_record=extra['hof_by_record'],hof_valid_count=extra['hof_valid_count'],hof_range_complete=extra['hof_range_complete'],hof_range_kcal_mol=extra['hof_range_kcal_mol'],status='PM7_GEOMETRY_CACHE_COMPLETE_HOF_COMPLETE')
    packet['pm7']=[dict(r,energy=task['hof'][r['conformer_id']]['value_kcal_mol']) for r in packet['pm7']];return packet
def census_claims(ctx,origins):
    """Complete old attempt metadata census before any new RMSD task dispatch."""
    rows=[];unknown=[]
    for path in sorted([*PC.LEDGER.iterdir(),*DAY_LEDGER.iterdir()]):
        ctx.check();need(path.name.endswith('.json') and len(path.stem)==64 and all(c in '0123456789abcdef' for c in path.stem),'ONLY_FIXED_CACHE_CLAIM_LEAVES')
        r=ref(path);claim=BI.read(r);jid=str(claim.get('job_id'))
        valid=(claim.get('uid')==1278 and claim.get('cache_key')==path.stem
            and jid in origins and claim.get('output_root')==origins.get(jid,{}).get('root'))
        if valid:valid=claim.get('node')==origins[jid]['request']['node'] and ((path.parent==PC.LEDGER)==(origins[jid]['kind']=='legacy'))
        row={'claim_reference':r,'actual_owner_job_id':jid,'registered_UID_node_root_matches':valid};rows.append(row)
        if not valid:unknown.append(row)
    result=ctx.write_json_new(ctx.out/'all_prior_cache_claim_census.json',{'claims':rows,'unknown_claim_owners_or_identity':unknown,
        'scope':'WHOLE_EXISTING_SHARED_PM7_TECHNICAL_LEDGER','unlisted_owner_is_not_unstarted':True})
    if unknown:ctx.stop=ctx.stop or 'UNDECLARED_OR_BAD_PRIOR_CACHE_OWNER_HOLD'
    return result,unknown
def transfer_ref(root,path):
    path=pathlib.Path(path);need(pathlib.Path(root) in path.parents and '..' not in path.parts,'FIXED_REGISTERED_TRANSITIVE_CACHE_OUTPUT');return ref(path)
def registered_for_postprocess(p):
    """Small metadata only. Caller adds all returned refs to real stage authority."""
    source=[];data=[];origins=[];previous=[]
    for entry in p.get('pm7_precache_registered_parents',[]):
        origin=M.registration(entry,'day');need(origin['actual']['state']=='COMPLETED' and origin['actual']['exit_code']=='0:0'
            and origin['receipt']is not None and origin['receipt']['schema']=='PM7_PRECACHE_DAY_RECEIPT_V1','ACTUAL_NEW_DAY_C0_AND_OWN_RECEIPT')
        receipt=origin['receipt'];plan=M.meta(receipt['plan_reference'])
        acceptance=M.meta(entry['root_acceptance_reference']);need(acceptance['schema']=='ROOT_ACCEPTED_PM7_PRECACHE_DAY_PREFIX_V1'
            and acceptance['status']=='ACTUAL_C0_READONLY_CACHE_PREFIX_ACCEPTED_NOT_COMMON' and acceptance['reviewer']=='root' and acceptance['root_reason']
            and acceptance['job_id']==origin['job_id'] and acceptance['catalog_part_references']==receipt['catalog_part_references']
            and all(acceptance[k]==entry[k] for k in ('request_reference','submission_reference','accounting_reference','receipt_reference'))
            and acceptance['proof_reference']==origin['proof_reference'] and acceptance['raw_accounting_reference']==origin['account']['raw_sacct_reference']
            and acceptance['closed_state_reference']==receipt['closed_state_reference'] and acceptance['common_or_final_D7_or_physical_ID_release']is False,
            'INDEPENDENT_ROOT_EXACT_C0_PREFIX_ADOPTION_NOT_FINAL_PUBLICATION')
        need(receipt['status'] in ('ACTUAL_DAY_DURABLE_PARTIAL_PREFIX_NOT_FULL','FULL_ROSTER_TECHNICAL_CACHE_ROOT_REVIEW_REQUIRED')
            and receipt['scope_key']==M.KEY and receipt['source_plan_reference']==plan['base_cache_plan_reference']
            and plan['base_cache_plan_reference']==p['cache_plan_reference']
            and plan['output_directory']==origin['root'] and receipt['common']is False and receipt['full_cache_release']is False,
            'C0_CACHE_PREFIX_NOT_COMMON_OR_D7_RELEASE')
        source.extend(v for v in entry.values() if type(v)is dict and set(v)=={'path','bytes','sha256'});source.extend([origin['account']['raw_sacct_reference'],origin['proof_reference'],receipt['plan_reference']])
        data.extend(receipt['catalog_part_references']);data.append(receipt['closed_state_reference']);origins.append(origin)
        previous.extend(plan['previous_precache_parents'])
    # Actual C0 prefix adoption does not promote an original FAILED owner to C0.
    # Its real request/proof/account remain separate and packets are revalidated.
    found={r['job_id']:r for r in origins}
    for entry in previous:
        row=M.registration(entry,'day')
        if row['job_id'] not in found:origins.append(row);found[row['job_id']]=row
        else:need(all(found[row['job_id']]['entry'][k]==entry[k] for k in ('request_reference','submission_reference','accounting_reference','receipt_reference')),
            'SAME_REGISTERED_ORIGIN_METADATA_NOT_REASSIGNED')
        source.extend(v for v in entry.values() if type(v)is dict and set(v)=={'path','bytes','sha256'});source.extend([row['account']['raw_sacct_reference'],row['proof_reference']])
    return origins,M.unique(source),M.unique(data)
def load_for_postprocess(ctx,db):
    """Call after original cache.setup; no oldbook or automatic source discovery."""
    origins,_,_=registered_for_postprocess(ctx.plan);ctx.pm7_precache_origins={r['job_id']:r for r in origins}
    db.execute('CREATE TABLE prior_precache(molecule_id VARCHAR PRIMARY KEY,row_json VARCHAR,source_job_id VARCHAR)')
    import pyarrow.parquet as pq
    for origin in origins:
        actual_parent(origin,ctx.proof)
        if origin['receipt']is None or origin['actual']['state']!='COMPLETED' or origin['actual']['exit_code']!='0:0':continue
        for r in origin['receipt']['catalog_part_references']:
            for batch in pq.ParquetFile(ctx.require(r)).iter_batches(batch_size=1024):
                for value in batch.to_pylist():
                    row=json.loads(value['row_json'])
                    if row.get('origin_kind') not in ('DAY_PACKET','LEGACY32'):continue # Legacy union remains in original prior_cache.
                    old=db.execute('SELECT row_json FROM prior_precache WHERE molecule_id=?',[row['molecule_id']]).fetchone()
                    need(old is None or json.loads(old[0])['geometry_packet_reference']==row['geometry_packet_reference'],'NO_CONFLICTING_DAY_PREFIX_PACKET')
                    if old is None:db.execute('INSERT INTO prior_precache VALUES(?,?,?)',[row['molecule_id'],M.canonical(row).decode(),row.get('origin_job_id',origin['job_id'])])
def reuse_for_postprocess(ctx,db,task):
    row=db.execute('SELECT row_json,source_job_id FROM prior_precache WHERE molecule_id=?',[task['meta']['molecule_id']]).fetchone()
    if row is None:return None
    value=json.loads(row[0])
    if value.get('origin_kind')=='LEGACY32':
        if not hasattr(ctx,'controls'):ctx.controls=POP.controls(M.meta(ctx.plan['cache_plan_reference']),ctx.proof)
        return control32_packet(ctx,task)
    claim_ref=ref(DAY_LEDGER/(task['cache_key']+'.json'));claim=BI.read(claim_ref)
    need(value['claim_reference']==claim_ref and value['cache_key']==task['cache_key'],'EXACT_POSTPROCESS_INDEPENDENT_CACHE_CLAIM')
    origin=ctx.pm7_precache_origins[row[1]];actual_parent(origin,ctx.proof)
    result,packet=packet_from_claim(ctx,task,claim,claim_ref,ctx.pm7_precache_origins)
    need(result['geometry_packet_reference']==value['geometry_packet_reference'] and packet['source_records']==task['records']
        and packet['hof_by_record']==task['hof'],'TRUE_NEW_PRODUCER_PACKET_VALIDATED_NO_RMSD_REPLAY')
    return packet
