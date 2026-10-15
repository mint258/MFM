"""Closed structural metadata consumer; unknown compositions are not full keys.

This validates the applied v2 evidence, not author graph truth or test targets.
The original complete-fullkey v1 consumer is deliberately left unchanged.
No raw LMDB record, fit call, molecular perception or test target is accessed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import time

from .identity import IDENTITY_POLICY, canonical_hash
from .manifest_views import _ordered_refs, _ref, _validate_parent

SCHEMA = "phase1_common_identity_and_composition_embargo_plan_v2"
EMBARGO_POLICY = "known_fullkey_plus_unresolved_qm7_native_non_h_composition_v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[A-Z]{14}-[A-Z]{10}-[A-Z]\Z")
_DATASETS = {"qm7", "qm9", "cyp_isoform", "az_exactsom", "expansionrx"}
_SYMBOLS = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
            "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu "
            "Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg "
            "Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og").split()
_Z = {symbol: index + 1 for index, symbol in enumerate(_SYMBOLS)}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name, *, maximum=200000):
    _require(type(value) is int and 0 <= value <= maximum, name + " is not a bounded integer")
    return value


def _digest(value):
    _require(isinstance(value, str) and _SHA.fullmatch(value), "Invalid structural SHA256")
    return value


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate metadata JSON key")
        result[key] = value
    return result


def _loads(raw):
    return json.loads(raw, object_pairs_hook=_unique_json,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite metadata JSON")))


def _seal(document, field):
    _require(type(document) is dict and document.get(field) == canonical_hash(
        {key: value for key, value in document.items() if key != field}), "Metadata receipt content changed: " + field)


class _Files:
    """Bound streaming metadata I/O; does not claim OS memory enforcement."""
    def __init__(self, directory):
        self.directory, self.before = Path(directory), {}
        self.began = time.monotonic()

    def check(self):
        _require(time.monotonic() - self.began <= 120, "Conservative proof metadata wall budget exceeded")

    def file(self, declaration):
        self.check()
        _require(type(declaration) is dict and {"path", "sha256", "bytes"} <= set(declaration), "Missing raw file binding")
        path = Path(declaration["path"])
        path = (path if path.is_absolute() else self.directory / path).resolve(strict=True)
        expected = _digest(declaration["sha256"])
        size = _integer(declaration["bytes"], "Metadata file bytes", maximum=1 << 30)
        _require(path.is_file() and path.stat().st_size == size, "Structural file size changed")
        previous = self.before.get(path)
        _require(previous is None or previous == (size, expected), "Conflicting binding of one structural file")
        if previous is None:
            _require(len(self.before) < 256, "Too many structural metadata files")
            self._hash(path, size, expected)
            self.before[path] = size, expected
        return path

    def _hash(self, path, size, expected):
        digest, actual = hashlib.sha256(), 0
        with path.open("rb") as stream:
            while chunk := stream.read(1 << 20):
                self.check()
                actual += len(chunk)
                _require(actual <= size, "Structural file grew during hash")
                digest.update(chunk)
        _require(actual == size and digest.hexdigest() == expected, "Structural raw file hash changed")

    def document(self, declaration):
        path = self.file(declaration)
        _require(path.stat().st_size <= 8 << 20, "Metadata JSON exceeds8MiB")
        with path.open("rb") as stream:
            raw = stream.read((8 << 20) + 1)
        _require(len(raw) <= 8 << 20, "Metadata JSON grew past its cap")
        return _loads(raw)

    def rows(self, declaration, count):
        _integer(count, "Ledger row count")
        path = self.file(declaration)
        if "rows" in declaration:
            _require(declaration["rows"] == count, "Declared ledger row count differs")
        with path.open("rb") as stream:
            for index in range(count):
                self.check()
                raw = stream.readline((256 << 10) + 1)
                _require(raw and len(raw) <= 256 << 10, "Missing/oversized structural ledger row")
                row = _loads(raw)
                _require(type(row) is dict, "Structural row is not an object")
                yield row
            _require(not stream.read(1), "Extra structural ledger rows")

    def finish(self):
        for path, (size, expected) in self.before.items():
            self._hash(path, size, expected)


def _composition(row):
    result = []
    for pair in row:
        _require(type(pair) is list and len(pair) == 2, "Malformed element count pair")
        z, count = pair
        _require(type(z) is int and 1 <= z <= 118 and type(count) is int and count > 0, "Invalid element composition")
        result.append((z, count))
    _require(result == sorted(set(result)) and len({z for z, _ in result}) == len(result), "Unordered/duplicate element counts")
    return tuple(result)


def _row_composition(row):
    full, non_h = _composition(row["full_element_counts"]), _composition(row["non_h_element_counts"])
    _require(non_h == tuple(pair for pair in full if pair[0] != 1)
             and canonical_hash(full) == row["full_composition_sha256"]
             and canonical_hash(non_h) == row["non_h_composition_sha256"], "Composition projection/hash changed")
    return full, non_h


def _native_unknown(row, files):
    """Read only XYZ element lines; property comment remains uninterpreted."""
    path = files.file({"path": row["source_ref"], "sha256": row["source_sha256"], "bytes": row["source_bytes"]})
    _require(path.stat().st_size <= 2 << 20, "Unknown source XYZ exceeds2MiB")
    with path.open("rb") as stream:
        header = stream.readline(128).strip()
        _require(header.isdigit(), "Unknown XYZ lacks an atom count")
        n = _integer(int(header), "Unknown native atom count", maximum=4096)
        _require(n > 0 and n == row["source_n_atoms"], "Unknown native source atom count changed")
        _require(len(stream.readline((256 << 10) + 1)) <= 256 << 10, "Unknown source comment exceeds cap")
        numbers = []
        for _ in range(n):
            line = stream.readline(4097)
            fields = line.split()
            _require(len(line) <= 4096 and len(fields) >= 4, "Unknown XYZ atom row is invalid")
            symbol = fields[0].decode("ascii")
            _require(symbol in _Z, "Unknown XYZ has an unsupported element symbol")
            numbers.append(_Z[symbol])
        _require(not stream.read((2 << 20) + 1).strip(), "Unknown XYZ contains extra structural rows")
    full, non_h = _row_composition(row)
    _require(tuple(sorted(Counter(numbers).items())) == full
             and canonical_hash(tuple(numbers)) == row["native_atomic_number_order_sha256"], "Unknown native element/order binding changed")
    _digest(row["native_coordinates_projection_sha256"])
    return non_h


def _verify_common_embargo(protocol, plan, train, validation, downstream, *, artifact_directory, downstream_directory):
    """Recompute the two-sided known-key/non-H proof from bound closed ledgers."""
    files = _Files(artifact_directory)
    plan_path = Path(artifact_directory) / "decontamination_plan.json"
    plan_raw = {"path": str(plan_path), "bytes": plan_path.stat().st_size,
                "sha256": protocol["data"]["decontamination_sha256"]}
    _require(files.document(plan_raw) == plan, "Supplied plan differs from protocol-bound raw plan")
    _seal(plan, "plan_sha256")
    _require(plan["schema_version"] == SCHEMA and plan["identity_policy"] == IDENTITY_POLICY
             and plan["selected_conservative_rule"] == "non_h_composition"
             and protocol["data"].get("test_embargo_policy") == EMBARGO_POLICY, "Unselected conservative embargo contract")
    inputs, application = plan["source_metadata_artifacts"], plan["application_artifacts"]
    _require(type(inputs) is dict and type(application) is dict, "Missing complete structural artifact maps")
    for declaration in list(inputs.values()) + list(application.values()):
        files.file(declaration)
    impact = files.document(plan["impact_execution"])
    _seal(impact, "content_sha256")
    _require(impact["schema_version"] == "phase1_conservative_embargo_impact_execution_v1"
             and impact["complete"] is True and impact["status"] == "COMPLETE_READ_ONLY_CONSERVATIVE_EMBARGO_IMPACT"
             and impact["input_before"] == impact["input_after"] and impact["source_before"] == impact["source_after"]
             and impact["filter_applied"] is False and impact["derived_manifests_created"] is False
             and impact["downstream_target_values_decoded"] is False, "Impact/source closure is incomplete")
    before = impact["input_before"]
    _require(type(before) is dict and before, "Missing original source/member bindings")
    for declaration in before.values():
        files.file(declaration)
    _require(set(inputs) == set(impact["artifacts"]), "Structural artifact coverage differs from closed impact")
    for name, declaration in inputs.items():
        _require(declaration == impact["artifacts"][name], "Structural artifact binding changed since impact")
    specification = files.document(application["frozen_test_specification.json"])
    _seal(specification, "specification_sha256")
    _require(downstream.get("test_identity_specification") == specification
             and specification["schema_version"] == "phase1_frozen_test_identity_and_composition_spec_v2"
             and specification["frozen"] is True and specification["role"] == "test"
             and specification["specification_sha256"] == plan["frozen_test_specification_sha256"], "Frozen downstream structural scope changed")
    projection = files.document(inputs["test_identity_projection_inventory.json"])
    _seal(projection, "projection_inventory_sha256")
    _require(specification["projection_inventory"] == inputs["test_identity_projection_inventory.json"]
             and specification["test_files"] == projection["known_test_files"]
             and specification["identity_bases"] == projection["identity_bases"]
             and set(projection["identity_bases"]) == _DATASETS
             and specification["unknown_qm7_records"] == projection["qm7_unresolved_records"] == 25
             and specification["full_molecular_identity_coverage"] is False, "Known/unknown benchmark inventory changed")
    measurement = files.document(inputs["impact_measurement.json"])
    _seal(measurement, "measurement_sha256")
    _require(measurement["projection_inventory_sha256"] == projection["projection_inventory_sha256"], "Measured source inventory changed")
    known_counts = plan["test_record_counts"]
    _require(set(known_counts) == _DATASETS and known_counts == measurement["known_test_records"], "Known test count scope differs")
    _require(all(_integer(value, "Known test records") > 0 for value in known_counts.values())
             and len(projection["known_test_files"]) == len(_DATASETS)
             and {entry["dataset"] for entry in projection["known_test_files"]} == _DATASETS,
             "Every declared dataset needs exactly one complete known projection")
    records = iter(files.rows(inputs["test_identities.jsonl"], sum(known_counts.values())))
    keys, datasets_by_key, members = set(), defaultdict(set), set()
    for declaration in projection["known_test_files"]:
        dataset, count = declaration["dataset"], 0
        _require(dataset in _DATASETS and declaration["rows"] == known_counts[dataset], "Projection dataset/count changed")
        with files.file(declaration).open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            for count, source in enumerate(reader, 1):
                files.check()
                row = next(records, None)
                _require(row is not None and row["identity_policy"] == IDENTITY_POLICY
                         and row["dataset"] == source["dataset"] == dataset
                         and row["sample_id"] == source["sample_id"] and str(row["fold"]) == source["fold"]
                         and row["source_ref"] == source["source_ref"] and row["projection_ordinal_1based"] == count
                         and row["inchikey"] == source["declared_inchikey"] and _KEY.fullmatch(row["inchikey"])
                         and row["identity_basis"] == source["identity_basis"] == projection["identity_bases"][dataset]
                         and row["projected_smiles_utf8_sha256"] == hashlib.sha256(source["SMILES"].encode()).hexdigest(),
                         "Known key/source/member/fold/order association changed")
                if dataset == "expansionrx":
                    # The pinned producer emits no parent JSON-row digest for
                    # official_test.csv: its raw CSV and ordinal are bound.
                    _require(row["parent_structure_row_sha256"] is None
                             and row["fold"] == "official_test"
                             and row["sample_id"] == str(count)
                             and row["source_ref"] == "official_test.csv:" + str(count),
                             "Expansion official source ordinal/null parent contract changed")
                else:
                    _digest(row["parent_structure_row_sha256"])
                member = dataset, row["sample_id"]
                _require(member not in members, "Duplicate known benchmark member")
                members.add(member)
                keys.add(row["inchikey"])
                datasets_by_key[row["inchikey"]].add(dataset)
            _require(count == known_counts[dataset], "Known projection is partial/extra")
    _require(next(records, None) is None and len(keys) == plan["unique_test_keys"] == measurement["known_test_unique_keys"], "Known identity union changed")
    unique = set()
    for row in files.rows(inputs["known_test_unique_identities.jsonl"], len(keys)):
        _seal(row, "known_test_identity_sha256")
        key = row["inchikey"]
        _require(key in keys and key not in unique and row["identity_policy"] == IDENTITY_POLICY
                 and row["datasets"] == sorted(datasets_by_key[key]), "Known unique identity lineage changed")
        unique.add(key)
    _require(unique == keys and specification["known_test_union"] == inputs["known_test_unique_identities.jsonl"]
             and plan["test_identity_union_hash"] == canonical_hash(sorted(keys)), "Known key hash/coverage changed")
    unknown, unknown_ids = set(), []
    for row in files.rows(inputs["qm7_unresolved_structures.jsonl"], 25):
        _seal(row, "unresolved_structure_sha256")
        _require(row["dataset"] == "qm7" and row["inchikey"] is None and row["graph_inferred"] is False
                 and row["status"] == "UNRESOLVED_FULL_MOLECULAR_IDENTITY" and row["target_values_decoded"] is False
                 and row["sample_id"] not in unknown_ids and ("qm7", row["sample_id"]) not in members
                 and type(row["fold"]) is int and 0 <= row["fold"] < 10, "Unknown member was fabricated/dropped/duplicated")
        unknown_ids.append(row["sample_id"])
        unknown.add(_native_unknown(row, files))
    _require(unknown_ids == measurement["unresolved_refs"] and specification["unknown_qm7_native_structures"] == inputs["qm7_unresolved_structures.jsonl"], "Unknown native subset/order changed")
    assignments = [decl for path, decl in before.items() if path.endswith("/scaffold_split/qm7/fold_assignments.csv")]
    _require(len(assignments) == 1, "Missing original QM7 member/fold assignment")
    original_unknown, original_known, original_members = [], {}, set()
    with files.file(assignments[0]).open(encoding="utf-8-sig", newline="") as stream:
        for source in csv.DictReader(stream):
            files.check()
            _require(source["dataset"] == "qm7" and source["sample_id"] not in original_members, "Invalid original QM7 member inventory")
            original_members.add(source["sample_id"])
            if source["SMILES"].strip():
                original_known[source["sample_id"]] = int(source["fold"]), source["xyz_path"]
            else:
                original_unknown.append((source["sample_id"], int(source["fold"]), source["xyz_path"]))
    reread_unknown = files.rows(inputs["qm7_unresolved_structures.jsonl"], 25)
    _require([(row["sample_id"], row["fold"], row["source_ref"]) for row in reread_unknown] == original_unknown
             and set(original_known) == {sample for dataset, sample in members if dataset == "qm7"}, "Unknown original ref/fold/order/member coverage changed")
    for declaration in projection["known_test_files"]:
        if declaration["dataset"] == "qm7":
            with files.file(declaration).open(encoding="utf-8", newline="") as stream:
                for source in csv.DictReader(stream):
                    _require(original_known[source["sample_id"]] == (int(source["fold"]), source["source_ref"]), "Known original QM7 ref/fold association changed")
    coverage = files.document(plan["unknown_composition_artifact"])
    _seal(coverage, "coverage_sha256")
    _require(coverage["coverage_sha256"] == plan["unknown_composition_coverage_sha256"]
             and coverage["fullkeys_for_unknowns"] is None and coverage["unknown_records"] == 25
             and coverage["unknown_member_ids"] == sorted(unknown_ids)
             and coverage["unknown_native_ledger"] == inputs["qm7_unresolved_structures.jsonl"]
             and coverage["unknown_non_h_compositions"] == [[list(pair) for pair in value] for value in sorted(unknown)]
             and coverage["unknown_non_h_composition_count"] == len(unknown), "Unknown composition coverage receipt changed")
    groups, compositions = {}, {}
    n_groups = _integer(coverage["pretraining_fullkey_groups"], "Parent identity groups")
    _require(coverage["representative_ledger"] == inputs["pretraining_representative_compositions.jsonl"], "Representative ledger changed")
    for row in files.rows(inputs["pretraining_representative_compositions.jsonl"], n_groups):
        _seal(row, "representative_composition_sha256")
        key = row["inchikey"]
        _require(_KEY.fullmatch(key) and key not in groups and row["identity_policy"] == IDENTITY_POLICY, "Missing/duplicate/invalid representative key")
        _, non_h = _row_composition(row)
        groups[key], compositions[key] = row, non_h
    excluded_keys = (set(groups) & keys) | {key for key in groups if compositions[key] in unknown}
    retained_keys, active_refs, all_parent_refs, group_counts = {}, {}, set(), Counter()
    parent_count = sum(_integer(plan["counts"][role]["parent_records"], "Parent role count") for role in ("train", "validation"))
    embargo_rows = iter(files.rows(application["pretraining_embargo_records.jsonl"], parent_count))
    excluded_rows = []
    for role, dataset in (("train", train), ("validation", validation)):
        counts, view = plan["counts"][role], plan["views"][role]
        _require(dataset.kind == role and dataset.diagnostic_only is False and len(dataset) == counts["retained"] == view["records"]
                 and dataset.pool_hash == view["pool_hash"] and dataset.view_hash == view["view_hash"]
                 and view["kind"] == role and view["atom_encoding"] == "zero_based", "Active strict manifest differs from frozen view")
        manifest = files.document(application["retained/" + role + ".json"])
        _require(manifest == dataset.manifest and manifest["pool_hash"] == dataset.pool_hash
                 and canonical_hash({key: value for key, value in manifest.items() if key != "pool_hash"}) == dataset.pool_hash
                 and dataset.atom_encoding == "zero_based", "Active manifest raw/semantic binding differs")
        candidates = [decl for path, decl in before.items() if path.endswith("/" + role + ".json") and "/fresh_identity/" not in path]
        _require(len(candidates) == 1, "Missing/ambiguous repaired parent manifest")
        parent = files.document(candidates[0])
        _require(_validate_parent(parent, role) == counts["parent_records"], "Parent manifest count/hash changed")
        identity_candidates = [decl for path, decl in before.items() if path.endswith("/fresh_identity/" + role + "_identities.jsonl")]
        _require(len(identity_candidates) == 1, "Missing/ambiguous full parent identity ledger")
        ordered_refs = iter(_ordered_refs(parent))
        retained_keys[role], active_refs[role], expected_rows = set(), [], []
        for index, row in enumerate(files.rows(identity_candidates[0], counts["parent_records"])):
            ref, key = _ref(row), row["inchikey"]
            _require(ref == next(ordered_refs, None) and ref not in all_parent_refs and row["role"] == role
                     and row["manifest_pool_hash"] == parent["pool_hash"] and row["status"] == "identity_ok"
                     and row["identity_policy"] == IDENTITY_POLICY and key in groups and groups[key]["role"] == role
                     and type(row["logical_index"]) is int and row["logical_index"] == index
                     and row["source_field"] in {"smiles", "isomeric_smiles", "canonical_smiles"}, "Parent record side/order/key coverage changed")
            all_parent_refs.add(ref)
            if group_counts[key] == 0:
                rep = groups[key]
                _require(all(rep[field] == row[field] for field in ("role", "logical_index", "shard", "real_index", "manifest_pool_hash", "source_field")), "First parent representative association changed")
            group_counts[key] += 1
            expected_embargo = {**row, "excluded_for_common_downstream_test_identity": key in keys,
                "excluded_for_unresolved_non_h_composition": compositions[key] in unknown,
                "matched_test_datasets": sorted(datasets_by_key.get(key, set()))}
            _require(next(embargo_rows, None) == expected_embargo, "Applied whole-group decision/source association changed")
            if key in excluded_keys:
                excluded_rows.append(row)
            if key not in excluded_keys:
                active_refs[role].append(ref)
                retained_keys[role].add(key)
                expected_rows.append({**row, "parent_logical_index": index, "parent_manifest_pool_hash": row["manifest_pool_hash"],
                                      "logical_index": len(expected_rows), "manifest_pool_hash": dataset.pool_hash})
        _require(next(ordered_refs, None) is None and len(active_refs[role]) == len(dataset)
                 and all(dataset.record_ref(index) == ref for index, ref in enumerate(active_refs[role])), "Derived retained order/side/membership changed")
        declaration = plan["retained_identity_ledgers"][role]
        _require(declaration["manifest_pool_hash"] == dataset.pool_hash and declaration["view_hash"] == dataset.view_hash
                 and files.file(declaration) == files.file(application[role + "_identities.jsonl"]), "Active identity ledger binding changed")
        actual_rows = files.rows(declaration, len(dataset))
        _require(all(actual == expected for actual, expected in zip(actual_rows, expected_rows)), "Derived identity ledger does not retain exact parent lineage")
        _require(counts["embargoed"] == counts["parent_records"] - len(dataset)
                 and counts["retained_unique_molecules"] == len(retained_keys[role])
                 and view["identity_hash"] == canonical_hash(sorted(retained_keys[role])), "Computed retained counts/hashes differ")
    _require(set(group_counts) == set(groups) and all(group_counts[key] == groups[key]["group_reference_count"] for key in groups), "Parent group/reference coverage changed")
    _require(next(embargo_rows, None) is None and plan["composition_only_excluded_keys"] == len(
        {key for key in groups if compositions[key] in unknown} - keys), "Applied group coverage/exclusion classification changed")
    closed_excluded = files.rows(application["excluded_records.jsonl"], len(excluded_rows))
    _require(all(all(actual.get(field) == value for field, value in expected.items())
                 for actual, expected in zip(closed_excluded, excluded_rows)), "Excluded record coverage/source lineage changed")
    intersections = {"train_validation": retained_keys["train"] & retained_keys["validation"],
                     "train_test": retained_keys["train"] & keys, "validation_test": retained_keys["validation"] & keys}
    non_h = {role: {compositions[key] for key in retained_keys[role]} & unknown for role in retained_keys}
    _require(not any(intersections.values()) and not any(non_h.values()), "Retained known-key or unknown non-H overlap remains")
    _require(plan["pairwise_full_identity_intersections"] == {name: 0 for name in intersections}
             and plan["retained_unknown_non_h_composition_intersection_count"] == coverage["retained_non_h_composition_intersection_count"] == 0,
             "Declared overlap receipt differs from actual sets")
    quarantine = files.document(application["quarantine.json"])
    quarantine_refs = {_ref(row) for row in quarantine["records"]}
    _require(len(quarantine_refs) == len(quarantine["records"]) and not quarantine_refs & all_parent_refs, "Quarantine reference conservation changed")
    conservation = {"original": len(all_parent_refs) + len(quarantine_refs), "active_before_embargo": len(all_parent_refs),
                    "retained": len(train) + len(validation), "embargoed": len(all_parent_refs) - len(train) - len(validation), "quarantine": len(quarantine_refs)}
    _require(conservation == plan["original_ref_conservation"], "Original/retained/excluded/quarantine conservation changed")
    files.finish()
    return {"scope": "complete_known_fullkeys_plus_explicit_unresolved_native_non_h_embargo_v2",
            "identity_policy": IDENTITY_POLICY, "test_embargo_policy": EMBARGO_POLICY,
            "train_unique": len(retained_keys["train"]), "validation_unique": len(retained_keys["validation"]),
            "overlaps": {name: 0 for name in intersections}, "unresolved_non_h_overlaps": {role: 0 for role in non_h},
            "train_identity_hash": canonical_hash(sorted(retained_keys["train"])),
            "validation_identity_hash": canonical_hash(sorted(retained_keys["validation"])),
            "known_test_unique": len(keys), "unresolved_qm7_records": 25,
            "full_test_molecular_identity_coverage": False, "conservative_test_embargo_coverage_verified": True,
            "test_identity_hash": canonical_hash(sorted(keys)), "ref_conservation": conservation,
            "source_or_author_graph_truth_independently_verified": False, "raw_lmdb_records_read": 0,
            "metadata_files_checked": len(files.before), "metadata_wall_seconds": time.monotonic() - files.began}


def verify_common_embargo(protocol, plan, train, validation, downstream, *, artifact_directory, downstream_directory):
    try:
        return _verify_common_embargo(protocol, plan, train, validation, downstream,
            artifact_directory=artifact_directory, downstream_directory=downstream_directory)
    except (KeyError, TypeError, OSError, StopIteration, UnicodeError) as error:
        raise ValueError("Missing/invalid conservative structural proof: " + str(error)) from error
