"""Sparse N1-extra int64 allocation core; no global IDs are assigned by the CLI."""
from __future__ import annotations
from . import contracts as C

def append_extra_id(molecule_id, *, historical_attempted_ids, ordinary_physical_ids,
                    registered_extra_ids, original_n):
    C.text(molecule_id)
    C.need(type(original_n) is int and original_n == 1, "EXACT_ORIGINAL_PM7_N1_REQUIRED")
    # The future CPU scanner must prove these cover ALL attempted, ordinary and
    # already registered extra IDs, including failed/nonconverged historical IDs.
    groups = (historical_attempted_ids, ordinary_physical_ids, registered_extra_ids)
    for values in groups:
        C.need(type(values) is list, "COMPLETE_ID_LIST_WITNESS_REQUIRED")
        for value in values:
            C.physical_id(value)
        C.need(len(values) == len(set(values)), "DUPLICATE_ID_WITHIN_AUTHORITY_DOMAIN")
    C.need(ordinary_physical_ids, "ACTUAL_ORDINARY_BASELINE_ID_REQUIRED")
    C.need(not (set(ordinary_physical_ids) & set(registered_extra_ids)), "EXTRA_CANNOT_REUSE_ORDINARY_PHYSICAL_ID")
    maximum = max([original_n - 1, *historical_attempted_ids, *ordinary_physical_ids, *registered_extra_ids])
    C.need(maximum < C.INT64_MAX, "EXTRA_PHYSICAL_ID_INT64_OVERFLOW")
    return {"molecule_id": molecule_id, "sprime_conf_idx": maximum + 1,
            "canonical_sprime_conf_idx": maximum + 1, "identity_namespace": C.EXTRA_NAMESPACE,
            "geometry_source": C.SOURCE, "ordinary_target_N_unchanged": 1,
            "maximum_all_previous_physical_or_attempted_ids": maximum}

def extra_base_row(supplement, assignment, alias_row):
    C.need(supplement["molecule_id"] == assignment["molecule_id"] == alias_row["molecule_id"],
           "SUPPLEMENT_ASSIGNMENT_ALIAS_MID_MUST_MATCH")
    C.need(supplement["geometry_source"] == C.SOURCE and supplement["origin"] == C.EXTRA_NAMESPACE,
           "ORIGINAL_N1_EXTRA_SOURCE_NAMESPACE_REQUIRED")
    C.need(supplement["baseline_geometry_id"] == alias_row["producer_geometry_id"] and
           supplement["baseline_geometry_sha256"] == alias_row["witness"]["geometry_sha256"],
           "SUPPLEMENT_BASELINE_ALIAS_NOT_BOUND")
    C.need(supplement["geometry_sha256"] != alias_row["witness"]["geometry_sha256"],
           "SAME_GEOMETRY_SHA_CANNOT_CREATE_SECOND_BASE")
    C.physical_id(assignment["sprime_conf_idx"])
    previous = C.physical_id(assignment["maximum_all_previous_physical_or_attempted_ids"])
    C.need(assignment["sprime_conf_idx"] == previous + 1 and previous >= alias_row["sprime_conf_idx"],
           "EXTRA_MUST_APPEND_AFTER_ALL_ATTEMPTED_ORDINARY_AND_REGISTERED_IDS")
    C.need(assignment["identity_namespace"] == C.EXTRA_NAMESPACE, "N1_NOT_ORDINARY_FILL_NAMESPACE")
    return {**supplement, **assignment, "producer_geometry_id": supplement["geometry_id"],
            "native_extra_conformer_id": C.text(supplement["native_extra_conformer_id"]),
            "baseline_geometry_id": alias_row["geometry_id"],
            "parent_geometry_id": None, "view_id": None,
            "usage_domain": "pprime_extra", "ordinary_sprime_member": False,
            "new_UFF_or_QM_calls": 0}

