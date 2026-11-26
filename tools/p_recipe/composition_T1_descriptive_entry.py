"""22C first EEV/CEV_size only; all closed mean statistics remain immutable."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint
from composition_mean_statistics_entry import atomic_array,atomic_npz,write_rows


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"primary_complete.json").exists():
                raise ValueError("Closed22C supplement must be reused")
            import numpy as np
            from composition_statistics import ridge_oof,cev_values,eev_values,summary
            from composition_descriptive import element_layout,accumulate_records,additional_output_peak
            forward=json.loads(Path(c["forward_summary"]).read_text())
            if forward["status"]!="COMPLETE" or forward["source_count"]!=4:
                raise ValueError("The four registered T1 sources must close first")
            with np.load(c["panel"],allow_pickle=False) as p:
                panel={k:p[k].copy() for k in ["Z","molecule_atom_offsets",
                    "record_atom_offsets","owners","X","first"]}
            layout=element_layout(panel);groups=len(layout["elements"])
            if additional_output_peak(groups,new_sources=4)>c["remaining_output_bytes"]:
                raise ValueError("Measured moment/OOF peak exceeds registered output")
            weights=np.load(c["weights"],allow_pickle=False)
            if weights.shape!=(1001,5000) or weights.dtype!=np.float64:
                raise ValueError("Original closed molecular weights must be reused")
            if {x["label"] for x in c["sources"]}!={"T1_1M","T1_3M","T1_6M","T1_9M"}:
                raise ValueError("Only the four T1 sources are registered")
            panel_identity=fingerprint(c["panel"]);weights_identity=fingerprint(c["weights"])
            cutoff=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
            def should_stop():
                return stop.requested or time.time()+c["work_unit_seconds"]>=cutoff
            rows=[];retained={};summaries={}
            for source in c["sources"]:
                if should_stop():return 75
                label=source["label"];directory=output/label;directory.mkdir(exist_ok=True)
                source_dir=Path(forward["sources"][label]).parent
                state=json.loads((source_dir/"cursor.json").read_text())
                if (state.get("complete") is not True
                        or state["identity"]["source"]!=source
                        or state["record_cursor"]!=len(panel["owners"])):
                    raise ValueError("Immutable original forward cursor differs")
                atom_path=source_dir/"atoms.npy";mean_path=source_dir/"means.npy"
                identity=dict(source=source,panel=panel_identity,weights=weights_identity,
                    atoms=fingerprint(atom_path),means=fingerprint(mean_path),
                    authority="USER_DIRECTIVE_20261122C")
                sealed=directory/"primary.json"
                if sealed.exists():
                    result=json.loads(sealed.read_text())
                    if result["identity"]!=identity:raise ValueError("Closed supplement identity changed")
                    summaries[label]=result
                    continue
                require_cpu_admission(c)
                original_reused=False
                prediction_path=directory/"size_OOF.npy";fit_path=directory/"size_OOF_complete.json"
                means=np.load(mean_path,mmap_mode="r",allow_pickle=False)
                y=np.asarray(means[panel["first"]],np.float64)
                if fit_path.exists():
                    fit=json.loads(fit_path.read_text())
                    if fit["identity"]!=identity or fit["prediction"]!=fingerprint(prediction_path):
                        raise ValueError("Closed size OOF binding differs")
                    prediction=np.load(prediction_path,allow_pickle=False)
                else:
                    prediction,alphas=ridge_oof(panel["X"][:,-2:],y)
                    atomic_array(prediction_path,prediction)
                    atomic_json(fit_path,dict(identity=identity,prediction=fingerprint(prediction_path),
                        selected_alphas=alphas))
                size_path=directory/"CEV_size_draws.npy"
                if size_path.exists():
                    size_draws=np.load(size_path,allow_pickle=False)
                else:
                    size_draws=cev_values(y,prediction,weights);atomic_array(size_path,size_draws)
                del means,y,prediction
                if should_stop():return 75
                moment_path=directory/"element_moments.npz"
                if moment_path.exists():
                    with np.load(moment_path,allow_pickle=False) as p:
                        if json.loads(str(p["identity"].item()))!=identity:
                            raise ValueError("Moment prefix source identity changed")
                        cursor=int(p["cursor"]);atom_sums=p["sums"].copy();atom_square=p["squares"].copy()
                else:
                    cursor=0;atom_sums=np.zeros((groups,512),np.float64)
                    atom_square=np.zeros(groups,np.float64)
                total=len(panel["owners"])
                if not 0<=cursor<=total or (cursor!=total and cursor%4096):
                    raise ValueError("Moment prefix is not an exact committed chunk")
                features=np.load(atom_path,mmap_mode="r",allow_pickle=False)
                if features.shape!=(int(panel["record_atom_offsets"][-1]),512) or features.dtype!=np.float32:
                    raise ValueError("Native atomic H0 cache shape/dtype changed")
                while cursor<total:
                    if should_stop():return 75
                    if cursor%16384==0:require_cpu_admission(c)
                    end=min(total,cursor+4096)
                    cursor=accumulate_records(atom_sums,atom_square,features,panel,layout,cursor,end)
                    atomic_npz(moment_path,identity=np.asarray(json.dumps(identity)),cursor=np.int64(cursor),
                        sums=atom_sums,squares=atom_square)
                    print(json.dumps(dict(source=label,moment_records=cursor,total=total)),flush=True)
                del features
                if should_stop():return 75
                eev=eev_values(atom_sums,atom_square,layout["counts"],
                    layout["owners"],layout["elements"],weights)
                draws=dict(CEV_size=size_draws,EEV=eev)
                metrics={k:summary(v) for k,v in draws.items()}
                del atom_sums,atom_square
                atomic_npz(directory/"primary_draws.npz",**draws)
                result=dict(status="COMPLETE",source=label,identity=identity,metrics=metrics,
                    original_M1_two_primaries_reused=original_reused,
                    mean_representation="mean(H)",atomic_representation="H",
                    old_CEV_CVF_CVFres_PR_recomputed=False)
                if fingerprint(atom_path)!=identity["atoms"] or fingerprint(mean_path)!=identity["means"]:
                    raise ValueError("Frozen features changed while consumed")
                atomic_json(sealed,result);summaries[label]=result
            for source in c["sources"]:
                label=source["label"];result=summaries[label]
                row=dict(source=label,samples=source["source_binding"]["samples"],
                    source_training_budget=source["source_binding"]["source_training_budget"],
                    molecules=5000,records=len(panel["owners"]),layer=6)
                for name,metric in result["metrics"].items():
                    row[name]=metric["value"]
                    row[name+"_CI_low"]=None if metric["ci95"] is None else metric["ci95"][0]
                    row[name+"_CI_high"]=None if metric["ci95"] is None else metric["ci95"][1]
                rows.append(row);retained[label]=str(output/label/"primary_draws.npz")
            primary=dict(status="COMPLETE",authority="USER_DIRECTIVE_20261122C",
                rows=rows,retained=retained,mean_metrics_added=["CEV_size"],atomic_metrics=["EEV"],
                original_M1_two_primaries_reused=False,old_mean_primaries_recomputed=False,
                new_bootstrap_weight_generations=0,H_comp_H_B4_decisions_changed=False,
                T1_four_sources_still_required=False,no_new_training=True)
            atomic_json(output/"primary.json",primary);write_rows(output/"rows.csv",rows)
            receipt=dict(status="COMPLETE",job_id=os.environ["SLURM_JOB_ID"],
                sources=4,new_size_OOF_fits=4,new_EEV_sources=4,original_M1_reused=False,
                statistics_precision="F64",bootstrap_unit="molecule",bootstrap_seed=20261025,
                new_bootstrap_weight_generations=0,decisions_changed=False)
            atomic_json(output/"primary_complete.json",receipt)
            print(json.dumps(receipt),flush=True);return 0


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--configuration",type=Path,required=True)
    c=json.loads(parser.parse_args().configuration.read_text())
    if c.get("ready") is not True or c.get("kind")!="COMPOSITION_T1_22C_DESCRIPTIVE" or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only22C descriptive supplement required")
    raise SystemExit(run(c))
