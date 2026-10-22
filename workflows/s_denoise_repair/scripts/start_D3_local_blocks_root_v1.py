"""Start only the replacement, bounded metadata coordinator."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")
assert os.getuid()==1278
for job in ["4515533","4515534"]:
    raw=subprocess.check_output(["sacct","-j",job,"--format=JobIDRaw,State,ExitCode","-n","-P"],text=True)
    row=next(r.split("|") for r in raw.splitlines() if r.split("|")[0]==job)
    assert row[1].startswith("CANCELLED"),row
phase=ROOT/"control/d3_local_blocks_v1"
phase.mkdir(parents=True,exist_ok=True)
receipt=phase/"startup_receipt.json"
assert not receipt.exists()
assert (ROOT/"configs/D3_source_binding_v4.json").is_file()
log=(ROOT/"logs/D3_root_local_blocks_v1.log").open("xb")
p=subprocess.Popen([sys.executable,str(ROOT/"source_v3/workflows/s_denoise/d3_root.py"),
    "--plan",str(ROOT/"configs/D3_local_blocks_plan_v1.json")],stdin=subprocess.DEVNULL,stdout=log,
    stderr=subprocess.STDOUT,cwd=ROOT.parent.parent,start_new_session=True)
log.close()
receipt.write_text(json.dumps({"pid":p.pid,"scope":"D3 metadata coordinator only","full_training_started":False,
    "replaces_retired_root":160742,"old_partial_jobs":["4515533","4515534"]},indent=2)+"\n")
print(receipt.read_text())
