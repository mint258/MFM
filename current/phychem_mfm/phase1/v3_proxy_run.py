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
    'tools/model_v3/run_supervised.py', 'tools/model_v3/prepare_recipe_experiment.py',
    'tools/model_v3/run_wsd_fork.py',
    'workflows/sprime_s/scripts/s_model_memory_v1.py')


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
    full_train_contract: dict | None = None
    grid_train_contract: dict | None = None

    @property
    def physical_policy(self):
        return getattr(self, "_physical_loss_policy", None)

    def with_physical_policy(self, policy):
        from .v3_physical_policy import PhysicalLossPolicy
        require(isinstance(policy, PhysicalLossPolicy), "Typed physical-loss policy required")
        policy.validate_for_registry(self.registry, enabled_fields=())
        value = replace(self)
        object.__setattr__(value, "_physical_loss_policy", policy)
        return value


def collect_sources(root=REPOSITORY):
    root = Path(root)
    paths = [*sorted((root/'current/phychem_mfm').rglob('*.py')), *(root/p for p in EXTRA_RUNTIME)]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def identity(configuration):
    # The original identity keeps its exact seed-only exclusion. New routing
    # semantics require this explicit version in the preregistered configuration.
    version = configuration.get('recipe_identity_schema')
    require(version in (None, 'model_v3_training_recipe_identity_v2'), 'Unknown recipe identity projection')
    value = {key:deepcopy(item) for key,item in configuration.items() if key != 'seed'}
    if version is not None:
        # UUID/model-name routing is operational, while device, threads, numeric
        # policy, batch budget and all model/data/source settings remain bound.
        # Actual UUID/name remain in configuration rawref, request/Root admission,
        # trainer bindings and the exact workload capacity profile qualification.
        runtime = value['proxy_contract']['execution']
        runtime.pop('gpu_uuid', None)
        runtime.pop('gpu_name', None)
    return canonical_hash(value)


def _git(root, *arguments):
    return subprocess.run(['git','-C',str(root),*arguments],check=True,stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).stdout.strip()


def validate_sources(request):
    source = request['sources']; expected = source['runtime_files']
    require(expected == collect_sources(), 'Actual runtime source inventory differs; base commit does not describe dirty engineering code')
    require(re.fullmatch('[a-f0-9]{40}',source['code_sha']) is not None, 'Full actual/base code SHA required')
    if request['mode'] in ('authoritative_proxy','authoritative_full_train','authoritative_grid_train'):
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
    if purpose == 'full_train': require(policy.get('full_train_contract') == configuration['full_train_contract'], 'Registered full TRAIN population differs')
    if purpose == 'training_execution':
        from .v3_training_execution import TrainingExecutionSpec
        require(TrainingExecutionSpec(**policy['training_execution']).semantic()
            == TrainingExecutionSpec(**configuration['training_execution']).semantic(),
            'Registered training execution differs')
    if purpose == 'grid_cell':
        require(policy.get('grid_train_contract') == configuration['grid_train_contract'], 'Registered exact grid cell differs')
        for key in ('frozen_model', 'frozen_recipe'):
            artifact_ref = policy.get(key)
            require(type(artifact_ref) is dict, 'Grid policy must bind actual frozen model/recipe rawrefs')
            binding_matches(artifact_ref)
    return {'reference':reference,'verified_local_commit_epoch':epoch,'policy_sha256':local['sha256'],
        'public_availability_is_Root_verified':True}


def validate_request(request, *, input_kind='authoritative_proxy', engineering_only=False):
    require(request.get('schema') == 'model_v3_proxy_request_v1', 'Explicit proxy request required')
    require(input_kind in ('authoritative_proxy','authoritative_full_train','authoritative_grid_train','synthetic') and request['mode'] ==
        ('synthetic_engineering' if input_kind == 'synthetic' else input_kind), 'CLI/request input scope differs')
    full_train = input_kind == 'authoritative_full_train'
    grid_train = input_kind == 'authoritative_grid_train'
    configuration = read_bound(request['configuration'])
    require(configuration.get('schema') == 'model_v3_proxy_configuration_v1'
        and type(configuration['seed']) is int and configuration['seed'] >= 0, 'Complete proxy configuration/seed required')
    engineering = request['mode'] == 'synthetic_engineering'
    require(engineering_only is engineering and configuration['engineering_only'] is engineering
        and (configuration['experiment_scope'] == ENGINEERING) is engineering,
        'Synthetic execution requires both --input synthetic and --engineering-only plus immutable markers')
    contract = configuration['proxy_contract']; model = configuration['model']
    require(configuration.get('recipe_identity_schema') in (None, 'model_v3_training_recipe_identity_v2'),
        'Unknown recipe identity projection')
    require(model['backbone']['dim'] == 512 and (engineering or model['backbone']['layers'] == 6), 'Canonical scientific6x512 model required')
    scopes = ('grid_cell',) if grid_train else ('full_convergence',) if full_train else ('calibration','comparison','recipe')
    require(engineering or request['scope'] in scopes, 'Explicit registered scientific purpose required')
    require('performance_execution_v1' not in model, 'Use the declared training_execution consumer; a plain factory must not ignore execution')
    if grid_train:
        from .v3_grid_training import validate_grid_contract
        grid = validate_grid_contract(configuration)
        require(request['input_projection']['index_sha256'] == grid['membership_sha256'], 'Grid request/index membership differs')
    if full_train:
        from .v3_full_training import validate_full_contract
        full=validate_full_contract(configuration)
        require(request['input_projection']['index_sha256'] == full['membership_sha256'],'Full TRAIN request/index population differs')
    declared_precision = contract['precision']
    require(declared_precision in ({'mode': mode, 'matmul_tf32': False, 'cudnn_tf32': False, 'matmul_precision': 'highest'}
        for mode in ('fp32', 'bf16')), 'Explicit selective precision/no TF32 policy required')
    require('training_execution' not in model, 'Training execution belongs to the top-level configuration')
    if 'training_execution' in configuration:
        from .v3_training_execution import TrainingExecutionSpec
        execution = TrainingExecutionSpec(**configuration['training_execution']).semantic()
        require(execution['options']['precision'] == declared_precision['mode']
            and execution['batch_padded_cost'] == contract['batch_limits']['max_padded_cost'],
            'Actual training precision/padded budget differs from declared execution')
        operational = request.get('training_execution_admission')
        if execution['checkpoint_policy'] == 'auto_closed_training_profile_v1':
            require(type(operational) is dict and set(operational) == {'schema', 'capacity_profile'}
                and operational['schema'] == 'model_v3_training_execution_admission_v1',
                'Auto training requires a bound actual training-specific capacity profile')
            binding_matches(operational['capacity_profile'])
        else:
            require(operational is None, 'Manual execution does not silently consume an automatic profile')
    else:
        require(declared_precision['mode'] == 'fp32' and request.get('training_execution_admission') is None,
            'Selective precision or capacity requires its explicit training execution consumer')
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
        require(type(request.get('long_run')) is dict,'Fresh finite Root storage/profile/quota/reservation refs required')
        limits=long_policy(configuration,plan)
        if full_train:
            resource=configuration['full_resource_contract']
            require(resource['durable_upper_bytes'] == limits['durable_bytes']
                and resource['checkpoint_upper_bytes'] == limits['checkpoint_bytes']
                and resource['profile_evidence'] == request['long_run']['profile'], 'Full storage declaration/profile differs from actual durable admission')
        validate_admission(request,configuration)
    receipts = {}
    if not engineering:
        required = ({'budget','validation','grid_cell'} if grid_train else {'budget','validation','recipe','full_train'} if full_train else
            {'budget','validation','calibration'} if request['scope'] == 'calibration' else {'budget','validation','selection','platform'})
        if request['scope'] == 'recipe': required.add('recipe')
        if 'training_execution' in configuration: required.add('training_execution')
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
        required_data = {'D1','D2','D3','D4','D6' if full_train or grid_train else 'D5','three_GPU_SDP_smoke'}
        require(required_data <= set(admission['evidence']), 'Missing actual input/integration authority references')
        if full_train: require(admission['evidence']['D6'] == configuration['full_train_contract']['release_evidence'], 'Root D6 release binding differs')
        if grid_train: require(admission['evidence']['D6'] == configuration['grid_train_contract']['release_evidence'], 'Root grid base release binding differs')
        if 'training_execution' in configuration:
            require('training_execution' in admission['evidence'], 'Missing actual accepted execution/source evidence')
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
        hook_name = ('verify_and_bind_model_v3_grid_TRAIN_inputs' if request['mode'] == 'authoritative_grid_train'
                      else 'verify_and_bind_model_v3_full_TRAIN_inputs' if request['mode'] == 'authoritative_full_train'
                     else 'verify_and_bind_model_v3_proxy_inputs')
        hook = getattr(module,hook_name,None)
        require(callable(hook), 'Missing pinned final-D authority hook; candidate providers are not admitted')
        inputs = hook(deepcopy(request))
        require(isinstance(inputs,ProxyInputs) and inputs.authority_kind == 'data_line_final'
            and inputs.release_accepted is True and inputs.verified_request_sha256 == canonical_hash(request)
            and inputs.authority_receipt, 'Final-D authority hook did not verify this exact request')
        require(inputs.index.authority == inputs.registry.authority == 'data_line', 'Final data-line index/registry authority required')
        if request['mode'] == 'authoritative_grid_train':
            from .v3_grid_training import verify_grid_inputs
            verify_grid_inputs(inputs, configuration)
        elif request['mode'] == 'authoritative_full_train':
            from .v3_full_training import verify_full_inputs
            verify_full_inputs(inputs,configuration)
        else:
            require(inputs.index.role == 'TRAIN' and len(inputs.index) == 240000,
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
    declared_physical = configuration.get('physical_policy_reference')
    require((declared_physical is None) == (inputs.physical_policy is None),
        'Declared physical-policy reference and bound consumer must agree')
    if declared_physical is not None:
        binding_matches(declared_physical)
        require(inputs.physical_policy.reference == declared_physical,
            'Actual physical policy differs from sealed configuration')
        from .v3_losses import loss_prediction_fields
        loss_prediction_fields(inputs.registry, inputs.normalizations, enabled_groups=contract['groups'],
            enabled_fields=contract['fields'], physical_policy=inputs.physical_policy)
    if request['mode'] == 'synthetic_engineering':
        require(inputs.authority_kind == 'synthetic_engineering' and inputs.release_accepted is False,
            'Engineering fixture cannot claim a final D release')
    return inputs


class ProxyStepTrainer(ArchitectureStepTrainer):
    """Unchanged original update/save/load; explicit validation context + SSE."""
    def __init__(self,*args,validation_policy,**kwargs):
        super().__init__(*args,**kwargs)
        self.validation_policy = deepcopy(validation_policy)
        self.recipe_initial_validation = False
        self.contract['proxy_validation'] = self.validation_policy
        self.bindings['trainer_configuration_sha256'] = canonical_hash(self.contract)

    def next_step(self,count):
        # Only the new selected-recipe SDP route requests a full initial cohort.
        # Original validate() preserves provider/RNG and runs the same guards.
        if self.recipe_initial_validation and self.clock.samples_consumed == 0:
            for role in ROLES:
                if self.validation_state[role]['completed_runs'] == 0:
                    self.validate(role)
        if hasattr(self,'recipe_phase_observer'): self.recipe_phase_observer('TRAIN_STEP')
        return super().next_step(count)
    def _validate_population(self,role,batches):
        if hasattr(self,'recipe_phase_observer'): self.recipe_phase_observer('VALIDATION')
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
            self._execution_validation_begin(role, count)
            with torch.no_grad():
                self.model.eval()
                for value in iterator:
                    if hasattr(self,'proxy_validation_guard'): self.proxy_validation_guard()
                    require(actual < count,'Validation exceeded declared population')
                    batch = self._prepared(value,role=role)
                    prediction,loss = self._forward_loss(batch)
                    execution_snapshot = self._execution_capture(role)
                    predictions,targets = self._tables(prediction,batch)
                    metric.add(predictions,targets,loss)
                    for key,tensor in (('x',batch.views.batch.x),('pos',batch.views.batch.pos)):
                        _hash_tensor(digest,key,tensor)
                    for name in sorted(targets):
                        _hash_tensor(digest,name+'/values',targets[name].values)
                        _hash_tensor(digest,name+'/valid',targets[name].valid)
                        _hash_tensor(digest,name+'/pairs',targets[name].pair_index)
                    self._execution_complete(execution_snapshot)
                    actual += 1
            require(actual == count,'Validation ended before declared population')
            self._execution_validation_complete(role)
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


def _workload_authority(request, configuration):
    evidence = {}
    if not configuration['engineering_only']:
        admission = read_bound(request['Root_admission'])
        population = 'D6' if request['mode'] in ('authoritative_full_train', 'authoritative_grid_train') else 'D5'
        evidence = {key: deepcopy(admission['evidence'][key]) for key in ('D1', 'D2', 'D4', population)}
    # Resource/auto-policy/Root admission revisions cannot alter the data identity.
    return {'kind': 'synthetic_engineering' if configuration['engineering_only'] else 'data_line_final',
        'release_accepted': not configuration['engineering_only'], 'data_release_evidence': evidence}


def _workload_projection(request, configuration, data):
    """Reconstruct numerical training settings from bound request/config metadata."""
    from .v3_contract import FieldSpec, TrainNormalization
    c = configuration['proxy_contract']
    require(type(data) is dict and set(data) == {'registry_sha256', 'normalization_sha256', 'data_version',
        'authority_sha256', 'selection', 'input_projection', 'validation_population_bindings',
        'registry_projection', 'normalization_projection'},
        'Exact producer registry/normalization/authority workload projection required')
    projection = data['registry_projection']
    registry = LabelRegistry(tuple(FieldSpec(**f) for f in projection['fields']), projection['version'],
        projection['source_sha256'], projection['authority'])

    norms = {name: TrainNormalization(**row) for name, row in data['normalization_projection'].items()}
    registry_sha = canonical_hash(asdict(registry))
    norm_sha = canonical_hash({name: asdict(value) for name, value in norms.items()})
    expected_authority = 'synthetic_fixture' if configuration['engineering_only'] else 'data_line'
    authority = _workload_authority(request, configuration)

    require(registry.authority == expected_authority and registry.version == request['input_projection']['data_version']
        and registry_sha == request['input_projection']['registry_sha256']
        and norm_sha == request['input_projection']['normalization_sha256'],
        'Workload registry/normalization metadata differs from actual request projection')
    expected_data = {'registry_sha256': registry_sha, 'normalization_sha256': norm_sha,
        'data_version': registry.version, 'authority_sha256': canonical_hash(authority),
        'selection': deepcopy(c['sampler']), 'input_projection': deepcopy(request['input_projection']),
        'validation_population_bindings': deepcopy(c['validation']['population_bindings']),
        'registry_projection': asdict(registry),
        'normalization_projection': {name: asdict(value) for name, value in norms.items()}}

    return {'schema': 'model_v3_training_workload_v1',
        'scope': ('engineering_synthetic_fixture' if configuration['engineering_only'] else
            'authoritative_grid_cell' if request['mode'] == 'authoritative_grid_train' else request['mode']),
        'seed': configuration['seed'], 'model_configuration': deepcopy(configuration['model']), 'data': expected_data,
        'groups': list(selected_groups(c['groups'])),
        'fields': [f.name for f in registry.enabled(c['groups'], c['fields'])],
        'heads': deepcopy(c['heads']), 'views': c['views'] if 'S' in c['groups'] else 'one',
        'view_policy': {'training': deepcopy(c['training_view']), 'precision': deepcopy(c['precision']),
            'schedule': deepcopy(c['schedule']), 'sample_budget': c['sample_budget'],
            'batch_limits': deepcopy(c['batch_limits'])},
        'loss': {'weights': deepcopy(c['loss_weights']), 'clip_norm': c['clip_norm']},
        'optimizer': deepcopy(c['optimizer']), 'validation': deepcopy(c['validation'])}


def validate_training_workload_request(workload, request, configuration):
    """Pure metadata qualifier used by both this producer and SA1's consumer.

    Actual provider authority was verified by bind_inputs in the qualified
    producer. This validator reconstructs all numerical settings, registry and
    TRAIN normalization content hashes without reopening targets or a provider.
    Root/source/SDK/terminal qualification stays the consumer's responsibility.
    """
    require(request.get('schema') == 'model_v3_proxy_request_v1'
        and request['configuration']['sha256'] == binding(request['configuration']['path'])['sha256']
        and read_bound(request['configuration']) == configuration,
        'Workload must bind the actual invoked immutable request/configuration')
    require(canonical_hash(_workload_projection(request, configuration, workload['data'])) == canonical_hash(workload),
        'Saved training workload differs from the actual invoked numerical/input contract')


def training_workload_binding(request, configuration, inputs):
    data = {'registry_sha256': inputs.registry.content_sha256,
        'normalization_sha256': request['input_projection']['normalization_sha256'],
        'data_version': inputs.index.version,
        'authority_sha256': canonical_hash(_workload_authority(request, configuration)),

        'selection': deepcopy(configuration['proxy_contract']['sampler']),
        'input_projection': deepcopy(request['input_projection']),
        'validation_population_bindings': deepcopy(inputs.validation_population_bindings),
        'registry_projection': asdict(inputs.registry),
        'normalization_projection': {name: asdict(value) for name, value in inputs.normalizations.items()}}
    workload = _workload_projection(request, configuration, data)
    require(canonical_hash(workload['data']) == canonical_hash(data), 'Actual provider projection differs from workload request')
    validate_training_workload_request(workload, request, configuration)
    return workload


def build_experiment(request,configuration,plan,inputs,tracker,*,output_root,lineage_root,lineage,device,
                     allow_unit_tracker=False):
    contract = configuration['proxy_contract']; seed = configuration['seed']
    torch.manual_seed(seed); np.random.seed(seed % 2**32); random.seed(seed)
    require(torch.get_float32_matmul_precision() == 'highest' and not torch.backends.cuda.matmul.allow_tf32
        and not torch.backends.cudnn.allow_tf32,'Effective precision differs from explicit request')
    execution_handle = None
    if 'training_execution' in configuration:
        from .v3_training_execution import build_training_encoder
        workload = training_workload_binding(request, configuration, inputs)
        execution_handle = build_training_encoder(configuration['model'], execution=configuration['training_execution'],
            workload_binding=workload, operational_admission=request.get('training_execution_admission'))
        encoder = execution_handle.encoder.to(device)
    else:
        encoder = build_architecture_model(configuration['model']).to(device)
    pd_registry = replace(inputs.registry,fields=tuple(f for f in inputs.registry.fields if f.group != 'S'))
    heads = V3HeadBank(pd_registry,**contract['heads']) if pd_registry.fields else None
    model_cls = V3TwoViewModel if contract['views'] == 'two' else V3MultiViewModel
    model = model_cls(encoder,heads,inputs.registry,inputs.structural_binding).to(device)
    if execution_handle is None:
        optimizer = torch.optim.AdamW(model.parameters(), **contract['optimizer'])
    else:
        from .v3_training_execution import make_training_optimizer, finalize_training_execution
        optimizer = make_training_optimizer(model, contract['optimizer'], execution_handle)
        finalize_training_execution(model, optimizer, execution_handle)
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
        probe_samples=contract['probe_samples'],allow_unit_tracker=allow_unit_tracker,
        training_execution=execution_handle,
        **({"physical_policy": inputs.physical_policy} if inputs.physical_policy is not None else {}),
        **contract['batch_limits'])
    trainer.recipe_initial_validation = request['scope'] == 'recipe' and tuple(contract['groups']) == ('S','D','P')
    controller_options = {}
    if 'long_run_policy' in configuration:
        from .v3_long_run_storage import controller_class
        controller_options['controller_factory'] = controller_class()
    return ProxySegmentExperiment(trainer,plan,output_root=output_root,lineage=lineage,
        input_scope='synthetic_fixture' if configuration['engineering_only'] else 'externally_supplied_adapter',
        model_configuration=request['configuration'],panel_binding=request['panel_binding'],
        panel_required=not configuration['engineering_only'],lineage_root=lineage_root,
        ledger_bytes=contract['resources']['ledger_bytes'],**controller_options)


def finalize_training_request(candidate_ref, registrations, admission, output, *, operational=None):
    """Use the actual shared admission/provider path; never bless a candidate."""
    request = deepcopy(read_bound(candidate_ref))
    require(operational is None or type(operational) is dict
        and set(operational) <= {'long_run', 'training_execution_admission'},
        'Only explicit durable/capacity operational refs may be supplied')
    if operational is not None:
        request.update(deepcopy(operational))
    request.update(registrations=deepcopy(registrations), Root_admission=deepcopy(admission))
    configuration, _, _ = validate_request(request, input_kind=request['mode'])
    inputs = bind_inputs(request, configuration)
    try:
        return write_once(output, request)
    finally:
        inputs.provider.close()


def engineering_request(directory,*,code_sha,layers=1,budget=6,views='three',seed=7,
                        training_execution=None,groups=('S','D','P')):
    """Prepare small explicit engineering metadata only; never starts a job."""
    from .v3_proxy_engineering import synthetic_proxy_inputs
    directory = physical(directory); directory.mkdir(parents=True,exist_ok=False)
    inputs = synthetic_proxy_inputs(views=views); sources = collect_sources()
    groups = list(selected_groups(groups)); require(groups, 'Engineering run needs selected groups')
    points = sorted({budget,*[n for n in (2,4) if n <= budget]})
    contract = {'sample_budget':budget,'milestones':points,'groups':groups,'fields':None,'views':views,
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
    if training_execution is not None:
        from .v3_training_execution import TrainingExecutionSpec
        policy = TrainingExecutionSpec(**training_execution).semantic()
        require(policy['batch_padded_cost'] == contract['batch_limits']['max_padded_cost'],
            'Engineering execution budget must equal the actual proxy batch budget')
        configuration['training_execution'] = policy
        contract['precision']['mode'] = policy['options']['precision']
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
