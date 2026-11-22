"""Original frozen R1/R3 for the authorized I1 own-budget3M checkpoint."""
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


def make_i1_readout(source, source_path, output, store):
    native=source["training_configuration"]
    if (native["arm"]!="I1" or native["samples"]!=3000000 or native["seed"]!=0
            or native["batch_size"]!=32 or native["microbatch_size"]!=32
            or native["p_recipe"]["anti_collapse"] is not False
            or native["activation_checkpointing"] is not False):
        raise ValueError("Only the registered own-budget3M seed0 B4-off source is authorized")
    output=Path(output)
    return dict(run=native["run"]+"_frozen_readout",arm="I1",stage=0,round=0,
        study_revision="fixed_20261115",samples=3000000,source_run=native["run"],
        source_configuration=str(source_path),source_training_budget=3000000,
        checkpoint=str(Path(native["output"])/"samples_3000000.pt"),
        checkpoint_resolver="actual_own_budget_terminal_checkpoint",
        layer=6,representation="H0",output=str(output),
        features=str(output/"features"),persist_features=True,R1_backend="slurm_cpu",
        store=str(store),statistics_backend="slurm_cpu",evaluation_samples=[3000000],
        authority="docs/p_recipe/USER_DIRECTIVE_20261122B.md",
        bootstrap_samples=1000,bootstrap_seed=20261025,
        new_training=False,new_seeds=False,readout_seed=0)

def validate(c):
    source_path=Path(c["source_configuration"])
    source=json.loads(source_path.read_text())
    if c["new_training"] is not False or c["new_seeds"] is not False:
        raise ValueError("This entry must not train a P model or add a seed")
    expected=make_i1_readout(source,source_path,c["output"],c["readout"]["store"])
    if c["readout"]!=expected:raise ValueError("Original frozen-R1/R3 recipe or I1 ancestry changed")
    if fingerprint(expected["checkpoint"])!=c["checkpoint_identity"]:
        raise ValueError("Actual own3M final checkpoint binding changed")
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
                    configuration,dataset,view=args
                    path=evaluate.feature_path(configuration,dataset)
                    if path.is_file():return original_features(*args,**kwargs)
                    payload=original_features(dict(configuration,persist_features=False),dataset,view,**kwargs)
                    boundary()
                    from noise_entry import atomic_checkpoint
                    path.parent.mkdir(parents=True,exist_ok=True)
                    atomic_checkpoint(path,payload)
                    return payload
                evaluate.run_probe,evaluate.ridge_probe,evaluate.produce_missing_features=probe,ridge,features
                atomic_json(output/"configuration.json",readout)
                try:
                    from i1_frozen_readout import gpu_r3
                    result=gpu_r3(dict(readout,output=str(output/"readout")))
                except ContinuationRequired:
                    atomic_json(output/"continuation.json",dict(status="SAVED_SAFE_BOUNDARY",job=os.environ["SLURM_JOB_ID"],seconds=time.monotonic()-started,source_identity=identity))
                    return 75
                finally:
                    evaluate.run_probe,evaluate.ridge_probe,evaluate.produce_missing_features=original_probe,original_ridge,original_features
                if len(result["files"])!=9:
                    raise ValueError("Original nine GPU R3 cells required; R1 is deferred to CPU")
                seconds=time.monotonic()-started
                atomic_json(output/"summary.json",dict(run=readout["run"],samples=readout["samples"],
                    status=WAITING,statistics_complete=False,statistics_backend="slurm_cpu",
                    source_run=readout["source_run"],source_training_budget=readout["source_training_budget"],training_performed=False,
                    gpu_readout_seconds=seconds,training_and_gpu_readout_seconds=seconds,
                    gpu_job_id=os.environ["SLURM_JOB_ID"],gpu_node=c["node"],gpu_uuid=c["gpu_uuid"],
                    continuation_native_R3_state=True,original_feature_producer_unchanged=True,
                    R1_deferred_to_CPU=True,H0_cache_identity={d:fingerprint(evaluate.feature_path(readout,d)) for d in ["expansionrx","cyp_isoform","qm9"]},
                    power_mean_watts=None,code_source_validation=c["source_validation"]))
                print(json.dumps(dict(status=WAITING,run=readout["run"],seconds=seconds)),flush=True)
                return 0
        finally:
            lock.close()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args()
    raise SystemExit(run(json.loads(Path(args.configuration).read_text())))
