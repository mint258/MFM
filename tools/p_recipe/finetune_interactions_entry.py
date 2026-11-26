"""First registered F interactions; no producer replay, refit or bootstrap draws."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint
from finetune_interactions import difference_in_differences


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            path=output/"interactions.json"
            cache=json.loads(path.read_text()) if path.exists() else dict(
                schema="F_PAIRED_MOLECULE_COUNT_INTERACTIONS_V1",comparisons={})
            loaded={}
            for item in c["comparisons"]:
                key=item["subset"]+"/"+item["task"]
                binding={p:fingerprint(p) for p in item["primaries"]}
                if key in cache["comparisons"]:
                    if cache["comparisons"][key]["source_binding"]!=binding:
                        raise ValueError("Closed interaction source changed")
                    continue
                if stop.requested or time.time()+c["work_unit_seconds"]>=float(
                        os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]):
                    atomic_json(path,cache);return 75
                for p in item["primaries"]:
                    if p not in loaded:loaded[p]=json.loads(Path(p).read_text())
                result=difference_in_differences([loaded[p] for p in item["primaries"]],
                    item["conditions"],item["task"])
                if {p:fingerprint(p) for p in binding}!=binding:
                    raise ValueError("Immutable original primary changed during consumption")
                result["source_binding"]=binding
                cache["comparisons"][key]=result;atomic_json(path,cache)
            receipt=dict(status="COMPLETE",job_id=os.environ["SLURM_JOB_ID"],
                comparisons=len(cache["comparisons"]),new_bootstrap_draws=0,
                new_model_fits=0,original_primary_replayed=False)
            atomic_json(output/"primary_complete.json",receipt)
            print(json.dumps(receipt),flush=True);return 0


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--configuration",type=Path,required=True)
    c=json.loads(parser.parse_args().configuration.read_text())
    if c.get("ready") is not True or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only F interaction configuration required")
    raise SystemExit(run(c))
