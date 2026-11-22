"""A3 inference only: original T2 P heads/VAL choices, resumable native batches."""
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import time

from finetune_entry import CooperativeStop,set_actual_deadline,admission,gpu_lock_and_check
from finetune_statistics_entry import atomic_json,fingerprint


def validate_model_configuration(c):
    recipe=c["p_recipe"]
    if (c["batch_size"]!=32 or c["microbatch_size"]!=32
            or c.get("gradient_accumulation_steps",1)!=1
            or c.get("activation_checkpointing") is not False
            or c.get("mean_labels") is not False or c["source"]!="PM7"
            or c["samples"]!=9000000):
        raise ValueError("A3 requires the frozen T2 B32/9M FP32 configuration")
    if (not recipe.get("anti_collapse") or recipe.get("family_equal",False)
            or recipe.get("uncertainty_weighting",False)
            or recipe.get("field_loss_multipliers")
            or not c["step_overhead"].get("grouped_fields")
            or not c["step_overhead"].get("prepared_input")):
        raise ValueError("A3 objective adapter requires the exact original T2 grouped-field branch")
    return recipe


def ordered_validation(pool,reader,fixed,start,batch_size,should_stop):
    pending=deque();next_index=start;count=(len(fixed)+batch_size-1)//batch_size
    try:
        while pending or next_index<count:
            while len(pending)<4 and next_index<count and not should_stop():
                selected=fixed[next_index*batch_size:(next_index+1)*batch_size]
                pending.append((next_index,pool.submit(reader,selected)))
                next_index+=1
            if should_stop() or not pending:return
            index,future=pending.popleft()
            yield index,future.result()
    finally:
        for _,future in pending:future.cancel()


def measure_batch(samples,pd,fields,gamma):
    import torch
    from phychem_mfm.phase1.v31_loader import encode_samples
    from penalty_statistics import b4_terms,p_objective
    with torch.no_grad():
        clean,h=encode_samples(samples,pd.encoder,device="cuda")
        prediction=pd.predict(samples,groups=("P",),fields=fields,
                              clean_features=h,clean_batch=clean)
        loss=pd.loss(prediction,samples,groups=("P",),fields=fields)
        P=p_objective(loss);hinge,decor=b4_terms(h,gamma)
        native_B4=hinge+decor;weighted_B4=.1*native_B4
    return dict(molecules=len(samples),atoms=len(h),
        conformers=[int(s["conformer_index"]) for s in samples],
        hinge=float(hinge),decorrelation=float(decor),B4=float(native_B4),
        weighted_B4=float(weighted_B4),P_loss=float(P))


def main(path):
    c=json.loads(Path(path).read_text())
    if (c.get("authority")!="docs/p_recipe/USER_DIRECTIVE_20261122B.md"
            or c.get("kind")!="A3_FORWARD" or c.get("ready") is not True):
        raise ValueError("Validated registered A3 inference configuration required")
    output=Path(c["output"])
    if (output/"summary.json").exists():
        raise ValueError("This A3 forward producer is already closed")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);node=admission(c);gpu_lock,card=gpu_lock_and_check(c,stop)
        try:
            os.environ["CUDA_VISIBLE_DEVICES"]=c["gpu_uuid"]
            import torch
            from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration
            from phychem_mfm.phase1.p_recipe_input import (reader_metadata,
                init_prepared_reader,read_prepared_validation)
            from phychem_mfm.phase1.v2_s_training import s_model
            from phychem_mfm.phase1.v31_training import V31PDModel
            from phychem_mfm.phase1.v31_loader import encode_samples
            from penalty_statistics import b4_terms,p_objective,validate_prefix
            cpus=int(os.environ["SLURM_CPUS_PER_TASK"])
            if cpus<c["cpus"]:raise ValueError("Insufficient actual CPU allocation")
            torch.set_num_threads(1);torch.set_float32_matmul_precision("highest")
            torch.backends.cuda.matmul.allow_tf32=False
            torch.backends.cudnn.allow_tf32=False
            output.mkdir(parents=True,exist_ok=True)
            with (output/"owner.lock").open("a") as owner:
                fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
                started=time.time();cutoff=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
                def should_stop():return stop.requested or time.time()+c["work_unit_seconds"]>=cutoff
                completed_path=output/"completed_forwards.json"
                completed=json.loads(completed_path.read_text()) if completed_path.exists() else {}
                signature=None
                for source in c["sources"]:
                    label=source["label"];binding=source["source_binding"]
                    state_path=output/label/"batches.json"
                    current=fingerprint(binding["checkpoint"])
                    if (current["bytes"]!=binding["bytes"]
                            or str(current["mtime_ns"])!=source["checkpoint_mtime_ns"]):
                        raise ValueError("Frozen checkpoint metadata changed")
                    identity=dict(source=source,checkpoint=current)
                    state=json.loads(state_path.read_text()) if state_path.exists() else None
                    if state is not None and state["identity"]!=identity:
                        raise ValueError("Saved A3 source identity changed")
                    if label in completed:
                        if (state is None or state.get("complete") is not True
                                or completed[label]!=str(state_path)):
                            raise ValueError("Closed A3 source seal differs")
                        continue
                    if should_stop():return 75
                    cp=torch.load(binding["checkpoint"],map_location="cpu",weights_only=True)
                    cfg=cp["configuration"];recipe=validate_model_configuration(cfg)
                    if cp["clock"]["samples_consumed"]!=binding["samples"]:
                        raise ValueError("Checkpoint sample clock differs")
                    selected={key:cfg[key] for key in ["batch_size","microbatch_size","samples","seed",
                        "source","root","normalizations","label_parameters","training_view",
                        "corpus","fields","p_recipe","head_form","step_overhead"]}
                    if signature is None:signature=selected
                    elif selected!=signature:raise ValueError("T2 source recipe/normalization changed")
                    validation_configuration=dataset_configuration(cfg,validation=True)
                    data=PRecipeDataset(**validation_configuration)
                    try:
                        fixed=list(map(int,data.indices))
                        if len(fixed)!=2000 or len(set(fixed))!=2000:
                            raise ValueError("Original fixed2000 VAL population required")
                        structural,architecture=s_model("C1-0","three")
                        structural.encoder.backbone.activation_checkpointing=False
                        pd=V31PDModel(structural.encoder,data.view,forms=cfg["head_form"],
                                      pooling="registry",p_recipe=recipe)
                        pd.configure_step_overhead(cfg["step_overhead"])
                        model=torch.nn.ModuleDict(dict(structural=structural,pd=pd))
                        model.load_state_dict(cp["model"]);del cp
                        model.cuda().eval()
                        fields=tuple(f.name for f in pd.registry.enabled(("P",))
                                     if cfg.get("fields") is None or f.name in cfg["fields"])
                        metadata=reader_metadata(pd,fields)
                        if state is None:
                            state=dict(identity=identity,fixed_indices=fixed,rows=[],complete=False)
                        if state["fixed_indices"]!=fixed:
                            raise ValueError("Fixed validation membership/order changed")
                        cursor=validate_prefix(state["rows"],fixed,32)
                        # DATA is unused by read_prepared_validation; use VAL-only
                        # initialization so no TRAIN population is materialized.
                        with ProcessPoolExecutor(c["workers"],
                                mp_context=multiprocessing.get_context("spawn"),
                                initializer=init_prepared_reader,
                                initargs=(validation_configuration,False,metadata,
                                          validation_configuration)) as pool:
                            with closing(ordered_validation(pool,read_prepared_validation,
                                    fixed,cursor,32,should_stop)) as batches:
                                for index,samples in batches:
                                    if should_stop():break
                                    row=dict(batch_index=index,
                                        molecule_indices=fixed[index*32:(index+1)*32],
                                        **measure_batch(samples,pd,fields,recipe["gamma"]))
                                    state["rows"].append(row)
                                    atomic_json(state_path,state)
                                    print(json.dumps(dict(source=label,batch=index,
                                        molecules_completed=sum(r["molecules"] for r in state["rows"]))),flush=True)
                        if len(state["rows"])!=(len(fixed)+31)//32:return 75
                        state["complete"]=True;atomic_json(state_path,state)
                        completed[label]=str(state_path);atomic_json(completed_path,completed)
                        del model,pd,structural
                        torch.cuda.empty_cache()
                    finally:
                        data.close()
                summary=dict(status="COMPLETE",kind="A3_FORWARD",job_id=os.environ["SLURM_JOB_ID"],
                    node=node,card=card,sources=completed,source_count=len(completed),
                    fixed_VAL_molecules=2000,batch_size=32,workers=c["workers"],
                    CPU_statistics_pending=True,new_training=False,new_optimizer_updates=0,
                    gamma_refitted=False,normalization_changed=False,TF32=False,
                    seconds_this_attempt=time.time()-started,
                    peak_GPU_allocated_bytes=torch.cuda.max_memory_allocated())
                atomic_json(output/"summary.json",summary)
                print(json.dumps(summary),flush=True)
                return 0
        finally:
            gpu_lock.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--configuration",type=Path,required=True)
    raise SystemExit(main(parser.parse_args().configuration))
