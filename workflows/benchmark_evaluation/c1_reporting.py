"""C1 final-report binding, native availability, and conditional seed plans.

These consumers produce new report statistics. They never select tasks, impute
missing native features, change frozen folds, or refit a model.
"""
from collections import defaultdict
from pathlib import Path
import json
import math
import numpy as np
from .selection import IncompleteComparison, SEED
from .reporting import resolve_endpoint, CV_DATASETS, BLIND_DATASETS, diagnostic_metrics, fold_rae
from .reporting import bind_native_origin,source_identity
from .comparisons import index_predictions, paired_improvement, needs_second_seed

FEATURE_GROUPS=("D","Pprime","Pprime_plus_D")
LEARNERS=("LightGBM","TabPFN")
TERMINAL=frozenset(("COMPLETED","FAILED","CANCELLED","TIMEOUT","OUT_OF_MEMORY","NODE_FAIL","BOOT_FAIL","PREEMPTED","DEADLINE"))

def expected_cells(catalog):
    cells=[]
    for endpoint in catalog:
        if endpoint["level"]=="molecule":
            cells.extend((endpoint["endpoint_key"],feature,model)
                         for feature in FEATURE_GROUPS for model in LEARNERS)
        elif endpoint["dataset"]=="NMRShiftDB2":
            cells.append((endpoint["endpoint_key"],"Pprime_plus_RDKit_atom","LightGBM"))
        elif endpoint["dataset"]=="pKahub" and endpoint["target"]=="single_site_mechanism":
            cells.append((endpoint["endpoint_key"],"Pprime_plus_RDKit_atom","LightGBM"))
        else:
            raise IncompleteComparison("An unregistered atomic C1 task cannot acquire invented D/TabPFN arms")
    if len(set(cells))!=len(cells):
        raise IncompleteComparison("Duplicate active C1 endpoint/configuration identity")
    return cells

def native_primary_row(raw, catalog, spec):
    dataset=raw.get("dataset",spec.get("dataset"))
    if dataset is None:
        raise IncompleteComparison("C1 producer dataset identity is absent")
    endpoint=resolve_endpoint(catalog,dataset,raw["task"])
    if raw.get("fit_population","retained")!="retained":
        return None
    if dataset not in BLIND_DATASETS and not (raw.get("retained",True) and raw.get("domain_eligible",True)):
        return None
    if dataset in BLIND_DATASETS:
        outside=bool(raw.get("blind_fallback",False)) or not (raw.get("retained",True) and raw.get("domain_eligible",True))
        if outside and raw["prediction"]!=raw["training_mean"]:
            raise IncompleteComparison("A C1 blind outside-domain point lost its actual fit TRAIN-mean fallback")
    row=dict(raw,endpoint_key=endpoint,dataset=dataset,evaluation_id=str(raw["record_id"]),
             learner=spec["learner"],feature_group=spec["feature_group"])
    index_predictions([row],allow_native_missing=True)
    return row

def native_population(original, candidate, scaffold_cv=False):
    """Candidate omission is declared native-feature missingness, never a new TEST."""
    ref=index_predictions(original)
    cand=index_predictions(candidate,allow_native_missing=True)
    if not set(cand).issubset(ref):
        raise IncompleteComparison("C1 native records include IDs outside the frozen primary TEST population")
    for identity,row in cand.items():
        source=ref[identity]
        if row["y_true"]!=source["y_true"] or row["full_inchikey"]!=source["full_inchikey"]:
            raise IncompleteComparison("C1 changed original experimental labels or full molecular identities")
        if scaffold_cv and (row.get("repetition"),row.get("fold"))!=(source.get("repetition"),source.get("fold")):
            raise IncompleteComparison("C1 changed a frozen original scaffold fold")
    available=[row for row in cand.values() if row["prediction"] is not None]
    if not available:
        raise IncompleteComparison("No native-feature predictions are available for this configuration")
    if scaffold_cv:
        fold_rae(available)
    return available,dict(original_primary_TEST_rows=len(ref),native_TEST_rows=len(cand),
        available_TEST_rows=len(available),missing_native_TEST_rows=len(ref)-len(available),
        original_primary_TEST_molecules=len({r["full_inchikey"] for r in ref.values()}),
        available_TEST_molecules=len({r["full_inchikey"] for r in available}),
        original_TEST_preserved_for_other_models=True,missing_native_features_imputed=False,
        evaluation_population="AVAILABLE_NATIVE_FEATURES_WITH_EXPLICIT_ORIGINAL_COVERAGE")

def single_model_statistics(rows, scaffold_cv=False):
    """One new final-report bootstrap; cluster all original atomic/repeat rows by molecule."""
    point=diagnostic_metrics(rows)
    if point["RAE"] is None:
        raise IncompleteComparison("C1 has a zero TRAIN-reference denominator")
    y=np.asarray([r["y_true"] for r in rows],float)
    p=np.asarray([r["prediction"] for r in rows],float)
    means=np.asarray([r["training_mean"] for r in rows],float)
    _,inverse=np.unique(np.asarray([r["full_inchikey"] for r in rows]),return_inverse=True)
    count=int(inverse.max())+1
    error=np.bincount(inverse,weights=np.abs(y-p),minlength=count)
    reference=np.bincount(inverse,weights=np.abs(y-means),minlength=count)
    rng=np.random.default_rng(SEED);draws=np.empty(1000,float)
    for index in range(1000):
        selected=rng.integers(0,count,size=count)
        denominator=float(reference[selected].sum())
        if denominator<=0:
            raise IncompleteComparison("A C1 molecule bootstrap draw has zero TRAIN-reference error")
        draws[index]=float(error[selected].sum()/denominator)
    low,high=map(float,np.quantile(draws,[.025,.975]))
    result=dict(point,RAE_CI95_low=low,RAE_CI95_high=high,bootstrap_draws=1000,
        TRAIN_mean_policy="Each configuration's actual eligible available-feature fit TRAIN arithmetic mean",
        CI_population="Same original complete-molecule groups; atomic observations and repeated folds remain together")
    if scaffold_cv:
        values=fold_rae(rows)
        result.update(original_scaffold_folds=25,mean25_fold_RAE=float(np.mean(list(values.values()))),
                      pooled_RAE=point["RAE"],significance_protocol="TUKEY_HSD_25_ORIGINAL_SCAFFOLD_FOLDS")
    return result

def primary_statistics(rows,records,scaffold_cv=False):
    """Reuse closed CPU producer scores; compute only previously deferred/new summaries."""
    primary=[r for r in records if r.get('fit_population','retained')=='retained'
             and r.get('evaluation_population','retained') not in {'full','excluded'}]
    reusable=[r for r in primary if r.get('MAE') not in (None,'') and r.get('RAE') not in (None,'')
              and str(r.get('bootstrap_draws',''))=='1000']
    if not scaffold_cv and reusable:
        if len(reusable)!=1:raise IncompleteComparison('Ambiguous closed official-split C1 statistics')
        original=reusable[0]
        if int(original['n_test_rows'])!=len(rows):
            raise IncompleteComparison('Closed C1 score metadata is bound to a different TEST population')
        score={key:float(original[key]) if original.get(key) not in (None,'') else None
               for key in ('MAE','RAE','RAE_CI95_low','RAE_CI95_high')}
        if any(score[key] is None or not math.isfinite(score[key]) for key in ('MAE','RAE')):
            raise IncompleteComparison('Closed C1 point metric is not finite')
        return dict(score,n_test_rows=len(rows),n_test_molecules=len({r['full_inchikey'] for r in rows}),
                    bootstrap_draws=1000,statistics_source='REUSED_CLOSED_CPU_PRODUCER_STATISTICS',
                    producer_metric_status=original.get('metric_status'),
                    standalone_existing_scores_recomputed=False)
    result=single_model_statistics(rows,scaffold_cv)
    result.update(statistics_source='NEW_CPU_REPORT_FOR_DEFERRED_GPU_OR_NEW_POOLED_CV_STATISTICS',
                  standalone_existing_scores_recomputed=False)
    return result

def fit_metadata_summary(records,scaffold_cv=False):
    """Report the producer's actual native-feature TRAIN size, never a baseline count."""
    primary=[r for r in records if r.get('fit_population','retained')=='retained'
             and r.get('evaluation_population','retained') not in {'full','excluded'}]
    counts=[int(r['n_train']) for r in primary if r.get('n_train') not in (None,'')]
    if not counts:return dict(actual_TRAIN_size='UNKNOWN_NOT_IN_CLOSED_PRODUCER_METADATA')
    if any(value<1 for value in counts):raise IncompleteComparison('A reported fitted model has no TRAIN rows')
    result=dict(actual_TRAIN_rows_min=min(counts),actual_TRAIN_rows_max=max(counts),
                TRAIN_size_source='Closed native producer fit metadata; available-feature TRAIN only')
    if not scaffold_cv and len(set(counts))!=1:
        raise IncompleteComparison('An official C1 configuration has inconsistent actual TRAIN sizes')
    if not scaffold_cv:result['actual_TRAIN_rows']=counts[0]
    widths=[int(r['feature_count']) for r in primary if r.get('feature_count') not in (None,'')]
    if widths:
        if len(set(widths))!=1:raise IncompleteComparison('A C1 configuration changed its native feature layout')
        result['input_feature_count']=widths[0]
    flags=[str(r.get('subsampling_ensemble','')).lower() for r in primary]
    if any(flag in {'true','false'} for flag in flags):
        result['official_TabPFN_subsampling_ensemble']=any(flag=='true' for flag in flags)
    return result

class C1ClosedConsumer:
    def __init__(self,catalog):
        self.catalog=catalog
        self.predictions=defaultdict(list)
        self.sources=[]
        self.seen=set()
        self.closed_cells=set()
        self.failures=[]
        self.unresolved_cells={}
        self.fit_metadata=defaultdict(list)

    def add_run(self,folder,native_state,spec):
        import pyarrow.parquet as pq
        if native_state not in TERMINAL:
            raise IncompleteComparison("C1 final reporting cannot read an active/pending producer")
        folder=Path(folder)
        path=folder/"manifest.json"
        if not path.is_file():
            raise IncompleteComparison("C1 producer has no closed manifest; repair its actual producer first")
        manifest=json.loads(path.read_text())
        if str(manifest.get("job"))!=str(spec["job"]):
            raise IncompleteComparison("C1 source manifest differs from its declared native job")
        self.sources.append(dict(spec,folder=str(folder),native_state=native_state,producer_status=manifest.get("status"),native_coverage=manifest.get("coverage")))
        import csv
        for path in sorted(folder.glob("*partial_results.csv")):
            with path.open(newline="") as stream:
                for record in csv.DictReader(stream):
                    if not record.get("task"):continue
                    dataset=record.get("dataset") or spec.get("dataset")
                    endpoint=resolve_endpoint(self.catalog,dataset,record["task"])
                    self.fit_metadata[(endpoint,spec["feature_group"],spec["learner"])].append(record)
        failures=list(manifest.get("failures",[]))+list(manifest.get("task_failures",[]))
        self.failures.extend(failures)
        for failure in failures:
            if failure.get("status") not in {
                    "NATIVE_PPRIME_FEATURES_UNAVAILABLE_NO_IMPUTATION",
                    "UNRESOLVED_OFFICIAL_LABEL_OR_FEATURE_BINDING",
                    "UNRESOLVED_AFTER_ALLOWED_REPORT_REPAIR"}:
                continue
            dataset=failure.get("dataset",spec.get("dataset"))
            if not dataset or not failure.get("task"):continue
            endpoint=resolve_endpoint(self.catalog,dataset,failure["task"])
            cell=(endpoint,spec["feature_group"],spec["learner"])
            reason=("PRODUCER_UNRESOLVED_AFTER_ALLOWED_REPORT_REPAIR: " if failure.get("status")=="UNRESOLVED_AFTER_ALLOWED_REPORT_REPAIR" else "NATIVE_FEATURE_POPULATION_UNAVAILABLE: ")
            self.unresolved_cells[cell]=reason+json.dumps(failure,sort_keys=True)
        for path in sorted(folder.rglob("*predictions.parquet")):
            if path in self.seen:
                raise IncompleteComparison("A C1 source file was scheduled twice")
            self.seen.add(path)
            for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
                for raw in batch.to_pylist():
                    row=native_primary_row(raw,self.catalog,spec)
                    if row is not None:row=bind_native_origin(row,spec["job"],folder)
                    if row is None:continue
                    cell=(row["endpoint_key"],spec["feature_group"],spec["learner"])
                    self.predictions[cell].append(row)
                    self.closed_cells.add(cell)

def make_primary_report(catalog,screen,baselines,c1_predictions,unresolved=None,fit_metadata=None):
    """Return provisional seed1 rows, registered contrasts, and only required seed2 cells."""
    unresolved={} if unresolved is None else dict(unresolved)
    roles={r["endpoint_key"]:r for r in screen}
    if set(roles)!={r["endpoint_key"] for r in catalog}:
        raise IncompleteComparison("C1 requires the one complete frozen B1 roster")
    endpoints={r["endpoint_key"]:r for r in catalog}
    table=[];contrasts=[];plan=[];seen_plan=set()
    for cell in expected_cells(catalog):
        key,feature,learner=cell
        endpoint=endpoints[key];role=roles[key]
        row=dict(endpoint_key=key,dataset=endpoint["dataset"],target=endpoint["target"],level=endpoint["level"],
                 feature_group=feature,learner=learner,model_seed=SEED,completed_seeds=1,
                 frozen_B1_role=role["decision"],task_roster_reselection=False,geometry="Shared Sprime UFF",
                 report_stage="PRIMARY_SEED_PENDING_CONDITIONAL_CONFIRMATION")
        if endpoint["dataset"]=="pKahub" and endpoint["target"]=="single_site_mechanism":
            table.append(dict(row,**{"status":"UNRESOLVED","reason":"ORIGINAL_EXPERIMENTAL_SINGLE_SITE_ATOM_ANNOTATIONS_ABSENT","completed_seeds":0}))
            continue
        if cell not in c1_predictions:
            if cell not in unresolved:
                raise IncompleteComparison("An expected C1 configuration has no closed predictions: "+repr(cell))
            table.append(dict(row,**{"status":"UNRESOLVED","reason":unresolved[cell],"completed_seeds":0}))
            continue
        source=baselines[key]["LightGBM-RDKit2D"]
        available,coverage=native_population(source,c1_predictions[cell],endpoint["dataset"] in CV_DATASETS)
        scores=primary_statistics(available,(fit_metadata or {}).get(cell,[]),endpoint["dataset"] in CV_DATASETS)
        fit=fit_metadata_summary((fit_metadata or {}).get(cell,[]),endpoint["dataset"] in CV_DATASETS)
        table.append(dict(row,**coverage,**fit,**{k:v for k,v in scores.items() if k!="status"},status="PRIMARY_REPORTED"))
        references=[("B1_LightGBM_RDKit2D",source)]
        if learner=="TabPFN":
            counterpart=(key,feature,"LightGBM")
            if counterpart in c1_predictions:
                references.append(("SAME_NATIVE_FEATURES_LIGHTGBM",c1_predictions[counterpart]))
        if feature in ("Pprime","Pprime_plus_D"):
            counterpart=(key,"D",learner)
            if counterpart in c1_predictions:
                references.append(("D_SAME_LEARNER",c1_predictions[counterpart]))
        for comparison_name,reference in references:
            comparison=paired_improvement(reference,c1_predictions[cell],allow_native_missing=True,
                                          scaffold_cv=endpoint["dataset"] in CV_DATASETS)
            contrasts.append(dict(endpoint_key=key,feature_group=feature,learner=learner,
                                  comparison=comparison_name,frozen_B1_role=role["decision"],**comparison))
            if cell not in seen_plan and needs_second_seed(learner=learner,final_role=role["decision"],
                                    significant_improvement=comparison["significant_improvement"]):
                plan.append(dict(endpoint_key=key,dataset=endpoint["dataset"],target=endpoint["target"],
                                 feature_group=feature,learner=learner,producer_task=c1_predictions[cell][0]["task"],primary_seed=SEED,confirmation_seed=SEED+1,
                                 frozen_B1_role=role["decision"],reason="FINAL_SIGNIFICANT_IMPROVEMENT",
                                 triggering_comparison=comparison_name,task_roster_reselection=False,
                                 fold_and_statistics_seed=SEED,original_labels_or_masks_changed=False,**source_identity(c1_predictions[cell])))
                seen_plan.add(cell)
    return table,contrasts,plan
