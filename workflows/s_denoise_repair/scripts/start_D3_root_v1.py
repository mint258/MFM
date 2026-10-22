"""Start only this experiment's metadata-only, bounded Slurm coordinator."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")
SOURCE = ROOT / "source_v2"
assert os.getuid() == 1278
phase = ROOT / "control/d3_single_layer_v1"
phase.mkdir(parents=True, exist_ok=True)
receipt = phase / "startup_receipt.json"
assert not receipt.exists(), "This start request was already used"
stream = (ROOT / "logs/D3_root_single_layer_v1.log").open("xb")
process = subprocess.Popen([sys.executable, str(SOURCE / "workflows/s_denoise/d3_root.py"),
    "--plan", str(ROOT / "configs/D3_single_layer_plan_v1.json")],
    stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
    cwd=ROOT.parent.parent, start_new_session=True)
stream.close()
receipt.write_text(json.dumps({"pid": process.pid, "scope": "D3 metadata coordinator only", "full_training_started": False}, indent=2) + "\n")
print(receipt.read_text())
