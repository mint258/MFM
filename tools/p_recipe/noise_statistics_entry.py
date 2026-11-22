"""CPU-only A1 noise producer; original seed0 points/primary CIs are reused."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import time

from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,fingerprint,atomic_json
from noise_statistics import summarize_noise


def original_points(manifest,summary,csv_path):
    points={t:dict(error=v["error"],E_ref=v["reference_error"],
                  score=v["normalized_improvement"]) for t,v in summary["tasks"].items()}
    expected={key[:-3] for key in manifest["files"] if key.endswith("/R3")}-set(points)
    selected={}
    with Path(csv_path).open() as stream:
        for row in csv.DictReader(stream):
            if (row["run"]==manifest["run"] and int(row["samples"])==manifest["samples"]
                    and row["readout"]=="R3" and row["task"] in expected):
                if row["task"] in selected:
                    raise ValueError("Duplicated original seed0 scalar row")
                selected[row["task"]]=row
    if set(selected)!=expected:
        raise ValueError("Original report-only seed0 scalar row is absent")
    for task,row in selected.items():
        def number(key):
            return float(row[key]) if row[key] else None
        points[task]=dict(error=number("error"),E_ref=number("E_ref"),score=number("score"))
    return points,selected


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop)
        require_cpu_admission(c)
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"primary_complete.json").exists():
                raise ValueError("A1 source statistics already closed; do not repeat")
            source=c["source"]
            seal=json.loads(Path(c["completed_readouts"]).read_text()).get(source["label"])
            if seal is None or seal!=c["sealed_source"]:
                raise ValueError("This source has not sealed all new readout seeds")
            manifests={0:json.loads(Path(seal["seed0"]).read_text())}
            if set(seal["new_seeds"])!={"1","2","3","4"}:
                raise ValueError("Only new readout seeds1-4")
            for seed in range(1,5):
                m=json.loads(Path(seal["new_seeds"][str(seed)]).read_text())
                if (m["readout_seed"]!=seed
                        or m["source_binding"]!=source["source_binding"]):
                    raise ValueError("Readout seed/frozen checkpoint identity changed")
                manifests[seed]=m
            original=manifests[0]
            summary=json.loads(Path(seal["seed0_scores"]).read_text())["R3"]
            points,selected_scalars=original_points(original,summary,c["original_scores_csv"])
            tasks=sorted(points)
            reference_manifest=json.loads(Path(c["reference_manifest"]).read_text())
            files={seed:{task:m["files"][task+"/R3"] for task in tasks}
                   for seed,m in manifests.items()}
            reference_files={task:reference_manifest["files"][task+"/R3"] for task in tasks}
            paths=[seal["seed0"],seal["seed0_scores"],c["reference_manifest"],
                   *seal["new_seeds"].values(),*reference_files.values(),
                   *[path for row in files.values() for path in row.values()]]
            bindings={p:fingerprint(p) for p in sorted(set(paths))}
            identity=dict(files=bindings,source=source,
                original_seed0_points=points,selected_original_CYP_scalar_rows=selected_scalars,
                original_seed0_primary_mean=summary["mean_normalized_improvement"],
                original_primary_bootstrap_ci=summary["bootstrap_ci"])
            import torch
            from phychem_mfm.phase1.v3_dev_evaluation_v2 import _unpack
            torch.set_num_threads(1)
            loaded={}
            def prediction(path):
                if path not in loaded:
                    v=torch.load(path,map_location="cpu",weights_only=False)
                    loaded[path]=_unpack(v["prediction"])
                return loaded[path]
            reference={t:prediction(path) for t,path in reference_files.items()}
            predictions={t:[prediction(files[seed][t]) for seed in range(5)] for t in tasks}
            if {p:fingerprint(p) for p in bindings}!=bindings:
                raise ValueError("Closed prediction/manifest changed during load")
            checkpoint=output/"primary_checkpoint.json"
            state=json.loads(checkpoint.read_text()) if checkpoint.exists() else None
            started=time.time()
            def should_stop():
                return (stop.requested or time.time()+c["work_unit_seconds"]>=
                        float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]))
            result=summarize_noise(predictions,reference,points,summary,
                input_identity=identity,state=state,checkpoint=lambda s:atomic_json(checkpoint,s),
                should_stop=should_stop)
            if result["status"]!="COMPLETE":
                return 75
            rows=[]
            for row in result["rows"]:
                row=dict(source=source["label"],
                    checkpoint_samples=source["source_binding"]["samples"],
                    source_training_budget=source["source_binding"]["source_training_budget"],
                    **row)
                row["error_metric"]=(reference[row["task"]].task.error_metric
                                     if row["task"] in reference else "normalized_seven_task_mean")
                rows.append(row)
            result["rows"]=rows
            atomic_json(output/"primary.json",result)
            tmp=output/"rows.csv.new"
            with tmp.open("w",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
                writer.writeheader();writer.writerows(rows)
                stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,output/"rows.csv")
            proposal=next(r["propose_multiseed_readout"] for r in rows if r["primary_mean"])
            complete=dict(status="COMPLETE",job_id=os.environ["SLURM_JOB_ID"],
                source=source["label"],rows=len(rows),statistics_wall_seconds=time.time()-started,
                seed0_primary_replayed=False,new_model_fits=0,
                reused_original_seed0_primary_intervals=8,
                first_report_only_CYP_seed0_intervals=2,
                bootstrap_samples=1000,bootstrap_seed=20261025,
                propose_future_multiseed_readout_for_user=proposal,
                current_decision_rules_changed=False)
            atomic_json(output/"primary_complete.json",complete)
            print(json.dumps(complete),flush=True)
            return 0


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    c=json.loads(p.parse_args().configuration.read_text())
    if c.get("ready") is not True or c.get("kind")!="A1_STATS" or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated registered A1 CPU configuration required")
    raise SystemExit(run(c))
