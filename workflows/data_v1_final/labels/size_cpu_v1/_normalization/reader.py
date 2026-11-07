"""Canonical typed-family reader joined to persistent masks and exact fit sides."""
from __future__ import annotations

import collections
import hashlib
from pathlib import Path
import struct

from runtime import (encode, identity, legacy, load, ref, require, restore_mask,
                     semantic_sha)
from compact import unpack


def selected_rows(pin, owners, columns, batch_records):
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = require(pin, content=False); before = identity(path)
    for batch in pq.ParquetFile(path).iter_batches(batch_size=batch_records, columns=columns, use_threads=False):
        take = [rid in owners for rid in batch.column(batch.schema.get_field_index("record_id")).to_pylist()]
        if not any(take):
            continue
        for row in batch.filter(pa.array(take)).to_pylist():
            owner = owners[row["record_id"]]
            if any(row[k] != owner[k] for k in ("record_id", "molecule_id", "attempt_id", "job_id", "task_id")):
                continue  # historical attempts have no standing in the final population
            yield row, owner
    if identity(path) != before:
        raise ValueError("SOURCE_CHANGED_DURING_FINAL_FIT")


def columns(family):
    names = ["record_id", "molecule_id", "attempt_id", "job_id", "task_id", "status"]
    if family == "D20":
        return names + ["values_float64", "valid_mask", "descriptor_names"]
    if family == "D3":
        return names + ["PMI1", "PMI2", "PMI3", "PBF_A", "volume_A3", "SASA_total_A2", "SASA_atom_A2", "issues"]
    return names + ["calc_type", "lane", "total_atoms", "values", "numeric_issues", "converged",
                    "scf_iterations", "precision_by_field_json", "source_status", "failure_code"]


def atom_order(numbers):
    if any(type(z) is not int or not 1 <= z <= 118 for z in numbers):
        raise ValueError("INVALID_ATOMIC_NUMBER_IN_FINAL_FIT")
    return hashlib.sha256(b"".join(struct.pack("<q", z) for z in numbers)).hexdigest()


def parity(compact, regenerated):
    # Reviews never alter a value mask. Calibration-specific reviews need not be regenerated here.
    for key in ("record_ordinal", "task_code", "in_scope_fields", "source_valid_fields", "valid_fields",
                "all_leaves_valid_fields", "newly_masked_fields", "source_reason_groups", "new_reason_groups",
                "leaf_exceptions"):
        if compact[key] != regenerated[key]:
            raise ValueError("PERSISTENT_MASK_AND_PINNED_DECODER_PARITY_FAILED:" + key)


def observations(item, group, side, source_cfg, hash_sources=False):
    import pyarrow.parquet as pq
    common, masks = legacy(source_cfg)
    ds, plan, fields = item["dataset"], item["plan"], item["fields"]
    all_rows = pq.read_table(require(side["side_table"]), use_threads=False).to_pylist()
    owners = {r["record_id"]: r for r in all_rows if r["fit_eligible"]}
    if len(all_rows) != side["records"] or len(owners) != side["fit_records"]:
        raise ValueError("FINAL_FIT_SIDE_RECORD_MASS_CHANGED")
    for r in owners.values():
        if r["effective_role"] != "TRAIN" or not r["common_population"] or r["fit_reason"] != "FIT_TRAIN_COMMON_NOT_DIAGNOSTIC":
            raise ValueError("FORBIDDEN_ROLE_OR_DIAGNOSTIC_REACHED_STATISTICS_KERNEL")
    identities = {}
    for pin in group["base_files"] + group["label_files"]:
        path = require(pin, content=hash_sources)
        identities[str(path)] = identity(path)
    numbers = {}
    base_columns = ["record_id", "molecule_id", "attempt_id", "job_id", "task_id", "atomic_numbers",
                    "native_atom_order_sha256", "source_payload_sha256", "geometry_status"]
    for pin in group["base_files"]:
        for row, owner in selected_rows(pin, owners, base_columns, 32):
            z = row["atomic_numbers"]
            if (owner["record_id"] in numbers or row["geometry_status"] not in ds["allowed_geometry_status"]
                    or len(z) != owner["total_atoms"] or atom_order(z) != row["native_atom_order_sha256"]
                    or row["source_payload_sha256"] != owner["record_payload_sha256"]
                    or sum(x > 1 for x in z) != owner["heavy_atoms"]):
                raise ValueError("FINAL_CANONICAL_ATOM_ORDER_PAYLOAD_OR_GEOMETRY_STATUS_DIFFERS")
            numbers[owner["record_id"]] = z
    if len(numbers) != len(owners):
        raise ValueError("FINAL_FIT_BASE_GEOMETRY_COVERAGE_INCOMPLETE")
    by_task = collections.defaultdict(list)
    for f in fields:
        by_task[f["task"]].append(f)
    seen = {task: set() for task in by_task}
    receipt = item["mask_receipts"][group["group_index"]]
    mask_files = {Path(p["path"]).name: p for p in receipt["outputs"] if p["path"].endswith(".mask.parquet")}
    for index, pin in enumerate(group["label_files"]):
        family = pin["family"]
        name = family + "_" + str(index).zfill(3) + ".mask.parquet"
        if name not in mask_files:
            raise ValueError("CANONICAL_MASK_FILE_FOR_SOURCE_MISSING:" + name)
        compact_rows = {}
        mask_path = require(mask_files[name])
        wanted_ord = {r["record_ordinal"] for r in owners.values()}
        for batch in pq.ParquetFile(mask_path).iter_batches(batch_size=4096, use_threads=False):
            # Mask tables contain no normal label values.
            for row in batch.to_pylist():
                if row["record_ordinal"] not in wanted_ord:
                    continue
                key = (row["record_ordinal"], row["task_code"])
                if key in compact_rows:
                    raise ValueError("DUPLICATE_FINAL_COMPACT_MASK_ROW")
                compact_rows[key] = row
        used = set()
        for row, owner in selected_rows(pin, owners, columns(family), source_cfg["source_read_batch_records"]):
            task = row.get("calc_type", family)
            if task not in by_task:
                raise ValueError("UNREGISTERED_TASK_IN_FINAL_SOURCE")
            if owner["record_id"] in seen[task]:
                raise ValueError("DUPLICATE_CANONICAL_FINAL_RECORD_TASK")
            seen[task].add(owner["record_id"])
            if family not in {"D20", "D3"} and (row["lane"] != owner["lane"] or row["total_atoms"] != owner["total_atoms"]):
                raise ValueError("FINAL_SOURCE_LANE_OR_ATOM_COUNT_DIFFERS")
            row["total_atoms"] = owner["total_atoms"]; row["calc_type"] = task
            entries = []
            for field, values, indices, reason in common.task_components(row, family, by_task[task]):
                _, source_mask, value_mask, sr, nr, reviews = masks.source_value_mask(field, row, values, reason)
                entries.append({"field": field, "field_id": field["field_id"], "field_key": field["field_key"],
                    "source_path": field["source_path"], "values_float64": [float(v) if type(v) in (int, float) else None for v in values],
                    "atom_indices": indices, "source_value_mask": source_mask, "value_mask": value_mask,
                    "source_reasons": sr, "new_reasons": nr, "review_reasons": reviews})
            masks.add_cross_field_checks(entries, row)
            key = owner["record_ordinal"], plan["task_codes"][task]
            if key not in compact_rows:
                raise ValueError("PERSISTENT_MASK_RECORD_TASK_MISSING")
            parity(compact_rows[key], encode(*key, entries)); used.add(key)
            for e in entries:
                e["value_mask"] = restore_mask(compact_rows[key], e["field_id"], len(e["values_float64"]))
                e["persisted_review_codes"] = [r["code"] for r in compact_rows[key]["review_groups"]
                                                if e["field_id"] in unpack(r["fields"])]
            yield owner, numbers[owner["record_id"]], entries
        if used != set(compact_rows):
            raise ValueError("PERSISTENT_MASK_TASK_COVERAGE_EXCEEDS_FINAL_SOURCE")
    if any(len(ids) != len(owners) for ids in seen.values()):
        raise ValueError("FINAL_FIT_RECORD_TASK_MASS_NOT_CONSERVED")
    for path, before in identities.items():
        if identity(path) != before:
            raise ValueError("FINAL_SOURCE_IDENTITY_CHANGED_ACROSS_GROUP_PASS")
