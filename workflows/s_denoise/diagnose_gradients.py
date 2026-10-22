"""D1: 200 exact batches at the old B3 epoch3 checkpoint, no optimizer updates."""
import json
from pathlib import Path
import time

from runtime import OLD, ROOT, old_configuration, native_components, save, sha, setup_imports
from gpu_runtime import gpu_runtime, check_memory


def main():
    setup_imports()
    with gpu_runtime("D1_gradients") as (output, status):
        import numpy as np
        import torch
        import wandb
        from s_model_memory_v1 import build_memory_bounded_model
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler, make_prefetch_loader, close_prefetch_iterator
        from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule
        from phychem_mfm.phase1.denoising_metrics import shared_gradient_diagnostics
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        torch.set_num_threads(8)
        torch.set_num_interop_threads(1)
        torch.manual_seed(0)
        cfg = old_configuration()
        ref = json.loads((OLD / "s_training/B3_seed0/latest_checkpoint.json").read_text())
        assert ref["consumed_records"] == 33314316 and sha(ref["path"]) == ref["sha256"]
        model = build_memory_bounded_model(cfg["model"])
        value = torch.load(ref["path"], map_location="cpu", weights_only=True)
        model.load_state_dict(value["model"], strict=True)
        del value
        model.cuda().train()
        index, dataset, counts = native_components("train", seed=0)
        sampler = BlockAtomBatchSampler(counts, seed=0, epoch=0, **cfg["sampler"])
        weights, supervision = LossWeights.from_mapping(cfg["training"]["loss"]), SupervisionConfig.from_variant("S")
        tracking = wandb.init(project="phychem-mfm-s-denoise-repair", mode="offline", dir=str(output),
                              name="D1_B3_epoch3_200batches", config={"checkpoint": ref, "actual_tasks": ["element", "distance", "bond_order"]})
        iterator = None
        rows = []
        try:
            iterator = iter(make_prefetch_loader(dataset, sampler, **cfg["loader"]))
            for step in range(200):
                corpus = next(iterator)
                batch = corpus.encoder_batch.to("cuda")
                outputs = model.forward_pretrain(batch, supervision.objectives)
                loss = compute_phase1_loss(outputs, batch, None, supervision, weights, Phase1JointSchedule(), 33314316)
                tasks = {name: loss.raw[name] for name in ("element", "distance", "bond_order")}
                diagnostics = shared_gradient_diagnostics(tasks, model)
                model.zero_grad(set_to_none=True)
                loss.total.backward()
                norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0))
                assert np.isfinite(norm), "SCIENTIFIC_STOP_NONFINITE_GRADIENT"
                row = {"batch": step, "records": len(corpus.logical_indices), "shared_gradients": diagnostics,
                       "all_parameter_gradient_norm_before_clip": norm, "clip_triggered": norm > 1.0,
                       "raw_losses": {name: float(value.detach()) for name, value in tasks.items()},
                       **check_memory(torch, status)}
                rows.append(row)
                tracking.log({"gradient_norm_before_clip": norm,
                              **{"gradient_fraction/" + k: v for k, v in diagnostics["fractions_of_sum_of_norms"].items()}}, step=step, commit=True)
                save(output / "progress.json", {"batches": len(rows), "expected": 200})
                sampler.commit_batch(corpus.logical_indices)
                model.zero_grad(set_to_none=True)
                del outputs, loss, tasks, batch, corpus
            mean = lambda field: {key: float(np.mean([r["shared_gradients"][field][key] for r in rows if r["shared_gradients"][field][key] is not None])) for key in rows[0]["shared_gradients"][field]}
            result = {"status": "D1_COMPLETE", "batches": len(rows), "checkpoint": ref,
                      "shared_parameters": "all trainable model.backbone parameters",
                      "norms_mean": mean("norms"), "fractions_mean": mean("fractions_of_sum_of_norms"),
                      "pair_cosines_mean": mean("cosine_similarities"),
                      "clip_trigger_fraction_all_parameters": float(np.mean([r["clip_triggered"] for r in rows])),
                      "rows": rows, "optimizer_updates": 0, "equal_task_weight": 1.0 / 3.0}
            save(output / "result.json", result)
            save(ROOT / "reports/D1_latest.json", {"path": str(output / "result.json"), "sha256": sha(output / "result.json")})
        finally:
            if iterator is not None:
                close_prefetch_iterator(iterator)
            dataset.close()
            tracking.finish()


if __name__ == "__main__":
    main()
