"""A5 two frozen L6/H0 sources, identical producer-validated UFF cohort."""
import argparse,fcntl,json,os,time
from dataclasses import replace
from pathlib import Path
from finetune_entry import CooperativeStop,set_actual_deadline,admission,gpu_lock_and_check,REPO
from finetune_statistics_entry import atomic_json,fingerprint
from a5_contracts import open_native_store,require_runtime_configuration

TASKS={"exp.LogD","exp.LogS","exp.Log_HLM_CLint"}

class CommonUFFView:
    def __init__(self,original,cohort):
        self.original=original
        self.rows={r["member_index"]:r for r in cohort["rows"]}
        self.dataset_id=original.dataset_id;self.tasks=original.tasks
        self.membership_sha256=original.membership_sha256+":A5_producer_validated_UFF"
    def view(self,role):
        return tuple(i for i in self.original.view(role) if i in self.rows)
    def molecule_group(self,index):
        return self.original.molecule_group(index)
    def get(self,index,*,role):
        import torch
        row=self.rows[index]
        if row["role"]!=role:raise ValueError("Original fixed inner role changed")
        sample=self.original.get(index,role=role)
        return replace(sample,pos=torch.tensor(row["coordinates_A"],dtype=torch.float32),geometry_ready=True)

def run(c):
    require_runtime_configuration(c)
    if (c.get("ready") is not True or c["source"]["label"] not in {"T2_9M","T4_9M"}
            or c["source"]["source_binding"]["samples"]!=9000000 or c["readout_seed"]!=0):
        raise ValueError("Only registered T2/T4 9M frozen R3 seed0")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);admission(c)
        lock,card=gpu_lock_and_check(c,stop);os.environ["CUDA_VISIBLE_DEVICES"]=c["gpu_uuid"]
        try:
            import torch
            from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
            from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec,task_rows
            from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack
            from phychem_mfm.phase1.v3_latent_evaluation import cached_rows
            from noise_features import produce_features
            from noise_readout import run_resumable_probe
            from noise_entry import load_encoder
            from finetune import atomic_checkpoint,ContinuationRequired
            torch.set_num_threads(c["cpus"]);torch.set_float32_matmul_precision("highest")
            torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
            cohort=json.loads(Path(c["cohort"]).read_text())
            if (cohort["status"]!="COMPLETE" or cohort["common_cohort_verified"] is not True
                    or cohort["full_inchikey_exact_join"] is not True or not cohort["rows"]):
                raise ValueError("Complete nonempty producer-validated common UFF cohort required")
            store=open_native_store(c["native_store"])
            original=GroupedTrainingView(store,"expansionrx","official",store.group_map)
            view=CommonUFFView(original,cohort)
            panel=json.loads((REPO/"configs/dev_panel_v3.json").read_text())
            tasks=[replace(TaskSpec(**{k:t[k] for k in ("task_id","dataset_id","field","output_level","error_metric","pooling")}),pooling="mean") for t in panel["tasks"] if t["task_id"] in TASKS]
            if {t.task_id for t in tasks}!=TASKS:raise ValueError("Exactly three ExpansionRx tasks required")
            output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
            with (output/"owner.lock").open("a") as owner:
                fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
                if (output/"primary_complete.json").exists():raise ValueError("Closed A5 readout must be reused")
                identity=dict(source=c["source"],cohort=fingerprint(c["cohort"]),native_store=c["native_store"],geometry="sealed_Sprime_UFF_common_native_atom_inventory")
                last_guard=0.
                def should_stop():
                    nonlocal last_guard
                    if stop.requested or time.time()+c["work_unit_seconds"]>=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]):return True
                    if time.monotonic()-last_guard>=15:
                        admission(c);last_guard=time.monotonic()
                    return False
                started=time.monotonic()
                encoder=load_encoder(c["source"])
                payload=produce_features(view,"expansionrx",encoder,output/"features",source_identity=identity,should_stop=should_stop)
                del encoder;torch.cuda.empty_cache()
                cached=cached_rows(payload)
                m=dict(run=c["run"],arm=c["source"]["label"],samples=9000000,readout_seed=0,layer=6,
                       source_roles=["train","train_inner_validation"],files={},details={},label_stds={},source_identity=identity)
                history=output/"history.jsonl"
                class History:
                    disabled=False
                    cell=""
                    def log(self,row,*,step,commit):
                        with history.open("a") as stream:stream.write(json.dumps(dict(cell=self.cell,step=step,**row))+"\n")
                tracker=History()
                for task in tasks:
                    if should_stop():return 75
                    train=task_rows(view,cached,task,role="train");validation=task_rows(view,cached,task,role="train_inner_validation")
                    values=torch.cat([r.targets[r.supervision_mask&r.candidate_mask].double() for r in train])
                    m["label_stds"][task.task_id]=float(values.std(unbiased=False))
                    key=task.task_id+"/R3";p=output/(task.task_id.replace(".","_")+"__R3.pt");tracker.cell=key
                    cell_identity=dict(source=identity,task=task.task_id)
                    if p.exists():
                        saved=torch.load(p,map_location="cpu",weights_only=True)
                        if saved["A5_identity"]!=cell_identity:raise ValueError("Closed A5 cell identity changed")
                    else:
                        prediction,detail=run_resumable_probe(train,validation,task,readout="R3",
                            n_ref=payload["n_ref"],seed=0,device="cuda",tracker=tracker,
                            relative_std_floor=True,internal_epoch_selection=True,
                            state_path=output/(task.task_id.replace(".","_")+"__complete.pt"),
                            source_identity=cell_identity,should_stop=should_stop)
                        saved=dict(prediction=_pack(prediction),detail=detail,A5_identity=cell_identity)
                        atomic_checkpoint(p,saved)
                    m["files"][key]=str(p);m["details"][key]={k:v for k,v in saved["detail"].items() if k!="state_dict"}
                    atomic_json(output/"predictions.json",m)
                atomic_json(output/"primary_complete.json",dict(status="GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS",
                    job=os.environ["SLURM_JOB_ID"],source=c["source"]["label"],manifest=str(output/"predictions.json"),
                    readout_cells=3,readout_seed=0,encoder_updated=False,common_cohort=c["cohort"],
                    alignment_repeated=False,new_geometry=False,seconds=time.monotonic()-started))
                return 0
        except ContinuationRequired:return 75
        finally:lock.close()

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args();raise SystemExit(run(json.loads(Path(args.configuration).read_text())))

