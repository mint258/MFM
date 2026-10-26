"""Opt-in finite durable accounting. This module never reserves real quota.

Root supplies actual reservation/profile/feed authority. Default proxy and
single-job supervisor limits remain separate and unchanged.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time

from .v3_contract import canonical_hash,require
from .v3_sample_budget_events import binding,canonical,encoded,owned_bytes,physical,read_bound,write_once,fsync_directory
from .v3_proxy_segments import owned_lock

COUNTS = ('launch_attempts','successful_segments','failed_attempts','checkpoint_attempts',
    'complete_checkpoints','successful_panels','failed_panels','wsd_children','events','ack_attempts')
KINDS = ('training','checkpoint','failed','SDK','cache','external_guard','H0_panel','source_snapshot','management')
OPERATIONAL_REFS = ('Root_segment_admission','quota_feed_descriptor','lease')
REPOSITORY = Path(__file__).absolute().parents[3]


def enabled(configuration): return 'long_run_policy' in configuration


def integer(value,name,minimum=1):
    require(type(value) is int and value >= minimum,'Explicit finite integer required: '+name)
    return value


def policy(configuration,plan=None):
    value = configuration['long_run_policy']
    require(set(value) == {'schema','segment_bytes','segment_seconds','durable_bytes','metadata_bytes',
        'metadata_records','managed_roots','inode_limit','quota_max_age_seconds','checkpoint_bytes','counts'}
        and value['schema'] == 'model_v3_long_run_policy_v1','Explicit complete long-run policy required')
    for key in set(value)-{'schema','counts'}: integer(value[key],key)
    require(128 << 20 <= value['segment_bytes'] <= 2 << 30 and value['segment_seconds'] <= 7200,
        'Original segment2GiB/2h limits remain')
    require(value['durable_bytes'] >= value['segment_bytes'] and value['metadata_bytes'] < value['durable_bytes']
        and value['checkpoint_bytes'] < value['segment_bytes'] and value['quota_max_age_seconds'] <= 90,
        'Finite durable/metadata/checkpoint/fresh-quota envelope differs')
    require(set(value['counts']) == set(COUNTS),'Every independent finite counter required')
    for key,count in value['counts'].items(): integer(count,key,0)
    require(value['counts']['launch_attempts'] > 0 and value['counts']['checkpoint_attempts'] > 0,
        'Training needs finite positive launch/checkpoint attempts')
    require(value['counts']['complete_checkpoints'] <= value['counts']['checkpoint_attempts']
        and value['counts']['successful_segments']+value['counts']['failed_attempts'] <= value['counts']['launch_attempts'],
        'Independent attempt/success/failure allowances inconsistent')
    if plan is not None:
        require(plan.max_total_checkpoints == value['counts']['checkpoint_attempts']
            and plan.max_segment_bytes <= value['segment_bytes'] and plan.max_segment_seconds <= value['segment_seconds'],
            'Original segment plan and explicit long-run checkpoint-attempt allowance differ')
        require(value['segment_bytes'] == configuration['proxy_contract']['resources']['joint_output_bytes'],
            'Opt-in segment cap must match the unchanged supervisor resource envelope')
    return value


def stable_request_identity(request):
    value = deepcopy(request); value.pop('Root_admission',None)
    for key in OPERATIONAL_REFS: value['long_run'].pop(key,None)
    return canonical_hash(value)


def profile_identity(configuration,request):
    """Explicit numeric/data projection; no cap-derived profile hash cycle."""
    contract = configuration['proxy_contract']
    keys = ('groups','fields','views','heads','optimizer','sampler','precision','training_view','validation',
        'batch_limits','loss_weights','clip_norm','probe_samples','execution')
    value = {'model':configuration['model'],'numeric_capacity_contract':{k:contract[k] for k in keys}}
    return canonical_hash({'configuration':value,'input_projection':request['input_projection'],
        'actual_runtime_files':request['sources']['runtime_files']})


def read_current(path):
    # Publication can replace a feed atomically. Retry only changed/vanished
    # immutable-byte observations, never malformed authority or wrong owner.
    for attempt in range(3):
        try:
            ref = binding(path); value = read_bound(ref)
            with physical(path).open('rb') as stream: raw = stream.read((2 << 20)+1)
            require(len(raw) <= 2 << 20 and hashlib.sha256(raw).hexdigest() == ref['sha256'],'Metadata changed before parsing')
            return value,ref,raw
        except FileNotFoundError:
            if attempt == 2: raise
        except ValueError as error:
            if str(error) not in ('Bound source changed while hashing','Metadata binding/size differs','Metadata changed before parsing') or attempt == 2: raise


def write_raw_once(path,raw):
    path = physical(path); require(len(raw) <= 2 << 20,'Bounded raw quota snapshot required')
    if path.exists(): require(path.read_bytes() == raw,'Existing raw quota snapshot differs')
    else:
        with path.open('xb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        fsync_directory(path.parent)
    return binding(path)


def parse_quota(feed,*,filesystem,uid,now,max_age,engineering):
    require(feed['schema'] == 'model_v3_Root_live_quota_v1' and feed['uid'] == uid
        and feed['host'] == 'sonmi' and feed['filesystem'] == filesystem and feed['returncode'] == 0,
        'Actual UID/filesystem/host/native quota receipt differs')
    require(type(feed['captured_unix']) in (int,float) and math.isfinite(feed['captured_unix'])
        and 0 <= now-feed['captured_unix'] <= max_age,'Quota feed stale or future')
    require(feed['authority'] == ('ENGINEERING_METADATA_FIXTURE' if engineering else 'ROOT_ACTUAL'),
        'Synthetic quota cannot supply scientific authority')
    rows = [line.split() for line in feed['stdout'].splitlines() if line.split() and line.split()[0] == filesystem]
    require(len(rows) == 1 and len(rows[0]) >= 4,'Unique native user quota row required')
    numbers = rows[0][1:4]
    require(all(re.fullmatch(r'[0-9]+\*?',number) for number in numbers),'Native quota integer KiB fields required')
    used,soft,hard = (int(number.rstrip('*'))*1024 for number in numbers)
    limits = [number for number in (soft,hard) if number > 0]
    require(limits and used <= min(limits),'Unknown or exhausted positive user quota limit')
    inode = feed['inodes']
    require(inode['filesystem'] == filesystem and inode['uid'] == uid
        and 0 <= now-inode['captured_unix'] <= max_age,'Fresh corresponding inode receipt required')
    integer(inode['available'],'available inodes',0)
    return {'used_bytes':used,'limit_bytes':min(limits),'free_bytes':min(limits)-used,'available_inodes':inode['available']}


def validate_admission(request,configuration,*,segment_id=None,job_root=None,lineage_root=None,now=None):
    """Read-only verification; does not create a reservation or any output."""
    value = policy(configuration); fixed_now = now; now = time.time() if now is None else now
    lr = request['long_run']; principal = read_bound(lr['reservation_principal'])
    require(principal['schema'] == 'model_v3_Root_durable_reservation_v1'
        and principal['uid'] == os.getuid() and principal['status'] == 'ROOT_COORDINATOR_RESERVED_FINITE'
        and principal['policy_sha256'] == canonical_hash(value)
        and principal['max_bytes'] == value['durable_bytes']
        and principal['counts'] == value['counts'],'Root finite reservation principal differs')
    accepted = principal.get('science_identities',[principal.get('science_identity_sha256')])
    require(type(accepted) is list and accepted and len(accepted) <= value['counts']['wsd_children']+1
        and canonical_hash({k:v for k,v in configuration.items() if k != 'seed'}) in accepted,
        'Reservation common scientific identity differs')
    integer(principal['initial_existing_bytes'],'initial existing bytes',0)
    integer(principal['reserved_additional_bytes'],'reserved additional bytes')
    require(principal['initial_existing_bytes']+principal['reserved_additional_bytes'] == value['durable_bytes'],
        'Historical baseline and new finite reservation do not cover this exact durable cap')
    require(set(principal['initial_counts']) == set(COUNTS),'Historical finite counters must be explicit, never reset')
    for key,number in principal['initial_counts'].items():
        integer(number,'historical '+key,0); require(number <= value['counts'][key],'Historical counter already exceeds plan')
    engineering = configuration['engineering_only'] is True
    expected_authority = 'ENGINEERING_METADATA_FIXTURE' if engineering else 'ROOT_ACTUAL'
    require(principal['authority'] == expected_authority,'Engineering reservation cannot enter science')
    root_record = read_bound(principal['Root_reservation_record'])
    require(root_record['reservation_id'] == principal['reservation_id'] and root_record['uid'] == principal['uid']
        and root_record['durable_root'] == principal['durable_root']
        and root_record['reserved_additional_bytes'] == principal['reserved_additional_bytes']
        and root_record['initial_counts'] == principal['initial_counts']
        and root_record['authority'] == expected_authority,'Root global reservation record differs')
    profile = read_bound(lr['profile'])
    require(profile['schema'] == 'model_v3_Root_long_run_profile_v1' and profile['authority'] == expected_authority
        and profile['profile_identity_sha256'] == profile_identity(configuration,request)
        and profile['code_sha'] == request['sources']['code_sha'],'Actual final configuration/data/source profile differs')
    measured = ('checkpoint_bytes','SDK_bytes_per_segment','save_seconds','validation_seconds','panel_seconds','cleanup_seconds')
    require(all(type(profile[key]) in (int,float) and math.isfinite(profile[key]) and profile[key] > 0 for key in measured)
        and profile['checkpoint_bytes'] <= value['checkpoint_bytes'],'All real checkpoint/SDK/save/validation/panel/cleanup measurements required')
    segment_plan = configuration['proxy_contract']['sample_plan']; resources = configuration['proxy_contract']['resources']
    require(segment_plan['max_checkpoints_per_segment']*value['checkpoint_bytes']+segment_plan['checkpoint_reserve_bytes']
        <= segment_plan['max_segment_bytes'] and profile['SDK_bytes_per_segment'] <= resources['tracking_bytes'],
        'Measured SDK and registered worst-case checkpoints do not fit original segment cap')
    require(profile['save_seconds']+profile['cleanup_seconds'] <= segment_plan['checkpoint_reserve_seconds']
        and segment_plan['max_checkpoints_per_segment']*(profile['save_seconds']+profile['validation_seconds'])
            +profile['cleanup_seconds'] < value['segment_seconds'],'Measured save/validation/cleanup timing exceeds segment reserves')
    require(profile['provider_future_state_bound_bytes'] >= 0 and profile['optimizer_future_state_bound_bytes'] >= 0,
        'Future committed-state bounds required')
    for key in ('checkpoint_bytes','SDK_bytes_per_segment','provider_future_state_bound_bytes','optimizer_future_state_bound_bytes'):
        integer(profile[key],key,0)
    require(profile['checkpoint_bytes']+profile['provider_future_state_bound_bytes']+profile['optimizer_future_state_bound_bytes']
        <= value['checkpoint_bytes'],'Measured payload plus declared future growth exceeds registered checkpoint cap')
    if not engineering:
        require(profile['final_D_authority_verified'] is True and profile['actual_final_D_profile'] is True
            and profile['status'] == 'ROOT_VERIFIED_FINAL_DATA_PROFILE','Final-D actual profile missing; prototype is not scientific capacity evidence')
        require(type(profile['base_records_per_second']) in (int,float) and math.isfinite(profile['base_records_per_second'])
            and profile['base_records_per_second'] > 0 and type(profile['accounting_worst_case_roots']) is int
            and profile['accounting_worst_case_roots'] >= value['managed_roots']
            and type(profile['accounting_seconds_per_guard']) in (int,float) and math.isfinite(profile['accounting_seconds_per_guard'])
            and profile['accounting_seconds_per_guard'] > 0,'Actual base-draw throughput and history-scale accounting cost required')
        terminal = read_bound(profile['actual_terminal'])
        require(terminal['status'] == 'COMPLETED' and terminal['exit_code'] == 0
            and terminal['profile'] == lr['profile_result'],'Actual successful final-D profile terminal required')
        raw_profile = read_bound(lr['profile_result'])
        profile_fields = (*measured,'base_records_per_second','accounting_worst_case_roots','accounting_seconds_per_guard')
        require(raw_profile['code_sha'] == request['sources']['code_sha']
            and all(raw_profile['long_run_measurements'][key] == profile[key] for key in profile_fields),
            'Root profile projection differs from actual saved measurements')
        for key in ('profile_result','final_data_evidence','future_state_evidence'):
            for ref in (lr[key] if type(lr[key]) is list else [lr[key]]):
                require(binding(ref['path']) == ref,'Profile/authority raw bytes differ')
    admission = read_bound(lr['Root_segment_admission']); lease = read_bound(lr['lease'])
    require(admission['schema'] == 'model_v3_Root_long_run_segment_admission_v1'
        and admission['stable_request_identity_sha256'] == stable_request_identity(request)
        and admission['reservation_principal'] == lr['reservation_principal']
        and admission['authority'] == expected_authority,'Root operational admission or stable request identity differs')
    require(lease['reservation_id'] == principal['reservation_id'] and lease['authority'] == expected_authority
        and lease['created_unix'] <= now < lease['expires_unix'],'Root reservation lease missing/expired')
    require(admission['lease'] == lr['lease'] and admission['quota_feed_descriptor'] == lr['quota_feed_descriptor'],
        'Root segment operational references differ')
    if segment_id is not None:
        require(admission['segment_id'] == segment_id and physical(admission['job_root']) == physical(job_root)
            and physical(admission['lineage_root']) == physical(lineage_root),'Admission is for another physical segment/lineage')
        require(lease['expires_unix']-now >= value['segment_seconds'],'Reservation lease must cover whole segment at launch')
        if not engineering:
            require(str(admission['job_id']) == os.environ.get('SLURM_JOB_ID'),'Root admission must bind the actual allocated job')
    descriptor = read_bound(lr['quota_feed_descriptor'])
    require(descriptor['schema'] == 'model_v3_Root_quota_feed_descriptor_v1'
        and descriptor['uid'] == principal['uid'] and descriptor['filesystem'] == principal['filesystem']
        and descriptor['authority'] == expected_authority,'Root live feed descriptor differs')
    require(binding(descriptor['producer_source']['path']) == descriptor['producer_source'], 'Pinned quota producer source differs')
    feed,feed_ref,raw_feed = read_current(descriptor['feed_path'])
    observation_now = time.time() if fixed_now is None else fixed_now
    require(observation_now < lease['expires_unix'],'Reservation lease expired during authority validation')
    quota = parse_quota(feed,filesystem=principal['filesystem'],uid=principal['uid'],now=observation_now,
        max_age=value['quota_max_age_seconds'],engineering=engineering)
    require(feed['producer_source_sha256'] == descriptor['producer_source']['sha256']
        and feed['phase_ledger_id'] == root_record['phase_ledger_id'],'Live quota producer/global phase identity differs')
    slots = feed['reservations']; own = slots[principal['reservation_id']]
    require(own['durable_root'] == principal['durable_root'] and own['principal_sha256'] == lr['reservation_principal']['sha256'],
        'Fresh global reservation slot ownership differs')
    for slot in slots.values(): integer(slot['remaining_bytes'],'outstanding reserved bytes',0)
    integer(feed['headroom_bytes'],'quota headroom',0)
    other = sum(slot['remaining_bytes'] for key,slot in slots.items() if key != principal['reservation_id'])
    available = quota['free_bytes']-other-feed['headroom_bytes']
    require(available >= 0 and quota['available_inodes'] >= value['inode_limit'],'Quota/inode/outstanding reservation overcommit')
    return {'policy':value,'principal':principal,'admission':admission,'profile':profile,'lease':lease,
        'quota':quota,'quota_ref':feed_ref,'feed':feed,'quota_available_after_other_bytes':available,
        'own_remaining_bytes':own['remaining_bytes'],'stable_request_identity_sha256':stable_request_identity(request),
        'raw_feed':raw_feed}


def _runtime_census(root):
    source = REPOSITORY/'tools/model_v3/runtime_monitor.py'
    name = '_long_run_census_'+hashlib.sha256(source.read_bytes()).hexdigest()
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name,source); module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module; spec.loader.exec_module(module)
    return sys.modules[name].owned_output_bytes(root)


class DurableLedger:
    """Append-only accounting under an already existing Root reservation."""
    def __init__(self,request,configuration):
        self.request,self.configuration = deepcopy(request),deepcopy(configuration)
        self.admission = validate_admission(request,configuration); self.limits = self.admission['policy']
        self.root = physical(self.admission['principal']['durable_root'])
        require(not self.root.is_relative_to(REPOSITORY),'Durable ledger remains outside Git')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self._depth = 0
        with self.transaction():
            for name in ('records','index','roots','feeds','lineages'): physical(self.root/name).mkdir(exist_ok=True)
            write_once(self.root/'PRINCIPAL.json',{'schema':'model_v3_durable_ledger_v1',
                'reservation_principal':request['long_run']['reservation_principal'],'policy':self.limits})
            self._space(0)
        self.register_root(self.root,kind='management',must_exist=True)
        registry = read_bound(request['long_run']['initial_roots'])
        require(registry['schema'] == 'model_v3_long_run_initial_roots_v1','Complete declared old-root registry required')
        for entry in registry['roots']: self.register_root(entry['path'],kind=entry['kind'],must_exist=entry['must_exist'],entry_type=entry['type'])

    @contextmanager
    def transaction(self):
        if self._depth:
            self._depth += 1
            try: yield
            finally: self._depth -= 1
        else:
            with owned_lock(self.root,'accounting.lock') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX); self._depth = 1
                try: yield
                finally: self._depth = 0; fcntl.flock(lock,fcntl.LOCK_UN)

    def _space(self,additional,entries=1):
        require(owned_bytes(self.root)+additional <= self.limits['metadata_bytes'],'Finite durable metadata bytes exhausted')
        count = sum(1 for _ in self.root.rglob('*.json'))
        require(count+(entries if additional else 0) <= self.limits['metadata_records'],'All metadata files, including quota snapshots, are bounded')
        if (self.root/'roots').exists():
            total = 0
            for row in self.root_records():
                path = physical(row['path'])
                if path.exists(): total += _runtime_census(path) if row['type'] == 'directory' else binding(path)['bytes']
            require(total+additional <= self.limits['durable_bytes'],'Metadata also consumes durable storage')

    def records(self):
        indices = sorted((self.root/'index').glob('*.json')); rows = []; previous = None; expected = set()
        require(len(indices) <= self.limits['metadata_records'],'Finite append-only index exhausted')
        for number,path in enumerate(indices,1):
            ref = binding(path); item = read_bound(ref)
            require(path.name == f'{number:012d}.json' and item['sequence'] == number and item['previous'] == previous,
                'Immutable counter index chain missing/changed; cannot reset history')
            row,record_ref = item['record'],item['record_ref']; target = physical(record_ref['path'])
            require(target.parent == self.root/'records' and target.name == canonical_hash({'kind':row['kind'],'identity':row['identity']})+'.json'
                and record_ref['sha256'] == hashlib.sha256(encoded(row)).hexdigest() and record_ref['bytes'] == len(encoded(row)),
                'Counter intent identity/bytes differ')
            require(str(target) not in expected,'Duplicate counter index intent')
            expected.add(str(target))
            if target.exists(): require(read_bound(record_ref) == row,'Published counter record differs')
            # A crash after the durable intent still consumes its slot. Missing
            # materialization cannot erase an attempt or free a hold.
            rows.append(row); previous = ref
        require(all(str(path) in expected for path in (self.root/'records').glob('*.json')),
            'Unindexed counter bytes retained; explicit recovery required')
        return rows

    def _ensure_fresh_authority(self):
        now = time.time()
        if now >= self.admission['lease']['expires_unix'] or not 0 <= now-self.admission['feed']['captured_unix'] <= self.limits['quota_max_age_seconds']:
            checked = validate_admission(self.request,self.configuration)
            require(checked['stable_request_identity_sha256'] == self.admission['stable_request_identity_sha256'],
                'Fresh operational authority changed stable lineage')
            self._space(len(checked['raw_feed']))
            write_raw_once(self.root/'feeds'/(checked['quota_ref']['sha256']+'.json'),checked['raw_feed'])
            self.admission = checked

    def append(self,kind,identity,body):
        require(kind in COUNTS or kind in ('observation','root_seen','segment_terminal'),'Known independent event kind required')
        key = canonical_hash({'kind':kind,'identity':identity}); value = {'kind':kind,'identity':identity,'body':body}
        with self.transaction():
            self._ensure_fresh_authority()
            path = self.root/'records'/(key+'.json')
            rows = self.records(); existing = [row for row in rows if row['kind'] == kind and row['identity'] == identity]
            if existing:
                require(existing == [value],'Immutable counter replay changes body')
            else:
                require(len(rows) < self.limits['metadata_records'],'Metadata record count exhausted')
                if kind in COUNTS: require(self.admission['principal']['initial_counts'][kind]+sum(row['kind'] == kind for row in rows)
                    < self.limits['counts'][kind], 'Independent '+kind+' cap exhausted')
                indices = sorted((self.root/'index').glob('*.json'))
                record_ref = {'path':str(path),'bytes':len(encoded(value)),'sha256':hashlib.sha256(encoded(value)).hexdigest()}
                intent = {'sequence':len(indices)+1,'previous':binding(indices[-1]) if indices else None,
                    'record_ref':record_ref,'record':value}
                self._space(len(encoded(value))+len(encoded(intent)),entries=2)
                write_once(self.root/'index'/f'{len(indices)+1:012d}.json',intent)
            return write_once(path,value)

    def register_root(self,path,*,kind,must_exist=False,entry_type='directory'):
        path = physical(path)
        require(kind in KINDS and entry_type in ('directory','file') and type(must_exist) is bool,'Explicit owned root kind/type required')
        require(not path.is_relative_to(REPOSITORY),'Outputs never belong in Git')
        record = {'path':str(path),'kind':kind,'must_exist':must_exist,'type':entry_type}
        key = canonical_hash({'path':str(path)})
        with self.transaction():
            self._ensure_fresh_authority()
            target = self.root/'roots'/(key+'.json'); previous = list((self.root/'roots').glob('*.json'))
            if not target.exists():
                require(len(previous) < self.limits['managed_roots'],'Managed root cap exhausted')
                for item in previous:
                    old = physical(read_bound(binding(item))['path'])
                    require(not old.is_relative_to(path) and not path.is_relative_to(old),'Duplicate/nested output roots would conceal or double-count storage')
                self._space(len(encoded(record)))
            return write_once(target,record)

    def root_records(self):
        paths = list((self.root/'roots').glob('*.json'))
        require(len(paths) <= self.limits['managed_roots'],'Managed root count drift')
        return [read_bound(binding(path)) for path in paths]

    def census(self):
        with self.transaction():
            rows = self.records(); seen = {row['identity'] for row in rows if row['kind'] == 'root_seen'}
            total,inodes = 0,0
            for row in self.root_records():
                path = physical(row['path'])
                if not path.exists():
                    require(not row['must_exist'] and str(path) not in seen,'Historical/previously observed root disappeared')
                    continue
                require(path.stat().st_uid == os.getuid(),'Root owner changed')
                require(path.is_dir() if row['type'] == 'directory' else path.is_file(),'Registered root type differs')
                total += _runtime_census(path) if row['type'] == 'directory' else binding(path)['bytes']
                inodes += 1
                if row['type'] == 'directory':
                    for _,directories,files in os.walk(path,followlinks=False): inodes += len(directories)+len(files)
                if str(path) not in seen: self.append('root_seen',str(path),{'exists':True})
            require(total <= self.limits['durable_bytes'],'Cumulative durable reservation byte cap exhausted')
            require(inodes <= self.limits['inode_limit'],'Explicit cumulative inode cap exhausted')
            self._space(0)
            # Root-seen intents written above are real output too.
            return sum((_runtime_census(physical(row['path'])) if row['type'] == 'directory' else binding(row['path'])['bytes'])
                for row in self.root_records() if physical(row['path']).exists())

    def refresh(self):
        checked = validate_admission(self.request,self.configuration)
        require(checked['stable_request_identity_sha256'] == self.admission['stable_request_identity_sha256'], 'Operational update changed scientific/source/data/principal identity')
        self.census(); principal = checked['principal']
        with self.transaction():
            snapshot = self.root/'feeds'/(checked['quota_ref']['sha256']+'.json')
            self._space(0 if snapshot.exists() else len(checked['raw_feed']))
            write_raw_once(snapshot,checked['raw_feed'])
        used = self.census()
        growth = max(0,used-principal['initial_existing_bytes'])
        remaining = max(0,principal['reserved_additional_bytes']-growth)
        effective = min(remaining,checked['own_remaining_bytes'])
        require(effective <= checked['quota_available_after_other_bytes'],'Fresh actual quota cannot cover outstanding own reservation')
        self.admission = checked
        return {'durable_bytes':used,'durable_remaining_bytes':self.limits['durable_bytes']-used,
            'quota_reserved_remaining_bytes':effective,'quota_snapshot':binding(snapshot)}

    def remaining(self,*,job_root=None):
        state = self.refresh()
        rows = self.records(); closed = {row['identity'] for row in rows if row['kind'] == 'segment_terminal'}
        current = str(physical(job_root)) if job_root is not None else None
        held = 0
        for row in rows:
            if row['kind'] == 'launch_attempts' and row['identity'] not in closed and row['identity'] != current:
                path = physical(row['identity']); actual = _runtime_census(path) if path.exists() else 0
                held += max(0,row['body']['held_bytes']-actual)
        return min(state['durable_remaining_bytes'],state['quota_reserved_remaining_bytes'])-held

    def allocate_segment(self,*,request_ref,segment_id,job_root,lineage_root):
        checked = validate_admission(self.request,self.configuration,segment_id=segment_id,job_root=job_root,lineage_root=lineage_root)
        with self.transaction():
            require(self.remaining() >= self.limits['segment_bytes'],'No unspent finite reservation for this whole segment; active holds retained')
            identity = str(physical(job_root))
            lineage = str(physical(lineage_root))
            self._space(1024)
            write_once(self.root/'lineages'/(canonical_hash({'path':lineage})+'.json'),
                {'lineage_root':lineage,'stable_request_identity_sha256':stable_request_identity(self.request)})
            self.register_root(job_root,kind='training')
            # Idempotent root registration is semantic, not a cap reset.
            existing_roots = {row['path']:row for row in self.root_records()}
            if str(physical(lineage_root)) not in existing_roots: self.register_root(lineage_root,kind='management')
            for entry in checked['admission']['external_roots']:
                self.register_root(entry['path'],kind=entry['kind'],entry_type=entry['type'],must_exist=entry['must_exist'])
            return self.append('launch_attempts',identity,{'request':request_ref,'segment_id':segment_id,'job_root':identity,
                'lineage_root':str(physical(lineage_root)),'held_bytes':self.limits['segment_bytes'],
                'Root_admission':self.request['long_run']['Root_segment_admission']})

    def terminal(self,*,job_root,status,result_ref):
        require(status in ('successful_segments','failed_attempts'),'Explicit computation terminal counter required')
        with self.transaction():
            self.refresh(); return self.append('observation',str(physical(job_root))+':child_terminal',{'result':result_ref,
                'child_status':status,'Root_terminal_not_asserted':True})

    def seal_segment(self,*,job_root,Root_closure_ref):
        """Release only unused hold after actual Root terminal/process closure.

        Actual bytes and all lifetime counters remain. This is not a scientific
        result/SDK metric certificate and does not ACK a panel.
        """
        closure = read_bound(Root_closure_ref); engineering = self.configuration['engineering_only']
        require(closure['schema'] == 'model_v3_Root_storage_segment_closure_v1'
            and closure['authority'] == ('ENGINEERING_METADATA_FIXTURE' if engineering else 'ROOT_ACTUAL')
            and physical(closure['job_root']) == physical(job_root),'Root storage closure identity differs')
        terminal_state = closure.get('status','COMPLETED') if engineering else None
        if not engineering:
            terminal = read_bound(closure['slurm_terminal']); supervisor = read_bound(closure['supervisor'])
            require(terminal['status'] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY')
                and str(terminal['job_id']) == str(supervisor['job_id'])
                and supervisor['remaining_recorded_processes_before_retirement'] == []
                and supervisor['private_storage_cleanup_errors'] == [],'Actual Slurm terminal and owned process/private cleanup closure required')
            terminal_state = ('COMPLETED' if terminal['status'] == 'COMPLETED' and terminal['exit_code'] == 0
                and supervisor['status'] == 'COMPLETED' and supervisor['exit_code'] == 0 else 'FAILED')
        with self.transaction():
            launches = [row for row in self.records() if row['kind'] == 'launch_attempts' and row['identity'] == str(physical(job_root))]
            require(len(launches) == 1,'Unknown launch cannot release a hold')
            admission = read_bound(launches[0]['body']['Root_admission'])
            if not engineering:
                require(str(admission['job_id']) == str(terminal['job_id']) == str(closure['job_id']), 'Root closure is for another actual job')
                source = admission['supervisor_source']
                require(binding(source['path']) == source and supervisor['supervisor_source_sha256'] == source['sha256'],
                    'Actual supervisor implementation differs from Root launch admission')
            self.refresh()
            panel = admission.get('workload','training') == 'panel'
            counter = ('successful_panels' if terminal_state == 'COMPLETED' else 'failed_panels') if panel else (
                'successful_segments' if terminal_state == 'COMPLETED' else 'failed_attempts')
            self.append(counter,str(physical(job_root)),{'Root_closure':Root_closure_ref})
            return self.append('segment_terminal',str(physical(job_root)),{'Root_closure':Root_closure_ref,
                'bytes_preserved':_runtime_census(physical(job_root)),'scientific_acceptance':False})

    def checkpoint(self,experiment,reason,save):
        import uuid
        with self.transaction():
            self.refresh()
            directories = experiment._all_checkpoint_directories()
            complete = sum((path/'EXPERIMENT_COMPLETE.json').exists() for path in directories)
            require(complete < self.limits['counts']['complete_checkpoints'],'Independent complete-checkpoint cap exhausted')
            attempt = self.append('checkpoint_attempts',uuid.uuid4().hex,{'segment':str(experiment.segment),
                'samples_consumed':experiment.trainer.clock.samples_consumed,'reason':reason})
            previous = experiment.last_checkpoint
            try:
                result = save()
                require(result['path'] != (previous or {}).get('path'),'A new attempt must create a new checkpoint')
                require(Path(result['path']).parent.joinpath('trainer/payload.pt').stat().st_size <= self.limits['checkpoint_bytes'],
                    'Actual checkpoint exceeds registered payload cap')
                self.append('complete_checkpoints',result['sha256'],{'completion':result,'attempt':attempt})
                return result
            finally:
                # Even exceptions retain the attempt and every actual byte.
                self._space(0)


def allocate_long_launch(root,*,request_ref,lineage,job_root,segment_id,maximum_attempts,maximum_bytes):
    """Compatibility metadata; the durable ledger owns independent attempt caps."""
    from .v3_proxy_segments import allocate_launch
    request = read_bound(request_ref)
    config = read_bound(request['configuration'])
    if not enabled(config):
        return allocate_launch(root,request_ref=request_ref,lineage=lineage,job_root=job_root,segment_id=segment_id,
            maximum_attempts=maximum_attempts,maximum_bytes=maximum_bytes)
    root = physical(root); root.mkdir(mode=0o700,parents=True,exist_ok=True)
    value = policy(config); require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',segment_id or ''),'Explicit segment id required')
    body = {'schema':'model_v3_proxy_launch_allocation_v1','segment_id':segment_id,
        'job_root':str(physical(job_root)),'request':request_ref}
    header = {'schema':'model_v3_long_run_launch_policy_v1','stable_request_identity_sha256':stable_request_identity(request),
        'lineage':lineage,'maximum_attempts':maximum_attempts,'maximum_bytes':maximum_bytes}
    with owned_lock(root,'metadata.lock') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX); physical(root/'launches').mkdir(exist_ok=True)
        paths = list((root/'launches').glob('*.json')); target = root/'launches'/(segment_id+'.json')
        require(not target.exists() and len(paths) < value['counts']['launch_attempts'],'Independent launch identity/cap exhausted')
        require(all(read_bound(binding(p))['job_root'] != body['job_root'] for p in paths),'Fresh long-run job root required')
        require(owned_bytes(root)+len(encoded(body))+len(encoded(header)) <= maximum_bytes,'Canonical metadata allowance exhausted')
        write_once(root/'LAUNCH_POLICY.json',header)
        return write_once(target,body)


def controller_class():
    # Late import keeps the optional path out of the original module cycle.
    from .v3_proxy_segments import BoundedLineageController
    class LongRunLineageController(BoundedLineageController):
        def __init__(self,*args,**kwargs):
            contract = kwargs['contract']; config = read_bound(contract['model_configuration'])
            self.long_policy = policy(config); self.storage = None
            super().__init__(*args,**kwargs)

        def registered_segments(self):
            with self.transaction():
                paths = list((self.root/'segments').glob('*.json'))
                require(len(paths) <= self.long_policy['counts']['launch_attempts'],'Independent segment registration cap exhausted')
                records = [read_bound(binding(path)) for path in paths]
                require(all(row['schema'] == 'model_v3_proxy_segment_registration_v1'
                    and row['contract_sha256'] == canonical(self.contract) and row['segment_id'] == path.stem
                    for row,path in zip(records,paths)),'Foreign long-run segment contract')
                return records

        def register_segment(self,*,segment_id,experiment_root,request_ref,parent):
            from .v3_sample_budget_events import canonical
            with self.transaction():
                require(len(self.registered_segments()) < self.long_policy['counts']['launch_attempts'],'Independent segment cap exhausted')
                root = physical(experiment_root)
                launch = read_bound(binding(self.root/'launches'/(segment_id+'.json')))
                require(launch['job_root'] == str(root.parent) and launch['request'] == request_ref,'Segment allocation differs')
                body = {'schema':'model_v3_proxy_segment_registration_v1','segment_id':segment_id,
                    'experiment_root':str(root),'request':request_ref,'parent_checkpoint':parent,'contract_sha256':canonical(self.contract)}
                path = self.root/'segments'/(segment_id+'.json'); require(not path.exists(),'Fresh segment identity required')
                self._space(len(encoded(body))); return write_once(path,body)

        def launch_roots(self):
            with self.transaction():
                paths = list((self.root/'launches').glob('*.json'))
                require(len(paths) <= self.long_policy['counts']['launch_attempts'],'Independent launch cap exhausted')
                header = read_bound(binding(self.root/'LAUNCH_POLICY.json'))
                for path in paths:
                    row = read_bound(binding(path)); request = read_bound(row['request'])
                    require(stable_request_identity(request) == header['stable_request_identity_sha256'],'Operational renewal changed stable request')
                return [physical(read_bound(binding(path))['job_root']) for path in paths]

        def publish(self,completion_ref):
            from .v3_sample_budget_events import verify_checkpoint_record
            _,state = verify_checkpoint_record(completion_ref)
            if self.storage is not None: self.storage.append('events',state['event']['event_id'],{'completion':completion_ref})
            return super().publish(completion_ref)

        def acknowledge(self,event_ref,result_ref,evidence_ref):
            require(self.storage is not None,'Long-run ACK requires fresh reservation authority through storage_control CLI')
            import uuid
            from .v3_sample_budget_events import validate_panel_evidence,fsync_directory
            # Global accounting then canonical metadata: same order as save/
            # publication, so an independent ACK cannot deadlock training.
            with self.storage.transaction(),self.transaction():
                self.storage.refresh()
                self.storage.append('ack_attempts',canonical_hash([event_ref,result_ref,evidence_ref]),
                    {'event':event_ref,'result':result_ref,'evidence':evidence_ref})
                event = read_bound(event_ref); known = {ref['sha256']:body for ref,body in self.events()}
                require(event_ref['sha256'] in known and event['body'] == known[event_ref['sha256']],'Unknown immutable event')
                body = event['body']; previous = self.acknowledgements().get(body['event_id'])
                if previous is not None:
                    require(previous['result'] == result_ref and previous['evidence'] == evidence_ref,'ACK replay changes evidence')
                    return previous
                result,evidence = read_bound(result_ref),read_bound(evidence_ref)
                validate_panel_evidence(body,result_ref,result,evidence)
                receipt = {'schema':'model_v3_sample_panel_ack_v1','event_id':body['event_id'],
                    'event':event_ref,'result':result_ref,'evidence':evidence_ref}
                size = 2*len(encoded(receipt)); self._space(size)
                require(self.storage.remaining() >= size,'Finite quota/durable ACK reserve exhausted')
                directory = self.root/'acks'/(body['event_id']+'_'+uuid.uuid4().hex)
                directory.mkdir(); fsync_directory(directory.parent)
                write_once(directory/'receipt.json',receipt); write_once(directory/'ACK_COMPLETE.json',receipt)
                return receipt
    return LongRunLineageController


def attach_experiment(experiment,ledger):
    experiment.durable_storage = ledger
    if hasattr(experiment.controller,'storage'): experiment.controller.storage = ledger
    # Checkpoint wrappers and numeric trainer contracts contain no seed-specific
    # reservation refs. They remain in launch/accounting records instead.
    return experiment
