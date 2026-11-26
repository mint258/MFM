"""A6: unchanged frozen R3 seed0 on 30000 TRAIN groups and original2048 evaluation."""
import argparse
from dataclasses import replace
import fcntl
import json
import os
from pathlib import Path
import time
from finetune_entry import CooperativeStop,set_actual_deadline,admission,gpu_lock_and_check,REPO
from finetune_statistics_entry import atomic_json


def features(members,fit,encoder,should_stop):
    import torch
    from torch_geometric.data import Batch,Data
    from finetune import ContinuationRequired
    records=[];sizes=[]
    with torch.no_grad():
        for start in range(0,len(members),32):
            if should_stop():raise ContinuationRequired("A6 frozen-feature batch boundary")
            selected=members[start:start+32]
            batch=Batch.from_data_list([Data(x=s.x.reshape(-1,1),pos=s.pos) for _,s in selected]).cuda()
            h=encoder.encode_atoms(batch).detach().cpu().float();offset=0
            for index,sample in selected:
                n=len(sample.x)
                records.append(dict(molecule_uid=sample.member_uid,member_index=index,
                    h0=h[offset:offset+n],source_atom_ids=sample.source_atom_ids))
                if index in fit:sizes.append(n)
                offset+=n
    return dict(records=records,n_ref=sum(sizes)/len(sizes))


def run(c):
    if c.get("ready") is not True:raise ValueError("A6 GPU readout must be activated")
    if ([x["label"] for x in c["sources"]]!=["T5_9M","T6_9M","T2_9M","random"]
            or c["readout_seed"]!=0 or c["train_groups"]!=30000 or c["evaluation_groups"]!=2048
            or c["random_encoder_seed"]!=20261025):
        raise ValueError("Fixed A6 source/population/seed contract changed")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);admission(c)
        lock,card=gpu_lock_and_check(c,stop);os.environ["CUDA_VISIBLE_DEVICES"]=c["gpu_uuid"]
        try:
            import torch
            from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore,bound_json
            from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
            from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec,task_rows
            from phychem_mfm.phase1.v3_downstream_targets import atomization_rows,ATOMIZATION_TASK_ID
            from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack
            from phychem_mfm.phase1.v3_latent_evaluation import cached_rows
            from phychem_mfm.phase1.v2_s_training import s_model
            from noise_readout import run_resumable_probe
            from noise_entry import load_encoder
            from finetune import atomic_checkpoint,ContinuationRequired
            torch.set_num_threads(16);torch.set_float32_matmul_precision("highest")
            torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
            receipt=bound_json(c["materialization"]["path"],c["materialization"]["sha256"])
            if receipt["status"]!="COMPLETE" or receipt["counts"]!={"train":30000,"train_inner_validation":2048}:
                raise ValueError("Only the complete A6 source may be consumed")
            store=TrainOnlyPackedStore(receipt["training_store"]["path"],receipt["training_store"]["sha256"])
            view=GroupedTrainingView(store,"qm9","0",store.group_map,max_train_groups=30000,max_validation_groups=2048)
            old=TrainOnlyPackedStore(c["original_store"],verify_digests=False)
            oldview=GroupedTrainingView(old,"qm9","0",old.group_map)
            if view.view("train_inner_validation")!=oldview.view("train_inner_validation") or not set(oldview.view("train"))<=set(view.view("train")):
                raise ValueError("A6 evaluation or nested TRAIN identity changed")
            members=[(i,view.get(i,role=role)) for role in ["train","train_inner_validation"] for i in view.view(role)]
            if any(not s.geometry_ready for _,s in members):
                raise ValueError("Missing original DFT geometry; no replacements permitted")
            fit=set(view.view("train"))
            panel=json.loads((REPO/"configs/dev_panel_v3.json").read_text())
            tasks=[replace(TaskSpec(**{k:t[k] for k in ["task_id","dataset_id","field","output_level","error_metric","pooling"]}),pooling="mean") for t in panel["tasks"] if t["dataset_id"]=="qm9"]
            if {t.task_id for t in tasks}!={"qm9.U0_atom","qm9.homo","qm9.lumo","qm9.alpha"}:
                raise ValueError("Only the four QM9 tasks are registered")
            output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
            with (output/"owner.lock").open("a") as owner:
                fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
                if (output/"primary_complete.json").exists():raise ValueError("Closed A6 readout must be reused")
                started=time.monotonic()
                def should_stop():
                    return stop.requested or time.time()+c["work_unit_seconds"]>=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
                completed={}
                for source in c["sources"]:
                    label=source["label"];base=output/label;base.mkdir(exist_ok=True)
                    if (base/"predictions.json").exists():
                        m=json.loads((base/"predictions.json").read_text())
                        if len(m["files"])==4:completed[label]=str(base/"predictions.json");continue
                    if should_stop():return 75
                    admission(c)
                    if label=="random":
                        with torch.random.fork_rng(devices=[0]):
                            torch.manual_seed(c["random_encoder_seed"])
                            model,_=s_model("C1-0","three")
                        encoder=model.encoder.cuda().eval();del model
                    else:encoder=load_encoder(source)
                    payload=features(members,fit,encoder,should_stop);del encoder
                    torch.cuda.empty_cache();cached=cached_rows(payload)
                    identity=dict(source=source,store=receipt["training_store"],membership_sha256=view.membership_sha256)
                    m=dict(run=c["run"]+"_"+label,arm=label,samples=source.get("source_binding",{}).get("samples",0),stage=0,round=0,
                        files={},details={},label_stds={},source_roles=["train","train_inner_validation"],readout_seed=0,source_identity=identity)
                    history=base/"history.jsonl"
                    class History:
                        disabled=False
                        cell=""
                        def log(self,row,*,step,commit):
                            with history.open("a") as stream:stream.write(json.dumps(dict(cell=self.cell,step=step,**row))+chr(10))
                    tracker=History()
                    for task in tasks:
                        maker=atomization_rows if task.task_id==ATOMIZATION_TASK_ID else task_rows
                        train=maker(view,cached,task,role="train");validation=maker(view,cached,task,role="train_inner_validation")
                        values=torch.cat([r.targets[r.supervision_mask&r.candidate_mask].double() for r in train])
                        m["label_stds"][task.task_id]=float(values.std(unbiased=False))
                        key=task.task_id+"/R3";path=base/(task.task_id.replace(".","_")+"__R3.pt");tracker.cell=key
                        if path.exists():
                            saved=torch.load(path,map_location="cpu",weights_only=True)
                            if saved["A6_identity"]!=dict(source=identity,task=task.task_id):raise ValueError("Closed A6 cell identity changed")
                        else:
                            if should_stop():return 75
                            prediction,detail=run_resumable_probe(train,validation,task,readout="R3",n_ref=payload["n_ref"],seed=0,
                                device="cuda",tracker=tracker,relative_std_floor=True,internal_epoch_selection=True,
                                state_path=base/(task.task_id.replace(".","_")+"__complete.pt"),source_identity=identity,should_stop=should_stop)
                            saved=dict(prediction=_pack(prediction),detail=detail,A6_identity=dict(source=identity,task=task.task_id))
                            atomic_checkpoint(path,saved)
                        m["files"][key]=str(path);m["details"][key]={k:v for k,v in saved["detail"].items() if k!="state_dict"}
                        atomic_json(base/"predictions.json",m)
                    completed[label]=str(base/"predictions.json");del cached,payload
                    atomic_json(output/"completed_sources.json",completed)
                atomic_json(output/"primary_complete.json",dict(status="GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS",job=os.environ["SLURM_JOB_ID"],
                    sources=completed,source_count=4,readout_cells=16,train_groups=30000,evaluation_groups=2048,
                    readout_seed=0,encoder_updated=False,new_geometry=False,seconds=time.monotonic()-started,power_mean_watts=None))
                return 0
        except ContinuationRequired:
            return 75
        finally:
            lock.close()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args()
    raise SystemExit(run(json.loads(Path(args.configuration).read_text())))
