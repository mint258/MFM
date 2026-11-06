"""Metadata-only disk protection for explicitly named window-three Slurm jobs.

This observer never restarts a producer or changes scientific inputs. It pauses
only matching processes owned by the configured UID before reserved disk space
or inodes are consumed. The four node observers share one output reservation.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import time

GIB = 1024 ** 3


def required_capacity(check, total_bytes):
    reserve = int(check["reserve_bytes"])
    if check.get("root_filesystem"):
        reserve = max(reserve, 10 * GIB, (int(total_bytes) + 9) // 10)
    return (reserve + int(check["planned_bytes"]),
            int(check["reserve_inodes"]) + int(check["planned_inodes"]))


def inspect_filesystem(check, statvfs=os.statvfs):
    try:
        value = statvfs(check["path"])
        total = value.f_blocks * value.f_frsize
        free = value.f_bavail * value.f_frsize
        if total <= 0 or value.f_files <= 0 or free < 0 or value.f_favail < 0:
            raise ValueError("filesystem capacity or inode capacity is unknown")
        need_bytes, need_inodes = required_capacity(check, total)
        return {"path": check["path"], "total_bytes": total,
                "available_bytes": free, "available_inodes": value.f_favail,
                "required_bytes": need_bytes, "required_inodes": need_inodes,
                "safe": free >= need_bytes and value.f_favail >= need_inodes}
    except (OSError, ValueError) as exc:
        return {"path": check["path"], "safe": False, "unknown": str(exc)}


def matches_job_environment(data, job_id):
    return ("SLURM_JOB_ID=" + str(job_id)).encode() in data.split(b"\0")


def process_identity(pid, job_id, uid, proc_root=Path("/proc")):
    folder = proc_root / str(pid)
    try:
        if folder.stat().st_uid != uid:
            return None
        if not matches_job_environment((folder / "environ").read_bytes(), job_id):
            return None
        stat = (folder / "stat").read_text()
        # The comm field may contain spaces or parentheses. Field 22 is starttime.
        fields = stat[stat.rfind(")") + 2:].split()
        return int(fields[19])
    except (OSError, ValueError, IndexError):
        return None


def job_processes(job_id, uid, proc_root=Path("/proc")):
    result = {}
    for folder in proc_root.iterdir():
        if not folder.name.isdecimal() or int(folder.name) == os.getpid():
            continue
        pid = int(folder.name)
        identity = process_identity(pid, job_id, uid, proc_root)
        if identity is not None:
            result[pid] = identity
    return result


def freeze_job(job_id, uid, proc_root=Path("/proc"), send_signal=os.kill):
    stopped = set()
    # Stop parent PIDs first; repeat discovery to include an already-forking child.
    for _ in range(3):
        for pid, identity in sorted(job_processes(job_id, uid, proc_root).items()):
            key = (pid, identity)
            if key in stopped:
                continue
            if process_identity(pid, job_id, uid, proc_root) != identity:
                continue
            try:
                send_signal(pid, signal.SIGSTOP)
                stopped.add(key)
            except ProcessLookupError:
                pass
    return [{"pid": pid, "start_ticks": ticks} for pid, ticks in sorted(stopped)]


def save_state(path, state):
    path = Path(path)
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(state, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def observe(config, probe=False):
    uid = int(config["uid"])
    if os.getuid() != uid or socket.gethostname().split(".")[0] != config["node"]:
        raise RuntimeError("observer UID or actual target node differs")
    while True:
        targets = job_processes(config["job_id"], uid)
        checks = [inspect_filesystem(check) for check in config["checks"]]
        if config.get('quota_status'):
            from .quota_guard import inspect_quota
            checks.append(inspect_quota(config['quota_status']))
        state = {"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "node": config["node"], "job_id": str(config["job_id"]),
                 "matching_processes": len(targets), "filesystems": checks,
                 "reservation_scope": config["reservation_scope"]}
        safe = all(check["safe"] for check in checks)
        if probe:
            state["state"] = "PREFLIGHT_SAFE" if safe and targets else "PREFLIGHT_NOT_READY"
            print(json.dumps(state), flush=True)
            return 0 if safe and targets else 1
        if not targets:
            state["state"] = "NO_JOB_PROCESSES"
            if safe:
                save_state(config["state_path"], state)
            print(json.dumps(state), flush=True)
            return 0
        if not safe:
            # Preserve native in-flight state. Do not cancel, retry or auto-resume.
            state["state"] = "DISK_WRITE_PAUSED"
            state["stopped_processes"] = freeze_job(config["job_id"], uid)
            # A status update is optional if the output filesystem is unavailable.
            try:
                if os.statvfs(Path(config["state_path"]).parent).f_bavail > 16:
                    save_state(config["state_path"], state)
            except OSError:
                pass
            print(json.dumps(state), flush=True)
            return 2
        state["state"] = "WATCHING"
        save_state(config["state_path"], state)
        time.sleep(float(config["interval_seconds"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    raise SystemExit(observe(json.loads(Path(args.config).read_text()), args.probe))
