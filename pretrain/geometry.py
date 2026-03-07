from __future__ import annotations

import torch
import torch.nn.functional as F
from utils_debug import safe_exp

try:
    from torch_cluster import radius_graph as _radius_graph_impl
except Exception:  # pragma: no cover - optional dependency
    _radius_graph_impl = None


def radius_graph(pos, r, batch=None, loop=False):
    """Compatibility wrapper with a pure-PyTorch fallback when torch_cluster is unavailable."""
    if _radius_graph_impl is not None:
        return _radius_graph_impl(pos, r=r, batch=batch, loop=loop)

    if batch is None:
        batch = torch.zeros(pos.size(0), dtype=torch.long, device=pos.device)

    src_all = []
    dst_all = []
    for graph_id in batch.unique(sorted=True):
        idx = torch.where(batch == graph_id)[0]
        if idx.numel() == 0:
            continue

        coords = pos[idx]
        dist = torch.cdist(coords, coords)
        keep = dist <= float(r)
        if not loop:
            keep.fill_diagonal_(False)

        src_local, dst_local = torch.where(keep)
        if src_local.numel() == 0:
            continue
        src_all.append(idx[src_local])
        dst_all.append(idx[dst_local])

    if not src_all:
        return pos.new_empty((2, 0), dtype=torch.long)
    return torch.stack([torch.cat(src_all), torch.cat(dst_all)], dim=0)


def build_local_graph(pos, batch_vec, cutoff, angle_sum_tolerance: float = 10.0):
    """Build local geometric index sets for angle/torsion/planar losses."""
    edge_index = radius_graph(pos, r=cutoff, batch=batch_vec, loop=False)
    if edge_index.numel() == 0:
        z = pos.new_zeros((0,), dtype=torch.long)
        return edge_index, z.view(0, 3), z.view(0, 4), z.view(0, 4)

    adj = [[] for _ in range(pos.size(0))]
    i, j = edge_index
    for a, b in zip(i.tolist(), j.tolist()):
        adj[a].append(b)
        adj[b].append(a)

    angles = []
    for center, neighbors in enumerate(adj):
        if len(neighbors) < 2:
            continue
        for x in range(len(neighbors)):
            for y in range(x + 1, len(neighbors)):
                angles.append([neighbors[x], center, neighbors[y]])

    angle_triplet = (
        pos.new_tensor(angles, dtype=torch.long)
        if angles
        else pos.new_empty((0, 3), dtype=torch.long)
    )

    dihedrals = []
    for i_, j_, k_ in angle_triplet.tolist():
        for l_ in adj[k_]:
            if l_ != j_ and l_ != i_:
                dihedrals.append([i_, j_, k_, l_])

    dihed_quad = (
        pos.new_tensor(dihedrals, dtype=torch.long)
        if dihedrals
        else pos.new_empty((0, 4), dtype=torch.long)
    )

    improper = []
    if angle_triplet.numel() > 0:
        all_angles_cos = angle_cos(pos, angle_triplet)
        center_to_angles = {}
        for idx, triplet in enumerate(angle_triplet.tolist()):
            center = triplet[1]
            center_to_angles.setdefault(center, []).append(all_angles_cos[idx])

        for center, neighbors in enumerate(adj):
            if len(neighbors) != 3:
                continue
            if center not in center_to_angles or len(center_to_angles[center]) != 3:
                continue

            angles_rad = [torch.acos(c.clamp(-1.0, 1.0)) for c in center_to_angles[center]]
            angle_sum_deg = torch.rad2deg(sum(angles_rad))
            if abs(angle_sum_deg - 360.0) < angle_sum_tolerance:
                i_nb, k_nb, l_nb = neighbors[0], neighbors[1], neighbors[2]
                improper.append([i_nb, k_nb, center, l_nb])
                improper.append([k_nb, l_nb, center, i_nb])

    improper_quad = (
        pos.new_tensor(improper, dtype=torch.long)
        if improper
        else pos.new_empty((0, 4), dtype=torch.long)
    )

    return edge_index, angle_triplet, dihed_quad, improper_quad


def planar_loss(coords_pred, coords_true, idx):
    """Planar loss via pseudo-torsion sine values."""
    sin_pred, _ = torsion_sin_cos(coords_pred, idx)
    sin_true, _ = torsion_sin_cos(coords_true, idx)
    return F.smooth_l1_loss(sin_pred, sin_true)


def angle_cos(coords, idx):
    v1 = coords[idx[:, 0]] - coords[idx[:, 1]]
    v2 = coords[idx[:, 2]] - coords[idx[:, 1]]
    return F.cosine_similarity(v1, v2, dim=-1)


def torsion_sin_cos(coords, idx):
    i, j, k, l = idx.t()
    b0 = coords[i] - coords[j]
    b1 = coords[k] - coords[j]
    b2 = coords[l] - coords[k]
    b1n = F.normalize(b1, dim=-1)
    v = b0 - (b0 * b1n).sum(-1, keepdim=True) * b1n
    w = b2 - (b2 * b1n).sum(-1, keepdim=True) * b1n
    x = (v * w).sum(-1)
    y = (torch.cross(b1n, v) * w).sum(-1)
    r = (x**2 + y**2 + 1e-9).sqrt()
    return y / r, x / r


def _kabsch_torch(p: torch.Tensor, q: torch.Tensor):
    """Rigid-body optimal rotation via Kabsch algorithm."""
    dtype = p.dtype
    p = p.float()
    q = q.float()
    c = p.T @ q
    u, _, vt = torch.linalg.svd(c, full_matrices=False)
    r = vt.T @ u.T
    if torch.det(r) < 0:
        vt[-1] *= -1
        r = vt.T @ u.T
    return r.to(dtype)


def _rmsd_pair(p: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
    pc, qc = p.mean(0, keepdim=True), q.mean(0, keepdim=True)
    p0, q0 = p - pc, q - qc
    r = _kabsch_torch(p0, q0)
    diff = p0 @ r - q0
    return diff.pow(2).mean().sqrt()


def map_global_to_dense_indices(
    idx: torch.Tensor,
    batch_vec: torch.Tensor,
    nmax: int,
    num_graphs: int,
    num_frames: int = 1,
) -> torch.Tensor:
    """Map concatenated global node indices to flattened dense indices."""
    device = batch_vec.device
    idx = idx.to(device)

    flat = idx.reshape(-1)
    counts = torch.bincount(batch_vec, minlength=num_graphs)
    offsets = torch.cumsum(torch.cat([counts.new_zeros(1), counts[:-1]]), dim=0)

    graph_id = batch_vec[flat]
    local = flat - offsets[graph_id]
    dense = (graph_id * nmax + local).view_as(idx)

    if num_frames == 1:
        return dense

    per_frame_stride = num_graphs * nmax
    dense_list = [dense + t * per_frame_stride for t in range(num_frames)]
    return torch.cat(dense_list, dim=0)


def planar_loss_mixed(
    coords_pred_dense: torch.Tensor,
    coords_true_flat: torch.Tensor,
    idx_dense: torch.Tensor,
    idx_global: torch.Tensor,
) -> torch.Tensor:
    """Planar loss where pred and target live in different index spaces."""
    sin_pred, _ = torsion_sin_cos(coords_pred_dense, idx_dense)
    sin_true, _ = torsion_sin_cos(coords_true_flat, idx_global)
    return F.smooth_l1_loss(sin_pred, sin_true)


def batch_rmsd(pred, true, mask, *, sample_ratio: float = 1.0):
    """Return accumulated RMSD and sampled count for weighted averaging."""
    rmsd_sum = 0.0
    n_sample = 0
    batch_size = pred.size(0)
    rand = torch.rand(batch_size, device=pred.device)

    for b in range(batch_size):
        if sample_ratio < 1.0 and rand[b] > sample_ratio:
            continue
        valid = mask[b] > 0
        if valid.sum() < 3:
            continue

        rmsd_val = _rmsd_pair(pred[b, valid], true[b, valid])
        rmsd_sum += rmsd_val.item()
        n_sample += 1

    return rmsd_sum, n_sample


def morse_energy(d_pred, d_true, d_coef: float = 1.0, a_coef: float = 1.0, clip: float = 20.0):
    diff = (d_pred - d_true).clamp(-clip, clip)
    return d_coef * (1 - safe_exp(-a_coef * diff / (d_true + 1e-4))) ** 2
