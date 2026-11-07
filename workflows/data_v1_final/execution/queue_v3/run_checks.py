"""Run only 14 new queue fixtures and 8 source-status synthetic fixtures."""
import os
import socket
import sys
import unittest
from pathlib import Path
from ..queue_v1.shared import ROOT, REPO, need, now, pin, write_new
from ..queue_v1.queue_contract import CPU_NODES
from .verify_proof_delta import verify


def main():
    jid = os.environ.get("SLURM_JOB_ID", "")
    need(jid.isdecimal() and os.getuid() == 1278
         and socket.gethostname().split(".")[0] in CPU_NODES, "ACTUAL_OWN_CPU_FIXTURE_JOB_REQUIRED")
    need(os.environ.get("SLURM_JOB_PARTITION") == "cpu"
         and os.environ.get("SLURM_CPUS_PER_TASK") == "16"
         and os.environ.get("SLURM_MEM_PER_NODE") == "65536"
         and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "STRICT_16CPU64G_CPU_ONLY_FIXTURES_REQUIRED")
    stages = [("workflows.data_v1_final.execution.queue_v3.test_v3", 14),
              ("workflows.data_v1_final.labels.source_status_v1.test_semantics", 8)]
    rows = []
    for module, expected in stages:
        suite = unittest.defaultTestLoader.loadTestsFromName(module)
        discovered = suite.countTestCases()
        need(discovered == expected, "EXACT_NEW_TEST_DISCOVERY_COUNT_REQUIRED:" + module)
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
        rows.append({"module": module, "expected": expected, "discovered": discovered,
            "ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "skips": len(result.skipped), "successful": result.wasSuccessful() and not result.skipped})
        if not rows[-1]["successful"]:
            break
    passed = len(rows) == len(stages) and all(row["successful"] and row["ran"] == row["expected"] for row in rows)
    old = REPO / "workflows/data_v1_final/execution/queue_v1/observe.py"
    new = Path(__file__).with_name("proof_v3.py")
    delta = verify(old.read_text(encoding="utf-8"), new.read_text(encoding="utf-8"))
    write_new(ROOT / "control/queue_v3_checks" / (jid + ".json"), {
        "schema": "ACTUAL_NEW_QUEUE_V3_AND_SOURCE_STATUS_FIXTURES_V1", "job_id": jid,
        "status": "ALL22_NEW_FIXTURES_PASSED_NO_SCIENCE" if passed else "NEW_FIXTURE_FAILURE_NO_SCIENCE",
        "stages": rows, "observed_at": now(), "proof_source_delta": delta,
        "proof_sources": [pin(old), pin(new)], "scientific_calls": 0, "real_source_records_read": 0,
        "prior_queue_v1_tests_rerun": False, "full_population_acceptance_granted": False})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
