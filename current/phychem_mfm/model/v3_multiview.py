"""Canonical opt-in S/PD v3 composition with one encoder pass per batch."""
from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor, nn
from torch_geometric.data import Data

from ..supervision import SupervisionConfig
from ..phase1.v3_contract import require, selected_groups
from ..phase1.v3_losses import compute_v3_loss
from ..phase1.v3_structural import combine_structural_loss, structural_raw_losses


@dataclass(frozen=True)
class MultiViewPredictions:
    source_outputs: object
    pd_predictions: dict[str, Tensor]
    clean_h0: Tensor
    structural_active: bool
    enabled_groups: tuple[str, ...]
    enabled_fields: tuple[str, ...]


class V3MultiViewModel(nn.Module):
    """Retain encoder.element_head/bond_head/geometry_head and shared H0 APIs."""
    def __init__(self, encoder, pd_heads, registry, structural_binding):
        super().__init__()
        require(getattr(encoder, "latent_dim", None) == 512, "V3 H0 must remain 512-dimensional")
        require(encoder.geometry_head_mode == "equivariant_noise" and encoder.head_profile == "phase1",
                "Canonical S path requires the original Phase1/A4 heads")
        structural_binding.validate(registry, element_classes=encoder.n_atom_types)
        pd_fields = tuple(field for field in registry.fields if field.group in ("P", "D"))
        require((pd_heads is None and not pd_fields) or (pd_heads is not None and pd_heads.dim == 512
                and pd_heads.registry.fields == pd_fields), "New head bank must contain exactly the P/D fields")
        self.encoder, self.pd_heads = encoder, pd_heads
        self.registry, self.structural_binding = registry, structural_binding
        self.latent_dim = 512

    def encode_atoms(self, batch: Data) -> Tensor:
        return self.encoder.encode_atoms(batch)

    def encode_graph(self, batch: Data, pooling: str = "mean") -> Tensor:
        return self.encoder.encode_graph(batch, pooling=pooling)

    def forward_pretrain(self, views, *, enabled_groups, enabled_fields=None,
                         pair_indices=None, prediction_offsets=None):
        groups = selected_groups(enabled_groups)
        active = self.registry.enabled(groups, enabled_fields)
        field_names = tuple(field.name for field in active)
        structural = "S" in groups
        require(views.includes_structural == structural, "PD-only uses one clean view; S uses three views")
        objectives = SupervisionConfig.from_variant("S").objectives if structural else ()
        outputs = self.encoder.forward_pretrain(views.batch, objectives)
        clean_h0 = outputs.atom_repr[views.clean_atom_rows]
        if self.pd_heads is None or not (set(groups) & {"P", "D"}):
            predictions = {}
        else:
            graph_index = views.batch.batch[views.clean_atom_rows]
            # The extracted rows retain native atom and base-molecule order.
            remap = graph_index.new_full((views.batch.num_graphs,), -1)
            remap[views.clean_graph_rows] = graph_index.new_tensor(range(len(views.clean_graph_rows)))
            pd_names = tuple(name for name in field_names if name in self.pd_heads.registry.by_name())
            predictions = self.pd_heads(clean_h0, remap[graph_index], views.batch.pos[views.clean_atom_rows],
                enabled_groups=tuple(group for group in groups if group != "S"), enabled_fields=pd_names,
                pair_indices=pair_indices, prediction_offsets=prediction_offsets)
        return MultiViewPredictions(outputs, predictions, clean_h0, structural, groups, field_names)

    def compute_loss(self, prediction, views, pd_targets, normalizations, *, enabled_groups, weights,
                     enabled_fields=None, atom_eligibility=None, bond_pair_eligibility=None, exposure_step=0):
        groups = selected_groups(enabled_groups)
        field_names = tuple(field.name for field in self.registry.enabled(groups, enabled_fields))
        require(prediction.structural_active == ("S" in groups), "Forward/loss structural switches differ")
        require(prediction.enabled_groups == groups and prediction.enabled_fields == field_names,
                "Forward/loss group or field switches differ")
        pd_groups = tuple(group for group in groups if group != "S")
        pd_loss = compute_v3_loss(prediction.pd_predictions, pd_targets, self.registry, normalizations,
                                  enabled_groups=pd_groups, enabled_fields=field_names,
                                  device=prediction.source_outputs.atom_repr.device)
        if "S" not in groups:
            return pd_loss
        raw, counts = structural_raw_losses(prediction.source_outputs, views, self.registry,
            self.structural_binding, weights, exposure_step=exposure_step, enabled_fields=field_names,
            atom_eligibility=atom_eligibility, bond_pair_eligibility=bond_pair_eligibility)
        return combine_structural_loss(pd_loss, raw, counts, enabled_groups=groups)
