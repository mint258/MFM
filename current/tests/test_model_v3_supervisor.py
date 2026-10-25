import importlib.util
import os
from pathlib import Path

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
