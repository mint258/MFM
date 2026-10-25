"""Frozen mask/owner bindings and geometry-precise final eligibility side tables."""
from __future__ import annotations

import collections
from pathlib import Path
import re

from runtime import (budget, identity, load, path_list, ref, require, save,
                     semantic_sha, sqlstr, write_blob)


def datasets(cfg):
    ready, pending = [], []
    for item in cfg["datasets"]:
        if (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", item["dataset_id"]) is None
                or item["label_group"] not in {"P_D", "Pprime"}):
            raise ValueError("UNSAFE_DATASET_ID_OR_UNKNOWN_LABEL_GROUP")
        if item.get("manifest") is None:
            pending.append({"dataset_id": item["dataset_id"], "label_group": item["label_group"],
                            "status": "PENDING_REAL_INDEPENDENT_SOURCE_NO_P_VALUE_SUBSTITUTION"})
            continue
        obj = load(require(item["manifest"]))
        if obj["schema"] != "FINAL_NORMALIZATION_DATASET_V1" or obj["status"] != "CANONICAL_MASKED_DATASET_FROZEN":
            raise ValueError("FINAL_SOURCE_DATASET_NOT_FROZEN")
        if obj["dataset_id"] != item["dataset_id"] or obj["label_group"] != item["label_group"]:
            raise ValueError("DATASET_ID_OR_LABEL_GROUP_BINDING_DIFFERS")
        if ((obj["label_group"] == "Pprime") != (obj["geometry_source"] == "uff_sprime")
                or obj["geometry_source"] not in {"pm7", "uff_sprime"}):
            raise ValueError("PPRIME_MUST_HAVE_ITS_OWN_UFF_SOURCE")
        if obj["adapter"] != "canonical_typed_family_v1":
            raise ValueError("UNSUPPORTED_SOURCE_ADAPTER_REQUIRES_EXPLICIT_IMPLEMENTATION")
        if obj["owner_record_semantics"] != "base_geometry_with_task_views":
            raise ValueError("OWNER_RECORD_TO_GEOMETRY_TASK_VIEW_SEMANTICS_NOT_EXPLICIT")
        if obj["geometry_source"] == "pm7" and obj["allowed_geometry_status"] != ["ORIGINAL_PM7_GEOMETRY"]:
            raise ValueError("PM7_BASE_GEOMETRY_STATUS_DIFFERS")
        if obj["geometry_source"] == "uff_sprime" and "ORIGINAL_PM7_GEOMETRY" in obj["allowed_geometry_status"]:
            raise ValueError("PPRIME_CANNOT_CONSUME_PM7_GEOMETRY_BYTES")
        plan = load(require(obj["group_plan"]))
        scan = load(require(obj["mask_scan_manifest"]))
        reduction = load(require(obj["mask_reduction"]))
        if (plan["mode"] != "full" or scan["mode"] != "full" or scan["phase"] != "mask"
                or reduction["mode"] != "full" or reduction["phase"] != "mask"):
            raise ValueError("PILOT_OR_NONFINAL_MASKS_CANNOT_DEFINE_D4")
        if (scan["plan"] != obj["group_plan"] or reduction["plan"] != obj["group_plan"]
                or reduction["scan_manifest"] != obj["mask_scan_manifest"]
                or scan["coverage_fingerprint"] != plan["coverage_fingerprint"]
                or reduction["coverage_fingerprint"] != plan["coverage_fingerprint"]):
            raise ValueError("CANONICAL_MASK_SOURCE_PLAN_SCOPE_DIFFERS")
        if (reduction.get("stop_fields") or reduction["records"] != plan["records"]
                or reduction.get("all_original_population_source_coverage") is not True
                or any(c["new_mask_fraction"] > .01 for c in reduction["field_counts"].values())):
            raise ValueError("MASK_SOURCE_COVERAGE_OR_ONE_PERCENT_STOP_NOT_CLOSED")
        fields = load(require(plan["field_map"]))
        if len({g["source_job_id"] for g in plan["groups"]}) != len(plan["groups"]):
            raise ValueError("CANONICAL_SOURCE_JOB_SPLIT_INTO_MULTIPLE_OWNER_GROUPS")
        allowed = set(obj["enabled_field_ids"])
        fields = [f for f in fields if f["field_id"] in allowed]
        if len(fields) != len(allowed) or not fields:
            raise ValueError("DATASET_ENABLED_FIELD_IDS_MISSING_OR_DUPLICATE")
        if obj["label_group"] == "Pprime" and any(f["field_key"].startswith("D.") for f in fields):
            raise ValueError("PPRIME_STATISTICS_MUST_NOT_ALIAS_DESCRIPTOR_OR_P_DATASET")
        if {f["task"] for f in fields} != set(plan["task_codes"]):
            raise ValueError("FINAL_DATASET_TASK_SET_DIFFERS_FROM_ENABLED_COMPONENTS")
        receipts = {}
        for pin in scan["group_receipts"]:
            r = load(require(pin)); i = r["group_index"]
            if i in receipts or r["status"] != "SOURCE_GROUP_SCANNED":
                raise ValueError("DUPLICATE_OR_INCOMPLETE_MASK_GROUP")
            receipts[i] = r
        if set(receipts) != {g["group_index"] for g in plan["groups"]}:
            raise ValueError("FINAL_MASK_GROUP_SET_INCOMPLETE")
        for g in plan["groups"]:
            r = receipts[g["group_index"]]
            if r["owner_index"] != g["owner_index"] or r["records"] != g["expected_records"]:
                raise ValueError("MASK_OWNER_INDEX_BINDING_DIFFERS")
        ready.append({"manifest": item["manifest"], "dataset": obj, "plan": plan,
                      "fields": fields, "mask_receipts": receipts})
    ids = [d["dataset"]["dataset_id"] for d in ready] + [d["dataset_id"] for d in pending]
    if len(ids) != len(set(ids)) or not ready:
        raise ValueError("DUPLICATE_DATASET_OR_NO_REAL_SOURCE_READY")
    return ready, pending


def side_table(db, group, dataset, root, cfg):
    """Materialize every owner row, including excluded rows and explicit reasons."""
    owner = require(group["owner_index"])
    before = identity(owner)
    db.execute("CREATE OR REPLACE VIEW owner_rows AS SELECT * FROM read_parquet(" + sqlstr(owner) + ")")
    names = {r[0] for r in db.execute("DESCRIBE owner_rows").fetchall()}
    if names & {"effective_role", "common_population", "geometry_source", "geometry_id", "parent_geometry_id",
                "view_id", "fit_reason", "fit_eligible"}:
        raise ValueError("RAW_OWNER_INDEX_ALREADY_CONTAINS_RESERVED_FINAL_FIT_COLUMNS")
    source = dataset["geometry_source"]
    if source == "pm7":
        join = "g.native_record_id=o.record_id"
    else:
        # This column is mandatory. Pprime record IDs and provenance source IDs are opaque.
        join = "g.sprime_conf_idx=o.sprime_conf_idx"
    db.execute("""CREATE OR REPLACE TEMP TABLE fit_side AS SELECT o.*,
        upper(r.effective_role) AS effective_role,m.common_population,
        g.geometry_source,g.geometry_id,g.parent_geometry_id,g.view_id,
        CASE WHEN upper(r.effective_role)<>'TRAIN' THEN 'ROLE_'||upper(r.effective_role)
          WHEN NOT m.common_population THEN 'OUTSIDE_FROZEN_COMMON_POPULATION'
          WHEN d.geometry_id IS NOT NULL OR p.geometry_id IS NOT NULL
            THEN 'HELDOUT_GEOMETRY_OR_ITS_PERTURBED_VIEW'
          ELSE 'FIT_TRAIN_COMMON_NOT_DIAGNOSTIC' END AS fit_reason,
        (upper(r.effective_role)='TRAIN' AND m.common_population
          AND d.geometry_id IS NULL AND p.geometry_id IS NULL) AS fit_eligible
        FROM owner_rows o LEFT JOIN roles r USING(molecule_id)
        LEFT JOIN members m USING(molecule_id)
        LEFT JOIN geometry g ON g.molecule_id=o.molecule_id AND g.geometry_source=""" + sqlstr(source) +
        " AND g.parent_geometry_id IS NULL AND " + join + """
        LEFT JOIN diagnostic d ON d.molecule_id=g.molecule_id AND d.geometry_source=g.geometry_source AND d.geometry_id=g.geometry_id
        LEFT JOIN diagnostic p ON p.molecule_id=g.molecule_id AND p.geometry_source=g.geometry_source AND p.geometry_id=g.parent_geometry_id""")
    n, u, ord_u, bad = db.execute("""SELECT count(*),count(DISTINCT record_id),count(DISTINCT record_ordinal),
        count(*) FILTER(WHERE effective_role IS NULL OR common_population IS NULL OR geometry_id IS NULL
        OR upper(new_role)<>effective_role OR fit_eligible IS NULL) FROM fit_side""").fetchone()
    if (n, u, ord_u, bad) != (group["expected_records"],) * 3 + (0,):
        raise ValueError("FINAL_FIT_SIDE_COVERAGE_ROLE_OR_GEOMETRY_FK_DIFFERS")
    if db.execute("SELECT count(*) FROM fit_side WHERE fit_eligible AND (effective_role<>'TRAIN' OR NOT common_population)").fetchone()[0]:
        raise ValueError("NON_TRAIN_OR_OUTSIDE_COMMON_LEAKED_INTO_FINAL_FIT")
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = db.execute("SELECT * FROM fit_side ORDER BY record_ordinal").fetch_arrow_table()
    sink = pa.BufferOutputStream(); pq.write_table(table, sink, compression="zstd", row_group_size=4096)
    pin = write_blob(Path(root) / (dataset["dataset_id"] + "_" + str(group["group_index"]).zfill(4) + ".fit.parquet"),
                     memoryview(sink.getvalue()), root, cfg["output_cap_bytes"])
    counts = dict(db.execute("SELECT fit_reason,count(*) FROM fit_side GROUP BY fit_reason ORDER BY fit_reason").fetchall())
    mass = db.execute("SELECT count(*) FILTER(WHERE fit_eligible),count(DISTINCT molecule_id) FILTER(WHERE fit_eligible) FROM fit_side").fetchone()
    eligible_keys = db.execute("SELECT record_ordinal,geometry_source,geometry_id FROM fit_side WHERE fit_eligible ORDER BY record_ordinal").fetchall()
    if identity(owner) != before:
        raise ValueError("OWNER_INDEX_CHANGED_DURING_SIDE_TABLE_CONSTRUCTION")
    return {"dataset_id": dataset["dataset_id"], "group_index": group["group_index"],
            "owner_index": group["owner_index"], "side_table": pin, "records": n,
            "fit_records": mass[0], "fit_molecules": mass[1], "reason_counts": counts,
            "fit_geometry_key_sha256": semantic_sha(eligible_keys)}


def prepare_sides(db, cfg, ready, root):
    sides, totals = [], {}
    for item in ready:
        ds, plan = item["dataset"], item["plan"]
        rows = [side_table(db, g, ds, root, cfg) for g in plan["groups"]]
        if sum(r["records"] for r in rows) != plan["records"]:
            raise ValueError("FINAL_SOURCE_RECORD_POPULATION_NOT_CONSERVED")
        reasons = collections.Counter()
        for row in rows:
            reasons.update(row["reason_counts"])
        if sum(reasons.values()) != plan["records"]:
            raise ValueError("ELIGIBLE_PLUS_EXCLUDED_RECORD_MASS_NOT_CONSERVED")
        # Molecules may occur in only one latest owner group.
        db.execute("CREATE OR REPLACE VIEW all_sides AS SELECT * FROM read_parquet(" +
                   path_list([r["side_table"]["path"] for r in rows]) + ")")
        n, u, ord_u, mols, lo, hi = db.execute("SELECT count(*),count(DISTINCT record_id),count(DISTINCT record_ordinal),count(DISTINCT molecule_id),min(record_ordinal),max(record_ordinal) FROM all_sides").fetchone()
        if n != u or n != ord_u or n != plan["records"] or mols != plan["molecules"] or (lo, hi) != (0, n-1):
            raise ValueError("CROSS_GROUP_CANONICAL_ID_OR_MOLECULE_MASS_DIFFERS")
        if db.execute("SELECT count(*) FROM (SELECT molecule_id,count(DISTINCT job_id) n FROM all_sides GROUP BY molecule_id HAVING n<>1)").fetchone()[0]:
            raise ValueError("MOLECULE_SPLIT_ACROSS_LATEST_OWNER_GROUPS")
        totals[ds["dataset_id"]] = {"source_records": n, "source_molecules": mols,
            "fit_records": sum(r["fit_records"] for r in rows), "reason_counts": dict(sorted(reasons.items())),
            "fit_molecules": db.execute("SELECT count(DISTINCT molecule_id) FROM all_sides WHERE fit_eligible").fetchone()[0]}
        sides.extend(rows)
    return sides, totals
