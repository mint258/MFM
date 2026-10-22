"""INT did not close the two owned prototype jobs; request actual cancellation."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")
CONTROL = ROOT / "control/d3_single_layer_v1"
assert os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi"
prior = CONTROL / "owned_retirement_for_io_revision_v1.json"
assert json.loads(prior.read_text())["status"] == "OWN_METADATA_RETIRED_INT_SENT_TO_TWO_OWN_PROTOTYPE_JOBS"
jobs = json.loads((CONTROL / "jobs.json").read_text())
assert set(jobs) == {"A0_seed0", "A0_seed1"}
record = {"reason": "INT did not stop the two own I/O prototype jobs; validated source-local block revision is ready",
          "prior_intent_sha256": hashlib.sha256(prior.read_bytes()).hexdigest(), "actions": []}
target = CONTROL / "owned_actual_cancellation_for_io_revision_v2.json"
assert not target.exists()
for key, job in jobs.items():
    raw = subprocess.check_output(["scontrol", "show", "job", job["job_id"], "--oneliner"], text=True)
    fields = dict(re.findall(r"(\w+)=([^\s]+)", raw))
    assert fields["UserId"] == "zixiao(1278)" and fields["Command"] == job["script"]
    assert fields["JobName"].startswith("srepair_d3_single_layer_v1_A0")
    command = ["scancel", job["job_id"]]
    action = {"condition": key, "actual_before": raw, "command": command}
    record["actions"].append(action)
    target.write_text(json.dumps({**record, "status": "OWN_CANCELLATION_INTENT"}, indent=2) + "\n")
    result = subprocess.run(command, text=True, capture_output=True)
    action.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    assert result.returncode == 0
record["status"] = "TWO_EXACT_OWN_CANCELLATIONS_REQUESTED_AWAITING_ACTUAL_TERMINAL"
target.write_text(json.dumps(record, indent=2) + "\n")
print(record["status"], flush=True)
