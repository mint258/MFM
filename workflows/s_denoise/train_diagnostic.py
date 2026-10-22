"""D3 fixed-step, molecule-level controls; no full-training acceptance here."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import time

from runtime import ROOT, old_configuration, save, sha, setup_imports
from gpu_runtime import gpu_runtime, check_memory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--source-binding", required=True)
    args = parser.parse_args()
    path = Path(args.configuration)
    cfg = json.loads(path.read_text())
    assert not (ROOT / "GUIDE_STOP.json").exists(), "GUIDE_STOP_MARKER_PRESENT"
    binding = json.loads(Path(args.source_binding).read_text())
    for reference in binding["files"]:
        assert sha(reference["path"]) == reference["sha256"], "D3_SOURCE_BINDING_MISMATCH"
    assert cfg["status"] == "D3_PREDECLARED_FIXED_STEP_PROTOCOL_V3"
    assert cfg["steps"] == 4000 and cfg["seed"] in [0, 1]
    setup_imports()
    with gpu_runtime(cfg["condition"] + "_seed" + str(cfg["seed"])) as (output, status):
        import numpy as np
        import torch
        import wandb
        from data import selected_components
        from s_model_memory_v1 import build_memory_bounded_model
        from s_convergence_runner_v8 import cpu_tree
        from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler, make_prefetch_loader, close_prefetch_iterator
        from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1LossPolicy, Phase1JointSchedule
        from phychem_mfm.phase1.denoising_metrics import DenoisingMetrics, shared_gradient_diagnostics
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        # Eight train workers may remain blocked on bounded prefetch during
        # validation. Four validation workers + four Torch threads fit 16 CPUs.
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        torch.manual_seed(cfg["seed"])
        torch.cuda.manual_seed_all(cfg["seed"])
        base = old_configuration()
        model = build_memory_bounded_model(cfg["model"]).cuda().train()
        optimizer = torch.optim.AdamW(model.parameters(), **cfg["optimizer"])
        weights = LossWeights.from_mapping(base["training"]["loss"])
        policy = Phase1LossPolicy.from_mapping(cfg["loss_policy"])
        supervision = SupervisionConfig.from_variant("S")
        local_blocks = cfg.get("runtime", {}).get("subset_map_close_uses_local_index", False)
        index, dataset, counts = selected_components("train", seed=cfg["seed"], epoch_noise=cfg["noise_seed_includes_epoch"], local_blocks=local_blocks)
        sampler = BlockAtomBatchSampler(counts, seed=cfg["seed"], epoch=0, **base["sampler"])
        val_index, val_dataset, val_counts = selected_components("full", seed=0, epoch_noise=True, local_blocks=local_blocks)
        tracking = wandb.init(project="phychem-mfm-s-denoise-repair", mode="offline", dir=str(output),
                              name=cfg["condition"] + "_seed" + str(cfg["seed"]),
                              config={"configuration": cfg, "config_sha256": sha(path), "runtime": status})
        tracking_exit_code = 1
        iterator = val_iterator = None
        curve, gradient_rows = [], []
        update = consumed = 0
        compute_seconds = loader_seconds = 0.0
        clip_count = 0
        checkpoint_total_seconds = 0.0
        start = time.monotonic()
        journal = (output / "metrics.jsonl").open("w")

        def loss_for(outputs, batch):
            loss = compute_phase1_loss(outputs, batch, None, supervision, weights,
                                       Phase1JointSchedule(), consumed, policy=policy)
            return loss

        def checkpoint(label):
            nonlocal checkpoint_total_seconds
            began = time.monotonic()
            payload = {"model": cpu_tree(model.state_dict(), torch), "optimizer": cpu_tree(optimizer.state_dict(), torch),
                       "config": cfg, "config_sha256": sha(path), "source_binding_sha256": sha(args.source_binding),
                       "optimizer_updates": update, "consumed_records": consumed,
                       "sampler": sampler.state_dict(), "cpu_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state(),
                       "tracking_run_id": str(tracking.id), "development_only": True,
                       "curve": curve, "gradient_rows": gradient_rows,
                       "training_compute_seconds": compute_seconds, "training_loader_wait_seconds": loader_seconds,
                       "clip_count": clip_count}
            target = output / (label + ".pt")
            pending = target.with_name(target.name + ".pending")
            with pending.open("wb") as stream:
                torch.save(payload, stream)
                stream.flush()
                os.fsync(stream.fileno())
            restored = torch.load(pending, map_location="cpu", weights_only=True)
            assert restored["optimizer_updates"] == update and restored["sampler"] == payload["sampler"]
            pending.replace(target)
            seconds = time.monotonic() - began
            checkpoint_total_seconds += seconds
            reference = {"path": str(target), "sha256": sha(target), "bytes": target.stat().st_size,
                         "optimizer_updates": update, "consumed_records": consumed,
                         "save_readback_seconds": seconds}
            save(output / "latest_checkpoint.json", reference)
            return reference

        def log(row):
            journal.write(json.dumps(row, allow_nan=False) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            tracking.log({key: value for key, value in row.items() if isinstance(value, (int, float))}, step=len(curve) + update, commit=True)

        def evaluate():
            nonlocal val_iterator
            validation_started = time.monotonic()
            model.eval()
            meter = DenoisingMetrics()
            val_sampler = BlockAtomBatchSampler(val_counts, seed=0, epoch=0, **base["sampler"])
            visited = 0
            validation_loader = {**base["loader"], "num_workers": 4}
            val_iterator = iter(make_prefetch_loader(val_dataset, val_sampler, **validation_loader))
            try:
                with torch.no_grad():
                    for corpus in val_iterator:
                        batch = corpus.encoder_batch.to("cuda", non_blocking=True)
                        outputs = model.forward_pretrain(batch, supervision.objectives)
                        meter.add(outputs, batch)
                        visited += len(corpus.logical_indices)
                        val_sampler.commit_batch(corpus.logical_indices)
                assert visited == len(val_index), "D3_VALIDATION_RECORD_COVERAGE_MISMATCH"
                result = {"optimizer_update": update, "consumed_records": consumed, "evaluation_records": visited,
                          "evaluation_molecules": 2000, "evaluation_wall_seconds": time.monotonic() - validation_started,
                          **meter.result()}
                curve.append(result)
                save(output / "curve.json", curve)
                log({"validation/" + key: value for key, value in result.items() if isinstance(value, (int, float))})
                return result
            finally:
                close_prefetch_iterator(val_iterator)
                val_iterator = None
                model.train()

        try:
            initial = evaluate()
            while update < cfg["steps"]:
                iterator = iter(make_prefetch_loader(dataset, sampler, **base["loader"]))
                exhausted = False
                try:
                    while update < cfg["steps"]:
                        if update % 32 == 0 and (ROOT / "GUIDE_STOP.json").exists():
                            checkpoint("guide_stop_partial")
                            raise RuntimeError("GUIDE_STOP_MARKER_PRESENT")
                        waiting = time.monotonic()
                        try:
                            corpus = next(iterator)
                        except StopIteration:
                            exhausted = True
                            break
                        loader_seconds += time.monotonic() - waiting
                        began = time.monotonic()
                        batch = corpus.encoder_batch.to("cuda", non_blocking=True)
                        optimizer.zero_grad(set_to_none=True)
                        outputs = model.forward_pretrain(batch, supervision.objectives)
                        loss = loss_for(outputs, batch)
                        objective = loss.total * cfg["total_loss_scale"]
                        if update % 200 == 0 or update >= cfg["steps"] - 20:
                            names = [name for name in ("element", cfg["geometry_task"], "bond_order") if loss.counts.get(name, 0)]
                            effective = {name: loss.task_weights.get(name, 0.0) * cfg["total_loss_scale"] for name in names}
                            diagnostics = shared_gradient_diagnostics({name: loss.raw[name] for name in names}, model, weights=effective)
                            gradient_rows.append({"optimizer_update": update, "diagnostics": diagnostics})
                        objective.backward()
                        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        assert torch.isfinite(objective) and torch.isfinite(norm), "GUIDE_STOP_NAN_OR_DIVERGENCE"
                        progress = update / cfg["steps"]
                        factor = (update + 1) / 100 if update < 100 else 0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * (update - 100) / (cfg["steps"] - 100)))
                        lr = cfg["optimizer"]["lr"] * factor
                        for group in optimizer.param_groups:
                            group["lr"] = lr
                        optimizer.step()
                        torch.cuda.synchronize()
                        compute_seconds += time.monotonic() - began
                        consumed += len(corpus.logical_indices)
                        sampler.commit_batch(corpus.logical_indices)
                        clip_count += int(norm > 1.0)
                        update += 1
                        if update % 32 == 0:
                            log({"optimizer_update": update, "consumed_records": consumed,
                                 "train_total_loss": float(objective.detach()), "lr": lr,
                                 "gradient_norm_before_clip": float(norm),
                                 "records_per_second_training": consumed / (compute_seconds + loader_seconds),
                                 **{"train_raw/" + k: float(v.detach()) for k, v in loss.raw.items()},
                                 **check_memory(torch, status)})
                            save(output / "progress.json", {"updates": update, "expected": cfg["steps"], "consumed_records": consumed})
                        del corpus, batch, outputs, loss, objective
                        if update % 500 == 0:
                            evaluate()
                            checkpoint(f"step_{update:06d}")
                finally:
                    close_prefetch_iterator(iterator)
                    iterator = None
                if exhausted:
                    assert sampler.samples_consumed == len(index)
                    sampler.advance_epoch()
            final = curve[-1] if curve[-1]["optimizer_update"] == update else evaluate()
            save(output / "gradient_diagnostics.json", gradient_rows)
            checkpoint_reference = checkpoint("final")
            assert update == 4000
            checkpoint_seconds = checkpoint_reference["save_readback_seconds"]
            report = {"status": "D3_CONDITION_COMPLETE", "condition": cfg["condition"], "seed": cfg["seed"],
                      "configuration_sha256": sha(path), "optimizer_updates": update, "consumed_records": consumed,
                      "final": final, "initial": initial, "runtime": status,
                      "training_seconds_including_loader": compute_seconds + loader_seconds,
                      "training_compute_seconds": compute_seconds, "training_loader_wait_seconds": loader_seconds,
                      "wall_seconds_including_evaluation": time.monotonic() - start,
                      "training_records_per_second": consumed / (compute_seconds + loader_seconds),
                      "clip_trigger_fraction": clip_count / update, "checkpoint": checkpoint_reference,
                      "checkpoint_save_readback_seconds": checkpoint_seconds,
                      "checkpoint_all_save_readback_seconds": checkpoint_total_seconds,
                      "final_gradient_rows": gradient_rows[-20:], **check_memory(torch, status)}
            save(output / "result.json", report)
            save(ROOT / "reports" / (cfg["condition"] + "_seed" + str(cfg["seed"]) + "_latest.json"),
                 {"path": str(output / "result.json"), "sha256": sha(output / "result.json")})
            tracking_exit_code = 0
        except Exception as exc:
            if isinstance(exc, FloatingPointError) or "GUIDE_STOP_NAN_OR_DIVERGENCE" in str(exc):
                stop = ROOT / "GUIDE_STOP.json"
                if not stop.exists():
                    save(stop, {"reason": "GUIDE_STOP_NAN_OR_DIVERGENCE", "condition": cfg["condition"],
                                "seed": cfg["seed"], "job_id": os.environ["SLURM_JOB_ID"],
                                "optimizer_updates": update, "consumed_records": consumed, "error": repr(exc)})
            raise
        finally:
            if iterator is not None:
                close_prefetch_iterator(iterator)
            if val_iterator is not None:
                close_prefetch_iterator(val_iterator)
            dataset.close()
            val_dataset.close()
            journal.close()
            tracking.finish(exit_code=tracking_exit_code)


if __name__ == "__main__":
    main()
