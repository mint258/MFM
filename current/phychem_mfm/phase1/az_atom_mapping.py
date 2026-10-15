"""Current-runtime AZ raw-SMILES correspondence; no files or target decoding.

Both universes are the same default SMILES parser's atoms. No AddHs, RemoveHs,
canonical roundtrip or inferred permutation is permitted. The imported ordered
direction proof is a structural algorithm, not a CYP supplier/parser contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from rdkit import Chem, rdBase

from .downstream_structures import ATTNSOM_COMMIT, MAX_ATOMS, MAX_LINE_BYTES
from .identity import canonical_hash
from .som_direction_equivalence import (
    SomDirectionEquivalenceError, verify_cyp_direction_equivalence,
)


AZ_MAPPING_SCHEMA = "phase1_az_raw_smiles_author_atom_mapping_v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class AZAtomMappingError(ValueError):
    """An AZ ordered source pair does not prove the complete correspondence."""


def _require(condition, message):
    if not condition:
        raise AZAtomMappingError(message)


@dataclass(frozen=True)
class AZAuthorAtomMapping:
    author_to_native: tuple[int, ...]
    native_to_author: tuple[int, ...]
    retained_native_ids: tuple[int, ...]
    deleted_native_ids: tuple[int, ...]
    provenance: dict


def build_az_author_atom_mapping(native_mol, raw_smiles: str, *, source_file: str,
                                source_file_sha256: str, source_record_1based: int,
                                raw_frame_sha256: str, source_smiles_sha256: str) -> AZAuthorAtomMapping:
    """Independently parse the same unmodified string and verify every atom.

File/frame references are declared by the caller; the source-backed producer
verifies their actual bytes. This helper never sees annotations or geometry
payloads and does not establish old-author-version or chemical truth.
"""
    _require(source_file == "az_120_compounds.csv", "AZ mapping requires the known raw CSV basename")
    _require(type(source_record_1based) is int and source_record_1based > 0, "Positive raw CSV ordinal required")
    for value in (source_file_sha256, raw_frame_sha256, source_smiles_sha256):
        _require(type(value) is str and _SHA.fullmatch(value) is not None, "Explicit lowercase source SHA256 required")
    _require(type(raw_smiles) is str and 0 < len(raw_smiles) <= MAX_LINE_BYTES, "Bounded unmodified raw SMILES required")
    try:
        encoded = raw_smiles.encode("utf-8")
    except UnicodeError as exc:
        raise AZAtomMappingError("Raw SMILES has invalid UTF8") from exc
    _require(len(encoded) <= MAX_LINE_BYTES and hashlib.sha256(encoded).hexdigest() == source_smiles_sha256,
             "Actual raw SMILES bytes differ from their binding")
    _require(isinstance(native_mol, Chem.Mol), "Native input must be an actual source mol")
    original = native_mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    try:
        with rdBase.BlockLogs():
            author = Chem.MolFromSmiles(raw_smiles)
        _require(author is not None, "Independent default AZ SMILES parser failed")
        n = author.GetNumAtoms()
        _require(0 < n <= MAX_ATOMS and native_mol.GetNumAtoms() == n, "AZ author/native atom counts differ")
        # Full ordered atom/bond/stereo/conformer proof precedes the identity map.
        # A complete E/Z directional gauge can be proved; partial flips cannot.
        receipt = verify_cyp_direction_equivalence(native_mol, author)
        _require(receipt.get("status") in ("EXACT_ORDERED_SIGNATURE", "VERIFIED_DIRECTION_COMPONENT_INVERSION")
                 and receipt.get("all_other_ordered_fields_exact_match") is True
                 and receipt.get("original_molecules_preserved") is True
                 and receipt.get("receipt_sha256") == canonical_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"}),
                 "Invalid ordered AZ pair proof")
        ids = tuple(range(n))
        proof = {
            "schema_version": AZ_MAPPING_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
            "dataset": "az_exactsom", "source_file": source_file,
            "source_file_sha256": source_file_sha256, "source_record_1based": source_record_1based,
            "raw_frame_sha256": raw_frame_sha256, "source_smiles_sha256": source_smiles_sha256,
            "author_repository": "dmis-lab/ATTNSOM", "author_commit": ATTNSOM_COMMIT,
            "author_loader": "dataset.py:load_az_csv", "author_parser": "Chem.MolFromSmiles defaults",
            "parser_options": {"sanitize": True, "removeHs": True, "parseName": True},
            "rdkit_version": rdBase.rdkitVersion, "author_environment_rdkit_pin": "2025.3.6",
            "author_version_reproduced": False,
            "native_atoms": n, "author_atoms": n, "author_to_native": ids, "native_to_author": ids,
            "retained_native_ids": ids, "deleted_native_ids": (),
            "bijection_scope": "all current raw-SMILES parser atoms in unchanged native order",
            "mapping_method": "independent default parse; full ordered proof then identity map",
            "additional_hydrogen_transform": "none", "atom_reordering": False,
            "source_index_base": 0, "output_index_base": 0, "index_decrement_count": 0,
            "native_ordered_graph_sha256": receipt["candidate_raw"]["ordered_graph_sha256"],
            "author_ordered_graph_sha256": receipt["author_raw"]["ordered_graph_sha256"],
            "ordered_pair_structure_verification": receipt["status"],
            "direction_equivalence": receipt, "direction_equivalence_receipt_sha256": receipt["receipt_sha256"],
            "direction_algorithm_scope": "borrowed conservative ordered-structure algorithm; not CYP RemoveHs/supplier semantics",
            "native_source_original_preserved": True, "annotation_semantics_verified": False,
            "labels_read_or_inferred": False, "geometry_ready_for_encoder": False,
            "source_hash_binding": "caller-declared references; this pure helper performs no file I/O",
        }
        proof["mapping_provenance_sha256"] = canonical_hash(proof)
        return AZAuthorAtomMapping(ids, ids, ids, (), proof)
    except AZAtomMappingError:
        raise
    except (SomDirectionEquivalenceError, RuntimeError, ValueError) as exc:
        raise AZAtomMappingError("AZ native/default author pair lacks full ordered correspondence") from exc
    finally:
        _require(native_mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == original,
                 "AZ mapping changed the original native source mol")
