"""New scope and resource IO only; original bounded scientific context is inherited."""
import fcntl,heapq,json,os,pathlib,stat,subprocess,threading,time,traceback
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as C,io as OLD
from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import io as PRE
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as QUOTA
KEY='ordinary_postprocess_resume_v1'
MODULE='workflows.data_v1_final.conformers.ordinary_postprocess_resume_v1.run'
HERE=C.REPO/'workflows/data_v1_final/conformers/ordinary_postprocess_resume_v1'
FILES=('__init__.py','io.py','reuse.py','run.py','README.md')
BASE=C.ROOT/'artifacts/conformers/ordinary_postprocess_resume_v1'
FUTURE=C.ROOT/'control/root_current_all_future_ledger_v1.json'
FUTURE_LOCK=C.ROOT/'control/root_current_all_future_ledger_v1.lock'
FLOOR=C.ROOT/'control/current_account_quota_floor_policy.json'


def sources():
    return C.unique([*(C.G.meta_pin(HERE/n) for n in FILES),*(C.G.meta_pin(p) for p in PRE.M.source_paths()),QUOTA.source_reference(),
        *(C.G.meta_pin(p) for p in (C.REPO/'workflows/data_v1_final/execution/cpu_account100_queue_v1').glob('*.py'))])


def parameters(p):
    return dict(stage='ORDINARY_CLOSED_COMMON_PM7_D7_ONLY',node=p['node'],cpus=16,wall_seconds=86400,
        drain_seconds=900,output_directory=p['output_directory'],output_cap_bytes=p['output_cap_bytes'],
        local_workspace_directory=p['local_workspace_directory'],local_workspace_cap_bytes=min(p['output_cap_bytes'],64<<30),
        common_component_reference=p['closed_common_manifest_reference'],PM7_failed_owner_reference=p['pm7_owner_entry']['accounting_reference'],
        cache_plan_reference=p['cache_plan_reference'],D3_closed_export_reference=p['D3_closed_export_reference'],
        D3_actual_export_receipt_reference=p['D3_actual_export_receipt_reference'],D3_actual_delivery_parent_job_id='4525880',
        fixed_random_seed=20261025,dedup_threshold_A=0.5,
        canonical_HOF_registry=60,PM7_population_molecules=1220466,PM7_population_records=11231854,
        Native_once_written=False,N1_extra_domain=False,new_UFF_calls=0,new_QM_calls=0,
        current_all_future_ledger_path=str(FUTURE),account_quota_floor_bytes=100000000000)


def admit(args,p):
    from workflows.data_v1_final.execution.cpu_account100_queue_v1.runtime import require_startup
    C.need(p['schema']=='ROOT_ORDINARY_POSTPROCESS_RESUME_PLAN_V1' and p['status']=='APPROVED' and p['reviewer']=='root'
        and p['node'] in ('compute-0-14','compute-0-18') and p['cpus']==16 and p['wall_seconds']==86400
        and type(p['output_cap_bytes']) is int and p['output_cap_bytes']>=8<<30
        and p['scope_parameters']==parameters(p),'ACTUAL_NEW_ORDINARY_SCOPE_NOT_OLD_C0_OR_N1')
    argv=[C.PY,'-B','-m',MODULE,'--plan',str(args.plan),'--root-preflight',str(args.root_preflight),'--output',str(args.output)]
    proof=require_startup(args.root_preflight,expected_scope_key=KEY,expected_scope_parameters=parameters(p),expected_execution_argv=argv,
        expected_source=HERE/'run.py',expected_kind='analysis',required_references=(C.G.meta_pin(args.plan),*sources()))
    req=proof['request'];C.need(req['cpus']==16 and req['node']==p['node'] and req['wall_seconds']==86400 and req['pilot'] is False
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['scope']['mode']=='BOUNDED_METADATA_PREPARATION'
        and req['estimated_peak_output_bytes']==p['output_cap_bytes'] and str(args.output)==p['output_directory']
        and all(r in req['source_references'] for r in sources()),'EXACT_GENERIC16_DAY_WITH_SOURCE_PINS')
    OLD.identity(proof)
    C.need(p['quota_provider_review_reference']==p['provider_review_reference'] and p['quota_provider_identity_reference']==p['provider_identity_reference'],
        'ONE_REAL_THIS_NODE_PROVIDER_NOT_AN_OLD_PM7_PROVIDER')
    return proof


class Context(OLD.Context):
    """Same original readers/writers/clock; V2 future and real allocated-block credit."""
    def __init__(self,p,proof,plan_ref,out):
        super().__init__(p,proof,plan_ref,out);self.events=[]
        self._closed_credit_seen=set();self._closed_credit_pending=[];self._closed_credit_sequence=0
        self._closed_credit_bytes=0;self._closed_credit_count=0
        self.local_out=pathlib.Path(p['local_workspace_directory']);self.local_cap=min(self.cap,64<<30);self._local_created=False
        C.need(self.local_out.is_absolute() and self.local_out.parent==pathlib.Path('/dev/shm')
            and self.local_out.name.startswith('dv1_ordinary_postprocess_') and '..' not in self.local_out.parts
            and not self.local_out.exists() and not any(x.is_symlink() for x in (self.local_out,*self.local_out.parents)),
            'FRESH_OWN_DEV_SHM_WORKSPACE_ONLY')
        OLD.identity(proof)
        mount=subprocess.run(['findmnt','-n','-T','/dev/shm','-o','TARGET,SOURCE,FSTYPE,FSROOT'],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
        fields=mount.stdout.strip().split()
        C.need(mount.returncode==0 and len(fields)==4 and fields[0]=='/dev/shm' and fields[2]=='tmpfs',
            'ACTUAL_NODE_LOCAL_DEV_SHM_TMPFS_REQUIRED')
        fs=os.statvfs('/dev/shm');free=fs.f_bavail*fs.f_frsize
        C.need(free>=self.local_cap+100000000000,'LOCAL_TMPFS_CAP_PLUS100GB_REQUIRED')
        self.local_out.mkdir(mode=0o700);self._local_created=True
        self._local_owner=dict(job_id=self.job_id,uid=1278,node=p['node'],local_workspace_directory=str(self.local_out))
        try:
            OLD.save(self.local_out/'.ordinary_workspace_owner.json',self._local_owner)
            (self.local_out/'duckdb_tmp').mkdir(mode=0o700)
            current=self.local_out.lstat();C.need(current.st_uid==1278 and stat.S_ISDIR(current.st_mode),'OWN_LOCAL_WORKSPACE_UID')
            self._local_root_identity=(current.st_dev,current.st_ino,current.st_uid)
            self.write_json_new(self.out/'local_workspace_observation.json',dict(self._local_owner,mount_raw=mount.stdout,
                fstype='tmpfs',local_available_bytes=free,local_whole_cap_bytes=self.local_cap,
                minimum_start_available_bytes=self.local_cap+100000000000,Main_quota_credit_for_local_bytes=0,
                authoritative_output=False))
        except BaseException:
            self.cleanup_local_workspace();raise
    def workspace(self):
        # Only the small own DB/spill namespace is sampled. This logical size
        # constrains software output; it is never Main quota/allocated credit.
        for attempt in range(3):
            try:
                roots=list(self.local_out.iterdir());allowed={'work.duckdb','work.duckdb.wal','duckdb_tmp','.ordinary_workspace_owner.json'}
                C.need(all(p.name in allowed and not p.is_symlink() for p in roots),'ONLY_OWN_LOCAL_DB_SPILL_AND_MARKER')
                paths=[p for p in roots if p.name in ('work.duckdb','work.duckdb.wal')]
                spill=self.local_out/'duckdb_tmp';paths.extend(spill.iterdir())
                rows=[(p,p.lstat()) for p in paths]
                C.need(all(stat.S_ISREG(v.st_mode) and v.st_uid==1278 and v.st_nlink==1 for p,v in rows),'OWN_REGULAR_LOCAL_DB_SPILL')
                after=[p for p in self.local_out.iterdir() if p.name in ('work.duckdb','work.duckdb.wal')];after.extend(spill.iterdir())
                if set(after)==set(paths):
                    size=sum(v.st_size for p,v in rows);C.need(size<=self.local_cap,'LOCAL_WORKSPACE64GIB_SOFT_CAP');return size
            except FileNotFoundError:pass
        raise ValueError('LOCAL_WORKSPACE_INVENTORY_UNSTABLE_RESOURCE_UNKNOWN')
    def cleanup_local_workspace(self):
        # Called only after all worker context managers and db.close. Never
        # recurse/delete a shared path; unexpected content remains for Root.
        if not self._local_created:return
        root=self.local_out;C.need(root.parent==pathlib.Path('/dev/shm') and not root.is_symlink(),'EXACT_LOCAL_TMPFS_CLEANUP_ONLY')
        s=root.lstat();C.need(s.st_uid==1278 and stat.S_ISDIR(s.st_mode),'OWN_LOCAL_CLEANUP_ROOT')
        if hasattr(self,'_local_root_identity'):C.need((s.st_dev,s.st_ino,s.st_uid)==self._local_root_identity,'SAME_FRESH_LOCAL_ROOT')
        marker=root/'.ordinary_workspace_owner.json'
        C.need(not marker.is_symlink() and marker.lstat().st_uid==1278 and json.loads(marker.read_text())==self._local_owner,'OWN_LOCAL_MARKER')
        rows=list(root.iterdir());allowed={'work.duckdb','work.duckdb.wal','duckdb_tmp','.ordinary_workspace_owner.json'}
        C.need(all(p.name in allowed and not p.is_symlink() for p in rows),'UNEXPECTED_LOCAL_ENTRY_NO_CLEANUP')
        files=[p for p in rows if p.name in ('work.duckdb','work.duckdb.wal')]
        spill=root/'duckdb_tmp';spills=list(spill.iterdir()) if spill.exists() else []
        if spill.exists():C.need(stat.S_ISDIR(spill.lstat().st_mode) and spill.lstat().st_uid==1278,'OWN_SPILL_DIRECTORY')
        for p in [*files,*spills,marker]:
            st=p.lstat();C.need(stat.S_ISREG(st.st_mode) and st.st_uid==1278 and st.st_nlink==1 and not p.is_symlink(),
                'ONLY_OWN_REGULAR_CLOSED_LOCAL_FILES_CAN_BE_REMOVED')
        removed=0
        for p in [*files,*spills]:removed+=p.lstat().st_size;p.unlink()
        if spill.exists():spill.rmdir()
        marker.unlink();root.rmdir();self._local_created=False
        print(json.dumps(dict(status='OWN_DERIVED_LOCAL_WORKSPACE_REMOVED',job_id=self.job_id,path=str(root),
            removed_logical_bytes=removed,Main_quota_credit=0,shared_files_deleted=False)),flush=True)
    def register_closed_output(self,ref):
        """One stable block sample for a known completed, immutable own ref.

        Only called after the original exclusive writer returns or a worker
        future returns its published positive packet ref. The original source
        never rewrites/deletes these paths. DB/spill/append files are excluded.
        No DATA body is read, and no output tree is enumerated.
        """
        with self.lock:
            ref=C.F.triple(ref);path=pathlib.Path(ref['path'])
            C.need(path.is_absolute() and '..' not in path.parts and self.out in path.parents,
                'CLOSED_PHYSICAL_CREDIT_ONLY_THIS_PARENT_OUTPUT')
            relative=path.relative_to(self.out)
            if 'duckdb_tmp' in relative.parts or path.suffix not in ('.json','.parquet','.gz'):return False
            # Positive refs are already fully verified by their producing
            # exclusive writer or original worker. Only metadata is sampled.
            try:
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                try:
                    a=os.fstat(fd);b=os.fstat(fd);current=path.lstat()
                finally:os.close(fd)
            except FileNotFoundError:return False
            C.need(stat.S_ISREG(a.st_mode) and a.st_uid==1278 and a.st_nlink==1
                and not stat.S_ISLNK(current.st_mode),'OWN_CLOSED_REGULAR_SINGLE_LINK_OUTPUT')
            if OLD.frame(a)!=OLD.frame(b) or OLD.frame(a)!=OLD.frame(current) or a.st_blocks!=b.st_blocks or a.st_blocks!=current.st_blocks:
                return False
            if a.st_size!=ref['bytes']:return False
            inode=(a.st_dev,a.st_ino)
            if inode in self._closed_credit_seen:return False
            self._closed_credit_seen.add(inode);self._closed_credit_sequence+=1
            # A later real quota-query start must follow both the stable frame
            # and its actual CPU-side sample, including any clock race.
            eligible_ns=max(a.st_mtime_ns,a.st_ctime_ns,time.time_ns())
            heapq.heappush(self._closed_credit_pending,(eligible_ns,self._closed_credit_sequence,a.st_blocks*512))
            return True
    def closed_credit_at(self,cutoff):
        """Each registered immutable inode enters the rolling total at most once."""
        ns=int(cutoff*1e9)
        while self._closed_credit_pending and self._closed_credit_pending[0][0]<=ns:
            _,_,blocks=heapq.heappop(self._closed_credit_pending)
            self._closed_credit_bytes+=blocks;self._closed_credit_count+=1
        return min(self.cap,self._closed_credit_bytes)
    def write(self,path,raw,key=None):
        with self.lock:
            ref=super().write(path,raw,key)
            self.register_closed_output(ref)
            return ref
    def record_quota(self,event):
        C.need(len(self.events)<6400,'FINITE_METADATA_RESOURCE_EVENTS')
        self.events.append(self.write_json_new(self.out/'quota_events'/('%05d.json'%len(self.events)),event))
    def observe(self,children=(),force=False):
        with self.lock:
            if not force and time.monotonic()<self.next:return self.stop
            self.next=time.monotonic()+30
            try:
                OLD.identity(self.proof);pids={os.getpid(),*children};rss=0
                for thread in pathlib.Path('/proc/self/task').iterdir():
                    try:pids.update(map(int,(thread/'children').read_text().split()))
                    except FileNotFoundError:pass
                for pid in pids:
                    try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    except FileNotFoundError:pass
                available=next(int(v.split()[1])*1024 for v in pathlib.Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:'))
                floor=C.G.load(FLOOR);C.need(floor['schema']=='CURRENT_USER_ACCOUNT_QUOTA_FLOOR_POLICY_POINTER_V1'
                    and floor['account_quota_floor_bytes']==100000000000 and floor['policy_reference']==self.plan['quota_floor_policy_reference'],
                    'ACTUAL_CURRENT_USER100GB_POLICY')
                with FUTURE_LOCK.open('rb') as f:
                    fcntl.flock(f,fcntl.LOCK_SH);ledger=C.G.load(FUTURE)
                    C.need(ledger['schema']=='ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V2' and ledger['totals_derived_live_from_entries'] is True
                        and not ledger['unknown_future_entries'],'ALL_CURRENT_FUTURES_KNOWN_V2_NOT_STATIC_OLD200GB')
                    rows=ledger['entries'];totals=[v['future_reserved_bytes'] for v in rows.values()]
                    C.need(all(type(n) is int and n>=0 for n in totals) and sum(totals)==ledger['known_future_reserved_bytes']==ledger['total_future_reserved_bytes'],
                        'EXACT_LIVE_ALL_FUTURE_ONCE_SUM')
                    own=rows[self.plan['future_ledger_entry_key']]
                    C.need(str(own['job_id'])==self.job_id and own['output_root']==str(self.out) and own['forecast_bytes']==self.cap,
                        'THIS_PARENT_REAL_REGISTERED_FUTURE_NOT_ANOTHER_WRITER')
                    quota=QUOTA.observe(self.client,expected_identity_reference=self.plan['quota_provider_identity_reference'],record=self.record_quota)
                    C.need(self.client.identity==self.plan['quota_provider_identity_reference'],'SAME_REAL_FINITE_PROVIDER')
                    cutoff=quota['raw_quota']['started_unix_seconds'];C.need(type(cutoff) in (int,float) and 0<=time.time()-cutoff<=120,'REAL_QUOTA_QUERY_TIME_FOR_BLOCK_CREDIT')
                    local_credit=self.closed_credit_at(cutoff)
                    ledger_remaining=own['future_reserved_bytes']
                    C.need(type(ledger_remaining) is int and 0<=ledger_remaining<=self.cap,'VALID_AUTHORITATIVE_REMAINING_OWN_FUTURE')
                    # The current Root V2 ledger may already carry more proven
                    # credit. Take max(proven credits), never add them or reject
                    # its legitimate credit merely because our local sample is conservative.
                    external_credit=self.cap-ledger_remaining
                    credit=max(local_credit,external_credit);remaining_own=self.cap-credit
                    future=ledger['total_future_reserved_bytes']-ledger_remaining+remaining_own
                remaining=OLD.remaining_wall(self.clock,time.monotonic())
                C.need(quota['publisher_expires_unix_seconds']>=self.clock['cpu_wall_at_anchor']+self.clock['remaining_at_anchor_seconds']+300,'FINITE_PROVIDER_COVERS_THIS_ALLOCATION')
                if quota['free_bytes']-future<100000000000:self.stop=self.stop or 'ACCOUNT100GB_STOP_NEW_READONLY_WORK'
                if remaining<=900:self.stop=self.stop or 'DAY_WALL_STOP_NEW_WORK_NATURAL_DRAIN'
                if rss>=self.plan['algorithm_rss_soft_cap_bytes'] or available<self.plan['minimum_MemAvailable_bytes']:self.stop=self.stop or 'MEMORY_STOP_NEW_WORK'
                if self.written+self.workspace()+sum(self.reserved.values())+(64<<20)>self.cap:self.stop=self.stop or 'OUTPUT_STOP_NEW_WORK'
                self.samples.append(dict(unix_seconds=time.time(),rss_bytes=rss,MemAvailable=available,remaining_wall_seconds=remaining,quota=quota,
                    current_all_future_reserved_bytes=ledger['total_future_reserved_bytes'],actual_own_allocated_prequota_credit_bytes=local_credit,
                    authoritative_ledger_own_credit_bytes=external_credit,effective_own_credit_bytes=credit,
                    credited_immutable_output_count=self._closed_credit_count,pending_closed_credit_count=len(self._closed_credit_pending),
                    effective_remaining_all_future_bytes=future,account_floor_bytes=100000000000,charged_bytes_not_used_as_disk=True,stop=self.stop))
                C.need(len(self.samples)<=6400,'FINITE_DAY_RESOURCE_OBSERVATIONS')
            except Exception as exc:
                self.failure=dict(error=repr(exc),traceback=traceback.format_exc(),last_quota=self.client.last)
                self.stop=self.stop or 'RESOURCE_OBSERVATION_UNKNOWN_STOP_NEW_WORK'
            return self.stop

def assemble_references(p):
    """Existing-stage input assembly only; never opens prepared/packet/DB DATA."""
    old=C.meta(p['pm7_preparation_plan_reference']);base=C.meta(p['cache_plan_reference'])
    current=sources();current_paths={r['path'] for r in current}
    source=[*current,*[r for r in old['source_references'] if r['path'] not in current_paths]]
    data=[*old['data_references'],*base['data_references'],p['closed_common_manifest_reference']]
    for key in ('original_config_reference','pm7_preparation_plan_reference','cache_plan_reference','closed_common_accounting_reference',
        'quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference','source_mapping_review_reference',
        'quota_floor_policy_reference'):
        C.need(p.get(key) is not None,'ACTUAL_INPUT_NOT_READY:'+key);source.append(p[key])
    # The real formal D3 index carries the original receipt/store catalog.
    # Both are DATA refs inherited from actual publication, not login-opened.
    for key in ('D3_closed_export_reference','D3_actual_export_receipt_reference'):
        C.need(p.get(key) is not None,'ACTUAL_D3_DELIVERY_NOT_READY:'+key)
        data.append(C.F.triple(p[key]))
    manifest=C.meta(p['closed_common_manifest_reference']) # Explicitly closed pure locator/count metadata.
    for key in ('membership_tables','physical_geometry_tables','uff_identity_tables'):data.extend(manifest[key])
    account=C.meta(p['closed_common_accounting_reference']);source.append(account['raw_sacct_reference'])
    entries=[p['pm7_owner_entry'],*old['legacy_cache_parents'],*old['previous_precache_parents']]
    for entry in entries:
        source.extend(entry[k] for k in ('request_reference','submission_reference','accounting_reference'))
        if entry.get('proof_reference') is not None:source.append(entry['proof_reference'])
        if entry.get('receipt_reference') is not None:data.append(entry['receipt_reference'])
        req=C.meta(entry['request_reference']);account=C.meta(entry['accounting_reference']);source.append(account['raw_sacct_reference'])
        source.extend(r for r in req['source_references'] if r['path'] not in current_paths);data.extend(req['data_references'])
        if entry.get('proof_reference') is None:
            argv=req['execution_argv'];source.append(C.G.meta_pin(argv[argv.index('--root-preflight')+1]))
    provider=C.meta(p['quota_provider_review_reference'])
    source.extend([*provider['provider_source_references'],*provider['evidence_references'],provider['marker_reference'],provider['count_correction_authority_reference']])
    mapping=C.meta(p['source_mapping_review_reference'])
    source.extend(mapping[k] for k in ('historical_node13_source_mapping_reference','formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review'))
    # Definitions in the original explicit Source allowlist remain Source; no
    # scientific JSON/DB/Parquet is promoted by its suffix or small size.
    data=C.unique(r for r in data if r['path'] not in current_paths)
    data_paths={r['path'] for r in data}
    source=C.unique(r for r in source if r['path'] not in data_paths)
    return source,data