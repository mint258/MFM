"""Opt-in D targets over the unchanged native reader and wide-store consumer.

This wrapper performs no fitting, target clipping or reception acceptance.
``DRecipeDataset(**native_kwargs, d_recipe=...)`` accepts the existing P
dataset-configuration kwargs. ``make_d_dataset(native, enabled=False)`` is the
identity path. Construct stores in each process, as with native LMDB readers.
"""
import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from phychem_mfm.phase1.v31_loader import V31Target, normalize_values


def _parameters(value):
    if value is None:
        return {}
    if isinstance(value, (str, Path)):
        return json.loads(Path(value).read_text(encoding="utf-8"))
    return copy.deepcopy(value)


def _affine(spec, *, declared_train=False):
    """Adapt declared parameter keys; never estimate or change their values."""
    result = copy.deepcopy(spec)
    if "center" not in result:
        result["center"] = result["mean"]
    if "scale" not in result:
        result["scale"] = result.get("std_ddof0", result.get("std_population", result.get("std")))
    if declared_train:
        result.setdefault("fit_role", "TRAIN")
    if result.get("fit_role") != "TRAIN":
        raise ValueError("D targets require fixed TRAIN normalization parameters")
    return result


def _block(field):
    if field["level"] in ("atom", "atom_vector"):
        return "atom_sasa"
    return "molecule_3d" if field["name"].startswith("D3.") else "graph_2d"


def _normalize_target(raw, specification, *, Z, new_wide_field=False):
    if new_wide_field and not specification.get("p_recipe_fitted", False):
        # The unchanged loader names its F64 arithmetic selector after the P
        # fitter. Use that existing path for new F64 descriptor targets only;
        # this call-local selector is never added to frozen parameter metadata.
        specification = dict(specification, p_recipe_fitted=True)
    return normalize_values(raw, specification, Z=Z)


class DRecipeDataset:
    def __init__(self, native=None, *, d_recipe=None, **native_kwargs):
        config = dict(d_recipe or {})
        parameters = config.get("label_parameters", native_kwargs.pop("label_parameters", None))
        self.label_parameters = _parameters(parameters)
        if native is None:
            from phychem_mfm.phase1.p_recipe_data import PRecipeDataset
            native = PRecipeDataset(label_parameters=None, **native_kwargs)
        elif native_kwargs:
            raise ValueError("Supply an existing native reader or reader kwargs, not both")
        self.native = native
        self.library = config.get("library", "D20")
        if self.library not in ("D20", "L1", "L2"):
            raise ValueError("Unknown registered D descriptor library")
        self.split = config.get("split", "FULL" if getattr(native, "evaluation", False) else "TRAIN")
        self.model_group = "P" if config.get("pma_compatibility", False) else "D"
        self.wide = config.get("wide_store")
        if self.library != "D20" and self.wide is None:
            from tools.d_recipe.wide_store import WideDescriptorStore
            self.wide = WideDescriptorStore(config["wide_manifest"], self.library)
        if self.library != "D20" and self.wide.library != self.library:
            raise ValueError("Wide store library does not match the D condition")
        native_fields = {field["name"]: field for field in native.view.fields if field["group"] == "D"}
        self._native_fields = native_fields
        self._wide_by_name = {}
        fields = [copy.deepcopy(field) for field in native_fields.values()
                  if self.library == "D20" or not field["name"].startswith("D20.")]
        schema = copy.deepcopy(native.view.schema)
        base_parameters = {}
        for field in fields:
            name = field["name"]
            base_parameters[name] = _affine(field.get("normalization", native.view.normalizations.get(name)))
        if self.library != "D20":
            for position, source_name in enumerate(self.wide.fields):
                canonical = "D20." + source_name
                if self.library == "L1" and canonical in native_fields:
                    field = copy.deepcopy(native_fields[canonical])
                    spec = field.get("normalization", native.view.normalizations.get(canonical))
                    base_parameters[canonical] = _affine(spec)
                else:
                    name = "D." + self.library + "." + source_name
                    column = self.wide.columns[position]
                    spec = self.wide.metadata["normalization"][column]
                    base_parameters[name] = _affine(spec, declared_train=True)
                    field = {"name": name, "field_key": name, "group": "D", "family": "descriptor",
                             "level": "molecule", "representation": "scalar", "loss_enabled": True,
                             "unit": "descriptor_native_unit", "pooling": "mean"}
                    self._wide_by_name[name] = position
                    # Model metadata only; never add selectors to native.view.
                    schema.setdefault("columns", {}).setdefault("d_recipe_wide", []).append(
                        {"field_key": name, "family": "descriptor", "level": "molecule",
                         "kind": "scalar", "column_index": position, "pooling": "mean"})
                fields.append(field)
        overrides = self.label_parameters.get("normalizations", {})
        self._base_parameters = base_parameters
        normalizations = {}
        for field in fields:
            name = field["name"]
            spec = _affine(overrides[name]) if name in overrides else copy.deepcopy(base_parameters[name])
            if field["level"] in ("atom", "atom_vector") and spec.get("element_reference") is not None:
                raise ValueError("Element reference is only defined for molecular D scalars")
            field.update(source_group="D", group=self.model_group, d_block=_block(field), normalization=spec)
            normalizations[name] = spec
        self._fields = {field["name"]: field for field in fields}
        manifest = copy.deepcopy(getattr(native.view, "manifest", {}))
        manifest["fields"] = copy.deepcopy(fields)
        self.view = SimpleNamespace(fields=fields, schema=schema, normalizations=normalizations,
                                    manifest=manifest, normalization_dataset="P_D")
        self.view.d_initialization_reference = None
        if self.library != "D20":
            # Match native head ordering before any wide replacement. This
            # view is metadata for shared initialization only, never a reader.
            reference_fields, reference_norms = [], {}
            for original in native_fields.values():
                field = copy.deepcopy(original)
                name = field["name"]
                spec = overrides[name] if name in overrides else field.get(
                    "normalization", native.view.normalizations.get(name))
                spec = _affine(spec)
                field.update(source_group="D", group=self.model_group,
                             d_block=_block(field), normalization=spec)
                reference_fields.append(field)
                reference_norms[name] = spec
            reference_manifest = copy.deepcopy(getattr(native.view, "manifest", {}))
            reference_manifest["fields"] = copy.deepcopy(reference_fields)
            self.view.d_initialization_reference = SimpleNamespace(
                fields=reference_fields, schema=copy.deepcopy(native.view.schema),
                normalizations=reference_norms, manifest=reference_manifest,
                normalization_dataset="P_D")

    @property
    def indices(self):
        return self.native.indices

    def __len__(self):
        return len(self.native)

    def choices(self, molecule):
        return self.native.choices(molecule)

    def close(self):
        # WideDescriptorStore holds read-only mmaps; no writer or acceptance
        # state exists to close. Native reader owns its ordinary close API.
        return self.native.close()

    def read(self, molecule, conformer):
        return self._adapt(self.native.read(molecule, conformer))

    def sample(self, rng):
        return self._adapt(self.native.sample(rng))

    def _adapt(self, sample):
        source = sample.get("original_targets", sample["targets"])
        wide = None if self.library == "D20" else self.wide.get_batch(
            self.split, [int(sample["molecule_index"])], standardized=False)
        originals, targets = {}, {}
        for name, field in self._fields.items():
            if name in self._wide_by_name:
                column = self._wide_by_name[name]
                raw = wide.raw_values[:, column:column + 1].copy()
                valid = wide.observed_valid[:, column:column + 1].copy()
                with np.errstate(invalid="ignore", over="ignore"):
                    values = _normalize_target(raw, self._base_parameters[name], Z=sample["Z"],
                                               new_wide_field=True)
                values = np.where(valid, values, np.nan)
                original = V31Target(raw, values, valid, "D", field["family"], field["level"],
                                     field["representation"], field.get("loss_enabled", True))
            else:
                # Canonical shared D20 always comes from native raw/masks,
                # even if an exported wide column is also available.
                original = source[name]
            originals[name] = original
            spec = self.view.normalizations[name]
            with np.errstate(invalid="ignore", over="ignore"):
                normalized = _normalize_target(original.raw, spec, Z=sample["Z"],
                                               new_wide_field=name in self._wide_by_name)
            normalized = np.where(original.valid, normalized, np.nan)
            targets[name] = replace(original, values=normalized, group=self.model_group)
        return dict(sample, targets=targets, original_targets=originals)


def make_d_dataset(native=None, *, enabled=False, d_recipe=None, **native_kwargs):
    if not enabled:
        if native is not None:
            if native_kwargs:
                raise ValueError("Existing native reader and reader kwargs are mutually exclusive")
            return native
        from phychem_mfm.phase1.p_recipe_data import PRecipeDataset
        return PRecipeDataset(**native_kwargs)
    return DRecipeDataset(native, d_recipe=d_recipe, **native_kwargs)
