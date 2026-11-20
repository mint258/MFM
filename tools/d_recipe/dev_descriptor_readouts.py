"""Opt-in section-5 B/C models over the unchanged native run_probe loop.

No training runs at import. Capacity policy and descriptor value source are
mandatory caller choices. The wrapper is process-local and must be used
serially within a process; it never edits the native module on disk.
"""
from contextlib import contextmanager
from collections.abc import Mapping
from dataclasses import dataclass, replace

import numpy as np
import torch
from torch import nn


@dataclass(frozen=True)
class H0Statistics:
    mean: torch.Tensor
    scale: torch.Tensor
    keep: torch.Tensor
    optimization_uids: tuple[str, ...]
    internal_uids: tuple[str, ...]


def composition_features(atomic_numbers):
    """Original graph Z1..118 counts plus heavy-atom count, without H inference.

    The caller supplies the complete original atom sequence including H, or an
    existing explicit atomic-number/count mapping. No graph construction,
    valence inference, geometry generation, label access or fitting occurs.
    """
    counts = np.zeros(118, dtype=np.int64)
    if isinstance(atomic_numbers, Mapping):
        for number, count in atomic_numbers.items():
            if (not isinstance(number, (int, np.integer)) or not 1 <= number <= 118
                    or not isinstance(count, (int, np.integer)) or count < 0):
                raise ValueError("Explicit source element counts require Z1..118 and nonnegative integers")
            counts[int(number) - 1] = int(count)
    else:
        numbers = np.asarray(atomic_numbers)
        if numbers.ndim != 1 or numbers.dtype.kind not in "iu" or (numbers < 1).any() or (numbers > 118).any():
            raise ValueError("Explicit source atomic numbers must be integers in 1..118")
        counts = np.bincount(numbers, minlength=119)[1:119].astype(np.int64, copy=False)
    return np.r_[counts, counts[1:].sum(dtype=np.int64)]


def optimization_h0_statistics(train, *, relative_std_floor, internal_epoch_selection):
    """Same label-independent optimization scope and H0 statistics as run_probe.

    The native loop has no exported helper for this scope. These few selection
    and statistic operations mirror its fixed protocol; the original loop still
    performs all batching, optimization, epoch selection and prediction.
    """
    train = tuple(train)
    held = set()
    if internal_epoch_selection:
        uids = sorted({row.molecule_uid for row in train})
        order = torch.randperm(len(uids), generator=torch.Generator().manual_seed(20261112)).tolist()
        held = {uids[index] for index in order[:max(1, (len(uids) + 9) // 10)]}
    optimization = tuple(row for row in train if row.molecule_uid not in held)
    if not optimization:
        raise ValueError("Native internal holdout leaves no optimization TRAIN molecules")
    atoms = torch.cat([row.h0.detach().double() for row in optimization])
    keep = torch.ones(atoms.shape[1], dtype=torch.bool, device=atoms.device)
    if relative_std_floor:
        std = atoms.std(0, unbiased=False)
        threshold = max(1e-12, 1e-4 * float(torch.quantile(std, .5)))
        keep = std >= threshold
    selected = atoms[:, keep]
    mean, scale = selected.mean(0), selected.std(0, unbiased=False)
    scale = torch.where(scale > 1e-12, scale, torch.ones_like(scale))
    return H0Statistics(mean, scale, keep,
                        tuple(sorted({row.molecule_uid for row in optimization})), tuple(sorted(held)))


def attach_descriptors(rows, batch, *, value_source, member_keys=None):
    """Attach raw values plus source-valid bits; padding happens only in model.

    `frozen_train_standardized` means the caller obtained batch.values with
    the descriptor consumer's published TRAIN-only affine transformation. This
    function never estimates parameters or normalizes on downstream rows.
    """
    rows = tuple(rows)
    if value_source not in ("raw", "frozen_train_standardized"):
        raise ValueError("Explicit raw or frozen_train_standardized descriptor value source required")
    if len(rows) != len(batch.molecule_ids):
        raise ValueError("Descriptor batch and native source rows differ")
    if all(uid is None for uid in batch.member_uids):
        if tuple(batch.molecule_ids) != tuple(row.molecule_uid for row in rows):
            raise ValueError("Explicit descriptor molecule IDs do not align with native rows")
    else:
        expected = tuple(member_keys) if member_keys is not None else tuple(
            row.source_member_uid or row.molecule_uid for row in rows)
        if tuple(batch.member_uids) != expected:
            raise ValueError("Descriptor member identities do not align with native rows")
    values = batch.raw_values if value_source == "raw" else batch.values
    valid = np.asarray(batch.observed_valid, dtype=bool)
    if np.shape(values) != (len(rows), len(batch.fields)) or np.shape(values) != valid.shape:
        raise ValueError("Descriptor value/mask/field layout differs")
    packed = np.concatenate((np.asarray(values, dtype=np.float64), valid.astype(np.float64)), axis=1)
    return tuple(replace(row, graph_features=torch.as_tensor(packed[index]).clone())
                 for index, row in enumerate(rows))


def trainable_parameters(model):
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


def capacity_plan(*, branch, capacity_policy, descriptor_fields, native_prototype):
    """Single analytical integer-width rounding, never model/validation search."""
    if branch not in ("B", "C") or capacity_policy not in ("total_params_matching", "hidden_width_256"):
        raise ValueError("Explicit B/C branch and approved capacity_policy required")
    if type(descriptor_fields) is not int or descriptor_fields < 1:
        raise ValueError("A nonempty frozen descriptor field list is required")
    target = trainable_parameters(native_prototype)
    fixed = trainable_parameters(native_prototype.atom) if branch == "C" else 0
    feature_width = 2 * descriptor_fields
    native_molecular_input = native_prototype.output[0].in_features
    molecular_input = feature_width + (native_molecular_input if branch == "C" else 0)
    coefficient, constant = molecular_input + 2, fixed + 1
    if capacity_policy == "hidden_width_256":
        hidden = 256
    else:
        quotient = max(1, (target - constant) // coefficient)
        hidden = min((quotient, quotient + 1),
                     key=lambda width: (abs(constant + coefficient * width - target), width))
    actual = constant + coefficient * hidden
    return dict(capacity_policy=capacity_policy, branch=branch, hidden_width=hidden,
                native_A_trainable_parameters=target, trainable_parameters=actual,
                parameter_difference=actual - target,
                relative_parameter_difference=(actual - target) / target,
                descriptor_fields=descriptor_fields, descriptor_model_input_width=feature_width,
                molecular_mlp_input_width=molecular_input,
                matching="analytic_nearest_positive_integer_width" if capacity_policy == "total_params_matching" else "fixed_256")


def model_descriptor_features(direct, field_count):
    """At model boundary only: missing numerical pad 0 + missing indicator."""
    if direct is None or direct.ndim != 2 or direct.shape[1] != 2 * field_count:
        raise ValueError("Expected frozen values followed by source-valid indicator channels")
    valid = direct[:, field_count:].bool()
    values = torch.where(valid, direct[:, :field_count], direct.new_zeros(())).float()
    if not bool(torch.isfinite(values).all()):
        raise ValueError("Observed direct descriptor is not representable as finite model FP32 input")
    return torch.cat((values, (~valid).to(values.dtype)), dim=1)


class DescriptorMLP(nn.Module):
    def __init__(self, field_count, hidden_width):
        super().__init__()
        self.field_count = field_count
        self.output = nn.Sequential(nn.Linear(2 * field_count, hidden_width), nn.ReLU(), nn.Linear(hidden_width, 1))

    def forward(self, h, mask, direct=None):
        return self.output(model_descriptor_features(direct, self.field_count)).squeeze(-1)


class H0DescriptorR3(nn.Module):
    def __init__(self, dimension, *, field_count, hidden_width, n_ref, mean, scale, native_factory):
        super().__init__()
        self.field_count = field_count
        self.native = native_factory(dimension, readout="R3", output_level="graph", n_ref=n_ref,
                                     mean=mean, scale=scale, direct_features=False)
        pooled_width = self.native.output[0].in_features
        self.native.output = nn.Sequential(nn.Linear(pooled_width + 2 * field_count, hidden_width), nn.ReLU(), nn.Linear(hidden_width, 1))

    def forward(self, h, mask, direct=None):
        from phychem_mfm.phase1.v3_dev_readouts import pooled_features
        h = torch.where(mask.unsqueeze(-1), h.detach(), h.new_zeros(()))
        atom = self.native.atom((h - self.native.feature_mean) / self.native.feature_scale)
        pooled = pooled_features(atom, mask, self.native.n_ref)
        descriptors = model_descriptor_features(direct, self.field_count)
        return self.native.output(torch.cat((pooled, descriptors), dim=1)).squeeze(-1)


@contextmanager
def probe_factory(module, factory):
    original = module.FrozenFeatureProbe
    try:
        module.FrozenFeatureProbe = factory
        yield
    finally:
        module.FrozenFeatureProbe = original


def run_descriptor_probe(train, validation, task, train_descriptors, validation_descriptors, *,
                         branch, capacity_policy, descriptor_value_source, n_ref, tracker,
                         relative_std_floor, internal_epoch_selection, seed=0, device="cpu",
                         train_member_keys=None, validation_member_keys=None, module=None):
    """Use native run_probe unchanged; no default capacity or input-value policy."""
    if task.output_level != "graph":
        raise ValueError("Section-5 direct B/C wrapper is for registered graph-output development tasks")
    train, validation = tuple(train), tuple(validation)
    if tuple(train_descriptors.fields) != tuple(validation_descriptors.fields):
        raise ValueError("TRAIN and validation descriptors must use the same frozen field order")
    if module is None:
        from phychem_mfm.phase1 import v3_dev_readouts as module
    native_factory = module.FrozenFeatureProbe
    scope = optimization_h0_statistics(train, relative_std_floor=relative_std_floor,
                                        internal_epoch_selection=internal_epoch_selection)
    with torch.random.fork_rng(devices=[]):
        prototype = native_factory(len(scope.mean), readout="R3", output_level="graph", n_ref=n_ref,
                                   mean=scope.mean, scale=scope.scale, direct_features=False)
        plan = capacity_plan(branch=branch, capacity_policy=capacity_policy,
                             descriptor_fields=len(train_descriptors.fields), native_prototype=prototype)
        del prototype
    train = attach_descriptors(train, train_descriptors, value_source=descriptor_value_source, member_keys=train_member_keys)
    validation = attach_descriptors(validation, validation_descriptors, value_source=descriptor_value_source,
                                    member_keys=validation_member_keys)

    def factory(dimension, *, readout, output_level, n_ref, mean, scale, direct_features=False):
        if readout != "R3" or output_level != "graph" or not direct_features or dimension != len(scope.mean):
            raise ValueError("Native probe scope/readout differs from the fixed B/C wrapper")
        # `mean/scale` supplied by native direct-feature detection are ignored:
        # descriptor values use only the explicitly chosen published policy.
        model = (DescriptorMLP(len(train_descriptors.fields), plan["hidden_width"]) if branch == "B" else
                 H0DescriptorR3(dimension, field_count=len(train_descriptors.fields), hidden_width=plan["hidden_width"],
                                n_ref=n_ref, mean=scope.mean, scale=scope.scale, native_factory=native_factory))
        if trainable_parameters(model) != plan["trainable_parameters"]:
            raise ValueError("Actual B/C trainable parameter count differs from the analytical capacity plan")
        return model

    with probe_factory(module, factory):
        prediction, metadata = module.run_probe(train, validation, task, readout="R3", n_ref=n_ref,
                                                seed=seed, device=device, tracker=tracker,
                                                relative_std_floor=relative_std_floor,
                                                internal_epoch_selection=internal_epoch_selection)
    return prediction, {**metadata, "D_direct_branch": branch, "capacity": plan,
                        "descriptor_value_source": descriptor_value_source,
                        "descriptor_statistics_refitted": False, "descriptor_loss_clipping": False,
                        "descriptor_fields": list(train_descriptors.fields),
                        "descriptor_model_layout": ["numeric_value_or_boundary_zero", "source_missing_indicator"],
                        "descriptor_model_feature_names": ["value/" + field for field in train_descriptors.fields]
                            + ["missing/" + field for field in train_descriptors.fields],
                        "descriptor_graph_transport_layout": ["source_value", "source_observed_valid"],
                        "source_store_values_modified": False,
                        "H0_features_used": branch == "C",
                        "H0_mean_scale_scope": ("same_native_internal_optimization_TRAIN" if branch == "C"
                                               else "native_A_capacity_reference_only"),
                        "optimization_molecule_uids": list(scope.optimization_uids),
                        "internal_molecule_uids": list(scope.internal_uids)}
