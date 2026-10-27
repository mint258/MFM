"""Pure final-population anti-join and original once-key reuse; no new calls."""
from __future__ import annotations
from collections import Counter
import hashlib
from pathlib import Path
from . import contracts as C
from workflows.data_v1_final.conformers.n1_pprime2_source_full_v1 import contract as original_n1

def classify_final_n1(row):
    mid = C.text(row["molecule_id"])
    key = original_n1.task_key(mid)  # Keep the existing consumed generation domain.
    base = {"molecule_id": mid, "generation_once_key": key,
            "new_generation_or_QM_authorized": False, "original_N_unchanged": True}
    if row.get("common_population") is not True or row.get("effective_role") not in ("TRAIN", "VAL") or type(row.get("S_conformers")) is not int or row["S_conformers"] != 1:
        return {**base, "classification": "OUTSIDE_TRUE_FINAL_COMMON_N1"}
    ids = row["ordinary_physical_ids"]
    C.need(type(ids) is list and len(ids) == len(set(ids)), "UNIQUE_FINAL_ORDINARY_PHYSICAL_IDS_REQUIRED")
    for idx in ids:
        C.physical_id(idx)
    once = row["original_generation_once_state"]
    C.need(once in ("ABSENT", "REGISTERED_NONTERMINAL", "CONSUMED_UNKNOWN", "CONSUMED_CLOSED", "CONFLICT"),
           "EXPLICIT_SHARED_ONCE_STATE_REQUIRED")
    C.need(row["source_task_key"] in (None, key), "NEW_NAMESPACE_CANNOT_REOPEN_CONSUMED_N1_KEY")
    if row.get("identity_conflict") is True or once == "CONFLICT":
        category = "IDENTITY_OR_ONCE_CONFLICT_HOLD"
    elif row.get("validated_closed_second_packet") is True:
        C.need(once == "CONSUMED_CLOSED" and row["source_task_key"] == key, "CLOSED_PACKET_REQUIRES_SAME_ACTUAL_CONSUMED_KEY")
        category = ("IMPORT_EXISTING_CLOSED_SOURCE_NO_NEW_CALL" if len(ids) == 1 and
                    row.get("closed_packet_final_baseline_alias_validated") is True else
                    "CLOSED_SOURCE_FINAL_ORDINARY_ALIAS_AUDIT_PENDING_NO_NEW_CALL")
    elif once == "REGISTERED_NONTERMINAL":
        category = "REGISTERED_NONTERMINAL_NO_RETRY"
    elif once != "ABSENT":
        category = "CONSUMED_UNKNOWN_OR_NO_VALIDATED_SECOND_NO_RETRY"
    elif len(ids) >= 2:
        category = "ORDINARY_COUNT_GE2_REQUIRES_ACTUAL_DISTINCT_IDENTITY_AUDIT"
    elif len(ids) == 0:
        category = "ACTUAL_ORDINARY_BASELINE_MISSING_HOLD"
    elif row.get("baseline_input_witness_validated") is not True:
        category = "BASELINE_INPUT_OR_GRAPH_WITNESS_UNRESOLVED_HOLD"
    elif ids[0] != 0:
        category = "LATE_NONZERO_BASELINE_REQUIRES_NEW_SOURCE_VALIDATOR_AUTHORITY_NO_CALL"
    else:
        category = "LATE_UNCONSUMED_BASELINE0_REQUIRES_EXPLICIT_ROOT_AUTHORITY_NO_CALL"
    return {**base, "classification": category, "actual_ordinary_physical_ids": ids,
            "late_baseline_must_not_be_relabelled_zero": True}

def census_partition(rows):
    seen, counts, output = set(), Counter(), []
    for row in rows:
        C.need(row["molecule_id"] not in seen, "DUPLICATE_FINAL_MID_ANTI_JOIN_INPUT")
        seen.add(row["molecule_id"])
        value = classify_final_n1(row)
        counts[value["classification"]] += 1
        output.append(value)
    C.need(sum(counts.values()) == len(seen), "FINAL_COMMON_N1_PARTITION_NOT_CONSERVED")
    return {"rows": output, "counts": dict(counts), "observed_input_molecules": len(seen),
            "source_4631_or_233_used_as_final_population": False,
            "new_calls_authorized": False, "final_population_requires_actual_cpu_census": True}

def reuse_baseline_once_key(existing_pair, observed_identity, original_task_key_function,
                           original_task_key_source_reference):
    # Importing the old formal_common module changes sys.path. Its safe exact
    # module loading and full source pins belong to the future CPU port; this
    # seam requires that actual function object, never a new namespace formula.
    function = original_task_key_function
    ref = C.reference(original_task_key_source_reference, small=True)
    expected = C.source_bindings()["formal_task_key"]["origin_reference"]
    path = Path(function.__code__.co_filename)
    C.need(str(path.absolute()) == ref["path"] and (ref["bytes"], ref["sha256"]) ==
           (expected["bytes"], expected["sha256"]) and path.is_file() and not path.is_symlink() and
           path.stat().st_size == ref["bytes"] and hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"],
           "EXACT_ORIGINAL_FORMAL_TASK_KEY_SOURCE_REQUIRED")
    C.need(function.__name__ == "task_key" and function.__globals__.get("task_key") is function and
           PathSuffix(function.__code__.co_filename), "ORIGINAL_FORMAL_TASK_KEY_FUNCTION_OBJECT_REQUIRED")
    fields = ("molecule_id", "atom_order_sha256", "uff_coordinate_sha256", "protocol_sha256", "record_id")
    actual = {k: existing_pair[k] for k in fields if k != "atom_order_sha256"}
    actual["atom_order_sha256"] = existing_pair["conformer"]["atom_order_sha256"]
    for name in fields:
        C.need(actual[name] == observed_identity[name], "EXACT_BASELINE_SCIENTIFIC_TASK_INPUT_CHANGED:" + name)
    key = function(*(observed_identity[k] for k in fields))
    C.need(C.sha(existing_pair["once_key"]) == key, "BASELINE_MUST_REUSE_EXISTING_PPRIME_TWELVE_ONCE_KEY")
    return {"once_key": key, "same_original_namespace": "pprime-twelve-once-v1",
            "new_attempt_authorized": False, "baseline_QM_duplicate_allowed": False}

def PathSuffix(value):
    return type(value) is str and value.replace("\\", "/").endswith("/pprime/formal_common_v1/common_v1.py")

