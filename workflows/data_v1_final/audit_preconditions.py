"""Audit small closed metadata; this does not perform dataset completion or scientific computation."""
from __future__ import annotations
import argparse, collections, csv, datetime, hashlib, json, os
from pathlib import Path

def reference(path):
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def audit(root):
    import pyarrow.parquet as pq
    stats = root / "tables/train_pd_stats_v3/all_field_statistics.csv"
    problems = root / "tables/sprime_problem_elements_v4.parquet"
    elements = root / "tables/s_population_marginals_v5/element_presence_marginals.csv"
    alignment = root / "reports/s_sprime_alignment_v4.json"
    paths = (stats, problems, elements, alignment)
    for path in paths:
        if path.stat().st_size > 5_000_000:
            raise RuntimeError("Only small closed metadata permitted: " + str(path))
    with stats.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    active = [r for r in rows if int(r["n"]) > 0 and float(r["std_ddof0"]) > 0]
    group = lambda row: "D" if row["domain"] in {"D", "D20", "D3"} else row["domain"]
    # Expanded xyz/tensor components have scalar_per_record=True, but are not original molecular scalars.
    scalars = collections.Counter(group(r) for r in active if r["main_correlation_eligible"] == "True")
    d_atoms = [r["feature_key"] for r in active if group(r) == "D" and r["level"] == "atom"]
    assert len(rows) == 264 and len(active) == 146
    assert dict(scalars) == {"P": 43, "D": 26}, dict(scalars)
    assert len(d_atoms) == 1 and "SASA_atom_A2" in d_atoms[0]
    with elements.open(encoding="utf-8", newline="") as f:
        erows = list(csv.DictReader(f))
    denominators = {}
    for r in erows:
        if r["atomic_number"] == "34":
            scope = r["population_scope"]
            value = int(r["denominator_element_population_molecules"])
            assert scope not in denominators or denominators[scope] == value
            denominators[scope] = value
    table = pq.read_table(problems)
    se_problems = [r for r in table.to_pylist() if r["atomic_number"] == 34]
    unsupported = collections.Counter()
    for r in se_problems:
        if r["Sprime_status"] == "UFF_UNSUPPORTED":
            unsupported[r["split_role"]] += int(r["molecules"])
    assert set(unsupported) == {"TRAIN", "FULL"}
    unsupported["ALL"] = sum(unsupported.values())
    assert denominators["ALL"] == denominators["TRAIN"] + denominators["FULL"]
    lower_bounds = {scope: {"unavoidable_exclusions": unsupported[scope],
                           "population": denom,
                           "minimum_fraction": unsupported[scope] / denom,
                           "exceeds_20_percent": unsupported[scope] / denom > .20}
                    for scope, denom in sorted(denominators.items())}
    align = json.loads(alignment.read_text(encoding="utf-8"))
    assert all(row["exceeds_20_percent"] for row in lower_bounds.values())
    return {
        "status": "STOP_RULE_CONFLICT_PRECOMPUTATION",
        "sources": [reference(p) for p in paths],
        "labels": {"all_components": len(rows), "nonempty_nonconstant_components": len(active),
                   "original_molecular_scalars_by_group": dict(scalars), "D_atom_fields": d_atoms,
                   "guide_molecular_scalars_by_group": {"P":42, "D":27},
                   "guide_scalar_allocation_matches_source": False},
        "selenium_problem_rows": se_problems,
        "selenium_unavoidable_exclusion_lower_bounds": lower_bounds,
        "existing_role_summary": align["summary"],
        "VAL_in_existing_role_summary": any(r["split_role"] == "VAL" for r in align["summary"]),
        "raw_scientific_data_read": False, "scientific_computation_started": False,
        "limitation": "Lower bounds from closed status aggregates before new retries; not a completed fill result.",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.audit_root)
    result.update(
        observed_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        hostname=os.uname().nodename, uid=os.getuid(), source_script=reference(Path(__file__)),
        supersedes_label_classification="preconditions_v1.json: expanded vector components are not original scalar fields",
    )
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({k: result[k] for k in (
        "status", "labels", "selenium_unavoidable_exclusion_lower_bounds",
        "VAL_in_existing_role_summary", "source_script")}, ensure_ascii=False))
if __name__ == "__main__":
    main()
