from tools.evaluate_target_adequacy import reassess_convergence
from tools.compare_exposure_scaling import _row_order


def _point(total, energy, charge=1.0):
    return {
        "val/loss/selection": total,
        "val/loss/raw/energy": energy,
        "val/loss/raw/charge": charge,
    }


def test_reassessment_does_not_inherit_obsolete_checkpoint_status():
    payload = {
        "global_exposure_step": 50_000,
        "optimizer_update_step": 500,
        "schedule": {
            "name": "delayed_v1",
            "descriptor_start_fraction_of_pass": 0.10,
            "descriptor_ramp_fraction_of_pass": 0.03,
            "stage1_decay_fraction_of_pass": 0.03,
            "stage1_floor": 0.3,
        },
        "discovery": {
            "pass_count": 1,
            "unique_structure_count": 50_000,
            "cumulative_structure_exposure": 50_000,
            "validation_history": [
                _point(1.00, 1.00),
                _point(1.02, 0.96),
                _point(1.03, 0.91),
                _point(1.04, 0.86),
            ],
            "convergence": {
                "status": "DIVERGED",
                "optimization_mature": False,
                "reasons": ["total_worsened"],
            },
        },
    }

    original, current = reassess_convergence(payload, target_adequate=False)

    assert original["status"] == "DIVERGED"
    assert current.status == "STILL_IMPROVING"
    assert not current.optimization_mature


def test_scaling_rows_have_stable_exposure_order():
    rows = [
        {"unique_structures": 200, "total_exposure": 200, "checkpoint_sha256": "b"},
        {"unique_structures": 50, "total_exposure": 50, "checkpoint_sha256": "a"},
        {"unique_structures": 100, "total_exposure": 100, "checkpoint_sha256": "c"},
    ]
    assert [row["unique_structures"] for row in sorted(rows, key=_row_order)] == [50, 100, 200]
