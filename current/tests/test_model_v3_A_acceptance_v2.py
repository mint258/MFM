"""CPU mechanism tests only; no CUDA/real data/A-class qualification."""
from argparse import ArgumentParser, Namespace
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import torch

from phychem_mfm.training.v3_performance_acceptance import (
    a_gradient_contract_v2, a_gradient_contract_sha256_v2,
    compare_tensors, compare_gradient_elements, compare_gradients_v2,
    analytic_zero_gradient_parameters, a_equivalence_report,
)


def tensor(values):
    return torch.tensor(values, dtype=torch.float64)


def test_v2_fixed_semantics_and_canonical_contract_hash():
    contract = a_gradient_contract_v2()
    expected = hashlib.sha256(json.dumps(contract, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert a_gradient_contract_sha256_v2() == expected
    assert contract["elementwise"]["atol"] == 1e-8
    assert contract["elementwise"]["rtol"] == 1e-4
    assert contract["analytic_zero"]["both_L2_norm_max"] == 1e-8
    contract["elementwise"]["atol"] = 100
    assert a_gradient_contract_v2()["elementwise"]["atol"] == 1e-8


@pytest.mark.parametrize("candidate,passed", [(0., True), (1e-12, False)])
def test_zero_atol_zero_reference_has_no_relative_allowance(candidate, passed):
    result = compare_gradient_elements({"p": tensor([0.])}, {"p": tensor([candidate])},
        atol=0., rtol=1e-4)
    assert result["pass"] is passed
    assert result["tensors"][0]["violating_elements"] == (0 if passed else 1)


def test_nonzero_reference_relative_allowance_and_direction_are_explicit():
    assert compare_gradient_elements({"p": tensor([1.])}, {"p": tensor([1.00005])},
        atol=0., rtol=1e-4)["pass"]
    ref, cand = tensor([1.]), tensor([1.000100015])
    assert not compare_gradients_v2({"p": ref}, {"p": cand}, analytic_zero_names=())["pass"]
    assert compare_gradients_v2({"p": cand}, {"p": ref}, analytic_zero_names=())["pass"]


def test_one_violating_element_cannot_hide_behind_tensor_L2():
    ref = torch.ones(10000)
    cand = ref.clone()
    cand[0] += .001
    assert compare_tensors({"p": ref}, {"p": cand}, tolerance=1e-4)["pass"]
    row = compare_gradients_v2({"p": ref}, {"p": cand},
        analytic_zero_names=())["tensors"][0]
    assert not row["pass"] and row["violating_elements"] == 1


def test_exact_absolute_boundary_and_nextafter():
    bound = tensor([1e-8])
    above = torch.nextafter(bound, tensor([float("inf")]))
    assert compare_gradients_v2({"p": tensor([0.])}, {"p": bound},
        analytic_zero_names=())["pass"]
    assert not compare_gradients_v2({"p": tensor([0.])}, {"p": above},
        analytic_zero_names=())["pass"]


@pytest.mark.parametrize("side", ["reference", "candidate", "both"])
def test_analytic_zero_requires_both_norms_even_when_elements_pass(side):
    tiny = tensor([7.5e-9, 7.5e-9])
    ref = tiny if side in ("reference", "both") else torch.zeros_like(tiny)
    cand = tiny if side in ("candidate", "both") else torch.zeros_like(tiny)
    report = compare_gradients_v2({"p": ref}, {"p": cand}, analytic_zero_names=("p",))
    row = report["tensors"][0]
    assert row["elementwise_pass"] and not row["analytic_zero_norm_pass"]
    assert not report["pass"]
    assert row["reference_norm"] is not None and row["candidate_norm"] is not None


def test_analytic_zero_norm_exact_boundary_is_inclusive():
    report = compare_gradients_v2({"p": tensor([1e-8])}, {"p": tensor([1e-8])},
        analytic_zero_names=("p",))
    assert report["pass"]
    assert report["tensors"][0]["reference_norm"] == 1e-8


@pytest.mark.parametrize("left,right,zero,passed,reason", [
    (None, None, (), True, "both_disabled"),
    (None, tensor([0.]), (), False, "missing_gradient_mismatch"),
    (tensor([0.]), None, (), False, "missing_gradient_mismatch"),
    (None, None, ("p",), False, "analytic_zero_gradient_missing"),
])
def test_disabled_heads_and_missing_active_analytic_gradients(left, right, zero, passed, reason):
    result = compare_gradients_v2({"p": left}, {"p": right}, analytic_zero_names=zero)
    assert result["pass"] is passed and result["tensors"][0]["reason"] == reason


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_is_failure_with_JSON_finite_metadata(bad):
    result = compare_gradients_v2({"p": tensor([0.])}, {"p": tensor([bad])},
        analytic_zero_names=("p",))
    assert not result["pass"] and result["tensors"][0]["reason"] == "nonfinite"
    json.dumps(result, allow_nan=False)


def test_set_shape_zero_registry_and_dtype_mismatches_are_not_hidden():
    with pytest.raises(ValueError, match="names"):
        compare_gradients_v2({"a": tensor([0.])}, {"b": tensor([0.])}, analytic_zero_names=())
    assert not compare_gradients_v2({"p": tensor([0.])}, {"p": tensor([[0.]])},
        analytic_zero_names=())["pass"]
    for names in (("not_present",), ("p", "p")):
        with pytest.raises(ValueError, match="analytic-zero"):
            compare_gradients_v2({"p": tensor([0.])}, {"p": tensor([0.])}, analytic_zero_names=names)
    with pytest.raises(ValueError, match="floating"):
        compare_gradients_v2({"p": torch.tensor([0])}, {"p": torch.tensor([0])},
            analytic_zero_names=())


def test_empty_tensor_audit_and_old_v1_reports_are_unchanged():
    old = compare_tensors({"p": tensor([1.])}, {"p": tensor([1.])}, tolerance=1e-4)
    assert old == {"pass": True, "tolerance": 1e-4,
                  "tensors": [{"name": "p", "relative_l2": 0., "max_absolute": 0., "pass": True}]}
    report = a_equivalence_report([{"p": tensor([1.])}], [{"p": tensor([1.])}],
        [{"p": None}], [{"p": None}], expected_batches=1)
    assert set(report) == {"gate", "batches", "pass", "results"}
    assert report["pass"] and report["results"][0]["gradient"]["tolerance"] == 1e-4
    empty = compare_gradients_v2({"p": torch.empty(0)}, {"p": torch.empty(0)},
        analytic_zero_names=())
    assert empty["pass"] and empty["tensors"][0]["elements"] == 0


def model_config(dim=512, heads=8, layers=6):
    return {"architecture": {"preset": "shared_light"},
        "backbone": {"n_atom_types": 119, "dim": dim, "heads": heads, "layers": layers,
            "ff_mult": 2, "dropout": 0., "use_dist_bias": True, "use_radius_mask": False,
            "activation_checkpointing": True},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
            "geometry_rbf_count": 4, "geometry_hidden_dim": 8}}


def workflow_path(monkeypatch):
    root = Path(__file__).absolute().parents[2]
    monkeypatch.syspath_prepend(str(root / "workflows/sprime_s/scripts"))
    return root


def test_real_six_layer_parameter_identity_shapes_and_no_RNG_or_parameter_mutation(monkeypatch):
    workflow_path(monkeypatch)
    from s_model_memory_v1 import build_memory_bounded_model
    from phychem_mfm.model.v3_performance import build_performance_model, PerformanceOptions
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(241)
        ref = build_memory_bounded_model(model_config())
        torch.random.default_generator.manual_seed(241)
        cand = build_performance_model(model_config(), PerformanceOptions(backbone_checkpointing=True),
            execution={"checkpoint_policy": "manual"})
        names = [f"backbone.layers.{i}.attn.dist_mlp.2.bias" for i in range(6)]
        for model in (ref, cand):
            before = {name: id(p) for name, p in model.named_parameters()}
            rng = torch.random.get_rng_state().clone()
            proof = analytic_zero_gradient_parameters(model)
            assert [row["name"] for row in proof] == names
            assert all(row["shape"] == [8] and row["dimension"] == 512 for row in proof)
            assert all(row["parameter_identity_checked"] and not row["exact_IEEE_zero_claimed"] for row in proof)
            assert before == {name: id(p) for name, p in model.named_parameters()}
            assert torch.equal(rng, torch.random.get_rng_state())
            assert all(p.dtype == torch.float32 for p in model.parameters())


@pytest.mark.parametrize("kind", ["missing_layer", "wrong_heads", "no_bias", "foreign_attention"])
def test_zero_list_requires_complete_real_semantics_not_name_or_smallness(monkeypatch, kind):
    workflow_path(monkeypatch)
    from phychem_mfm.factory import build_model
    from phychem_mfm.model.attention import DenseGeoSelfAttention
    with torch.random.fork_rng(devices=[]):
        model = build_model(model_config(dim=16, heads=2))
    if kind == "missing_layer":
        model.backbone.layers = model.backbone.layers[:-1]
    elif kind == "wrong_heads":
        model.backbone.layers[0].attn.nheads = 3
    elif kind == "no_bias":
        model.backbone.layers[0].attn.dist_mlp[2].bias = None
    else:
        class UnregisteredAttention(DenseGeoSelfAttention):
            pass
        model.backbone.layers[0].attn.__class__ = UnregisteredAttention
    with pytest.raises(ValueError):
        analytic_zero_gradient_parameters(model)


@pytest.fixture
def paired(monkeypatch):
    root = workflow_path(monkeypatch)
    monkeypatch.syspath_prepend(str(root / "tools/model_v3"))
    spec = importlib.util.spec_from_file_location("A_v2_paired_unit",
        root / "tools/model_v3/paired_a_acceptance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def publication_inputs(tmp_path, paired):
    # Mechanism-only fixture, never an actual publication/GPU qualification.
    document = tmp_path / "rules.md"
    document.write_bytes(b"UNIT ONLY - not scientific authority\n")
    checker = tmp_path / "checker.json"
    checker.write_text('{"scope":"unit-only"}\n')
    def rawref(path):
        raw = path.read_bytes()
        return {"path": str(path.absolute()), "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}
    raw = document.read_bytes()
    commit = "1" * 40
    pub = {"schema": "model_v3_exact_tree_publication_actual_v1",
        "repository_full_name": "mint258/MFM", "public_code_sha": commit, "tree_sha": "2" * 40,
        "public_branch_readback_verified": True, "public_Git_API_tree_readback_verified": True,
        "checker_closure": rawref(checker),
        "files": [{"path": paired._RULE_DOCUMENT_REPO_PATH, "mode": "100644", "type": "blob",
                   "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}]}
    publication = tmp_path / "publication.json"
    publication.write_text(json.dumps(pub))
    args = Namespace(acceptance_version="v2", acceptance_rule_document=document,
        acceptance_rule_document_sha256=rawref(document)["sha256"], acceptance_prereg_sha=commit,
        acceptance_rule_publication=publication,
        acceptance_rule_publication_sha256=rawref(publication)["sha256"],
        fixed_batch_only=False, smoke=False, export_candidate_checkpoint=None)
    return args, pub


def test_cli_binding_records_exact_rule_publication_sources_and_v1_no_keys(paired, tmp_path):
    parser = ArgumentParser()
    paired.add_acceptance_arguments(parser)
    old = parser.parse_args([])
    assert paired.bind_acceptance_rules(old) is None
    args, pub = publication_inputs(tmp_path, paired)
    result = paired.bind_acceptance_rules(args)
    assert result["version"] == "v2" and result["public_rule_commit"] == args.acceptance_prereg_sha
    assert result["public_rule_blob"] == pub["files"][0]["sha"]
    assert set(result["source_refs"]) == {"rule_document", "Root_publication", "publication_checker_closure"}
    assert result["network_or_Git_verification_performed_by_child"] is False


@pytest.mark.parametrize("kind", ["only_public40", "wrong_blob", "false_readback", "conflicting_repo", "changed_doc"])
def test_actual_receipt_and_blob_required_not_a_self_declared_public40(paired, tmp_path, kind):
    args, pub = publication_inputs(tmp_path, paired)
    if kind == "only_public40":
        args.acceptance_rule_publication = None
    elif kind == "changed_doc":
        args.acceptance_rule_document.write_bytes(b"changed")
    else:
        if kind == "wrong_blob":
            pub["files"][0]["sha"] = "3" * 40
        elif kind == "false_readback":
            pub["public_Git_API_tree_readback_verified"] = False
        else:
            pub["repository"] = "other/repository"
        args.acceptance_rule_publication.write_text(json.dumps(pub))
        args.acceptance_rule_publication_sha256 = hashlib.sha256(
            args.acceptance_rule_publication.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        paired.bind_acceptance_rules(args)


@pytest.mark.parametrize("kind", ["smoke", "export", "v1"])
def test_fixed_only_scope_cannot_silently_reduce_new_full_trial(paired, tmp_path, kind):
    args, _ = publication_inputs(tmp_path, paired)
    args.fixed_batch_only = True
    if kind == "smoke":
        args.smoke = True
    elif kind == "export":
        args.export_candidate_checkpoint = tmp_path / "not_created_export"
    else:
        args.acceptance_version = "v1"
    with pytest.raises(ValueError):
        paired.bind_acceptance_rules(args)


def test_fixed_only_request_is_explicit_and_publication_repository_alias_is_consistent(paired, tmp_path):
    args, pub = publication_inputs(tmp_path, paired)
    pub["repository"] = pub["repository_full_name"]
    args.acceptance_rule_publication.write_text(json.dumps(pub))
    args.acceptance_rule_publication_sha256 = hashlib.sha256(args.acceptance_rule_publication.read_bytes()).hexdigest()
    args.fixed_batch_only = True
    result = paired.bind_acceptance_rules(args)
    assert result["fixed_batch_only"] is True and result["version"] == "v2"
