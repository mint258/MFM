"""Source-bound proxy/calibration execution; this module supplies no D schema."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys

import numpy as np
import torch

from ..model.v3_architecture import build_architecture_model
from ..model.v3_heads import V3HeadBank
from ..model.v3_multiview import V3MultiViewModel
from ..training.losses import LossWeights
from .v3_architecture_training import ArchitectureStepTrainer
from .v3_architecture_views import V3TwoViewModel
from .v3_contract import LabelRegistry, canonical_hash, require, selected_groups
from .v3_decision_evidence import git_registration
from .v3_precision_experiment import PrecisionValidationAccumulator, _hash_tensor
from .v3_sample_budget_events import binding, encoded, physical, read_bound, write_once
from .v3_sample_budget_experiment import SampleBudgetPlan
from .v3_proxy_segments import ProxySegmentExperiment
from .v3_sampling import ConformationSelection, UniformMoleculeSampler
from .v3_structural import StructuralViewConfig
from .v3_trainer import SampleLRScheduler
from .v3_training import DEFAULT_SAMPLE_MILESTONES,SampleClock

ENGINEERING = 'ENGINEERING_SYNTHETIC_ONLY'
ROLES = ('VAL', 'TRAIN_UNSEEN_CONFORMATION')
REPOSITORY = Path(__file__).absolute().parents[3]
EXTRA_RUNTIME = ('tools/model_v3/run_proxy_experiment.py', 'tools/model_v3/a_execution_runtime.py',
    'tools/model_v3/runtime_monitor.py', 'tools/model_v3/private_runtime_storage.py',
    'tools/model_v3/run_supervised.py', 'workflows/sprime_s/scripts/s_model_memory_v1.py')


@dataclass(frozen=True)
class ProxyInputs:
    """Objects returned by a separately SHA-pinned, reviewed authority hook.

    Release verification remains that hook's responsibility. authority_receipt
    is opaque; this is a model protocol, not a fabricated physical D5 format.
    """
    index: object
    provider: object
    registry: object
    structural_binding: object
    normalizations: dict
    authority_receipt: dict
    validation_population_bindings: dict
    authority_kind: str
    release_accepted: bool
    verified_request_sha256: str = ''


def collect_sources(root=REPOSITORY):
    root = Path(root)
    paths = [*sorted((root/'current/phychem_mfm').rglob('*.py')), *(root/p for p in EXTRA_RUNTIME)]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def identity(configuration):
    # Only pretraining seed differs across a registered seed pair. Nested
    # validation/corruption seeds and all budget/source settings remain.
    return canonical_hash({key:value for key,value in configuration.items() if key != 'seed'})


def _git(root, *arguments):
    return subprocess.run(['git','-C',str(root),*arguments],check=True,stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).stdout.strip()


def validate_sources(request):
    source = request['sources']; expected = source['runtime_files']
    require(expected == collect_sources(), 'Actual runtime source inventory differs; base commit does not describe dirty engineering code')
    require(re.fullmatch('[a-f0-9]{40}',source['code_sha']) is not None, 'Full actual/base code SHA required')
    if request['mode'] == 'authoritative_proxy':
        require(_git(REPOSITORY,'rev-parse','HEAD') == source['code_sha']
            and _git(REPOSITORY,'rev-parse','HEAD^{tree}') == source['tree_sha']
            and not _git(REPOSITORY,'status','--porcelain','--untracked-files=all'),
            'Scientific execution requires this exact clean committed source/tree')
        require(source['state'] == 'clean_committed', 'Scientific source state differs')
    else:
        require(source['state'] == 'engineering_raw_inventory_not_claimed_in_base_commit', 'Engineering source provenance must be explicit')
    return canonical_hash(expected)


def _registration(reference, *, purpose, configuration):
    require(set(reference) == {'executed_local','public'}, 'Explicit local/public preregistration mapping required')
    local, public = reference['executed_local'], reference['public']
    policy,epoch = git_registration(local,expected_sha256=local['sha256'])
    require(set(public) == {'commit','tree'} and re.fullmatch('[a-f0-9]{40}',public['commit'])
        and _git(local['repository'],'rev-parse',local['commit']+'^{tree}') == public['tree'],
        'Executed local/public policy tree mapping differs')
    require(policy.get('schema') == 'model_v3_proxy_registered_policy_v1'
        and purpose in policy['purposes'] and policy['configuration_identity_sha256'] == identity(configuration)
        and configuration['seed'] in policy['pretraining_seeds'], 'Preregistered policy/configuration/seed differs')
    contract = configuration['proxy_contract']
    if purpose == 'budget': require(policy['sample_budget'] == contract['sample_budget'], 'Registered sample budget differs')
    if purpose == 'validation': require(policy['validation'] == contract['validation'], 'Registered validation policy differs')
    return {'reference':reference,'verified_local_commit_epoch':epoch,'policy_sha256':local['sha256'],
        'public_availability_is_Root_verified':True}


def validate_request(request, *, input_kind='authoritative_proxy', engineering_only=False):
    require(request.get('schema') == 'model_v3_proxy_request_v1', 'Explicit proxy request required')
    require(input_kind in ('authoritative_proxy','synthetic') and request['mode'] ==
        ('synthetic_engineering' if input_kind == 'synthetic' else 'authoritative_proxy'), 'CLI/request input scope differs')
    configuration = read_bound(request['configuration'])
    require(configuration.get('schema') == 'model_v3_proxy_configuration_v1'
        and type(configuration['seed']) is int and configuration['seed'] >= 0, 'Complete proxy configuration/seed required')
    engineering = request['mode'] == 'synthetic_engineering'
    require(engineering_only is engineering and configuration['engineering_only'] is engineering
        and (configuration['experiment_scope'] == ENGINEERING) is engineering,
        'Synthetic execution requires both --input synthetic and --engineering-only plus immutable markers')
    contract = configuration['proxy_contract']; model = configuration['model']
    require(model['backbone']['dim'] == 512 and (engineering or model['backbone']['layers'] == 6), 'Canonical scientific6x512 model required')
    require(engineering or request['scope'] in ('calibration','comparison','recipe'), 'Explicit registered scientific purpose required')
    require(contract['precision'] == {'mode':'fp32','matmul_tf32':False,'cudnn_tf32':False,'matmul_precision':'highest'},
        'First proxy runner supports declared strict fp32 only; no silent bf16/TF32 composition')
    require(contract['views'] in ('two','three') and contract['validation']['views'] == contract['views'],
        'Explicit matching training/validation view policy required; cross-view validation is not implemented')
    require(set(contract['validation']['population_bindings']) == set(ROLES)
        and type(contract['validation']['seed']) is int and contract['validation']['seed'] >= 0
        and type(contract['validation']['epoch']) is int and contract['validation']['epoch'] >= 0,
        'Both fixed validation populations/seed/epoch required')
    for sha in contract['validation']['population_bindings'].values():
        require(re.fullmatch('[a-f0-9]{64}',sha) is not None, 'Full validation membership binding required')
    groups = selected_groups(contract['groups']); require(groups, 'At least one enabled group required')
    plan = SampleBudgetPlan(**{**contract['sample_plan'],
        **{key:tuple(contract['sample_plan'][key]) for key in ('panel_samples','validation_samples','validation_roles')}})
    require(plan.sample_budget == contract['sample_budget'] and set(plan.validation_roles) == set(ROLES), 'Sample budget and two-role validation plan differ')
    from .v3_long_run_storage import enabled as long_enabled,policy as long_policy,validate_admission
    require((long_enabled(configuration) or plan.max_total_checkpoints <= 128) and set(plan.panel_samples) <= set(plan.validation_samples),
        'Bounded global checkpoint attempts and both-population validation at every panel point required')
    require(engineering or {n for n in DEFAULT_SAMPLE_MILESTONES if n <= plan.sample_budget} <= set(contract['milestones']),
        'Scientific clock must retain every original1/2/4/8/...M milestone within budget')
    resources = contract['resources']
    require(type(resources['joint_output_bytes']) is int and 256 << 20 <= resources['joint_output_bytes'] <= 2 << 30
        and 8 << 20 <= resources['ledger_bytes'] <= 32 << 20
        and resources['tracking_bytes'] >= 8 << 20
        and plan.max_segment_bytes+resources['tracking_bytes']+resources['ledger_bytes']+96*(1 << 20) <= resources['joint_output_bytes'],
        'Checkpoint/tracking/canonical-ledger/outer reserve must jointly fit original2GiB')
    source_sha = validate_sources(request)
    require(configuration['runtime_source_inventory_sha256'] == source_sha, 'Configuration runtime inventory differs')
    require(configuration['input_projection_sha256'] == canonical_hash(request['input_projection']), 'Configuration input projection differs')
    if long_enabled(configuration):
        long_policy(configuration,plan)
        validate_admission(request,configuration)
    receipts = {}
    if not engineering:
        required = {'budget','validation','calibration'} if request['scope'] == 'calibration' else {'budget','validation','selection','platform'}
        if request['scope'] == 'recipe': required.add('recipe')
        require(required <= set(request['registrations']), 'Missing explicit preregistered scope/budget/validation/decision references')
        receipts = {purpose:_registration(request['registrations'][purpose],purpose=purpose,configuration=configuration) for purpose in required}
        admission = read_bound(request['Root_admission'])
        require(admission.get('schema') == 'model_v3_proxy_Root_admission_v1'
            and admission['status'] == 'ROOT_ADMITTED_FINAL_INPUTS'
            and admission['configuration_identity_sha256'] == identity(configuration)
            and admission['scope'] == request['scope'] and admission['code_sha'] == request['sources']['code_sha']
            and admission['tree_sha'] == request['sources']['tree_sha']
            and admission['request_identity_sha256'] == canonical_hash({k:v for k,v in request.items() if k != 'Root_admission'}),
            'Missing/unfinished Root scientific admission or request projection differs')
        require({'D1','D2','D3','D4','D5','three_GPU_SDP_smoke'} <= set(admission['evidence']), 'Missing actual input/integration authority references')
        for reference in admission['evidence'].values(): binding_matches(reference)
    return configuration,plan,receipts


def binding_matches(reference):
    require(binding(reference['path']) == reference, 'Bound external authority/source bytes differ')


def bind_inputs(request, configuration):
    contract = configuration['proxy_contract']
    if request['mode'] == 'synthetic_engineering':
        from .v3_proxy_engineering import synthetic_proxy_inputs
        inputs = synthetic_proxy_inputs(views=contract['views'])
    else:
        ref = request['adapter']; binding_matches(ref)
        name = 'model_v3_proxy_adapter_'+ref['sha256']
        spec = importlib.util.spec_from_file_location(name,ref['path'])
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
        hook = getattr(module,'verify_and_bind_model_v3_proxy_inputs',None)
        require(callable(hook), 'Missing pinned final-D authority hook; candidate providers are not admitted')
        inputs = hook(deepcopy(request))
        require(isinstance(inputs,ProxyInputs) and inputs.authority_kind == 'data_line_final'
            and inputs.release_accepted is True and inputs.verified_request_sha256 == canonical_hash(request)
            and inputs.authority_receipt, 'Final-D authority hook did not verify this exact request')
        require(inputs.index.authority == inputs.registry.authority == 'data_line'
            and inputs.index.role == 'TRAIN' and len(inputs.index) == 240000,
            'Scientific proxy needs actual D5 240000 TRAIN molecules, never a record prefix')
    require(isinstance(inputs,ProxyInputs) and isinstance(inputs.registry,LabelRegistry)
        and inputs.index.version == inputs.provider.data_version == inputs.registry.version
        and inputs.provider.read_only is True and inputs.provider.node_local is True, 'Bound readonly node-local input projection required')
    require(callable(getattr(inputs.provider,'close',None)), 'Provider must expose deterministic close for bounded cleanup')
    require(inputs.validation_population_bindings == contract['validation']['population_bindings'], 'Actual validation memberships differ')
    actual = {'index_sha256':inputs.index.content_sha256,'registry_sha256':inputs.registry.content_sha256,
        'normalization_sha256':canonical_hash({k:asdict(v) for k,v in inputs.normalizations.items()}),
        'adapter_sha256':inputs.provider.source_sha256,'data_version':inputs.index.version}
    require(request['input_projection'] == actual, 'Registry/D4/D5/adapter/data projection differs')
    if request['mode'] == 'synthetic_engineering':
        require(inputs.authority_kind == 'synthetic_engineering' and inputs.release_accepted is False,
            'Engineering fixture cannot claim a final D release')
    return inputs


class ProxyStepTrainer(ArchitectureStepTrainer):
    """Unchanged original update/save/load; explicit validation context + SSE."""
    def __init__(self,*args,validation_policy,**kwargs):
        super().__init__(*args,**kwargs)
        self.validation_policy = deepcopy(validation_policy)
        self.contract['proxy_validation'] = self.validation_policy
        self.bindings['trainer_configuration_sha256'] = canonical_hash(self.contract)

    def _validate_population(self,role,batches):
        old,old_mode = self.view_config,self.model.training
        self.view_config = replace(old,seed=self.validation_policy['seed'],epoch=self.validation_policy['epoch'])
        seed = self.validation_policy['seed']
        torch.manual_seed(seed); np.random.seed(seed % 2**32); random.seed(seed)
        metric = PrecisionValidationAccumulator(self.model.registry,role=role,enabled_groups=self.groups,enabled_fields=self.fields)
        digest = hashlib.sha256(); actual = 0
        try:
            if batches is None:
                count,iterator = self.provider.validation_batches(role=role,view_config=self.view_config,enabled_groups=self.groups,enabled_fields=self.fields)
            else:
                require(type(batches) in (list,tuple),'Bounded explicit validation batches required')
                count,iterator = len(batches),iter(batches)
            require(type(count) is int and 0 < count <= self.validation_batch_cap,'Bounded full validation population required')
            with torch.no_grad():
                self.model.eval()
                for value in iterator:
                    if hasattr(self,'proxy_validation_guard'): self.proxy_validation_guard()
                    require(actual < count,'Validation exceeded declared population')
                    batch = self._prepared(value,role=role)
                    prediction,loss = self._forward_loss(batch)
                    predictions,targets = self._tables(prediction,batch)
                    metric.add(predictions,targets,loss)
                    for key,tensor in (('x',batch.views.batch.x),('pos',batch.views.batch.pos)):
                        _hash_tensor(digest,key,tensor)
                    for name in sorted(targets):
                        _hash_tensor(digest,name+'/values',targets[name].values)
                        _hash_tensor(digest,name+'/valid',targets[name].valid)
                        _hash_tensor(digest,name+'/pairs',targets[name].pair_index)
                    actual += 1
            require(actual == count,'Validation ended before declared population')
        finally:
            self.view_config = old; self.model.train(old_mode)
        result = metric.result()
        for field in self.model.registry.fields:
            if field.name not in result['fields']:
                result['fields'][field.name] = {'valid_labels':0,'loss':None,'MAE':None,'R2':None,'accuracy':None,'enabled':False,'metric_status':'INACTIVE'}
            else:
                item = result['fields'][field.name]; item['enabled'] = True
                item['metric_status'] = ('NO_VALID_LABELS' if item['valid_labels'] == 0 else 'CATEGORICAL_R2_MAE_NA'
                    if field.kind in ('binary','classification') else 'R2_CONSTANT_OR_INSUFFICIENT_LABELS' if item['R2'] is None else 'AVAILABLE')
        result.update(validation_seed=seed,validation_epoch=self.validation_policy['epoch'],
            population_binding_sha256=self.validation_policy['population_bindings'][role],input_population_sha256=digest.hexdigest())
        self.validation_state[role] = {'completed_runs':self.validation_state[role]['completed_runs']+1,'last_result':deepcopy(result)}
        self._log({'event':'VALIDATION','samples_consumed':self.clock.samples_consumed,'optimizer_updates':self.clock.optimizer_updates,**result})
        return result


def build_experiment(request,configuration,plan,inputs,tracker,*,output_root,lineage_root,lineage,device,
                     allow_unit_tracker=False):
    contract = configuration['proxy_contract']; seed = configuration['seed']
    torch.manual_seed(seed); np.random.seed(seed % 2**32); random.seed(seed)
    require(torch.get_float32_matmul_precision() == 'highest' and not torch.backends.cuda.matmul.allow_tf32
        and not torch.backends.cudnn.allow_tf32,'Effective precision differs from explicit request')
    encoder = build_architecture_model(configuration['model']).to(device)
    pd_registry = replace(inputs.registry,fields=tuple(f for f in inputs.registry.fields if f.group != 'S'))
    heads = V3HeadBank(pd_registry,**contract['heads']) if pd_registry.fields else None
    model_cls = V3TwoViewModel if contract['views'] == 'two' else V3MultiViewModel
    model = model_cls(encoder,heads,inputs.registry,inputs.structural_binding).to(device)
    optimizer = torch.optim.AdamW(model.parameters(),**contract['optimizer'])
    sampler = UniformMoleculeSampler(inputs.index,seed=seed,sample_budget=plan.sample_budget,
        selection=ConformationSelection(**contract['sampler']['selection']),geometry_source=contract['sampler']['geometry_source'])
    scheduler = SampleLRScheduler(optimizer,sample_budget=plan.sample_budget,**contract['schedule'])
    bindings = {'code_sha':request['sources']['code_sha'],'configuration_sha256':request['configuration']['sha256'],
        'registry_sha256':inputs.registry.source_sha256,'normalization_sha256':request['input_projection']['normalization_sha256'],
        'data_version':inputs.index.version,'proxy_runtime_sources_sha256':canonical_hash(request['sources']['runtime_files']),
        'proxy_scope':configuration['experiment_scope'],'proxy_engineering_only':configuration['engineering_only'],
        'proxy_execution_binding':contract['execution'],'proxy_authority_receipt_sha256':canonical_hash(inputs.authority_receipt)}
    trainer = ProxyStepTrainer(model,optimizer,scheduler,sampler,SampleClock(plan.sample_budget,tuple(contract['milestones'])),
        inputs.provider,inputs.normalizations,LossWeights(**contract['loss_weights']),tracker,bindings,
        enabled_groups=tuple(contract['groups']),enabled_fields=contract['fields'],
        view_config=StructuralViewConfig(seed=seed,**contract['training_view']),structural_views=contract['views'],
        validation_policy=contract['validation'],gradient_clip_norm=contract['clip_norm'],gradient_probe_interval=500,
        probe_samples=contract['probe_samples'],allow_unit_tracker=allow_unit_tracker,**contract['batch_limits'])
    controller_options = {}
    if 'long_run_policy' in configuration:
        from .v3_long_run_storage import controller_class
        controller_options['controller_factory'] = controller_class()
    return ProxySegmentExperiment(trainer,plan,output_root=output_root,lineage=lineage,
        input_scope='synthetic_fixture' if configuration['engineering_only'] else 'externally_supplied_adapter',
        model_configuration=request['configuration'],panel_binding=request['panel_binding'],
        panel_required=not configuration['engineering_only'],lineage_root=lineage_root,
        ledger_bytes=contract['resources']['ledger_bytes'],**controller_options)


def engineering_request(directory,*,code_sha,layers=1,budget=6,views='three',seed=7):
    """Prepare small explicit engineering metadata only; never starts a job."""
    from .v3_proxy_engineering import synthetic_proxy_inputs
    directory = physical(directory); directory.mkdir(parents=True,exist_ok=False)
    inputs = synthetic_proxy_inputs(views=views); sources = collect_sources()
    points = sorted({budget,*[n for n in (2,4) if n <= budget]})
    contract = {'sample_budget':budget,'milestones':points,'groups':['S','D','P'],'fields':None,'views':views,
        'heads':{'forms':'H1','hidden_dim':64},'optimizer':{'lr':.0003,'betas':[.9,.95],'weight_decay':.01,'eps':1e-8,'foreach':False,'fused':False},
        'schedule':{'mode':'cosine','warmup_samples':0,'decay_start_samples':None,'minimum_ratio':0.},
        'sampler':{'selection':{'mode':'all','k':None},'geometry_source':'PM7'},
        'precision':{'mode':'fp32','matmul_tf32':False,'cudnn_tf32':False,'matmul_precision':'highest'},
        'training_view':{'epoch':0,'topology_level':.3,'geometry_level':.2,'noise_seed_includes_epoch':True},
        'validation':{'seed':0,'epoch':0,'views':views,'population_bindings':inputs.validation_population_bindings},
        'batch_limits':{'max_molecules':2,'max_native_atoms':64,'max_padded_cost':10000},'clip_norm':1.,'probe_samples':1,
        'loss_weights':asdict(LossWeights()),'execution':{'device':'cpu','threads':1,'deterministic':True,'gpu_uuid':None,'gpu_name':None},
        'resources':{'joint_output_bytes':2 << 30,'ledger_bytes':16 << 20,'tracking_bytes':128 << 20,'rss_bytes':28 << 30},
        'sample_plan':asdict(SampleBudgetPlan(budget,tuple(points),tuple(points),ROLES,2,2,2,16,300,30,8 << 20,1536 << 20))}
    model = {'architecture':{'preset':'shared_light'},'backbone':{'dim':512,'layers':layers,'heads':8,'ff_mult':2 if layers == 6 else 1,'n_atom_types':119,'dropout':0.},
        'head':{'profile':'phase1','geometry_head':'equivariant_noise','geometry_hidden_dim':64 if layers == 6 else 32,'geometry_message_layers':0,'geometry_pair_chunk_size':8192}}
    projection = {'index_sha256':inputs.index.content_sha256,'registry_sha256':inputs.registry.content_sha256,
        'normalization_sha256':canonical_hash({k:asdict(v) for k,v in inputs.normalizations.items()}),
        'adapter_sha256':inputs.provider.source_sha256,'data_version':inputs.index.version}
    configuration = {'schema':'model_v3_proxy_configuration_v1','seed':seed,'model':model,'proxy_contract':contract,
        'experiment_scope':ENGINEERING,'engineering_only':True,'runtime_source_inventory_sha256':canonical_hash(sources),
        'input_projection_sha256':canonical_hash(projection)}
    config_ref = write_once(directory/'configuration.json',configuration)
    inputs.provider.close()
    request = {'schema':'model_v3_proxy_request_v1','mode':'synthetic_engineering','scope':'engineering','configuration':config_ref,
        'sources':{'code_sha':code_sha,'tree_sha':None,'state':'engineering_raw_inventory_not_claimed_in_base_commit','runtime_files':sources},
        'input_projection':projection,'registrations':{},'panel_binding':{'panel_sha256':canonical_hash({'engineering_panel':True}),
            'training_store_sha256':canonical_hash({'engineering_store':True}),'membership_sha256':{name:canonical_hash({'engineering':name}) for name in ('cyp_isoform','expansionrx','qm9')},
            'preregistration_sha':code_sha,'code_sha':code_sha}}
    return write_once(directory/'request.json',request)


def checkpoint_capacity(trainer):
    """Actual tensor floor and full-Adam planning scenario, not a size proof.

    Full AdamW moments are planned even before the first update. Unexecuted
    source heads can have no materialized moments, so that scenario is not an
    actual lower bound. Actual safe
    torch.save bytes are measured by the original COMPLETE receipts; both a
    cooperative census and RLIMIT_FSIZE constrain each attempted new payload.
    """
    tensors = [v for v in trainer.model.state_dict().values() if isinstance(v,torch.Tensor)]
    model = sum(v.numel()*v.element_size() for v in tensors)
    moments = sum(p.numel()*8 for p in trainer.model.parameters() if p.requires_grad)
    def tensor_bytes(value):
        if isinstance(value,torch.Tensor): return value.numel()*value.element_size()
        if isinstance(value,dict): return sum(tensor_bytes(v) for v in value.values())
        if isinstance(value,(tuple,list)): return sum(tensor_bytes(v) for v in value)
        return 0
    actual = tensor_bytes(trainer.optimizer.state_dict())
    scenario = model+moments
    return {'model_tensor_bytes':model,'full_AdamW_moment_tensor_bytes':moments,
        'materialized_optimizer_tensor_bytes':actual,'tensor_floor_bytes':model+actual,
        'full_AdamW_tensor_scenario_bytes':scenario,'planning_reserve_bytes':math.ceil(scenario*1.15)+(8 << 20),
        'serialization_upper_bound_proven':False,'excludes_extra_provider_state_and_metadata':True}
