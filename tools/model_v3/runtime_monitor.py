"""Read-only resource accounting shared by bounded development GPU runners."""
from __future__ import annotations

import os
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time

PF_EXITING = 4


def _proc_frame(pid):
    raw = Path(f"/proc/{pid}/stat").read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    return {"pid": int(raw.split(" ", 1)[0]), "state": fields[0], "ppid": int(fields[1]),
            "pgid": int(fields[2]), "sid": int(fields[3]), "flags": int(fields[6]),
            "start_ticks": int(fields[19])}


def capture_process_identity(pid, *, expected_cgroup=None, expected_argv=None):
    """Bind an active process, distinguishing actual exit from live drift.

    PF_EXITING is the kernel-header value verified in the site's Stage60 probe.
    The first/last stat frames bind birth and exit state; a 0->PF_EXITING change
    needs a third confirming frame before an exiting cgroup is disregarded.
    """
    import psutil
    pid = int(pid)
    try:
        first = _proc_frame(pid)
        status = Path(f"/proc/{pid}/status").read_text()
        uid = int(next(line for line in status.splitlines() if line.startswith("Uid:")).split()[1])
        argv_bytes = Path(f"/proc/{pid}/cmdline").read_bytes()
        cgroup = Path(f"/proc/{pid}/cgroup").read_text()
        second = _proc_frame(pid)
        if (first["pid"], first["start_ticks"]) != (second["pid"], second["start_ticks"]):
            return {"status": "IDENTITY_CHANGED", "pid": pid}
        first_exiting = first["state"] in {"Z", "X"} or bool(first["flags"] & PF_EXITING)
        last_exiting = second["state"] in {"Z", "X"} or bool(second["flags"] & PF_EXITING)
        if first_exiting and not last_exiting:
            return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "exit_flag_reverted"}
        if last_exiting and not first_exiting:
            third = _proc_frame(pid)
            if (second["pid"], second["start_ticks"]) != (third["pid"], third["start_ticks"]) or not (
                    third["state"] in {"Z", "X"} or third["flags"] & PF_EXITING):
                return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "exit_transition_unconfirmed"}
            second = third
        if last_exiting:
            return {"status": "EXITING", "pid": pid, "start_ticks": second["start_ticks"], "uid": uid}
        if (first["pgid"], first["sid"]) != (second["pgid"], second["sid"]):
            return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "process_session_changed"}
        if uid != os.getuid():
            return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "uid_changed"}
        job = os.environ.get("SLURM_JOB_ID")
        if not job or not re.search(r"(?:^|/)job[_-]?" + re.escape(job) + r"(?:/|$)", cgroup, re.M):
            return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "actual_slurm_job_cgroup_missing"}
        if expected_cgroup is not None and cgroup != expected_cgroup:
            return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "live_cgroup_changed"}
        argv = [part.decode("utf-8", "surrogateescape") for part in argv_bytes.rstrip(b"\0").split(b"\0")]
        if not argv_bytes or expected_argv is not None and argv != list(expected_argv):
            return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "argv_changed"}
        return {"status": "ACTIVE", "pid": pid, "uid": uid,
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "start_ticks": second["start_ticks"], "pgid": second["pgid"], "sid": second["sid"],
                "argv": argv, "argv_sha256": hashlib.sha256(argv_bytes).hexdigest(),
                "cgroup": cgroup, "slurm_job_id": job, "created": psutil.Process(pid).create_time()}
    except (FileNotFoundError, ProcessLookupError, psutil.NoSuchProcess):
        try:
            final = _proc_frame(pid)
        except (FileNotFoundError, ProcessLookupError):
            return {"status": "GONE", "pid": pid}
        if final["state"] in {"Z", "X"} or final["flags"] & PF_EXITING:
            return {"status": "EXITING", "pid": pid, "start_ticks": final["start_ticks"]}
        return {"status": "UNREADABLE", "pid": pid, "reason": "proc_file_missing_for_live_process"}


def owned_output_bytes(root, *, max_entries=50000):
    """Count the declared single-run W&B layout without following any links.

    The four SDK forms mirror the site's validated Stage57 dirfd census. Only
    latest-run, debug.log, debug-internal.log and per-run debug-core.log are
    recognized; arbitrary internal symlinks are rejected too. Missing SDK
    targets are allowed only after exact location/target-form validation.
    """
    for attempt in range(3):
        try:
            return _output_census(root, max_entries=max_entries)
        except FileNotFoundError:
            if attempt == 2:
                raise


def _output_census(root, *, max_entries):
    if os.name != "posix":
        raise ValueError("POSIX dirfd accounting required")
    root = Path(root).absolute()
    if ".." in root.parts:
        raise ValueError("Unsafe output root")
    try:
        initial = root.lstat()
    except FileNotFoundError:
        return 0
    uid = os.getuid()
    if not stat.S_ISDIR(initial.st_mode) or initial.st_uid != uid:
        raise ValueError("Output root must be an owned ordinary directory")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(root, flags)
    counted, paths, regular, links, walked, directory_targets = {}, {}, {}, {}, set(), []
    run_pattern = r"offline-run-[0-9]{8}_[0-9]{6}-[a-z0-9]{8}"
    core_pattern = r"core-debug-[0-9]{8}_[0-9]{6}\.log"

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def owned(info, predicate):
        require(info.st_uid == uid and info.st_dev == initial.st_dev and predicate(info.st_mode),
                "Output UID, device or ordinary type differs")

    def register(relative, info, inventory=None):
        name, key = relative.as_posix(), (info.st_dev, info.st_ino)
        require(name not in paths or paths[name] == key, "Output path changed inode during census")
        paths[name] = key
        require(len(paths) <= max_entries, "Output inode census exceeds entry cap")
        row = counted.setdefault(key, {"bytes": info.st_size, "nlink": info.st_nlink, "mode": stat.S_IFMT(info.st_mode)})
        require(row["mode"] == stat.S_IFMT(info.st_mode), "Output inode type changed")
        row["bytes"], row["nlink"] = max(row["bytes"], info.st_size), max(row["nlink"], info.st_nlink)
        if inventory is not None:
            inventory[name] = key
        return key

    def target_path(relative, text):
        require(text and "\\" not in text and "\0" not in text and len(text) <= 4096, "Unsafe SDK link text")
        pointer = PurePosixPath(text)
        if pointer.is_absolute():
            require(pointer.parts[:len(root.parts)] == root.parts, "SDK link escapes output root")
            components, stack = pointer.parts[len(root.parts):], []
        else:
            components, stack = pointer.parts, list(relative.parent.parts)
        for part in components:
            if part == "..":
                require(bool(stack), "SDK link escapes output root")
                stack.pop()
            elif part not in ("", "."):
                stack.append(part)
        require(stack and len(stack) <= 8, "Unexpected SDK target depth")
        return PurePosixPath(*stack)

    def inspect_target(relative, directory):
        descriptor = os.dup(root_fd)
        prefix = PurePosixPath(".")
        try:
            for part in relative.parts[:-1]:
                try:
                    following = os.open(part, flags, dir_fd=descriptor)
                except FileNotFoundError:
                    return None
                except OSError as exc:
                    raise ValueError("SDK target ancestor is not an ordinary unlinked directory") from exc
                os.close(descriptor)
                descriptor = following
                prefix = prefix / part
                info = os.fstat(descriptor)
                owned(info, stat.S_ISDIR)
                register(prefix, info)
            try:
                info = os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return None
            owned(info, stat.S_ISDIR if directory else stat.S_ISREG)
            register(relative, info, None if directory else regular)
            return info.st_dev, info.st_ino
        finally:
            os.close(descriptor)

    def check_link(relative, descriptor, name, info):
        owned(info, stat.S_ISLNK)
        parts = relative.parts
        text = os.readlink(name, dir_fd=descriptor)
        target = target_path(relative, text)
        if parts == ("wandb", "latest-run"):
            require(len(target.parts) == 2 and target.parts[0] == "wandb" and re.fullmatch(run_pattern, target.parts[1]),
                    "Unexpected SDK latest-run target")
            directory = True
        elif len(parts) == 2 and parts[0] == "wandb" and parts[1] in {"debug.log", "debug-internal.log"}:
            require(len(target.parts) == 4 and target.parts[0] == "wandb" and re.fullmatch(run_pattern, target.parts[1])
                    and target.parts[2:] == ("logs", parts[1]), "Unexpected SDK debug-log target")
            directory = False
        else:
            require(len(parts) == 4 and parts[0] == "wandb" and re.fullmatch(run_pattern, parts[1])
                    and parts[2:] == ("logs", "debug-core.log"), "Unexpected output symlink location")
            require(len(target.parts) == 4 and target.parts[:3] == ("cache", "wandb", "logs")
                    and re.fullmatch(core_pattern, target.parts[-1]), "Unexpected SDK debug-core cache target")
            directory = False
        target_key = inspect_target(target, directory)
        current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        require((info.st_dev, info.st_ino, info.st_mode, info.st_uid) ==
                (current.st_dev, current.st_ino, current.st_mode, current.st_uid)
                and os.readlink(name, dir_fd=descriptor) == text, "SDK link changed during census")
        register(relative, current, links)
        if directory and target_key is not None:
            directory_targets.append(target.as_posix())

    try:
        opened = os.fstat(root_fd)
        require((opened.st_dev, opened.st_ino) == (initial.st_dev, initial.st_ino), "Output root changed before open")
        def walk_error(error):
            raise error
        for directory, dirs, files, descriptor in os.fwalk(".", topdown=True, follow_symlinks=False,
                                                          onerror=walk_error, dir_fd=root_fd):
            relative = PurePosixPath(directory)
            info = os.fstat(descriptor)
            owned(info, stat.S_ISDIR)
            register(relative, info)
            walked.add(relative.as_posix())
            for name in tuple(dirs):
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    check_link(relative / name, descriptor, name, info)
                    dirs.remove(name)
                else:
                    owned(info, stat.S_ISDIR)
            for name in files:
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    check_link(relative / name, descriptor, name, info)
                else:
                    owned(info, stat.S_ISREG)
                    register(relative / name, info, regular)
        require(all(target in walked for target in directory_targets), "SDK run target was not independently walked")
        occurrences = {}
        for key in (*regular.values(), *links.values()):
            occurrences[key] = occurrences.get(key, 0) + 1
        require(all(count == counted[key]["nlink"] for key, count in occurrences.items()),
                "Output inode has an external or changed hard link")
        final = root.lstat()
        require(stat.S_ISDIR(final.st_mode) and final.st_uid == uid and
                (final.st_dev, final.st_ino) == (initial.st_dev, initial.st_ino), "Output root changed during census")
        return sum(row["bytes"] for row in counted.values())
    finally:
        os.close(root_fd)


def query(argv):
    return subprocess.check_output(argv, stdin=subprocess.DEVNULL, text=True, timeout=15)


def inherited_log_bytes(*, exclude_root=None):
    """Count owned regular stdout/stderr files once, without reading content."""
    seen, total = set(), 0
    for number in (1, 2):
        info = os.fstat(number)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            continue
        if exclude_root is not None:
            target = Path(os.readlink(f"/proc/self/fd/{number}"))
            if target.is_absolute() and target.is_relative_to(Path(exclude_root).absolute()):
                continue
        key = info.st_dev, info.st_ino
        if key not in seen:
            seen.add(key)
            total += info.st_size
    return total


def gpu_observation(uuid, *, own_pids=()):
    rows = query(["nvidia-smi", "--query-gpu=uuid,name,driver_version,memory.total,memory.free,memory.used,utilization.gpu",
                  "--format=csv,noheader,nounits"]).splitlines()
    selected = [row.split(",") for row in rows if row.split(",")[0].strip() == uuid]
    if len(selected) != 1:
        raise RuntimeError("Exact physical GPU UUID is absent or ambiguous")
    row = [field.strip() for field in selected[0]]
    applications = query(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory",
                          "--format=csv,noheader,nounits"]).splitlines()
    apps = []
    for line in applications:
        parts = [field.strip() for field in line.split(",")]
        if len(parts) >= 3 and parts[0] == uuid:
            memory = int(parts[2]) * 1024**2 if parts[2].isdecimal() else None
            apps.append({"pid": int(parts[1]), "used_memory_bytes": memory,
                         "own": int(parts[1]) in set(own_pids)})
    return {"captured_unix": time.time(), "uuid": uuid, "name": row[1], "driver_version": row[2],
            "total_bytes": int(row[3]) * 1024**2, "free_bytes": int(row[4]) * 1024**2,
            "used_bytes": int(row[5]) * 1024**2, "utilization_percent": float(row[6]),
            "compute_processes": apps, "foreign_processes": [item for item in apps if not item["own"]]}


def owned_process_observation(root_pid):
    import psutil
    root = psutil.Process(root_pid)
    if root.uids().real != os.getuid():
        raise RuntimeError("Supervisor process owner differs")
    rows = []
    for process in (root, *root.children(recursive=True)):
        try:
            before = process.create_time()
            if process.uids().real != os.getuid():
                raise RuntimeError("A descendant owner differs")
            state = process.status()
            if state == psutil.STATUS_ZOMBIE:
                continue
            rss = process.memory_info().rss
            if process.create_time() != before:
                raise RuntimeError("Process identity changed during resource observation")
            rows.append({"pid": process.pid, "created": before, "rss_bytes": rss,
                         "uid": os.getuid(), "state": state})
        except psutil.NoSuchProcess:
            continue
    return {"processes": rows, "rss_sum_bytes": sum(row["rss_bytes"] for row in rows)}


def bounded_trace_export(profiler, path, *, output_root, output_budget_bytes, reserve_bytes=16 * 1024**2):
    """Set a kernel-enforced per-file ceiling for the remaining trace budget."""
    import resource
    current = owned_output_bytes(output_root)
    remaining = int(output_budget_bytes) - current - reserve_bytes
    if remaining <= 0:
        raise RuntimeError("Insufficient output headroom for a profiler trace")
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    cap = remaining if soft == resource.RLIM_INFINITY else min(remaining, soft)
    resource.setrlimit(resource.RLIMIT_FSIZE, (cap, hard))
    try:
        profiler.export_chrome_trace(str(path))
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
    final = owned_output_bytes(output_root)
    if final > output_budget_bytes - reserve_bytes:
        raise RuntimeError("Trace consumed reserved finalization space")
    return {"per_file_kernel_cap_bytes": cap, "output_bytes_after_trace": final,
            "finalization_reserve_bytes": reserve_bytes}
