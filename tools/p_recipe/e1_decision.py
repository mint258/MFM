"""E1 decision algebra on original retained molecular draws; no new sampling."""
import numpy as np
from finetune_statistics import TASKS
from phychem_mfm.phase1.p_recipe_seed_policy import combined_seed_decision

KS=(1,2,5,10)

def full_score(primary,group):
    if primary["status"]!="COMPLETE":raise ValueError("Closed full primary required")
    state=primary["retained"];identity=state["identity"]
    if not identity.get("seed_mean_draws") or state["completed_draws"]!=1000:
        raise ValueError("E1 seed-mean primary1000 draws required")
    rows={r["task"]:r for r in primary["rows"] if r["condition"]==group}
    if set(rows)!=set(TASKS) or any(r["seed_count"]!=3 for r in rows.values()):
        raise ValueError("Exact full4tasks x3seeds required")
    values=np.asarray([state["draws"][group+"/"+t]["scratch_improvement_seed_mean"] for t in TASKS],dtype=np.float64)
    if values.shape!=(4,1000) or not np.isfinite(values).all():
        raise ValueError("Incomplete seed-mean draws")
    return (float(np.mean([rows[t]["scratch_improvement_seed_mean"] for t in TASKS])),
            values.mean(axis=0).tolist())

def compare_full(candidate,baseline,candidate_group,baseline_group):
    a,b=(p["retained"]["identity"] for p in (candidate,baseline))
    if (any(a[k]!=b[k] for k in ("groups","bootstrap_seed","samples"))
            or any(a["input_identity"][k]!=b["input_identity"][k] for k in ("scratch","random_reference"))):
        raise ValueError("Full molecular draws or baseline bindings differ")
    ca,cd=full_score(candidate,candidate_group);ba,bd=full_score(baseline,baseline_group)
    return combined_seed_decision({0:(ca,ba,cd,bd)})

def compare_frozen(candidate,baseline,readout="R3"):
    a,b=(p[readout] for p in (candidate,baseline))
    if any(not p.get("complete") or p["bootstrap_samples"]!=1000 or p["bootstrap_defined"]!=1000 for p in (a,b)):
        raise ValueError("Original frozen seven-task scores incomplete")
    if any(a["paired_bootstrap"][k]!=b["paired_bootstrap"][k] for k in ("groups","seed")):
        raise ValueError("Original frozen molecular draws differ")
    return combined_seed_decision({0:(a["mean_normalized_improvement"],b["mean_normalized_improvement"],
        a["paired_bootstrap"]["values"],b["paired_bootstrap"]["values"])})

def choose_k(rows):
    """Provisional local choice; a selected WIN must confirm before adoption."""
    if set(rows)!=set(KS):raise ValueError("All four registered cells must be accounted for")
    allowed=[]
    for k,row in rows.items():
        if row.get("missing"):continue
        verdicts=[row[x]["decision"]["verdict"] for x in ("frozen_R3","full")]
        if all(v in ("win","tie") for v in verdicts):allowed.append(k)
    if not allowed:raise ValueError("Original k10 identity reference must remain eligible")
    chosen=min(allowed)
    needs_seed1=chosen<10 and any(rows[chosen][x]["decision"]["verdict"]=="win" for x in ("frozen_R3","full"))
    return dict(provisional_k_star=chosen,conditional_seed1_required_for_adoption=needs_seed1,
        missing_ks=[k for k in KS if rows[k].get("missing")],
        status="WAITING_CONDITIONAL_SEED1" if needs_seed1 else "SEED0_DECISION_COMPLETE",
        shared_P_S_adoption_requires_user_confirmation=True)
