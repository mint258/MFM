"""Independent synthetic native-order geometry generation contracts.

Actual small RDKit molecules exercise generation; patched calls only force
failure branches. No real data, labels, split selection or physical truth is
used. These tests are statically authored locally and run only on the server.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import random

import numpy as np
import pytest
from rdkit import Chem, rdBase
import torch

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.phase1 import generated_geometry as generated
from phychem_mfm.phase1.downstream_readout import SourceAlignedH0Readout
from phychem_mfm.phase1.downstream_structures import read_az_raw_smiles, read_cyp_mol_block
from phychem_mfm.phase1.generated_geometry import (
    GeneratedGeometryError, prepare_native_generated_geometry,
)


def all_props(mol):
    return mol.ToBinary(Chem.PropertyPickleOptions.AllProps)


def independent_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def independent_tensor_hash(tensor):
    value = tensor.detach().cpu().contiguous()
    raw = (str(value.dtype).encode() + b"\0"
           + independent_hash(tuple(value.shape)).encode("ascii") + b"\0"
           + value.numpy().tobytes())
    return hashlib.sha256(raw).hexdigest()


def source_block():
    # Independent rows: C/H/O/H/N; source H is interleaved, not a suffix.
    symbols = ("C", "H", "O", "H", "N")
    coordinates = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.),
                   (0., 2., 0.), (-1., 0., 0.))
    bonds = ((1, 2), (1, 3), (3, 4), (1, 5))
    lines = ["synthetic native source", f"{'SYNTHETIC':<20}2D", "",
             "  5  4  0  0  0  0            999 V2000"]
    lines += [f"{x:10.4f}{y:10.4f}{z:10.4f} {symbol:<3} 0  0  0  0  0  0  0  0  0  0  0  0"
              for symbol, (x, y, z) in zip(symbols, coordinates)]
    lines += [f"{left:3d}{right:3d}  1  0  0  0  0" for left, right in bonds]
    return "\n".join(lines + ["M  END", ""])


def prepare(structure=None, *, seed=731, **kwargs):
    return prepare_native_generated_geometry(
        read_az_raw_smiles("CCO") if structure is None else structure,
        seed=seed, **kwargs)


def rng_snapshot():
    return random.getstate(), np.random.get_state(), torch.get_rng_state().clone()


def assert_rng_equal(snapshot):
    py, np_state, th = snapshot
    assert random.getstate() == py and torch.equal(torch.get_rng_state(), th)
    now = np.random.get_state()
    assert now[0] == np_state[0] and np.array_equal(now[1], np_state[1])
    assert now[2:] == np_state[2:]


@pytest.mark.parametrize("raw_smiles,numbers", [
    ("CCO", (6, 6, 8)),
    ("[2H]OC", (1, 8, 6)),
    ("C[C@H](O)F", (6, 6, 8, 9)),
    ("F/C=C/F", (9, 6, 6, 9)),
])
def test_actual_small_graphs_return_exact_native_rows(raw_smiles, numbers):
    structure = read_az_raw_smiles(raw_smiles)
    assert structure.atomic_numbers == numbers
    before = all_props(structure.mol)
    result = prepare(structure)
    batch = result.encoder_batch
    assert set(batch.keys()) == {"x", "pos", "batch", "ptr"}
    assert batch.x.dtype == torch.long and batch.x.tolist() == [z - 1 for z in numbers]
    assert batch.pos.dtype == torch.float32 and batch.pos.shape == (len(numbers), 3)
    assert result.native_coordinates_float64.dtype == torch.float64
    assert result.native_coordinates_float64.shape == (len(numbers), 3)
    assert result.native_coordinates_float64.device.type == "cpu"
    assert torch.equal(batch.pos, result.native_coordinates_float64.float())
    assert torch.isfinite(batch.pos).all()
    assert batch.batch.tolist() == [0] * len(numbers)
    assert batch.ptr.tolist() == [0, len(numbers)]
    assert result.source_atom_ids.tolist() == list(range(len(numbers)))
    assert all(value.device.type == "cpu" for value in
               (batch.x, batch.pos, batch.batch, batch.ptr, result.source_atom_ids))
    assert all_props(structure.mol) == before
    with pytest.raises(FrozenInstanceError):
        result.source_atom_ids = torch.arange(len(numbers))


def test_interleaved_source_h_and_original_2d_conformer_are_preserved():
    structure = read_cyp_mol_block(source_block())
    assert structure.atomic_numbers == (6, 1, 8, 1, 7)
    assert structure.mol.GetNumConformers() == 1
    assert structure.mol.GetConformer().Is3D() is False
    structure.mol.SetProp("synthetic_provenance", "keep complete original properties")
    structure.mol.GetAtomWithIdx(1).SetProp("native_h", "source row one")
    before = all_props(structure.mol)
    original_coords = structure.mol.GetConformer().GetPositions().copy()
    result = prepare(structure)
    assert result.encoder_batch.x.tolist() == [5, 0, 7, 0, 6]
    assert result.source_atom_ids.tolist() == [0, 1, 2, 3, 4]
    assert result.encoder_batch.ptr.tolist() == [0, 5]
    assert all_props(structure.mol) == before
    assert np.array_equal(structure.mol.GetConformer().GetPositions(), original_coords)


@pytest.mark.parametrize("raw_smiles", ["CCO", "C[C@H](O)F"])
def test_same_seed_actual_repeat_is_byte_deterministic_without_global_rng(raw_smiles):
    structure = read_az_raw_smiles(raw_smiles)
    before = all_props(structure.mol)
    rng = rng_snapshot()
    legacy = Chem.GetUseLegacyStereoPerception()
    first, second = prepare(structure, seed=42), prepare(structure, seed=42)
    assert torch.equal(first.encoder_batch.pos, second.encoder_batch.pos)
    assert first.provenance == second.provenance
    assert_rng_equal(rng)
    assert Chem.GetUseLegacyStereoPerception() == legacy
    assert all_props(structure.mol) == before


@pytest.mark.parametrize("seed", [True, None, -1, 2**31, 0.0, "731"])
def test_seed_is_explicit_bounded_plain_integer(seed):
    with pytest.raises(GeneratedGeometryError):
        prepare(seed=seed)


def test_omitted_seed_is_not_inferred():
    with pytest.raises(TypeError):
        prepare_native_generated_geometry(read_az_raw_smiles("CCO"))


@pytest.mark.parametrize("name,cap", [
    ("max_native_atoms", True), ("max_native_atoms", 0),
    ("max_native_atoms", 257), ("max_work_atoms", False),
    ("max_work_atoms", 0), ("max_work_atoms", 513),
])
def test_atom_caps_are_plain_bounded_positive_integers(name, cap):
    with pytest.raises(GeneratedGeometryError):
        prepare(**{name: cap})


def test_native_cap_and_temporary_addh_cap_reject_instead_of_filtering():
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure, max_native_atoms=2)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure, max_native_atoms=3, max_work_atoms=3)
    assert all_props(structure.mol) == before
    assert prepare(structure, max_native_atoms=3, max_work_atoms=9).encoder_batch.x.numel() == 3


@pytest.mark.parametrize("structure", [None, "CCO", {"mol": "CCO"}])
def test_api_rejects_values_without_source_structure_contract(structure):
    with pytest.raises(GeneratedGeometryError):
        prepare_native_generated_geometry(structure, seed=731)


@pytest.mark.parametrize("field,value", [
    ("atomic_numbers", (6, 8, 6)), ("x", (5, 0, 7)),
    ("source_atom_map", (1, 0, 2)), ("mol", None),
])
def test_source_contract_drift_fails_without_mutating_original(field, value):
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    altered = replace(structure, **{field: value})
    with pytest.raises(GeneratedGeometryError):
        prepare(altered)
    assert all_props(structure.mol) == before


@pytest.mark.parametrize("raw_smiles", ["CC.O", "[Na+].[Cl-]"])
def test_actual_disconnected_graph_is_unsupported_without_largest_fragment_selection(raw_smiles):
    structure = read_az_raw_smiles(raw_smiles)
    before = all_props(structure.mol)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


def test_actual_unsupported_forcefield_element_fails_without_uff_fallback():
    structure = read_az_raw_smiles("[Xe]")
    before = all_props(structure.mol)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


def test_outputs_are_owned_and_separate_calls_do_not_alias():
    structure = read_az_raw_smiles("[2H]OC")
    before = all_props(structure.mol)
    first, second = prepare(structure), prepare(structure)
    expected = second.encoder_batch.pos.clone()
    expected64 = second.native_coordinates_float64.clone()
    first.native_coordinates_float64.add_(50.)
    assert torch.equal(first.encoder_batch.pos, expected)
    first.encoder_batch.pos.add_(100.)
    first.encoder_batch.x.fill_(0)
    first.source_atom_ids[0] = 99
    assert torch.equal(second.encoder_batch.pos, expected)
    assert torch.equal(second.native_coordinates_float64, expected64)
    assert second.encoder_batch.x.tolist() == [0, 7, 5]
    assert second.source_atom_ids.tolist() == [0, 1, 2]
    assert all_props(structure.mol) == before


def test_receipt_hashes_actual_f64_fp32_transport_and_candidate_boundaries():
    structure = read_cyp_mol_block(source_block())
    before = all_props(structure.mol)
    result = prepare(structure, seed=731)
    proof = result.provenance
    assert proof["schema_version"] == "phase1_native_generated_geometry_v1"
    assert proof["state"] == "NOT_FROZEN" and proof["formal_eligible"] is False
    assert proof["geometry_status"] == "GENERATED_CANDIDATE_READY"
    assert proof["source_n_atoms"] == proof["source_native_rows"] == 5
    assert proof["native_explicit_h_atoms"] == 2
    assert proof["work_n_atoms"] > 5
    assert proof["scratch_added_h_atoms"] == proof["work_n_atoms"] - 5
    assert proof["native_to_work_atom_ids"] == list(range(5))
    assert proof["extra_work_h_encoder_rows"] == 0
    assert proof["source_sha256"] == structure.provenance["source_sha256"]
    assert proof["source_structure_allprops_sha256"] == hashlib.sha256(before).hexdigest()
    assert proof["source_atomic_number_order_sha256"] == independent_hash((6, 1, 8, 1, 7))
    assert proof["generated_native_coordinates_float64_sha256"] == independent_tensor_hash(result.native_coordinates_float64)
    assert "generated_native_coordinates_float64" not in proof
    tensors = {name: getattr(result.encoder_batch, name) for name in ("x", "pos", "batch", "ptr")}
    tensors["source_atom_ids"] = result.source_atom_ids
    assert proof["encoder_tensor_hashes"] == {name: independent_tensor_hash(value) for name, value in tensors.items()}
    error = (result.native_coordinates_float64 - result.encoder_batch.pos.double()).abs().max().item()
    assert proof["quantization_max_abs_error"] == error
    assert proof["recipe_sha256"] == independent_hash(proof["recipe"])
    bound = dict(proof)
    own_hash = bound.pop("geometry_provenance_sha256")
    assert own_hash == independent_hash(bound)
    assert proof["source_units"] == "not used or inferred"
    assert proof["output_units"] == "angstrom"
    for key in ("source_units_independently_verified", "output_units_independently_verified",
                "chemical_geometry_independently_verified", "source_file_record_association_independently_verified",
                "source_graph_identity_independently_verified", "atom_permutation_applied",
                "centering_applied", "scaling_applied"):
        assert proof[key] is False
    assert proof["source_structure_preserved"] and proof["native_graph_preserved"]
    assert proof["conformer_generated"] and proof["tensor_transport_verified"]
    assert proof["mmff_aromaticity_typing_on_separate_copy"] and proof["mmff_status"] == 0
    recipe = proof["recipe"]
    assert recipe["rdkit_version"] == "2025.09.5" and recipe["use_legacy_stereo_perception"] is True
    assert recipe["embedding"] == "ETKDGv3"
    assert recipe["embedding_calls"] == recipe["returned_conformers"] == recipe["numThreads"] == 1
    assert recipe["randomSeed"] == 731 and recipe["maxIterations"] == 200
    assert recipe["timeout_seconds"] == 2 and recipe["clearConfs"] and recipe["enforceChirality"]
    assert recipe["mmff_variant"] == "MMFF94" and recipe["mmff_max_iterations"] == 500
    assert recipe["fallback"] == "none"
    assert all_props(structure.mol) == before


@pytest.mark.parametrize("raw_smiles", ["C[C@H](O)F", "F/C=C/F"])
def test_independent_native_coordinate_stereo_decoder_matches_defined_source(raw_smiles):
    structure = read_az_raw_smiles(raw_smiles)
    result = prepare(structure)
    reference = Chem.Mol(structure.mol)
    reference.RemoveAllConformers()
    Chem.AssignStereochemistry(reference, cleanIt=True, force=True)
    actual = Chem.Mol(structure.mol)
    actual.RemoveAllConformers()
    Chem.RemoveStereochemistry(actual)
    conf = Chem.Conformer(structure.n_atoms)
    conf.Set3D(True)
    for index, row in enumerate(result.native_coordinates_float64.tolist()):
        conf.SetAtomPosition(index, row)
    actual.AddConformer(conf, assignId=True)
    Chem.AssignStereochemistryFrom3D(actual, confId=0, replaceExistingTags=True)
    if raw_smiles == "C[C@H](O)F":
        assert reference.GetAtomWithIdx(1).GetProp("_CIPCode") == actual.GetAtomWithIdx(1).GetProp("_CIPCode")
        checked = result.provenance["stereo_validation"]["specified_tetrahedral_centers"]
        assert len(checked) == 1 and checked[0]["native_atom_id"] == 1
        assert checked[0]["expected_cip"] == checked[0]["decoded_cip"] == actual.GetAtomWithIdx(1).GetProp("_CIPCode")
    else:
        assert reference.GetBondWithIdx(1).GetStereo() == actual.GetBondWithIdx(1).GetStereo()
        checked = result.provenance["stereo_validation"]["specified_alkene_bonds"]
        assert len(checked) == 1 and checked[0]["source_bond_id"] == 1
        assert checked[0]["expected_stereo"] == checked[0]["decoded_stereo"] == str(actual.GetBondWithIdx(1).GetStereo())
    assert result.provenance["stereo_validation"]["unspecified_stereo_promoted_to_source_features"] is False


def test_real_aromatic_mmff_typing_copy_can_preserve_native_template():
    structure = read_az_raw_smiles("c1ccccc1O")
    before = all_props(structure.mol)
    result = prepare(structure)
    assert result.encoder_batch.x.tolist() == [5] * 6 + [7]
    assert result.encoder_batch.pos.shape == (7, 3)
    assert result.provenance["mmff_status"] == 0
    assert all_props(structure.mol) == before


def test_missing_mmff_parameters_fail_without_optimizer_or_fallback(monkeypatch):
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    monkeypatch.setattr(generated.AllChem, "MMFFHasAllMoleculeParams", lambda _mol: False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Missing MMFF parameters must not optimize or fall back")

    monkeypatch.setattr(generated.AllChem, "MMFFOptimizeMolecule", forbidden)
    monkeypatch.setattr(generated.AllChem, "UFFOptimizeMolecule", forbidden)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


@pytest.mark.parametrize("status", [1, -1])
def test_nonconverged_or_failed_mmff_returns_no_candidate(monkeypatch, status):
    structure = read_az_raw_smiles("CCO")
    before, rng = all_props(structure.mol), rng_snapshot()
    monkeypatch.setattr(generated.AllChem, "MMFFOptimizeMolecule", lambda *_args, **_kwargs: status)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before
    assert_rng_equal(rng)


def test_embed_failure_is_single_call_no_retry_or_optimizer(monkeypatch):
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    calls = []

    def failure(_mol, params):
        calls.append((params.randomSeed, params.numThreads, params.maxIterations, params.timeout))
        return -1

    def forbidden(*_args, **_kwargs):
        pytest.fail("Failed embedding cannot advance to optimization")

    monkeypatch.setattr(generated.AllChem, "EmbedMolecule", failure)
    monkeypatch.setattr(generated.AllChem, "MMFFOptimizeMolecule", forbidden)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure, seed=42)
    assert calls == [(42, 1, 200, 2)]
    assert all_props(structure.mol) == before


@pytest.mark.parametrize("operation", ["AddHs", "EmbedMolecule", "MMFFOptimizeMolecule"])
def test_library_exceptions_are_wrapped_without_source_or_rng_mutation(monkeypatch, operation):
    structure = read_az_raw_smiles("CCO")
    before, rng = all_props(structure.mol), rng_snapshot()

    def broken(*_args, **_kwargs):
        raise RuntimeError("synthetic library failure")

    namespace = generated.Chem if operation == "AddHs" else generated.AllChem
    monkeypatch.setattr(namespace, operation, broken)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before
    assert_rng_equal(rng)


def test_same_element_native_permutation_after_addhs_is_rejected(monkeypatch):
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    original_addhs = generated.Chem.AddHs

    def reordered(mol, **kwargs):
        actual = original_addhs(mol, **kwargs)
        # C/C retain equal Z, so a symbols-only check cannot catch this drift.
        order = list(range(actual.GetNumAtoms()))
        order[0], order[1] = order[1], order[0]
        return Chem.RenumberAtoms(actual, order)

    monkeypatch.setattr(generated.Chem, "AddHs", reordered)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


def test_mmff_nonaromatic_bond_type_drift_is_rejected(monkeypatch):
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    actual_optimizer = generated.AllChem.MMFFOptimizeMolecule

    def drift(mol, **kwargs):
        status = actual_optimizer(mol, **kwargs)
        assert status == 0
        bond = mol.GetBondWithIdx(0)
        assert not bond.GetIsAromatic() and bond.GetBondType() == Chem.BondType.SINGLE
        bond.SetBondType(Chem.BondType.DOUBLE)
        return status

    monkeypatch.setattr(generated.AllChem, "MMFFOptimizeMolecule", drift)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


def test_coordinates_mirroring_defined_tetrahedral_center_is_rejected(monkeypatch):
    structure = read_az_raw_smiles("C[C@H](O)F")
    before = all_props(structure.mol)
    actual_optimizer = generated.AllChem.MMFFOptimizeMolecule

    def reflected(mol, **kwargs):
        status = actual_optimizer(mol, **kwargs)
        assert status == 0
        conf = mol.GetConformer(kwargs["confId"])
        for index in range(mol.GetNumAtoms()):
            point = conf.GetAtomPosition(index)
            conf.SetAtomPosition(index, (-point.x, point.y, point.z))
        return status

    monkeypatch.setattr(generated.AllChem, "MMFFOptimizeMolecule", reflected)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


@pytest.mark.parametrize("coordinate", [float("nan"), 1e40])
def test_nonfinite_or_fp32_overflow_optimized_coordinates_fail_closed(monkeypatch, coordinate):
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    actual_optimizer = generated.AllChem.MMFFOptimizeMolecule

    def altered(mol, **kwargs):
        status = actual_optimizer(mol, **kwargs)
        assert status == 0
        conf = mol.GetConformer(kwargs["confId"])
        conf.SetAtomPosition(0, (coordinate, 0., 0.))
        return status

    monkeypatch.setattr(generated.AllChem, "MMFFOptimizeMolecule", altered)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


@pytest.mark.parametrize("guard", ["version", "legacy"])
def test_unsupported_runtime_semantics_fail_before_generation(monkeypatch, guard):
    structure = read_az_raw_smiles("CCO")
    before = all_props(structure.mol)
    if guard == "version":
        monkeypatch.setattr(generated.rdBase, "rdkitVersion", "2025.03.6")
    else:
        monkeypatch.setattr(generated.Chem, "GetUseLegacyStereoPerception", lambda: False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Unsupported runtime cannot start candidate generation")

    monkeypatch.setattr(generated.AllChem, "EmbedMolecule", forbidden)
    with pytest.raises(GeneratedGeometryError):
        prepare(structure)
    assert all_props(structure.mol) == before


def test_api_does_not_open_save_or_load_files(monkeypatch):
    structure = read_az_raw_smiles("CCO")
    rng = rng_snapshot()

    def forbidden(*_args, **_kwargs):
        pytest.fail("Candidate geometry is an in-memory label-free primitive")

    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(torch, "load", forbidden)
    monkeypatch.setattr(torch, "save", forbidden)
    assert prepare(structure).encoder_batch.x.numel() == 3
    assert_rng_equal(rng)


def test_real_tiny_shared_h0_atom_readout_observes_only_native_ids():
    structure = read_cyp_mol_block(source_block())
    result = prepare(structure)
    rng = torch.get_rng_state().clone()
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device="cpu").manual_seed(731).get_state())
        config = small_config("light")
        config["backbone"].update(dim=8, heads=2, layers=1, dropout=0.0)
        config["head"]["profile"] = "phase1"
        model = build_model(config).eval()
        readout = SourceAlignedH0Readout(8, 1, output_level="atom", hidden_dim=4).eval()
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    with torch.no_grad():
        h0 = model.encode_atoms(result.encoder_batch)
        output = readout(h0, source_atom_ids=result.source_atom_ids,
                         batch=result.encoder_batch.batch, ptr=result.encoder_batch.ptr)
    assert h0.shape == (5, 8) and torch.isfinite(h0).all()
    assert output.predictions.shape == (5, 1) and torch.isfinite(output.predictions).all()
    assert output.source_atom_ids.tolist() == [0, 1, 2, 3, 4]
    assert output.ptr.tolist() == [0, 5]
    assert all(torch.equal(value, before[name]) for name, value in model.state_dict().items())
    assert torch.equal(torch.get_rng_state(), rng)
