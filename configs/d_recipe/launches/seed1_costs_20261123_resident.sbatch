#!/usr/bin/python3 -ISB
#SBATCH --job-name=D-seed1-costs-CPU
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-11
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --signal=B:USR1@180
#SBATCH --no-requeue
#SBATCH --chdir=/
#SBATCH --output=/tmp/d_recipe_managed_D-seed1-costs-CPU_%j.log
_LIFECYCLE_SOURCE = "\"\"\"Own-process cleanup for future D entries; scientific runners stay unchanged.\n\nThis module is inactive until an entry explicitly calls supervise().  It never\nuses SIGKILL.  A kernel-stuck process is reported for administrator recovery.\n\"\"\"\nimport ctypes\nfrom dataclasses import dataclass\nimport os\nfrom pathlib import Path\nimport signal\nimport time\n\n\n@dataclass(frozen=True)\nclass Identity:\n    pid: int\n    start_ticks: int\n    uids: tuple\n    cgroup: str\n    state: str\n\n\ndef identity(pid):\n    try:\n        raw = Path(\"/proc/%d/stat\" % pid).read_text()\n        fields = raw[raw.rfind(\")\") + 2:].split()\n        status = Path(\"/proc/%d/status\" % pid).read_text().splitlines()\n        uids = tuple(int(v) for v in next(\n            line for line in status if line.startswith(\"Uid:\")).split()[1:])\n        return Identity(pid, int(fields[19]), uids,\n                        Path(\"/proc/%d/cgroup\" % pid).read_text(), fields[0])\n    except (FileNotFoundError, ProcessLookupError):\n        return None\n\n\ndef same_process(expected, actual):\n    return (actual is not None and expected.pid == actual.pid\n            and expected.start_ticks == actual.start_ticks\n            and expected.uids == actual.uids)\n\n\ndef owned_scope(record, uid, scope):\n    return (record is not None and record.uids == (uid,) * 4\n            and scope in record.cgroup.splitlines()\n            and record.state not in (\"Z\", \"X\"))\n\n\ndef signal_owned(expected, sig, *, uid, scope):\n    \"\"\"Bind a signal to UID/start_ticks/exact cgroup, using pidfd when present.\"\"\"\n    current = identity(expected.pid)\n    if not same_process(expected, current) or not owned_scope(current, uid, scope):\n        return False\n    if hasattr(os, \"pidfd_open\") and hasattr(signal, \"pidfd_send_signal\"):\n        try:\n            fd = os.pidfd_open(expected.pid, 0)\n        except ProcessLookupError:\n            return False\n        try:\n            current = identity(expected.pid)\n            if not same_process(expected, current) or not owned_scope(current, uid, scope):\n                return False\n            signal.pidfd_send_signal(fd, sig)\n        finally:\n            os.close(fd)\n    else:\n        current = identity(expected.pid)\n        if not same_process(expected, current) or not owned_scope(current, uid, scope):\n            return False\n        try:\n            os.kill(expected.pid, sig)\n        except ProcessLookupError:\n            return False\n    return True\n\n\ndef children(pid):\n    result = set()\n    try:\n        tasks = list(Path(\"/proc/%d/task\" % pid).iterdir())\n    except FileNotFoundError:\n        return result\n    for task in tasks:\n        try:\n            result.update(int(v) for v in (task / \"children\").read_text().split())\n        except FileNotFoundError:\n            continue\n    return result\n\n\ndef descendants(pid):\n    found, pending = {}, list(children(pid))\n    while pending:\n        child = pending.pop()\n        if child in found:\n            continue\n        record = identity(child)\n        if record is None:\n            continue\n        found[child] = record\n        pending.extend(children(child))\n    return found\n\n\ndef enable_subreaper():\n    libc = ctypes.CDLL(None, use_errno=True)\n    if libc.prctl(36, 1, 0, 0, 0) != 0:\n        raise OSError(ctypes.get_errno(), \"PR_SET_CHILD_SUBREAPER failed\")\n\n\ndef reap_adopted(exclude):\n    for pid in children(os.getpid()) - set(exclude):\n        record = identity(pid)\n        if record is not None and record.state not in (\"Z\", \"X\"):\n            continue\n        try:\n            os.waitpid(pid, os.WNOHANG)\n        except ChildProcessError:\n            continue\n\n\ndef slurm_scope(job_id):\n    record = identity(os.getpid())\n    if record is None:\n        raise RuntimeError(\"Own process identity unavailable\")\n    for line in record.cgroup.splitlines():\n        path = line.split(\":\", 2)[-1]\n        if \"/job_%s/\" % job_id in path:\n            return line\n    raise RuntimeError(\"Real Slurm job/step cgroup is required\")\n\n\ndef cleanup_seconds(value):\n    if type(value) is not int or value < 180:\n        raise ValueError(\"Reserve at least180seconds before the real TimeLimit\")\n    return value\n\n\ndef supervise(command, *, end_epoch, scope, grace_seconds=900,\n              request_stop=None, poll_seconds=.25, stop_state=None, report=print):\n    \"\"\"Run once, request a safe boundary, then TERM and reap every owned child.\n\n    end_epoch must come from the actual allocation, or None for UNLIMITED.\n    request_stop may create a cooperative handoff and return its Popen handle;\n    that metadata helper is supervised as well.  A stop returns75, never a\n    successful scientific completion.  An unresolved exit remains supervised\n    and is reported once; it is not declared clean from a batch exit code.\n    \"\"\"\n    import subprocess\n\n    grace = cleanup_seconds(grace_seconds)\n    if not 0 < poll_seconds <= 5:\n        raise ValueError(\"Bounded process-observation interval required\")\n    if end_epoch is not None and end_epoch - time.time() <= grace:\n        raise RuntimeError(\"No work may start inside the cleanup window\")\n    job_id = os.environ.get(\"SLURM_JOB_ID\")\n    if not job_id or scope != slurm_scope(job_id):\n        raise RuntimeError(\"Use the exact current allocation/step scope\")\n    enable_subreaper()\n    uid = os.getuid()\n    if uid == 0:\n        raise RuntimeError(\"D supervisor must run as the actual non-root user\")\n    flags = stop_state if stop_state is not None else {}\n    old_handlers = {}\n    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):\n        old_handlers[sig] = signal.getsignal(sig)\n        signal.signal(sig, lambda received, frame: flags.setdefault(\"signal\", received))\n    root = None\n    helpers, terminated = [], set()\n    stopping = None\n    reported_unresolved = False\n    term_at = None\n    try:\n        root = subprocess.Popen(command, start_new_session=True)\n        while True:\n            now = time.time()\n            root.poll()\n            for helper in helpers:\n                helper.poll()\n            reap_adopted([root.pid] + [p.pid for p in helpers])\n            tree = descendants(os.getpid())\n            active = {pid: rec for pid, rec in tree.items()\n                      if rec.state not in (\"Z\", \"X\")}\n            if stopping is None and (flags or\n                    (end_epoch is not None and now >= end_epoch - grace)):\n                stopping = now\n                reason = (\"SIGNAL_%s\" % flags.get(\"signal\") if flags\n                          else \"ALLOCATION_CLEANUP_WINDOW\")\n                report({\"phase\": \"STOP_DISPATCH_REQUESTED\", \"reason\": reason})\n                if request_stop is not None and root.returncode is None:\n                    helper = request_stop()\n                    if helper is not None:\n                        helpers.append(helper)\n                # TERM/INT can be followed by a short site KillWait.  Deadline\n                # or USR1 gives the full preregistered cleanup reservation.\n                immediate = flags.get(\"signal\") in (signal.SIGTERM, signal.SIGINT)\n                term_at = (now + 10 if immediate else\n                           (end_epoch - max(180, grace // 3)\n                            if end_epoch is not None else now + grace * 2 / 3))\n                if request_stop is None:\n                    term_at = now\n            # A normal runner must not leave stopped/orphaned descendants.\n            if root.returncode is not None and term_at is None:\n                term_at = now\n            if term_at is not None and now >= term_at:\n                for pid, rec in active.items():\n                    key = (pid, rec.start_ticks)\n                    if key in terminated:\n                        continue\n                    if signal_owned(rec, signal.SIGTERM, uid=uid, scope=scope):\n                        terminated.add(key)\n                        report({\"phase\": \"OWNED_TERM\", \"pid\": pid,\n                                \"start_ticks\": rec.start_ticks})\n                        # Let a stopped worker consume its pending TERM; do\n                        # not resume it in advance of the exit request.\n                        if rec.state in (\"T\", \"t\"):\n                            signal_owned(rec, signal.SIGCONT, uid=uid, scope=scope)\n            root.poll()\n            for helper in helpers:\n                helper.poll()\n            reap_adopted([root.pid] + [p.pid for p in helpers])\n            remaining = descendants(os.getpid())\n            if (root.returncode is not None and\n                    all(p.returncode is not None for p in helpers) and\n                    not remaining):\n                report({\"phase\": \"OWNED_TREE_REAPED\", \"root\": root.pid,\n                        \"root_returncode\": root.returncode})\n                return 75 if stopping is not None else root.returncode\n            if (end_epoch is not None and now >= end_epoch - 180\n                    and not reported_unresolved):\n                reported_unresolved = True\n                report({\"phase\": \"ADMIN_REQUIRED_EXIT_NOT_PROVEN\",\n                        \"pids\": sorted(remaining), \"no_SIGKILL\": True})\n            time.sleep(poll_seconds)\n    finally:\n        # Do not hide a failed control path or leave a descendant from an\n        # exception. Keep supervising after one TERM while the parent can reap.\n        if root is not None:\n            while True:\n                for rec in descendants(os.getpid()).values():\n                    key = (rec.pid, rec.start_ticks)\n                    if key not in terminated and owned_scope(rec, uid, scope):\n                        if signal_owned(rec, signal.SIGTERM, uid=uid, scope=scope):\n                            terminated.add(key)\n                            if rec.state in (\"T\", \"t\"):\n                                signal_owned(rec, signal.SIGCONT, uid=uid, scope=scope)\n                root.poll()\n                for helper in helpers:\n                    helper.poll()\n                reap_adopted([root.pid] + [p.pid for p in helpers])\n                if (root.returncode is not None\n                        and all(p.returncode is not None for p in helpers)\n                        and not descendants(os.getpid())):\n                    break\n                time.sleep(poll_seconds)\n        for sig, handler in old_handlers.items():\n            signal.signal(sig, handler)\n\n"
_WORKER_COMMAND = ["/bin/bash","-c","set -euo pipefail\ncd /share/home/zixiao/descriptor_analysis/MFM_d_recipe\nexport CUDA_VISIBLE_DEVICES=''\nexec /share/home/zixiao/.conda/envs/chemprop/bin/python -B -c 'import csv,json,math,statistics\nfrom pathlib import Path\nfrom tools.d_recipe.resources import DJointGuard,execution_site\nfrom tools.d_recipe.train import publish_summary\nc=json.loads(\"{\\\"output\\\":\\\"/share/home/zixiao/descriptor_analysis/MFM_d_recipe/results/d_recipe\\\",\\\"output_filesystem\\\":\\\"/share\\\",\\\"storage_peak_bytes\\\":42074762973,\\\"peer_storage_guard_root\\\":\\\"/share/home/zixiao/descriptor_analysis/MFM_p_heads_20261117\\\",\\\"local_concurrent_bytes\\\":38788923392,\\\"execution\\\":\\\"Slurm\\\"}\")\nentries=json.loads(\"[{\\\"arm\\\":\\\"D-R0\\\",\\\"run\\\":\\\"d_recipe_20261120_D_R0_seed0_3M_seed1\\\",\\\"job_id\\\":4538566,\\\"elapsed_seconds\\\":39014,\\\"allocated_CPUs\\\":5,\\\"TotalCPU_raw\\\":\\\"00:00:00\\\",\\\"training_seconds\\\":38099.351692557335,\\\"gpu_uuid\\\":\\\"GPU-6965a7c7-025e-e4fd-013a-2be3245ef7c6\\\"},{\\\"arm\\\":\\\"D-R1\\\",\\\"run\\\":\\\"d_recipe_20261120_D_R1_seed0_3M_seed1\\\",\\\"job_id\\\":4538567,\\\"elapsed_seconds\\\":38604,\\\"allocated_CPUs\\\":5,\\\"TotalCPU_raw\\\":\\\"00:00:00\\\",\\\"training_seconds\\\":38135.12057595514,\\\"gpu_uuid\\\":\\\"GPU-dac07d74-6269-c7db-8832-340dd3c0b377\\\"}]\")\nexecution_site(c,cpu=True)\nDJointGuard(c)\nroot=Path(\"/share/home/zixiao/descriptor_analysis/MFM_d_recipe\")\nfor item in entries:\n source=root/\"results/d_recipe/training\"/item[\"run\"]/\"gpu_telemetry.csv\"\n with source.open(newline=\"\") as stream:rows=list(csv.DictReader(stream))\n watts=[];missing=0\n for row in rows:\n  if row[\"run\"]!=item[\"run\"] or row[\"gpu_uuid\"]!=item[\"gpu_uuid\"]:raise ValueError(\"Telemetry source belongs to another run/card\")\n  try:p=float(row[\"power_watts\"])\n  except (ValueError,TypeError):missing+=1;continue\n  if not math.isfinite(p):missing+=1;continue\n  watts.append(p)\n result=dict(item,schema=\"D_NATIVE_GPU_COST_V1\",state=\"COMPLETED\",exit_code=\"0:0\",\n  seed=1,samples=3000000,gpu_model=rows[0][\"gpu_name\"] if rows else None,target_one_GPU_job_wall_hours=item[\"elapsed_seconds\"]/3600,\n  allocated_CPU_hours=item[\"elapsed_seconds\"]*item[\"allocated_CPUs\"]/3600,\n  training_loop_including_fixed_VAL_samples_per_second=3000000/item[\"training_seconds\"],\n  whole_card_power_watts_sample_mean=statistics.mean(watts) if watts else None,\n  power_samples=len(watts),power_missing_samples=missing,power_source=str(source),\n  power_scope=\"Arithmetic mean of original whole-card samples recorded while 0<samples<training_budget; includes the sampled training-active window, excludes final GPU readout under the original sampler condition\",\n  power_weighting=\"Native point-sample mean; not a time-integrated energy or attributed device-only measurement\",\n  TotalCPU_seconds=None,TotalCPU_available=False,TotalCPU_reason=\"Parent TotalCPU is zero/unreported at this site; do not report it as measured zero training CPU\",\n  Slurm_accounting_scope=\"Original parent allocation only; no queue, batch/extern or observation step is added twice\",\n  source_function=\"tools/p_recipe/native_run.py:record_gpu_telemetry\",\n  scientific_metrics_recomputed=False)\n destination=root/\"results/d_recipe\"/(item[\"arm\"]+\"_seed1_complete_GPU_job_costs_20261123.json\")\n publish_summary(destination,result,c)\n print(json.dumps(result),flush=True)\n'"]
_CHILD_ENV = {"PYTHONDONTWRITEBYTECODE":"1","PYTHONIOENCODING":"utf-8","PYTHONPATH":"/share/home/zixiao/descriptor_analysis/MFM_d_recipe:/share/home/zixiao/descriptor_analysis/MFM_d_recipe/current:/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120:/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120/current:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps","PATH":"/usr/bin:/bin:/usr/sbin:/sbin:/share/apps/softwares/anaconda3/bin:/share/apps/softwares/anaconda3/condabin:/share/home/zixiao/.local/bin:/share/home/zixiao/bin:/share/apps/bin:/usr/share/Modules/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/sbin:/share/apps/software/anaconda/bin:/share/apps/scripts:/share/apps/software/anaconda/bin:/share/apps/scripts","OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1","NUMEXPR_NUM_THREADS":"1"}
_ALLOWED_NODES = ["compute-0-11"]
_CLEANUP_SECONDS = 180
_ROOT_FUTURE_BYTES = 38788923392
_COOPERATIVE = False
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import time
import types

_exit = types.ModuleType("d_resident_exit")
sys.modules[_exit.__name__] = _exit
exec(compile(_LIFECYCLE_SOURCE, "<resident-exit-lifecycle>", "exec"),
     _exit.__dict__)
_job = os.environ.get("SLURM_JOB_ID")
if not _job:
    raise RuntimeError("A real Slurm allocation is required")
_scope = _exit.slurm_scope(_job)
_exit.enable_subreaper()
_stop = {}
for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
    signal.signal(_sig, lambda received, frame: _stop.setdefault("signal", received))


def _query(arguments):
    process = subprocess.Popen(arguments, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    bound = _exit.identity(process.pid)
    until = time.monotonic() + 10
    interrupted = False
    while True:
        try:
            out, error = process.communicate(timeout=.2)
            break
        except subprocess.TimeoutExpired:
            if _stop or time.monotonic() >= until:
                interrupted = True
                if bound is not None:
                    _exit.signal_owned(bound, signal.SIGTERM,
                                       uid=os.getuid(), scope=_scope)
                # Do not orphan or declare an unproven control query cleaned.
                try:
                    out, error = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    print(json.dumps(dict(phase="ADMIN_REQUIRED_RESIDENT_QUERY",
                                          pid=process.pid)), flush=True)
                    out, error = process.communicate()
                break
    if interrupted or process.returncode:
        raise RuntimeError("Resident Slurm query did not close normally: "
                           + error.decode("utf-8", "replace")[:500])
    return dict(re.findall(r"(\w+)=(\S+)", out.decode("utf-8", "replace")))


_record = _query(["/usr/bin/scontrol", "show", "job", _job, "-o"])
if (_record.get("JobId") != _job
        or _record.get("TimeLimit") in (None, "UNLIMITED", "NOT_SET", "N/A")
        or _record.get("EndTime") in (None, "Unknown", "N/A", "None")):
    raise RuntimeError("Actual finite allocation deadline must be known")
_end = datetime.datetime.fromisoformat(_record["EndTime"]).timestamp()
_node = os.uname().nodename.split(".")[0]
_health = _query(["/usr/bin/scontrol", "show", "node", _node, "-o"])
_state = _health.get("State", "").upper()
if (_health.get("NodeName") != _node or not _state
        or any(value in _state for value in
               ("DRAIN", "DOWN", "NOT_RESPOND", "NO_RESPOND", "UNKNOWN", "FAIL"))):
    raise RuntimeError("Actual node health is not admitted")
if _ALLOWED_NODES and _node not in _ALLOWED_NODES:
    raise RuntimeError("Actual node differs from the registered target")
_root = os.statvfs("/")
if os.stat("/tmp").st_dev != os.stat("/").st_dev:
    raise RuntimeError("Register a separate /tmp filesystem before this entry")
_system = max(10 * 2**30, (_root.f_blocks * _root.f_frsize + 9) // 10)
if (_root.f_bavail * _root.f_frsize < _system + _ROOT_FUTURE_BYTES
        or _root.f_favail < 10000):
    raise RuntimeError("Actual root reserve, future or inode allowance unavailable")
_exit.cleanup_seconds(_CLEANUP_SECONDS)
if _end - time.time() <= _CLEANUP_SECONDS:
    raise RuntimeError("No work may start in the cleanup window")
for _name, _value in _CHILD_ENV.items():
    os.environ[_name] = _value
os.environ["D_EXIT_OUTER_SUPERVISION"] = "1"
os.environ["D_RESIDENT_SUPERVISOR_PID"] = str(os.getpid())
os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"] = str(
    _exit.identity(os.getpid()).start_ticks)
print(json.dumps(dict(phase="RESIDENT_BEFORE_SHARED_SOURCE", job_id=_job,
                      node=_node, TimeLimit=_record["TimeLimit"],
                      EndTime=_record["EndTime"],
                      root_available_bytes=_root.f_bavail * _root.f_frsize,
                      root_inodes=_root.f_favail,
                      source_independent=True)), flush=True)


def _cooperative_stop():
    # Only the direct managed child is asked to save/exit. A child still
    # loading shared Python code has no workers or committed training yet.
    for pid in _exit.children(os.getpid()):
        current = _exit.identity(pid)
        if current is not None:
            _exit.signal_owned(current, signal.SIGUSR1,
                               uid=os.getuid(), scope=_scope)


_result = _exit.supervise(
    _WORKER_COMMAND, end_epoch=_end, scope=_scope,
    grace_seconds=_CLEANUP_SECONDS, stop_state=_stop,
    request_stop=_cooperative_stop if _COOPERATIVE else None,
    report=lambda event: print(json.dumps(event), flush=True))
print(json.dumps(dict(phase="RESIDENT_TERMINAL", job_id=_job,
                      returncode=_result,
                      remaining_children=sorted(_exit.children(os.getpid())))),
      flush=True)
raise SystemExit(128 - _result if _result < 0 else _result)
