"""Strict supplied-text AZ exact-group capability; no labels, masks or file I/O.

The fixed ATTNSOM loader accepts two literal lists and uses 0-based raw-SMILES
parser indices. This capability preserves groups and rejects malformed input
instead of reproducing its filtering/truncation or all-zero fallbacks. Empty
and extended-only states never establish valid negative supervision.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import json
import re

from .identity import canonical_hash

AZ_ANNOTATION_SCHEMA = "phase1_az_exact_group_annotation_v1"
AUTHOR_COMMIT = "0faa38bbd1665262efb3642a2a3ae0f83c928a49"
AUTHOR_SOURCE_URL = "https://github.com/dmis-lab/ATTNSOM/blob/" + AUTHOR_COMMIT + "/dataset.py"
GROUP_COLUMN = "SoMs grouped (numbers provided are atom indices)"
FLAG_COLUMN = "Exact SoM annotation (1) or extended SoM annotation (0) per group"
MAX_FIELD_BYTES, MAX_AST_NODES, MAX_AST_DEPTH = 65536, 4096, 8
MAX_GROUPS, MAX_INDEX_TOKENS, MAX_AUTHOR_ATOMS = 1024, 8192, 4096
_SPACE = " \t\n\r\v\f"
_DIGITS = re.compile(r"[0-9]+\Z")


class AZAnnotationError(ValueError):
    """Supplied AZ annotation text is outside the strict bounded grammar."""


def _require(ok, message):
    if not ok:
        raise AZAnnotationError(message)


@dataclass(frozen=True, init=False)
class AZExactGroups:
    groups: tuple[tuple[int, ...], ...]
    raw_group_strings: tuple[str, ...]
    flags: tuple[int, ...]
    exact_author_ids: tuple[int, ...]
    annotation_state: str
    _provenance_json: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise AZAnnotationError("Use parse_az_exact_groups; no supplied receipt bypass")

    @property
    def provenance(self) -> dict:
        """Each access returns an owned JSON snapshot; internal receipt is immutable."""
        return json.loads(self._provenance_json)

    def to_dict(self) -> dict:
        return {"groups": [list(group) for group in self.groups], "raw_group_strings": list(self.raw_group_strings),
                "flags": list(self.flags), "exact_author_ids": list(self.exact_author_ids),
                "annotation_state": self.annotation_state, "provenance": self.provenance}


def _literal_list(text, name):
    _require(type(text) is str and len(text) <= MAX_FIELD_BYTES, name + " requires bounded supplied text")
    try:
        encoded = text.encode("utf-8")
        _require(len(encoded) <= MAX_FIELD_BYTES, name + " exceeds UTF8 byte cap")
        tree = ast.parse(text.strip(_SPACE), mode="eval")
        pending, nodes = [(tree, 0)], 0
        while pending:
            node, depth = pending.pop()
            nodes += 1
            _require(nodes <= MAX_AST_NODES and depth <= MAX_AST_DEPTH, name + " exceeds AST node/depth cap")
            _require(type(node) in (ast.Expression, ast.List, ast.Constant, ast.Load), name + " permits literal lists/constants only")
            pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
        _require(type(tree.body) is ast.List, name + " requires a literal list")
        result = ast.literal_eval(tree)
    except AZAnnotationError:
        raise
    except (UnicodeError, ValueError, SyntaxError, RecursionError, MemoryError) as exc:
        raise AZAnnotationError(name + " has invalid bounded UTF8/literal syntax") from exc
    _require(type(result) is list and len(result) <= MAX_GROUPS, name + " exceeds group cap")
    return result, {"decoded_field_utf8_sha256": hashlib.sha256(encoded).hexdigest(), "decoded_field_utf8_bytes": len(encoded),
                    "hash_scope": "supplied decoded text UTF8; not raw CSV field/frame bytes", "ast_nodes": nodes}


def parse_az_exact_groups(som_groups_text: str, annotation_types_text: str, *, n_author_atoms: int) -> AZExactGroups:
    """Parse both complete fields before deriving the exact 0-based binary set.

    Groups are strings of ASCII unsigned decimals separated by commas, or an
    empty/ASCII-whitespace string. Flags accept integer 0/1 or literal strings
    trimming to exactly '0'/'1', as in the author's example; bool is rejected.
    Caller atom count is declared parser metadata, not independently verified.
    """
    _require(type(n_author_atoms) is int and 0 < n_author_atoms <= MAX_AUTHOR_ATOMS, "Actual declared author atom count required")
    raw_groups, groups_binding = _literal_list(som_groups_text, "groups")
    raw_flags, flags_binding = _literal_list(annotation_types_text, "flags")
    _require(len(raw_groups) == len(raw_flags), "Group/flag cardinality must be exactly equal")
    groups, flags, flag_types, flag_string_hashes = [], [], [], []
    duplicates, exact_duplicates, seen_all, seen_exact, exact_ids = [], [], set(), set(), []
    occurrences = exact_occurrences = 0
    for group_id, (raw_group, raw_flag) in enumerate(zip(raw_groups, raw_flags)):
        _require(type(raw_group) is str and raw_group.isascii(), "Every group must be an ASCII string")
        if type(raw_flag) is int:
            _require(raw_flag in (0, 1), "Integer flag must be 0 or 1")
            flag, flag_type, string_hash = raw_flag, "integer", None
        else:
            _require(type(raw_flag) is str and raw_flag.isascii() and raw_flag.strip(_SPACE) in ("0", "1"), "String flag must be exactly ASCII 0 or 1 after trim")
            flag, flag_type = int(raw_flag.strip(_SPACE)), "string"
            string_hash = hashlib.sha256(raw_flag.encode("utf-8")).hexdigest()
        parsed = []
        for token_id, token in enumerate(raw_group.split(",") if raw_group.strip(_SPACE) else []):
            token = token.strip(_SPACE)
            _require(_DIGITS.fullmatch(token) is not None, "Group index requires an ASCII unsigned decimal")
            digits = token.lstrip("0") or "0"
            _require(len(digits) <= len(str(n_author_atoms - 1)), "Group index exceeds author atom range")
            index = int(digits)
            _require(0 <= index < n_author_atoms, "Group index outside 0..author_atoms-1")
            occurrences += 1
            _require(occurrences <= MAX_INDEX_TOKENS, "Index-token count exceeds cap")
            parsed.append(index)
            if index in seen_all:
                duplicates.append((group_id, token_id, index))
            seen_all.add(index)
            if flag == 1:
                exact_occurrences += 1
                if index in seen_exact:
                    exact_duplicates.append((group_id, token_id, index))
                else:
                    seen_exact.add(index)
                    exact_ids.append(index)
        groups.append(tuple(parsed))
        flags.append(flag)
        flag_types.append(flag_type)
        flag_string_hashes.append(string_hash)
    state = ("NO_GROUPS" if not groups else "EXACT_INDICES_PRESENT" if exact_ids else
             "EXACT_GROUPS_EMPTY" if any(flags) else "EMPTY_GROUPS" if not occurrences else "EXTENDED_ONLY")
    proof = {"schema_version": AZ_ANNOTATION_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
             "annotation_state": state, "author_parser_atom_count": n_author_atoms,
             "author_atom_count_independently_verified": False, "source_index_base": 0, "output_index_base": 0, "index_decrement_count": 0,
             "groups": groups, "raw_group_strings": raw_groups, "normalized_flags": flags,
             "raw_flag_types": flag_types, "raw_flag_string_utf8_sha256": flag_string_hashes, "exact_author_ids": exact_ids,
             "group_count": len(groups), "empty_group_count": sum(not g for g in groups), "exact_group_count": sum(flags),
             "extended_group_count": len(flags) - sum(flags), "all_index_occurrences": occurrences,
             "all_unique_index_count": len(seen_all), "all_duplicate_occurrence_count": len(duplicates), "duplicate_occurrences": duplicates,
             "exact_index_occurrences": exact_occurrences, "unique_exact_author_atom_count": len(exact_ids),
             "exact_duplicate_occurrence_count": len(exact_duplicates), "exact_duplicate_occurrences": exact_duplicates,
             "duplicate_policy": "binary-set idempotence; groups/repetitions preserved; exact IDs first appearance",
             "groups_field": {"column": GROUP_COLUMN, **groups_binding}, "flags_field": {"column": FLAG_COLUMN, **flags_binding},
             "limits": {"field_utf8_bytes": MAX_FIELD_BYTES, "ast_nodes": MAX_AST_NODES, "ast_depth": MAX_AST_DEPTH,
                        "groups": MAX_GROUPS, "index_tokens": MAX_INDEX_TOKENS, "author_atoms": MAX_AUTHOR_ATOMS},
             "author_repository": "dmis-lab/ATTNSOM", "author_commit": AUTHOR_COMMIT, "author_source_url": AUTHOR_SOURCE_URL,
             "author_source_lines": "dataset.py:22-24,47-102", "source_contract": "AZ raw-SMILES parser 0-based; exact flag1 groups only",
             "strictness_scope": "preserves empty groups; rejects malformed tokens/types/ranges, nonbinary flags and list-size mismatch instead of tolerant filtering/fallback",
             "exact_set_order_scope": "first appearance; author sorts the same exact set, no output atom reordering performed",
             "source_or_property_association_verified": False, "annotation_truth_verified": False, "annotation_completeness_verified": False,
             "chemical_negative_truth_verified": False, "author_version_reproduced": False,
             "labels_or_supervision_masks_generated": False, "native_mapping_or_geometry_used": False, "source_or_file_io": False}
    proof["annotation_provenance_sha256"] = canonical_hash(proof)
    result = object.__new__(AZExactGroups)
    for key, value in (("groups", tuple(groups)), ("raw_group_strings", tuple(raw_groups)), ("flags", tuple(flags)),
                       ("exact_author_ids", tuple(exact_ids)), ("annotation_state", state),
                       ("_provenance_json", json.dumps(proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))):
        object.__setattr__(result, key, value)
    return result
