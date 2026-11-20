"""Reuse compatible, closed B6 RDKit columns without reading task labels.

This adapter reads only source identity, RDKit values and their existing masks.
It does not read xTB payloads, regenerate geometry or fit/filter any fields.
An incompatible cache is ignored; the registered descriptor worker remains
the calculation path. Canonical D20 overrides remain the caller's priority.
"""
import json
from pathlib import Path

import numpy as np


POLICY = "RemoveHs on a source graph copy; native geometry/atom IDs untouched"
SMILES_SOURCES = frozenset(("qm9", "expansionrx", "az_exactsom"))


def version_tuple(value):
    try:
        return tuple(int(part) for part in str(value).split("."))
    except ValueError:
        return None


def unchanged_remove_hs(smiles):
    """Bind the old graph policy, without evaluating descriptors or hashes."""
    from rdkit import Chem
    if not isinstance(smiles, str) or not smiles:
        return False
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return False
    removed = Chem.RemoveHs(Chem.Mol(molecule))
    # These sources used the same MolFromSmiles constructor as D20. Reuse
    # only when the additional old RemoveHs operation leaves its graph intact.
    return (molecule.GetNumAtoms() == removed.GetNumAtoms()
            and Chem.MolToSmiles(molecule, isomericSmiles=True)
            == Chem.MolToSmiles(removed, isomericSmiles=True))


class B6L1Cache:
    def __init__(self, manifest, *, fields, rdkit_version, member_uids):
        self.manifest_path = str(Path(manifest).resolve())
        self.fields = tuple(fields)
        self.records = {}
        self.compatible, self.reason = False, None
        source = json.loads(Path(manifest).read_text(encoding="utf-8"))
        names = tuple(source.get("rdkit_descriptor_names", ()))
        expected_version, source_version = version_tuple(rdkit_version), version_tuple(source.get("rdkit_version"))
        if (source.get("schema") != "DATA_V1_DOWNSTREAM_BASELINE_DESCRIPTORS_V2"
                or source.get("status") != "SOURCE_SLICE_COMPLETE_WITH_EXPLICIT_MISSING"
                or source.get("target_or_annotation_values_decoded") is not False):
            self.reason = "not_the_closed_target_free_B6_format"
            return
        if source.get("rdkit_2D_graph_policy") != POLICY:
            self.reason = "unknown_source_graph_policy"
            return
        if expected_version is None or source_version != expected_version:
            self.reason = "RDKit_version_differs"
            return
        if (len(names) != len(set(names)) or len(self.fields) != len(set(self.fields))
                or set(names) != set(self.fields)):
            self.reason = "descriptor_field_set_differs"
            return
        self.compatible = True
        wanted = set(member_uids)
        if not wanted:
            return
        import pyarrow.parquet as pq
        columns = ["dataset", "member_uid", "source_ordinal", "rdkit_values", "rdkit_mask"]
        order = np.asarray([names.index(name) for name in self.fields], dtype=np.int64)
        for part in source["files"]:
            for batch in pq.ParquetFile(part["path"]).iter_batches(batch_size=1024, columns=columns, use_threads=False):
                for row in batch.to_pylist():
                    uid = row["member_uid"]
                    if uid not in wanted or row["dataset"] not in SMILES_SOURCES:
                        continue
                    values = np.asarray(row["rdkit_values"], dtype=np.float64)
                    valid = np.asarray(row["rdkit_mask"], dtype=bool)
                    if values.shape != (len(names),) or valid.shape != values.shape:
                        raise ValueError("Closed B6 source columns do not align with its field list")
                    record = (row["dataset"], row["source_ordinal"], values[order], valid[order])
                    self.records.setdefault(uid, []).append(record)

    def get(self, member_uid, smiles, source_ordinal=None):
        if not self.compatible:
            return None
        matches = self.records.get(member_uid, ())
        if source_ordinal is not None:
            matches = [row for row in matches if row[1] == source_ordinal]
        if len(matches) != 1 or not unchanged_remove_hs(smiles):
            return None
        _, _, values, valid = matches[0]
        # A missing source entry stays missing. The old B6 format has no
        # separate per-field numeric-event reason; do not invent that reason.
        return {name: float(value) if observed else None
                for name, value, observed in zip(self.fields, values, valid)}

    def provenance(self):
        return {"source": self.manifest_path, "compatible": self.compatible,
                "reason": self.reason, "normalization_fitted": False,
                "cache_fields_reordered_by_name": True, "task_labels_read": False,
                "missing_reason_resolution": "existing_B6_valid_or_missing_mask_only",
                "graph_binding": "same_MolFromSmiles_source_and_unchanged_RemoveHs"}
