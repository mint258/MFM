"""Registered factorial and restart-preservation checks; metadata only."""
from collections import Counter
import json
from pathlib import Path

import pytest

from analysis_plan import configurations, materialize, assign, second_batch_configurations


@pytest.fixture
def plan():
    path = Path(__file__).resolve().parents[2]/"configs/p_recipe/fixed_20261115/analysis_20261122/plan.json"
    return json.loads(path.read_text())


def test_exact_factorial_does_not_create_new_frozen_runs(plan):
    rows = configurations(plan)
    assert len(rows) == len({r["run"] for r in rows}) == 120
    assert Counter(r["mode"] for r in rows) == {"full":84,"top2":24,"scratch":12}
    assert set(Counter(r["task"] for r in rows).values()) == {30}
    assert all(not r["ready"] and r["node"] is None and r["gpu_uuid"] is None for r in rows)
    assert all(r["pretraining_seed"] is None for r in rows if r["mode"]=="scratch")
    assert all(r["source_binding"]["pretraining_samples_used"]==0 for r in rows if r["mode"]=="scratch")
    assert all(r["seed_role"]=="finetuning" for r in rows)


def test_registered_hyperparameters_cannot_be_overridden(plan):
    plan["protocol"]["optimizer"]["encoder_lr"] = 3e-4
    with pytest.raises(ValueError, match="optimizer"):
        configurations(plan)


def test_materialization_preserves_existing_assignment_and_closed_cursor(plan, tmp_path):
    path = tmp_path/"plan.json"
    path.write_text(json.dumps(plan))
    files = materialize(path)
    first = Path(files[0])
    active = json.loads(first.read_text())
    active.update(ready=True, node="compute-0-6", epoch=17, job_id="original-fixture")
    first.write_text(json.dumps(active))
    assert materialize(path) == files
    assert json.loads(first.read_text()) == active


def test_binding_a_target_does_not_activate_an_unvalidated_run(plan):
    c = configurations(plan)[0]
    bound = assign(c, node="compute-0-6", gpu_uuid="GPU-fixture",
        reservation_ids=["own-fixture"], nvidia_smi="/usr/bin/nvidia-smi",
        work_unit_seconds=3, unit_duration_basis="synthetic test")
    assert bound["ready"] is False and c["node"] is None
    with pytest.raises(ValueError):
        assign(c, node="compute-0-21", gpu_uuid="GPU-fixture",
            reservation_ids=["own-fixture"], nvidia_smi="/usr/bin/nvidia-smi",
            work_unit_seconds=3, unit_duration_basis="synthetic test")

def test_second_batch_has60_runs_and_does_not_add_a_new3M_baseline(plan):
    rows = second_batch_configurations(plan)
    assert len(rows) == len({r["run"] for r in rows}) == 60
    assert {r["source_binding"]["label"] for r in rows} == {
        "round2_M1","round2_B4","round2_B3","round3_M2","T4_9M"}
    assert all(r["mode"]=="full" and not r["ready"] for r in rows)
    assert "round4_F2" not in {r["source_binding"]["label"] for r in rows}
    baseline = next(r for r in plan["source_resolution"]["followup_bindings"] if r["label"]=="round4_F2")
    intermediate = next(r for r in plan["source_resolution"]["bindings"] if r["arm"]=="T2" and r["samples"]==3000000)
    assert baseline["source_training_budget"]==3000000
    assert intermediate["source_training_budget"]==9000000
    assert baseline["checkpoint"] != intermediate["checkpoint"]