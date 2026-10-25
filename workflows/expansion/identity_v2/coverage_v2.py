"""All-original-role/fold/raw source coverage; never a test-only embargo proof."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..common import require
from .projection_v2 import full_keys, identity, source_smiles_keys


QM_FOLD_COLUMNS = ("dataset", "sample_id", "fold")
CYP_FOLD_COLUMNS = ("dataset", "sample_id", "sample_uid", "compound_id", "isoform", "fold", "source_sdf", "SMILES_isomeric")
AZ_FOLD_COLUMNS = ("dataset", "sample_id", "sample_uid", "compound_id", "fold", "SMILES_isomeric")
EXTERNAL_PENDING = ("tdc_admet", "moleculenet", "marcel_drugs75k", "marcel_kraken", "coconut")


def integer(value, lower, upper):
    require(isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).isascii() and
            str(value).isdigit() and lower <= int(value) <= upper, "Invalid original integer ID/fold")
    return int(value)


def assignment_fold_union(dataset, assignments, fold_files, columns, id_column, expected_count):
    """Compare ten whole identity-only fold files to the whole assignment.

    Selected columns are deliberately narrow: no mol_block, coordinates,
    scaffold, descriptor, assay or target values are decoded or compared.
    """
    allowed = {QM_FOLD_COLUMNS, CYP_FOLD_COLUMNS, AZ_FOLD_COLUMNS}
    require(tuple(columns) in allowed and id_column in columns and set(fold_files) == set(range(10)),
            "Exact reviewed identity-column contract and all ten fold files required")
    expected = {}
    for row in assignments:
        require(set(row) == set(columns) and row["dataset"] == dataset and row[id_column], "Assignment identity schema/ID mismatch")
        source_id = row[id_column]
        require(source_id not in expected, "Duplicate original assignment source ID")
        fold = integer(row["fold"], 0, 9)
        expected[source_id] = (fold, tuple(row[k] for k in columns))
    require(len(expected) == expected_count, "Whole assignment count differs from independently pinned original population")
    seen, per_fold = set(), Counter()
    for fold in range(10):
        for row in fold_files[fold]:
            require(set(row) == set(columns) and row["dataset"] == dataset, "Fold identity schema/dataset mismatch")
            source_id = row[id_column]
            require(source_id not in seen and source_id in expected and integer(row["fold"], 0, 9) == fold and
                    expected[source_id] == (fold, tuple(row[k] for k in columns)),
                    "Duplicate/wrong-fold/missing-assignment or altered identity-only fold member")
            seen.add(source_id)
            per_fold[fold] += 1
    require(seen == set(expected), "Ten-fold union omitted original members")
    return {source_id: item[0] for source_id, item in expected.items()}, {
        "status": "ALL_TEN_IDENTITY_ONLY_FOLDS_MATCH_WHOLE_ASSIGNMENT",
        "records": len(expected), "fold_counts": {str(k): per_fold[k] for k in range(10)},
        "selected_columns": list(columns), "target_or_feature_values_used": False,
    }


def qm_original_universe(fold_by_sample, dataset):
    size = {"qm7": 7165, "qm9": 133885}[dataset]
    parsed = {integer(key, 1, size): fold for key, fold in fold_by_sample.items()}
    require(len(parsed) == size and set(parsed) == set(range(1, size + 1)), "Original full QM ID universe was narrowed")
    return parsed


def cyp_rows(raw_cache, fold_cache, raw_tickets, *, assignment_folds):
    """Reuse exact source-version-bound full keys, without reading SDF features."""
    by_name = {Path(t.reference["path"]).name: t for t in raw_tickets}
    require(len(by_name) == 9, "All nine original CYP SDF current pins required")
    raw = {}
    for row in raw_cache:
        key = (row["source_file"], row["source_record_1based"])
        require(row["status"] == "STRUCTURE_READ" and key[0] in by_name and type(key[1]) is int and
                key not in raw, "Invalid/missing/duplicate raw CYP ledger identity")
        keys, _ = full_keys([row["inchikey"]])
        require(len(keys) == 1, "Raw CYP cache has no full identity key")
        raw[key] = keys[0]
    required = {(name, ordinal) for name, ticket in by_name.items() for ordinal in range(1, ticket.physical_count + 1)}
    require(len(required) == 2003 and set(raw) == required, "CYP raw ledger is not the independently counted whole2003 source set")
    require(len(assignment_folds) == 2003, "Independently checked whole CYP assignment/fold union required")
    connected, sample_ids, uids, result = set(), set(), set(), []
    for row in fold_cache:
        key = (row["source_file"], row["source_record_1based"])
        require(row["status"] == "SOURCE_ORDER_CONNECTED" and key in raw and key not in connected and
                row["inchikey"] == raw[key] and row["sample_uid"] and row["sample_id"] not in sample_ids,
                "CYP all-fold ledger no longer binds every original raw record exactly once")
        fold = integer(row["fold"], 0, 9)
        uid = row["sample_uid"]
        require(uid.endswith("::" + str(key[1])) and uid.startswith(Path(key[0]).stem + "::") and uid not in uids and
                assignment_folds.get(uid) == fold, "CYP UID/raw source/independently checked assignment mismatch")
        connected.add(key)
        sample_ids.add(row["sample_id"])
        uids.add(uid)
        result.append(identity("som_cyp", key[0] + ":" + str(key[1]), "all", [], [raw[key]],
                               memberships=["all_raw", "fold_" + str(fold)]))
    require(connected == required and uids == set(assignment_folds), "Never accept successful-only/test-only CYP identities")
    return result, {"raw_records": 2003, "fold_union_records": len(connected), "additional_raw_records": 0}


def az_rows(raw_cache, fold_cache, raw_csv, *, assignment_folds):
    raw, ordinals = {}, set()
    for row in raw_cache:
        source_id = row["compound_id"]
        require(row["status"] == "STRUCTURE_READ" and source_id and source_id not in raw and
                row["source_record_1based"] not in ordinals, "AZ original raw ID/ordinal missing or duplicated")
        keys, _ = full_keys([row["inchikey"]])
        require(len(keys) == 1, "Original raw AZ full identity missing")
        raw[source_id] = (row["source_record_1based"], keys[0])
        ordinals.add(row["source_record_1based"])
    require(len(raw) == 120 and ordinals == set(range(1, 121)), "All120 raw AZ source records are required")
    smiles, csv_seen = {}, set()
    for ordinal, row in enumerate(raw_csv, 1):
        require(set(row) == {"Compound ID", "SMILES"}, "AZ CSV must project only original ID/SMILES")
        source_id = row["Compound ID"]
        require(source_id in raw and source_id not in csv_seen and raw[source_id][0] == ordinal, "Current AZ raw CSV/cache identity order mismatch")
        keys, errors = source_smiles_keys({"SMILES": row["SMILES"]})
        require(not errors and keys == [raw[source_id][1]], "Current AZ raw SMILES/key differs from bound source cache")
        csv_seen.add(source_id)
        smiles[source_id] = row["SMILES"]
    require(csv_seen == set(raw), "AZ current raw projection omitted one or more of120 members")
    require(len(assignment_folds) == 109, "Independently checked whole AZ109 assignment/fold union required")
    used = {}
    for row in fold_cache:
        source_id = row["compound_id"]
        require(row["status"] == "RAW_ID_CONNECTED" and source_id in raw and source_id not in used and
                row["sample_uid"] == "az::" + source_id and row["inchikey"] == raw[source_id][1],
                "AZ fold source identity mismatch/duplicate")
        used[source_id] = integer(row["fold"], 0, 9)
        require(assignment_folds.get(row["sample_uid"]) == used[source_id], "AZ fold/cache and independent current assignment differ")
    require(len(used) == 109 and {"az::" + key for key in used} == set(assignment_folds) and
            len(set(raw) - set(used)) == 11, "AZ must preserve fold109 plus extra11 raw records")
    result = [identity("som_az", source_id, "all", [smiles[source_id]], [values[1]],
                       memberships=["all_raw", "fold_" + str(used[source_id])] if source_id in used else ["all_raw", "raw_only"])
              for source_id, values in raw.items()]
    return result, {"raw_records": 120, "fold_union_records": 109, "additional_raw_records": 11,
                    "additional_raw_ids": sorted(set(raw) - set(used)), "omission_reason_inferred": False}


def v1_whole_scope_proof(*, total_rows, unique_source_ids, role_counts, embargo_class_counts, missing_identity_rows):
    expected = {"TRAIN": 11104772, "VAL": 11322, "FULL": 115760, "EMBARGO": 4900}
    require(total_rows == unique_source_ids == 11236754 and dict(role_counts) == expected and
            dict(embargo_class_counts) == {"known_fullkey_embargo": 4100, "unknown_non_h_composition_embargo": 800} and
            missing_identity_rows == 0, "Whole formal+4900 identity/role/unique-ID proof is incomplete")
    return {"status": "ALL_ORIGINAL_V1_ROLES_AND_4900_EMBARGO_PROJECTED",
            "records": total_rows, "effective_roles": expected, "later_common_filter_applied": False,
            "val_is_existing_routine": True, "routine_exported_twice": False}


def external_pending_manifest(catalog):
    datasets = {r["dataset"]: r for r in catalog["datasets"]}
    result = []
    for name in EXTERNAL_PENDING:
        source = datasets[name]
        result.append({"dataset": name, "status": "PENDING_ALL_SOURCE_ALL_SPLIT_PHYSICAL_IDENTITY_PROOF",
                       "required_roles": source["required_roles"],
                       "required_subdatasets": source.get("required_subdatasets"),
                       "all_source_identity_count": None, "all_source_identity_sha256": None,
                       "all_source_decontamination_accepted": False})
    return result
