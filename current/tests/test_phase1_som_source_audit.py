"""Synthetic full source joins; target fields are forbidden to the projection."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
from rdkit import Chem

import tools.audit_phase1_som_structures as som_audit
from tools.audit_phase1_som_structures import (
    AuditError, CYP_FILES, Deadline, FOLD_COLUMNS, RAW_AZ_COLUMNS, SOURCE_CONTRACT_COMMIT,
    audit_som_structures, csv_byte_rows, project_columns, projected_csv,
)


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def write_fold_members(assignment_path):
    """Synthetic fixture only: preserve target columns while writing ten folds."""
    columns, rows = read_csv(assignment_path)
    for fold in range(10):
        write_csv(assignment_path.parent / f"fold_{fold + 1}.csv", columns,
                  [row for row in rows if int(row["fold"]) == fold])


def fixture_benchmark(tmp_path, *, explicit_h=False):
    root = tmp_path / "benchmark"
    cyp_dir, az_dir = root / "cyp_isoform/raw", root / "az_exactsom/raw"
    cyp_dir.mkdir(parents=True)
    mol = Chem.MolFromSmiles("CCO")
    if explicit_h:
        mol = Chem.AddHs(mol)
    block = Chem.MolToMolBlock(mol)
    rows = []
    for index, filename in enumerate(CYP_FILES):
        path = cyp_dir / filename
        # Invalid UTF-8 properties must remain opaque, not fed to a text SDF
        # loader or interpreted to choose atom correspondence/range/basis.
        path.write_bytes(block.encode() + b">  <PRIMARY_SOM>\n\xff FORBIDDEN_PROPERTY\n\n$$$$\n\n")
        isoform = path.stem
        rows.append({"dataset": "cyp_isoform", "sample_id": str(index + 1),
                     "sample_uid": f"{isoform}::source-id::1",
                     "compound_id": "source-id", "isoform": isoform, "fold": "0",
                     "SMILES": "CCO", "split_group_key": "cyp-group",
                     "source_sdf": str(path.resolve()), "SMILES_isomeric": "CCO",
                     "n_atoms": str(mol.GetNumAtoms()), "mol_block": block,
                     "all_som_atoms_1based_json": "FORBIDDEN_LABEL", "citation": "FORBIDDEN_CITATION"})
    cyp_folds = root / "scaffold_split/cyp_isoform/fold_assignments.csv"
    write_csv(cyp_folds, list(rows[0]), rows)
    write_fold_members(cyp_folds)
    az_raw = az_dir / "az_120_compounds.csv"
    write_csv(az_raw, ["Compound ID", "SMILES", "Comment", "Exact SoM annotation (1) or extended SoM annotation (0) per group"],
              [{"Compound ID": "Cmpd_1", "SMILES": "OCC", "Comment": "FORBIDDEN_COMMENT",
                "Exact SoM annotation (1) or extended SoM annotation (0) per group": "FORBIDDEN_FLAG"},
               {"Compound ID": "raw-only", "SMILES": "C", "Comment": "FORBIDDEN_OMISSION_REASON",
                "Exact SoM annotation (1) or extended SoM annotation (0) per group": "FORBIDDEN_FLAG"}])
    az_folds = root / "scaffold_split/az_exactsom/fold_assignments.csv"
    write_csv(az_folds, ["dataset", "sample_id", "sample_uid", "compound_id", "fold", "SMILES",
                         "split_group_key", "SMILES_isomeric", "n_atoms", "exact_flags_json"],
              [{"dataset": "az_exactsom", "sample_id": "1", "sample_uid": "az::Cmpd_1",
                "compound_id": "Cmpd_1", "fold": "1", "SMILES": "CCO", "split_group_key": "az-group",
                "SMILES_isomeric": "CCO", "n_atoms": "3", "exact_flags_json": "FORBIDDEN_FLAG"}])
    write_fold_members(az_folds)
    return root, cyp_folds, az_folds, az_raw


def expected_tree(root, path):
    files = []
    sources = [(root / "cyp_isoform/raw" / name, f"cyp_dataset/{name}") for name in CYP_FILES]
    sources.append((root / "az_exactsom/raw/az_120_compounds.csv", "cyp_dataset/az/az_120_compounds.csv"))
    for source, repository_path in sources:
        content = source.read_bytes()
        files.append({"repository_path": repository_path, "bytes": len(content),
                      "git_blob_sha1": hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()})
    path.write_text(json.dumps({"repository": "dmis-lab/ATTNSOM", "commit": SOURCE_CONTRACT_COMMIT, "files": files}), encoding="utf-8")
    return path


def defects(output):
    return [json.loads(line) for line in (output / "defects.jsonl").read_text().splitlines()]


def test_full_source_join_keeps_raw_atom_order_ids_members_and_targets_opaque(tmp_path):
    root, cyp, az, raw = fixture_benchmark(tmp_path)
    original = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    expected = expected_tree(root, tmp_path / "tree.json")
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output, expected_source_metadata=expected)
    assert code == 0 and summary["complete_scope"] and summary["source_version_binding_complete"]
    assert summary["ten_fold_member_coverage_complete"]
    for dataset, count in (("cyp_isoform", 9), ("az_exactsom", 1)):
        membership = summary["ten_fold_membership"][dataset]
        assert membership["files_read_complete"] == 10
        assert membership["observed_rows"] == membership["matched_rows"] == count
        assert membership["structural_membership_complete"]
        assert membership["missing_or_unmatched_members"] == 0
        for fold in range(1, 11):
            metadata = summary["sources"][f"{dataset}_fold_members/fold_{fold}"]
            path = root / "scaffold_split" / dataset / f"fold_{fold}.csv"
            assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert summary["counts"]["cyp_isoform"]["fold_records_connected"] == 9
    assert summary["counts"]["az_exactsom"]["raw_records"] == 2
    assert summary["counts"]["az_exactsom"]["fold_records_connected"] == 1
    assert summary["raw_only"]["az_exactsom"] == ["raw-only"]
    assert summary["dataset_unique_full_keys"]["cyp_isoform"] == 1
    az_record = json.loads((output / "az_folds.jsonl").read_text().splitlines()[0])
    assert az_record["atomic_numbers"] == [8, 6, 6]  # Raw OCC, never canonical CCO.
    assert az_record["source_atom_map"] == [0, 1, 2]
    assert not az_record["provenance"]["geometry_ready_for_encoder"]
    assert not az_record["provenance"]["mapping_audit_complete"]
    assert summary["scope"].startswith("NOT_FROZEN")
    assert all(path.read_bytes() == content for path, content in original.items())
    assert all("FORBIDDEN" not in path.read_text() for path in output.glob("*.json*"))


def test_projection_never_indexes_targets_flags_or_comments():
    class GuardedRow(list):
        def __getitem__(self, index):
            assert index not in {1, 3}, "Forbidden target column was selected"
            return super().__getitem__(index)
    header = ["sample_id", "exact_flags_json", "fold", "Comment", "mol_block"]
    row = GuardedRow(["record", object(), "0", object(), "STRUCTURE"])
    assert project_columns(header, row, FOLD_COLUMNS) == {"sample_id": "record", "fold": "0", "mol_block": "STRUCTURE"}
    header = ["Compound ID", "Comment", "SMILES", "SoMs grouped (numbers provided are atom indices)"]
    assert project_columns(header, GuardedRow(["c1", object(), "CO", object()]), RAW_AZ_COLUMNS) == {"Compound ID": "c1", "SMILES": "CO"}


def test_cyp_full_identity_cross_isoform_fold_conflict_is_failed_without_reassignment(tmp_path):
    root, cyp, _, _ = fixture_benchmark(tmp_path)
    columns, rows = read_csv(cyp)
    rows[1]["fold"] = "2"
    write_csv(cyp, columns, rows)
    before = cyp.read_bytes()
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output)
    assert code == 2 and summary["complete_scope"]
    overlap = next(item for item in defects(output) if "spans existing folds" in item["error"])
    assert len(overlap["references"]) == 9 and overlap["dataset"] == "cyp_isoform"
    assert cyp.read_bytes() == before


def test_cyp_same_element_permutation_cannot_pass_only_by_fullkey_and_atom_count(tmp_path):
    root, cyp, _, _ = fixture_benchmark(tmp_path)
    columns, rows = read_csv(cyp)
    rows[0]["mol_block"] = Chem.MolToMolBlock(Chem.RenumberAtoms(Chem.MolFromSmiles("CCO"), [1, 0, 2]))
    write_csv(cyp, columns, rows)
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output)
    assert code == 2 and summary["complete_scope"]
    assert any("source-order atom/bond graph" in item["error"] for item in defects(output))


def test_explicit_h_statistics_do_not_claim_annotation_indexing_verified(tmp_path):
    root, _, _, _ = fixture_benchmark(tmp_path, explicit_h=True)
    summary, code = audit_som_structures(root, output_dir=tmp_path / "audit")
    assert code == 0
    assert summary["counts"]["cyp_isoform"]["raw_records_with_explicit_h"] == 9
    assert summary["counts"]["cyp_isoform"]["fold_records_with_explicit_h"] == 9
    assert any("explicit-H annotation indexing still unverified" in item for item in summary["boundaries"])
    assert summary["source_version_binding_complete"] is False


@pytest.mark.parametrize("change", ["duplicate_raw_id", "unknown_fold_id", "atom_count", "stereo", "duplicate_fold_id"])
def test_az_source_join_defects_are_retained_and_nonzero(tmp_path, change):
    root, _, folds, raw = fixture_benchmark(tmp_path)
    columns, rows = read_csv(folds)
    if change == "duplicate_raw_id":
        raw_columns, raw_rows = read_csv(raw)
        raw_rows[1]["Compound ID"] = raw_rows[0]["Compound ID"]
        write_csv(raw, raw_columns, raw_rows)
    elif change == "unknown_fold_id":
        rows[0]["compound_id"], rows[0]["sample_uid"] = "not-in-raw", "az::not-in-raw"
    elif change == "atom_count":
        rows[0]["n_atoms"] = "4"
    elif change == "stereo":
        rows[0]["SMILES_isomeric"] = "F[C@H](Cl)Br"
    else:
        rows.append(dict(rows[0]))
    write_csv(folds, columns, rows)
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output)
    assert code == 2 and summary["defect_count"] > 0
    assert any(item.get("dataset") == "az_exactsom" for item in defects(output))
    if change == "duplicate_raw_id":
        assert summary["counts"]["az_exactsom"]["fold_records_connected"] == 0


@pytest.mark.parametrize("change", ["missing", "ambiguous", "wrong_blob", "wrong_bytes", "wrong_commit"])
def test_supplied_git_tree_metadata_must_bind_every_known_source(tmp_path, change):
    root, _, _, _ = fixture_benchmark(tmp_path)
    expected = expected_tree(root, tmp_path / "tree.json")
    payload = json.loads(expected.read_text())
    if change == "missing":
        payload["files"].pop(0)
    elif change == "ambiguous":
        payload["files"].append({**payload["files"][0], "repository_path": "cyp_dataset/other/1A2.sdf"})
    elif change == "wrong_blob":
        payload["files"][0]["git_blob_sha1"] = "0" * 40
    elif change == "wrong_commit":
        payload["commit"] = "a" * 40
    else:
        payload["files"][0]["bytes"] += 1
    expected.write_text(json.dumps(payload))
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output, expected_source_metadata=expected)
    assert code != 0 and not summary["source_version_binding_complete"]
    assert summary["defect_count"] > 0


def test_actual_csv_path_does_not_decode_invalid_utf8_targets_or_comments(tmp_path):
    root, cyp, az, raw = fixture_benchmark(tmp_path)
    for path in (cyp, az, raw, *root.glob("scaffold_split/*/fold_[0-9]*.csv")):
        source = path.read_bytes()
        # CSV framing stays valid; decoding these forbidden field values would
        # immediately fail, including in raw AZ comments/flags and fold labels.
        for marker in (b"FORBIDDEN_LABEL", b"FORBIDDEN_CITATION", b"FORBIDDEN_FLAG",
                       b"FORBIDDEN_COMMENT", b"FORBIDDEN_OMISSION_REASON"):
            source = source.replace(marker, b"\xff\xfe\x00OPAQUE_VALUE")
        path.write_bytes(source)
    expected = expected_tree(root, tmp_path / "tree.json")
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output, expected_source_metadata=expected)
    assert code == 0 and summary["complete_scope"] and summary["source_version_binding_complete"]
    assert summary["ten_fold_member_coverage_complete"]
    assert summary["counts"]["cyp_isoform"]["fold_records_connected"] == 9
    assert summary["counts"]["az_exactsom"]["fold_records_connected"] == 1
    assert all("OPAQUE_VALUE" not in path.read_text() for path in output.glob("*.json*"))


def test_csv_structure_utf8_quotes_commas_multiline_crlf_and_bom_are_preserved(tmp_path):
    path = tmp_path / "structure.csv"
    source = ('\ufeffsample_id,mol_block,SMILES,Comment\r\n'
              '"结构, ""quoted""","header\r\nM  END\n","OCC",').encode("utf-8")
    source += b'"\xff,\xfe\r\nopaque ""target quote"""\r\n'
    path.write_bytes(source)
    projected = list(projected_csv(path, {"sample_id", "mol_block", "SMILES"},
                                   {"sample_id", "mol_block", "SMILES"}, Deadline(10), 10))
    assert projected == [(1, {"sample_id": '结构, "quoted"', "mol_block": "header\r\nM  END\n", "SMILES": "OCC"})]
    framed = list(csv_byte_rows(source, Deadline(10)))
    assert framed[1][3] == b'\xff,\xfe\r\nopaque "target quote"'
    assert all(isinstance(value, bytes) for row in framed for value in row)


@pytest.mark.parametrize("source", [
    b'sample_id,mol_block\n1,"unclosed\n',
    b'sample_id,mol_block\n1,"closed"junk\n',
    b'sample_id,mol_block\n1,unquoted"quote\n',
    b'sample_id,mol_block\n1\n',
    b'sample_id,mol_block\n1,structure,extra\n',
    b'sample_id,mol_block\n1,\xff\n',
])
def test_csv_malformed_frames_or_invalid_selected_utf8_fail(tmp_path, source):
    path = tmp_path / "bad.csv"
    path.write_bytes(source)
    with pytest.raises(AuditError):
        list(projected_csv(path, {"sample_id", "mol_block"}, {"sample_id", "mol_block"}, Deadline(10), 10))


@pytest.mark.parametrize("relative", ["", "raw_audit", "scaffold_split/audit", "cyp_isoform/raw/audit"])
def test_output_inside_input_tree_is_rejected_before_any_directory_or_byte_changes(tmp_path, relative):
    root, _, _, _ = fixture_benchmark(tmp_path)
    paths_before = {str(path.relative_to(root)) for path in root.rglob("*")}
    bytes_before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="outside the benchmark input tree"):
        audit_som_structures(root, output_dir=root / relative)
    assert {str(path.relative_to(root)) for path in root.rglob("*")} == paths_before
    assert all(path.read_bytes() == contents for path, contents in bytes_before.items())


def test_csv_source_path_cannot_read_outside_known_raw_root(tmp_path, monkeypatch):
    root, cyp, _, _ = fixture_benchmark(tmp_path)
    outside = tmp_path / "outside.sdf"
    outside.write_text("UNAUTHORIZED_SYNTHETIC_CONTENT")
    columns, rows = read_csv(cyp)
    rows[0]["source_sdf"] = str(outside.resolve())
    write_csv(cyp, columns, rows)
    original_open = Path.open
    def guarded_open(path, *args, **kwargs):
        assert path != outside, "CSV directed a file read outside the known raw root"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)
    output = tmp_path / "audit"
    _, code = audit_som_structures(root, output_dir=output)
    assert code == 2 and any("outside its known" in item["error"] for item in defects(output))


def test_internal_wall_limit_and_record_cap_produce_partial_evidence(tmp_path):
    root, _, _, _ = fixture_benchmark(tmp_path)
    elapsed = iter(range(1000))
    output = tmp_path / "wall"
    summary, code = audit_som_structures(root, output_dir=output, max_wall_seconds=1, clock=lambda: next(elapsed))
    assert code == 3 and not summary["complete_scope"] and summary["status"] == "PARTIAL"
    summary, code = audit_som_structures(root, output_dir=tmp_path / "records", max_records=8)
    assert code == 3 and not summary["complete_scope"]
    with pytest.raises(FileExistsError):
        audit_som_structures(root, output_dir=output)


def test_ten_fold_members_ignore_quoted_invalid_utf8_targets_and_allow_row_reordering(tmp_path):
    root, cyp, _, _ = fixture_benchmark(tmp_path)
    columns, rows = read_csv(cyp)
    rows[0]["sample_id"] = 'structure, "quoted"'
    write_csv(cyp, columns, rows)
    write_fold_members(cyp)
    first = cyp.parent / "fold_1.csv"
    columns, rows = read_csv(first)
    write_csv(first, columns, list(reversed(rows)))
    for path in root.glob("scaffold_split/*/fold_[0-9]*.csv"):
        # Quoted comma, CRLF, doubled quotes and invalid UTF-8 are framing only;
        # fold labels may differ from assignment labels and remain undecoded.
        opaque = b'"\xff,\xfe\r\nOPAQUE_TARGET_SENTINEL ""quoted"" target"'
        source = path.read_bytes().replace(b"FORBIDDEN_LABEL", opaque).replace(b"FORBIDDEN_FLAG", opaque)
        path.write_bytes(source)
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output)
    assert code == 0 and summary["ten_fold_member_coverage_complete"]
    assert summary["ten_fold_membership"]["cyp_isoform"]["matched_rows"] == 9
    assert summary["ten_fold_membership"]["az_exactsom"]["matched_rows"] == 1
    assert all("OPAQUE_TARGET_SENTINEL" not in path.read_text() for path in output.glob("*.json*"))


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate_within", "duplicate_across",
                                    "wrong_file", "wrong_declared_fold", "missing_file"])
def test_ten_fold_member_defects_prevent_coverage_proof_without_repair(tmp_path, change):
    root, cyp, _, _ = fixture_benchmark(tmp_path)
    first, second = cyp.parent / "fold_1.csv", cyp.parent / "fold_2.csv"
    columns, rows = read_csv(first)
    if change == "missing":
        rows.pop(0)
    elif change == "extra":
        rows.append({**rows[0], "sample_id": "unknown", "sample_uid": "unknown"})
    elif change == "duplicate_within":
        rows.append(dict(rows[0]))
    elif change == "duplicate_across":
        write_csv(second, columns, [dict(rows[0])])
    elif change == "wrong_file":
        write_csv(second, columns, [rows.pop(0)])
    elif change == "wrong_declared_fold":
        rows[0]["fold"] = "1"
    else:
        second.unlink()
    write_csv(first, columns, rows)
    original = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output)
    assert code != 0 and not summary["ten_fold_member_coverage_complete"]
    assert not summary["ten_fold_membership"]["cyp_isoform"]["structural_membership_complete"]
    assert any(item.get("stage") == "ten_fold_membership" for item in defects(output))
    assert all(path.read_bytes() == value for path, value in original.items())
    assert set(original) == {path for path in root.rglob("*") if path.is_file()}
    if change.startswith("duplicate"):
        assert summary["ten_fold_membership"]["cyp_isoform"]["duplicate_rows"] == 1
    if change == "extra":
        assert summary["ten_fold_membership"]["cyp_isoform"]["extra_rows"] == 1


@pytest.mark.parametrize("field", ["SMILES", "SMILES_isomeric", "source_sdf", "mol_block",
                                   "split_group_key", "sample_uid", "compound_id", "n_atoms", "isoform"])
def test_ten_fold_selected_structure_source_or_group_drift_cannot_pass_by_stable_id(tmp_path, field):
    root, cyp, _, _ = fixture_benchmark(tmp_path)
    path = cyp.parent / "fold_1.csv"
    columns, rows = read_csv(path)
    # No reparsing or identity-only comparison can excuse differing source
    # structure values, even a chemically equivalent noncanonical SMILES.
    rows[0][field] = "OCC" if field in {"SMILES", "SMILES_isomeric"} else rows[0][field] + "_DRIFT"
    write_csv(path, columns, rows)
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output)
    assert code == 2 and summary["complete_scope"] and not summary["ten_fold_member_coverage_complete"]
    assert summary["ten_fold_membership"]["cyp_isoform"]["structural_drift_rows"] == 1
    assert any("drift from assignment" in item["error"] and field in item["error"] for item in defects(output))


def test_ten_fold_csv_missing_required_structural_column_is_incomplete(tmp_path):
    root, _, az, _ = fixture_benchmark(tmp_path)
    path = az.parent / "fold_2.csv"
    columns, rows = read_csv(path)
    columns.remove("split_group_key")
    for row in rows:
        row.pop("split_group_key")
    write_csv(path, columns, rows)
    output = tmp_path / "audit"
    summary, code = audit_som_structures(root, output_dir=output)
    assert code != 0 and not summary["complete_scope"]
    assert not summary["ten_fold_member_coverage_complete"]
    assert any("lacks required structural columns" in item["error"] for item in defects(output))


def test_ten_fold_cumulative_records_and_mid_membership_deadline_are_partial(tmp_path, monkeypatch):
    root, cyp, _, _ = fixture_benchmark(tmp_path)
    path = cyp.parent / "fold_1.csv"
    second = cyp.parent / "fold_2.csv"
    columns, rows = read_csv(path)
    write_csv(second, columns, [dict(rows[0])])
    summary, code = audit_som_structures(root, output_dir=tmp_path / "record_limit", max_records=9)
    assert code == 3 and not summary["complete_scope"] and not summary["ten_fold_member_coverage_complete"]
    write_csv(second, columns, [])
    elapsed = [0.]
    original_project = som_audit.projected_csv
    def expire_during_fold_scan(path, *args, **kwargs):
        yield from original_project(path, *args, **kwargs)
        if path.name == "fold_5.csv":
            elapsed[0] = 2.
    monkeypatch.setattr(som_audit, "projected_csv", expire_during_fold_scan)
    summary, code = audit_som_structures(root, output_dir=tmp_path / "wall_limit", max_wall_seconds=1,
                                         clock=lambda: elapsed[0])
    assert code == 3 and summary["status"] == "PARTIAL"
    assert not summary["complete_scope"] and not summary["ten_fold_member_coverage_complete"]
    membership = summary["ten_fold_membership"]["cyp_isoform"]
    assert membership["matched_rows"] == 9 and membership["files_read_complete"] == 5
    assert membership["missing_or_unmatched_members"] is None
    assert not membership["structural_membership_complete"]
