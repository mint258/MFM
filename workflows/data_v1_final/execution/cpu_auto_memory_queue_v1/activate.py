"""Claim disjoint held jobs, verify a live observer, then release only these IDs."""
import argparse
import pathlib
import subprocess
import time
from .shared import (ROOT, REPO, PY, fields, load, need, on_login, pin,
                               query, read_small, now, write_new)
from .contract import validate_request
from .contract import (registry_path, validate_bound_request, job_identity,
                       validate_observer_identity)
from .registry import (lock_file, own_directory, process_identity, register_claims, verify_claims,
                       verify_disjoint)


def checked_row(name):
    rp = ROOT / "control/requests" / (name + ".json")
    sp = ROOT / "control/submissions" / (name + ".json")
    req, sub = load(rp), load(sp)
    need(sub.get("schema") == "CPU_AUTO_MEMORY_SUBMISSION_V1" and sub["request"] == req and sub["request_reference"] == pin(rp)
         and sub["sbatch_returncode"] == 0, "ACTUAL_OWNED_SUBMISSION_REQUEST_REQUIRED")
    validate_bound_request(req, read_small=read_small)
    validate_request(req, read_small=read_small,
                     script_text=read_small(req["script_reference"]["path"]).decode())
    raw = query(["scontrol", "show", "job", sub["job_id"], "--oneliner"])
    job_identity(req, raw, job_id=sub["job_id"], held=True)
    return {"job_id": sub["job_id"], "request_reference": pin(rp),
            "receipt_reference": pin(sp), "held_readback": raw}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-name", action="append", required=True)
    parser.add_argument("--registry", type=pathlib.Path, required=True)
    parser.add_argument("--observer-output", type=pathlib.Path, required=True)
    args = parser.parse_args(); on_login(); registry_path(args.registry)
    need(len(set(args.job_name)) == len(args.job_name), "UNIQUE_NEW_JOB_NAMES_REQUIRED")
    need(not args.registry.exists() and not args.observer_output.exists()
         and args.observer_output.parent == ROOT / "control/cpu_auto_memory_observers",
         "NEW_CANONICAL_PHASE_AND_OBSERVER_REQUIRED")
    registry = {"schema": "REGISTERED_CPU_AUTO_MEMORY_JOBS_V1", "observed_at": now(),
        "jobs": [checked_row(name) for name in args.job_name], "other_jobs_modified": False,
        "all_required_deliverables_still_pending": True, "claims_required": True}
    # Serialize only new registry registration. Existing v1 observation continues.
    with lock_file(ROOT / "control/cpu_auto_memory_registration.lock"):
        verify_disjoint(args.registry, registry, new=True)
        register_claims(args.registry, registry)
        write_new(args.registry, registry)
    registry_reference = pin(args.registry)
    own_directory(args.observer_output.parent)
    logpath = args.observer_output.with_suffix(".log")
    argv = [PY, "-B", "-m", "workflows.data_v1_final.execution.cpu_auto_memory_queue_v1.observe",
        "--registry", str(args.registry), "--output", str(args.observer_output),
        "--max-seconds", "86400", "--poll-seconds", "20"]
    with logpath.open("xb") as log:
        child = subprocess.Popen(argv, cwd=REPO, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 45; identity = None
    source = REPO / "workflows/data_v1_final/execution/cpu_auto_memory_queue_v1/observe.py"
    while time.monotonic() < deadline:
        need(child.poll() is None, "NEW_PHASE_OBSERVER_EXITED_NO_RELEASE")
        try:
            saved = load(args.observer_output / "identity.json")
            validate_observer_identity(saved, process_identity(child.pid), expected_argv=argv,
                registry_reference=registry_reference, source_reference=pin(source))
            pointer = load(args.observer_output / "latest.json")
            need(pin(pointer["snapshot"]["path"]) == pointer["snapshot"], "OBSERVER_HEARTBEAT_PIN_CHANGED")
            heartbeat = load(pointer["snapshot"]["path"])
            need(heartbeat["identity_reference"] == pin(args.observer_output / "identity.json")
                 and 0 <= time.monotonic() - heartbeat["observed_boot_monotonic"] <= 10,
                 "FRESH_SAME_BOOT_OBSERVER_HEARTBEAT_REQUIRED")
            identity = saved; break
        except (OSError, ValueError, KeyError):
            time.sleep(.2)
    need(identity is not None, "ACTUAL_LIVE_BOUND_OBSERVER_REQUIRED_BEFORE_RELEASE")
    releases = []
    for row in registry["jobs"]:
        need(child.poll() is None and pin(args.registry) == registry_reference,
             "EXACT_ACTIVE_OBSERVER_AND_REGISTRY_REQUIRED")
        validate_observer_identity(identity, process_identity(child.pid), expected_argv=argv,
            registry_reference=registry_reference, source_reference=pin(source))
        verify_claims(args.registry, registry)
        fresh = checked_row(load(row["request_reference"]["path"])["job_name"])
        need(fresh["job_id"] == row["job_id"] and fresh["request_reference"] == row["request_reference"]
             and fresh["receipt_reference"] == row["receipt_reference"], "OWN_HELD_BINDING_CHANGED_NO_RELEASE")
        output = query(["scontrol", "release", row["job_id"]])
        after = query(["scontrol", "show", "job", row["job_id"], "--oneliner"])
        releases.append({"job_id": row["job_id"], "before": fresh["held_readback"],
                         "release_stdout": output, "after": after})
    own_directory(ROOT / "control/cpu_auto_memory_activations")
    activation = ROOT / "control/cpu_auto_memory_activations" / (args.registry.stem + ".json")
    write_new(activation, {"schema": "ACTUAL_CPU_AUTO_MEMORY_PHASE_ACTIVATION_V1",
        "registry_reference": registry_reference, "observer_identity_reference": pin(args.observer_output / "identity.json"),
        "observer_pid": child.pid, "releases": releases, "observed_at": now(),
        "status": "OWN_JOBS_RELEASED_FRESH_CPU_CODE_QUOTA_PROOFS_STILL_REQUIRED",
        "other_jobs_modified": False, "old_observer_modified": False})
    print(__import__("json").dumps({"activation": pin(activation),
        "job_ids": [r["job_id"] for r in registry["jobs"]], "observer_pid": child.pid,
        "status": "ACTUAL_DISJOINT_QUEUE_LIVE_NOT_SCIENCE_COMPLETE"}), flush=True)


if __name__ == "__main__":
    main()
