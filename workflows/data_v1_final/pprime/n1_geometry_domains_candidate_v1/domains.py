"""Separate physical catalog, ordinary training, P-prime compute and training."""
from __future__ import annotations
from . import contracts as C

def diagnostic_eligible(original_pm7_base_count, ordinary_uff_base_count):
    C.need(type(original_pm7_base_count) is int and original_pm7_base_count >= 0 and
           type(ordinary_uff_base_count) is int and ordinary_uff_base_count >= 0, "ORDINARY_BASE_COUNTS_REQUIRED")
    return original_pm7_base_count >= 2 and ordinary_uff_base_count >= 2

def domain_memberships(ordinary_catalog_ids, ordinary_training_ids, extra_ids,
                       expanded_fixed_random, diagnostic_excluded_ids):
    for values in (ordinary_catalog_ids, ordinary_training_ids, extra_ids, expanded_fixed_random):
        C.need(type(values) is list and all(type(v) is str and v for v in values) and
               len(values) == len(set(values)), "UNIQUE_EXPLICIT_GEOMETRY_ID_LIST_REQUIRED")
    ordinary, extra = set(ordinary_catalog_ids), set(extra_ids)
    C.need(ordinary and not ordinary & extra and set(ordinary_training_ids) <= ordinary,
           "ORDINARY_BASELINE_SINGLE_STORAGE_AND_TRAINING_SUBSET_REQUIRED")
    C.need(set(expanded_fixed_random) == ordinary | extra and len(expanded_fixed_random) >= 2,
           "EXPANDED_ORDER_MUST_COVER_EACH_ACTUAL_BASE_EXACTLY_ONCE")
    # A missing D1/D5 condition/diagnostic authority cannot be guessed from an
    # empty list. None means the third domain is still explicitly unresolved.
    training = None
    if diagnostic_excluded_ids is not None:
        C.need(type(diagnostic_excluded_ids) is list and
               len(diagnostic_excluded_ids) == len(set(diagnostic_excluded_ids)) and
               set(diagnostic_excluded_ids) <= ordinary | extra, "ACTUAL_DIAGNOSTIC_BASE_EXCLUSIONS_REQUIRED")
        training = [gid for gid in expanded_fixed_random if gid not in set(diagnostic_excluded_ids)]
    return {"ordinary_sprime_training": list(ordinary_training_ids),
            "pprime_compute_first2": expanded_fixed_random[:2],
            "pprime_training_after_diagnostic": training,
            "ordinary_geometry_count_increased_by_extra": False,
            "extra_used_for_ordinary_D5_diagnostic_eligibility": False,
            "training_condition_contract_accepted": False,
            "physical_catalog_baseline_occurrences": 1,
            "production_or_training_release_authorized": False}

