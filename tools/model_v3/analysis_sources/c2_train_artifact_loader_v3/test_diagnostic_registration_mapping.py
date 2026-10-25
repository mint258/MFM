"""Metadata-only regression: local execution commit is not public publication."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import subprocess

import pytest

import coordinate_baseline_v2 as base
from test_accepted_train_artifact_v2 import make_diagnostic_registration


def git(reference, *args):
    return subprocess.run(["git", "-C", reference["repository"], *args], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()


def test_distinct_real_local_and_public_commits_verify_same_tree_and_exact_blob(tmp_path, monkeypatch):
    local, public = make_diagnostic_registration(tmp_path)
    monkeypatch.setattr(base, "DIAGNOSTIC_PREREGISTRATION", public["commit"])
    original = {"protocol_registration": local, "public_registration": public}
    binding = {"protocol_registration": deepcopy(local)}
    proof = base.validate_diagnostic_registration(original, binding)
    assert local["commit"] != public["commit"]
    assert git(local, "rev-parse", local["commit"]+"^{tree}") == git(local, "rev-parse", public["commit"]+"^{tree}")
    assert proof["executed_local_protocol_registration"] == local
    assert proof["public_registration"] == public and proof["verified_local_tree"] == public["tree"]
    assert proof["verified_protocol_blob_raw_sha256"] == base.DIAGNOSTIC_PROTOCOL_RAW_SHA256


@pytest.mark.parametrize("change", ["wrong_public", "wrong_local_ref", "wrong_tree", "wrong_blob", "absent_local_object", "missing_public", "source_inventory_drift"])
def test_wrong_mapping_component_is_rejected_independently(tmp_path, monkeypatch, change):
    local, public = make_diagnostic_registration(tmp_path)
    monkeypatch.setattr(base, "DIAGNOSTIC_PREREGISTRATION", public["commit"])
    original = {"protocol_registration": deepcopy(local), "public_registration": deepcopy(public)}
    binding = {"protocol_registration": deepcopy(local)}
    if change == "wrong_public": original["public_registration"]["commit"] = local["commit"]
    elif change == "wrong_local_ref": binding["protocol_registration"]["commit"] = public["commit"]
    elif change in ("wrong_tree", "wrong_blob"):
        path = Path(local["repository"])/("extra.txt" if change == "wrong_tree" else local["path"])
        path.write_text("synthetic changed tree" if change == "wrong_tree" else "synthetic wrong protocol blob")
        git(local, "add", path.name)
        git(local, "-c", "user.name=Synthetic Test", "-c", "user.email=fixture@example.invalid", "commit", "-m", "synthetic drift")
        changed = {**local, "commit": git(local, "rev-parse", "HEAD")}
        original["protocol_registration"] = changed
        binding["protocol_registration"] = deepcopy(changed)
        if change == "wrong_tree":
            assert hashlib.sha256(subprocess.run(["git", "-C", local["repository"], "show", changed["commit"]+":"+local["path"]],
                check=True, stdout=subprocess.PIPE).stdout).hexdigest() == base.DIAGNOSTIC_PROTOCOL_RAW_SHA256
    elif change == "absent_local_object":
        original["protocol_registration"]["commit"] = "f"*40
        binding["protocol_registration"] = deepcopy(original["protocol_registration"])
    elif change == "missing_public": original.pop("public_registration")
    else:
        current = base.support_runtime.executed_sources()
        monkeypatch.setattr(base.support_runtime, "executed_sources", lambda: {**current, "solver_math.py": "0"*64})
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        base.validate_diagnostic_registration(original, binding)


def test_real_closed_559_metadata_mapping_only_no_arrays_or_native_geometry(monkeypatch):
    def forbidden_array_decode(*args, **kwargs):
        raise AssertionError("Metadata-only regression must not decode parameter arrays")
    monkeypatch.setattr(base.np, "load", forbidden_array_decode)
    root = Path(os.environ.get("C2_CLOSED_559_ROOT", "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/C2_train_diagnostic_4520559"))
    path = root/"input_binding.json"
    if not path.is_file():
        if os.environ.get("C2_REQUIRE_REAL_559_METADATA") == "1": pytest.fail("Required closed 559 metadata missing")
        pytest.skip("Closed external 559 metadata is not part of the Git source package")
    template = base.support_runtime.bound_json(base.support_runtime.binding(Path(__file__).with_name("prior_TRAIN_artifact_v2_protocol.json")))
    binding_ref = {"path": str(path), "sha256": template["TRAIN_diagnostic_input_binding_raw_sha256"]}
    binding = base.support_runtime.bound_json(binding_ref)
    original = base.support_runtime.bound_json(binding["inputs"])
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest(),
        binding["inputs"]["path"]: hashlib.sha256(Path(binding["inputs"]["path"]).read_bytes()).hexdigest()}
    proof = base.validate_diagnostic_registration(original, binding)
    assert proof["executed_local_protocol_registration"]["commit"] != proof["public_registration"]["commit"]
    assert proof["public_registration"]["commit"] == base.DIAGNOSTIC_PREREGISTRATION
    assert proof["verified_local_tree"] == original["public_registration"]["tree"]
    assert before == {filename: hashlib.sha256(Path(filename).read_bytes()).hexdigest() for filename in before}
    # Deliberately no np.load, Source constructor, records(), prediction or VAL.
