"""Generate one exact Root-reviewed Sprime wave2 metadata stage; never submit."""
from __future__ import annotations
import argparse,csv,io,json,pathlib,sys,time
REPO_PATH=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO_PATH));sys.dont_write_bytecode=True
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,PY,on_login,pin,load,write_new,read_small
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C

HERE=pathlib.Path(__file__).absolute().parent
FILES=('__init__.py','generate.py','README.md')
FORMAL=REPO/'workflows/data_v1_final/conformers/formal_cpu_auto_v3'
MAPPED=FORMAL.parent/'formal_cpu_auto_prepare_mapping_v1'
CLOSER=FORMAL.parent/'formal_cpu_auto_close_index_v1'
CONFIG=REPO/'configs/data_v1/conformers/formal_cpu_auto_v3.json'
DRAFT=ROOT/'artifacts/conformers/formal_cpu_auto_v3/draft_v1/draft.json'
TEMPLATE=ROOT/'control/sprime_v3_wave1_prepare_mapping_stage_v1/stage_spec.json'
MAPPING=ROOT/'control/sprime_v3_node13_canonical_source_mount_root_review_v1.json'
OLD_QUOTA=ROOT/'control/sprime_v3_main_quota_reuse_root_review_v1.json'
WAVE1_CLOSED=C.BASE/'wave1/batch-00000/closed_v1/closed_batch.json'
WAVE1_CLOSE_NAME='dv1_q_sprime_v3_wave1_close_20261027_v1'
WAVE2=C.BASE/'wave2'
BATCHES=tuple('batch-%05d'%i for i in range(1,180))
WALL=8*3600;MAX_CONCURRENT=2;SCIENCE_RESERVE=len(BATCHES)*C.CAP;WAVE_RESERVE=(len(BATCHES)+3)*C.CAP
CEILING=len(BATCHES)*16*WALL
PROOF_PLACEHOLDER='__ROOT_STARTUP_PROOF__'


def is_data(path):
    path=pathlib.Path(path);name=path.name.lower();text=str(path)
    return (path.suffix.lower() in {'.parquet','.jsonl','.gz','.lmdb','.mdb','.sqlite','.sqlite3'}
        or name.startswith(('terminal_outcomes','all_consumed_outcomes'))
        or name in {'pilot_consumed_imports.json','enough_controls16.json','task.json','tasks.json','base.json','baseline.json'}
        or any(part in path.parts for part in ('packets','task_shards','tasks','bases','baselines','baseline_packets','baseline_evidence'))
        or '/reproduction/' in text)


def meta_pin(path):
    path=pathlib.Path(path)
    C.need(path.is_absolute() and '..' not in path.parts and not is_data(path),'SCIENTIFIC_DATA_CANNOT_BE_LOGIN_PINNED_OR_PARSED:'+str(path))
    return pin(path)


def metadata(path,schema=None):
    reference=meta_pin(path);value=load(path)
    if schema is not None:C.need(value.get('schema')==schema,'EXACT_SMALL_METADATA_SCHEMA_REQUIRED:'+str(path))
    return reference,value


class References:
    def __init__(self,template):
        self.sources={};self.data={}
        for value in template['source_references']:self.add(value,data=is_data(value['path']))
        for value in template['data_references']:self.add(value,data=True)

    def add(self,value,*,data=False):
        value=C.triple(value);path=value['path'];target=self.data if data or is_data(path) else self.sources
        other=self.sources if target is self.data else self.data
        C.need(path not in target or target[path]==value,'CONFLICTING_INPUT_SHA_TRIPLES')
        if path in other:
            C.need(other[path]==value,'CONFLICTING_SOURCE_DATA_SHA_TRIPLES')
            # Scientific DATA classification wins, including a historical tiny
            # terminal-outcomes JSON incorrectly placed among template sources.
            if target is self.data:other.pop(path)
            else:return
        target[path]=value

    def small(self,path):
        reference=meta_pin(path);self.add(reference);return reference

    def validate_small_sources(self):
        for reference in self.sources.values():C.need(meta_pin(reference['path'])==reference,'ACTUAL_SMALL_SOURCE_PIN_CHANGED')
        C.need(not(set(self.sources)&set(self.data)) and all(not is_data(p) for p in self.sources),'SOURCE_DATA_SETS_DISJOINT')


def account(path,required=(),*,c0=()):
    C.need(ROOT/'control' in pathlib.Path(path).parents,'ONLY_EXISTING_ROOT_CONTROL_ACCOUNTING_METADATA')
    reference,value=metadata(path,'DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1')
    C.need(value.get('endpoint')=='202.38.247.57:22' and value.get('uid')==1278,'ONLY_ACTUAL_MAIN_UID1278_ACCOUNTING')
    meta_pin(value['raw_sacct_reference']['path']);parents=C.accounting(reference,required)
    for row in csv.DictReader(io.StringIO(read_small(value['raw_sacct_reference']['path']).decode()),delimiter='|'):
        if row.get('JobIDRaw',row.get('JobID','')).isdecimal() and row.get('UID'):
            C.need(row['UID']=='1278','FOREIGN_PARENT_ACCOUNTING_CANNOT_BECOME_MAIN_EVIDENCE')
    for jid in map(str,c0):
        row=parents[jid];C.need(row['state']=='COMPLETED' and row['exit_code']=='0:0' and int(row['alloc_cpus'])==16,
            'PREVIOUS_CPU_STAGE_MUST_HAVE_ACTUAL_C0_NOT_A_PLANNED_RESULT')
    return reference,value,parents


def add_account(refs,reference,value):
    refs.add(reference);refs.add(value['raw_sacct_reference'])


def original_sources(refs):
    for name in ('__init__.py','contract.py','runtime_io.py','plan.py','prepare_batch.py','run_batch.py','finalize.py',
            'identity.py','close_index.py','test_contract.py','README.md','frozen_sources.json','root_review_schemas.json'):
        refs.small(FORMAL/name)
    for name in ('__init__.py','mapping.py','prepare_batch.py'):refs.small(MAPPED/name)
    for name in ('__init__.py','run.py'):refs.small(CLOSER/name)
    for name in FILES:refs.small(HERE/name)
    for reference in C.sources().values():refs.add(reference)


def common_inputs(args):
    C.need(args.root_approve_exact_stage and args.root_reason.strip(),'EXPLICIT_ROOT_STAGE_DECISION_AND_REASON_REQUIRED')
    config_ref,value=metadata(CONFIG,'DATA_V1_SPRIME_FORMAL_CPU_AUTO_V3');C.config(config_ref)
    template_ref,template=metadata(TEMPLATE,'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1');refs=References(template)
    refs.add(template_ref);refs.add(config_ref);original_sources(refs)
    pilot_ref=refs.small(ROOT/'control/sprime_v3_censored_pilot_root_review_v1.json');pilot=load(pilot_ref['path'])
    # Only the locators are moved; never parse the pilot task/outcome bodies.
    for name in ('pilot_tasks','terminal_outcomes'):refs.add(pilot[name],data=True)
    mapping_ref,mapping=metadata(MAPPING,'ROOT_SPRIME_NODE13_SOURCE_MOUNT_MAPPING_V1');refs.add(mapping_ref)
    for name in ('formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review'):
        reference=mapping[name];C.need(meta_pin(reference['path'])==reference,'ACTUAL_MAPPING_SOURCE_EVIDENCE_CHANGED');refs.add(reference)
    C.need(value['wall_seconds']==WALL and value['max_molecules_per_batch']==500 and value['max_output_bytes']==8<<30,
        'EXACT_ORIGINAL8H500MOLECULE8GIB_CONFIGURATION_REQUIRED')
    return config_ref,value,refs,pilot_ref,mapping_ref


def approve_resource(refs,out,args):
    previous_ref,previous=metadata(OLD_QUOTA,'SPRIME_MAIN_ACCOUNT_QUOTA_REUSE_ROOT_REVIEW_V3')
    C.need(previous['reviewer']=='root' and previous['scientific_authority_is_separate'] is True
        and previous['N1_population_authority_is_not_Sprime_authority'] is True,'EXISTING_RESOURCE_FACTS_ONLY')
    launch_ref=previous['provider_actual_launch_reference'];C.need(meta_pin(launch_ref['path'])==launch_ref,'REAL_FINITE_PUBLISHER_LAUNCH_REFERENCE')
    launch=load(launch_ref['path']);provider_review_ref=previous['provider_review_reference'];provider_review=load(provider_review_ref['path'])
    identity_ref,identity=metadata(pathlib.Path(provider_review['publisher_output_dir'])/'identity.json','MAIN_LOGIN_ACCOUNT_QUOTA_PUBLISHER_IDENTITY_V1')
    C.need(identity['review_reference']==provider_review_ref and identity['uid']==launch['uid']==1278
        and identity['endpoint']==launch['endpoint']=='202.38.247.57:22' and identity['pid']==launch['actual_pid']
        and identity['start_ticks']==launch['actual_start_ticks'] and identity['boot_id']==launch['actual_boot_id']
        and identity['execution_argv']==launch['actual_argv'],'ACTUAL_ORIGINAL_FINITE_PUBLISHER_IDENTITY_BINDING')
    expires=identity['expires_unix_seconds']
    C.need(time.time()<expires,'EXISTING_QUOTA_PROVIDER_LEASE_EXPIRED_NO_AUTOMATIC_RENEWAL')
    review=dict(previous,whole_wave_output_reserve_bytes=WAVE_RESERVE,
        previous_resource_review_reference=previous_ref,root_decision_reason=args.root_reason,
        scientific_slot_output_reserve_bytes=SCIENCE_RESERVE,auxiliary_slot_output_reserve_bytes=3*C.CAP,
        publisher_identity_reference=identity_ref,publisher_actual_expiry_unix_seconds=expires,publisher_started_or_renewed_by_generator=False,
        fresh_CPU_provider_observation_still_required=True,
        root_review_notes='New output reservation only:179 science caps plus3 auxiliary caps; not memory. Existing node13 map/provider/source/launch facts unchanged. Fresh CPU quota minus entire wave reserve, provider reserve and200GB headroom required at every stage; stale/expired provider STOP and natural drain. No quota promise or publisher renewal.')
    reference=write_new(out/'quota_reuse_review.json',review);refs.add(reference);refs.add(previous_ref);refs.add(launch_ref);refs.add(identity_ref)
    return reference


def exact_stage(out,refs,stage,config_ref,pilot_ref,argv,wall,parents,args):
    kind='conformer' if stage=='run' else 'analysis';mode='FULL_SOURCE_AFTER_PROFILE' if stage=='run' else 'BOUNDED_METADATA_PREPARATION'
    authority=C.sources()['resource_authority'];cost=C.sources()['cost_authority']
    parents=list({r['path']:C.triple(r) for r in [*parents,cost]}.values())
    for reference in parents:refs.add(reference)
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
        'resource_authority_reference':authority,'kind':kind,'scope_key':'sprime_formal_cpu_auto_v3_'+stage,
        'scope_parameters':C.scope(stage,config_ref),'pilot':False,'wall_seconds':wall,'estimated_peak_output_bytes':C.CAP,
        'stage_output_cap_bytes':C.CAP,'execution_argv':argv,'scope_mode':mode,'parent_evidence_references':parents,
        'root_review_reason':args.root_reason,
        'generator_source_references':[meta_pin(HERE/name) for name in FILES],
        'scientific_quality_thresholds_unchanged':True,'full_forecast_status':C.FORECAST,'estimated_full_core_hours':None,
        'no_scientific_data_read_or_hashed_on_login':True,'provider_launched_or_renewed':False,'automatic_retry':False,
        'requested_science_ceiling_core_hours':CEILING//3600,'request_ceiling_is_not_forecast_or_actual_cost_guarantee':True}
    if stage=='run':review.update(profile_reviewed=True,approved_profile_reference=pilot_ref)
    review_ref=write_new(out/'scope_review.json',review);refs.add(review_ref);refs.validate_small_sources()
    spec={k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv')}
    spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
        source_references=list(refs.sources.values()),data_references=list(refs.data.values()),
        scope={'mode':mode,'review':review_ref,'parent_profile':pilot_ref if stage=='run' else None})
    reference=write_new(out/'stage_spec.json',spec)
    print(json.dumps({'stage_spec':reference,'stage':stage,'source_count':len(refs.sources),'data_count':len(refs.data),
        'submitted_jobs':0,'scientific_bodies_read':False,'provider_started_or_renewed':False},sort_keys=True))


def freeze(args,out,config_ref,value,refs,pilot_ref,mapping_ref):
    C.need(args.root_approve_wave2 and args.root_observed_wave1_successes==500,'ROOT_EXPLICIT_FINITE179_WAVE_AND_ACTUAL500SUCCESS_REVIEW_REQUIRED')
    draft_ref,draft=metadata(DRAFT,C.SCHEMAS['draft']);closed_ref,closed=metadata(WAVE1_CLOSED,'SPRIME_FORMAL_CPU_CLOSED_BATCH_V3')
    C.need(draft['status']=='DRAFT_NOT_AUTHORITY_TO_RUN' and draft['config']==config_ref and draft['runtime']['job_id']=='4521457'
        and draft['unstarted_planned_molecules']==89749 and len(draft['batches'])==180
        and draft['original_deficit_molecules']==99351 and draft['unsupported_molecules']==9282 and draft['non_unsupported_deficits']==90069
        and draft['historical_consumed_deficit_molecules']==320 and draft['kernel_sha256']==C.KERNEL_SHA
        and draft['full_forecast_status']==C.FORECAST and draft['estimated_full_core_hours'] is None,'ORIGINAL_ACTUAL180_BATCH_DRAFT_REQUIRED')
    by_id={b['batch_id']:b for b in draft['batches']}
    C.need(len(by_id)==180 and set(by_id)=={'batch-%05d'%i for i in range(180)}
        and by_id['batch-00000']['molecules']==500 and sum(by_id[k]['molecules'] for k in BATCHES)==89249
        and all(by_id[k]['molecules']==500 for k in BATCHES[:-1]) and by_id[BATCHES[-1]]['molecules']==249,
        'EXACT179_REMAINING_DISJOINT_DRAFT_SLOTS_LAST249_NO_TASK_BODY_READ')
    C.need(closed['status']=='ACTUAL_TERMINAL_BATCH_CLASSIFIED' and closed['batch_id']=='batch-00000'
        and closed['actual_parent_job_id']=='4521475' and closed['valid_packets']==closed['consumed_outcomes']==500
        and closed['execution_unresolved']==closed['unstarted_count']==0 and not(closed['errors'] or closed['consumed_elsewhere']),
        'ACTUAL_INDEPENDENT500_CLOSURE_REQUIRED_NOT_PRODUCER_C0_ALONE')
    close_req_ref,close_req=metadata(ROOT/'control/requests'/(WAVE1_CLOSE_NAME+'.json'))
    close_sub_ref,close_sub=metadata(ROOT/'control/submissions'/(WAVE1_CLOSE_NAME+'.json'),'CPU_AUTO_MEMORY_SUBMISSION_V1')
    C.need(close_sub['job_id']=='4521477' and close_sub['sbatch_returncode']==0 and close_sub['request']==close_req
        and close_sub['uid']==1278
        and close_sub['request_reference']==close_req_ref and close_req['execution_argv'][:4]==[PY,'-B',str(CLOSER/'run.py'),'close']
        and close_req['execution_argv'][-2:]==['--output',str(WAVE1_CLOSED.parent)],'REAL_INDEPENDENT_CLOSER1477_REGISTRATION_AND_OUTPUT_REQUIRED')
    close_descriptor_path=ROOT/'control/sprime_v3_wave1_close_stage_v1/descriptor.json'
    expected_close=[PY,'-B',str(CLOSER/'run.py'),'close','--config',str(CONFIG),'--root-preflight',close_req['startup_proof_path'],
        '--quota-reuse-review',str(OLD_QUOTA),'--descriptor',str(close_descriptor_path),'--output',str(WAVE1_CLOSED.parent)]
    C.need(close_req['execution_argv']==expected_close and close_req['scope_key']=='sprime_formal_cpu_auto_v3_close'
        and close_req['scope_parameters']==C.scope('close',config_ref),'EXACT_ACTUAL_PRIOR_CLOSE_PRIMARY_OPTIONS_AND_SCOPE')
    descriptor_ref,descriptor=metadata(close_descriptor_path)
    C.need(all(descriptor[k]==closed[k] for k in ('plan','prepared','request','submission','accounting')),'PRIOR_CLOSE_ACTUAL_DESCRIPTOR_OUTPUT_CHAIN')
    account_ref,account_value,parents=account(args.accounting,('4521457','4521475','4521477'),c0=('4521457','4521475','4521477'))
    C.need(all(closed['actual_parent'][k]==parents['4521475'][k] for k in ('state','exit_code','alloc_cpus','elapsed_raw_seconds')),
        'CLOSED_FIRST500_ACTUAL_PARENT_DIFFERS_FROM_ACCOUNTING')
    add_account(refs,account_ref,account_value)
    quota_ref=approve_resource(refs,out,args);jobs=[]
    for bid in BATCHES:
        jobs.append({'batch_id':bid,'job_name':'dv1_q_sprime_v3_wave2_b'+bid[6:]+'_20261027_v1',
            'node':'compute-0-13','cpus':16,'wall_seconds':WALL,'whole_output_cap_bytes':C.CAP,
            'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','output_root':str(WAVE2/bid/'generation_v1')})
    wave={'schema':C.SCHEMAS['wave_review'],'status':'APPROVED_BOUNDED_WAVE','reviewer':'root','draft_reference':draft_ref,
        'config_reference':config_ref,'jobs':jobs,'maximum_concurrent_jobs':MAX_CONCURRENT,
        'requested_allocation_core_seconds_ceiling':CEILING,'requested_allocation_core_hours_ceiling':CEILING//3600,
        'approved_over_500_core_hours':True,'full_forecast_status':C.FORECAST,'estimated_full_core_hours':None,
        'ceiling_is_not_full_forecast_or_actual_cost_guarantee':True,'scientific_quality_thresholds_unchanged':True,
        'resource_authority':C.sources()['resource_authority'],'cost_authority':C.sources()['cost_authority'],
        'root_reason':args.root_reason,'prior500_independent_closed_reference':closed_ref,
        'root_reported_prior500_SUCCESS_count':args.root_observed_wave1_successes,
        'prior500_success_basis':'ROOT_REVIEWED_EXISTING_TERMINAL_OUTCOME_METADATA; NOT_INFERRED_FROM_C0_OR_VALID_PACKET_COUNT',
        'prior500_outcomes_reference':closed['terminal_outcomes'],'prior_independent_closer_request':close_req_ref,
        'prior_independent_closer_submission':close_sub_ref,'actual_previous_parent_accounting':account_ref,
        'quota_reuse_review_reference':quota_ref,'source_mapping_review_reference':mapping_ref,
        'provider_expiry_STOP_and_natural_drain':True,'automatic_retry':False,'common_frozen':False}
    wave_ref=write_new(out/'finite_wave_root_review.json',wave);C.approve_wave(draft_ref,draft,wave_ref,config_ref)
    for key in ('original_deficits','unsupported','pilot_imports'):refs.add(draft[key],data=True)
    for bid in BATCHES:refs.add(by_id[bid]['tasks'],data=True)
    refs.add(closed['terminal_outcomes'],data=True);refs.add(closed['unstarted_metas'],data=True)
    parents=[draft_ref,wave_ref,account_ref,closed_ref,close_req_ref,close_sub_ref,descriptor_ref,pilot_ref,quota_ref,mapping_ref]
    argv=[PY,'-B',str(FORMAL/'plan.py'),'freeze','--config',str(CONFIG),'--root-preflight',PROOF_PLACEHOLDER,
        '--quota-reuse-review',quota_ref['path'],'--draft',str(DRAFT),'--wave-review',wave_ref['path'],'--output',str(WAVE2/'frozen_v1')]
    manifest={'schema':'ROOT_SPRIME_WAVE2_METADATA_MANIFEST_V1','config_reference':config_ref,'draft_reference':draft_ref,
        'wave_review_reference':wave_ref,'quota_reuse_review_reference':quota_ref,'mapping_review_reference':mapping_ref,
        'batch_ids':list(BATCHES),'molecules':89249,'science_jobs':179,'maximum_concurrent_jobs':2,
        'scientific_output_reserve_bytes':SCIENCE_RESERVE,'whole_wave_output_reserve_bytes':WAVE_RESERVE,
        'requested_science_core_seconds_ceiling':CEILING,'requested_science_core_hours_ceiling':CEILING//3600,
        'full_forecast_status':C.FORECAST,'estimated_full_core_hours':None,'actual_future_job_ids':[],
        'plan_expected_path':str(WAVE2/'frozen_v1/plan.json'),'plan_reference':None,
        'source_mapping_review_reference':mapping_ref,'no_scientific_bodies_read':True,'provider_started_or_renewed':False}
    write_new(out/'wave2_manifest.json',manifest);exact_stage(out,refs,'freeze',config_ref,pilot_ref,argv,3600,parents,args)


def after_freeze(args,out,config_ref,value,refs,pilot_ref,mapping_ref):
    C.need(args.manifest and args.plan and args.batch_id in BATCHES,'ACTUAL_WAVE2_MANIFEST_PLAN_AND_ONE_EXACT_BATCH_REQUIRED')
    C.need(ROOT/'control' in args.manifest.parents and args.manifest.name=='wave2_manifest.json','ONLY_NEW_ROOT_CONTROL_MANIFEST_METADATA')
    manifest_ref,manifest=metadata(args.manifest,'ROOT_SPRIME_WAVE2_METADATA_MANIFEST_V1')
    C.need(str(args.plan)==manifest['plan_expected_path']==str(WAVE2/'frozen_v1/plan.json'),'ONLY_EXACT_EXPECTED_WAVE2_PLAN_LOCATOR')
    plan_ref,plan=metadata(args.plan,C.SCHEMAS['plan']);quota_ref=manifest['quota_reuse_review_reference']
    C.need(meta_pin(quota_ref['path'])==quota_ref and manifest['config_reference']==config_ref and manifest['batch_ids']==list(BATCHES)
        and manifest['whole_wave_output_reserve_bytes']==WAVE_RESERVE and manifest['mapping_review_reference']==mapping_ref,
        'EXACT_REAL_WAVE2_METADATA_BINDINGS')
    quota=load(quota_ref['path']);identity_ref=quota['publisher_identity_reference']
    C.need(meta_pin(identity_ref['path'])==identity_ref and time.time()<load(identity_ref['path'])['expires_unix_seconds'],
        'ACTUAL_FINITE_PROVIDER_EXPIRED_NO_AUTOMATIC_RENEWAL')
    refs.add(identity_ref)
    C.need(plan['status']=='BOUNDED_WAVE_FROZEN_IMPORTS_CLOSED' and plan['config']==config_ref
        and plan['root_review']==manifest['wave_review_reference'] and plan['draft']==manifest['draft_reference']
        and len(plan['jobs'])==179 and plan['maximum_concurrent_jobs']==2 and plan['imports320_durably_verified'] is True,
        'ONLY_ACTUAL_FROZEN179_WAVE2_PLAN_ALLOWED')
    C.need(plan['draft']==meta_pin(DRAFT) and meta_pin(plan['root_review']['path'])==plan['root_review'],
        'ONLY_ORIGINAL_DRAFT_AND_SMALL_REAL_ROOT_REVIEW_LOCATORS')
    C.need({b['batch_id'] for b in plan['batches']}==set(BATCHES) and {j['batch_id'] for j in plan['jobs']}==set(BATCHES)
        and all(j['wall_seconds']==WALL and j['node']=='compute-0-13' and j['cpus']==16 for j in plan['jobs']),
        'EXACT179_INITIAL_BATCHES_AND_FIXED_REQUEST_CEILINGS')
    draft=C.read(plan['draft']);C.approve_wave(plan['draft'],draft,plan['root_review'],config_ref)
    batch=next(b for b in plan['batches'] if b['batch_id']==args.batch_id);slot=next(s for s in plan['jobs'] if s['batch_id']==args.batch_id)
    C.need(slot['output_root']==str(WAVE2/args.batch_id/'generation_v1') and slot['wall_seconds']==WALL,'EXACT_APPROVED_SCIENCE_OUTPUT_AND8H_SLOT')
    refs.add(batch['tasks'],data=True)
    for key in ('pilot_imports','original_deficits','unsupported'):refs.add(plan[key],data=True)
    parents=[manifest_ref,plan_ref,plan['draft'],plan['root_review'],pilot_ref,quota_ref,mapping_ref]
    if args.stage=='prepare':
        account_ref,av,ap=account(args.accounting,(plan['runtime']['job_id'],),c0=(plan['runtime']['job_id'],));add_account(refs,account_ref,av);parents.append(account_ref)
        argv=[PY,'-B',str(MAPPED/'prepare_batch.py'),'--config',str(CONFIG),'--plan',str(args.plan),'--batch-id',args.batch_id,
            '--root-preflight',PROOF_PLACEHOLDER,'--quota-reuse-review',quota_ref['path'],'--source-mapping-review',mapping_ref['path'],
            '--output',str(WAVE2/args.batch_id/'prepared_mapping_v1')];wall=14400
    else:
        C.need(args.prepared,'ACTUAL_CPU_PREPARED_HEADER_REQUIRED')
        C.need(args.prepared==WAVE2/args.batch_id/'prepared_mapping_v1/prepared.json','ONLY_EXACT_ACTUAL_BATCH_PREPARED_HEADER_LOCATOR')
        prepared_ref,prepared=metadata(args.prepared,C.SCHEMAS['prepared'])
        C.need(prepared['status']=='ORIGINAL_BATCH_INPUTS_READY_NOT_GENERATED' and prepared['config']==config_ref and prepared['plan']==plan_ref
            and prepared['batch']==batch and prepared['molecules']==batch['molecules'] and prepared['kernel_sha256']==C.KERNEL_SHA,
            'ACTUAL_CPU_PREPARED_EXACT_BATCH_HEADER_REQUIRED')
        refs.add(prepared['tasks'],data=True);parents.append(prepared_ref)
        for old in prepared['old_sprime_sources']:refs.add(old['reference'],data=True)
        refs.add(prepared['formal_source'],data=True)
        if args.stage=='run':
            ar,av,ap=account(args.accounting,(prepared['runtime']['job_id'],),c0=(prepared['runtime']['job_id'],));add_account(refs,ar,av);parents.append(ar)
            argv=[PY,'-B',str(FORMAL/'run_batch.py'),'--config',str(CONFIG),'--prepared',str(args.prepared),
                '--root-preflight',PROOF_PLACEHOLDER,'--quota-reuse-review',quota_ref['path'],'--output',slot['output_root']];wall=WALL
        else:
            C.need(args.request and args.submission,'ACTUAL_REGISTERED_RUN_AND_SUBMISSION_REQUIRED_AFTER_TERMINAL')
            C.need(args.request==ROOT/'control/requests'/(slot['job_name']+'.json')
                and args.submission==ROOT/'control/submissions'/(slot['job_name']+'.json'),'ONLY_ACTUAL_APPROVED_SLOT_REGISTRY_METADATA')
            request_ref,request=metadata(args.request);submission_ref,submission=metadata(args.submission,'CPU_AUTO_MEMORY_SUBMISSION_V1')
            jid=str(submission['job_id']);ar,av,ap=account(args.accounting,(jid,));add_account(refs,ar,av)
            C.need(submission['request']==request and submission['request_reference']==request_ref and submission['sbatch_returncode']==0
                and submission['uid']==1278 and request['job_name']==slot['job_name'] and request['node']==slot['node']=='compute-0-13'
                and request['cpus']==16 and request['wall_seconds']==WALL and request['kind']=='conformer' and request['pilot'] is False,
                'ONLY_ACTUAL_TERMINAL_REGISTERED_APPROVED_SOURCE_SLOT_CAN_CLOSE')
            expected=[PY,'-B',str(FORMAL/'run_batch.py'),'--config',str(CONFIG),'--prepared',str(args.prepared),
                '--root-preflight',request['startup_proof_path'],'--quota-reuse-review',quota_ref['path'],'--output',slot['output_root']]
            C.need(request['execution_argv']==expected and request['scope_key']=='sprime_formal_cpu_auto_v3_run'
                and request['scope_parameters']==C.scope('run',config_ref),'ACTUAL_PRIMARY_AND_COMPLETE_RUN_OPTION_CHAIN')
            descriptor=write_new(out/'descriptor.json',{'plan':plan_ref,'prepared':prepared_ref,'request':request_ref,'submission':submission_ref,'accounting':ar})
            parents.extend((request_ref,submission_ref,ar,descriptor))
            argv=[PY,'-B',str(CLOSER/'run.py'),'close','--config',str(CONFIG),'--root-preflight',PROOF_PLACEHOLDER,
                '--quota-reuse-review',quota_ref['path'],'--descriptor',descriptor['path'],'--output',str(WAVE2/args.batch_id/'closed_v1')];wall=7200
    exact_stage(out,refs,args.stage,config_ref,pilot_ref,argv,wall,parents,args)


def main():
    on_login();p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=('freeze','prepare','run','close'))
    p.add_argument('--output',type=pathlib.Path,required=True,help='New Root control directory; never a compute-stage output directory.')
    p.add_argument('--accounting',type=pathlib.Path,required=True,help='Existing real terminal accounting/raw metadata; never a job prediction.')
    p.add_argument('--root-reason',required=True);p.add_argument('--root-approve-exact-stage',action='store_true')
    p.add_argument('--root-approve-wave2',action='store_true');p.add_argument('--root-observed-wave1-successes',type=int)
    for name in ('manifest','plan','prepared','request','submission'):p.add_argument('--'+name,type=pathlib.Path)
    p.add_argument('--batch-id');args=p.parse_args();out=args.output
    C.need(out.is_absolute() and ROOT/'control' in out.parents and '..' not in out.parts and not out.exists()
        and not any(x.is_symlink() for x in (out,*out.parents)),'NEW_NON_SYMLINK_ROOT_CONTROL_OUTPUT_ONLY')
    config_ref,value,refs,pilot_ref,mapping_ref=common_inputs(args)
    out.mkdir(parents=True,exist_ok=False)
    if args.stage=='freeze':freeze(args,out,config_ref,value,refs,pilot_ref,mapping_ref)
    else:after_freeze(args,out,config_ref,value,refs,pilot_ref,mapping_ref)


if __name__=='__main__':main()
