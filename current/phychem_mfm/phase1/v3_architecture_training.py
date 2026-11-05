"""Executable opt-in C1/C3 trainer extension over the unchanged v3 trainer."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import torch
from torch_geometric.utils import to_dense_batch

from .v3_architecture_views import V3TwoViewModel, masked_two_view_outputs
from .v3_contract import FieldTarget, canonical_hash, require
from .v3_trainer import V3StepTrainer, PreparedV3Batch


def architecture_training_sources():
    """Exact implementation bytes required to resume/evaluate this new schema."""
    package = Path(__file__).absolute().parents[1]
    names = ("phase1/v3_architecture_training.py", "phase1/v3_architecture_views.py",
             "phase1/v3_trainer.py", "phase1/v3_structural.py", "model/v3_architecture.py",
             "model/v3_multiview.py", "model/v3_heads.py", "model/shared.py", "model/backbone.py",
             "model/attention.py", "model/heads.py", "model/common.py")
    return {name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in names}


class ArchitectureStepTrainer(V3StepTrainer):
    """Reuse updates, clocks, probes, tracking, validation and immutable resume.

    The explicitly supplied provider must use the corresponding view builder.
    This class checks its physical layout before any encoder/optimizer work.
    """
    def __init__(self, model, *args, structural_views="three", **kwargs):
        require(structural_views in ("two", "three"), "Explicit two/three structural view policy required")
        require(isinstance(model, V3TwoViewModel) == (structural_views == "two"),
                "Two-view trainer/model policy must agree")
        self.structural_views = structural_views
        super().__init__(model, *args, **kwargs)
        self.physical_views_per_sample = (2 if structural_views == "two" else 3) if "S" in self.groups else 1
        options = getattr(model.encoder, "v3_architecture_options", None)
        self.contract["architecture_extension"] = {
            "schema": "model_v3_architecture_trainer_v1", "structural_views": structural_views,
            "physical_views_per_sample": self.physical_views_per_sample,
            "encoder_configuration": deepcopy(model.encoder.config_dict()),
            "encoder_architecture_options": deepcopy(options), "encoder_state_prefix": "encoder.",
            "model_class": type(model).__module__ + "." + type(model).__qualname__,
            "implementation_sources": architecture_training_sources(),
            "extension_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self.bindings["trainer_configuration_sha256"] = canonical_hash(self.contract)

    def _within_capacity(self, choices):
        maximum, atom_limit, cost_limit = self.batch_limits
        views = (2 if self.structural_views == "two" else 3) if "S" in self.groups else 1
        return (len(choices) <= maximum and sum(choice.native_atoms for choice in choices) <= atom_limit
                and views * len(choices) * max(choice.native_atoms for choice in choices) ** 2 <= cost_limit)

    def _prepared(self, batch, *, role, choices=None):
        # Reject mismatched physical expansion before a device copy/forward.
        require(isinstance(batch, PreparedV3Batch), "Prepared v3 batch required")
        types = (0, 3) if self.structural_views == "two" else (0, 1, 2)
        if "S" not in self.groups:
            types = (0,)
        require(batch.views.batch.sample_type_id.reshape(-1).tolist()
                == [value for _ in batch.choices for value in types], "Prepared physical view layout differs")
        counts = (batch.views.batch.ptr[1:] - batch.views.batch.ptr[:-1]).tolist()
        require(counts == [choice.native_atoms for choice in batch.choices for _ in types],
                "Prepared physical view atom counts differ")
        return super()._prepared(batch, role=role, choices=choices)

    def _tables(self, prediction, batch):
        if self.structural_views == "three" or "S" not in self.groups:
            return super()._tables(prediction, batch)
        predictions, targets = dict(prediction.pd_predictions), dict(batch.pd_targets)
        binding, views = self.model.structural_binding, batch.views
        for role in ("element", "noise", "bond"):
            name = binding.field_name(role)
            if name not in self.fields:
                continue
            masked = masked_two_view_outputs(prediction.source_outputs, views, role,
                atom_eligibility=batch.atom_eligibility.get(role), bond_pair_eligibility=batch.bond_pair_eligibility)
            if role == "bond":
                bond = masked.bond
                predictions[name] = bond.order
                targets[name] = FieldTarget(bond.order_target[:, None],
                    torch.ones(len(bond.order), device=self.device, dtype=torch.bool))
                continue
            types = views.batch.sample_type_id.reshape(-1)
            node = masked.node_mask.squeeze(-1).bool()
            if role == "element":
                labels, _ = to_dense_batch(views.batch.target_x, views.batch.batch)
                corrupt, _ = to_dense_batch(views.batch.element_corrupt_mask, views.batch.batch)
                logits = masked.element_logits
                valid = node & types.eq(3)[:, None] & corrupt.reshape(node.shape).bool()
                valid &= labels[..., 0].ge(0) & labels[..., 0].lt(logits.size(-1) - 1)
                predictions[name] = logits.reshape(-1, logits.size(-1))
                targets[name] = FieldTarget(labels.reshape(-1, 1).long(), valid.reshape(-1))
            else:
                noisy, _ = to_dense_batch(views.batch.pos, views.batch.batch)
                clean, _ = to_dense_batch(views.batch.target_pos, views.batch.batch)
                valid = node & types.eq(3)[:, None] & torch.isfinite(noisy).all(-1) & torch.isfinite(clean).all(-1)
                predictions[name] = masked.noise_pred.reshape(-1, 3)
                targets[name] = FieldTarget((noisy - clean).reshape(-1, 3), valid.reshape(-1))
        return predictions, targets
