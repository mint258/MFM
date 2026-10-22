"""Bounded GPU validation of real batches, metrics and new loss integration."""
import json
import time

from runtime import ROOT, old_configuration, save, setup_imports
from gpu_runtime import gpu_runtime, check_memory


def main():
    setup_imports()
    with gpu_runtime("new_loss_gpu_smoke_v1") as (output, status):
        import torch
        import wandb
        from data import selected_components
        from s_model_memory_v1 import build_memory_bounded_model
        from s_convergence_runner_v8 import cpu_tree
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler, collate_native_views
        from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1LossPolicy, Phase1JointSchedule
        from phychem_mfm.phase1.denoising_metrics import DenoisingMetrics
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        torch.set_num_threads(16)
        torch.manual_seed(0)
        base = old_configuration()
        index, dataset, counts = selected_components("train", seed=0, epoch_noise=True, local_blocks=True)
        sampler = BlockAtomBatchSampler(counts, seed=0, epoch=0, **base["sampler"])
        batches = list(sampler)
        largest = max(batches, key=lambda batch: len(batch) * max(counts.ref(i).native_n_atoms for i in batch) ** 2)
        # Use the actual frozen sampler's first batch and largest padded batch.
        selected = [batches[0], largest]
        run = wandb.init(project="phychem-mfm-s-denoise-repair", mode="offline", dir=str(output), name="GPU_smoke_real_S_batches")
        rows = []
        try:
            for group in ["A0", "A1", "A2"]:
                cfg = json.loads((ROOT / "source_v3/workflows/s_denoise/configs" / (group + "_seed0_v3.json")).read_text())
                model = build_memory_bounded_model(cfg["model"]).cuda().train()
                optimizer = torch.optim.AdamW(model.parameters(), **cfg["optimizer"])
                policy = Phase1LossPolicy.from_mapping(cfg["loss_policy"])
                for number, indices in enumerate(selected):
                    batch = collate_native_views([dataset[i] for i in indices]).encoder_batch.to("cuda")
                    torch.cuda.reset_peak_memory_stats()
                    start = time.monotonic()
                    optimizer.zero_grad(set_to_none=True)
                    outputs = model.forward_pretrain(batch, SupervisionConfig.from_variant("S").objectives)
                    loss = compute_phase1_loss(outputs, batch, None, SupervisionConfig.from_variant("S"),
                        LossWeights.from_mapping(base["training"]["loss"]), Phase1JointSchedule(), 0, policy=policy)
                    if group == "A2":
                        assert "denoise_eps_mse" in loss.weighted and "distance" not in loss.weighted
                        assert loss.raw["distance"].requires_grad is False
                    loss.total.backward()
                    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    assert torch.isfinite(norm) and torch.isfinite(loss.total), "GUIDE_STOP_NONFINITE_SMOKE"
                    optimizer.step()
                    torch.cuda.synchronize()
                    seconds = time.monotonic() - start
                    meter = DenoisingMetrics()
                    meter.add(outputs, batch)
                    row = {"condition": group, "batch": number, "records": len(indices),
                           "forward_backward_step_seconds": seconds, "metrics": meter.result(), **check_memory(torch, status)}
                    rows.append(row)
                    run.log({"step_seconds": seconds, "records": len(indices), **check_memory(torch, status)}, step=len(rows), commit=True)
                    del outputs, loss, batch
                safe_path = output / (group + "_safe_checkpoint.pt")
                safe_value = cpu_tree({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                    "configuration": cfg, "sampler": sampler.state_dict(),
                    "cpu_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state()}, torch)
                torch.save(safe_value, safe_path)
                readback = torch.load(safe_path, map_location="cpu", weights_only=True)
                assert readback["configuration"] == cfg and readback["sampler"] == safe_value["sampler"]
                for key, value in safe_value["model"].items():
                    assert torch.equal(readback["model"][key], value)
                del optimizer, model
                torch.cuda.empty_cache()
            save(output / "result.json", {"status": "REAL_S_MODEL_NEW_LOSS_GPU_SMOKE_PASS", "rows": rows})
        finally:
            dataset.close()
            run.finish()


if __name__ == "__main__":
    main()
