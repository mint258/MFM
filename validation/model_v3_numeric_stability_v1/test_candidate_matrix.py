"""Explicit scientific validation: original 48 cases, original absolute 1e-5.

Run separately from the ordinary CPU regression suite under Root's owned runtime.
Every complete failed measurement and all 52 arrays survive before any assertion.
"""
import hashlib
import json
import os
from pathlib import Path
import traceback

import pytest
import torch

from candidate_composed_adapter import load_equation, composition_mode, durable_file, FIXTURE_SHA256
from phychem_mfm.model.v3_numeric_stability import COMPENSATED, LEGACY

EQUATION = load_equation()


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    durable_file(path)


@pytest.mark.parametrize("spec", EQUATION.CASE_SPECS, ids=lambda case: case.identity)
def test_original_complete_composition_candidate_absolute_1e_minus5(spec, tmp_path):
    device = os.environ.get("MODEL_V3_NUMERIC_TEST_DEVICE", "cpu")
    mode = os.environ.get("MODEL_V3_NUMERIC_TEST_MODE", COMPENSATED)
    assert device in ("cpu", "cuda:0") and mode in (LEGACY, COMPENSATED)
    if device == "cuda:0":
        assert torch.cuda.is_available() and torch.cuda.device_count() == 1
    assert EQUATION.ABSOLUTE_TOLERANCE == 1e-5 and EQUATION.RELATIVE_TOLERANCE == 0
    try:
        with composition_mode(EQUATION, mode):
            measured = EQUATION.measure_case(spec, device=device,
                threads=int(os.environ.get("MODEL_V3_NUMERIC_TEST_THREADS", "1")),
                terminal_output_directory=tmp_path)
        artifact = measured["actual_terminal_output_artifact"]
        durable_file(artifact["path"])
        result = {"schema": "model_v3_numeric_stability_composed_case_v1", "numeric_mode": mode,
            "original_fixture_source_sha256": FIXTURE_SHA256, "trained_or_selected_model": False,
            "measured": measured}
        save(tmp_path/(spec.identity+"__numeric_case.json"), result)
    except Exception as error:
        partial = tmp_path/(spec.identity+"__terminals.npz")
        if partial.is_file(): durable_file(partial)
        save(tmp_path/(spec.identity+"__exception.json"), {"case_id": spec.identity,
            "numeric_mode": mode, "exception": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(), "passed": False})
        raise
    assert len(artifact["arrays"]) == 52 and artifact["numeric_bytes"] <= 320*1024
    raw = Path(artifact["path"]).read_bytes()
    assert len(raw) <= 512*1024 and hashlib.sha256(raw).hexdigest() == artifact["sha256"]
    assert len(measured["measurements"]) == 3 and all(len(t["fields"]) == 13 for t in measured["measurements"])
    assert measured["encoder_forward_shapes"] == [[88 if spec.views == "two" else 132, 512]]*4
    configuration = measured["encoder_configuration"]
    if mode == COMPENSATED:
        assert configuration["backbone_config"]["numeric_mode"] == mode
        assert configuration["head_config"]["numeric_mode"] == mode
    else:
        assert "numeric_mode" not in configuration["backbone_config"]
        assert "numeric_mode" not in configuration["head_config"]
    EQUATION.assert_case_passed(measured)
