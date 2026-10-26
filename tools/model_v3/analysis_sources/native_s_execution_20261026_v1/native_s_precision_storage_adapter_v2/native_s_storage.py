"""Native-S-only finite storage adapter over Root075's immutable accounting.

No quota reservation, source-data write, Slurm submission, final-D authority or
numeric B acceptance is supplied by this module. Root provides every authority
reference. PROFILE_ONLY is a separate real-native bootstrap, never engineering
evidence promoted to scientific capacity.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import types
import uuid
import runtime_origin
import root_coverage
import profile_lifecycle

HERE = Path(__file__).absolute().parent
ROOT_COMMIT = '075123e2fa2c511bf074a31f42df272d692e5356'
SCOPE = 'existing_native_S_original_TRAIN_record_sampler_not_D5'
PROFILE = 'PROFILE_ONLY_NO_B_ACCEPTANCE'
SCIENCE = 'FOUR_NATIVE_S_B_MEMBERS'
PLAN = dict(input_scope=SCOPE, updates=20000, sample_budget=10240000,
    validation_updates=list(range(0,20001,500)), checkpoint_updates=[10000,20000], warmup_samples=0)
SOURCE = dict(manifest_sha256='2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997',
    snapshot_sha256='d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f',
    validation_selection_sha256='9ef81dcd5d3a84411328a76c5fbe7ccf123bc032e72e87a580d0b4c0bdf11e67',
    population_manifest_sha256='d21bae7f7b6c1dfbfe9342635ded80a55ddc05baba46ebfaa66cb7831866b96e',
    geometry='native_original_pos_no_PM7_or_Sprime_alias', TRAIN_records=11104772,
    validation_role='PRETRAIN_VAL', validation_records=1024, validation_atoms=55650,
    validation_noise_seed=0, validation_epoch=0, roles=['TRAIN','PRETRAIN_VAL'],
    TRAIN_UNSEEN_CONFORMATION='NOT_PROVIDED_D5', D5_authority=False)


def require(condition,message):
    if not condition: raise ValueError(message)


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''): h.update(block)
    return h.hexdigest()


def load_runtime(pin_path=None,*,metadata_only=False,allow_candidate_profile=False):
    """One canonical combined tree; no alias namespace or package-path edits."""
    path=pin_path or os.environ.get('MODEL_V3_NATIVE_S_RUNTIME_CONTRACT') or HERE/'runtime_contract.json'
    contract=runtime_origin.read_contract(path,metadata_only=metadata_only,allow_candidate_profile=allow_candidate_profile)
    module,_=runtime_origin.import_runtime(contract)
    return module,contract


def runtime_pin(contract):
    return canonical(runtime_origin.runtime_identity(contract))


def check_runtime_binding(request,configuration,contract):
    require(configuration['Root_runtime_pin']==runtime_pin(contract),'Combined runtime source identity pin differs')
    if contract['status']=='CANDIDATE_PROFILE_ONLY':
        require(configuration['purpose']==PROFILE and configuration['profile_updates']==20,
            'Candidate runtime permits only explicit20-update profile; no20k/science admission')
    require(Path(configuration['science']['native_repo']).absolute()==Path(contract['runtime_root']).absolute(),
        'Native and accounting runtime must be the same immutable tree')
    require(request['native_member']['code_sha']==contract['combined_commit']
        and request['native_member']['prereg_sha']==contract['public_commit'],
        'Actual combined/public commit binding differs')


def stable_native_request(request,storage):
    return storage.stable_request_identity(request)


def identity(configuration,request):
    return canonical({'science':configuration['science'],'native_sources':request['native_member']['sources'],
        'runtime':request['native_member']['runtime'],'native_code_sha':request['native_member']['code_sha'],
        'prereg_sha':request['native_member']['prereg_sha'],'Root_runtime_pin':configuration['Root_runtime_pin']})


def check_native_member(value,configuration):
    science=configuration['science']
    require(science['scope']==SCOPE and science['source']==SOURCE and science['plan']==PLAN,
        'Explicit original-native-S TRAIN/PRETRAIN_VAL/population/20k scope required')
    require(science['members']==[[0,'fp32'],[0,'bf16'],[1,'fp32'],[1,'bf16']]
        and science['model']=={'dim':512,'layers':6,'heads':8,'ff_mult':2}
        and science['sampling']=='original_TRAIN_record_natural_counts_not_molecule_uniform',
        'Four real512x6 members and original record sampler required')
    require(value['scope']==SCOPE and canonical(value['plan'])==canonical(PLAN) and value['seed'] in (0,1)
        and type(value['seed']) is int and value['precision'] in ('fp32','bf16'),
        'Native callback member or committed update plan differs')
    require(all(re.fullmatch('[0-9a-f]{40}',value[key]) for key in ('code_sha','prereg_sha'))
        and value['sources'] and all(re.fullmatch('[0-9a-f]{64}',v) for v in value['sources'].values()),
        'Actual/public native source inventory required')
    require(value['runtime']['device']=='cuda' and value['runtime'].get('gpu_uuid','').startswith('GPU-')
        and value['runtime'].get('deterministic_execution_sha256'),'Actual same-physical-GPU deterministic runtime required')


def validate_profile(request,configuration,storage,engineering):
    if configuration['purpose']==PROFILE:
        require(configuration['profile_updates'] in range(1,101),'Profile-only has a fixed1..100 native-update endpoint')
        return None
    require(configuration['purpose']==SCIENCE,'Explicit native science or profile-only purpose required')
    import evidence_graph as graph
    profile=storage.read_bound(request['long_run']['profile'])
    authority='ENGINEERING_METADATA_FIXTURE' if engineering else 'ROOT_ACTUAL'
    require(profile['schema']=='model_v3_Root_existing_native_S_profile_v2'
        and profile['authority']==authority and profile['scope']==SCOPE and profile['D5_authority'] is False
        and profile['profile_identity_sha256']==identity(configuration,request),
        'Actual native-S capacity profile differs; final-D/prototype substitutions are not admitted')
    disjoint=dict(TRAIN_records_checked=11104772,validation_records=1024,record_overlap=0,molecule_overlap=0,
        metadata_only=True,original_split_unchanged=True)
    require(profile['source']==SOURCE and profile['full_TRAIN_disjointness']==disjoint,'Whole TRAIN/VAL proof missing')
    require(set(profile['measurements'])=={'fp32','bf16'},'Both actual precision profiles required')
    limits=storage.policy(configuration); capacity=configuration['capacity']
    keys=('checkpoint_bytes','non_checkpoint_output_bytes','save_seconds','validation_seconds','cleanup_seconds',
        'base_records_per_second','accounting_seconds_per_guard','accounting_worst_case_roots')
    for precision,row in profile['measurements'].items():
        require(all(type(row[key]) in (int,float) and not isinstance(row[key],bool) and math.isfinite(row[key]) and row[key]>0
            for key in keys),'Actual positive native profile measurements required')
        for key in ('checkpoint_bytes','non_checkpoint_output_bytes','provider_future_state_bound_bytes','optimizer_future_state_bound_bytes'):
            require(type(row[key]) is int and row[key]>=0,'Finite raw-byte growth bound required')
        require(row['checkpoint_bytes']+row['provider_future_state_bound_bytes']+row['optimizer_future_state_bound_bytes']
            <=limits['checkpoint_bytes'],'Actual checkpoint plus future state exceeds finite cap')
        require(row['non_checkpoint_output_bytes']<=capacity['non_checkpoint_bytes']
            and row['save_seconds']+row['cleanup_seconds']<=capacity['checkpoint_reserve_seconds']
            and row['accounting_worst_case_roots']>=limits['managed_roots'],'Measured native envelope does not cover policy')
        if engineering: continue
        terminal=graph.terminal(storage,row['actual_terminal'])
        require(terminal['profile_result']==row['profile_result'],'Actual terminal is for another profile')
        supervisor=storage.read_bound(terminal['supervisor'])
        source=terminal['supervisor_source']
        require(storage.binding(source['path'])==source
            and Path(source['path'])==storage.REPOSITORY/'tools/model_v3/run_supervised.py'
            and supervisor['supervisor_source_sha256']==source['sha256']
            and str(supervisor['job_id'])==str(terminal['job_id']) and supervisor['status']=='COMPLETED'
            and supervisor['exit_code']==0 and supervisor['first_failure'] is None
            and supervisor['remaining_recorded_processes_before_retirement']==[]
            and supervisor['private_storage_cleanup_errors']==[],
            'Actual supervisor source/job/process/private closure required')
        raw=storage.read_bound(row['profile_result'])
        require(raw['schema']=='existing_native_S_storage_profile_result_v2' and raw['purpose']==PROFILE
            and raw['precision']==precision and raw['scope']==SCOPE and raw['D5_authority'] is False
            and raw['status']=='PROFILE_CHILD_COMPLETED_PENDING_OUTER_AND_NATIVE_SDK'
            and raw['failure'] is None and raw['cleanup_errors']==[] and raw['source']==SOURCE
            and raw['full_TRAIN_disjointness']==disjoint and 1<=raw['observed_profile_updates']<=100
            and raw['native_code_sha']==request['native_member']['code_sha']
            and raw['native_sources']==request['native_member']['sources']
            and raw['runtime']==request['native_member']['runtime'] and raw['prereg_sha']==request['native_member']['prereg_sha']
            and all(raw['measurements'][key]==row[key] for key in
                ('checkpoint_bytes','save_seconds','validation_seconds','cleanup_seconds','base_records_per_second')),
            'Projection differs from actual source-bound native profile')
        require(supervisor['output_budget_bytes']==limits['segment_bytes']
            and supervisor['child_output_budget_bytes']==raw['inherited_child_output_budget_bytes']
            ==limits['segment_bytes']-profile_lifecycle.GUARD_RESERVE,'Actual child budget was enlarged')
        coverage=storage.read_bound(raw['coverage_observation'])
        require(coverage['schema']=='native_S_actual_root_coverage_v2' and coverage['all_actual_outputs_covered'] is True
            and coverage['private_receipt']['path']==supervisor['private_storage_bindings_path'],
            'Actual private/external coverage is not the supervisor binding')
        graph.sdk(storage,row['native_SDK_verification'],configuration=configuration,raw_profile=raw,profile_ref=row['profile_result'])
        closed=graph.closed_outputs(storage,row['closed_output_census'],configuration=configuration,profile_ref=row['profile_result'])
        require(closed['non_checkpoint_output_bytes']==row['non_checkpoint_output_bytes']
            and closed['coverage_observation']==raw['coverage_observation'],'Closed non-CP/external census differs')
        future=graph.future_state(storage,row['future_state_certificate'],configuration=configuration,raw_profile=raw,profile_ref=row['profile_result'])
        require(future['provider_future_state_bound_bytes']==row['provider_future_state_bound_bytes']
            and future['optimizer_future_state_bound_bytes']==row['optimizer_future_state_bound_bytes'],'Future-state bytes differ')
        graph.precision(storage,row['selective_precision_certificate'],configuration=configuration,raw_profile=raw,profile_ref=row['profile_result'])
        accounting_projection=storage.read_bound(row['accounting_certificate'])
        graph.producer(storage,accounting_projection,configuration,'accounting_runner')
        accounting=storage.read_bound(accounting_projection['raw_measurement'])
        accounting_terminal=graph.terminal(storage,row['accounting_terminal'])
        require(accounting_projection['schema']=='native_S_accounting_pressure_projection_v2'
            and accounting_terminal['produced_artifact']==accounting_projection['raw_measurement']
            and accounting['schema']=='native_S_accounting_pressure_v2'
            and accounting['status']=='ACCOUNTING_CHILD_COMPLETED_PENDING_OUTER'
            and accounting['Root_runtime_pin']==configuration['Root_runtime_pin'] and accounting['operational_metadata_only'] is True
            and accounting['measurement_passes']>=8 and accounting['managed_roots']>=limits['managed_roots']
            and accounting['metadata_records']>=limits['metadata_records']
            and accounting['measured_seconds']+raw['measurements']['current_accounting_seconds']==row['accounting_seconds_per_guard']
            and accounting['managed_roots']==row['accounting_worst_case_roots'],'Actual full-history accounting cost/terminal missing')
    return profile


def validate_admission(request,configuration,storage,*,segment_id=None,job_root=None,lineage_root=None,now=None):
    """Native admission, sharing Root finite arithmetic without a final-D alias."""
    fixed_now=now; now=time.time() if now is None else now
    limits=storage.policy(configuration); lr=request['long_run']
    engineering=configuration['engineering_only'] is True
    authority='ENGINEERING_METADATA_FIXTURE' if engineering else 'ROOT_ACTUAL'
    require(configuration['schema']=='existing_native_S_storage_configuration_v2','Native storage v2 configuration required')
    require(configuration['Root_storage_commit']==ROOT_COMMIT,'Root storage commit pin differs')
    check_native_member(request['native_member'],configuration)
    require(configuration['purpose'] in (PROFILE,SCIENCE),'No other source authority admitted')
    capacity=configuration['capacity']
    for key in ('non_checkpoint_bytes','checkpoint_reserve_bytes','checkpoint_reserve_seconds','max_checkpoints_per_segment','child_seconds'):
        storage.integer(capacity[key],key)
    require(limits['segment_bytes']==2<<30 and limits['segment_seconds']==7200
        and capacity['child_seconds']==6900 and capacity['GPU_fraction']==.85
        and capacity['max_checkpoints_per_segment']==2 and capacity['checkpoint_reserve_seconds']==300,
        'Original2GiB/2h/6900s/85% and finite checkpoint reserve remain')
    require(capacity['max_checkpoints_per_segment']*limits['checkpoint_bytes']+capacity['checkpoint_reserve_bytes']
        +capacity['non_checkpoint_bytes']<=limits['segment_bytes']-profile_lifecycle.GUARD_RESERVE,
        'Worst-case child checkpoints/non-checkpoint/reserve do not fit inherited outer-minus96MiB cap')
    principal=storage.read_bound(lr['reservation_principal'])
    require(principal['schema']=='model_v3_Root_durable_reservation_v1' and principal['uid']==os.getuid()
        and principal['status']=='ROOT_COORDINATOR_RESERVED_FINITE' and principal['authority']==authority
        and principal['policy_sha256']==storage.canonical_hash(limits)
        and principal['max_bytes']==limits['durable_bytes'] and principal['counts']==limits['counts'],
        'Actual finite Root principal/counts/owner differ')
    accepted=principal.get('science_identities',[principal.get('science_identity_sha256')])
    require(type(accepted) is list and len(accepted)==1 and storage.canonical_hash(configuration) in accepted,
        'Reservation must bind this exact native-only policy/science configuration')
    storage.integer(principal['initial_existing_bytes'],'initial existing bytes',0)
    storage.integer(principal['reserved_additional_bytes'],'reserved bytes')
    require(principal['initial_existing_bytes']+principal['reserved_additional_bytes']==limits['durable_bytes'],
        'Historical bytes and finite additional reservation do not cover exact cap')
    require(set(principal['initial_counts'])==set(storage.COUNTS),'All historical counters required')
    for key,count in principal['initial_counts'].items():
        storage.integer(count,'historical '+key,0); require(count<=limits['counts'][key],'Historical counter exhausted')
    root_record=storage.read_bound(principal['Root_reservation_record'])
    require(all(root_record[k]==principal[k] for k in ('reservation_id','uid','durable_root','reserved_additional_bytes','initial_counts','authority')),
        'Root global reservation record differs')
    profile=validate_profile(request,configuration,storage,engineering)
    admission=storage.read_bound(lr['Root_segment_admission']); lease=storage.read_bound(lr['lease'])
    envelope=admission['resource_envelope']
    require(envelope['outer_output_budget_bytes']==limits['segment_bytes']
        and envelope['child_output_budget_bytes']==limits['segment_bytes']-profile_lifecycle.GUARD_RESERVE
        and envelope['supervisor_output_reserve_bytes']==profile_lifecycle.GUARD_RESERVE,
        'Root envelope must preserve actual supervisor-derived child budget')
    storage.integer(envelope['private_storage_budget_bytes'],'private storage budget')
    storage.integer(envelope['additional_durable_private_growth_hold_bytes'],'extra durable private growth',0)
    require(admission['schema']=='model_v3_Root_long_run_segment_admission_v1'
        and admission['authority']==authority and admission['stable_request_identity_sha256']==stable_native_request(request,storage)
        and admission['reservation_principal']==lr['reservation_principal'] and admission['lease']==lr['lease']
        and admission['quota_feed_descriptor']==lr['quota_feed_descriptor'],'Root operational native admission differs')
    allowed_workloads=('native_S_profile_only','native_S_accounting_pressure') if configuration['purpose']==PROFILE else ('native_S_B_member',)
    require(admission['workload'] in allowed_workloads,
        'Profile-only cannot enter four-member science allocation')
    if admission['workload']=='native_S_accounting_pressure':
        require(admission['operational_metadata_only'] is True,'Accounting pressure has no model/data authority')
    require(lease['reservation_id']==principal['reservation_id'] and lease['authority']==authority
        and lease['created_unix']<=now<lease['expires_unix'],'Fresh reservation lease required')
    if segment_id is not None:
        require(admission['segment_id']==segment_id and storage.physical(admission['job_root'])==storage.physical(job_root)
            and storage.physical(admission['lineage_root'])==storage.physical(lineage_root)
            and lease['expires_unix']-now>=limits['segment_seconds'],'Admission for exact whole physical segment required')
        if not engineering: require(str(admission['job_id'])==os.environ.get('SLURM_JOB_ID'),'Actual allocated job differs')
    descriptor=storage.read_bound(lr['quota_feed_descriptor'])
    require(descriptor['schema']=='model_v3_Root_quota_feed_descriptor_v1' and descriptor['authority']==authority
        and descriptor['uid']==principal['uid'] and descriptor['filesystem']==principal['filesystem']
        and storage.binding(descriptor['producer_source']['path'])==descriptor['producer_source'],'Pinned actual Root quota publisher required')
    feed,feed_ref,raw_feed=storage.read_current(descriptor['feed_path'])
    observation_now=time.time() if fixed_now is None else fixed_now
    quota=storage.parse_quota(feed,filesystem=principal['filesystem'],uid=principal['uid'],now=observation_now,
        max_age=limits['quota_max_age_seconds'],engineering=engineering)
    require(observation_now<lease['expires_unix'] and feed['producer_source_sha256']==descriptor['producer_source']['sha256']
        and feed['phase_ledger_id']==root_record['phase_ledger_id'],'Actual fresh quota/phase/lease identity differs')
    own=feed['reservations'][principal['reservation_id']]
    require(own['durable_root']==principal['durable_root'] and own['principal_sha256']==lr['reservation_principal']['sha256'],
        'Outstanding reservation slot differs')
    for row in feed['reservations'].values(): storage.integer(row['remaining_bytes'],'outstanding reserved bytes',0)
    storage.integer(feed['headroom_bytes'],'quota headroom',0)
    available=quota['free_bytes']-sum(row['remaining_bytes'] for key,row in feed['reservations'].items()
        if key!=principal['reservation_id'])-feed['headroom_bytes']
    require(available>=0 and quota['available_inodes']>=limits['inode_limit'],'Quota/inode/outstanding overcommit')
    return dict(policy=limits,principal=principal,admission=admission,profile=profile,lease=lease,quota=quota,
        quota_ref=feed_ref,feed=feed,quota_available_after_other_bytes=available,own_remaining_bytes=own['remaining_bytes'],
        stable_request_identity_sha256=stable_native_request(request,storage),raw_feed=raw_feed)


def ledger_class(storage):
    class NativeLedger(storage.DurableLedger):
        def register_root(self,path,**kwargs):
            require(not storage.physical(path).is_relative_to(storage.physical(self.configuration['science']['native_repo'])),
                'Native model Git worktree is not an output root')
            return super().register_root(path,**kwargs)

        def __init__(self,request,configuration):
            self.request,self.configuration=deepcopy(request),deepcopy(configuration)
            self.admission=validate_admission(request,configuration,storage); self.limits=self.admission['policy']
            self.root=storage.physical(self.admission['principal']['durable_root'])
            require(not self.root.is_relative_to(storage.REPOSITORY)
                and not self.root.is_relative_to(storage.physical(configuration['science']['native_repo'])),
                'Durable accounting stays outside both Git worktrees')
            self.root.mkdir(mode=0o700,parents=True,exist_ok=True); self._depth=0
            with self.transaction():
                for name in ('records','index','roots','feeds','lineages'): (self.root/name).mkdir(exist_ok=True)
                storage.write_once(self.root/'PRINCIPAL.json',dict(schema='model_v3_durable_ledger_v1',
                    reservation_principal=request['long_run']['reservation_principal'],policy=self.limits))
                self._space(0)
            self.register_root(self.root,kind='management',must_exist=True)
            registry=storage.read_bound(request['long_run']['initial_roots'])
            require(registry['schema']=='model_v3_long_run_initial_roots_v1','Complete old-root registry required')
            for row in registry['roots']: self.register_root(row['path'],kind=row['kind'],must_exist=row['must_exist'],entry_type=row['type'])

        def _ensure_fresh_authority(self):
            now=time.time()
            if now>=self.admission['lease']['expires_unix'] or not 0<=now-self.admission['feed']['captured_unix']<=self.limits['quota_max_age_seconds']:
                checked=validate_admission(self.request,self.configuration,storage)
                require(checked['stable_request_identity_sha256']==self.admission['stable_request_identity_sha256'],'Fresh operational authority changed native identity')
                self._space(len(checked['raw_feed']))
                storage.write_raw_once(self.root/'feeds'/(checked['quota_ref']['sha256']+'.json'),checked['raw_feed'])
                self.admission=checked

        def refresh(self):
            checked=validate_admission(self.request,self.configuration,storage)
            require(checked['stable_request_identity_sha256']==self.admission['stable_request_identity_sha256'],'Stable native member changed')
            self.census(); snapshot=self.root/'feeds'/(checked['quota_ref']['sha256']+'.json')
            with self.transaction():
                self._space(0 if snapshot.exists() else len(checked['raw_feed']))
                storage.write_raw_once(snapshot,checked['raw_feed'])
            used=self.census(); principal=checked['principal']
            remaining=max(0,principal['reserved_additional_bytes']-max(0,used-principal['initial_existing_bytes']))
            effective=min(remaining,checked['own_remaining_bytes'])
            require(effective<=checked['quota_available_after_other_bytes'],'Fresh actual quota cannot cover outstanding own reservation')
            self.admission=checked
            return dict(durable_bytes=used,durable_remaining_bytes=self.limits['durable_bytes']-used,
                quota_reserved_remaining_bytes=effective,quota_snapshot=storage.binding(snapshot))

        def allocate_segment(self,*,request_ref,segment_id,job_root,lineage_root):
            checked=validate_admission(self.request,self.configuration,storage,segment_id=segment_id,job_root=job_root,lineage_root=lineage_root)
            with self.transaction():
                held=self.limits['segment_bytes']+checked['admission']['resource_envelope']['additional_durable_private_growth_hold_bytes']
                require(self.remaining()>=held,'No whole-segment/private-growth finite reservation; active holds retained')
                identity=str(storage.physical(job_root)); lineage=str(storage.physical(lineage_root))
                self._space(1024)
                storage.write_once(self.root/'lineages'/(storage.canonical_hash({'path':lineage})+'.json'),
                    dict(lineage_root=lineage,stable_request_identity_sha256=stable_native_request(self.request,storage)))
                self.register_root(job_root,kind='training')
                if lineage not in {row['path'] for row in self.root_records()}: self.register_root(lineage_root,kind='management')
                for row in checked['admission']['external_roots']:
                    self.register_root(row['path'],kind=row['kind'],entry_type=row['type'],must_exist=row['must_exist'])
                return self.append('launch_attempts',identity,dict(request=request_ref,segment_id=segment_id,job_root=identity,
                    lineage_root=lineage,held_bytes=held,Root_admission=self.request['long_run']['Root_segment_admission']))
    return NativeLedger


class NativeStorageAdapter:
    def __init__(self,callback,*,request_ref,storage,pins):
        callback=json.loads(json.dumps(callback,allow_nan=False))
        self.storage,self.request_ref=storage,request_ref
        self.request=storage.read_bound(request_ref); self.configuration=storage.read_bound(self.request['configuration'])
        require(self.configuration['engineering_only'] is False,'Engineering quota/profile fixtures cannot bind actual native training')
        check_runtime_binding(self.request,self.configuration,pins)
        require(self.configuration['Root_runtime_pin']==runtime_pin(pins),'Exact Root runtime source pin differs')
        check_native_member(callback,self.configuration)
        member={key:callback[key] for key in ('scope','plan','seed','precision','code_sha','prereg_sha','sources','runtime')}
        require(member==self.request['native_member'],'Native hook callback differs from admitted member/source/runtime')
        self.job_root=storage.physical(callback['output_root'])
        native_repo=storage.physical(self.configuration['science']['native_repo'])
        for name,expected in callback['sources'].items():
            path=Path(__file__) if name=='external_Root_total_storage_hook' else native_repo/name
            require(not path.is_symlink() and path.is_file() and sha(path)==expected,'Actual native callback source changed: '+name)
        self.ledger=ledger_class(storage)(self.request,self.configuration)
        admitted=self.ledger.admission['admission']; self.lineage_root=storage.physical(admitted['lineage_root'])
        require(admitted['workload'] in ('native_S_profile_only','native_S_B_member'),
            'CPU metadata-pressure admission cannot bind an actual model')
        require(not self.job_root.exists(),'Native segment must be fresh before SDK/model initialization')
        self.child_budget=profile_lifecycle.inherited_budget(self.ledger.limits['segment_bytes'])
        require(callback['max_segment_bytes']==self.child_budget and type(callback['wall_seconds']) is int
            and 60<=callback['wall_seconds']<=6900,'Unchanged child output/wall limits required')
        self.coverage=root_coverage.observe(callback,admitted,self.ledger.admission['principal'],storage,pins)
        self.ledger.allocate_segment(request_ref=request_ref,segment_id=admitted['segment_id'],job_root=self.job_root,lineage_root=self.lineage_root)
        self.binding=dict(schema='existing_native_S_total_storage_policy_binding_v1',scope=SCOPE,purpose=self.configuration['purpose'],
            configuration=self.request['configuration'],Root_runtime_pin=runtime_pin(pins),
            reservation_principal=self.request['long_run']['reservation_principal'],D5_authority=False)
        self.last_refresh,self.pending,self.experiment,self.closed=0.,None,None,False
        self.timings=[]

    def _verify_inputs(self,experiment):
        values=experiment.inputs.bindings
        require(experiment.plan.input_scope==SCOPE and values['scope']==SCOPE and values['geometry']==SOURCE['geometry']
            and values['node_local'] is False and values['read_only'] is True
            and values['validation_role']=='PRETRAIN_VAL' and values['validation_records']==1024
            and values['validation_atoms']==55650 and values['validation_seed']==values['validation_epoch']==0
            and values['TRAIN_UNSEEN_CONFORMATION']=='NOT_PROVIDED_D5','Actual reader native source/role population differs')
        require(values['disjointness']==dict(TRAIN_records_checked=11104772,validation_records=1024,record_overlap=0,
            molecule_overlap=0,metadata_only=True,original_split_unchanged=True),'Full TRAIN/validation disjoint proof required')
        require(values['TRAIN']['manifest_sha256']==SOURCE['manifest_sha256']
            and values['TRAIN']['original_shard_snapshot']['sha256']==SOURCE['snapshot_sha256']
            and values['validation_selection']['sha256']==SOURCE['validation_selection_sha256']
            and values['population_manifest_sha256']==SOURCE['population_manifest_sha256'],'Native population raw pins differ')

    def _reconcile_checkpoint(self):
        if self.pending is None: return
        path,attempt=self.pending
        if (path/'COMPLETE.json').exists():
            require((path/'payload.pt').stat().st_size<=self.ledger.limits['checkpoint_bytes'],'Native payload exceeds bounded hash/read size')
            marker=self.storage.read_bound(self.storage.binding(path/'COMPLETE.json')); payload=self.storage.binding(path/'payload.pt')
            require(marker['schema']=='model_v3_training_checkpoint_v1'
                and marker['payload_sha256']==payload['sha256'] and marker['payload_bytes']==payload['bytes']
                and payload['bytes']<=self.ledger.limits['checkpoint_bytes'],'Complete native safe payload differs or exceeds cap')
            require(marker['bindings']==self.experiment.bindings,'Native checkpoint source/config differs')
            intent=self.storage.read_bound(attempt)['body']
            require(marker['optimizer_updates']==intent['updates'] and marker['samples_consumed']==intent['samples'],
                'Native checkpoint committed update/sample clocks differ from save intent')
            self.ledger.append('complete_checkpoints',payload['sha256'],dict(completion=self.storage.binding(path/'COMPLETE.json'),attempt=attempt))
            self.pending=None

    def guard(self,action,experiment):
        require(not self.closed and action in ('step','validation','checkpoint'),'Known live native storage action required')
        if self.configuration['purpose']==PROFILE:
            maximum=self.configuration['profile_updates']
            require(experiment.clock.optimizer_updates<=maximum and
                (action!='step' or experiment.clock.optimizer_updates<maximum),
                'Profile-only reservation cannot execute beyond its fixed short update ceiling')
        self.experiment=experiment; self._verify_inputs(experiment); self._reconcile_checkpoint()
        if not self.configuration['engineering_only']:
            if not (self.job_root/'actual_root_coverage_v2.json').exists():
                self.storage.write_once(self.job_root/'actual_root_coverage_v2.json',self.coverage)
            for key,value in self.coverage['planned_SDK_environment'].items():
                require(os.environ.get(key)==value,'Actual SDK environment differs from Root coverage')
        now=time.monotonic()
        if action!='step' or now-self.last_refresh>=30:
            if not self.configuration['engineering_only']:
                from private_runtime_storage import load_storage_bindings,sampled_storage_bytes
                current_private=load_storage_bindings()
                require(current_private==self.coverage['private_bindings'],'Actual private storage receipt/context changed')
                private_bytes=sampled_storage_bytes(current_private['roots'])['bytes']
                require(private_bytes<=self.coverage['private_budget_bytes'],'Actual private scratch/cache exceeds finite budget')
            self.ledger.refresh(); self.last_refresh=now
        if action=='checkpoint':
            require(self.pending is None,'Incomplete previous checkpoint attempt retained; cannot retry invisibly')
            rows=self.ledger.records()
            require(self.ledger.admission['principal']['initial_counts']['complete_checkpoints']
                +sum(row['kind']=='complete_checkpoints' for row in rows)<self.ledger.limits['counts']['complete_checkpoints'],
                'Independent complete-checkpoint cap exhausted before save')
            require(sum(row['kind']=='checkpoint_attempts' and row['body'].get('segment')==str(self.job_root) for row in rows)
                <self.configuration['capacity']['max_checkpoints_per_segment'],'Per-segment checkpoint-attempt cap exhausted')
            path=self.job_root/f'checkpoint_u{experiment.clock.optimizer_updates}_log{experiment.log_cursor}'
            require(not path.exists(),'Fresh native checkpoint path required')
            attempt=self.ledger.append('checkpoint_attempts',uuid.uuid4().hex,dict(segment=str(self.job_root),
                path=str(path),updates=experiment.clock.optimizer_updates,samples=experiment.clock.samples_consumed))
            self.pending=(path,attempt)

    def close(self):
        if self.closed: return
        self._reconcile_checkpoint(); self.ledger.refresh()
        self.ledger.append('observation',str(self.job_root)+':child_storage_close',dict(
            incomplete_checkpoint_attempt=None if self.pending is None else self.pending[1],
            scientific_acceptance=False,native_SDK_and_Root_terminal_pending=True))
        # No hold release here. Root storage_control --seal needs real terminal,
        # supervisor source/process closure and private cleanup, even on failure.
        self.closed=True


def bind_native_s_precision_storage(callback):
    path=os.environ.get('MODEL_V3_NATIVE_S_STORAGE_REQUEST')
    expected=os.environ.get('MODEL_V3_NATIVE_S_STORAGE_REQUEST_SHA256','')
    require(path and re.fullmatch('[0-9a-f]{64}',expected),'Root exact native storage request path/SHA required')
    require(sha(path)==expected,'Native storage request bytes differ')
    preliminary=json.loads(Path(path).read_text())
    configuration=runtime_origin.read_qa_reference(preliminary['configuration'])
    storage,pins=load_runtime(allow_candidate_profile=configuration['purpose']==PROFILE)
    ref=storage.binding(path); require(ref['sha256']==expected,'Native storage request bytes differ')
    return NativeStorageAdapter(callback,request_ref=ref,storage=storage,pins=pins)
