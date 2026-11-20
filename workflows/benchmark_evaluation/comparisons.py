"""Paired final comparisons and the user's conditional second-seed policy.

These are new reporting statistics on original closed predictions. They never
change B1 membership, labels, original CV folds, or model hyperparameters.
"""
import math
import numpy as np
from .selection import IncompleteComparison, SEED

FOLDS = frozenset((r, f) for r in range(5) for f in range(5))

def index_predictions(rows, allow_native_missing=False):
    mapping = {}
    for row in rows:
        identity = row.get("evaluation_id", row.get("record_id"))
        if identity is None or not str(identity).strip() or not row.get("full_inchikey"):
            raise IncompleteComparison("Original evaluation ID and full molecular identity are required")
        identity = str(identity)
        if identity in mapping:
            raise IncompleteComparison("Duplicate original evaluation ID")
        value = row.get("prediction")
        if value is None:
            if not allow_native_missing:
                raise IncompleteComparison("A missing prediction cannot shrink an ordinary comparison")
        elif not math.isfinite(float(value)):
            raise IncompleteComparison("A nonfinite model prediction is not an availability declaration")
        if not (math.isfinite(float(row["y_true"])) and math.isfinite(float(row["training_mean"]))):
            raise IncompleteComparison("Original labels and fit TRAIN means must be finite")
        mapping[identity] = row
    if not mapping:
        raise IncompleteComparison("No predictions are available")
    return mapping

def paired_improvement(reference, candidate, *, allow_native_missing=False, scaffold_cv=False):
    """Use a declared common native-feature population only for C1 missingness.

    Every molecular bootstrap draw is paired across methods. Each method keeps
    its actual original TRAIN-mean reference. CV significance uses Tukey HSD on
    all25 original fold scores; official-split significance uses the paired
    RAE-improvement95% interval. Pooled RAE is also reported for transparency.
    """
    ref = index_predictions(reference, allow_native_missing)
    cand = index_predictions(candidate, allow_native_missing)
    if not allow_native_missing and set(ref) != set(cand):
        raise IncompleteComparison("Ordinary comparison populations differ")
    shared = sorted(set(ref) & set(cand))
    for identity in shared:
        left, right = ref[identity], cand[identity]
        if left["y_true"] != right["y_true"] or left["full_inchikey"] != right["full_inchikey"]:
            raise IncompleteComparison("Original labels or molecular groups differ")
        if scaffold_cv and (left.get("repetition"), left.get("fold")) != (right.get("repetition"), right.get("fold")):
            raise IncompleteComparison("Original CV fold membership differs")
    ids = [identity for identity in shared
           if ref[identity]["prediction"] is not None and cand[identity]["prediction"] is not None]
    if not ids:
        raise IncompleteComparison("No common native-feature predictions are available")
    y = np.asarray([ref[key]["y_true"] for key in ids], float)
    p = np.asarray([[side[key]["prediction"] for key in ids] for side in (ref,cand)], float)
    means = np.asarray([[side[key]["training_mean"] for key in ids] for side in (ref,cand)], float)
    groups = np.asarray([str(ref[key]["full_inchikey"]) for key in ids])
    unique,inverse = np.unique(groups,return_inverse=True)
    errors = np.asarray([np.bincount(inverse,weights=np.abs(y-value),minlength=len(unique)) for value in p])
    references = np.asarray([np.bincount(inverse,weights=np.abs(y-mean),minlength=len(unique)) for mean in means])
    divisors = references.sum(axis=1)
    if np.any(divisors <= 0):
        raise IncompleteComparison("A TRAIN-mean reference has zero error on the comparison population")
    rae = errors.sum(axis=1)/divisors
    draws = np.empty(1000,float);rng = np.random.default_rng(SEED)
    for index in range(1000):
        sample = rng.integers(0,len(unique),size=len(unique))
        divisor = references[:,sample].sum(axis=1)
        if np.any(divisor <= 0):
            raise IncompleteComparison("A whole-molecule paired draw has zero TRAIN-reference error")
        values = errors[:,sample].sum(axis=1)/divisor
        draws[index] = values[0]-values[1]
    lower,upper = map(float,np.quantile(draws,[.025,.975]))
    answer = dict(reference_RAE=float(rae[0]),candidate_RAE=float(rae[1]),
                  reference_MAE=float(np.abs(y-p[0]).mean()),candidate_MAE=float(np.abs(y-p[1]).mean()),
                  pooled_RAE_improvement=float(rae[0]-rae[1]),
                  paired_RAE_improvement_CI95_low=lower,paired_RAE_improvement_CI95_high=upper,
                  paired_RAE_improvement_SE=float(draws.std(ddof=1)),bootstrap_draws=1000,
                  common_TEST_rows=len(ids),common_TEST_molecules=len(unique),
                  original_reference_rows=len(ref),original_candidate_rows=len(cand),
                  reference_rows_outside_common_available_population=len(ref)-len(ids),
                  candidate_rows_outside_common_available_population=len(cand)-len(ids),
                  comparison_population="DECLARED_COMMON_NATIVE_FEATURES" if allow_native_missing else "IDENTICAL_ORIGINAL_TEST",
                  training_mean_policy="Each method retains its actual fit TRAIN mean; no TEST mean",
                  significance_method="PAIRED_MOLECULE_BOOTSTRAP95",
                  significant_improvement=lower > 0)
    if scaffold_cv:
        from scipy.stats import tukey_hsd
        for side in (ref,cand):
            observed={(row.get("repetition"),row.get("fold")) for row in side.values()}
            if observed != FOLDS:
                raise IncompleteComparison("Every registered CV fold is required")
        scores = [[],[]]
        for repetition,fold in sorted(FOLDS):
            selected=np.asarray([i for i,key in enumerate(ids) if
                (ref[key]["repetition"],ref[key]["fold"])==(repetition,fold)],int)
            if not len(selected):
                raise IncompleteComparison("Native missingness emptied a registered common CV fold")
            for method in range(2):
                denominator=float(np.abs(y[selected]-means[method,selected]).sum())
                if denominator <= 0:
                    raise IncompleteComparison("A registered CV fold has zero TRAIN-reference error")
                scores[method].append(float(np.abs(y[selected]-p[method,selected]).sum()/denominator))
        test=tukey_hsd(*scores)
        difference=float(test.statistic[0,1]);pvalue=float(test.pvalue[0,1])
        answer.update(significance_method="TUKEY_HSD_25_ORIGINAL_SCAFFOLD_FOLDS",
                      reference_mean25_RAE=float(np.mean(scores[0])),candidate_mean25_RAE=float(np.mean(scores[1])),
                      Tukey_mean_RAE_improvement=difference,Tukey_pvalue=pvalue,
                      significant_improvement=bool(math.isfinite(pvalue) and pvalue<.05 and difference>0))
    return answer

def needs_second_seed(*, learner, final_role, significant_improvement,
                      current_seed_count=1, rollback_lost_samples=False):
    """Traditional ML stays at one seed; neural configurations never exceed two."""
    if type(current_seed_count) is not int or current_seed_count not in (1,2):
        raise ValueError("One or two actual completed seeds must be declared")
    if current_seed_count==2 or learner not in ("TabPFN","Chemprop-v2"):
        return False
    if rollback_lost_samples:
        return True
    return final_role in ("RETAIN","APPENDIX") and significant_improvement is True

def baseline_confirmation_plan(screen, predictions):
    """Confirm a final Chemprop winner against its strongest traditional control."""
    from .selection import BASELINES
    from .reporting import CV_DATASETS, primary_rows
    plan, comparisons = [], []
    for record in screen:
        if (record.get("status") != "SCREENED" or
                record.get("decision") not in ("RETAIN","APPENDIX") or
                record.get("best_baseline") != "Chemprop-v2"):
            continue
        key=record["endpoint_key"];dataset=record["dataset"]
        controls=[name for name in BASELINES if name!="Chemprop-v2"]
        reference=min(controls,key=lambda name:record[name+"_RAE"])
        result=paired_improvement(primary_rows(dataset,predictions[key][reference]),
                                  primary_rows(dataset,predictions[key]["Chemprop-v2"]),
                                  scaffold_cv=dataset in CV_DATASETS)
        comparisons.append(dict(endpoint_key=key,dataset=dataset,target=record["target"],
                                reference_model=reference,candidate_model="Chemprop-v2",**result))
        if needs_second_seed(learner="Chemprop-v2",final_role=record["decision"],
                             significant_improvement=result["significant_improvement"]):
            plan.append(dict(endpoint_key=key,dataset=dataset,target=record["target"],
                             model="Chemprop-v2",primary_seed=SEED,confirmation_seed=SEED+1,
                             frozen_B1_decision=record["decision"],reason="FINAL_SIGNIFICANT_IMPROVEMENT",
                             reference_model=reference,significance_method=result["significance_method"],
                             task_roster_reselection=False,original_folds_or_split_unchanged=True))
    return plan,comparisons
