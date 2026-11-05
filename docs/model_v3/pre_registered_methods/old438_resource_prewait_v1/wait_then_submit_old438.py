"""Read-only Node0 CPU wait, then ONE unchanged frozen old438 Root submission.

No scientific execution, new admission, retry, rerouting or storage reservation is
implemented here. The original routing-v7 Root/worker guards remain authoritative.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time

B = Path("/share/home/zixiao/descriptor_analysis")
N = B / "runs/model_v3_20261026"
PKG = N / "performance_remaining_Av2_20261029_routing_v7"
SOURCE = N / "performance_old438_resource_prewait_v1_source/wait_then_submit_old438.py"
CONTROL = N / "performance_old438_resource_prewait_v1"
NODE = "compute-0-0"
GPU = "GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332"
KNOWN_HOSTS = Path("/share/home/zixiao/.ssh/known_hosts")
PINS = {"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_remaining_Av2_20261029_routing_v7/source_pins.json","bytes":27165,"sha256":"672c271e56f09f39379ad4992fbbb97e38ed262bbde13e5d57e7914467f73269"}
DRIVER = {"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_remaining_Av2_20261029_routing_v7/Root_submit.py","bytes":18271,"sha256":"92cf19222bcc059c107a6be342af5fb482a619db3cf76ee9134fbdb745090642"}
PLAN = {"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_remaining_Av2_20261029_routing_v7/PLAN.json","bytes":59726,"sha256":"96f76028cabd4e4fcd692746a517a28b5922ba8054190dca2f7ebd676b9c3391"}
PUBLICATION = {"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/canonical_model_v3_delivery_publication_20261029_v1/METHOD_PUBLICATION_WITH_SHARED_POLICY_v1.json","bytes":52011,"sha256":"2858169e09799507e7e550f21fc1807eafa006e9cd24d72ff2b6675869eb2064"}
METHOD_PREFIX = "docs/model_v3/pre_registered_methods/performance_remaining_Av2_20261029_routing_v7/"
NAMES = {"PLAN.json", "METHODS.md", "run_remaining_Av2.sbatch", "Root_submit.py", "source_pins.json"}


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def rawref(path):
    path = Path(path)
    for ancestor in (path, *path.parents):
        need(not ancestor.is_symlink(), "No symlink source/control/trust ancestry")
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 1278 and before.st_nlink == 1
         and 0 < before.st_size <= 2 << 20, "Small owned ordinary metadata/source required")
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
         "Metadata/source changed while read")
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}, raw


def read(reference):
    actual, raw = rawref(reference["path"])
    need(actual == reference, "Frozen raw reference changed")
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "Duplicate metadata key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(RuntimeError("Nonfinite metadata")))


def original_inputs():
    need(rawref(DRIVER["path"])[0] == DRIVER, "Original Root driver changed")
    pins, plan, publication = read(PINS), read(PLAN), read(PUBLICATION)
    need(pins["schema"] == "model_v3_remaining_six_Av2_routing_sources_v2"
         and pins["routing_version"] == 7 and pins["source_directory"] == str(PKG)
         and len(pins["files"]) == 4
         and {Path(item["path"]).name for item in pins["files"]} == NAMES - {"source_pins.json"},
         "Exact original four leaves and pins required")
    for item in pins["files"]:
        need(rawref(item["path"])[0] == item, "Original routing source changed")
    need(plan["routing_version"] == 7 and plan["method_prefix"] == METHOD_PREFIX,
         "Original routing-v7 plan required")
    rows = [row for row in plan["cases"] if row["old_job_id"] == "4520438"]
    need(len(rows) == 1, "One old438 selector required")
    case = rows[0]
    need(case["expected_node"] == NODE and case["gpu_uuid"] == GPU
         and case["expected_gpu"] == "3090" and case["performance_execution_request"] is None
         and case["old500_reused"] is False, "Unchanged original old438 route required")
    need(publication["schema"] == "model_v3_exact_tree_publication_actual_v1"
         and publication["public_branch_readback_verified"] is True
         and publication["public_Git_API_tree_readback_verified"] is True
         and len(publication["files"]) == 111, "Actual sealed 111-blob method publication required")
    published = {item["path"]: item for item in publication["files"]}
    need(len(published) == 111, "No duplicate public method paths")
    for name in NAMES:
        _, raw = rawref(PKG / name)
        item = published[METHOD_PREFIX + name]
        need(item["type"] == "blob"
             and item["sha"] == hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw).hexdigest(),
             "Original routing method differs from its public blob")
    return case


def identity(source):
    command = Path("/proc/self/cmdline").read_bytes()
    tail = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    return dict(pid=os.getpid(), uid=os.getuid(),
                boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                start_ticks=int(tail[19]), pgid=os.getpgid(0), sid=os.getsid(0),
                argv=[part.decode(errors="surrogateescape") for part in command.rstrip(bytes([0])).split(bytes([0]))],
                argv_sha256=hashlib.sha256(command).hexdigest(), source=source,
                source_sha256=source["sha256"], started_unix=time.time())


def status(value, *, fresh=False):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    need(len(raw) <= 128 << 10, "Bounded overwritten status required")
    target = CONTROL / ("identity.json" if fresh else "status.json")
    temporary = CONTROL / ("identity.pending" if fresh else "status.pending")
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    need(not fresh or not target.exists(), "Fresh controller identity required")
    os.replace(temporary, target)


def actual_submission(case):
    path = Path(case["control"]) / "Root_submission_actual_v1.json"
    if not path.exists():
        return {"receipt": None, "first_true_sbatch": None}
    reference = rawref(path)[0]
    value = read(reference)
    need(value["old_job_id"] == "4520438" and value["declared_routing_version"] == 7
         and value["source_package"] == PINS and value["plan"] == PLAN
         and value["Root_driver"] == DRIVER and value["operations_publication"] == PUBLICATION,
         "Original submission receipt lineage differs")
    rows = [row for row in value["observations"] if row.get("argv", [])[:1] == ["sbatch"]]
    need(len(rows) <= 1, "More than one actual sbatch observation")
    first = None
    if rows:
        row = rows[0]
        need(row["argv"] == value["argv"], "Original sbatch argv differs from persisted intent")
        match = re.fullmatch(r"(\d+)(?:;[A-Za-z0-9_.-]+)?", row["stdout"].strip())
        if row["returncode"] == 0 and match:
            first = {"job_id": match[1], "observation": row}
            need(value["job_id"] in (None, match[1]), "Conflicting actual job identity")
    if value["status"] == "SUBMITTED":
        need(first is not None and value["job_id"] == first["job_id"],
             "SUBMITTED without a true sbatch observation")
    return {"receipt": reference, "receipt_status": value["status"], "first_true_sbatch": first}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--deadline-utc", required=True,
                        help="Root fixes one absolute UTC deadline, no more than seven days after launch")
    parser.add_argument("--root-confirm-no-old438-attempt-or-other-coordinator",
                        action="store_true", required=True)
    args = parser.parse_args()
    need(os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi"
         and not os.environ.get("SLURM_JOB_ID"), "Root login metadata only")
    need(Path(__file__).absolute() == SOURCE, "Execute the declared live coordinator only")
    source = rawref(SOURCE)[0]
    need(re.fullmatch("[0-9a-f]{64}", args.source_sha256) is not None
         and source["sha256"] == args.source_sha256, "Actual coordinator source SHA required")
    start = time.time()
    end = datetime.datetime.fromisoformat(args.deadline_utc.replace("Z", "+00:00"))
    need(end.utcoffset() == datetime.timedelta(0), "Explicit UTC deadline required")
    deadline = end.timestamp()
    need(0 < deadline - start <= 7 * 86400, "Finite absolute horizon at most seven days")
    monotonic_deadline = time.monotonic() + deadline - start
    def before_deadline():
        need(time.time() < deadline and time.monotonic() < monotonic_deadline,
             "Absolute seven-day horizon expired; no new submission")
    case = original_inputs()
    family = Path(case["family"])
    need(not family.exists() and not family.is_symlink(),
         "Old438 family/intent/layout exists; Root reconciliation required, no retry")
    CONTROL.mkdir(mode=0o700)  # Fresh namespace; never resume/reuse an old controller.
    fd = os.open(CONTROL / "controller.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    child = None
    common = {"schema": "model_v3_old438_read_only_resource_prewait_v1",
              "deadline_utc": end.isoformat(), "automatic_retry": False,
              "scientific_acceptance": False, "original_method_publication": PUBLICATION}
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        own = identity(source)
        common["identity"] = own
        common["Root_confirmed_no_old438_attempt_or_other_coordinator"] = True
        status({**common, "status": "CONTROLLER_IDENTITY"}, fresh=True)
        while True:
            before_deadline()
            tick = time.monotonic()
            started = time.time()
            argv = ["scontrol", "show", "node", NODE, "-o"]
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, timeout=20)
            finished = time.time()
            need(len(result.stdout) + len(result.stderr) <= 64 << 10,
                 "Bounded read-only node observation required")
            need(result.returncode == 0, "Node observation failed; stop, no retry")
            fields = re.findall(r"\b(NodeName|CPUAlloc|CPUTot|State)=([^\s]+)", result.stdout)
            values = dict(fields)
            need(len(fields) == len(values) == 4 and values["NodeName"] == NODE
                 and all(re.fullmatch(r"\d+", values[key]) for key in ("CPUAlloc", "CPUTot")),
                 "Unknown/ambiguous actual node observation; stop")
            alloc, total = int(values["CPUAlloc"]), int(values["CPUTot"])
            base_state = values["State"].split("+", 1)[0].rstrip("*")
            need(base_state in {"IDLE", "ALLOCATED", "MIXED", "COMPLETING", "RESERVED"}
                 and 0 <= alloc <= total and total > 0
                 and not any(flag in values["State"] for flag in
                             ("DOWN", "DRAIN", "FAIL", "UNKNOWN", "NOT_RESPONDING")),
                 "Unavailable/unknown node state; Root reconciliation required")
            observation = dict(argv=argv, returncode=result.returncode,
                stdout=result.stdout, stderr=result.stderr, started_unix=started,
                finished_unix=finished, elapsed_seconds=time.monotonic() - tick,
                observed_free_CPUs=total - alloc)
            before_deadline()  # Includes the entire observation, never uses stale ready data.
            ready = total - alloc >= 16
            status({**common, "status": "CPU_OBSERVED_READY_NOT_ADMISSION" if ready
                    else "WAITING_FOR_16_ACTUAL_NODE0_CPUS", "observation": observation})
            if ready:
                break
            time.sleep(max(0, min(60 - (time.monotonic() - tick),
                                  deadline - time.time(),
                                  monotonic_deadline - time.monotonic())))
        original_inputs()
        need(rawref(SOURCE)[0] == source, "Coordinator source changed while waiting")
        need(not family.exists() and not family.is_symlink(),
             "Concurrent old438 family/intent appeared; no submission/retry")
        trust = rawref(KNOWN_HOSTS)[0]  # Hash only existing trusted bytes; never print or edit keys.
        command = [case["logical_python"], "-u", "-B", DRIVER["path"], "4520438",
                   "--method-publication", PUBLICATION["path"],
                   "--method-publication-sha256", PUBLICATION["sha256"],
                   "--source-pins-sha256", PINS["sha256"],
                   "--known-hosts-sha256", trust["sha256"]]
        env = {key: value for key, value in os.environ.items() if not key.startswith("SBATCH_")}
        status({**common, "status": "CALLING_ORIGINAL_ROOT_ONCE_NOT_YET_A_JOB",
                "original_argv": command, "existing_trust_reference": trust})
        before_deadline()  # Last check immediately before the sole Popen.
        child = subprocess.Popen(command, cwd=B, env=env, stdin=subprocess.DEVNULL)
        status({**common, "status": "ORIGINAL_ROOT_SINGLE_CALL_LIVE", "child_pid": child.pid,
                "original_argv": command, "existing_trust_reference": trust})
        returncode = child.wait()
        submitted = actual_submission(case)
        need(returncode == 0 and submitted.get("receipt_status") == "SUBMITTED"
             and submitted["first_true_sbatch"] is not None,
             "Original child failed/ambiguous; retain actual receipt, Root reconciliation, no retry")
        status({**common, "status": "ORIGINAL_SINGLE_SBATCH_RECORDED_PENDING_ACTUAL_JOB_CLOSURE",
                "child_pid": child.pid, "child_returncode": returncode, **submitted})
        print(json.dumps({"status": "ONE_ORIGINAL_SUBMISSION_RECORDED",
                          "control": str(CONTROL), **submitted}, sort_keys=True))
    except BaseException as error:
        evidence = {}
        try:
            evidence = actual_submission(case)
        except BaseException as evidence_error:
            evidence = {"receipt_read_error": type(evidence_error).__name__ + ": " + str(evidence_error)}
        status({**common, "status": "STOPPED_ROOT_RECONCILIATION_NO_RETRY",
                "child_pid": None if child is None else child.pid,
                "child_returncode": None if child is None else child.poll(),
                "error": {"type": type(error).__name__, "message": str(error)}, **evidence})
        raise
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
