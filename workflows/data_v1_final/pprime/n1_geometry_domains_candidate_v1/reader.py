"""Bounded read-only N1 supplement reader library, not a resource/admission port.

Future actual CPU entry must run fixtures/admission before calling this module.
It reads no DATA at import, calls no worker_init, and never changes a once ledger.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
from . import contracts as C

def _stamp(s):
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_uid

def read_packet(reference, expected_task, *, origin_owner, current_uid, current_endpoint,
                actual_terminal_closure_reference, relocation_reference=None):
    from workflows.data_v1_final.conformers.n1_pprime2_source_full_v1 import contract as original
    from workflows.data_v1_final.pprime.geometry import geometry_hash
    ref = C.data_reference(reference); origin = C.owner(origin_owner)
    C.text(current_endpoint)
    C.reference(actual_terminal_closure_reference, small=True)
    C.need(type(current_uid) is int and current_uid > 0 and ref["bytes"] <= C.PACKET_CAP,
           "BOUNDED_CURRENT_OWNED_PACKET_REQUIRED")
    if current_uid != origin["uid"] or current_endpoint != origin["endpoint"]:
        C.need(relocation_reference is not None, "CROSS_UID_REQUIRES_EXPLICIT_ACTUAL_RELOCATION_AUTHORITY")
    if relocation_reference is not None:
        C.reference(relocation_reference, small=True)
    # This reuses the old pure task validator only for its actual old schema.
    # Its idx==0 gate remains intact; nonzero late baselines need a new source
    # validator/authority, never a rewritten zero or this old-source protocol.
    original.validate_task(expected_task, expected_task["authority_references"]["source_population_authority"])
    path = Path(ref["path"])
    C.need(not any(p.is_symlink() for p in (path, *path.parents)), "NO_SYMLINK_PACKET_PATH")
    before = path.lstat()
    C.need(stat.S_ISREG(before.st_mode) and before.st_uid == current_uid and before.st_size == ref["bytes"],
           "EXACT_CURRENT_PACKET_FRAME_REQUIRED")
    with path.open("rb") as raw:
        first = os.fstat(raw.fileno()); digest = hashlib.sha256()
        while chunk := raw.read(1 << 20):
            digest.update(chunk)
        C.need(digest.hexdigest() == ref["sha256"], "PACKET_WHOLE_COMPRESSED_SHA_MISMATCH")
        raw.seek(0)
        with gzip.GzipFile(fileobj=raw, mode="rb") as stream:
            decoded = stream.read(C.PACKET_CAP + 1)
            C.need(len(decoded) <= C.PACKET_CAP and stream.read(1) == b"", "FULL_GZIP_EOF_CRC_AND_DECODE_BOUND_REQUIRED")
        after = os.fstat(raw.fileno())
    C.need(_stamp(before) == _stamp(first) == _stamp(after) == _stamp(path.lstat()), "PACKET_CHANGED_DURING_SAME_FD_READ")
    def no_constant(value):
        raise C.ContractError("NONSTANDARD_JSON_NUMBER:" + value)
    saved = json.loads(decoded, parse_constant=no_constant)
    mid = expected_task["meta"]["molecule_id"]
    C.need(saved["schema"] == "N1_PPRIME2_PILOT_GENERATION_PACKET_V2" and
           saved["task_key"] == expected_task["task_key"] == original.task_key(mid) and
           saved["summary"]["molecule_id"] == mid and saved["source_population_authority_reference"] ==
           expected_task["authority_references"]["source_population_authority"], "EXACT_CLOSED_SOURCE_TASK_IDENTITY_REQUIRED")
    C.need(saved["common"] is False and saved["pilot_membership"] is False and
           saved["production_membership"] is False and saved["final_common_reference"] is None and
           saved["original_PM7_pointer_count_changed"] is False and
           saved["original_Sprime_count_changed"] is False, "SOURCE_PACKET_CANNOT_RELEASE_COMMON_OR_CHANGE_N")
    runtime = saved["runtime"]
    C.need(runtime["uid"] == origin["uid"] and runtime["job_id"] == origin["job_id"] and
           type(runtime["pid"]) is int and runtime["pid"] > 0 and
           type(runtime["start_ticks"]) is int and runtime["start_ticks"] > 0 and
           type(runtime["boot_id"]) is str and runtime["boot_id"], "ORIGIN_OWNER_ACTUAL_WORKER_BINDING_REQUIRED")
    old, baseline = saved["baseline_original_row"], saved["baseline_identity"]
    result = {"packet": saved, "packet_reference": ref, "origin_owner": origin,
              "actual_terminal_closure_reference": actual_terminal_closure_reference,
              "relocation_reference": relocation_reference, "new_UFF_calls": 0, "new_QM_calls": 0,
              "physical_extra_id_assigned": False, "source_only_not_final_Common": True,
              "expanded_view_collection_marker_is_not_a_physical_view": True}
    if baseline is None:
        return {**result, "status": "UNRESOLVED_SOURCE_BASELINE_NO_EXTRA_ACCEPTANCE"}
    numbers = expected_task["source_atomic_numbers"]
    atom_sha = hashlib.sha256(struct.pack("<" + "q" * len(numbers), *numbers)).hexdigest()
    C.need(old == expected_task["existing_conformers"][0] and C.value_sha(old) ==
           expected_task["baseline_row_sha256"] == baseline["full_original_row_sha256"], "COMPLETE_BASELINE_ROW_SHA_CHANGED")
    C.need(baseline["geometry_id"] == expected_task["baseline_geometry_id"] and
           baseline["original_sprime_conf_idx"] == old["sprime_conf_idx"] == 0 and
           old["atom_order_sha256"] == atom_sha and
           geometry_hash(numbers, old["coordinates"]) == baseline["geometry_sha256"], "BASELINE_F64_ATOM_OR_PHYSICAL_ID_CHANGED")
    for event in saved["candidate_optimizer_events"]:
        if event["finite"]:
            C.need(geometry_hash(numbers, event["coordinates"]) == event["geometry_sha256"], "CANDIDATE_F64_SHA_CHANGED")
    extra = saved["supplement"]
    if extra is None:
        return {**result, "status": "UNRESOLVED_SOURCE_SECOND_GEOMETRY_NO_RETRY"}
    C.need(extra["molecule_id"] == mid and extra["status"] == "SUCCESS" and extra["converged"] is True and
           extra["geometry_source"] == C.SOURCE and extra["origin"] == C.EXTRA_NAMESPACE and
           extra["source_record_id"] == expected_task["records"][0]["record_id"] and
           extra["atomic_numbers"] == numbers and extra["atom_order_sha256"] == atom_sha and
           geometry_hash(numbers, extra["coordinates"]) == extra["geometry_sha256"] != baseline["geometry_sha256"],
           "EXACT_REAL_SECOND_F64_GRAPH_ANCHOR_AND_SOURCE_IDENTITY_REQUIRED")
    C.need(extra["seed"] == original.proposed_seed(mid) != old["seed"] and
           extra["native_extra_conformer_id"] == f"n1p2:{extra['seed']}:{extra['candidate_id']}" and
           extra["baseline_geometry_id"] == baseline["geometry_id"] and
           extra["baseline_geometry_sha256"] == baseline["geometry_sha256"], "EXTRA_NATIVE_ID_SEED_BASELINE_CHANGED")
    events = [e for e in saved["candidate_optimizer_events"] if e["candidate_key"] == extra["optimizer_event_key"]]
    C.need(len(events) == 1, "ONE_RETAINED_NATIVE_OPTIMIZER_EVENT_FOR_EXTRA_REQUIRED")
    event = events[0]
    C.need(event["optimizer_called"] is True and event["optimization_finished"] is True and
           event["geometry_readback_finished"] is True and event["finite"] is True and
           event["stereo_valid"] is True and event["optimizer_code"] == 0 and
           event["candidate_id"] == extra["candidate_id"] and event["seed"] == extra["seed"] and
           event["geometry_sha256"] == extra["geometry_sha256"] and event["coordinates"] == extra["coordinates"] and
           event["energy"] == extra["uff_energy_kcal_mol"], "EXTRA_MUST_MATCH_ACTUAL_RETAINED_FINISHED_NATIVE_EVENT")
    return {**result, "status": "SOURCE_SUPPLEMENT_READBACK_CANDIDATE_REQUIRES_FINAL_ALIAS_AND_AUTHORITY"}

