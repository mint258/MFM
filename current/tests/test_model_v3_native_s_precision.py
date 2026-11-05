"""Native-S B scope/lifecycle tests; actual source interop is separately required."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import math

import pytest
import torch

from phychem_mfm.phase1.v3_contract import canonical_hash
from phychem_mfm.phase1.v3_native_s_precision import NativeSPrecisionPlan, NativeSPrecisionExperiment, compare_native_s_members
from phychem_mfm.phase1.v3_native_s_precision_data import SCOPE, bridge_native_corpus
from phychem_mfm.phase1.v3_native_s_precision_fixture import SyntheticNativeSInputs
from phychem_mfm.phase1.v3_precision_experiment import PrecisionValidationAccumulator
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v3_structural import StructuralViewConfig
from phychem_mfm.phase1.v3_training import capture_rng_state, restore_rng_state
from test_model_v3_trainer import UnitTracker
from test_model_v3_training import assert_tree_equal


@pytest.fixture(autouse=True)
def one_thread_rng():
    state, threads = capture_rng_state(), torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(threads)
        restore_rng_state(state)


def plan():
    return NativeSPrecisionPlan('synthetic_native_fixture', 4, 12, (0, 2, 4), (2, 4))


def experiment(seed=0, precision='fp32'):
    source = SyntheticNativeSInputs(seed=seed)
    tracker = UnitTracker(f'unit-native-{seed}-{precision}')
    engine = NativeSPrecisionExperiment(source, plan(), seed=seed, precision=precision, tracker=tracker,
        source_bindings={'prepared_test_source': 'a' * 64}, code_sha='b' * 40, prereg_sha='c' * 40,
        allow_unit_tracker=True)
    return engine


def test_native_scope_does_not_wait_for_D5_but_cannot_be_fixture():
    production = NativeSPrecisionPlan()
    assert production.input_scope == SCOPE and production.updates == 20000
    assert production.validation_updates == tuple(range(0, 20001, 500))
    with pytest.raises(ValueError):
        replace(production, updates=500)
    with pytest.raises(ValueError):
        replace(production, validation_updates=(500, 20000))
    with pytest.raises(ValueError, match='Real native'):
        NativeSPrecisionExperiment(SyntheticNativeSInputs(seed=0), production, seed=0, precision='fp32',
            tracker=UnitTracker(), source_bindings={'s': 'a' * 64}, code_sha='b' * 40,
            prereg_sha='c' * 40, allow_unit_tracker=True)


def test_bridge_preserves_original_batch_bonds_masks_targets_and_counts():
    source = SyntheticNativeSInputs(seed=0)
    corpus, prepared = source.next_train()
    assert prepared.views.batch is corpus.encoder_batch
    for field in ('x', 'pos', 'target_x', 'target_pos', 'element_corrupt_mask', 'rdkit_bond_index', 'rdkit_bond_order'):
        assert torch.equal(getattr(prepared.views.batch, field), getattr(corpus.encoder_batch, field))
    assert prepared.views.clean_graph_rows.tolist() == [0, 3, 6]
    assert len(prepared.views.clean_atom_rows) == sum(corpus.native_atom_counts)
    assert all(value.all() for value in prepared.views.graph_eligibility.values())
    assert all('synthetic_fixture' in choice.geometry_scope for choice in prepared.choices)
    broken = deepcopy(corpus)
    broken.encoder_batch.sample_type_id[0] = 2
    with pytest.raises(ValueError, match='view order'):
        bridge_native_corpus(broken, config=StructuralViewConfig(), data_version='fixture', role='TRAIN', fixture=True)
    wrong = (replace(prepared.choices[0], record_id='different_record'), *prepared.choices[1:])
    with pytest.raises(ValueError, match='identity sidecar'):
        bridge_native_corpus(corpus, config=StructuralViewConfig(), data_version='fixture', role='TRAIN', choices=wrong, fixture=True)


def test_explicit_uncommitted_prefetch_is_replayed_after_cursor_restore():
    source = SyntheticNativeSInputs(seed=0)
    first, _ = source.next_train()
    speculative, _ = source.next_train()
    assert source.samples_consumed == 0
    source.commit(first)
    state = source.state_dict()
    fresh = SyntheticNativeSInputs(seed=0)
    fresh.load_state_dict(state)
    replay, _ = fresh.next_train()
    assert replay.record_keys == speculative.record_keys and fresh.samples_consumed == 3


@pytest.mark.parametrize('precision', ['fp32', 'bf16'])
def test_real_cpu_training_safe_resume_matches_uninterrupted_every_parameter_and_Adam(precision, tmp_path):
    uninterrupted = experiment(precision=precision)
    complete = tmp_path / 'complete'
    complete.mkdir()
    uninterrupted.run(complete)
    uninterrupted_rng = capture_rng_state()
    segmented = experiment(precision=precision)
    first = tmp_path / 'first'
    first.mkdir()
    segmented.run(first, until_update=2)
    checkpoint = next(first.glob('checkpoint_u2_*'))
    payload = torch.load(checkpoint / 'payload.pt', map_location='cpu', weights_only=True)
    assert payload['clock']['optimizer_updates'] == 2
    resumed = experiment(precision=precision)
    resumed.load(checkpoint, output_root=first)
    tail = tmp_path / 'tail'
    tail.mkdir()
    result = resumed.run(tail)
    assert result['optimizer_updates'] == 4 and result['samples_consumed'] == 12
    assert resumed.points == uninterrupted.points and resumed.input_chain == uninterrupted.input_chain
    for name, value in uninterrupted.model.state_dict().items():
        assert torch.equal(value, resumed.model.state_dict()[name]), name
    for old, new in zip(uninterrupted.optimizer.state.values(), resumed.optimizer.state.values()):
        assert set(old) == set(new)
        assert all(torch.equal(old[key], new[key]) if isinstance(old[key], torch.Tensor) else old[key] == new[key] for key in old)
    assert_tree_equal(capture_rng_state(), uninterrupted_rng)


def test_u0_saved_and_resume_does_not_replay_initial_validation(tmp_path):
    engine = experiment()
    initial = tmp_path / 'initial'
    initial.mkdir()
    engine.run(initial, until_update=0)
    checkpoint = next(initial.glob('checkpoint_u0_*'))
    resumed = experiment()
    resumed.load(checkpoint, output_root=initial)
    initial_cursor = resumed.log_cursor
    assert set(resumed.points) == {'0'}
    tail = tmp_path / 'tail'
    tail.mkdir()
    resumed.run(tail, until_update=1)
    assert resumed.log_cursor == initial_cursor + 1


def test_wall_pause_publishes_committed_checkpoint_and_same_future_stream(tmp_path):
    engine = experiment()
    root = tmp_path / 'paused'
    root.mkdir()
    result = engine.run(root, pause_requested=lambda: engine.clock.optimizer_updates == 1)
    assert result['status'] == 'SEGMENT_PAUSED' and result['optimizer_updates'] == 1
    checkpoint = next(root.glob('checkpoint_u1_*'))
    resumed = experiment()
    resumed.load(checkpoint, output_root=root)
    assert resumed.inputs.read_cursor == resumed.inputs.committed == 1
    next_corpus, _ = resumed.inputs.next_train()
    assert next_corpus.record_keys == tuple(f'synthetic-1-{i}' for i in range(3))


def test_validation_preserves_all_rng_and_denominator_is_coordinate_components():
    engine = experiment()
    before = capture_rng_state()
    point = engine.validate()
    assert_tree_equal(capture_rng_state(), before)
    noise = point['population']['s_noise']
    assert noise['component_denominator'] == 3 * noise['valid_labels']
    assert noise['unit'] == 'angstrom' and noise['target_width'] == 3 and noise['sigma'] == .1


def test_validation_SSE_uses_all_components_and_masks_not_batch_mean_loss():
    field = FieldSpec('noise', 'S', 'structural', 'atom', kind='denoise_eps_mse', representation='vector', unit='angstrom')
    registry = LabelRegistry((field,), 'unit_fixture', 'a' * 64)
    metric = PrecisionValidationAccumulator(registry, role='VAL', enabled_groups=('S',))
    # Different batch sizes and a masked row make averaging field means wrong.
    for values, mask in (([[1., 2., 2.], [999., 999., 999.]], [True, False]),
                         ([[0., 0., 3.], [0., 0., 0.]], [True, True])):
        prediction = {'noise': torch.tensor(values)}
        targets = {'noise': FieldTarget(torch.zeros_like(prediction['noise']), torch.tensor(mask))}
        loss = compute_v3_loss(prediction, targets, registry, {}, enabled_groups=('S',))
        metric.add(prediction, targets, loss)
    row = metric.result()['fields']['noise']
    assert row['valid_labels'] == 3 and row['component_denominator'] == 9
    assert row['squared_error_sum'] == 18. and row['RMSE'] == math.sqrt(2.)
    assert row['vector_RMSE'] == math.sqrt(6.)
    assert row['eps_component_RMSE'] == row['RMSE'] / .1


@pytest.mark.parametrize('changed', ['seed', 'precision', 'source'])
def test_wrong_member_or_configuration_cannot_restore(tmp_path, changed):
    old = experiment()
    root = tmp_path / 'old'
    root.mkdir()
    old.run(root, until_update=0)
    checkpoint = next(root.glob('checkpoint_u0_*'))
    wrong = experiment(seed=1 if changed == 'seed' else 0, precision='bf16' if changed == 'precision' else 'fp32')
    if changed == 'source':
        wrong.bindings['source_inventory_sha256'] = 'e' * 64
    with pytest.raises(ValueError):
        wrong.load(checkpoint, output_root=root)


def test_all_original_S_fields_have_actual_nonzero_loss_and_valid_counts(tmp_path):
    engine = experiment()
    with torch.autocast('cpu', enabled=False):
        engine.step()
    assert engine.clock.optimizer_updates == 1
    row = engine.tracker.records[-1]
    for name in ('s_element', 's_noise', 's_bond'):
        assert row['valid_count/' + name] > 0
        assert row['loss/' + name] > 0


@pytest.mark.parametrize('precision', ['fp32', 'bf16'])
def test_first_actual_CPU_forward_records_selective_module_dtypes(precision):
    engine = experiment(precision=precision)
    engine.validate()
    selected = [row for row in engine.dtype_observations.values() if row['selective_backbone_matrix_module']]
    retained = [row for row in engine.dtype_observations.values() if not row['selective_backbone_matrix_module']]
    assert selected and retained
    assert all(row['device'] == 'cpu' for row in selected + retained)
    assert all(row['output_dtype'] == ('torch.bfloat16' if precision == 'bf16' else 'torch.float32') for row in selected)
    assert all(row['output_dtype'] == 'torch.float32' for row in retained)
    assert all(row['parameter_dtypes'] == ['torch.float32'] for row in selected + retained)


def test_four_members_require_paired_inputs_population_and_original_threshold(tmp_path):
    members = []
    for seed in (0, 1):
        for mode in ('fp32', 'bf16'):
            root = tmp_path / f'{seed}_{mode}'
            root.mkdir()
            members.append(experiment(seed, mode).run(root))
    result = compare_native_s_members(members)
    assert result['scientific_acceptance'] is False and result['D5_authority'] is False
    changed = deepcopy(members)
    changed[1]['training_input_chain_sha256'] = 'f' * 64
    with pytest.raises(ValueError, match='Paired'):
        compare_native_s_members(changed)
    changed = deepcopy(members)
    changed[1]['validation']['0']['population']['s_noise']['component_denominator'] += 1
    with pytest.raises(ValueError, match='counts'):
        compare_native_s_members(changed)
