"""D-only model bridge for the unchanged P training loop.

Three explicitly named aggregate loss entries are exposed to the training-loop
bookkeeping. They are not physical labels and never create prediction heads.
The underlying V31PDModel/V3HeadBank continue to own only real D heads.
"""
from copy import deepcopy
import json
import math

import numpy as np
import torch
import torch.nn.functional as F

from phychem_mfm.phase1.v31_training import V31PDModel, torch_affine
from phychem_mfm.phase1.v3_contract import FieldSpec
from phychem_mfm.phase1.v3_losses import V3LossResult

try:
    from .loss import BLOCKS, DBlockWeights, compute_d_loss, mask_graph_targets
except ImportError:
    from loss import BLOCKS, DBlockWeights, compute_d_loss, mask_graph_targets


BLOCK_ALIASES = {"graph_2d": "D_BLOCK_GRAPH_2D", "molecule_3d": "D_BLOCK_MOLECULE_3D",
                 "atom_sasa": "D_BLOCK_ATOM_SASA"}


class AggregateRegistry:
    """Metadata facade: default aggregate entries, explicitly requested real fields."""

    def __init__(self, original, aliases):
        self.original, self.aliases = original, tuple(aliases)
        self.fields = original.fields + self.aliases
        self.version = original.version + ":D_BLOCK_AGGREGATES"
        self.source_sha256, self.authority = original.source_sha256, original.authority

    def by_name(self):
        return {field.name: field for field in self.fields}

    def enabled(self, groups, names=None):
        if names is None:
            return tuple(field for field in self.aliases if field.group in groups)
        names = tuple(names)
        if len(names) != len(set(names)) or set(names) - set(self.by_name()):
            raise ValueError("Unknown or duplicate D physical/aggregate field")
        return tuple(field for field in self.fields if field.group in groups and field.name in names)


class DRecipeModel(V31PDModel):
    """Opt-in D constructor; the legacy V31PDModel path is not modified.

    `view` is an independent D view with real field names/normalizations intact,
    internal group P, and source_group D. This lets the existing PMA router act
    on D molecular heads while preserving the original atomic SASA head.

    Wide-library views provide `d_initialization_reference`: the independent
    native D20+D3 view in its original field order. For the same entry RNG,
    encoder, and P-recipe options, shared real head/projector/PMA tensors and
    the post-initialization CPU RNG are copied from that native construction.
    New library-only heads retain their own values. D20 leaves this attribute
    None and follows the original initialization path without a reference build.
    """

    def __init__(self, encoder, view, *, block_weights=None, binding=None, d_recipe=None,
                 graph_mask_enabled=False, mask_seed=None, include_3d=True, **kwargs):
        options = d_recipe or {}
        block_weights = block_weights if block_weights is not None else options["block_weights"]
        binding = binding if binding is not None else options["scientific_binding"]
        graph_mask_enabled = options.get("graph_mask_enabled", graph_mask_enabled)
        mask_seed = options.get("mask_seed", mask_seed)
        include_3d = options.get("include_3d", include_3d)
        reference_view = getattr(view, "d_initialization_reference", None)
        shared_initialization, native_post_init_rng = None, None
        if reference_view is not None:
            # Reuse the already-created encoder object. V31PDModel constructs
            # heads/projectors/PMA but never reinitializes encoder parameters.
            # The fork prevents native-reference construction from advancing
            # the actual wide model's entry RNG.
            with torch.random.fork_rng(devices=[]):
                native = V31PDModel(encoder, reference_view, **kwargs)
                shared_initialization = {
                    name: value.detach().clone()
                    for name, value in native.state_dict().items()
                    if torch.is_tensor(value) and not name.startswith("encoder.")
                }
                native_post_init_rng = torch.get_rng_state().clone()
                del native
        super().__init__(encoder, view, **kwargs)
        if shared_initialization is not None:
            actual = {**dict(self.named_parameters()), **dict(self.named_buffers())}
            with torch.no_grad():
                for name, value in shared_initialization.items():
                    if name in actual and actual[name].shape == value.shape:
                        actual[name].copy_(value)
            # New wide-only fields retain their own initialized values. Shared
            # tensors and subsequent dropout/global RNG match native D20+D3.
            # Registry extra-state is deliberately never copied across libraries.
            torch.set_rng_state(native_post_init_rng)
        self.block_weights = (block_weights if isinstance(block_weights, DBlockWeights)
                              else DBlockWeights(**block_weights))
        weights = [getattr(self.block_weights, block) for block in BLOCKS]
        if any(not math.isfinite(value) or value < 0 for value in weights) or not math.isclose(sum(weights), 1., abs_tol=1e-12):
            raise ValueError("Supply the three frozen D-R0 block weights summing to one")
        # Require ordinary JSON metadata so checkpoint identity comparisons do
        # not depend on Python object identity or unsafe deserialization types.
        self._d_binding = json.loads(json.dumps(binding, allow_nan=False))
        self.graph_mask_enabled, self.include_3d = graph_mask_enabled, include_3d
        if graph_mask_enabled and mask_seed is None:
            raise ValueError("D-K1 requires an explicit dedicated mask_seed")
        self._d_mask_generator = torch.Generator(device="cpu")
        self._d_mask_generator.manual_seed(0 if mask_seed is None else mask_seed)
        self._d_binding.update(block_weights=dict(zip(BLOCKS, weights)),
                               graph_mask_enabled=graph_mask_enabled,
                               mask_seed=mask_seed, include_3d=include_3d,
                               output_parameterization=self.output_parameterization)
        self.real_registry, self.real_head_registry = self.registry, self.head_registry
        self.block_fields = {block: [] for block in BLOCKS}
        for field in self.real_registry.fields:
            definition = self.definitions[field.name]
            if field.group != "P" or definition.get("source_group", "D") != "D":
                raise ValueError("D bridge requires independent D fields routed internally as P")
            block = definition.get("d_block")
            if block is None:
                block = ("atom_sasa" if field.level == "atom" else
                         "molecule_3d" if field.name.startswith("D3.") else "graph_2d")
            if block not in BLOCKS or field.representation != "scalar":
                raise ValueError("D bridge accepts only the registered scalar D blocks")
            if (block == "atom_sasa") != (field.level == "atom"):
                raise ValueError("D block and source target level differ")
            self.block_fields[block].append(field.name)
        if len(self.block_fields["atom_sasa"]) > 1:
            raise ValueError("Taskbook declares one native atomic SASA field")
        # Derived CPU metadata only: no buffer, parameter or extra checkpoint
        # state is added. The source frozen specs remain in scientific binding.
        self._d_molecular_affines = {}
        for block in ("graph_2d", "molecule_3d"):
            for name in self.block_fields[block]:
                definition = self.definitions[name]
                specification = definition.get("normalization", self.view.normalizations.get(name))
                if specification is None:
                    raise ValueError("Missing frozen D4 normalization for " + name)
                self._d_molecular_affines[name] = (
                    float(np.asarray(specification["center"]).reshape(-1)[0]),
                    float(np.asarray(specification["scale"]).reshape(-1)[0]))
        aliases = tuple(FieldSpec(BLOCK_ALIASES[block], "P", block, "graph", unit="normalized_D_block_loss")
                        for block in BLOCKS)
        self.registry = AggregateRegistry(self.real_registry, aliases)
        self.head_registry = AggregateRegistry(self.real_head_registry, aliases)
        self.selections.update({field.name: (field.name, None) for field in aliases})
        self.last_masks = None
        self.mask_counts = {"source_valid": 0, "source_missing": 0,
                            "random_dropped": 0, "effective_valid": 0}
        self._d_binding["target_definitions"] = [dict(name=field.name,
            d_block=self.definitions[field.name].get("d_block"),
            target_affine_arithmetic=("F64_then_FP32_target" if field.name.startswith(("D.L1.", "D.L2."))
                                      else "unchanged_native_normalize_values"),
            normalization=deepcopy(self.definitions[field.name].get("normalization",
                self.view.normalizations.get(field.name)))) for field in self.real_registry.fields]

    @property
    def field_loss_multipliers(self):
        return {BLOCK_ALIASES[block]: getattr(self.block_weights, block) for block in BLOCKS}

    def _expand(self, fields):
        selected = tuple(BLOCK_ALIASES.values()) if fields is None else tuple(fields)
        result = []
        inverse = {alias: block for block, alias in BLOCK_ALIASES.items()}
        for name in selected:
            result.extend(self.block_fields[inverse[name]] if name in inverse else (name,))
        return tuple(dict.fromkeys(result))

    def predict(self, samples, *, groups=("P",), fields=None, **kwargs):
        return super().predict(samples, groups=groups, fields=self._expand(fields), **kwargs)

    def _pack(self, predictions, samples, selected):
        first = next(iter(predictions.values()))
        batch_size = len(samples)
        packed_prediction, packed_target, packed_valid = {}, {}, {}
        for block in BLOCKS:
            names = [name for name in self.block_fields[block] if name in selected]
            if names and block != "atom_sasa":
                # Stack in frozen field order before casting/transforming.
                # Each block creates only one affine constant tensor and one
                # target/valid H2D copy, independent of descriptor-library width.
                prediction = torch.cat([predictions[name].reshape(batch_size, 1)
                                        for name in names], dim=1).float()
                if self.output_parameterization == "raw":
                    affine = prediction.new_tensor(
                        [[self._d_molecular_affines[name][index] for name in names] for index in (0, 1)])
                    center, scale = affine.unbind(0)
                    prediction = (prediction - center) / scale
                values_cpu = np.stack([
                    np.concatenate([sample["targets"][name].values for sample in samples]).reshape(batch_size)
                    for name in names], axis=1)
                valid_cpu = np.stack([
                    np.concatenate([sample["targets"][name].valid for sample in samples]).reshape(batch_size)
                    for name in names], axis=1)
                packed_prediction[block] = prediction
                packed_target[block] = torch.as_tensor(values_cpu, device=prediction.device, dtype=torch.float32)
                packed_valid[block] = torch.as_tensor(valid_cpu, device=prediction.device, dtype=torch.bool)
                continue
            columns, targets, masks = [], [], []
            for name in names:
                definition = self.definitions[name]
                specification = definition.get("normalization", self.view.normalizations.get(name))
                if specification is None:
                    raise ValueError("Missing frozen D4 normalization for " + name)
                prediction = predictions[name].float()
                if self.output_parameterization == "raw":
                    prediction = torch_affine(prediction, specification)
                value = torch.as_tensor(np.concatenate([s["targets"][name].values for s in samples]),
                                        device=prediction.device, dtype=torch.float32)
                valid = torch.as_tensor(np.concatenate([s["targets"][name].valid for s in samples]),
                                        device=prediction.device, dtype=torch.bool)
                if block != "atom_sasa":
                    columns.append(prediction.reshape(batch_size, 1))
                    targets.append(value.reshape(batch_size, 1))
                    masks.append(valid.reshape(batch_size, 1))
                else:
                    lengths = [len(s["Z"]) for s in samples]
                    if sum(lengths) != prediction.numel() or value.numel() != sum(lengths) or valid.numel() != sum(lengths):
                        raise ValueError("Native atomic SASA length differs from source atoms")
                    largest = max(lengths)
                    for pred, truth, observed in zip(prediction.reshape(-1).split(lengths),
                                                     value.reshape(-1).split(lengths),
                                                     valid.reshape(-1).split(lengths)):
                        padding = (0, largest - pred.numel())
                        columns.append(F.pad(pred, padding))
                        targets.append(F.pad(truth, padding))
                        masks.append(F.pad(observed, padding, value=False))
            if columns:
                combine = torch.stack if block == "atom_sasa" else lambda values: torch.cat(values, dim=1)
                packed_prediction[block], packed_target[block], packed_valid[block] = (
                    combine(values) for values in (columns, targets, masks))
            else:
                packed_prediction[block] = first.new_empty((batch_size, 0), dtype=torch.float32)
                packed_target[block] = first.new_empty((batch_size, 0), dtype=torch.float32)
                packed_valid[block] = torch.empty((batch_size, 0), device=first.device, dtype=torch.bool)
        return packed_prediction, packed_target, packed_valid

    def loss(self, predictions, samples, *, groups=("P",), fields=None, **kwargs):
        real = set(self._expand(fields))
        prediction, target, valid = self._pack(predictions, samples, real)
        # CPU-only dedicated mask RNG is portable across GPU placements and
        # never consumes global Torch or the molecule/conformer sampler state.
        graph_mask = mask_graph_targets(valid["graph_2d"].cpu(),
                                        enabled=self.graph_mask_enabled and self.training,
                                        generator=self._d_mask_generator)
        if self.training:
            for name, value in (("source_valid", graph_mask.observed_valid),
                                ("source_missing", ~graph_mask.observed_valid),
                                ("random_dropped", graph_mask.random_dropped),
                                ("effective_valid", graph_mask.effective_valid)):
                self.mask_counts[name] += int(value.sum())
        effective = dict(valid)
        effective["graph_2d"] = graph_mask.effective_valid.to(valid["graph_2d"].device)
        result = compute_d_loss(prediction, target, effective, self.block_weights,
                                enabled=True, include_3d=self.include_3d)
        self.last_masks = {**result.masks, "graph_2d": graph_mask}
        values = {BLOCK_ALIASES[block]: result.block_means[block].mean() for block in BLOCKS}
        counts = {alias: len(samples) for alias in BLOCK_ALIASES.values()}
        return V3LossResult(result.total, values, {"P": result.total}, counts,
                            {"P": len(BLOCKS)}, ("P",))

    def get_extra_state(self):
        return {"schema": "D_RECIPE_MODEL_STATE_V1", "binding": deepcopy(self._d_binding),
                "mask_rng": self._d_mask_generator.get_state(), "mask_counts": dict(self.mask_counts)}

    def set_extra_state(self, state):
        if state.get("schema") != "D_RECIPE_MODEL_STATE_V1" or state.get("binding") != self._d_binding:
            raise ValueError("D checkpoint scientific binding differs from the requested condition")
        self._d_mask_generator.set_state(state["mask_rng"].cpu())
        self.mask_counts = dict(state["mask_counts"])
