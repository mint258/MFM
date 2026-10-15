"""Filter exact manifest indices using a complete, hash-bound identity audit.

This module neither reads LMDB records nor chooses exclusions. A caller supplies
explicit per-side record references after settling the applicable split policy.
It preserves each parent's order and side and never expands either source pool.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Mapping

from .identity import IDENTITY_POLICY, canonical_hash


VIEW_VERSION = "exact_parent_index_filter_v1"
ROLES = ("train", "validation")
_KEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_STATUSES = {"identity_ok", "identity_parse_error", "record_read_error"}
_SOURCE_FIELDS = {"smiles", "isomeric_smiles", "canonical_smiles"}


def _integer(value, field):
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative JSON integer")
    return value


def _sha(value, field):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"{field} must be a SHA-256 digest")
    return value


def _load_json(value):
    if isinstance(value, Mapping):
        result = copy.deepcopy(dict(value))
        return result, {"content_hash": canonical_hash(result)}
    path = Path(value).resolve()
    raw = path.read_bytes()
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return result, {"path": str(path), "file_sha256": hashlib.sha256(raw).hexdigest(),
                    "content_hash": canonical_hash(result)}


def _ref(value):
    shard = value.get("shard")
    if not isinstance(shard, str) or not shard or "\\" in shard:
        raise ValueError("A record reference needs a nonempty relative POSIX shard path")
    posix, windows = PurePosixPath(shard), PureWindowsPath(shard)
    if not posix.parts or posix.is_absolute() or windows.drive or ".." in posix.parts or str(posix) != shard:
        raise ValueError("Shard reference escapes or aliases its declared data root")
    return shard, _integer(value.get("real_index"), "real_index")


def _validate_parent(manifest, role):
    payload = dict(manifest)
    pool_hash = _sha(payload.pop("pool_hash", None), "parent pool_hash")
    if canonical_hash(payload) != pool_hash:
        raise ValueError(f"{role} parent content hash mismatch")
    if manifest.get("kind") != role or manifest.get("diagnostic_only", False):
        raise ValueError("Filtering requires full original train/validation manifests")
    if not isinstance(manifest.get("data_root"), str) or not manifest["data_root"]:
        raise ValueError("Parent manifest must retain its declared data root")
    if not isinstance(manifest.get("segments"), list) or not manifest["segments"]:
        raise ValueError("Parent manifest requires nonempty segments")
    ranges = defaultdict(list)
    count = 0
    for segment in manifest["segments"]:
        shard, start = _ref({"shard": segment.get("shard"), "real_index": segment.get("start")})
        end = _integer(segment.get("end"), "segment end")
        length = _integer(segment.get("count"), "segment count")
        if end < start or length != end - start + 1:
            raise ValueError("Invalid parent segment count/range")
        ranges[shard].append((start, end))
        count += length
    for intervals in ranges.values():
        ordered = sorted(intervals)
        if any(a[1] >= b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError("Parent manifest contains duplicate or overlapping record references")
    if count != _integer(manifest.get("unique_structure_count"), "parent structure count"):
        raise ValueError("Parent structure count does not match its segments")
    return count


def _ordered_refs(manifest):
    for segment in manifest["segments"]:
        for index in range(segment["start"], segment["end"] + 1):
            yield segment["shard"], index


def _ledger_rows(path, declaration):
    """Hash the exact bytes while validating every JSONL row, including EOF."""
    expected_hash = _sha(declaration.get("sha256"), "ledger sha256")
    expected_rows = _integer(declaration.get("rows"), "ledger row count")
    digest, count = hashlib.sha256(), 0
    with Path(path).open("rb") as stream:
        for line in stream:
            digest.update(line)
            try:
                row = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Identity ledger contains an invalid or blank JSONL row") from exc
            if not isinstance(row, dict):
                raise ValueError("Identity ledger rows must be JSON objects")
            count += 1
            yield row
    if count != expected_rows:
        raise ValueError("Identity ledger row count mismatch")
    if digest.hexdigest() != expected_hash:
        raise ValueError("Identity ledger content hash mismatch")


def _path_for_ledger(summary, name, overrides, summary_origin):
    declaration = summary.get("ledgers", {}).get(name)
    if not isinstance(declaration, dict):
        raise ValueError(f"Missing required identity ledger: {name}")
    declared = overrides.get(name, declaration.get("path"))
    if not declared:
        raise ValueError(f"Missing required identity ledger path: {name}")
    path = Path(declared)
    if not path.is_absolute() and "path" in summary_origin and name not in overrides:
        path = Path(summary_origin["path"]).parent / path
    if not path.is_file():
        raise ValueError(f"Missing identity ledger file: {name}")
    return path.resolve(), declaration


def _validate_audit_parent(summary, manifest, origin, role, count):
    metadata = summary.get("manifests", {}).get(role, {})
    if (metadata.get("kind") != role or metadata.get("pool_hash") != manifest["pool_hash"]
            or metadata.get("diagnostic_only") is not False
            or metadata.get("selected_structure_count") != count
            or metadata.get("source_structure_count") != count
            or metadata.get("identity_policy") != IDENTITY_POLICY):
        raise ValueError(f"Identity audit does not cover this complete {role} parent")
    if "file_sha256" in metadata:
        expected = _sha(metadata["file_sha256"], "audit parent file_sha256")
        if origin.get("file_sha256") != expected:
            raise ValueError("Audit parent file hash differs; provide the original manifest file")
    expected_view = canonical_hash({
        "pool_hash": manifest["pool_hash"], "atom_encoding": metadata.get("atom_encoding"),
        "diagnostic_only": False, "logical_selection": None,
        "reader_policy": "exact_key_no_fallback_v1",
    })
    if metadata.get("atom_encoding") not in {"zero_based", "atomic_number"} or metadata.get("view_hash") != expected_view:
        raise ValueError("Identity audit has an unknown or partial dataset view")
    view = summary.get("views", {}).get(role, {})
    if (view.get("full_record_coverage") is not True or view.get("attempted_records") != count
            or view.get("expected_records") != count):
        raise ValueError("Identity audit has incomplete parent record coverage")


def _filtered_segments(parent, excluded):
    """Split at excluded keys; merge only adjoining, metadata-identical runs."""
    excluded_by_shard = defaultdict(list)
    for shard, index in excluded:
        excluded_by_shard[shard].append(index)
    for indices in excluded_by_shard.values():
        indices.sort()
    output = []

    def append(segment, start, end):
        if end < start:
            return
        item = copy.deepcopy(segment)
        item.update(start=start, end=end, count=end - start + 1)
        metadata = {key: value for key, value in item.items() if key not in {"start", "end", "count"}}
        if output:
            previous = output[-1]
            previous_metadata = {key: value for key, value in previous.items() if key not in {"start", "end", "count"}}
            if previous["end"] + 1 == start and previous_metadata == metadata:
                previous["end"] = end
                previous["count"] += item["count"]
                return
        output.append(item)

    for segment in parent["segments"]:
        start, end = segment["start"], segment["end"]
        for removed in excluded_by_shard.get(segment["shard"], []):
            if start <= removed <= end:
                append(segment, start, removed - 1)
                start = removed + 1
        append(segment, start, end)
    return output


def _domain(shard):
    name = PurePosixPath(shard).name.lower()
    if name.startswith("principal_"):
        return "principal"
    if name.startswith(("unimol_", "molecule_")):
        return "molecule"
    raise ValueError("Cannot recompute existing domain composition for an unknown shard")


def derive_manifest_views(
    train_manifest,
    validation_manifest,
    *,
    audit_summary,
    exclude_refs,
    output_directory,
    ledger_paths: Mapping | None = None,
) -> dict:
    """Generate new manifests after complete validation, without LMDB access.

    Inputs are JSON paths or mappings. ``exclude_refs`` is an explicit mapping
    ``{"train": [{"shard": ..., "real_index": ..., "reason": ...}],
    "validation": [...]}``; no policy is inferred from overlaps or defects.
    Optional ledger-path overrides permit byte-identical evidence relocation.
    The new directory must not exist. Return manifests plus a provenance report.
    """
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite a manifest-view output directory")
    parents, origins, counts = {}, {}, {}
    for role, value in zip(ROLES, (train_manifest, validation_manifest)):
        parents[role], origins[role] = _load_json(value)
        counts[role] = _validate_parent(parents[role], role)
        origins[role]["pool_hash"] = parents[role]["pool_hash"]
    summary, summary_origin = _load_json(audit_summary)
    if (summary.get("scope") != "complete_declared_manifests"
            or summary.get("full_record_coverage") is not True
            or summary.get("identity_policy") != IDENTITY_POLICY
            or summary.get("source_lmdb_unchanged") is not True
            or summary.get("split_unchanged") is not True
            or summary.get("records_reassigned_or_deleted") != 0):
        raise ValueError("A complete immutable-parent identity audit is required")
    exclusions, exclusions_origin = _load_json(exclude_refs)
    if set(exclusions) != set(ROLES):
        raise ValueError("Explicit exclusions must declare exactly train and validation sides")
    excluded = {}
    for role in ROLES:
        _validate_audit_parent(summary, parents[role], origins[role], role, counts[role])
        if not isinstance(exclusions[role], list):
            raise ValueError("Exclusions must be explicit lists of record references")
        references = []
        for item in exclusions[role]:
            if not isinstance(item, dict) or set(item) - {"shard", "real_index", "reason"}:
                raise ValueError("Unknown exclusion fields; roles cannot be changed")
            if "reason" in item and (not isinstance(item["reason"], str) or not item["reason"].strip()):
                raise ValueError("An exclusion reason must be a nonempty string")
            references.append(_ref(item))
        if len(set(references)) != len(references):
            raise ValueError("Duplicate explicit exclusion reference")
        excluded[role] = set(references)
    overrides = dict(ledger_paths or {})
    if set(overrides) - {"train", "validation", "defects", "overlap"}:
        raise ValueError("Unknown ledger-path override")
    ledger_evidence, identities, retained, defects, removed = {}, {}, {}, {}, {}
    domain_counts, domain_keys = {}, {}
    for role in ROLES:
        path, declaration = _path_for_ledger(summary, role, overrides, summary_origin)
        expected_refs = iter(_ordered_refs(parents[role]))
        identities[role], retained[role] = defaultdict(list), set()
        removed[role] = []
        successes = failures = kept = 0
        domain_counts[role], domain_keys[role] = Counter(), defaultdict(set)
        unseen_exclusions = set(excluded[role])
        for logical_index, row in enumerate(_ledger_rows(path, declaration)):
            expected_ref = next(expected_refs, None)
            reference = _ref(row)
            if (expected_ref is None or reference != expected_ref
                    or type(row.get("logical_index")) is not int or row["logical_index"] != logical_index
                    or row.get("role") != role or row.get("manifest_pool_hash") != parents[role]["pool_hash"]):
                raise ValueError("Identity ledger contains a duplicate, unknown, reordered or wrong-parent record reference")
            status = row.get("status")
            if status not in _STATUSES:
                raise ValueError("Identity ledger has an unknown record status")
            is_removed = reference in excluded[role]
            if is_removed:
                unseen_exclusions.remove(reference)
                removed[role].append({"shard": reference[0], "real_index": reference[1],
                                      "parent_logical_index": logical_index, "identity_status": status})
            if status == "identity_ok":
                key = row.get("inchikey")
                if (row.get("identity_policy") != IDENTITY_POLICY or not isinstance(key, str)
                        or not _KEY.fullmatch(key) or row.get("source_field") not in _SOURCE_FIELDS):
                    raise ValueError("Ledger identity must use the complete standard InChIKey and declared source policy")
                successes += 1
                identities[role][key].append({"logical_index": logical_index, "shard": reference[0],
                                              "real_index": reference[1], "source_field": row["source_field"]})
                if not is_removed:
                    retained[role].add(key)
                    kept += 1
                    if "domain_composition" in parents[role]:
                        domain = _domain(reference[0])
                        domain_counts[role][domain] += 1
                        domain_keys[role][domain].add(key)
            else:
                failures += 1
                defects[(role, *reference)] = canonical_hash(row)
                if not is_removed:
                    raise ValueError("Retained record has an unresolved identity or read defect; explicit exclusion is required")
        if next(expected_refs, None) is not None or successes + failures != counts[role]:
            raise ValueError("Identity ledger does not provide complete parent record coverage")
        if unseen_exclusions:
            raise ValueError("Explicit exclusion contains an unknown record reference on this side")
        if not kept:
            raise ValueError("Filtering cannot leave an empty train or validation manifest")
        view = summary["views"][role]
        if (view.get("successful_identities") != successes or view.get("failed_records") != failures
                or view.get("observed_unique_molecules") != len(identities[role])):
            raise ValueError("Audit summary identity counts disagree with its complete ledger")
        ledger_evidence[role] = {"path": str(path), "sha256": declaration["sha256"], "rows": declaration["rows"]}

    path, declaration = _path_for_ledger(summary, "defects", overrides, summary_origin)
    seen_defects = set()
    for row in _ledger_rows(path, declaration):
        reference = (row.get("role"), *_ref(row))
        if reference in seen_defects or defects.get(reference) != canonical_hash(row):
            raise ValueError("Defect ledger does not match the full per-side identity ledger")
        seen_defects.add(reference)
    if seen_defects != set(defects):
        raise ValueError("Defect ledger lacks complete identity-defect coverage")
    ledger_evidence["defects"] = {"path": str(path), "sha256": declaration["sha256"], "rows": declaration["rows"]}
    intersection = set(identities["train"]) & set(identities["validation"])
    path, declaration = _path_for_ledger(summary, "overlap", overrides, summary_origin)
    seen_overlap = set()
    for row in _ledger_rows(path, declaration):
        key = row.get("inchikey")
        if (key not in intersection or key in seen_overlap or row.get("identity_policy") != IDENTITY_POLICY
                or row.get("train_record_refs") != identities["train"][key]
                or row.get("validation_record_refs") != identities["validation"][key]):
            raise ValueError("Overlap ledger does not preserve every overlapping parent record reference")
        seen_overlap.add(key)
    if seen_overlap != intersection or summary.get("observed_identity_intersection_count") != len(intersection):
        raise ValueError("Overlap ledger/summary disagrees with the recomputed full identity intersection")
    for role in ROLES:
        if summary.get(f"overlap_{role}_record_count") != sum(len(identities[role][key]) for key in intersection):
            raise ValueError("Audit summary overlap record counts disagree with the complete ledger")
    identity_complete = not defects
    if (summary.get("all_record_identities_resolved") is not identity_complete
            or summary.get("full_scope_identity_intersection_count") != (len(intersection) if identity_complete else None)):
        raise ValueError("Audit summary completeness claim disagrees with its ledger")
    ledger_evidence["overlap"] = {"path": str(path), "sha256": declaration["sha256"], "rows": declaration["rows"]}
    remaining_overlap = retained["train"] & retained["validation"]
    if remaining_overlap:
        raise ValueError(f"Filtered train/validation still overlap on {len(remaining_overlap)} full InChIKeys")

    binding = {"version": VIEW_VERSION, "identity_policy": IDENTITY_POLICY,
               "parents": origins, "identity_audit": summary_origin,
               "identity_ledgers": ledger_evidence, "explicit_exclusions": exclusions_origin}
    binding_hash = canonical_hash(binding)
    derived, results = {}, {}
    for role in ROLES:
        parent = parents[role]
        child = copy.deepcopy(parent)
        child.pop("pool_hash")
        historical = {key: copy.deepcopy(value) for key, value in parent.items()
                      if key not in {"segments", "records"}}
        child["segments"] = _filtered_segments(parent, excluded[role])
        retained_count = sum(segment["count"] for segment in child["segments"])
        if retained_count != counts[role] - len(excluded[role]):
            raise ValueError("Filtered segment counts do not match the explicit index exclusions")
        child.update(
            pool_id=f"{parent.get('pool_id', role)}__exact_index_view_{binding_hash[:12]}",
            parent_pool_hash=parent["pool_hash"], unique_structure_count=retained_count,
            unique_molecule_count=len(retained[role]), molecule_identity_field=IDENTITY_POLICY,
            selection_rule=VIEW_VERSION,
            parent_molecule_hash=canonical_hash({"parents": sorted(retained[role])}),
        )
        if "records" in parent:
            original_refs = [_ref(row) for row in parent["records"]]
            if len(set(original_refs)) != counts[role] or set(original_refs) != set(_ordered_refs(parent)):
                raise ValueError("Parent optional record index does not cover its exact segments")
            child["records"] = [copy.deepcopy(row) for row, ref in zip(parent["records"], original_refs)
                                if ref not in excluded[role]]
        if "domain_composition" in parent:
            child["domain_composition"] = {
                "structure_counts": dict(sorted(domain_counts[role].items())),
                "structure_ratios": {domain: count / retained_count for domain, count in sorted(domain_counts[role].items())},
                "unique_parent_molecule_counts": {domain: len(keys) for domain, keys in sorted(domain_keys[role].items())},
                "unresolved_parent_structure_count": 0, "identity_policy": IDENTITY_POLICY,
            }
        child["index_filter_provenance"] = {
            "version": VIEW_VERSION, "binding_hash": binding_hash, "binding": copy.deepcopy(binding),
            "parent_metadata": historical, "parent_structure_count": counts[role],
            "excluded_structure_count": len(excluded[role]), "excluded_refs_hash": canonical_hash(exclusions[role]),
            "retained_identity_hash": canonical_hash(sorted(retained[role])),
            "retained_order": "parent_logical_order", "side_unchanged": True,
            "source_lmdb_unchanged": True, "records_reassigned": 0,
            "identity_count_source": "full_hash_bound_identity_ledger",
            "downstream_decontamination": "not_established_by_this_index_filter",
        }
        child["pool_hash"] = canonical_hash(child)
        _validate_parent(child, role)
        derived[role] = child
        results[role] = {
            "filename": f"{role}.json", "parent_pool_hash": parent["pool_hash"],
            "content_hash": child["pool_hash"], "pool_hash": child["pool_hash"],
            "parent_structure_count": counts[role], "retained_structure_count": retained_count,
            "excluded_structure_count": len(excluded[role]), "retained_unique_molecules": len(retained[role]),
            "retained_identity_hash": canonical_hash(sorted(retained[role])), "excluded_refs": removed[role],
        }
    report = {
        "version": VIEW_VERSION, "status": "validated_exact_index_views", "binding": binding,
        "binding_hash": binding_hash, "views": results, "retained_identity_intersection_count": 0,
        "retained_identity_defects": 0, "source_lmdb_unchanged": True, "parent_manifests_unchanged": True,
        "records_reassigned": 0, "records_added": 0,
        "scope": "filtered_complete_declared_parents_only",
        "downstream_decontamination": "not_established_by_this_index_filter",
    }
    report["report_hash"] = canonical_hash(report)
    artifacts = {**{f"{role}.json": derived[role] for role in ROLES},
                 "explicit_exclusions.json": exclusions, "derivation.json": report}
    encoded_artifacts = {name: (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
                                + "\n").encode("utf-8") for name, payload in artifacts.items()}
    # No output directory or files are created until all input checks pass.
    output.mkdir(parents=True, exist_ok=False)
    for filename, encoded in encoded_artifacts.items():
        with (output / filename).open("xb") as stream:
            stream.write(encoded)
    return {"output_directory": str(output), "manifests": derived, "report": report}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--train-manifest", required=True, type=Path)
    parser.add_argument("--validation-manifest", required=True, type=Path)
    parser.add_argument("--identity-audit-summary", required=True, type=Path)
    parser.add_argument("--exclusions", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = derive_manifest_views(args.train_manifest, args.validation_manifest,
                                   audit_summary=args.identity_audit_summary, exclude_refs=args.exclusions,
                                   output_directory=args.output_dir)
    print(json.dumps({"output_directory": result["output_directory"],
                      "binding_hash": result["report"]["binding_hash"],
                      "views": {role: {key: value for key, value in result["report"]["views"][role].items()
                                       if key != "excluded_refs"} for role in ROLES}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
