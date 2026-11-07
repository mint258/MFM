"""One baseline, one explicit producer-to-final physical alias; no duplication."""
from __future__ import annotations
from . import contracts as C

WITNESS_FIELDS = {"molecule_id", "sprime_conf_idx", "full_original_row_sha256",
                  "geometry_sha256", "atom_order_sha256", "seed", "source_locator"}

def checked_witness(value):
    C.need(type(value) is dict and WITNESS_FIELDS <= set(value), "ACTUAL_BASELINE_WITNESS_REQUIRED")
    C.text(value["molecule_id"]); C.physical_id(value["sprime_conf_idx"])
    C.physical_id(value["seed"])
    for key in ("full_original_row_sha256", "geometry_sha256", "atom_order_sha256"):
        C.sha(value[key])  # NULL geometry_sha in old map is never a witness.
    loc = value["source_locator"]
    C.need(type(loc) is dict and set(loc) == {"reference", "source_format", "source_row_index",
                                            "source_member", "source_record_id"}, "EXACT_SOURCE_ROW_LOCATOR_REQUIRED")
    C.data_reference(loc["reference"]); C.text(loc["source_format"]); C.text(loc["source_record_id"])
    C.need(type(loc["source_row_index"]) is int and loc["source_row_index"] >= 0,
           "ACTUAL_SOURCE_ROW_INDEX_REQUIRED")
    C.need(loc["source_member"] is None or type(loc["source_member"]) is str,
           "EXPLICIT_SOURCE_MEMBER_OR_NULL_REQUIRED")
    return {k: value[k] for k in WITNESS_FIELDS}

def baseline_alias(producer, ordinary):
    left, right = checked_witness(producer), checked_witness(ordinary)
    C.need(left == right, "BASELINE_MID_INDEX_ROW_SHA_GEOMETRY_ATOM_SEED_LOCATOR_MUST_MATCH")
    origin, final = C.text(producer["producer_geometry_id"]), C.text(ordinary["geometry_id"])
    return {"molecule_id": left["molecule_id"], "producer_geometry_id": origin,
            "geometry_id": final, "sprime_conf_idx": left["sprime_conf_idx"],
            "witness": right, "baseline_storage_copies_added": 0,
            "producer_ID_is_final_ID": origin == final}

def require_bijection(rows):
    producer, physical = {}, {}
    for row in rows:
        a, b = row["producer_geometry_id"], row["geometry_id"]
        C.need(a not in producer and b not in physical, "BASELINE_ALIAS_MUST_BE_ONE_TO_ONE")
        producer[a], physical[b] = b, a
    return {"aliases": len(rows), "baseline_storage_copies_added": 0}

