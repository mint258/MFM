"""First CPU mean(H) composition primaries; original cross-fitting/bootstrap reused."""
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
            from composition_statistics import (bootstrap_weights,ridge_oof,
                cev_values,cvf_values,summary)
            from composition_mean_statistics import participation_ratio,b4_decision
            forward_path=Path(c["forward_summary"])
            forward=json.loads(forward_path.read_text())
            if (forward["status"]!="COMPLETE" or forward["source_count"]!=8
                    or forward["layer"]!=6 or forward["molecules"]!=5000):
                raise ValueError("Exactly the registered eight closed L6 sources required")
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
                original_statistics_blob=c["original_statistics_blob"])
            identity_path=output/"input_identity.json"
            if identity_path.exists():
                if json.loads(identity_path.read_text())!=binding:
                    raise ValueError("Closed panel/forward identity changed")
            else:atomic_json(identity_path,binding)
            weight_path=output/"weights.npy"
            if weight_path.exists():
                weights=np.load(weight_path,allow_pickle=False)
            else:
                weights=np.vstack([np.ones((1,5000),np.float64),bootstrap_weights(5000)])
                atomic_array(weight_path,weights)
            if weights.shape!=(1001,5000) or weights.dtype!=np.float64:
                raise ValueError("Original1000 paired molecular F64 draws required")
            reusable=c["reuse_original_M1"]
            old_summary=json.loads(Path(reusable["original_summary"]).read_text())
            old=old_summary["conditions"][reusable["original_condition"]]
            if (old["status"]!="COMPLETE" or old["records"]!=forward["records"]
                    or old["molecules"]!=5000
                    or old["source"]["checkpoint"]!=reusable["source_checkpoint"]):
                raise ValueError("Original M1 closed-source/population binding differs")
            # Fixed VAL selection source is compared structurally, without numerical replay.
            import ast
            def val_ast(path):
                return ast.dump(next(x for x in ast.parse(Path(path).read_text()).body
                    if isinstance(x,ast.FunctionDef) and x.name=="validation_indices"),
                    include_attributes=False)
            if val_ast(c["validation_source"])!=val_ast(reusable["validation_source"]):
                raise ValueError("Original VAL selection definition differs")
            panel_receipt=json.loads(Path(c["panel_complete"]).read_text())
            old_mtime=Path(reusable["original_summary"]).stat().st_mtime_ns
            for name,value in panel_receipt["identity"]["inputs"].items():
                if name!=c["validation_source"] and int(value["mtime_ns"])>old_mtime:
                    raise ValueError("Panel input changed after original M1 primary")
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
                    if label==reusable["label"]:
                        with np.load(reusable["bootstrap"],allow_pickle=False) as old_draws:
                            base={k:old_draws["6_"+k].copy() for k in ["CEV","CVF","CVF_res"]}
                        if any(v.shape!=(1001,) for v in base.values()):
                            raise ValueError("Original M1 molecular draw count changed")
                        metrics={k:old["layers"]["6"][k] for k in base}
                        state["original_M1_primary_reused"]=True
                    else:
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
            def contrast(left,right):
                with np.load(retained[left]["base_draws"],allow_pickle=False) as a:
                    with np.load(retained[right]["base_draws"],allow_pickle=False) as b:
                        return a["CEV"]-b["CEV"]
            first_delta=contrast("round2_B4","round2_M1")
            second_delta=contrast("round3_M2","round2_B3")
            first_summary=summary(first_delta);second_summary=summary(second_delta)
            b4=dict(B4_minus_M1=first_summary,M2_minus_B3=second_summary,
                decision=b4_decision(first_summary,second_summary),
                representation="mean(H)",layer=6,mechanism_claim=False)
            t2=contrast("T2_9M","T2_1M")
            atomic_npz(output/"new_paired_draws.npz",B4_minus_M1=first_delta,
                M2_minus_B3=second_delta,T2_9M_minus_1M=t2)
            hcomp=dict(T2_9M_minus_1M=summary(t2),
                decision="PENDING_T1_BUDGET_READOUTS_AND_COMPOSITION",
                T1_difference_in_differences=None,mechanism_claim=False)
            atomic_json(output/"primary.json",dict(status="COMPLETE",rows=rows,
                H_B4=b4,H_comp=hcomp,retained=retained,input_identity=binding,
                original_M1_three_primaries_reused=True,atomic_metrics_pending=True,
                frozen_recipe_changed=False))
            write_rows(output/"rows.csv",rows)
            receipt=dict(status="COMPLETE",job_id=os.environ["SLURM_JOB_ID"],
                rows=8,new_OOF_sources=7,original_M1_three_primaries_reused=True,
                layer=6,representation="mean(H)",bootstrap_seed=20261025,
                repetitions=1000,unit="molecule",precision="F64",
                atomic_metrics_pending=True,H_B4=b4,H_comp=hcomp)
            atomic_json(output/"primary_complete.json",receipt)
            print(json.dumps(receipt),flush=True);return 0


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--configuration",required=True,type=Path)
    c=json.loads(parser.parse_args().configuration.read_text())
    if c.get("ready") is not True or c.get("kind")!="COMPOSITION_MEAN_STATS" or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only mean(H) statistics required")
    raise SystemExit(run(c))
