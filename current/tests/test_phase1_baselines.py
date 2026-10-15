import numpy as np
import pytest
import torch
from torch_geometric.data import Data

from phychem_mfm.phase1.baselines import TrainingBaselines, RegressionMeter
from phychem_mfm.phase1.evaluation import OriginalUnitEvaluator
from phychem_mfm.model.outputs import PretrainOutputs
from phychem_mfm.training.data import fast_collate
from types import SimpleNamespace


def molecule(atoms, energy, charges, charge_mask=None):
    return Data(x=torch.tensor(atoms).view(-1, 1), pos=torch.zeros(len(atoms), 3),
                energy=torch.tensor([float(energy)]), energy_mask=torch.tensor([1.]),
                y=torch.tensor(charges).view(-1, 1),
                charge_mask=torch.tensor(charge_mask if charge_mask is not None else [1.] * len(atoms)).view(-1, 1))


def test_original_units_training_fitted_controls_and_missing_charge():
    training = [molecule([0, 0, 5], 12, [.1, .1, -.2]), molecule([0, 5], 10, [.3, 999.], [1., 0.]),
                molecule([0, 0, 5, 5], 20, [.2, .2, -.4, -.4])]
    baseline = TrainingBaselines().fit(training, train_manifest={"role": "train", "sha256": "train-only"})
    for record in training:
        np.testing.assert_allclose(baseline.energy(record), record.energy.item(), atol=1e-10)
    assert baseline.charge_means[5] == pytest.approx(-1 / 3)
    assert baseline.charge_counts[5] == 3
    with pytest.raises(ValueError, match="training manifest"):
        TrainingBaselines().fit(training, train_manifest={"role": "validation"})


def test_regression_aggregates_labels_rather_than_batch_means():
    meter = RegressionMeter()
    meter.add([1.], [0.])
    meter.add([3., 3., 3.], [0., 0., 0.])
    assert meter.result()["mae"] == 2.5
    assert meter.result()["count"] == 4


def test_energy_baseline_supports_scalar_lmdb_values_and_real_collation():
    training = [molecule([0, 0, 5], 12, [.1, .1, -.2]), molecule([0, 5], 10, [.3, -.4]),
                molecule([0, 0, 5, 5], 20, [.2, .2, -.4, -.4])]
    for record in training:
        record.energy = float(record.energy)
        record.sample_type_id = torch.tensor([0])
        record.rdkit_node_estate_index = torch.zeros(len(record.x), 1)
    baseline = TrainingBaselines().fit(training, train_manifest={"role": "train"})
    batch = fast_collate(training[:2])
    output = PretrainOutputs(atom_repr=torch.zeros(5, 8), graph_repr=torch.zeros(2, 8),
                             energy_pred=torch.tensor([[13.], [9.]]))
    evaluator = OriginalUnitEvaluator(SimpleNamespace(), baseline)
    evaluator.add(batch, output)
    energy = evaluator.result()["targets"]["energy_kcal_per_mol"]
    assert energy["model"]["mae"] == 1.
    assert energy["baseline"]["mae"] == pytest.approx(0., abs=1e-10)
    assert energy["model"]["count"] == 2


def test_missing_training_baseline_does_not_hide_model_metric():
    record = molecule([0, 5], 10, [.3, -.4])
    record.sample_type_id = torch.tensor([0])
    record.rdkit_graph_desc = torch.zeros(1, 31)
    record.rdkit_graph_desc[0, 0] = 2.
    record.rdkit_graph_desc_mask = torch.zeros(1, 31)
    record.rdkit_graph_desc_mask[0, 0] = 1.
    batch = fast_collate([record])
    baseline = TrainingBaselines()
    model = SimpleNamespace(graph_descriptor_names=("MolLogP",), graph_descriptor_target_indices=(0,))
    output = PretrainOutputs(atom_repr=torch.zeros(2, 8), graph_repr=torch.zeros(1, 8), graph_descriptor_pred=torch.tensor([[3.]]))
    evaluator = OriginalUnitEvaluator(model, baseline)
    evaluator.add(batch, output)
    metric = evaluator.result()["targets"]["D/MolLogP"]
    assert metric["model"]["mae"] == 1.
    assert metric["baseline"]["status"].startswith("unavailable")


def test_element_scores_only_legal_targets_but_counts_padding_prediction_as_error():
    record = molecule([0] * 6, 10, [0.] * 6)
    record.sample_type_id = torch.tensor([2])
    record.target_x = torch.tensor([[0.], [94.], [-1.], [2.5], [float("nan")], [5.]])
    record.element_corrupt_mask = torch.ones(6, 1, dtype=torch.bool)
    batch = fast_collate([record])
    logits = torch.zeros(1, 6, 95)
    logits[0, 0, 0] = 1.
    logits[0, 5, 94] = 1.
    output = PretrainOutputs(atom_repr=torch.zeros(6, 8), graph_repr=torch.zeros(1, 8), element_logits=logits)
    evaluator = OriginalUnitEvaluator(SimpleNamespace(), TrainingBaselines(n_atom_types=95))
    evaluator.add(batch, output)
    metric = evaluator.result()["targets"]["element"]
    assert metric["model"]["count"] == metric["baseline"]["count"] == 2
    assert metric["model"]["accuracy"] == .5
    assert np.asarray(metric["model"]["confusion"])[94].sum() == 0
    assert metric["model"]["confusion"][5][94] == 1


def test_geometry_counts_unique_unordered_pairs_with_padding_and_local_cutoff():
    first = molecule([0, 0, 5], 10, [0., 0., 0.])
    second = molecule([0, 5], 10, [0., 0.])
    clean = molecule([0, 5], 10, [0., 0.])
    first.pos = torch.tensor([[0., 0., 0.], [1., 0., 0.], [3., 0., 0.]])
    second.pos = torch.tensor([[0., 0., 0.], [1., 0., 0.]])
    clean.pos = second.pos.clone()
    for record, view in ((first, 1), (second, 1), (clean, 0)):
        record.sample_type_id = torch.tensor([view])
        record.target_pos = record.pos.clone()
    batch = fast_collate([first, second, clean])
    predicted = torch.zeros(3, 3, 3)
    predicted[0, :3] = first.pos * 2.
    predicted[1, :2] = second.pos * 2.
    predicted[1, 2] = torch.tensor([100., 100., 100.])  # Padding is excluded.
    predicted[2, :2] = clean.pos * 100.  # Clean geometry is excluded.
    output = PretrainOutputs(atom_repr=torch.zeros(7, 8), graph_repr=torch.zeros(3, 8), coordinate_pred=predicted)
    evaluator = OriginalUnitEvaluator(SimpleNamespace(), TrainingBaselines(), cutoff=2.)
    evaluator.add(batch, output)
    report = evaluator.result()
    all_pairs = report["targets"]["geometry_all_pair_A"]
    local_pairs = report["targets"]["geometry_local_pair_A"]
    assert all_pairs["model"]["count"] == all_pairs["baseline"]["count"] == 4
    assert all_pairs["model"]["mae"] == pytest.approx(1.75)
    assert all_pairs["baseline"]["mae"] == 0.
    assert local_pairs["model"]["count"] == local_pairs["baseline"]["count"] == 2
    assert local_pairs["model"]["mae"] == pytest.approx(1.)
    assert report["geometry_pair_count_semantics"].startswith("unique unordered")


def test_element_majority_is_fit_on_train_corrupted_targets_despite_many_hydrogens():
    clean = molecule([0] * 20 + [5, 5, 6], 10, [0.] * 23)
    topology = clean.clone()
    topology.target_x = clean.x.clone()
    topology.x[-3:, 0] = torch.tensor([7, 7, 5])
    topology.element_corrupt_mask = topology.x.ne(topology.target_x).any(dim=1).view(-1, 1)
    topology.sample_type_id = torch.tensor([2])
    task_baseline = TrainingBaselines().fit([clean], train_manifest={"role": "train", "sha256": "train-only"},
                                            element_records=[topology])
    assert task_baseline.element_majority == 5
    assert task_baseline.provenance["element_majority_source"] == "train_topology_actual_corrupted_target_x"
    assert task_baseline.provenance["element_fit_labels"] == 3
    assert task_baseline.provenance["element_fit_view_records"] == 1
    assert task_baseline.provenance["element_class_counts"] == {"5": 2, "6": 1}
    targets = topology.target_x[topology.element_corrupt_mask].numpy()
    assert (targets == task_baseline.element_majority).mean() == pytest.approx(2 / 3)
    compatibility_baseline = TrainingBaselines().fit([clean], train_manifest={"role": "train"})
    assert compatibility_baseline.element_majority == 0
    assert compatibility_baseline.provenance["element_majority_source"].endswith("compatibility_only")


def test_element_baseline_rejects_stale_corruption_mask_and_excludes_reserved_target():
    clean = molecule([0, 5], 10, [0., 0.])
    topology = clean.clone()
    topology.sample_type_id = torch.tensor([2])
    topology.target_x = torch.tensor([[94], [5]])
    topology.x = torch.tensor([[0], [7]])
    topology.element_corrupt_mask = torch.ones(2, 1, dtype=torch.bool)
    baseline = TrainingBaselines().fit([clean], train_manifest={"role": "train"}, element_records=[topology])
    assert baseline.element_majority == 5
    assert baseline.provenance["element_fit_labels"] == 1
    assert baseline.provenance["element_rejected_corrupted_targets"] == 1
    topology.element_corrupt_mask.zero_()
    with pytest.raises(ValueError, match="actual input changes"):
        TrainingBaselines().fit([clean], train_manifest={"role": "train"}, element_records=[topology])
