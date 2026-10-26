"""CPU-only metadata and controlled owned fork/exec tests, never Slurm submission."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

import pytest

import identity_revision_v4 as core


def ident(pid=100, argv=None, *, parent=False):
    argv = list(argv or ["/python", "-B", "/worker.py"])
    return {"status": "ACTIVE", "pid": pid, "uid": 1278,
            "boot_id": "eb0dc3d0-b5c9-4ca0-8074-c9177a9163b1",
            "start_ticks": 10000 + pid, "pgid": 100, "sid": 100,
            "ppid": 90 if parent else 100, "argv": argv,
            "argv_sha256": core.argv_sha256(argv),
            "cgroup": "1:freezer:/slurm/uid_1278/job_12345/step_batch\n",
            "slurm_job_id": "12345", "created": 100000.0 + pid}


def fixture_context():
    roles = [{"role": f"pytest_shard_{i:02d}", "shard": i, "launch_kind": "exec",
              "expected_argv": ["/python", "-B", "-m", "pytest", f"/tests/test_{i}.py"],
              "cwd": "/tree/current", "start_new_session": False, "stdin": "DEVNULL"}
             for i in range(4)]
    return {"source_pins": {"path": "/pins.json", "bytes": 10, "sha256": "1" * 64},
            "worker_source": {"path": "/worker.py", "bytes": 20, "sha256": "2" * 64},
            "control_plan": {"path": "/plan.json", "bytes": 30, "sha256": "3" * 64},
            "roles": roles}


def registry_fixture(*, clock=None, emit=None):
    events = []
    parent = ident(parent=True)
    context = fixture_context()
    registry = core.IdentityRegistry(parent, emit or events.append, context=context,
                                     clock=clock or (lambda: 0.0))
    manifest = core.make_manifest(parent, context)
    ref = {"path": "/manifest.json", "bytes": 40, "sha256": "4" * 64}
    registry.set_manifest(manifest, ref)
    return registry, events


def target(registry, role=0, pid=200):
    return ident(pid, registry.manifest["roles"][role]["expected_argv"])


def receipt(registry, child, role=0):
    return core.make_exec_receipt(registry.manifest, registry.manifest_ref,
                                  registry.manifest["roles"][role], child)


def fixed_runtime():
    pins = {"runtime_sources": [core.file_ref(core.HELPERS / (name + ".py"))
                               for name in ("runtime_monitor", "private_runtime_storage", "run_supervised")]}
    return core.load_fixed_runtime(pins)


def test_original_signal_authority_keys_remain_exact():
    runtime = fixed_runtime()
    assert tuple(runtime["run_supervised"].IDENTITY_KEYS) == core.IDENTITY_KEYS
    assert "created" not in core.IDENTITY_KEYS


@pytest.mark.parametrize("field", core.IDENTITY_KEYS)
def test_each_frozen_signal_authority_field_is_still_required(monkeypatch, field):
    runtime = fixed_runtime()
    cleanup = runtime["run_supervised"]
    before, after = ident(parent=True), ident(parent=True)
    if field in {"pid", "uid", "start_ticks", "pgid", "sid"}:
        after[field] += 1
    elif field == "boot_id":
        after[field] = "fb0dc3d0-b5c9-4ca0-8074-c9177a9163b1"
    elif field == "argv_sha256":
        after["argv"] = ["/python", "/other.py"]
        after[field] = core.argv_sha256(after["argv"])
    else:
        after[field] += "changed"
    monkeypatch.setattr(cleanup, "capture_process_identity", lambda *a, **k: after)
    assert cleanup.recorded_process_state(before)["status"] == "IDENTITY_CHANGED"
    assert cleanup.same_owned_process(before) is None


def test_creation_time_drift_is_diagnostic_and_does_not_rewrite_authority():
    events = []
    before = ident(parent=True)
    registry = core.IdentityRegistry(before, events.append)
    after = {**before, "created": before["created"] + 1.0}
    assert registry.observe(after) == "MATCH"
    assert registry.observe(after) == "MATCH"
    assert registry.observed[(before["pid"], before["start_ticks"])] == before
    assert sum(row["kind"] == "WALL_CLOCK_DIAGNOSTIC_CHANGED" for row in events) == 1


def test_identity_difference_is_fsynced_before_raise_and_keeps_original(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    fsyncs = []
    native = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (fsyncs.append(fd), native(fd))[-1])
    log = core.EventLog(path)
    before = ident(parent=True)
    registry = core.IdentityRegistry(before, log)
    after = {**before, "argv": ["/python", "/unexpected.py"]}
    after["argv_sha256"] = core.argv_sha256(after["argv"])
    with pytest.raises(core.IdentityViolation):
        registry.observe(after)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(fsyncs) == 3  # root event file + parent directory, then difference event
    assert rows[-1]["changed_keys"] == ["argv_sha256"]
    assert rows[-1]["before"] == before and rows[-1]["after"] == after
    assert registry.observed[(100, before["start_ticks"])] == before


def test_event_cap_is_fail_closed(tmp_path):
    path = tmp_path / "events.jsonl"
    log = core.EventLog(path, cap_bytes=128)
    with pytest.raises(ValueError, match="cap"):
        log({"kind": "CONTROL", "full_identity": "x" * 200})
    assert not path.exists()


def test_atomic_publication_is_complete_exclusive_and_raw_bound(tmp_path):
    path = tmp_path / "manifest.json"
    value = {"field": "完整", "nested": [1, 2, 3]}
    ref = core.atomic_json(path, value)
    assert core.read_json(path, ref["sha256"]) == value
    with pytest.raises(FileExistsError):
        core.atomic_json(path, {"replace": True})
    assert core.read_json(path) == value
    assert list(tmp_path.iterdir()) == [path]


def test_source_inventory_raw_hash_and_runtime_bytes_are_required(tmp_path):
    source = tmp_path / "owned.py"
    source.write_text("x = 1\n")
    pins = {"schema": core.PINS_SCHEMA, "runtime_sources": [core.file_ref(source)]}
    path = tmp_path / "pins.json"
    ref = core.atomic_json(path, pins)
    assert core.verify_source_pins(path, ref["sha256"]) == pins
    with pytest.raises(ValueError, match="Raw SHA"):
        core.verify_source_pins(path, "0" * 64)
    source.write_text("x = 2\n")
    with pytest.raises(ValueError, match="drift"):
        core.verify_source_pins(path, ref["sha256"])


def test_pending_parent_clone_has_no_signal_authority_and_exact_receipt_enrolls():
    registry, events = registry_fixture()
    clone = ident(200)
    child = target(registry)
    assert registry.observe(clone) == "PENDING"
    assert (200, clone["start_ticks"]) not in registry.observed
    assert registry.observe(child) == "PENDING"
    registry.enroll_receipt(receipt(registry, child), child)
    assert registry.observed[(200, child["start_ticks"])] == child
    assert not registry.pending
    transition = [e for e in events if e["kind"] == "PENDING_EXEC_TRANSITION"]
    assert len(transition) == 1 and transition[0]["changed_keys"] == ["argv_sha256"]


@pytest.mark.parametrize("field", ["uid", "boot_id", "pgid", "sid", "cgroup", "slurm_job_id", "ppid", "start_ticks"])
def test_receipt_cannot_change_pending_kernel_or_session_identity(field):
    registry, _ = registry_fixture()
    first = ident(200)
    registry.observe(first)
    child = target(registry)
    if field in {"uid", "pgid", "sid", "ppid", "start_ticks"}:
        child[field] += 1
    elif field == "boot_id":
        child[field] = "fb0dc3d0-b5c9-4ca0-8074-c9177a9163b1"
    elif field == "slurm_job_id":
        child["slurm_job_id"] = "12346"
        child["cgroup"] = child["cgroup"].replace("12345", "12346")
    else:
        child[field] += "other"
    # A stale/reused PID is not allowed to borrow a pending birth or role.
    with pytest.raises((core.IdentityViolation, ValueError)):
        registry.enroll_receipt(receipt(registry, target(registry)), child)
    assert not registry.roles and (200, first["start_ticks"]) not in registry.observed


@pytest.mark.parametrize("field", ["manifest", "role", "source_pins", "worker_source", "control_plan",
                                  "job_id", "uid", "parent_pid", "child_pid", "popen_returned_after_exec"])
def test_metadata_tamper_cannot_authorize_exec(field):
    registry, _ = registry_fixture()
    child = target(registry)
    registry.observe(child)
    value = receipt(registry, child)
    if field == "manifest":
        value[field] = {**value[field], "sha256": "0" * 64}
    elif field in {"source_pins", "worker_source", "control_plan"}:
        value[field] = {**value[field], "sha256": "0" * 64}
    elif field == "role":
        value[field] = "unknown"
    elif field == "job_id":
        value[field] = "12346"
    elif field == "popen_returned_after_exec":
        value[field] = False
    else:
        value[field] += 1
    with pytest.raises(ValueError):
        registry.enroll_receipt(value, child)
    assert not registry.roles


def test_already_enrolled_later_exec_is_rejected_and_cleanup_cannot_rebind():
    registry, _ = registry_fixture()
    child = target(registry)
    registry.observe(child)
    registry.enroll_receipt(receipt(registry, child), child)
    after = {**child, "argv": ["/python", "/later_unknown_exec.py"]}
    after["argv_sha256"] = core.argv_sha256(after["argv"])
    with pytest.raises(core.IdentityViolation):
        registry.observe(after)
    registry.quarantine(after, "Cleanup discovery is not enrollment")
    assert registry.observed[(200, child["start_ticks"])] == child


def test_unknown_pending_exec_is_rejected_with_evidence():
    registry, events = registry_fixture()
    clone = ident(200)
    registry.observe(clone)
    after = {**clone, "argv": ["/python", "/unknown.py"]}
    after["argv_sha256"] = core.argv_sha256(after["argv"])
    with pytest.raises(core.IdentityViolation, match="undeclared"):
        registry.observe(after)
    assert events[-1]["before"] == clone and events[-1]["after"] == after


def test_repeated_stable_parent_clone_does_not_prove_fork_only_or_exec_completion():
    now = [0.0]
    registry, _ = registry_fixture(clock=lambda: now[0])
    clone = ident(200)
    for elapsed in (0, 1, 2, 29):
        now[0] = elapsed
        assert registry.observe(clone) == "PENDING"
    assert not registry.roles and (200, clone["start_ticks"]) not in registry.observed
    now[0] = core.PENDING_SECONDS + 0.01
    with pytest.raises(core.IdentityViolation, match="deadline"):
        registry.observe(clone)


def test_fork_only_launch_kind_is_not_silently_admitted_by_this_four_exec_protocol():
    registry, _ = registry_fixture()
    value = deepcopy(registry.manifest)
    value["roles"][0]["launch_kind"] = "fork_only"
    with pytest.raises(ValueError):
        core.validate_manifest(value, registry.parent, registry.context)


def test_role_reuse_and_completion_with_missing_receipts_are_rejected():
    registry, _ = registry_fixture()
    first = target(registry)
    registry.observe(first)
    registry.enroll_receipt(receipt(registry, first), first)
    second = target(registry, pid=201)
    registry.observe(second)
    with pytest.raises(ValueError, match="reused"):
        registry.enroll_receipt(receipt(registry, second), second)
    with pytest.raises(ValueError):
        registry.require_completed_enrollment()


def test_unresolved_pending_and_cleanup_discovery_never_create_signal_authority():
    registry, _ = registry_fixture()
    pending = ident(200)
    other = ident(300, ["/python", "/other.py"])
    registry.observe(pending)
    registry.quarantine(other, "Unknown at cleanup")
    rows = registry.unresolved(lambda pid: pending if pid == 200 else other)
    assert len(rows) == 2 and all(r["status"] == "UNRESOLVED_NO_SIGNAL_AUTHORITY" for r in rows)
    assert set(registry.observed) == {(registry.parent["pid"], registry.parent["start_ticks"])}
    assert registry.unresolved(lambda pid: {"status": "GONE", "pid": pid}) == []


def test_four_exact_receipts_allow_completion_without_changing_grouping_or_argv(tmp_path):
    for name, size in [("w.py", 11), ("a.py", 11), ("c.py", 8), ("d.py", 5), ("e.py", 4), ("f.py", 3)]:
        (tmp_path / name).write_text("x" * size)
    groups = core.partition_groups(list(tmp_path.iterdir()))
    assert [[p.name for p in group] for group in groups] == [["a.py"], ["w.py"], ["c.py", "f.py"], ["d.py", "e.py"]]
    roles = core.pytest_roles("/python", "/tree", "/output", groups)
    assert roles[2]["expected_argv"] == ["/python", "-B", "-m", "pytest",
        str(tmp_path / "c.py"), str(tmp_path / "f.py"), "-q", "-p", "no:cacheprovider",
        "--junitxml=/output/shard_02.xml", "--basetemp=/output/tmp_2"]
    registry, _ = registry_fixture()
    for index in range(4):
        child = target(registry, role=index, pid=200 + index)
        registry.observe(child)
        registry.enroll_receipt(receipt(registry, child, index), child)
    registry.require_completed_enrollment()
    assert len(registry.roles) == 4 and len(registry.observed) == 5


def test_fixture_census_counts_registration_and_never_follows_fixture_link(tmp_path):
    from fixture_census_v4 import fixture_output_bytes
    output = tmp_path / "out"
    (output / "tmp_0").mkdir(parents=True)
    (output / ".process_registration_v4").mkdir()
    (output / ".process_registration_v4/manifest.json").write_text('{"control":1}')
    outside = tmp_path / "outside"
    outside.write_bytes(b"x" * 4096)
    (output / "tmp_0/link").symlink_to(outside)
    total = fixture_output_bytes(output, output=output, fixtures={"tmp_0"})
    actual = sum(p.lstat().st_size for p in [output, output / "tmp_0",
        output / ".process_registration_v4", output / ".process_registration_v4/manifest.json",
        output / "tmp_0/link"])
    assert total == actual
    with pytest.raises(ValueError):
        fixture_output_bytes(outside, output=output, fixtures={"tmp_0"})


@pytest.mark.skipif(sys.platform != "linux" or not hasattr(os, "fork"), reason="Actual owned Linux fork/exec required")
def test_actual_fork_clone_exec_receipt_and_pending_rss_are_observed(tmp_path):
    """Real /proc + old monitor, no mocked identities and no Slurm submission."""
    runtime = fixed_runtime()
    monitor = runtime["runtime_monitor"]
    group = Path("/proc/self/cgroup").read_text()
    parent = core.capture_identity(monitor, os.getpid(), expected_cgroup=group)
    assert parent["status"] == "ACTIVE"
    context = fixture_context()  # explicitly a test-only protocol context
    command = [sys.executable, "-B", "-c", "import time; time.sleep(10)"]
    context["roles"][0]["expected_argv"] = command
    events = []
    registry = core.IdentityRegistry(parent, events.append, context=context)
    manifest = core.make_manifest(parent, context)
    manifest_ref = core.atomic_json(tmp_path / "manifest.json", manifest)
    registry.set_manifest(manifest, manifest_ref)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(write_fd)
            os.read(read_fd, 1)
            os.close(read_fd)
            os.execv(command[0], command)
        finally:
            os._exit(90)
    os.close(read_fd)
    bound = None
    try:
        clone = core.capture_identity(monitor, pid, expected_cgroup=group)
        assert clone["status"] == "ACTIVE" and clone["argv"] == parent["argv"]
        assert registry.observe(clone) == "PENDING"
        observation = monitor.owned_process_observation(os.getpid())
        measured = [row for row in observation["processes"] if row["pid"] == pid]
        assert len(measured) == 1 and measured[0]["rss_bytes"] > 0
        assert observation["rss_sum_bytes"] >= measured[0]["rss_bytes"]
        assert (pid, clone["start_ticks"]) not in registry.observed
        os.write(write_fd, b"1")
        os.close(write_fd)
        write_fd = None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            bound = core.capture_identity(monitor, pid, expected_cgroup=group)
            if bound["status"] == "ACTIVE" and bound["argv"] == command:
                break
            time.sleep(0.01)
        assert bound["status"] == "ACTIVE" and bound["argv"] == command
        assert not core.changed_keys(clone, bound, core.CORE_KEYS)
        assert registry.observe(bound) == "PENDING"
        value = core.make_exec_receipt(manifest, manifest_ref, manifest["roles"][0], bound)
        ref = core.atomic_json(tmp_path / "exec.json", value)
        fresh = core.capture_identity(monitor, pid, expected_cgroup=group)
        registry.enroll_receipt(core.read_json(ref["path"], ref["sha256"]), fresh)
        assert registry.observed[(pid, fresh["start_ticks"])] == fresh
        assert any(row["kind"] == "PENDING_EXEC_TRANSITION" for row in events)
    finally:
        if write_fd is not None:
            os.close(write_fd)
        # The test owns this exact fork birth. Full frozen identity is rechecked
        # immediately before its sole individual signal; never use killpg.
        current = core.capture_identity(monitor, pid, expected_cgroup=group)
        authority = bound if bound and bound.get("status") == "ACTIVE" else locals().get("clone")
        if current["status"] == "ACTIVE" and authority and not core.changed_keys(authority, current):
            os.kill(pid, signal.SIGTERM)
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass

@pytest.mark.skipif(sys.platform != 'linux', reason='Actual owned Linux Popen identity required')
def test_real_popen_receipt_and_strict_match_cleanup(tmp_path):
    import subprocess
    runtime = fixed_runtime()
    monitor, cleanup = runtime['runtime_monitor'], runtime['run_supervised']
    group = Path('/proc/self/cgroup').read_text()
    parent = core.capture_identity(monitor, os.getpid(), expected_cgroup=group)
    command = [sys.executable, '-B', '-c', 'import time; time.sleep(10)']
    context = fixture_context()
    context['roles'][0]['expected_argv'] = command
    registry = core.IdentityRegistry(parent, lambda event: None, context=context)
    manifest = core.make_manifest(parent, context)
    ref = core.atomic_json(tmp_path / 'manifest.json', manifest)
    registry.set_manifest(manifest, ref)
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL)
    bound = None
    try:
        bound = core.capture_identity(monitor, process.pid, expected_cgroup=group, expected_argv=command)
        assert bound['status'] == 'ACTIVE'
        registry.observe(bound)
        value = core.make_exec_receipt(manifest, ref, manifest['roles'][0], bound)
        receipt_ref = core.atomic_json(tmp_path / 'exec.json', value)
        fresh = core.capture_identity(monitor, process.pid, expected_cgroup=group)
        registry.enroll_receipt(core.read_json(receipt_ref['path'], receipt_ref['sha256']), fresh)
        forged = {**fresh, 'argv_sha256': '0' * 64}
        assert cleanup.same_owned_process(forged) is None
        assert process.poll() is None  # refused authority has not signalled it
        result = cleanup.stop_recorded({(fresh['pid'], fresh['start_ticks']): fresh}, grace_seconds=0)
        assert result['actions'] and all(row['pid'] == process.pid for row in result['actions'])
        assert result['remaining'] == []
        assert process.wait(timeout=5) != 0
    finally:
        if process.poll() is None and bound and bound.get('status') == 'ACTIVE':
            cleanup.stop_recorded({(bound['pid'], bound['start_ticks']): bound}, grace_seconds=0)
            process.wait(timeout=5)
@pytest.mark.skipif(sys.platform != 'linux', reason='Actual rejected /proc frame evidence required')
def test_rejected_capture_retains_full_diagnostic_without_granting_authority():
    runtime = fixed_runtime()
    group = Path('/proc/self/cgroup').read_text()
    result = core.capture_identity(runtime['runtime_monitor'], os.getpid(), expected_cgroup=group + 'wrong')
    assert result['status'] == 'IDENTITY_CHANGED'
    evidence = result['diagnostic_identity']
    assert evidence['status'] == 'DIAGNOSTIC_ONLY' and evidence['coherent_kernel_frame'] is True
    assert all(key in evidence for key in core.IDENTITY_KEYS)
    assert evidence['cgroup'] == group and evidence['uid'] == os.getuid()
    assert evidence['slurm_job_id'] == os.environ['SLURM_JOB_ID']
    with pytest.raises(ValueError):
        core.validate_identity(evidence)