"""A1 five-readout-seed noise; reuse all closed seed0 primary statistics."""
import math
import numpy as np
from phychem_mfm.phase1.v3_dev_evaluation import error
from phychem_mfm.phase1.v3_downstream_targets import PRIMARY_TASK_IDS
from finetune_statistics import same_population, normalized, interval


def summarize_noise(predictions,reference,seed0_points,original_summary,*,
                    input_identity,state=None,checkpoint=None,should_stop=None):
    primary=tuple(sorted(original_summary["included_tasks"]))
    if (original_summary["bootstrap_samples"]!=1000 or original_summary["bootstrap_seed"]!=20261025
            or original_summary["bootstrap_unit"]!="molecule"):
        raise ValueError("Original registered bootstrap contract differs")
    if (len(primary)!=7 or set(primary)!=set(PRIMARY_TASK_IDS)
            or set(predictions)!=set(reference) or set(predictions)!=set(seed0_points)
            or len(predictions)!=9):
        raise ValueError("Original nine-task panel and seven-task primary coverage required")
    points={};new_cyp=sorted(set(predictions)-set(primary))
    for task in sorted(predictions):
        values=predictions[task]
        if reference[task].task.task_id!=task:
            raise ValueError("Task key/native prediction identity differs")
        if len(values)!=5:
            raise ValueError("Exactly original seed0 plus new seeds1-4 required")
        for value in values:
            same_population(reference[task],value)
        original=seed0_points[task]
        errors=[original["error"]]+[error(p) for p in values[1:]]
        scores=[original["score"]]+[normalized(e,original["E_ref"]) for e in errors[1:]]
        if task in primary and any(v is None or not math.isfinite(v) for v in scores):
            raise ValueError("A primary task has unavailable five-seed scores")
        points[task]=(errors,scores)
    populations={}
    for task in new_cyp:
        p=predictions[task][0]
        populations.setdefault(p.task.dataset_id,set()).update(p.molecule_uids)
    populations={k:sorted(v) for k,v in sorted(populations.items())}
    identity=dict(input_identity=input_identity,groups=populations,tasks=new_cyp,
                  bootstrap_seed=20261025,samples=1000,
                  original_seed0_primary_replayed=False)
    if state is None:
        state=dict(identity=identity,completed_draws=0,draws={t:[] for t in new_cyp},
                   rng_state=np.random.default_rng(20261025).bit_generator.state)
    elif state["identity"]!=identity:
        raise ValueError("Unfinished A1 primary input identity changed")
    done=state["completed_draws"]
    if (not isinstance(done,int) or not 0<=done<=1000
            or set(state["draws"])!=set(new_cyp)
            or any(len(v)!=done for v in state["draws"].values())):
        raise ValueError("A1 bootstrap cursor/retained values inconsistent")
    rng=np.random.default_rng();rng.bit_generator.state=state["rng_state"]
    lookup={}
    for task in new_cyp:
        rows={}
        for index,uid in enumerate(predictions[task][0].molecule_uids):
            rows.setdefault(uid,[]).append(index)
        lookup[task]=rows
    for i in range(done,1000):
        if should_stop is not None and should_stop():
            if checkpoint:checkpoint(state)
            return dict(status="CONTINUATION_REQUIRED",state=state)
        draws={dataset:rng.choice(groups,len(groups),replace=True).tolist()
               for dataset,groups in populations.items()}
        for task in new_cyp:
            p,ref=predictions[task][0],reference[task]
            indices=[i for uid in draws[p.task.dataset_id] for i in lookup[task].get(uid,())]
            state["draws"][task].append(normalized(error(p,indices),error(ref,indices)))
        state["completed_draws"]=i+1
        state["rng_state"]=rng.bit_generator.state
        if checkpoint and (i+1)%50==0:checkpoint(state)
    rows=[]
    tau_half=max(.01,.05*original_summary["mean_normalized_improvement"])/2
    for task in sorted(predictions):
        errors,scores=points[task]
        if task in primary:
            bounds=original_summary["tasks"][task]["bootstrap_ci"]
            count=original_summary["tasks"][task]["bootstrap_defined"]
            origin="existing_original_seed0_primary"
        else:
            bounds,count=interval(state["draws"][task])
            origin="first_report_only_CYP_seed0_bootstrap"
        rows.append(_row(task,errors,scores,bounds,count,origin,tau_half,False))
    mean_scores=[original_summary["mean_normalized_improvement"]]+[
        float(np.mean([points[t][1][seed] for t in primary])) for seed in range(1,5)]
    rows.append(_row("PRIMARY7_MEAN",None,mean_scores,original_summary["bootstrap_ci"],
        original_summary["bootstrap_defined"],"existing_original_seed0_primary",
        tau_half,True))
    return dict(status="COMPLETE",rows=rows,retained_new_CYP_seed0=state,
                original_seed0_primary_replayed=False,new_model_fits=0)


def _row(task,errors,scores,bounds,defined,origin,tau_half,is_primary_mean):
    finite=all(v is not None and math.isfinite(v) for v in scores)
    mean=float(np.mean(scores)) if finite else None
    std=float(np.std(scores,ddof=1)) if finite else None
    width=(bounds[1]-bounds[0])/2 if bounds is not None else None
    ratio=std/width if std is not None and width is not None and width>0 else None
    row=dict(task=task,seed_count=5,primary_mean=is_primary_mean,
        included_in_primary_mean=task in PRIMARY_TASK_IDS,
        error_seed_mean=float(np.mean(errors)) if errors and all(e is not None for e in errors) else None,
        error_seed_std=float(np.std(errors,ddof=1)) if errors and all(e is not None for e in errors) else None,
        score_seed_mean=mean,score_seed_std=std,
        bootstrap_halfwidth_seed0=width,std_over_seed0_bootstrap_halfwidth=ratio,
        bootstrap_seed0_ci_lower=bounds[0] if bounds else None,
        bootstrap_seed0_ci_upper=bounds[1] if bounds else None,
        bootstrap_defined=defined,bootstrap_halfwidth_origin=origin,
        tau_half_original_seed0_primary=tau_half,
        propose_multiseed_readout=bool(is_primary_mean and std is not None and std>=tau_half),
        bootstrap_seed=20261025,bootstrap_unit="molecule",
        proposal_only_no_decision_rule_changed=True)
    for seed in range(5):
        row["seed"+str(seed)+"_error"]=errors[seed] if errors else None
        row["seed"+str(seed)+"_score"]=scores[seed]
    return row
