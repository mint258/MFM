"""Original graph entrance, proven from the field creator rather than its name.

This is a candidate semantic choice awaiting an independent Root review. The
original creator parses data.smiles.strip() as template; its canonical_smiles
explicitly disables isomeric output. Reidentified geometry is a separate axis.
"""
from __future__ import annotations

import hashlib
from . import contracts as C

SELECTOR = "ORIGINAL_CREATOR_SMILES_STRIP_TEMPLATE_V1"


def identity_row(row):
    C.need(type(row) is dict and set(row) <= C.IDENTITY_COLUMNS,
           "IDENTITY_ALLOWLIST_ONLY_NO_TARGET_OR_LABEL_COLUMNS")
    C.need(set(C.REQUIRED_IDENTITY_COLUMNS) <= set(row), "ACTUAL_FORMAL_IDENTITY_COLUMNS_REQUIRED")
    C.need(type(row["molecule_id"]) is str and row["molecule_id"] and
           type(row["record_id"]) is str and row["record_id"], "ORIGINAL_MID_RECORD_ID_REQUIRED")
    # Preserve every supplied historical key and accepted-difference flag. They
    # are evidence, not a new equality-to-derived-key acceptance condition.
    return dict(row)


def select(row):
    source = identity_row(row)
    raw = source["smiles"]
    text = raw.strip() if type(raw) is str else None
    status = "SOURCE_GRAPH_PRESENT" if text else "SOURCE_GRAPH_UNAVAILABLE"
    return {"selector": SELECTOR, "status": status, "source_smiles_raw": raw,
            "source_smiles_for_original_template": text,
            "variant_id": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
            "cid": None, "original_identity": source,
            "canonical_smiles_is_nonisomeric_creator_output": True,
            "geometry_reidentified_graph_selected": False,
            "historical_key_equality_is_not_a_new_gate": True}

