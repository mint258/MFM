"""Summarize closed screening metadata without reopening molecular data."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import stat


def read_reference(reference):
    path = Path(reference["path"])
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"Not an ordinary closed metadata file: {path}")
    if before.st_size > 2 * 1024 * 1024:
        raise ValueError(f"Metadata exceeds 2 MiB: {path}")
    with path.open("rb") as handle:
        import os
        frame = os.fstat(handle.fileno())
        body = handle.read()
        after = os.fstat(handle.fileno())
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if not signature(before) == signature(frame) == signature(after) == signature(path.lstat()):
        raise ValueError(f"Metadata changed during read: {path}")
    actual = dict(path=str(path), bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    if actual != {k: reference[k] for k in actual}:
        raise ValueError(f"Metadata reference mismatch: {path}")
    return json.loads(body)


def summarize(authority_reference):
    authority = read_reference(authority_reference)
    projection_reference = authority["original_source_projection"]
    projection = read_reference(projection_reference)
    first, overlap, reasons, counts = (Counter() for _ in range(4))
    rows = 0
    fragments = projection["fragments"]
    if len({r["path"] for r in fragments}) != len(fragments):
        raise ValueError("Duplicate fragment metadata references")
    for reference in fragments:
        fragment = read_reference(reference)
        if fragment["scientific_functions_invoked"] or not fragment["technical_UNKNOWN_is_not_chemical_exclusion"]:
            raise ValueError("Unexpected fragment interpretation")
        fc = fragment["chemical_first_rule_counts"]
        oc = fragment["chemical_overlap_rule_counts"]
        for mapping in (fc, oc):
            if set(mapping) - {"X01", "X02", "X03", "X04", "X05"}:
                raise ValueError("Unknown screening rule")
            if any(type(n) is not int or n < 0 for n in mapping.values()):
                raise ValueError("Invalid rule count")
        c = fragment["all_source_counts"]
        if sum(c.values()) != fragment["input_rows"] or sum(fc.values()) != c["chemReject"]:
            raise ValueError("Fragment counts do not conserve source rows")
        if any(oc.get(k, 0) < v for k, v in fc.items()):
            raise ValueError("Overlap count smaller than first rule count")
        first.update(fc)
        overlap.update(oc)
        reasons.update(fragment["technical_reason_counts"])
        counts.update(c)
        rows += fragment["input_rows"]
    if dict(counts) != projection["counts"] or dict(counts) != authority["original_source_counts"]:
        raise ValueError("Original screening counts disagree")
    current = authority["source_counts"]
    if rows != authority["source_rows"] or sum(current.values()) != rows:
        raise ValueError("Corrected source count conservation failed")
    recovered = current["accepted"] - counts["accepted"]
    if (recovered < 0 or recovered != counts["technicalUnresolved"] - current["technicalUnresolved"]
            or current["chemReject"] != counts["chemReject"]):
        raise ValueError("Recovery is not an accepted-only technical disposition")
    return dict(
        schema="PUBCHEM_CLOSED_SCREENING_FUNNEL_V1",
        pool_authority_reference=authority_reference,
        projection_manifest_reference=projection_reference,
        fragment_metadata_references=fragments,
        fragment_count=len(fragments), source_rows=rows,
        original_source_counts=dict(counts), corrected_source_counts=current,
        recovered_original_technical_records=recovered,
        chemical_first_rule_counts={k: first[k] for k in ("X01", "X02", "X03", "X04", "X05")},
        chemical_overlap_rule_counts={k: overlap[k] for k in ("X01", "X02", "X03", "X04", "X05")},
        original_technical_reason_counts=dict(sorted(reasons.items())),
        unique_full_keys=authority["unique_full_keys"],
        duplicate_fullkey_aliases=authority["counts"]["duplicate_fullkey_aliases"],
        first_rule_counts_are_mutually_exclusive=True,
        overlap_rule_counts_are_not_additive=True,
        technical_reasons_may_overlap_and_precede_recovery=True,
        technical_UNKNOWN_is_not_chemical_exclusion=True,
        scientific_data_reopened=False, scientific_functions_invoked=False,
        limitations=["Technical reason counts describe original records before the accepted-only recovery.",
                     "Per-rule survivor denominators are not reconstructed from overlapping technical reasons."],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", required=True, help="JSON file containing a path/bytes/sha256 reference")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reference = json.loads(Path(args.authority).read_text())
    result = summarize(reference)
    body = (json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    with Path(args.output).open("xb") as handle:
        handle.write(body)
    print(json.dumps(dict(path=args.output, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                          source_rows=result["source_rows"], counts=result["corrected_source_counts"],
                          chemical_first_rule_counts=result["chemical_first_rule_counts"])))


if __name__ == "__main__":
    main()
