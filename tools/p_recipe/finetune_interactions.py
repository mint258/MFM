"""Paired molecule-count difference-in-differences on retained F draws only."""
from finetune_statistics import interval


def difference_in_differences(primaries, conditions, task):
    if len(primaries)!=4 or len(conditions)!=4:
        raise ValueError("Exactly full-left/full-right/frozen-left/frozen-right required")
    identity=primaries[0]["retained"]["identity"]
    rows=[];draws=[]
    for primary,condition in zip(primaries,conditions):
        if primary["status"]!="COMPLETE":
            raise ValueError("Only closed primary producers may be consumed")
        other=primary["retained"]["identity"]
        if (any(identity[k]!=other[k] for k in ("groups","bootstrap_seed","samples"))
                or any(identity["input_identity"][k]!=other["input_identity"][k]
                    for k in ("scratch","random_reference"))):
            raise ValueError("Original paired population/draws/baselines differ")
        row=next(r for r in primary["rows"] if r["condition"]==condition and r["task"]==task)
        value=primary["retained"]["draws"][condition+"/"+task]["scratch_improvement"]
        if len(value)!=1000:
            raise ValueError("Original1000 aligned molecular draws required")
        rows.append(row);draws.append(value)
    differences=[None if any(v is None for v in values)
        else values[0]-values[1]-values[2]+values[3] for values in zip(*draws)]
    bounds,defined=interval(differences)
    def contrast(field):
        values=[r[field] for r in rows]
        return values[0]-values[1]-values[2]+values[3]
    return dict(conditions=list(conditions),task=task,
        delta_seed_mean=contrast("scratch_improvement_seed_mean"),
        delta_ensemble=contrast("ensemble_scratch_improvement"),
        ensemble_ci_lower=bounds[0] if bounds else None,
        ensemble_ci_upper=bounds[1] if bounds else None,
        bootstrap_defined=defined,
        ci_estimand="full_minus_frozen_molecule_count_gain_of_mean_predictions",
        interpretation="Descriptive; seed-mean point and ensemble CI are distinct",
        new_bootstrap_draws=0,new_model_fits=0,recipe_changed=False)
