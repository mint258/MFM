"""Independent physical-unit/count/resume oracles; synthetic CPU data only.

No native corpus or downstream target files are consumed. The root executes
these on a compute node against the actual overlaid modules, not on Windows.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch_geometric.data import Data

from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.model.outputs import BondOutputs, PretrainOutputs
from phychem_mfm.model.phase1_specs import (PHASE1_GRAPH_DESCRIPTOR_NAMES,
    PHASE1_CHARGE_DESCRIPTOR_SPECS, PHASE1_ELEMENT_DESCRIPTOR_SPECS)
from phychem_mfm.phase1.baselines import TrainingBaselines
from phychem_mfm.phase1.evaluation import OriginalUnitEvaluator
from phychem_mfm.phase1.full_corpus_controls import (BINDING_FIELDS, FullCorpusControlsError,
    load_full_corpus_controls)
from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.data import fast_collate
from phychem_mfm.training.losses import LossWeights
from phychem_mfm.training.full_corpus_normalization import STREAMS, full_train_regression_normalization

PREP_SHA = "f04ccd742e79d7f606a61b244434f6de2c776e59b5715a2b354d2336761802ae"


def _seal(row, key):
    row.pop(key, None)
    row[key] = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    return row


@lru_cache(maxsize=1)
def _builder():
    path = Path(os.environ.get("PHASE1_FULL_PREPARATION_HELPER",
        "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage50_full_corpus_preparation/prepare_closed_full_corpus_artifacts.py"))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PREP_SHA
    spec = importlib.util.spec_from_file_location("stage55_actual_fullprep", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_controls(normalization, build_validation_controls):
    """Pure tiny-fixture factory usable by root trainer tests (no IO).

    The supplied callable is the actual frozen fullprep builder. This synthetic
    population places charge observations on Z1 and has one H per observed
    energy graph. It supplies valid Gram sufficient statistics, never a fake
    production artifact or an old baseline fit.
    """
    moments = deepcopy(normalization["full_training_moments"])
    binding = {key: deepcopy(normalization["training_provenance"][key]) for key in BINDING_FIELDS}
    n = moments["energy"]["count"]
    row = np.zeros(119)
    row[0] = row[118] = 1.
    by_element = {str(z): {"count": 0, "mean": 0., "m2": 0.} for z in range(1, 119)}
    by_element["1"] = deepcopy(moments["charge"])
    categories = {s.name: {} for s in PHASE1_CHARGE_DESCRIPTOR_SPECS + PHASE1_ELEMENT_DESCRIPTOR_SPECS
                  if s.task_type != "regression"}
    stats = {"schema_version": binding["estimator"], "train_only": True,
        "observed_train_records": binding["observed_train_records"], "observed_train_atoms": binding["observed_train_atoms"],
        "moments": moments, "charge_by_element": by_element, "categorical_counts": categories,
        "energy_linear_reference_sufficient_statistics": {"basis": "native_element_counts_Z1_to_Z118_then_intercept_v1",
            "count": n, "xtx": (n * np.outer(row, row)).tolist(), "xty": (n * moments["energy"]["mean"] * row).tolist()}}
    # Match the actual producer write_json -> consumer read_json boundary.
    # In-memory NumPy solve diagnostics are not the physical JSON artifact.
    return json.loads(json.dumps(build_validation_controls(_seal(stats, "statistics_sha256"), binding),
                                 allow_nan=False))


def _norm():
    binding = {"schema_version": "phase1_full_train_normalization_binding_v1", "train_only": True,
        "full_coverage": True, "role": "train", "estimator": "phase1_train_only_fp64_chan_population_moments_v1",
        "train_manifest_sha256": "a" * 64, "train_view_sha256": "b" * 64, "base_index_sha256": "c" * 64,
        "quality_artifact_sha256": "d" * 64, "moments_file_sha256": "e" * 64,
        "retained_train_records": 2, "observed_train_records": 2, "observed_train_atoms": 3}
    moments = {name: {"count": 0, "mean": 0., "m2": 0.} for name in STREAMS}
    moments.update(energy={"count": 2, "mean": 5., "m2": 8.},
                   charge={"count": 3, "mean": 2., "m2": 6.}, estate_index={"count": 1, "mean": 9., "m2": 0.})
    moments["graph/MolLogP"] = {"count": 2, "mean": .5, "m2": .5}
    return full_train_regression_normalization(moments, binding)


def _controls():
    norm = _norm()
    raw = make_controls(norm, _builder().build_validation_controls)
    # Independent two-design-row oracle extends the generic tiny fixture to Z118.
    gram, rhs = np.zeros((119, 119)), np.zeros(119)
    for element, target in ((0, 3.), (117, 7.)):
        row = np.zeros(119)
        row[element] = row[118] = 1
        gram += np.outer(row, row)
        rhs += row * target
    coeff, _, rank, singular = np.linalg.lstsq(gram, rhs, rcond=None)
    raw["energy"].update(coefficients=coeff.tolist(), gram_rank=int(rank), gram_singular_values=singular.tolist(),
                          normal_equation_residual_l2=float(np.linalg.norm(gram @ coeff - rhs)))
    raw["charge"]["counts_Z1_to_Z118"] = [2] + [0] * 116 + [1]
    raw["charge"]["means_Z1_to_Z118"] = [1.] + [2.] * 116 + [4.]
    raw["native_clean_element_control"]["class_counts_Z1_to_Z118"] = raw["charge"]["counts_Z1_to_Z118"].copy()
    raw["categorical"]["donor"] = {"available": True, "valid_labels": 3, "prediction": 0,
        "class_counts": {"0": 2, "1": 1}, "tie_break": "smallest_class_id"}
    raw["categorical"]["acceptor"] = {"available": True, "valid_labels": 2, "prediction": 0,
        "class_counts": {"0": 1, "1": 1}, "tie_break": "smallest_class_id"}
    _seal(raw, "controls_sha256")
    return raw, norm, load_full_corpus_controls(raw, norm)


def _model():
    return SimpleNamespace(n_atom_types=119, graph_descriptor_names=PHASE1_GRAPH_DESCRIPTOR_NAMES,
        graph_descriptor_target_indices=tuple(GRAPH_DESCRIPTOR_NAMES.index(n) for n in PHASE1_GRAPH_DESCRIPTOR_NAMES))


def _record(atom, energy, charge, *, view=0):
    return Data(x=torch.tensor([[atom]], dtype=torch.long), pos=torch.zeros(1, 3),
        target_pos=torch.zeros(1, 3), target_x=torch.tensor([[atom]], dtype=torch.long),
        element_corrupt_mask=torch.zeros(1, 1), sample_type_id=torch.tensor([view]),
        energy=torch.tensor([float(energy)]), energy_mask=torch.ones(1), y=torch.tensor([[float(charge)]]),
        charge_mask=torch.ones(1, 1), rdkit_node_mask=torch.ones(1, 1))


def _physical_output(energy, charge):
    b = len(energy)
    return PretrainOutputs(atom_repr=torch.zeros(b, 8), graph_repr=torch.zeros(b, 8),
        energy_pred=torch.tensor(energy).view(b, 1), charge_pred=torch.tensor(charge).view(b, 1, 1),
        node_mask=torch.ones(b, 1, 1, dtype=torch.bool), charge_mask=torch.ones(b, 1, 1, dtype=torch.bool))


def _assert_builtin(value):
    if type(value) is dict:
        assert all(type(k) is str for k in value)
        for child in value.values():
            _assert_builtin(child)
    elif type(value) is list:
        for child in value:
            _assert_builtin(child)
    else:
        assert value is None or type(value) in (str, bool, int, float)
        assert type(value) is not float or math.isfinite(value)


def test_physical118_plus_intercept_predictions_and_typed_unavailability():
    raw, norm, controls = _controls()
    assert controls.n_atom_types == 118 and len(controls.energy_coefficients) == 119
    assert controls.energy_coefficients[0] + controls.energy_coefficients[118] == pytest.approx(3.)
    assert controls.energy_coefficients[117] + controls.energy_coefficients[118] == pytest.approx(7.)
    assert controls.charge_means[0] == 1 and controls.charge_means[117] == 4 and controls.charge_means[1] == 2
    assert controls.node_predictions["acceptor"] == 0 and controls.node_predictions["estate_index"] == 9
    assert controls.graph_means["MolLogP"] == .5
    assert raw["native_clean_element_control"]["available"] is True
    assert controls.element_majority is None and controls.bond_majority is None
    assert controls.unavailable["element"]["status"] == "PENDING_ACTUAL_TRAIN_SOURCE_CORRUPTION_FIT"
    assert controls.to_dict()["energy"]["training_application"] == "NONE"


def test_controls_are_owned_deep_immutable_and_json_export_is_detached():
    raw, norm, controls = _controls()
    raw["energy"]["coefficients"][0] = 999
    exported = controls.to_dict()
    exported["charge"]["counts_Z1_to_Z118"][0] = 999
    assert controls.charge_counts[0] == 2 and controls.energy_coefficients[0] != 999
    with pytest.raises(ValueError):
        controls.charge_means.setflags(write=True)
    with pytest.raises(TypeError):
        controls.provenance["training_binding"]["role"] = "validation"
    with pytest.raises(TypeError):
        controls.graph_means["MolLogP"] = 99


@pytest.mark.parametrize("drift", ["width120", "physical119", "subtract", "charge_count", "wrong_binding", "typed_binding", "majority", "false_truth"])
def test_resealed_scientifically_wrong_controls_are_rejected(drift):
    raw, norm, _ = _controls()
    if drift == "width120":
        raw["energy"]["coefficients"].append(0.)
    elif drift == "physical119":
        raw["energy"]["physical_element_count"] = 119
    elif drift == "subtract":
        raw["energy"]["training_application"] = "SUBTRACT"
    elif drift == "charge_count":
        raw["charge"]["counts_Z1_to_Z118"][0] -= 1
    elif drift == "wrong_binding":
        raw["training_binding"]["train_view_sha256"] = "f" * 64
    elif drift == "typed_binding":
        raw["training_binding"]["train_only"] = 1
    elif drift == "majority":
        raw["categorical"]["acceptor"]["prediction"] = 1
    else:
        raw["chemical_or_negative_label_truth_independently_verified"] = True
    _seal(raw, "controls_sha256")
    with pytest.raises(FullCorpusControlsError):
        load_full_corpus_controls(raw, norm)


def test_stale_controls_and_invalid_normalization_seals_reject():
    raw, norm, _ = _controls()
    raw["charge"]["global_mean"] = 99
    with pytest.raises(FullCorpusControlsError, match="seal"):
        load_full_corpus_controls(raw, norm)
    raw, norm, _ = _controls()
    norm["training_statistics"]["muE"] = 99
    with pytest.raises(FullCorpusControlsError, match="normalization"):
        load_full_corpus_controls(raw, norm)


def test_unobserved_controls_are_none_not_identity_or_clean_element_predictions():
    norm = _norm()
    moments = {key: {"count": 0, "mean": 0., "m2": 0.} for key in STREAMS}
    binding = {key: norm["training_provenance"][key] for key in BINDING_FIELDS}
    norm = full_train_regression_normalization(moments, binding)
    raw = make_controls(norm, _builder().build_validation_controls)
    controls = load_full_corpus_controls(raw, norm)
    assert controls.energy_coefficients is None and controls.charge_means is None
    assert controls.element_majority is None and not controls.node_predictions and not controls.graph_means
    evaluator = OriginalUnitEvaluator(_model(), controls)
    evaluator.add(fast_collate([_record(0, 3., 1.)]), _physical_output([4.], [2.]))
    report = evaluator.result()
    assert report["targets"]["energy_kcal_per_mol"]["model"]["mae"] == 1.
    assert report["targets"]["energy_kcal_per_mol"]["baseline"]["available"] is False
    _assert_builtin(report)


def test_original_unit_energy_and_charge_hand_mae_no_second_inverse():
    _, _, controls = _controls()
    records = [_record(0, 3., 1.), _record(117, 7., 4.)]
    original = [r.clone() for r in records]
    evaluator = OriginalUnitEvaluator(_model(), controls)
    evaluator.add(fast_collate(records), _physical_output([5., 6.], [2., 3.]))
    result = evaluator.result()
    e, q = result["targets"]["energy_kcal_per_mol"], result["targets"]["net_atomic_charge_e"]
    assert e["model"]["mae"] == 1.5 and e["model"]["rmse"] == pytest.approx(math.sqrt(2.5))
    assert e["baseline"]["mae"] == pytest.approx(0., abs=1e-12)
    assert q["model"]["mae"] == 1. and q["baseline"]["mae"] == 0.
    assert e["model"]["count"] == q["model"]["count"] == 2
    for record, saved in zip(records, original):
        assert torch.equal(record.energy, saved.energy) and torch.equal(record.y, saved.y)
    _assert_builtin(result)


def test_masks_finite_labels_and_unseen_charge_count_match_the_actual_loss():
    _, _, controls = _controls()
    records = [_record(0, 3., 1.), _record(1, 7., 2.), _record(0, 999., float("nan"))]
    records[0].energy_mask.fill_(2.)  # Not the exact valid-energy declaration 1.
    output = _physical_output([5., 6., 999.], [2., 4., 999.])
    output.charge_mask[0] = False  # Explicit model/producer charge mask wins.
    batch = fast_collate(records)
    loss = compute_phase1_loss(output, batch, {"stdE": 2., "stdQ": 1.},
        SupervisionConfig.from_variant("P"), LossWeights(), Phase1JointSchedule(), 0)
    evaluator = OriginalUnitEvaluator(_model(), controls)
    evaluator.add(batch, output)
    result = evaluator.result()
    assert result["targets"]["energy_kcal_per_mol"]["model"]["count"] == loss.counts["energy"] == 2
    assert result["targets"]["net_atomic_charge_e"]["model"]["count"] == loss.counts["charge"] == 1
    assert result["unseen_charge_element_atoms"] == 1
    assert result["targets"]["net_atomic_charge_e"]["baseline"]["mae"] == 0.


def test_energy_control_never_counts_reserved_input_class_in_excluded_topology_view():
    _, _, controls = _controls()
    records = [_record(0, 3., 1., view=0), _record(118, 999., 0., view=2)]
    output = PretrainOutputs(atom_repr=torch.zeros(2, 8), graph_repr=torch.zeros(2, 8),
                             energy_pred=torch.tensor([[4.], [999.]]))
    evaluator = OriginalUnitEvaluator(_model(), controls)
    evaluator.add(fast_collate(records), output)
    metric = evaluator.result()["targets"]["energy_kcal_per_mol"]
    assert metric["model"]["count"] == metric["baseline"]["count"] == 1
    assert metric["model"]["mae"] == 1. and metric["baseline"]["mae"] == pytest.approx(0., abs=1e-12)


def _three_views():
    records = [_record(0, 3., 1., view=view) for view in (0, 1, 2)]
    for record in records:
        record.x = torch.tensor([[0], [5]])
        record.target_x = record.x.clone()
        record.pos = torch.tensor([[0., 0., 0.], [1., 0., 0.]])
        record.target_pos = record.pos.clone()
        record.element_corrupt_mask = torch.zeros(2, 1)
        record.y = torch.zeros(2, 1)
        record.charge_mask = torch.ones(2, 1)
        record.rdkit_node_mask = torch.ones(2, 1)
    batch = fast_collate(records)
    order = torch.zeros(3, 5)
    order[:, 0] = 1.
    bond = BondOutputs(existence=torch.empty(0), order=order, pair_index=torch.tensor([[0, 2, 4], [1, 3, 5]]),
        pair_graph_index=torch.arange(3), existence_target=torch.ones(3), order_target=torch.tensor([0, 1, 2]))
    output = PretrainOutputs(atom_repr=torch.zeros(6, 8), graph_repr=torch.zeros(3, 8),
        node_mask=torch.ones(3, 2, 1, dtype=torch.bool), element_logits=torch.zeros(3, 2, 119),
        coordinate_pred=torch.stack([r.pos for r in records]), bond=bond)
    return batch, output


def test_positive_bonds_three_views_score_only_clean_with_objective_count_oracle():
    _, _, controls = _controls()
    batch, output = _three_views()
    before = output.bond.order_target.clone()
    loss = compute_phase1_loss(output, batch, {}, SupervisionConfig.from_variant("S"),
        LossWeights(), Phase1JointSchedule(), 0)
    evaluator = OriginalUnitEvaluator(_model(), controls)
    evaluator.add(batch, output)
    metric = evaluator.result()["targets"]["bond_order_positive"]
    assert metric["model"]["count"] == loss.counts["bond_order"] == 1
    assert metric["model"]["accuracy"] == 1.
    assert metric["baseline"]["available"] is False
    assert metric["baseline"]["evidence_state"] == "PENDING_ACTUAL_TRAIN_SOURCE_BOND_FIT"
    assert torch.equal(before, output.bond.order_target)


def test_legal_element_padding_prediction_is_error_and_pending_baseline_stays_none():
    _, _, controls = _controls()
    record = _record(0, 0., 0., view=2)
    record.element_corrupt_mask.fill_(1)
    output = PretrainOutputs(atom_repr=torch.zeros(1, 8), graph_repr=torch.zeros(1, 8),
        element_logits=torch.zeros(1, 1, 119), node_mask=torch.ones(1, 1, 1, dtype=torch.bool))
    output.element_logits[0, 0, 118] = 1.
    evaluator = OriginalUnitEvaluator(_model(), controls)
    evaluator.add(fast_collate([record]), output)
    metric = evaluator.result()["targets"]["element"]
    assert metric["model"]["count"] == 1 and metric["model"]["accuracy"] == 0.
    assert metric["model"]["confusion"][0][118] == 1
    assert metric["baseline"]["available"] is False


def test_original_continuous_and_categorical_accumulators_have_hand_correct_values():
    _, _, controls = _controls()
    evaluator = OriginalUnitEvaluator(_model(), controls)
    evaluator.regression("D/MolLogP", [2., 1.], [0., 1.], [.5, .5])
    evaluator.regression("D/estate_index", [10.], [9.], [9.])
    evaluator.classification("D/donor", [0, 1, 1], [0, 0, 1], [0, 0, 0], 2)
    evaluator.classification("D/is_aromatic", [1], [1], None, 2)
    result = evaluator.result()["targets"]
    assert result["D/MolLogP"]["model"]["mae"] == 1. and result["D/MolLogP"]["baseline"]["mae"] == .5
    assert result["D/estate_index"]["model"]["mae"] == 1.
    assert result["D/donor"]["model"]["accuracy"] == pytest.approx(2 / 3)
    assert result["D/donor"]["model"]["confusion"] == [[1, 1], [0, 1]]
    assert result["D/is_aromatic"]["baseline"]["available"] is False


def _seed_partial(evaluator):
    evaluator.add(fast_collate([_record(1, 4., 2.)]), _physical_output([6.], [3.]))
    evaluator.classification("element", [0, 118], [0, 5], None, 119)
    evaluator.classification("D/donor", [0, 1], [0, 0], [0, 0], 2)


def test_partial_original_unit_state_restores_exact_counts_and_continues_identically():
    _, _, controls = _controls()
    uninterrupted, resumed = OriginalUnitEvaluator(_model(), controls), OriginalUnitEvaluator(_model(), controls)
    _seed_partial(uninterrupted)
    state = uninterrupted.state_dict()
    saved = deepcopy(state)
    _assert_builtin(state)
    resumed.load_state_dict(state)
    assert resumed.result() == uninterrupted.result() and resumed.state_dict() == state
    batch, output = _three_views()
    for evaluator in (uninterrupted, resumed):
        evaluator.add(batch, output)
        evaluator.regression("D/MolLogP", [1., 4., 4.], [0., 0., 0.], [.5, .5, .5])
    assert resumed.result() == uninterrupted.result()
    assert resumed.state_dict() == uninterrupted.state_dict()
    assert state == saved  # Continued NumPy accumulation owns its storage.
    assert resumed.result()["unseen_charge_element_atoms"] == 1


@pytest.mark.parametrize("drift", ["negative_error", "impossible_error", "wrong_kind", "wrong_shape", "duplicate", "unseen", "availability", "contract_type"])
def test_resealed_bad_meter_states_reject_atomically(drift):
    _, _, controls = _controls()
    evaluator = OriginalUnitEvaluator(_model(), controls)
    _seed_partial(evaluator)
    before, result = evaluator.state_dict(), evaluator.result()
    wrong = deepcopy(before)
    regression = next(row for row in wrong["meters"] if row["kind"] == "regression")
    classification = next(row for row in wrong["meters"] if row["kind"] == "classification")
    if drift == "negative_error":
        regression["squared"] = -1.
    elif drift == "impossible_error":
        regression["absolute"], regression["squared"] = 100., 1.
    elif drift == "wrong_kind":
        regression["kind"] = "classification"
    elif drift == "wrong_shape":
        classification["confusion"].pop()
    elif drift == "duplicate":
        wrong["meters"].append(deepcopy(wrong["meters"][0]))
    elif drift == "unseen":
        wrong["unseen_charge_atoms"] = 99
    elif drift == "availability":
        wrong["unavailable_baselines"].append("energy_kcal_per_mol")
        wrong["unavailable_baselines"].sort()
    else:
        wrong["contract"]["cutoff"] = 2  # Typed semantic contract is fixed float.
    _seal(wrong, "state_sha256")
    with pytest.raises(ValueError):
        evaluator.load_state_dict(wrong)
    assert evaluator.state_dict() == before and evaluator.result() == result


def test_stale_state_and_controls_drift_fail_before_any_accumulator_mutation():
    raw, norm, controls = _controls()
    first = OriginalUnitEvaluator(_model(), controls)
    _seed_partial(first)
    state = first.state_dict()
    state["unseen_charge_atoms"] = 0
    receiver = OriginalUnitEvaluator(_model(), controls)
    empty = receiver.state_dict()
    with pytest.raises(ValueError, match="seal"):
        receiver.load_state_dict(state)
    assert receiver.state_dict() == empty
    raw["training_binding"]["moments_file_sha256"] = "f" * 64
    # A distinct but internally valid training source contract cannot resume it.
    moments = deepcopy(norm["full_training_moments"])
    binding = dict(raw["training_binding"])
    other_norm = full_train_regression_normalization(moments, binding)
    other = load_full_corpus_controls(_seal(raw, "controls_sha256"), other_norm)
    receiver = OriginalUnitEvaluator(_model(), other)
    before = receiver.state_dict()
    with pytest.raises(ValueError, match="contract"):
        receiver.load_state_dict(first.state_dict())
    assert receiver.state_dict() == before


def test_legacy_baseline_signature_and_builtin_results_remain_usable():
    legacy = TrainingBaselines(n_atom_types=95)
    legacy.energy_coefficients = np.zeros(96)
    legacy.energy_coefficients[-1] = 3.
    evaluator = OriginalUnitEvaluator(SimpleNamespace(), legacy)
    output = PretrainOutputs(atom_repr=torch.zeros(1, 8), graph_repr=torch.zeros(1, 8), energy_pred=torch.tensor([[4.]]))
    evaluator.add(fast_collate([_record(0, 3., 1.)]), output)
    assert evaluator.result()["targets"]["energy_kcal_per_mol"]["model"]["mae"] == 1.
    state = evaluator.state_dict()
    restored = OriginalUnitEvaluator(SimpleNamespace(), legacy)
    restored.load_state_dict(state)
    assert restored.result() == evaluator.result()
    _assert_builtin(restored.result())
