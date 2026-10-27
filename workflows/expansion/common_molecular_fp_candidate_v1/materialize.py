"""Standard-library small-metadata candidate generator. Never opens DATA.

No submit/finalize/approval function exists. Even a complete candidate remains
nonexecutable until an independently reviewed future CPU port is implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from . import contracts as C


def small_load(ref):
    ref = C.reference(ref, small=True)
    p = Path(ref["path"])
    before = p.lstat()
    C.need(stat.S_ISREG(before.st_mode) and not p.is_symlink() and
           before.st_size == ref["bytes"], "CLOSED_SMALL_REGULAR_METADATA_REQUIRED")
    with p.open("rb") as stream:
        first = os.fstat(stream.fileno())
        raw = stream.read((2 << 20) + 1)
        last = os.fstat(stream.fileno())
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    C.need(stamp(before) == stamp(first) == stamp(last) == stamp(p.lstat()), "SMALL_METADATA_CHANGED")
    C.need(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"],
           "ACTUAL_SMALL_METADATA_PIN_MISMATCH")
    return json.loads(raw)


def source_ref(path):
    path = Path(path)
    before = path.lstat()
    C.need(stat.S_ISREG(before.st_mode) and not path.is_symlink() and
           0 < before.st_size <= 2 << 20, "SMALL_SOURCE_ONLY_BEFORE_OPEN")
    with path.open("rb") as stream:
        first = os.fstat(stream.fileno())
        raw = stream.read((2 << 20) + 1)
        last = os.fstat(stream.fileno())
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    C.need(stamp(before) == stamp(first) == stamp(last) == stamp(path.lstat()) and
           len(raw) == before.st_size, "SMALL_SOURCE_CHANGED")
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def candidate(request):
    C.need(type(request) is dict and request.get("schema") == C.REQUEST_SCHEMA and
           request.get("requested_scope") == "FINAL_COMMON_TRAIN_VAL_ONLY", "EXACT_CANDIDATE_REQUEST_REQUIRED")
    missing = []
    parents = {}
    for name in ("common_population_manifest_reference", "canonical_authority_receipt_reference",
                 "graph_selection_review_reference", "final_parent_accounting_reference",
                 "origin_relocation_review_reference"):
        ref = request.get(name)
        if ref is None:
            missing.append(name)
        else:
            parents[name] = {"reference": C.reference(ref, small=True), "metadata": small_load(ref)}
    evidence_ref = C.reference(request["source_evidence_reference"], small=True)
    evidence = small_load(evidence_ref)
    C.need(evidence.get("schema") == "COMMON_GRAPH_FIELD_CREATOR_SOURCE_EVIDENCE_V1" and
           evidence.get("source_only_not_execution_authority") is True, "CREATOR_SOURCE_EVIDENCE_REQUIRED")
    kernels = request.get("scientific_kernel_references", [])
    C.need(type(kernels) is list and len(kernels) == len(C.KERNEL_PATHS), "EXACT_FOUR_FROZEN_KERNEL_PINS_REQUIRED")
    for ref, suffix in zip(kernels, C.KERNEL_PATHS):
        C.reference(ref, small=True)
        C.need(ref["path"].replace("\\", "/").endswith("/" + suffix), "ORDERED_FROZEN_KERNEL_LOCATORS_REQUIRED")
        # Only small source is opened here; scientific input files never are.
        raw_ref = source_ref(ref["path"])
        C.need(raw_ref["bytes"] == ref["bytes"] and raw_ref["sha256"] == ref["sha256"], "CURRENT_KERNEL_SOURCE_PIN_MISMATCH")
    data = []
    expected = None
    common = parents.get("common_population_manifest_reference", {}).get("metadata")
    authority = parents.get("canonical_authority_receipt_reference", {}).get("metadata")
    if common is not None:
        C.need(common.get("schema") == common.get("status") == "COMMON_POPULATION_V1_FROZEN" and
               common.get("pilot_only") is False, "ONLY_TRUE_FINAL_COMMON_MANIFEST_MAY_SUPPLY_CENSUS")
        parts = common.get("membership_tables")
        C.need(type(parts) is list and len(parts) == 16, "ACTUAL_SIXTEEN_FINAL_COMMON_PARTS_REQUIRED")
        data.extend(C.data_reference(ref) for ref in parts)
        C.need(len({r["path"] for r in data}) == 16, "DUPLICATE_COMMON_PART_LOCATOR")
        roles = common.get("roles")
        C.need(type(roles) is list and len(roles) == 2 and
               {r["effective_role"] for r in roles} == set(C.ROLES), "ACTUAL_FINAL_TRAIN_VAL_ROLE_CENSUS_REQUIRED")
        for row in roles:
            C.need(type(row["molecules"]) is int and row["molecules"] > 0 and
                   type(row["pm7_records"]) is int and row["pm7_records"] > 0, "FINAL_ROLE_INTEGER_COUNTS_REQUIRED")
        expected = {"molecules": sum(r["molecules"] for r in roles),
                    "molecules_by_role": {r["effective_role"]: r["molecules"] for r in roles},
                    "native_records_by_role": {r["effective_role"]: r["pm7_records"] for r in roles},
                    "MID_set_digest": "MUST_BE_COMPUTED_FROM_ALL_16_PARTS_IN_FRESH_CPU_ALLOCATION"}
        C.need(expected["molecules"] == common["denominator_molecules"] - common["excluded_molecules"],
               "FINAL_COMMON_DENOMINATOR_CENSUS_DISAGREES")
    if authority is not None:
        C.need(authority.get("status") == "ALL_BOUND_INPUTS_SHA_VERIFIED", "ORIGINAL_FORMAL_SOURCE_AUTHORITY_REQUIRED")
        entries = [r for r in authority.get("outputs", []) if r.get("name") == "formal_population"]
        C.need(len(entries) == 1, "ONE_ORIGINAL_FORMAL_POPULATION_REQUIRED")
        data.append(C.data_reference(entries[0]["reference"]))
        if common is not None:
            C.need(common["formal_population_authority_receipt"] ==
                   parents["canonical_authority_receipt_reference"]["reference"],
                   "COMMON_CANONICAL_AUTHORITY_PARENT_DIFFERS_RELOCATION_NEEDS_SEPARATE_PORT")
    review = parents.get("graph_selection_review_reference", {}).get("metadata")
    if review is not None:
        C.need(review.get("schema") == "COMMON_SOURCE_GRAPH_SELECTION_REVIEW_V1" and
               review.get("status") == "ROOT_REVIEWED_SOURCE_ONLY" and
               review.get("selected_source_field") == "smiles" and
               review.get("original_creator_strip_then_parse") is True and
               review.get("canonical_smiles_nonisomeric_not_full_graph") is True and
               review.get("accepted_historical_key_differences_preserved") is True and
               review.get("multiple_graphs_hold_without_representative") is True,
               "EXPLICIT_ROOT_GRAPH_SEMANTICS_REVIEW_REQUIRED")
    missing += ["IMPLEMENT_FRESH_CPU_ADMISSION_AND_RESOURCE_PORT",
                "VERIFY_ACTUAL_PARENT_ACCOUNTING_AND_ORIGIN_RELOCATION_IN_PORT",
                "VERIFY_DATA_FULL_SHA_STABLE_FD_THEN_ALL_PARTS_AND_FORMAL_CENSUS_IN_CPU",
                "RUN_3_PURE_METHODS_BEFORE_DATA_THEN_VALIDATE_TRUE_GRAPH_VARIANTS",
                "IMPLEMENT_BOUNDED16_WORKERS32_PENDING_DURABLE_READBACK_AND_OUTPUT_BUDGET"]
    return {"schema": C.CANDIDATE_SCHEMA, "status": "NONEXECUTABLE_CANDIDATE",
            "execution_implemented": C.EXECUTION_IMPLEMENTED, "scope_key": C.KEY,
            "source_evidence_reference": evidence_ref, "parent_metadata": parents,
            "scientific_kernel_references": kernels, "data_references_not_opened": data,
            "expected_final_common_census_if_available": expected, "missing_or_future_port_requirements": missing,
            "fingerprint_recipe": C.FINGERPRINT_RECIPE, "legacy_projection_schema": C.PROJECTION_SCHEMA,
            "population_roles": list(C.ROLES), "one_row_per_common_molecule": True,
            "cid_when_original_authority_has_none": None,
            "source_graph_selection": "ORIGINAL_CREATOR_SMILES_STRIP_TEMPLATE_V1_PENDING_ROOT_REVIEW",
            "strict5_only_after_single_graph_per_MID": True,
            "rich_all_original_graph_key_and_QC_variants_preserved": True,
            "historical_key_equality_is_not_a_new_gate": True,
            "new_chemical_exclusion_rule": False, "downstream_values_used": False,
            "targets_present": False, "actual_statistics_or_NN_claimed": False,
            "baseline1M_authority": None, "baseline_domain": "SEPARATE_PENDING_ROOT_FREEZE",
            "orders_or_Pprime_or_identity_or_pool_release_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    a = parser.parse_args()
    request_pin = source_ref(a.request)
    result = candidate(small_load(request_pin))
    result["request_reference"] = request_pin
    result["candidate_sources"] = [source_ref(p) for p in sorted(Path(__file__).parent.glob("*.py"))]
    raw = (C.canonical(result) + "\n").encode("utf-8")
    C.need(len(raw) <= 2 << 20, "SMALL_CANDIDATE_METADATA_ONLY")
    a.output_directory.mkdir(parents=True, exist_ok=False)
    with (a.output_directory / "candidate.json").open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(C.canonical({"status": "NONEXECUTABLE_CANDIDATE", "reference": source_ref(a.output_directory / "candidate.json")}))


if __name__ == "__main__":
    main()

