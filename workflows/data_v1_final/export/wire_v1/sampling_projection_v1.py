"""Per-molecule, per-source projection of D5 training rows, never a release.

Callers must supply authenticated D5 training_geometry/training_orders rows
and canonical geometry atom counts. This pure adapter neither reads a corpus
nor asserts that final D5, a joint contract, or a node-local provider exists.
"""
from __future__ import annotations

SOURCES = {"pm7": "PM7", "uff_sprime": "Sprime_UFF"}
ORDER_TYPES = {"fixed_random", "energy", "diversity"}


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _text(value):
    _require(type(value) is str and bool(value) and "\0" not in value,
             "NONEMPTY_LITERAL_ID_REQUIRED")
    return value


def _bounded_rows(values, cap):
    result = []
    for value in values:
        _require(len(result) < cap, "PER_MOLECULE_PROJECTION_CAP_EXCEEDED")
        result.append(dict(value))
    return result


def _flags(values, *, groups=False):
    _require(isinstance(values, dict) and bool(values), "EXPLICIT_EXPOSURE_MASK_REQUIRED")
    _require(all(type(k) is str and bool(k) and type(v) is bool
                 for k, v in values.items()), "BOOLEAN_EXPOSURE_MASK_REQUIRED")
    if groups:
        _require(set(values) == {"S", "D", "P"}, "ALL_THREE_GROUP_MASKS_REQUIRED")
    return [[k, values[k]] for k in sorted(values)]


def project_training_sources(molecule_id, *, effective_role, training_geometries,
                             training_orders, diagnostic_targets, native_atom_counts,
                             group_mask, family_mask, max_rows=4096):
    """Return separate MoleculeEntry-shaped dictionaries for PM7 and Sprime.

    geometry_id is the projected conformer_id and opaque provider locator.
    Native record/conformer identities are preserved separately, never joined
    across geometry sources. Views are excluded from base-conformer sampling.
    minimum_energy_conformer_id uses retained energy training_rank 0, which
    need not have original rank 0 after diagnostic exclusion.
    """
    _text(molecule_id)
    _require(effective_role == "TRAIN", "TRAIN_PROJECTION_ONLY")
    _require(type(max_rows) is int and max_rows > 0, "POSITIVE_PER_MOLECULE_CAP")
    group_flags = _flags(group_mask, groups=True)
    family_flags = _flags(family_mask)
    geometries = _bounded_rows(training_geometries, max_rows)
    orders = _bounded_rows(training_orders, 3 * max_rows)
    excluded = _bounded_rows(diagnostic_targets, max_rows)
    excluded_ids = set()
    for row in excluded:
        _require(row["molecule_id"] == molecule_id and row["geometry_source"] in SOURCES,
                 "DIAGNOSTIC_MOLECULE_OR_SOURCE_DIFFERS")
        gid = _text(row["geometry_id"])
        _require(gid not in excluded_ids, "DUPLICATE_DIAGNOSTIC_TARGET")
        excluded_ids.add(gid)
    by_id = {}
    for row in geometries:
        gid = _text(row["geometry_id"])
        _require(row["molecule_id"] == molecule_id and row["geometry_source"] in SOURCES,
                 "GEOMETRY_MOLECULE_OR_SOURCE_DIFFERS")
        _require(gid not in by_id, "GEOMETRY_ID_COLLISION_ACROSS_SOURCES")
        _require(gid not in excluded_ids and row["parent_geometry_id"] not in excluded_ids,
                 "DIAGNOSTIC_GEOMETRY_LEAKED_INTO_TRAINING")
        parent, view = row["parent_geometry_id"], row["view_id"]
        _require((parent is None) == (view is None), "VIEW_PARENT_PAIR_REQUIRED")
        src = row["geometry_source"]
        native, idx = row["native_record_id"], row["sprime_conf_idx"]
        if src == "pm7":
            _text(native)
            _require(idx is None, "PM7_MUST_NOT_USE_UFF_CONFORMER_INDEX")
        else:
            _require(type(idx) is int and idx >= 0, "UFF_PHYSICAL_INDEX_REQUIRED")
            _require(native is None or type(native) is str,
                     "UFF_NATIVE_RECORD_IS_PROVENANCE_ONLY")
        by_id[gid] = row
    base = {gid: row for gid, row in by_id.items() if row["view_id"] is None}
    physical = set()
    for row in base.values():
        key = (row["geometry_source"], row["native_record_id"] if row["geometry_source"] == "pm7"
               else row["sprime_conf_idx"])
        _require(key not in physical, "DUPLICATE_BASE_PHYSICAL_IDENTITY")
        physical.add(key)
    for row in by_id.values():
        if row["parent_geometry_id"] is not None:
            parent = base.get(row["parent_geometry_id"])
            _require(parent is not None and parent["geometry_source"] == row["geometry_source"],
                     "VIEW_PARENT_NOT_RETAINED_IN_SAME_SOURCE")
    _require(base and isinstance(native_atom_counts, dict)
             and set(native_atom_counts) == set(base), "EXACT_BASE_GEOMETRY_ATOM_COUNTS_REQUIRED")
    _require(all(type(n) is int and n > 0 for n in native_atom_counts.values()),
             "POSITIVE_CANONICAL_ATOM_COUNTS_REQUIRED")
    grouped = {(src, kind): [] for src in SOURCES for kind in ORDER_TYPES}
    seen = set()
    for row in orders:
        gid = _text(row["geometry_id"])
        src, kind = row["geometry_source"], row["order_type"]
        _require(row["molecule_id"] == molecule_id and (src, kind) in grouped,
                 "ORDER_MOLECULE_SOURCE_OR_TYPE_DIFFERS")
        _require(gid in base and base[gid]["geometry_source"] == src,
                 "ORDER_MUST_REFERENCE_RETAINED_BASE_IN_OWN_SOURCE")
        _require((gid, kind) not in seen, "DUPLICATE_GEOMETRY_ORDER")
        seen.add((gid, kind))
        _require(type(row["rank"]) is int and row["rank"] >= 0
                 and type(row["training_rank"]) is int and row["training_rank"] >= 0,
                 "EXPLICIT_NONNEGATIVE_ORIGINAL_AND_TRAINING_RANK_REQUIRED")
        grouped[src, kind].append(row)
    entries, native_ids = {}, {}
    for src, model_src in SOURCES.items():
        members = {gid for gid, row in base.items() if row["geometry_source"] == src}
        _require(bool(members), "BOTH_SOURCE_PROJECTIONS_REQUIRED")
        ranks = {}
        for kind in ORDER_TYPES:
            rows = sorted(grouped[src, kind], key=lambda r: r["training_rank"])
            _require({r["geometry_id"] for r in rows} == members and len(rows) == len(members),
                     "THREE_COMPLETE_SOURCE_ORDERS_REQUIRED")
            _require([r["training_rank"] for r in rows] == list(range(len(rows))),
                     "CONTIGUOUS_SOURCE_TRAINING_RANKS_REQUIRED")
            originals = [r["rank"] for r in rows]
            _require(originals == sorted(set(originals)),
                     "TRAINING_RANK_MUST_PRESERVE_ORIGINAL_ORDER")
            ranks[kind] = {r["geometry_id"]: r["training_rank"] for r in rows}
        conformers = []
        for gid in sorted(members, key=ranks["fixed_random"].__getitem__):
            row = base[gid]
            conformers.append({"conformer_id": gid,
                "fixed_order": ranks["fixed_random"][gid],
                "native_atoms": native_atom_counts[gid],
                "geometry_locators": [[model_src, gid]],
                "diversity_order": ranks["diversity"][gid]})
            native_ids[gid] = {k: row[k] for k in ("geometry_id", "molecule_id",
                "geometry_source", "native_record_id", "sprime_conf_idx")}
        minimum = next(gid for gid, rank in ranks["energy"].items() if rank == 0)
        entries[src] = {"molecule_id": molecule_id, "conformers": conformers,
            "group_mask": group_flags, "family_mask": family_flags,
            "mixed_geometry_source": model_src,
            "minimum_energy_conformer_id": minimum}
    return {"schema": "D5_PER_SOURCE_TRAINING_SAMPLING_PROJECTION_V1",
        "status": "CANDIDATE_PROJECTION_NOT_RELEASE",
        "source_entries": entries, "native_conformer_identity": native_ids,
        "projected_conformer_id_semantics": "opaque D5 geometry_id; no cross-source alignment",
        "minimum_energy_rule": "retained energy training_rank=0 after diagnostic anti-join",
        "contract_finalized": False, "real_data_export_accepted": False}
