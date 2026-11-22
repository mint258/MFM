"""Registered 11-22B fine-tuning loop; NEW runs only, not yet validated/activated.

The caller supplies original TRAIN/inner-validation TaskMolecule records and
native geometry keyed by source_member_uid, plus a managed stop callback.
Bootstrap and aggregation belong to the CPU producer, not this GPU loop.
"""
from dataclasses import replace
import math
import os
from pathlib import Path

import torch
from torch import nn

from phychem_mfm.phase1.v3_dev_readouts import FrozenFeatureProbe
from phychem_mfm.phase1.v3_dev_evaluation import _validate_molecules, _prediction, error


TASKS = ("qm9.U0_atom", "qm9.homo", "exp.LogD", "exp.LogS")
MODES = ("top2", "full", "scratch")


class ContinuationRequired(RuntimeError):
    """Complete optimizer-update boundary saved; resume the same run."""


def internal_split(rows):
    uids = sorted({row.molecule_uid for row in rows})
    order = torch.randperm(len(uids), generator=torch.Generator().manual_seed(20261112)).tolist()
    held = {uids[i] for i in order[:max(1, (len(uids)+9)//10)]}
    return (tuple(r for r in rows if r.molecule_uid not in held),
            tuple(r for r in rows if r.molecule_uid in held))


def configure_encoder(encoder, mode):
    if mode not in MODES:
        raise ValueError("Only the registered trainable modes belong in this loop")
    encoder.requires_grad_(mode != "top2")
    if mode == "top2":
        layers = encoder.backbone.layers
        if len(layers) != 6:
            raise ValueError("Registered six-layer encoder required for top2")
        # Only the final two transformer layers; the separate output norm,
        # embeddings and the first four layers remain frozen.
        for layer in layers[-2:]:
            layer.requires_grad_(True)
    return tuple(p for p in encoder.parameters() if p.requires_grad)


def learning_rate_fraction(update, total):
    if not 1 <= update <= total:
        raise ValueError("Update must be in the registered complete50-epoch budget")
    warmup = max(1, math.ceil(total * .05))
    if update <= warmup:
        return update / warmup
    return .5 * (1. + math.cos(math.pi * (update - warmup) / (total - warmup)))


def fit_normalization(train):
    """Exactly the current R3 optimization-only moments, mask and target scale."""
    std = torch.cat([r.h0.double() for r in train]).std(0, unbiased=False)
    threshold = max(1e-12, 1e-4 * float(torch.quantile(std, .5)))
    keep = std >= threshold
    if not bool(keep.any()):
        raise ValueError("No nonconstant initial H0 dimensions remain")
    atom = torch.cat([r.h0[:, keep].double() for r in train])
    mean, scale = atom.mean(0), atom.std(0, unbiased=False)
    scale = torch.where(scale > 1e-12, scale, torch.ones_like(scale))
    observed = torch.cat([r.targets[r.supervision_mask & r.candidate_mask].double() for r in train])
    if not len(observed):
        raise ValueError("No observed optimization labels")
    target_mean, target_scale = float(observed.mean()), float(observed.std(unbiased=False))
    return dict(keep=keep, mean=mean, scale=scale, target_mean=target_mean,
                target_scale=target_scale if target_scale > 1e-12 else 1.)


def state_cpu(module):
    return {k: v.detach().cpu().clone() for k, v in module.state_dict().items()}


def atomic_checkpoint(path, state):
    # Fixed own-run checkpoint path; peak includes old+new complete state.
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    torch.save(state, tmp)
    os.replace(tmp, path)


def run_finetune(encoder, train, evaluation, geometry, task, *, mode, seed, n_ref,
                 output, tracker, should_stop, source_binding, initial_architecture,
                 resume_state=None, device="cuda"):
    """Resume a single registered task/mode/seed; return original-unit predictions.

    Initial rows contain the initial encoder's detached H0, exactly as R3.
    On resume the caller may reconstruct same-shaped placeholder H0 because the
    complete checkpoint retains the original fixed TRAIN normalization.
    geometry maps each native source member UID to its original sample (x,pos).
    should_stop must use the native managed work deadline and cooperative flag.
    """
    if task.task_id not in TASKS or task.output_level != "graph" or task.error_metric != "mae":
        raise ValueError("Only the four registered graph regression tasks")
    if seed not in (0, 1, 2) or mode not in MODES or n_ref <= 0:
        raise ValueError("Unregistered mode/seed or invalid TRAIN N_ref")
    if not callable(should_stop) or not callable(getattr(tracker, "log", None)):
        raise ValueError("Managed safe-boundary control and tracking are required")
    if device not in ("cpu", "cuda"):
        raise ValueError("Explicit CPU test or allocated CUDA device required")
    train, evaluation = _validate_molecules(train, task), _validate_molecules(evaluation, task)
    if {r.molecule_uid for r in train} & {r.molecule_uid for r in evaluation}:
        raise ValueError("Original optimization/evaluation molecule groups overlap")
    train, internal = internal_split(train)
    if not train or not internal:
        raise ValueError("Both internal TRAIN subsets are required")
    retained = tuple(r for r in train if bool((r.supervision_mask & r.candidate_mask).any()))
    if not retained:
        raise ValueError("No observed optimization records")
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    encoder = encoder.to(device=device, dtype=torch.float32)
    trainable = configure_encoder(encoder, mode)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    resume_path = output / "complete_state.pt"
    identity = dict(protocol="USER_DIRECTIVE_20261122B_FIXED_V1",
                    source_binding=source_binding, initial_architecture=initial_architecture,
                    task=task.task_id, mode=mode, seed=seed, n_ref=float(n_ref),
                    train_records=[r.source_member_uid or r.molecule_uid for r in train],
                    internal_records=[r.source_member_uid or r.molecule_uid for r in internal],
                    eval_records=[r.source_member_uid or r.molecule_uid for r in evaluation])
    saved = resume_state
    if saved is None and resume_path.is_file():
        saved = torch.load(resume_path, map_location="cpu", weights_only=True)
    if saved is not None and saved["identity"] != identity:
        raise ValueError("Complete-state run identity or original cohorts changed")
    normal = saved["normalization"] if saved is not None else fit_normalization(train)
    keep = normal["keep"].to(device)
    # This matches R3's explicit seed reset immediately before head creation.
    torch.manual_seed(seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(seed)
    head = FrozenFeatureProbe(int(normal["keep"].sum()), readout="R3",
        output_level="graph", n_ref=n_ref, mean=normal["mean"], scale=normal["scale"]).to(device)
    optimizer = torch.optim.AdamW([
        dict(params=trainable, lr=1e-4), dict(params=head.parameters(), lr=1e-3)],
        betas=(.9, .999), weight_decay=.01, eps=1e-8, foreach=False, fused=False)
    rng = torch.Generator(device="cpu").manual_seed(seed)
    updates, epoch, offset = 0, 0, 0
    order, phase = [], "train"
    best_error, selected_epoch, best_encoder, best_head = float("inf"), None, None, None
    if saved is not None:
        encoder.load_state_dict(saved["encoder"])
        head.load_state_dict(saved["head"])
        optimizer.load_state_dict(saved["optimizer"])
        rng.set_state(saved["shuffle_rng"])
        torch.set_rng_state(saved["torch_rng"])
        if device == "cuda":
            torch.cuda.set_rng_state_all(saved["cuda_rng"])
        updates, epoch, offset = saved["updates"], saved["epoch"], saved["offset"]
        order, phase = saved["order"], saved["phase"]
        best_error, selected_epoch = saved["best_error"], saved["selected_epoch"]
        best_encoder, best_head = saved["best_encoder"], saved["best_head"]
    total_updates = 50 * math.ceil(len(retained) / 32)

    def save():
        atomic_checkpoint(resume_path, dict(schema="P_FINE_TUNE_COMPLETE_STATE_V1",
            identity=identity, initial_architecture=initial_architecture,
            normalization=normal, encoder=state_cpu(encoder),
            head=state_cpu(head), optimizer=optimizer.state_dict(),
            shuffle_rng=rng.get_state(), torch_rng=torch.get_rng_state(),
            cuda_rng=torch.cuda.get_rng_state_all() if device == "cuda" else [],
            updates=updates, epoch=epoch,
            offset=offset, order=order, phase=phase, best_error=best_error,
            selected_epoch=selected_epoch, best_encoder=best_encoder, best_head=best_head))

    def boundary():
        if should_stop():
            save()
            raise ContinuationRequired("Complete fine-tune state saved at a safe boundary")

    def batch(rows):
        from torch_geometric.data import Batch, Data
        selected = [geometry[r.source_member_uid or r.molecule_uid] for r in rows]
        for row, sample in zip(rows, selected):
            if not torch.equal(row.source_atom_ids.cpu(), sample.source_atom_ids.cpu()):
                raise ValueError("Native source atom order changed")
        graph = Batch.from_data_list([Data(x=s.x.reshape(-1, 1), pos=s.pos) for s in selected]).to(device)
        atom = encoder.encode_atoms(graph)[:, keep]
        counts = [len(s.x) for s in selected]
        padded = atom.new_zeros((len(rows), max(counts), atom.shape[1]))
        mask = torch.zeros((len(rows), max(counts)), dtype=torch.bool, device=device)
        cursor = 0
        for i, count in enumerate(counts):
            padded[i, :count] = atom[cursor:cursor+count]
            mask[i, :count] = True
            cursor += count
        predicted = head(padded, mask)
        y = torch.cat([r.targets for r in rows]).to(device).float()
        observed = torch.cat([r.supervision_mask & r.candidate_mask for r in rows]).to(device)
        return predicted, y, observed

    def predict(rows):
        encoder.eval()
        head.eval()
        values = []
        with torch.no_grad():
            for start in range(0, len(rows), 32):
                p, _, _ = batch(rows[start:start+32])
                values.extend((p * normal["target_scale"] + normal["target_mean"]).cpu().tolist())
        return _prediction(task, rows, values)

    # Explicit phase/order/cursor prevents repeating a completed training epoch
    # when interrupted before its internal epoch-selection pass.
    while epoch < 50:
        if phase == "train":
            if not order:
                order = torch.randperm(len(retained), generator=rng).tolist()
            encoder.train()
            head.train()
            while offset < len(order):
                boundary()
                selected = tuple(retained[i] for i in order[offset:offset+32])
                ratio = learning_rate_fraction(updates+1, total_updates)
                for group, base in zip(optimizer.param_groups, (1e-4, 1e-3)):
                    group["lr"] = base * ratio
                p, y, mask = batch(selected)
                loss = nn.functional.mse_loss(p[mask], (y[mask]-normal["target_mean"])/normal["target_scale"])
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("Nonfinite registered fine-tuning loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
                offset += len(selected)
                updates += 1
                tracker.log({"finetune/loss": float(loss.detach()),
                             "finetune/epoch": epoch, "finetune/update": updates,
                             "finetune/optimization_samples": epoch*len(retained)+offset,
                             "finetune/encoder_lr": optimizer.param_groups[0]["lr"],
                             "finetune/head_lr": optimizer.param_groups[1]["lr"]},
                            step=updates, commit=True)
            phase = "select_epoch"
        boundary()
        internal_error = error(predict(internal))
        if internal_error is None:
            raise ValueError("Internal MAE unavailable")
        if internal_error < best_error:
            best_error, selected_epoch = internal_error, epoch+1
            best_encoder, best_head = state_cpu(encoder), state_cpu(head)
        tracker.log({"finetune/internal_mae": internal_error, "finetune/epoch": epoch},
                    step=updates, commit=True)
        epoch, offset, order, phase = epoch+1, 0, [], "train"
        # Intermediate full state is an ordinary authorized run output, not a
        # restart from pretrained weights; old/new checkpoint peak is reserved.
        save()
    boundary()
    encoder.load_state_dict(best_encoder)
    head.load_state_dict(best_head)
    prediction = predict(evaluation)
    detail = dict(task=task.task_id, mode=mode, finetune_seed=seed,
        epochs=50, selected_epoch=selected_epoch, updates=updates,
        internal_mae=best_error, evaluation_mae=error(prediction),
        n_ref=float(n_ref), batch_size=32, precision="float32", tf32=False,
        optimizer="AdamW", encoder_lr=1e-4, head_lr=1e-3, warmup_fraction=.05,
        schedule="cosine_to_zero", split_seed=20261112,
        normalization_fit_scope="optimization_only",
        removed_dimensions=int((~normal["keep"]).sum()),
        head="Unchanged current R3 FrozenFeatureProbe",
        top2_scope="backbone.layers[-2:] only; separate out_norm frozen" if mode=="top2" else None)
    return prediction, detail