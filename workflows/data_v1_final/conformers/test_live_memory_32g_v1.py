"""Fixture-only policy checks; never reads real /proc or starts chemistry."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import subprocess

from live_memory_policy_32g_v1 import (ALLOWED_NODES, BASIS, CONFIG_SHA, GIB, PREPARED_SHA,
                                   MemoryMonitor, ProcSampler, evaluate_memory, parse_meminfo,
                                   parse_stat, validate_approval_payload, validate_root_intent)


def approval_fixture():
    config = {"path": "/fixture/config.json", "bytes": 3629, "sha256": CONFIG_SHA}
    prepared = {"path": "/fixture/prepared.json", "bytes": 54827, "sha256": PREPARED_SHA}
    approval = {"schema": "DATA_V1_LIVE_MEMORY_32G_USER_APPROVAL_V1", "status": "APPROVED_BY_USER",
                "user_reply": "在小规模数据测试时可以降低资源使用情况，但是之后的正式数据生成必须使用原有硬件要求",
                "scope": {"task": "SB2_SPRIME_FILL_336_PILOT_ONLY", "molecules": 336,
                          "cpus": 16, "memory_gib": 32, "wall_seconds": 14400,
                          "root_interpretation": "Fixture-only 336-molecule 16CPU/32GiB/4h pilot; no real approval file",
                          "formal_generation_uses_original_hardware_requirements": True,
                          "allowed_nodes": sorted(ALLOWED_NODES), "config_reference": config,
                          "prepared_reference": prepared}}
    return approval, config, prepared


def stat_fixture(pid, *, ppid=1, pgid=999, sid=999, start=100, rss=32, state="R", flags=0):
    fields = ["0"] * 22
    for index, value in {0: state, 1: ppid, 2: pgid, 3: sid, 6: flags, 19: start, 21: rss}.items():
        fields[index] = str(value)
    return f"{pid} (fixture with ) parentheses) " + " ".join(fields)


def add_process(root, pid, *, ppid=1, rss=32, children=(), job="fixture-job", uid=None, state="R", flags=0):
    base = root / str(pid)
    thread = base / "task" / str(pid)
    thread.mkdir(parents=True)
    (base / "stat").write_text(stat_fixture(pid, ppid=ppid, rss=rss, state=state, flags=flags))
    owner = os.getuid() if uid is None else uid
    (base / "status").write_text("Uid:\t" + "\t".join([str(owner)] * 4) + "\n")
    (base / "environ").write_bytes(("SLURM_JOB_ID=" + job).encode() + b"\0SECRET_FIXTURE=withheld\0")
    (base / "cgroup").write_text("7:freezer:/fixture/job_fixture-job/step_batch\n")
    (thread / "children").write_text(" ".join(map(str, children)))


class PolicyTests(unittest.TestCase):
    def test_exact_user_reply_must_be_preserved(self):
        approval, config, prepared = approval_fixture()
        approval["user_reply"] = "Approved all formal generation with reduced memory"
        with self.assertRaisesRegex(ValueError, "EXACT_SMALL_SCALE_USER_REPLY"):
            validate_approval_payload(approval, config, prepared)

    def test_formal_generation_cannot_inherit_pilot_reduction(self):
        approval, config, prepared = approval_fixture()
        approval["scope"]["formal_generation_uses_original_hardware_requirements"] = False
        with self.assertRaisesRegex(ValueError, "FORMAL_GENERATION_MUST_RETAIN"):
            validate_approval_payload(approval, config, prepared)

    def test_pending_or_missing_user_approval_rejected(self):
        approval, config, prepared = approval_fixture()
        approval["status"] = "PENDING_USER_REPLY"
        with self.assertRaisesRegex(ValueError, "ACTUAL_USER_APPROVAL"):
            validate_approval_payload(approval, config, prepared)

    def test_empty_user_reply_rejected(self):
        approval, config, prepared = approval_fixture()
        approval["user_reply"] = " "
        with self.assertRaisesRegex(ValueError, "ACTUAL_USER_APPROVAL"):
            validate_approval_payload(approval, config, prepared)

    def test_scope_resources_each_cannot_expand(self):
        for key, value in {"molecules": 337, "cpus": 32, "memory_gib": 33, "wall_seconds": 14401}.items():
            approval, config, prepared = approval_fixture()
            approval["scope"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "SCOPE"):
                validate_approval_payload(approval, config, prepared)

    def test_node_scope_cannot_expand(self):
        approval, config, prepared = approval_fixture()
        approval["scope"]["allowed_nodes"].append("compute-0-20")
        with self.assertRaisesRegex(ValueError, "NODE_SCOPE"):
            validate_approval_payload(approval, config, prepared)

    def test_original_input_sha_required(self):
        approval, config, prepared = approval_fixture()
        changed = dict(prepared, sha256="0" * 64)
        approval["scope"]["prepared_reference"] = changed
        with self.assertRaisesRegex(ValueError, "CLOSED_PREPARED_SHA"):
            validate_approval_payload(approval, config, changed)

    def test_matching_scope_is_accepted_as_data_only(self):
        approval, config, prepared = approval_fixture()
        self.assertEqual(validate_approval_payload(approval, config, prepared)["molecules"], 336)

    def test_memavailable_is_required_no_free_memory_fallback(self):
        with self.assertRaisesRegex(ValueError, "MEMAVAILABLE_REQUIRED"):
            parse_meminfo("MemTotal: 1000 kB\nMemFree: 900 kB\n")

    def test_meminfo_range_checked(self):
        with self.assertRaisesRegex(ValueError, "INVALID_MEMINFO_RANGE"):
            parse_meminfo("MemTotal: 10 kB\nMemAvailable: 11 kB\n")

    def test_node_boundary_is_inclusive_and_adds_full_32g(self):
        # 200 GiB capacity: 170 GiB threshold; node used138 + reservation32 =170.
        sample = evaluate_memory({"MemTotal": 200 * GIB, "MemAvailable": 62 * GIB}, 200 * GIB, GIB)
        self.assertTrue(sample["dispatch_allowed"])
        denied = evaluate_memory({"MemTotal": 200 * GIB, "MemAvailable": 62 * GIB - 1}, 200 * GIB, GIB)
        self.assertFalse(denied["node_gate_passed"])
        self.assertEqual(sample["reserved_bytes"], 32 * GIB)

    def test_smaller_slurm_capacity_is_used(self):
        sample = evaluate_memory({"MemTotal": 300 * GIB, "MemAvailable": 150 * GIB}, 200 * GIB, 0)
        self.assertEqual(sample["capacity_bytes"], 200 * GIB)
        self.assertFalse(sample["node_gate_passed"])

    def test_owned_rss_at_24g_stops_dispatch(self):
        sample = evaluate_memory({"MemTotal": 200 * GIB, "MemAvailable": 200 * GIB}, 200 * GIB, 24 * GIB)
        self.assertFalse(sample["owned_rss_gate_passed"])
        self.assertFalse(sample["dispatch_allowed"])

    def test_stat_comm_parentheses_and_field_offsets(self):
        parsed = parse_stat(stat_fixture(42, ppid=41, start=123456, rss=543))
        self.assertEqual((parsed["pid"], parsed["ppid"], parsed["start_ticks"], parsed["rss_pages"]), (42, 41, 123456, 543))

    def test_denial_is_sticky_after_recovery(self):
        samples = iter([{"dispatch_allowed": False, "observed_monotonic": time.monotonic()},
                        {"dispatch_allowed": True, "observed_monotonic": time.monotonic()}])
        monitor = MemoryMonitor(lambda: next(samples))
        monitor.observe()
        monitor.observe()
        self.assertFalse(monitor.allow_dispatch())
        self.assertIsNotNone(monitor.first_denial)

    def test_metric_error_stops_dispatch(self):
        def invalid():
            raise PermissionError("fixture metric unavailable")
        monitor = MemoryMonitor(invalid)
        monitor.observe()
        self.assertFalse(monitor.allow_dispatch())
        self.assertTrue(monitor.samples[0]["metric_invalid"])

    def test_stale_metric_stops_dispatch(self):
        monitor = MemoryMonitor(lambda: {"dispatch_allowed": True, "observed_monotonic": time.monotonic() - 3})
        monitor.observe()
        self.assertFalse(monitor.allow_dispatch())
        self.assertEqual(monitor.first_denial["reason"], "LIVE_MEMORY_SAMPLE_STALE")

    def test_root_intent_requires_new_explicit_basis(self):
        _, config, prepared = approval_fixture()
        ref = {"path": "/fixture/approval.json", "bytes": 100, "sha256": "a" * 64}
        # One exactly representable injected clock for both sides. time.time()
        # carries sub-microsecond bits which ISO datetime cannot round-trip;
        # rounding an observed instant up could manufacture a negative age.
        now = datetime(2026, 10, 25, 4, 0, 0, tzinfo=timezone.utc).timestamp()
        receipt = {"observed_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                   "request": {"memory_basis": BASIS, "approval_reference": ref, "node": "compute-0-17",
                               "cpus": 16, "memory_gib": 32, "wall_seconds": 14400, "kind": "conformer", "pilot": True,
                               "root_review": {"status": "APPROVED"},
                               "source_references": [config, prepared], "estimated_peak_output_bytes": 8 * GIB},
                   "account_free_bytes": 500 * GIB, "existing_jobs_all_users": [{"metadata": "MinMemoryNode=0"}],
                   "node_metadata": "NodeName=compute-0-17 RealMemory=375000 AllocMem=0"}
        self.assertEqual(validate_root_intent(receipt, ref, config, prepared, node="compute-0-17", now_epoch=now), 375000 * 1024 ** 2)
        receipt["request"]["memory_basis"] = "ASSUME_ZERO_USE"
        with self.assertRaisesRegex(ValueError, "EXPLICIT_LIVE_MEMORY_APPROVAL"):
            validate_root_intent(receipt, ref, config, prepared, node="compute-0-17", now_epoch=now)
        receipt["request"]["memory_basis"] = BASIS
        for age in (0, 3600):
            receipt["observed_at"] = datetime.fromtimestamp(now - age, timezone.utc).isoformat()
            with self.subTest(valid_age=age):
                validate_root_intent(receipt, ref, config, prepared, node="compute-0-17", now_epoch=now)
        for age in (-1, 3601):
            receipt["observed_at"] = datetime.fromtimestamp(now - age, timezone.utc).isoformat()
            with self.subTest(invalid_age=age), self.assertRaisesRegex(ValueError, "ROOT_INTENT_STALE"):
                validate_root_intent(receipt, ref, config, prepared, node="compute-0-17", now_epoch=now)


class ProcessFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dv1_live_memory_fixture_")
        self.root, self.parent, self.child = Path(self.temp.name), os.getpid(), os.getpid() + 100000
        (self.root / "meminfo").write_text(f"MemTotal: {200 * GIB // 1024} kB\nMemAvailable: {180 * GIB // 1024} kB\n")
        add_process(self.root, self.parent, children=[self.child], rss=32)
        add_process(self.root, self.child, ppid=self.parent, rss=64)
        self.sampler = ProcSampler("fixture-job", 200 * GIB, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_counts_parent_and_owned_descendant_only(self):
        add_process(self.root, self.child + 1, rss=999999, job="other-job")
        sample = self.sampler()
        self.assertEqual(sample["owned_rss_bytes"], 96 * os.sysconf("SC_PAGE_SIZE"))
        self.assertEqual({row["pid"] for row in sample["processes"]}, {self.parent, self.child})

    def test_foreign_job_child_rejected(self):
        (self.root / str(self.child) / "environ").write_bytes(b"SLURM_JOB_ID=other-job\0")
        with self.assertRaisesRegex(ValueError, "JOB_ID_MISMATCH"):
            self.sampler()

    def test_foreign_uid_child_rejected(self):
        (self.root / str(self.child) / "status").write_text("Uid:\t999999\t999999\t999999\t999999\n")
        with self.assertRaisesRegex(ValueError, "UID_MISMATCH"):
            self.sampler()

    def test_foreign_cgroup_child_rejected(self):
        (self.root / str(self.child) / "cgroup").write_text("7:freezer:/fixture/other-job\n")
        with self.assertRaisesRegex(ValueError, "CGROUP_MISMATCH"):
            self.sampler()

    def test_reused_pid_identity_rejected(self):
        first = stat_fixture(self.child, ppid=self.parent, start=100)
        second = stat_fixture(self.child, ppid=self.parent, start=200)
        with patch.object(Path, "read_text", side_effect=[first, second]):
            with self.assertRaisesRegex(ValueError, "IDENTITY_CHANGED"):
                self.sampler.read_process(self.child, self.parent)

    def test_zombie_does_not_require_readable_environment(self):
        (self.root / str(self.child) / "stat").write_text(stat_fixture(self.child, ppid=self.parent, state="Z"))
        (self.root / str(self.child) / "environ").write_bytes(b"")
        sample = self.sampler()
        self.assertEqual({row["pid"] for row in sample["processes"]}, {self.parent})

    def test_stable_exiting_flag_is_excluded(self):
        (self.root / str(self.child) / "stat").write_text(stat_fixture(self.child, ppid=self.parent, flags=4))
        sample = self.sampler()
        self.assertEqual({row["pid"] for row in sample["processes"]}, {self.parent})


class RootAdapterFixtureTests(unittest.TestCase):
    def setUp(self):
        from submit_pilot_live_memory_32g_v1 import submit_once, validate_32g_request
        self.submit_once, self.validate_request = submit_once, validate_32g_request
        self.temp = tempfile.TemporaryDirectory(prefix="dv1_32g_submit_fixture_")
        self.root = Path(self.temp.name)
        def write_new(path, value):
            with path.open("x") as stream:
                json.dump(value, stream)
        self.controller = SimpleNamespace(PROJECT=self.root, write_new=write_new,
            file_ref=lambda path: {"path": str(path), "bytes": path.stat().st_size, "sha256": "fixture"},
            fields=lambda text: dict(value.split("=", 1) for value in text.split()),
            memory_mib=lambda value: int(value[:-1]) * 1024 if value.endswith("G") else int(value),
            query=lambda argv: f"WorkDir={self.root} ReqNodeList=compute-0-17 NumCPUs=16 MinMemoryNode=32G")
        self.request = {"script_reference": {"path": "/fixture/pilot32.sbatch"}, "node": "compute-0-17"}
        self.intent, self.receipt = self.root / "attempt.intent.json", self.root / "attempt.json"
        self.record = {"request": self.request}

    def tearDown(self):
        self.temp.cleanup()

    def test_job_id_is_durable_when_controller_readback_fails(self):
        def unavailable(argv):
            raise RuntimeError("fixture controller readback unavailable")
        self.controller.query = unavailable
        with patch("submit_pilot_live_memory_32g_v1.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="4529999\n", stderr="")) as run:
            with self.assertRaisesRegex(RuntimeError, "readback unavailable"):
                self.submit_once(self.controller, self.request, self.record, self.intent, self.receipt)
        self.assertEqual(json.loads(self.receipt.read_text())["job_id"], "4529999")
        self.assertIn("NO_AUTOMATIC_RETRY", json.loads((self.root / "attempt.verification.json").read_text())["status"])
        self.assertEqual(run.call_count, 1)

    def test_unknown_timeout_is_preserved_once(self):
        with patch("submit_pilot_live_memory_32g_v1.subprocess.run", side_effect=subprocess.TimeoutExpired(["sbatch"], 45)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.submit_once(self.controller, self.request, self.record, self.intent, self.receipt)
        self.assertEqual(json.loads(self.receipt.read_text())["status"], "SUBMISSION_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY")
        self.assertTrue(self.intent.exists())
        self.assertEqual(run.call_count, 1)

    def test_unrecognized_response_does_not_claim_job_id(self):
        with patch("submit_pilot_live_memory_32g_v1.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="ambiguous", stderr="")):
            with self.assertRaisesRegex(RuntimeError, "Unrecognized"):
                self.submit_once(self.controller, self.request, self.record, self.intent, self.receipt)
        self.assertNotIn("job_id", json.loads(self.receipt.read_text()))
        self.assertIn("NO_AUTOMATIC_RETRY", json.loads(self.receipt.read_text())["status"])

    def test_rejected_submission_is_preserved(self):
        with patch("submit_pilot_live_memory_32g_v1.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="fixture rejection")):
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                self.submit_once(self.controller, self.request, self.record, self.intent, self.receipt)
        self.assertEqual(json.loads(self.receipt.read_text())["status"], "SUBMISSION_FAILED_NO_AUTOMATIC_RETRY")

    def test_existing_intent_never_resubmits(self):
        self.intent.write_text("{}")
        with patch("submit_pilot_live_memory_32g_v1.subprocess.run") as run:
            with self.assertRaises(FileExistsError):
                self.submit_once(self.controller, self.request, self.record, self.intent, self.receipt)
        run.assert_not_called()

    def test_successful_actual_id_and_32g_readback(self):
        with patch("submit_pilot_live_memory_32g_v1.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="4529999\n", stderr="")):
            result = self.submit_once(self.controller, self.request, self.record, self.intent, self.receipt)
        self.assertEqual(result, "4529999")
        self.assertEqual(json.loads((self.root / "attempt.verification.json").read_text())["status"], "SUBMITTED_JOB_METADATA_VERIFIED")

    def test_login_source_guard_rejects_gib_asset_before_read(self):
        request = {"script_reference": {"bytes": 1}, "source_references": [{"bytes": 3 * 1024 ** 3}]}
        with self.assertRaisesRegex(ValueError, "ONLY_SMALL_SOURCE"):
            self.validate_request(SimpleNamespace(), request)


if __name__ == "__main__":
    unittest.main()
