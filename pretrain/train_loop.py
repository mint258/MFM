from __future__ import annotations

from contextlib import nullcontext
import logging
import math
import sys
from typing import Dict

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import r2_score
from torch_geometric.utils import to_dense_batch
from tqdm import tqdm

from dataset.descriptor_schema import (
    CHARGE_DESCRIPTOR_SPECS,
    ELEMENT_DESCRIPTOR_SPECS,
    GRAPH_DESCRIPTOR_NAMES,
    GRAPH_FIELD,
    GRAPH_MASK_FIELD,
    NODE_MASK_FIELD,
)

from .geometry import (
    angle_cos,
    build_local_graph,
    map_global_to_dense_indices,
    morse_energy,
    torsion_sin_cos,
)

LOGGER = logging.getLogger("multitask")


def _autocast_ctx(fp16: bool):
    """Use AMP only when explicitly enabled on CUDA; otherwise no-op context."""
    if fp16 and torch.cuda.is_available():
        return torch.amp.autocast(device_type="cuda", dtype=torch.float16)
    return nullcontext()


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


def _stat_tensor(std, key: str, device, *, shape=None) -> torch.Tensor:
    value = std[key]
    if isinstance(value, torch.Tensor):
        tensor = value.to(device=device, dtype=torch.float32)
    else:
        tensor = torch.tensor(value, device=device, dtype=torch.float32)
    if shape is not None:
        tensor = tensor.view(*shape)
    return tensor


def _masked_mean(values: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    mask = mask.float()
    return (values * mask).sum() / mask.sum().clamp(min=1.0)


def _standardized_mse(
    pred: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    *,
    mean: torch.Tensor | float,
    std_value: torch.Tensor | float,
) -> torch.Tensor:
    pred_std = (pred - mean) / std_value
    target_std = (target - mean) / std_value
    loss = F.mse_loss(pred_std, target_std, reduction="none")
    return _masked_mean(loss, mask)


def _masked_binary_loss_and_acc(logits: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, float]:
    target = target.float()
    loss = F.binary_cross_entropy_with_logits(logits, target, reduction="none")
    loss = _masked_mean(loss, mask)

    valid = mask.bool()
    if valid.any():
        acc = (logits[valid] > 0).eq(target[valid] > 0.5).float().mean().item()
    else:
        acc = float("nan")
    return loss, acc


def _masked_multiclass_loss_and_acc(logits: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, float]:
    num_classes = logits.size(-1)
    target = target.clamp(min=0, max=num_classes - 1)
    flat_logits = logits.reshape(-1, num_classes)
    flat_target = target.reshape(-1)
    flat_mask = mask.reshape(-1).float()

    ce = F.cross_entropy(flat_logits, flat_target, reduction="none")
    loss = (ce * flat_mask).sum() / flat_mask.sum().clamp(min=1.0)

    valid = flat_mask.bool()
    if valid.any():
        pred = flat_logits.argmax(dim=-1)
        acc = pred[valid].eq(flat_target[valid]).float().mean().item()
    else:
        acc = float("nan")
    return loss, acc


def _masked_regression_r2(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> float:
    valid = mask.bool()
    if not valid.any():
        return float("nan")

    pred_np = pred[valid].detach().cpu().numpy()
    target_np = target[valid].detach().cpu().numpy()
    finite = np.isfinite(pred_np) & np.isfinite(target_np)
    if finite.sum() <= 1:
        return float("nan")
    return float(r2_score(target_np[finite], pred_np[finite]))


def _flatten_graph_attr(batch, attr_name: str, num_graphs: int):
    value = getattr(batch, attr_name, None)
    if not isinstance(value, torch.Tensor):
        return None
    return value.view(num_graphs, -1)


def _dense_node_attr(batch, attr_name: str, *, fill_value=0, dtype=None):
    value = getattr(batch, attr_name, None)
    if not isinstance(value, torch.Tensor):
        return None
    if dtype is not None:
        value = value.to(dtype)
    dense, _ = to_dense_batch(value, batch.batch, fill_value=fill_value)
    return dense


def _accumulate_detail(stats: dict, key: str, value: float, weight: int) -> None:
    stats[key] = stats.get(key, 0.0) + value * weight


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
    lam_e_desc,
    lam_q,
    lam_q_desc,
    lam_z,
    lam_z_desc,
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
    batch_logger=None,
    batch_log_interval=0,
    global_step_start=0,
):
    train = optim is not None
    model.train(train)
    global_step = int(global_step_start)

    # Coordinate and planar losses are intentionally retired and must stay disabled.
    lam_c = 0.0
    lam_p = 0.0

    stats = {
        "E": 0.0,
        "E_desc": 0.0,
        "Q": 0.0,
        "Q_desc": 0.0,
        "Z": 0.0,
        "Z_desc": 0.0,
        "Geom": 0.0,
        "Geom_d": 0.0,
        "Geom_a": 0.0,
        "Geom_t": 0.0,
        "Bal": 0.0,
        "B": 0,
        "bad": 0,
        "R2_e": 0.0,
        "R2_q": 0.0,
        "R2_z": 0.0,
        "Acc_z": 0.0,
    }

    energy_desc_names = tuple(model.graph_descriptor_names)
    charge_specs = tuple(model.charge_descriptor_specs)
    element_specs = tuple(model.element_descriptor_specs)

    energy_desc_mean = _stat_tensor(std, "graph_desc_mu", device, shape=(1, -1))
    energy_desc_std = _stat_tensor(std, "graph_desc_std", device, shape=(1, -1))
    formal_charge_mean = _stat_tensor(std, "formal_charge_mu", device)
    formal_charge_std = _stat_tensor(std, "formal_charge_std", device)
    estate_index_mean = _stat_tensor(std, "estate_index_mu", device)
    estate_index_std = _stat_tensor(std, "estate_index_std", device)

    for batch in tqdm(loader, desc=desc, leave=False):
        batch = batch.to(device)
        grad_norm = None
        if train:
            optim.zero_grad(set_to_none=True)

        with _autocast_ctx(fp16):
            outputs = model(batch)
            coords_pred = outputs["coords"]
            energy_outputs = outputs["energy"]
            charge_outputs = outputs["charge"]
            elem_outputs = outputs["element"]
            charge_mask = outputs["charge_mask"]
            node_mask = outputs["node_mask"]
            bal = outputs["balance_loss"]

            energy_pred = energy_outputs["energy"]
            graph_desc_pred = energy_outputs["graph_desc"]
            charge_pred = charge_outputs["charge"]
            elem_pred = elem_outputs["element"]

            _batch_size, nmax, _ = coords_pred.shape
            charge_mask_f = charge_mask.squeeze(-1).float()
            node_mask_f = node_mask.squeeze(-1).float()

            if stats["B"] == 0:
                LOGGER.info(
                    "First batch outputs: coords=%s energy=%s graph_desc=%s charge=%s elem=%s charge_mask=%s node_mask=%s",
                    tuple(coords_pred.shape),
                    tuple(energy_pred.shape),
                    tuple(graph_desc_pred.shape),
                    tuple(charge_pred.shape),
                    tuple(elem_pred.shape),
                    tuple(charge_mask.shape),
                    tuple(node_mask.shape),
                )

            pad_idx = getattr(model, "pad_elem_index", getattr(model, "n_atom_types", n_atom_types) - 1)
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

            y_e = ((batch.energy.view(-1, 1) - std["muE"]) / std["stdE"]).to(device)
            p_e = (energy_pred - std["muE"]) / std["stdE"]
            if lam_e > 0:
                loss_e = F.mse_loss(p_e, y_e, reduction="none").mean()
            else:
                loss_e = torch.tensor(0.0, device=device)

            has_charge_target = hasattr(batch, "y")
            if has_charge_target:
                charge_true_pad, _ = to_dense_batch(batch.y, batch.batch, fill_value=0.0)
                charge_true_std = ((charge_true_pad - std["muQ"]) / std["stdQ"]).to(device)
                charge_pred_std = (charge_pred - std["muQ"]) / std["stdQ"]
                loss_q = F.mse_loss(charge_pred_std, charge_true_std, reduction="none")
                loss_q = _masked_mean(loss_q, charge_mask)
            else:
                charge_true_pad = torch.zeros_like(charge_pred)
                loss_q = torch.tensor(0.0, device=device)

            graph_desc_true = _flatten_graph_attr(batch, GRAPH_FIELD, batch.num_graphs)
            graph_desc_mask = _flatten_graph_attr(batch, GRAPH_MASK_FIELD, batch.num_graphs)
            energy_desc_losses = []
            if isinstance(graph_desc_true, torch.Tensor) and isinstance(graph_desc_mask, torch.Tensor):
                graph_desc_true = graph_desc_true.to(device=device, dtype=torch.float32)
                graph_desc_mask = graph_desc_mask.to(device=device, dtype=torch.float32)
                for idx, name in enumerate(energy_desc_names):
                    task_loss = _standardized_mse(
                        graph_desc_pred[:, idx : idx + 1],
                        graph_desc_true[:, idx : idx + 1],
                        graph_desc_mask[:, idx : idx + 1],
                        mean=energy_desc_mean[:, idx : idx + 1],
                        std_value=energy_desc_std[:, idx : idx + 1],
                    )
                    energy_desc_losses.append(task_loss)
                loss_e_desc = torch.stack(energy_desc_losses).mean() if energy_desc_losses else torch.tensor(0.0, device=device)
            else:
                graph_desc_true = None
                graph_desc_mask = None
                loss_e_desc = torch.tensor(0.0, device=device)

            rdkit_node_mask = _dense_node_attr(batch, NODE_MASK_FIELD, fill_value=0, dtype=torch.float32)
            if isinstance(rdkit_node_mask, torch.Tensor):
                rdkit_node_mask = (rdkit_node_mask > 0.5).to(device=device, dtype=torch.float32)
                rdkit_node_mask = rdkit_node_mask * node_mask.float()
            else:
                rdkit_node_mask = torch.zeros_like(node_mask, dtype=torch.float32)

            charge_desc_losses = []
            charge_desc_targets = {}
            for spec in charge_specs:
                target = _dense_node_attr(batch, spec.field_name, fill_value=0)
                if target is None:
                    continue
                target = target.to(device)
                charge_desc_targets[spec.name] = target
                if spec.task_type == "regression":
                    if spec.name == "formal_charge":
                        task_loss = _standardized_mse(
                            charge_outputs[spec.name],
                            target.float(),
                            rdkit_node_mask,
                            mean=formal_charge_mean,
                            std_value=formal_charge_std,
                        )
                    else:
                        task_loss = _standardized_mse(
                            charge_outputs[spec.name],
                            target.float(),
                            rdkit_node_mask,
                            mean=estate_index_mean,
                            std_value=estate_index_std,
                        )
                else:
                    task_loss, _ = _masked_binary_loss_and_acc(
                        charge_outputs[spec.name],
                        target.float(),
                        rdkit_node_mask,
                    )
                charge_desc_losses.append(task_loss)
            loss_q_desc = torch.stack(charge_desc_losses).mean() if charge_desc_losses else torch.tensor(0.0, device=device)

            elem_desc_losses = []
            elem_desc_targets = {}
            for spec in element_specs:
                target = _dense_node_attr(batch, spec.field_name, fill_value=0)
                if target is None:
                    continue
                target = target.to(device)
                elem_desc_targets[spec.name] = target
                if spec.task_type == "binary":
                    task_loss, _ = _masked_binary_loss_and_acc(
                        elem_outputs[spec.name],
                        target.float(),
                        rdkit_node_mask,
                    )
                else:
                    task_loss, _ = _masked_multiclass_loss_and_acc(
                        elem_outputs[spec.name],
                        target.squeeze(-1).long(),
                        rdkit_node_mask.squeeze(-1),
                    )
                elem_desc_losses.append(task_loss)
            loss_z_desc = torch.stack(elem_desc_losses).mean() if elem_desc_losses else torch.tensor(0.0, device=device)

            pos_source = batch.target_pos if hasattr(batch, "target_pos") else batch.pos
            true_xyz_pad, _ = to_dense_batch(pos_source, batch.batch)
            geom_mask = node_mask_f

            loss_d = torch.tensor(0.0, device=device)
            loss_a = torch.tensor(0.0, device=device)
            loss_t = torch.tensor(0.0, device=device)
            if lam_d > 0:
                dist_pred = torch.cdist(coords_pred, coords_pred)
                dist_true = torch.cdist(true_xyz_pad, true_xyz_pad)
                pair_mask = geom_mask[:, :, None] * geom_mask[:, None, :]
                v = morse_energy(dist_pred, dist_true, morse_d, morse_a) * pair_mask
                morse_per_atom = torch.log1p(v.sum(-1).clamp(min=0.0)) * geom_mask
                loss_d = morse_per_atom.sum() / geom_mask.sum().clamp(min=1.0)

            if lam_a > 0 or lam_t > 0:
                flat_pos_true = pos_source
                batch_vec = batch.batch
                _, angle_triplet, dihed_quad, _ = build_local_graph(flat_pos_true, batch_vec, graph_cutoff)

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

            loss_geom = lam_d * loss_d + lam_a * loss_a + lam_t * loss_t

            if any(
                detect_nan_inf(item)
                for item in (loss_geom, loss_e, loss_e_desc, loss_q, loss_q_desc, loss_z, loss_z_desc)
            ):
                analyze_and_abort(
                    model,
                    batch,
                    {
                        "loss_geom": loss_geom,
                        "loss_e": loss_e,
                        "loss_e_desc": loss_e_desc,
                        "loss_q": loss_q,
                        "loss_q_desc": loss_q_desc,
                        "loss_z": loss_z,
                        "loss_z_desc": loss_z_desc,
                    },
                )

            loss_tot = (
                lam_e * loss_e
                + lam_e_desc * loss_e_desc
                + lam_q * loss_q
                + lam_q_desc * loss_q_desc
                + lam_z * loss_z
                + lam_z_desc * loss_z_desc
                + loss_geom
                + bal
            )

        if torch.isnan(loss_tot) or torch.isinf(loss_tot):
            raise ValueError("NaN/Inf total loss")

        if train:
            scaler.scale(loss_tot).backward()
            scaler.unscale_(optim)
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optim)
            scaler.update()
            if scheduler is not None:
                scheduler.step()
            global_step += 1

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

            stats["B"] += num_graphs
            stats["E"] += loss_e.item() * num_graphs
            stats["E_desc"] += loss_e_desc.item() * num_graphs
            stats["Q"] += loss_q.item() * num_graphs
            stats["Q_desc"] += loss_q_desc.item() * num_graphs
            stats["Z"] += loss_z.item() * num_graphs
            stats["Z_desc"] += loss_z_desc.item() * num_graphs
            stats["Bal"] += bal.item() * num_graphs
            stats["Geom"] += loss_geom.item() * num_graphs
            stats["Geom_d"] += loss_d.item() * num_graphs
            stats["Geom_a"] += loss_a.item() * num_graphs
            stats["Geom_t"] += loss_t.item() * num_graphs

            stats["R2_e"] += (0.0 if math.isnan(r2_energy) else r2_energy) * num_graphs
            stats["R2_q"] += (0.0 if math.isnan(r2_charge) else r2_charge) * num_graphs
            stats["R2_z"] += (0.0 if math.isnan(r2_elem) else r2_elem) * num_graphs
            stats["Acc_z"] += (0.0 if math.isnan(acc_elem) else acc_elem) * num_graphs

            if graph_desc_true is not None and graph_desc_mask is not None:
                for idx, name in enumerate(energy_desc_names):
                    pred_task = graph_desc_pred[:, idx : idx + 1]
                    true_task = graph_desc_true[:, idx : idx + 1]
                    mask_task = graph_desc_mask[:, idx : idx + 1]
                    task_loss = _standardized_mse(
                        pred_task,
                        true_task,
                        mask_task,
                        mean=energy_desc_mean[:, idx : idx + 1],
                        std_value=energy_desc_std[:, idx : idx + 1],
                    )
                    task_r2 = _masked_regression_r2(pred_task, true_task, mask_task)
                    _accumulate_detail(stats, f"loss_energy_desc_{name}", task_loss.item(), num_graphs)
                    _accumulate_detail(
                        stats,
                        f"r2_energy_desc_{name}",
                        0.0 if math.isnan(task_r2) else task_r2,
                        num_graphs,
                    )

            for spec in charge_specs:
                target = charge_desc_targets.get(spec.name)
                if target is None:
                    continue
                pred = charge_outputs[spec.name]
                if spec.task_type == "regression":
                    if spec.name == "formal_charge":
                        task_loss = _standardized_mse(
                            pred,
                            target.float(),
                            rdkit_node_mask,
                            mean=formal_charge_mean,
                            std_value=formal_charge_std,
                        )
                    else:
                        task_loss = _standardized_mse(
                            pred,
                            target.float(),
                            rdkit_node_mask,
                            mean=estate_index_mean,
                            std_value=estate_index_std,
                        )
                    metric_value = _masked_regression_r2(pred, target.float(), rdkit_node_mask)
                    metric_key = f"r2_charge_desc_{spec.name}"
                else:
                    task_loss, metric_value = _masked_binary_loss_and_acc(pred, target.float(), rdkit_node_mask)
                    metric_key = f"acc_charge_desc_{spec.name}"
                _accumulate_detail(stats, f"loss_charge_desc_{spec.name}", task_loss.item(), num_graphs)
                _accumulate_detail(
                    stats,
                    metric_key,
                    0.0 if math.isnan(metric_value) else metric_value,
                    num_graphs,
                )

            for spec in element_specs:
                target = elem_desc_targets.get(spec.name)
                if target is None:
                    continue
                pred = elem_outputs[spec.name]
                if spec.task_type == "binary":
                    task_loss, metric_value = _masked_binary_loss_and_acc(pred, target.float(), rdkit_node_mask)
                    metric_key = f"acc_elem_desc_{spec.name}"
                else:
                    task_loss, metric_value = _masked_multiclass_loss_and_acc(
                        pred,
                        target.squeeze(-1).long(),
                        rdkit_node_mask.squeeze(-1),
                    )
                    metric_key = f"acc_elem_desc_{spec.name}"
                _accumulate_detail(stats, f"loss_elem_desc_{spec.name}", task_loss.item(), num_graphs)
                _accumulate_detail(
                    stats,
                    metric_key,
                    0.0 if math.isnan(metric_value) else metric_value,
                    num_graphs,
                )

            if train and batch_logger is not None and batch_log_interval > 0 and (global_step % batch_log_interval == 0):
                batch_logger(
                    {
                        "loss_total": loss_tot.item(),
                        "loss_energy": loss_e.item(),
                        "loss_energy_desc": loss_e_desc.item(),
                        "loss_charge": loss_q.item(),
                        "loss_charge_desc": loss_q_desc.item(),
                        "loss_elem": loss_z.item(),
                        "loss_elem_desc": loss_z_desc.item(),
                        "loss_geom": loss_geom.item(),
                        "loss_geom_dist": loss_d.item(),
                        "loss_geom_angle": loss_a.item(),
                        "loss_geom_torsion": loss_t.item(),
                        "loss_balance": bal.item(),
                        "grad_norm": float(grad_norm.item()) if grad_norm is not None else None,
                        "lr": optim.param_groups[0]["lr"] if optim is not None else None,
                        "graphs": num_graphs,
                    },
                    global_step,
                )

    denom = max(1, stats["B"])
    for key, value in list(stats.items()):
        if key in {"B", "bad", "global_step"}:
            continue
        stats[key] = value / denom

    stats["global_step"] = global_step
    return stats
