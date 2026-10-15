from __future__ import annotations

from contextlib import nullcontext
import logging
import math
import os
import sys
import time
from typing import Dict

import numpy as np
import torch
import torch.distributed as dist
import torch.nn.functional as F
from sklearn.metrics import r2_score
from torch_geometric.utils import to_dense_batch
from tqdm import tqdm

try:
    from ..dataset.descriptor_schema import (
        BOND_INDEX_FIELD,
        CHARGE_DESCRIPTOR_SPECS,
        ELEMENT_DESCRIPTOR_SPECS,
        GRAPH_FIELD,
        GRAPH_MASK_FIELD,
        NODE_MASK_FIELD,
    )
except ImportError:
    from dataset.descriptor_schema import (
        BOND_INDEX_FIELD,
        CHARGE_DESCRIPTOR_SPECS,
        ELEMENT_DESCRIPTOR_SPECS,
        GRAPH_FIELD,
        GRAPH_MASK_FIELD,
        NODE_MASK_FIELD,
    )

from .data import ELEMENT_CORRUPT_MASK_FIELD, SAMPLE_TYPE_TO_ID
from .dist_utils import unwrap_model
from .ddp_debug import DDPDebugConfig, DDPPhaseWatchdog
from .dataloader_debug import DataLoaderDebugConfig, DataLoaderWatchdog
from .geometry import (
    angle_cos,
    build_local_graph,
    map_global_to_dense_indices,
    morse_energy,
    torsion_sin_cos,
)

LOGGER = logging.getLogger("multitask")
CLEAN_SAMPLE_TYPE_ID = int(SAMPLE_TYPE_TO_ID["clean"])
GEOM_SAMPLE_TYPE_ID = int(SAMPLE_TYPE_TO_ID["geom"])
TOPO_SAMPLE_TYPE_ID = int(SAMPLE_TYPE_TO_ID["topo"])
BOTH_SAMPLE_TYPE_ID = int(SAMPLE_TYPE_TO_ID["both"])


def _is_dist_ready() -> bool:
    return dist.is_available() and dist.is_initialized()


def _sync_stats_across_ranks(stats: Dict[str, float], global_step: int) -> Dict[str, float]:
    if not _is_dist_ready():
        stats["global_step"] = int(global_step)
        return stats

    gathered = [None for _ in range(dist.get_world_size())]
    dist.all_gather_object(gathered, {"stats": stats, "global_step": int(global_step)})

    merged: Dict[str, float] = {}
    for payload in gathered:
        for key, value in payload["stats"].items():
            numeric = int(value) if key in {"B", "bad"} or key.startswith("W_") else float(value)
            merged[key] = merged.get(key, 0) + numeric

    merged["global_step"] = max(int(payload["global_step"]) for payload in gathered)
    return merged


def _autocast_ctx(device: torch.device, amp_dtype: str):
    amp_dtype = str(amp_dtype or "none").lower()
    if device.type != "cuda" or amp_dtype == "none":
        return nullcontext()
    if amp_dtype == "bf16":
        return torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16)
    if amp_dtype == "fp16":
        return torch.amp.autocast(device_type="cuda", dtype=torch.float16)
    return nullcontext()


def _float32_if_needed(value):
    if isinstance(value, torch.Tensor) and value.is_floating_point() and value.dtype != torch.float32:
        return value.float()
    return value


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


def build_grad_scaler(device: torch.device, amp_dtype: str):
    if device.type == "cuda" and str(amp_dtype).lower() == "fp16":
        return torch.cuda.amp.GradScaler()
    return DummyScaler()


def _global_parameter_norm(parameters) -> float:
    norms = [param.detach().float().norm(2) for param in parameters if param is not None]
    if not norms:
        return 0.0
    stacked = torch.stack(norms)
    return float(torch.norm(stacked, p=2).item())


def _global_grad_norm(parameters) -> float:
    norms = [param.grad.detach().float().norm(2) for param in parameters if param is not None and param.grad is not None]
    if not norms:
        return 0.0
    stacked = torch.stack(norms)
    return float(torch.norm(stacked, p=2).item())


def detect_nan_inf(tensor: torch.Tensor) -> bool:
    return torch.isnan(tensor).any() or torch.isinf(tensor).any()


def analyze_and_abort(model, batch, intermediates: Dict[str, torch.Tensor]) -> None:
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


def _standardized_huber(
    pred: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    *,
    mean: torch.Tensor | float,
    std_value: torch.Tensor | float,
    delta: float = 5.0,
) -> torch.Tensor:
    pred_std = (pred - mean) / std_value
    target_std = (target - mean) / std_value
    diff = pred_std - target_std
    abs_diff = diff.abs()
    delta_tensor = torch.as_tensor(delta, device=diff.device, dtype=diff.dtype)
    quadratic = torch.minimum(abs_diff, delta_tensor)
    linear = abs_diff - quadratic
    loss = 0.5 * quadratic.square() + delta_tensor * linear
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

    pred_np = pred[valid].detach().to(dtype=torch.float32).cpu().numpy()
    target_np = target[valid].detach().to(dtype=torch.float32).cpu().numpy()
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


def _sample_type_ids(batch, device: torch.device, num_graphs: int) -> torch.Tensor:
    value = getattr(batch, "sample_type_id", None)
    if not isinstance(value, torch.Tensor):
        return torch.full((num_graphs,), CLEAN_SAMPLE_TYPE_ID, device=device, dtype=torch.long)

    sample_types = value.view(-1).to(device=device, dtype=torch.long)
    if sample_types.numel() == num_graphs:
        return sample_types
    if sample_types.numel() == 1 and num_graphs > 1:
        return sample_types.expand(num_graphs)
    LOGGER.warning(
        "Unexpected sample_type_id shape %s for num_graphs=%d; fallback to clean.",
        tuple(value.shape),
        num_graphs,
    )
    return torch.full((num_graphs,), CLEAN_SAMPLE_TYPE_ID, device=device, dtype=torch.long)


def _descriptor_ramp(global_step: int, stage1_max_steps: int, stage2_descriptor_ramp_steps: int) -> float:
    if int(global_step) < int(stage1_max_steps):
        return 0.0
    if int(stage2_descriptor_ramp_steps) <= 0:
        return 1.0
    progress = (int(global_step) - int(stage1_max_steps)) / max(1, int(stage2_descriptor_ramp_steps))
    return float(min(1.0, max(0.0, progress)))


def _stage1_signal_scale(
    global_step: int,
    stage1_max_steps: int,
    stage1_signal_decay_steps: int,
    stage1_signal_floor: float,
) -> float:
    if int(global_step) < int(stage1_max_steps):
        return 1.0
    if int(stage1_signal_decay_steps) <= 0:
        return 1.0
    floor = float(min(1.0, max(0.0, stage1_signal_floor)))
    progress = (int(global_step) - int(stage1_max_steps)) / max(1, int(stage1_signal_decay_steps))
    progress = min(1.0, max(0.0, float(progress)))
    return float(1.0 - progress * (1.0 - floor))


def _graph_masked_mean(values: torch.Tensor, graph_mask: torch.Tensor) -> torch.Tensor:
    mask = graph_mask.float()
    while mask.dim() < values.dim():
        mask = mask.unsqueeze(-1)
    return (values * mask).sum() / mask.sum().clamp(min=1.0)


def _stats_weight_key(key: str) -> str:
    if key in {"E", "E_desc", "R2_e"} or key.startswith("loss_energy_desc_") or key.startswith("r2_energy_desc_"):
        return "W_e"
    if key in {"Q", "Q_desc", "R2_q"} or key.startswith("loss_charge_desc_") or key.startswith("r2_charge_desc_") or key.startswith("acc_charge_desc_"):
        return "W_q"
    if key in {"Z", "R2_z", "Acc_z"}:
        return "W_z"
    if key in {"Z_desc"} or key.startswith("loss_elem_desc_") or key.startswith("acc_elem_desc_"):
        return "W_z_desc"
    if key in {"Bond_exist", "Bond_order", "Acc_bond_exist", "Acc_bond_order"}:
        return "W_bond_pairs"
    if key in {"Geom", "Geom_d", "Geom_a", "Geom_t"}:
        return "W_geom"
    return "B"


def _average_task_groups(task_groups: dict[str, list[torch.Tensor]], device: torch.device) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    grouped_means: dict[str, torch.Tensor] = {}
    for task_type, losses in task_groups.items():
        if losses:
            grouped_means[task_type] = torch.stack(losses).mean()
    if not grouped_means:
        return torch.tensor(0.0, device=device), grouped_means
    return torch.stack(list(grouped_means.values())).mean(), grouped_means


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
    lam_bond_exist,
    lam_bond_order,
    z_label_smooth,
    z_focal_gamma,
    z_temp,
    z_class_balance,
    z_entropy_reg,
    z_logit_l2,
    morse_d,
    morse_a,
    stage1_max_steps,
    stage2_descriptor_ramp_steps,
    stage1_signal_decay_steps,
    stage1_signal_floor,
    graph_cutoff=2.0,
    optim=None,
    amp_dtype="none",
    desc="Train",
    scheduler=None,
    batch_logger=None,
    step_timing_logger=None,
    batch_log_interval=0,
    global_step_start=0,
    is_main_process=True,
    distributed_sync=False,
    max_optimizer_steps=None,
    dataloader_debug: DataLoaderDebugConfig | None = None,
    ddp_debug: DDPDebugConfig | None = None,
    current_epoch: int | None = None,
    current_stage: int | None = None,
    progress_total: int | None = None,
    progress_initial: int = 0,
    progress_mininterval: float = 10.0,
    progress_miniters: int = 100,
    old_pretraining_strategy: bool = False,
    grad_clip_norm: float = 1.0,
):
    train = optim is not None
    use_old_pretraining_strategy = bool(old_pretraining_strategy and train)
    model.train(train)
    global_step = int(global_step_start)
    raw_model = unwrap_model(model)
    optimizer_steps = 0
    completed_pass = True
    step_limit = int(max_optimizer_steps) if max_optimizer_steps else None

    lam_c = 0.0
    lam_p = 0.0

    stats = {
        "E": 0.0,
        "E_desc": 0.0,
        "Q": 0.0,
        "Q_desc": 0.0,
        "Z": 0.0,
        "Z_desc": 0.0,
        "Bond_exist": 0.0,
        "Bond_order": 0.0,
        "Geom": 0.0,
        "Geom_d": 0.0,
        "Geom_a": 0.0,
        "Geom_t": 0.0,
        "Bal": 0.0,
        "Loss_selection": 0.0,
        "Loss_total": 0.0,
        "DescRamp": 0.0,
        "Stage1Scale": 0.0,
        "B": 0,
        "W_e": 0,
        "W_q": 0,
        "W_z": 0,
        "W_z_desc": 0,
        "W_bond_pairs": 0,
        "W_bond_graphs": 0,
        "W_geom": 0,
        "Graphs_clean": 0.0,
        "Graphs_geom": 0.0,
        "Graphs_topo": 0.0,
        "Graphs_both": 0.0,
        "bad": 0,
        "R2_e": 0.0,
        "R2_q": 0.0,
        "R2_z": 0.0,
        "Acc_z": 0.0,
        "Acc_bond_exist": 0.0,
        "Acc_bond_order": 0.0,
        "T_fetch_s": 0.0,
        "T_process_s": 0.0,
        "T_step_s": 0.0,
        "N_nodes": 0,
    }

    energy_desc_names = tuple(raw_model.graph_descriptor_names)
    energy_desc_indices = tuple(
        int(idx)
        for idx in getattr(raw_model, "graph_descriptor_target_indices", tuple(range(len(energy_desc_names))))
    )
    charge_specs = tuple(raw_model.charge_descriptor_specs)
    element_specs = tuple(raw_model.element_descriptor_specs)

    energy_mean = _stat_tensor(std, "muE", device)
    energy_std = _stat_tensor(std, "stdE", device)
    charge_mean = _stat_tensor(std, "muQ", device)
    charge_std = _stat_tensor(std, "stdQ", device)
    energy_desc_mean = _stat_tensor(std, "graph_desc_mu", device, shape=(1, -1))
    energy_desc_std = _stat_tensor(std, "graph_desc_std", device, shape=(1, -1))
    if energy_desc_indices:
        energy_desc_index_tensor = torch.tensor(energy_desc_indices, device=device, dtype=torch.long)
        energy_desc_mean = energy_desc_mean.index_select(1, energy_desc_index_tensor)
        energy_desc_std = energy_desc_std.index_select(1, energy_desc_index_tensor)
    formal_charge_mean = _stat_tensor(std, "formal_charge_mu", device)
    formal_charge_std = _stat_tensor(std, "formal_charge_std", device)
    estate_index_mean = _stat_tensor(std, "estate_index_mu", device)
    estate_index_std = _stat_tensor(std, "estate_index_std", device)

    debug_cfg = dataloader_debug or DataLoaderDebugConfig(enabled=False)
    base_iterator = iter(loader)
    try:
        inferred_progress_total = len(loader)
    except TypeError:
        inferred_progress_total = None

    resolved_progress_total = progress_total if progress_total is not None else inferred_progress_total
    if resolved_progress_total is None and train and step_limit is not None:
        resolved_progress_total = int(progress_initial) + int(step_limit)
    elif resolved_progress_total is not None and progress_total is None and train and step_limit is not None:
        resolved_progress_total = min(int(resolved_progress_total), int(progress_initial) + int(step_limit))

    resolved_progress_initial = max(0, int(progress_initial))
    if resolved_progress_total is not None:
        resolved_progress_total = max(0, int(resolved_progress_total))
        resolved_progress_initial = min(resolved_progress_initial, resolved_progress_total)

    progress_kwargs = {
        "total": resolved_progress_total,
        "initial": resolved_progress_initial,
        "desc": desc,
        "leave": False,
        "mininterval": max(0.0, float(progress_mininterval)),
    }
    resolved_progress_miniters = int(progress_miniters)
    if resolved_progress_miniters > 0:
        progress_kwargs["miniters"] = max(1, resolved_progress_miniters)
    progress = tqdm(**progress_kwargs) if is_main_process else None
    watchdog = DataLoaderWatchdog(
        base_iterator,
        cfg=debug_cfg,
        rank=int(dist.get_rank()) if _is_dist_ready() else 0,
        desc=desc,
        loader_name="train" if train else "val",
        is_main_process=is_main_process,
    )
    ddp_cfg = ddp_debug or DDPDebugConfig(enabled=False)
    current_rank = int(dist.get_rank()) if _is_dist_ready() else 0
    world_size = int(dist.get_world_size()) if _is_dist_ready() else 1
    local_rank = int(os.environ.get("LOCAL_RANK", device.index if device.index is not None else 0))
    ddp_watchdog = DDPPhaseWatchdog(
        cfg=ddp_cfg,
        rank=current_rank,
        world_size=world_size,
        local_rank=local_rank,
        device=device,
        desc=desc,
        model=model,
        is_main_process=is_main_process,
    )
    batch_index = 0
    try:
        while True:
            watchdog.waiting_for_batch(
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
            )
            fetch_start = time.perf_counter()
            try:
                batch = next(base_iterator)
            except StopIteration:
                break
            except Exception as exc:
                watchdog.exception(
                    event="batch_fetch_exception",
                    exc=exc,
                    batch_index=batch_index,
                    global_step=global_step,
                    optimizer_steps=optimizer_steps,
                )
                raise
            fetch_elapsed = time.perf_counter() - fetch_start
            watchdog.batch_fetched(
                wait_s=fetch_elapsed,
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                num_graphs=getattr(batch, "num_graphs", None),
            )

            process_start = time.perf_counter()
            to_device_elapsed = 0.0
            model_forward_elapsed = 0.0
            loss_compute_elapsed = 0.0
            backward_elapsed = 0.0
            unscale_elapsed = 0.0
            grad_clip_elapsed = 0.0
            optimizer_step_elapsed = 0.0
            scheduler_elapsed = 0.0
            optimizer_elapsed = 0.0
            metrics_elapsed = 0.0
            fetch_duration_skew_ms = None
            to_device_duration_skew_ms = None
            model_forward_duration_skew_ms = None
            loss_compute_duration_skew_ms = None
            backward_duration_skew_ms = None
            optimizer_duration_skew_ms = None
            step_total_duration_skew_ms = None
            ddp_watchdog.mark(
                "batch_to_device_start",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
            )
            to_device_start = time.perf_counter()
            batch = batch.to(device, non_blocking=(device.type == "cuda"))
            if step_timing_logger is not None:
                step_timing_logger.sync(device)
            to_device_elapsed = time.perf_counter() - to_device_start
            if step_timing_logger is not None:
                to_device_duration_skew_ms = step_timing_logger.duration_skew_ms(to_device_elapsed, device)
            num_graphs = int(batch.num_graphs)
            num_nodes = int(batch.x.size(0)) if hasattr(batch, "x") and isinstance(batch.x, torch.Tensor) else 0
            ddp_watchdog.mark(
                "batch_to_device_done",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
                duration_s=time.perf_counter() - process_start,
                num_graphs=num_graphs,
                num_nodes=num_nodes,
            )
            grad_norm = None
            if train:
                optim.zero_grad(set_to_none=True)
                ddp_watchdog.mark(
                    "optimizer_zero_grad_done",
                    batch_index=batch_index,
                    global_step=global_step,
                    optimizer_steps=optimizer_steps,
                    epoch=current_epoch,
                    stage=current_stage,
                    num_graphs=num_graphs,
                )

            forward_start = time.perf_counter()
            ddp_watchdog.mark(
                "forward_start",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
                num_graphs=num_graphs,
            )
            descriptor_ramp = _descriptor_ramp(global_step, stage1_max_steps, stage2_descriptor_ramp_steps)
            stage1_signal_scale = _stage1_signal_scale(
                global_step,
                stage1_max_steps,
                stage1_signal_decay_steps,
                stage1_signal_floor,
            )
            set_runtime_task_gates = getattr(raw_model, "set_runtime_task_gates", None)
            if callable(set_runtime_task_gates):
                set_runtime_task_gates(
                    bond_enabled=bool(float(lam_bond_exist) > 0.0 or float(lam_bond_order) > 0.0),
                    energy_desc_enabled=bool(descriptor_ramp > 0.0 and float(lam_e_desc) > 0.0 and len(energy_desc_names) > 0),
                    charge_desc_enabled=bool(descriptor_ramp > 0.0 and float(lam_q_desc) > 0.0 and len(charge_specs) > 0),
                    element_desc_enabled=bool(descriptor_ramp > 0.0 and float(lam_z_desc) > 0.0 and len(element_specs) > 0),
                    legacy_pretraining_strategy=use_old_pretraining_strategy,
                )
            grad_ctx = torch.enable_grad() if train else torch.no_grad()
            with grad_ctx:
                if step_timing_logger is not None:
                    step_timing_logger.sync(device)
                model_forward_start = time.perf_counter()
                with _autocast_ctx(device, amp_dtype):
                    outputs = model(batch)
                    coords_pred = outputs["coords"]
                    energy_outputs = outputs["energy"]
                    charge_outputs = outputs["charge"]
                    elem_outputs = outputs["element"]
                    bond_outputs = outputs["bond"]
                    fused_node_repr = outputs["fused_node_repr"]
                    fused_graph_repr = outputs["fused_graph_repr"]
                    charge_mask = outputs["charge_mask"]
                    node_mask = outputs["node_mask"]
                    bal = outputs["balance_loss"]

                    if step_timing_logger is not None:
                        step_timing_logger.sync(device)
                    model_forward_elapsed = time.perf_counter() - model_forward_start
                    if step_timing_logger is not None:
                        model_forward_duration_skew_ms = step_timing_logger.duration_skew_ms(model_forward_elapsed, device)
                    loss_compute_start = time.perf_counter()
                    energy_pred = energy_outputs["energy"]
                    graph_desc_pred = energy_outputs["graph_desc"]
                    charge_pred = charge_outputs["charge"]
                    elem_pred = elem_outputs["element"]

                    charge_mask_f = charge_mask.squeeze(-1).float()
                    node_mask_f = node_mask.squeeze(-1).float()
                    graph_sample_type = _sample_type_ids(batch, device, num_graphs)
                    clean_graph_mask = graph_sample_type.eq(CLEAN_SAMPLE_TYPE_ID)
                    geom_graph_mask = clean_graph_mask | graph_sample_type.eq(GEOM_SAMPLE_TYPE_ID) | graph_sample_type.eq(BOTH_SAMPLE_TYPE_ID)
                    topo_graph_mask = graph_sample_type.eq(TOPO_SAMPLE_TYPE_ID) | graph_sample_type.eq(BOTH_SAMPLE_TYPE_ID)
                    clean_graph_mask_f = clean_graph_mask.to(device=device, dtype=torch.float32)
                    geom_graph_mask_f = geom_graph_mask.to(device=device, dtype=torch.float32)
                    topo_graph_mask_f = topo_graph_mask.to(device=device, dtype=torch.float32)
                    full_graph_mask_f = torch.ones_like(clean_graph_mask_f)
                    clean_graph_count = int(clean_graph_mask_f.sum().item())
                    geom_graph_count = int(geom_graph_mask_f.sum().item())
                    topo_graph_count = int(topo_graph_mask_f.sum().item())
                    sample_type_counts = torch.bincount(graph_sample_type, minlength=len(SAMPLE_TYPE_TO_ID))
                    clean_node_mask = node_mask_f.unsqueeze(-1) * clean_graph_mask_f.view(-1, 1, 1)
                    geom_node_mask = node_mask_f.unsqueeze(-1) * geom_graph_mask_f.view(-1, 1, 1)
                    topo_node_mask = node_mask_f.unsqueeze(-1) * topo_graph_mask_f.view(-1, 1, 1)
                    energy_graph_mask_f = full_graph_mask_f if use_old_pretraining_strategy else clean_graph_mask_f
                    charge_node_mask = node_mask_f.unsqueeze(-1) * energy_graph_mask_f.view(-1, 1, 1)
                    geom_loss_graph_mask_f = full_graph_mask_f if use_old_pretraining_strategy else geom_graph_mask_f
                    geom_loss_graph_mask = geom_loss_graph_mask_f > 0.5
                    geom_loss_node_mask = node_mask_f.unsqueeze(-1) * geom_loss_graph_mask_f.view(-1, 1, 1)
                    energy_graph_count = int(energy_graph_mask_f.sum().item())
                    geom_supervised_graph_count = int(geom_loss_graph_mask_f.sum().item())

                    if is_main_process and stats["B"] == 0:
                        LOGGER.info(
                            "First batch outputs: coords=%s energy=%s graph_desc=%s charge=%s elem=%s bond_exist=%s bond_order=%s fused_node=%s fused_graph=%s charge_mask=%s node_mask=%s clean_graphs=%d/%d geom_graphs=%d topo_graphs=%d desc_ramp=%.3f stage1_scale=%.3f",
                            tuple(coords_pred.shape),
                            tuple(energy_pred.shape),
                            tuple(graph_desc_pred.shape),
                            tuple(charge_pred.shape),
                            tuple(elem_pred.shape),
                            tuple(bond_outputs["existence"].shape),
                            tuple(bond_outputs["order"].shape),
                            tuple(fused_node_repr.shape),
                            tuple(fused_graph_repr.shape),
                            tuple(charge_mask.shape),
                            tuple(node_mask.shape),
                            clean_graph_count,
                            num_graphs,
                            geom_graph_count,
                            topo_graph_count,
                            descriptor_ramp,
                            stage1_signal_scale,
                        )

                    pad_idx = getattr(raw_model, "pad_elem_index", getattr(raw_model, "n_atom_types", n_atom_types) - 1)
                    elem_source = batch.target_x if hasattr(batch, "target_x") else batch.x
                    elem_true_pad, _ = to_dense_batch(elem_source[:, 0].long(), batch.batch, fill_value=pad_idx)
                    elem_corrupt_mask = _dense_node_attr(batch, ELEMENT_CORRUPT_MASK_FIELD, fill_value=0, dtype=torch.float32)
                    if isinstance(elem_corrupt_mask, torch.Tensor):
                        elem_corrupt_mask = (elem_corrupt_mask > 0.5).to(device=device, dtype=torch.float32)
                        elem_corrupt_mask = elem_corrupt_mask * topo_node_mask
                    else:
                        elem_corrupt_mask = torch.zeros_like(node_mask, dtype=torch.float32)

                # Keep AMP on the model forward only. Compute all losses in fp32 so
                # bf16 activations do not later collide with fp32 targets during backward.
                coords_pred = _float32_if_needed(coords_pred)
                fused_node_repr = _float32_if_needed(fused_node_repr)
                fused_graph_repr = _float32_if_needed(fused_graph_repr)
                charge_mask = _float32_if_needed(charge_mask)
                node_mask = _float32_if_needed(node_mask)
                bal = _float32_if_needed(bal)

                energy_pred = _float32_if_needed(energy_pred)
                graph_desc_pred = _float32_if_needed(graph_desc_pred)
                charge_pred = _float32_if_needed(charge_pred)
                elem_pred = _float32_if_needed(elem_pred)

                for key, value in list(charge_outputs.items()):
                    charge_outputs[key] = _float32_if_needed(value)
                for key, value in list(elem_outputs.items()):
                    elem_outputs[key] = _float32_if_needed(value)
                for key in ("existence", "order", "existence_target", "order_target", "pair_distance"):
                    if key in bond_outputs:
                        bond_outputs[key] = _float32_if_needed(bond_outputs[key])

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

                if use_old_pretraining_strategy:
                    elem_prime_mask = (elem_true_flat != pad_idx).float()
                else:
                    elem_prime_mask = (elem_corrupt_mask.squeeze(-1).reshape(-1) > 0.5).float()
                mask_f = (elem_true_flat != pad_idx).float() * elem_prime_mask
                loss_z = (ce_all * mask_f).sum() / mask_f.sum().clamp(min=1.0)
                elem_supervised_count = int(mask_f.sum().item())

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

                regression_loss_fn = _standardized_mse if use_old_pretraining_strategy else _standardized_huber

                energy_target = batch.energy.view(-1, 1).to(device=device, dtype=torch.float32)
                loss_e = (
                    regression_loss_fn(
                        energy_pred,
                        energy_target,
                        energy_graph_mask_f.view(-1, 1),
                        mean=energy_mean,
                        std_value=energy_std,
                    )
                    if lam_e > 0
                    else torch.tensor(0.0, device=device)
                )

                has_charge_target = hasattr(batch, "y")
                charge_supervision_mask = charge_mask.float() * charge_node_mask
                if has_charge_target:
                    charge_true_pad, _ = to_dense_batch(batch.y, batch.batch, fill_value=0.0)
                    loss_q = regression_loss_fn(
                        charge_pred,
                        charge_true_pad.to(device=device, dtype=torch.float32),
                        charge_supervision_mask,
                        mean=charge_mean,
                        std_value=charge_std,
                    )
                else:
                    charge_true_pad = torch.zeros_like(charge_pred)
                    loss_q = torch.tensor(0.0, device=device)

                graph_desc_true = _flatten_graph_attr(batch, GRAPH_FIELD, batch.num_graphs)
                graph_desc_mask = _flatten_graph_attr(batch, GRAPH_MASK_FIELD, batch.num_graphs)
                energy_desc_losses = []
                if descriptor_ramp > 0.0 and isinstance(graph_desc_true, torch.Tensor) and isinstance(graph_desc_mask, torch.Tensor):
                    graph_desc_true = graph_desc_true.to(device=device, dtype=torch.float32)
                    graph_desc_mask = graph_desc_mask.to(device=device, dtype=torch.float32) * clean_graph_mask_f.view(-1, 1)
                    if energy_desc_indices:
                        graph_desc_true = graph_desc_true.index_select(1, energy_desc_index_tensor)
                        graph_desc_mask = graph_desc_mask.index_select(1, energy_desc_index_tensor)
                    for idx, name in enumerate(energy_desc_names):
                        task_loss = _standardized_huber(
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
                rdkit_charge_mask = rdkit_node_mask * clean_node_mask
                rdkit_elem_mask = rdkit_node_mask * clean_node_mask

                charge_desc_loss_groups: dict[str, list[torch.Tensor]] = {
                    "regression": [],
                    "binary": [],
                }
                charge_desc_targets = {}
                if descriptor_ramp > 0.0:
                    for spec in charge_specs:
                        target = _dense_node_attr(batch, spec.field_name, fill_value=0)
                        if target is None:
                            continue
                        target = target.to(device)
                        charge_desc_targets[spec.name] = target
                        if spec.task_type == "regression":
                            if spec.name == "formal_charge":
                                task_loss = _standardized_huber(
                                    charge_outputs[spec.name],
                                    target.float(),
                                    rdkit_charge_mask,
                                    mean=formal_charge_mean,
                                    std_value=formal_charge_std,
                                )
                            else:
                                task_loss = _standardized_huber(
                                    charge_outputs[spec.name],
                                    target.float(),
                                    rdkit_charge_mask,
                                    mean=estate_index_mean,
                                    std_value=estate_index_std,
                                )
                        else:
                            task_loss, _ = _masked_binary_loss_and_acc(
                                charge_outputs[spec.name],
                                target.float(),
                                rdkit_charge_mask,
                            )
                        charge_desc_loss_groups.setdefault(spec.task_type, []).append(task_loss)
                loss_q_desc, charge_desc_group_losses = _average_task_groups(charge_desc_loss_groups, device)

                elem_desc_loss_groups: dict[str, list[torch.Tensor]] = {
                    "binary": [],
                    "multiclass": [],
                }
                elem_desc_targets = {}
                if descriptor_ramp > 0.0:
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
                                rdkit_elem_mask,
                            )
                        else:
                            task_loss, _ = _masked_multiclass_loss_and_acc(
                                elem_outputs[spec.name],
                                target.squeeze(-1).long(),
                                rdkit_elem_mask.squeeze(-1),
                            )
                        elem_desc_loss_groups.setdefault(spec.task_type, []).append(task_loss)
                loss_z_desc, elem_desc_group_losses = _average_task_groups(elem_desc_loss_groups, device)

                bond_exist_logits = bond_outputs["existence"]
                bond_order_logits = bond_outputs["order"]
                bond_exist_target = bond_outputs["existence_target"]
                bond_order_target = bond_outputs["order_target"]
                bond_pair_count = int(bond_outputs.get("sampled_pair_count", 0))
                bond_positive_count = int(bond_outputs.get("positive_pair_count", 0))
                bond_valid_graph_count = int(bond_outputs.get("valid_graph_count", 0))
                if isinstance(bond_exist_logits, torch.Tensor) and bond_pair_count > 0:
                    bond_pair_mask = torch.ones_like(bond_exist_target, dtype=torch.float32, device=device)
                    loss_bond_exist, acc_bond_exist = _masked_binary_loss_and_acc(
                        bond_exist_logits,
                        bond_exist_target.float(),
                        bond_pair_mask,
                    )
                    loss_bond_order, acc_bond_order = _masked_multiclass_loss_and_acc(
                        bond_order_logits,
                        bond_order_target.long(),
                        torch.ones_like(bond_order_target, dtype=torch.float32, device=device),
                    )
                else:
                    loss_bond_exist = torch.tensor(0.0, device=device)
                    loss_bond_order = torch.tensor(0.0, device=device)
                    acc_bond_exist = float("nan")
                    acc_bond_order = float("nan")

                pos_source = batch.target_pos if hasattr(batch, "target_pos") else batch.pos
                true_xyz_pad, _ = to_dense_batch(pos_source, batch.batch)
                geom_mask = geom_loss_node_mask.squeeze(-1)

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

                if (lam_a > 0 or lam_t > 0) and geom_supervised_graph_count > 0:
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
                        geom_triplet_mask = geom_loss_graph_mask[batch_vec[i]]
                        keep = geom_triplet_mask & (dij < loss_cutoff) & (djk < loss_cutoff)
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
                        geom_quad_mask = geom_loss_graph_mask[batch_vec[i]]
                        keep = geom_quad_mask & (dij < loss_cutoff) & (djk < loss_cutoff) & (dkl < loss_cutoff)
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
                    for item in (
                        loss_geom,
                        loss_e,
                        loss_e_desc,
                        loss_q,
                        loss_q_desc,
                        loss_z,
                        loss_z_desc,
                        loss_bond_exist,
                        loss_bond_order,
                    )
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
                            "loss_bond_exist": loss_bond_exist,
                            "loss_bond_order": loss_bond_order,
                        },
                    )

                stage1_selection = (
                    lam_e * loss_e
                    + lam_q * loss_q
                    + lam_z * loss_z
                    + lam_bond_exist * loss_bond_exist
                    + lam_bond_order * loss_bond_order
                    + loss_geom
                )
                stage2_selection = (
                    descriptor_ramp * lam_e_desc * loss_e_desc
                    + descriptor_ramp * lam_q_desc * loss_q_desc
                    + descriptor_ramp * lam_z_desc * loss_z_desc
                )
                loss_selection = stage1_signal_scale * stage1_selection + stage2_selection
                loss_tot = loss_selection + bal
                if step_timing_logger is not None:
                    step_timing_logger.sync(device)
                loss_compute_elapsed = time.perf_counter() - loss_compute_start
                if step_timing_logger is not None:
                    loss_compute_duration_skew_ms = step_timing_logger.duration_skew_ms(loss_compute_elapsed, device)

            ddp_watchdog.mark(
                "forward_done",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
                duration_s=time.perf_counter() - forward_start,
                loss_total=float(loss_tot.detach().float().item()),
                num_graphs=num_graphs,
            )

            if torch.isnan(loss_tot) or torch.isinf(loss_tot):
                raise ValueError("NaN/Inf total loss")

            if train:
                backward_start = time.perf_counter()
                ddp_watchdog.mark(
                    "backward_start",
                    batch_index=batch_index,
                    global_step=global_step,
                    optimizer_steps=optimizer_steps,
                    epoch=current_epoch,
                    stage=current_stage,
                    loss_total=float(loss_tot.detach().float().item()),
                    num_graphs=num_graphs,
                )
                if step_timing_logger is not None:
                    step_timing_logger.sync(device)
                scaler.scale(loss_tot).backward()
                if step_timing_logger is not None:
                    step_timing_logger.sync(device)
                backward_elapsed = time.perf_counter() - backward_start
                if step_timing_logger is not None:
                    backward_duration_skew_ms = step_timing_logger.duration_skew_ms(backward_elapsed, device)
                ddp_watchdog.mark(
                    "backward_done",
                    batch_index=batch_index,
                    global_step=global_step,
                    optimizer_steps=optimizer_steps,
                    epoch=current_epoch,
                    stage=current_stage,
                    duration_s=backward_elapsed,
                    loss_total=float(loss_tot.detach().float().item()),
                    num_graphs=num_graphs,
                )
                optimizer_start = time.perf_counter()
                unscale_start = time.perf_counter()
                scaler.unscale_(optim)
                if step_timing_logger is not None:
                    step_timing_logger.sync(device)
                unscale_elapsed = time.perf_counter() - unscale_start
                ddp_watchdog.log_grad_summary(
                    raw_model,
                    batch_index=batch_index,
                    global_step=global_step,
                    optimizer_steps=optimizer_steps,
                    epoch=current_epoch,
                    stage=current_stage,
                )
                ddp_watchdog.mark(
                    "optimizer_step_start",
                    batch_index=batch_index,
                    global_step=global_step,
                    optimizer_steps=optimizer_steps,
                    epoch=current_epoch,
                    stage=current_stage,
                    num_graphs=num_graphs,
                )
                grad_clip_start = time.perf_counter()
                if float(grad_clip_norm) > 0:
                    grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), float(grad_clip_norm))
                    grad_norm = float(grad_norm.item()) if isinstance(grad_norm, torch.Tensor) else float(grad_norm)
                else:
                    grad_norm = _global_grad_norm(model.parameters())
                if step_timing_logger is not None:
                    step_timing_logger.sync(device)
                grad_clip_elapsed = time.perf_counter() - grad_clip_start
                optimizer_step_start = time.perf_counter()
                scaler.step(optim)
                scaler.update()
                if step_timing_logger is not None:
                    step_timing_logger.sync(device)
                optimizer_step_elapsed = time.perf_counter() - optimizer_step_start
                if scheduler is not None:
                    scheduler_start = time.perf_counter()
                    scheduler.step()
                    scheduler_elapsed = time.perf_counter() - scheduler_start
                global_step += 1
                optimizer_steps += 1
                optimizer_elapsed = time.perf_counter() - optimizer_start
                if step_timing_logger is not None:
                    optimizer_duration_skew_ms = step_timing_logger.duration_skew_ms(optimizer_elapsed, device)
                ddp_watchdog.mark(
                    "optimizer_step_done",
                    batch_index=batch_index,
                    global_step=global_step,
                    optimizer_steps=optimizer_steps,
                    epoch=current_epoch,
                    stage=current_stage,
                    duration_s=backward_elapsed + optimizer_elapsed,
                    loss_total=float(loss_tot.detach().float().item()),
                    num_graphs=num_graphs,
                )

            ddp_watchdog.mark(
                "metrics_start",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
                num_graphs=num_graphs,
            )
            metrics_start = time.perf_counter()
            with torch.no_grad():
                et = batch.energy.view(-1).detach().to(dtype=torch.float32).cpu().numpy()
                ep = energy_pred.view(-1).detach().to(dtype=torch.float32).cpu().numpy()
                energy_graph_np = (energy_graph_mask_f > 0.5).detach().cpu().numpy().astype(bool)
                mask_e = np.isfinite(et) & np.isfinite(ep) & energy_graph_np
                r2_energy = r2_score(et[mask_e], ep[mask_e]) if mask_e.sum() > 1 else float("nan")

                if has_charge_target:
                    qt = charge_true_pad.view(-1).detach().to(dtype=torch.float32).cpu().numpy()
                    qp = charge_pred.view(-1).detach().to(dtype=torch.float32).cpu().numpy()
                    qm = charge_supervision_mask.squeeze(-1).view(-1).cpu().numpy().astype(bool)
                    mask_q = np.isfinite(qt) & np.isfinite(qp) & qm
                    r2_charge = r2_score(qt[mask_q], qp[mask_q]) if mask_q.sum() > 1 else float("nan")
                else:
                    r2_charge = float("nan")

                zt = elem_true_pad.view(-1).cpu().numpy()
                zp = elem_pred.argmax(-1).view(-1).detach().cpu().numpy()
                mask_z = (elem_prime_mask.view(-1).detach().cpu().numpy() > 0.5) & (zt != pad_idx)
                if mask_z.sum() > 1:
                    r2_elem = r2_score(zt[mask_z], zp[mask_z])
                    acc_elem = float((zp[mask_z] == zt[mask_z]).mean())
                else:
                    r2_elem, acc_elem = float("nan"), float("nan")

                stats["B"] += num_graphs
                stats["W_e"] += energy_graph_count
                stats["W_q"] += energy_graph_count
                stats["W_z"] += elem_supervised_count
                stats["W_z_desc"] += clean_graph_count
                stats["W_bond_pairs"] += bond_pair_count
                stats["W_bond_graphs"] += bond_valid_graph_count
                stats["W_geom"] += geom_supervised_graph_count
                stats["Graphs_clean"] += int(sample_type_counts[CLEAN_SAMPLE_TYPE_ID].item())
                stats["Graphs_geom"] += int(sample_type_counts[GEOM_SAMPLE_TYPE_ID].item())
                stats["Graphs_topo"] += int(sample_type_counts[TOPO_SAMPLE_TYPE_ID].item())
                stats["Graphs_both"] += int(sample_type_counts[BOTH_SAMPLE_TYPE_ID].item())
                stats["E"] += loss_e.item() * energy_graph_count
                stats["E_desc"] += loss_e_desc.item() * clean_graph_count
                stats["Q"] += loss_q.item() * energy_graph_count
                stats["Q_desc"] += loss_q_desc.item() * clean_graph_count
                stats["Z"] += loss_z.item() * elem_supervised_count
                stats["Z_desc"] += loss_z_desc.item() * clean_graph_count
                stats["Bond_exist"] += loss_bond_exist.item() * bond_pair_count
                stats["Bond_order"] += loss_bond_order.item() * bond_pair_count
                stats["Bal"] += bal.item() * num_graphs
                stats["Loss_selection"] += loss_selection.item() * num_graphs
                stats["Loss_total"] += loss_tot.item() * num_graphs
                stats["DescRamp"] += descriptor_ramp * num_graphs
                stats["Stage1Scale"] += stage1_signal_scale * num_graphs
                stats["Geom"] += loss_geom.item() * geom_supervised_graph_count
                stats["Geom_d"] += loss_d.item() * geom_supervised_graph_count
                stats["Geom_a"] += loss_a.item() * geom_supervised_graph_count
                stats["Geom_t"] += loss_t.item() * geom_supervised_graph_count

                stats["R2_e"] += (0.0 if math.isnan(r2_energy) else r2_energy) * energy_graph_count
                stats["R2_q"] += (0.0 if math.isnan(r2_charge) else r2_charge) * energy_graph_count
                stats["R2_z"] += (0.0 if math.isnan(r2_elem) else r2_elem) * elem_supervised_count
                stats["Acc_z"] += (0.0 if math.isnan(acc_elem) else acc_elem) * elem_supervised_count
                stats["Acc_bond_exist"] += (0.0 if math.isnan(acc_bond_exist) else acc_bond_exist) * bond_pair_count
                stats["Acc_bond_order"] += (0.0 if math.isnan(acc_bond_order) else acc_bond_order) * bond_pair_count
                current_process_elapsed = time.perf_counter() - process_start
                stats["T_fetch_s"] += fetch_elapsed
                stats["T_process_s"] += current_process_elapsed
                stats["T_step_s"] += fetch_elapsed + current_process_elapsed
                stats["N_nodes"] += num_nodes

                if descriptor_ramp > 0.0 and graph_desc_true is not None and graph_desc_mask is not None:
                    for idx, name in enumerate(energy_desc_names):
                        pred_task = graph_desc_pred[:, idx : idx + 1]
                        true_task = graph_desc_true[:, idx : idx + 1]
                        mask_task = graph_desc_mask[:, idx : idx + 1]
                        task_loss = _standardized_huber(
                            pred_task,
                            true_task,
                            mask_task,
                            mean=energy_desc_mean[:, idx : idx + 1],
                            std_value=energy_desc_std[:, idx : idx + 1],
                        )
                        task_r2 = _masked_regression_r2(pred_task, true_task, mask_task)
                        _accumulate_detail(stats, f"loss_energy_desc_{name}", task_loss.item(), clean_graph_count)
                        _accumulate_detail(stats, f"r2_energy_desc_{name}", 0.0 if math.isnan(task_r2) else task_r2, clean_graph_count)

                if descriptor_ramp > 0.0:
                    for spec in charge_specs:
                        target = charge_desc_targets.get(spec.name)
                        if target is None:
                            continue
                        pred = charge_outputs[spec.name]
                        if spec.task_type == "regression":
                            if spec.name == "formal_charge":
                                task_loss = _standardized_huber(
                                    pred,
                                    target.float(),
                                    rdkit_charge_mask,
                                    mean=formal_charge_mean,
                                    std_value=formal_charge_std,
                                )
                            else:
                                task_loss = _standardized_huber(
                                    pred,
                                    target.float(),
                                    rdkit_charge_mask,
                                    mean=estate_index_mean,
                                    std_value=estate_index_std,
                                )
                            metric_value = _masked_regression_r2(pred, target.float(), rdkit_charge_mask)
                            metric_key = f"r2_charge_desc_{spec.name}"
                        else:
                            task_loss, metric_value = _masked_binary_loss_and_acc(pred, target.float(), rdkit_charge_mask)
                            metric_key = f"acc_charge_desc_{spec.name}"
                        _accumulate_detail(stats, f"loss_charge_desc_{spec.name}", task_loss.item(), clean_graph_count)
                        _accumulate_detail(stats, metric_key, 0.0 if math.isnan(metric_value) else metric_value, clean_graph_count)
                    for task_type, group_loss in charge_desc_group_losses.items():
                        _accumulate_detail(stats, f"loss_charge_desc_group_{task_type}", group_loss.item(), clean_graph_count)

                    for spec in element_specs:
                        target = elem_desc_targets.get(spec.name)
                        if target is None:
                            continue
                        pred = elem_outputs[spec.name]
                        if spec.task_type == "binary":
                            task_loss, metric_value = _masked_binary_loss_and_acc(pred, target.float(), rdkit_elem_mask)
                        else:
                            task_loss, metric_value = _masked_multiclass_loss_and_acc(
                                pred,
                                target.squeeze(-1).long(),
                                rdkit_elem_mask.squeeze(-1),
                            )
                        _accumulate_detail(stats, f"loss_elem_desc_{spec.name}", task_loss.item(), clean_graph_count)
                        _accumulate_detail(stats, f"acc_elem_desc_{spec.name}", 0.0 if math.isnan(metric_value) else metric_value, clean_graph_count)
                    for task_type, group_loss in elem_desc_group_losses.items():
                        _accumulate_detail(stats, f"loss_elem_desc_group_{task_type}", group_loss.item(), clean_graph_count)

                if train and batch_logger is not None and batch_log_interval > 0 and (global_step % batch_log_interval == 0):
                    step_total_s = fetch_elapsed + current_process_elapsed
                    scaler_scale = float(scaler.get_scale()) if hasattr(scaler, "get_scale") else None
                    batch_logger(
                        {
                            "loss_total": loss_tot.item(),
                            "loss_selection": loss_selection.item(),
                            "descriptor_ramp": descriptor_ramp,
                            "stage1_signal_scale": stage1_signal_scale,
                            "loss_energy": loss_e.item(),
                            "loss_energy_desc": loss_e_desc.item(),
                            "loss_charge": loss_q.item(),
                            "loss_charge_desc": loss_q_desc.item(),
                            "loss_elem": loss_z.item(),
                            "loss_elem_desc": loss_z_desc.item(),
                            "loss_bond_exist": loss_bond_exist.item(),
                            "acc_bond_exist": 0.0 if math.isnan(acc_bond_exist) else acc_bond_exist,
                            "loss_bond_order": loss_bond_order.item(),
                            "acc_bond_order": 0.0 if math.isnan(acc_bond_order) else acc_bond_order,
                            "loss_geom": loss_geom.item(),
                            "loss_geom_dist": loss_d.item(),
                            "loss_geom_angle": loss_a.item(),
                            "loss_geom_torsion": loss_t.item(),
                            "loss_balance": bal.item(),
                            "grad_norm": float(grad_norm) if grad_norm is not None else None,
                            "param_norm": _global_parameter_norm(raw_model.parameters()),
                            "lr": optim.param_groups[0]["lr"] if optim is not None else None,
                            "graphs": num_graphs,
                            "nodes": num_nodes,
                            "graphs_clean": clean_graph_count,
                            "graphs_geom_supervised": geom_supervised_graph_count,
                            "graphs_topo_supervised": topo_graph_count,
                            "graphs_perturbed": num_graphs - clean_graph_count,
                            "bond_graphs_ok": bond_valid_graph_count,
                            "bond_pairs": bond_pair_count,
                            "bond_pairs_positive": bond_positive_count,
                            "amp_dtype": amp_dtype,
                            "amp_scaler_scale": scaler_scale,
                            "fetch_time_s": fetch_elapsed,
                            "process_time_s": current_process_elapsed,
                            "step_time_s": step_total_s,
                            "graphs_per_s": float(num_graphs) / max(step_total_s, 1e-9),
                            "nodes_per_s": float(num_nodes) / max(step_total_s, 1e-9),
                            "fetch_share": fetch_elapsed / max(step_total_s, 1e-9),
                        },
                        global_step,
                    )

            metrics_elapsed = time.perf_counter() - metrics_start
            ddp_watchdog.mark(
                "metrics_done",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
                duration_s=time.perf_counter() - process_start,
                loss_total=float(loss_tot.detach().float().item()),
                num_graphs=num_graphs,
            )
            process_elapsed = time.perf_counter() - process_start
            step_total_elapsed = fetch_elapsed + process_elapsed
            if step_timing_logger is not None:
                fetch_duration_skew_ms = step_timing_logger.duration_skew_ms(fetch_elapsed, device)
                step_total_duration_skew_ms = step_timing_logger.duration_skew_ms(step_total_elapsed, device)
            if train and step_timing_logger is not None:
                cuda_mem_allocated_mb = None
                cuda_mem_reserved_mb = None
                cuda_max_mem_allocated_mb = None
                if device.type == "cuda" and torch.cuda.is_available():
                    current_device = device.index if device.index is not None else torch.cuda.current_device()
                    cuda_mem_allocated_mb = torch.cuda.memory_allocated(current_device) / (1024**2)
                    cuda_mem_reserved_mb = torch.cuda.memory_reserved(current_device) / (1024**2)
                    cuda_max_mem_allocated_mb = torch.cuda.max_memory_allocated(current_device) / (1024**2)
                step_timing_logger.log_step(
                    {
                        "desc": desc,
                        "epoch": current_epoch,
                        "stage": current_stage,
                        "batch_index": batch_index,
                        "global_step": global_step,
                        "optimizer_steps": optimizer_steps,
                        "amp_dtype": str(amp_dtype),
                        "num_graphs": num_graphs,
                        "num_nodes": num_nodes,
                        "fetch_s": fetch_elapsed,
                        "to_device_s": to_device_elapsed,
                        "model_forward_s": model_forward_elapsed,
                        "loss_compute_s": loss_compute_elapsed,
                        "backward_s": backward_elapsed,
                        "unscale_s": unscale_elapsed,
                        "grad_clip_s": grad_clip_elapsed,
                        "optimizer_step_s": optimizer_step_elapsed,
                        "scheduler_s": scheduler_elapsed,
                        "optimizer_s": optimizer_elapsed,
                        "metrics_s": metrics_elapsed,
                        "process_total_s": process_elapsed,
                        "step_total_s": step_total_elapsed,
                        "fetch_duration_skew_ms": fetch_duration_skew_ms,
                        "to_device_duration_skew_ms": to_device_duration_skew_ms,
                        "model_forward_duration_skew_ms": model_forward_duration_skew_ms,
                        "loss_compute_duration_skew_ms": loss_compute_duration_skew_ms,
                        "backward_duration_skew_ms": backward_duration_skew_ms,
                        "optimizer_duration_skew_ms": optimizer_duration_skew_ms,
                        "step_total_duration_skew_ms": step_total_duration_skew_ms,
                        "graphs_per_s": float(num_graphs) / max(step_total_elapsed, 1e-9),
                        "nodes_per_s": float(num_nodes) / max(step_total_elapsed, 1e-9),
                        "cuda_mem_allocated_mb": cuda_mem_allocated_mb,
                        "cuda_mem_reserved_mb": cuda_mem_reserved_mb,
                        "cuda_max_mem_allocated_mb": cuda_max_mem_allocated_mb,
                    },
                    global_step=global_step,
                )
            ddp_watchdog.mark(
                "batch_complete",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
                duration_s=process_elapsed,
                loss_total=float(loss_tot.detach().float().item()),
                num_graphs=num_graphs,
            )
            watchdog.batch_processed(
                process_s=process_elapsed,
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
            )
            if progress is not None:
                progress.update(1)
            batch_index += 1

            if train and step_limit and optimizer_steps >= step_limit:
                completed_pass = False
                break
    except Exception as exc:
        ddp_watchdog.exception(
            event="run_epoch_exception",
            exc=exc,
            batch_index=batch_index,
            global_step=global_step,
            optimizer_steps=optimizer_steps,
            epoch=current_epoch,
            stage=current_stage,
        )
        raise
    finally:
        if progress is not None:
            progress.close()
        clear_runtime_task_gates = getattr(raw_model, "clear_runtime_task_gates", None)
        if callable(clear_runtime_task_gates):
            clear_runtime_task_gates()
        watchdog.close()

    try:
        if distributed_sync:
            ddp_watchdog.mark(
                "distributed_stats_sync_start",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
            )
            stats = _sync_stats_across_ranks(stats, global_step)
            global_step = stats["global_step"]
            ddp_watchdog.mark(
                "distributed_stats_sync_done",
                batch_index=batch_index,
                global_step=global_step,
                optimizer_steps=optimizer_steps,
                epoch=current_epoch,
                stage=current_stage,
            )
        else:
            stats["global_step"] = global_step

        denom = max(1, stats["B"])
        for key, value in list(stats.items()):
            if key in {"B", "bad", "global_step"} or key.startswith("W_") or key.startswith("T_") or key.startswith("N_"):
                continue
            weight_key = _stats_weight_key(key)
            key_denom = int(stats.get(weight_key, denom if weight_key == "B" else 0))
            stats[key] = value / max(1, key_denom)

        stats["optimizer_steps"] = int(optimizer_steps)
        stats["completed_pass"] = int(completed_pass)
        return stats
    finally:
        ddp_watchdog.close()
