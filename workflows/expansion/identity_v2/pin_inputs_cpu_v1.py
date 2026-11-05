"""Compute-only physical pins, identity-column counts and source schema facts.

Whole-file SHA consumes opaque bytes. CSV conversion materializes only the
identity/role column allowlist. SDF properties and JSONL records are not decoded;
MAT exposes variable metadata only, never X/T/R values. This is not an all-source
decontamination acceptance or identity export.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import tarfile
import threading
import time

from .. import common, download_raw_v1 as quota_source, source as network_source
from ..common import ARTIFACT_ROOT, check_quota, dump_new, load, reference, require, verify
from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime as cpu_runtime

CSV_IDENTITY_NAMES = {"source_id", "record_id", "sample_id", "sample_uid", "molecule_id", "compound_id", "compound id",
                      "molecule name", "id", "cid", "num", "name", "cmpd_chemblid", "smiles", "smiles_isomeric",
                      "smiles_canonical", "canonical_smiles", "isomeric_smiles", "mol", "inchikey", "inchi_key", "inchi",
                      "fold", "split", "role", "dataset", "source_sdf", "source_file", "source_record_1based", "xyz_path"}


def physical_stat(path):
    s = Path(path).stat()
    return {"device": s.st_dev, "inode": s.st_ino, "size": s.st_size, "mtime_ns": s.st_mtime_ns, "uid": s.st_uid}


def describe_identity_source(item):
    cpu_runtime.checkpoint()
    path, kind = Path(item["path"]), item["kind"]
    result = {"kind": kind, "targets_or_features_materialized": False}
    if kind == "parquet":
        import pyarrow.parquet as pq
        p = pq.ParquetFile(path)
        result.update(records=p.metadata.num_rows, row_groups=p.metadata.num_row_groups,
                      column_names=p.schema_arrow.names, count_basis="Parquet physical-row footer; no value pages opened")
    elif kind in ("csv", "csv_gz"):
        opener = gzip.open if kind == "csv_gz" else open
        with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
            names = next(csv.reader(stream))
        require(names and len(names) == len(set(names)), "Missing or duplicate CSV header columns")
        selected = [n for n in names if n.casefold() in CSV_IDENTITY_NAMES]
        require(selected, "No approved identity/role column found; do not select target/feature columns to count records")
        import pyarrow as pa
        import pyarrow.csv as pc
        counts, missing = 0, {k: 0 for k in selected}
        with pc.open_csv(str(path), read_options=pc.ReadOptions(use_threads=False, block_size=1 << 20),
                         parse_options=pc.ParseOptions(newlines_in_values=True),
                         convert_options=pc.ConvertOptions(include_columns=selected,
                             column_types={k: pa.string() for k in selected})) as stream:
            for batch in stream:
                cpu_runtime.checkpoint()
                counts += batch.num_rows
                for k in selected:
                    missing[k] += batch.column(batch.schema.get_field_index(k)).null_count
        result.update(records=counts, column_names=names, materialized_columns=selected, null_cells_by_identity_column=missing,
                      count_basis="Streaming CSV count of identity/role projection, without label filtering")
    elif kind in ("sdf", "jsonl_opaque"):
        count = 0
        with path.open("rb") as stream:
            for line in stream:
                cpu_runtime.checkpoint()
                count += int(line.rstrip(b"\r\n") == b"$$$$") if kind == "sdf" else int(bool(line.strip()))
        result.update(records=count, count_basis="Opaque SDF record delimiters" if kind == "sdf" else "Opaque nonempty JSONL line boundaries",
                      sdf_properties_decoded=False, jsonl_value_objects_decoded=False)
    elif kind == "mat_Z_metadata":
        from scipy.io import whosmat
        inventory = [{"name": n, "shape": list(shape), "class": c} for n, shape, c in whosmat(path)]
        z = [r for r in inventory if r["name"] == "Z"]
        require(len(z) == 1 and len(z[0]["shape"]) == 2, "Original QM7 Z array metadata missing or ambiguous")
        result.update(records=z[0]["shape"][0], variable_inventory_metadata_only=inventory,
                      loaded_numeric_value_variables=[], count_basis="Original MAT Z first dimension; X/T/R not loaded")
    elif kind == "qm9_tar_metadata":
        identifiers, files, other = set(), 0, 0
        with tarfile.open(path, mode="r|*") as archive:
            for member in archive:
                cpu_runtime.checkpoint()
                if not member.isfile():
                    continue
                match = re.fullmatch(r"dsgdb9nsd_(\d{6})\.xyz", Path(member.name).name)
                if match:
                    identifier = int(match.group(1))
                    require(identifier not in identifiers, "Duplicate original QM9 archive source ID")
                    identifiers.add(identifier); files += 1
                else:
                    other += 1
        require(identifiers == set(range(1, 133886)), "QM9 archive is not the complete original133885 source ID set")
        result.update(records=files, unique_original_ids=len(identifiers), other_regular_members=other,
                      source_payloads_decoded=False, count_basis="Original archive member headers/ID range only")
    elif kind == "metadata_json":
        require(path.name in ("download_manifest.json", ".exported_from_qm7_mat.json") and path.stat().st_size <= 8 * 1024 ** 2,
                "Only declared small download/export provenance metadata may be decoded")
        data = load(path)
        allowed = ("dataset", "format", "files", "status", "source_url", "source_mat", "n_xyz", "created_at_utc", "updated_at_utc")
        result.update(records=None, version_metadata={k: data[k] for k in allowed if k in data},
                      count_basis="Small version/download provenance metadata only")
    else:
        raise ValueError("Unreviewed identity-only source kind: " + kind)
    expected = item.get("expected_records")
    if expected is not None:
        require(result["records"] == expected, "Independent physical record count differs for " + item["source_id"])
    return result


def pin_one(item):
    cpu_runtime.checkpoint()
    started = time.monotonic()
    result = {"source_id": item["source_id"], "dataset": item["dataset"], "kind": item["kind"],
              "scope_role": item["scope_role"], "required": item["required"], "path": item["path"],
              "worker_thread_id": threading.get_native_id()}
    path = Path(item["path"])
    try:
        require(path.is_absolute() and any(path.is_relative_to(root) for root in
                (Path("/share/home/zixiao/descriptor_analysis"), Path("/share/home/zixiao/benchmark_dataset"))),
                "Source path is outside the specifically reviewed project/benchmark roots")
        if not path.is_file():
            result.update(status="PENDING_PHYSICAL_PATH_MISSING", seconds=time.monotonic() - started)
            return result
        before = physical_stat(path)
        if item.get("expected_bytes") is not None:
            require(before["size"] == item["expected_bytes"], "Known historical source byte count changed")
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                cpu_runtime.checkpoint()
                h.update(block)
        digest = h.hexdigest()
        if item.get("expected_sha256") is not None:
            require(digest == item["expected_sha256"], "Known historical source SHA changed")
        metadata = describe_identity_source(item)
        after = physical_stat(path)
        require(before == after, "Source physical identity changed during current SHA/count/probe")
        result.update(status="CURRENT_BYTES_SHA_AND_IDENTITY_METADATA_PINNED",
                      reference={"path": str(path), "bytes": before["size"], "sha256": digest},
                      before=before, after=after, stable_file_identity={"dev": after["device"], "ino": after["inode"], "mtime_ns": after["mtime_ns"]},
                      identity_metadata=metadata, seconds=time.monotonic() - started)
    except Exception as exc:
        result.update(status="STOP_SOURCE_PIN_OR_IDENTITY_METADATA_ERROR", error_type=type(exc).__name__, error=str(exc),
                      seconds=time.monotonic() - started)
    return result


def run(plan_path, intent_path):
    node = socket.gethostname().split(".")[0]
    require(node in {"compute-0-2", *(f"compute-0-{i}" for i in range(8, 20))} and os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID", "").isdecimal() and
            int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16, "Actual reviewed CPU-only zixiao16CPU Slurm allocation required")
    plan, intent = load(plan_path), load(intent_path)
    require(plan["schema"] == "identity_only_physical_input_pin_cpu_plan_v1" and plan["status"] == "READY" and
            plan["workers"] == 16 and plan["peak_output_cap_bytes"] == 32 * 1024 ** 2, "Root-bound READY input-pin plan required")
    request = intent["request"]
    require(intent["uid"] == 1278 and request["root_review"]["status"] == "APPROVED" and request["root_review"]["reviewer"] == "root" and
            request["node"] == node and request["cpus"] == 16 and request["memory_gib"] == 4 and
            request["pilot"] is True and request["partition"] == "cpu" and request["scope_key"] == "identity_source_pins_76" and
            request["resource_policy"] == "CPU_BOUNDED_TEST_LIVE_MEMORY_V1" and
            0 < request["wall_seconds"] <= 3600 and request["estimated_peak_output_bytes"] == plan["peak_output_cap_bytes"] + 32 * 1024 ** 2,
            "Root physical-input pin resources/scope differ")
    catalog = load(verify(plan["source_catalog"]))
    require(catalog["schema"] == "expansion_identity_source_locator_catalog_v2", "Wrong isolated source locator catalog")
    needed = [reference(plan_path), plan["source_catalog"], plan["cpu_decision_reference"], plan["central_runtime_reference"],
              *plan["code_sources"], *catalog["metadata_authorities"]]
    declared = {r["path"]: r for r in request["source_references"]}
    require(all(declared.get(r["path"]) == r for r in needed), "Root did not bind source catalog/code/historical locator metadata")
    for ref in [*plan["code_sources"], *catalog["metadata_authorities"]]:
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, common.__file__, quota_source.__file__, network_source.__file__, cpu_runtime.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Actual input-pin import chain not pinned")
    ids = [r["source_id"] for r in catalog["inputs"]]
    require(len(ids) == len(set(ids)) == 76, "Exactly the original76 distinct input tasks required for CPU sourcepin16")
    cpu_proof = cpu_runtime.root_guard(intent_path, plan_path, plan["peak_output_cap_bytes"], wall_limit=3600)
    cpu_runtime.checkpoint()
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "identity") and not out.exists(), "Fresh identity-input pin output required")
    out.mkdir(parents=True)
    started = time.monotonic()
    quota_source.acquire_fresh_quota(plan["quota"], out / "quota_start.json")
    check_quota(out / "quota_start.json", request["estimated_peak_output_bytes"])
    cpu_runtime.checkpoint()
    barrier = threading.Barrier(16)
    with ThreadPoolExecutor(max_workers=16, initializer=lambda: barrier.wait(timeout=180)) as pool:
        outputs = list(pool.map(pin_one, catalog["inputs"]))
    stop = [r for r in outputs if r["status"].startswith("STOP_") or (r["required"] and r["status"] == "PENDING_PHYSICAL_PATH_MISSING")]
    pending = [r["source_id"] for r in outputs if r["status"] == "PENDING_PHYSICAL_PATH_MISSING"]
    worker_ids = sorted({r["worker_thread_id"] for r in outputs})
    workers_ok = len(worker_ids) == 16
    report = {"schema": "identity_only_current_physical_input_pins_cpu_v1", "status": "STOP_REQUIRED_SOURCE_PIN_FAILURE" if stop or not workers_ok else
              "CURRENT_INPUT_PINS_COMPLETE_WITH_PENDING_LOCATORS" if pending else "CURRENT_BOUND_INPUT_PINS_COMPLETE",
              "node": node, "uid": os.getuid(), "job_id": os.environ["SLURM_JOB_ID"], "plan": reference(plan_path),
              "root_submission": reference(intent_path), "source_catalog": plan["source_catalog"], "outputs": outputs,
              "pending_locators": pending, "blocking_source_ids": [r["source_id"] for r in stop] + ([] if workers_ok else ["ACTUAL_THREAD16_COVERAGE"]),
              "opaque_body_hashing_performed": True, "identity_or_role_columns_only": True,
              "target_or_feature_values_materialized": False, "identity_export_completed": False,
              "all_source_all_split_decontamination_accepted": False, "wall_seconds": time.monotonic() - started,
              "worker_thread_ids_observed": worker_ids, "cpu_runtime_proof": cpu_proof}
    cpu_runtime.checkpoint()
    dump_new(out / "receipt.json", report)
    require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= plan["peak_output_cap_bytes"], "Input-pin receipt output cap exceeded")
    require(not stop, "STOP: required source input missing, changed or failed identity-only metadata count")
    require(workers_ok, "Sourcepin16 actual independent worker coverage missing")
    print(json.dumps({"status": report["status"], "receipt": reference(out / "receipt.json")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-submit-intent", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
