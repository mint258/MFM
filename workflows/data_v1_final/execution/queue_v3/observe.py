"""Observe only a disjoint claimed phase; reuse frozen v1 startup proof math."""
import argparse
import json
import os
import pathlib
import re
import time
from ..queue_v1.shared import ROOT, load, need, on_login, pin, query, read_small, now, write_new
from ..queue_v1.queue_contract import validate_request
from .proof_v3 import create_proof as v3_create_proof
from .contract import registry_path, validate_bound_request
from .registry import (lock_file, own_directory, phase_lock_path, process_identity, verify_claims,
                       verify_disjoint)

TERMINAL = {"COMPLETED", "FAILED", "TIMEOUT", "CANCELLED", "OUT_OF_MEMORY", "NODE_FAIL",
            "PREEMPTED", "BOOT_FAIL", "DEADLINE", "REVOKED", "SPECIAL_EXIT"}


def create_owned_proof(row, registry, path):
    members = [member for member in registry["jobs"] if member["job_id"] == row.get("job_id")]
    need(len(members) == 1 and members[0] == row, "ONLY_THIS_REGISTRY_ROW_MAY_RECEIVE_PROOF")
    verify_claims(path, registry)
    req = load(row["request_reference"]["path"])
    validate_bound_request(req, read_small=read_small)
    validate_request(req, read_small=read_small,
                     script_text=read_small(req["script_reference"]["path"]).decode())
    return v3_create_proof(row)


def run(args):
    registry_reference = pin(args.registry); registry = load(args.registry)
    need(registry.get("schema") == "REGISTERED_QUEUED_CPU_JOBS_V3", "EXACT_V3_REGISTERED_PHASE_REQUIRED")
    verify_disjoint(args.registry, registry, new=False); verify_claims(args.registry, registry)
    need(not args.output.exists() and not args.output.is_symlink(), "NEW_OBSERVER_OUTPUT_REQUIRED")
    own_directory(args.output.parent)
    args.output.mkdir(mode=0o700)
    identity = process_identity(os.getpid())
    identity.update(source_reference=pin(pathlib.Path(__file__).absolute()),
        registry_reference=registry_reference, started_at=now(), max_seconds=args.max_seconds)
    write_new(args.output / "identity.json", identity)
    identity_reference = pin(args.output / "identity.json")
    start = time.monotonic(); last = None; iteration = 0
    while time.monotonic() - start < args.max_seconds:
        need(pin(args.registry) == registry_reference, "ACTIVE_REGISTRY_CHANGED")
        iteration += 1; states = []
        for row in registry["jobs"]:
            try:
                receipt = load(row["receipt_reference"]["path"]); jid = receipt["job_id"]
                need(pin(row["receipt_reference"]["path"]) == row["receipt_reference"]
                     and jid == row["job_id"], "EXACT_REGISTERED_RECEIPT_IDENTITY_REQUIRED")
                raw = query(["sacct", "-j", jid,
                    "--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS", "-n", "-P"])
                parents = [line.split("|") for line in raw.splitlines() if line.split("|")[0] == jid]
                need(len(parents) == 1, "ONE_ACTUAL_CURRENT_PARENT_REQUIRED")
                parent = parents[0]
                if parent[1].split()[0] in TERMINAL:
                    states.append({"job_id": jid, "state": parent[1], "exit_code": parent[2], "parent_raw": raw})
                else:
                    states.append(create_owned_proof(row, registry, args.registry))
            except Exception as exc:
                states.append({"job_id": row.get("job_id"), "observation_error": repr(exc), "not_terminal": True})
        compact = json.dumps(states, sort_keys=True)
        if compact != last:
            write_new(args.output / ("observation_" + str(iteration) + ".json"),
                      {"observed_at": now(), "states": states})
            last = compact
        heartbeat = {"identity_reference": identity_reference, "observed_at": now(),
            "observed_boot_monotonic": time.monotonic(), "iteration": iteration, "states": states,
            "elapsed_seconds": time.monotonic() - start,
            "all_terminal": all(str(v.get("state") or "UNKNOWN").split()[0] in TERMINAL for v in states)}
        snapshot = args.output / ("heartbeat_" + str(iteration) + ".json")
        write_new(snapshot, heartbeat)
        link = args.output / ("pointer_" + str(iteration) + ".json")
        write_new(link, {"snapshot": pin(snapshot)})
        os.replace(link, args.output / "latest.json")
        if heartbeat["all_terminal"]:
            write_new(args.output / "closure.json", {"status": "REGISTERED_PHASE_ALL_TERMINAL_NOT_GLOBAL_TASK_COMPLETE",
                "states": states, "observed_at": now()})
            return
        time.sleep(args.poll_seconds)
    write_new(args.output / "closure.json", {
        "status": "FINITE_OBSERVER_LEASE_ENDED_REOBSERVE_SAME_JOBS_NO_RESUBMISSION", "observed_at": now()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=86400)
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args(); on_login(); registry_path(args.registry)
    need(1 <= args.max_seconds <= 86400 and 5 <= args.poll_seconds <= 60, "FINITE_LOCAL_OBSERVER_LEASE_REQUIRED")
    need(args.output.parent == ROOT / "control/queue_v3_observers"
         and re.fullmatch(r"[a-z0-9_]+", args.output.name), "NEW_CANONICAL_OBSERVER_OUTPUT_REQUIRED")
    # This lock is per registry. The still-live v1 global observer is untouched.
    with lock_file(phase_lock_path(args.registry)):
        run(args)


if __name__ == "__main__":
    main()
