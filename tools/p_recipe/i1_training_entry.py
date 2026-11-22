"""Registered I1: fresh3M/seed0, only B4 disabled, original complete-state handoff."""
import argparse
import csv
import json
import os
from pathlib import Path
import threading
import time
from finetune_entry import CooperativeStop,set_actual_deadline,admission,gpu_lock_and_check,native_query
from finetune_statistics_entry import atomic_json,fingerprint
from i1_runtime_control import watch


def validate(c):
    original=json.loads(Path(c["baseline_configuration"]).read_text())
    native=c["training_configuration"]
    if (native["samples"]!=3000000 or native["seed"]!=0
            or native["batch_size"]!=32 or native["microbatch_size"]!=32
            or native["activation_checkpointing"] is not False
            or native["p_recipe"]["anti_collapse"] is not False
            or original["p_recipe"]["anti_collapse"] is not True):
        raise ValueError("Only the registered B32/FP32 I1 B4-off3M seed0 is allowed")
    expected=dict(original["p_recipe"]);expected["anti_collapse"]=False
    if native["p_recipe"]!=expected:
        raise ValueError("I1 may only change the B4 loss switch")
    allowed={"run","arm","output","components","protocol_exception","handoff_request","handoff_ack"}
    for key in original:
        if key not in allowed|{"p_recipe"} and native.get(key)!=original[key]:
            raise ValueError("I1 changed another baseline field: "+key)
    if "window2_TRAIN_normalization_parameters_20261107_v1" not in native["normalizations"]:
        raise ValueError("The fixed11-07 fullTRAIN normalization is required")
    if native["output"]!=c["output"]:
        raise ValueError("Training output differs from admitted writer")
    return dict(native)


def run(c):
    if c.get("ready") is not True:raise ValueError("I1 must be activated")
    with CooperativeStop() as stop:
        def guard():
            admission(c)
            import shared_guard
            from budget_resume_admission import validate_canonical_filesystem
            validate_canonical_filesystem(c["control_directory"],"/share")
            claim=json.loads((shared_guard.REGISTRY/"p-recipe.json").read_text())
            future=sum(x["bytes"] for x in claim["entries"] if x["kind"]=="shared_fs" and x.get("path")=="/share")
            shared_guard.check_with_timeout("p-recipe","shared_fs",future,path="/share")
        set_actual_deadline(c,stop);guard()
        lock,card=gpu_lock_and_check(c,stop)
        os.environ["CUDA_VISIBLE_DEVICES"]=c["gpu_uuid"]
        done=threading.Event();thread=None
        try:
            native=validate(c)
            import torch
            from phychem_mfm.phase1.p_recipe_training import train
            torch.set_float32_matmul_precision("highest")
            torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
            job=os.environ["SLURM_JOB_ID"]
            # Every allocation has its own request/ack; old handoffs are retained.
            control=Path(c["control_directory"])
            native["handoff_request"]=str(control/(native["run"]+"_"+job+"_handoff_request.json"))
            native["handoff_ack"]=str(control/(native["run"]+"_"+job+"_handoff_ack.json"))
            if c.get("resume_checkpoint"):
                path=Path(c["resume_checkpoint"])
                if path.parent.resolve()!=Path(c["output"]).resolve():
                    raise ValueError("Only this I1 run's own closed checkpoint may resume")
                native["resume"]=str(path)
            elif Path(c["output"]).exists():
                raise ValueError("Fresh I1 output already exists; inspect rather than restart")
            cutoff=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])-c["work_unit_seconds"]
            def telemetry():
                out=Path(c["output"])
                if not out.is_dir():return
                text=native_query([c["nvidia_smi"],"--id="+c["gpu_uuid"],
                    "--query-gpu=uuid,power.draw,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits"],stop)
                row=next(csv.reader(text.splitlines()))
                if row[0].strip()!=c["gpu_uuid"]:raise ValueError("Telemetry GPU differs")
                sample=dict(timestamp=time.time(),job_id=job,gpu_uuid=c["gpu_uuid"],
                    power_watts=float(row[1]),memory_mib=float(row[2]),GPU_utilization_percent=float(row[3]))
                with (out/"managed_gpu_telemetry.jsonl").open("a") as stream:
                    stream.write(json.dumps(sample)+chr(10))
            thread=threading.Thread(target=watch,args=(native,job),kwargs=dict(
                done=done,stop_requested=lambda:stop.requested,stop_new_at=cutoff,
                guard=guard,telemetry=telemetry),name="I1_actual_runtime_watch")
            thread.start()
            result=train(native)
            done.set();thread.join()
            receipt=dict(status=result["status"],job_id=job,node=c["node"],card=card,
                result=result,source_validation=c["source_validation"],only_science_change="p_recipe.anti_collapse=false",
                baseline_checkpoint=c["baseline_checkpoint"],new_baseline_training=False,
                FP32=True,TF32=False,normalization_unchanged=True,
                request=native["handoff_request"],ack=native["handoff_ack"],
                monitor_thread_joined=not thread.is_alive())
            atomic_json(Path(c["output"])/("managed_attempt_"+job+".json"),receipt)
            print(json.dumps(receipt),flush=True)
            return 0
        finally:
            done.set()
            if thread is not None:thread.join()
            lock.close()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args()
    raise SystemExit(run(json.loads(Path(args.configuration).read_text())))
