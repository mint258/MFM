"""Metadata oracles only; root executes with a real frozen protocol path."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from formal_plan import compile_plan, digest, verify_wire_payload, FormalReadoutError


@pytest.fixture
def protocol():
    path = Path(os.environ["PHASE1_FORMAL_PROTOCOL_PATH"])
    return json.loads(path.read_bytes()), hashlib.sha256(path.read_bytes()).hexdigest()


def test_complete_five_dataset_fit_accounting(protocol):
    actual, raw = protocol
    plan = compile_plan(actual, protocol_file_sha256=raw)
    assert plan["counts"] == {"encoders": 27, "main_groups": 41, "auxiliary_groups": 21,
        "maximum_fits": 1674, "all_output_tasks": 35, "primary_endpoints": 32,
        "primary_cells": 239, "all_task_cells": 269}
    assert len({row["fit_id"] for row in plan["fits"]}) == 1674
    assert sum(row["dataset_id"] == "expansionrx" for row in plan["fits"]) == 54
    assert all(row["fold_id"] == "official" for row in plan["fits"] if row["dataset_id"] == "expansionrx")
    assert not any(row["readout"] == "raw_mean_h0_linear" for row in plan["fits"] if row["output_level"] == "atom")
    expansion = next(row for row in plan["groups"] if row["dataset_id"] == "expansionrx")
    assert expansion["units"] == [actual["downstream"]["analysis_rules"]["endpoints"][name]["units"]
                                  for name in expansion["endpoints"]]
    assert expansion["units"][0] == "source_label:LogD"


def test_scope_reduction_resealed_still_rejected(protocol):
    original, raw = protocol
    changed = deepcopy(original)
    changed["strategies"]["joint"]["variants"] = ["SDP"]
    changed["content_sha256"] = digest({key: value for key, value in changed.items() if key != "content_sha256"})
    with pytest.raises(FormalReadoutError, match="coverage"):
        compile_plan(changed, protocol_file_sha256=raw)


def test_source_typed_wandb_float_spelling_exact():
    expected = {"loss": 0.0, "updates": 1, "mode": "fixed", "flag": False}
    restored = verify_wire_payload({"loss": 0, "updates": 1, "mode": "fixed", "flag": False, "_step": 0}, expected)
    assert type(restored["loss"]) is float and type(restored["updates"]) is int
    for bad in ({"loss": 1e-15, "updates": 1, "mode": "fixed", "flag": False},
                {"loss": 0, "updates": True, "mode": "fixed", "flag": False},
                {"loss": 0, "updates": 1, "mode": "fixed", "flag": False, "unknown": 0}):
        with pytest.raises(FormalReadoutError):
            verify_wire_payload(bad, expected)
