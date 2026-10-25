"""Read an explicitly pinned, bounded canonical owner manifest and WP5 families.

The manifest must be derived from catalog authority population + latest owners.
It carries the final record roles; this module never invents a VAL assignment.
"""
from __future__ import annotations

import os
from pathlib import Path

from common import OWNER_KEYS, read_json, storage_preflight, verify_reference


def identity(path):
    st = Path(path).stat()
    return (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def load_plan(path):
    plan = read_json(path)
    if plan.get("schema_version") != "v1-label-pilot-plan.1":
        raise ValueError("UNKNOWN_PLAN_VERSION")
    if plan.get("mode") != "pilot" or not 1 <= int(plan.get("max_records", 0)) <= 5000:
        raise ValueError("THIS_READER_IS_BOUNDED_PILOT_ONLY")
    if int(plan.get("workers", 0)) != 16:
        raise ValueError("PILOT_REQUIRES_16_WORKERS")
    allocation = os.environ.get("SLURM_CPUS_PER_TASK")
    if allocation is None or int(allocation) < 16 or "SLURM_JOB_ID" not in os.environ:
        raise ValueError("SCIENTIFIC_PILOT_REQUIRES_OWN_16_CPU_SLURM_ALLOCATION")
    if os.uname().nodename.split(".")[0] != "compute-0-20":
        raise ValueError("LABEL_ANALYSIS_REQUIRES_DEFAULT_COMPUTE20")
    for key in ("registry", "record_manifest", "source_files", "mask_rules", "closed_verification"):
        verify_reference(plan["sources"][key])
    storage_preflight(plan)
    if int(plan["max_output_bytes"]) > int(plan["storage_budget"]["total_declared_new_bytes"]):
        raise ValueError("OUTPUT_BUDGET_EXCEEDS_QUOTA_RESERVATION")
    provenance = plan.get("canonical_provenance", {})
    if (provenance.get("identity_keys") != list(OWNER_KEYS)
            or provenance.get("owner_state") != "COMPLETE"
            or provenance.get("receipt_context_consistent") is not True
            or provenance.get("export_published") is not True):
        raise ValueError("MISSING_CANONICAL_LATEST_OWNER_PROVENANCE")
    for key in ("catalog", "population", "latest_molecules"):
        ref = provenance.get(key, {})
        if not ref.get("path") or not ref.get("sha256") or int(ref.get("bytes", 0)) <= 0:
            raise ValueError("MISSING_CANONICAL_SOURCE_PIN:" + key)
    return plan


def owner_index(plan):
    import pyarrow.parquet as pq
    p = verify_reference(plan["sources"]["record_manifest"])
    table = pq.read_table(p)
    required = set(OWNER_KEYS) | {"lane", "total_atoms", "new_role", "common_population_v1"}
    if not required <= set(table.column_names):
        raise ValueError("OWNER_MANIFEST_COLUMNS_MISSING:" + str(sorted(required - set(table.column_names))))
    if not 1 <= table.num_rows <= int(plan["max_records"]):
        raise ValueError("OWNER_MANIFEST_EXCEEDS_BOUNDED_RECORD_COUNT")
    result = {}
    for row in table.to_pylist():
        if row["record_id"] in result:
            raise ValueError("DUPLICATE_CANONICAL_RECORD")
        row["new_role"] = row["new_role"].upper()
        if row["new_role"] not in {"TRAIN", "VAL", "FULL", "EMBARGO"}:
            raise ValueError("INVALID_FROZEN_RECORD_ROLE")
        if type(row["common_population_v1"]) is not bool or int(row["total_atoms"]) <= 0:
            raise ValueError("INVALID_COMMON_POPULATION_OR_ATOM_COUNT")
        numbers = row.get("atomic_numbers")
        if numbers is not None and (len(numbers) != row["total_atoms"] or any(type(z) is not int or not 1 <= z <= 118 for z in numbers)):
            raise ValueError("ATOMIC_NUMBERS_DO_NOT_MATCH_OWNER_RECORD")
        result[row["record_id"]] = row
    return result


def source_jobs(plan, owners):
    rows = read_json(verify_reference(plan["sources"]["source_files"]))
    if not isinstance(rows, list):
        raise ValueError("SOURCE_FILES_MUST_BE_CANONICAL_CATALOG_PROJECTION")
    seen = set()
    wanted_jobs = {int(row["job_id"]) for row in owners.values()}
    tasks = []
    enabled = read_json(verify_reference(plan["sources"]["registry"]))["fields"]
    families = {f["family_source"] for f in enabled if f["status"] == "enabled"}
    for ref in rows:
        if ref["path"] in seen:
            raise ValueError("DUPLICATE_SOURCE_FILE_PATH")
        seen.add(ref["path"])
        if ref["family"] not in families or int(ref["source_job_id"]) not in wanted_jobs:
            continue
        if ref.get("inherited_full_readback_verified") is not True or len(ref.get("sha256", "")) != 64:
            raise ValueError("SOURCE_FILE_NOT_BOUND_TO_CLOSED_READBACK")
        verify_reference(ref, content=False)
        tasks.append(ref)
    if not tasks:
        raise ValueError("NO_CANONICAL_SOURCE_FILES")
    return tasks


def iter_canonical_file(ref, owners, batch_size=16):
    import pyarrow.parquet as pq
    p = verify_reference(ref, content=False)
    before = identity(p)
    family = ref["family"]
    columns = list(OWNER_KEYS) + ["status"]
    if family == "D20":
        columns += ["values_float64", "valid_mask", "descriptor_names"]
    elif family == "D3":
        columns += ["PMI1", "PMI2", "PMI3", "PBF_A", "volume_A3", "SASA_total_A2", "SASA_atom_A2", "issues"]
    else:
        columns += ["calc_type", "lane", "total_atoms", "values", "numeric_issues", "converged", "scf_iterations", "precision_by_field_json", "source_status", "failure_code"]
    for batch in pq.ParquetFile(p).iter_batches(batch_size=batch_size, columns=columns, use_threads=False):
        for row in batch.to_pylist():
            owner = owners.get(row["record_id"])
            if owner is None or any(row[k] != owner[k] for k in OWNER_KEYS):
                continue
            if int(row["job_id"]) != int(ref["source_job_id"]):
                raise ValueError("SOURCE_JOB_MAPPING_DIFFERS_FROM_ROW")
            if family not in ("D20", "D3") and row["lane"] != owner["lane"]:
                raise ValueError("CANONICAL_LATEST_LANE_DIFFERS")
            if "total_atoms" in row and int(row["total_atoms"]) != int(owner["total_atoms"]):
                raise ValueError("SOURCE_TOTAL_ATOMS_DIFFERS")
            row["total_atoms"] = owner["total_atoms"]
            row["calc_type"] = row.get("calc_type", family)
            row["new_role"] = owner["new_role"]
            row["common_population_v1"] = owner["common_population_v1"]
            row["atomic_numbers"] = owner.get("atomic_numbers")
            yield row
    if identity(p) != before:
        raise ValueError("SOURCE_FILE_IDENTITY_CHANGED_DURING_READ")
