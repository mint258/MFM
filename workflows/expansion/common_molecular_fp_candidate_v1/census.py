"""Bounded pure census over ordered unique MIDs, never physical-conformer scores."""
from __future__ import annotations

from collections import Counter
import hashlib
from . import contracts as C


class Census:
    def __init__(self):
        self.previous = None
        self.rows = 0
        self.roles = Counter()
        self.native_records = Counter()
        self.digest = hashlib.sha256()

    def add(self, molecule_id, effective_role, native_records):
        C.need(type(molecule_id) is str and molecule_id and effective_role in C.ROLES and
               type(native_records) is int and native_records > 0, "EXACT_NATIVE_MOLECULAR_CENSUS_REQUIRED")
        C.need(self.previous is None or molecule_id > self.previous,
               "SORTED_UNIQUE_MID_REQUIRED_NO_CONFORMER_DOUBLE_COUNT")
        self.previous = molecule_id
        for value in (molecule_id, effective_role):
            raw = value.encode("utf-8")
            self.digest.update(len(raw).to_bytes(8, "big"))
            self.digest.update(raw)
        self.rows += 1
        self.roles[effective_role] += 1
        self.native_records[effective_role] += native_records

    def result(self):
        return {"molecules": self.rows,
                "molecules_by_role": {r: self.roles[r] for r in C.ROLES},
                "native_records_by_role": {r: self.native_records[r] for r in C.ROLES},
                "sorted_length_prefixed_MID_role_sha256": self.digest.hexdigest()}


def require_same_membership(expected, observed):
    C.need(expected == observed, "EXACT_COMMON_MID_ROLE_AND_RECORD_CENSUS_NOT_CONSERVED")

