"""Owned-process closure for future benchmark consumers, not live model jobs.

The caller must separately close actual node/storage admission. This module does
not guarantee that an uninterruptible kernel/filesystem wait can be terminated.
It never sends SIGKILL or reports success while owned descendants remain.
"""
import base64
import ctypes
import json
import math
import os
import re
import selectors
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import namedtuple

Identity = namedtuple("Identity", "pid uid start_ticks cgroup state")


def identity(pid):
    try:
        root = "/proc/" + str(pid)
        with open(root + "/stat") as stream:
            raw = stream.read()
        parts = raw[raw.rfind(")") + 2:].split()
        with open(root + "/cgroup") as stream:
            group = stream.read()
        return Identity(pid, os.stat(root).st_uid, int(parts[19]), group, parts[0])
    except (FileNotFoundError, ProcessLookupError):
        return None


def descendants(pid):
    answer = set()
    todo = [pid]
    while todo:
        parent = todo.pop()
        try:
            tasks = os.listdir("/proc/" + str(parent) + "/task")
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        for task in tasks:
            try:
                path = "/proc/" + str(parent) + "/task/" + task + "/children"
                with open(path) as stream:
                    children = [int(value) for value in stream.read().split()]
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            for child in children:
                if child not in answer:
                    answer.add(child)
                    todo.append(child)
    return answer


def same_process(before, after):
    return after is not None and (before.pid, before.start_ticks) == (after.pid, after.start_ticks)


def term_owned(before, context):
    """Signal a recorded owned child through a pidfd, never an unchecked PID."""
    current = identity(before.pid)
    if not same_process(before, current):
        return False
    if (current.uid != context.uid or current.cgroup != context.cgroup
            or current.uid != before.uid or current.cgroup != before.cgroup):
        raise RuntimeError("Owned process identity or cgroup changed")
    try:
        descriptor = os.pidfd_open(before.pid, 0)
    except ProcessLookupError:
        return False
    try:
        current = identity(before.pid)
        if not same_process(before, current):
            return False
        if current.uid != context.uid or current.cgroup != context.cgroup:
            raise RuntimeError("Refuse signal after ownership change")
        try:
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        except ProcessLookupError:
            return False
        return True
    finally:
        os.close(descriptor)


def _subreaper(value=None):
    libc = ctypes.CDLL(None, use_errno=True)
    if value is None:
        result = ctypes.c_int()
        if libc.prctl(37, ctypes.byref(result), 0, 0, 0):
            raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER")
        return result.value
    if libc.prctl(36, int(value), 0, 0, 0):
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")


def run_unit(argv, deadline, reserve_seconds, estimated_seconds, stdin_data=None,
             capture=False, poll_seconds=0.025, settle_seconds=5):
    """Run one indivisible consumer unit; deadline uses time.monotonic().

    Only a standalone, single-threaded supervisor with no existing children may
    own this scope. After TERM it waits/reaps; a D-state child is retained in the
    original scope for operator recovery rather than abandoned or force-killed.
    """
    if (not argv or not os.path.isabs(argv[0])
            or any(not math.isfinite(v) or v <= 0
                   for v in (deadline, reserve_seconds, estimated_seconds, poll_seconds, settle_seconds))):
        raise ValueError("Absolute command and finite positive time budgets required")
    if time.monotonic() + reserve_seconds + estimated_seconds >= deadline:
        return dict(returncode=75, reason="INSUFFICIENT_REAL_TIME", children_exited=True,
                    owned=[], reaped=[], stdout="", stderr="")
    if (sys.platform != "linux" or not hasattr(os, "pidfd_open")
            or not hasattr(signal, "pidfd_send_signal")):
        raise RuntimeError("Linux pidfd APIs are required before launching a consumer")
    if threading.current_thread() is not threading.main_thread() or threading.active_count() != 1:
        raise RuntimeError("A standalone single-threaded supervisor is required")
    if descendants(os.getpid()):
        raise RuntimeError("Refuse scope with pre-existing children")
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise RuntimeError("A standalone default SIGCHLD handler is required")
    context = identity(os.getpid())
    if context is None:
        raise RuntimeError("Cannot establish supervisor process identity")
    probe = os.pidfd_open(os.getpid(), 0)
    try:
        signal.pidfd_send_signal(probe, 0)
    finally:
        os.close(probe)
    previous_subreaper = _subreaper()
    _subreaper(1)
    old_handlers = {}
    stop = {"reason": None}
    records = {}
    signalled = set()
    reaped = []
    uninterruptible = set()
    selector = selectors.DefaultSelector()
    collected = {"stdout": bytearray(), "stderr": bytearray()}
    input_offset = 0
    child = None
    leader_finished_at = [None]

    def request_stop(number, frame):
        if stop["reason"] is None:
            stop["reason"] = "SIGNAL_" + signal.Signals(number).name

    def track():
        for pid in descendants(os.getpid()):
            try:
                found = identity(pid)
            except PermissionError:
                stop["reason"] = "OWNERSHIP_REQUIRES_OPERATOR"
                continue
            if found:
                records[(found.pid, found.start_ticks)] = found
                if found.state == "D":
                    uninterruptible.add((found.pid, found.start_ticks))

    def pump():
        nonlocal input_offset
        for key, event in selector.select(0):
            stream, kind = key.fileobj, key.data
            try:
                if kind == "stdin":
                    if stop["reason"] or input_offset == len(stdin_data):
                        selector.unregister(stream)
                        stream.close()
                        continue
                    count = os.write(stream.fileno(), stdin_data[input_offset:input_offset + 65536])
                    input_offset += count
                else:
                    data = os.read(stream.fileno(), 65536)
                    if data:
                        available = 131072 - len(collected[kind])
                        collected[kind].extend(data[:available])
                        if len(data) > available:
                            stop["reason"] = stop["reason"] or "CONTROL_OUTPUT_LIMIT"
                    else:
                        selector.unregister(stream)
                        stream.close()
            except BlockingIOError:
                continue
            except BrokenPipeError:
                selector.unregister(stream)
                stream.close()

    def drain(ignore_io_errors=False):
        """Keep supervising until the leader and every observed descendant exit."""
        while True:
            leader_code = child.poll()
            if leader_code is not None and leader_finished_at[0] is None:
                leader_finished_at[0] = time.monotonic()
            track()
            try:
                pump()
            except (OSError, ValueError):
                if not ignore_io_errors:
                    raise
                for key in list(selector.get_map().values()):
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
            live = []
            for item in list(records.values()):
                if item.pid != child.pid:
                    try:
                        result, status = os.waitpid(item.pid, os.WNOHANG)
                        if result:
                            reaped.append(dict(pid=item.pid, status=status))
                            if status:
                                stop["reason"] = stop["reason"] or "ADOPTED_WORKER_FAILED"
                    except ChildProcessError:
                        pass
                try:
                    current = identity(item.pid)
                except PermissionError:
                    stop["reason"] = "OWNERSHIP_REQUIRES_OPERATOR"
                    live.append(item)
                    continue
                if same_process(item, current):
                    live.append(current)
            if (leader_code is not None and live
                    and time.monotonic() >= leader_finished_at[0] + settle_seconds):
                stop["reason"] = stop["reason"] or "DESCENDANT_OUTLIVED_LEADER"
            if time.monotonic() >= deadline - reserve_seconds:
                stop["reason"] = stop["reason"] or "CLEANUP_WINDOW"
            if stop["reason"]:
                for item in live:
                    token = (item.pid, item.start_ticks)
                    if token not in signalled and item.state != "Z":
                        try:
                            term_owned(item, context)
                            signalled.add(token)
                        except (OSError, RuntimeError):
                            # An unverifiable live child stays supervised; never
                            # signal it blindly or abandon it as a successful exit.
                            stop["reason"] = "OWNERSHIP_REQUIRES_OPERATOR"
            if leader_code is not None and not live and not descendants(os.getpid()):
                pump()
                return leader_code
            time.sleep(poll_seconds)

    try:
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
            old_handlers[number] = signal.signal(number, request_stop)
        if stop["reason"]:
            return dict(returncode=75, reason=stop["reason"], children_exited=True,
                        owned=[], reaped=[], stdout="", stderr="")
        # The first exec is local and filesystem-independent. The known child
        # then execs the frozen command, so a slow NFS exec cannot strand the
        # supervisor inside Popen before it has an owned PID to manage.
        launch = ["/usr/bin/python3", "-I", "-S", "-B", "-c",
                  "import os,sys;os.execv(sys.argv[1],sys.argv[1:])"] + list(argv)
        child = subprocess.Popen(
            launch, stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None, start_new_session=True, bufsize=0)
        first = identity(child.pid)
        if first:
            records[(first.pid, first.start_ticks)] = first
        if stdin_data is not None:
            os.set_blocking(child.stdin.fileno(), False)
            selector.register(child.stdin, selectors.EVENT_WRITE, "stdin")
        if capture:
            for kind in ("stdout", "stderr"):
                stream = getattr(child, kind)
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, kind)
        try:
            code = drain()
        except BaseException:
            stop["reason"] = stop["reason"] or "SUPERVISOR_EXCEPTION"
            drain(ignore_io_errors=True)
            raise
        output_code = 75 if stop["reason"] else (code if code >= 0 else 128 - code)
        return dict(returncode=output_code, leader_returncode=code, reason=stop["reason"],
                    children_exited=True, owned=[item._asdict() for item in records.values()],
                    reaped=reaped, uninterruptible_observed=sorted(uninterruptible),
                    stdout=collected["stdout"].decode("utf-8", "replace"),
                    stderr=collected["stderr"].decode("utf-8", "replace"))
    finally:
        # Even a failed Popen constructor can leave a newly created child.
        # There were no children at entry and no concurrent dispatch threads.
        # Keep ownership/reaping until this scope is actually empty.
        if descendants(os.getpid()):
            stop["reason"] = stop["reason"] or "SUPERVISOR_EXCEPTION"
            if child is not None:
                drain(ignore_io_errors=True)
            else:
                while descendants(os.getpid()):
                    track()
                    for item in list(records.values()):
                        current = identity(item.pid)
                        if not same_process(item, current):
                            continue
                        token = (current.pid, current.start_ticks)
                        if current.state != "Z" and token not in signalled:
                            try:
                                term_owned(current, context)
                                signalled.add(token)
                            except (OSError, RuntimeError):
                                pass
                        try:
                            os.waitpid(current.pid, os.WNOHANG)
                        except ChildProcessError:
                            pass
                    time.sleep(poll_seconds)
        for key in list(selector.get_map().values()):
            try:
                key.fileobj.close()
            except OSError:
                pass
        selector.close()
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
        _subreaper(previous_subreaper)


def duration_seconds(value):
    if value in ("UNLIMITED", "NOT_SET", "N/A"):
        raise ValueError("A finite actual Slurm TimeLimit is required")
    days, clock = value.split("-", 1) if "-" in value else ("0", value)
    parts = [int(part) for part in clock.split(":")]
    if len(parts) == 1:
        seconds = parts[0] * 60
    elif len(parts) == 2:
        seconds = parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError("Invalid Slurm duration")
    return int(days) * 86400 + seconds


def actual_window(text, job_id, uid, node, queried_at):
    fields = dict(re.findall(r"(?:^|\s)([^=\s]+)=(\S*)", text))
    if (fields.get("JobId") != str(job_id) or fields.get("JobState") != "RUNNING"
            or not fields.get("UserId", "").endswith("(" + str(uid) + ")")
            or fields.get("NodeList") != node or fields.get("Partition") != "cpu"):
        raise ValueError("Exact running owned CPU job required")
    remaining = duration_seconds(fields["TimeLimit"]) - duration_seconds(fields["RunTime"])
    if remaining <= 0:
        raise ValueError("Actual job has no remaining time")
    return queried_at + remaining



def require_healthy_node(text, node):
    fields = dict(re.findall(r"(?:^|\s)([^=\s]+)=(\S*)", text))
    reason = re.search(r"(?:^|\s)Reason=(.*?)(?:\s+[A-Za-z][A-Za-z0-9_]*=|$)", text)
    reason_text = reason.group(1).lower() if reason else ""
    if (fields.get("NodeName") != node
            or fields.get("State") not in {"IDLE", "MIXED", "ALLOCATED"}
            or any(value in reason_text for value in
                   ("kill task failed", "not responding", "unkillable", "spooldir is full"))):
        raise RuntimeError("Node health is not admitted; do not bypass or retry a faulty node")


def authorized_cpu_nodes(allowed_nodes=None):
    """Default legacy range; an explicit frozen selection can admit this session's CPU2."""
    legacy = frozenset("compute-0-" + str(i) for i in range(8, 20))
    if allowed_nodes is None:
        return legacy
    if (not isinstance(allowed_nodes, (list, tuple, set, frozenset))
            or not allowed_nodes or any(not isinstance(node, str) for node in allowed_nodes)):
        raise ValueError("An explicit nonempty frozen CPU-node selection is required")
    selected = frozenset(allowed_nodes)
    if not selected.issubset(legacy | {"compute-0-2"}):
        raise ValueError("Only this session's approved actual CPU nodes are permitted")
    return selected


def run_slurm_consumer(argv, estimated_seconds, stdin_data=None, allowed_nodes=None):
    """Read Slurm 22.05's actual window before dispatching any frozen payload."""
    job = os.environ.get("SLURM_JOB_ID", "")
    node = socket.gethostname().split(".")[0]
    if not job.isdigit() or node not in authorized_cpu_nodes(allowed_nodes):
        raise RuntimeError("An allocated authorized CPU node is required")
    context = identity(os.getpid())
    if not re.search(r"/job_" + job + r"(?:/|\n|$)", context.cgroup):
        raise RuntimeError("Current cgroup must belong to the exact Slurm job")
    query_started = time.monotonic()
    control = run_unit(
        ["/usr/bin/scontrol", "show", "job", job, "-o"],
        query_started + 20, 5, 1, capture=True)
    if control["returncode"]:
        return control
    deadline = actual_window(control["stdout"], job, os.getuid(), node, query_started)
    health = run_unit(
        ["/usr/bin/scontrol", "show", "node", node, "-o"],
        deadline, 180, 1, capture=True)
    if health["returncode"]:
        return health
    require_healthy_node(health["stdout"], node)
    return run_unit(argv, deadline, 180, estimated_seconds, stdin_data=stdin_data)


def wrap_sbatch(script, supervisor_source, estimated_seconds,
                local_log_path="/tmp/benchmark-C1-consumer-%j.log", allowed_nodes=None):
    """Prepare a NEW queued entry; never modify an already running/copy-saved script."""
    if not script.startswith("#!/bin/bash\n") or "#SBATCH --signal" in script:
        raise ValueError("An unwrapped frozen Bash batch script is required")
    if not isinstance(estimated_seconds, (int, float)) or estimated_seconds <= 0:
        raise ValueError("An explicit unit runtime planning estimate is required")
    if not re.fullmatch(r"/tmp/benchmark-C1-consumer-[A-Za-z0-9_.%\-]+\.log", local_log_path):
        raise ValueError("A reserved node-local /tmp consumer log is required")
    selected_nodes = authorized_cpu_nodes(allowed_nodes)
    frozen_nodes = None if allowed_nodes is None else tuple(sorted(selected_nodes))
    prefix = []
    for line in script.splitlines():
        if not line.strip() or line.startswith("#"):
            prefix.append(line)
        else:
            break
    # Slurm opens output and changes directory before this Python entry exists.
    # Keep those operations local; shared paths belong only to the supervised child.
    prefix = [line for line in prefix if not re.match(
        r"^#SBATCH\s+(?:--(?:output|error|input|chdir|export)(?:=|\s)|-(?:o|e|i|D)(?:=|\s))", line)]
    header = "\n".join(prefix).rstrip() + (
        "\n#SBATCH --signal=B:USR1@180\n#SBATCH --chdir=/\n"
        "#SBATCH --export=PATH=/usr/bin:/bin,LC_ALL=C,LANG=C,"
        "BENCHMARK_SOURCE_CACHE,BENCHMARK_CONFIRMATION_BINDINGS_JSON,"
        "BENCHMARK_B1_CONFIRMATION_REPORT,BENCHMARK_C1_CONFIRMATION_REPORT,"
        "BENCHMARK_CONFIRMATION_EVIDENCE_JSON,BENCHMARK_NATIVE_SLURM_ACCOUNTING_CONFIG\n"
        "#SBATCH --input=/dev/null\n"
        "#SBATCH --output=" + local_log_path + "\n"
        "#SBATCH --error=" + local_log_path + "\n")
    code = base64.b64encode(supervisor_source.encode("utf-8")).decode("ascii")
    payload = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return header + """exec /usr/bin/python3 -I -S - <<'BENCHMARK_CONSUMER_LIFECYCLE'
import base64,json,sys
scope={"__name__":"benchmark_consumer_lifecycle"}
exec(compile(base64.b64decode(%r),"<consumer-lifecycle>","exec"),scope)
result=scope["run_slurm_consumer"](["/bin/bash","-s"],%r,stdin_data=base64.b64decode(%r),allowed_nodes=%r)
print(json.dumps({"consumer_lifecycle":result}),flush=True)
sys.exit(result["returncode"])
BENCHMARK_CONSUMER_LIFECYCLE
""" % (code, estimated_seconds, payload, frozen_nodes)
