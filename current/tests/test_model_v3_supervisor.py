import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import psutil
import pytest


def helper(monkeypatch):
    directory = Path(__file__).absolute().parents[2] / "tools/model_v3"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location("model_v3_supervisor_test", directory / "run_supervised.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pid_identity_mismatch_is_never_a_signal_target(monkeypatch):
    module = helper(monkeypatch)
    observed = module.capture_process_identity(os.getpid())
    assert observed["status"] == "ACTIVE", observed
    assert module.same_owned_process({**observed, "start_ticks": observed["start_ticks"] + 1}) is None
    assert module.same_owned_process({**observed, "argv_sha256": "0" * 64}) is None
    assert module.same_owned_process(observed).pid == os.getpid()


def test_wall_clock_correction_preserves_kernel_process_identity(monkeypatch):
    module = helper(monkeypatch)
    observed = module.capture_process_identity(os.getpid())
    original = module.capture_process_identity

    def corrected(pid, **kwargs):
        current = original(pid, **kwargs)
        return {**current, "created": current["created"] - 1.} if current["status"] == "ACTIVE" else current

    monkeypatch.setattr(module, "capture_process_identity", corrected)
    state = module.recorded_process_state(observed)
    assert state["status"] == "MATCH" and state["wall_clock_creation_time_changed"]
    assert module.same_owned_process(observed).pid == os.getpid()
    for key, value in (("start_ticks", observed["start_ticks"] + 1),
                       ("boot_id", "different-boot"), ("argv_sha256", "0" * 64),
                       ("cgroup", "different-owned-job"), ("slurm_job_id", "different-job")):
        assert module.recorded_process_state({**observed, key: value})["status"] != "MATCH"


def test_owned_child_can_close_after_wall_clock_creation_drift(monkeypatch):
    module = helper(monkeypatch)
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                               stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        observed = module.capture_process_identity(process.pid)
        assert observed["status"] == "ACTIVE"
        original = module.capture_process_identity

        def corrected(pid, **kwargs):
            current = original(pid, **kwargs)
            if current["status"] == "ACTIVE":
                current = {**current, "created": current["created"] + 1.}
            return current

        monkeypatch.setattr(module, "capture_process_identity", corrected)
        result = module.stop_recorded({(process.pid, observed["start_ticks"]): observed}, grace_seconds=3)
        assert result["remaining"] == []
        assert any(row.get("signal") for row in result["actions"])
        assert not any("signal_refused" in row for row in result["actions"])
        assert process.wait(timeout=5) != 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_natural_exit_between_observation_and_signal_is_preserved(monkeypatch):
    module = helper(monkeypatch)
    alive = [True]
    class Exiting:
        def send_signal(self, _signal):
            alive[0] = False
            raise psutil.NoSuchProcess(999999)
    monkeypatch.setattr(module, "same_owned_process", lambda row: Exiting() if alive[0] else None)
    monkeypatch.setattr(module, "recorded_process_state", lambda row: {"status": "MATCH" if alive[0] else "GONE"})
    result = module.stop_recorded({(999999, 1.): {"pid": 999999, "created": 1.}})
    assert result["remaining"] == []
    assert result["actions"] == [{"pid": 999999, "state": "NATURAL_EXIT_BEFORE_SIGNAL"}]


@pytest.mark.parametrize("last_flags, expected", [(4, "EXITING"), (0, "IDENTITY_CHANGED")])
def test_exit_transition_needs_confirmation_and_ignores_exiting_root_cgroup(monkeypatch, last_flags, expected):
    module = helper(monkeypatch)
    import runtime_monitor
    original = runtime_monitor._proc_frame(os.getpid())
    frames = iter([{**original, "state": "R", "flags": flag} for flag in (0, 4, last_flags)])
    monkeypatch.setattr(runtime_monitor, "_proc_frame", lambda pid: next(frames))
    original_read = Path.read_text
    def read(path, *args, **kwargs):
        return "0::/\n" if str(path).endswith("/cgroup") else original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    observed = runtime_monitor.capture_process_identity(os.getpid(), expected_cgroup="old-job-cgroup")
    assert observed["status"] == expected
