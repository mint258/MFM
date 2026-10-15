#!/usr/bin/env python3
"""Full 50k train / 8k validation identity audit; never change either split."""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
import time


# Identity-only CPU work must not initialize or inspect CUDA devices.
os.environ["CUDA_VISIBLE_DEVICES"] = ""
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phychem_mfm.phase1.data import StrictManifestDataset
from phychem_mfm.phase1.identity import IDENTITY_POLICY, identity_from_record
from phychem_mfm.training.checkpoint import source_provenance


DEFAULT_TRAIN_MANIFEST = PROJECT_ROOT / "manifests/discovery_v3_quality/train_50000.json"
DEFAULT_VALIDATION_MANIFEST = PROJECT_ROOT / "manifests/discovery_v3_quality/validation.json"
EXPECTED_COUNTS = {"train": 50000, "validation": 8000}


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


class JsonlLedger:
    def __init__(self, path, stack):
        self.path = path
        self.handle = stack.enter_context(path.open("xb"))
        self.digest = hashlib.sha256()
        self.rows = 0

    def write(self, row):
        encoded = (json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        self.handle.write(encoded)
        self.digest.update(encoded)
        self.rows += 1

    def evidence(self):
        return {"path": str(self.path.resolve()), "sha256": self.digest.hexdigest(), "rows": self.rows}


def selected_structure(record):
    # Match identity_from_record's first nonempty source exactly. Cache the raw
    # string, without stripping or canonicalizing it into a different source.
    for field in ("smiles", "isomeric_smiles", "canonical_smiles"):
        value = getattr(record, field, None)
        if isinstance(value, str) and value.strip():
            return field, value
    return None, None


def audit_full_manifest_identities(train, validation, *, output_dir, max_wall_seconds=840.,
                                   source_metadata, manifest_metadata=None, clock=time.perf_counter):
    """Audit every declared record; return evidence and an explicit process code.

    The CLI additionally requires the fixed 50,000 / 8,000 manifest sources.
    This helper accepts full declared views for focused tests, never subsets.
    """
    if not 0 < float(max_wall_seconds) <= 900:
        raise ValueError("Identity audit wall budget must be positive and at most 900 seconds")
    datasets = {"train": train, "validation": validation}
    for role, dataset in datasets.items():
        if dataset.kind != role or dataset.diagnostic_only or getattr(dataset, "_selection", None) is not None:
            raise ValueError("Identity audit requires complete original train/validation manifests; diagnostic subsets are forbidden")
        if len(dataset) != int(dataset.manifest["unique_structure_count"]):
            raise ValueError("Identity audit view length does not cover its entire declared manifest")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = clock()
    counters = {role: {"expected_records": len(dataset), "attempted_records": 0,
                       "successful_identities": 0, "failed_records": 0}
                for role, dataset in datasets.items()}
    identity_records = {role: defaultdict(list) for role in datasets}
    cache, cache_hits, cache_misses = {}, 0, 0
    wall_exceeded = False
    with ExitStack() as stack:
        ledgers = {role: JsonlLedger(output / f"{role}_identities.jsonl", stack) for role in datasets}
        defects = JsonlLedger(output / "defects.jsonl", stack)
        overlaps = JsonlLedger(output / "overlap.jsonl", stack)
        for role, dataset in datasets.items():
            for logical_index in range(len(dataset)):
                if clock() - started >= max_wall_seconds:
                    wall_exceeded = True
                    break
                shard, real_index = dataset.record_ref(logical_index)
                reference = {"role": role, "logical_index": logical_index, "shard": shard,
                             "real_index": int(real_index), "manifest_pool_hash": dataset.pool_hash}
                counters[role]["attempted_records"] += 1
                try:
                    record = dataset.raw_record(logical_index)
                except Exception as exc:
                    defect = {**reference, "status": "record_read_error", "error_type": type(exc).__name__, "error": str(exc)}
                    ledgers[role].write(defect)
                    defects.write(defect)
                    counters[role]["failed_records"] += 1
                    continue
                field, raw_structure = selected_structure(record)
                cache_key = (field, raw_structure)
                if cache_key in cache:
                    cache_hits += 1
                    identity, failure = cache[cache_key]
                else:
                    cache_misses += 1
                    try:
                        identity = identity_from_record(record)
                        failure = None
                    except Exception as exc:
                        identity = None
                        failure = {"error_type": type(exc).__name__, "error": str(exc)}
                    cache[cache_key] = (identity, failure)
                if failure is not None:
                    defect = {**reference, "status": "identity_parse_error", "source_field": field,
                              "raw_structure": raw_structure, **failure}
                    ledgers[role].write(defect)
                    defects.write(defect)
                    counters[role]["failed_records"] += 1
                    continue
                row = {**reference, "status": "identity_ok", "inchikey": identity.inchikey,
                       "source_field": identity.source_field, "identity_policy": IDENTITY_POLICY}
                ledgers[role].write(row)
                identity_records[role][identity.inchikey].append(
                    {"logical_index": logical_index, "shard": shard, "real_index": int(real_index),
                     "source_field": identity.source_field}
                )
                counters[role]["successful_identities"] += 1
            if wall_exceeded:
                break
        intersection = sorted(set(identity_records["train"]) & set(identity_records["validation"]))
        for key in intersection:
            overlaps.write({"inchikey": key, "identity_policy": IDENTITY_POLICY,
                            "train_record_refs": identity_records["train"][key],
                            "validation_record_refs": identity_records["validation"][key]})
        coverage_complete = all(value["attempted_records"] == value["expected_records"] for value in counters.values())
        identity_complete = coverage_complete and not any(value["failed_records"] for value in counters.values())
        reasons = []
        if wall_exceeded:
            reasons.append("wall_budget_partial_scope")
        if any(value["failed_records"] for value in counters.values()):
            reasons.append("record_or_identity_defects")
        if intersection:
            reasons.append("train_validation_identity_overlap")
        status = "partial_wall_budget" if wall_exceeded else ("failed_defects" if reasons else "passed_full_scope_disjoint")
        for role, value in counters.items():
            value["observed_unique_molecules"] = len(identity_records[role])
            value["full_record_coverage"] = value["attempted_records"] == value["expected_records"]
        summary = {
            "status": status, "exit_code": 3 if wall_exceeded else (2 if reasons else 0),
            "scope": "complete_declared_manifests" if coverage_complete else "partial_declared_manifests",
            "identity_policy": IDENTITY_POLICY, "full_record_coverage": coverage_complete,
            "all_record_identities_resolved": identity_complete, "failure_reasons": reasons,
            "views": counters, "source": dict(source_metadata),
            "manifests": manifest_metadata or {role: dataset.summary() for role, dataset in datasets.items()},
            "observed_identity_intersection_count": len(intersection),
            "full_scope_identity_intersection_count": len(intersection) if identity_complete else None,
            "overlap_train_record_count": sum(len(identity_records["train"][key]) for key in intersection),
            "overlap_validation_record_count": sum(len(identity_records["validation"][key]) for key in intersection),
            "cache": {"policy": "exact_selected_source_field_and_unmodified_raw_string",
                      "hits": cache_hits, "misses": cache_misses, "entries": len(cache)},
            "ledgers": {**{role: ledger.evidence() for role, ledger in ledgers.items()},
                        "defects": defects.evidence(), "overlap": overlaps.evidence()},
            "elapsed_seconds": clock() - started, "max_wall_seconds": float(max_wall_seconds),
            "execution": "CPU identity extraction only; no CUDA calls, targets, normalization or training",
            "source_lmdb_unchanged": True, "split_unchanged": True, "records_reassigned_or_deleted": 0,
            "interpretation": "Only a successful complete audit proves this train/validation identity disjointness; no downstream decontamination claim",
        }
    write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--train-manifest", type=Path, default=DEFAULT_TRAIN_MANIFEST)
    parser.add_argument("--validation-manifest", type=Path, default=DEFAULT_VALIDATION_MANIFEST)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-wall-seconds", type=float, default=840.)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error("Refusing to overwrite an existing identity audit output directory")
    if not 0 < args.max_wall_seconds <= 900:
        parser.error("--max-wall-seconds must be positive and at most 900")
    began = time.perf_counter()
    source = {}
    metadata = {}
    try:
        source = source_provenance(PROJECT_ROOT)
        paths = {"train": args.train_manifest.resolve(), "validation": args.validation_manifest.resolve()}
        required_paths = {"train": DEFAULT_TRAIN_MANIFEST.resolve(), "validation": DEFAULT_VALIDATION_MANIFEST.resolve()}
        if paths != required_paths:
            raise ValueError("This bounded full audit is pinned to the declared train_50000.json and validation.json sources")
        datasets = {}
        for role, path in paths.items():
            metadata[role] = {"path": str(path), "file_sha256": file_sha256(path)}
            dataset = StrictManifestDataset(path, atom_encoding="zero_based", validate_encoding=False)
            if dataset.kind != role or len(dataset) != EXPECTED_COUNTS[role]:
                raise ValueError(f"Expected the full {role} manifest of {EXPECTED_COUNTS[role]} original records")
            datasets[role] = dataset
            metadata[role].update(dataset.summary())
        remaining = args.max_wall_seconds - (time.perf_counter() - began)
        if remaining <= 0:
            raise TimeoutError("Wall budget exhausted before full-manifest record audit initialization")
        summary = audit_full_manifest_identities(datasets["train"], datasets["validation"], output_dir=output,
                  max_wall_seconds=remaining, source_metadata=source, manifest_metadata=metadata)
        summary["total_wall_seconds"] = time.perf_counter() - began
        summary["requested_max_wall_seconds"] = args.max_wall_seconds
        write_json(output / "summary.json", summary)
    except Exception as exc:
        output.mkdir(parents=True, exist_ok=True)
        defect = {"status": "initialization_or_runtime_failure", "error_type": type(exc).__name__, "error": str(exc)}
        write_json(output / "initialization_or_runtime_defect.json", defect)
        summary = {"status": "failed_partial_scope", "exit_code": 2,
                   "scope": "not_a_complete_identity_audit", "full_record_coverage": False,
                   "all_record_identities_resolved": False, "full_scope_identity_intersection_count": None,
                   "source": source, "manifests": metadata, "defect": defect,
                   "total_wall_seconds": time.perf_counter() - began, "requested_max_wall_seconds": args.max_wall_seconds,
                   "source_lmdb_unchanged": True, "split_unchanged": True, "records_reassigned_or_deleted": 0}
        write_json(output / "summary.json", summary)
    print(json.dumps({"status": summary["status"], "exit_code": summary["exit_code"],
                      "output_dir": str(output), "full_record_coverage": summary["full_record_coverage"],
                      "views": summary.get("views"),
                      "observed_identity_intersection_count": summary.get("observed_identity_intersection_count")}, sort_keys=True))
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
