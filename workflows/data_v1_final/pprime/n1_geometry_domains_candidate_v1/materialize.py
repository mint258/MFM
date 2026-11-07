"""Small-metadata candidate CLI; no reader invocation, actual IDs or READY."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from . import contracts as C

PARENTS = (
    "final_common_reference", "full_sprime_completion_reference", "whole_roles_reference",
    "ordinary_physical_map_reference", "ordinary_orders_reference",
    "n1_source_terminal_close_reference", "n1_source_accounting_reference",
    "shared_n1_once_census_reference", "canonical_graph_authority_reference",
    "d1_condition_semantics_reference", "d5_diagnostic_authority_reference",
    "late_source_validator_authority_reference",
)

def small_reference(path):
    p = Path(path); s = p.lstat()
    C.need(stat.S_ISREG(s.st_mode) and not p.is_symlink() and 0 < s.st_size <= 2 << 20,
           "SMALL_SOURCE_OR_METADATA_ONLY_BEFORE_OPEN")
    with p.open("rb") as stream:
        first = os.fstat(stream.fileno()); raw = stream.read((2 << 20) + 1); after = os.fstat(stream.fileno())
    stamp = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns)
    C.need(stamp(s) == stamp(first) == stamp(after) == stamp(p.lstat()) and len(raw) == s.st_size,
           "SMALL_METADATA_FRAME_CHANGED")
    return {"path": str(p.absolute()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}, raw

def small_load(ref):
    C.reference(ref, small=True)
    C.need(Path(ref["path"]).lstat().st_size == ref["bytes"], "SMALL_EXPECTED_METADATA_SIZE_REQUIRED")
    observed, raw = small_reference(ref["path"])
    C.need((observed["bytes"], observed["sha256"]) == (ref["bytes"], ref["sha256"]), "ACTUAL_SMALL_PIN_MISMATCH")
    return json.loads(raw)

def candidate(request):
    C.need(type(request) is dict and request.get("schema") == C.REQUEST and
           request.get("requested_scope") == "FINAL_COMMON_N1_INDEPENDENT_PPRIME_DOMAIN_ONLY", "EXACT_CANDIDATE_SCOPE_REQUIRED")
    evidence = C.reference(request["source_evidence_reference"], small=True)
    value = small_load(evidence)
    C.need(value["schema"] == "N1_GEOMETRY_DOMAINS_SOURCE_EVIDENCE_V1" and
           value["source_only_not_execution_authority"] is True, "ACTUAL_SOURCE_SEMANTICS_EVIDENCE_REQUIRED")
    parents, missing, data = {}, [], []
    for name in PARENTS:
        ref = request.get(name)
        if ref is None:
            missing.append(name)
        else:
            parents[name] = {"reference": C.reference(ref, small=True), "small_metadata": small_load(ref)}
    common = parents.get("final_common_reference", {}).get("small_metadata")
    if common is not None:
        C.need(common.get("schema") == common.get("status") == "COMMON_POPULATION_V1_FROZEN" and
               common.get("pilot_only") is False, "TRUE_FINAL_COMMON_ONLY_NOT_SOURCE_ROSTER")
        C.need(type(common.get("membership_tables")) is list and len(common["membership_tables"]) == 16,
               "ALL_FINAL_COMMON_MEMBERSHIP_PART_LOCATORS_REQUIRED")
        data.extend(C.data_reference(ref) for ref in common["membership_tables"])
        C.need(type(common.get("physical_geometry_tables")) is list and common["physical_geometry_tables"],
               "ACTUAL_ORDINARY_PHYSICAL_MAP_LOCATORS_REQUIRED")
        data.extend(C.data_reference(ref) for ref in common["physical_geometry_tables"])
    for ref in request.get("additional_closed_DATA_locators", []):
        data.append(C.data_reference(ref))
    missing += ["FRESH_RESOURCE_AND_FULL_ARGV_SOURCE_ACCOUNTING_PORT_NOT_IMPLEMENTED",
                "ACTUAL_CPU_ALL_FINAL_COMMON_N1_CENSUS_AND_ANTI_JOIN_NOT_OBSERVED",
                "ACTUAL_BASELINE_ALIAS_WITNESSES_AND_ALL_ATTEMPTED_ID_MAXIMA_NOT_OBSERVED",
                "ALL_SELECTED_PACKETS_TASK_CLAIM_START_TERMINAL_AND_F64_SHA_RECONCILIATION_NOT_OBSERVED",
                "D1_CONDITION_DOMAIN_AND_D5_TRAINING_MEMBERSHIP_ACCEPTANCE_NOT_RELEASED",
                "NONZERO_LATE_BASELINE_REQUIRES_INDEPENDENT_REAL_SOURCE_VALIDATOR_NO_ZERO_RELABEL"]
    return {"schema": C.SCHEMA, "status": "NONEXECUTABLE_CANDIDATE", "scope_key": C.KEY,
            "execution_implemented": False, "source_evidence_reference": evidence,
            "actual_small_parent_metadata": parents, "DATA_locators_not_opened": data,
            "missing_or_future_CPU_requirements": missing,
            "geometry_source": C.SOURCE, "extra_identity_namespace": C.EXTRA_NAMESPACE,
            "ordinary_sprime_target_N_changed": False, "baseline_duplicated": False,
            "extra_parent_geometry_id": None, "extra_view_id": None,
            "expanded_view_marker_used_as_perturbation_view": False,
            "usage_domains": list(C.DOMAINS), "D5_eligibility_uses_ordinary_counts_only": True,
            "physical_extra_ids_assigned": False, "source_counts_4631_233_claimed_as_final_census": False,
            "extra_ID_rule": "strict append after max(all historical attempted, ordinary physical, registered extra), nonnegative int64 no overflow",
            "order_identity": {"seed": C.ORDER_SEED, "source_literal": C.SOURCE, "physical_int64": True,
                               "original_stable_key_and_order_function_objects": True,
                               "original_fixed_map_proper_Kabsch_object_required": True,
                               "producer_native_orders_preserved_as_provenance": True},
            "baseline_QM_namespace": "pprime-twelve-once-v1",
            "original_N1_generation_once_namespace_retained": True,
            "new_UFF_calls_authorized": 0, "new_QM_calls_authorized": 0,
            "old15covarianceFAIL_2000_full_HOLD_preserved": True,
            "scientific_quality_or_pool_or_training_release_authorized": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--output-directory", type=Path, required=True)
    a = p.parse_args()
    request_ref, raw = small_reference(a.request)
    value = candidate(json.loads(raw)); value["request_reference"] = request_ref
    value["candidate_python_sources"] = [small_reference(path)[0] for path in sorted(Path(__file__).parent.glob("*.py"))]
    body = C.canonical(value) + b"\n"
    C.need(len(body) <= 2 << 20, "SMALL_METADATA_OUTPUT_ONLY")
    a.output_directory.mkdir(parents=True, exist_ok=False)
    with (a.output_directory / "candidate.json").open("xb") as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    print(C.canonical({"status": "NONEXECUTABLE_CANDIDATE", "reference": small_reference(a.output_directory / "candidate.json")[0]}).decode())

if __name__ == "__main__":
    main()

