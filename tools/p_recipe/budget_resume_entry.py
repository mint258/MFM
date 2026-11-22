"""Continue only the six remaining original T1 readouts; no new P training."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time

from budget_resume_admission import admission
from finetune_entry import CooperativeStop, set_actual_deadline, gpu_lock_and_check
from finetune_statistics_entry import atomic_json, fingerprint


def validate(c):
    from budget_curve import make_configuration, source_complete
    from execution_ledger import C, read
    if (c["point"]["arm"]!="T1" or c["point"]["samples"] not in
            [1000000,4000000,5000000,6000000,7000000,8000000]
            or c["new_training"] is not False or c["new_seeds"] is not False):
        raise ValueError("Only the six existing T1 checkpoints are authorized")
    original=json.loads(Path(c["source_configuration"]).read_text())
    if not source_complete(original,read(C/"study_execution.json")):
        raise ValueError("Original 9M source and endpoint statistics must close")
    expected=make_configuration(original,c["point"])
    if c["readout"]!=expected:
        raise ValueError("Original readout recipe or ancestry changed")
    if fingerprint(expected["checkpoint"])!=c["checkpoint_identity"]:
        raise ValueError("Checkpoint binding changed")
    return expected


def run(c):
    if c.get("ready") is not True:
        raise ValueError("Coordinator must activate this exact registered point")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop)
        admission(c)
        lock,card=gpu_lock_and_check(c,stop)
        os.environ["CUDA_VISIBLE_DEVICES"]=c["gpu_uuid"]
        started=time.monotonic()
        try:
            readout=validate(c);output=Path(readout["output"]);output.mkdir(parents=True,exist_ok=True)
            with (output/"resident_owner.lock").open("a") as owner:
                fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
                if (output/"summary.json").exists():
                    raise ValueError("Existing summary must be reused, never replayed")
                from finetune import ContinuationRequired
                from noise_readout import run_resumable_probe
                import evaluate
                from budget_curve import WAITING
                identity=dict(checkpoint=c["checkpoint_identity"],configuration=readout)
                def should_stop():
                    return stop.requested or time.time()+c["work_unit_seconds"]>=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
                def boundary():
                    if should_stop():raise ContinuationRequired("Safe original readout boundary")
                    admission(c)
                original_probe=evaluate.run_probe
                original_ridge=evaluate.ridge_probe
                original_features=evaluate.produce_missing_features
                def probe(train,validation,task,**kwargs):
                    boundary()
                    state=output/"readout"/(task.task_id.replace(".","_")+"__complete_R3.pt")
                    return run_resumable_probe(train,validation,task,state_path=state,
                        source_identity=identity,should_stop=should_stop,**kwargs)
                def ridge(*args,**kwargs):
                    boundary()
                    return original_ridge(*args,**kwargs)
                def features(*args,**kwargs):
                    boundary()
                    # The original nonpersistent B32 feature producer is unchanged.
                    # A stopped dataset's in-memory features may be regenerated;
                    # closed predictions and complete R3 optimizer/RNG states stay.
                    return original_features(*args,**kwargs)
                evaluate.run_probe,evaluate.ridge_probe,evaluate.produce_missing_features=probe,ridge,features
                atomic_json(output/"configuration.json",readout)
                try:
                    result=evaluate.run(dict(readout,output=str(output/"readout")))
                except ContinuationRequired:
                    atomic_json(output/"continuation.json",dict(status="SAVED_SAFE_BOUNDARY",job=os.environ["SLURM_JOB_ID"],seconds=time.monotonic()-started,source_identity=identity))
                    return 75
                finally:
                    evaluate.run_probe,evaluate.ridge_probe,evaluate.produce_missing_features=original_probe,original_ridge,original_features
                if len(result["files"])!=18:
                    raise ValueError("Original nine tasks times R1/R3 required")
                seconds=time.monotonic()-started
                atomic_json(output/"summary.json",dict(run=readout["run"],samples=readout["samples"],
                    status=WAITING,statistics_complete=False,statistics_backend="slurm_cpu",
                    source_run=readout["source_run"],source_training_budget=9000000,training_performed=False,
                    gpu_readout_seconds=seconds,training_and_gpu_readout_seconds=seconds,
                    gpu_job_id=os.environ["SLURM_JOB_ID"],gpu_node=c["node"],gpu_uuid=c["gpu_uuid"],
                    continuation_native_R3_state=True,original_feature_producer_unchanged=True,
                    power_mean_watts=None,code_source_validation=c["source_validation"]))
                print(json.dumps(dict(status=WAITING,run=readout["run"],seconds=seconds)),flush=True)
                return 0
        finally:
            lock.close()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args()
    raise SystemExit(run(json.loads(Path(args.configuration).read_text())))
