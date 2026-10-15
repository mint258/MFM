"""Strict, pure PRIMARY_SOM projection into the preserved native CYP order.

This is a NOT_FROZEN capability, not a choice of formal negative supervision.
Only the fixed ATTNSOM primary-property grammar and nine isoform tasks are
supported. ASCII parsing is deliberately stricter than the author's tolerant
loader. Only the supplied primary text and mapping metadata are consumed; no
additional targets, properties, molecules, coordinates or files are read.
Source/property association and the mapping's molecular evidence remain caller
claims: validating their metadata cannot independently prove their truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re

from .downstream_structures import ATTNSOM_COMMIT, MAX_ATOMS, SOURCE_CONTRACT
from .identity import canonical_hash
from .som_atom_mapping import AUTHOR_RDKIT_PIN, CYPAuthorAtomMapping, MAPPING_SCHEMA
from .som_direction_equivalence import DIRECTION_EQUIVALENCE_SCHEMA


ANNOTATION_SCHEMA = "phase1_cyp_primary_annotation_v1"
CYP_ISOFORMS = ("1A2", "2A6", "2B6", "2C8", "2C9", "2C19", "2D6", "2E1", "3A4")
MAX_ANNOTATION_BYTES = 65536
MAX_MAPPING_PROVENANCE_BYTES = 1048576
_EMPTY_POLICIES = ("reject", "preserve_unknown", "author_zero")
_SPACE = " \t\n\r\v\f"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[0-9]+\Z")


class SomAnnotationError(ValueError):
    """A primary field or its declared source mapping is not strictly valid."""


@dataclass(frozen=True)
class CYPPrimaryAnnotation:
    labels: tuple[int | None, ...]
    candidate_mask: tuple[bool, ...]
    supervision_mask: tuple[bool, ...]
    positive_author_ids: tuple[int, ...]
    positive_native_ids: tuple[int, ...]
    provenance: dict


def _require(condition, message):
    if not condition:
        raise SomAnnotationError(message)


def _digest(value, name):
    _require(isinstance(value, str) and _SHA256.fullmatch(value) is not None,
             name + " must be a lowercase SHA256")
    return value


def _ids(values, name, *, nullable=False, require_tuple=False):
    _require(isinstance(values, tuple) if require_tuple else isinstance(values, (list, tuple)),
             name + " must be an explicit atom-ID sequence")
    _require(len(values) <= MAX_ATOMS, name + " exceeds MAX_ATOMS")
    _require(all(type(value) is int or (nullable and value is None) for value in values),
             name + " contains a non-integer atom ID")
    return tuple(values)


def _bounded_metadata_copy(value):
    """Bound traversal and each possible JSON string chunk before encoding."""
    nodes, string_bytes, active = 0, 0, set()

    def scan(item, depth):
        nonlocal nodes, string_bytes
        nodes += 1
        _require(nodes <= MAX_MAPPING_PROVENANCE_BYTES and depth <= 64,
                 "Mapping provenance exceeds its node/depth bound")
        kind = type(item)
        if kind is str:
            _require(len(item) <= MAX_MAPPING_PROVENANCE_BYTES,
                     "Mapping provenance scalar exceeds its byte bound")
            string_bytes += 2  # JSON string quotes, including dictionary keys.
            for char in item:
                code = ord(char)
                _require(not 0xD800 <= code <= 0xDFFF, "Mapping provenance contains invalid Unicode")
                if char in ('"', "\\", "\b", "\f", "\n", "\r", "\t"):
                    string_bytes += 2
                elif code < 32:
                    string_bytes += 6
                else:
                    string_bytes += 1 if code < 128 else 2 if code < 2048 else 3 if code < 65536 else 4
                _require(string_bytes <= MAX_MAPPING_PROVENANCE_BYTES,
                         "Mapping provenance strings exceed their encoded byte bound")
        elif kind in (dict, list, tuple):
            _require(id(item) not in active, "Mapping provenance contains a cycle")
            _require(len(item) <= MAX_MAPPING_PROVENANCE_BYTES - nodes,
                     "Mapping provenance container exceeds its item bound")
            active.add(id(item))
            if kind is dict:
                for key, entry in item.items():
                    _require(type(key) is str, "Mapping provenance keys must be strings")
                    scan(key, depth + 1)
                    scan(entry, depth + 1)
            else:
                for entry in item:
                    scan(entry, depth + 1)
            active.remove(id(item))
        elif kind is int:
            # Also prevents an enormous single numeric encoder chunk.
            _require(item.bit_length() <= 4096, "Mapping provenance integer exceeds its scalar bound")
        elif kind is float:
            _require(math.isfinite(item), "Mapping provenance numbers must be finite")
        else:
            _require(kind in (bool, type(None)), "Mapping provenance must contain only JSON metadata")

    try:
        scan(value, 0)
        encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False)
        encoded = bytearray()
        for chunk in encoder.iterencode(value):
            block = chunk.encode("utf-8")
            _require(len(encoded) + len(block) <= MAX_MAPPING_PROVENANCE_BYTES,
                     "Mapping provenance exceeds its serialized byte bound")
            encoded.extend(block)
        return json.loads(encoded)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, SomAnnotationError):
            raise
        raise SomAnnotationError("Mapping provenance must be bounded finite JSON metadata") from exc


def _validated_mapping(mapping, isoform):
    """Check the existing producer's receipt, without re-proving any molecule."""
    _require(isinstance(mapping, CYPAuthorAtomMapping),
             "mapping must be a CYPAuthorAtomMapping")
    forward = _ids(mapping.author_to_native, "author_to_native", require_tuple=True)
    inverse = _ids(mapping.native_to_author, "native_to_author", nullable=True, require_tuple=True)
    retained = _ids(mapping.retained_native_ids, "retained_native_ids", require_tuple=True)
    deleted = _ids(mapping.deleted_native_ids, "deleted_native_ids", require_tuple=True)
    native_count, author_count = len(inverse), len(forward)
    _require(0 < author_count <= native_count <= MAX_ATOMS, "Invalid native/author atom counts")
    _require(len(set(forward)) == author_count
             and all(0 <= index < native_count for index in forward), "Invalid retained native IDs")
    _require(forward == tuple(sorted(forward)) == retained,
             "Author order must be the producer's ordered retained native subset")
    retained_set = set(retained)
    _require(deleted == tuple(index for index in range(native_count) if index not in retained_set),
             "Deleted native IDs do not complement the retained set")
    expected_inverse = [None] * native_count
    for author_id, native_id in enumerate(forward):
        expected_inverse[native_id] = author_id
    _require(inverse == tuple(expected_inverse), "Native/author maps are not a retained-subset bijection")

    _require(isinstance(mapping.provenance, dict), "Mapping provenance must be a dictionary")
    # This detached copy has no references into the caller's nested metadata.
    proof = _bounded_metadata_copy(mapping.provenance)
    digest = _digest(proof.get("mapping_provenance_sha256"), "mapping_provenance_sha256")
    _require(canonical_hash({key: value for key, value in proof.items()
                             if key != "mapping_provenance_sha256"}) == digest,
             "Mapping provenance hash does not match its complete contents")
    expected = {"schema_version": MAPPING_SCHEMA, "state": "NOT_FROZEN",
                "source_contract": SOURCE_CONTRACT, "author_repository": "dmis-lab/ATTNSOM",
                "author_commit": ATTNSOM_COMMIT, "author_loader": "dataset.py:load_cyp_sdf",
                "author_parser": "Chem.SDMolSupplier default sanitize=True/removeHs=True/strictParsing=True",
                "author_environment_rdkit_pin": AUTHOR_RDKIT_PIN,
                "mapping_method": "private native lineage on a copy; Chem.RemoveHs defaults",
                "bijection_scope": "author_atoms_to_retained_native_subset_only",
                "source_hash_binding": "caller-declared references; helper performs no file I/O",
                "source_file": isoform + ".sdf"}
    for name, value in expected.items():
        _require(proof.get(name) == value, "Mapping source contract differs at " + name)
    for name in ("formal_eligible", "author_version_reproduced", "annotation_semantics_verified",
                 "labels_read_or_inferred", "geometry_ready_for_encoder", "source_or_fold_mutation"):
        _require(proof.get(name) is False, "Mapping has an unsupported claim at " + name)
    for name in ("ordered_pair_structure_verified", "all_other_ordered_fields_exact_match",
                 "paired_structure_semantics_verified"):
        _require(proof.get(name) is True, "Mapping lacks its structural receipt at " + name)
    for name, value in (("native_atoms", native_count), ("author_atoms", author_count)):
        _require(type(proof.get(name)) is int and proof[name] == value,
                 "Mapping count differs at " + name)
    for name, value in (("author_to_native", forward), ("native_to_author", inverse),
                        ("retained_native_ids", retained), ("deleted_native_ids", deleted)):
        _require(_ids(proof.get(name), name, nullable=name == "native_to_author") == value,
                 "Mapping arrays differ from provenance at " + name)
    for name in ("source_file_sha256", "source_block_sha256", "native_ordered_graph_sha256",
                 "candidate_ordered_graph_sha256", "author_ordered_graph_sha256",
                 "candidate_ordered_signature_sha256", "author_ordered_signature_sha256",
                 "native_coordinates_sha256", "author_coordinates_sha256"):
        _digest(proof.get(name), name)
    _require(type(proof.get("source_record_1based")) is int and proof["source_record_1based"] > 0,
             "Mapping requires a positive source record ordinal")
    _require(isinstance(proof.get("rdkit_version"), str) and bool(proof["rdkit_version"]),
             "Mapping must record its current parser runtime")
    _require(proof.get("author_runtime_version_matches_pin") is (proof["rdkit_version"] == "2025.03.6"),
             "Mapping runtime/pinned-version flag is inconsistent")

    receipt = proof.get("direction_equivalence")
    _require(isinstance(receipt, dict), "Mapping lacks its direction-equivalence receipt")
    receipt_digest = _digest(receipt.get("receipt_sha256"), "receipt_sha256")
    _require(receipt_digest == proof.get("direction_equivalence_receipt_sha256")
             and canonical_hash({key: value for key, value in receipt.items()
                                 if key != "receipt_sha256"}) == receipt_digest,
             "Direction-equivalence receipt hash is inconsistent")
    _require(receipt.get("schema_version") == DIRECTION_EQUIVALENCE_SCHEMA
             and receipt.get("state") == "NOT_FROZEN"
             and receipt.get("rdkit_version") == proof["rdkit_version"],
             "Direction receipt schema/runtime does not match the mapping")
    for name in ("formal_eligible", "author_version_reproduced", "annotation_semantics_verified",
                 "labels_read_or_inferred", "atom_or_bond_reordering", "direction_flags_rewritten"):
        _require(receipt.get(name) is False, "Direction receipt has an unsupported claim at " + name)
    for name in ("original_molecules_preserved", "all_other_ordered_fields_exact_match"):
        _require(receipt.get(name) is True, "Direction receipt lacks its structural claim at " + name)
    status = receipt.get("status")
    _require(status in ("EXACT_ORDERED_SIGNATURE", "VERIFIED_DIRECTION_COMPONENT_INVERSION")
             and proof.get("ordered_pair_structure_verification") == status,
             "Mapping has no supported ordered-pair verification mode")
    for name in ("ordered_signature_exact_match", "ordered_direction_flags_exact_match"):
        _require(type(proof.get(name)) is bool and proof[name] is receipt.get(name)
                 and proof[name] is (status == "EXACT_ORDERED_SIGNATURE"),
                 "Mapping direction status differs at " + name)
    for role in ("candidate", "author"):
        raw = receipt.get(role + "_raw")
        _require(isinstance(raw, dict)
                 and raw.get("ordered_graph_sha256") == proof[role + "_ordered_graph_sha256"]
                 and raw.get("ordered_signature_sha256") == proof[role + "_ordered_signature_sha256"],
                 "Mapping raw hashes differ from direction receipt for " + role)
    if status == "EXACT_ORDERED_SIGNATURE":
        _require(proof["candidate_ordered_graph_sha256"] == proof["author_ordered_graph_sha256"]
                 and proof["candidate_ordered_signature_sha256"] == proof["author_ordered_signature_sha256"],
                 "Exact mapping claims unequal candidate/author signatures")
        decoded = receipt.get("decoded_copies")
        _require(receipt.get("changed_bond_ids") == [] and receipt.get("components") == []
                 and isinstance(decoded, dict) and decoded.get("performed") is False,
                 "Exact mapping claims changed components or copy redecoding")
    return forward, inverse, retained, deleted, proof


def decode_cyp_primary_annotation(primary_som, mapping: CYPAuthorAtomMapping, *,
                                  isoform: str, empty_policy: str) -> CYPPrimaryAnnotation:
    """Decode a present PRIMARY_SOM string, then project one time through its map.

    Input is bounded to 64 KiB of UTF-8 and metadata to 1 MiB, with no truncation.
    Only ASCII whitespace/digits are accepted; leading zeros and idempotent
    duplicates are legal. Every integer must be 1..author_atoms before one
    subtraction. Missing properties and malformed fields always fail.

    ``preserve_unknown`` gives a present-empty field no supervision, whereas
    explicit ``author_zero`` reproduces the author's binary all-zero capability
    on retained atoms. Neither option establishes chemical negative truth or
    formal eligibility. Nonempty candidate 0/1 likewise describes author-code
    semantics, not independently verified annotation completeness. Deleted H
    is unknown; retained special H stays in the actual mapped candidate set.

    The caller must prove the property and structure came from the same source
    record. This pure function checks declared metadata only, performs no I/O,
    and never mutates mapping data, molecular state or random-number generators.
    """
    _require(isinstance(isoform, str) and isoform in CYP_ISOFORMS, "Unsupported CYP isoform")
    _require(isinstance(empty_policy, str) and empty_policy in _EMPTY_POLICIES,
             "empty_policy must explicitly be reject, preserve_unknown or author_zero")
    _require(isinstance(primary_som, str), "A present PRIMARY_SOM string is required; missing is unknown")
    _require(len(primary_som) <= MAX_ANNOTATION_BYTES, "PRIMARY_SOM exceeds its byte bound")
    _require(primary_som.isascii(), "PRIMARY_SOM accepts ASCII whitespace and decimal digits only")
    try:
        encoded = primary_som.encode("utf-8")
    except UnicodeError as exc:
        raise SomAnnotationError("PRIMARY_SOM must have valid UTF-8 text") from exc
    _require(len(encoded) <= MAX_ANNOTATION_BYTES, "PRIMARY_SOM exceeds its UTF-8 byte bound")
    forward, inverse, retained, deleted, source = _validated_mapping(mapping, isoform)
    stripped = primary_som.strip(_SPACE)
    raw_tokens = tuple(re.split(r"[ \t\n\r\v\f]+", stripped)) if stripped else ()
    _require(bool(raw_tokens) or empty_policy != "reject", "Present-empty PRIMARY_SOM is rejected")
    unique, seen, duplicates, duplicate_positions = [], set(), [], []
    for position, token in enumerate(raw_tokens):
        _require(_TOKEN.fullmatch(token) is not None, "Malformed PRIMARY_SOM token")
        digits = token.lstrip("0") or "0"
        # Avoid Python's huge-int conversion limit; long leading zeros are safe.
        _require(len(digits) <= len(str(len(forward))), "PRIMARY_SOM index exceeds author atom count")
        one_based = int(digits)
        _require(1 <= one_based <= len(forward), "PRIMARY_SOM index is outside 1..author_atoms")
        author_id = one_based - 1
        if author_id in seen:
            duplicates.append(author_id)
            duplicate_positions.append(position)
        else:
            seen.add(author_id)
            unique.append(author_id)
    positive_author = tuple(unique)
    positive_native = tuple(forward[index] for index in positive_author)
    candidate = tuple(index is not None for index in inverse)
    has_supervision = bool(raw_tokens) or empty_policy == "author_zero"
    supervision = candidate if has_supervision else (False,) * len(inverse)
    labels = [None] * len(inverse)
    if has_supervision:
        for index in retained:
            labels[index] = 0
        for index in positive_native:
            labels[index] = 1
    labels = tuple(labels)
    state = ("NONEMPTY_BINARY_SET" if raw_tokens else "PRESENT_EMPTY_AUTHOR_ZERO"
             if empty_policy == "author_zero" else "PRESENT_EMPTY_UNKNOWN")
    provenance = {
        "schema_version": ANNOTATION_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
        "annotation_truth_verified": False, "annotation_completeness_verified": False,
        "property_name": "PRIMARY_SOM", "property_present": True,
        "isoform": isoform, "empty_policy": empty_policy, "annotation_state": state,
        "decoded_property_utf8_sha256": hashlib.sha256(encoded).hexdigest(),
        "decoded_property_utf8_bytes": len(encoded),
        "input_byte_bound": MAX_ANNOTATION_BYTES, "raw_tokens": raw_tokens,
        "raw_token_count": len(raw_tokens), "unique_positive_count": len(unique),
        "duplicate_count": len(duplicates), "duplicate_author_ids": tuple(duplicates),
        "duplicate_token_positions": tuple(duplicate_positions),
        "duplicate_policy": "binary-set idempotence; first-appearance order retained",
        "grammar": "ASCII unsigned decimal tokens separated by ASCII whitespace only",
        "strictness_scope": "stricter malformed/missing/Unicode/range handling; not a literal tolerant-loader replica",
        "source_index_base": 1, "output_index_base": 0, "index_decrement_count": 1,
        "index_conversion": "int(token)-1 exactly once, then author_to_native",
        "positive_author_ids": positive_author, "positive_native_ids": positive_native,
        "native_atoms": len(inverse), "author_atoms": len(forward),
        "author_to_native": forward, "native_to_author": inverse,
        "retained_native_ids": retained, "deleted_native_ids": deleted,
        "labels": labels, "candidate_mask": candidate, "supervision_mask": supervision,
        "candidate_count": sum(candidate), "supervision_count": sum(supervision),
        "candidate_universe": "all author parser atoms mapped to retained native subset; no element filter",
        "label_semantics": "author-code binary set within candidates; deleted atoms unknown",
        "present_empty_author_code_all_zero": not bool(raw_tokens),
        "supervision_enabled_by_decoder_policy": has_supervision,
        "chemical_negative_truth_verified": False,
        "source_contract": source["source_contract"], "author_repository": source["author_repository"],
        "author_commit": source["author_commit"], "author_loader": source["author_loader"],
        "author_parser": source["author_parser"], "rdkit_version": source["rdkit_version"],
        "author_environment_rdkit_pin": source["author_environment_rdkit_pin"],
        "author_version_reproduced": False,
        "source_file": source["source_file"], "source_file_sha256": source["source_file_sha256"],
        "source_record_1based": source["source_record_1based"], "source_block_sha256": source["source_block_sha256"],
        "mapping_schema_version": source["schema_version"],
        "mapping_provenance_sha256": source["mapping_provenance_sha256"],
        "direction_equivalence_receipt_sha256": source["direction_equivalence_receipt_sha256"],
        "ordered_pair_structure_verification": source["ordered_pair_structure_verification"],
        "mapping_metadata_consistent": True, "mapping_molecular_truth_independently_verified": False,
        "source_or_annotation_truth_independently_verified": False,
        "property_source_record_association_independently_verified": False,
        "structure_block_hash_covers_property": False,
        "source_binding_scope": "caller-declared file/record/block plus supplied property; no file or molecule I/O",
        "source_or_fold_mutation": False, "other_annotation_levels_consumed": False,
        "geometry_ready_for_encoder": False,
    }
    provenance["annotation_provenance_sha256"] = canonical_hash(provenance)
    return CYPPrimaryAnnotation(labels, candidate, supervision, positive_author, positive_native, provenance)
