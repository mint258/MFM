"""Actual CPU selective-bf16 training/recovery; never a proxy or CUDA result."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from test_model_v3_trainer import UnitTracker
from test_model_v3_training import assert_tree_equal
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry
from phychem_mfm.phase1.v3_losses import V3LossResult
from phychem_mfm.phase1.v3_precision_experiment import (PrecisionPlan, PrecisionValidationAccumulator,
    bind_authoritative_inputs, compare_precision_members, validate_role_sources, B_VALIDATION_AUTHORITY)
from phychem_mfm.phase1.v3_precision_synthetic import synthetic_inputs, build_precision_member
from phychem_mfm.phase1.v3_training import capture_rng_state


@pytest.fixture(autouse=True)
def cpu_environment():
    original_threads = torch.get_num_threads()
    original_tf32 = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    try:
        yield
    finally:
        torch.set_num_threads(original_threads)
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = original_tf32


def member(plan, *, seed=0, precision="fp32", run_id="unit-member"):
    root = Path(__file__).parents[2]
    names = ("current/phychem_mfm/phase1/v3_precision_experiment.py", "current/phychem_mfm/phase1/v3_precision_synthetic.py",
             "current/phychem_mfm/phase1/v3_trainer.py", "current/phychem_mfm/model/v3_performance.py")
    source = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    return build_precision_member(synthetic_inputs(), plan, seed=seed, precision=precision,
        tracker=UnitTracker(run_id), source_bindings=source, code_sha="c" * 40, allow_unit_tracker=True)


def test_rmse_uses_true_vector_population_not_field_mean_loss():
    field = FieldSpec("noise", "S", "structural", "atom", kind="denoise_eps_mse", representation="vector", unit="angstrom")
    registry = LabelRegistry((field,), "synthetic", "a" * 64)
    meter = PrecisionValidationAccumulator(registry, role="VAL", enabled_groups=("S",))
    prediction = torch.tensor([[3., 0., 0.], [0., 4., 0.]])
    target = FieldTarget(torch.zeros_like(prediction), torch.ones(2, dtype=torch.bool))
    zero = torch.tensor(123.)  # deliberately not a raw-error mean
    loss = V3LossResult(zero, {"noise": zero}, {"S": zero}, {"noise": 2}, {"S": 1}, ("S",))
    meter.add({"noise": prediction}, {"noise": target}, loss)
    row = meter.result()["fields"]["noise"]
    assert row["squared_error_sum"] == 25 and row["component_denominator"] == 6
    assert row["RMSE"] == pytest.approx((25 / 6)**.5)
    assert row["vector_RMSE"] == pytest.approx((25 / 2)**.5)
    assert row["eps_component_RMSE"] == pytest.approx(row["RMSE"] / .1)
    assert row["unit"] == "angstrom" and row["sigma"] == .1


@pytest.mark.parametrize("precision", ("fp32", "bf16"))
def test_actual_cpu_member_resume_matches_uninterrupted_model_optimizer_rng_and_curves(tmp_path, precision):
    plan = PrecisionPlan("synthetic", 4, (0, 2, 4), (4,), 2, 8)
    original = member(plan, precision=precision)
    first = tmp_path / "first"; first.mkdir()
    paused = original.run(first, until_update=2)
    assert paused["status"] == "SEGMENT_PAUSED" and paused["optimizer_updates"] == 2
    checkpoint, = first.glob("checkpoint_*")
    before_continue = capture_rng_state()
    continuation = tmp_path / "uninterrupted"; continuation.mkdir()
    original.run(continuation)
    expected = (deepcopy(original.trainer.model.state_dict()), deepcopy(original.trainer.optimizer.state_dict()),
                original.trainer.scheduler.state_dict(), original.trainer.sampler.state_dict(),
                original.trainer.provider.state_dict(), deepcopy(original.points), capture_rng_state())
    restored = member(plan, precision=precision, run_id="unit-resumed")
    restored.load(checkpoint, output_root=first)
    assert_tree_equal(before_continue, capture_rng_state())
    assert restored.points["0"] == original.points["0"]
    resumed = tmp_path / "resumed"; resumed.mkdir()
    result = restored.run(resumed)
    actual = (restored.trainer.model.state_dict(), restored.trainer.optimizer.state_dict(),
              restored.trainer.scheduler.state_dict(), restored.trainer.sampler.state_dict(),
              restored.trainer.provider.state_dict(), restored.points, capture_rng_state())
    assert_tree_equal(expected, actual)
    assert result["optimizer_updates"] == 4 and result["samples_consumed"] == 8
    assert result["scientific_acceptance"] is False
    assert restored.trainer.resume_parent["id"] == "unit-member"
    assert set(result["validation"]["4"]) == {"VAL", "TRAIN_UNSEEN_CONFORMATION"}
    assert all(p.dtype == torch.float32 for p in restored.trainer.model.parameters())
    assert not any(row["event"] == "VALIDATION" and row["optimizer_updates"] == 0 for row in restored.trainer.tracker.records)
    with pytest.raises(FileExistsError):
        restored.save(checkpoint, output_root=first)


def test_authority_and_real_endpoint_fail_closed_without_d5():
    with pytest.raises(ValueError, match="exactly20000"):
        PrecisionPlan("authoritative_proxy", 2, (2,), (2,), 2, 4)
    with pytest.raises(ValueError, match="authoritative D5"):
        bind_authoritative_inputs(object(), {})
    fake = SimpleNamespace(verify_and_bind_model_v3_precision_inputs=lambda request: synthetic_inputs())
    with pytest.raises(ValueError, match="TRAIN molecule/conformer"):
        bind_authoritative_inputs(fake, {})
    requests = []
    def too_small(request):
        requests.append(request)
        inputs = synthetic_inputs()
        return replace(inputs, index=replace(inputs.index, authority="data_line"))
    with pytest.raises(ValueError, match="exactly240000 TRAIN molecules"):
        bind_authoritative_inputs(SimpleNamespace(verify_and_bind_model_v3_precision_inputs=too_small), {})
    assert requests[0]["required_population"]["molecule_count"] == 240000
    assert requests[0]["required_population"]["geometry_source"] == "PM7"
    assert requests[0]["required_population"]["allowed_conformations"] == "all_authoritatively_allowed"
    assert requests[0]["required_verification"]["same_gpu_environment_for_all_four_runs"] is True
    with pytest.raises(ValueError, match="Synthetic inputs"):
        build_precision_member(synthetic_inputs(), PrecisionPlan("authoritative_proxy"), seed=0, precision="fp32",
            tracker=UnitTracker(), source_bindings={"unit": "a" * 64}, code_sha="c" * 40, allow_unit_tracker=True)


def test_production_defaults_match_published_zero_500_grid_and_inner_authority():
    plan = PrecisionPlan("authoritative_proxy")
    assert plan.validation_updates == tuple(range(0, 20001, 500)) and plan.validation_seed == 0
    with pytest.raises(ValueError, match="published B grid/noise seed"):
        replace(plan, validation_updates=tuple(range(0, 20001, 1000)))
    with pytest.raises(ValueError, match="published B grid/noise seed"):
        replace(plan, validation_seed=20261025)
    populations = {"VAL": "a" * 64, "TRAIN_UNSEEN_CONFORMATION": "b" * 64}
    sources = {role: {"population_binding_sha256": digest, "purpose": "B_NUMERIC_GATE" if role == "VAL" else "DIAGNOSTIC_ONLY",
        "authority": B_VALIDATION_AUTHORITY if role == "VAL" else "separate_D5_TRAIN_conformation_diagnostic"}
        for role, digest in populations.items()}
    assert validate_role_sources(sources, populations, production=True) == ("VAL",)
    sources["VAL"]["authority"] = "external_VAL_cannot_replace_proxy_TRAIN_inner"
    with pytest.raises(ValueError, match="TRAIN-only molecular inner authority"):
        validate_role_sources(sources, populations, production=True)


def test_update_zero_checkpoint_restores_without_revalidating_or_consuming_samples(tmp_path):
    plan = PrecisionPlan("synthetic", 1, (0, 1), (1,), 2, 2)
    original = member(plan, precision="bf16")
    first = tmp_path / "zero"; first.mkdir()
    result = original.run(first, until_update=0)
    assert result["optimizer_updates"] == result["samples_consumed"] == 0
    assert set(result["validation"]) == {"0"}
    checkpoint, = first.glob("checkpoint_u0_*")
    restored = member(plan, precision="bf16", run_id="unit-zero-resumed")
    restored.load(checkpoint, output_root=first)
    assert restored.trainer.clock.optimizer_updates == restored.trainer.clock.samples_consumed == 0
    assert restored.trainer.provider.calls == 0
    assert_tree_equal(original.points, restored.points)
    root = tmp_path / "zero_resumed"; root.mkdir()
    restored.run(root)
    assert not any(row["event"] == "VALIDATION" and row["optimizer_updates"] == 0 for row in restored.trainer.tracker.records)
    assert restored.trainer.clock.optimizer_updates == 1 and restored.trainer.clock.samples_consumed == 2


def test_real_cli_missing_d5_rejects_before_sdk_model_or_output(tmp_path, monkeypatch):
    script = Path(__file__).parents[2] / "tools/model_v3/run_precision_experiment.py"
    spec = importlib.util.spec_from_file_location("precision_cli_early_rejection", script)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setenv("SLURM_JOB_ID", "unit-interface-only")
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "16")
    destination = tmp_path / "must_remain_absent"
    args = module.parser().parse_args(["member", "--precision", "bf16", "--seed", "0",
        "--code-sha", "c" * 40, "--prereg-sha", "d" * 40, "--output", str(destination)])
    with pytest.raises(ValueError, match="Awaiting authoritative D5"):
        module.run_member(args)
    assert not destination.exists()


def test_resume_rejects_changed_member_and_incomplete_checkpoint(tmp_path):
    plan = PrecisionPlan("synthetic", 2, (0, 2), (2,), 2, 4)
    original = member(plan)
    original.trainer.next_step(2)
    original.save(tmp_path / "checkpoint", output_root=tmp_path)
    wrong_member = member(plan, precision="bf16")
    before = deepcopy(wrong_member.trainer.model.state_dict())
    with pytest.raises(ValueError, match="member/config/source"):
        wrong_member.load(tmp_path / "checkpoint", output_root=tmp_path)
    assert_tree_equal(before, wrong_member.trainer.model.state_dict())
    partial = tmp_path / "partial"; partial.mkdir()
    with pytest.raises(FileNotFoundError):
        member(plan).load(partial, output_root=tmp_path)


def test_four_actual_cpu_members_and_full_curve_rejections(tmp_path):
    plan = PrecisionPlan("synthetic", 1, (0, 1), (1,), 2, 2)
    results = []
    for precision in ("fp32", "bf16"):
        for seed in (0, 1):
            root = tmp_path / f"{precision}_{seed}"; root.mkdir()
            experiment = member(plan, precision=precision, seed=seed)
            results.append(experiment.run(root))
            del experiment
    audit = compare_precision_members(results)
    assert audit["status"] == "SYNTHETIC_HARNESS_ONLY" and audit["scientific_acceptance"] is False
    # Four actual curves are retained regardless of whether the strict gate passes.
    assert set(audit["roles"]) == {"VAL", "TRAIN_UNSEEN_CONFORMATION"}
    assert audit["gate_roles"] == ["VAL"]
    assert all(row["denoising_2_percent"] is not None for role in audit["roles"].values() for row in role["results"])
    changed = deepcopy(results)
    changed[-1]["validation"]["1"]["VAL"]["population"]["s_noise"]["sigma"] = .2
    with pytest.raises(ValueError, match="units/sigma/effective population"):
        compare_precision_members(changed)
    changed = deepcopy(results); changed[-1]["optimizer_updates"] = 0
    with pytest.raises(ValueError, match="endpoint"):
        compare_precision_members(changed)
    changed = deepcopy(results); changed[-1]["contract"]["comparison_binding"]["source_files"]["new"] = "0" * 64
    with pytest.raises(ValueError, match="source/data/plan"):
        compare_precision_members(changed)
    changed = deepcopy(results); del changed[-1]["validation"]["0"]
    with pytest.raises(ValueError, match="Complete identical validation grid"):
        compare_precision_members(changed)
