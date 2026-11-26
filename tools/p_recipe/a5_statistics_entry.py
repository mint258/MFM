"""A5 first UFF paired statistics; original-geometry draws are consumed unchanged."""
from cpu_ssh_runtime import execution_handle
import argparse,fcntl,json,os,time
from dataclasses import replace
from pathlib import Path
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json
TASKS=("exp.LogD","exp.LogS","exp.Log_HLM_CLint")

def run(c):
    if c.get("ready") is not True or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only A5 primary required")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        import numpy as np
        import torch
        from phychem_mfm.phase1.v3_dev_evaluation import compare_panel
        from phychem_mfm.phase1.v3_dev_evaluation_v2 import _unpack
        torch.set_num_threads(1)
        out=Path(c["output"]);out.mkdir(parents=True,exist_ok=True)
        with (out/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (out/"primary_complete.json").exists():raise ValueError("Closed A5 primary must be reused")
            cohort=json.loads(Path(c["cohort"]).read_text())
            if cohort["status"]!="COMPLETE":raise ValueError("Shared UFF producer incomplete")
            reference=json.loads(Path(c["reference_manifest"]).read_text())
            def load(path):
                return _unpack(torch.load(path,map_location="cpu",weights_only=True)["prediction"])
            summaries={}
            for label in ("T2_9M","T4_9M"):
                saved=out/(label+"_UFF_scores.json")
                if saved.exists():summaries[label]=json.loads(saved.read_text());continue
                if stop.requested or time.time()+c["work_unit_seconds"]>=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]):return 75
                require_cpu_admission(c)
                receipt=json.loads(Path(c["GPU_receipts"][label]).read_text())
                if receipt["status"]!="GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS" or receipt["readout_cells"]!=3:
                    raise ValueError("Both original A5 GPU readouts must close")
                manifest=json.loads(Path(receipt["manifest"]).read_text())
                actual={t:load(manifest["files"][t+"/R3"]) for t in TASKS}
                random={}
                for t,a in actual.items():
                    r=load(reference["files"][t+"/R3"])
                    lookup={uid:i for i,uid in enumerate(r.source_record_uids)}
                    ids=np.asarray([lookup[uid] for uid in a.source_record_uids],dtype=np.int64)
                    random[t]=replace(r,molecule_uids=tuple(r.molecule_uids[i] for i in ids),
                        source_record_uids=tuple(r.source_record_uids[i] for i in ids),
                        targets=r.targets[ids],predictions=r.predictions[ids],valid=r.valid[ids])
                result=compare_panel(actual,random,architecture_sha256="C1-0-reference",
                    reference_architecture_sha256="C1-0-reference",retain_paired_samples=True,retain_task_samples=True)
                if not result["complete"] or result["bootstrap_defined"]!=1000:
                    raise ValueError("Registered UFF primary undefined")
                result.update(source=label,common_cohort=c["cohort"],readout_seed=0,
                    reference_policy="Original frozen random-encoder R3 predictions on exactly the common accepted evaluation members")
                atomic_json(saved,result);summaries[label]=result
            left,right=(summaries[k] for k in ("T2_9M","T4_9M"))
            if left["paired_bootstrap"]["groups"]!=right["paired_bootstrap"]["groups"]:
                raise ValueError("New UFF paired molecular draw population differs")
            original={label:json.loads(Path(path).read_text())["R3"] for label,path in c["original_geometry_scores"].items()}
            a,b=(original[k] for k in ("T2_9M","T4_9M"))
            if a["paired_bootstrap"]["groups"]!=b["paired_bootstrap"]["groups"]:
                raise ValueError("Original retained molecular draws cannot be paired")
            rows=[];draws={}
            for geometry,one,two in [("original",a,b),("sealed_UFF_common",left,right)]:
                delta=[];samples=[]
                for t in TASKS:
                    point=one["tasks"][t]["normalized_improvement"]-two["tasks"][t]["normalized_improvement"]
                    values=np.asarray(one["paired_bootstrap"]["task_values"][t],float)-np.asarray(two["paired_bootstrap"]["task_values"][t],float)
                    if values.shape!=(1000,) or not np.isfinite(values).all():
                        raise ValueError("Exactly original1000 paired task draws required")
                    rows.append(dict(task=t,geometry=geometry,delta=point,ci95=np.quantile(values,[.025,.975]).tolist()))
                    delta.append(point);samples.append(values)
                mean=np.mean(samples,axis=0)
                rows.append(dict(task="three_task_mean",geometry=geometry,delta=float(np.mean(delta)),ci95=np.quantile(mean,[.025,.975]).tolist()))
                draws[geometry]=mean.tolist()
            old=next(r for r in rows if r["task"]=="three_task_mean" and r["geometry"]=="original")
            new=next(r for r in rows if r["task"]=="three_task_mean" and r["geometry"]=="sealed_UFF_common")
            if new["ci95"][0]>0:interpretation="P advantage over Pprime is not explained solely by downstream/pretraining geometry matching"
            elif new["ci95"][0]<=0<=new["ci95"][1] and old["ci95"][0]>0:
                interpretation="Original difference is mainly attributable to downstream geometry matching"
            else:interpretation="Other pattern; report all original per-task results without recipe changes"
            primary=dict(status="COMPLETE",authority=c["authority"],rows=rows,interpretation=interpretation,
                common_cohort_verified=True,full_inchikey_exact_join=True,cohort=c["cohort"],
                accepted_members=cohort["accepted_members"],excluded_members=len(cohort["excluded"]),
                exclusion_reasons=cohort["exclusion_reasons"],paired_bootstrap_samples=1000,bootstrap_seed=20261025,
                original_geometry_primary_draws_reused=True,original_geometry_refitted=False,
                original_geometry_population="Original closed native evaluation cohort; original retained draws reused",
                UFF_population="Shared producer-accepted cohort in both T2/T4; original random predictions restricted to this cohort",
                new_GPU_R3_cells=6,readout_seed=0,QM9_unchanged_DFT=True,descriptive_only=True,
                frozen_recipe_changed=False,conditional_seed1_required=False,T4_decision_changed=False)
            atomic_json(out/"primary.json",primary)
            atomic_json(Path(c["publication_primary"]),primary)
            atomic_json(out/"paired_mean_draws.json",draws)
            atomic_json(out/"primary_complete.json",dict(status="COMPLETE",job=execution_handle(),
                rows=len(rows),new_model_fits=0,old_geometry_bootstrap_replayed=False))
            print(json.dumps(dict(status="COMPLETE",rows=len(rows),interpretation=interpretation)),flush=True)
            return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args();raise SystemExit(run(json.loads(Path(args.configuration).read_text())))

