"""Synthetic acceptance of access boundaries and molecular inner evaluation."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v3_dev_panel import (TrainOnlyView, molecule_folds, audit_role_calls,
    NativeGeometry, FrozenH0Cache, encoder_state_sha256)
from phychem_mfm.phase1.v3_dev_evaluation import (TaskSpec, TaskMolecule, TaskPrediction,
    ridge_probe, nonlinear_probe, error, compare_panel, seed_standard_deviation)


class FakeStore:
    def __init__(self, dataset='qm9'):
        self.dataset = dataset; self.accesses = []

    def contract(self, dataset, fold):
        train = list(range(15))
        validation = [] if dataset == 'expansionrx' else list(range(15, 20))
        return {'member_indices': {'train': train, 'train_inner_validation': validation},
                'ordered_members': {'train': [f'm{i}' for i in train],
                                    'train_inner_validation': [f'm{i}' for i in validation]},
                'tasks': ['U0'], 'output_level': 'graph'}

    def view(self, dataset, fold, *, role):
        self.accesses.append(('view', role))
        assert role in ('train', 'train_inner_validation')
        return self.contract(dataset, fold)['member_indices'][role]

    def get(self, dataset, member):
        self.accesses.append(('get', member))
        if member >= 20:
            raise AssertionError('physical access outside the development population')
        return SimpleNamespace(member_uid=f'm{member}', dataset_id=dataset, member_index=member)


def test_denied_role_and_member_never_reach_physical_store():
    store = FakeStore(); view = TrainOnlyView(store, 'qm9', '0')
    before = list(store.accesses)
    with pytest.raises(ValueError):
        view.get(999, role='train')
    with pytest.raises(ValueError):
        view.get(0, role='final')
    with pytest.raises(ValueError):
        view.get(15, role='train')
    assert store.accesses == before
    assert view.get(15, role='train_inner_validation').member_uid == 'm15'


def test_expansion_inner_split_uses_only_original_training_members():
    store = FakeStore('expansionrx')
    first, second = TrainOnlyView(store, 'expansionrx', 'official'), TrainOnlyView(store, 'expansionrx', 'official')
    fit, valid = set(first.view('train')), set(first.view('train_inner_validation'))
    assert not fit & valid and fit | valid == set(range(15))
    assert len(valid) == 3 and first.membership_sha256 == second.membership_sha256
    assert not any(kind == 'get' for kind, _ in store.accesses)
    assignments = molecule_folds(['a', 'a', 'b', 'c', 'd', 'e'], folds=5)
    assert len(assignments) == 5 and len(set(assignments.values())) == 5


def test_static_guard_rejects_forbidden_roles_and_historical_entry_points(tmp_path):
    path = tmp_path / 'bad.py'
    path.write_text("provider.view('x','0',role='final')\nfrom old.formal_readout import evaluate_outer\n")
    assert len(audit_role_calls([path])) == 2
    root = Path(__file__).absolute().parents[1] / 'phychem_mfm/phase1'
    assert audit_role_calls([root / 'v3_dev_panel.py', root / 'v3_dev_evaluation.py']) == []


class TinyEncoder(torch.nn.Module):
    latent_dim = 512

    def __init__(self):
        super().__init__(); self.emb = torch.nn.Embedding(119, 512); self.calls = 0

    def encode_atoms(self, batch):
        self.calls += 1
        assert set(batch.keys()) <= {'x', 'pos', 'batch', 'ptr'}
        return self.emb(batch.x.reshape(-1))


def test_h0_is_cached_once_without_targets_and_encoder_is_frozen(tmp_path):
    torch.manual_seed(9); encoder = TinyEncoder().train()
    records = [NativeGeometry('synthetic', f'm{i}', i, torch.tensor([[5], [0]]),
                torch.tensor([[0., 0., 0.], [1., 0., 0.]]), torch.tensor([0, 1])) for i in range(4)]
    cache = FrozenH0Cache(tmp_path / 'external-cache', repository_root=tmp_path / 'repo')
    before = encoder_state_sha256(encoder)
    first, metadata = cache.get_or_compute(encoder, records, architecture_sha256='a'*64, membership_sha256='b'*64)
    second, _ = cache.get_or_compute(encoder, records, architecture_sha256='a'*64, membership_sha256='b'*64)
    assert encoder.calls == 1 and encoder.training and encoder_state_sha256(encoder) == before
    assert first[0].h0.shape == (2, 512) and not first[0].h0.requires_grad
    assert all(torch.equal(a.h0, b.h0) for a, b in zip(first, second))
    assert metadata['targets_cached'] is False
    with pytest.raises(ValueError):
        FrozenH0Cache(tmp_path / 'repo/cache', repository_root=tmp_path / 'repo')


def molecules(prefix, count, *, offset=0., atom=False):
    rows = []
    for i in range(count):
        x = float(i+1)+offset
        h = torch.tensor([[x, 1., x/5., 0.], [x+1., 0., x/7., 1.]], dtype=torch.float32)
        target = torch.tensor([1., 0.]) if atom else torch.tensor([2.*float(h[:, 0].mean())+1.])
        mask = torch.ones(len(target), dtype=torch.bool)
        rows.append(TaskMolecule(f'{prefix}{i}', h, torch.tensor([0, 1]), target, mask, mask))
    return tuple(rows)


def test_ridge_selects_alpha_on_optimization_only_and_is_affine_unit_correct():
    task = TaskSpec('synthetic', 'synthetic', 'value', 'graph', 'mae')
    fit, held = molecules('fit', 15), molecules('held', 5, offset=20.)
    prediction, metadata = ridge_probe(fit, held, task, alphas=(1e-6, .01, 100.))
    assert error(prediction) < .001
    shifted = tuple(replace(row, targets=row.targets+1000.) for row in held)
    changed, shifted_meta = ridge_probe(fit, shifted, task, alphas=(1e-6, .01, 100.))
    assert metadata['selected_alpha'] == shifted_meta['selected_alpha']
    assert np.array_equal(prediction.predictions, changed.predictions)
    assert metadata['normalization_fit_scope'] == 'train'


def test_site_metric_and_bootstrap_count_repeated_molecule_draws():
    task = TaskSpec('som', 'synthetic', 'site', 'atom', 'one_minus_hit1')
    prediction = TaskPrediction(task, ('a', 'a', 'b', 'b'), np.array([1., 0., 1., 0.]),
        np.array([.9, .1, .1, .9]), np.ones(4, dtype=bool))
    assert error(prediction) == .5
    assert error(prediction, [0, 1, 0, 1, 2, 3]) == pytest.approx(1/3)
    reference = replace(prediction, predictions=np.array([.1, .9, .1, .9]))
    result = compare_panel({'som': prediction}, {'som': reference}, architecture_sha256='a',
        reference_architecture_sha256='a', bootstrap_samples=20)
    assert result['bootstrap_unit'] == 'molecule'
    assert result['mean_normalized_improvement'] == .5
    assert result['tasks']['som']['observed_molecules'] == 2
    with pytest.raises(ValueError):
        compare_panel({'som': prediction}, {'som': reference}, architecture_sha256='a', reference_architecture_sha256='b')


def test_auroc_ties_and_unavailable_reference_are_explicit():
    task = TaskSpec('binary', 'synthetic', 'binary', 'graph', 'one_minus_auroc')
    prediction = TaskPrediction(task, ('a', 'b'), np.array([0., 1.]), np.array([.5, .5]), np.ones(2, dtype=bool))
    assert error(prediction) == .5
    perfect = replace(prediction, predictions=np.array([0., 1.]))
    result = compare_panel({'binary': prediction}, {'binary': perfect}, architecture_sha256='same',
        reference_architecture_sha256='same', bootstrap_samples=10)
    assert not result['complete'] and result['mean_normalized_improvement'] is None
    assert seed_standard_deviation([1., 3.], scientific_configuration_hashes=['a', 'a']) == pytest.approx(2**.5)
    with pytest.raises(ValueError):
        seed_standard_deviation([1., 3.], scientific_configuration_hashes=['a', 'b'])


class Tracker:
    def __init__(self):
        self.rows = []

    def log(self, row, *, step, commit):
        assert commit is True and step == len(self.rows)
        self.rows.append(row)


def test_existing_source_aligned_readout_uses_fixed_endpoint_and_masks_nan():
    task = TaskSpec('synthetic', 'synthetic', 'value', 'graph', 'mae')
    fit = list(molecules('fit', 8))
    fit[0] = replace(fit[0], targets=torch.tensor([float('nan')]), supervision_mask=torch.tensor([False]))
    held = molecules('held', 3, offset=2.)
    tracker = Tracker()
    before = torch.random.get_rng_state().clone()
    prediction, metadata = nonlinear_probe(fit, held, task, tracker=tracker)
    assert metadata['epochs'] == 20 and metadata['batch_graphs'] == 32
    assert metadata['updates'] == len(tracker.rows) == 20
    assert metadata['encoder_updated'] is False and np.isfinite(prediction.predictions).all()
    assert torch.equal(before, torch.random.get_rng_state())
