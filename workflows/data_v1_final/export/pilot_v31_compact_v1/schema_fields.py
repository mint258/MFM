"""Compile the existing 146-field registry into one external MFM4 schema.

This is a structure compiler, not a numeric exporter, normalizer, mask builder,
or physical-policy decision. Inputs are already loaded metadata dictionaries.
No file is opened and no SHA is computed. ``compile_schema`` returns the schema
dict itself: ``columns`` and ``target_layout`` are consumed by the assembler.

Target order uses the minimum existing field_id, with registry/mapping order as
the stable tie-breaker. A target's members and component_order are retained.
Single-member vectors keep the same real field_id on each axis; they do not
create registry fields. Atom vectors occupy one [N,3] column per target.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re

from .codec import codec_schema


UNKNOWN = "UNKNOWN"
_AXES = ("x", "y", "z")
_TENSOR6 = ("xx", "xy", "yy", "xz", "yz", "zz")
_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


class SchemaError(ValueError):
    """Existing registry/mapping metadata cannot describe this array layout."""


def _declared(mapping, name):
    return deepcopy(mapping[name]) if name in mapping else UNKNOWN


def _positive_references(value):
    """Copy supplied positive references without opening or hashing paths."""
    if isinstance(value, Mapping):
        if "path" in value:
            if (not isinstance(value["path"], str) or not value["path"]
                    or type(value.get("bytes")) is not int or value["bytes"] <= 0
                    or not isinstance(value.get("sha256"), str)
                    or _SHA.fullmatch(value["sha256"]) is None):
                raise SchemaError("parquet references must be existing positive refs")
            return deepcopy(dict(value))
        return {key: _positive_references(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_positive_references(item) for item in value]
    raise SchemaError("parquet references must contain only positive ref objects")


def _targets(mapping):
    raw = mapping.get("physical_targets")
    if isinstance(raw, Mapping):
        result = []
        for target_id, entry in raw.items():
            entry = deepcopy(dict(entry))
            if "target_id" in entry and entry["target_id"] != target_id:
                raise SchemaError("target ID differs from its mapping key")
            entry["target_id"] = target_id
            result.append(entry)
        return result
    if not isinstance(raw, list) or any(not isinstance(t, Mapping) for t in raw):
        raise SchemaError("physical_targets must be an existing list or ID map")
    return [deepcopy(dict(t)) for t in raw]


def _field_metadata(field, target, policy, registry_order):
    original_status = policy.get('physical_policy_status', field.get('bounded_physical_definition', {}).get('physical_policy_status', UNKNOWN))
    original_loss = False if isinstance(original_status, str) and ('LOSS_DISABLED' in original_status or original_status.startswith('DISABLED_')) else (True if original_status == 'ACTUAL_TARGET_CONDITION_SOURCE_ENABLED' else UNKNOWN)
    registry_loss = {name: deepcopy(value) for name, value in field.items()
                     if name == "loss" or name.startswith("loss_")}
    return {
        "registry_id": _declared(field, "registry_id"),
        "field_id": field["field_id"],
        "key": field["field_key"], "field_key": field["field_key"],
        "registry_order": registry_order,
        "component": _declared(field, "component"),
        "family": deepcopy(field.get("family_v1_final", UNKNOWN)),
        "mapping_family": _declared(target, "family"),
        "group": _declared(field, "group"),
        "level": _declared(field, "level"),
        "target_level": _declared(target, "level"),
        "unit": _declared(field, "unit"),
        "mapping_unit": _declared(target, "unit"),
        "unit_status": _declared(target, "unit_status"),
        "extensive": _declared(field, "extensivity"),
        "extensivity": _declared(field, "extensivity"),
        "registry_status": _declared(field, "status"),
        "loss": registry_loss if registry_loss else UNKNOWN,
        "loss_status": original_status,
        "loss_enabled": original_loss,
        "loss_enabled_condition": "Original source validity and D4 target-local eligibility still apply",
        "target_policy": deepcopy(policy),
        "physical_policy_status": _declared(policy, "physical_policy_status"),
        "source_path": _declared(field, "source_path"),
    }


def _components(target, members, fields, expected):
    """Describe existing axes, allowing one registry field for the vector."""
    order = target.get("component_order", list(expected))
    if list(order) != list(expected):
        raise SchemaError("mapping component order is unsupported for this layout")
    if len(members) == 1:
        return [(component, members[0], fields[0], axis)
                for axis, component in enumerate(order)]
    if len(members) != len(order):
        raise SchemaError("mapping vector/tensor member count differs from its axes")
    if [member.get("component") for member in members] != list(order):
        raise SchemaError("mapping members and declared component order differ")
    return [(component, member, field, axis)
            for axis, (component, member, field) in enumerate(zip(order, members, fields))]


def _array_definitions(columns):
    # Symbols describe axes only. The assembler supplies actual dimensions.
    specs = [
        (1, "Z", "u1", ["N"], ["M"]),
        (2, "bonds", "i2", ["E", 2], ["M"]),
        (3, "bond_order", "u1", ["E"], ["M"]),
        (4, "d20", "f4", [len(columns["d20"])], ["M"]),
        (5, "role", "u1", [], ["M"]),
        (6, "conformer_counts", "u2", [2], ["M"]),
        (7, "PM7_random", "u2", ["C_PM7"], ["M"]),
        (8, "UFF_random", "u2", ["C_UFF"], ["M"]),
        (9, "PM7_energy", "u2", ["C_PM7"], ["M"]),
        (10, "PM7_diversity", "u2", ["C_PM7"], ["M"]),
        (11, "UFF_energy", "u2", ["C_UFF"], ["M"]),
        (12, "UFF_diversity", "u2", ["C_UFF"], ["M"]),
        (13, "holdoutPM7", "u1", ["C_PM7"], ["M"]),
        (14, "holdoutUFF", "u1", ["C_UFF"], ["M"]),
        (21, "pos", "f4", ["N", 3], ["P", "U"]),
        (22, "pos_perturbed", "f4", ["N", 3], ["P", "U"]),
        (23, "mol_labels", "f4", [len(columns["mol_labels"])], ["P", "U"]),
        (24, "atom_labels", "f4", ["N", len(columns["atom_labels"])], ["P", "U"]),
        (25, "atom_vectors", "f4", ["N", len(columns["atom_vectors"]), 3], ["P", "U"]),
        (26, "pair_index", "i2", ["J", 2], ["P", "U"]),
        (27, "pair_labels", "f4", ["J", len(columns["pair_labels"])], ["P", "U"]),
        (31, "r73_pair_row", "u4", ["K"], ["P", "U"]),
        (32, "r73_channel_codes", "u2", ["K", 3], ["P", "U"]),
        (33, "r73_onsite", "u1", ["K"], ["P", "U"]),
        (34, "r73_values", "f4", ["K"], ["P", "U"]),
    ]
    result = {str(array_id): {"id": array_id, "name": name, "dtype": dtype,
                             "shape": shape, "record_kinds": kinds}
              for array_id, name, dtype, shape, kinds in specs}
    result["6"]["component_order"] = ["PM7", "UFF"]
    result["13"]["boolean_codes"] = result["14"]["boolean_codes"] = {"0": False, "1": True}
    result["31"]["meaning"] = "zero-based row into this conformer's pair_index; preserve K order and duplicates"
    result["32"]["component_order"] = ["basis_i", "basis_j", "channel"]
    result["32"]["codebook"] = "r73_channel_codebook; code 0 means absent"
    result["33"]["codes"] = {"0": "absent", "1": "false", "2": "true"}
    result["34"]["missing_value"] = "NaN only where the original value validmask is false"
    return result


def compile_schema(registry, mapping, target_policy, versions,
                   parquet_references, code_commit):
    """Return one raw/unnormalized schema plus the assembler's column layout.

    Input registry/mapping/target_policy are the actual existing bounded JSON
    objects. versions and parquet references are copied, never resolved or
    hashed. No loss state disables numeric export. Only the assembler's
    existing false validity masks may replace corresponding values by NaN.
    """
    if any(not isinstance(value, Mapping) for value in
           (registry, mapping, target_policy, versions)):
        raise SchemaError("registry/mapping/policy/versions must be metadata maps")
    if not isinstance(code_commit, str) or not code_commit:
        raise SchemaError("code_commit must be supplied by the caller")
    raw_fields = registry.get("fields")
    if not isinstance(raw_fields, list):
        raise SchemaError("registry fields must retain their original list order")
    enabled = []
    by_key = {}
    field_ids = set()
    for original_order, field in enumerate(raw_fields):
        if not isinstance(field, Mapping) or field.get("status") != "enabled":
            continue
        key, field_id = field.get("field_key"), field.get("field_id")
        if (not isinstance(key, str) or not key or key in by_key
                or type(field_id) is not int or field_id < 0 or field_id in field_ids):
            raise SchemaError("enabled registry keys and field_ids must be unique")
        field_ids.add(field_id)
        by_key[key] = (field, original_order)
        enabled.append((field_id, original_order, field))
    if len(enabled) != 146:
        raise SchemaError("this compact export requires the actual 146 enabled fields")
    policy_map = target_policy.get("targets", target_policy.get("target_policy", {}))
    if not isinstance(policy_map, Mapping):
        raise SchemaError("target policy must retain its existing target-ID map")
    targets = _targets(mapping)
    prepared = []
    covered = set()
    seen_targets = set()
    for mapping_order, target in enumerate(targets):
        tid, members = target.get("target_id"), target.get("members")
        if (not isinstance(tid, str) or not tid or tid in seen_targets
                or not isinstance(members, list) or not members):
            raise SchemaError("unique target IDs and nonempty exact members are required")
        seen_targets.add(tid)
        matched = []
        for member in members:
            if not isinstance(member, Mapping) or member.get("field_key") not in by_key:
                raise SchemaError("mapping member is not an enabled registry field")
            field, order = by_key[member["field_key"]]
            if member.get("registry_id") != field.get("registry_id"):
                raise SchemaError("mapping member registry_id differs from its field")
            if member["field_key"] in covered:
                raise SchemaError("one enabled registry field belongs to multiple targets")
            covered.add(member["field_key"])
            matched.append((field, order))
        prepared.append((min(field["field_id"] for field, _ in matched),
                         min(order for _, order in matched), mapping_order,
                         target, matched))
    if covered != set(by_key):
        raise SchemaError("mapping does not exactly cover all 146 enabled registry fields")

    columns = {name: [] for name in
               ("d20", "mol_labels", "atom_labels", "atom_vectors", "pair_labels")}
    layouts = {}
    field_catalog = {}
    for _, _, _, target, matched in sorted(prepared, key=lambda item: item[:3]):
        tid = target["target_id"]
        members = target["members"]
        fields = [field for field, _ in matched]
        policy = deepcopy(policy_map.get(tid, {}))
        if not isinstance(policy, Mapping):
            raise SchemaError("per-target policy must be a metadata map")
        metas = []
        for (field, order), member in zip(matched, members):
            meta = _field_metadata(field, target, policy, order)
            meta["target_id"] = tid
            meta["mapping_member"] = deepcopy(member)
            field_catalog[field["field_key"]] = meta
            metas.append(meta)
        kind, level = target.get("kind"), target.get("level")
        is_r73 = (target.get("wire_kind") == "SOURCE_ORDERED_RECORDS_V1"
                  and all(member.get("registry_id") == 73 for member in members))
        if target.get("wire_kind") == "SOURCE_ORDERED_RECORDS_V1" and not is_r73:
            raise SchemaError("only the declared r73 ordered target has this four-array layout")
        d20_flags = [member["field_key"].startswith("D20.") for member in members]
        if any(d20_flags) and not all(d20_flags):
            raise SchemaError("D20 and conformer-level fields cannot share a target")
        layout = {"array_name": None, "column_indices": [], "kind": kind,
                  "level": level, "storage": _declared(target, "storage"),
                  "members": deepcopy(members), "target_id": tid,
                  "component_order": _declared(target, "component_order"),
                  "target_policy": deepcopy(policy),
                  "mapping_target": deepcopy(target)}
        if is_r73:
            if len(members) != 1:
                raise SchemaError("r73 is one original ordered-record value field")
            layout.update(array_name="r73_ordered", array_ids=[31, 32, 33, 34],
                          field_metadata=metas[0], source_order_and_duplicates_preserved=True)
        else:
            if all(d20_flags):
                if kind != "scalar" or level != "molecule" or len(members) != 1:
                    raise SchemaError("D20 fields must retain their mapped molecule scalars")
                array_name = "d20"
            elif level == "molecule" and kind in ("scalar", "vector", "symmetric_tensor"):
                array_name = "mol_labels"
            elif level == "atom" and kind == "scalar":
                array_name = "atom_labels"
            elif level == "atom" and kind == "vector":
                array_name = "atom_vectors"
            elif level in ("pair", "sparse_atom_pair") and kind == "scalar":
                array_name = "pair_labels"
            else:
                raise SchemaError(f"unsupported existing target layout: {tid}/{kind}/{level}")
            layout["array_name"] = array_name
            if kind == "scalar":
                if len(members) != 1:
                    raise SchemaError("a mapped scalar target must have exactly one member")
                expanded = [(None, members[0], fields[0], None)]
            elif kind == "vector":
                expanded = _components(target, members, fields, _AXES)
            else:
                if target.get("storage") != "symmetric6":
                    raise SchemaError("this layout requires the existing tensor symmetric6 storage")
                expanded = _components(target, members, fields, _TENSOR6)
            if array_name == "atom_vectors":
                index = len(columns[array_name])
                components = []
                for component, member, field, source_index in expanded:
                    meta = deepcopy(field_catalog[field["field_key"]])
                    meta.update(component=component, source_component_index=source_index)
                    components.append(meta)
                column = deepcopy(metas[0])
                column.update(column_index=index, components=components,
                              member_metadata=deepcopy(metas), kind=kind,
                              storage=_declared(target, "storage"))
                columns[array_name].append(column)
                layout["column_indices"] = [index]
            else:
                for component, member, field, source_index in expanded:
                    index = len(columns[array_name])
                    column = deepcopy(field_catalog[field["field_key"]])
                    column.update(column_index=index, kind=kind,
                                  storage=_declared(target, "storage"),
                                  source_component_index=source_index)
                    if component is not None:
                        column["component"] = component
                    columns[array_name].append(column)
                    layout["column_indices"].append(index)
        layouts[tid] = layout

    schema = {
        "schema": "D3_V31_MFM4_COMPACT_ARRAY_SCHEMA_V1", "contract_version": "v3.1",
        "codec": codec_schema(), "numeric_values": "raw_unnormalized",
        "normalization_applied": False,
        "numeric_missingness": "NaN only for the original false validmask; loss-disabled finite values remain stored",
        "scientific_filtering_or_scale_changed": False,
        "enabled_registry_fields": len(enabled),
        "field_order": "existing field_id ascending, registry ordinal tie-break; mapping members/component order retained within target",
        "fields": [deepcopy(field_catalog[field["field_key"]])
                   for _, _, field in sorted(enabled, key=lambda item: item[:2])],
        "columns": columns, "target_layout": layouts,
        "array_definitions": _array_definitions(columns),
        "r73_channel_codebook": ["__ABSENT__"],
        "r73_channel_codebook_policy": "shared string dictionary for basis_i/basis_j/optional channel; 0 absent; assembler appends actual strings once and writes final schema",
        "r73_order": "K preserves original record order and duplicates; values are not reduced into ordinary pair_labels",
        "target_policy": deepcopy(dict(target_policy)),
        "registry_D20_names": deepcopy(registry.get("D20_names", UNKNOWN)),
        "versions": deepcopy(dict(versions)),
        "parquet_references": _positive_references(parquet_references),
        "code_commit": code_commit,
        "input_content_hashes_computed": False,
        "order_availability": {key: deepcopy(mapping[key]) for key in
                               ("available_orders", "unavailable_orders", "full_three_order",
                                "lowest_energy_rank0_available") if key in mapping},
    }
    return schema
