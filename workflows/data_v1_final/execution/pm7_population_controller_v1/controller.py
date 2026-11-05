"""Finite Main-login metadata orchestration; actual Root range grant required."""
from __future__ import annotations
import argparse,csv,io,json,os,pathlib,re,stat,subprocess,sys,time
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO))
from workflows.data_v1_final.execution.pm7_population_controller_v1 import contract as C,derive as D
from workflows.data_v1_final.conformers.pm7_population_cache_v1 import metadata as M,contract as P
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import capacity_gate as CG
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import contract as A
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import own_directory,process_identity,verify_claims,verify_disjoint
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import PY,on_login,query,read_small
HELPER=C.RUN/'control/submit_one_queued_cpu_stage_20261026_v2.py'
HELPER_SHA='9aea8fe7ef8714b1dfa713e241f29a155a4e8b27d776c85948c58fcb7c676980'
FIRST_NAME='dv1_q_pm7_population5000_20261027_v1';FIRST_PHASE='pm7_population5000_20261027_v1'
FIRST_ACCOUNT=C.RUN/'control/accounting/pm7_population5000_4521775_v1.json'
FIRST_OUTPUT=P.BASE/'batch5000_000_v1';PREP=M.OLD/'prepared_v1/prepared.json'


def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def write(path,value):
    result=M.write(path,value);sync(path.parent);return result


def source_inventory():
    first=M.load(C.RUN/'control/requests'/(FIRST_NAME+'.json'))
    refs=[*first['source_references'],*[M.pin(C.HERE/n) for n in C.FILES],M.pin(CG.__file__),M.pin(HELPER)]
    central=REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2'
    refs.extend(M.pin(central/n) for n in ('shared.py','contract.py','registry.py','runtime.py','materialize.py','activate.py','observe.py','proof.py'))
    C.need(M.pin(HELPER)['sha256']==HELPER_SHA,'FROZEN_ROOT_CENTRAL_HELPER')
    refs=M.unique(refs)
    for r in refs:C.need(M.pin(r['path'])==r,'ACTUAL_SOURCE_OR_SMALL_METADATA_CHANGED')
    return refs


def review_inputs(root):
    prepared=M.load(PREP)
    return dict(schema='UNSIGNED_PM7_EXISTING247_RANGE_INPUT_LOCATORS_V1',approved=False,submitted=False,
        population_prepared_reference=M.pin(PREP),future_shards_reference=prepared['future_shards'],
        whole_molecule_roster_reference=prepared['whole_molecule_roster'],source_references=source_inventory(),state_root=str(root),
        first5000_accounting_reference=M.pin(FIRST_ACCOUNT),first5000_receipt_reference=M.pin(FIRST_OUTPUT/'receipt.json'),
        first5000_submission_reference=M.pin(C.RUN/'control/submissions'/(FIRST_NAME+'.json')),
        missing_authorities=['ACTUAL_SPRIME_ALL179_CLOSED_STATE','ACTUAL_CURRENT_PROVIDER_AND_ROOT_BASE_RESERVE_REVIEW',
            'ACTUAL_ROOT_RANGE_REVIEW_AND_FINAL_CPU_SOURCE_TEST_RECEIPT','ACTUAL_OWNED_MASTER_AND_PRIOR_COST_CLOSURES'],
        no_future_pins_created=True)


def accounting(reference,jid,allowed_nodes=None):
    allowed_nodes={'compute-0-13'} if allowed_nodes is None else set(allowed_nodes)
    v=M.actual(reference);raw=pathlib.Path(v['raw_sacct_reference']['path'])
    C.need(v['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and v['endpoint']=='202.38.247.57:22'
        and v['uid']==1278 and v['query_returncode']==0 and M.pin(raw)==v['raw_sacct_reference'],'ACTUAL_COMPLETE_PARENT_ACCOUNTING_AND_RAW')
    rows=[r for r in csv.DictReader(io.StringIO(raw.read_text()),delimiter='|') if r.get('JobIDRaw')==str(jid)]
    C.need(len(rows)==len(v['parents'])==1 and rows[0]['UID']=='1278','EXACT_MAIN_PARENT_ACCOUNTING')
    r=rows[0];p=v['parents'][0]
    expected=dict(job_id=str(jid),state=r['State'].split()[0],exit_code=r['ExitCode'],alloc_cpus=int(r['AllocCPUS']),
        elapsed_raw_seconds=int(r['ElapsedRaw']),node=r['NodeList'])
    C.need(p==expected and p['state'] in C.TERMINAL and 0<=p['alloc_cpus']<=16
        and p['node'] in allowed_nodes|{'','None assigned','None','(null)'}
        and v['allocated_core_seconds']==p['alloc_cpus']*p['elapsed_raw_seconds'],'ALL_REAL_ELAPSED_COST_NO_CEILING_SUBSTITUTION')
    if p['state']=='COMPLETED' and p['exit_code']=='0:0':C.need(p['alloc_cpus']==16 and p['node'] in allowed_nodes,'ACTUAL_C0_CPU16_AUTHORIZED_NODE')
    return p


def validate_review(path,root):
    ref=M.pin(path);v=M.actual(ref);prepared=M.load(PREP);shards_ref=prepared['future_shards'];rows=C.descriptors(M.actual(shards_ref))
    C.need(v['schema']==C.SCHEMA and v['status']==C.STATUS and v['reviewer']=='root' and v['root_reason']
        and v['endpoint']=='202.38.247.57:22' and v['uid']==1278 and v['state_root']==str(root)
        and v['source_references']==source_inventory(),'EXACT_ACTUAL_ROOT_RANGE_AND_SOURCE_APPROVAL')
    C.need(v['delegation_policy']==C.POLICY and v['derive_only_frozen_candidate_plan_quota_scope'] is True
        and v['per_job_human_review_claimed'] is False and v['known_scientific_pending_policy']=='COLLECT_ALL_STATES_NO_RELEASE'
        and v['automatic_retry'] is False and v['common_or_physical_ID_release'] is False,'NO_PROXY_ROOT_SCIENTIFIC_APPROVAL_OR_RETRY')
    pure=M.actual(v['pure_controller_cpu_test_reference'])
    C.need(pure['status']=='PASS' and pure['tests_run']==pure['expected']==6 and not pure['errors'] and not pure['failures']
        and all(M.pin(r['path'])==r for r in pure['source_references'])
        and all(M.pin(C.HERE/n) in pure['source_references'] for n in C.FILES if n.endswith('.py')),'ACTUAL_SIX_PURE_CONTROLLER_CPU_TESTS_AND_SOURCE_PINS_REQUIRED')
    pure_parent=accounting(pure['parent_accounting_reference'],pure['job_id'],{'compute-0-'+str(n) for n in A.NODES['analysis']})
    C.need(pure_parent['state']=='COMPLETED' and pure_parent['exit_code']=='0:0','PURE_CONTROLLER_FIXTURE_ACTUAL_C0_NOT_SELF_ATTESTATION')
    C.need(v['future_shards_reference']==shards_ref and v['population_prepared_reference']==M.pin(PREP)
        and v['whole_molecule_roster_reference']==prepared['whole_molecule_roster']
        and v['maximum_active_jobs']==2 and v['maximum_owned_pending_jobs']==2 and v['node']=='compute-0-13'
        and v['cpus']==16 and v['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and 1200<=v['wall_seconds']<=172800 and v['controller_output_cap_bytes']==C.CONTROL_CAP
        and v['runtime_PM7_pool_reserve_bytes']==C.POOL and v['reserved_slots_are_not_allocated_jobs'] is True
        and type(v['non_PM7_future_output_reserve_bytes']) is int and v['non_PM7_future_output_reserve_bytes']>=0,'EXACT247_TWO_SLOT_BOUNDED_RESOURCE_POLICY')
    C.need(re.fullmatch(r'pm7_full247_[a-z0-9_]+',v['phase_prefix']) is not None,'FIXED_OWN_RANGE_NAME_PREFIX')
    state=M.actual(v['Sprime_all179_closed_state_reference']);stages=state['stages']
    C.need(state['status']=='ALL179_INITIAL_BATCHES_CLOSED_NOT_GLOBAL_QUALITY_RELEASE'
        and set(stages)=={'batch-%05d'%n for n in range(1,180)},'ACTUAL_ALL179_SPRIME_CLOSED_BEFORE_PM7_RANGE')
    for record in stages.values():
        close=record['close'];counts=close['closure_counts']
        C.need(close['terminal'] is True and close['state']=='COMPLETED' and close['exit_code']=='0:0'
            and close['closure_errors_count']==close['consumed_elsewhere_count']==counts['execution_unresolved']==counts['unstarted_count']==0
            and counts['valid_packets']>0,'NO_PARTIAL_OR_UNKNOWN_SPRIME_RANGE_PRECONDITION')
    C.need(v['first5000_accounting_reference']==M.pin(FIRST_ACCOUNT)
        and accounting(v['first5000_accounting_reference'],'4521775')['state']=='COMPLETED'
        and v['first5000_receipt_reference']==M.pin(FIRST_OUTPUT/'receipt.json'),'ACTUAL5000_BENCHMARK_NOT_FORECAST')
    C.receipt(M.actual(v['first5000_receipt_reference']),rows['g01_s00000'])
    # Cost provenance is retained independently; it is not a 1.5x stop gate.
    C.need(v['prior_cost_accounting_references'] and v['root_owned_master_accounting_reference'],'ACTUAL_PRIOR_PARENT_COST_INVENTORY_REQUIRED')
    for item in [*v['prior_cost_accounting_references'],v['root_owned_master_accounting_reference']]:M.actual(item)
    quota,resources=M.resource(v['resource_template_review_reference']['path'])
    C.need(M.pin(v['resource_template_review_reference']['path'])==v['resource_template_review_reference']
        and quota['whole_wave_output_reserve_bytes']==v['non_PM7_future_output_reserve_bytes']+C.CAP
        and quota['provider_review_reference']==v['provider_review_reference']
        and quota['publisher_identity_reference']==v['publisher_identity_reference'],'ROOT_BASE_PLUS_TWO_SLOT_TEMPLATE_NO_SELF_RELEASE_OF_OTHER_RESERVES')
    provider=Q.load_review(v['provider_review_reference']);identity=Q.pinned(v['publisher_identity_reference'])
    C.need(identity['review_reference']==v['provider_review_reference'] and identity['publisher_output_dir']==provider['publisher_output_dir'],'EXACT_ACTUAL_FINITE_PROVIDER_NO_RENEWAL')
    return ref,v,rows,provider,identity


class Controller:
    def __init__(self,args,review_ref,review,rows,provider,identity):
        self.args=args;self.root=args.state_root;self.ref=review_ref;self.review=review;self.rows=rows;self.provider=provider;self.publisher=identity
        self.deadline=min(time.time()+args.max_seconds,identity['expires_unix_seconds']-300);self.sequence=0;self.provider_sequence=-1
        C.need(time.time()<self.deadline,'EXISTING_PROVIDER_HAS_NO_CONTROLLER_LEASE_NO_RENEWAL')
        self.launch=str(time.time_ns())+'_'+str(os.getpid());self.batches={};self.last_quota=None;self.registration_cache={}
        for n in ('launches','events','states','intents','commands','accounts','stages'):own_directory(self.root/n)
        self.launch_ref=write(self.root/'launches'/(self.launch+'.json'),dict(process_identity(os.getpid()),
            schema='ACTUAL_FINITE_PM7_METADATA_CONTROLLER_LAUNCH_V1',execution_argv=[PY,'-B',str(C.HERE/'controller.py'),*sys.argv[1:]],
            review_reference=self.ref,publisher_identity_reference=review['publisher_identity_reference'],deadline_unix_seconds=self.deadline,
            source_references=source_inventory(),endpoint='202.38.247.57:22',uid=1278,reason=args.reason,not_a_science_job=True))

    def event(self,kind,**fields):
        self.sequence+=1
        return write(self.root/'events'/(self.launch+'_%07d.json'%self.sequence),dict(kind=kind,unix_seconds=time.time(),launch_reference=self.launch_ref,**fields))

    def budget(self):
        C.need(time.time()<self.deadline,'FINITE_CONTROLLER_DEADLINE_NO_NEW_ACTION')
        latest=M.load(pathlib.Path(self.provider['publisher_output_dir'])/'latest.json')
        C.need(latest['schema']==Q.LATEST_SCHEMA and latest['review_reference']==self.review['provider_review_reference']
            and latest['identity_reference']==self.review['publisher_identity_reference'],'EXACT_FRESH_PROVIDER_POINTER')
        snapshot=latest['snapshot_reference'];p=pathlib.Path(snapshot['path'])
        C.need(p.parent==pathlib.Path(self.provider['publisher_output_dir']) and re.fullmatch(r'observation_[0-9]{6}\.json',p.name),'ONLY_OWN_PROVIDER_OBSERVATION')
        self.last_quota=dict(snapshot_reference=snapshot,publisher_identity_reference=latest['identity_reference'],validation_pending=True)
        value=Q.pinned(snapshot);self.last_quota.update(provider_status=value.get('status'),provider_error=value.get('error'),
            observed_unix_seconds=value.get('observed_unix_seconds'),validation_now_unix_seconds=time.time())
        parsed=Q.validate_observation(value,self.publisher,latest['identity_reference'],self.provider,latest['review_reference'],self.last_quota['validation_now_unix_seconds'])
        C.need(value['sequence']>=self.provider_sequence,'NO_PROVIDER_ROLLBACK');self.provider_sequence=value['sequence']
        base=self.review['non_PM7_future_output_reserve_bytes'];free=parsed['free_bytes']
        self.last_quota=dict(snapshot_reference=snapshot,free_bytes=free,non_PM7_future_reserved_bytes=base,
            conservative_PM7_two_slot_pool_bytes=C.POOL,actual_jobs_future_caps_bytes=C.future_bytes(self.batches),
            quota_already_includes_all_retired_files=True,publisher_cap_bytes=Q.CAP,controller_metadata_cap_bytes=C.CONTROL_CAP)
        C.need(free-base-C.POOL-Q.CAP-C.CONTROL_CAP>=200000000000,'CURRENT200GB_PLUS_ROOT_BASE_TWO_SLOTS_PROVIDER_CONTROLLER_REQUIRED')
        # Metadata tree only: no scientist output traversal on login.
        total=0
        for directory,dirs,files in os.walk(self.root,followlinks=False):
            for name in dirs+files:
                p=pathlib.Path(directory)/name;C.need(not p.is_symlink(),'OWN_CONTROLLER_NO_SYMLINKS')
            total+=sum((pathlib.Path(directory)/n).stat().st_size for n in files)
        C.need(total<C.CONTROL_CAP,'FINITE_CONTROLLER_METADATA_OUTPUT_CAP')

    def names(self,batch):
        phase=self.review['phase_prefix']+'_'+batch;return 'dv1_q_'+phase,phase

    def registration(self,batch):
        first=batch=='g01_s00000';name,phase=(FIRST_NAME,FIRST_PHASE) if first else self.names(batch)
        paths={k:C.RUN/'control'/sub/(name+'.json' if k in ('request','submission') else phase+'.json')
            for k,sub in (('request','requests'),('submission','submissions'),('registry','cpu_auto_memory_registries'),('activation','cpu_auto_memory_activations'))}
        intent=self.root/'intents'/(batch+'.json');any_actual=any(p.exists() for p in paths.values())
        if not any_actual:
            if intent.exists() or (self.root/'stages'/batch).exists():return {'ambiguous':True,'reason':'PREEXISTING_INTENT_OR_PARTIAL_STAGE_NO_AUTOMATIC_RESUBMISSION'}
            return {}
        if not all(p.exists() for p in paths.values()):return {'ambiguous':True,'reason':'PARTIAL_ACTUAL_REGISTRATION_NO_AUTOMATIC_ACTIVATION_OR_SUBMISSION'}
        frames=[]
        for path in paths.values():
            info=path.lstat();C.need(not path.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_ORDINARY_REGISTRATION_METADATA')
            frames.append((str(path),info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_uid))
        if batch in self.registration_cache:
            saved=self.registration_cache[batch]
            for path in saved['extra_paths']:
                info=path.lstat();C.need(not path.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_BOUND_IMMUTABLE_STAGE_METADATA')
                frames.append((str(path),info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_uid))
            C.need(saved['frames']==frames,'IMMUTABLE_REGISTERED_METADATA_FRAME_CHANGED')
            return dict(saved['row'])
        refs={k:M.pin(p) for k,p in paths.items()};request=M.actual(refs['request']);submission=M.actual(refs['submission'])
        A.validate_bound_request(request,read_small=read_small)
        A.validate_request(request,read_small=read_small,script_text=read_small(request['script_reference']['path']).decode())
        registry=M.actual(refs['registry']);activation=M.actual(refs['activation']);jid=str(submission['job_id'])
        verify_disjoint(paths['registry'],registry,new=False);verify_claims(paths['registry'],registry)
        C.need(submission['request_reference']==refs['request'] and submission['sbatch_returncode']==0 and submission['uid']==1278
            and submission['request']==request
            and registry['jobs'][0]['request_reference']==refs['request'] and registry['jobs'][0]['receipt_reference']==refs['submission']
            and len(registry['jobs'])==len(activation['releases'])==1 and registry['jobs'][0]['job_id']==activation['releases'][0]['job_id']==jid
            and activation['registry_reference']==refs['registry'],'EXACT_REAL_SUBMISSION_REGISTRATION_AND_ACTIVATION')
        selected=dict(file_group=self.rows[batch]['file_group'],shard_index=self.rows[batch]['shard_index'],offset=0,limit=self.rows[batch]['molecules'])
        C.need(request['job_name']==name and request['scope_key']==P.SCOPE and request['scope_parameters']==P.scope(selected)
            and request['cpus']==16 and request['node']=='compute-0-13' and request['kind']=='analysis' and request['pilot'] is False
            and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['stage_output_cap_bytes']==C.CAP,'EXACT_FROZEN_NATIVE_PM7_SCOPE')
        argv=request['execution_argv'];C.need(len(argv)==11 and argv[:3]==[PY,'-B',str(P.HERE/'run.py')]
            and argv[3::2]==['--plan','--root-preflight','--quota-reuse-review','--output']
            and argv[6]==request['startup_proof_path'],'EXACT_PRIMARY_FULL_OPTIONS_CHAIN')
        output=pathlib.Path(argv[-1]);plan_ref=M.pin(argv[4]);plan=M.actual(plan_ref)
        C.need(plan['selection']==selected and plan['whole_molecule_roster']==self.review['whole_molecule_roster_reference']
            and plan['future_shards_reference']==self.review['future_shards_reference'],'EXACT_ORIGINAL_ROSTER_AUTHORITY')
        if first:
            C.need(jid=='4521775' and output==FIRST_OUTPUT and refs['submission']==self.review['first5000_submission_reference']
                and M.pin(FIRST_OUTPUT/'receipt.json')==self.review['first5000_receipt_reference'],'FIRST5000_REAL_ADOPTION_NEVER_RECOMPUTE')
        else:
            C.need(intent.exists(),'NO_UNREVIEWED_EXTERNAL_RANGE_JOB_ADOPTION');expected=M.load(intent)
            C.need(refs['request']['path']==expected['expected_request_path'] and output==pathlib.Path(expected['output'])
                and M.pin(expected['stage_spec_reference']['path'])==expected['stage_spec_reference'],'EXACT_DURABLE_INTENT_STAGE')
            spec=M.actual(expected['stage_spec_reference']);expected_argv=list(spec['execution_argv']);expected_argv[6]=request['startup_proof_path']
            C.need(argv==expected_argv and request['root_review']['stage_spec_reference']==expected['stage_spec_reference']
                and all(r in request['source_references'] for r in spec['source_references'])
                and request['data_references']==spec['data_references'],'IMMUTABLE_GENERATED_STAGE_FULL_CHAIN')
        observer=C.RUN/'control/cpu_auto_memory_observers'/phase
        identity_ref=M.pin(observer/'identity.json');identity=M.actual(identity_ref)
        C.need(activation['observer_identity_reference']==identity_ref and identity['registry_reference']==refs['registry'],'ORIGINAL_REGISTERED_OBSERVER_IDENTITY')
        row=dict(job_id=jid,job_name=name,phase=phase,actual_registered_references=refs,output=str(output),observer=str(observer),
            plan_reference=plan_ref,retired=False)
        extra_paths=[pathlib.Path(plan_ref['path']),pathlib.Path(identity_ref['path']),pathlib.Path(request['root_review']['stage_spec_reference']['path']),
            pathlib.Path(request['scope']['review']['path'])]
        if not first:extra_paths.append(intent)
        for path in extra_paths:
            info=path.lstat();C.need(not path.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_BOUND_IMMUTABLE_STAGE_METADATA')
            frames.append((str(path),info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_uid))
        self.registration_cache[batch]={'frames':frames,'extra_paths':extra_paths,'row':row};return dict(row)

    def observe(self):
        rows={};self.batches=rows
        for k in self.rows:rows[k]=self.registration(k)
        ids=[r['job_id'] for r in rows.values() if r.get('job_id')]
        C.need(len(ids)==len(set(ids)),'NO_PARENT_REUSED_ACROSS_SHARDS')
        if not ids:return rows
        argv=['sacct','-j',','.join(ids),'--parsable2','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,UID'];raw=query(argv)
        parents=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|') if r.get('JobIDRaw','').isdecimal()]
        C.need(len(parents)==len({r['JobIDRaw'] for r in parents}) and {r['JobIDRaw'] for r in parents}==set(ids),'EXACT_DISTINCT_QUERIED_PARENT_ROWS')
        observed={r['JobIDRaw']:r for r in parents}
        C.need(set(observed)==set(ids),'ACTUAL_REGISTERED_PARENTS_MUST_ALL_BE_VISIBLE')
        for batch,row in rows.items():
            if not row.get('job_id'):continue
            jid=row['job_id'];p=observed[jid];C.need(p['UID']=='1278','OWN_ACTUAL_MAIN_PARENT_ONLY');row.update(state=p['State'].split()[0],exit_code=p['ExitCode'])
            if row['state'] not in C.TERMINAL:continue
            parent=dict(job_id=jid,state=row['state'],exit_code=row['exit_code'],alloc_cpus=int(p['AllocCPUS']),elapsed_raw_seconds=int(p['ElapsedRaw']),node=p['NodeList'])
            # A later Slurm terminal observation can include additional cleanup
            # elapsed. Retain every distinct observation; never overwrite it.
            directory=self.root/'accounts'/batch;own_directory(directory);signature=C.digest(parent)
            account=directory/('accounting_'+signature+'.json')
            if not account.exists():
                raw_path=directory/('sacct_'+signature+'.txt')
                if raw_path.exists():C.need(raw_path.read_text()==raw,'PARTIAL_ACCOUNT_RAW_CHANGED_NO_OVERWRITE')
                else:
                    with raw_path.open('x') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                write(account,dict(schema='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1',status='ACTUAL_PARENT_ACCOUNTING_CLOSED',endpoint='202.38.247.57:22',uid=1278,
                    query_returncode=0,query_argv=argv,raw_sacct_reference=M.pin(raw_path),parents=[parent],allocated_core_seconds=parent['alloc_cpus']*parent['elapsed_raw_seconds'],
                    failed_timeout_startup_cleanup_elapsed_retained=True))
            row['accounting_reference']=M.pin(account);parent=accounting(row['accounting_reference'],jid)
            if parent['state']!='COMPLETED' or parent['exit_code']!='0:0':row.update(failed=True,reason='ACTUAL_TERMINAL_PARENT_NOT_C0_NO_AUTO_RETRY');continue
            receipt_ref=M.pin(pathlib.Path(row['output'])/'receipt.json');receipt=M.actual(receipt_ref);C.receipt(receipt,self.rows[batch])
            C.need(receipt['job_id']==jid and receipt['plan_reference']==row['plan_reference'],'ACTUAL_RECEIPT_PRODUCER')
            fixtures=M.actual(receipt['fixtures_reference']);C.need(fixtures['status']=='PASS' and fixtures['tests_run']==fixtures['expected']==17
                and not fixtures['errors'] and not fixtures['failures'] and not fixtures['skipped'] and fixtures['before_all_scientific_bodies'] is True,'ORIGINAL17_FIXTURES_BEFORE_BODY')
            closure_path=pathlib.Path(row['observer'])/'closure.json';closure=M.load(closure_path) if closure_path.exists() else None
            row.update(receipt_reference=receipt_ref,retired=C.retired(parent,closure,jid),logical_bytes='UNKNOWN_PENDING_CPU_INVENTORY',allocated_bytes='UNKNOWN_PENDING_CPU_INVENTORY',
                charged_bytes_is_not_physical_inventory=receipt['charged_bytes'],geometry_complete_molecules=receipt['geometry_complete_molecules'],
                geometry_pending_or_unresolved_molecules=receipt['geometry_pending_or_unresolved_molecules'],geometry_status_counts=receipt['geometry_status_counts'],
                hof_valid_records=receipt['selected_HOF_reader_valid_records'],hof_missing_reason_counts=receipt['selected_HOF_reader_missing_reason_counts'],
                hof_NULL_review_records=receipt['selected_HOF_NULL_convergence_review_records'])
            if closure is not None:
                row['observer_closure_reference']=M.pin(closure_path)
                C.need(row['retired'],'ORIGINAL_OBSERVER_LEASE_OR_TERMINAL_MISMATCH_REQUIRES_ROOT_NO_REDISPATCH')
        C.need(sum(r.get('state')=='PENDING' for r in rows.values())<=self.review['maximum_owned_pending_jobs'],'OWN_RANGE_PENDING_LIMIT_NO_TOUCH_OTHER_JOBS')
        return rows

    def dispatch(self,batch):
        def transition(fd):
            self.budget();C.need(C.capacity(self.batches),'AT_MOST_TWO_UNRETIRED_PARENTS')
            C.need(C.lease_allows(time.time(),self.publisher['expires_unix_seconds'],self.review['wall_seconds']),'NO_ADMISSION_WITHOUT_FULL_ALLOCATION_ENVELOPE_LEASE')
            C.need(not self.registration(batch),'EXISTING_STAGE_OR_REGISTRATION_NO_RESUBMIT')
            spec,output,stamp=D.build(self.root,batch,self.rows[batch],self.review,self.ref,self.launch_ref,self.review['wall_seconds'])
            name,phase=self.names(batch);intent=self.root/'intents'/(batch+'.json')
            write(intent,dict(schema='PM7_RANGE_SUBMISSION_INTENT_NO_REISSUE_V1',batch_id=batch,stage_spec_reference=spec,output=output,
                expected_request_path=str(C.RUN/'control/requests'/(name+'.json')),launch_reference=self.launch_ref,delegation=stamp))
            argv=[PY,'-B',str(HELPER),'--spec',spec['path'],'--node','compute-0-13','--name',name,'--phase',phase]
            log=self.root/'commands'/(batch+'.stdout.txt');err=self.root/'commands'/(batch+'.stderr.txt')
            with log.open('xb') as out,err.open('xb') as error:
                child=subprocess.Popen(argv,stdout=out,stderr=error,pass_fds=(fd,))
                try:actual_identity=process_identity(child.pid)
                except (OSError,ValueError) as exc:actual_identity={'pid':child.pid,'unavailable_after_actual_Popen':repr(exc),'identity_not_fabricated':True}
                self.event('ACTUAL_METADATA_HELPER_LAUNCHED',batch_id=batch,pid=child.pid,argv=argv,actual_identity=actual_identity,outer_fd_inherited=True)
                until=min(self.deadline,time.time()+600)
                while child.poll() is None and time.time()<until:time.sleep(min(1,max(0,until-time.time())))
                C.need(child.poll() is not None,'UNRESOLVED_HELPER_RETAINS_OUTER_FD_ROOT_REVIEW_NO_SIGNALS')
                C.need(child.returncode==0,'CENTRAL_HELPER_FAILED_NO_AUTOMATIC_REISSUE:'+str(child.returncode))
            result=self.registration(batch);C.need(result.get('job_id') and not result.get('ambiguous'),'ACTUAL_COMPLETE_REGISTRATION_AFTER_HELPER')
            self.event('REGISTERED_NEW_DISJOINT_SHARD',batch_id=batch,job_id=result['job_id'],stage_spec_reference=spec)
        return CG.guarded_transition(lambda:query(['scontrol','show','node','compute-0-13','--oneliner']),transition,
            lambda:CG.serialization_lock(C.RUN/'control'/CG.LOCK_NAME))

    def snapshot(self,status,reason=None):
        values=dict(schema='FINITE_PM7_EXISTING247_CONTROLLER_STATE_V1',status=status,reason=reason,review_reference=self.ref,
            launch_reference=self.launch_ref,unix_seconds=time.time(),deadline_unix_seconds=self.deadline,batches=self.batches,
            future_writer_cap_bytes=C.future_bytes(self.batches),conservative_runtime_pool_reserve_bytes=C.POOL,last_quota=self.last_quota,
            source_molecules=1220466,source_records=11231854,retired_shards=sum(bool(r.get('retired')) for r in self.batches.values()),
            allocated_core_seconds_distinct_this247=sum(M.actual(r['accounting_reference'])['allocated_core_seconds'] for r in self.batches.values() if r.get('accounting_reference')),
            prior_cost_accounting_references=self.review['prior_cost_accounting_references'],root_owned_master_accounting_reference=self.review['root_owned_master_accounting_reference'],
            prefix_logical_bytes='UNKNOWN_PENDING_CPU_INVENTORY',prefix_allocated_bytes='UNKNOWN_PENDING_CPU_INVENTORY',
            common=False,full_cache_release=False,physical_ID_release=False,automatic_retry=False,science_or_other_jobs_signalled=False)
        reference=write(self.root/'states'/(self.launch+'_%07d.json'%self.sequence),values);self.sequence+=1
        pending=self.root/('latest_'+self.launch+'_'+str(self.sequence)+'.json');write(pending,{'state_reference':reference});os.replace(pending,self.root/'latest.json');sync(self.root)
        return reference

    def run(self):
        while time.time()<self.deadline:
            try:
                self.budget();self.batches=self.observe();decision=C.next_action(self.batches,self.rows)
                if decision['action']=='HOLD':self.snapshot('HOLD_ROOT_REVIEW_NO_NEW_DISPATCH',decision);return 3
                if decision['action']=='ALL_RETIRED_PENDING_CPU_INVENTORY':self.snapshot('ALL247_RETIRED_PENDING_CPU_INVENTORY_AND_ROOT_REVIEW');return 0
                self.snapshot('OBSERVED_FINITE_RANGE',decision)
                if decision['action']=='DISPATCH' and not self.args.observe_only:
                    result=self.dispatch(decision['batch_id']);self.event('CAPACITY_OR_TRANSITION_RESULT',result=result)
                if self.args.single_cycle:return 0
                time.sleep(min(15,max(0,self.deadline-time.time())))
            except Exception as exc:
                self.snapshot('HOLD_ROOT_REVIEW_NO_NEW_DISPATCH',repr(exc));return 3
        self.snapshot('FINITE_LEASE_ENDED_NO_RENEWAL_OR_SIGNALS');return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root-range-review',type=pathlib.Path)
    parser.add_argument('--state-root',required=True,type=pathlib.Path);parser.add_argument('--root-run-reviewed-pm7',action='store_true')
    parser.add_argument('--reason');parser.add_argument('--max-seconds',type=int,default=3600);parser.add_argument('--print-review-inputs',action='store_true')
    parser.add_argument('--single-cycle',action='store_true');parser.add_argument('--observe-only',action='store_true');parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();on_login()
    C.need(REPO==C.REPO and C.HERE==C.REPO/'workflows/data_v1_final/execution/pm7_population_controller_v1'
        and C.BASE in args.state_root.parents and '..' not in args.state_root.parts
        and process_identity(os.getpid())['argv']==[PY,'-B',str(C.HERE/'controller.py'),*sys.argv[1:]],'EXACT_MAIN_LOGIN_PRIMARY_FULL_ARGV_OWN_ROOT')
    if args.print_review_inputs:print(json.dumps(review_inputs(args.state_root)));return 0
    C.need(args.root_range_review and args.root_run_reviewed_pm7 and args.reason and args.reason.strip() and 1<=args.max_seconds<=86400,'EXPLICIT_FINITE_ROOT_LAUNCH')
    own_directory(args.state_root);ref,review,rows,provider,identity=validate_review(args.root_range_review,args.state_root)
    with CG.serialization_lock(args.state_root/'own_instance.lock'):
        latest=args.state_root/'latest.json'
        if latest.exists():
            previous_ref=M.load(latest)['state_reference'];previous=M.actual(previous_ref)
            C.need(args.resume and previous['schema']=='FINITE_PM7_EXISTING247_CONTROLLER_STATE_V1'
                and review.get('resume_from_state_reference')==previous_ref,'ROOT_EXACT_PRIOR_STATE_REQUIRED_FOR_RESUME')
        else:C.need(not args.resume,'NO_FABRICATED_PRIOR_STATE')
        return Controller(args,ref,review,rows,provider,identity).run()


if __name__=='__main__':sys.exit(main())
