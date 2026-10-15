"""Synthetic source-order/unit/numbering cases; no benchmark labels or files."""
from __future__ import annotations

import hashlib

import pytest
from rdkit import Chem

from phychem_mfm.phase1.downstream_structures import (
    BOHR_TO_ANGSTROM, IDENTITY_CONSTRUCTION, READER_IDENTITY_VERSION,
    DownstreamStructureError, _identity_from_mol, convert_som_indices,
    read_az_raw_smiles, read_cyp_mol_block, read_qm7_xyz, read_xyz_structure,
)
from phychem_mfm.phase1.identity import canonical_hash, molecule_identity


def xyz_file(tmp_path, body: bytes, name="source.xyz"):
    path = tmp_path / name
    path.write_bytes(body)
    return path


def bond_pairs(mol):
    return {tuple(sorted((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())))
            for bond in mol.GetBonds()}


def specified_graph_with_coordinates(smiles, *, reflection=1):
    """Fix graph stereo before supplying arbitrary diagnostic 3D coordinates."""
    mol = Chem.MolFromSmiles(smiles)
    conformer = Chem.Conformer(mol.GetNumAtoms())
    conformer.Set3D(True)
    for index in range(mol.GetNumAtoms()):
        # Reflection changes coordinates, never the specified atom/bond stereo.
        conformer.SetAtomPosition(index, (reflection * float(index + 1),
                                         float((index * index) % 3), .3 * (index % 2)))
    mol.AddConformer(conformer)
    return mol


def test_xyz_bohr_source_rows_and_nonstandard_exponents(tmp_path):
    source = b"3\nopaque comment\nO 1D+0 -2d-1 3*^-2\nC .5 0. 1e+0\nH 0 0 0\n"
    path = xyz_file(tmp_path, source)
    result = read_qm7_xyz(path)
    assert result.atomic_numbers == (8, 6, 1)
    assert result.x == (7, 5, 0)
    assert result.source_atom_map == (0, 1, 2)
    assert result.pos_angstrom[0] == pytest.approx(
        (BOHR_TO_ANGSTROM, -.2 * BOHR_TO_ANGSTROM, .03 * BOHR_TO_ANGSTROM))
    assert result.provenance["source_units"] == "bohr"
    assert result.provenance["coordinate_scale"] == 0.529177210903
    assert result.provenance["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert result.identity is None and result.mol is None
    assert result.provenance["identity_status"] == "not inferred from coordinates"


def test_xyz_does_not_decode_invalid_comment_extra_column_or_target_tail(tmp_path):
    # Any attempt to UTF-8 decode a target-bearing line/column would fail.
    source = b"1\n\xff\x00 OPAQUE_COMMENT\n6 1 2 3 \xff INVALID_EXTRA_COLUMN\n\xfe OPAQUE_TAIL\n"
    path = xyz_file(tmp_path, source)
    result = read_xyz_structure(path, units="angstrom")
    assert result.x == (5,) and result.pos_angstrom == ((1., 2., 3.),)
    assert result.provenance["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert "OPAQUE" not in str(result.provenance)
    changed = source + b"\xff DIFFERENT_OPAQUE_BYTES\n"
    other = read_xyz_structure(xyz_file(tmp_path, changed, "other.xyz"), units="angstrom")
    assert other.pos_angstrom == result.pos_angstrom and other.x == result.x
    assert other.provenance["source_sha256"] != result.provenance["source_sha256"]
    assert path.read_bytes() == source


def test_same_element_xyz_permutation_is_not_undone(tmp_path):
    left = read_xyz_structure(xyz_file(tmp_path, b"2\n\nC 1 0 0\nC 2 0 0\n"), units="angstrom")
    right = read_xyz_structure(xyz_file(tmp_path, b"2\n\nC 2 0 0\nC 1 0 0\n", "swap.xyz"), units="angstrom")
    assert left.x == right.x == (5, 5)
    assert right.pos_angstrom == tuple(reversed(left.pos_angstrom))
    assert left.source_atom_map == right.source_atom_map == (0, 1)
    assert not right.provenance["permutation_applied"]
    assert right.provenance["mapping_audit_complete"] is False


@pytest.mark.parametrize("source", [
    b"0\n\n", b"-1\n\n", b"1.0\n\n", b"2\n\nC 0 0 0\n",
    b"1\n\nC 0 0\n", b"1\n\nXx 0 0 0\n", b"1\n\n0 0 0 0\n",
    b"1\n\n119 0 0 0\n", b"1\n\nC NaN 0 0\n", b"1\n\nC inf 0 0\n",
    b"1\n\nC 1e999 0 0\n", b"1\n\nC 1D 0 0\n", b"1\n\nC 1_0 0 0\n",
])
def test_xyz_rejects_invalid_structure_without_reading_labels(tmp_path, source):
    with pytest.raises(DownstreamStructureError):
        read_xyz_structure(xyz_file(tmp_path, source), units="angstrom")


@pytest.mark.parametrize("units", [None, "auto", "Angstrom", "nm"])
def test_xyz_requires_explicit_units(tmp_path, units):
    with pytest.raises(DownstreamStructureError, match="units"):
        read_xyz_structure(xyz_file(tmp_path, b"1\n\nH 0 0 0\n"), units=units)


def test_cyp_same_element_graph_permutation_preserves_bond_atom_indices():
    original = Chem.MolFromSmiles("CCO")
    permuted = Chem.RenumberAtoms(original, [1, 0, 2])
    block = Chem.MolToMolBlock(permuted)
    result = read_cyp_mol_block(block, expected_n_atoms=3)
    unpermuted = read_cyp_mol_block(Chem.MolToMolBlock(original))
    # Both Z sequences/full keys agree, while the oxygen is attached to a
    # different source carbon index. Equal Z/key never licenses reordering.
    assert result.atomic_numbers == unpermuted.atomic_numbers == (6, 6, 8)
    assert result.identity.inchikey == unpermuted.identity.inchikey
    assert bond_pairs(result.mol) == bond_pairs(permuted)
    assert bond_pairs(result.mol) != bond_pairs(unpermuted.mol)
    assert result.source_atom_map == (0, 1, 2)
    assert [atom.GetIntProp("_phase1_source_atom_index") for atom in result.mol.GetAtoms()] == [0, 1, 2]
    assert result.provenance["source_sha256"] == hashlib.sha256(block.encode()).hexdigest()


@pytest.mark.parametrize("is_3d", [False, True])
def test_cyp_dimension_flags_do_not_approve_geometry(is_3d):
    mol = Chem.MolFromSmiles("CCCO")
    conformer = Chem.Conformer(mol.GetNumAtoms())
    conformer.Set3D(is_3d)
    for index in range(mol.GetNumAtoms()):
        conformer.SetAtomPosition(index, (float(index), float(index % 2), .5 * index if is_3d else 0.))
    mol.AddConformer(conformer)
    result = read_cyp_mol_block(Chem.MolToMolBlock(mol))
    assert result.provenance["source_conformer_dimensions"] == ["3D" if is_3d else "2D"]
    assert result.pos_angstrom is None
    assert result.provenance["geometry_ready_for_encoder"] is False
    assert result.provenance["coordinate_units"] == "unverified"


def test_cyp_retains_explicit_h_az_uses_author_default_h_policy():
    hydrogenated = Chem.AddHs(Chem.MolFromSmiles("CO"))
    cyp = read_cyp_mol_block(Chem.MolToMolBlock(hydrogenated))
    assert cyp.n_atoms == hydrogenated.GetNumAtoms()
    assert cyp.atomic_numbers == tuple(atom.GetAtomicNum() for atom in hydrogenated.GetAtoms())
    assert cyp.provenance["parser_options"]["removeHs"] is False
    # Default raw parser removes the ordinary explicit H but retains isotope H.
    az = read_az_raw_smiles("[H]OC")
    isotope = read_az_raw_smiles("[2H]OC")
    assert az.atomic_numbers == (8, 6) and isotope.atomic_numbers == (1, 8, 6)
    assert az.provenance["parser_options"]["removeHs"] is True
    assert isotope.mol.GetAtomWithIdx(0).GetIsotope() == 2


def test_az_raw_order_survives_canonical_identity_metadata():
    result = read_az_raw_smiles("OCC")
    assert result.atomic_numbers == (8, 6, 6)
    assert result.identity.canonical_isomeric_smiles == "CCO"
    assert result.source_atom_map == (0, 1, 2)
    assert result.mol.GetAtomWithIdx(0).GetAtomicNum() == 8
    assert result.pos_angstrom is None and not result.provenance["geometry_ready_for_encoder"]


def test_full_stereo_identity_is_not_replaced_by_nonisomeric_smiles():
    left, right = "F[C@H](Cl)Br", "F[C@@H](Cl)Br"
    az_left, az_right = read_az_raw_smiles(left), read_az_raw_smiles(right)
    assert az_left.atomic_numbers == az_right.atomic_numbers
    assert az_left.identity.inchikey != az_right.identity.inchikey
    cyp = read_cyp_mol_block(Chem.MolToMolBlock(Chem.MolFromSmiles(left)))
    assert cyp.identity.inchikey == az_left.identity.inchikey


@pytest.mark.parametrize("smiles", ["F[C@H](Cl)Br", "F[C@@H](Cl)Br", "[13CH3]O", "C[NH3+]", "[2H]OC"])
def test_specified_graph_identity_ignores_3d_and_reflected_coordinates_without_mutating_source(smiles):
    expected = molecule_identity(smiles)
    plain = Chem.MolFromSmiles(smiles)
    for mol in (plain, specified_graph_with_coordinates(smiles),
                specified_graph_with_coordinates(smiles, reflection=-1)):
        before = mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
        result = _identity_from_mol(mol, "specified_source_graph")
        assert result.inchikey == expected.inchikey
        assert result.canonical_isomeric_smiles == expected.canonical_isomeric_smiles
        assert mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before


@pytest.mark.parametrize("left,right", [
    ("F[C@H](Cl)Br", "F[C@@H](Cl)Br"), ("CO", "[13CH3]O"), ("CN", "C[NH3+]"),
])
def test_graph_identity_keeps_stereo_isotope_and_charge_distinctions(left, right):
    first = _identity_from_mol(specified_graph_with_coordinates(left), "mol_block")
    second = _identity_from_mol(specified_graph_with_coordinates(right), "mol_block")
    assert first.inchikey != second.inchikey
    assert first.policy == second.policy == "standard_full_inchikey_v1"


def test_source_graph_identity_provenance_binds_v2_and_retains_default_key_only_as_diagnostic():
    source = specified_graph_with_coordinates("F[C@H](Cl)Br")
    block = Chem.MolToMolBlock(source)
    parsed = Chem.MolFromMolBlock(block, sanitize=True, removeHs=False, strictParsing=True)
    expected_graph = molecule_identity(Chem.MolToSmiles(Chem.Mol(parsed), canonical=True, isomericSmiles=True))
    expected_default = Chem.MolToInchiKey(Chem.Mol(parsed))
    result = read_cyp_mol_block(block)
    assert result.identity.inchikey == expected_graph.inchikey
    assert result.n_atoms == parsed.GetNumAtoms()
    assert bond_pairs(result.mol) == bond_pairs(parsed)
    assert result.mol.GetNumConformers() == parsed.GetNumConformers() == 1
    def positions(mol):
        return [(point.x, point.y, point.z) for point in
                (mol.GetConformer().GetAtomPosition(i) for i in range(mol.GetNumAtoms()))]
    assert positions(result.mol) == positions(parsed)
    metadata = result.provenance
    assert metadata["source_contract"] == "source_atom_order_v1"
    assert metadata["reader_identity_version"] == READER_IDENTITY_VERSION == 2
    assert metadata["identity_construction"] == IDENTITY_CONSTRUCTION == "rdkit_graph_no_conformers_v1"
    assert metadata["conformer_identity_input"] == "ignored_on_copy"
    assert metadata["graph_identity_inchikey"] == expected_graph.inchikey
    assert metadata["source_mol_default_inchikey"] == expected_default
    assert metadata["source_mol_default_inchikey_differs_from_graph"] == (expected_default != expected_graph.inchikey)
    assert metadata["source_mol_default_inchikey_scope"] == "diagnostic only; never a grouping selector"
    assert metadata["source_mol_default_inchikey_conformer_dimensions"] == ["3D"]
    contract = dict(metadata)
    observed = contract.pop("identity_provenance_hash")
    assert observed == canonical_hash(contract)
    contract["reader_identity_version"] = 1
    assert canonical_hash(contract) != observed


def test_unavailable_conformer_default_diagnostic_does_not_select_or_reject_graph_identity(monkeypatch):
    block = Chem.MolToMolBlock(specified_graph_with_coordinates("CO"))
    original = Chem.MolToInchiKey
    def graph_only_inchi_key(mol, *args, **kwargs):
        if mol.GetNumConformers():
            raise RuntimeError("Synthetic diagnostic-only failure")
        return original(mol, *args, **kwargs)
    monkeypatch.setattr(Chem, "MolToInchiKey", graph_only_inchi_key)
    result = read_cyp_mol_block(block)
    assert result.identity.inchikey == molecule_identity("CO").inchikey
    assert result.mol.GetNumConformers() == 1
    assert result.provenance["source_mol_default_inchikey"] is None
    assert result.provenance["source_mol_default_inchikey_differs_from_graph"] is None
    assert result.provenance["source_mol_default_inchikey_error"] == "RuntimeError"


def test_invalid_mol_block_or_atom_count_is_explicit_failure():
    with pytest.raises(DownstreamStructureError):
        read_cyp_mol_block("invalid mol block")
    with pytest.raises(DownstreamStructureError, match="n_atoms"):
        read_cyp_mol_block(Chem.MolToMolBlock(Chem.MolFromSmiles("CO")), expected_n_atoms=3)
    with pytest.raises(DownstreamStructureError):
        read_az_raw_smiles("not a valid structure")


def test_som_explicit_0_based_preserves_zero_1_based_subtracts_once():
    assert convert_som_indices([0, 2], index_base=0, n_source_atoms=3) == (0, 2)
    assert convert_som_indices("0, 2", index_base=0, n_source_atoms=3) == (0, 2)
    once = convert_som_indices("1 3", index_base=1, n_source_atoms=3)
    assert once == (0, 2)
    assert convert_som_indices(once, index_base=0, n_source_atoms=3) == once
    with pytest.raises(DownstreamStructureError):
        convert_som_indices(once, index_base=1, n_source_atoms=3)
    assert convert_som_indices([2, 0], index_base=0, n_source_atoms=3) == (2, 0)


@pytest.mark.parametrize("indices", [-1, {0, 1}, {"atoms": [0]}, [True], [0.], ["0"],
                                     [-1], [3], [0, 0], "1, 2 3", "1,,2", "[0]", "1.0", "-1", b"0"])
def test_som_rejects_ambiguity_negative_range_and_duplicate_indices(indices):
    with pytest.raises(DownstreamStructureError):
        convert_som_indices(indices, index_base=0, n_source_atoms=3)


@pytest.mark.parametrize("base", [None, True, 2, -1, "0", 0.])
def test_som_rejects_implicit_or_invalid_basis(base):
    with pytest.raises(DownstreamStructureError, match="index_base"):
        convert_som_indices([1], index_base=base, n_source_atoms=3)


def test_som_no_automatic_source_range_or_base_guessing():
    with pytest.raises(DownstreamStructureError):
        convert_som_indices([0], index_base=1, n_source_atoms=3)
    with pytest.raises(DownstreamStructureError):
        convert_som_indices([1], index_base=0, n_source_atoms=0)
    with pytest.raises(TypeError):
        convert_som_indices([0], n_source_atoms=3)
    assert convert_som_indices([], index_base=0, n_source_atoms=3) == ()
