"""Single-recipe native-order geometry preparation, not a frozen protocol.

Only a supplied source structure is consumed. Added H atoms exist on scratch
molecules for ETKDG/MMFF, never in the encoder or the native label universe.
No files, annotations, models, global seeds or source structures are changed.
Iteration limits and the embedding timeout are cooperative library limits;
the caller must impose a separate process wall/memory/output budget.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import re

from rdkit import Chem, rdBase
from rdkit.Chem import AllChem
import torch
from torch_geometric.data import Data

from .downstream_structures import SourceStructure, SOURCE_CONTRACT
from .identity import canonical_hash
from .source_geometry import (
    SourceEncoderGeometry, SourceGeometryError, geometry_tensor_sha256,
    MAX_PROVENANCE_BYTES, TENSOR_HASH_RECIPE,
)


GENERATED_GEOMETRY_SCHEMA = "phase1_native_generated_geometry_v1"
RDKIT_VERSION = "2025.09.5"
_MARKER = "_phase1_source_atom_index"
_SHA = re.compile(r"[0-9a-f]{64}")


class GeneratedGeometryError(SourceGeometryError):
    """The fixed candidate recipe failed; no ready geometry is returned."""


@dataclass(frozen=True)
class GeneratedNativeGeometry(SourceEncoderGeometry):
    """Native FP64 payload is separate from the four-key FP32 encoder input."""

    native_coordinates_float64: torch.Tensor


def _require(condition, message):
    if not condition:
        raise GeneratedGeometryError(message)


def _groups(mol):
    return [(str(g.GetGroupType()), [a.GetIdx() for a in g.GetAtoms()],
             [b.GetIdx() for b in g.GetBonds()]) for g in mol.GetStereoGroups()]


def _graph(mol, native_count=None):
    count = mol.GetNumAtoms() if native_count is None else native_count
    atoms = [(a.GetAtomicNum(), a.GetIsotope(), a.GetFormalCharge(),
              str(a.GetChiralTag()), a.GetIsAromatic(),
              a.GetNumRadicalElectrons(), a.GetAtomMapNum())
             for a in list(mol.GetAtoms())[:count]]
    bonds = [(b.GetBeginAtomIdx(), b.GetEndAtomIdx(), str(b.GetBondType()),
              b.GetIsAromatic(), b.GetIsConjugated(), str(b.GetStereo()),
              tuple(b.GetStereoAtoms()), str(b.GetBondDir()))
             for b in mol.GetBonds()
             if b.GetBeginAtomIdx() < count and b.GetEndAtomIdx() < count]
    return {"atoms": atoms, "bonds": bonds, "stereo_groups": _groups(mol)}


def _layout(mol):
    # MMFF may legitimately Kekulize/change aromatic typing on its own copy.
    # Connectivity, element/isotope/charge, source lineage and stereo may not.
    return {
        "atoms": [(a.GetAtomicNum(), a.GetIsotope(), a.GetFormalCharge(),
                   str(a.GetChiralTag()), a.GetNumRadicalElectrons(), a.GetAtomMapNum(),
                   a.GetIntProp(_MARKER) if a.HasProp(_MARKER) else None)
                  for a in mol.GetAtoms()],
        "bonds": [(b.GetBeginAtomIdx(), b.GetEndAtomIdx(), str(b.GetStereo()),
                   tuple(b.GetStereoAtoms()), str(b.GetBondDir())) for b in mol.GetBonds()],
        "stereo_groups": _groups(mol),
    }


def _specified_stereo(graph, generated, native_count, conf_id):
    reference = Chem.Mol(graph)
    reference.RemoveAllConformers()
    Chem.AssignStereochemistry(reference, cleanIt=True, force=True)
    decoded = Chem.Mol(generated)
    # Clear cached stereo on the independent decoding copy: retaining input
    # flags would turn the check into an assertion of its own input.
    Chem.RemoveStereochemistry(decoded)
    Chem.AssignStereochemistryFrom3D(decoded, confId=conf_id, replaceExistingTags=True)
    atom_checks, bond_checks = [], []
    tetra = (Chem.ChiralType.CHI_TETRAHEDRAL_CW, Chem.ChiralType.CHI_TETRAHEDRAL_CCW)
    defined_bonds = (Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ,
                     Chem.BondStereo.STEREOCIS, Chem.BondStereo.STEREOTRANS)
    for atom in graph.GetAtoms():
        if atom.GetIdx() >= native_count or atom.GetChiralTag() == Chem.ChiralType.CHI_UNSPECIFIED:
            continue
        _require(atom.GetChiralTag() in tetra, "Specified non-tetrahedral stereo is unsupported")
        index = atom.GetIdx()
        expected, actual = reference.GetAtomWithIdx(index), decoded.GetAtomWithIdx(index)
        _require(expected.HasProp("_CIPCode") and actual.HasProp("_CIPCode")
                 and expected.GetProp("_CIPCode") == actual.GetProp("_CIPCode"),
                 "Generated coordinates contradict or fail to resolve specified tetrahedral stereo")
        atom_checks.append({"native_atom_id": index, "expected_cip": expected.GetProp("_CIPCode"),
                            "decoded_cip": actual.GetProp("_CIPCode")})
    for bond in graph.GetBonds():
        if bond.GetStereo() not in defined_bonds:
            _require(bond.GetStereo() in (Chem.BondStereo.STEREONONE, Chem.BondStereo.STEREOANY),
                     "Specified non-alkene bond stereo is unsupported")
            continue
        index = bond.GetIdx()
        expected, actual = reference.GetBondWithIdx(index), decoded.GetBondWithIdx(index)
        _require(expected.GetStereo() in (Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ)
                 and actual.GetStereo() == expected.GetStereo()
                 and tuple(actual.GetStereoAtoms()) == tuple(expected.GetStereoAtoms()),
                 "Generated coordinates contradict or fail to resolve specified alkene stereo")
        bond_checks.append({"source_bond_id": index, "expected_stereo": str(expected.GetStereo()),
                            "decoded_stereo": str(actual.GetStereo()),
                            "control_atom_ids": list(expected.GetStereoAtoms())})
    return {"method": "independent graph-only clean force CIP reference; independent cleared-stereo 3D decoding copy",
            "specified_tetrahedral_centers": atom_checks, "specified_alkene_bonds": bond_checks,
            "unspecified_stereo_promoted_to_source_features": False,
            "chemical_stereochemistry_truth_independently_verified": False}


def prepare_native_generated_geometry(
    structure: SourceStructure, *, seed: int,
    max_native_atoms: int = 256, max_work_atoms: int = 512,
) -> GeneratedNativeGeometry:
    """Generate one fixed candidate conformer and project only native rows.

    The original source graph/AllProps/conformers remain intact. MMFF94 uses
    a separate force-field copy because its aromaticity typing is mutable.
    Only coordinates return to the unmodified expanded template, whose
    specified stereo is independently checked from those coordinates.
    Units describe the RDKit generator convention, not source-coordinate
    units or an independently verified chemical/experimental geometry.
    """
    _require(type(seed) is int and 0 <= seed <= 2147483647, "seed must be an explicit bounded nonnegative integer")
    _require(type(max_native_atoms) is int and 0 < max_native_atoms <= 256,
             "max_native_atoms must be a positive integer no greater than 256")
    _require(type(max_work_atoms) is int and 0 < max_work_atoms <= 512,
             "max_work_atoms must be a positive integer no greater than 512")
    _require(rdBase.rdkitVersion == RDKIT_VERSION and Chem.GetUseLegacyStereoPerception() is True,
             "The candidate recipe requires pinned RDKit 2025.09.5 legacy stereo perception")
    _require(type(structure) is SourceStructure and isinstance(structure.mol, Chem.Mol),
             "A genuine source-reader SourceStructure and molecule are required")
    source = structure.mol
    original = source.ToBinary(Chem.PropertyPickleOptions.AllProps)
    try:
        count = source.GetNumAtoms()
        numbers = structure.atomic_numbers
        _require(type(numbers) is tuple and 0 < count <= max_native_atoms and len(numbers) == count
                 and all(type(z) is int and 1 <= z <= 118 for z in numbers)
                 and numbers == tuple(a.GetAtomicNum() for a in source.GetAtoms())
                 and structure.x == tuple(z - 1 for z in numbers)
                 and structure.source_atom_map == tuple(range(count)),
                 "Native source atom encoding/order or count is invalid")
        _require(len(Chem.GetMolFrags(source)) == 1, "Disconnected sources have no supported relative-fragment geometry")
        _require(all(not a.HasQuery() and a.HasProp(_MARKER) and a.GetIntProp(_MARKER) == a.GetIdx()
                     for a in source.GetAtoms()) and all(not b.HasQuery() for b in source.GetBonds()),
                 "Native source lineage or query-free graph is invalid")
        metadata = deepcopy(structure.provenance)
        _require(type(metadata) is dict and metadata.get("source_contract") == SOURCE_CONTRACT
                 and metadata.get("source_kind") in ("mol_block", "raw_smiles")
                 and metadata.get("source_atomic_number_order_hash") == canonical_hash(numbers)
                 and type(metadata.get("source_sha256")) is str and _SHA.fullmatch(metadata["source_sha256"])
                 and structure.identity is not None,
                 "Source reader provenance does not bind the native input")
        _require(len(json.dumps(metadata, allow_nan=False).encode("utf-8")) <= MAX_PROVENANCE_BYTES,
                 "Source metadata exceeds the bounded geometry receipt")
        expected_work = count + sum(a.GetNumExplicitHs() + a.GetNumImplicitHs() for a in source.GetAtoms())
        _require(expected_work <= max_work_atoms, "Expanded work graph exceeds max_work_atoms")
        native_graph = _graph(source)
        scratch = Chem.Mol(source)
        scratch.RemoveAllConformers()
        with rdBase.BlockLogs():
            scratch = Chem.AddHs(scratch, addCoords=False)
        work_count = scratch.GetNumAtoms()
        _require(work_count == expected_work and count <= work_count <= max_work_atoms
                 and _graph(scratch, count) == native_graph,
                 "AddHs changed the retained native graph, atom order or specified stereo")
        _require(all(a.HasProp(_MARKER) and a.GetIntProp(_MARKER) == a.GetIdx()
                     for a in list(scratch.GetAtoms())[:count])
                 and all(a.GetAtomicNum() == 1 and not a.HasProp(_MARKER)
                         for a in list(scratch.GetAtoms())[count:]),
                 "Added scratch atoms cannot redefine native source lineage")
        template_graph = _graph(scratch)
        recipe = {"rdkit_version": RDKIT_VERSION, "use_legacy_stereo_perception": True,
                  "embedding": "ETKDGv3", "embedding_calls": 1, "returned_conformers": 1,
                  "maxIterations": 200, "timeout_seconds": 2, "numThreads": 1,
                  "randomSeed": seed, "clearConfs": True, "enforceChirality": True,
                  "mmff_variant": "MMFF94", "mmff_max_iterations": 500,
                  "mmff_nonbonded_threshold": 100.0, "mmff_ignore_interfragment_interactions": True,
                  "fallback": "none", "hydrogens": "AddHs scratch only; project native rows; never RemoveHs"}
        params = AllChem.ETKDGv3()
        params.randomSeed, params.numThreads, params.maxIterations = seed, 1, 200
        params.timeout, params.clearConfs, params.enforceChirality = 2, True, True
        params.trackFailures = True
        with rdBase.BlockLogs():
            conf_id = AllChem.EmbedMolecule(scratch, params)
        _require(conf_id >= 0 and scratch.GetNumConformers() == 1, "ETKDGv3 did not produce its single candidate conformer")
        _require(_graph(scratch) == template_graph, "Embedding changed the expanded template graph or stereo")
        forcefield_copy = Chem.Mol(scratch)
        _require(AllChem.MMFFHasAllMoleculeParams(forcefield_copy), "MMFF94 parameters are unavailable")
        before_mmff_layout = _layout(forcefield_copy)
        with rdBase.BlockLogs():
            mmff_status = AllChem.MMFFOptimizeMolecule(
                forcefield_copy, mmffVariant="MMFF94", maxIters=500,
                nonBondedThresh=100.0, confId=conf_id, ignoreInterfragInteractions=True,
            )
        _require(mmff_status == 0, "MMFF94 failed to converge within the fixed 500 iterations")
        _require(_layout(forcefield_copy) == before_mmff_layout,
                 "MMFF changed lineage, connectivity, element or specified stereo")
        for before_bond, after_bond in zip(scratch.GetBonds(), forcefield_copy.GetBonds()):
            if not before_bond.GetIsAromatic() and not after_bond.GetIsAromatic():
                _require(before_bond.GetBondType() == after_bond.GetBondType(),
                         "MMFF changed a non-aromatic bond order")
        optimized = forcefield_copy.GetConformer(conf_id)
        conformer = scratch.GetConformer(conf_id)
        _require(optimized.Is3D() and optimized.GetNumAtoms() == work_count,
                 "Optimizer conformer is not the complete 3D work graph")
        for index in range(work_count):
            point = optimized.GetAtomPosition(index)
            _require(all(math.isfinite(v) for v in (point.x, point.y, point.z)), "Generated coordinates are nonfinite")
            conformer.SetAtomPosition(index, point)
        _require(_graph(scratch) == template_graph, "Coordinate transfer changed the retained expanded graph")
        stereo = _specified_stereo(scratch, scratch, count, conf_id)
        coordinates = []
        for i in range(count):
            point = conformer.GetAtomPosition(i)
            coordinates.append((point.x, point.y, point.z))
        positions64 = torch.tensor(coordinates, dtype=torch.float64, device="cpu")
        positions = positions64.to(dtype=torch.float32).clone()
        _require(bool(torch.isfinite(positions).all()), "Generated native coordinates overflow FP32")
        x = torch.tensor(structure.x, dtype=torch.long, device="cpu")
        ids = torch.arange(count, dtype=torch.long, device="cpu")
        batch = torch.zeros(count, dtype=torch.long, device="cpu")
        ptr = torch.tensor((0, count), dtype=torch.long, device="cpu")
        hashes = {name: geometry_tensor_sha256(value) for name, value in
                  {"x": x, "pos": positions, "batch": batch, "ptr": ptr, "source_atom_ids": ids}.items()}
        proof = {
            "schema_version": GENERATED_GEOMETRY_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
            "geometry_status": "GENERATED_CANDIDATE_READY", "conformer_generated": True,
            "source_scope": "provided source-reader structure only; no files or annotation values",
            "source_sha256": metadata["source_sha256"], "reader_provenance": metadata,
            "graph_identity": deepcopy(structure.identity.to_dict()),
            "source_structure_allprops_sha256": hashlib.sha256(original).hexdigest(),
            "source_native_graph_sha256": canonical_hash(native_graph),
            "source_n_atoms": count, "source_native_rows": count,
            "source_atomic_number_order_sha256": canonical_hash(numbers),
            "native_explicit_h_atoms": sum(z == 1 for z in numbers),
            "work_n_atoms": work_count, "scratch_added_h_atoms": work_count - count,
            "native_to_work_atom_ids": list(range(count)), "extra_work_h_encoder_rows": 0,
            "source_atom_ids_policy": "native source index i -> encoder row i; no permutation",
            "hydrogen_policy": "all native atoms retained; AddHs scratch extras excluded from encoder and labels",
            "source_units": "not used or inferred", "output_units": "angstrom",
            "output_units_basis": "RDKit ETKDG/MMFF generator convention; no source-coordinate conversion",
            "source_units_independently_verified": False, "output_units_independently_verified": False,
            "chemical_geometry_independently_verified": False,
            "source_file_record_association_independently_verified": False,
            "source_graph_identity_independently_verified": False,
            "source_structure_preserved": True, "native_graph_preserved": True,
            "native_graph_preservation_scope": "ordered native atom fields, native-native bonds and stereo groups; virtual H counts intentionally expand on scratch only",
            "mmff_aromaticity_typing_on_separate_copy": True,
            "mmff_working_graph_differs_from_template": _graph(forcefield_copy) != template_graph,
            "mmff_status": mmff_status, "embedding_conformer_id": conf_id,
            "embedding_failure_counts": list(params.GetFailureCounts()),
            "recipe": recipe, "recipe_sha256": canonical_hash(recipe), "stereo_validation": stereo,
            "generated_native_coordinates_float64_sha256": geometry_tensor_sha256(positions64),
            "encoder_tensor_hashes": hashes, "tensor_hash_recipe": TENSOR_HASH_RECIPE,
            "quantization_max_abs_error": float((positions64 - positions.to(torch.float64)).abs().max().item()),
            "quantization_absolute_error_unit": "angstrom (generator convention)",
            "atom_permutation_applied": False, "centering_applied": False, "scaling_applied": False,
            "tensor_transport_verified": True,
            "bounds": {"max_native_atoms": max_native_atoms, "max_work_atoms": max_work_atoms,
                       "max_provenance_bytes": MAX_PROVENANCE_BYTES,
                       "wall_time": "library cooperative limits only; caller process budget required"},
        }
        proof["geometry_provenance_sha256"] = canonical_hash(proof)
        _require(len(json.dumps(proof, sort_keys=True, separators=(",", ":"), allow_nan=False)
                     .encode("utf-8")) <= MAX_PROVENANCE_BYTES, "Generated geometry proof exceeds 64KiB")
        return GeneratedNativeGeometry(Data(x=x, pos=positions, batch=batch, ptr=ptr), ids, proof,
                                       positions64.clone())
    except (RuntimeError, TypeError, ValueError, OverflowError, RecursionError) as exc:
        if isinstance(exc, GeneratedGeometryError):
            raise
        raise GeneratedGeometryError("Fixed native geometry preparation failed") from exc
    finally:
        _require(source.ToBinary(Chem.PropertyPickleOptions.AllProps) == original,
                 "Geometry preparation changed original source graph, properties or conformers")
