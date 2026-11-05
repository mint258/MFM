"""Independent existing-native-S B scope; the original D5 protocol is unchanged."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import re
from pathlib import Path
import random
import time
import numpy as np
import torch

from .v3_contract import canonical_hash, require
from .v3_native_s_precision_data import ExistingNativeSInputs, SCOPE, VAL_ROLE
from .v3_precision_experiment import PrecisionValidationAccumulator, curve_point, _hash_tensor, write_new_json
from .v3_trainer import V3StepTrainer, SampleLRScheduler, _preserve_rng, _tracker, _execution_state
from .v3_training import SampleClock, save_new_checkpoint, load_checkpoint, shared_backbone_gradient_norms
from ..model.v3_multiview import V3MultiViewModel
from ..model.v3_performance import PerformanceOptions, build_performance_model, execution_context, make_adamw
from ..training.losses import LossWeights
from ..training.v3_performance_acceptance import bf16_curve_report


@dataclass(frozen=True)
class NativeSPrecisionPlan:
    input_scope: str = SCOPE
    updates: int = 20000
    sample_budget: int = 10240000
    validation_updates: tuple = tuple(range(0, 20001, 500))
    checkpoint_updates: tuple = (10000, 20000)
    warmup_samples: int = 0

    def __post_init__(self):
        require(self.input_scope in (SCOPE, 'synthetic_native_fixture'), 'Explicit native-S or fixture scope required')
        require(type(self.updates) is int and self.updates > 0 and type(self.sample_budget) is int
                and self.sample_budget >= self.updates and 0 <= self.warmup_samples < self.sample_budget,
                'Explicit update/sample schedule bounds required')
        for grid in (self.validation_updates, self.checkpoint_updates):
            require(type(grid) is tuple and grid == tuple(sorted(set(grid))) and grid
                    and all(type(value) is int and 0 <= value <= self.updates for value in grid)
                    and grid[-1] == self.updates, 'Complete fixed update grid required')
        require(self.validation_updates[0] == 0, 'Initial untrained validation point required')
        if self.input_scope == SCOPE:
            require(self.updates == 20000 and self.sample_budget == 10240000
                    and self.validation_updates == tuple(range(0, 20001, 500)),
                    'Existing-S B is20000 optimizer updates with original validation grid; samples do not replace updates')

    @property
    def sha256(self):
        return canonical_hash(asdict(self))


class NativeSPrecisionExperiment:
    """One real precision/seed member with committed-cursor safe checkpoints."""
    groups = ('S',)

    def __init__(self, inputs, plan, *, seed, precision, tracker, source_bindings, code_sha,
                 prereg_sha, device='cpu', allow_unit_tracker=False, runtime_binding=None, storage_policy_binding=None):
        require(seed in (0, 1) and type(seed) is int and precision in ('fp32', 'bf16'), 'Exactly four paired members')
        require(isinstance(plan, NativeSPrecisionPlan) and inputs.seed == seed, 'Source/member seed or plan differs')
        if plan.input_scope == SCOPE:
            require(type(inputs) is ExistingNativeSInputs and inputs.scope == SCOPE and torch.device(device).type == 'cuda',
                    'Real native-S inputs and actual CUDA required; no fixture substitution')
            bb = inputs.model_configuration['backbone']
            require((bb['dim'], bb['layers'], bb['heads']) == (512, 6, 8), 'Real B primary architecture512x6 required')
        else:
            require(inputs.scope == 'synthetic_native_fixture', 'Fixture must remain explicitly synthetic')
        require(source_bindings and all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) for value in source_bindings.values()),
                'Complete source inventory required')
        require(all(type(value) is str and re.fullmatch('[0-9a-f]{40}', value) for value in (code_sha, prereg_sha)), 'Actual/public source commits required')
        self.inputs, self.plan, self.seed, self.precision = inputs, plan, seed, precision
        self.options = PerformanceOptions(precision=precision, backbone_checkpointing=True)
        self.device = torch.device(device)
        torch.manual_seed(seed)
        np.random.seed(seed)
        random.seed(seed)
        encoder = build_performance_model(inputs.model_configuration, self.options).to(device)
        self.model = V3MultiViewModel(encoder, None, inputs.registry, inputs.structural_binding)
        self.optimizer = make_adamw(self.model, {'lr': 3e-4, 'betas': [.9, .95], 'weight_decay': .01}, self.options)
        self.scheduler = SampleLRScheduler(self.optimizer, sample_budget=plan.sample_budget, warmup_samples=plan.warmup_samples)
        self.clock = SampleClock(plan.sample_budget, ())
        self.weights = LossWeights.from_mapping(inputs.loss_mapping)
        self.fields = tuple(field.name for field in inputs.registry.fields)
        self.tracker, self.tracker_identity = tracker, _tracker(tracker, allow_unit_tracker)
        self.log_cursor, self.pending_log, self.resume_parent = 0, None, None
        self.points, self.saved_updates = {}, []
        self.training_step_seconds = 0.
        self.segment_training_samples = 0
        self.input_chain = canonical_hash({'scope': plan.input_scope, 'seed': seed})
        self.dtype_observations = {}
        self.common = {'plan': asdict(plan), 'source_files': dict(source_bindings), 'code_sha': code_sha,
            'prereg_sha': prereg_sha, 'data_version': inputs.data_version, 'registry': inputs.registry.content_sha256,
            'model': inputs.model_configuration, 'loss_weights': asdict(self.weights),
            'loss_semantics': 'V3_S_mean_of_observed_original_raw_fields; not_legacy_weighted_total',
            'schedule': self.scheduler.contract, 'runtime': dict(runtime_binding or {}),
            'Root_storage_policy': deepcopy(storage_policy_binding or {}),
            'base_options': asdict(replace(self.options, precision='fp32')),
            'source_scope': inputs.scope, 'validation_role': VAL_ROLE, 'validation_seed': 0, 'validation_epoch': 0,
            'D5_authority': False, 'TRAIN_UNSEEN_CONFORMATION': 'NOT_PROVIDED'}
        self.contract = {**self.common, 'seed': seed, 'precision': precision,
            'input_binding': deepcopy(inputs.bindings), 'sampler_contract_sha256': inputs.sampler.content_sha256,
            'execution': _execution_state(self.model)}
        self.bindings = {'code_sha': code_sha, 'configuration_sha256': canonical_hash(self.contract),
            'registry_sha256': inputs.registry.source_sha256, 'normalization_sha256': canonical_hash({}),
            'data_version': inputs.data_version, 'source_inventory_sha256': canonical_hash(source_bindings)}

    def _log(self, row):
        require(self.pending_log is None, 'Pending tracking record blocks new work')
        self.pending_log = {**row, 'log_cursor': self.log_cursor}
        if self.resume_parent is not None:
            self.pending_log['resume_parent_run_id'] = self.resume_parent['id']
        self.flush_pending_log()

    def flush_pending_log(self):
        if self.pending_log is not None:
            require(self.tracker.step <= self.log_cursor, 'SDK ahead of safe log cursor; use a fresh lineage')
            self.tracker.log(self.pending_log, step=self.log_cursor, commit=True)
            self.pending_log = None
            self.log_cursor += 1

    def _forward(self, prepared):
        batch = prepared.to(self.device)
        # Observe a real first forward; hooks retain only dtype signatures.
        # This checks Linear/LayerNorm module boundaries. QK/AV matmul kernels
        # still need the independent CUDA audit before production admission.
        hooks = []
        if not self.dtype_observations:
            for name, module in self.model.named_modules():
                if module.__class__.__name__ not in ('Linear', 'LayerNorm'):
                    continue
                selected = bool(re.fullmatch(r'encoder\.backbone\.layers\.\d+\.(attn\.(qkv|proj)|ffn\.net\.\d+)', name))
                expected = torch.bfloat16 if self.precision == 'bf16' and selected else torch.float32
                def observe(layer, args, output, name=name, expected=expected, selected=selected):
                    require(isinstance(output, torch.Tensor) and output.dtype == expected,
                            'Selective precision module dtype differs: ' + name)
                    self.dtype_observations[name] = {'output_dtype': str(output.dtype), 'device': output.device.type,
                        'selective_backbone_matrix_module': selected,
                        'parameter_dtypes': sorted({str(p.dtype) for p in layer.parameters()})}
                    require(all(p.dtype == torch.float32 for p in layer.parameters()), 'Parameter dtype changed')
                hooks.append(module.register_forward_hook(observe))
        try:
            with torch.autocast(device_type=self.device.type, enabled=False):
                prediction = self.model.forward_pretrain(batch.views, enabled_groups=self.groups)
                loss = self.model.compute_loss(prediction, batch.views, {}, {}, enabled_groups=self.groups,
                    weights=self.weights, exposure_step=self.clock.samples_consumed)
        finally:
            for hook in hooks:
                hook.remove()
        require(bool(torch.isfinite(loss.total)), 'Nonfinite native precision loss')
        return batch, prediction, loss

    def _tables(self, prediction, prepared):
        return V3StepTrainer._tables(self, prediction, prepared)

    def step(self):
        require(self.pending_log is None, 'Pending history blocks update')
        corpus, prepared = self.inputs.next_train()
        count = len(prepared.choices)
        require(count <= self.clock.max_next_samples(count), 'Native input would exceed explicit sample budget')
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        batch, prediction, loss = self._forward(prepared)
        tables = self._tables(prediction, batch)
        metrics = V3StepTrainer._field_metrics(self, *tables, loss)
        observed = any(value > 0 for value in loss.counts.values())
        require(observed and loss.total.requires_grad, 'Native S batch has no effective supervision; cannot advance20000 update protocol')
        probe = {}
        if observed:
            update = self.clock.optimizer_updates + 1
            if update % 500 == 0:
                with _preserve_rng():
                    _, _, probe_loss = self._forward(self.inputs.probe_train(corpus))
                    probe = shared_backbone_gradient_norms(probe_loss.groups, self.model.encoder.backbone.parameters(),
                                                          optimizer_update=update, interval=500)
                    require(all(math.isfinite(value) for value in probe.values()), 'Nonfinite native gradient probe')
            loss.total.backward()
            norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.)
            require(bool(torch.isfinite(norm)) and all(bool(torch.isfinite(p.grad).all())
                for p in self.model.parameters() if p.grad is not None), 'Nonfinite native gradient')
            self.optimizer.step()
        else:
            norm = None
        # Hash actual source inputs before commit. Never hash predictions as population.
        digest = hashlib.sha256()
        for name in ('x', 'pos', 'target_x', 'target_pos', 'sample_type_id', 'element_corrupt_mask', 'rdkit_bond_index', 'rdkit_bond_order'):
            _hash_tensor(digest, name, getattr(prepared.views.batch, name, None))
        step_sha = canonical_hash({'records': [asdict(choice) for choice in prepared.choices], 'tensors': digest.hexdigest()})
        self.inputs.commit(corpus)
        self.clock.advance(count, optimizer_updated=observed)
        self.scheduler.set_consumed(self.clock.samples_consumed)
        require(self.inputs.sampler.samples_consumed == self.clock.samples_consumed, 'Native committed clocks differ')
        self.input_chain = canonical_hash({'previous': self.input_chain, 'input': step_sha,
                                          'samples': self.clock.samples_consumed, 'updates': self.clock.optimizer_updates})
        self._log({'event': 'TRAIN', 'optimizer_updates': self.clock.optimizer_updates, 'samples_consumed': self.clock.samples_consumed,
            'loss': float(loss.total.detach()), 'preclip_gradient_norm': None if norm is None else float(norm),
            'input_sha256': step_sha, 'committed_input_chain_sha256': self.input_chain,
            'valid_counts': dict(loss.counts), **metrics, **probe})

    def validate(self):
        previous = self.model.training
        digest, records = hashlib.sha256(), 0
        # Internal accumulator's VAL enum is a math API alias. The actual source
        # and published point role are always original PRETRAIN_VAL, never D5.
        accumulator = PrecisionValidationAccumulator(self.model.registry, role='VAL', enabled_groups=self.groups)
        try:
            with _preserve_rng(), torch.no_grad():
                torch.manual_seed(0)
                np.random.seed(0)
                random.seed(0)
                self.model.eval()
                with closing(self.inputs.validation_batches()) as iterator:
                    for prepared in iterator:
                        batch, prediction, loss = self._forward(prepared)
                        predictions, targets = self._tables(prediction, batch)
                        accumulator.add(predictions, targets, loss)
                        digest.update(canonical_hash([asdict(choice) for choice in prepared.choices]).encode())
                        for name in ('x', 'pos', 'target_x', 'target_pos', 'sample_type_id', 'element_corrupt_mask'):
                            _hash_tensor(digest, name, getattr(prepared.views.batch, name, None))
                        for name in sorted(targets):
                            _hash_tensor(digest, name + ':target', targets[name].values)
                            _hash_tensor(digest, name + ':valid', targets[name].valid)
                        for name in ('pair_index', 'pair_graph_index', 'existence_target', 'order_target'):
                            _hash_tensor(digest, 'bond:' + name, getattr(prediction.source_outputs.bond, name))
                        records += len(prepared.choices)
            require(records == self.inputs.bindings['validation_records'], 'Incomplete fixed validation population')
            result = accumulator.result()
            result.update(role=VAL_ROLE, validation_seed=0, validation_epoch=0, records=records,
                input_population_sha256=digest.hexdigest(), optimizer_updates=self.clock.optimizer_updates)
            point = curve_point(result, self.model.structural_binding.noise)
            point['role'] = VAL_ROLE
            self._log({'event': 'VALIDATION', 'optimizer_updates': self.clock.optimizer_updates,
                       'samples_consumed': self.clock.samples_consumed, **result})
            return point
        finally:
            self.model.train(previous)

    def save(self, path, *, output_root):
        require(self.pending_log is None, 'Only acknowledged tracking state can be published')
        extra = {'contract': self.contract, 'scheduler': self.scheduler.state_dict(), 'points': deepcopy(self.points),
            'saved_updates': sorted(set([*self.saved_updates, self.clock.optimizer_updates])), 'log_cursor': self.log_cursor,
            'input_chain': self.input_chain, 'tracker': self.tracker_identity, 'model_training': self.model.training,
            'dtype_observations': deepcopy(self.dtype_observations)}
        marker = save_new_checkpoint(path, output_root=output_root, model=self.model, optimizer=self.optimizer,
            sampler=self.inputs.sampler, clock=self.clock, bindings=self.bindings, extra_state=extra)
        self.saved_updates = extra['saved_updates']
        return marker

    def load(self, path, *, output_root):
        extra = load_checkpoint(path, output_root=output_root, model=self.model, optimizer=self.optimizer,
            sampler=self.inputs.sampler, clock=self.clock, expected_bindings=self.bindings)
        require(extra['contract'] == self.contract, 'Native precision member contract differs')
        self.scheduler.load_state_dict(extra['scheduler'])
        self.points, self.saved_updates = extra['points'], extra['saved_updates']
        self.log_cursor, self.input_chain, self.resume_parent = extra['log_cursor'], extra['input_chain'], extra['tracker']
        self.model.train(extra['model_training'])
        self.dtype_observations = extra['dtype_observations']

    def run(self, root, *, until_update=None, guard=None, pause_requested=None):
        root = Path(root)
        target = self.plan.updates if until_update is None else until_update
        require(root.is_dir() and type(target) is int and self.clock.optimizer_updates <= target <= self.plan.updates,
                'Fresh segment root and explicit advancing update endpoint required')
        if self.plan.input_scope == SCOPE:
            require(callable(guard), 'Root bounded resource/storage admission hook required for real native-S')
        self.flush_pending_log()
        def events():
            update = self.clock.optimizer_updates
            if update in self.plan.validation_updates and str(update) not in self.points:
                if guard:
                    guard('validation', self)
                self.points[str(update)] = self.validate()
            if update in self.plan.checkpoint_updates and update not in self.saved_updates:
                if guard:
                    guard('checkpoint', self)
                self.save(root / f'checkpoint_u{update}_log{self.log_cursor}', output_root=root)
        with execution_context(self.options):
            events()
            while self.clock.optimizer_updates < target:
                # An operational boundary never consumes a speculative batch.
                # Publish the complete committed state before the outer wall.
                if pause_requested is not None and pause_requested():
                    break
                tick, previous_samples = time.perf_counter(), self.clock.samples_consumed
                if guard:
                    guard('step', self)
                self.step()
                self.training_step_seconds += time.perf_counter() - tick
                self.segment_training_samples += self.clock.samples_consumed - previous_samples
                events()
            endpoint = self.clock.optimizer_updates
            if endpoint not in self.saved_updates:
                if guard:
                    guard('checkpoint', self)
                self.save(root / f'checkpoint_u{endpoint}_log{self.log_cursor}', output_root=root)
        result = {'schema': 'existing_native_S_precision_member_v1', 'scope': self.plan.input_scope,
            'status': 'UPDATES_COMPLETE_PENDING_OUTER_TERMINAL' if endpoint == self.plan.updates else 'SEGMENT_PAUSED',
            'seed': self.seed, 'precision': self.precision, 'optimizer_updates': self.clock.optimizer_updates,
            'samples_consumed': self.clock.samples_consumed, 'training_input_chain_sha256': self.input_chain,
            'common_binding': self.common, 'member_contract': self.contract, 'validation': deepcopy(self.points),
            'tracker': self.tracker_identity, 'resume_parent': self.resume_parent, 'scientific_acceptance': False,
            'D5_authority': False, 'SDK_and_Slurm_closure': 'REQUIRED_INDEPENDENTLY'}
        result['dtype_observation'] = {'module_boundary_signatures': self.dtype_observations,
            'scope': 'actual_Linear_LayerNorm_outputs_and_fp32_parameters; QK_AV_kernels_need_independent_CUDA_audit',
            'actual_device': self.device.type, 'CUDA_acceptance': False}
        result['segment_throughput'] = {'base_records': self.segment_training_samples,
            'training_step_wall_seconds': self.training_step_seconds,
            'base_records_per_second': self.segment_training_samples / self.training_step_seconds if self.training_step_seconds else None,
            'scope': 'includes_step_guard_source_wait_forward_backward_probe_optimizer_hash_and_SDK; excludes_validation_checkpoint_initialization'}
        write_new_json(root / 'member_result.json', result)
        return result


def compare_native_s_members(members):
    require(len(members) == 4 and {(member['seed'], member['precision']) for member in members}
        == {(seed, mode) for seed in (0, 1) for mode in ('fp32', 'bf16')}, 'Four true training members required')
    require(len({member['tracker']['id'] for member in members}) == 4, 'Four distinct final tracking lineages required')
    common = members[0]['common_binding']
    plan_data = common['plan']
    plan = NativeSPrecisionPlan(**{**plan_data, 'validation_updates': tuple(plan_data['validation_updates']),
                                 'checkpoint_updates': tuple(plan_data['checkpoint_updates'])})
    for member in members:
        require(member['common_binding'] == common and member['optimizer_updates'] == plan.updates
            and member['scope'] == plan.input_scope and member['member_contract']['seed'] == member['seed']
            and member['member_contract']['precision'] == member['precision']
            and member['status'] == 'UPDATES_COMPLETE_PENDING_OUTER_TERMINAL'
            and set(member['validation']) == {str(value) for value in plan.validation_updates},
            'Incomplete or different native precision source/plan/population')
    for seed in (0, 1):
        pair = [member for member in members if member['seed'] == seed]
        require(pair[0]['samples_consumed'] == pair[1]['samples_consumed']
            and pair[0]['training_input_chain_sha256'] == pair[1]['training_input_chain_sha256']
            and pair[0]['member_contract']['sampler_contract_sha256'] == pair[1]['member_contract']['sampler_contract_sha256'],
            'Paired precision training source/cursor order differs')
    reference_point = members[0]['validation']
    for member in members:
        for update, value in member['validation'].items():
            original = reference_point[update]
            require(value['role'] == VAL_ROLE and value['population'] == original['population']
                and value['input_population_sha256'] == original['input_population_sha256']
                and value['validation_noise_seed'] == value['validation_epoch'] == 0,
                'Actual validation units/counts/inputs/masks/pairs differ')
    runs = {mode: [{'seed': member['seed'], 'optimizer_updates': member['optimizer_updates'],
        'validation': {int(update): point['metrics'] for update, point in member['validation'].items()}}
        for member in members if member['precision'] == mode] for mode in ('fp32', 'bf16')}
    result = bf16_curve_report(runs['fp32'], runs['bf16'], validation_updates=plan.validation_updates,
        denoise_metric='s_noise/RMSE', required_updates=plan.updates)
    return {'scope': plan.input_scope, 'numeric_gate': result, 'scientific_acceptance': False,
            'D5_authority': False, 'required_independent_evidence': 'all segments source/Slurm/supervisor/nativeSDK/actualCUDA dtype/storage closure'}
