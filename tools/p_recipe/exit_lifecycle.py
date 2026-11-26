"""Own-process cleanup for future D entries; scientific runners stay unchanged.

This module is inactive until an entry explicitly calls supervise().  It never
uses SIGKILL.  A kernel-stuck process is reported for administrator recovery.
"""
import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import time


@dataclass(frozen=True)
class Identity:
    pid: int
    start_ticks: int
    uids: tuple
    cgroup: str
    state: str


def identity(pid):
    try:
        raw = Path("/proc/%d/stat" % pid).read_text()
        fields = raw[raw.rfind(")") + 2:].split()
        status = Path("/proc/%d/status" % pid).read_text().splitlines()
        uids = tuple(int(v) for v in next(
            line for line in status if line.startswith("Uid:")).split()[1:])
        return Identity(pid, int(fields[19]), uids,
                        Path("/proc/%d/cgroup" % pid).read_text(), fields[0])
    except (FileNotFoundError, ProcessLookupError):
        return None


def same_process(expected, actual):
    return (actual is not None and expected.pid == actual.pid
            and expected.start_ticks == actual.start_ticks
            and expected.uids == actual.uids)


def owned_scope(record, uid, scope):
    return (record is not None and record.uids == (uid,) * 4
            and scope in record.cgroup.splitlines()
            and record.state not in ("Z", "X"))


def signal_owned(expected, sig, *, uid, scope):
    """Bind a signal to UID/start_ticks/exact cgroup, using pidfd when present."""
    current = identity(expected.pid)
    if not same_process(expected, current) or not owned_scope(current, uid, scope):
        return False
    if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
        try:
            fd = os.pidfd_open(expected.pid, 0)
        except ProcessLookupError:
            return False
        try:
            current = identity(expected.pid)
            if not same_process(expected, current) or not owned_scope(current, uid, scope):
                return False
            signal.pidfd_send_signal(fd, sig)
        finally:
            os.close(fd)
    else:
        current = identity(expected.pid)
        if not same_process(expected, current) or not owned_scope(current, uid, scope):
            return False
        try:
            os.kill(expected.pid, sig)
        except ProcessLookupError:
            return False
    return True


def children(pid):
    result = set()
    try:
        tasks = list(Path("/proc/%d/task" % pid).iterdir())
    except (FileNotFoundError, ProcessLookupError):
        return result
    for task in tasks:
        try:
            result.update(int(v) for v in (task / "children").read_text().split())
        except (FileNotFoundError, ProcessLookupError):
            continue
    return result


def descendants(pid):
    found, pending = {}, list(children(pid))
    while pending:
        child = pending.pop()
        if child in found:
            continue
        record = identity(child)
        if record is None:
            continue
        found[child] = record
        pending.extend(children(child))
    return found


def enable_subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")


def reap_adopted(exclude):
    for pid in children(os.getpid()) - set(exclude):
        record = identity(pid)
        if record is not None and record.state not in ("Z", "X"):
            continue
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            continue


def slurm_scope(job_id):
    record = identity(os.getpid())
    if record is None:
        raise RuntimeError("Own process identity unavailable")
    for line in record.cgroup.splitlines():
        path = line.split(":", 2)[-1]
        if "/job_%s/" % job_id in path:
            return line
    raise RuntimeError("Real Slurm job/step cgroup is required")


def cleanup_seconds(value):
    if type(value) is not int or value < 180:
        raise ValueError("Reserve at least180seconds before the real TimeLimit")
    return value


def supervise(command, *, end_epoch, scope, grace_seconds=900,
              request_stop=None, poll_seconds=.25, stop_state=None, report=print, ssh_identity=None):
    """Run once, request a safe boundary, then TERM and reap every owned child.

    end_epoch must come from the actual allocation, or None for UNLIMITED.
    request_stop may create a cooperative handoff and return its Popen handle;
    that metadata helper is supervised as well.  A stop returns75, never a
    successful scientific completion.  An unresolved exit remains supervised
    and is reported once; it is not declared clean from a batch exit code.
    """
    import subprocess

    grace = cleanup_seconds(grace_seconds)
    if not 0 < poll_seconds <= 5:
        raise ValueError("Bounded process-observation interval required")
    if end_epoch is not None and end_epoch - time.time() <= grace:
        raise RuntimeError("No work may start inside the cleanup window")
    job_id = os.environ.get("SLURM_JOB_ID")
    if ssh_identity is None:
        if not job_id or scope != slurm_scope(job_id):
            raise RuntimeError("Use the exact current allocation/step scope")
    else:
        current = identity(os.getpid())
        if (job_id or not os.environ.get("P_CPU_SSH_EXECUTION_ID")
                or not same_process(ssh_identity, current)
                or current.uids != (os.getuid(),) * 4
                or scope != next((line for line in current.cgroup.splitlines() if line.startswith("0::")), None)):
            raise RuntimeError("Actual SSH supervisor UID/start/cgroup required")
    enable_subreaper()
    uid = os.getuid()
    if uid == 0:
        raise RuntimeError("D supervisor must run as the actual non-root user")
    flags = stop_state if stop_state is not None else {}
    old_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
        old_handlers[sig] = signal.getsignal(sig)
        signal.signal(sig, lambda received, frame: flags.setdefault("signal", received))
    root = None
    helpers, terminated = [], set()
    stopping = None
    reported_unresolved = False
    term_at = None
    try:
        root = subprocess.Popen(command, start_new_session=True)
        while True:
            now = time.time()
            root.poll()
            for helper in helpers:
                helper.poll()
            reap_adopted([root.pid] + [p.pid for p in helpers])
            tree = descendants(os.getpid())
            active = {pid: rec for pid, rec in tree.items()
                      if rec.state not in ("Z", "X")}
            if stopping is None and (flags or
                    (end_epoch is not None and now >= end_epoch - grace)):
                stopping = now
                reason = ("SIGNAL_%s" % flags.get("signal") if flags
                          else "ALLOCATION_CLEANUP_WINDOW")
                report({"phase": "STOP_DISPATCH_REQUESTED", "reason": reason})
                if request_stop is not None and root.returncode is None:
                    helper = request_stop()
                    if helper is not None:
                        helpers.append(helper)
                # TERM/INT can be followed by a short site KillWait.  Deadline
                # or USR1 gives the full preregistered cleanup reservation.
                immediate = flags.get("signal") in (signal.SIGTERM, signal.SIGINT)
                term_at = (now + 10 if immediate else
                           (end_epoch - max(180, grace // 3)
                            if end_epoch is not None else now + grace * 2 / 3))
                if request_stop is None:
                    term_at = now
            # A normal runner must not leave stopped/orphaned descendants.
            if root.returncode is not None and term_at is None:
                term_at = now
            if term_at is not None and now >= term_at:
                for pid, rec in active.items():
                    key = (pid, rec.start_ticks)
                    if key in terminated:
                        continue
                    if signal_owned(rec, signal.SIGTERM, uid=uid, scope=scope):
                        terminated.add(key)
                        report({"phase": "OWNED_TERM", "pid": pid,
                                "start_ticks": rec.start_ticks})
                        # Let a stopped worker consume its pending TERM; do
                        # not resume it in advance of the exit request.
                        if rec.state in ("T", "t"):
                            signal_owned(rec, signal.SIGCONT, uid=uid, scope=scope)
            root.poll()
            for helper in helpers:
                helper.poll()
            reap_adopted([root.pid] + [p.pid for p in helpers])
            remaining = descendants(os.getpid())
            if (root.returncode is not None and
                    all(p.returncode is not None for p in helpers) and
                    not remaining):
                report({"phase": "OWNED_TREE_REAPED", "root": root.pid,
                        "root_returncode": root.returncode})
                return 75 if stopping is not None else root.returncode
            if (end_epoch is not None and now >= end_epoch - 180
                    and not reported_unresolved):
                reported_unresolved = True
                report({"phase": "ADMIN_REQUIRED_EXIT_NOT_PROVEN",
                        "pids": sorted(remaining), "no_SIGKILL": True})
            time.sleep(poll_seconds)
    finally:
        # Do not hide a failed control path or leave a descendant from an
        # exception. Keep supervising after one TERM while the parent can reap.
        if root is not None:
            while True:
                for rec in descendants(os.getpid()).values():
                    key = (rec.pid, rec.start_ticks)
                    if key not in terminated and owned_scope(rec, uid, scope):
                        if signal_owned(rec, signal.SIGTERM, uid=uid, scope=scope):
                            terminated.add(key)
                            if rec.state in ("T", "t"):
                                signal_owned(rec, signal.SIGCONT, uid=uid, scope=scope)
                root.poll()
                for helper in helpers:
                    helper.poll()
                reap_adopted([root.pid] + [p.pid for p in helpers])
                if (root.returncode is not None
                        and all(p.returncode is not None for p in helpers)
                        and not descendants(os.getpid())):
                    break
                time.sleep(poll_seconds)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)

