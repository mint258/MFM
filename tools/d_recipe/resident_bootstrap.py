"""Render a Slurm-copied supervisor before any shared-source import.

This renderer submits nothing and changes no scientific worker. The resulting
script starts the system Python directly, so shell startup and shared module
loading are both inside the supervised child. All array work stays original.
"""
import os

_BOOTSTRAP = "import datetime\nimport json\nimport os\nimport re\nimport signal\nimport subprocess\nimport sys\nimport time\nimport types\n\n_exit = types.ModuleType(\"d_resident_exit\")\nsys.modules[_exit.__name__] = _exit\nexec(compile(_LIFECYCLE_SOURCE, \"<resident-exit-lifecycle>\", \"exec\"),\n     _exit.__dict__)\n_job = os.environ.get(\"SLURM_JOB_ID\")\nif not _job:\n    raise RuntimeError(\"A real Slurm allocation is required\")\n_scope = _exit.slurm_scope(_job)\n_exit.enable_subreaper()\n_stop = {}\nfor _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):\n    signal.signal(_sig, lambda received, frame: _stop.setdefault(\"signal\", received))\n\n\ndef _query(arguments):\n    process = subprocess.Popen(arguments, stdout=subprocess.PIPE,\n                               stderr=subprocess.PIPE)\n    bound = _exit.identity(process.pid)\n    until = time.monotonic() + 10\n    interrupted = False\n    while True:\n        try:\n            out, error = process.communicate(timeout=.2)\n            break\n        except subprocess.TimeoutExpired:\n            if _stop or time.monotonic() >= until:\n                interrupted = True\n                if bound is not None:\n                    _exit.signal_owned(bound, signal.SIGTERM,\n                                       uid=os.getuid(), scope=_scope)\n                # Do not orphan or declare an unproven control query cleaned.\n                try:\n                    out, error = process.communicate(timeout=5)\n                except subprocess.TimeoutExpired:\n                    print(json.dumps(dict(phase=\"ADMIN_REQUIRED_RESIDENT_QUERY\",\n                                          pid=process.pid)), flush=True)\n                    out, error = process.communicate()\n                break\n    if interrupted or process.returncode:\n        raise RuntimeError(\"Resident Slurm query did not close normally: \"\n                           + error.decode(\"utf-8\", \"replace\")[:500])\n    return dict(re.findall(r\"(\\w+)=(\\S+)\", out.decode(\"utf-8\", \"replace\")))\n\n\n_record = _query([\"/usr/bin/scontrol\", \"show\", \"job\", _job, \"-o\"])\nif (_record.get(\"JobId\") != _job\n        or _record.get(\"TimeLimit\") in (None, \"UNLIMITED\", \"NOT_SET\", \"N/A\")\n        or _record.get(\"EndTime\") in (None, \"Unknown\", \"N/A\", \"None\")):\n    raise RuntimeError(\"Actual finite allocation deadline must be known\")\n_end = datetime.datetime.fromisoformat(_record[\"EndTime\"]).timestamp()\n_node = os.uname().nodename.split(\".\")[0]\n_health = _query([\"/usr/bin/scontrol\", \"show\", \"node\", _node, \"-o\"])\n_state = _health.get(\"State\", \"\").upper()\nif (_health.get(\"NodeName\") != _node or not _state\n        or any(value in _state for value in\n               (\"DRAIN\", \"DOWN\", \"NOT_RESPOND\", \"NO_RESPOND\", \"UNKNOWN\", \"FAIL\"))):\n    raise RuntimeError(\"Actual node health is not admitted\")\nif _ALLOWED_NODES and _node not in _ALLOWED_NODES:\n    raise RuntimeError(\"Actual node differs from the registered target\")\n_root = os.statvfs(\"/\")\nif os.stat(\"/tmp\").st_dev != os.stat(\"/\").st_dev:\n    raise RuntimeError(\"Register a separate /tmp filesystem before this entry\")\n_system = max(10 * 2**30, (_root.f_blocks * _root.f_frsize + 9) // 10)\nif (_root.f_bavail * _root.f_frsize < _system + _ROOT_FUTURE_BYTES\n        or _root.f_favail < 10000):\n    raise RuntimeError(\"Actual root reserve, future or inode allowance unavailable\")\n_exit.cleanup_seconds(_CLEANUP_SECONDS)\nif _end - time.time() <= _CLEANUP_SECONDS:\n    raise RuntimeError(\"No work may start in the cleanup window\")\nfor _name, _value in _CHILD_ENV.items():\n    os.environ[_name] = _value\nos.environ[\"D_EXIT_OUTER_SUPERVISION\"] = \"1\"\nos.environ[\"D_RESIDENT_SUPERVISOR_PID\"] = str(os.getpid())\nos.environ[\"D_RESIDENT_SUPERVISOR_START_TICKS\"] = str(\n    _exit.identity(os.getpid()).start_ticks)\nprint(json.dumps(dict(phase=\"RESIDENT_BEFORE_SHARED_SOURCE\", job_id=_job,\n                      node=_node, TimeLimit=_record[\"TimeLimit\"],\n                      EndTime=_record[\"EndTime\"],\n                      root_available_bytes=_root.f_bavail * _root.f_frsize,\n                      root_inodes=_root.f_favail,\n                      source_independent=True)), flush=True)\n\n\ndef _cooperative_stop():\n    # Only the direct managed child is asked to save/exit. A child still\n    # loading shared Python code has no workers or committed training yet.\n    for pid in _exit.children(os.getpid()):\n        current = _exit.identity(pid)\n        if current is not None:\n            _exit.signal_owned(current, signal.SIGUSR1,\n                               uid=os.getuid(), scope=_scope)\n\n\n_result = _exit.supervise(\n    _WORKER_COMMAND, end_epoch=_end, scope=_scope,\n    grace_seconds=_CLEANUP_SECONDS, stop_state=_stop,\n    request_stop=_cooperative_stop if _COOPERATIVE else None,\n    report=lambda event: print(json.dumps(event), flush=True))\nprint(json.dumps(dict(phase=\"RESIDENT_TERMINAL\", job_id=_job,\n                      returncode=_result,\n                      remaining_children=sorted(_exit.children(os.getpid())))),\n      flush=True)\nraise SystemExit(128 - _result if _result < 0 else _result)\n"


def render_sbatch(command, lifecycle_source, *, directives=(), child_environment=None,
                  allowed_nodes=(), cleanup_seconds=900,
                  root_future_bytes=16 * 2**30 + 128 * 2**20,
                  cooperative=False):
    if (not isinstance(command, (list, tuple)) or not command
            or any(not isinstance(v, str) or not v for v in command)
            or not os.path.isabs(command[0])):
        raise ValueError("An absolute argv command is required")
    if type(cleanup_seconds) is not int or cleanup_seconds < 180:
        raise ValueError("Reserve at least180seconds of the real allocation")
    if type(root_future_bytes) is not int or root_future_bytes < 0:
        raise ValueError("Register the target's joint root future")
    if not isinstance(lifecycle_source, str) or not lifecycle_source:
        raise ValueError("Embed the exact reviewed lifecycle source")
    if any(not isinstance(v, str) or not v.startswith("#SBATCH ")
           or "\n" in v or "\r" in v for v in directives):
        raise ValueError("One literal Slurm directive per line")
    environment = dict(child_environment or {})
    if any(not isinstance(k, str) or not isinstance(v, str)
           or "=" in k or "\x00" in k or "\x00" in v
           for k, v in environment.items()):
        raise ValueError("Use literal string environment values")
    values = {
        "_LIFECYCLE_SOURCE": lifecycle_source,
        "_WORKER_COMMAND": list(command),
        "_CHILD_ENV": environment,
        "_ALLOWED_NODES": list(allowed_nodes),
        "_CLEANUP_SECONDS": cleanup_seconds,
        "_ROOT_FUTURE_BYTES": root_future_bytes,
        "_COOPERATIVE": bool(cooperative),
    }
    assignments = "\n".join(key + " = " + repr(value) for key, value in values.items())
    return ("#!/usr/bin/python3 -ISB\n" + "\n".join(directives)
            + "\n" + assignments + "\n" + _BOOTSTRAP)
