"""E1 guarded runner: reuse original P training, complete-state and exit providers."""
import argparse,json,os
from pathlib import Path
import i1_training_entry as shared
from phychem_mfm.phase1.p_recipe_conformers import training_conformer_cap

def validate(c):
    original=json.loads(Path(c["baseline_configuration"]).read_text())
    native=c["training_configuration"]
    if training_conformer_cap(native) not in (1,2,5):
        raise ValueError("Only the three new E1 cells may train; k10 is reused")
    allowed={"run","arm","output","checkpoint_samples"}
    for key,value in original.items():
        if key not in allowed and native.get(key)!=value:
            raise ValueError("E1 changed another baseline field: "+key)
    if set(native)-set(original)-{"conformer_cap","checkpoint_samples"}:
        raise ValueError("Unregistered E1 native configuration keys")
    if (native["samples"]!=3000000 or native["seed"]!=0
            or native["batch_size"]!=32 or native["microbatch_size"]!=32
            or native["activation_checkpointing"] is not False
            or native["p_recipe"]["anti_collapse"] is not True
            or "window2_TRAIN_normalization_parameters_20261107_v1" not in native["normalizations"]
            or native["output"]!=c["output"]):
        raise ValueError("Frozen original own-budget3M B32/FP32 recipe required")
    return dict(native)

def run(c):
    code=shared.run(c,validate_configuration=validate,science_change="TRAIN conformer_cap; published fixed_random after D5")
    receipt=json.loads((Path(c["output"])/("managed_attempt_"+os.environ["SLURM_JOB_ID"]+".json")).read_text())
    result=receipt["result"]
    # A complete-state handoff is a continuation, never a successful3M finish.
    return code if result.get("samples",0)==3000000 else 75

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args();raise SystemExit(run(json.loads(Path(args.configuration).read_text())))
