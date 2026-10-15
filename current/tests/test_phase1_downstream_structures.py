"""Structure alignment failures must stay visible; target columns stay unused."""
from __future__ import annotations

from rdkit import Chem

from tools.phase1_audit_downstream_structures import (
    Deadline, audit_cyp_record, audit_qm_record, project_structure_row,
)


def write_xyz(path, numbers):
    table = Chem.GetPeriodicTable()
    rows = [str(len(numbers)), "UNUSED_TARGET_COMMENT=123456789"]
    # The fifth column is intentionally not numeric: it must never be parsed.
    rows += [f"{table.GetElementSymbol(z)} {index}.0 0.0 0.0 UNUSED_ATOMIC_LABEL" for index, z in enumerate(numbers)]
    rows.append("UNUSED_DATASET_TARGET_TAIL")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_qm_same_multiset_wrong_order_is_reported_without_permutation(tmp_path):
    mol = Chem.AddHs(Chem.MolFromSmiles("CO"))
    sequence = [atom.GetAtomicNum() for atom in mol.GetAtoms()]
    original = tmp_path / "original.xyz"
    write_xyz(original, sequence)
    valid = audit_qm_record({"SMILES": "CO", "xyz_path": str(original)}, tmp_path / "fold_assignments.csv", Deadline(5))
    assert valid["checks_passed"] and valid["same_atomic_number_order"]
    changed = sequence[:]
    changed[0], changed[1] = changed[1], changed[0]
    permuted = tmp_path / "permuted.xyz"
    write_xyz(permuted, changed)
    before = permuted.read_bytes()
    report = audit_qm_record({"SMILES": "CO", "xyz_path": str(permuted)}, tmp_path / "fold_assignments.csv", Deadline(5))
    assert report["same_element_multiset"] and report["same_atom_count"]
    assert not report["same_atomic_number_order"] and not report["checks_passed"]
    assert not report["permutation_applied"]
    assert report["first_order_mismatches"][0]["position_1based"] == 1
    assert permuted.read_bytes() == before
    assert "UNUSED" not in str(report)


def test_cyp_identity_equality_does_not_reorder_original_mol_block():
    source = Chem.RenumberAtoms(Chem.MolFromSmiles("CCO"), [2, 1, 0])
    block = Chem.MolToMolBlock(source)
    row = {"SMILES": "CCO", "SMILES_isomeric": "CCO", "mol_block": block, "n_atoms": "3"}
    report = audit_cyp_record(row, Deadline(5))
    assert report["checks_passed"] and report["identity_matches_source_mol_block"]
    assert report["n_atoms_matches_source"]
    assert report["mol_block_first_atomic_numbers"] == [8, 6, 6]
    assert not report["smiles_order_matches_mol_block"]
    assert not report["permutation_applied"] and row["mol_block"] == block
    assert "NOT PROVED" in report["som_source_index_map"]


def test_structure_projection_never_indexes_quantum_or_som_target_columns():
    class GuardedRow(list):
        def __getitem__(self, index):
            assert index not in {1, 3}, "A target field was selected"
            return super().__getitem__(index)

    header = ["SMILES", "target_atomization_energy", "sample_id", "all_som_atoms_1based_json", "fold"]
    row = GuardedRow(["CO", object(), "structure-1", object(), "2"])
    projected = project_structure_row(header, row)
    assert projected == {"SMILES": "CO", "sample_id": "structure-1", "fold": "2"}
