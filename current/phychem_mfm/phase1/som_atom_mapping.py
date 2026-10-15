"""Target-free CYP native-to-author atom lineage; no files or label decoding.

The caller supplies the retained-H native mol and the same record parsed by
the current RDKit default SDF supplier. A RemoveHs copy must match that actual
author mol in order, graph, stereo and coordinates, with a separately recorded
proof permitted for complete E/Z direction-component sign inversion. Only
the retained native subset is in bijection with author atoms. This is NOT_FROZEN preparation, not
proof of annotation semantics, author-version reproduction or H0 geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral
import re

from rdkit import Chem, rdBase

from .downstream_structures import ATTNSOM_COMMIT, MAX_ATOMS, SOURCE_CONTRACT
from .identity import canonical_hash
from .som_direction_equivalence import (
    SomDirectionEquivalenceError, verify_cyp_direction_equivalence,
)


MAPPING_SCHEMA = "phase1_cyp_native_author_atom_mapping_v2"
AUTHOR_RDKIT_PIN = "2025.3.6"
_LINEAGE = "_phase1_som_mapping_native_id_v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class SomAtomMappingError(ValueError):
    """A source pair does not prove the declared ordered atom correspondence."""


@dataclass(frozen=True)
class CYPAuthorAtomMapping:
    author_to_native: tuple[int, ...]
    native_to_author: tuple[int | None, ...]
    retained_native_ids: tuple[int, ...]
    deleted_native_ids: tuple[int, ...]
    provenance: dict


def _source_binding(source_file, source_file_sha256, source_record_1based,
                    source_block_sha256):
    if not isinstance(source_file, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.sdf", source_file):
        raise SomAtomMappingError("source_file must be a CYP SDF basename, not a path")
    for name, value in (("source_file_sha256", source_file_sha256),
                        ("source_block_sha256", source_block_sha256)):
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise SomAtomMappingError(f"{name} must be an explicit lowercase SHA256")
    if (isinstance(source_record_1based, bool) or not isinstance(source_record_1based, Integral)
            or source_record_1based <= 0):
        raise SomAtomMappingError("source_record_1based must be an explicit positive integer")
    return {"source_file": source_file, "source_file_sha256": source_file_sha256,
            "source_record_1based": int(source_record_1based),
            "source_block_sha256": source_block_sha256}


def _ordered_structure(mol):
    """Read structural getters only; no SDF/atom properties or target values."""
    count = mol.GetNumAtoms()
    if not 0 < count <= MAX_ATOMS:
        raise SomAtomMappingError("Source atom count is outside the bounded contract")
    atoms = []
    for atom in mol.GetAtoms():
        z = atom.GetAtomicNum()
        if not 1 <= z <= 118 or atom.HasQuery():
            raise SomAtomMappingError("Unsupported source element or query atom")
        atoms.append((z, atom.GetIsotope(), atom.GetFormalCharge(),
                      atom.GetNumExplicitHs(), atom.GetNumImplicitHs(), atom.GetNoImplicit(),
                      str(atom.GetChiralTag()), atom.GetIsAromatic(),
                      atom.GetNumRadicalElectrons(), atom.GetAtomMapNum()))
    bonds = []
    for bond in mol.GetBonds():
        if bond.HasQuery():
            raise SomAtomMappingError("Query bonds are outside the source contract")
        bonds.append((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(), str(bond.GetBondType()),
                      bond.GetIsAromatic(), bond.GetIsConjugated(), str(bond.GetStereo()),
                      tuple(bond.GetStereoAtoms()), str(bond.GetBondDir())))
    groups = [(str(group.GetGroupType()), tuple(atom.GetIdx() for atom in group.GetAtoms()),
               tuple(bond.GetIdx() for bond in group.GetBonds())) for group in mol.GetStereoGroups()]
    conformers = []
    if mol.GetNumConformers() > 16:
        raise SomAtomMappingError("Source conformer count is outside the bounded contract")
    for conformer in mol.GetConformers():
        coordinates = []
        for index in range(count):
            point = conformer.GetAtomPosition(index)
            row = (point.x, point.y, point.z)
            if not all(math.isfinite(value) for value in row):
                raise SomAtomMappingError("Source coordinates must be finite")
            coordinates.append(row)
        conformers.append((conformer.GetId(), conformer.Is3D(), tuple(coordinates)))
    return {"atoms": tuple(atoms), "bonds": tuple(bonds), "stereo_groups": tuple(groups),
            "conformers": tuple(conformers)}


def _graph_hash(signature):
    return canonical_hash({key: signature[key] for key in ("atoms", "bonds", "stereo_groups")})


def build_cyp_author_atom_mapping(native_mol, author_mol, *, source_file: str,
                                  source_file_sha256: str, source_record_1based: int,
                                  source_block_sha256: str) -> CYPAuthorAtomMapping:
    """Verify one source pair without reading files or interpreting annotations.

    Both inputs must come from the same structural SDF record; the author mol
    must be the caller's actual default-supplier result in this RDKit runtime.
    The helper checks ordered equivalence, not the caller's file/hash claims.
    No implicit atom matching, canonical roundtrip, index conversion or label
    mask is performed. Original molecules, properties and coordinates stay
    untouched. The candidate's default RemoveHs may retain special H atoms.
    """
    binding = _source_binding(source_file, source_file_sha256, source_record_1based,
                              source_block_sha256)
    if not isinstance(native_mol, Chem.Mol) or not isinstance(author_mol, Chem.Mol):
        raise SomAtomMappingError("Both inputs must be actual RDKit source molecules")
    try:
        # Read and mutate copies only, including any structural property caches.
        native, author = Chem.Mol(native_mol), Chem.Mol(author_mol)
        native_signature, author_signature = _ordered_structure(native), _ordered_structure(author)
        for index, atom in enumerate(native.GetAtoms()):
            atom.SetIntProp(_LINEAGE, index)
        with rdBase.BlockLogs():
            candidate = Chem.RemoveHs(native)
        candidate_signature = _ordered_structure(candidate)
        if any(not atom.HasProp(_LINEAGE) for atom in candidate.GetAtoms()):
            raise SomAtomMappingError("Default RemoveHs lost native atom lineage")
        author_to_native = tuple(atom.GetIntProp(_LINEAGE) for atom in candidate.GetAtoms())
        count = len(native_signature["atoms"])
        if (len(set(author_to_native)) != len(author_to_native)
                or any(not 0 <= index < count for index in author_to_native)):
            raise SomAtomMappingError("Default RemoveHs produced invalid or duplicate native lineage")
        if author_to_native != tuple(sorted(author_to_native)):
            raise SomAtomMappingError("Default RemoveHs reordered the native source atoms")
        retained = author_to_native
        retained_set = set(retained)
        deleted = tuple(index for index in range(count) if index not in retained_set)
        if any(native_signature["atoms"][index][0] != 1 for index in deleted):
            raise SomAtomMappingError("Default RemoveHs deleted a non-hydrogen source atom")
        for author_index, native_index in enumerate(retained):
            if candidate_signature["atoms"][author_index][:3] != native_signature["atoms"][native_index][:3]:
                raise SomAtomMappingError("A retained atom changed element, isotope or formal charge")
        for field in ("atoms", "stereo_groups", "conformers"):
            if candidate_signature[field] != author_signature[field]:
                raise SomAtomMappingError(f"Default RemoveHs and actual author mol differ in ordered {field}")
        try:
            direction_equivalence = verify_cyp_direction_equivalence(candidate, author)
        except SomDirectionEquivalenceError as exc:
            raise SomAtomMappingError("Default RemoveHs and actual author mol differ in ordered bonds") from exc
    except SomAtomMappingError:
        raise
    except Exception as exc:
        raise SomAtomMappingError("Source structure or default RemoveHs comparison failed") from exc

    inverse = [None] * count
    for author_index, native_index in enumerate(author_to_native):
        inverse[native_index] = author_index
    provenance = {
        "schema_version": MAPPING_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
        "source_contract": SOURCE_CONTRACT, "author_repository": "dmis-lab/ATTNSOM",
        "author_commit": ATTNSOM_COMMIT, "author_loader": "dataset.py:load_cyp_sdf",
        "author_parser": "Chem.SDMolSupplier default sanitize=True/removeHs=True/strictParsing=True",
        "author_environment_rdkit_pin": AUTHOR_RDKIT_PIN, "rdkit_version": rdBase.rdkitVersion,
        "author_runtime_version_matches_pin": rdBase.rdkitVersion == "2025.03.6",
        "author_version_reproduced": False,
        "version_scope": "current runtime ordered-pair verification; not author-version equivalence",
        "mapping_method": "private native lineage on a copy; Chem.RemoveHs defaults",
        "bijection_scope": "author_atoms_to_retained_native_subset_only",
        "native_atoms": count, "author_atoms": len(author_to_native),
        "retained_native_ids": retained, "deleted_native_ids": deleted,
        "author_to_native": author_to_native, "native_to_author": tuple(inverse),
        "native_ordered_graph_sha256": _graph_hash(native_signature),
        "candidate_ordered_graph_sha256": _graph_hash(candidate_signature),
        "author_ordered_graph_sha256": _graph_hash(author_signature),
        "candidate_ordered_signature_sha256": canonical_hash(candidate_signature),
        "author_ordered_signature_sha256": canonical_hash(author_signature),
        "native_coordinates_sha256": canonical_hash(native_signature["conformers"]),
        "author_coordinates_sha256": canonical_hash(author_signature["conformers"]),
        "ordered_pair_structure_verified": True,
        "ordered_pair_structure_verified_meaning": "same retained order and non-direction fields; exact or proven E/Z directional semantics",
        "ordered_pair_structure_verification": direction_equivalence["status"],
        "ordered_signature_exact_match": direction_equivalence["ordered_signature_exact_match"],
        "ordered_direction_flags_exact_match": direction_equivalence["ordered_direction_flags_exact_match"],
        "all_other_ordered_fields_exact_match": True,
        "paired_structure_semantics_verified": True,
        "direction_equivalence": direction_equivalence,
        "direction_equivalence_receipt_sha256": direction_equivalence["receipt_sha256"],
        "annotation_semantics_verified": False, "labels_read_or_inferred": False,
        "geometry_ready_for_encoder": False, "source_or_fold_mutation": False,
        "source_hash_binding": "caller-declared references; helper performs no file I/O",
        **binding,
    }
    provenance["mapping_provenance_sha256"] = canonical_hash(provenance)
    return CYPAuthorAtomMapping(author_to_native, tuple(inverse), retained, deleted, provenance)
