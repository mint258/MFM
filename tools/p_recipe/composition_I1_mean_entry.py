"""I1 and own-budget F2 mean(H); unchanged frozen definitions and weights."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import time
from finetune_entry import CooperativeStop, set_actual_deadline
from finetune_statistics_entry import require_cpu_admission, atomic_json, fingerprint


def atomic_npz(path, **arrays):
    import numpy as np
    temporary = path.with_name(path.name+".new")
    with temporary.open("wb") as stream:
        np.savez(stream, **arrays); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def atomic_array(path, array):
    import numpy as np
    temporary = path.with_name(path.name+".new")
    with temporary.open("wb") as stream:
        np.save(stream, array, allow_pickle=False); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_rows(path, rows):
    temporary = path.with_name(path.name+".new")
    with temporary.open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary,path)


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop); require_cpu_admission(c)
        output=Path(c["output"]); output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"primary_complete.json").exists():
                raise ValueError("Closed composition primary must be reused")
            import numpy as np
            from composition_statistics import (ridge_oof,
                cev_values,cvf_values,summary)
            from composition_mean_statistics import participation_ratio
            forward_path=Path(c["forward_summary"])
            forward=json.loads(forward_path.read_text())
            if (forward["status"]!="COMPLETE" or forward["source_count"]!=2
                    or forward["layer"]!=6 or forward["molecules"]!=5000):
                raise ValueError("Exactly the I1 and own-budget F2 L6 sources required")
            sources=c["sources"]
            if set(forward["sources"])!={s["label"] for s in sources}:
                raise ValueError("Forward source set differs from registered statistics")
            with np.load(c["panel"],allow_pickle=False) as p:
                X=p["X"].copy(); first=p["first"].copy(); owners=p["owners"].copy()
            if X.shape[0]!=5000 or len(first)!=5000:
                raise ValueError("Original fixed5000 panel required")
            cutoff=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
            def should_stop():
                return stop.requested or time.time()+c["work_unit_seconds"]>=cutoff
            binding=dict(forward=fingerprint(forward_path),panel=fingerprint(c["panel"]),
                original_statistics_blob=c["original_statistics_blob"],weights=fingerprint(c["weights"]))
            identity_path=output/"input_identity.json"
            if identity_path.exists():
                if json.loads(identity_path.read_text())!=binding:
                    raise ValueError("Closed panel/forward identity changed")
            else:atomic_json(identity_path,binding)
            weight_path=Path(c["weights"])
            if not weight_path.is_file():raise ValueError("Original paired weights required")
            weights=np.load(weight_path,allow_pickle=False)
            if weights.shape!=(1001,5000) or weights.dtype!=np.float64:
                raise ValueError("Original1000 paired molecular F64 draws required")
            expected={"F2_3M","I1_3M"}
            if {x["label"] for x in sources}!=expected or any(x["source_binding"]["arm"]!={"F2_3M":"F2","I1_3M":"I1"}[x["label"]] or x["source_binding"]["source_training_budget"]!=3000000 for x in sources):
                raise ValueError("Only the registered own-budget3M baseline and I1 are permitted")
            rows=[];retained={}
            for source in sources:
                if should_stop():return 75
                label=source["label"];source_dir=Path(forward["sources"][label]).parent
                source_state=json.loads((source_dir/"cursor.json").read_text())
                if source_state.get("complete") is not True or source_state["record_cursor"]!=forward["records"]:
                    raise ValueError("Source feature cursor not complete")
                if source_state["identity"]["source"]!=source:
                    raise ValueError("Statistics source differs from immutable forward")
                means_path=source_dir/"means.npy"
                identity=dict(source=source,mean=fingerprint(means_path),panel=binding["panel"])
                directory=output/label; directory.mkdir(exist_ok=True)
                state_path=directory/"statistics.json"
                state=json.loads(state_path.read_text()) if state_path.exists() else dict(
                    identity=identity,PR=[],base_summary=None)
                if state["identity"]!=identity:
                    raise ValueError("Saved statistics source identity changed")
                base_path=directory/"base_draws.npz"
                if state["base_summary"] is None:
                    means=np.load(means_path,mmap_mode="r",allow_pickle=False)
                    y=np.asarray(means[first],np.float64)
                    prediction_path=directory/"OOF_prediction.npy"
                    alpha_path=directory/"OOF_complete.json"
                    if alpha_path.exists():
                        seal=json.loads(alpha_path.read_text())
                        if seal["identity"]!=identity or seal["prediction"]!=fingerprint(prediction_path):
                            raise ValueError("Closed OOF prediction binding differs")
                        prediction=np.load(prediction_path,allow_pickle=False)
                    else:
                        prediction,alphas=ridge_oof(X,y)
                        atomic_array(prediction_path,prediction)
                        atomic_json(alpha_path,dict(identity=identity,
                            prediction=fingerprint(prediction_path),selected_alphas=alphas))
                    if should_stop():return 75
                    if base_path.exists():
                        with np.load(base_path,allow_pickle=False) as stored:
                            base={k:stored[k].copy() for k in ["CEV","CVF","CVF_res"]}
                    else:
                        cev=cev_values(y,prediction,weights)
                        cvf,res=cvf_values(np.asarray(means,np.float64),owners,prediction,weights)
                        base=dict(CEV=cev,CVF=cvf,CVF_res=res)
                    metrics={k:summary(v) for k,v in base.items()}
                    del means,y,prediction
                    atomic_npz(base_path,**base)
                    state["base_summary"]=metrics; atomic_json(state_path,state)
                else:
                    with np.load(base_path,allow_pickle=False) as stored:
                        base={k:stored[k].copy() for k in ["CEV","CVF","CVF_res"]}
                means=np.load(means_path,mmap_mode="r",allow_pickle=False)
                y=np.asarray(means[first],np.float64)
                while len(state["PR"])<1001:
                    if should_stop():return 75
                    begin=len(state["PR"]);end=min(1001,begin+50)
                    for w in weights[begin:end]:
                        value=participation_ratio(y,w)
                        state["PR"].append(float(value) if np.isfinite(value) else None)
                    atomic_json(state_path,state)
                    print(json.dumps(dict(source=label,PR_draws_completed=end-1)),flush=True)
                if "PR" not in state["base_summary"]:
                    state["base_summary"]["PR"]=summary(np.asarray([
                        np.nan if v is None else v for v in state["PR"]],np.float64))
                    state["complete"]=True;atomic_json(state_path,state)
                if fingerprint(means_path)!=identity["mean"]:
                    raise ValueError("Immutable features changed while consumed")
                retained[label]=dict(base_draws=str(base_path),statistics=str(state_path))
                row=dict(source=label,samples=source["source_binding"]["samples"],
                    source_training_budget=source["source_binding"]["source_training_budget"],
                    representation="mean(H)",layer=6,molecules=5000,records=forward["records"])
                for metric,values in state["base_summary"].items():
                    row[metric]=values["value"]
                    row[metric+"_CI_low"]=None if values["ci95"] is None else values["ci95"][0]
                    row[metric+"_CI_high"]=None if values["ci95"] is None else values["ci95"][1]
                rows.append(row);del means,y
            atomic_json(output/"primary.json",dict(status="COMPLETE",rows=rows,
                retained=retained,input_identity=binding,weights=fingerprint(weight_path),
                I1_baseline_only=True,old_eight_mean_primaries_recomputed=False,
                original_M1_three_primaries_reused=False,atomic_metrics_pending=True,
                frozen_recipe_changed=False))
            write_rows(output/"rows.csv",rows)
            receipt=dict(status="COMPLETE",job_id=os.environ["SLURM_JOB_ID"],
                rows=2,new_OOF_sources=2,original_M1_three_primaries_reused=False,
                layer=6,representation="mean(H)",bootstrap_seed=20261025,
                repetitions=1000,unit="molecule",precision="F64",
                new_bootstrap_weight_generations=0,atomic_metrics_pending=True,
                I1_baseline_paired_diagnostic_pending=True)
            atomic_json(output/"primary_complete.json",receipt)
            print(json.dumps(receipt),flush=True);return 0


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--configuration",required=True,type=Path)
    c=json.loads(parser.parse_args().configuration.read_text())
    if c.get("ready") is not True or c.get("kind")!="COMPOSITION_I1_MEAN_STATS" or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only mean(H) statistics required")
    raise SystemExit(run(c))
