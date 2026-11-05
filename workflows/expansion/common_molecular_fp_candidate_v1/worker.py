"""Thin candidate science seam. No CLI, allocation, body reader or pool release.

A future independently reviewed CPU port must validate final parents, graph
selection, source pins, fixtures and resources before calling these functions.
"""
from __future__ import annotations

from . import contracts as C


def load_kernel():
    from workflows.expansion import screen, features_legacy_compatible_v2 as old
    from workflows.expansion import features_generic_candidate_v1 as generic
    C.need(old._legacy_features is screen.features and
           old.chemical_flags is screen.chemical_flags and
           old.rdkit_modules is screen.rdkit_modules and
           old._fallback_features is generic.features_candidate,
           "FROZEN_FEATURE_FUNCTION_OBJECTS_REQUIRED")
    # This is the existing proof, not a rewritten fallback or feature recipe.
    proof = old.source_scope_proof()
    return old.features_candidate, proof


def derive(selected, ordinal, kernel):
    C.need(type(ordinal) is int and ordinal >= 0, "EXPLICIT_GRAPH_TASK_ORDINAL_REQUIRED")
    if selected["status"] != "SOURCE_GRAPH_PRESENT":
        return {"variant_id": selected["variant_id"], "status": "SOURCE_GRAPH_UNAVAILABLE",
                "features": None, "error": None, "chemical_exclusion_applied": False}
    # kernel must be the function returned by load_kernel(), never a replacement
    # graph parser, neutralizer, descriptor implementation or fallback policy.
    from workflows.expansion import features_legacy_compatible_v2 as old
    C.need(kernel is old.features_candidate, "EXACT_FROZEN_FEATURE_DISPATCH_REQUIRED")
    try:
        value = kernel(None, selected["source_smiles_for_original_template"], ordinal)
        status = "FEATURES_DERIVED" if value.get("reasons") == [] else "FEATURE_VALUES_UNRESOLVED"
        return {"variant_id": selected["variant_id"], "status": status, "features": value,
                "error": None, "chemical_exclusion_applied": False}
    except Exception as exc:
        return {"variant_id": selected["variant_id"], "status": "FEATURE_COMPUTE_UNRESOLVED",
                "features": None, "error": {"type": type(exc).__name__, "message": str(exc)},
                "chemical_exclusion_applied": False}

