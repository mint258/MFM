"""Independent small closed-metadata oracles; no test targets or LMDB reads.

Remote CPU execution is required. Synthetic graphs only supply genuine keys;
the hand element counts, references and conservation are independent oracles.
Passing this suite does not prove the site's GPU isolation or author graphs.
"""
from collections import Counter
import copy
import csv
import hashlib
import io
import json

import pytest

from phychem_mfm.phase1 import decontamination_v2 as proof
from phychem_mfm.phase1 import formal_gate as gate
from phychem_mfm.phase1 import formal_runtime as runtime
from phychem_mfm.phase1.data import StrictManifestDataset
from phychem_mfm.phase1.identity import IDENTITY_POLICY, canonical_hash, molecule_identity


def _seal(value, field):
    value[field] = canonical_hash({key: item for key, item in value.items() if key != field})
    return value


def _put(path, value, *, rows=False, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw:
        data = value
    elif rows:
        data = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in value)
    else:
        data = (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(data)
    return {"path": path.as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _csv(path, rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return _put(path, stream.getvalue().encode(), raw=True)


def _segments(shard, indices):
    segments = []
    for index in indices:
        if segments and segments[-1]["end"] + 1 == index:
            segments[-1]["end"] = index
            segments[-1]["count"] += 1
        else:
            segments.append({"shard": shard, "start": index, "end": index, "count": 1})
    return segments


class ClosedCase:
    """Re-seal all derived bytes after each intentional scientific contradiction."""
    def __init__(self, root, *, unknown_carbons=8, fault=None):
        self.root, self.fault = root, fault
        self.keys = {smiles: molecule_identity(smiles).inchikey
                     for smiles in ("C", "CC", "CCC", "N", "CO", "C#N", "F", "O", "c1ccccc1")}
        self.full = {"C": [[1, 4], [6, 1]], "CC": [[1, 6], [6, 2]],
                     "CCC": [[1, 8], [6, 3]], "N": [[1, 3], [7, 1]],
                     "CO": [[1, 4], [6, 1], [8, 1]], "C#N": [[1, 1], [6, 1], [7, 1]]}
        self.smiles = {"train": ["C", "CC", "CC", "N", "CCC"], "validation": ["CO", "C#N"]}
        if fault == "cross_side_key":
            self.smiles["validation"][0] = "CC"
        self.parents, self.parent_rows, self.parent_bindings = {}, {}, {}
        data_root = root / "opaque_lmdb"
        data_root.mkdir()
        for role, smiles in self.smiles.items():
            shard = role + ".lmdb"
            (data_root / shard).write_bytes(b"Not an LMDB: metadata-only oracle.\n")
            parent = _seal({"kind": role, "diagnostic_only": False,
                            "data_root": data_root.as_posix(),
                            "segments": _segments(shard, range(len(smiles))),
                            "unique_structure_count": len(smiles)}, "pool_hash")
            self.parents[role] = parent
            self.parent_rows[role] = [{"role": role, "logical_index": index,
                "shard": shard, "real_index": index, "manifest_pool_hash": parent["pool_hash"],
                "status": "identity_ok", "identity_policy": IDENTITY_POLICY,
                "inchikey": self.keys[smi], "source_field": "smiles"}
                for index, smi in enumerate(smiles)]
            self.parent_bindings[role] = _put(root / "parents" / (role + ".json"), parent)
        self.before = {value["path"]: value for value in self.parent_bindings.values()}
        for role, rows in self.parent_rows.items():
            value = _put(root / "fresh_identity" / (role + "_identities.jsonl"), rows, rows=True)
            self.before[value["path"]] = value
        datasets = ["qm7", "qm9", "cyp_isoform", "az_exactsom", "expansionrx"]
        known_smiles = ["C", "N", "c1ccccc1", "F", "O"]
        source_artifacts, declarations, known_rows = {}, [], []
        self.bases = {dataset: "declared_synthetic_graph_v1" for dataset in datasets}
        for dataset, smiles in zip(datasets, known_smiles):
            source = {"dataset": dataset, "sample_id": dataset + "-known", "fold": "0",
                      "source_ref": dataset + "-source", "SMILES": smiles,
                      "declared_inchikey": self.keys[smiles], "identity_basis": self.bases[dataset]}
            if dataset == "expansionrx":
                source.update(sample_id="1", fold="official_test", source_ref="official_test.csv:1")
            row = {key: source[key] for key in ("dataset", "sample_id", "source_ref", "identity_basis")}
            row.update({"fold": "official_test" if dataset == "expansionrx" else 0, "identity_policy": IDENTITY_POLICY,
                        "projection_ordinal_1based": 1, "inchikey": self.keys[smiles],
                        "projected_smiles_utf8_sha256": hashlib.sha256(smiles.encode()).hexdigest(),
                        "parent_structure_row_sha256": None if dataset == "expansionrx" else canonical_hash({"source": source["source_ref"]})})
            if fault == "non_expansion_null_parent" and dataset == "qm9":
                row["parent_structure_row_sha256"] = None
            if fault == "expansion_fake_parent" and dataset == "expansionrx":
                row["parent_structure_row_sha256"] = "f" * 64
            if fault == "known_smiles_hash" and dataset == "qm9":
                row["projected_smiles_utf8_sha256"] = "f" * 64
            name = dataset + "_test_identities.csv"
            declared = _csv(root / "impact" / name, [source], list(source))
            declared.update({"dataset": dataset, "rows": 1, "role": "test", "smiles_column": "SMILES"})
            source_artifacts[name] = {key: declared[key] for key in ("path", "sha256", "bytes")}
            declarations.append(declared)
            known_rows.append(row)
        if fault == "duplicate_projection_dataset":
            declarations[-1]["dataset"] = "qm7"
        known_keys = {row["inchikey"] for row in known_rows}
        source_artifacts["test_identities.jsonl"] = _put(root / "impact/test_identities.jsonl", known_rows, rows=True)
        unique = [_seal({"inchikey": row["inchikey"], "identity_policy": IDENTITY_POLICY,
                         "datasets": [row["dataset"]]}, "known_test_identity_sha256") for row in known_rows]
        source_artifacts["known_test_unique_identities.jsonl"] = _put(root / "impact/known_test_unique_identities.jsonl", unique, rows=True)
        unknown_rows, assignment_rows = [], [{"dataset": "qm7", "sample_id": "qm7-known",
            "fold": 0, "xyz_path": "qm7-source", "SMILES": "C"}]
        for index in range(25):
            source_path = root / "unknown" / (str(index) + ".xyz")
            source = (str(unknown_carbons) + "\nOpaque comment; no properties interpreted.\n"
                      + "C 0 0 0\n" * unknown_carbons).encode()
            bound = _put(source_path, source, raw=True)
            self.before[bound["path"]] = bound
            row = {"dataset": "qm7", "sample_id": "unknown-" + str(index), "fold": index % 10,
                   "source_ref": bound["path"], "source_sha256": bound["sha256"], "source_bytes": bound["bytes"],
                   "source_n_atoms": unknown_carbons, "inchikey": None, "graph_inferred": False,
                   "status": "UNRESOLVED_FULL_MOLECULAR_IDENTITY", "target_values_decoded": False,
                   "full_element_counts": [[6, unknown_carbons]], "non_h_element_counts": [[6, unknown_carbons]],
                   "full_composition_sha256": canonical_hash([[6, unknown_carbons]]),
                   "non_h_composition_sha256": canonical_hash([[6, unknown_carbons]]),
                   "native_atomic_number_order_sha256": canonical_hash([6] * unknown_carbons),
                   "native_coordinates_projection_sha256": canonical_hash({"opaque_source": bound["sha256"]})}
            assignment_rows.append({"dataset": "qm7", "sample_id": row["sample_id"], "fold": row["fold"],
                                    "xyz_path": row["source_ref"], "SMILES": ""})
            if index == 0 and fault in {"unknown_fold", "unknown_ref", "unknown_composition", "fake_unknown_key"}:
                if fault == "unknown_fold":
                    row["fold"] = 9
                elif fault == "unknown_ref":
                    row["source_ref"] = (root / "unknown/1.xyz").as_posix()
                elif fault == "unknown_composition":
                    row["non_h_element_counts"] = [[6, unknown_carbons + 1]]
                    row["non_h_composition_sha256"] = canonical_hash(row["non_h_element_counts"])
                else:
                    row["inchikey"] = self.keys["CC"]
            unknown_rows.append(_seal(row, "unresolved_structure_sha256"))
        if fault == "unknown_missing":
            unknown_rows.pop()
        if fault == "unknown_extra":
            unknown_rows.append(copy.deepcopy(unknown_rows[-1]))
        if fault == "unknown_order":
            unknown_rows.reverse()
        if fault == "extra_original_blank":
            assignment_rows.append({"dataset": "qm7", "sample_id": "unexpected-original-member",
                                    "fold": 0, "xyz_path": "opaque-source", "SMILES": ""})
        bound = _csv(root / "scaffold_split/qm7/fold_assignments.csv", assignment_rows,
                     ["dataset", "sample_id", "fold", "xyz_path", "SMILES"])
        self.before[bound["path"]] = bound
        source_artifacts["qm7_unresolved_structures.jsonl"] = _put(root / "impact/qm7_unresolved_structures.jsonl", unknown_rows, rows=True)
        self.unknown_path = root / "unknown/0.xyz"
        counts = Counter(row["inchikey"] for rows in self.parent_rows.values() for row in rows)
        representatives, seen = [], set()
        for role, rows in self.parent_rows.items():
            for index, row in enumerate(rows):
                if row["inchikey"] in seen:
                    continue
                seen.add(row["inchikey"])
                full = self.full[self.smiles[role][index]]
                non_h = [pair for pair in full if pair[0] != 1]
                representative = {**row, "group_reference_count": counts[row["inchikey"]],
                                  "full_element_counts": full, "non_h_element_counts": non_h,
                                  "full_composition_sha256": canonical_hash(full),
                                  "non_h_composition_sha256": canonical_hash(non_h)}
                if fault == "representative_first_ref" and self.smiles[role][index] == "CC":
                    representative["real_index"] += 1
                if fault == "representative_count" and self.smiles[role][index] == "CC":
                    representative["group_reference_count"] = 1
                representatives.append(_seal(representative, "representative_composition_sha256"))
        if fault == "missing_representative":
            representatives.pop()
        source_artifacts["pretraining_representative_compositions.jsonl"] = _put(root / "impact/pretraining_representative_compositions.jsonl", representatives, rows=True)
        source_artifacts["pretraining_impact_records.jsonl"] = _put(root / "impact/pretraining_impact_records.jsonl", [], rows=True)
        projection = _seal({"known_test_files": declarations, "identity_bases": self.bases,
                            "qm7_unresolved_records": 25}, "projection_inventory_sha256")
        source_artifacts["test_identity_projection_inventory.json"] = _put(root / "impact/test_identity_projection_inventory.json", projection)
        measurement = _seal({"projection_inventory_sha256": projection["projection_inventory_sha256"],
                             "known_test_records": dict.fromkeys(datasets, 1), "known_test_unique_keys": 5,
                             "unresolved_refs": [row["sample_id"] for row in unknown_rows]}, "measurement_sha256")
        source_artifacts["impact_measurement.json"] = _put(root / "impact/impact_measurement.json", measurement)
        impact = _seal({"schema_version": "phase1_conservative_embargo_impact_execution_v1", "complete": True,
            "status": "COMPLETE_READ_ONLY_CONSERVATIVE_EMBARGO_IMPACT", "input_before": self.before,
            "input_after": copy.deepcopy(self.before), "source_before": {"commit": "a" * 40},
            "source_after": {"commit": "a" * 40}, "filter_applied": False,
            "derived_manifests_created": False, "downstream_target_values_decoded": False,
            "artifacts": source_artifacts}, "content_sha256")
        impact_bound = _put(root / "impact/summary.json", impact)
        application = {}
        specification = _seal({"schema_version": "phase1_frozen_test_identity_and_composition_spec_v2",
            "frozen": True, "role": "test", "test_files": declarations, "identity_bases": self.bases,
            "projection_inventory": source_artifacts["test_identity_projection_inventory.json"],
            "unknown_qm7_records": 25, "full_molecular_identity_coverage": False,
            "known_test_union": source_artifacts["known_test_unique_identities.jsonl"],
            "unknown_qm7_native_structures": source_artifacts["qm7_unresolved_structures.jsonl"]}, "specification_sha256")
        application["frozen_test_specification.json"] = _put(root / "frozen_test_specification.json", specification)
        coverage = _seal({"fullkeys_for_unknowns": None, "unknown_records": 25,
            "unknown_member_ids": sorted(row["sample_id"] for row in unknown_rows),
            "unknown_native_ledger": source_artifacts["qm7_unresolved_structures.jsonl"],
            "unknown_non_h_compositions": [[[6, unknown_carbons]]], "unknown_non_h_composition_count": 1,
            "pretraining_fullkey_groups": len(seen),
            "representative_ledger": source_artifacts["pretraining_representative_compositions.jsonl"],
            "retained_non_h_composition_intersection_count": 0}, "coverage_sha256")
        application["unknown_composition_coverage.json"] = _put(root / "unknown_composition_coverage.json", coverage)
        representative_by_key = {row["inchikey"]: row for row in representatives}
        heavy_excluded = {key for key, row in representative_by_key.items()
                          if row["non_h_element_counts"] == [[6, unknown_carbons]]}
        excluded = known_keys | heavy_excluded
        self.datasets, active_ledgers, views, role_counts, embargo, excluded_rows = {}, {}, {}, {}, {}, []
        for role, rows in self.parent_rows.items():
            retained = [row for row in rows if row["inchikey"] not in excluded]
            if role == "train" and fault == "partial_group":
                retained = [row for row in retained if row["real_index"] != 2]
            if role == "train" and fault == "retained_known_key":
                retained.insert(0, rows[0])
            if role == "train" and fault == "retained_unknown_composition":
                retained.insert(0, rows[1])
            if role == "train" and fault == "retained_order":
                retained.reverse()
            manifest = _seal({"kind": role, "data_root": data_root.as_posix(),
                "segments": _segments(role + ".lmdb", [row["real_index"] for row in retained]),
                "unique_structure_count": len(retained), "parent_manifest_pool_hash": self.parents[role]["pool_hash"]}, "pool_hash")
            bound = _put(root / "retained" / (role + ".json"), manifest)
            application["retained/" + role + ".json"] = bound
            dataset = StrictManifestDataset(manifest, atom_encoding="zero_based")
            dataset._read = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Raw LMDB read forbidden"))
            self.datasets[role] = dataset
            identity_rows = [{**row, "parent_logical_index": row["logical_index"],
                             "parent_manifest_pool_hash": row["manifest_pool_hash"],
                             "logical_index": index, "manifest_pool_hash": manifest["pool_hash"]}
                             for index, row in enumerate(retained)]
            if role == "train" and fault == "retained_parent_cursor":
                identity_rows[0]["parent_logical_index"] += 1
            if role == "train" and fault == "retained_side":
                identity_rows[0]["role"] = "validation"
            bound = _put(root / (role + "_identities.jsonl"), identity_rows, rows=True)
            application[role + "_identities.jsonl"] = bound
            active_ledgers[role] = {**bound, "rows": len(retained), "manifest_pool_hash": dataset.pool_hash,
                                    "view_hash": dataset.view_hash}
            retained_keys = {row["inchikey"] for row in retained}
            views[role] = {"path": application["retained/" + role + ".json"]["path"], "records": len(retained),
                "kind": role, "pool_hash": dataset.pool_hash, "view_hash": dataset.view_hash,
                "identity_hash": canonical_hash(sorted(retained_keys)), "atom_encoding": "zero_based"}
            role_counts[role] = {"parent_records": len(rows), "retained": len(retained),
                                "embargoed": len(rows) - len(retained), "retained_unique_molecules": len(retained_keys)}
            for row in rows:
                datasets_for_key = sorted(known["dataset"] for known in known_rows if known["inchikey"] == row["inchikey"])
                embargo.setdefault(role, []).append({**row, "excluded_for_common_downstream_test_identity": row["inchikey"] in known_keys,
                    "excluded_for_unresolved_non_h_composition": row["inchikey"] in heavy_excluded,
                    "matched_test_datasets": datasets_for_key})
                if row["inchikey"] in excluded:
                    excluded_rows.append(row)
        embargo_rows = embargo["train"] + embargo["validation"]
        if fault == "embargo_false_boolean":
            embargo_rows[0]["excluded_for_common_downstream_test_identity"] = False
        if fault == "excluded_missing":
            excluded_rows.pop()
        application["pretraining_embargo_records.jsonl"] = _put(root / "pretraining_embargo_records.jsonl", embargo_rows, rows=True)
        application["excluded_records.jsonl"] = _put(root / "excluded_records.jsonl", excluded_rows, rows=True)
        quarantine = {"records": [{"shard": "quarantined.lmdb", "real_index": 99}]}
        if fault == "quarantine_overlap":
            quarantine["records"] = [{"shard": "train.lmdb", "real_index": 0}]
        application["quarantine.json"] = _put(root / "quarantine.json", quarantine)
        for name in ("explicit_exclusions.json", "retained/explicit_exclusions.json", "retained/derivation.json"):
            application[name] = _put(root / name, {"scope": "synthetic opaque supplemental receipt"})
        n_retained = sum(len(dataset) for dataset in self.datasets.values())
        self.plan = _seal({"schema_version": proof.SCHEMA, "identity_policy": IDENTITY_POLICY,
            "selected_conservative_rule": "non_h_composition", "source_metadata_artifacts": source_artifacts,
            "application_artifacts": application, "impact_execution": impact_bound,
            "frozen_test_specification_sha256": specification["specification_sha256"],
            "test_record_counts": dict.fromkeys(datasets, 1), "unique_test_keys": 5,
            "test_identity_union_hash": canonical_hash(sorted(known_keys)),
            "unknown_composition_artifact": application["unknown_composition_coverage.json"],
            "unknown_composition_coverage_sha256": coverage["coverage_sha256"],
            "retained_identity_ledgers": active_ledgers, "views": views, "counts": role_counts,
            "composition_only_excluded_keys": len(heavy_excluded - known_keys),
            "pairwise_full_identity_intersections": dict.fromkeys(("train_validation", "train_test", "validation_test"), 0),
            "retained_unknown_non_h_composition_intersection_count": 0,
            "original_ref_conservation": {"original": 8, "active_before_embargo": 7, "retained": n_retained,
                                          "embargoed": 7 - n_retained, "quarantine": 1}}, "plan_sha256")
        self.downstream = {"test_identity_specification": specification}
        self.protocol = {"data": {"test_embargo_policy": proof.EMBARGO_POLICY}}
        self.reseal()

    def reseal(self):
        _seal(self.plan, "plan_sha256")
        binding = _put(self.root / "decontamination_plan.json", self.plan)
        self.protocol["data"]["decontamination_sha256"] = binding["sha256"]

    def verify(self):
        return runtime.verify_decontamination(self.protocol, self.plan, self.datasets["train"],
            self.datasets["validation"], self.downstream, artifact_directory=self.root,
            downstream_directory=self.root)


def test_v2_actual_strict_segments_full_group_and_original_order(tmp_path):
    case = ClosedCase(tmp_path)
    result = case.verify()
    assert [case.datasets["train"].record_ref(index) for index in range(3)] == [
        ("train.lmdb", 1), ("train.lmdb", 2), ("train.lmdb", 4)]
    assert result["ref_conservation"] == {"original": 8, "active_before_embargo": 7,
        "retained": 5, "embargoed": 2, "quarantine": 1}
    assert result["train_unique"] == result["validation_unique"] == 2
    assert result["unresolved_qm7_records"] == 25
    assert result["full_test_molecular_identity_coverage"] is False
    assert result["conservative_test_embargo_coverage_verified"] is True
    assert result["raw_lmdb_records_read"] == 0
    assert all(not dataset._readers for dataset in case.datasets.values())


def test_v2_composition_excludes_entire_group_without_inventing_a_key(tmp_path):
    case = ClosedCase(tmp_path, unknown_carbons=2)
    result = case.verify()
    assert case.plan["composition_only_excluded_keys"] == 1
    assert case.datasets["train"].record_ref(0) == ("train.lmdb", 4)
    assert result["ref_conservation"]["embargoed"] == 4
    assert result["unresolved_non_h_overlaps"] == {"train": 0, "validation": 0}
    assert result["full_test_molecular_identity_coverage"] is False


@pytest.mark.parametrize("fault", ["known_smiles_hash", "duplicate_projection_dataset",
    "non_expansion_null_parent", "expansion_fake_parent",
    "unknown_fold", "unknown_ref", "unknown_composition", "fake_unknown_key", "unknown_missing",
    "unknown_extra", "unknown_order", "extra_original_blank", "representative_first_ref",
    "representative_count", "missing_representative", "partial_group", "retained_known_key",
    "retained_order", "retained_parent_cursor", "retained_side", "embargo_false_boolean",
    "excluded_missing", "quarantine_overlap", "cross_side_key"])
def test_consistently_resealed_scientific_contradictions_fail(tmp_path, fault):
    case = ClosedCase(tmp_path, fault=fault)
    with pytest.raises(ValueError):
        case.verify()


def test_resealed_retained_unknown_composition_is_rejected(tmp_path):
    case = ClosedCase(tmp_path, unknown_carbons=2, fault="retained_unknown_composition")
    with pytest.raises(ValueError):
        case.verify()


@pytest.mark.parametrize("what", ["raw_source", "raw_application", "raw_plan", "missing_source",
    "policy_omitted", "policy_boolean", "dataset_pool", "dataset_view", "dataset_encoding",
    "dataset_diagnostic", "declared_intersection", "declared_conservation"])
def test_raw_binding_active_view_and_policy_fail_closed(tmp_path, what):
    case = ClosedCase(tmp_path)
    if what == "raw_source":
        case.unknown_path.write_bytes(case.unknown_path.read_bytes() + b"\n")
    elif what == "raw_application":
        path = tmp_path / "train_identities.jsonl"
        path.write_bytes(path.read_bytes() + b"{}\n")
    elif what == "raw_plan":
        path = tmp_path / "decontamination_plan.json"
        path.write_bytes(path.read_bytes() + b"\n")
    elif what == "missing_source":
        case.unknown_path.unlink()
    elif what == "policy_omitted":
        del case.protocol["data"]["test_embargo_policy"]
    elif what == "policy_boolean":
        case.protocol["data"]["test_embargo_policy"] = True
    elif what == "dataset_pool":
        case.datasets["train"].pool_hash = "f" * 64
    elif what == "dataset_view":
        case.datasets["validation"].view_hash = "f" * 64
    elif what == "dataset_encoding":
        case.datasets["train"].atom_encoding = "atomic_number"
    elif what == "dataset_diagnostic":
        case.datasets["validation"].diagnostic_only = True
    elif what == "declared_intersection":
        case.plan["pairwise_full_identity_intersections"]["train_test"] = 1
        case.reseal()
    else:
        case.plan["original_ref_conservation"]["original"] += 1
        case.reseal()
    with pytest.raises(ValueError):
        case.verify()


def test_source_change_after_read_is_rejected_at_final_rehash(tmp_path, monkeypatch):
    case = ClosedCase(tmp_path)
    original = proof._Files.finish
    def mutate_then_close(files):
        case.unknown_path.write_bytes(case.unknown_path.read_bytes().replace(b"C 0 0 0", b"C 0 0 1", 1))
        return original(files)
    monkeypatch.setattr(proof._Files, "finish", mutate_then_close)
    with pytest.raises(ValueError, match="hash changed"):
        case.verify()


def test_metadata_wall_cap_is_checked(tmp_path, monkeypatch):
    case = ClosedCase(tmp_path)
    ticks = iter([0., 121.])
    monkeypatch.setattr(proof.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="wall budget"):
        case.verify()


@pytest.mark.parametrize("account,policy,raw,expected", [
    ("research", None, "research", "research"),
    (None, {"mode": "inherit_site_default", "resolved_account": None}, "(null)", None),
    (None, {"mode": "inherit_site_default", "resolved_account": "site_real"}, "site_real", "site_real")])
def test_account_contract_separates_request_from_actual_account(account, policy, raw, expected):
    protocol = {"compute": {"account": account}}
    if policy is not None:
        protocol["compute"]["account_policy"] = policy
    result = gate._verify_allocation_account(protocol, {"Account": raw})
    assert result["effective_account"] == expected
    assert result["slurm_account_raw"] == raw
    assert result["requested_account"] == account


@pytest.mark.parametrize("compute,job", [
    ({}, {"Account": "(null)"}), ({"account": None}, {"Account": "(null)"}),
    ({"account": ""}, {"Account": ""}), ({"account": "(null)"}, {"Account": "(null)"}),
    ({"account": True}, {"Account": "True"}), ({"account": "research"}, {"Account": "other"}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default"}}, {"Account": "(null)"}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default", "resolved_account": None, "extra": True}}, {"Account": "(null)"}),
    ({"account": None, "account_policy": {"mode": "anything", "resolved_account": None}}, {"Account": "(null)"}),
    ({"account": "fake", "account_policy": {"mode": "inherit_site_default", "resolved_account": None}}, {"Account": "(null)"}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default", "resolved_account": "(null)"}}, {"Account": "(null)"}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default", "resolved_account": None}}, {}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default", "resolved_account": None}}, {"Account": None}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default", "resolved_account": None}}, {"Account": ""}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default", "resolved_account": None}}, {"Account": "N/A"}),
    ({"account": None, "account_policy": {"mode": "inherit_site_default", "resolved_account": None}}, {"Account": "named"})])
def test_missing_fake_or_wrong_effective_accounts_are_rejected(compute, job):
    with pytest.raises(ValueError):
        gate._verify_allocation_account({"compute": compute}, job)


def test_legacy_complete_fullkey_route_preserves_existing_validation(monkeypatch, tmp_path):
    protocol = {"data": {"source_manifest_sha256": "a" * 64, "split_manifest_sha256": "b" * 64},
                "downstream": {"split_manifest_sha256": "c" * 64}}
    evidence = {"schema_version": "phase1_decontamination_v1", "identity_policy": IDENTITY_POLICY,
                "source_manifest_sha256": "a" * 64, "split_manifest_sha256": "b" * 64,
                "downstream_split_manifest_sha256": "c" * 64, "ledgers": {"train": "t", "validation": "v"}}
    monkeypatch.setattr(runtime, "verify_identity_ledger", lambda dataset, declaration, **kw: {declaration})
    monkeypatch.setattr(runtime, "frozen_test_identities", lambda specification: ({"test"}, {"scope": "legacy"}))
    assert runtime.verify_decontamination(protocol, evidence, object(), object(), {},
        artifact_directory=tmp_path, downstream_directory=tmp_path)["test"] == {"scope": "legacy"}
    monkeypatch.setattr(runtime, "frozen_test_identities", lambda specification: ({"t"}, {}))
    with pytest.raises(ValueError, match="overlap"):
        runtime.verify_decontamination(protocol, evidence, object(), object(), {},
            artifact_directory=tmp_path, downstream_directory=tmp_path)
