from __future__ import annotations

import argparse
import csv
import json
import math
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader
from torch_geometric.utils import to_dense_batch
from tqdm import tqdm

from models.moe import MultiTaskMoE
from pretrain.data import OnlyStableWrapper, MaskedPerturbDataset, create_dataset, fast_collate
from pretrain.degrade_molecules import DegradeConfig
from pretrain.geometry import _rmsd_pair, angle_cos, build_local_graph, morse_energy, torsion_sin_cos

try:
    from rdkit import Chem

    from dataset.rdkit_descriptor_generator import CIP_CODE_TO_INT, _attach_conformer

    HAVE_RDKIT = True
except Exception:  # pragma: no cover - optional dependency
    Chem = None
    CIP_CODE_TO_INT = {"": 0, "R": 1, "S": 2, "other": 3}
    _attach_conformer = None
    HAVE_RDKIT = False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        "Evaluate geom-stage checkpoints on the validation set with richer geometry metrics."
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default="test_ckpt/search/node4_geom_stage",
        help="Directory containing the stage-related checkpoints to evaluate.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="log/search/node4_geom_stage/manifest.tsv",
        help="Manifest TSV used to annotate each checkpoint with its search-time hyperparameters.",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default="test_data/principal_valid_test.lmdb",
        help="Validation LMDB path.",
    )
    parser.add_argument("--val-start", type=int, default=0)
    parser.add_argument("--val-end", type=int, default=874)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--device",
        type=str,
        default=("cuda" if torch.cuda.is_available() else "cpu"),
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="log/analysis/geom_stage_eval",
        help="Directory to write summary TSV/JSON outputs.",
    )
    parser.add_argument(
        "--checkpoint-glob",
        type=str,
        default="*.pt",
        help="Glob pattern under --checkpoint-dir.",
    )
    parser.add_argument(
        "--perturb-mode",
        type=str,
        default="both",
        choices=["topo", "geom", "both"],
        help="Input corruption mode used for validation inference.",
    )
    parser.add_argument("--perturb-level", type=float, default=0.5)
    parser.add_argument(
        "--perturb-seed",
        type=int,
        default=114,
        help="Base perturb seed used in training.",
    )
    parser.add_argument(
        "--val-seed-offset",
        type=int,
        default=1_100_000,
        help=(
            "Added to --perturb-seed for validation perturbations. "
            "The default matches the previous small-scale search setup with one train root."
        ),
    )
    parser.add_argument("--graph-cutoff", type=float, default=2.0)
    parser.add_argument("--loss-cutoff", type=float, default=2.0)
    parser.add_argument("--morse-D", type=float, default=1.0)
    parser.add_argument("--morse-a", type=float, default=1.0)
    parser.add_argument(
        "--clash-threshold",
        type=float,
        default=0.8,
        help="Predicted inter-atomic distance below this is treated as a hard clash candidate.",
    )
    parser.add_argument(
        "--clash-reference-min-dist",
        type=float,
        default=1.6,
        help="Only count clashes for pairs whose true distance is larger than this threshold.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Optional batch cap for quick smoke evaluation. 0 means full validation set.",
    )
    return parser.parse_args()


def _safe_div(num: float, den: float) -> float:
    if den <= 0:
        return float("nan")
    return num / den


def _wrapped_abs_deg(pred_deg: torch.Tensor, true_deg: torch.Tensor) -> torch.Tensor:
    delta = torch.remainder(pred_deg - true_deg + 180.0, 360.0) - 180.0
    return delta.abs()


def _dense_node_attr(batch, attr_name: str, *, fill_value=0, dtype=None):
    value = getattr(batch, attr_name, None)
    if not isinstance(value, torch.Tensor):
        return None
    if dtype is not None:
        value = value.to(dtype)
    dense, _ = to_dense_batch(value, batch.batch, fill_value=fill_value)
    return dense


def _list_attr(batch, attr_name: str, expected_len: int) -> list[Any]:
    value = getattr(batch, attr_name, None)
    if isinstance(value, (list, tuple)):
        return list(value)
    if value is None:
        return [None] * expected_len
    return [value] + [None] * max(0, expected_len - 1)


def _unique_undirected_edges(edge_index: torch.Tensor) -> torch.Tensor:
    if edge_index.numel() == 0:
        return edge_index.new_empty((2, 0))
    src = torch.minimum(edge_index[0], edge_index[1])
    dst = torch.maximum(edge_index[0], edge_index[1])
    keep = src != dst
    if not keep.any():
        return edge_index.new_empty((2, 0))
    pairs = torch.stack([src[keep], dst[keep]], dim=1)
    pairs = torch.unique(pairs, dim=0)
    return pairs.t().contiguous()


def _batched_upper_triangle_mask(n_atom: int, device: torch.device) -> torch.Tensor:
    return torch.triu(torch.ones((n_atom, n_atom), dtype=torch.bool, device=device), diagonal=1)


def _load_checkpoint(path: Path, *, map_location: str | torch.device = "cpu") -> dict[str, Any]:
    try:
        return torch.load(path, map_location=map_location, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=map_location)


def _parse_run_command(command: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    tokens = shlex.split(command)
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if not token.startswith("--"):
            idx += 1
            continue
        key = token[2:].replace("-", "_")
        if idx + 1 < len(tokens) and not tokens[idx + 1].startswith("--"):
            parsed[key] = tokens[idx + 1]
            idx += 2
        else:
            parsed[key] = True
            idx += 1
    return parsed


def _read_manifest(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    entries: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t", 3)
            if len(parts) < 4:
                continue
            if parts[0] == "run_name" and parts[1] == "start_time":
                continue
            run_name, start_time, gpu_id, command = parts
            cli = _parse_run_command(command)
            entries[run_name] = {
                "run_name": run_name,
                "start_time": start_time,
                "gpu_id": gpu_id,
                "command": command,
                "cli": cli,
            }
    return entries


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _build_model_from_checkpoint_cfg(cfg: dict[str, Any], device: torch.device) -> MultiTaskMoE:
    model = MultiTaskMoE(
        cfg["backbone_config"],
        n_atom_types=int(cfg["n_atom_types"]),
        n_experts_energy=int(cfg["n_experts_energy"]),
        n_experts_charge=int(cfg["n_experts_charge"]),
        n_experts_elem=int(cfg["n_experts_elem"]),
        n_experts_geom=int(cfg["n_experts_geom"]),
        top_k_energy=int(cfg["top_k_energy"]),
        top_k_charge=int(cfg["top_k_charge"]),
        top_k_elem=int(cfg["top_k_elem"]),
        top_k_geom=int(cfg["top_k_geom"]),
        expert_real_layers=int(cfg["expert_real_layers"]),
        expert_int_layers=int(cfg["expert_int_layers"]),
        expert_heads=int(cfg["expert_heads"]),
        expert_ff_mult=int(cfg["expert_ff_mult"]),
    )
    return model.to(device)


def _build_eval_dataset(args: argparse.Namespace):
    base = OnlyStableWrapper(create_dataset(args.data_root, args.val_start, args.val_end))
    degrade_cfg = DegradeConfig(
        mode=args.perturb_mode,
        level=args.perturb_level,
        topo_replace_frac=None,
        topo_delete_frac=0.0,
        geom_noise_std=None,
        geom_angle_std_deg=0.0,
        geom_bond_scale_std=0.0,
    )
    seed = int(args.perturb_seed + args.val_seed_offset)
    return MaskedPerturbDataset(base, degrade_cfg, seed=seed)


def _build_loader(dataset, *, batch_size: int, num_workers: int) -> DataLoader:
    kwargs = {
        "batch_size": batch_size,
        "shuffle": False,
        "num_workers": num_workers,
        "pin_memory": True,
        "persistent_workers": False,
        "collate_fn": fast_collate,
    }
    if num_workers > 0:
        kwargs["prefetch_factor"] = 2
    return DataLoader(dataset, **kwargs)


def _bond_adjacency_and_edges(mol) -> tuple[list[list[int]], list[tuple[int, int]]]:
    adjacency = [[] for _ in range(mol.GetNumAtoms())]
    edges: list[tuple[int, int]] = []
    for bond in mol.GetBonds():
        a = int(bond.GetBeginAtomIdx())
        b = int(bond.GetEndAtomIdx())
        adjacency[a].append(b)
        adjacency[b].append(a)
        edges.append((min(a, b), max(a, b)))
    return adjacency, edges


def _bond_angle_triplets(adjacency: list[list[int]]) -> torch.Tensor:
    triplets: list[list[int]] = []
    for center, neighbors in enumerate(adjacency):
        uniq = sorted(set(neighbors))
        for left_idx in range(len(uniq)):
            for right_idx in range(left_idx + 1, len(uniq)):
                triplets.append([uniq[left_idx], center, uniq[right_idx]])
    if not triplets:
        return torch.empty((0, 3), dtype=torch.long)
    return torch.tensor(triplets, dtype=torch.long)


def _bond_torsion_quads(adjacency: list[list[int]]) -> torch.Tensor:
    quads: list[list[int]] = []
    for j, neigh_j in enumerate(adjacency):
        neigh_j = sorted(set(neigh_j))
        for k in neigh_j:
            if j >= k:
                continue
            left = [i for i in neigh_j if i != k]
            right = [l for l in sorted(set(adjacency[k])) if l != j]
            for i in left:
                for l in right:
                    quads.append([i, j, k, l])
    if not quads:
        return torch.empty((0, 4), dtype=torch.long)
    return torch.tensor(quads, dtype=torch.long)


def _cip_codes_from_conformer(template_h, coords: torch.Tensor) -> list[int] | None:
    if not HAVE_RDKIT or _attach_conformer is None:
        return None
    try:
        mol = _attach_conformer(template_h, coords.detach().cpu())
        if hasattr(Chem, "AssignAtomChiralTagsFromStructure"):
            Chem.AssignAtomChiralTagsFromStructure(mol)
        if hasattr(Chem, "AssignStereochemistryFrom3D"):
            Chem.AssignStereochemistryFrom3D(mol)
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    except Exception:
        return None

    output: list[int] = []
    for atom in mol.GetAtoms():
        code = atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else ""
        output.append(int(CIP_CODE_TO_INT.get(code, CIP_CODE_TO_INT["other"])))
    return output


def _compute_topology_metrics(
    *,
    smiles: str | None,
    atomic_numbers: torch.Tensor,
    pred_coords: torch.Tensor,
    true_coords: torch.Tensor,
    cip_target: torch.Tensor | None,
) -> dict[str, Any]:
    result = {
        "attempted": 0,
        "matched": 0,
        "bond_abs_sum": 0.0,
        "bond_sq_sum": 0.0,
        "bond_count": 0,
        "bond_angle_abs_deg_sum": 0.0,
        "bond_angle_count": 0,
        "bond_torsion_abs_deg_sum": 0.0,
        "bond_torsion_count": 0,
        "cip_correct": 0,
        "cip_count": 0,
    }
    if not HAVE_RDKIT or not smiles or not isinstance(smiles, str) or not smiles.strip():
        return result

    result["attempted"] = 1
    try:
        template = Chem.MolFromSmiles(smiles.strip())
        if template is None:
            return result
        template_h = Chem.AddHs(template)
    except Exception:
        return result

    rdkit_z = [int(atom.GetAtomicNum()) for atom in template_h.GetAtoms()]
    if rdkit_z != [int(v) for v in atomic_numbers.view(-1).tolist()]:
        return result

    result["matched"] = 1
    adjacency, bond_pairs = _bond_adjacency_and_edges(template_h)
    if bond_pairs:
        bond_idx = torch.tensor(bond_pairs, dtype=torch.long, device=pred_coords.device)
        pred_len = (pred_coords[bond_idx[:, 0]] - pred_coords[bond_idx[:, 1]]).norm(dim=-1)
        true_len = (true_coords[bond_idx[:, 0]] - true_coords[bond_idx[:, 1]]).norm(dim=-1)
        diff = pred_len - true_len
        result["bond_abs_sum"] = diff.abs().sum().item()
        result["bond_sq_sum"] = diff.square().sum().item()
        result["bond_count"] = int(diff.numel())

    angle_triplets = _bond_angle_triplets(adjacency).to(pred_coords.device)
    if angle_triplets.numel():
        pred_cos = angle_cos(pred_coords, angle_triplets)
        true_cos = angle_cos(true_coords, angle_triplets)
        pred_deg = torch.rad2deg(torch.acos(pred_cos.clamp(-1.0, 1.0)))
        true_deg = torch.rad2deg(torch.acos(true_cos.clamp(-1.0, 1.0)))
        diff = (pred_deg - true_deg).abs()
        result["bond_angle_abs_deg_sum"] = diff.sum().item()
        result["bond_angle_count"] = int(diff.numel())

    torsion_quads = _bond_torsion_quads(adjacency).to(pred_coords.device)
    if torsion_quads.numel():
        pred_sin, pred_cos = torsion_sin_cos(pred_coords, torsion_quads)
        true_sin, true_cos = torsion_sin_cos(true_coords, torsion_quads)
        pred_deg = torch.rad2deg(torch.atan2(pred_sin, pred_cos))
        true_deg = torch.rad2deg(torch.atan2(true_sin, true_cos))
        diff = _wrapped_abs_deg(pred_deg, true_deg)
        result["bond_torsion_abs_deg_sum"] = diff.sum().item()
        result["bond_torsion_count"] = int(diff.numel())

    if cip_target is not None:
        pred_cip = _cip_codes_from_conformer(template_h, pred_coords)
        if pred_cip is not None:
            pred_cip_t = torch.tensor(pred_cip, dtype=torch.long, device=pred_coords.device)
            valid = cip_target.view(-1).long() > 0
            if valid.any():
                result["cip_count"] = int(valid.sum().item())
                result["cip_correct"] = int(pred_cip_t[valid].eq(cip_target.view(-1).long()[valid]).sum().item())

    return result


@dataclass
class EvalState:
    graph_count: int = 0
    atom_count: int = 0
    rmsd_values: list[float] = field(default_factory=list)
    morse_loss_sum: float = 0.0
    global_dist_abs_sum: float = 0.0
    global_dist_sq_sum: float = 0.0
    global_dist_count: int = 0
    local_dist_abs_sum: float = 0.0
    local_dist_sq_sum: float = 0.0
    local_dist_count: int = 0
    local_angle_abs_deg_sum: float = 0.0
    local_angle_count: int = 0
    local_torsion_abs_deg_sum: float = 0.0
    local_torsion_count: int = 0
    clash_count: int = 0
    clash_candidate_count: int = 0
    topo_graphs_attempted: int = 0
    topo_graphs_matched: int = 0
    bond_abs_sum: float = 0.0
    bond_sq_sum: float = 0.0
    bond_count: int = 0
    bond_angle_abs_deg_sum: float = 0.0
    bond_angle_count: int = 0
    bond_torsion_abs_deg_sum: float = 0.0
    bond_torsion_count: int = 0
    cip_correct: int = 0
    cip_count: int = 0

    def add_topology_metrics(self, payload: dict[str, Any]) -> None:
        self.topo_graphs_attempted += int(payload["attempted"])
        self.topo_graphs_matched += int(payload["matched"])
        self.bond_abs_sum += float(payload["bond_abs_sum"])
        self.bond_sq_sum += float(payload["bond_sq_sum"])
        self.bond_count += int(payload["bond_count"])
        self.bond_angle_abs_deg_sum += float(payload["bond_angle_abs_deg_sum"])
        self.bond_angle_count += int(payload["bond_angle_count"])
        self.bond_torsion_abs_deg_sum += float(payload["bond_torsion_abs_deg_sum"])
        self.bond_torsion_count += int(payload["bond_torsion_count"])
        self.cip_correct += int(payload["cip_correct"])
        self.cip_count += int(payload["cip_count"])

    def summary(self) -> dict[str, Any]:
        rmsd_sorted = sorted(self.rmsd_values)
        rmsd_median = float("nan")
        if rmsd_sorted:
            mid = len(rmsd_sorted) // 2
            if len(rmsd_sorted) % 2 == 1:
                rmsd_median = rmsd_sorted[mid]
            else:
                rmsd_median = 0.5 * (rmsd_sorted[mid - 1] + rmsd_sorted[mid])

        return {
            "n_graphs": self.graph_count,
            "n_atoms": self.atom_count,
            "rmsd_align_mean": _safe_div(sum(self.rmsd_values), len(self.rmsd_values)),
            "rmsd_align_median": rmsd_median,
            "morse_loss_mean": _safe_div(self.morse_loss_sum, self.graph_count),
            "dist_mae_global": _safe_div(self.global_dist_abs_sum, self.global_dist_count),
            "dist_rmse_global": math.sqrt(_safe_div(self.global_dist_sq_sum, self.global_dist_count))
            if self.global_dist_count > 0
            else float("nan"),
            "dist_mae_local": _safe_div(self.local_dist_abs_sum, self.local_dist_count),
            "dist_rmse_local": math.sqrt(_safe_div(self.local_dist_sq_sum, self.local_dist_count))
            if self.local_dist_count > 0
            else float("nan"),
            "angle_mae_deg_local": _safe_div(self.local_angle_abs_deg_sum, self.local_angle_count),
            "torsion_mae_deg_local": _safe_div(self.local_torsion_abs_deg_sum, self.local_torsion_count),
            "hard_clash_ratio": _safe_div(self.clash_count, self.clash_candidate_count),
            "topology_graphs_attempted": self.topo_graphs_attempted,
            "topology_graphs_matched": self.topo_graphs_matched,
            "bond_length_mae": _safe_div(self.bond_abs_sum, self.bond_count),
            "bond_length_rmse": math.sqrt(_safe_div(self.bond_sq_sum, self.bond_count))
            if self.bond_count > 0
            else float("nan"),
            "bond_angle_mae_deg": _safe_div(self.bond_angle_abs_deg_sum, self.bond_angle_count),
            "bond_torsion_mae_deg": _safe_div(self.bond_torsion_abs_deg_sum, self.bond_torsion_count),
            "cip_accuracy": _safe_div(self.cip_correct, self.cip_count),
            "global_dist_pair_count": self.global_dist_count,
            "local_dist_pair_count": self.local_dist_count,
            "local_angle_count": self.local_angle_count,
            "local_torsion_count": self.local_torsion_count,
            "clash_candidate_count": self.clash_candidate_count,
            "bond_count": self.bond_count,
            "bond_angle_count": self.bond_angle_count,
            "bond_torsion_count": self.bond_torsion_count,
            "cip_count": self.cip_count,
        }


def _evaluate_checkpoint(
    ckpt_path: Path,
    loader: DataLoader,
    args: argparse.Namespace,
    device: torch.device,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_checkpoint(ckpt_path, map_location="cpu")
    cfg = payload["cfg"]
    model = _build_model_from_checkpoint_cfg(cfg, device)
    model.load_state_dict(payload["model_state"], strict=True)
    model.eval()

    state = EvalState()
    with torch.inference_mode():
        for batch_idx, batch in enumerate(tqdm(loader, desc=ckpt_path.stem, leave=False)):
            if args.max_batches > 0 and batch_idx >= args.max_batches:
                break

            batch = batch.to(device)
            outputs = model(batch)

            coords_pred = outputs["coords"]
            node_mask = outputs["node_mask"].squeeze(-1).bool()
            pos_source = batch.target_pos if hasattr(batch, "target_pos") else batch.pos
            true_xyz_pad, _ = to_dense_batch(pos_source, batch.batch, fill_value=0.0)

            elem_source = batch.target_x if hasattr(batch, "target_x") else batch.x
            atom_dense, _ = to_dense_batch(elem_source[:, 0].long(), batch.batch, fill_value=0)
            cip_dense = _dense_node_attr(batch, "rdkit_node_cip_code", fill_value=0, dtype=torch.long)
            smiles_list = _list_attr(batch, "smiles", batch.num_graphs)

            for graph_idx in range(batch.num_graphs):
                valid = node_mask[graph_idx]
                n_atom = int(valid.sum().item())
                if n_atom < 2:
                    continue

                pred = coords_pred[graph_idx, valid]
                true = true_xyz_pad[graph_idx, valid]
                atomic_numbers = atom_dense[graph_idx, valid].view(-1).long()
                cip_target = None
                if isinstance(cip_dense, torch.Tensor):
                    cip_target = cip_dense[graph_idx, valid].view(-1).long()

                state.graph_count += 1
                state.atom_count += n_atom

                if n_atom >= 3:
                    rmsd_val = float(_rmsd_pair(pred, true).item())
                    state.rmsd_values.append(rmsd_val)

                dist_pred = torch.cdist(pred, pred)
                dist_true = torch.cdist(true, true)
                tri_mask = _batched_upper_triangle_mask(n_atom, pred.device)
                global_diff = dist_pred[tri_mask] - dist_true[tri_mask]
                if global_diff.numel():
                    state.global_dist_abs_sum += global_diff.abs().sum().item()
                    state.global_dist_sq_sum += global_diff.square().sum().item()
                    state.global_dist_count += int(global_diff.numel())

                    clash_candidates = dist_true[tri_mask] > float(args.clash_reference_min_dist)
                    if clash_candidates.any():
                        clash_hits = dist_pred[tri_mask][clash_candidates] < float(args.clash_threshold)
                        state.clash_count += int(clash_hits.sum().item())
                        state.clash_candidate_count += int(clash_candidates.sum().item())

                morse_v = morse_energy(dist_pred, dist_true, args.morse_D, args.morse_a)
                morse_per_atom = torch.log1p(morse_v.sum(-1).clamp(min=0.0))
                state.morse_loss_sum += float(morse_per_atom.mean().item())

                zero_batch = torch.zeros(n_atom, dtype=torch.long, device=pred.device)
                edge_index, angle_triplet, dihed_quad, _ = build_local_graph(true, zero_batch, args.graph_cutoff)
                edge_index = _unique_undirected_edges(edge_index)
                if edge_index.numel():
                    local_pred = (pred[edge_index[0]] - pred[edge_index[1]]).norm(dim=-1)
                    local_true = (true[edge_index[0]] - true[edge_index[1]]).norm(dim=-1)
                    local_diff = local_pred - local_true
                    state.local_dist_abs_sum += local_diff.abs().sum().item()
                    state.local_dist_sq_sum += local_diff.square().sum().item()
                    state.local_dist_count += int(local_diff.numel())

                if angle_triplet.numel():
                    i, j, k = angle_triplet.t()
                    keep = ((true[i] - true[j]).norm(dim=-1) < args.loss_cutoff) & (
                        (true[j] - true[k]).norm(dim=-1) < args.loss_cutoff
                    )
                    if keep.any():
                        kept_angles = angle_triplet[keep]
                        pred_cos = angle_cos(pred, kept_angles)
                        true_cos = angle_cos(true, kept_angles)
                        pred_deg = torch.rad2deg(torch.acos(pred_cos.clamp(-1.0, 1.0)))
                        true_deg = torch.rad2deg(torch.acos(true_cos.clamp(-1.0, 1.0)))
                        diff_deg = (pred_deg - true_deg).abs()
                        state.local_angle_abs_deg_sum += diff_deg.sum().item()
                        state.local_angle_count += int(diff_deg.numel())

                if dihed_quad.numel():
                    i, j, k, l = dihed_quad.t()
                    keep = (
                        ((true[i] - true[j]).norm(dim=-1) < args.loss_cutoff)
                        & ((true[j] - true[k]).norm(dim=-1) < args.loss_cutoff)
                        & ((true[k] - true[l]).norm(dim=-1) < args.loss_cutoff)
                    )
                    if keep.any():
                        kept_torsions = dihed_quad[keep]
                        pred_sin, pred_cos = torsion_sin_cos(pred, kept_torsions)
                        true_sin, true_cos = torsion_sin_cos(true, kept_torsions)
                        pred_deg = torch.rad2deg(torch.atan2(pred_sin, pred_cos))
                        true_deg = torch.rad2deg(torch.atan2(true_sin, true_cos))
                        diff_deg = _wrapped_abs_deg(pred_deg, true_deg)
                        state.local_torsion_abs_deg_sum += diff_deg.sum().item()
                        state.local_torsion_count += int(diff_deg.numel())

                topo_metrics = _compute_topology_metrics(
                    smiles=smiles_list[graph_idx] if graph_idx < len(smiles_list) else None,
                    atomic_numbers=atomic_numbers,
                    pred_coords=pred,
                    true_coords=true,
                    cip_target=cip_target,
                )
                state.add_topology_metrics(topo_metrics)

    return state.summary(), cfg


def _checkpoint_metadata(
    *,
    ckpt_path: Path,
    cfg: dict[str, Any],
    manifest_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    cli = manifest_entry["cli"] if manifest_entry else {}
    bb_cfg = cfg["backbone_config"]
    return {
        "run_name": ckpt_path.stem,
        "checkpoint_path": str(ckpt_path.resolve()),
        "hidden_channels": int(bb_cfg.get("hidden_channels", bb_cfg.get("atom_embedding_dim", -1))),
        "bb_layers": int(bb_cfg.get("bb_layers", bb_cfg.get("num_layers", -1))),
        "bb_heads": int(bb_cfg.get("bb_heads", -1)),
        "expert_real_layers": int(cfg.get("expert_real_layers", -1)),
        "expert_int_layers": int(cfg.get("expert_int_layers", -1)),
        "n_experts_geom": int(cfg.get("n_experts_geom", -1)),
        "top_k_geom": int(cfg.get("top_k_geom", -1)),
        "stage1_max_epochs": _coerce_int(cli.get("stage1_max_epochs")),
        "lambda_dist": _coerce_float(cli.get("lambda_dist")),
        "lambda_angle": _coerce_float(cli.get("lambda_angle")),
        "lambda_torsion": _coerce_float(cli.get("lambda_torsion")),
        "train_batch_size": _coerce_int(cli.get("batch_size")),
        "train_epochs": _coerce_int(cli.get("epochs")),
        "manifest_command": manifest_entry["command"] if manifest_entry else "",
    }


def _write_outputs(results: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tsv_path = output_dir / "geom_stage_summary.tsv"
    json_path = output_dir / "geom_stage_summary.json"

    if results:
        fieldnames = list(results[0].keys())
        with tsv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(results)
    else:
        tsv_path.write_text("", encoding="utf-8")

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)


def _print_console_summary(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No checkpoints were evaluated.")
        return

    print("Geometry evaluation summary")
    for row in results:
        print(
            f"- {row['run_name']}: "
            f"RMSD={row['rmsd_align_mean']:.4f}, "
            f"Morse={row['morse_loss_mean']:.4f}, "
            f"LocalDistRMSE={row['dist_rmse_local']:.4f}, "
            f"AngleMAE={row['angle_mae_deg_local']:.2f} deg, "
            f"TorsionMAE={row['torsion_mae_deg_local']:.2f} deg, "
            f"Clash={row['hard_clash_ratio']:.6f}"
        )


def main() -> None:
    args = _parse_args()
    device = torch.device(args.device)
    checkpoint_dir = Path(args.checkpoint_dir)
    manifest_map = _read_manifest(Path(args.manifest))

    dataset = _build_eval_dataset(args)
    loader = _build_loader(dataset, batch_size=args.batch_size, num_workers=args.num_workers)

    ckpt_paths = sorted(checkpoint_dir.glob(args.checkpoint_glob))
    if not ckpt_paths:
        raise FileNotFoundError(f"No checkpoints matched {args.checkpoint_glob!r} under {checkpoint_dir}")

    results: list[dict[str, Any]] = []
    for ckpt_path in ckpt_paths:
        metrics, cfg = _evaluate_checkpoint(ckpt_path, loader, args, device)
        row = {}
        row.update(_checkpoint_metadata(ckpt_path=ckpt_path, cfg=cfg, manifest_entry=manifest_map.get(ckpt_path.stem)))
        row.update(metrics)
        results.append(row)

    results.sort(key=lambda item: (float("inf") if math.isnan(item["rmsd_align_mean"]) else item["rmsd_align_mean"]))
    output_dir = Path(args.output_dir)
    _write_outputs(results, output_dir)
    _print_console_summary(results)
    print(f"Saved summary TSV to {output_dir.resolve() / 'geom_stage_summary.tsv'}")
    print(f"Saved summary JSON to {output_dir.resolve() / 'geom_stage_summary.json'}")


if __name__ == "__main__":
    main()
