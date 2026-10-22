"""Retire only the verified own metadata coordinator and its two prototype jobs."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")
CONTROL = ROOT / "control/d3_single_layer_v1"
assert os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi"
identity = json.loads((CONTROL / "identity.json").read_text())
pid = identity["pid"]
script = ROOT / "source_v2/workflows/s_denoise/d3_root.py"
assert hashlib.sha256(script.read_bytes()).hexdigest() == identity["source_sha256"]
assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == identity["boot_id"]
assert Path(f"/proc/{pid}").stat().st_uid == identity["uid"] == 1278
stat = Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()
assert int(stat[19]) == identity["start_ticks"]
argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
assert str(script).encode() in argv
record = {"reason": "validated subset I/O lifecycle improvement; no scientific input change", "identity": identity,
          "source_preserved": True, "scientific_scope_unchanged": True, "job_actions": []}
destination = CONTROL / "owned_retirement_for_io_revision_v1.json"
assert not destination.exists()
destination.write_text(json.dumps({**record, "status": "INTENT_RECORDED"}, indent=2) + "\n")
os.kill(pid, signal.SIGTERM)
for _ in range(50):
    if not Path(f"/proc/{pid}").exists():
        break
    try:
        if Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()[0] == "Z":
            break
    except FileNotFoundError:
        break
    time.sleep(0.2)
else:
    raise RuntimeError("Verified metadata coordinator has not exited")
jobs = json.loads((CONTROL / "jobs.json").read_text())
assert set(jobs) == {"A0_seed0", "A0_seed1"}, "Unexpected new tasks; review before signaling"
for key, job in jobs.items():
    raw = subprocess.check_output(["scontrol", "show", "job", job["job_id"], "--oneliner"], text=True)
    fields = dict(re.findall(r"(\w+)=([^\s]+)", raw))
    assert fields["UserId"] == "zixiao(1278)"
    assert fields["JobName"].startswith("srepair_d3_single_layer_v1_A0")
    assert fields["Command"] == job["script"]
    assert not (ROOT / "diagnostics" / key / ("job_" + job["job_id"]) / "result.json").exists()
    action = {"condition": key, "job_id": job["job_id"], "actual_before": raw,
              "command": ["scancel", "--signal=INT", "--full", job["job_id"]]}
    record["job_actions"].append(action)
    destination.write_text(json.dumps({**record, "status": "SIGNAL_INTENT_RECORDED"}, indent=2) + "\n")
    result = subprocess.run(action["command"], text=True, capture_output=True)
    action["returncode"], action["stdout"], action["stderr"] = result.returncode, result.stdout, result.stderr
    assert result.returncode == 0
record["status"] = "OWN_METADATA_RETIRED_INT_SENT_TO_TWO_OWN_PROTOTYPE_JOBS"
record["partial_training"] = "No final endpoint accepted; committed diagnostic logs and all actual costs retained. Unsaved updates are not merged into the new 4000-update controls."
destination.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"status": record["status"], "jobs": [r["job_id"] for r in record["job_actions"]]}), flush=True)
