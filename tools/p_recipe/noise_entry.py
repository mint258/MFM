"""Registered A1: four frozen checkpoints, only new R3 readout seeds1-4."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from finetune_entry import (REPO, ROOT, CooperativeStop, set_actual_deadline,
                            admission, gpu_lock_and_check)


def validate_configuration(c):
    expected={"T2_1M":("T2",1000000,9000000),
              "T2_6M":("T2",6000000,9000000),
              "T2_9M":("T2",9000000,9000000),
              "round4_F2":("F2",3000000,3000000)}
    actual={s["label"]:(s["source_binding"]["arm"],s["source_binding"]["samples"],
                       s["source_binding"]["source_training_budget"]) for s in c["sources"]}
    if actual!=expected or len(c["sources"])!=4:
        raise ValueError("Only original T2 1/6/9M and round4 F2 own3M are registered")
    if (c["readout_seeds"]!=[1,2,3,4] or c["layer"]!=6
            or c["timebox_seconds"]!=14400 or c.get("new_pretraining") is not False):
        raise ValueError("A1 seeds0 reuse/L6/timebox/no-pretraining contract changed")


def atomic_json(path,value):
    temporary=path.with_name(path.name+".new")
    with temporary.open("w") as stream:
        json.dump(value,stream,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def load_encoder(binding):
    import torch
    from phychem_mfm.phase1.v2_s_training import s_model
    p=Path(binding["source_binding"]["checkpoint"]);s=p.stat()
    if (s.st_size!=binding["source_binding"]["bytes"]
            or str(s.st_mtime_ns)!=binding["checkpoint_mtime_ns"]):
        raise ValueError("Frozen source checkpoint metadata changed")
    checkpoint=torch.load(p,map_location="cpu",weights_only=True)
    c=checkpoint["configuration"]
    spec=checkpoint.get("architecture",{}).get("backbone",{}).get("v3_latent")
    model,_=s_model(c["distance_bias"],c["views"],
        latent="none" if spec is None else spec["kind"],latent_config=spec)
    weights=checkpoint["model"]
    if any(k.startswith("structural.") for k in weights):
        weights={k.removeprefix("structural."):v for k,v in weights.items()
                 if k.startswith("structural.")}
    model.load_state_dict(weights)
    return model.encoder.cuda().eval()


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop)
        node=admission(c)
        lock,card=gpu_lock_and_check(c,stop)
        os.environ["CUDA_VISIBLE_DEVICES"]=c["gpu_uuid"]
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        budget_path=output/"compute_budget.json"
        budget=json.loads(budget_path.read_text()) if budget_path.exists() else {
            "used_seconds":0.,"active":None,"attempts":[]}
        if budget["active"] is not None:
            lock.close()
            raise ValueError("Prior attempt identity/actual exit must be reconciled before resume")
        budget["active"]=dict(job=os.environ["SLURM_JOB_ID"],pid=os.getpid())
        atomic_json(budget_path,budget)
        started=time.monotonic();outcome="FAILED";continuation_type=None
        manifests={}
        def should_stop():
            elapsed=time.monotonic()-started
            return (stop.requested or time.time()+c["work_unit_seconds"] >=
                    float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
                    or budget["used_seconds"]+elapsed+c["work_unit_seconds"] >=
                    c["timebox_seconds"]-180)
        try:
            import torch
            from dataclasses import replace
            from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec, task_rows
            from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack
            from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
            from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
            from phychem_mfm.phase1.v3_downstream_targets import atomization_rows, ATOMIZATION_TASK_ID
            from phychem_mfm.phase1.v3_latent_evaluation import cached_rows
            from finetune import atomic_checkpoint, ContinuationRequired
            continuation_type=ContinuationRequired
            from noise_features import produce_features
            from noise_readout import run_resumable_probe
            torch.set_num_threads(int(os.environ["SLURM_CPUS_PER_TASK"]))
            torch.set_float32_matmul_precision("highest")
            torch.backends.cuda.matmul.allow_tf32=False
            torch.backends.cudnn.allow_tf32=False
            panel=json.loads((REPO/"configs/dev_panel_v3.json").read_text())
            tasks=[TaskSpec(**{k:t[k] for k in ("task_id","dataset_id","field",
                "output_level","error_metric","pooling")}) for t in panel["tasks"]]
            tasks=[replace(t,pooling="mean") for t in tasks]
            if len(tasks)!=9:raise ValueError("Original nine-task developer panel required")
            store=TrainOnlyPackedStore(c["store"],verify_digests=False)
            views={d:GroupedTrainingView(store,d,"official" if d=="expansionrx" else "0",
                       store.group_map) for d in ("expansionrx","cyp_isoform","qm9")}
            class History:
                disabled=False
                cell=""
                def log(self,row,*,step,commit):
                    with history.open("a") as stream:
                        stream.write(json.dumps(dict(cell=self.cell,step=step,**row))+"\n")
            for binding in c["sources"]:
                label=binding["label"];base=output/label;base.mkdir(exist_ok=True)
                features=base/"features";history=base/"history.jsonl"
                tracker=History();encoder=None
                original=json.loads(Path(binding["seed0_manifest"]).read_text())
                source_identity=dict(binding=binding,membership_version=store.data_version)
                source_manifests={}
                try:
                    for dataset,view in views.items():
                        if should_stop():raise ContinuationRequired("Stopped before new dataset")
                        if not (features/(dataset+".pt")).exists() and encoder is None:
                            encoder=load_encoder(binding)
                        payload=produce_features(view,dataset,encoder,features,
                            source_identity=source_identity,should_stop=should_stop)
                        cached=cached_rows(payload)
                        for task in (t for t in tasks if t.dataset_id==dataset):
                            maker=atomization_rows if task.task_id==ATOMIZATION_TASK_ID else task_rows
                            train=maker(view,cached,task,role="train")
                            validation=maker(view,cached,task,role="train_inner_validation")
                            for seed in c["readout_seeds"]:
                                destination=base/("seed"+str(seed));destination.mkdir(exist_ok=True)
                                manifest_path=destination/"predictions.json"
                                m=json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(
                                    run=c["run"]+"_"+label+"_seed"+str(seed),files={},details={},
                                    readout_seed=seed,layer=6,source_binding=binding["source_binding"],
                                    seed0_manifest=binding["seed0_manifest"],
                                    label_stds=original["label_stds"],
                                    protocol="original_R3_new_readout_seed_only",
                                    source_roles=["train","train_inner_validation"])
                                key=task.task_id+"/R3"
                                path=destination/(task.task_id.replace(".","_")+"__R3.pt")
                                if path.exists():
                                    saved=torch.load(path,map_location="cpu",weights_only=True)
                                    if saved["A1_identity"]!=dict(source=source_identity,seed=seed,task=task.task_id):
                                        raise ValueError("Closed R3 cell identity changed")
                                else:
                                    if should_stop():raise ContinuationRequired("Stopped before new R3 cell")
                                    tracker.cell=label+"/"+str(seed)+"/"+key
                                    checkpoint=destination/(task.task_id.replace(".","_")+"__complete.pt")
                                    prediction,detail=run_resumable_probe(train,validation,task,
                                        readout="R3",n_ref=payload["n_ref"],seed=seed,device="cuda",
                                        tracker=tracker,relative_std_floor=True,internal_epoch_selection=True,
                                        state_path=checkpoint,source_identity=source_identity,should_stop=should_stop)
                                    saved=dict(prediction=_pack(prediction),detail=detail,
                                        A1_identity=dict(source=source_identity,seed=seed,task=task.task_id))
                                    atomic_checkpoint(path,saved)
                                m["files"][key]=str(path)
                                m["details"][key]={k:v for k,v in saved["detail"].items() if k!="state_dict"}
                                atomic_json(manifest_path,m)
                                source_manifests[str(seed)]=str(manifest_path)
                        del cached,payload
                    if len(source_manifests)!=4:
                        raise ValueError("Missing new registered readout seeds")
                    for path in source_manifests.values():
                        if len(json.loads(Path(path).read_text())["files"])!=9:
                            raise ValueError("Incomplete nine-task R3 source")
                    manifests[label]=dict(seed0=binding["seed0_manifest"],
                        seed0_scores=binding["seed0_scores"],new_seeds=source_manifests)
                    atomic_json(output/"completed_readouts.json",manifests)
                finally:
                    del encoder
                    torch.cuda.empty_cache()
            outcome="COMPLETE"
            atomic_json(output/"summary.json",dict(status=outcome,run=c["run"],
                job_id=os.environ["SLURM_JOB_ID"],node=node,card=card,
                new_readout_units=16,new_task_cells=144,seed0_reused=True,
                new_R1_fits=0,new_pretraining=False,readouts=manifests,
                seconds_this_attempt=time.monotonic()-started))
            return 0
        except BaseException as error:
            if continuation_type is None or not isinstance(error,continuation_type):
                raise
            outcome=("UNRESOLVED_TIMEBOX" if budget["used_seconds"]+time.monotonic()-started+
                     c["work_unit_seconds"]>=c["timebox_seconds"]-180 else "CONTINUATION_REQUIRED")
            atomic_json(output/"partial_summary.json",dict(status=outcome,readouts=manifests,
                original_complete_cells_preserved=True,job_id=os.environ["SLURM_JOB_ID"]))
            return 75
        finally:
            seconds=time.monotonic()-started
            budget["used_seconds"]+=seconds
            budget["attempts"].append(dict(job=os.environ["SLURM_JOB_ID"],
                                           seconds=seconds,status=outcome))
            budget["active"]=None
            atomic_json(budget_path,budget)
            lock.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--configuration",type=Path,required=True)
    args=parser.parse_args();c=json.loads(args.configuration.read_text())
    validate_configuration(c)
    if c.get("ready") is not True or c.get("kind")!="A1":
        raise ValueError("Registered A1 configuration not activated")
    closed=Path(c["output"])/"summary.json"
    if closed.exists() and json.loads(closed.read_text()).get("status")=="COMPLETE":
        raise ValueError("A1 producer is already complete")
    return run(c)


if __name__=="__main__":
    raise SystemExit(main())
