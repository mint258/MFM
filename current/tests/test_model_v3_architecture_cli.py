"""C CLI transport/integration tests; UNIT evidence never grants Data authority."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from phychem_mfm.phase1 import v3_architecture_readiness as readiness
from phychem_mfm.phase1.v3_sample_budget_events import binding, read_bound, write_once
from test_model_v3_architecture_readiness import setup, registry


ROOT = Path(__file__).absolute().parents[2]


@pytest.fixture
def cli():
    path = ROOT / "tools/model_v3/prepare_architecture_experiment.py"
    spec = importlib.util.spec_from_file_location("architecture_cli_UNIT", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def case(setup, tmp_path):
    """A real fixed Git policy blob, but no real Data release or run authority."""
    request, config, policy, trials, resolutions, base_ref = setup
    repo = tmp_path / "UNIT_policy_repository"
    repo.mkdir()
    document = {"schema": "model_v3_decision_policy_v1", "rules": policy.rules}
    policy_file = repo / "policy.json"
    policy_file.write_text(json.dumps(document, sort_keys=True, allow_nan=False) + "\n")
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    git("init", "-q")
    git("add", "policy.json")
    git("-c", "user.name=UNIT", "-c", "user.email=unit@example.invalid",
        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
        "commit", "-qm", "UNIT policy, no scientific authority")
    sha = binding(policy_file)["sha256"]
    reference = {"repository": str(repo), "commit": git("rev-parse", "HEAD"),
                 "path": "policy.json", "sha256": sha}
    return request, config, trials, resolutions, base_ref, reference, sha


def invoke(cli, tmp_path, command, manifest, *, output=None, sha=None):
    reference = write_once(tmp_path / "CLI_inputs.json", manifest)
    output = output or tmp_path / "CLI_output"
    result = cli.main([command, "--inputs", reference["path"], "--inputs-sha256",
                       sha or reference["sha256"], "--output", str(output)])
    return result, reference


def transport(case, index=0):
    _, _, trials, _, base_ref, policy, sha = case
    return {"policy": policy, "policy_sha256": sha,
            "trial": asdict(trials[index]), "base_request": base_ref}


def test_resolve_dispatches_bound_inputs_and_fixed_policy_without_admitting(case, cli, tmp_path, monkeypatch):
    _, _, _, _, _, policy_ref, sha = case
    source = write_once(tmp_path / "UNIT_resolution.json",
                        {"scope": "UNIT_DISPATCH_ONLY_NOT_CLOSED_SELECTION"})
    calls = []
    def resolve(reference, policy):
        calls.append((reference, policy))
        return {"inputs": reference, "policy_sha256": policy.sha256}
    monkeypatch.setattr(readiness, "resolve_inputs", resolve)
    result_ref, manifest_ref = invoke(cli, tmp_path, "resolve",
        {"policy": policy_ref, "policy_sha256": sha, "resolution_inputs": source})
    result = read_bound(result_ref)
    assert len(calls) == 1 and calls[0][0] == source
    assert calls[0][1].reference == policy_ref and calls[0][1].sha256 == sha
    assert result == {"inputs": source, "policy_sha256": sha, "input_manifest": manifest_ref}
    assert "Root_admission" not in result and "configuration" not in result


@pytest.mark.parametrize("index", (0, 6, 19))
def test_prepare_dispatch_preserves_trial_and_reuses_real_compiler_only_as_UNIT(case, cli, tmp_path, monkeypatch, index):
    request, config, trials, resolutions, base_ref, policy_ref, sha = case
    before = deepcopy((request, config))
    source = write_once(tmp_path / "UNIT_resolution.json", {"scope": "UNIT_TRANSPORT_ONLY"})
    resolved = deepcopy(resolutions)
    resolved.update(inputs=source, policy_sha256=sha)
    for name in ("C1", "C3"):
        resolved[name]["policy_sha256"] = sha
    resolved_calls = []
    def resolve(reference, policy):
        resolved_calls.append((reference, policy.sha256))
        return resolved
    calls = []
    def prepare(trial, base, selections, policy, output, *, base_request_ref):
        # Only the dispatcher is isolated. No production Data gate is mocked PASS.
        # This callback compiles an explicitly UNIT proposal, never a request.
        assert trial == trials[index] and base == request and base_request_ref == base_ref
        assert selections == resolved and policy.reference == policy_ref
        compiled = readiness.compile_trial(trial, config, selections, policy, registry=registry())
        calls.append(trial.scientific_identity)
        output.mkdir()
        return write_once(output / "UNIT_ONLY.json",
            {"scope": "UNIT_COMPILER_DISPATCH_NOT_DATA_AUTHORITY", "configuration": compiled})
    monkeypatch.setattr(readiness, "resolve_inputs", resolve)
    monkeypatch.setattr(readiness, "prepare_trial", prepare)
    manifest = {**transport(case, index), "resolution_inputs": source}
    result_ref, _ = invoke(cli, tmp_path, "prepare", manifest)
    result = read_bound(result_ref)
    compiled = result["configuration"]
    assert calls == [trials[index].scientific_identity] and resolved_calls == [(source, sha)]
    assert compiled["model"]["backbone"]["distance_bias_projection_bias"] is False
    assert compiled["model"]["backbone"]["dim"] == 512 and compiled["model"]["backbone"]["layers"] == 6
    assert compiled["proxy_contract"]["views"] == ("three" if index == 0 else "two" if index == 19 else "two")
    assert "$" not in json.dumps(compiled) and "training_execution" not in compiled
    if index == 19:
        assert compiled["proxy_contract"]["heads"]["pooling_overrides"] == {
            "p_extensive": "learned", "p_intensive": "learned"}
    assert not (tmp_path / "CLI_output/request.UNADMITTED.json").exists()
    assert (request, config) == before


@pytest.mark.parametrize("mode", ("synthetic_engineering", "authoritative_pilot",
                                 "authoritative_full_train", "authoritative_grid_train"))
def test_real_prepare_rejects_other_modes_without_creating_output(case, cli, tmp_path, mode):
    request = deepcopy(case[0])
    request["mode"] = mode
    base = write_once(tmp_path / "UNIT_wrong_mode.json", request)
    with pytest.raises(ValueError, match="authoritative D5 proxy"):
        invoke(cli, tmp_path, "prepare", {**transport(case), "base_request": base})
    assert not (tmp_path / "CLI_output").exists()


def test_relabelled_UNIT_request_does_not_bypass_actual_scientific_gate(case, cli, tmp_path):
    request = deepcopy(case[0])
    request["mode"] = "authoritative_proxy"
    base = write_once(tmp_path / "UNIT_relabelled_not_authority.json", request)
    with pytest.raises(ValueError, match="Synthetic execution"):
        invoke(cli, tmp_path, "prepare", {**transport(case), "base_request": base})
    assert not (tmp_path / "CLI_output").exists()


@pytest.mark.parametrize("wrong", ("0" * 64, "bad"))
def test_wrong_manifest_sha_cannot_create_output(case, cli, tmp_path, wrong):
    with pytest.raises(ValueError):
        invoke(cli, tmp_path, "prepare", transport(case), sha=wrong)
    assert not (tmp_path / "CLI_output").exists()


@pytest.mark.parametrize("extra", ("registry", "configuration", "training_execution"))
def test_cli_cannot_override_registry_model_or_runtime(case, cli, tmp_path, extra):
    with pytest.raises(ValueError, match="declared architecture command"):
        invoke(cli, tmp_path, "prepare", {**transport(case), extra: {}})
    assert not (tmp_path / "CLI_output").exists()


def test_stale_policy_sha_is_rejected_before_output(case, cli, tmp_path):
    with pytest.raises(ValueError, match="registration SHA"):
        invoke(cli, tmp_path, "prepare", {**transport(case), "policy_sha256": "0" * 64})
    assert not (tmp_path / "CLI_output").exists()


def test_real_resolution_gate_rejects_unknown_evidence_schema(case, cli, tmp_path):
    source = write_once(tmp_path / "UNIT_unknown_resolution.json",
                        {"schema": "UNIT_UNKNOWN_NOT_ACTUAL_RUNS"})
    with pytest.raises(ValueError, match="selection inputs"):
        invoke(cli, tmp_path, "resolve", {"policy": case[5], "policy_sha256": case[6],
                                         "resolution_inputs": source})
    assert not (tmp_path / "CLI_output").exists()


@pytest.mark.parametrize("kind", ("existing", "inside_repository"))
def test_outputs_must_be_fresh_and_outside_source(case, cli, tmp_path, kind):
    output = tmp_path / "existing"
    if kind == "existing":
        output.mkdir()
    else:
        output = ROOT / "FORBIDDEN_CLI_UNIT_OUTPUT"
        assert not output.exists()
    with pytest.raises(ValueError, match="Fresh outside-Git"):
        invoke(cli, tmp_path, "prepare", transport(case), output=output)
    assert not (output / "request.UNADMITTED.json").exists()
