"""Exact-index filtering preserves split membership and rejects weak evidence."""
from __future__ import annotations

from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path

import pytest

from phychem_mfm.phase1.data import StrictManifestDataset
from phychem_mfm.phase1.identity import IDENTITY_POLICY, canonical_hash
from phychem_mfm.phase1.manifest_views import derive_manifest_views


ETHANOL = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
ETHANE = "OTMSDBZUPAUEDD-UHFFFAOYSA-N"
WATER = "XLYOFNOQVPJJNP-UHFFFAOYSA-N"
BENZENE = "UHOVQNZJYSORNB-UHFFFAOYSA-N"
CO2 = "CURLTUGMZLYLDI-UHFFFAOYSA-N"
METHANE = "VNWKTOKETHGBQD-UHFFFAOYSA-N"
PRINCIPAL = "principal_fixture.lmdb"
MOLECULE = "unimol_fixture.lmdb"


def _write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_ledger(path, rows):
    raw = b"".join((json.dumps(row, sort_keys=True) + "\n").encode("utf-8") for row in rows)
    path.write_bytes(raw)
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows)}


def _parent(root, role, ranges):
    segments = []
    refs = []
    for shard, start, end in ranges:
        stat = (root / shard).stat()
        segments.append({"shard": shard, "start": start, "end": end, "count": end - start + 1,
                         "source_size": stat.st_size, "source_mtime_ns": stat.st_mtime_ns,
                         "source_note": "immutable_original_metadata"})
        refs.extend((shard, index) for index in range(start, end + 1))
    payload = {
        "format_version": 1, "pool_id": f"fixture_{role}", "kind": role, "data_root": str(root),
        "segments": segments, "unique_structure_count": len(refs), "unique_molecule_count": 999,
        "parent_pool_hash": "b" * 64, "parent_molecule_hash": "c" * 64,
        "molecule_identity_field": "historical_source_prefixed_smiles",
        "selection_rule": "historical_unmodified", "filter_max_atoms": 196,
        "data_quality_policy_hash": "a" * 64, "data_quality_protocol_version": "quality_fixture",
        "quality_scan_counts_for_build": {"raw_scanned": 100, "quality_quarantined": 5},
        "domain_protocol_version": "domain-matched-v3.1",
        "domain_composition": {"structure_counts": {"historical": len(refs)},
                               "unique_parent_molecule_counts": {"historical": 999}},
        "raw_scanned_count": 100, "filtered_out_structure_count": 5,
        "records": [{"shard": shard, "real_index": index, "structure_id": f"s{index}",
                     "parent_molecule_id": f"source_prefixed:{index}"} for shard, index in refs],
    }
    payload["pool_hash"] = canonical_hash(payload)
    return payload, refs


def _fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    # Constructor-only StrictManifestDataset validation does not open LMDB.
    for name in (PRINCIPAL, MOLECULE):
        (source / name).write_bytes(b"immutable-source-stat-fixture")
    parents, refs, paths, rows = {}, {}, {}, {}
    ranges = {
        "train": [(PRINCIPAL, 10, 13), (PRINCIPAL, 14, 15), (MOLECULE, 7, 8), (PRINCIPAL, 2, 3)],
        "validation": [(PRINCIPAL, 50, 52), (MOLECULE, 90, 90)],
    }
    identities = {
        "train": [ETHANOL, ETHANE, ETHANOL, ETHANE, BENZENE, BENZENE, ETHANOL, WATER, BENZENE, BENZENE],
        "validation": [ETHANOL, CO2, None, METHANE],
    }
    for role in ("train", "validation"):
        parents[role], refs[role] = _parent(source, role, ranges[role])
        paths[role] = tmp_path / f"parent_{role}.json"
        _write_json(paths[role], parents[role])
        rows[role] = []
        for logical, ((shard, index), key) in enumerate(zip(refs[role], identities[role])):
            row = {"role": role, "logical_index": logical, "shard": shard, "real_index": index,
                   "manifest_pool_hash": parents[role]["pool_hash"], "source_field": "smiles"}
            if key is None:
                row.update(status="identity_parse_error", error_type="MoleculeIdentityError",
                           error="unparseable structure fixture", raw_structure="invalid_fixture")
            else:
                row.update(status="identity_ok", inchikey=key, identity_policy=IDENTITY_POLICY)
            rows[role].append(row)
    fixture = {"parents": parents, "parent_paths": paths, "refs": refs, "rows": rows,
               "root": tmp_path, "summary_path": tmp_path / "summary.json",
               "output": tmp_path / "derived",
               "exclusions": {
                   "train": [{"shard": PRINCIPAL, "real_index": 10, "reason": "explicit overlap policy"},
                             {"shard": PRINCIPAL, "real_index": 12},
                             {"shard": MOLECULE, "real_index": 7}],
                   "validation": [{"shard": PRINCIPAL, "real_index": 52, "reason": "explicit quarantine"}],
               }}
    _rebuild_audit(fixture)
    return fixture


def _rebuild_audit(fixture):
    """Build complete evidence from fixture rows, without chemical recomputation."""
    ledgers, groups, views, metadata = {}, {}, {}, {}
    defects = []
    for role in ("train", "validation"):
        rows = fixture["rows"][role]
        parent, path = fixture["parents"][role], fixture["parent_paths"][role]
        ledgers[role] = _write_ledger(fixture["root"] / f"{role}_identities.jsonl", rows)
        groups[role] = defaultdict(list)
        for row in rows:
            if row["status"] == "identity_ok":
                groups[role][row["inchikey"]].append({key: row[key] for key in
                                                       ("logical_index", "shard", "real_index", "source_field")})
            else:
                defects.append(row)
        failed = sum(row["status"] != "identity_ok" for row in rows)
        expected = parent["unique_structure_count"]
        views[role] = {"expected_records": expected, "attempted_records": len(rows),
                       "successful_identities": len(rows) - failed, "failed_records": failed,
                       "observed_unique_molecules": len(groups[role]), "full_record_coverage": len(rows) == expected}
        metadata[role] = {
            "path": str(path), "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "kind": role, "pool_hash": parent["pool_hash"], "diagnostic_only": False,
            "selected_structure_count": expected, "source_structure_count": expected,
            "atom_encoding": "zero_based", "identity_policy": IDENTITY_POLICY,
            "view_hash": canonical_hash({"pool_hash": parent["pool_hash"], "atom_encoding": "zero_based",
                                         "diagnostic_only": False, "logical_selection": None,
                                         "reader_policy": "exact_key_no_fallback_v1"}),
        }
    intersection = sorted(set(groups["train"]) & set(groups["validation"]))
    overlap = [{"inchikey": key, "identity_policy": IDENTITY_POLICY,
                "train_record_refs": groups["train"][key], "validation_record_refs": groups["validation"][key]}
               for key in intersection]
    ledgers["defects"] = _write_ledger(fixture["root"] / "defects.jsonl", defects)
    ledgers["overlap"] = _write_ledger(fixture["root"] / "overlap.jsonl", overlap)
    summary = {
        "scope": "complete_declared_manifests", "full_record_coverage": True,
        "identity_policy": IDENTITY_POLICY, "source_lmdb_unchanged": True,
        "split_unchanged": True, "records_reassigned_or_deleted": 0,
        "manifests": metadata, "views": views, "ledgers": ledgers,
        "observed_identity_intersection_count": len(intersection),
        "full_scope_identity_intersection_count": None if defects else len(intersection),
        "all_record_identities_resolved": not defects,
        "overlap_train_record_count": sum(len(groups["train"][key]) for key in intersection),
        "overlap_validation_record_count": sum(len(groups["validation"][key]) for key in intersection),
    }
    fixture["summary"] = summary
    _write_json(fixture["summary_path"], summary)


def _derive(fixture, **changes):
    kwargs = {"audit_summary": fixture["summary_path"], "exclude_refs": fixture["exclusions"],
              "output_directory": fixture["output"]}
    kwargs.update(changes)
    return derive_manifest_views(fixture["parent_paths"]["train"], fixture["parent_paths"]["validation"], **kwargs)


def test_filter_preserves_order_split_source_metadata_and_recomputes_fullkey_counts(tmp_path):
    fixture = _fixture(tmp_path)
    original_bytes = {role: path.read_bytes() for role, path in fixture["parent_paths"].items()}
    fixture["exclusions"]["train"].append({"shard": PRINCIPAL, "real_index": 14, "reason": "explicit fixture exclusion"})
    result = _derive(fixture)
    expected_train = [(PRINCIPAL, 11), (PRINCIPAL, 13), (PRINCIPAL, 15),
                      (MOLECULE, 8), (PRINCIPAL, 2), (PRINCIPAL, 3)]
    expected_validation = [(PRINCIPAL, 50), (PRINCIPAL, 51), (MOLECULE, 90)]
    for role, expected in (("train", expected_train), ("validation", expected_validation)):
        child = result["manifests"][role]
        dataset = StrictManifestDataset(fixture["output"] / f"{role}.json", validate_encoding=False)
        assert [dataset.record_ref(index) for index in range(len(dataset))] == expected
        assert child["kind"] == role and child["data_root"] == fixture["parents"][role]["data_root"]
        assert child["unique_structure_count"] == len(expected)
        assert child["unique_molecule_count"] == 3  # full keys, not old source-prefix count 999
        assert child["data_quality_policy_hash"] == "a" * 64
        assert child["quality_scan_counts_for_build"] == {"raw_scanned": 100, "quality_quarantined": 5}
        history = child["index_filter_provenance"]["parent_metadata"]
        assert history["parent_pool_hash"] == "b" * 64
        assert history["unique_molecule_count"] == 999
        assert history["pool_hash"] == fixture["parents"][role]["pool_hash"]
        for segment in child["segments"]:
            assert segment["source_note"] == "immutable_original_metadata"
            stat = (Path(child["data_root"]) / segment["shard"]).stat()
            assert segment["source_size"] == stat.st_size and segment["source_mtime_ns"] == stat.st_mtime_ns
        assert len(child["records"]) == len(expected)
        assert child["pool_hash"] == canonical_hash({key: value for key, value in child.items() if key != "pool_hash"})
        assert result["report"]["views"][role]["content_hash"] == dataset.pool_hash
        assert fixture["parent_paths"][role].read_bytes() == original_bytes[role]
    composition = result["manifests"]["train"]["domain_composition"]
    assert composition["structure_counts"] == {"molecule": 1, "principal": 5}
    assert composition["unique_parent_molecule_counts"] == {"molecule": 1, "principal": 2}
    assert result["report"]["records_added"] == result["report"]["records_reassigned"] == 0
    assert result["report"]["retained_identity_intersection_count"] == 0
    assert result["report"]["retained_identity_defects"] == 0
    assert result["report"]["downstream_decontamination"].startswith("not_established")


def test_segment_merge_only_joins_adjacent_retained_records_in_existing_order(tmp_path):
    fixture = _fixture(tmp_path)
    child = _derive(fixture)["manifests"]["train"]
    assert [(row["shard"], row["start"], row["end"]) for row in child["segments"]] == [
        (PRINCIPAL, 11, 11), (PRINCIPAL, 13, 15), (MOLECULE, 8, 8), (PRINCIPAL, 2, 3),
    ]


def test_metadata_incompatibility_prevents_merging_adjacent_segments(tmp_path):
    fixture = _fixture(tmp_path)
    parent = fixture["parents"]["train"]
    parent["segments"][1]["source_note"] = "different_retained_source_metadata"
    parent.pop("pool_hash")
    parent["pool_hash"] = canonical_hash(parent)
    _write_json(fixture["parent_paths"]["train"], parent)
    for row in fixture["rows"]["train"]:
        row["manifest_pool_hash"] = parent["pool_hash"]
    _rebuild_audit(fixture)
    child = _derive(fixture)["manifests"]["train"]
    assert [(row["shard"], row["start"], row["end"]) for row in child["segments"]] == [
        (PRINCIPAL, 11, 11), (PRINCIPAL, 13, 13), (PRINCIPAL, 14, 15),
        (MOLECULE, 8, 8), (PRINCIPAL, 2, 3),
    ]
    assert child["segments"][2]["source_note"] == "different_retained_source_metadata"


@pytest.mark.parametrize("mutation,match", [
    ("unknown_exclusion", "unknown record"),
    ("duplicate_exclusion", "Duplicate"),
    ("wrong_side", "unknown record"),
    ("retained_parse_error", "unresolved identity"),
    ("retained_overlap", "still overlap"),
    ("partial_summary", "complete immutable-parent"),
    ("missing_ledger", "Missing identity ledger"),
    ("hash_tamper", "content hash mismatch"),
    ("unknown_ref", "unknown, reordered"),
    ("duplicate_row", "unknown, reordered"),
    ("missing_row", "complete parent record coverage"),
    ("partial_view", "unknown or partial"),
    ("parent_hash", "parent content hash mismatch"),
    ("parent_file_bytes", "parent file hash differs"),
    ("missing_defects", "complete identity-defect coverage"),
    ("incomplete_overlap_refs", "every overlapping"),
])
def test_invalid_scope_or_identity_evidence_fails_without_creating_outputs(tmp_path, mutation, match):
    fixture = _fixture(tmp_path)
    if mutation == "unknown_exclusion":
        fixture["exclusions"]["train"].append({"shard": PRINCIPAL, "real_index": 9999})
    elif mutation == "duplicate_exclusion":
        fixture["exclusions"]["train"].append(copy.deepcopy(fixture["exclusions"]["train"][0]))
    elif mutation == "wrong_side":
        fixture["exclusions"]["train"].append({"shard": PRINCIPAL, "real_index": 52})
    elif mutation == "retained_parse_error":
        fixture["exclusions"]["validation"] = []
    elif mutation == "retained_overlap":
        fixture["exclusions"]["train"] = fixture["exclusions"]["train"][:-1]
    elif mutation == "partial_summary":
        fixture["summary"]["full_record_coverage"] = False
    elif mutation == "missing_ledger":
        Path(fixture["summary"]["ledgers"]["train"]["path"]).unlink()
    elif mutation == "hash_tamper":
        path = Path(fixture["summary"]["ledgers"]["train"]["path"])
        path.write_bytes(path.read_bytes().replace(ETHANE.encode(), BENZENE.encode(), 1))
    elif mutation in {"unknown_ref", "duplicate_row", "missing_row"}:
        if mutation == "unknown_ref":
            fixture["rows"]["train"][1]["real_index"] = 9999
        elif mutation == "duplicate_row":
            fixture["rows"]["train"][1] = copy.deepcopy(fixture["rows"]["train"][0])
        else:
            fixture["rows"]["train"].pop()
        _rebuild_audit(fixture)
    elif mutation == "partial_view":
        fixture["summary"]["manifests"]["train"]["view_hash"] = "a" * 64
    elif mutation == "parent_hash":
        parent = copy.deepcopy(fixture["parents"]["train"])
        parent["unique_structure_count"] += 1
        _write_json(fixture["parent_paths"]["train"], parent)
    elif mutation == "parent_file_bytes":
        path = fixture["parent_paths"]["train"]
        path.write_bytes(path.read_bytes() + b"\n")
    elif mutation == "missing_defects":
        path = Path(fixture["summary"]["ledgers"]["defects"]["path"])
        fixture["summary"]["ledgers"]["defects"] = _write_ledger(path, [])
    elif mutation == "incomplete_overlap_refs":
        path = Path(fixture["summary"]["ledgers"]["overlap"]["path"])
        row = json.loads(path.read_text(encoding="utf-8"))
        row["train_record_refs"].pop()
        fixture["summary"]["ledgers"]["overlap"] = _write_ledger(path, [row])
    _write_json(fixture["summary_path"], fixture["summary"])
    with pytest.raises((ValueError, FileNotFoundError), match=match):
        _derive(fixture)
    assert not fixture["output"].exists()


def test_same_full_key_across_source_fields_is_still_overlap(tmp_path):
    fixture = _fixture(tmp_path)
    fixture["rows"]["validation"][0]["source_field"] = "isomeric_smiles"
    _rebuild_audit(fixture)
    fixture["exclusions"]["train"] = []
    with pytest.raises(ValueError, match="still overlap"):
        _derive(fixture)
    assert not fixture["output"].exists()


def test_existing_output_directory_is_never_overwritten(tmp_path):
    fixture = _fixture(tmp_path)
    fixture["output"].mkdir()
    sentinel = fixture["output"] / "existing.txt"
    sentinel.write_text("keep exact bytes", encoding="utf-8")
    with pytest.raises(FileExistsError, match="overwrite"):
        _derive(fixture)
    assert sentinel.read_text(encoding="utf-8") == "keep exact bytes"
    assert sorted(path.name for path in fixture["output"].iterdir()) == ["existing.txt"]


def test_byte_identical_relocated_ledgers_remain_hash_bound(tmp_path):
    fixture = _fixture(tmp_path)
    relocated = tmp_path / "copied_evidence"
    relocated.mkdir()
    overrides = {}
    for name, declaration in fixture["summary"]["ledgers"].items():
        path = relocated / f"{name}.jsonl"
        path.write_bytes(Path(declaration["path"]).read_bytes())
        overrides[name] = path
    result = _derive(fixture, ledger_paths=overrides)
    binding = result["report"]["binding"]
    for name, declaration in fixture["summary"]["ledgers"].items():
        assert binding["identity_ledgers"][name]["sha256"] == declaration["sha256"]
        assert binding["identity_ledgers"][name]["path"] == str(overrides[name].resolve())
    assert binding["identity_audit"]["file_sha256"] == hashlib.sha256(fixture["summary_path"].read_bytes()).hexdigest()
