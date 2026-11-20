"""Close required neural confirmations without changing frozen tasks or replaying primary scores."""
import math
from .selection import IncompleteComparison,SEED

def cell_key(row,baseline=False):
    return (row["endpoint_key"],row.get("model","Chemprop-v2")) if baseline else (
        row["endpoint_key"],row["feature_group"],row["learner"])

def _unique(rows,baseline=False):
    result={}
    for row in rows:
        key=cell_key(row,baseline)
        if key in result:raise IncompleteComparison("Duplicate final-report configuration: "+repr(key))
        result[key]=row
    return result

def _closed_confirmation(plan,evidence):
    if evidence.get("model_seed")!=SEED+1:
        raise IncompleteComparison("Confirmation model seed differs from the registered second seed")
    if evidence.get("split_and_statistics_seed")!=SEED:
        raise IncompleteComparison("A confirmation changed the frozen split/statistics seed")
    if evidence.get("original_labels_or_masks_changed",False) or evidence.get("task_roster_reselection",False):
        raise IncompleteComparison("A confirmation changed original scientific inputs or the task roster")
    if evidence.get("status")=="UNRESOLVED":
        if not evidence.get("native_failure_reason") or not evidence.get("sources"):
            raise IncompleteComparison("An unresolved confirmation requires actual native failure evidence")
        return dict(completed=False,confirmation_status="SECOND_SEED_UNRESOLVED_NATIVE_FAILURE",
                    confirmation_reason=evidence["native_failure_reason"])
    if evidence.get("status")!="COMPLETED" or not evidence.get("sources"):
        raise IncompleteComparison("Required confirmation is still pending or lacks native source binding")
    stats=evidence.get("statistics",{})
    if any(not isinstance(stats.get(key),(int,float)) or isinstance(stats[key],bool)
           or not math.isfinite(stats[key]) for key in ("MAE","RAE")):
        raise IncompleteComparison("Closed confirmation lacks finite original-unit MAE/RAE")
    if stats.get("n_test_rows",0)<1:
        raise IncompleteComparison("Closed confirmation has no original TEST observations")
    comparisons=evidence.get("comparisons",[])
    names=[row["comparison"] for row in comparisons]
    if len(set(names))!=len(names):
        raise IncompleteComparison("Duplicate second-seed registered comparison")
    if plan["reason"]=="FINAL_SIGNIFICANT_IMPROVEMENT":
        triggering=plan.get("triggering_comparisons") or [plan.get("triggering_comparison",plan.get("reference_model"))]
        if not all(triggering):raise IncompleteComparison("The registered original comparison identity is absent")
        if not set(triggering).issubset(names):
            raise IncompleteComparison("A required original significant comparison lacks second-seed evidence")
        reproduced=any(row["significant_improvement"] for row in comparisons if row["comparison"] in triggering)
        state="SECOND_SEED_SIGNIFICANT_IMPROVEMENT_REPRODUCED" if reproduced else "SECOND_SEED_DID_NOT_REPRODUCE_SIGNIFICANCE"
    elif plan["reason"] in {"TRAINING_ROLLBACK_REDO","SOURCE_BINDING_ERROR_REQUIRED_REDO_OF_TRAINED_1H_SAMPLES"}:
        state="REQUIRED_TRAINING_REDO_SECOND_SEED_REPORTED"
    else:
        raise IncompleteComparison("Unregistered neural confirmation reason")
    return dict(completed=True,confirmation_status=state,confirmation_reason=plan["reason"])

def finalize_c1(primary_rows,required_plan,evidence):
    """Return both seed rows. Primary estimates are copied exactly, never recalculated."""
    primary=_unique(primary_rows)
    plans=_unique(required_plan)
    if set(evidence)!=set(plans):
        raise IncompleteComparison("Every required confirmation must close; unplanned second seeds are rejected")
    if not set(plans).issubset(primary):
        raise IncompleteComparison("A second seed cannot introduce a new C1 task or configuration")
    table=[];contrasts=[]
    for key,original in primary.items():
        row=dict(original,report_stage="FINAL",task_roster_reselection=False,
                 primary_statistics_recomputed=False)
        if key not in plans:
            row.update(confirmation_status="NOT_REQUIRED_UNDER_ONE_SEED_RULE")
            table.append(row);continue
        plan=plans[key]
        if plan["learner"]!="TabPFN" or plan["reason"]!="FINAL_SIGNIFICANT_IMPROVEMENT":
            raise IncompleteComparison("Traditional ML never acquires a second seed")
        if plan.get("frozen_B1_role") not in {"RETAIN","APPENDIX"}:
            raise IncompleteComparison("A nonfinal C1 cell cannot trigger improvement confirmation")
        native=evidence[key];closed=_closed_confirmation(plan,native)
        row.update({k:v for k,v in closed.items() if k!="completed"})
        row["completed_seeds"]=2 if closed["completed"] else 1
        row["confirmation_sources"]=native["sources"]
        table.append(row)
        if closed["completed"]:
            second=dict(original,**native.get("fit_metadata",{}))
            second.update(native["statistics"])
            second.update(model_seed=SEED+1,completed_seeds=2,report_stage="FINAL",
                          confirmation_status=closed["confirmation_status"],confirmation_reason=plan["reason"],
                          frozen_B1_role=original["frozen_B1_role"],task_roster_reselection=False,
                          statistics_source="FIRST_CPU_REPORT_OF_CLOSED_SECOND_SEED_PREDICTIONS",
                          primary_statistics_recomputed=False,confirmation_sources=native["sources"])
            table.append(second)
            contrasts.extend(dict(item,endpoint_key=key[0],feature_group=key[1],learner=key[2],
                                  model_seed=SEED+1,task_roster_reselection=False)
                             for item in native.get("comparisons",[]))
    return table,contrasts

def finalize_baseline_confirmations(screen,required_plan,evidence):
    """Supplement the single frozen B1 screen; never rerun screening or modify its decisions."""
    roster={row["endpoint_key"]:row for row in screen}
    if len(roster)!=len(screen):raise IncompleteComparison("Duplicate frozen B1 endpoint")
    plans=_unique(required_plan,True)
    if set(evidence)!=set(plans):raise IncompleteComparison("Missing or unplanned baseline confirmation")
    output=[]
    for key,plan in plans.items():
        if key[0] not in roster or key[1]!="Chemprop-v2":
            raise IncompleteComparison("Only a frozen original Chemprop task can acquire confirmation")
        native=evidence[key];closed=_closed_confirmation(plan,native)
        result=dict(plan,**{k:v for k,v in closed.items() if k!="completed"},
                    frozen_B1_decision=roster[key[0]]["decision"],task_roster_reselection=False,
                    sources=native["sources"],completed_seeds=2 if closed["completed"] else 1)
        if closed["completed"]:result.update(native["statistics"],model_seed=SEED+1)
        output.append(result)
    return output
