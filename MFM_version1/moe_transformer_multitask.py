# ================= moe_transformer_multitask.py =================
"""
MultiTask MoE model (Energy/Charge/Element/Geometry).

Structural refactor goals (minimal-break on *outputs*):
- Remove EGNN + ComENetAutoEncoder dependency.
- Remove KL/VAE path (LatentBottleneck, kl_loss, return_latent, etc.).
- Remove TS (time-series) mode entirely.
- Introduce a real-coordinate Transformer backbone.
- Split the old ETBlock into two *parallel* implementations:
    * ETBlockReal: uses real coordinates `pos` as read-only geometric context (no pos updates)
    * ETBlockInternal: uses internal coordinate state `r` and can update it (no access to real `pos`)
- Keep the main MultiTaskMoE output interface unchanged:
    coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, bal

Notes on real/internal boundary (enforced by design):
- ETBlockReal.forward(x, pos, batch) -> x_out
- ETBlockInternal.forward(x, r, batch) -> (x_out, r_out)
- ETExpert contains two independent ModuleLists:
    real_layers (ETBlockReal) and int_layers (ETBlockInternal).
  Forward may execute real then internal (mixed), but blocks NEVER read each other's coordinates/state.
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch_geometric.data import Batch, Data
from torch_geometric.nn import global_mean_pool
from torch_geometric.utils import to_dense_batch


# ----------------------------- utils -----------------------------

def ensure_batch_attr(data: Data) -> Tensor:
    """Return a 1D `batch` vector for node->graph assignment."""
    if isinstance(data, Batch):
        return data.batch
    if getattr(data, "batch", None) is None:
        return torch.zeros(data.num_nodes, dtype=torch.long, device=data.x.device)
    return data.batch


def _init_linear(w: Tensor, b: Optional[Tensor] = None, initializer: str = "xavier_uniform") -> None:
    """Self-contained init (previously came from EGNN.initialize_weights)."""
    if initializer in {"glorot", "xavier_uniform"}:
        nn.init.xavier_uniform_(w)
    elif initializer == "xavier_normal":
        nn.init.xavier_normal_(w)
    elif initializer == "kaiming_uniform":
        nn.init.kaiming_uniform_(w, a=math.sqrt(5))
    else:
        nn.init.xavier_uniform_(w)
    if b is not None:
        nn.init.zeros_(b)


# ----------------------------- basic MLP -----------------------------

class Linear(nn.Linear):
    """nn.Linear with explicit, self-contained initialization."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        bias: bool = True,
        weight_initializer: str = "xavier_uniform",
    ) -> None:
        self.weight_initializer = weight_initializer
        super().__init__(in_channels, out_channels, bias=bias)

    def reset_parameters(self) -> None:  # noqa: D401
        _init_linear(self.weight, self.bias, initializer=self.weight_initializer)


class MLP(nn.Module):
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int,
        out_dim: int,
        num_layers: int = 3,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        assert num_layers >= 1
        layers: list[nn.Module] = []
        if num_layers == 1:
            layers.append(Linear(in_dim, out_dim))
        else:
            layers.append(Linear(in_dim, hidden_dim))
            layers.append(nn.SiLU())
            for _ in range(num_layers - 2):
                layers.append(Linear(hidden_dim, hidden_dim))
                layers.append(nn.SiLU())
                if dropout > 0:
                    layers.append(nn.Dropout(dropout))
            layers.append(Linear(hidden_dim, out_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: Tensor) -> Tensor:
        return self.net(x)


# ---------------------- coordinate / task decoders ----------------------

class CoordinateDecoder(nn.Module):
    def __init__(self, atom_embedding_dim: int, hidden_dim: int, output_dim: int = 3) -> None:
        super().__init__()
        self.shared_decoder = nn.Sequential(
            Linear(atom_embedding_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )
        self.coord_head = Linear(hidden_dim, output_dim)

    def forward(self, atom_embeddings: Tensor) -> Tensor:
        h = self.shared_decoder(atom_embeddings)
        return self.coord_head(h)


# -------------------------- dense attention core --------------------------

class DenseGeoSelfAttention(nn.Module):
    """Self-attention on dense sequences with (optional) distance bias and radius mask.

    Inputs:
      x:   (B, N, D)
      pos: (B, N, 3)  (real coords or internal coords)
      mask:(B, N)     True for valid nodes, False for padding

    Returns:
      out:  (B, N, D)
      attn: (B, H, N, N) attention weights (after softmax)
    """

    def __init__(
        self,
        dim: int,
        nheads: int,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
    ) -> None:
        super().__init__()
        assert dim % nheads == 0, "dim must be divisible by nheads"
        self.dim = dim
        self.nheads = nheads
        self.d_head = dim // nheads
        self.dropout = dropout

        self.qkv = Linear(dim, 3 * dim)
        self.proj = Linear(dim, dim)

        self.use_dist_bias = use_dist_bias
        self.use_radius_mask = use_radius_mask
        self.radius = float(radius)

        if use_dist_bias:
            # bias per head: (dist2)->(H)
            self.dist_mlp = nn.Sequential(
                Linear(1, dim),
                nn.SiLU(),
                Linear(dim, nheads),
            )
        else:
            self.dist_mlp = None

        self.attn_drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: Tensor, pos: Tensor, mask: Tensor) -> Tuple[Tensor, Tensor]:
        bsz, seqlen, _ = x.shape
        qkv = self.qkv(x).view(bsz, seqlen, 3, self.nheads, self.d_head)
        q, k, v = qkv.unbind(dim=2)  # (B, N, H, Dh)

        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        logits = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_head)

        diff = pos[:, :, None, :] - pos[:, None, :, :]
        dist2 = (diff * diff).sum(dim=-1)

        if self.use_dist_bias and self.dist_mlp is not None:
            bias = self.dist_mlp(dist2.unsqueeze(-1))  # (B, N, N, H)
            bias = bias.permute(0, 3, 1, 2).contiguous()
            logits = logits + bias

        key_invalid = ~mask
        logits = logits.masked_fill(key_invalid[:, None, None, :], -1e9)

        if self.use_radius_mask:
            rad2 = self.radius * self.radius
            logits = logits.masked_fill(dist2[:, None, :, :] > rad2, -1e9)

        attn = torch.softmax(logits, dim=-1)
        attn = self.attn_drop(attn)

        ctx = torch.matmul(attn, v)
        ctx = ctx.transpose(1, 2).contiguous().view(bsz, seqlen, self.dim)

        out = self.proj(ctx)
        out = out * mask.unsqueeze(-1).to(out.dtype)
        return out, attn


class DenseFFN(nn.Module):
    def __init__(self, dim: int, ff_mult: int, dropout: float = 0.0) -> None:
        super().__init__()
        hidden = int(dim * ff_mult)
        self.net = nn.Sequential(
            Linear(dim, hidden),
            nn.SiLU(),
            nn.Dropout(dropout) if dropout > 0 else nn.Identity(),
            Linear(hidden, dim),
        )

    def forward(self, x: Tensor) -> Tensor:
        return self.net(x)


# -------------------------- backbone (real coords) --------------------------

class RealCoordTransformerLayer(nn.Module):
    def __init__(
        self,
        dim: int,
        nheads: int,
        ff_mult: int,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
    ) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = DenseGeoSelfAttention(
            dim=dim,
            nheads=nheads,
            dropout=dropout,
            use_dist_bias=use_dist_bias,
            use_radius_mask=use_radius_mask,
            radius=radius,
        )
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = DenseFFN(dim=dim, ff_mult=ff_mult, dropout=dropout)

    def forward(self, x: Tensor, pos: Tensor, mask: Tensor) -> Tensor:
        a, _ = self.attn(self.norm1(x), pos, mask)
        x = x + a
        x = x + self.ffn(self.norm2(x))
        x = x * mask.unsqueeze(-1).to(x.dtype)
        return x


class RealCoordTransformerBackbone(nn.Module):
    """Node-level backbone that conditions on real 3D coordinates (no graph construction)."""

    def __init__(
        self,
        n_atom_types: int,
        dim: int,
        layers: int = 6,
        heads: int = 8,
        ff_mult: int = 4,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
    ) -> None:
        super().__init__()
        self.n_atom_types = int(n_atom_types)
        self.dim = int(dim)

        self.atom_emb = nn.Embedding(self.n_atom_types, self.dim)

        self.layers = nn.ModuleList(
            [
                RealCoordTransformerLayer(
                    dim=self.dim,
                    nheads=heads,
                    ff_mult=ff_mult,
                    dropout=dropout,
                    use_dist_bias=use_dist_bias,
                    use_radius_mask=use_radius_mask,
                    radius=radius,
                )
                for _ in range(layers)
            ]
        )
        self.out_norm = nn.LayerNorm(self.dim)

    def forward(self, data: Data) -> Tensor:
        if getattr(data, "pos", None) is None:
            raise ValueError("RealCoordTransformerBackbone requires data.pos (real coordinates).")
        batch = ensure_batch_attr(data)

        x_raw = data.x
        if x_raw.dim() == 2:
            x_raw = x_raw[:, 0]
        x_idx = x_raw.long().clamp(min=0, max=self.n_atom_types - 1)

        x = self.atom_emb(x_idx)
        x_dense, mask = to_dense_batch(x, batch, fill_value=0.0)
        pos_dense, _ = to_dense_batch(data.pos.to(torch.float32), batch, fill_value=0.0)

        for layer in self.layers:
            x_dense = layer(x_dense, pos_dense, mask)

        x_dense = self.out_norm(x_dense) * mask.unsqueeze(-1).to(x_dense.dtype)
        return x_dense[mask]


# -------------------------- experts (real/internal blocks) --------------------------

class ETBlockReal(nn.Module):
    """Expert block using real coordinates as read-only context (no coord updates)."""

    def __init__(
        self,
        dim: int,
        nheads: int = 4,
        ff_mult: int = 2,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
    ) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = DenseGeoSelfAttention(
            dim=dim,
            nheads=nheads,
            dropout=dropout,
            use_dist_bias=use_dist_bias,
            use_radius_mask=use_radius_mask,
            radius=radius,
        )
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = DenseFFN(dim=dim, ff_mult=ff_mult, dropout=dropout)

    def forward(self, x: Tensor, pos: Tensor, batch: Tensor) -> Tensor:
        x_dense, mask = to_dense_batch(x, batch, fill_value=0.0)
        pos_dense, _ = to_dense_batch(pos.to(torch.float32), batch, fill_value=0.0)

        a, _ = self.attn(self.norm1(x_dense), pos_dense, mask)
        x_dense = x_dense + a
        x_dense = x_dense + self.ffn(self.norm2(x_dense))
        x_dense = x_dense * mask.unsqueeze(-1).to(x_dense.dtype)
        return x_dense[mask]


class ETBlockInternal(nn.Module):
    """Expert block using *internal* coordinates r (and can update r)."""

    def __init__(
        self,
        dim: int,
        nheads: int = 4,
        ff_mult: int = 2,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
    ) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = DenseGeoSelfAttention(
            dim=dim,
            nheads=nheads,
            dropout=dropout,
            use_dist_bias=use_dist_bias,
            use_radius_mask=use_radius_mask,
            radius=radius,
        )
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = DenseFFN(dim=dim, ff_mult=ff_mult, dropout=dropout)
        self.coord_gate = nn.Sequential(Linear(dim, 1), nn.Sigmoid())

    def forward(self, x: Tensor, r: Tensor, batch: Tensor) -> Tuple[Tensor, Tensor]:
        x_dense, mask = to_dense_batch(x, batch, fill_value=0.0)
        r_dense, _ = to_dense_batch(r.to(torch.float32), batch, fill_value=0.0)

        a, attn = self.attn(self.norm1(x_dense), r_dense, mask)
        x_dense = x_dense + a
        x_dense = x_dense + self.ffn(self.norm2(x_dense))
        x_dense = x_dense * mask.unsqueeze(-1).to(x_dense.dtype)

        # internal coordinate update (NO access to real pos)
        attn_mean = attn.mean(dim=1)
        diff = r_dense[:, :, None, :] - r_dense[:, None, :, :]
        delta = (attn_mean.unsqueeze(-1) * diff).sum(dim=2)
        gate = self.coord_gate(x_dense)
        r_dense = (r_dense + gate * delta) * mask.unsqueeze(-1).to(r_dense.dtype)

        return x_dense[mask], r_dense[mask]


class ETExpert(nn.Module):
    """Unified expert framework with two independent paths (real/internal)."""

    def __init__(
        self,
        dim: int,
        real_layers: int,
        int_layers: int,
        nheads: int = 4,
        ff_mult: int = 2,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
    ) -> None:
        super().__init__()
        self.real_layers = nn.ModuleList(
            [
                ETBlockReal(dim, nheads=nheads, ff_mult=ff_mult, dropout=dropout,
                            use_dist_bias=use_dist_bias, use_radius_mask=use_radius_mask, radius=radius)
                for _ in range(int(real_layers))
            ]
        )
        self.int_layers = nn.ModuleList(
            [
                ETBlockInternal(dim, nheads=nheads, ff_mult=ff_mult, dropout=dropout,
                                use_dist_bias=use_dist_bias, use_radius_mask=use_radius_mask, radius=radius)
                for _ in range(int(int_layers))
            ]
        )

        # pos_mlp ONLY exists/used when int_layers>0
        self.pos_mlp: Optional[nn.Module]
        if len(self.int_layers) > 0:
            self.pos_mlp = nn.Sequential(Linear(dim, dim), nn.SiLU(), Linear(dim, 3))
        else:
            self.pos_mlp = None

        self.out_norm = nn.LayerNorm(dim)

    def forward(self, x: Tensor, *, batch: Tensor, pos: Optional[Tensor] = None) -> Tensor:
        # real path
        if len(self.real_layers) > 0:
            if pos is None:
                raise ValueError("ETExpert real_layers>0 requires `pos` (real coordinates).")
            for blk in self.real_layers:
                x = blk(x, pos, batch)

        # internal path
        if len(self.int_layers) > 0:
            if self.pos_mlp is None:
                raise RuntimeError("pos_mlp must exist when int_layers>0.")
            r = self.pos_mlp(x)
            for blk in self.int_layers:
                x, r = blk(x, r, batch)

        return self.out_norm(x)


def _resolve_task_layers(base_real: int, base_int: int, overrides: Optional[Dict[str, int]], key: str) -> int:
    if overrides is None:
        return base_real if key == "real" else base_int
    return int(overrides.get(key, base_real if key == "real" else base_int))


class MultiTaskMoE(nn.Module):
    """Multi-task MoE model.

    Output:
        coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, bal
    """

    def __init__(
        self,
        backbone_config: Dict,
        n_atom_types: int,
        n_experts_geom: int = 4,
        n_experts_energy: int = 2,
        n_experts_charge: int = 2,
        n_experts_elem: int = 1,
        top_k_geom: int = 1,
        top_k_energy: int = 1,
        top_k_charge: int = 1,
        top_k_elem: int = 1,
        expert_layers: int = 2,  # alias -> expert_real_layers
        expert_real_layers: Optional[int] = None,
        expert_int_layers: int = 0,
        expert_heads: int = 4,
        expert_ff_mult: int = 2,
        balance_weight: float = 1e-2,
    ) -> None:
        super().__init__()
        self.balance_weight = float(balance_weight)
        self.n_atom_types = int(n_atom_types)

        dim = int(backbone_config.get("atom_embedding_dim", backbone_config.get("hidden_channels", 512)))
        bb_layers = int(backbone_config.get("bb_layers", backbone_config.get("num_layers", 6)))
        bb_heads = int(backbone_config.get("bb_heads", 8))
        bb_ff_mult = int(backbone_config.get("bb_ff_mult", 4))
        bb_dropout = float(backbone_config.get("bb_dropout", 0.0))
        bb_use_dist_bias = bool(backbone_config.get("bb_use_dist_bias", True))
        bb_use_radius_mask = bool(backbone_config.get("bb_use_radius_mask", False))
        bb_radius = float(backbone_config.get("bb_radius", backbone_config.get("cutoff", 8.0)))

        self.backbone = RealCoordTransformerBackbone(
            n_atom_types=self.n_atom_types,
            dim=dim,
            layers=bb_layers,
            heads=bb_heads,
            ff_mult=bb_ff_mult,
            dropout=bb_dropout,
            use_dist_bias=bb_use_dist_bias,
            use_radius_mask=bb_use_radius_mask,
            radius=bb_radius,
        )
        self.latent_dim = dim

        real_layers = int(expert_layers if expert_real_layers is None else expert_real_layers)
        int_layers = int(expert_int_layers)

        overrides_energy = backbone_config.get("expert_layers_energy", None)
        overrides_charge = backbone_config.get("expert_layers_charge", None)
        overrides_elem = backbone_config.get("expert_layers_elem", None)
        overrides_geom = backbone_config.get("expert_layers_geom", None)

        self.experts_energy = nn.ModuleList(
            [ETExpert(dim, _resolve_task_layers(real_layers, int_layers, overrides_energy, "real"),
                      _resolve_task_layers(real_layers, int_layers, overrides_energy, "int"),
                      nheads=expert_heads, ff_mult=expert_ff_mult, radius=bb_radius)
             for _ in range(n_experts_energy)]
        )
        self.experts_charge = nn.ModuleList(
            [ETExpert(dim, _resolve_task_layers(real_layers, int_layers, overrides_charge, "real"),
                      _resolve_task_layers(real_layers, int_layers, overrides_charge, "int"),
                      nheads=expert_heads, ff_mult=expert_ff_mult, radius=bb_radius)
             for _ in range(n_experts_charge)]
        )
        self.experts_elem = nn.ModuleList(
            [ETExpert(dim, _resolve_task_layers(real_layers, int_layers, overrides_elem, "real"),
                      _resolve_task_layers(real_layers, int_layers, overrides_elem, "int"),
                      nheads=expert_heads, ff_mult=expert_ff_mult, radius=bb_radius)
             for _ in range(n_experts_elem)]
        )
        self.experts_geom = nn.ModuleList(
            [ETExpert(dim, _resolve_task_layers(real_layers, int_layers, overrides_geom, "real"),
                      _resolve_task_layers(real_layers, int_layers, overrides_geom, "int"),
                      nheads=expert_heads, ff_mult=expert_ff_mult, radius=bb_radius)
             for _ in range(n_experts_geom)]
        )

        self.gate_energy = Linear(dim, n_experts_energy)
        self.gate_charge = Linear(dim, n_experts_charge)
        self.gate_elem = Linear(dim, n_experts_elem)
        self.gate_geom = Linear(dim, n_experts_geom)

        self.top_k_energy = int(top_k_energy)
        self.top_k_charge = int(top_k_charge)
        self.top_k_elem = int(top_k_elem)
        self.top_k_geom = int(top_k_geom)

        self.coord_decoder = CoordinateDecoder(atom_embedding_dim=dim, hidden_dim=dim, output_dim=3)
        self.charge_head = Linear(dim, 1)
        self.elem_head = Linear(dim, n_atom_types)

        self.energy_pool = global_mean_pool
        self.energy_head = nn.Sequential(
            Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            Linear(dim, 1),
        )

    def _route(
        self,
        latent_base: Tensor,
        batch: Tensor,
        *,
        gate_layer: nn.Module,
        experts: nn.ModuleList,
        top_k: int,
        pos: Optional[Tensor],
    ) -> Tuple[Tensor, Tensor]:
        graph_repr = global_mean_pool(latent_base, batch)
        gate_logits = gate_layer(graph_repr)
        gate_probs = torch.softmax(gate_logits, dim=-1)

        top_k = min(int(top_k), gate_probs.size(1))
        topk_vals, topk_idx = torch.topk(gate_probs, k=top_k, dim=-1)
        sparse = torch.zeros_like(gate_probs).scatter_(1, topk_idx, topk_vals)
        gate_probs = sparse / (sparse.sum(dim=-1, keepdim=True) + 1e-9)

        gate_node = gate_probs[batch]
        out = torch.zeros_like(latent_base)

        for e, expert in enumerate(experts):
            if gate_probs[:, e].max() < 1e-6:
                continue
            emb_e = expert(latent_base, batch=batch, pos=pos)
            out = out + gate_node[:, e : e + 1] * emb_e

        me = gate_probs.mean(dim=0)
        ce = (gate_probs > 0).float().mean(dim=0)
        bal_loss = (me * ce).sum() * float(self.balance_weight)
        return out, bal_loss

    def forward(self, data: Data) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        batch = ensure_batch_attr(data)
        if getattr(data, "pos", None) is None:
            raise ValueError("MultiTaskMoE requires data.pos (real coordinates).")
        pos = data.pos

        latent0 = self.backbone(data)

        latent_E, bal_E = self._route(latent0, batch, gate_layer=self.gate_energy, experts=self.experts_energy, top_k=self.top_k_energy, pos=pos)
        latent_Q, bal_Q = self._route(latent0, batch, gate_layer=self.gate_charge, experts=self.experts_charge, top_k=self.top_k_charge, pos=pos)
        latent_Z, bal_Z = self._route(latent0, batch, gate_layer=self.gate_elem, experts=self.experts_elem, top_k=self.top_k_elem, pos=pos)
        latent_G, bal_G = self._route(latent0, batch, gate_layer=self.gate_geom, experts=self.experts_geom, top_k=self.top_k_geom, pos=pos)

        balance_loss = bal_E + bal_Q + bal_Z + bal_G

        coords_atom = self.coord_decoder(latent_G)
        coords_pred, mask = to_dense_batch(coords_atom, batch, fill_value=0.0)

        charge_atom = self.charge_head(latent_Q)
        charge_pred, _ = to_dense_batch(charge_atom, batch, fill_value=0.0)

        elem_atom = self.elem_head(latent_Z)
        elem_pred, _ = to_dense_batch(elem_atom, batch, fill_value=0.0)

        energy_node = self.energy_head(latent_E)
        energy_pred = self.energy_pool(energy_node, batch).unsqueeze(-1)

        cm = getattr(data, "charge_mask", None)
        if cm is not None and isinstance(cm, Tensor) and cm.dim() == 1 and cm.numel() == latent0.size(0):
            cm_dense, _ = to_dense_batch(cm.to(torch.float32).unsqueeze(-1), batch, fill_value=0.0)
            charge_mask = (cm_dense > 0.5) & mask.unsqueeze(-1)
        else:
            charge_mask = mask.unsqueeze(-1)

        return coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, balance_loss

    @torch.no_grad()
    def forward_from_latent(
        self,
        latent: Tensor,
        data_static: Data,
        *,
        node_mask: Optional[Tensor] = None,
        return_dense: bool = True,
        pos: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        batch = ensure_batch_attr(data_static)

        if latent.dim() == 3:
            if node_mask is None:
                raise ValueError("node_mask is required when latent is dense (B, N, D).")
            nm = node_mask.squeeze(-1) if node_mask.dim() == 3 else node_mask
            latent0 = latent[nm]
        else:
            latent0 = latent

        if pos is None and getattr(data_static, "pos", None) is not None:
            pos = data_static.pos

        if pos is not None and pos.dim() == 3:
            if node_mask is None:
                raise ValueError("node_mask is required when pos is dense (B, N, 3).")
            nm = node_mask.squeeze(-1) if node_mask.dim() == 3 else node_mask
            pos_flat = pos[nm]
        else:
            pos_flat = pos

        if pos_flat is None:
            expert_groups = {
                "energy": self.experts_energy,
                "charge": self.experts_charge,
                "elem": self.experts_elem,
                "geom": self.experts_geom,
            }
            for task_name, task_experts in expert_groups.items():
                if any(len(expert.real_layers) > 0 for expert in task_experts):
                    raise ValueError(
                        f"forward_from_latent(pos=None) requires expert_real_layers_{task_name}=0 for all experts."
                    )

        latent_E, bal_E = self._route(latent0, batch, gate_layer=self.gate_energy, experts=self.experts_energy, top_k=self.top_k_energy, pos=pos_flat)
        latent_Q, bal_Q = self._route(latent0, batch, gate_layer=self.gate_charge, experts=self.experts_charge, top_k=self.top_k_charge, pos=pos_flat)
        latent_Z, bal_Z = self._route(latent0, batch, gate_layer=self.gate_elem, experts=self.experts_elem, top_k=self.top_k_elem, pos=pos_flat)
        latent_G, bal_G = self._route(latent0, batch, gate_layer=self.gate_geom, experts=self.experts_geom, top_k=self.top_k_geom, pos=pos_flat)
        balance_loss = bal_E + bal_Q + bal_Z + bal_G

        coords_atom = self.coord_decoder(latent_G)
        charge_atom = self.charge_head(latent_Q)
        elem_atom = self.elem_head(latent_Z)
        energy_node = self.energy_head(latent_E)

        if not return_dense:
            ones = torch.ones(latent0.size(0), 1, device=latent0.device, dtype=torch.bool)
            return coords_atom, charge_atom, elem_atom, energy_node, ones, balance_loss

        coords_pred, mask = to_dense_batch(coords_atom, batch, fill_value=0.0)
        charge_pred, _ = to_dense_batch(charge_atom, batch, fill_value=0.0)
        elem_pred, _ = to_dense_batch(elem_atom, batch, fill_value=0.0)
        energy_pred = global_mean_pool(energy_node, batch).unsqueeze(-1)
        charge_mask = mask.unsqueeze(-1)
        return coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, balance_loss
