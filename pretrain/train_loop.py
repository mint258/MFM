from __future__ import annotations

import logging
import math
import sys
from typing import Dict, Optional

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import r2_score
from torch.cuda.amp import autocast
from torch_geometric.utils import to_dense_batch
from tqdm import tqdm

from .geometry import (
    angle_cos,
    batch_rmsd,
    build_local_graph,
    map_global_to_dense_indices,
    morse_energy,
    planar_loss_mixed,
    torsion_sin_cos,
)

LOGGER = logging.getLogger("multitask")


class DummyScaler:
    """Fallback scaler for non-fp16 training."""

    def scale(self, loss):
        return loss

    def unscale_(self, optimizer):
        return None

    def step(self, optimizer):
        optimizer.step()

    def update(self):
        return None


def detect_nan_inf(tensor: torch.Tensor) -> bool:
    return torch.isnan(tensor).any() or torch.isinf(tensor).any()


def analyze_and_abort(model, batch, intermediates: Dict[str, torch.Tensor]) -> None:
    """Dump diagnostics when NaN/Inf appears and abort training."""
    LOGGER.error("Detected NaN/Inf, aborting training and dumping diagnostics...")

    for name in ["pos", "x"]:
        if hasattr(batch, name):
            value = getattr(batch, name)
            if isinstance(value, torch.Tensor):
                count = int((~torch.isfinite(value)).sum().item())
                LOGGER.error("Batch.%s non-finite count: %d", name, count)

    for name, param in model.named_parameters():
        if param is None:
            continue
        count = int((~torch.isfinite(param.data)).sum().item())
        if count:
            LOGGER.error("PARAM %s non-finite elements: %d", name, count)

    for name, tensor in intermediates.items():
        if isinstance(tensor, torch.Tensor):
            count = int((~torch.isfinite(tensor)).sum().item())
            LOGGER.error("Intermediate %s non-finite elements: %d", name, count)

    sys.exit(1)


def run_epoch(
    model,
    loader,
    device,
    std,
    scaler,
    *,
    loss_cutoff,
    n_atom_types,
    lam_c,
    lam_d,
    lam_a,
    lam_t,
    lam_p,
    lam_e,
    lam_q,
    lam_z,
    z_label_smooth,
    z_focal_gamma,
    z_temp,
    z_class_balance,
    z_entropy_reg,
    z_logit_l2,
    morse_d,
    morse_a,
    graph_cutoff=2.0,
    optim=None,
    fp16=False,
    desc="Train",
    scheduler=None,
):
    train = optim is not None
    model.train(train)

    stats = {
        "E": 0.0,
        "Q": 0.0,
        "Z": 0.0,
        "Geom": 0.0,
        "Geom_c": 0.0,
        "Geom_d": 0.0,
        "Geom_a": 0.0,
        "Geom_t": 0.0,
        "Geom_p": 0.0,
        "RMSD": 0.0,
        "RMSD_n": 0,
        "Bal": 0.0,
        "B": 0,
        "bad": 0,
        "R2_e": 0.0,
        "R2_q": 0.0,
        "R2_z": 0.0,
        "Acc_z": 0.0,
    }

    for batch in tqdm(loader, desc=desc, leave=False):
        batch = batch.to(device)
        if train:
            optim.zero_grad(set_to_none=True)

        with autocast(enabled=fp16):
            coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, bal = model(batch)
            _batch_size, nmax, _ = coords_pred.shape
            charge_mask_f = charge_mask.squeeze(-1)

            if stats["B"] == 0:
                LOGGER.info(
                    "First batch outputs: coords=%s charge=%s elem=%s energy=%s mask=%s",
                    tuple(coords_pred.shape),
                    tuple(charge_pred.shape),
                    tuple(elem_pred.shape),
                    tuple(energy_pred.shape),
                    tuple(charge_mask.shape),
                )

            # Element classification loss.
            pad_idx = getattr(model, "pad_elem_index", getattr(model, "n_elem_classes", n_atom_types) - 1)
            elem_source = batch.target_x if hasattr(batch, "target_x") else batch.x
            elem_true_pad, _ = to_dense_batch(elem_source[:, 0].long(), batch.batch, fill_value=pad_idx)

            num_classes = elem_pred.size(-1)
            elem_logits_flat = elem_pred.reshape(-1, num_classes)
            elem_true_flat = elem_true_pad.view(-1)

            temp = max(1.0, float(z_temp))
            logits_t = elem_logits_flat / temp

            weights = None
            if z_class_balance != "none":
                with torch.no_grad():
                    valid = elem_true_flat != pad_idx
                    yv = elem_true_flat[valid]
                    hist = torch.bincount(yv, minlength=num_classes).float()
                    if z_class_balance == "batch_inv":
                        w = 1.0 / (hist + 1e-6)
                    else:
                        beta = 0.999
                        eff = (1.0 - torch.pow(beta, hist)) / (1.0 - beta)
                        w = 1.0 / (eff + 1e-6)
                    w[pad_idx] = 0.0
                    w = (w / (w.sum() + 1e-6)) * num_classes
                    weights = w.to(elem_logits_flat.device)

            if z_label_smooth > 0:
                ce_all = F.cross_entropy(
                    logits_t,
                    elem_true_flat,
                    weight=weights,
                    ignore_index=pad_idx,
                    reduction="none",
                    label_smoothing=z_label_smooth,
                )
            elif z_focal_gamma > 0:
                ce_raw = F.cross_entropy(
                    logits_t,
                    elem_true_flat,
                    weight=weights,
                    ignore_index=pad_idx,
                    reduction="none",
                )
                p_t = torch.exp(-ce_raw)
                ce_all = (1 - p_t) ** z_focal_gamma * ce_raw
            else:
                ce_all = F.cross_entropy(
                    logits_t,
                    elem_true_flat,
                    weight=weights,
                    ignore_index=pad_idx,
                    reduction="none",
                )

            mask_f = (elem_true_flat != pad_idx).float()
            loss_z = (ce_all * mask_f).sum() / mask_f.sum().clamp(min=1.0)

            if z_entropy_reg > 0:
                with torch.no_grad():
                    p_t = F.softmax(logits_t, dim=-1)
                entropy = -(p_t * (p_t.clamp_min(1e-12)).log()).sum(-1)
                loss_conf = (-entropy * mask_f).sum() / mask_f.sum().clamp(min=1.0)
                loss_z = loss_z + z_entropy_reg * loss_conf

            if z_logit_l2 > 0:
                valid_mask = mask_f.bool()
                if valid_mask.any():
                    loss_z = loss_z + z_logit_l2 * (elem_logits_flat[valid_mask] ** 2).mean()

            # Energy loss.
            y_e = ((batch.energy.view(-1, 1, 1) - std["muE"]) / std["stdE"]).to(device)
            p_e = (energy_pred - std["muE"]) / std["stdE"]
            if lam_e > 0:
                loss_e = F.mse_loss(p_e, y_e, reduction="none").mean()
            else:
                loss_e = torch.tensor(0.0, device=device)

            # Charge loss.
            has_charge_target = hasattr(batch, "y")
            if has_charge_target:
                charge_true_pad, _ = to_dense_batch(batch.y, batch.batch, fill_value=0.0)
                charge_true_std = ((charge_true_pad - std["muQ"]) / std["stdQ"]).to(device)
                charge_pred_std = (charge_pred - std["muQ"]) / std["stdQ"]
                loss_q = F.mse_loss(charge_pred_std * charge_mask, charge_true_std * charge_mask, reduction="none")
                loss_q = loss_q.sum() / charge_mask.sum().clamp(min=1.0)
            else:
                charge_true_pad = torch.zeros_like(charge_pred)
                loss_q = torch.tensor(0.0, device=device)

            # Geometry losses.
            pos_source = batch.target_pos if hasattr(batch, "target_pos") else batch.pos
            true_xyz_pad, _ = to_dense_batch(pos_source, batch.batch)
            geom_mask = charge_mask_f.float()

            loss_c = torch.tensor(0.0, device=device)
            loss_d = torch.tensor(0.0, device=device)
            loss_a = torch.tensor(0.0, device=device)
            loss_t = torch.tensor(0.0, device=device)
            loss_p = torch.tensor(0.0, device=device)

            if lam_c > 0:
                coord_se = ((coords_pred - true_xyz_pad) ** 2).sum(-1) * geom_mask
                loss_c = coord_se.sum() / geom_mask.sum().clamp(min=1.0)

            if lam_d > 0:
                dist_pred = torch.cdist(coords_pred, coords_pred)
                dist_true = torch.cdist(true_xyz_pad, true_xyz_pad)
                pair_mask = geom_mask[:, :, None] * geom_mask[:, None, :]
                v = morse_energy(dist_pred, dist_true, morse_d, morse_a) * pair_mask
                morse_per_atom = torch.log1p(v.sum(-1).clamp(min=0.0)) * geom_mask
                loss_d = morse_per_atom.sum() / geom_mask.sum().clamp(min=1.0)

            if lam_a > 0 or lam_t > 0 or lam_p > 0:
                flat_pos_true = pos_source
                batch_vec = batch.batch
                _, angle_triplet, dihed_quad, improper_quad = build_local_graph(flat_pos_true, batch_vec, graph_cutoff)

                bt, nmax, _ = coords_pred.shape
                num_graphs = int(batch_vec.max().item() + 1)
                num_frames = max(1, bt // num_graphs)

                if lam_a > 0 and angle_triplet.numel():
                    i, j, k = angle_triplet.t()
                    dij = (flat_pos_true[i] - flat_pos_true[j]).norm(dim=-1)
                    djk = (flat_pos_true[j] - flat_pos_true[k]).norm(dim=-1)
                    keep = (dij < loss_cutoff) & (djk < loss_cutoff)
                    if keep.any():
                        ang_idx_global = angle_triplet[keep]
                        ang_idx_dense = map_global_to_dense_indices(
                            ang_idx_global,
                            batch_vec,
                            nmax,
                            num_graphs=num_graphs,
                            num_frames=num_frames,
                        )
                        cp = angle_cos(coords_pred.view(-1, 3), ang_idx_dense)
                        ct = angle_cos(flat_pos_true, ang_idx_global)
                        if num_frames > 1:
                            ct = ct.repeat(num_frames)
                        loss_a = F.smooth_l1_loss(cp, ct)

                if lam_t > 0 and dihed_quad.numel():
                    i, j, k, l = dihed_quad.t()
                    dij = (flat_pos_true[i] - flat_pos_true[j]).norm(dim=-1)
                    djk = (flat_pos_true[j] - flat_pos_true[k]).norm(dim=-1)
                    dkl = (flat_pos_true[k] - flat_pos_true[l]).norm(dim=-1)
                    keep = (dij < loss_cutoff) & (djk < loss_cutoff) & (dkl < loss_cutoff)
                    if keep.any():
                        dih_idx_global = dihed_quad[keep]
                        dih_idx_dense = map_global_to_dense_indices(
                            dih_idx_global,
                            batch_vec,
                            nmax,
                            num_graphs=num_graphs,
                            num_frames=num_frames,
                        )
                        sp, cp = torsion_sin_cos(coords_pred.view(-1, 3), dih_idx_dense)
                        st, ct = torsion_sin_cos(flat_pos_true, dih_idx_global)
                        if num_frames > 1:
                            st = st.repeat(num_frames)
                            ct = ct.repeat(num_frames)
                        loss_t = F.smooth_l1_loss(sp, st) + F.smooth_l1_loss(cp, ct)

                if lam_p > 0 and improper_quad.numel():
                    i, k, j, l = improper_quad.t()
                    dij = (flat_pos_true[i] - flat_pos_true[j]).norm(dim=-1)
                    dkj = (flat_pos_true[k] - flat_pos_true[j]).norm(dim=-1)
                    dlj = (flat_pos_true[l] - flat_pos_true[j]).norm(dim=-1)
                    keep = (dij < loss_cutoff) & (dkj < loss_cutoff) & (dlj < loss_cutoff)
                    if keep.any():
                        imp_idx_global = improper_quad[keep]
                        imp_idx_dense = map_global_to_dense_indices(
                            imp_idx_global,
                            batch_vec,
                            nmax,
                            num_graphs=num_graphs,
                            num_frames=num_frames,
                        )
                        loss_p = planar_loss_mixed(
                            coords_pred.view(-1, 3),
                            flat_pos_true,
                            imp_idx_dense,
                            imp_idx_global,
                        )

            loss_geom = lam_c * loss_c + lam_d * loss_d + lam_a * loss_a + lam_t * loss_t + lam_p * loss_p

            if detect_nan_inf(loss_geom) or detect_nan_inf(loss_e) or detect_nan_inf(loss_q) or detect_nan_inf(loss_z):
                analyze_and_abort(
                    model,
                    batch,
                    {
                        "loss_geom": loss_geom,
                        "loss_e": loss_e,
                        "loss_q": loss_q,
                        "loss_z": loss_z,
                    },
                )

            loss_tot = lam_e * loss_e + lam_q * loss_q + lam_z * loss_z + loss_geom + bal

        if torch.isnan(loss_tot) or torch.isinf(loss_tot):
            raise ValueError("NaN/Inf total loss")

        if train:
            scaler.scale(loss_tot).backward()
            scaler.unscale_(optim)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optim)
            scaler.update()
            if scheduler is not None:
                scheduler.step()

        num_graphs = batch.num_graphs
        with torch.no_grad():
            et = batch.energy.view(-1).cpu().numpy()
            ep = energy_pred.view(-1).detach().cpu().numpy()
            mask_e = np.isfinite(et) & np.isfinite(ep)
            r2_energy = r2_score(et[mask_e], ep[mask_e]) if mask_e.sum() > 1 else float("nan")

            if has_charge_target:
                qt = charge_true_pad.view(-1).cpu().numpy()
                qp = charge_pred.view(-1).detach().cpu().numpy()
                qm = charge_mask_f.view(-1).cpu().numpy().astype(bool)
                mask_q = np.isfinite(qt) & np.isfinite(qp) & qm
                r2_charge = r2_score(qt[mask_q], qp[mask_q]) if mask_q.sum() > 1 else float("nan")
            else:
                r2_charge = float("nan")

            zt = elem_true_pad.view(-1).cpu().numpy()
            zp = elem_pred.argmax(-1).view(-1).detach().cpu().numpy()
            mask_z = zt != pad_idx
            if mask_z.sum() > 1:
                r2_elem = r2_score(zt[mask_z], zp[mask_z])
                acc_elem = float((zp[mask_z] == zt[mask_z]).mean())
            else:
                r2_elem, acc_elem = float("nan"), float("nan")

            sample_ratio = 0.1 if train else 1.0
            rmsd_sum, rmsd_cnt = batch_rmsd(
                coords_pred.detach(),
                true_xyz_pad.detach(),
                geom_mask.detach(),
                sample_ratio=sample_ratio,
            )

            stats["RMSD"] += rmsd_sum
            stats["RMSD_n"] += rmsd_cnt
            stats["B"] += num_graphs
            stats["E"] += loss_e.item() * num_graphs
            stats["Q"] += loss_q.item() * num_graphs
            stats["Z"] += loss_z.item() * num_graphs
            stats["Bal"] += bal.item() * num_graphs
            stats["Geom"] += loss_geom.item() * num_graphs
            stats["Geom_c"] += loss_c.item() * num_graphs
            stats["Geom_d"] += loss_d.item() * num_graphs
            stats["Geom_a"] += loss_a.item() * num_graphs
            stats["Geom_t"] += loss_t.item() * num_graphs
            stats["Geom_p"] += loss_p.item() * num_graphs

            stats["R2_e"] += (0.0 if math.isnan(r2_energy) else r2_energy) * num_graphs
            stats["R2_q"] += (0.0 if math.isnan(r2_charge) else r2_charge) * num_graphs
            stats["R2_z"] += (0.0 if math.isnan(r2_elem) else r2_elem) * num_graphs
            stats["Acc_z"] += (0.0 if math.isnan(acc_elem) else acc_elem) * num_graphs

    if stats["RMSD_n"] > 0:
        stats["RMSD"] /= stats["RMSD_n"]
    else:
        stats["RMSD"] = float("nan")

    denom = max(1, stats["B"])
    for key in [
        "E",
        "Q",
        "Z",
        "Geom",
        "Geom_c",
        "Geom_d",
        "Geom_a",
        "Geom_t",
        "Geom_p",
        "Bal",
        "R2_e",
        "R2_q",
        "R2_z",
        "Acc_z",
    ]:
        stats[key] /= denom

    return stats
