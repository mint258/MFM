"""Actual 6x512 encoder/head compositions, not a standalone head oracle."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import traceback

import pytest
import torch

from phychem_mfm.phase1.v3_composed_equivariance import (
    ABSOLUTE_TOLERANCE, CASE_SPECS, HEAD_POLICIES, VIEW_CONFIGURATION, ORDINALS,
    assert_case_passed, field_measurement, fixture_batch, measure_case, protocol,
    pushed_views, transform_expected, transforms,
)
from phychem_mfm.phase1.v3_architecture_views import build_two_structural_views
from phychem_mfm.phase1.v3_structural import build_structural_views


@pytest.mark.parametrize("spec", CASE_SPECS, ids=lambda case: case.identity)
def test_actual_six_layer_encoder_to_all_heads_absolute_equivariance(spec, tmp_path):
    device = os.environ.get("MODEL_V3_EQ_TEST_DEVICE", "cpu")
    assert device in ("cpu", "cuda:0")
    if device == "cuda:0":
        # An explicitly requested GPU check must fail rather than skip.
        assert torch.cuda.is_available() and torch.cuda.device_count() == 1
    threads = int(os.environ.get("MODEL_V3_EQ_TEST_THREADS", "1"))
    try:
        result = measure_case(spec, device=device, threads=threads, terminal_output_directory=tmp_path)
    except Exception as error:
        failure = {"case_id": spec.identity, "exception": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(), "passed": False}
        partial = tmp_path/(spec.identity+"__terminals.npz")
        if partial.is_file():
            raw_partial = partial.read_bytes()
            failure["partial_actual_terminal_output_artifact"] = {"path": str(partial), "bytes": len(raw_partial),
                "sha256": hashlib.sha256(raw_partial).hexdigest()}
        (tmp_path/(spec.identity+"__exception.json")).write_text(
            json.dumps(failure, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
        raise
    # Store complete failed measurements before asserting. Root preserves its
    # owned pytest basetemp or runs the bound CLI for permanent case receipts.
    path = tmp_path/(spec.identity+".json")
    path.write_text(json.dumps(result, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    artifact = result["actual_terminal_output_artifact"]
    raw = Path(artifact["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
    assert len(artifact["arrays"]) == 13*4 and artifact["numeric_bytes"] <= 320*1024
    assert len(result["measurements"]) == 3
    assert all(len(item["fields"]) == 13 for item in result["measurements"])
    assert result["encoder_forward_shapes"] == [[88 if spec.views == "two" else 132, 512]]*4
    assert_case_passed(result)


def test_frozen_matrix_covers_all_actual_configurations_and_proper_transforms():
    value = protocol()
    assert len(CASE_SPECS) == len({c.identity for c in CASE_SPECS}) == value["case_count"] == 48
    assert {c.head_policy for c in CASE_SPECS} == set(HEAD_POLICIES)
    assert {c.distance_bias for c in CASE_SPECS} == {"C1-0", "C1-a", "C1-b"}
    assert {c.views for c in CASE_SPECS} == {"two", "three"}
    assert value["relative_tolerance"] == 0 and value["absolute_tolerance"] == 1e-5
    assert (fixture_batch().ptr[1:]-fixture_batch().ptr[:-1]).tolist() == [3, 9, 32]
    assert all(abs(t.document()["determinant"]-1) < 1e-12 for t in transforms())


@pytest.mark.parametrize("count", ("two", "three"))
def test_push_forward_keeps_existing_noise_and_actual_masks_and_target_frame(count):
    builder = build_two_structural_views if count == "two" else build_structural_views
    original = builder(fixture_batch(), ordinals=ORDINALS, config=VIEW_CONFIGURATION)
    before = original.batch.pos.clone(), original.batch.target_pos.clone(), original.batch.x.clone()
    for transform in transforms():
        moved, proof = pushed_views(original, transform)
        assert torch.equal(moved.batch.x, original.batch.x)
        assert torch.equal(moved.batch.target_x, original.batch.target_x)
        assert torch.equal(moved.batch.element_corrupt_mask, original.batch.element_corrupt_mask)
        assert torch.equal(moved.batch.rdkit_bond_index, original.batch.rdkit_bond_index)
        assert proof["same_noise_pushforward_maxabs_A"] <= 2e-6 and not proof["random_views_regenerated"]
    assert all(torch.equal(a, b) for a, b in zip(before, (original.batch.pos, original.batch.target_pos, original.batch.x)))


def test_negative_oracle_rejects_missing_or_inverse_vector_rotation():
    reference = torch.tensor([[.5, -.3, .7], [-.1, .9, .4]], dtype=torch.float32)
    transform = transforms()[0]
    expected = transform_expected(reference, transform, "vector")
    correct = field_measurement("vector", expected.float(), expected, law="vector", unit="fixture", require_nonzero=True, reference=reference)
    assert correct["passed"]
    for wrong in (reference, (reference.double() @ transform.rotation.T).float()):
        result = field_measurement("vector", wrong, expected, law="vector", unit="fixture", require_nonzero=True, reference=reference)
        assert not result["passed"] and result["maxabs"] > ABSOLUTE_TOLERANCE


def test_negative_oracle_rejects_coordinate_as_displacement_or_vector_as_coordinate():
    reference = torch.tensor([[.5, -.3, .7], [-.1, .9, .4]], dtype=torch.float32)
    transform = transforms()[2]
    vector = transform_expected(reference, transform, "vector")
    coordinate = transform_expected(reference, transform, "coordinate")
    for actual, expected, law in ((vector, coordinate, "coordinate"), (coordinate, vector, "vector")):
        result = field_measurement(law, actual.float(), expected, law=law, unit="fixture", require_nonzero=True, reference=reference)
        assert not result["passed"] and result["maxabs"] >= 1.


def test_absolute_only_and_nonzero_oracle_cannot_pass_by_relative_scale_or_zeros():
    reference = torch.full((1, 3), 100., dtype=torch.float32)
    actual = reference.clone(); actual[0, 1] += 5e-5
    result = field_measurement("scalar", actual, reference, law="invariant", unit="fixture")
    assert not result["passed"] and result["maxabs"] > ABSOLUTE_TOLERANCE
    assert result["argmax"]["component"] == 1 and result["relative_tolerance"] == 0
    zero = field_measurement("vector", torch.zeros(2, 3), torch.zeros(2, 3),
        law="vector", unit="fixture", require_nonzero=True)
    assert zero["maxabs"] == 0 and not zero["passed"] and zero["actual_nonzero_rows"] == 0


def test_nonfinite_oracle_fails_with_json_safe_measurements():
    value = torch.tensor([[float("nan"), 0., 1.]])
    result = field_measurement("vector", value, torch.ones(1, 3), law="vector", unit="fixture", require_nonzero=True)
    assert not result["passed"] and not result["finite"] and result["maxabs"] is None
    json.dumps(result, allow_nan=False)


def _execution_cli():
    path = Path(__file__).absolute().parents[2]/"tools/model_v3/check_composed_equivariance.py"
    specification = importlib.util.spec_from_file_location("composed_equivariance_cli_for_test", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_execution_request_pins_all_actual_sources_and_rejects_manifest_or_protocol_drift(tmp_path):
    cli = _execution_cli()
    original = cli.source_request("cpu", "compute-0-12")
    assert original["expected_composed_cases"] == 48 and original["expected_legacy_cuda_cases"] == 0
    assert "workflows/sprime_s/scripts/s_model_memory_v1.py" in original["source_files"]
    assert all(node.split("::")[0] in original["source_files"] for node in cli.LEGACY_CUDA_NODES)
    for index, mutation in enumerate((None, "source", "protocol", "cases")):
        value = deepcopy(original)
        if mutation == "source":
            value["source_files"]["current/phychem_mfm/model/v3_heads.py"]["sha256"] = "0"*64
        elif mutation == "protocol": value["protocol"]["absolute_tolerance"] = 2e-5
        elif mutation == "cases": value["case_ids"] = value["case_ids"][:-1]
        path = tmp_path/f"request{index}.json"
        cli.write_json(path, value)
        raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if mutation is None: assert cli.read_request(path, raw_sha) == original
        else:
            with pytest.raises(ValueError, match="identity differs"): cli.read_request(path, raw_sha)


def test_gpu_request_requires_uuid_and_cpu_request_rejects_gpu_node_without_initializing_cuda():
    cli = _execution_cli()
    before = torch.cuda.is_initialized()
    with pytest.raises(ValueError, match="CPU node"):
        cli.source_request("cpu", "compute-0-20")
    with pytest.raises(ValueError, match="UUID"):
        cli.source_request("cuda:0", "compute-0-20")
    value = cli.source_request("cuda:0", "compute-0-20", gpu_uuid="GPU-12345678-1234-1234-1234-123456789abc")
    assert value["expected_legacy_cuda_cases"] == 2 and len(value["legacy_cuda_test_nodes"]) == 2
    assert torch.cuda.is_initialized() == before  # request preparation is not GPU execution/admission.
