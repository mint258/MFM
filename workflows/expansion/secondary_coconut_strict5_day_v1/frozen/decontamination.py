"""Identity-only all-source exclusion index. Pending sources fail closed.

Published old test-only embargo evidence never closes this new all-split gate.
No downstream target values or molecular features are accepted by this module.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from .common import KEY_RE, check_quota, dump_new, external_output, load, reference, require, verify, wp5_key

REQUIRED = {"v1_all_roles_and_embargo", "expansionrx", "som_cyp", "som_az", "qm7", "qm9",
            "tdc_admet", "moleculenet", "marcel_drugs75k", "marcel_kraken", "coconut"}
ALLOWED_IDENTITY_FIELDS = {"source_id", "role", "subdataset", "inchikeys", "non_h_composition"}


def metadata_status(manifest):
    require(manifest.get("schema") == "expansion_decontamination_sources_v1", "Wrong source manifest schema")
    sources = manifest["sources"]
    ids = [s["dataset"] for s in sources]
    require(len(ids) == len(set(ids)) and set(ids) == REQUIRED, "Required decontamination scope changed or duplicated")
    return {"schema": "expansion_decontamination_scope_status_v1", "ready": [s["dataset"] for s in sources if s["status"] == "READY"],
            "pending": [s["dataset"] for s in sources if s["status"] != "READY"],
            "status": "READY" if all(s["status"] == "READY" for s in sources) else "PENDING"}


def validate_ready(manifest):
    status = metadata_status(manifest)
    require(status["status"] == "READY", "PENDING all-source/all-split decontamination: " + ",".join(status["pending"]))
    for source in manifest["sources"]:
        require(source.get("version") and source.get("raw_artifacts"), "Source version and physical raw pins required")
        for ref in source["raw_artifacts"]:
            verify(ref)
        coverage = load(verify(source["coverage_evidence"]))
        require(coverage.get("schema") == "expansion_all_source_identity_coverage_v1" and coverage["dataset"] == source["dataset"],
                "Wrong all-source coverage proof")
        require(coverage["all_splits"] is True and coverage["unresolved_without_identity_or_composition"] == 0,
                "Incomplete all-split identity coverage")
        require(set(coverage["covered_roles"]) == set(source["required_roles"]), "Missing source split roles")
        require(set(coverage["covered_subdatasets"]) == set(source.get("required_subdatasets", [])), "Missing source subdatasets")
        require(coverage["raw_artifacts"] == source["raw_artifacts"] and coverage["identities"] == source["identities"],
                "Coverage proof not bound to these physical raw/identity files")
        require(type(coverage["expected_identity_records"]) is int and coverage["expected_identity_records"] > 0,
                "Missing independently counted complete source size")
        verify(source["identities"])
    return status


def identity_keys(row):
    require(set(row) <= ALLOWED_IDENTITY_FIELDS, "Identity export has unexpected columns; targets/features forbidden")
    require(isinstance(row.get("source_id"), str) and row["source_id"] and row.get("role"), "Source ID and role required")
    keys = row.get("inchikeys", [])
    require(isinstance(keys, list) and len(keys) == len(set(keys)), "Invalid identity list")
    output = []
    for key in keys:
        output.extend((("full", key), ("wp5", wp5_key(key))))
    composition = row.get("non_h_composition")
    if composition is not None:
        require(isinstance(composition, list) and composition and all(isinstance(p, list) and len(p) == 2 and
            type(p[0]) is int and 2 <= p[0] <= 118 and type(p[1]) is int and p[1] > 0 for p in composition),
            "Invalid conservative non-H composition")
        require([p[0] for p in composition] == sorted(set(p[0] for p in composition)), "Composition must have unique sorted elements")
        output.append(("composition", json.dumps(composition, separators=(",", ":"))))
    require(output, "Unresolved identity without conservative composition")
    return output


def build(manifest_path, output, quota_receipt, projected_bytes):
    manifest = load(manifest_path)
    validate_ready(manifest)
    check_quota(quota_receipt, projected_bytes)
    output = external_output(output)
    output.mkdir(parents=True)
    db_path = output / "excluded_identities.sqlite"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT,PRIMARY KEY(kind,key,dataset)) WITHOUT ROWID")
    counts = {}
    try:
        for source in manifest["sources"]:
            coverage = load(source["coverage_evidence"]["path"])
            count, roles, subdatasets = 0, Counter(), Counter()
            with Path(source["identities"]["path"]).open(encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    require(row["role"] in source["required_roles"], "Identity has undeclared source role")
                    require(row.get("subdataset", "") in source.get("required_subdatasets", [""]), "Undeclared subdataset")
                    db.executemany("INSERT OR IGNORE INTO excluded VALUES(?,?,?)", [(kind, key, source["dataset"]) for kind, key in identity_keys(row)])
                    count += 1
                    roles[row["role"]] += 1
                    subdatasets[row.get("subdataset", "")] += 1
                    if count % 10000 == 0:
                        db.commit()
                        require(db_path.stat().st_size <= projected_bytes, "STOP: exclusion-index byte budget exceeded")
            require(count == coverage["expected_identity_records"] == source["identities"]["rows"], "Identity count differs from full-source proof")
            require(set(roles) == set(source["required_roles"]), "Identity file lacks a required split")
            require(set(subdatasets) == set(source.get("required_subdatasets", [""])), "Identity file lacks a required dataset")
            counts[source["dataset"]] = {"records": count, "roles": dict(roles), "subdatasets": dict(subdatasets)}
        db.commit()
    finally:
        db.close()
    require(db_path.stat().st_size <= projected_bytes, "STOP: exclusion-index byte budget exceeded")
    dump_new(output / "receipt.json", {"schema": "expansion_exclusion_index_v1", "status": "COMPLETE",
        "source_manifest": reference(manifest_path), "sources": counts, "database": reference(db_path),
        "identity_policy": ["full_inchikey", "connectivity14_plus_protonation_last_character", "conservative_unresolved_non_h_composition"],
        "targets_consumed": False, "downstream_features_available_for_ranking": False})


def contamination(row, db):
    checks = [("full", row["full_key"]), ("wp5", wp5_key(row["full_key"])), ("composition", row["non_h_composition"])]
    result = set()
    for kind, key in checks:
        result.update((kind, item[0]) for item in db.execute("SELECT dataset FROM excluded WHERE kind=? AND key=?", (kind, key)))
    return sorted(result)


def filter_pool(screen_path, exclusion_path, regression_path, output, quota_receipt, projected_bytes):
    """Apply full-key/WP5/composition exclusions without dropping source evidence."""
    screen, exclusion, regression = map(load, (screen_path, exclusion_path, regression_path))
    require(screen.get("schema") == "pubchem_screen_v1" and screen.get("complete_source") is True,
            "Full pinned PubChem screening required before final decontamination")
    require(exclusion.get("schema") == "expansion_exclusion_index_v1" and exclusion.get("status") == "COMPLETE",
            "Complete all-source exclusion index required")
    require(set(exclusion.get("sources", {})) == REQUIRED, "Exclusion-index source coverage differs")
    require(regression.get("status") == "PASS" and regression.get("agreement", 0) >= .999 and
            regression.get("unexplained_mismatches") == 0 and regression.get("full_v1_selection_regression_passed") is True,
            "Full-v1 input/selection regression still pending")
    source = verify(screen["database"])
    index = verify(exclusion["database"])
    check_quota(quota_receipt, projected_bytes)
    output = external_output(output)
    output.mkdir(parents=True)
    outpath = output / "eligible_candidates.sqlite"
    incoming = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    excluded = sqlite3.connect(index.as_uri() + "?mode=ro", uri=True)
    outgoing = sqlite3.connect(outpath)
    outgoing.execute("CREATE TABLE candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,wp5_key TEXT,features TEXT NOT NULL)")
    counts, examples = Counter(), {}
    try:
        for raw in incoming.execute("SELECT full_key,cid,wp5_key,features FROM candidates ORDER BY full_key"):
            features = json.loads(raw[3])
            hits = contamination(features, excluded)
            counts["input_unique_molecules"] += 1
            if hits:
                counts["excluded_molecules"] += 1
                for kind, dataset in hits:
                    reason = kind + ":" + dataset
                    counts[reason] += 1
                    examples.setdefault(reason, [])
                    if len(examples[reason]) < 20:
                        examples[reason].append({"cid": raw[1], "full_key": raw[0]})
            else:
                outgoing.execute("INSERT INTO candidates VALUES(?,?,?,?)", raw)
                counts["eligible_molecules"] += 1
            if counts["input_unique_molecules"] % 10000 == 0:
                outgoing.commit()
                require(outpath.stat().st_size <= projected_bytes, "STOP: filtered-pool budget exceeded")
        outgoing.commit()
    finally:
        incoming.close()
        excluded.close()
        outgoing.close()
    require(outpath.stat().st_size <= projected_bytes, "STOP: filtered-pool budget exceeded")
    dump_new(output / "receipt.json", {"schema": "expansion_filtered_pool_v1", "status": "COMPLETE",
        "screen": reference(screen_path), "exclusion_index": reference(exclusion_path), "regression": reference(regression_path),
        "all_sources_all_splits_verified": True, "counts": dict(counts), "examples": examples,
        "database": reference(outpath), "source_aliases_preserved_by_reference": screen["database"],
        "downstream_targets_consumed": False})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("metadata-status", "build", "filter"))
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--quota-receipt", type=Path)
    p.add_argument("--projected-output-bytes", type=int)
    p.add_argument("--screen-receipt", type=Path)
    p.add_argument("--exclusion-receipt", type=Path)
    p.add_argument("--regression-receipt", type=Path)
    a = p.parse_args()
    if a.action == "metadata-status":
        print(json.dumps(metadata_status(load(a.manifest)), indent=2))
    else:
        from .common import require_compute
        require_compute()
        require(a.output and a.quota_receipt and a.projected_output_bytes, "Output and quota-reviewed budget required")
        if a.action == "build":
            build(a.manifest, a.output, a.quota_receipt, a.projected_output_bytes)
        else:
            require(a.screen_receipt and a.exclusion_receipt and a.regression_receipt, "Three closed receipts required")
            filter_pool(a.screen_receipt, a.exclusion_receipt, a.regression_receipt, a.output,
                        a.quota_receipt, a.projected_output_bytes)


if __name__ == "__main__":
    main()
