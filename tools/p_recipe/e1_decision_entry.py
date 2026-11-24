"""Registered E1 closure on original primary draws; no fits or resampling."""
import argparse,fcntl,json,os
from pathlib import Path
from e1_decision import compare_frozen,compare_full,choose_k,KS
from e1_training_entry import validate as validate_training
from i1_decision_entry import retained_clip_report
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json,fingerprint

def validate_frozen_source(k,native,evaluation,summary):
    if (native.get("samples")!=3000000 or native.get("seed")!=0 or
            native.get("conformer_cap",10)!=k or native.get("budget_curve")):
        raise ValueError("E1 requires exact own3M seed0 and registered cap")
    if (evaluation["samples"]!=3000000 or evaluation.get("source_training_budget",3000000)!=3000000 or
            evaluation.get("source_run",evaluation["run"])!=native["run"] or
            evaluation.get("layer",6)!=6 or evaluation.get("representation","H0")!="H0" or
            evaluation.get("readout_seed",0)!=0):
        raise ValueError("E1 original frozen source/budget/L6 H0 differs")
    if summary.get("status")!="COMPLETE" or summary["samples"]!=3000000:
        raise ValueError("E1 original frozen scoring incomplete")

def load_cell(k,entry,baseline):
    native=(json.loads(Path(entry["native_configuration"]).read_text()) if k==10 else
            validate_training(json.loads(Path(entry["managed_configuration"]).read_text())))
    if k==10 and native!=baseline:raise ValueError("k10 must reuse original round4 F2")
    evaluation=json.loads(Path(entry["evaluation_configuration"]).read_text())
    root=Path(evaluation["output"])
    summary=json.loads((root/"summary.json").read_text())
    validate_frozen_source(k,native,evaluation,summary)
    if k<10:
        actual=json.loads((Path(native["output"])/"summary.json").read_text())
        if actual.get("samples")!=3000000 or actual.get("updates")!=93750:
            raise ValueError("Actual E1 own3M training incomplete")
    cp=fingerprint(Path(native["output"])/"samples_3000000.pt")
    seen=set()
    for path in entry["full_fit_configurations"]:
        c=json.loads(Path(path).read_text());binding=c["source_binding"]
        if (c.get("ready") is not True or c["mode"]!="full" or c["pretraining_seed"]!=0 or
                binding["checkpoint"]!=cp["path"] or binding["bytes"]!=cp["bytes"] or
                binding["samples"]!=3000000 or binding["source_training_budget"]!=3000000):
            raise ValueError("E1 full fine-tune source is not the original own3M checkpoint")
        if json.loads((Path(c["output"])/"summary.json").read_text()).get("status")!="COMPLETE":
            raise ValueError("An original E1 full fit is incomplete")
        seen.add((c["task"],c["seed"]))
    from finetune_statistics import TASKS
    if len(entry["full_fit_configurations"])!=12 or seen!={(t,s) for t in TASKS for s in (0,1,2)}:
        raise ValueError("E1 full4tasks x3seeds source coverage differs")
    full=json.loads(Path(entry["full_primary"]).read_text())
    frozen=json.loads((root/"readout/scores.json").read_text())
    identity=dict(native_checkpoint=cp,frozen=fingerprint(root/"readout/scores.json"),
                  full=fingerprint(entry["full_primary"]))
    return native,frozen,full,identity

def run(c):
    if c.get("ready") is not True:raise ValueError("Original four-cell primaries must close first")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        output=Path(c["output"]);output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"seed0_complete.json").exists():raise ValueError("Original E1 seed0 decision is closed; reuse")
            base=json.loads(Path(c["baseline_configuration"]).read_text())
            entries={x["k"]:x for x in c["cells"]}
            if set(entries)!=set(KS):raise ValueError("All four registered cells required")
            loaded={};rows={};identities={}
            for k in KS:
                if stop.requested:return 75
                entry=entries[k]
                if entry.get("missing"):
                    rows[k]=dict(k=k,missing=True,timebox=entry["timebox"])
                else:loaded[k]=load_cell(k,entry,base)
            if 10 not in loaded:raise ValueError("Original k10 reference cannot be missing")
            for k,(native,frozen,full,identity) in loaded.items():
                if stop.requested:return 75
                group=entries[k]["full_group"]
                rows[k]=dict(k=k,frozen_R1=compare_frozen(frozen,loaded[10][1],"R1"),
                    frozen_R3=compare_frozen(frozen,loaded[10][1],"R3"),
                    full=compare_full(full,loaded[10][2],group,entries[10]["full_group"]),
                    full_task_rows=[r for r in full["rows"] if r["condition"]==group],
                    frozen_primary=identity["frozen"]["path"],full_primary=identity["full"]["path"],
                    gradient_clip_report=retained_clip_report(native))
                identities[str(k)]=identity
            choice=choose_k(rows)
            result=json.loads(Path(c["plan"]).read_text())
            required=choice["conditional_seed1_required_for_adoption"] and c["adoption_intended"]
            result.update(status="WAITING_CONDITIONAL_SEED1" if required else "COMPLETE",
                k_star=None if required else choice["provisional_k_star"],
                provisional_k_star=choice["provisional_k_star"],results=[rows[k] for k in KS],
                conditional_seed1_required=required,conditional_seed1_complete=False,
                adoption_intended=c["adoption_intended"],source_identity=identities,
                original_bootstrap_draws_replayed=0,new_bootstrap_draws=0,
                final_REPORT_generated=False,job=os.environ["SLURM_JOB_ID"])
            for cell in result['cells']:
                k=cell['k']
                if rows[k].get('missing'):
                    cell['full_finetuning']='UNRESOLVED_MISSING_ORIGINAL_TIMEBOX'
                else:
                    cell['training']='REUSED_ROUND4_F2_OWN3M' if k==10 else 'COMPLETE_OWN3M'
                    cell['frozen']='COMPLETE_ORIGINAL_R1_R3'
                    cell['full_finetuning']='COMPLETE_ORIGINAL_FULL12'
            if not required:
                from e1_report import validate_closed
                validate_closed(result)
            atomic_json(output/"primary.json",result)
            atomic_json(output/"seed0_complete.json",dict(status="COMPLETE_SEED0",source_identity=identities,
                job=os.environ["SLURM_JOB_ID"],conditional_seed1_required=required))
            print(json.dumps(dict(status=result["status"],k_star=result["k_star"],
                provisional_k_star=result["provisional_k_star"],conditional_seed1_required=required)),flush=True)
            return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    a=p.parse_args()
    if os.environ.get("CUDA_VISIBLE_DEVICES")!="":raise ValueError("CPU-only E1 decision required")
    raise SystemExit(run(json.loads(a.configuration.read_text())))
