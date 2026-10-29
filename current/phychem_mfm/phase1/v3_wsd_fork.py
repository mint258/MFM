"""Explicit WSD child lineage over the unchanged strict parent trainer APIs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import torch

from . import v3_proxy_run as proxy
from .v3_contract import canonical_hash,require
from .v3_proxy_segments import ProxySegmentExperiment,owned_lock,allocate_launch
from .v3_sample_budget_events import (binding,canonical,encoded,owned_bytes,physical,
    read_bound,verify_checkpoint_record,write_once)
from .v3_sample_budget_experiment import SampleBudgetPlan
from .v3_sampling import UniformMoleculeSampler
from .v3_trainer import SampleLRScheduler
from .v3_training import SampleClock,capture_rng_state,restore_rng_state

MODULE = 'current/phychem_mfm/phase1/v3_wsd_fork.py'
TOOL = 'tools/model_v3/run_wsd_fork.py'
ALLOWED_ADDITIONS = frozenset((MODULE,TOOL))


def fork_sources():
    return {**proxy.collect_sources(),TOOL:hashlib.sha256((proxy.REPOSITORY/TOOL).read_bytes()).hexdigest()}


def verify_parent_sources(parent,child):
    """No changed/deleted parent file; additions must be explicit new fork code.

    Engineering parents bind raw bytes without claiming their base contains
    dirty files. Scientific parents additionally verify every historical Git
    blob. Current child clean HEAD is checked by the unchanged child validator.
    """
    expected = parent['sources']['runtime_files']; actual = fork_sources()
    require(expected and set(expected) <= set(actual)
        and all(actual[p] == sha for p,sha in expected.items()),'Parent implementation changed or disappeared')
    additions = {p:actual[p] for p in set(actual)-set(expected)}
    require(set(additions) <= ALLOWED_ADDITIONS
        and child['wsd_fork']['source_additions'] == additions,'Only exact pinned new fork additions are allowed')
    require(re.fullmatch('[a-f0-9]{40}',parent['sources']['code_sha']) is not None,'Full historical parent code SHA required')
    if parent['mode'] == 'authoritative_proxy':
        require(parent['sources']['state'] == 'clean_committed'
            and proxy._git(proxy.REPOSITORY,'rev-parse',parent['sources']['code_sha']+'^{tree}') == parent['sources']['tree_sha'],
            'Historical parent committed tree differs')
        for relative,sha in expected.items():
            raw = subprocess.run(['git','-C',str(proxy.REPOSITORY),'show',parent['sources']['code_sha']+':'+relative],
                check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
            require(hashlib.sha256(raw).hexdigest() == sha,'Historical parent Git source blob differs')
    else:
        require(parent['mode'] == 'synthetic_engineering'
            and parent['sources']['state'] == 'engineering_raw_inventory_not_claimed_in_base_commit',
            'Explicit engineering parent provenance required')
    return {'parent_inventory_sha256':canonical_hash(expected),'new_fork_additions':additions,
        'parent_Git_blobs_verified':parent['mode'] == 'authoritative_proxy'}


def plan_from(configuration):
    value = configuration['proxy_contract']['sample_plan']
    return SampleBudgetPlan(**{**value,**{key:tuple(value[key]) for key in ('panel_samples','validation_samples','validation_roles')}})


def retained_projection(configuration):
    result = deepcopy(configuration)
    for key in ('runtime_source_inventory_sha256','wsd_fork'): result.pop(key,None)
    contract = result['proxy_contract']
    for key in ('sample_budget','schedule'): contract.pop(key)
    for key in ('sample_budget','panel_samples','validation_samples'): contract['sample_plan'].pop(key)
    return result


def validate_fork(request,*,input_kind='authoritative_proxy',engineering_only=False):
    child,child_plan,registrations = proxy.validate_request(request,input_kind=input_kind,engineering_only=engineering_only)
    policy = child['wsd_fork']; fork = request['fork']
    require(set(policy) == {'schema','parent_configuration_identity_sha256','fork_samples','decay_samples',
        'minimum_ratio','source_additions','family_ledger_bytes','maximum_forks'}
        and policy['schema'] == 'model_v3_wsd_fork_policy_v1','Explicit complete WSD policy; no seed-specific fields allowed')
    parent = read_bound(fork['parent_request']); parent_config = read_bound(parent['configuration'])
    require(parent['mode'] == request['mode'] and parent_config['engineering_only'] is child['engineering_only']
        and parent['scope'] == request['scope'],'Parent/child engineering and scientific scope cannot change')
    require(parent_config.get('wsd_fork') is None,'Nested WSD forks require a separately designed lineage; not supported')
    require(retained_projection(parent_config) == retained_projection(child)
        and parent['input_projection'] == request['input_projection']
        and parent['panel_binding'] == request['panel_binding'],'Only source addition, budget/point schedule and decay may differ')
    require(policy['parent_configuration_identity_sha256'] == proxy.identity(parent_config),
        'Parent configuration identity differs; no seed-specific checkpoint enters child identity')
    require(all(key not in child for key in ('parent_checkpoint','parent_request','parent_complete','parent_seed')),
        'Seed-specific parent references belong in request.fork, not configuration')
    proof = verify_parent_sources(parent,child)
    record,state = verify_checkpoint_record(fork['parent_complete'])
    require(state['contract']['model_configuration'] == parent['configuration']
        and state['contract']['trainer_bindings']['proxy_runtime_sources_sha256'] == canonical_hash(parent['sources']['runtime_files'])
        and state['contract']['trainer_bindings']['code_sha'] == parent['sources']['code_sha']
        and state['contract']['plan'] == json.loads(encoded(asdict(plan_from(parent_config))))
        and not state['pending_log'],'Parent must be an exact fully committed original contract')
    n = state['samples_consumed']; old = parent_config['proxy_contract']; new = child['proxy_contract']
    require(type(policy['fork_samples']) is int and n == policy['fork_samples'] and n > 0
        and type(policy['decay_samples']) is int and policy['decay_samples'] > 0
        and child_plan.sample_budget == n+policy['decay_samples'],'Registered fork point or exact consumed-draw decay budget differs')
    require(type(policy['minimum_ratio']) in (int,float) and math.isfinite(policy['minimum_ratio'])
        and 0 <= policy['minimum_ratio'] <= 1,'Explicit finite registered decay floor required')
    require(old['schedule']['mode'] == 'wsd' and old['schedule']['warmup_samples'] <= n < old['schedule']['decay_start_samples'],
        'WSD fork requires a checkpoint in the declared parent stable interval')
    require(new['schedule'] == {'mode':'wsd','warmup_samples':0,'decay_start_samples':n,'minimum_ratio':policy['minimum_ratio']},
        'Explicit short cosine decay starts continuously at the parent stable sample clock')
    require(type(policy['maximum_forks']) is int and 1 <= policy['maximum_forks'] <= 8
        and type(policy['family_ledger_bytes']) is int and 2 << 20 <= policy['family_ledger_bytes'] <= 8 << 20,
        'Bounded explicit family metadata and fork count required')
    require(new['resources']['ledger_bytes']+policy['family_ledger_bytes']+new['resources']['tracking_bytes']
        +(96 << 20)+child_plan.max_segment_bytes <= new['resources']['joint_output_bytes'],
        'Parent and all children share original2GiB; family reserve cannot be omitted')
    parent_ledger = physical(fork['parent_ledger'])
    require(read_bound(binding(parent_ledger/'EXPERIMENT.json'))['contract'] == state['contract'],'Actual parent canonical ledger differs')
    registration = read_bound(fork['parent_segment_registration'])
    require(Path(fork['parent_segment_registration']['path']).parent == parent_ledger/'segments'
        and registration['contract_sha256'] == canonical(state['contract'])
        and physical(fork['parent_complete']['path']).parent.is_relative_to(
            physical(registration['experiment_root'])/'segments'/registration['segment_id']), 'Parent checkpoint is not registered in its actual lineage')
    if not engineering_only:
        # Original authority/registration remains part of the strict parent chain.
        admission = read_bound(parent['Root_admission'])
        require(admission['status'] == 'ROOT_ADMITTED_FINAL_INPUTS'
            and admission['request_identity_sha256'] == canonical_hash({k:v for k,v in parent.items() if k != 'Root_admission'}),
            'Original scientific parent admission differs')
        purposes = ['budget','validation',*(['calibration'] if parent['scope'] == 'calibration' else ['selection','platform'])]
        if parent['scope'] == 'recipe': purposes.append('recipe')
        for purpose in purposes:
            proxy._registration(parent['registrations'][purpose],purpose=purpose,configuration=parent_config)
        receipt = proxy._registration(request['registrations']['wsd_fork'],purpose='wsd_fork',configuration=child)
        registered,_ = proxy.git_registration(request['registrations']['wsd_fork']['executed_local'],expected_sha256=receipt['policy_sha256'])
        require(registered['wsd_fork'] == policy,'Registered full WSD lineage/decay policy differs')
        terminal = read_bound(fork['parent_terminal'])
        require(terminal['status'] == 'COMPLETED' and terminal['exit_code'] == 0
            and terminal['checkpoint_complete'] == fork['parent_complete'] and terminal['parent_training_sealed_for_fork'] is True,
            'Actual Root successful sealed parent terminal receipt required')
        registrations['wsd_fork'] = receipt
    return child,child_plan,registrations,parent,parent_config,state,proof


def ledger_roots(root,maximum=128):
    root = physical(root); roots = {root}
    for folder,key in (('segments','experiment_root'),('launches','job_root')):
        paths = list(physical(root/folder).glob('*.json'))
        require(len(paths) <= maximum,'Bounded family ledger inventory required')
        for path in paths:
            value = read_bound(binding(path)); item = physical(value[key])
            roots.add(item.parent if key == 'experiment_root' else item)
    return roots


class ForkFamily:
    """One immutable bounded family; parent files and ACKs are never copied."""
    def __init__(self,root,*,fork,policy,child_identity,maximum_checkpoints):
        self.root = physical(root)
        require(str(self.root) == fork['family_root'],'Immutable request family root differs; budget cannot reset')
        parent_contract = read_bound(binding(physical(fork['parent_ledger'])/'EXPERIMENT.json'))['contract']
        parent_configuration = read_bound(parent_contract['model_configuration'])
        self.long_policy = parent_configuration.get('long_run_policy')
        require(maximum_checkpoints == parent_contract['plan']['max_total_checkpoints'],
            'Family checkpoint/attempt maximum cannot increase beyond original parent plan')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.limit,self.maximum = policy['family_ledger_bytes'],maximum_checkpoints
        body = {'schema':'model_v3_wsd_family_v1','parent_request':fork['parent_request'],
            'parent_complete':fork['parent_complete'],'parent_ledger':fork['parent_ledger'],
            'child_configuration_identity_sha256':child_identity,'policy':policy,'maximum_checkpoints':maximum_checkpoints}
        with owned_lock(self.root,'metadata.lock') as lock:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX)
            require(owned_bytes(self.root)+ (0 if (self.root/'FAMILY.json').exists() else len(encoded(body))) <= self.limit,'Family metadata capacity exhausted')
            write_once(self.root/'FAMILY.json',body); physical(self.root/'children').mkdir(exist_ok=True)
        self.body = body

    def register_child(self,*,lineage,ledger,request_ref):
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',lineage or ''),'Bounded child lineage id required')
        body = {'schema':'model_v3_wsd_child_allocation_v1','lineage':lineage,'ledger':str(physical(ledger)),'request':request_ref}
        with owned_lock(self.root,'metadata.lock') as lock:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX)
            path = physical(self.root/'children'/(lineage+'.json'))
            others = list((self.root/'children').glob('*.json'))
            require(path.exists() or len(others) < self.body['policy']['maximum_forks'],'Registered total fork count exhausted')
            require(all(read_bound(binding(p))['ledger'] != body['ledger'] or p == path for p in others),'Child ledger reused by another lineage')
            require(owned_bytes(self.root)+(0 if path.exists() else len(encoded(body))) <= self.limit,'Family metadata cap exhausted')
            if self.long_policy is not None and path.exists():
                from .v3_long_run_storage import stable_request_identity
                existing = read_bound(binding(path))
                require(existing['ledger'] == body['ledger'] and stable_request_identity(read_bound(existing['request']))
                    == stable_request_identity(read_bound(request_ref)),'WSD operational renewal changed stable child request')
                return binding(path)
            return write_once(path,body)

    def ledgers(self):
        paths = list((self.root/'children').glob('*.json'))
        require(len(paths) <= self.body['policy']['maximum_forks'] and owned_bytes(self.root) <= self.limit,'Family cap drift')
        result = [physical(self.body['parent_ledger']),*[physical(read_bound(binding(p))['ledger']) for p in paths]]
        attempts = 0
        for ledger in result:
            folder = 'launches' if (ledger/'LAUNCH_POLICY.json').exists() else 'segments'
            attempts += len(list((ledger/folder).glob('*.json')))
        launch_max = self.long_policy['counts']['launch_attempts'] if self.long_policy is not None else self.maximum
        require(attempts <= launch_max,'Shared parent/fork segment attempt budget exhausted')
        return result

    def reserve_launch(self,ledger,**arguments):
        # All WSD launch allocations serialize through the family lock; a
        # failed initialization consumes a slot rather than creating a budget.
        with owned_lock(self.root,'metadata.lock') as lock:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX)
            attempts = 0
            for item in self.ledgers():
                folder = 'launches' if (item/'LAUNCH_POLICY.json').exists() else 'segments'
                attempts += len(list((item/folder).glob('*.json')))
            launch_max = self.long_policy['counts']['launch_attempts'] if self.long_policy is not None else self.maximum
            require(attempts < launch_max,'Shared parent/fork attempt cap reached before SDK/model initialization')
            if self.long_policy is not None:
                from .v3_long_run_storage import allocate_long_launch
                return allocate_long_launch(ledger,**arguments)
            return allocate_launch(ledger,**arguments)

    def roots(self):
        roots = {self.root}
        maximum = self.long_policy['counts']['launch_attempts'] if self.long_policy is not None else 128
        for ledger in self.ledgers(): roots.update(ledger_roots(ledger,maximum))
        ordered = sorted(roots,key=lambda p:len(p.parts))
        require(all(not b.is_relative_to(a) for i,a in enumerate(ordered) for b in ordered[i+1:]),'Family roots overlap; no duplicate accounting')
        return ordered

    def checkpoint_directories(self):
        result = set()
        for ledger in self.ledgers():
            paths = list((ledger/'segments').glob('*.json'))
            maximum = self.long_policy['counts']['launch_attempts'] if self.long_policy is not None else 128
            require(len(paths) <= maximum,'Bounded family segment count required')
            for path in paths:
                row = read_bound(binding(path)); root = physical(row['experiment_root'])/'segments'/row['segment_id']
                result.update(root.glob('checkpoint_*'))
        return list(result)


class WSDChildExperiment(ProxySegmentExperiment):
    def __init__(self,*args,family,**kwargs):
        self.family = family
        super().__init__(*args,**kwargs)

    def lineage_output_roots(self): return self.family.roots()

    def _all_checkpoint_directories(self): return self.family.checkpoint_directories()


def restore_and_fork(request,configuration,plan,inputs,tracker,*,output_root,lineage_root,lineage,family,
                     parent,parent_config,parent_state,child_authority_receipt=None,allow_unit_tracker=False):
    """Strictly restore parent, then construct an explicit child around same state."""
    root = physical(output_root); fork = request['fork']
    restored = proxy.build_experiment(parent,parent_config,plan_from(parent_config),inputs,tracker,
        output_root=root/'parent_restore/training',lineage_root=root/'parent_restore/ledger',
        lineage=parent_state['contract']['lineage'],device=parent_config['proxy_contract']['execution']['device'],
        allow_unit_tracker=allow_unit_tracker)
    require(restored.contract == parent_state['contract'],'Reconstructed complete original parent contract differs')
    directory = physical(fork['parent_complete']['path']).parent
    restored.trainer.load(directory/'trainer',output_root=directory)
    trainer = restored.trainer; n = trainer.clock.samples_consumed
    execution = configuration['proxy_contract']['execution']
    require(torch.get_num_threads() == execution['threads']
        and torch.are_deterministic_algorithms_enabled() is execution['deterministic']
        and torch.get_float32_matmul_precision() == 'highest'
        and not torch.backends.cuda.matmul.allow_tf32 and not torch.backends.cudnn.allow_tf32,
        'Restored actual parent execution differs from declared retained child precision/runtime')
    require(n == configuration['wsd_fork']['fork_samples'] and trainer.pending_log is None,'Restored parent cursor/log is not a stable committed fork')
    lrs = [float(g['lr']) for g in trainer.optimizer.param_groups]
    require(all(lr > 0 and lr == trainer.scheduler.contract['base_lrs'][i] for i,lr in enumerate(lrs)),
        'Parent LR is not in its declared stable plateau')
    # No model/optimizer/provider rebuild. The initial parent load above restored
    # the original RNG. Constructors below must not advance that RNG stream.
    rng = capture_rng_state(); contract = configuration['proxy_contract']
    sampler = UniformMoleculeSampler(trainer.sampler.index,seed=trainer.sampler.seed,sample_budget=plan.sample_budget,
        selection=trainer.sampler.selection,geometry_source=trainer.sampler.geometry_source)
    sampler.load_state_dict({**sampler.state_dict(),'samples_consumed':n})
    scheduler = SampleLRScheduler(trainer.optimizer,sample_budget=plan.sample_budget,**contract['schedule'])
    scheduler.set_consumed(n)
    require([float(g['lr']) for g in trainer.optimizer.param_groups] == lrs,'First child LR is discontinuous')
    clock = SampleClock(plan.sample_budget,trainer.clock.milestones,n,trainer.clock.optimizer_updates,list(trainer.clock.saved_milestones))
    bindings = {**trainer.bindings,'code_sha':request['sources']['code_sha'],'configuration_sha256':request['configuration']['sha256'],
        'proxy_runtime_sources_sha256':canonical_hash(request['sources']['runtime_files']),
        'wsd_fork_policy_sha256':canonical_hash(configuration['wsd_fork'])}
    require(child_authority_receipt is not None or configuration['engineering_only'],'Child request needs its own final authority verification receipt')
    if child_authority_receipt is not None:
        bindings['proxy_authority_receipt_sha256'] = canonical_hash(child_authority_receipt)
    child_execution = None
    if trainer.training_execution is not None:
        from .v3_training_execution import rebind_training_execution
        child_execution = rebind_training_execution(trainer.model, trainer.optimizer, trainer.training_execution,
            workload_binding=proxy.training_workload_binding(request, configuration, inputs),
            execution=configuration['training_execution'], operational_admission=request.get('training_execution_admission'))
    child = proxy.ProxyStepTrainer(trainer.model,trainer.optimizer,scheduler,sampler,clock,trainer.provider,
        trainer.normalizations,trainer.weights,tracker,bindings,enabled_groups=trainer.groups,enabled_fields=trainer.fields,
        view_config=trainer.view_config,structural_views=trainer.structural_views,validation_policy=trainer.validation_policy,
        gradient_clip_norm=trainer.gradient_clip_norm,gradient_probe_interval=trainer.gradient_probe_interval,
        probe_samples=trainer.probe_samples,allow_unit_tracker=allow_unit_tracker,validation_batch_cap=trainer.validation_batch_cap,
        training_execution=child_execution, **contract['batch_limits'])
    child.log_cursor = trainer.log_cursor
    # The actual saved SDK identity, not the new construction tracker, is parent.
    child.resume_parent = deepcopy(trainer.resume_parent)
    child.validation_state = deepcopy(trainer.validation_state); child.model.train(trainer.model.training)
    restore_rng_state(rng)
    controller_options = {}
    if 'long_run_policy' in configuration:
        from .v3_long_run_storage import controller_class
        controller_options['controller_factory'] = controller_class()
    experiment = WSDChildExperiment(child,plan,output_root=root/'training',lineage=lineage,
        input_scope=restored.input_scope,model_configuration=request['configuration'],panel_binding=request['panel_binding'],
        panel_required=not configuration['engineering_only'],lineage_root=lineage_root,
        ledger_bytes=contract['resources']['ledger_bytes'],family=family,**controller_options)
    experiment.points = deepcopy(parent_state['points'])
    write_once(root/'FORK_RECEIPT.json',{'schema':'model_v3_wsd_fork_receipt_v1','parent_request':fork['parent_request'],
        'parent_complete':fork['parent_complete'],'parent_contract_sha256':canonical(parent_state['contract']),
        'child_contract_sha256':canonical(experiment.contract),'fork_samples':n,'optimizer_updates':clock.optimizer_updates,
        'log_cursor':child.log_cursor,'continuous_lrs':lrs,'physical_draw_contract_except_budget':
            {k:v for k,v in sampler.contract.items() if k != 'sample_budget'},
        'sampling_cursor_reset':False,'optimizer_reset':False,'RNG_reset':False,'parent_ACKs_copied':False,
        'scientific_acceptance':False,'outer_terminal_evidence_required':True})
    return experiment


def verify_fork_chain(experiment,completion_ref):
    """Bind this complete child checkpoint to the actual immutable parent bundle.

    The parent reference is run provenance. It is deliberately not a training
    recipe binding, where its seed-specific bytes would poison seed-pair SD.
    """
    _,state = verify_checkpoint_record(completion_ref)
    require(state['contract'] == experiment.contract,'Checkpoint belongs to another child contract')
    folder = experiment.family.root/'children'
    allocation_ref = binding(folder/(state['contract']['lineage']+'.json'))
    allocation = read_bound(allocation_ref); request = read_bound(allocation['request'])
    family_ref = binding(experiment.family.root/'FAMILY.json'); family = read_bound(family_ref)
    require(request['fork']['parent_complete'] == family['parent_complete']
        and request['fork']['parent_request'] == family['parent_request']
        and request['configuration'] == state['contract']['model_configuration']
        and allocation['ledger'] == str(experiment.controller.root)
        and canonical_hash(read_bound(request['configuration'])['wsd_fork']) ==
            state['contract']['trainer_bindings']['wsd_fork_policy_sha256'], 'Complete immutable parent/child fork chain differs')
    return {'schema':'model_v3_wsd_checkpoint_chain_v1','child_complete':completion_ref,'family':family_ref,
        'child_registration':allocation_ref,'child_request':allocation['request'],
        'parent_complete':family['parent_complete'],'parent_request':family['parent_request'],
        'scientific_acceptance':False,'actual_Root_terminal_and_SDK_verification_required':True}


def engineering_fork_request(directory,*,parent_request_ref,parent_complete_ref,parent_ledger,
                             parent_segment_registration,family_root,code_sha,decay_samples,maximum_forks=1):
    """Prepare explicit analytic metadata, after a real engineering parent save."""
    directory = physical(directory); directory.mkdir(parents=True,exist_ok=False)
    parent = read_bound(parent_request_ref); config = read_bound(parent['configuration'])
    require(parent['mode'] == 'synthetic_engineering' and config['engineering_only'] is True,'Engineering parent only')
    _,state = verify_checkpoint_record(parent_complete_ref); n = state['samples_consumed']
    current = fork_sources(); additions = {p:sha for p,sha in current.items() if p not in parent['sources']['runtime_files']}
    child = deepcopy(config); contract = child['proxy_contract']; total = n+decay_samples
    contract['sample_budget'] = total
    contract['schedule'] = {'mode':'wsd','warmup_samples':0,'decay_start_samples':n,'minimum_ratio':0.}
    points = sorted({total,*[v for v in contract['milestones'] if v <= total]})
    contract['sample_plan'].update(sample_budget=total,panel_samples=points,validation_samples=points)
    child['runtime_source_inventory_sha256'] = canonical_hash(proxy.collect_sources())
    child['wsd_fork'] = {'schema':'model_v3_wsd_fork_policy_v1','parent_configuration_identity_sha256':proxy.identity(config),
        'fork_samples':n,'decay_samples':decay_samples,'minimum_ratio':0.,'source_additions':additions,
        'family_ledger_bytes':2 << 20,'maximum_forks':maximum_forks}
    request = {**deepcopy(parent),'configuration':write_once(directory/'configuration.json',child),
        'sources':{'code_sha':code_sha,'tree_sha':None,'state':'engineering_raw_inventory_not_claimed_in_base_commit',
            'runtime_files':proxy.collect_sources()},
        'fork':{'parent_request':parent_request_ref,'parent_complete':parent_complete_ref,
            'parent_ledger':str(physical(parent_ledger)),'parent_segment_registration':parent_segment_registration,
            'family_root':str(physical(family_root))}}
    request.pop('Root_admission',None)
    return write_once(directory/'request.json',request)
