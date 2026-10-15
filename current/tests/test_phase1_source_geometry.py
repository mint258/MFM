"""Hand-written synthetic mol blocks and encoder-only geometry oracles.

No dataset files, labels, geometry generation or physical stereochemistry truth
are used. RDKit dimension flags are tested as parser behavior, not ground truth.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math
from pathlib import Path
import random

import numpy as np
import pytest
from rdkit import Chem, rdBase
import torch

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.phase1 import source_geometry as geometry
from phychem_mfm.phase1.source_geometry import (
    SourceGeometryError, build_cyp_source_encoder_geometry,
)


SYMBOLS = ("C", "H", "O", "H", "N")
NUMBERS = (6, 1, 8, 1, 7)
COORDINATES = (
    (1.2345, -2.3456, 0.1234),
    (2.2345, -2.3456, 0.1234),
    (1.2345, -1.1456, 0.1234),
    (0.7345, -0.7456, 0.1234),
    (0.0345, -2.6456, 0.1234),
)
BONDS = ((1, 2, 1, 0), (1, 3, 1, 0), (3, 4, 1, 0), (1, 5, 1, 0))


def mol_block(*, dimension="3D", symbols=SYMBOLS, positions=COORDINATES,
              bonds=BONDS, title="synthetic geometry only"):
    """Explicit source rows; no SMILES conversion, generated coordinates or H."""
    assert len(symbols) == len(positions)
    lines = [title, f"{'SYNTHETIC':<20}{dimension}", "",
             f"{len(symbols):3d}{len(bonds):3d}  0  0  0  0            999 V2000"]
    lines.extend(
        f"{x:10.4f}{y:10.4f}{z:10.4f} {symbol:<3} 0  0  0  0  0  0  0  0  0  0  0  0"
        for symbol, (x, y, z) in zip(symbols, positions)
    )
    lines.extend(f"{left:3d}{right:3d}{order:3d}{stereo:3d}  0  0  0"
                 for left, right, order, stereo in bonds)
    return "\n".join(lines + ["M  END"]) + "\n"


def v3000_block(coordinate="1.25", *, element="C"):
    return "\n".join([
        "synthetic V3000 geometry", f"{'SYNTHETIC':<20}3D", "",
        "  0  0  0     0  0            999 V3000", "M  V30 BEGIN CTAB",
        "M  V30 COUNTS 1 0 0 0 0", "M  V30 BEGIN ATOM",
        f"M  V30 1 {element} {coordinate} 0 0.125 0",
        "M  V30 END ATOM", "M  V30 END CTAB", "M  END", "",
    ])


def parse_native(block):
    with rdBase.BlockLogs():
        mol = Chem.MolFromMolBlock(block, sanitize=True, removeHs=False, strictParsing=True)
    assert mol is not None, "The independent synthetic source must actually parse"
    return mol


def all_props(mol):
    return mol.ToBinary(Chem.PropertyPickleOptions.AllProps)


def independent_canonical_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def independent_tensor_hash(tensor):
    value = tensor.detach().cpu().contiguous()
    shape_hash = independent_canonical_hash(tuple(value.shape)).encode("ascii")
    raw = str(value.dtype).encode("ascii") + b"\0" + shape_hash + b"\0" + value.numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def build(block=None, **kwargs):
    return build_cyp_source_encoder_geometry(mol_block() if block is None else block,
                                            source_units="angstrom", **kwargs)


def test_hand_rows_explicit_h_and_f64_to_f32_oracle():
    block = mol_block()
    result = build(block)
    batch = result.encoder_batch
    assert set(batch.keys()) == {"x", "pos", "batch", "ptr"}
    assert batch.x.dtype == torch.long and batch.x.tolist() == [5, 0, 7, 0, 6]
    assert batch.pos.dtype == torch.float32 and batch.pos.shape == (5, 3)
    expected64 = torch.tensor(COORDINATES, dtype=torch.float64)
    expected32 = expected64.to(torch.float32)
    assert torch.equal(batch.pos, expected32)
    assert result.source_atom_ids.dtype == torch.long
    assert result.source_atom_ids.tolist() == [0, 1, 2, 3, 4]
    assert batch.batch.tolist() == [0] * 5 and batch.ptr.tolist() == [0, 5]
    assert batch.batch.dtype == batch.ptr.dtype == torch.long
    assert all(value.device.type == "cpu" for value in
               (batch.x, batch.pos, batch.batch, batch.ptr, result.source_atom_ids))
    receipt = result.provenance
    assert receipt["source_block_sha256"] == hashlib.sha256(block.encode()).hexdigest()
    assert receipt["source_block_utf8_bytes"] == len(block.encode())
    assert receipt["source_n_atoms"] == receipt["source_native_rows"] == 5
    assert receipt["explicit_h_atoms"] == 2
    assert receipt["parsed_conformer_count"] == 1 and receipt["parsed_is_3d"] is True
    assert receipt["schema_version"] == "phase1_cyp_source_encoder_geometry_v1"
    assert receipt["source_format"] == "V2000"
    assert receipt["source_units"] == receipt["output_units"] == "angstrom"
    assert receipt["quantization_absolute_error_unit"] == "angstrom"
    assert receipt["coordinate_scale"] == 1.0
    assert receipt["source_structure_preserved"] is True
    assert receipt["tensor_transport_verified"] is True
    for field in ("source_units_independently_verified", "chemical_geometry_independently_verified",
                  "source_file_record_association_independently_verified",
                  "source_graph_identity_independently_verified", "source_dimension_is_physical_geometry_proof",
                  "atom_permutation_applied", "centering_applied", "scaling_applied", "conformer_generated"):
        assert receipt[field] is False
    assert receipt["bounds"]["max_input_bytes"] == 8 * 1024 * 1024
    assert receipt["bounds"]["reused_reader_max_input_bytes"] == 2 * 1024 * 1024
    assert receipt["source_atomic_number_order_sha256"] == independent_canonical_hash(NUMBERS)
    assert receipt["source_coordinates_float64_sha256"] == independent_tensor_hash(expected64)
    error = (expected32.double() - expected64).abs().max().item()
    assert error > 0.0 and receipt["quantization_max_abs_error"] == error
    with pytest.raises(FrozenInstanceError):
        result.source_atom_ids = torch.arange(5)


@pytest.mark.parametrize("tail", ["\n\n", "  \n\t\n"])
def test_whitespace_tail_keeps_source_bytes_binding_and_same_geometry(tail):
    plain = mol_block()
    original, padded = build(plain), build(plain + tail)
    assert torch.equal(original.encoder_batch.pos, padded.encoder_batch.pos)
    assert padded.provenance["source_block_sha256"] == hashlib.sha256((plain + tail).encode()).hexdigest()
    assert original.provenance["source_block_sha256"] != padded.provenance["source_block_sha256"]


@pytest.mark.parametrize("dimension,positions", [
    ("3D", tuple((x, y, 0.0) for x, y, _ in COORDINATES)),
    ("2D", COORDINATES),
])
def test_parser_3d_accepts_planar_or_header_mismatch_without_physical_claim(dimension, positions):
    block = mol_block(dimension=dimension, positions=positions)
    native = parse_native(block)
    assert native.GetConformer().Is3D() is True
    result = build(block)
    assert result.provenance["source_header_dimension"] == dimension
    assert result.provenance["parsed_is_3d"] is True
    assert torch.equal(result.encoder_batch.pos, torch.tensor(positions, dtype=torch.float32))
    assert result.provenance["state"] == "NOT_FROZEN"
    assert result.provenance["formal_eligible"] is False
    if dimension == "3D":
        # Genuine rank-two source; no requirement to force a tetrahedral volume.
        centered = result.encoder_batch.pos.double() - result.encoder_batch.pos.double().mean(0)
        assert torch.linalg.matrix_rank(centered).item() == 2


def test_raw_3d_header_with_wedge_but_parsed_2d_is_rejected():
    positions = ((0., 0., 0.), (1., 0., 0.), (-1., 0., 0.), (0., 1., 0.), (0., -1., 0.))
    block = mol_block(symbols=("C", "F", "Cl", "Br", "H"), positions=positions,
                      bonds=((1, 2, 1, 1), (1, 3, 1, 0), (1, 4, 1, 0), (1, 5, 1, 0)))
    native = parse_native(block)
    assert native.GetConformer().Is3D() is False
    before = all_props(native)
    with pytest.raises(SourceGeometryError):
        build(block)
    assert all_props(native) == before


@pytest.mark.parametrize("units", [None, "bohr", "Angstrom", "angstrom ", 1])
def test_units_require_exact_explicit_angstrom(units):
    with pytest.raises(SourceGeometryError):
        build_cyp_source_encoder_geometry(mol_block(), source_units=units)


def test_omitted_units_is_not_silently_inferred():
    with pytest.raises(TypeError):
        build_cyp_source_encoder_geometry(mol_block())


@pytest.mark.parametrize("cap", [True, 0, -1, 5.0, "5", 4097])
def test_invalid_atom_caps_are_rejected(cap):
    with pytest.raises(SourceGeometryError):
        build(max_atoms=cap)


def test_exact_atom_cap_accepts_and_smaller_cap_rejects_without_filtering():
    assert build(max_atoms=5).encoder_batch.x.numel() == 5
    with pytest.raises(SourceGeometryError):
        build(max_atoms=4)


def test_reused_reader_stricter_byte_cap_rejects_without_parsing_or_output():
    block = mol_block(title="x" * (2 * 1024 * 1024))
    assert 2 * 1024 * 1024 < len(block.encode()) < 8 * 1024 * 1024
    with pytest.raises(SourceGeometryError):
        build(block)


def test_v3000_source_format_diagnostic_keeps_explicit_source_coordinates():
    block = v3000_block()
    result = build(block)
    assert result.provenance["source_format"] == "V3000"
    assert result.provenance["source_header_dimension"] == "3D"
    assert result.encoder_batch.x.tolist() == [5]
    assert result.source_atom_ids.tolist() == [0]
    assert torch.equal(result.encoder_batch.pos, torch.tensor([[1.25, 0., 0.125]], dtype=torch.float32))


@pytest.mark.parametrize("block", [None, b"M  END\n", "", "not a mol block\nM  END\n",
                                  "x" * (8 * 1024 * 1024 + 1)])
def test_missing_malformed_and_oversize_input_fail_closed(block):
    with pytest.raises(SourceGeometryError):
        build_cyp_source_encoder_geometry(block, source_units="angstrom")


@pytest.mark.parametrize("tail", ["\n> <PRIMARY_SOM>\n1 2\n", "\n$$$$\n", "SECOND_BLOCK"])
def test_properties_record_delimiter_and_multiple_structures_are_rejected(tail):
    block = mol_block()
    if tail == "SECOND_BLOCK":
        tail = mol_block()
    with pytest.raises(SourceGeometryError):
        build(block + tail)


@pytest.mark.parametrize("token", ["nan", "inf", "1e40"])
def test_nonfinite_or_finite64_overflow_coordinates_are_rejected(token):
    block = v3000_block(token)
    if token == "1e40":
        native = parse_native(block)
        x = native.GetConformer().GetAtomPosition(0).x
        assert math.isfinite(x) and x > torch.finfo(torch.float32).max
    with pytest.raises(SourceGeometryError):
        build(block)


@pytest.mark.parametrize("fault", ["missing", "multiple", "parsed_2d"])
def test_conformer_cardinality_and_parsed_dimension_fail_closed(monkeypatch, fault):
    source = geometry.read_cyp_mol_block(mol_block())
    altered = Chem.Mol(source.mol)
    if fault == "missing":
        altered.RemoveAllConformers()
    elif fault == "multiple":
        altered.AddConformer(Chem.Conformer(altered.GetConformer()), assignId=True)
    else:
        altered.GetConformer().Set3D(False)
    injected = replace(source, mol=altered)
    before = all_props(altered)
    monkeypatch.setattr(geometry, "read_cyp_mol_block", lambda *_args, **_kwargs: injected)
    with pytest.raises(SourceGeometryError):
        build()
    assert all_props(altered) == before


def test_native_mol_graph_stereo_coordinates_and_allprops_remain_unchanged(monkeypatch):
    real_reader = geometry.read_cyp_mol_block
    observed = []
    block = mol_block(
        symbols=("C", "F", "Cl", "Br", "H"),
        positions=((0.2345, -0.3456, 0.1234), (1.2345, -0.3456, 0.1234),
                   (0.2345, 0.6544, 0.1234), (0.2345, -0.3456, 1.1234),
                   (-0.7655, -1.3456, -0.8766)),
        bonds=((1, 2, 1, 0), (1, 3, 1, 0), (1, 4, 1, 0), (1, 5, 1, 0)),
    )

    def capture(block, **kwargs):
        source = real_reader(block, **kwargs)
        source.mol.SetProp("synthetic_marker", "not an annotation")
        source.mol.GetAtomWithIdx(2).SetProp("atom_marker", "keep")
        observed.append((source.mol, all_props(source.mol)))
        return source

    def forbidden(*_args, **_kwargs):
        pytest.fail("Geometry handoff may not change atom order/H or regenerate a block")

    monkeypatch.setattr(geometry, "read_cyp_mol_block", capture)
    for name in ("AddHs", "RemoveHs", "RenumberAtoms", "MolToMolBlock"):
        monkeypatch.setattr(Chem, name, forbidden)
    result = build(block)
    assert len(observed) == 1
    native, before = observed[0]
    assert all_props(native) == before
    assert tuple(atom.GetAtomicNum() for atom in native.GetAtoms()) == (6, 9, 17, 35, 1)
    assert native.GetAtomWithIdx(0).GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED
    result.encoder_batch.pos[0, 0] = 100.
    result.encoder_batch.x[0] = 1
    result.source_atom_ids[0] = 3
    assert all_props(native) == before


def test_owned_output_tensors_do_not_alias_other_calls_or_source_id_metadata():
    original, independent = build(), build()
    preserved = independent.encoder_batch.pos.clone()
    original.encoder_batch.pos.add_(10.)
    original.encoder_batch.x.fill_(0)
    original.source_atom_ids[0] = 99
    assert torch.equal(independent.encoder_batch.pos, preserved)
    assert independent.encoder_batch.x.tolist() == [5, 0, 7, 0, 6]
    assert independent.source_atom_ids.tolist() == [0, 1, 2, 3, 4]
    assert independent.encoder_batch.batch.tolist() == [0] * 5


def test_geometry_conversion_does_not_open_files_or_consume_rng(monkeypatch):
    block = mol_block()
    python_rng, numpy_rng, torch_rng = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()

    def forbidden(*_args, **_kwargs):
        pytest.fail("Geometry API receives a structure block, not a file or checkpoint")

    for name in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(torch, "load", forbidden)
    monkeypatch.setattr(torch, "save", forbidden)
    result = build(block)
    assert result.encoder_batch.x.numel() == 5
    assert random.getstate() == python_rng and torch.equal(torch.get_rng_state(), torch_rng)
    current = np.random.get_state()
    assert current[0] == numpy_rng[0] and np.array_equal(current[1], numpy_rng[1])
    assert current[2:] == numpy_rng[2:]


def test_tensor_and_receipt_hashes_bind_actual_owned_values():
    result = build()
    receipt = result.provenance
    expected = {name: independent_tensor_hash(getattr(result.encoder_batch, name))
                for name in ("x", "pos", "batch", "ptr")}
    expected["source_atom_ids"] = independent_tensor_hash(result.source_atom_ids)
    assert receipt["encoder_tensor_hashes"] == expected
    for name in ("x", "pos", "batch", "ptr"):
        assert geometry.geometry_tensor_sha256(getattr(result.encoder_batch, name)) == expected[name]
    bound = dict(receipt)
    own_hash = bound.pop("geometry_provenance_sha256")
    assert own_hash == independent_canonical_hash(bound)
    result.encoder_batch.pos[1, 0] += 0.5
    assert independent_tensor_hash(result.encoder_batch.pos) != receipt["encoder_tensor_hashes"]["pos"]


def test_actual_tiny_shared_h0_forward_uses_only_four_geometry_keys_and_real_h():
    result = build()
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device="cpu").manual_seed(731).get_state())
        config = small_config("light")
        config["backbone"].update(dim=8, heads=2, layers=1, dropout=0.0)
        config["head"]["profile"] = "phase1"
        model = build_model(config).eval()
    seen = []

    def check_geometry(_module, args):
        batch = args[0]
        assert set(batch.keys()) == {"x", "pos", "batch", "ptr"}
        assert batch.x.ndim == 1 and batch.x.tolist() == [5, 0, 7, 0, 6]
        assert (batch.x >= 0).all() and (batch.x < config["backbone"]["n_atom_types"]).all()
        seen.append(batch.x.numel())

    handle = model.backbone.register_forward_pre_hook(check_geometry)
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    try:
        with torch.no_grad():
            h0 = model.encode_atoms(result.encoder_batch)
    finally:
        handle.remove()
    assert seen == [5] and h0.shape == (5, 8) and torch.isfinite(h0).all()
    assert all(torch.equal(value, before[name]) for name, value in model.state_dict().items())
    # Native H maps to x=0; it is an actual row, never discarded as padding.
    assert result.encoder_batch.ptr[-1].item() == len(NUMBERS)
    with pytest.raises(SourceGeometryError):
        build(v3000_block(element="*"))
