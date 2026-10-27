"""Pure molecular reducer; no representative graph, OR fingerprint or key vote."""
from __future__ import annotations

from . import contracts as C


def reduce_variants(molecule_id, effective_role, records, results):
    C.need(type(molecule_id) is str and molecule_id and effective_role in C.ROLES,
           "FINAL_COMMON_MID_ROLE_REQUIRED")
    C.need(type(records) is int and records > 0 and type(results) is list and results,
           "ALL_OBSERVED_GRAPH_VARIANTS_REQUIRED")
    reasons = []
    complete = [r for r in results if r.get("status") == "FEATURES_DERIVED"]
    if len(complete) != len(results):
        reasons.append("ONE_OR_MORE_SOURCE_GRAPH_VARIANTS_UNRESOLVED")
    identities, feature_values = set(), set()
    for result in complete:
        f = result.get("features")
        C.need(type(f) is dict, "FROZEN_FEATURE_RESULT_REQUIRED")
        if not (C.valid_full_key(f.get("full_key")) and type(f.get("isomeric_smiles")) is str
                and f["isomeric_smiles"]):
            reasons.append("DERIVED_GRAPH_OR_FULL_KEY_UNRESOLVED")
            continue
        identities.add((f["isomeric_smiles"], f["full_key"]))
        # Input spelling, task ordinal and absent CID are provenance, not graph
        # differences. All actual molecular feature values must still agree.
        feature_values.add(C.canonical({k: v for k, v in f.items()
                                        if k not in ("source_smiles", "ordinal", "cid")}))
    if len(identities) > 1:
        reasons.append("MULTIPLE_LEGITIMATE_CANONICAL_GRAPHS_OR_FULL_KEYS")
    if len(feature_values) > 1 and len(identities) <= 1:
        reasons.append("SAME_GRAPH_FEATURE_VALUES_DISAGREE")
    if not identities:
        reasons.append("NO_COMPLETE_CANONICAL_GRAPH")
    projection = None
    if not reasons:
        f = complete[0]["features"]
        projection = {"molecule_id": molecule_id, "full_key": f["full_key"],
                      "ecfp4_2048_hex": f["ecfp4_2048_hex"],
                      "generic_murcko": f["generic_murcko"],
                      "generic_ring_systems": f["generic_ring_systems"]}
        validate_projection(projection)
    return {"molecule_id": molecule_id, "effective_role": effective_role, "cid": None,
            "native_records": records, "graph_variant_results": results,
            "status": "UNIQUE_GRAPH_PROJECTION_CANDIDATE" if projection is not None else "HOLD",
            "hold_reasons": sorted(set(reasons)), "strict5_projection": projection,
            "historical_keys_or_accepted_differences_used_as_exclusion": False,
            "representative_graph_chosen": False, "fingerprints_merged": False,
            "production_or_pool_release_authorized": False}


def validate_projection(row):
    C.need(type(row) is dict and set(row) == C.PROJECTION_FIELDS, "EXACT_OLD_CONSUMER_FIVE_FIELDS_REQUIRED")
    C.need(type(row["molecule_id"]) is str and row["molecule_id"] and
           C.valid_full_key(row["full_key"]), "NATIVE_MID_AND_FULL_KEY_REQUIRED")
    value = row["ecfp4_2048_hex"]
    C.need(type(value) is str and len(value) == 512 and
           all(c in "0123456789abcdef" for c in value), "EXACT_2048_BINARY_FINGERPRINT_REQUIRED")
    C.need(type(row["generic_murcko"]) is str and
           type(row["generic_ring_systems"]) is list and
           all(type(s) is str for s in row["generic_ring_systems"]),
           "ORIGINAL_SCAFFOLD_AND_RING_VALUES_REQUIRED")
    # Empty acyclic Murcko is retained as "". Duplicate native ring-system
    # entries are retained; the unchanged consumer counts set-presence per MID.
    return row

