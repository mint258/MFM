"""Synthetic QM source/fold coverage; no target or real benchmark processing."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from phychem_mfm.phase1.identity import canonical_hash, molecule_identity
from tools import audit_phase1_qm_sources as audit


COLUMNS = ["dataset", "sample_id", "xyz_path", "SMILES", "target",
           "split_group_key", "fold"]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    # Valid CSV framing, deliberately invalid UTF-8 in every forbidden value.
    path.write_bytes(path.read_bytes().replace(b"FORBIDDEN_TARGET", b"\xff\xfe\x00OPAQUE_TARGET"))


def xyz_bytes(numbers=(8, 6, 6), *, original="CCO", relaxed="CCO", qm9=True):
    symbols = {1: "H", 6: "C", 7: "N", 8: "O", 9: "F"}
    source = str(len(numbers)).encode() + b"\n\xffOPAQUE_COMMENT\n"
    for index, number in enumerate(numbers):
        source += f"{symbols[number]} {index + 1}.0D+0 {index + 2}*^0 0".encode()
        source += b" \xffOPAQUE_CHARGE\n"
    if qm9:
        source += b"\xffOPAQUE_FREQUENCIES\n"
        source += original.encode() + b"\t" + relaxed.encode() + b"\n"
        source += b"\xffOPAQUE_INCHI\n"
    return source


def fixture_benchmark(tmp_path, dataset="qm9", *, members=None):
    root = tmp_path / "benchmark"
    source_root = root / dataset / ("extracted/xyz" if dataset == "qm7" else "extracted_figshare")
    source_root.mkdir(parents=True)
    if members is None:
        members = [(1, 0, "CCO", "CCO", (8, 6, 6))]
    rows = []
    for sample_id, fold, original, relaxed, numbers in members:
        filename = f"qm7_{sample_id:05d}.xyz" if dataset == "qm7" else f"dsgdb9nsd_{sample_id:06d}.xyz"
        path = source_root / filename
        path.write_bytes(xyz_bytes(numbers, original=original, relaxed=relaxed, qm9=dataset == "qm9"))
        rows.append({"dataset": dataset, "sample_id": str(sample_id), "fold": str(fold),
                     "xyz_path": str(path.resolve()), "SMILES": audit.nonstereo_graph_smiles(original),
                     "split_group_key": f"unchanged::{sample_id}", "target": "FORBIDDEN_TARGET"})
    folder = root / "scaffold_split" / dataset
    assignments = folder / "fold_assignments.csv"
    write_csv(assignments, rows)
    for fold in range(10):
        write_csv(folder / f"fold_{fold + 1}.csv", [row for row in rows if int(row["fold"]) == fold])
    return root, assignments, source_root, rows


def ledger(output, name="source_records"):
    return [json.loads(line) for line in (output / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]


def input_snapshot(root):
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_qm9_full_existing_scope_keeps_source_atom_order_and_target_bytes_opaque(tmp_path, monkeypatch):
    root, _, _, rows = fixture_benchmark(tmp_path, members=[
        (1, 0, "CCO", "CCO", (8, 6, 6)),
        (2, 9, "CCN", "CCN", (7, 6, 6)),
    ])
    before = input_snapshot(root)
    original_reader = audit.read_xyz_structure
    observed = []
    def check_reader(path, **kwargs):
        structure = original_reader(path, **kwargs)
        observed.append(structure)
        return structure
    monkeypatch.setattr(audit, "read_xyz_structure", check_reader)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    stats = summary["datasets"]["qm9"]
    assert code == 0 and summary["complete_scope"]
    assert stats["assignment_rows"] == stats["source_records_successful"] == stats["fold_members_checked"] == 2
    assert stats["fold_files_complete"] == 10 and stats["cross_fold_key_count"] == 0
    assert stats["key_overlap_proof_available"] and stats["unique_source_keys_union"] == 2
    assert not summary["formal_eligible"] and not summary["targets_decoded"]
    assert summary["source_version_binding"].startswith("observed exact file hashes")
    assert observed[0].atomic_numbers == (8, 6, 6)
    assert observed[0].x == (7, 5, 5) and observed[0].source_atom_map == (0, 1, 2)
    assert observed[0].pos_angstrom == ((1.0, 2.0, 0.0), (2.0, 3.0, 0.0), (3.0, 4.0, 0.0))
    record = ledger(output)[0]
    assert record["source_units"] == "angstrom" and record["coordinate_scale"] == 1.0
    assert record["original_gdb"]["inchikey"] == molecule_identity(rows[0]["SMILES"]).inchikey
    assert record["identity_source_line_1based"] == 7
    assert not record["identity_atom_mapping_proven"] and not record["mapping_audit_complete"]
    assert all(path.read_bytes() == content for path, content in before.items())
    assert all("OPAQUE" not in path.read_text(encoding="utf-8") for path in output.glob("*.json*"))
    for name, metadata in summary["ledgers"].items():
        assert hashlib.sha256((output / f"{name}.jsonl").read_bytes()).hexdigest() == metadata["sha256"]


def test_qm7_full_coordinates_use_bohr_and_never_infer_bonds_charge_or_identity(tmp_path, monkeypatch):
    root, assignments, _, rows = fixture_benchmark(tmp_path, "qm7")
    rows[0]["SMILES"] = "UNPARSED_LEGACY_STRUCTURE"
    write_csv(assignments, rows)
    write_csv(assignments.parent / "fold_1.csv", rows)
    def forbidden_identity(*_args, **_kwargs):
        pytest.fail("QM7 coordinates must not be turned into an authoritative identity")
    monkeypatch.setattr(audit, "molecule_identity", forbidden_identity)
    original_reader = audit.read_xyz_structure
    seen = []
    def reader(path, **kwargs):
        structure = original_reader(path, **kwargs)
        seen.append(structure)
        return structure
    monkeypatch.setattr(audit, "read_xyz_structure", reader)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm7",))
    assert code == 0 and summary["complete_scope"]
    record = ledger(output)[0]
    assert record["source_full_identity_status"] == "UNPROVEN" and record["source_keys"] == {}
    assert record["coordinate_scale"] == 0.529177210903 and record["source_units"] == "bohr"
    assert seen[0].pos_angstrom[0][0] == pytest.approx(0.529177210903)
    assert seen[0].identity is None and seen[0].mol is None
    assert not summary["datasets"]["qm7"]["key_overlap_proof_available"]
    assert summary["datasets"]["qm7"]["cross_fold_key_count"] is None
    assert not summary["formal_eligible"]


def test_two_qm9_stereo_keys_are_retained_without_replacing_member_or_isolating(tmp_path):
    original, relaxed = "C[C@H](O)F", "C[C@@H](O)F"
    root, assignments, _, _ = fixture_benchmark(tmp_path, members=[(1, 4, original, relaxed, (9, 6, 8, 6, 1))])
    before = input_snapshot(root)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    assert code == 0 and summary["complete_scope"]
    record = ledger(output)[0]
    assert record["original_gdb"]["inchikey"] == molecule_identity(original).inchikey
    assert record["relaxed"]["inchikey"] == molecule_identity(relaxed).inchikey
    assert record["original_gdb"]["inchikey"] != record["relaxed"]["inchikey"]
    assert record["source_keys_equal"] is False and record["fold"] == "4"
    assert summary["datasets"]["qm9"]["original_relaxed_differences"] == 1
    assert summary["datasets"]["qm9"]["unique_source_keys_union"] == 2
    assert summary["defect_count"] == 0 and not record["identity_atom_mapping_proven"]
    assert all(path.read_bytes() == content for path, content in before.items())
    assert not (output / "manifest.json").exists()


def test_union_detects_relaxed_to_original_cross_fold_key_without_reassignment(tmp_path):
    root, _, _, _ = fixture_benchmark(tmp_path, members=[
        (1, 0, "CCCO", "CCOC", (8, 6, 6, 6)),
        (2, 1, "CCOC", "CCOC", (8, 6, 6, 6)),
    ])
    before = input_snapshot(root)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    assert code == 2 and summary["complete_scope"]
    assert summary["datasets"]["qm9"]["cross_fold_key_count"] == 1
    defect = next(row for row in ledger(output, "defects") if row["stage"] == "source_key_overlap")
    assert {row["fold"] for row in defect["references"]} == {"0", "1"}
    assert {row["source_graph"] for row in defect["references"]} == {"original_gdb", "relaxed"}
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("change", ["wrong_fold", "unknown_id", "wrong_path", "changed_smiles", "duplicate", "missing_file"])
def test_ten_fold_structural_members_must_exactly_match_assignments(tmp_path, change):
    root, assignments, source_root, rows = fixture_benchmark(tmp_path)
    fold_path = assignments.parent / "fold_1.csv"
    row = dict(rows[0])
    if change == "wrong_fold":
        row["fold"] = "1"
    elif change == "unknown_id":
        row["sample_id"] = "999"
    elif change == "wrong_path":
        row["xyz_path"] = str(source_root / "dsgdb9nsd_999999.xyz")
    elif change == "changed_smiles":
        row["SMILES"] = "CCN"
    elif change == "missing_file":
        fold_path.unlink()
    if change != "missing_file":
        write_csv(fold_path, [row, row] if change == "duplicate" else [row])
    before = input_snapshot(root)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    assert code == 2 and summary["defect_count"] > 0
    assert not summary["datasets"]["qm9"]["key_overlap_proof_available"]
    assert summary["datasets"]["qm9"]["cross_fold_key_count"] is None
    assert ledger(output, "defects")
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("change", ["bad_original", "bad_relaxed", "missing_second", "third_token", "missing_inchi", "csv_graph"])
def test_qm9_source_identity_failures_are_preserved_without_zero_overlap_proof(tmp_path, change):
    root, assignments, source_root, rows = fixture_benchmark(tmp_path)
    path = source_root / "dsgdb9nsd_000001.xyz"
    source = path.read_bytes()
    if change == "bad_original":
        source = source.replace(b"CCO\tCCO", b"INVALID_SMILES\tCCO")
    elif change == "bad_relaxed":
        source = source.replace(b"CCO\tCCO", b"CCO\tINVALID_SMILES")
    elif change == "missing_second":
        source = source.replace(b"CCO\tCCO", b"CCO")
    elif change == "third_token":
        source = source.replace(b"CCO\tCCO", b"CCO\tCCO\t\xffOPAQUE_UNKNOWN")
    elif change == "missing_inchi":
        source = source.replace(b"\xffOPAQUE_INCHI\n", b"")
    else:
        rows[0]["SMILES"] = "CCN"
        write_csv(assignments, rows)
        write_csv(assignments.parent / "fold_1.csv", rows)
    path.write_bytes(source)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    assert code == 2 and summary["complete_scope"]
    assert summary["datasets"]["qm9"]["source_records_successful"] == 0
    assert not summary["datasets"]["qm9"]["key_overlap_proof_available"]
    record = ledger(output)[0]
    assert record["status"] == "failed"
    assert record["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record["source_units"] == "angstrom"
    if change == "bad_original":
        assert record["relaxed"]["inchikey"] == molecule_identity("CCO").inchikey
        assert record["identity_errors"]["original_gdb"]
    if change == "bad_relaxed":
        assert record["original_gdb"]["inchikey"] == molecule_identity("CCO").inchikey
        assert record["identity_errors"]["relaxed"]
    assert ledger(output, "defects")


def test_failed_source_does_not_skip_remaining_existing_members(tmp_path):
    root, _, source_root, _ = fixture_benchmark(tmp_path, members=[
        (1, 0, "CCO", "CCO", (8, 6, 6)), (2, 1, "CCN", "CCN", (7, 6, 6)),
    ])
    (source_root / "dsgdb9nsd_000001.xyz").write_bytes(b"3\nopaque\nC nan 0 0\n")
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    assert code == 2 and summary["complete_scope"]
    assert [row["status"] for row in ledger(output)] == ["failed", "structure_ok"]
    assert summary["datasets"]["qm9"]["assignment_rows"] == 2
    assert summary["datasets"]["qm9"]["source_records_successful"] == 1
    assert summary["datasets"]["qm9"]["cross_fold_key_count"] is None


def test_source_path_and_filename_id_fail_before_reading_other_file(tmp_path, monkeypatch):
    root, assignments, _, rows = fixture_benchmark(tmp_path)
    outside = tmp_path / "dsgdb9nsd_000001.xyz"
    outside.write_bytes(b"UNAUTHORIZED_SOURCE")
    rows[0]["xyz_path"] = str(outside)
    write_csv(assignments, rows)
    write_csv(assignments.parent / "fold_1.csv", rows)
    original_open = Path.open
    def guarded_open(path, *args, **kwargs):
        assert path != outside, "CSV directed an unauthorized source read"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    assert code == 2 and any("outside its known" in row["error"] for row in ledger(output, "defects"))
    assert not summary["datasets"]["qm9"]["key_overlap_proof_available"]


@pytest.mark.parametrize("dataset", ["qm7", "qm9"])
def test_generator_filename_id_must_match_existing_member_before_file_read(tmp_path, monkeypatch, dataset):
    root, assignments, source_root, rows = fixture_benchmark(tmp_path, dataset)
    wrong_name = "qm7_00002.xyz" if dataset == "qm7" else "dsgdb9nsd_000002.xyz"
    wrong_path = source_root / wrong_name
    wrong_path.write_bytes(b"UNAUTHORIZED_WRONG_ID_SOURCE")
    rows[0]["xyz_path"] = str(wrong_path)
    write_csv(assignments, rows)
    write_csv(assignments.parent / "fold_1.csv", rows)
    original_open = Path.open
    def guarded_open(path, *args, **kwargs):
        assert path != wrong_path, "A different filename ID must not be read as this member"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=(dataset,))
    assert code == 2 and any("filename ID" in row["error"] for row in ledger(output, "defects"))
    assert ledger(output)[0]["sample_id"] == "1" and ledger(output)[0]["status"] == "failed"
    assert not summary["formal_eligible"]


def test_same_element_permutation_changes_geometry_hash_and_is_never_reordered(tmp_path):
    root, assignments, source_root, rows = fixture_benchmark(tmp_path)
    deadline = audit.Deadline(10)
    path = source_root / "dsgdb9nsd_000001.xyz"
    first = audit.audit_qm_source_record(rows[0], "qm9", source_root, assignments, deadline)
    lines = path.read_bytes().splitlines(keepends=True)
    lines[3], lines[4] = lines[4], lines[3]  # Both C, coordinates stay with source rows.
    path.write_bytes(b"".join(lines))
    second = audit.audit_qm_source_record(rows[0], "qm9", source_root, assignments, deadline)
    assert first["source_atomic_number_order_hash"] == second["source_atomic_number_order_hash"]
    assert first["coordinate_projection_hash"] != second["coordinate_projection_hash"]
    assert first["source_atom_map_hash"] == second["source_atom_map_hash"] == canonical_hash((0, 1, 2))
    assert first["source_keys"] == second["source_keys"]
    assert not second["identity_atom_mapping_proven"]


def test_changing_opaque_targets_changes_byte_binding_but_not_structure_projection(tmp_path):
    root, assignments, source_root, rows = fixture_benchmark(tmp_path)
    path = source_root / "dsgdb9nsd_000001.xyz"
    first = audit.audit_qm_source_record(rows[0], "qm9", source_root, assignments, audit.Deadline(10))
    path.write_bytes(path.read_bytes().replace(b"OPAQUE_CHARGE", b"DIFFERENT_OPAQUE_CHARGE"))
    second = audit.audit_qm_source_record(rows[0], "qm9", source_root, assignments, audit.Deadline(10))
    assert first["source_sha256"] != second["source_sha256"]
    assert first["coordinate_projection_hash"] == second["coordinate_projection_hash"]
    assert first["source_keys"] == second["source_keys"]


def test_source_changed_between_geometry_and_identity_read_cannot_pass(tmp_path, monkeypatch):
    root, assignments, source_root, rows = fixture_benchmark(tmp_path)
    original_reader = audit.read_xyz_structure
    def changed_source(path, **kwargs):
        structure = original_reader(path, **kwargs)
        path.write_bytes(path.read_bytes().replace(b"OPAQUE_COMMENT", b"CHANGED_COMMENT"))
        return structure
    monkeypatch.setattr(audit, "read_xyz_structure", changed_source)
    with pytest.raises(audit.AuditError, match="changed between geometry and identity"):
        audit.audit_qm_source_record(rows[0], "qm9", source_root, assignments, audit.Deadline(10))


@pytest.mark.parametrize("relative", ["", "scaffold_split/audit", "qm9/extracted_figshare/audit"])
def test_outputs_inside_input_tree_rejected_without_writing(tmp_path, relative):
    root, _, _, _ = fixture_benchmark(tmp_path)
    before = input_snapshot(root)
    with pytest.raises(ValueError, match="outside the benchmark"):
        audit.audit_qm_sources(root, output_dir=root / relative, datasets=("qm9",))
    assert input_snapshot(root) == before


def test_wall_member_and_file_caps_leave_partial_summary_not_full_identity_proof(tmp_path, monkeypatch):
    root, _, _, _ = fixture_benchmark(tmp_path, members=[
        (1, 0, "CCO", "CCO", (8, 6, 6)), (2, 1, "CCN", "CCN", (7, 6, 6)),
    ])
    clock = iter(range(1000))
    wall_output = tmp_path / "wall"
    summary, code = audit.audit_qm_sources(root, output_dir=wall_output, datasets=("qm9",),
                                          max_wall_seconds=1, clock=lambda: next(clock))
    assert code == 3 and summary["status"] == "PARTIAL" and not summary["complete_scope"]
    assert (wall_output / "summary.json").exists() and ledger(wall_output, "defects")
    summary, code = audit.audit_qm_sources(root, output_dir=tmp_path / "members", datasets=("qm9",), max_records=1)
    assert code == 3 and not summary["complete_scope"]
    assert summary["datasets"]["qm9"]["assignment_rows"] == 1
    assert summary["datasets"]["qm9"]["cross_fold_key_count"] is None
    monkeypatch.setattr(audit, "MAX_CSV_BYTES", 16)
    summary, code = audit.audit_qm_sources(root, output_dir=tmp_path / "bytes", datasets=("qm9",))
    assert code == 3 and not summary["complete_scope"]
    with pytest.raises(FileExistsError):
        audit.audit_qm_sources(root, output_dir=wall_output, datasets=("qm9",))


def test_output_budget_preserves_partial_active_reference_and_never_claims_complete(tmp_path, monkeypatch):
    root, _, _, _ = fixture_benchmark(tmp_path)
    monkeypatch.setattr(audit, "MAX_OUTPUT_BYTES", 1024 * 1024 + 200)
    output = tmp_path / "audit"
    summary, code = audit.audit_qm_sources(root, output_dir=output, datasets=("qm9",))
    assert code == 3 and summary["status"] == "PARTIAL" and not summary["complete_scope"]
    assert summary["partial_active_reference"]["sample_id"] == "1"
    assert summary["partial_source_evidence"]["source_sha256"]
    assert not summary["datasets"]["qm9"]["key_overlap_proof_available"]
    assert (output / "summary.json").exists()
    assert summary["ledger_bytes"] <= 200


@pytest.mark.parametrize("kwargs", [
    {"max_wall_seconds": 841}, {"max_wall_seconds": float("nan")}, {"max_wall_seconds": 0},
    {"max_records": 200001}, {"max_records": True}, {"datasets": ("qm9", "qm9")},
    {"datasets": ("qm7b",)},
])
def test_invalid_budgets_or_scope_fail_before_output_creation(tmp_path, kwargs):
    output = tmp_path / "audit"
    with pytest.raises(ValueError):
        audit.audit_qm_sources(tmp_path / "benchmark", output_dir=output, **kwargs)
    assert not output.exists()
