"""Same CPU process recipe under separate old/new package imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from runtime import ROOT, OLD, SOURCE, DEPS, native_components, old_configuration, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version", choices=["old", "new", "compare"])
    args = parser.parse_args()
    destination = ROOT / "reports/legacy_bitexact_v3"
    destination.mkdir(parents=True, exist_ok=True)
    if args.version == "compare":
        old = json.loads((destination / "old.json").read_text())
        new = json.loads((destination / "new.json").read_text())
        assert old["hashes"] == new["hashes"], "GUIDE_STOP_LEGACY_BITEXACT_FAILED"
        save(destination / "result.json", {"status": "LEGACY_V2_BITEXACT_PASS", "compared_tensors": len(old["hashes"]),
              "scope": "same v2 config, same fixed real eight-record batch, full initialization state, H0/predictions/raw and total losses, CPU byte equality", "old": old["source"], "new": new["source"]})
        print("LEGACY_V2_BITEXACT_PASS", flush=True)
        return
    source = Path("/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime") if args.version == "old" else SOURCE / "current"
    sys.path[:0] = [str(source), str(DEPS), str(OLD / "scripts")]
    import torch
    from s_model_memory_v1 import build_memory_bounded_model
    from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    from phychem_mfm.training.data import fast_collate
    torch.set_num_threads(16)
    torch.manual_seed(8123)
    cfg = old_configuration()
    model = build_memory_bounded_model(cfg["model"]).eval()
    _, dataset, _ = native_components("train", seed=0)
    try:
        views = [dataset[i] for i in [0, 1, 7, 18, 95, 100, 1001, 9001]]
        batch = fast_collate([v for row in views for v in row.views])
        with torch.no_grad():
            output = model.forward_pretrain(batch, SupervisionConfig.from_variant("S").objectives)
            loss = compute_phase1_loss(output, batch, None, SupervisionConfig.from_variant("S"),
                                       LossWeights.from_mapping(cfg["training"]["loss"]), Phase1JointSchedule(), 0)
        tensors = {"state/" + k: v for k, v in model.state_dict().items()}
        tensors.update({"H0": output.atom_repr, "element": output.element_logits,
                        "coordinates": output.coordinate_pred, "bond": output.bond.order,
                        "total": loss.total, **{"raw/" + k: v for k, v in loss.raw.items()},
                        "batch/x": batch.x, "batch/pos": batch.pos, "batch/target_pos": batch.target_pos})
        hashes = {key: {"dtype": str(value.dtype), "shape": list(value.shape),
                        "sha256": hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()} for key, value in tensors.items()}
        save(destination / (args.version + ".json"), {"source": str(source), "hashes": hashes})
    finally:
        dataset.close()


if __name__ == "__main__":
    main()
