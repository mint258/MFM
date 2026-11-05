"""Prepared CPU tests; no CUDA/fused/native-training acceptance is claimed."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import torch

PATH = Path(__file__).with_name("diagnose_native_feedback.py")
SPEC = importlib.util.spec_from_file_location("external_a06_native_feedback", PATH)
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


def config():
    reference = {"fused_adamw": False, "backbone_checkpointing": None, "precision": "fp32", "tf32": False,
        "compile_backbone": False, "distance_pair_rows": 65536, "distance_checkpointing": True, "head_checkpointing": True}
    return {"code_sha": diagnostic.CODE_SHA, "prereg_sha": diagnostic.PREREG_SHA, "seed": 0, "input": "native_s",
        "trajectory_updates": 500, "smoke": False, "gpu_uuid": diagnostic.GPU_UUID,
        "optimizer": {"lr": .0003, "betas": [.9, .95], "weight_decay": .01}, "gradient_clip_norm": 1., "dynamic_balancer": False,
        "model": {"backbone": {"activation_checkpointing": True, "dim": 512, "dropout": 0., "ff_mult": 2,
            "heads": 8, "layers": 6, "n_atom_types": 119, "radius": 8., "use_dist_bias": True, "use_radius_mask": False}},
        "reference": reference, "candidate": {**reference, "fused_adamw": True, "backbone_checkpointing": True},
        "data_version": {"sampler": {"max_padded_cost": 8000000}, "loader": {"num_workers": 8}, "exact_atom_sort": False, "seed": 0},
        "deterministic_controls": {"requested": True, "actual": {"deterministic_algorithms": True}}}


def row(update):
    return {"optimizer_updates": update, "loss": 1.25, "gradient_norm": 2., "base_records": 2,
            "native_atoms": 21, "consumed_base_records": 2 * update, "input_receipt_sha256": "a" * 64,
            "valid_label_counts": {"graphs": 6, "element": 2, "bond_order": 3, "denoise_eps_mse": 21}}


def test_exact_original_configuration_is_admitted():
    diagnostic.validate_configuration(config())


@pytest.mark.parametrize("path,value", [
    (("seed",), 1), (("gpu_uuid",), "GPU-other"), (("input",), "synthetic"),
    (("candidate", "tf32"), True), (("candidate", "distance_checkpointing"), False),
    (("data_version", "sampler", "max_padded_cost"), 4000000),
    (("optimizer", "lr"), .0001), (("gradient_clip_norm",), 2.),
    (("deterministic_controls", "requested"), False)])
def test_native_science_or_environment_changes_reject(path, value):
    altered = config()
    current = altered
    for name in path[:-1]:
        current = current[name]
    current[path[-1]] = value
    with pytest.raises(ValueError):
        diagnostic.validate_configuration(altered)


def test_replay_requires_every_original_scientific_scalar_and_type():
    expected = row(14)
    assert diagnostic.replay_comparison(expected, deepcopy(expected))["pass"]
    for name in diagnostic.REPLAY_FIELDS:
        changed = deepcopy(expected)
        if isinstance(changed[name], dict):
            changed[name]["bond_order"] += 1
        elif isinstance(changed[name], str):
            changed[name] = "b" * 64
        else:
            changed[name] += .000000000001
        result = diagnostic.replay_comparison(expected, changed)
        assert not result["pass"] and name in result["differences"]
    typed = deepcopy(expected)
    typed["optimizer_updates"] = 14.
    assert not diagnostic.replay_comparison(expected, typed)["pass"]


def test_history_full500_eof_and_json_types_are_verified(tmp_path):
    path = tmp_path / "original.jsonl"
    lines = [(json.dumps(row(update)) + "\n").encode() for update in range(1, 501)]
    path.write_bytes(b"".join(lines))
    assert len(diagnostic.read_original_history(path)) == 500
    for corrupt in (b"".join(lines[:-1]), b"".join(lines)[:-1], b"".join(lines[:3] + [lines[2]] + lines[4:]),
                    b"".join(lines).replace(b'"loss": 1.25', b'"loss": NaN', 1),
                    b"".join(lines).replace(b'"loss": 1.25', b'"loss": 1.25, "loss": 1.25', 1)):
        path.write_bytes(corrupt)
        with pytest.raises(ValueError):
            diagnostic.read_original_history(path)


def test_bounded_reader_rejects_oversized_or_nonregular_source(tmp_path):
    path = tmp_path / "large"
    path.write_bytes(b"123456")
    with pytest.raises(ValueError, match="Bounded ordinary"):
        diagnostic.file_ref(path, limit=5)
    with pytest.raises(ValueError, match="Bounded ordinary"):
        diagnostic.file_ref(tmp_path)


def test_shadow_clone_preserves_rng_names_bits_and_none_pattern():
    generator_state = torch.get_rng_state().clone()
    model = torch.nn.Linear(3, 2)
    original = list(model.named_parameters())
    rng = torch.get_rng_state().clone()
    shadow = diagnostic.clone_shadow(torch, original)
    assert torch.equal(torch.get_rng_state(), rng)
    for (name, parameter), (other_name, other) in zip(original, shadow):
        assert name == other_name and torch.equal(parameter, other)
        assert parameter.data_ptr() != other.data_ptr()
        assert other.grad is None
    torch.set_rng_state(generator_state)


def test_real_cpu_adapter_borrows_gradients_without_feedback_or_mutation():
    # CPU AdamW verifies ownership and hashing only. The actual diagnostic
    # independently requiresCUDA + true fused dispatch; this is not its oracle.
    reference = [("used", torch.nn.Parameter(torch.tensor([1., 2.]))),
                 ("unused", torch.nn.Parameter(torch.tensor([3.])))]
    reference[0][1].grad = torch.tensor([.1, -.2])
    shadow = diagnostic.clone_shadow(torch, reference)
    original = [parameter.detach().clone() for _, parameter in reference]
    optimizer = torch.optim.AdamW([p for _, p in shadow], lr=.0003, betas=(.9, .95), weight_decay=.01)
    with diagnostic.borrow_reference_gradients(reference, shadow) as receipt:
        assert shadow[0][1].grad is reference[0][1].grad
        assert shadow[1][1].grad is None
        optimizer.step()
    assert receipt["unchanged"] and receipt["before"] == receipt["after"] == receipt["reference_after"]
    assert all(p.grad is None for _, p in shadow)
    assert all(torch.equal(p, before) for (_, p), before in zip(reference, original))
    assert not torch.equal(shadow[0][1], reference[0][1])
    assert torch.equal(shadow[1][1], reference[1][1])
    assert len(optimizer.state) == 1


def test_borrowed_gradient_mutation_is_detected_and_references_retired():
    reference = [("x", torch.nn.Parameter(torch.tensor([1., 2.])))]
    reference[0][1].grad = torch.tensor([.1, -.2])
    shadow = diagnostic.clone_shadow(torch, reference)
    with pytest.raises(RuntimeError, match="changed borrowed"):
        with diagnostic.borrow_reference_gradients(reference, shadow):
            shadow[0][1].grad[0] += 1.
    assert shadow[0][1].grad is None


def test_borrowed_none_pattern_and_metadata_are_not_coerced():
    reference = [("x", torch.nn.Parameter(torch.tensor([1., 2.])))]
    reference[0][1].grad = torch.tensor([.1, -.2])
    with pytest.raises(ValueError, match="order"):
        with diagnostic.borrow_reference_gradients(reference, [("other", reference[0][1])]):
            pass
    with pytest.raises(ValueError, match="metadata"):
        with diagnostic.borrow_reference_gradients(reference, [("x", torch.nn.Parameter(torch.ones(3)))]):
            pass
    shadow = diagnostic.clone_shadow(torch, reference)
    with pytest.raises(RuntimeError, match="changed borrowed"):
        with diagnostic.borrow_reference_gradients(reference, shadow):
            shadow[0][1].grad = None
    assert shadow[0][1].grad is None


def test_all_parameters_keep_old_floor_null_bias_and_original_gate():
    from phychem_mfm.training.v3_performance_acceptance import compare_tensors, trajectory_report
    name = "backbone.layers.0.attn.dist_mlp.2.bias"
    reference = {name: torch.zeros(8), "active": torch.tensor([1., 2.]), "disabled": None}
    candidate = {name: torch.full((8,), 1e-10), "active": torch.tensor([1., 2.]), "disabled": None}
    old = compare_tensors(reference, candidate, tolerance=1e-4)
    result = diagnostic.compact_comparison(torch, reference, candidate, tolerance=1e-4)
    assert result["pass"] == old["pass"] is False
    expected = next(item for item in old["tensors"] if item["name"] == name)
    assert result["fixed_six_distance_biases"][0]["relative_l2"] == expected["relative_l2"]
    assert result["parameters_audited"] == 3 and result["disabled_both"] == 1
    assert result["failed_parameters"] == 1
    # Original14 threshold failure stays a failure even for a shorter diagnostic.
    gate = trajectory_report({1: 1.}, {1: 1.0029128788627426}, expected_updates=1)
    assert not gate["pass"] and gate["results"][0]["relative_difference"] > .001


def test_missing_gradient_and_nonfinite_diagnostic_values_reject():
    result = diagnostic.compact_comparison(torch, {"x": None}, {"x": torch.ones(1)}, tolerance=1e-4)
    assert not result["pass"] and result["missing_gradient_mismatches"] == ["x"]
    with pytest.raises(FloatingPointError):
        diagnostic.compact_comparison(torch, {"x": torch.ones(1)}, {"x": torch.tensor([float("nan")])}, tolerance=1e-4)


def test_cli_cannot_request_500_or_change_actual_code():
    args = diagnostic.parser().parse_args(["--repo", "/repo", "--pins-sha256", "a" * 64,
        "--code-sha", diagnostic.CODE_SHA, "--output", "/fresh"])
    assert args.updates == 15 and args.expected_gpu == "5090"
    with pytest.raises(SystemExit):
        diagnostic.parser().parse_args(["--repo", "/repo", "--pins-sha256", "a" * 64,
            "--code-sha", diagnostic.CODE_SHA, "--output", "/fresh", "--updates", "500"])


def test_parameter_and_moment_summaries_do_not_invent_a_pass_gate():
    result = diagnostic.compact_comparison(torch, {"parameter": torch.zeros(2)},
        {"parameter": torch.ones(2)}, tolerance=None)
    assert result["pass"] is None and result["failed_parameters"] is None
    assert result["max_relative_l2"] > 1e12


def test_pins_detect_both_original_and_diagnostic_source_drift(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "frozen.py"
    source.write_bytes(b"frozen source\n")
    other = tmp_path / "evidence.json"
    other.write_bytes(b"{}\n")
    roles = ("script", "tests", "readme", "457_configuration", "457_reference_history", "457_candidate_history",
             "457_gate", "457_summary", "457_status", "485_summary", "485_script", "485_configuration")
    pins = {"schema": "A06_native_feedback_source_pins_v1", "base_code_sha": diagnostic.CODE_SHA,
        "files": [{**diagnostic.file_ref(PATH if role == "script" else other), "role": role} for role in roles],
        "original_repo_source_sha256": {"frozen.py": diagnostic.file_ref(source)["sha256"]}}
    assert len(diagnostic.verify_pins(pins, repo)) == len(roles) + 1
    source.write_bytes(b"changed source\n")
    with pytest.raises(ValueError, match="Frozen8ece"):
        diagnostic.verify_pins(pins, repo)
    source.write_bytes(b"frozen source\n")
    other.write_bytes(b'{"changed":true}\n')
    with pytest.raises(ValueError, match="Pinned source/evidence"):
        diagnostic.verify_pins(pins, repo)


def test_torch_preimport_rejection_is_before_scientific_work():
    assert "torch" in sys.modules
    with pytest.raises(RuntimeError, match="Fresh process"):
        diagnostic.run(object())
