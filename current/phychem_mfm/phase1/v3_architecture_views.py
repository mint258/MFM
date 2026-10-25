"""Opt-in C3 two-view bridge retaining original clean/both S objectives."""
from __future__ import annotations

from copy import copy
from dataclasses import replace

import torch
from torch_geometric.data import Batch

from ..model.v3_multiview import V3MultiViewModel
from ..supervision import SupervisionConfig
from ..training.degrade_molecules import DegradeConfig, degrade_once
from .objectives import Phase1JointSchedule, Phase1LossPolicy, compute_phase1_loss
from .v3_contract import require, selected_groups
from .v3_losses import compute_v3_loss
from .v3_structural import (ROLES, RAW_NAMES, StructuralViews, StructuralViewConfig,
                           _masked_for_role, build_structural_views, combine_structural_loss)


def combined_degrade_config(config: StructuralViewConfig):
    """Retain separate topology strength and geometry sigma in the both view."""
    topology, geometry = config.degrade_config("topo"), config.degrade_config("geom")
    return DegradeConfig(mode="both", level=config.geometry_level, atom_encoding="zero_based",
        topo_replace_frac=topology.topo_replace_frac, topo_delete_frac=0.,
        geom_noise_std=geometry.geom_noise_std, geom_angle_std_deg=0.,
        geom_bond_scale_std=0., geom_radius=geometry.geom_radius).finalize()


def build_two_structural_views(clean_batch, *, ordinals, config=StructuralViewConfig(),
                               include_structural=True, graph_eligibility=None):
    """Keep native atoms, actual-change mask, and clean targets; never alter labels."""
    # Reuse the validated clean-only bridge, then add exactly one both view.
    clean = build_structural_views(clean_batch, ordinals=ordinals, config=config,
        include_structural=False, graph_eligibility=graph_eligibility)
    require(type(include_structural) is bool, "Explicit structural view switch required")
    if not include_structural:
        return clean
    result, clean_atoms, clean_graphs, graph_map, atom_map = [], [], [], [], []
    base_offset = expanded_offset = 0
    for graph, (record, ordinal) in enumerate(zip(clean.batch.to_data_list(), clean.ordinals)):
        before_x, before_pos = record.x.clone(), record.pos.clone()
        generator = torch.Generator(device="cpu").manual_seed(config.noise_seed(ordinal))
        both = degrade_once(record.clone(), combined_degrade_config(config), generator)
        both.target_x, both.target_pos = before_x.clone(), before_pos.clone()
        both.sample_type_id = torch.tensor([3], dtype=torch.long)
        require(len(both.x) == len(record.x) and torch.equal(
            both.element_corrupt_mask.view(-1).bool(), both.x.ne(before_x).any(-1)),
            "Both view must retain native order and the actual element-change mask")
        clean_atoms.append(torch.arange(expanded_offset, expanded_offset + len(record.x)))
        clean_graphs.append(len(result))
        for view in (record, both):
            result.append(view)
            graph_map.append(graph)
            atom_map.append(torch.arange(base_offset, base_offset + len(record.x)))
            expanded_offset += len(record.x)
        base_offset += len(record.x)
    return StructuralViews(Batch.from_data_list(result), torch.cat(clean_atoms), torch.tensor(clean_graphs),
        torch.tensor(graph_map), torch.cat(atom_map), clean.graph_eligibility, clean.ordinals, config, True)


def two_view_structural_raw_losses(outputs, views, registry, binding, weights, *, exposure_step=0,
                                   enabled_fields=None, atom_eligibility=None, bond_pair_eligibility=None):
    require(views.includes_structural and views.batch.sample_type_id.reshape(-1).tolist()
            == [value for _ in views.ordinals for value in (0, 3)], "C3 requires clean/both physical view pairs")
    require(weights.geom_angle_std_deg == weights.geom_bond_scale_std == 0,
            "A4 eps loss requires additive Gaussian noise")
    sigma = combined_degrade_config(views.config).geom_noise_std
    require(weights.denoise_sigma == sigma == registry.by_name()[binding.noise].denoise_sigma,
            "Both-view sigma, registry and original S loss differ")
    masks = dict(atom_eligibility or {})
    require(set(masks) <= set(ROLES), "Unknown structural atom-mask role")
    selected = {field.name for field in registry.enabled(("S",), enabled_fields)}
    raw, counts = {}, {}
    policy = Phase1LossPolicy.from_mapping({"geometry_task": "denoise_eps_mse"})
    for role in ROLES:
        field, name = binding.field_name(role), RAW_NAMES[role]
        if field not in selected:
            continue
        # The legacy role-mask helper selects a single view id. Give only that
        # mask helper a metadata copy; source loss still sees the real id3 both
        # view, which its existing geom/topo predicates explicitly support.
        masked = masked_two_view_outputs(outputs, views, role, atom_eligibility=masks.get(role),
                                          bond_pair_eligibility=bond_pair_eligibility)
        source = compute_phase1_loss(masked, views.batch, None, SupervisionConfig.from_variant("S"),
            weights, Phase1JointSchedule(), exposure_step, policy=policy)
        raw[field], counts[field] = source.raw[name], int(source.counts[name])
    return raw, counts


def masked_two_view_outputs(outputs, views, role, *, atom_eligibility=None, bond_pair_eligibility=None):
    """Use the same independent role mask for both source loss and metrics."""
    require(role in ROLES, "Unknown structural role")
    mask_batch = copy(views.batch)
    if role != "bond":
        mask_batch.sample_type_id = torch.where(mask_batch.sample_type_id.eq(3),
            mask_batch.sample_type_id.new_tensor(2 if role == "element" else 1), mask_batch.sample_type_id)
    return _masked_for_role(outputs, replace(views, batch=mask_batch), role,
        atom_eligibility=atom_eligibility, bond_pair_eligibility=bond_pair_eligibility)


class V3TwoViewModel(V3MultiViewModel):
    """Same single encoder pass and clean-only PD; explicit C3 loss adapter."""
    def forward_pretrain(self, views, *, enabled_groups, enabled_fields=None,
                         pair_indices=None, prediction_offsets=None):
        if views.includes_structural:
            require(views.batch.sample_type_id.reshape(-1).tolist()
                    == [value for _ in views.ordinals for value in (0, 3)],
                    "C3 requires clean/both physical view pairs")
        return super().forward_pretrain(views, enabled_groups=enabled_groups, enabled_fields=enabled_fields,
            pair_indices=pair_indices, prediction_offsets=prediction_offsets)

    def compute_loss(self, prediction, views, pd_targets, normalizations, *, enabled_groups, weights,
                     enabled_fields=None, atom_eligibility=None, bond_pair_eligibility=None, exposure_step=0):
        groups = selected_groups(enabled_groups)
        field_names = tuple(field.name for field in self.registry.enabled(groups, enabled_fields))
        require(prediction.structural_active == ("S" in groups), "Forward/loss structural switches differ")
        require(prediction.enabled_groups == groups and prediction.enabled_fields == field_names,
                "Forward/loss group or field switches differ")
        pd_loss = compute_v3_loss(prediction.pd_predictions, pd_targets, self.registry, normalizations,
            enabled_groups=tuple(group for group in groups if group != "S"), enabled_fields=field_names,
            device=prediction.source_outputs.atom_repr.device)
        if "S" not in groups:
            return pd_loss
        raw, counts = two_view_structural_raw_losses(prediction.source_outputs, views, self.registry,
            self.structural_binding, weights, exposure_step=exposure_step, enabled_fields=field_names,
            atom_eligibility=atom_eligibility, bond_pair_eligibility=bond_pair_eligibility)
        return combine_structural_loss(pd_loss, raw, counts, enabled_groups=groups)
