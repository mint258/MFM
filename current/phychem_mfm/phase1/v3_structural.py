"""Three-view S bridge retaining the existing S heads and single-task losses."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, replace
import hashlib

import torch
from torch import Tensor
from torch_geometric.data import Batch
from torch_geometric.utils import to_dense_batch

from ..supervision import SupervisionConfig
from ..training.degrade_molecules import DegradeConfig, degrade_once
from .objectives import Phase1JointSchedule, Phase1LossPolicy, compute_phase1_loss
from .v3_contract import LabelRegistry, require
from .v3_losses import V3LossResult

ROLES = ("element", "noise", "bond")
RAW_NAMES = {"element": "element", "noise": "denoise_eps_mse", "bond": "bond_order"}


@dataclass(frozen=True)
class StructuralFieldBinding:
    """Explicit model configuration; never infer roles from a D-1 field name."""
    element: str
    noise: str
    bond: str

    def validate(self, registry: LabelRegistry, *, element_classes=119):
        names = (self.element, self.noise, self.bond)
        require(len(set(names)) == 3 and all(name in registry.by_name() for name in names),
                "Exactly three distinct explicit structural fields required")
        fields = registry.by_name()
        require({field.name for field in registry.fields if field.group == "S"} == set(names),
                "Every S registry field must have an explicit canonical structural binding")
        require(fields[self.element].level == "atom" and fields[self.element].kind == "classification"
                and fields[self.element].classes == element_classes, "Element binding must match the original logits including reserved padding class")
        require(fields[self.noise].level == "atom" and fields[self.noise].kind == "denoise_eps_mse"
                and fields[self.noise].representation == "vector", "Noise binding requires A4 eps loss")
        require(fields[self.bond].level == "pair" and fields[self.bond].kind == "classification"
                and fields[self.bond].classes == 5, "Bond binding requires original positive-only five-class CE")

    def field_name(self, role):
        require(role in ROLES, "Unknown structural role")
        return getattr(self, role)


@dataclass(frozen=True)
class StructuralViewConfig:
    seed: int = 0
    epoch: int = 0
    topology_level: float = .3
    geometry_level: float = .2
    noise_seed_includes_epoch: bool = True

    def __post_init__(self):
        require(type(self.seed) is int and self.seed >= 0 and type(self.epoch) is int and self.epoch >= 0,
                "Nonnegative view seed/epoch required")
        require(type(self.noise_seed_includes_epoch) is bool, "Explicit epoch noise policy required")

    def noise_seed(self, ordinal):
        require(type(ordinal) is int and ordinal >= 0, "Explicit consumed sample ordinal required")
        if not self.noise_seed_includes_epoch:
            return self.seed + ordinal
        payload = f"{self.seed}:{ordinal}:{self.epoch}".encode("ascii")
        return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "little") & ((1 << 63) - 1)

    def degrade_config(self, mode):
        return DegradeConfig(mode=mode, level=float(self.geometry_level if mode == "geom" else self.topology_level),
                             atom_encoding="zero_based", topo_delete_frac=0., geom_angle_std_deg=0.,
                             geom_bond_scale_std=0.).finalize()


@dataclass(frozen=True)
class StructuralViews:
    batch: Batch
    clean_atom_rows: Tensor
    clean_graph_rows: Tensor
    base_graph_index: Tensor
    base_atom_index: Tensor
    graph_eligibility: dict[str, Tensor]
    ordinals: tuple[int, ...]
    config: StructuralViewConfig
    includes_structural: bool

    def to(self, device, *, non_blocking=False):
        return StructuralViews(copy(self.batch).to(device, non_blocking=non_blocking),
            self.clean_atom_rows.to(device, non_blocking=non_blocking),
            self.clean_graph_rows.to(device, non_blocking=non_blocking),
            self.base_graph_index.to(device, non_blocking=non_blocking),
            self.base_atom_index.to(device, non_blocking=non_blocking),
            {key: value.to(device, non_blocking=non_blocking) for key, value in self.graph_eligibility.items()},
            self.ordinals, self.config, self.includes_structural)


def eligibility_from_choices(choices, registry, binding: StructuralFieldBinding, *, enabled_fields=None):
    names = None if enabled_fields is None else set(enabled_fields)
    fields = registry.by_name()
    result = {}
    for role in ROLES:
        name = binding.field_name(role)
        flags = []
        for choice in choices:
            groups, families = dict(choice.group_mask), dict(choice.family_mask)
            require(fields[name].family in families, "Explicit structural family mask required")
            flags.append(groups["S"] and families[fields[name].family] and (names is None or name in names))
        result[role] = torch.tensor(flags, dtype=torch.bool)
    return result


def build_structural_views(clean_batch: Batch, *, ordinals, config=StructuralViewConfig(),
                           include_structural=True, graph_eligibility=None) -> StructuralViews:
    """Original transport fields are copied; no label conversions or QM occur."""
    require(isinstance(clean_batch, Batch) and clean_batch.x.device.type == clean_batch.pos.device.type == "cpu",
            "Build deterministic views from an already decoded CPU clean Batch")
    records, ordinals = clean_batch.to_data_list(), tuple(ordinals)
    require(len(records) == len(ordinals) and len(set(ordinals)) == len(ordinals), "One unique sample ordinal per base molecule draw required")
    require(type(include_structural) is bool, "Explicit structural view switch required")
    supplied = graph_eligibility or {role: torch.ones(len(records), dtype=torch.bool) for role in ROLES}
    require(set(supplied) == set(ROLES), "Each structural role needs its own graph eligibility")
    eligibility = {}
    for role, value in supplied.items():
        require(isinstance(value, Tensor) and value.dtype == torch.bool and value.shape == (len(records),)
                and value.device.type == "cpu", "Boolean base-molecule eligibility required")
        eligibility[role] = value.clone()
    output, clean_rows, clean_graphs, graph_map, atom_map = [], [], [], [], []
    expanded_offset = base_offset = 0
    modes = ("clean", "geom", "topo") if include_structural else ("clean",)
    for i, (record, ordinal) in enumerate(zip(records, ordinals)):
        require(record.x.dtype == torch.long and record.x.ndim == 2 and record.x.size(1) == 1
                and bool(((record.x >= 0) & (record.x < 118)).all())
                and record.pos.dtype == torch.float32 and record.pos.shape == (len(record.x), 3)
                and bool(torch.isfinite(record.pos).all()), "Native atom order/fp32 source geometry required")
        x, pos = record.x.clone(), record.pos.clone()
        for view_id, mode in enumerate(modes):
            generator = torch.Generator(device="cpu").manual_seed(config.noise_seed(ordinal))
            view = degrade_once(record.clone(), config.degrade_config(mode), generator)
            require(len(view.x) == len(x), "Structural views must not delete native atoms")
            view.target_x, view.target_pos = x.clone(), pos.clone()
            view.sample_type_id = torch.tensor([view_id], dtype=torch.long)
            require(torch.equal(view.x.ne(x).any(dim=1), view.element_corrupt_mask.view(-1).bool()),
                    "Actual element-corruption facts must be preserved")
            if mode == "clean":
                clean_rows.append(torch.arange(expanded_offset, expanded_offset + len(x)))
                clean_graphs.append(len(output))
            output.append(view)
            graph_map.append(i)
            atom_map.append(torch.arange(base_offset, base_offset + len(x)))
            expanded_offset += len(x)
        base_offset += len(x)
    return StructuralViews(Batch.from_data_list(output), torch.cat(clean_rows), torch.tensor(clean_graphs),
                           torch.tensor(graph_map), torch.cat(atom_map), eligibility, ordinals, config, include_structural)


def _masked_for_role(outputs, views, role, *, atom_eligibility=None, bond_pair_eligibility=None):
    device = outputs.atom_repr.device
    graph_keep = views.graph_eligibility[role].to(device)
    node = outputs.node_mask.clone()
    source_types = views.batch.sample_type_id.reshape(-1)
    view_id = {"element": 2, "noise": 1, "bond": 0}[role]
    if role != "bond":
        selected = source_types.eq(view_id)
        node[selected] &= graph_keep[views.base_graph_index[selected]][:, None, None]
        if atom_eligibility is not None:
            require(atom_eligibility.dtype == torch.bool and atom_eligibility.ndim == 1
                    and len(atom_eligibility) == len(views.clean_atom_rows), "Base-atom field eligibility differs")
            flat = atom_eligibility.to(device)[views.base_atom_index]
            dense, _ = to_dense_batch(flat, views.batch.batch, fill_value=False)
            node[selected] &= dense[selected].unsqueeze(-1)
        return replace(outputs, node_mask=node)
    bond = outputs.bond
    require(bond is not None, "Original S bond outputs required")
    keep = graph_keep[views.base_graph_index[bond.pair_graph_index]]
    if atom_eligibility is not None:
        require(atom_eligibility.dtype == torch.bool and atom_eligibility.shape == (len(views.clean_atom_rows),),
                "Base-atom field eligibility differs")
        atoms = atom_eligibility.to(device)[views.base_atom_index]
        keep &= atoms[bond.pair_index[0]] & atoms[bond.pair_index[1]]
    if bond_pair_eligibility is not None:
        require(bond_pair_eligibility.dtype == torch.bool and bond_pair_eligibility.shape == keep.shape,
                "Explicit original-output pair eligibility differs")
        keep &= bond_pair_eligibility.to(device)
    filtered = replace(bond, existence=bond.existence[keep], order=bond.order[keep], pair_index=bond.pair_index[:, keep],
                       pair_graph_index=bond.pair_graph_index[keep], existence_target=bond.existence_target[keep],
                       order_target=bond.order_target[keep], sampled_pair_count=int(keep.sum()),
                       positive_pair_count=int(keep.sum()), valid_graph_count=len(bond.pair_graph_index[keep].unique()))
    return replace(outputs, bond=filtered)


def structural_raw_losses(outputs, views: StructuralViews, registry, binding, weights, *, exposure_step=0,
                          enabled_fields=None, atom_eligibility=None, bond_pair_eligibility=None):
    require(views.includes_structural, "Structural supervision needs three views")
    require(weights.geom_angle_std_deg == 0 and weights.geom_bond_scale_std == 0,
            "A4 eps loss requires additive Gaussian noise")
    sigma = views.config.degrade_config("geom").geom_noise_std
    require(weights.denoise_sigma == sigma == registry.by_name()[binding.noise].denoise_sigma,
            "View, registry and original S loss sigma differ")
    masks = dict(atom_eligibility or {})
    require(set(masks) <= set(ROLES), "Unknown structural atom-mask role")
    # Validate names before filtering them by the enabled S role.
    selected = {field.name for field in registry.enabled(("S",), enabled_fields)}
    policy = Phase1LossPolicy.from_mapping({"geometry_task": "denoise_eps_mse"})
    def calculate(value):
        return compute_phase1_loss(value, views.batch, None, SupervisionConfig.from_variant("S"),
                                    weights, Phase1JointSchedule(), exposure_step, policy=policy)
    default = not masks and bond_pair_eligibility is None and all(bool(value.all()) for value in views.graph_eligibility.values())
    common = calculate(outputs) if default else None
    raw, counts = {}, {}
    for role in ROLES:
        field, name = binding.field_name(role), RAW_NAMES[role]
        if field not in selected:
            continue
        value = common if common is not None else calculate(_masked_for_role(
            outputs, views, role, atom_eligibility=masks.get(role), bond_pair_eligibility=bond_pair_eligibility))
        raw[field], counts[field] = value.raw[name], int(value.counts[name])
    return raw, counts


def combine_structural_loss(pd_loss: V3LossResult, raw, counts, *, enabled_groups) -> V3LossResult:
    groups = tuple(group for group in ("S", "D", "P") if group in enabled_groups)
    field_losses, field_counts = dict(pd_loss.fields), dict(pd_loss.counts)
    group_losses, observed = dict(pd_loss.groups), dict(pd_loss.observed_fields)
    if "S" in groups:
        require(set(raw) == set(counts), "Structural raw/count mappings differ")
        field_losses.update(raw); field_counts.update(counts)
        valid = [raw[name] for name, count in counts.items() if count > 0]
        group_losses["S"] = torch.stack(valid).mean() if valid else pd_loss.total.new_zeros(())
        observed["S"] = len(valid)
    total = torch.stack([group_losses[group] for group in groups]).mean() if groups else pd_loss.total.new_zeros(())
    result = V3LossResult(total, field_losses, group_losses, field_counts, observed, groups, pd_loss.audit_counts)
    if pd_loss.has_loss_readiness:
        loss_counts, statuses = dict(pd_loss.loss_counts), dict(pd_loss.loss_status)
        if "S" in groups:
            loss_counts.update(counts)
            statuses.update({name: "READY" if count else "NO_VALID_LABELS" for name, count in counts.items()})
        physical, scale = dict(pd_loss.physical_status), dict(pd_loss.scale_status)
        if pd_loss.physical_policy_sha256 is not None and "S" in groups:
            physical.update({name: "NOT_TARGETED_BY_BOUND_PHYSICAL_POLICY" for name in counts})
            scale.update({name: "NOT_APPLICABLE_STRUCTURAL" for name in counts})
        return result.with_loss_readiness(loss_counts, statuses, pd_loss.loss_reasons,
            physical_status=physical, scale_status=scale, scale_reasons=pd_loss.scale_reasons,
            policy_sha256=pd_loss.physical_policy_sha256)
    return result
