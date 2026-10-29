"""Read forty Stage5 templates only; no Torch, data, model, tests or submission."""
import argparse
import json
from pathlib import Path


def check(root):
    plan = json.loads((root / "PLAN.json").read_text())
    rows = plan["first_seed_trials"]
    assert len(rows) == 20 and len({r["name"] for r in rows}) == 20
    assert plan["trial_counts"] == {"C1": 6, "C3": 4, "H": 9, "pooling": 1, "total": 20}
    assert plan["first_seed"] == 0 and plan["C4_status"] == "USER_V3_PASS_FP64_4524734_48_OF_48"
    assert plan["data_authority_created"] is False and plan["actual_experiments"] == []
    stages = {"C1": 0, "C3": 0, "H": 0, "pooling": 0}
    for row in rows:
        name = row["name"]
        stage = ("pooling" if name == "H_H1_P_learned_pooling" else
                 "C1" if name.startswith("C1_") else "C3" if name.startswith("C3_") else "H")
        stages[stage] += 1
        for kind in ("scientific", "smoke"):
            path = (root / row[kind]).resolve()
            assert path.is_relative_to(root.resolve())
            item = json.loads(path.read_text())
            assert item["trial_name"] == name and item["pretraining_seed"] == 0
            assert item["status"] == "DRAFT_NOT_TRAINABLE_NO_DATA_AUTHORITY" and item["request"] is None
            assert all(v is None for v in item["data_references"].values())
            assert item["C4"]["status"] == "PASS" and item["C4"]["FP32"] == "DIAGNOSTIC_ONLY_NOT_A_GATE"
            assert item["r674"] == {"loss": "LOSS_DISABLED", "retain_prediction_head": True,
                                     "additional_diagnostics": False}
            shape = item["model_shape"]
            assert (shape["layers"], shape["dim"], shape["heads"], shape["head_dim"],
                    shape["FFN_hidden"], shape["H0_dim"]) == (6, 512, 8, 64, 1024, 512)
            assert shape["dim"] % shape["heads"] == 0 and shape["FFN_hidden"] == shape["dim"] * 2
            assert item["execution"]["path"] == "plain_source_s_architecture"
            assert item["execution"]["training_execution"] is None
            assert item["model_overlay"]["backbone"]["distance_bias_projection_bias"] is False
            if kind == "smoke":
                smoke = item["wiring"]
                assert smoke["optimizer_updates_total"] == 50 and smoke["pilot_global_optimizer_update_cap"] == 2000
                assert smoke["distance"] == row["distance"] and smoke["views"] == row["views"]
                assert smoke["head_forms"] == row["head"] and smoke["pooling"] == row["pooling"]
                assert item["classification"] == "NOT_SELECTED_NOT_SCIENTIFIC"
                assert smoke["selected_C1"] is None and smoke["selected_C3"] is None
            else:
                proxy = item["proxy"]
                assert proxy["TRAIN_molecules"] == 240000 and proxy["geometry"] == "PM7"
                assert proxy["conformers"] == "all_authorized_D5" and proxy["sample_budget_proposal"] == 6000000
                assert proxy["confirmed_sample_budget"] is None and proxy["sample_budget_plateau_evidence"] is None
                assert proxy["B0"] is None and proxy["capacity_evidence"] is None
                assert proxy["optimizer"] == {"lr": 0.0003, "betas": [0.9, 0.95]}
                assert proxy["clip_norm"] == 1 and proxy["warmup_fraction"] == 0.02 and proxy["schedule"] == "cosine"
                assert item["design"]["selection_dependencies"] == row["selection_dependencies"]
                if stage != "C1":
                    assert item["design"]["distance_bias"] is None
                if stage in ("H", "pooling"):
                    assert item["design"]["views"] is None
    assert stages == {"C1": 6, "C3": 4, "H": 9, "pooling": 1}
    return {"status": "STATIC_TEMPLATE_STRUCTURE_VALID_NOT_EXECUTION_OR_DATA_ACCEPTANCE",
            "first_seed_templates": 20, "wiring_templates": 20, "shape": "6x512x8; H0=512",
            "sample_budget": "6M_PROPOSAL_PLATFORM_EVIDENCE_PENDING", "B0": None,
            "actual_Data_authority": False, "actual_model_updates": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).absolute().parent)
    print(json.dumps(check(parser.parse_args().root), sort_keys=True, allow_nan=False))
