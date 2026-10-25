"""Whole local source/fold proofs and original identity rows, independent of common."""
from __future__ import annotations

from ..common import require
from ..identity_v2 import coverage_v2 as coverage, projection_v2 as projection
from . import readers


LOCAL_MOLNET = {
    "local_moleculenet_bace": ("bace", ("mol", "CID", "Model"), "mol"),
    "local_moleculenet_bbbp": ("bbbp", ("num", "name", "smiles"), "smiles"),
    "local_moleculenet_clintox": ("clintox", ("smiles",), "smiles"),
    "local_moleculenet_esol": ("esol", ("Compound ID", "smiles"), "smiles"),
    "local_moleculenet_freesolv": ("freesolv", ("smiles",), "smiles"),
    "local_moleculenet_lipophilicity": ("lipophilicity", ("CMPD_CHEMBLID", "smiles"), "smiles"),
}


def whole_fold_proof(tickets, dataset, source_dataset, columns, id_column, count):
    assignment = tickets[dataset + "_all_assignment_fold_assignments"]
    folds = {i: readers.csv_identity_rows(tickets[dataset + "_fold_" + str(i + 1) + "_fold_" + str(i + 1)], columns)
             for i in range(10)}
    return coverage.assignment_fold_union(source_dataset, readers.csv_identity_rows(assignment, columns), folds,
                                          columns, id_column, count)


def prepare_small_cohorts(tickets):
    cyp_folds, cyp_proof = whole_fold_proof(tickets, "som_cyp", "cyp_isoform", coverage.CYP_FOLD_COLUMNS, "sample_uid", 2003)
    az_folds, az_proof = whole_fold_proof(tickets, "som_az", "az_exactsom", coverage.AZ_FOLD_COLUMNS, "sample_uid", 109)
    qm7_folds, qm7_proof = whole_fold_proof(tickets, "qm7", "qm7", coverage.QM_FOLD_COLUMNS, "sample_id", 7165)
    qm9_folds, qm9_proof = whole_fold_proof(tickets, "qm9", "qm9", coverage.QM_FOLD_COLUMNS, "sample_id", 133885)
    qm7_folds = coverage.qm_original_universe(qm7_folds, "qm7")
    qm9_folds = coverage.qm_original_universe(qm9_folds, "qm9")
    cyp_rows, cyp_source_proof = coverage.cyp_rows(readers.json_identity_rows(tickets["ledger_cyp_sources"], "cyp_sources"),
        readers.json_identity_rows(tickets["ledger_cyp_folds"], "cyp_folds"),
        [t for t in tickets.values() if t.locator["dataset"] == "som_cyp" and t.locator["scope_role"] == "all_raw"], assignment_folds=cyp_folds)
    az_rows, az_source_proof = coverage.az_rows(readers.json_identity_rows(tickets["ledger_az_sources"], "az_sources"),
        readers.json_identity_rows(tickets["ledger_az_folds"], "az_folds"),
        readers.csv_identity_rows(tickets["som_az_all_raw_az_120_compounds"], ("Compound ID", "SMILES")), assignment_folds=az_folds)
    qm7_rows = [projection.qm7_row(sample_id, values, qm7_folds[sample_id])
                for sample_id, values in readers.qm7_native_z(tickets["qm7_raw_mat_Z_only"])]
    historical_qm9, seen_qm7 = {}, set()
    for row in readers.json_identity_rows(tickets["ledger_qm_source_records"], "qm_sources"):
        if row["dataset"] == "qm9":
            sample_id = coverage.integer(row["sample_id"], 1, 133885)
            require(sample_id not in historical_qm9 and row["source_sha256"] and row["source_bytes"],
                    "Original QM9 source hash/ID missing; never use successful-only ledger subset")
            historical_qm9[sample_id] = {"source_sha256": row["source_sha256"], "source_bytes": row["source_bytes"]}
        else:
            require(row["dataset"] == "qm7", "Unexpected dataset in whole QM source ledger")
            seen_qm7.add(coverage.integer(row["sample_id"], 1, 7165))
    require(set(historical_qm9) == set(range(1, 133886)) and seen_qm7 == set(range(1, 7166)), "Whole141050 original QM ledger scope differs")
    facts = {"som_cyp_folds": cyp_proof, "som_cyp_raw": cyp_source_proof,
             "som_az_folds": az_proof, "som_az_raw": az_source_proof, "qm7_folds": qm7_proof, "qm9_folds": qm9_proof,
             "qm7_composition_only_records": len(qm7_rows), "qm9_source_member_hash_records": len(historical_qm9)}
    return cyp_rows + az_rows + qm7_rows, qm9_folds, historical_qm9, facts


def graph_tasks(tickets, qm9_folds, historical_qm9, *, size=512):
    """Original source dictionaries only; graph identity calculations run in workers."""
    batch = []
    for role in ("train", "test"):
        count = 0
        for count, row in enumerate(readers.csv_identity_rows(tickets["expansionrx_" + role], ("Molecule Name", "SMILES")), 1):
            batch.append({"kind": "expansionrx", "role": role, "ordinal": count, "row": row})
            if len(batch) == size:
                yield batch; batch = []
        require(count == {"train": 5326, "test": 2282}[role], "Whole ExpansionRx source count differs")
    for source_id, (name, columns, smiles_column) in LOCAL_MOLNET.items():
        count = 0
        for count, row in enumerate(readers.csv_identity_rows(tickets[source_id], columns), 1):
            batch.append({"kind": "local_moleculenet", "source": source_id, "name": name, "ordinal": count,
                          "row": row, "smiles_column": smiles_column})
            if len(batch) == size:
                yield batch; batch = []
        require(count == tickets[source_id].physical_count, "Local full-source MoleculeNet count differs")
    for sample_id, payload in readers.qm9_archive_rows(tickets["qm9_raw_original_archive"]):
        batch.append({"kind": "qm9", "sample_id": sample_id, "payload": payload, "fold": qm9_folds[sample_id],
                      "historical_source": historical_qm9[sample_id]})
        if len(batch) == size:
            yield batch; batch = []
    if batch:
        yield batch


def project_task(value):
    kind = value["kind"]
    if kind == "expansionrx":
        return projection.expansionrx_row(value["row"], value["role"], value["ordinal"])
    if kind == "qm9":
        return projection.qm9_row(value["sample_id"], value["payload"], value["fold"], value["historical_source"])
    require(kind == "local_moleculenet", "Unexpected graph identity task")
    row, field = value["row"], value["smiles_column"]
    keys, errors = projection.source_smiles_keys({field: row[field]})
    result = projection.identity("moleculenet_" + value["name"], str(value["ordinal"]), "all", [row[field]], keys,
                                 memberships=["all"] + (["source_Model:" + row["Model"]] if row.get("Model") else []),
                                 unresolved_variant=bool(errors))
    result.update(original_identity_columns=row, identity_errors=errors,
                  source_record_1based=value["ordinal"], source_locator_id=value["source"])
    return result
