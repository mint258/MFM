"""Exact finite raw-row cost scope and actual-inventory metadata authority."""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as execution


SCOPE = "sb5_pubchem_raw_uniform_cost_10000_v1"
COUNT, LONGEST, SEED = 10000, 16, 20261026
CAP, WALL, WORKERS, PENDING = 2 * 1024 ** 3, 14400, 16, 32
CONTAINER_CAP = 1024 ** 3
INDEX_CAP = 4096


def parameters(inventory_pin, index_pin, owned_root, n, cost_decision_ref):
    return {"uniform_raw_rows": COUNT, "longest_diagnostic_rows": LONGEST, "seed": SEED,
        "sampling": "sorted(random.Random(seed).sample(range(1,N+1),10000))", "population_N": n,
        "without_replacement": True, "longest_excluded_from_uniform_mean": True,
        "independent_original_X_audit": True, "dispatcher_already_includes_X_and_parse": True,
        "actual_worker_processes": WORKERS, "max_pending_tasks": PENDING, "container_budget_bytes": CONTAINER_CAP,
        "RDKit": "2025.09.5", "heavy_atom_upper_bound": None, "isotope_policy": "preserve",
        "stereo_policy": "preserve_source", "guide_filtered_dedup_1M_reference": False,
        "cost_decision_reference": cost_decision_ref, "cost_overrun_action": "REPORT_AND_CONTINUE",
        "allocation_ceiling_is_not_a_profile_forecast": True,
        "derived_part_authority": {"actual_inventory_receipt": inventory_pin, "source_index_reference": index_pin,
            "owned_output_root": owned_root, "max_index_entry_bytes": INDEX_CAP,
            "canonical_filename": "source_{index:06d}.tsv", "index_sequence_starts_zero": True,
            "all_ordinal_row_byte_SHA_UID_no_symlink_fstat_checks_required": True,
            "extra_directory_scan_or_guessed_reference_allowed": False},
        "apply_pool_repair": False, "decontamination": False, "novelty": False,
        "UFF_QM_or_training": False, "full_source_screening_acceptance": False}


def inventory_metadata(receipt):
    shared.need(receipt.get("schema") == "SB5_PUBCHEM_RAW_INVENTORY_RECEIPT_V2" and
        receipt.get("job_id") == "4521093" and receipt.get("node") == "compute-0-13" and receipt.get("uid") == 1278 and
        receipt.get("status") == "RAW_FULL_EOF_INVENTORY_COMPLETE_NO_CHEMICAL_SCREENING" and
        receipt.get("raw_complete_SHA_verified") is True and receipt.get("gzip_EOF_CRC_revalidated") is True and
        receipt.get("chemical_screening_performed") is False and receipt.get("full_source_pool_release_authorized") is False,
        "ACTUAL_COMPLETE_INVENTORY_V2_REQUIRED")
    counts, index = receipt["counts"], receipt["source_index"]
    shared.need(type(counts["records"]) is int and counts["records"] == 124857440 and counts["cid_records"] == counts["records"] and
        type(index["part_count"]) is int and index["part_count"] == 500 and
        counts["uncompressed_bytes"] > 0 and 0 < counts["maximum_source_line_bytes"] <= counts["uncompressed_bytes"],
        "ACTUAL_INVENTORY_COUNTS_NOT_A_GUESSED_N")
    path = PurePosixPath(index["reference"]["path"])
    shared.need(path.is_absolute() and ".." not in path.parts and path.name == "source_index.jsonl" and
        str(path.parent).startswith(str(execution.ARTIFACTS) + "/raw/"), "EXACT_OWNED_INVENTORY_INDEX_LOCATOR")
    return counts["records"], index["reference"], str(path.parent)


def validate_actual_parent(receipt, account_path):
    # Reuse the registered metadata-only accounting validator, not a new scheduler query.
    from ..materialize_full_sources_v2 import parent_from_account
    parent, raw_sacct = parent_from_account(account_path, receipt["job_id"])
    shared.need(parent["NodeList"] == receipt["node"] and receipt["uid"] == 1278,
                "EXACT_CURRENT_INVENTORY_PARENT_NODE_UID")
    return parent, raw_sacct


def verify_compatible_source(plan):
    from .. import features_legacy_compatible_v2 as compatible
    from .. import screen
    actual = compatible.source_scope_proof()
    prior = shared.load(plan["anchors"]["compat_receipt"]["path"])
    shared.need(prior["job_id"] == "4520597" and prior["rdkit"] == "2025.09.5" and actual == prior["source_scope_proof"] and
        compatible.chemical_flags is screen.chemical_flags and compatible.wp5_key is screen.wp5_key and
        compatible.rdkit_modules is screen.rdkit_modules, "EXACT_ACTUAL597_COMPOSITIONAL_SOURCE_PROOF_REQUIRED")
    return actual


def authority(plan, proof):
    declared = {r["path"]: r for r in proof["request"]["source_references"]}
    for ref in (plan["inventory_receipt"], plan["inventory_accounting"], plan["raw_producer_receipt"]):
        execution.verify_small(ref, declared)
    receipt = shared.load(plan["inventory_receipt"]["path"])
    n, index_ref, owned_root = inventory_metadata(receipt)
    parent, raw_sacct = validate_actual_parent(receipt, plan["inventory_accounting"]["path"])
    shared.need(parent == plan["inventory_actual_parent"] and raw_sacct in plan["authority_references"],
                "CURRENT_ACTUAL_INVENTORY_PARENT_AUTHORITY_DIFFERS")
    raw = shared.load(plan["raw_producer_receipt"]["path"])
    shared.need(raw["job_id"] == "4520348" and raw["file"] == receipt["raw_source"] == plan["raw_file"] and
        raw["gzip"]["gzip_read_to_eof_crc_validated"] is True and
        raw["gzip"]["uncompressed_bytes_read"] == receipt["counts"]["uncompressed_bytes"] and
        plan["source_index"] == index_ref and plan["inventory_owned_root"] == owned_root and plan["population_N"] == n,
        "EXACT_RAW348_AND_ACTUAL_INVENTORY_BINDING")
    shared.need(plan["scope_parameters"] == parameters(plan["inventory_receipt"], index_ref, owned_root, n, plan["cost_decision_reference"]) and
        proof["request"]["data_references"] == [plan["raw_file"], index_ref], "EXPLICIT_DERIVED_INDEX_AUTHORITY_REQUIRED")
    return receipt
