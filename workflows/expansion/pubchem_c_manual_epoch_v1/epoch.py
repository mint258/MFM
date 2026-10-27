"""Manual metadata epoch authority. No automatic grant, retry or science body IO."""
import argparse,ast,copy,fcntl,json,os,re,stat,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_continuation_alpha_v3 import contracts as A
from pubchem_c_metadata_recovery_v4 import controller as R,recovery as OLD
from . import policy as P
HERE=Q.ROOT/'code/pubchem_c_manual_epoch_v1';QUEUE=Q.ROOT/'code/secondary_cpu_readonly_pubchem_epoch_v1'
FILES=('__init__.py','epoch.py','controller.py','policy.py','fixture_cpu.py','test_epoch.py','README.md')
QUEUE_FILES=('__init__.py','adapters.py','controller.py')
SOURCE='ROOT_PUBCHEM_MANUAL_EPOCH_SOURCE_REVIEW_V1';REVIEW='ROOT_PUBCHEM_MANUAL_EPOCH_CUTOVER_REVIEW_V1'
CONTROL=Q.ROOT/'control/secondary_cpu_queue';GLOBAL=CONTROL/'pubchem_C_finite500_global.lock'
MODULE='pubchem_c_manual_epoch_v1.controller';CAP=16<<20


def sources():return [*(Q.ref(HERE/n) for n in FILES),*(Q.ref(QUEUE/n) for n in QUEUE_FILES)]


def value(reference):return R.meta(reference)


def fresh(path):
    p=Q.literal(path);Q.need(Q.ROOT/'control' in p.parents and not p.exists(),'FRESH_IMMUTABLE_METADATA_ONLY');return p


def own_state(path):
    p=Q.literal(path);Q.need(CONTROL in p.parents and not any(q.is_symlink() for q in (p,*p.parents)),'OWN_LITERAL_CONTROL_STATE');return p


def lock_global():
    # Same physical global lock; close our descriptor on WAIT, including EAGAIN.
    GLOBAL.parent.mkdir(parents=True,exist_ok=True);fd=os.open(GLOBAL,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        s=os.fstat(fd);Q.need(stat.S_ISREG(s.st_mode) and s.st_uid==1264 and s.st_nlink==1,'OWN_REGULAR_GLOBAL_FINITE500_LOCK')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:os.close(fd);return None
        return fd
    except BaseException:os.close(fd);raise


def process(pid):
    Q.need(type(pid) is int and pid>0,'ACTUAL_POSITIVE_PID');p=Path('/proc')/str(pid)
    try:
        raw=(p/'stat').read_text();tail=raw[raw.rfind(')')+2:].split();status=(p/'status').read_text()
        uid=int(next(x for x in status.splitlines() if x.startswith('Uid:')).split()[1])
        # A foreign reused PID is distinguishable without reading its argv.
        argv=[v.decode() for v in (p/'cmdline').read_bytes().split(b'\0') if v] if uid==1264 else None
        return {'pid':pid,'uid':uid,'start_ticks':int(tail[19]),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'argv':argv}
    except (FileNotFoundError,ProcessLookupError):return None


def live(identity):
    current=process(identity['pid'])
    return current is not None and all(current[k]==identity[k] for k in ('pid','uid','start_ticks','boot_id','argv'))

def state_inventory(directory):
    directory=own_state(directory);top=directory.lstat();Q.need(stat.S_ISDIR(top.st_mode) and top.st_uid==1264,'EXISTING_OWN_HISTORICAL_STATE_REQUIRED');rows=[];used=0
    for p in sorted(directory.rglob('*')):
        s=p.lstat();Q.need(s.st_uid==1264 and (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)) and not p.is_symlink(),'OWN_METADATA_STATE_NO_LINKS')
        if p.is_dir():continue
        Q.need(p.suffix in ('.json','.txt','.md') and s.st_size<=2<<20,'SMALL_METADATA_STATE_ONLY')
        used+=s.st_size;Q.need(used<=CAP,'ORIGINAL16MIB_STATE_BOUNDS');rows.append({'relative_path':p.relative_to(directory).as_posix(),'reference':R.pin(p)})
    return {'directory':str(directory),'files':rows,'logical_bytes':used,'scientific_DATA_read':False}


def last_deadline_event(inventory):
    refs=[r for r in inventory['files'] if Path(r['relative_path']).name.startswith('event_')]
    Q.need(refs,'LAST_PREDECESSOR_EVENT_REQUIRED');row=value(refs[-1]['reference'])
    Q.need(str(row.get('action','')).startswith('FINITE_') or str(row.get('status','')).startswith('FINITE_')
      or row.get('status')=='ROOT_REVIEWED_DEADLINE_DRAIN_COMPLETE','ACTUAL_LAST_DEADLINE_OR_DRAIN_EVENT_REQUIRED')
    return refs[-1]['reference']


def source_review(reference):
    r=value(reference);Q.need(r['schema']==SOURCE and r['status']=='ROOT_APPROVED_EXACT_METADATA_SOURCES' and r['reviewer']=='root'
      and r['reason'].strip() and r['metadata_source_references']==sources() and r['scientific_source13_references']==A.sources()
      and r['science_or_once_modified'] is False and r['new_queue_algorithm'] is False,'INDEPENDENT_SOURCE_REVIEW_NO_SCIENCE13_CHANGES')
    for ref in r['metadata_source_references']:Q.verify(ref)
    return r


def fixture_evidence(receipt_ref,account_ref):
    from . import fixture_cpu as F
    receipt=value(receipt_ref);account=value(account_ref);p=account['actual_parent'];proof=value(receipt['startup_proof_reference']);plan=value(receipt['plan_reference'])
    F.validate_metadata(plan)
    Q.need(receipt['schema']=='PUBCHEM_MANUAL_EPOCH_SOURCE3_CPU_RECEIPT_V1' and receipt['status']=='PASS_PENDING_REAL_TERMINAL_ACCOUNTING'
      and A.pure_counts(receipt,3) and receipt['source_references']==sources() and receipt['scientific_body_reads']==0
      and receipt['Budget_constructed'] is receipt['ProcessPool_started'] is receipt['ordinal_claim_written'] is False
      and receipt['source_inverse_proof']['status']=='EXACT_MANUAL_EPOCH_COORDINATION_SOURCE_PROOF', 'NEW_SOURCE3_NOT_HISTORICAL_PASS')
    Q.need(account['endpoint']==proof['endpoint']==Q.ENDPOINT and account['uid']==proof['uid']==1264 and account['query_returncode']==0
      and account['actual_terminal'] is True and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['UID']=='1264'
      and p['AllocCPUS']=='16' and p['Partition']=='cpu' and p['NodeList']==proof['node'] in Q.NODES
      and p['JobIDRaw']==str(proof['job_id'])==str(receipt['actual_runtime']['job_id'])
      and account['allocated_core_seconds_observed']==16*int(p['ElapsedRaw']) and proof['schema']==F.PROOF
      and proof['plan_reference']==receipt['plan_reference'],'ACTUAL_NEW_ALPHA_SOURCE3_C0_CHAIN')
    R.LEGACY.actual_raw(account['raw_sacct_reference'],p)
    return {'receipt_reference':receipt_ref,'accounting_reference':account_ref,'raw_reference':account['raw_sacct_reference'],
      'job_id':p['JobIDRaw'],'allocated_core_seconds':account['allocated_core_seconds_observed'],'endpoint':Q.ENDPOINT,'uid':1264}


def grants(reference):
    current=A.range_review(reference);info=current['manual_resource_epoch'];previous=A.range_review(info['predecessor_grant_reference'])
    Q.need(info['schema']=='EXPLICIT_MANUAL_PUBCHEM_RESOURCE_EPOCH_V1' and info['old_deadline_unix_seconds']==previous['deadline_unix_seconds']
      and re.fullmatch('[a-z][a-z0-9_]{0,40}',info['epoch_id']) and info['automatic_renewal'] is False,'OLD_GRANT_DEADLINE_IMMUTABLE')
    predecessor=own_state(info['predecessor_state_directory']);new=own_state(info['new_state_directory'])
    prior=previous.get('manual_resource_epoch');earlier=([prior['predecessor_state_directory'],*prior['earlier_state_directories']] if prior else [])
    Q.need(info['earlier_state_directories']==earlier and new not in [predecessor,*(own_state(p) for p in earlier)],'NEW_STATE_AND_COMPLETE_HISTORICAL_STATE_CHAIN')
    if prior:Q.need(str(predecessor)==prior['new_state_directory'],'PREDECESSOR_MANUAL_EPOCH_EXACT_STATE')
    else:Q.need(predecessor==OLD.STATE,'ORIGINAL_V4_STATE_NOT_AN_UNRELATED_DIRECTORY')
    P.finite_epoch(previous['deadline_unix_seconds'],current['authorized_unix_seconds'],current['deadline_unix_seconds'])
    expected=A.merge([*(prior['origin_grant_references'] if prior else []),info['predecessor_grant_reference']])
    Q.need(info['origin_grant_references']==expected,'EXACT_ALL_PREDECESSOR_GRANTS_NO_SELF_HASH_CYCLE')
    source_review(info['metadata_source_review_reference']);Q.need(info['metadata_source_references']==sources(),'NEW_METADATA_SOURCE_SET_SEPARATE_FROM_SCIENCE13')
    # The current grant is added here after it actually exists; it never embeds its own SHA.
    allowed=A.merge([*expected,reference]);roots={r['path']:A.range_review(r) for r in allowed}
    for item in roots.values():
        Q.need(item['source_references']==A.sources() and item['full_shard_manifest_reference']==current['full_shard_manifest_reference']
          and item['metadata_freeze_receipt_reference']==current['metadata_freeze_receipt_reference']
          and item['allowed_nodes']==list(R.S.NODES) and item['storage_scope_review_reference']['path']==str(R.SCOPE7),'SAME_FROZEN13_PARTITION_AND_STORAGE7')
        for ref in item['frozen_dependency_source_references']:Q.verify(ref)
        Q.authority(item['resource_authority_reference']['path']);Q.source_review(item['base_controller_review_reference']['path'])
    return current,roots

def inverse():
    from . import controller as N
    report=OLD.inverse()
    for name in ('close_new','account_row','materialize_one','actual_imports','data_locator','meta','pin','available_controller_lock'):
        Q.need(getattr(N,name) is getattr(R,name),'DIRECT_ORIGINAL_METADATA_VALIDATOR:'+name)
    Q.need(N.S is R.S and N.V is R.V and N.A is R.A,'ORIGINAL_SCHEDULING_STATE_QUEUE_AND_SCIENCE13_OBJECTS')
    Q.need(Q.read_small(QUEUE/'controller.py')==Q.read_small(Q.ROOT/'code/secondary_cpu_readonly_queue_v13/controller.py'),'QUEUE_FULL_BYTES_UNCHANGED')
    # New orchestration is explicitly new. Unchanged scientific validators and
    # exact old v4 inverse are retained, not mislabeled as an identical registry.
    funcs={name:ast.dump(ast.parse(__import__('inspect').getsource(getattr(N,name))),include_attributes=False)
      for name in ('registry','run','main')}
    return {'status':'EXACT_MANUAL_EPOCH_COORDINATION_SOURCE_PROOF','old_v4_inverse':report,'scientific13_inverse':A.source_inverse_proof(),
      'direct_original_methods':['close_new','account_row','materialize_one','actual_imports','data_locator','meta','pin','available_controller_lock'],
      'declared_new_coordination_groups':['multi_origin_registry','manual_cutover_and_finite_state','metadata_cli'],
      'new_registry_and_lifecycle_are_new_not_old_AST_identical':True,
      'new_coordination_AST_sha256':{k:__import__('hashlib').sha256(v.encode()).hexdigest() for k,v in funcs.items()},
      'numeric_science_or_once_source_changed':False,'controller13_source_set_unchanged':True,'global_monkeypatch':False}


def cutover_binding(pin,cut,root,pinref):
    info=root['manual_resource_epoch']
    Q.need(pin['schema']=='PINNED_OWN_PUBCHEM_CONTROLLER_IDENTITY_V1' and pin['uid']==1264
      and pin['predecessor_grant_reference']==info['predecessor_grant_reference'] and pin['state_directory']==info['predecessor_state_directory']
      and pin['old_deadline_unix_seconds']==info['old_deadline_unix_seconds'],'EXACT_PINNED_PREDECESSOR_GRANT_STATE_IDENTITY')
    Q.need(cut['schema']=='ACTUAL_PUBCHEM_MANUAL_EPOCH_CUTOVER_V1' and cut['predecessor_identity_reference']==pinref
      and cut['old_deadline_unix_seconds']==info['old_deadline_unix_seconds'] and cut['predecessor_state_directory']==info['predecessor_state_directory']
      and cut['pinned_old_identity_live'] is False and cut['old_exit_code']=='UNKNOWN' and cut['signals_sent'] is False
      and cut['global_lock_exclusively_held_during_capture'] is True and cut['observed_unix_seconds']>=info['old_deadline_unix_seconds'],
      'ACTUAL_CUTOVER_NOT_EXIT0_OR_BACKDATED_DEADLINE')
    Q.need(pin['state_binding_reference']==R.pin(own_state(pin['state_directory'])/'binding.json'),'IMMUTABLE_PREDECESSOR_BINDING')
    binding=value(pin['state_binding_reference']);Q.need(binding['root_range_review_reference']==info['predecessor_grant_reference']
      and binding['deadline_unix_seconds']==info['old_deadline_unix_seconds'],'ORIGINAL_BINDING_AND_FIXED_DEADLINE_RETAINED')
    Q.need(last_deadline_event(cut['stable_state_inventory'])==cut['last_deadline_event_reference']
      and [v['directory'] for v in cut['earlier_state_inventories']]==info['earlier_state_directories'],'LAST_REAL_DEADLINE_EVENT_AND_COMPLETE_PRIOR_STATE_CHAIN')


def require_review(reference):
    r=value(reference);Q.need(r['schema']==REVIEW and r['status']=='ROOT_APPROVED_MANUAL_EPOCH_CUTOVER' and r['reviewer']=='root'
      and r['endpoint']==Q.ENDPOINT and r['uid']==1264 and r['reason'].strip() and r['metadata_source_references']==sources()
      and r['no_automatic_retry_or_renewal_and_no_signals_or_cancel'] is True,'EXPLICIT_NEW_ROOT_EPOCH_REVIEW')
    source_review(r['source_review_reference']);actual=fixture_evidence(r['source3_receipt_reference'],r['source3_accounting_reference'])
    Q.need(actual==r['source3_actual_evidence'],'SOURCE3_EXACT_ACTUAL_EVIDENCE')
    root,roots=grants(r['new_grant_reference']);pin=value(r['predecessor_identity_reference']);cut=value(r['cutover_reference'])
    cutover_binding(pin,cut,root,r['predecessor_identity_reference'])
    info=root['manual_resource_epoch'];Q.need(r['new_state_directory']==info['new_state_directory'] and r['earlier_state_directories']==info['earlier_state_directories']
      and r['source_review_reference']==info['metadata_source_review_reference'],'SAME_NEW_STATE_SOURCE_AND_HISTORICAL_CHAIN')
    # Fresh liveness/global-lock/stability are checked by run before any state intent.
    adopted=value(r['adoption_reference']);Q.need(adopted['new_grant_reference']==r['new_grant_reference']
      and adopted['cutover_reference']==r['cutover_reference'],'EXACT_ACTUAL_ADOPTION_NOT_FUTURE_HASH')
    Q.need(type(r['explicit_old_held_admissions']) is list,'EXPLICIT_HELD_RESOURCE_ADOPTION_LIST')
    for item in r['explicit_old_held_admissions']:
        Q.need(set(item)=={'shard_index','job_id','queue_request_reference','submission_reference','origin_grant_reference'}
          and str(item['shard_index']) in adopted['registered_requests']
          and item['queue_request_reference']==adopted['registered_requests'][str(item['shard_index'])], 'EXACT_OLD_HELD_PARENT_NOT_A_NEW_SUBMISSION')
        Q.verify(item['queue_request_reference']);sub=value(item['submission_reference']);req=value(item['queue_request_reference'])
        plan=value(req['adapter']['input_reference']);Q.need(sub['job_id']==item['job_id'] and sub['queue_request_reference']==item['queue_request_reference']
          and plan['continuation_range_review_reference']==item['origin_grant_reference'] and item['origin_grant_reference']['path'] in roots,'ROOT_APPROVED_ORIGIN_HELD_BINDING')
    for reference in adopted['population_row_references'].values():value(reference)
    Q.verify(r['global_owned_cost_checkpoint_reference'])
    inverse();return r,root,roots,pin,cut

def candidate(a):
    Q.login();out=fresh(a.output)
    if a.mode=='source-template':
        Q.write_new(out,{'schema':SOURCE,'status':'ROOT_REVIEW_REQUIRED','reviewer':None,'reason':None,
          'metadata_source_references':sources(),'scientific_source13_references':A.sources(),'science_or_once_modified':False,'new_queue_algorithm':False});return
    if a.mode=='grant-candidate':
        oldref=Q.ref(a.predecessor_grant);old=A.range_review(oldref);now=time.time();P.finite_epoch(old['deadline_unix_seconds'],now,a.deadline)
        Q.need(now<a.deadline and re.fullmatch('[a-z][a-z0-9_]{0,40}',a.epoch_id),'EXPLICIT_FINITE_EPOCH_ID_DEADLINE')
        new=copy.deepcopy(old);new.update(status='ROOT_REVIEW_REQUIRED',reviewer=None,authorized_unix_seconds=now,deadline_unix_seconds=a.deadline,
          delegated_template_reason=None,Root_approval_or_submission_created=False)
        Q.need(not own_state(a.new_state).exists(),'NEW_MANUAL_EPOCH_STATE_MUST_BE_ABSENT')
        prior=old.get('manual_resource_epoch');origin_refs=[*(prior['origin_grant_references'] if prior else []),oldref]
        source_ref=Q.ref(a.source_review);source_review(source_ref)
        new['manual_resource_epoch']={'schema':'EXPLICIT_MANUAL_PUBCHEM_RESOURCE_EPOCH_V1','epoch_id':a.epoch_id,
          'predecessor_grant_reference':oldref,'old_deadline_unix_seconds':old['deadline_unix_seconds'],
          'predecessor_state_directory':str(own_state(a.predecessor_state)), 'new_state_directory':str(own_state(a.new_state)),
          'origin_grant_references':A.merge(origin_refs),'earlier_state_directories':([prior['predecessor_state_directory'],*prior['earlier_state_directories']] if prior else []),
          'metadata_source_review_reference':source_ref,'metadata_source_references':sources(),'automatic_renewal':False}
        Q.write_new(out,new);return
    if a.mode=='pin-predecessor':
        identity=process(a.pid);Q.need(identity is not None and identity['uid']==1264,'ACTUAL_RUNNING_OWN_PREDECESSOR_REQUIRED');argv=identity['argv']
        Q.need(argv.count('-m')==1 and argv[argv.index('-m')+1] in ('pubchem_c_metadata_recovery_v4.controller',MODULE),'FIXED_OWN_METADATA_CONTROLLER')
        if argv[argv.index('-m')+1]==MODULE:
            Q.need(argv.count('--epoch-review')==1,'EXACT_PRIOR_MANUAL_EPOCH_REVIEW_ARGV');previous=value(Q.ref(argv[argv.index('--epoch-review')+1]))
            Q.need(previous['new_grant_reference']==Q.ref(a.predecessor_grant) and previous['new_state_directory']==str(a.predecessor_state),'ACTUAL_PRIOR_MANUAL_EPOCH_GRANT_STATE')
        else:
            Q.need(argv.count('--root-range-review')==1 and argv[argv.index('--root-range-review')+1]==str(a.predecessor_grant)
              and argv.count('--state-directory')==1 and argv[argv.index('--state-directory')+1]==str(a.predecessor_state),'ACTUAL_PREDECESSOR_GRANT_AND_STATE')
        grant=Q.ref(a.predecessor_grant);root=A.range_review(grant)
        Q.write_new(out,{'schema':'PINNED_OWN_PUBCHEM_CONTROLLER_IDENTITY_V1',**identity,'predecessor_grant_reference':grant,
          'state_directory':str(own_state(a.predecessor_state)),'state_binding_reference':R.pin(own_state(a.predecessor_state)/'binding.json'),
          'old_deadline_unix_seconds':root['deadline_unix_seconds'],'launch_reference':Q.ref(a.predecessor_launch),'observed_unix_seconds':time.time()});return
    if a.mode=='capture-cutover':
        pinref=Q.ref(a.predecessor_identity);identity=value(pinref)
        if live(identity):print('WAIT_PREDECESSOR_LIVE_ZERO_INTENT');return
        fd=lock_global()
        if fd is None:print('WAIT_GLOBAL_OWNER_ZERO_INTENT');return
        try:
            Q.need(time.time()>=identity['old_deadline_unix_seconds'],'OLD_FIXED_DEADLINE_NOT_RENEWED_OR_SHORTENED')
            predecessor=A.range_review(identity['predecessor_grant_reference']);prior=predecessor.get('manual_resource_epoch')
            earlier=[prior['predecessor_state_directory'],*prior['earlier_state_directories']] if prior else []
            earlier_inventories=[state_inventory(p) for p in earlier]
            inv=state_inventory(identity['state_directory']);last=last_deadline_event(inv)
            Q.need(inv==state_inventory(identity['state_directory']) and all(v==state_inventory(v['directory']) for v in earlier_inventories)
              and not live(identity),'STABLE_OLD_STATE_UNDER_EXCLUSIVE_GLOBAL_LOCK')
            Q.write_new(out,{'schema':'ACTUAL_PUBCHEM_MANUAL_EPOCH_CUTOVER_V1','predecessor_identity_reference':pinref,
              'predecessor_state_directory':identity['state_directory'],'old_deadline_unix_seconds':identity['old_deadline_unix_seconds'],
              'pinned_old_identity_live':False,'old_exit_code':'UNKNOWN','current_reused_pid_observation':process(identity['pid']),
              'stable_state_inventory':inv,'earlier_state_inventories':earlier_inventories,'last_deadline_event_reference':last,'observed_unix_seconds':time.time(),
              'global_lock_exclusively_held_during_capture':True,'signals_sent':False})
        finally:os.close(fd)
        return
    if a.mode=='adoption-candidate':
        from . import controller as N
        grantref=Q.ref(a.new_grant);root,roots=grants(grantref);pinref=Q.ref(a.predecessor_identity);identity=value(pinref);cutref=Q.ref(a.cutover);cut=value(cutref)
        source_ref=Q.ref(a.source_review);source_review(source_ref);actual=fixture_evidence(Q.ref(a.source3_receipt),Q.ref(a.source3_accounting))
        fd=lock_global()
        if fd is None or live(identity):
            if fd is not None:os.close(fd)
            print('WAIT_PREDECESSOR_OR_GLOBAL_OWNER_ZERO_INTENT');return
        try:
            Q.need(time.time()>=cut['old_deadline_unix_seconds'] and cut['stable_state_inventory']==state_inventory(cut['predecessor_state_directory'])
              and all(v==state_inventory(v['directory']) for v in cut['earlier_state_inventories']), 'ACTUAL_STABLE_CUTOVER')
            cutover_binding(identity,cut,root,pinref)
            frozen,partition,initial,attempts,base=R.actual_imports(root,grantref)
            pop,fees,folders=N.registry(None,root,grantref,partition,initial,attempts,roots,[cut['predecessor_state_directory'],*root['manual_resource_epoch']['earlier_state_directories']],capture=True)
            entries=out.with_name(out.stem+'_adopted_entries');Q.need(not entries.exists(),'FRESH_PER_SHARD_SMALL_ADOPTION_ENTRIES');entries.mkdir(mode=0o700)
            row_refs={str(i):Q.write_new(entries/('shard_%04d.json'%i),row) for i,row in sorted(pop.items())}
            adopted={'new_grant_reference':grantref,'cutover_reference':cutref,'population_row_references':row_refs,
              'attempt_cost_rows':[{k:row[k] for k in ('job_id','actual_allocated_core_seconds','accounting_reference')} for row in fees.values()],
              'registered_requests':{str(i):R.pin(f/'request.json') for i,(f,q) in folders.items()},
              'scientific_body_reads':0,'old_state_modified':False,'pool_release_authorized':False}
            ar=Q.write_new(out.with_name(out.stem+'_adoption.json'),adopted)
            review={'schema':REVIEW,'status':'ROOT_REVIEW_REQUIRED','reviewer':None,'reason':None,'metadata_source_references':sources(),
              'source_review_reference':source_ref,'new_grant_reference':grantref,'predecessor_identity_reference':pinref,'cutover_reference':cutref,
              'source3_receipt_reference':actual['receipt_reference'],'source3_accounting_reference':actual['accounting_reference'],
              'source3_actual_evidence':actual,'adoption_reference':ar,'explicit_old_held_admissions':[],
              'endpoint':Q.ENDPOINT,'uid':1264,'earlier_state_directories':root['manual_resource_epoch']['earlier_state_directories'],
              'no_automatic_retry_or_renewal_and_no_signals_or_cancel':True,'global_owned_cost_checkpoint_reference':Q.ref(a.cost_checkpoint),
              'new_state_directory':root['manual_resource_epoch']['new_state_directory']}
            Q.write_new(out,review)
        finally:os.close(fd)
        return
    raise ValueError('EXPLICIT_METADATA_MODE_REQUIRED')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('source-template','grant-candidate','pin-predecessor','capture-cutover','adoption-candidate'))
    for name in ('output','predecessor-grant','predecessor-state','predecessor-launch','new-state','predecessor-identity','new-grant','cutover','source-review','source3-receipt','source3-accounting','cost-checkpoint'):
        p.add_argument('--'+name,type=Path)
    p.add_argument('--pid',type=int);p.add_argument('--epoch-id');p.add_argument('--deadline',type=float)
    candidate(p.parse_args())

if __name__=='__main__':main()
