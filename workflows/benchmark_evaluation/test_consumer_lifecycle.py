"""Behavioral checks for the future consumer entry; no benchmark data is read."""
import base64
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock
from workflows.benchmark_evaluation import consumer_lifecycle as lifecycle


@unittest.skipUnless(sys.platform == "linux" and hasattr(os, "pidfd_open")
                     and hasattr(signal, "pidfd_send_signal"), "Linux pidfd required")
class ConsumerLifecycleTests(unittest.TestCase):
    def command(self, code):
        return [sys.executable, "-I", "-S", "-B", "-c", code]

    def run_code(self, code, deadline_seconds=4, reserve=0.3, capture=True):
        return lifecycle.run_unit(
            self.command(code), time.monotonic() + deadline_seconds,
            reserve, 0.03, capture=capture, poll_seconds=0.01, settle_seconds=0.1)

    def assert_closed(self, result):
        self.assertTrue(result["children_exited"])
        self.assertFalse(lifecycle.descendants(os.getpid()))
        for record in result["owned"]:
            current = lifecycle.identity(record["pid"])
            self.assertTrue(current is None or current.start_ticks != record["start_ticks"])

    def test_complete_foreground_child_is_reaped(self):
        previous = lifecycle._subreaper()
        result = self.run_code("print('closed')")
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["leader_returncode"], 0)
        self.assertEqual(result["stdout"].strip(), "closed")
        self.assertIsNone(result["reason"])
        self.assert_closed(result)
        self.assertEqual(lifecycle._subreaper(), previous)

    def test_parent_term_closes_leader_and_adopted_grandchild(self):
        code = """
import os,signal,subprocess,sys,time
subprocess.Popen([sys.executable,'-I','-S','-B','-c','import time;time.sleep(8)'])
time.sleep(0.25)
os.kill(os.getppid(),signal.SIGTERM)
time.sleep(8)
"""
        result = self.run_code(code)
        self.assertEqual(result["returncode"], 75)
        self.assertEqual(result["reason"], "SIGNAL_SIGTERM")
        self.assertGreaterEqual(len(result["owned"]), 2)
        self.assert_closed(result)

    def test_cleanup_window_ends_interruptible_work_before_hard_deadline(self):
        started = time.monotonic()
        result = self.run_code("import time;time.sleep(8)", deadline_seconds=0.8, reserve=0.25)
        self.assertEqual(result["returncode"], 75)
        self.assertEqual(result["reason"], "CLEANUP_WINDOW")
        self.assertLess(time.monotonic() - started, 3)
        self.assert_closed(result)

    def test_zero_leader_code_cannot_hide_a_living_background_worker(self):
        code = """
import subprocess,sys,time
subprocess.Popen([sys.executable,'-I','-S','-B','-c','import time;time.sleep(8)'])
time.sleep(0.2)
"""
        result = self.run_code(code)
        self.assertEqual(result["leader_returncode"], 0)
        self.assertEqual(result["returncode"], 75)
        self.assertEqual(result["reason"], "DESCENDANT_OUTLIVED_LEADER")
        self.assertGreaterEqual(len(result["owned"]), 2)
        self.assert_closed(result)


    def test_adopted_worker_failure_is_not_hidden_by_zero_leader_exit(self):
        code = """
import subprocess,sys
subprocess.Popen([sys.executable,'-I','-S','-B','-c','raise SystemExit(7)'])
"""
        result = self.run_code(code)
        self.assertEqual(result["leader_returncode"], 0)
        self.assertEqual(result["returncode"], 75)
        self.assertEqual(result["reason"], "ADOPTED_WORKER_FAILED")
        self.assert_closed(result)

    def test_insufficient_budget_never_starts_a_command(self):
        with mock.patch.object(lifecycle.subprocess, "Popen", side_effect=AssertionError("must not start")):
            result = lifecycle.run_unit(
                self.command("raise AssertionError"), time.monotonic() + 0.2, 0.15, 0.1)
        self.assertEqual(result["returncode"], 75)
        self.assertEqual(result["reason"], "INSUFFICIENT_REAL_TIME")
        self.assertEqual(result["owned"], [])
        self.assertFalse(lifecycle.descendants(os.getpid()))

    def test_existing_unrelated_child_is_not_adopted_or_signalled(self):
        sibling = subprocess.Popen(self.command("import sys;sys.stdin.buffer.read()"), stdin=subprocess.PIPE)
        try:
            with self.assertRaisesRegex(RuntimeError, "pre-existing children"):
                self.run_code("raise AssertionError('must not start')")
            self.assertIsNone(sibling.poll())
        finally:
            sibling.stdin.close()
            sibling.wait()
        self.assertFalse(lifecycle.descendants(os.getpid()))

    def test_reused_pid_identity_is_never_signalled(self):
        current = lifecycle.identity(os.getpid())
        stale = current._replace(start_ticks=current.start_ticks + 1)
        with mock.patch.object(lifecycle.os, "pidfd_open", side_effect=AssertionError("unsafe open")):
            self.assertFalse(lifecycle.term_owned(stale, current))

    def test_control_output_is_bounded_and_closed_without_success(self):
        result = self.run_code("import sys;sys.stdout.write('x'*300000)")
        self.assertEqual(result["returncode"], 75)
        self.assertEqual(result["reason"], "CONTROL_OUTPUT_LIMIT")
        self.assertLessEqual(len(result["stdout"]), 131072)
        self.assert_closed(result)


    def test_supervisor_io_exception_still_reaps_its_worker(self):
        real_select = lifecycle.selectors.DefaultSelector.select
        calls = [0]
        def interrupted_once(instance, timeout=None):
            calls[0] += 1
            if calls[0] == 1:
                raise OSError("injected supervisor I/O error")
            return real_select(instance, timeout)
        with mock.patch.object(lifecycle.selectors.DefaultSelector, "select", interrupted_once):
            with self.assertRaisesRegex(OSError, "injected"):
                self.run_code("import time;time.sleep(8)")
        self.assertFalse(lifecycle.descendants(os.getpid()))

    def test_spawn_exception_after_fork_does_not_abandon_a_child(self):
        real_popen = lifecycle.subprocess.Popen
        created = []
        def create_then_fail(*args, **kwargs):
            created.append(real_popen(*args, **kwargs))
            raise OSError("injected spawn completion error")
        try:
            with mock.patch.object(lifecycle.subprocess, "Popen", create_then_fail):
                with self.assertRaisesRegex(OSError, "injected"):
                    self.run_code("import time;time.sleep(8)")
            self.assertFalse(lifecycle.descendants(os.getpid()))
            self.assertIsNone(lifecycle.identity(created[0].pid))
        finally:
            for process in created:
                process.poll()
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream:
                        stream.close()

    def test_actual_slurm22_window_uses_real_limit_and_owner(self):
        raw = ("JobId=42 JobState=RUNNING UserId=test(%s) Partition=cpu "
               "NodeList=compute-0-10 RunTime=00:02:10 TimeLimit=00:10:00") % os.getuid()
        self.assertEqual(lifecycle.actual_window(raw, 42, os.getuid(), "compute-0-10", 100), 570)
        for changed in [
            raw.replace("RUNNING", "COMPLETED"),
            raw.replace("JobId=42", "JobId=43"),
            raw.replace("TimeLimit=00:10:00", "TimeLimit=UNLIMITED"),
        ]:
            with self.assertRaises(ValueError):
                lifecycle.actual_window(changed, 42, os.getuid(), "compute-0-10", 100)


    def test_faulty_node_state_or_cleanup_reason_declines_start(self):
        lifecycle.require_healthy_node("NodeName=compute-0-10 State=MIXED Reason=None", "compute-0-10")
        for raw in [
            "NodeName=compute-0-10 State=MIXED+DRAIN Reason=None",
            "NodeName=compute-0-10 State=DOWN Reason=None",
            "NodeName=compute-0-10 State=MIXED Reason=Kill task failed [time]",
            "NodeName=compute-0-10 State=MIXED Reason=Not responding [time]",
        ]:
            with self.assertRaises(RuntimeError):
                lifecycle.require_healthy_node(raw, "compute-0-10")

    def test_new_wrapper_preserves_frozen_payload_and_original_time_limit(self):
        original = ("#!/bin/bash\n#SBATCH --time=00:10:00\n#SBATCH --cpus-per-task=1\n"
                    "#SBATCH --output=/share/home/original-%j.log\n"
                    "#SBATCH --error=/share/home/original-%j.err\n"
                    "#SBATCH --chdir=/share/home/original\n#SBATCH --export=ALL\n"
                    "#SBATCH --input=/share/home/original.stdin\n"
                    "set -euo pipefail\nexport MODEL_SEED=20261026\nprintf 'original\\n'\n")
        wrapped = lifecycle.wrap_sbatch(original, "# source", 60)
        self.assertIn("#SBATCH --time=00:10:00\n", wrapped)
        self.assertEqual(wrapped.count("#SBATCH --signal=B:USR1@180"), 1)
        marker = "stdin_data=base64.b64decode("
        encoded = wrapped.split(marker, 1)[1].split(")", 1)[0]
        self.assertEqual(base64.b64decode(encoded.strip("'\"")).decode(), original)
        self.assertIn("exec /usr/bin/python3 -I -S", wrapped)
        self.assertEqual(original.count("--signal"), 0)
        outer_header = wrapped.split("exec /usr/bin/python3", 1)[0]
        self.assertIn("#SBATCH --chdir=/\n", outer_header)
        self.assertIn("#SBATCH --output=/tmp/benchmark-C1-consumer-%j.log\n", outer_header)
        self.assertIn("#SBATCH --error=/tmp/benchmark-C1-consumer-%j.log\n", outer_header)
        self.assertIn("#SBATCH --export=PATH=/usr/bin:/bin,LC_ALL=C,LANG=C,", outer_header)
        self.assertIn("BENCHMARK_NATIVE_SLURM_ACCOUNTING_CONFIG\n", outer_header)
        self.assertIn("#SBATCH --input=/dev/null\n", outer_header)
        self.assertNotIn("/share/home", outer_header)
        self.assertNotIn("--export=ALL", outer_header)

    def test_outer_entry_refuses_unreserved_shared_log_path(self):
        original = "#!/bin/bash\n#SBATCH --time=00:10:00\nset -euo pipefail\ntrue\n"
        with self.assertRaises(ValueError):
            lifecycle.wrap_sbatch(original, "# source", 60, "/share/home/log-%j.log")


if __name__ == "__main__":
    unittest.main()
