"""First CPU summaries of newly closed second-seed predictions; primary scores are never replayed."""
from .selection import IncompleteComparison,SEED
from .comparisons import index_predictions,paired_improvement
from .c1_reporting import single_model_statistics

def summarize_confirmation(primary,candidate,references,*,sources,scaffold_cv=False,fit_metadata=None):
    """Bind exact original candidate populations, then make only new seed2 statistics/contrasts."""
    original=index_predictions(primary,allow_native_missing=True)
    second=index_predictions(candidate,allow_native_missing=True)
    if set(original)!=set(second):
        raise IncompleteComparison("Second seed changed the original candidate TEST population")
    for identity,row in second.items():
        first=original[identity]
        for field in ("y_true","full_inchikey","training_mean","repetition","fold"):
            if row.get(field)!=first.get(field):
                raise IncompleteComparison("Second seed changed frozen TEST labels/identity/folds or actual TRAIN mean")
        if (row["prediction"] is None)!=(first["prediction"] is None):
            raise IncompleteComparison("Second seed changed native-feature availability")
    available=[row for row in second.values() if row["prediction"] is not None]
    if not sources:raise IncompleteComparison("Closed second-seed native source evidence is required")
    statistics=single_model_statistics(available,scaffold_cv)
    contrasts=[dict(comparison=name,reference_model_seed=SEED,candidate_model_seed=SEED+1,
                    **paired_improvement(rows,candidate,allow_native_missing=True,scaffold_cv=scaffold_cv))
               for name,rows in references.items()]
    return dict(status="COMPLETED",model_seed=SEED+1,split_and_statistics_seed=SEED,
                sources=sources,statistics=statistics,comparisons=contrasts,fit_metadata=fit_metadata or {},
                original_labels_or_masks_changed=False,task_roster_reselection=False,
                primary_scores_recomputed=False,new_statistics_only_for_second_seed=True)
