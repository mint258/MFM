"""Repeated source records are one chemical unit for splits and uncertainty."""
from dataclasses import replace

import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
from phychem_mfm.phase1.v3_dev_evaluation import (TaskSpec, TaskPrediction, compare_panel,
    TaskMolecule, ridge_probe, error)


def chemical_key(index):
    return chr(65+index)*14 + '-ABCDEFGHIJ-A'


class SourceStore:
    def __init__(self, expansion=False):
        self.expansion = expansion; self.reads = []

    def contract(self, dataset, fold):
        fit = list(range(15)); held = [] if self.expansion else list(range(15, 20))
        return {'member_indices': {'train': fit, 'train_inner_validation': held},
                'ordered_members': {'train': [f'source:{i}' for i in fit],
                                    'train_inner_validation': [f'source:{i}' for i in held]},
                'tasks': ['3A4', '2D6'], 'output_level': 'atom'}

    def view(self, dataset, fold, *, role):
        return self.contract(dataset, fold)['member_indices'][role]

    def get(self, dataset, member):
        self.reads.append(member)
        raise AssertionError('No labels may be read while making cohort decisions')


def mapping(dataset, count=20):
    return {(dataset, i): {'member_uid': f'source:{i}', 'full_inchikey': chemical_key(i)} for i in range(count)}


def test_cross_isoform_duplicates_share_group_and_leaking_fit_members_are_purged():
    store = SourceStore(); groups = mapping('cyp_isoform')
    groups['cyp_isoform', 1]['full_inchikey'] = chemical_key(0)
    groups['cyp_isoform', 15]['full_inchikey'] = chemical_key(0)
    view = GroupedTrainingView(store, 'cyp_isoform', '0', groups, max_train_groups=2, max_validation_groups=2)
    assert view.membership['purged_optimization_member_indices'] == [0, 1]
    fit_groups = {view.molecule_group(i) for i in view.view('train')}
    valid_groups = {view.molecule_group(i) for i in view.view('train_inner_validation')}
    assert len(fit_groups) == len(valid_groups) == 2 and not fit_groups & valid_groups
    assert not store.reads


def test_missing_full_group_identity_is_rejected_instead_of_using_record_uid():
    store = SourceStore(); groups = mapping('cyp_isoform')
    groups.pop(('cyp_isoform', 2))
    with pytest.raises(ValueError, match='molecule identity'):
        GroupedTrainingView(store, 'cyp_isoform', '0', groups)
    assert not store.reads


def test_official_training_duplicates_cannot_straddle_expansion_inner_split():
    store = SourceStore(expansion=True); groups = mapping('expansionrx', 15)
    groups['expansionrx', 1]['full_inchikey'] = chemical_key(0)
    view = GroupedTrainingView(store, 'expansionrx', 'official', groups)
    assert (0 in view.view('train')) == (1 in view.view('train'))
    assert not ({view.molecule_group(i) for i in view.view('train')}
                & {view.molecule_group(i) for i in view.view('train_inner_validation')})
    assert not store.reads


def test_bootstrap_clusters_isoform_records_but_hit1_uses_each_native_record():
    task = TaskSpec('site', 'cyp_isoform', '3A4', 'atom', 'one_minus_hit1')
    candidate = TaskPrediction(task, ('chemicalA',)*4+('chemicalB',)*2,
        np.array([1., 0., 1., 0., 1., 0.]), np.array([.9, .1, .1, .9, .1, .9]),
        np.ones(6, dtype=bool), ('isoformA',)*2+('isoformB',)*2+('other',)*2)
    assert error(candidate) == pytest.approx(2/3)
    reference = replace(candidate, predictions=np.array([.1, .9, .1, .9, .1, .9]))
    result = compare_panel({'site': candidate}, {'site': reference}, architecture_sha256='same',
        reference_architecture_sha256='same', bootstrap_samples=20)
    assert result['tasks']['site']['observed_molecules'] == 2
    assert result['mean_normalized_improvement'] == pytest.approx(1/3)


def test_ridge_groups_duplicate_native_records_in_the_same_cv_fold():
    task = TaskSpec('regression', 'synthetic', 'y', 'graph', 'mae')
    rows = []
    for i in range(10):
        for repeated in range(2):
            h = torch.tensor([[float(i), 1.]])
            rows.append(TaskMolecule(f'molecule{i}', h, torch.tensor([0]), torch.tensor([2.*i+1.]),
                torch.tensor([True]), torch.tensor([True]), f'source{i}_{repeated}'))
    validation = tuple(replace(row, molecule_uid='held'+row.molecule_uid,
        source_member_uid='held'+row.source_member_uid) for row in rows[:2])
    prediction, metadata = ridge_probe(rows, validation, task)
    assert metadata['fold_assignment_sha256'] and error(prediction) < .001
