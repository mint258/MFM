"""F paired comparisons: algebra only on retained primary molecular draws."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time

from finetune_entry import CooperativeStop, set_actual_deadline
from finetune_statistics_entry import require_cpu_admission, fingerprint, atomic_json
from finetune_statistics import paired_contrast


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop)
        require_cpu_admission(c)
        out=Path(c["output"]);out.mkdir(parents=True,exist_ok=True)
        with (out/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            path=out/"contrasts.json"
            cache=json.loads(path.read_text()) if path.exists() else {
                "schema":"F_RETAINED_PAIRED_ALGEBRA_V1","comparisons":{}}
            loaded={}
            for item in c["comparisons"]:
                key=item["left"]+"__minus__"+item["right"]+"/"+item["task"]
                binding={side:fingerprint(item[side+"_primary"]) for side in ("left","right")}
                if key in cache["comparisons"]:
                    if cache["comparisons"][key]["source_binding"]!=binding:
                        raise ValueError("Closed paired comparison input identity changed")
                    continue
                if (stop.requested or time.time()+c["work_unit_seconds"]>=
                        float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])):
                    atomic_json(path,cache)
                    return 75
                for side in ("left","right"):
                    p=item[side+"_primary"]
                    if p not in loaded:
                        loaded[p]=json.loads(Path(p).read_text())
                row=paired_contrast(loaded[item["left_primary"]],item["left"],
                    item["right"],item["task"],right_primary=loaded[item["right_primary"]])
                row["source_binding"]=binding
                cache["comparisons"][key]=row
                atomic_json(path,cache)
            atomic_json(out/"primary_complete.json",dict(status="COMPLETE",
                job_id=os.environ["SLURM_JOB_ID"],comparisons=len(cache["comparisons"]),
                new_bootstrap_draws=0,new_model_fits=0,original_primary_replayed=False))
            print(json.dumps(dict(status="COMPLETE",comparisons=len(cache["comparisons"]),
                                  new_bootstrap_draws=0)),flush=True)
            return 0


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    c=json.loads(p.parse_args().configuration.read_text())
    if c.get("ready") is not True or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only retained-draw configuration required")
    raise SystemExit(run(c))
