"""First CPU-only A3 fixed-VAL summaries and the preregistered I2 condition."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import time
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"primary_complete.json").exists():
                raise ValueError("Closed A3 primary must not be repeated")
            source=Path(c["forward_summary"]);before=fingerprint(source)
            summary=json.loads(source.read_text())
            if (summary["status"]!="COMPLETE" or summary["source_count"]!=4
                    or summary["fixed_VAL_molecules"]!=2000):
                raise ValueError("All four original VAL forward sources must close")
            from penalty_statistics import summarize_batches,intervention_condition
            rows=[];bindings={str(source):before}
            for label in ["T2_1M","T2_3M","T2_6M","T2_9M"]:
                if stop.requested:return 75
                path=summary["sources"][label];bound=fingerprint(path)
                state=json.loads(Path(path).read_text())
                if state.get("complete") is not True:raise ValueError("Source batch cursor not closed")
                binding=state["identity"]["source"]["source_binding"]
                row=summarize_batches(state["rows"],state["fixed_indices"],32)
                rows.append(dict(source=label,checkpoint_samples=binding["samples"],
                    source_training_budget=binding["source_training_budget"],**row))
                bindings[path]=bound
            if {p:fingerprint(p) for p in bindings}!=bindings:
                raise ValueError("Closed A3 native inputs changed during load")
            trigger=intervention_condition(rows)
            atomic_json(output/"primary.json",dict(status="COMPLETE",rows=rows,
                I2_condition=trigger,input_identity=bindings,new_model_forwards=0,
                bootstrap_draws=0,current_recipe_changed=False))
            temp=output/"rows.csv.new"
            with temp.open("w",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader()
                writer.writerows(rows);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,output/"rows.csv")
            receipt=dict(status="COMPLETE",job_id=os.environ["SLURM_JOB_ID"],
                         rows=len(rows),I2_condition=trigger,new_model_forwards=0,
                         new_training=False,statistics_precision="F64")
            atomic_json(output/"primary_complete.json",receipt)
            print(json.dumps(receipt),flush=True);return 0


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--configuration",type=Path,required=True)
    c=json.loads(parser.parse_args().configuration.read_text())
    if c.get("ready") is not True or c.get("kind")!="A3_STATS" or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only A3 configuration required")
    raise SystemExit(run(c))
