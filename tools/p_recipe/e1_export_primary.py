"""Export a new E1 primary once; no prediction/model read or bootstrap replay."""
import argparse,json,os,fcntl
from pathlib import Path
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint

def run(c):
    if c.get("ready") is not True:raise ValueError("Registered export required")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"summary.json").exists():raise ValueError("Closed export must be reused")
            source=Path(c["source"])
            complete=json.loads((source/"primary_complete.json").read_text())
            if complete.get("status")!="COMPLETE" or complete.get("estimator")!="E1_three_seed_point_mean_and_matched_seed_mean_CI":
                raise ValueError("Original E1 seed-mean primary not closed")
            destination=Path(c["destination"]);destination.mkdir(parents=True,exist_ok=True)
            identities={}
            for name in ("primary.json","rows.csv","primary_complete.json"):
                if stop.requested:return 75
                before=fingerprint(source/name);data=(source/name).read_bytes()
                if fingerprint(source/name)!=before:raise ValueError("Primary changed during export")
                target=destination/name
                if target.exists():raise ValueError("Preserve existing export; do not overwrite")
                temporary=target.with_name(target.name+".new")
                with temporary.open("xb") as stream:
                    stream.write(data);stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,target);identities[name]=dict(original=before,destination=str(target))
            atomic_json(output/"summary.json",dict(status="COMPLETE",kind="E1_ORIGINAL_PRIMARY_EXPORT",
                job=os.environ["SLURM_JOB_ID"],source=str(source),files=identities,
                new_predictions=0,new_bootstrap_draws=0))
            return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    args=p.parse_args()
    if os.environ.get("CUDA_VISIBLE_DEVICES")!="":raise ValueError("CPU-only required")
    raise SystemExit(run(json.loads(args.configuration.read_text())))
