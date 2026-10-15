import json
from types import SimpleNamespace

import pytest

from tools.phase1_audit_manifest_identities import audit_full_manifest_identities


class FullView:
    def __init__(self, role, structures, *, diagnostic=False):
        self.kind = role
        self.records = [SimpleNamespace(smiles=value) for value in structures]
        self.diagnostic_only = diagnostic
        self._selection = None
        self.pool_hash = role + "-full-manifest"
        self.manifest = {"unique_structure_count": len(self.records)}

    def __len__(self):
        return len(self.records)

    def raw_record(self, index):
        return self.records[index]

    def __getitem__(self, index):
        raise AssertionError("Identity audit must not normalize or inspect training targets")

    def record_ref(self, index):
        return self.kind + ".lmdb", index + 10

    def summary(self):
        return {"kind": self.kind, "source_structure_count": len(self), "pool_hash": self.pool_hash}


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_complete_audit_preserves_all_duplicate_conformer_refs_and_exact_cache(tmp_path):
    output = tmp_path / "audit"
    summary = audit_full_manifest_identities(FullView("train", ["CCO", "CCO"]), FullView("validation", ["CCN"]),
              output_dir=output, source_metadata={"source_sha256": "source-a"})
    assert summary["exit_code"] == 0 and summary["full_record_coverage"]
    assert summary["all_record_identities_resolved"] and summary["full_scope_identity_intersection_count"] == 0
    assert summary["views"]["train"]["attempted_records"] == 2
    assert summary["views"]["train"]["observed_unique_molecules"] == 1
    assert summary["cache"]["hits"] == 1
    ledger = rows(output / "train_identities.jsonl")
    assert [row["real_index"] for row in ledger] == [10, 11]
    assert len({row["inchikey"] for row in ledger}) == 1
    assert all(row["source_field"] == "smiles" for row in ledger)
    assert not rows(output / "defects.jsonl")
    with pytest.raises(FileExistsError):
        audit_full_manifest_identities(FullView("train", ["CCO"]), FullView("validation", ["CCN"]),
                                       output_dir=output, source_metadata={})


def test_overlap_saves_all_record_refs_and_fails_without_reassignment(tmp_path):
    output = tmp_path / "overlap"
    summary = audit_full_manifest_identities(FullView("train", ["CCO", "OCC"]), FullView("validation", ["CCO"]),
                                            output_dir=output, source_metadata={})
    assert summary["exit_code"] == 2 and summary["status"] == "failed_defects"
    assert summary["full_scope_identity_intersection_count"] == 1
    overlap = rows(output / "overlap.jsonl")
    assert len(overlap) == 1 and len(overlap[0]["train_record_refs"]) == 2
    assert len(overlap[0]["validation_record_refs"]) == 1
    assert summary["records_reassigned_or_deleted"] == 0


def test_parse_failure_finishes_full_record_coverage_and_preserves_defects(tmp_path):
    output = tmp_path / "defects"
    train = FullView("train", ["CCO", "invalid_structure", "invalid_structure"])
    # A parseable lower-priority source must not silently rescue invalid SMILES.
    train.records[1].canonical_smiles = "CCO"
    train.records[2].canonical_smiles = "CCO"
    summary = audit_full_manifest_identities(train, FullView("validation", ["CCN"]),
                                            output_dir=output, source_metadata={})
    assert summary["exit_code"] == 2 and summary["full_record_coverage"]
    assert not summary["all_record_identities_resolved"]
    assert summary["full_scope_identity_intersection_count"] is None
    assert summary["views"]["train"]["failed_records"] == 2
    defects = rows(output / "defects.jsonl")
    assert [row["logical_index"] for row in defects] == [1, 2]
    assert all(row["raw_structure"] == "invalid_structure" for row in defects)


def test_wall_deadline_is_explicit_partial_evidence_and_never_zero_overlap_proof(tmp_path):
    values = iter([0., 0., 2., 2.])
    clock = lambda: next(values, 2.)
    output = tmp_path / "partial"
    summary = audit_full_manifest_identities(FullView("train", ["CCO", "CCN"]), FullView("validation", ["CCO"]),
              output_dir=output, source_metadata={}, max_wall_seconds=1., clock=clock)
    assert summary["exit_code"] == 3 and summary["status"] == "partial_wall_budget"
    assert not summary["full_record_coverage"] and summary["full_scope_identity_intersection_count"] is None
    assert summary["views"]["train"]["attempted_records"] == 1
    assert summary["views"]["validation"]["attempted_records"] == 0
    assert len(rows(output / "train_identities.jsonl")) == 1


def test_diagnostic_subset_cannot_be_presented_as_full_audit(tmp_path):
    with pytest.raises(ValueError, match="diagnostic subsets are forbidden"):
        audit_full_manifest_identities(FullView("train", ["CCO"], diagnostic=True), FullView("validation", ["CCN"]),
                                       output_dir=tmp_path / "forbidden", source_metadata={})
