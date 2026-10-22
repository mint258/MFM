"""Explicit shard0 node12-to-node18 execution migration; frozen V3 core unchanged."""
from __future__ import annotations
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
HOME = Path("/share/home/zixiao")
STATE = ROOT / "reports/home_stat_inventory_v2_20261016"
FINAL = ROOT / "acceptance/final_20261016_v1"
CORE = ROOT / "scripts/wp5_file_inventory_v3.py"
CORE_SHA = "dea339a9b6444791c575738cad7185a202ec0578002c3d8adff385a9ba9571b2"
PREVIOUS_JOB = "4515552"

def reference(path):
    raw = path.read_bytes()
    return raw, {"path": str(path), "bytes": len(raw),
                 "sha256": hashlib.sha256(raw).hexdigest()}

def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())

def main():
    if len(sys.argv) != 1:
        raise ValueError("FIXED_STATE_SHARD0_MIGRATION_NO_OVERRIDE_ARGUMENTS")
    job = os.environ.get("SLURM_JOB_ID", "")
    host = socket.gethostname().split(".")[0]
    if os.getuid() != 1278 or host != "compute-0-18" or not job.isdigit() or os.environ.get("SLURM_CPUS_PER_TASK") != "24":
        raise ValueError("ACTUAL_UID1278_NODE18_SLURM24CPU_REQUIRED")
    _, core_ref = reference(CORE)
    if core_ref["sha256"] != CORE_SHA:
        raise ValueError("FROZEN_V3_CORE_SHA_CHANGED")
    core = importlib.import_module("wp5_file_inventory_v3")
    if Path(core.__file__).absolute() != CORE:
        raise ValueError("EXACT_FROZEN_V3_IMPORT_REQUIRED")
    manifest_raw, manifest_ref = reference(STATE / "manifest.json")
    manifest = json.loads(manifest_raw)
    if manifest.get("status") != "SIX_DISJOINT_DIRECTORY_SHARDS_READY":
        raise ValueError("EXACT_READY_STATE_MANIFEST_REQUIRED")
    expected = core.config(HOME, STATE)
    if json.dumps(manifest.get("config"), sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("EXACT_ORIGINAL_HOME_STATE_SHARD_CONFIG_REQUIRED")
    old_raw, old_ref = reference(STATE / "shard_0_last_report.json")
    old = json.loads(old_raw)
    if (old.get("job_id") != PREVIOUS_JOB or old.get("shard") != 0
        or old.get("node", "").split(".")[0] != "compute-0-12"
        or old.get("schema") != "WP5_DIRECTORY_INVENTORY_SHARD_V2"
        or old.get("status") != "SHARD_CHECKPOINTED_PENDING_REMAINS"
        or old.get("error_directories") != 0
        or old.get("states") != {"DONE": 257466, "LARGE_PENDING": 2}):
        raise ValueError("EXPECTED_4515552_SHARD0_CHECKPOINT_2_LARGE_ZERO_ERRORS_REQUIRED")
    output = FINAL / ("g0_shard0_node18_migration_" + job)
    output.mkdir(exist_ok=False)
    _, entry_ref = reference(Path(__file__))
    context = {
        "schema": "WP5_G0_SHARD0_NODE18_EXECUTION_MIGRATION_V1",
        "slurm_job_id": job, "uid": os.getuid(), "actual_execution_node": host,
        "previous_execution_node": "compute-0-12", "new_execution_node": "compute-0-18",
        "previous_job_id": PREVIOUS_JOB, "shard": 0, "home": str(HOME), "state": str(STATE),
        "frozen_v3_core": core_ref, "entry_source": entry_ref,
        "original_manifest": manifest_ref, "previous_shard_report": old_ref,
        "workers": 24, "hours": 46, "directory_budget_seconds": 165600,
        "include_large": True, "retry_errors": False,
        "core_and_NODES_modified": False, "seed_shard_ownership_changed": False,
        "DONE_reset_or_rescanned": False, "scientific_parameters_changed": False,
        "source_file_contents_opened": False, "overall_G0_complete_claimed": False,
        "guard_scope": "Exact original config and closed predecessor checkpoint metadata; "
                       "Root supplies actual predecessor terminal accounting. This entry does not query Slurm.",
        "lock_policy": "Frozen V3 scan_shard obtains the original nonblocking exclusive shard_0 lock; "
                       "all task claims, INFLIGHT recovery, directory transactions and commits remain V3.",
    }
    started = time.time()
    save(output / "migration_before.json",
         {**context, "event": "GUARDS_PASSED_BEFORE_FROZEN_CORE_CALL", "observed_epoch": started})
    try:
        result = core.scan_shard(STATE, 0, workers=24, hours=46, budget=165600,
                                 include_large=True, retry_errors=False)
    except BaseException as error:
        save(output / "migration_failure.json",
             {**context, "event": "FROZEN_CORE_CALL_RAISED",
              "started_epoch": started, "finished_epoch": time.time(),
              "error_type": type(error).__name__, "error": str(error)})
        raise
    _, resulting_ref = reference(STATE / "shard_0_last_report.json")
    save(output / "migration_after.json",
         {**context, "event": "FROZEN_CORE_RETURNED", "started_epoch": started,
          "finished_epoch": time.time(), "resulting_shard_report": resulting_ref,
          "shard_status": result["status"], "states": result["states"],
          "error_directories": result["error_directories"],
          "processed_directories_this_attempt": result["processed_directories_this_attempt"],
          "pending_directory_tasks": sum(n for key, n in result["states"].items() if key != "DONE"),
          "shard_complete_without_errors": result["status"] == "SHARD_COMPLETE"})
    print(json.dumps({"status": result["status"], "shard": 0, "execution_node": host,
                      "state": str(STATE), "migration_receipts": str(output)}))

if __name__ == "__main__":
    main()
