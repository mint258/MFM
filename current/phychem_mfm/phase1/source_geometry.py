"""CYP native-order structure-to-tensor transport; NOT_FROZEN preparation.

Only a supplied structural mol block ending at M  END is consumed. Units are
an explicit caller declaration. A parsed 3D flag is an interface requirement,
not independent evidence of an optimized or chemically suitable geometry.
No files, annotations, models, conformer generation or atom reordering occur.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math

from rdkit import Chem
import torch
from torch import Tensor
from torch_geometric.data import Data

from .downstream_structures import (
    MAX_ATOMS,
    MAX_STRUCTURE_BYTES,
    DownstreamStructureError,
    read_cyp_mol_block,
)
from .identity import canonical_hash


GEOMETRY_SCHEMA = "phase1_cyp_source_encoder_geometry_v1"
MAX_PROVENANCE_BYTES = 64 * 1024
TENSOR_HASH_RECIPE = "dtype_utf8_NUL_canonical_shape_sha256_ascii_NUL_contiguous_cpu_native_bytes_v1"


class SourceGeometryError(ValueError):
    """A supplied CYP block cannot satisfy the explicit tensor transport."""


@dataclass(frozen=True)
class SourceEncoderGeometry:
    """Owned CPU tensors and detached proof metadata, not deeply frozen tensors."""

    encoder_batch: Data
    source_atom_ids: Tensor
    provenance: dict


def _require(condition, message):
    if not condition:
        raise SourceGeometryError(message)


def geometry_tensor_sha256(tensor: Tensor) -> str:
    """Hash a CPU long/FP32/FP64 tensor with explicit dtype and shape framing."""
    _require(isinstance(tensor, Tensor) and tensor.device.type == "cpu"
             and tensor.layout == torch.strided
             and tensor.dtype in (torch.long, torch.float32, torch.float64),
             "Geometry hashing requires an explicit supported CPU tensor")
    owned = tensor.detach().contiguous()
    digest = hashlib.sha256()
    digest.update(str(owned.dtype).encode("utf-8") + b"\0")
    digest.update(canonical_hash(tuple(owned.shape)).encode("ascii") + b"\0")
    digest.update(owned.numpy().tobytes(order="C"))
    return digest.hexdigest()


def _source_text(block):
    _require(type(block) is str and 0 < len(block) <= MAX_STRUCTURE_BYTES,
             "A bounded nonempty structural mol block is required")
    try:
        source = block.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SourceGeometryError("Mol block is not valid UTF8 text") from exc
    _require(len(source) <= MAX_STRUCTURE_BYTES, "Mol block exceeds the 8MiB input bound")
    lines = block.split("\n")
    ends = [index for index, line in enumerate(lines) if line.strip() == "M  END"]
    _require(len(ends) == 1 and ends[0] >= 4
             and all(not line.strip() for line in lines[ends[0] + 1:])
             and all(line.strip() != "$$$$" for line in lines),
             "Input must contain one M END-only mol block without SDF properties or another record")
    # MDL's program/header line has the dimension marker at columns 21..22.
    # Keep this distinct from the actual parsed conformer's Is3D flag.
    dimension = lines[1].rstrip("\r")[20:22].strip()
    dimension = dimension if dimension in ("2D", "3D") else "UNSPECIFIED"
    counts = lines[3]
    source_format = ("V3000" if "V3000" in counts else
                     "V2000" if "V2000" in counts else "UNRECOGNIZED")
    return source, dimension, source_format


def _transport(structure, limit):
    mol = structure.mol
    _require(isinstance(mol, Chem.Mol), "Reader must provide its genuine parsed source molecule")
    before = mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    try:
        numbers = structure.atomic_numbers
        count = mol.GetNumAtoms()
        _require(type(numbers) is tuple and 0 < count <= limit and len(numbers) == count
                 and all(type(z) is int and 1 <= z <= 118 for z in numbers),
                 "Source atom count or Z is outside the native encoder vocabulary")
        _require(tuple(atom.GetAtomicNum() for atom in mol.GetAtoms()) == numbers
                 and structure.x == tuple(z - 1 for z in numbers)
                 and structure.source_atom_map == tuple(range(count)),
                 "Reader atom numbers, zero-based encoding or native order disagree")
        for index, atom in enumerate(mol.GetAtoms()):
            _require(atom.HasProp("_phase1_source_atom_index")
                     and atom.GetIntProp("_phase1_source_atom_index") == index,
                     "Reader native source atom marker differs from its row")
        _require(mol.GetNumConformers() == 1,
                 "Exactly one source conformer is required; no implicit selection is permitted")
        conformer = mol.GetConformer()
        _require(conformer.Is3D() is True, "The sole parsed source conformer must be flagged 3D")
        _require(conformer.GetNumAtoms() == count, "Source conformer atom count differs")
        coordinates = []
        for index in range(count):
            point = conformer.GetAtomPosition(index)
            xyz = (point.x, point.y, point.z)
            _require(all(math.isfinite(value) for value in xyz), "Source coordinates must be finite")
            coordinates.append(xyz)
        coordinates64 = torch.tensor(coordinates, dtype=torch.float64, device="cpu")
        positions = coordinates64.to(dtype=torch.float32).clone()
        _require(bool(torch.isfinite(positions).all()), "Source coordinates overflow the FP32 encoder representation")
        x = torch.tensor(tuple(z - 1 for z in numbers), dtype=torch.long, device="cpu")
        source_ids = torch.arange(count, dtype=torch.long, device="cpu")
        batch = torch.zeros(count, dtype=torch.long, device="cpu")
        ptr = torch.tensor((0, count), dtype=torch.long, device="cpu")
        tensors = {"x": x, "pos": positions, "batch": batch, "ptr": ptr,
                   "source_atom_ids": source_ids}
        hashes = {name: geometry_tensor_sha256(tensor) for name, tensor in tensors.items()}
        quantization_error = float((coordinates64 - positions.to(dtype=torch.float64)).abs().max().item())
        return Data(x=x, pos=positions, batch=batch, ptr=ptr), source_ids, {
            "source_n_atoms": count,
            "source_native_rows": count,
            "explicit_h_atoms": sum(z == 1 for z in numbers),
            "source_atomic_number_order_sha256": canonical_hash(numbers),
            "source_coordinates_float64_sha256": geometry_tensor_sha256(coordinates64),
            "encoder_tensor_hashes": hashes,
            "quantization_max_abs_error": quantization_error,
            "parsed_conformer_count": 1,
            "parsed_is_3d": True,
        }
    except (RuntimeError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, SourceGeometryError):
            raise
        raise SourceGeometryError("Source geometry extraction failed") from exc
    finally:
        _require(mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before,
                 "Geometry transport changed source graph, properties or conformer state")


def build_cyp_source_encoder_geometry(
    block: str, *, source_units, max_atoms: int = MAX_ATOMS,
) -> SourceEncoderGeometry:
    """Extract a single native-order CYP graph's owned CPU encoder tensors.

    The reused source reader additionally retains its existing 2MiB mol-block
    parsing limit. Its graph identity is copied as metadata, not a geometry or
    raw-file association proof. Nothing centers, scales, reorders or changes
    source atoms. FP64 parsed coordinates are rounded once to FP32, with the
    actual maximum absolute cast error recorded in declared angstrom units.
    The dataclass is frozen; caller-owned returned tensors/dicts are mutable.
    """
    _require(type(source_units) is str and source_units == "angstrom",
             "source_units must explicitly declare angstrom; no conversion is performed")
    _require(type(max_atoms) is int and 0 < max_atoms <= MAX_ATOMS,
             "max_atoms must be an explicit positive integer no greater than 4096")
    source, dimension, source_format = _source_text(block)
    try:
        structure = read_cyp_mol_block(block)
    except (DownstreamStructureError, RuntimeError, TypeError, ValueError) as exc:
        raise SourceGeometryError("Bounded CYP source reader rejected the structural block") from exc
    encoder_batch, source_ids, extraction = _transport(structure, max_atoms)
    reader_provenance = deepcopy(structure.provenance)
    _require(reader_provenance.get("source_sha256") == hashlib.sha256(source).hexdigest()
             and reader_provenance.get("source_bytes") == len(source)
             and reader_provenance.get("source_atomic_number_order_hash")
             == extraction["source_atomic_number_order_sha256"],
             "Reader provenance does not bind the supplied block and native Z order")
    _require(structure.identity is not None, "Source reader graph identity metadata is missing")
    provenance = {
        "schema_version": GEOMETRY_SCHEMA,
        "state": "NOT_FROZEN",
        "formal_eligible": False,
        "source_block_sha256": hashlib.sha256(source).hexdigest(),
        "source_block_utf8_bytes": len(source),
        "source_scope": "provided M END-only structural text; no raw file or property values",
        "source_units": "angstrom",
        "output_units": "angstrom",
        "coordinate_scale": 1.0,
        "source_units_independently_verified": False,
        "chemical_geometry_independently_verified": False,
        "source_file_record_association_independently_verified": False,
        "source_graph_identity_independently_verified": False,
        "source_dimension_is_physical_geometry_proof": False,
        "source_header_dimension": dimension,
        "source_format": source_format,
        "graph_identity": deepcopy(structure.identity.to_dict()),
        "reader_provenance": reader_provenance,
        "atom_encoding": "zero_based",
        "encoder_graph_count": 1,
        "source_atom_ids_policy": "native source index i -> encoder row i; no permutation",
        "hydrogen_policy": "retain every native atom including explicit H; no AddHs or RemoveHs",
        "atom_permutation_applied": False,
        "centering_applied": False,
        "scaling_applied": False,
        "conformer_generated": False,
        "source_structure_preserved": True,
        "tensor_transport_verified": True,
        "tensor_transport_scope": "this supplied parsed block only; no chemical suitability claim",
        "tensor_hash_recipe": TENSOR_HASH_RECIPE,
        "coordinate_cast": "parsed FP64 -> FP32; roundoff recorded, not exact decimal preservation",
        "quantization_absolute_error_unit": "angstrom",
        "bounds": {"max_atoms": max_atoms, "max_input_bytes": MAX_STRUCTURE_BYTES,
                   "reused_reader_max_input_bytes": 2 * 1024 * 1024,
                   "max_provenance_bytes": MAX_PROVENANCE_BYTES,
                   "wall_time": "caller cooperative budget; no hard timeout in this primitive"},
        **extraction,
    }
    provenance["geometry_provenance_sha256"] = canonical_hash(provenance)
    try:
        size = len(json.dumps(provenance, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise SourceGeometryError("Geometry proof must remain finite JSON metadata") from exc
    _require(size <= MAX_PROVENANCE_BYTES, "Geometry proof exceeds the bounded 64KiB metadata limit")
    return SourceEncoderGeometry(encoder_batch, source_ids, provenance)
