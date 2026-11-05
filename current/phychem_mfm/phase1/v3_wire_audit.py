"""Pickleable CPU-only source validity/reason evidence; no dense cause inference."""
from __future__ import annotations

from dataclasses import dataclass
import math

from .v3_contract import canonical_hash, require


@dataclass(frozen=True)
class MemberReasonAudit:
    field_key: str
    leaf_shape: tuple[int, ...]
    source_validity: tuple[bool, ...]
    source_codes: tuple[int, ...]
    new_codes: tuple[int, ...]
    review_codes: tuple[int, ...]
    sparse_leaf_indices: tuple[int, ...]
    sparse_leaf_codes: tuple[int, ...]

    def __post_init__(self):
        require(type(self.field_key) is str and bool(self.field_key), "Explicit source member required")
        require(type(self.leaf_shape) is tuple and all(type(n) is int and n >= 0 for n in self.leaf_shape)
                and len(self.source_validity) == math.prod(self.leaf_shape)
                and all(type(v) is bool for v in self.source_validity), "Immutable exact source leaf validity required")
        require(all(type(values) is tuple for values in (self.source_validity, self.source_codes, self.new_codes,
                self.review_codes, self.sparse_leaf_indices, self.sparse_leaf_codes)), "Immutable source reason tuples required")
        require(len(self.sparse_leaf_indices) == len(self.sparse_leaf_codes)
                and len(set(self.sparse_leaf_indices)) == len(self.sparse_leaf_indices)
                and all(type(i) is int and 0 <= i < len(self.source_validity) and not self.source_validity[i]
                        for i in self.sparse_leaf_indices), "Source sparse exceptions must address invalid leaves")
        for values in (self.source_codes, self.new_codes, self.review_codes, self.sparse_leaf_codes):
            require(all(type(v) is int and 0 < v <= 65535 for v in values), "Literal uint16 reason codes required")

    def leaf(self, index):
        require(type(index) is int and 0 <= index < len(self.source_validity), "Native source leaf index required")
        code = dict(zip(self.sparse_leaf_indices, self.sparse_leaf_codes)).get(index)
        if code is None:
            code = 0 if self.source_validity[index] else 65535
        return {"source_valid": self.source_validity[index], "leaf_exception_code": code,
                "unresolved_leaf_cause": code == 65535, "source_field_reason_set": self.source_codes,
                "new_field_reason_set": self.new_codes, "review_field_reason_set": self.review_codes,
                "field_sets_are_not_dense_leaf_causes": True}


@dataclass(frozen=True)
class FieldReasonAudit:
    target_id: str
    model_field: str
    source_shape: tuple[int, ...]
    source_validity: tuple[bool, ...]
    model_row_validity: tuple[bool, ...]
    members: tuple[MemberReasonAudit, ...]
    group_exposed: bool
    family_exposed: bool
    granularity: str = "field-set+sparse-leaf-v1"

    def __post_init__(self):
        require(self.granularity == "field-set+sparse-leaf-v1" and type(self.members) is tuple
                and all(isinstance(v, MemberReasonAudit) for v in self.members), "Declared source causal granularity required")
        require(type(self.source_shape) is tuple and type(self.source_validity) is tuple
                and all(type(n) is int and n >= 0 for n in self.source_shape)
                and len(self.source_validity) == math.prod(self.source_shape)
                and all(type(v) is bool for v in self.source_validity)
                and type(self.model_row_validity) is tuple and all(type(v) is bool for v in self.model_row_validity),
                "Source component validity is separate from model row validity")
        require(type(self.group_exposed) is bool and type(self.family_exposed) is bool,
                "Exposure is a separate literal recipe decision")


@dataclass(frozen=True)
class SampleSourceAudit:
    export_record_id: str
    geometry_id: str
    identity_sha256: str
    native_identity_sha256: str
    atom_order_sha256: str
    codebook_sha256: str
    fields: tuple[FieldReasonAudit, ...]
    authority: str = "synthetic_candidate_fixture_only_not_D3"

    def __post_init__(self):
        require(self.authority == "synthetic_candidate_fixture_only_not_D3" and type(self.fields) is tuple,
                "Candidate audit cannot claim data-line authority")
        require(all(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value) for value in
                (self.identity_sha256, self.native_identity_sha256, self.atom_order_sha256, self.codebook_sha256)),
                "Explicit identity/codebook bindings required")

    def query(self, target_id, member, leaf):
        targets = [field for field in self.fields if field.target_id == target_id]
        require(len(targets) == 1, "Unknown or ambiguous audit target")
        values = [value for value in targets[0].members if value.field_key == member]
        require(len(values) == 1, "Unknown or ambiguous source member")
        return {**values[0].leaf(leaf), "group_exposed": targets[0].group_exposed,
                "family_exposed": targets[0].family_exposed, "codebook_sha256": self.codebook_sha256,
                "identity_sha256": self.identity_sha256}


def source_identity(metadata):
    """Existing DataB shared geometry/label identity, no physical field guessed."""
    keys = ("molecule_id", "export_record_id", "geometry_source", "effective_role", "source_role", "n_atoms",
            "parent_geometry_id", "view_id")
    return {key: metadata[key] for key in keys}


def identity_sha256(metadata):
    return canonical_hash(source_identity(metadata))
