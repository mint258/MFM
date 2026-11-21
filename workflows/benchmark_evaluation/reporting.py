"""Bind closed B1 producer outputs for the single registered task-screen consumer.

This module reads predictions for reporting and new paired statistics. It does not
refit models, rerun producer scores, change populations, or use C1 for decisions.
"""
from collections import defaultdict
from pathlib import Path
import json
import math
import numpy as np
from workflows.benchmark_data.task_selection import canonical_task_key
from .selection import BASELINES, IncompleteComparison, align_predictions, decide_endpoint, tukey_cv

CV_DATASETS = frozenset(("C7H10O2", "PPE1694", "Joung2020"))
BLIND_DATASETS = frozenset(("ExpansionRx", "ASAP_Polaris2025"))
APPENDIX_DATASETS = frozenset(("Biogen_ADME", "TDC_ADMET"))
FOLDS = frozenset((r, f) for r in range(5) for f in range(5))

def resolve_endpoint(catalog, dataset, task):
    """Resolve original source task names against the frozen active catalog."""
    if dataset in ("MoleculeACE", "PharmaBench", "TDC_ADMET"):
        target = {"MoleculeACE": "y", "PharmaBench": "value", "TDC_ADMET": "Y"}[dataset]
        expected = canonical_task_key(dataset, task) + "::" + target
        matches = [r for r in catalog if r["dataset"] == dataset and r["endpoint_key"] == expected]
    elif dataset == "pKahub":
        target = {"acid": "macro_acid", "base": "macro_base"}.get(task, task)
        matches = [r for r in catalog if r["dataset"] == dataset and r["target"] == target]
    else:
        matches = [r for r in catalog if r["dataset"] == dataset and r["target"] == task]
    if len(matches) != 1:
        raise IncompleteComparison("Producer task does not match exactly one active catalog endpoint: " + repr((dataset, task)))
    return matches[0]["endpoint_key"]


def bind_native_origin(row, job, folder, array_job=None):
    """Attach closed native source identity without changing experimental fields."""
    actual=str(job);source=str(array_job) if array_job is not None else actual
    if not actual.isdigit() or not source.isdigit():
        raise IncompleteComparison("Closed prediction source has no actual native producer identity")
    return dict(row,native_producer_job=actual,primary_source_job=source,native_source_folder=str(folder))

def source_identity(rows):
    """A conditional configuration belongs to one original producer or repetition array."""
    if not rows or any(not r.get("primary_source_job") or not r.get("native_producer_job")
                       or not r.get("native_source_folder") for r in rows):
        raise IncompleteComparison("Conditional plan lacks the original native prediction source binding")
    roots={str(r["primary_source_job"]) for r in rows}
    if len(roots)!=1:
        raise IncompleteComparison("One conditional configuration has conflicting original native producers")
    return dict(primary_source_job=next(iter(roots)),
                primary_native_jobs=sorted({str(r["native_producer_job"]) for r in rows}),
                primary_source_folders=sorted({r["native_source_folder"] for r in rows}))

def normalize_prediction(row, catalog):
    if row["model"] not in BASELINES:
        raise IncompleteComparison("C1 or an unregistered model cannot enter the B1 screen")
    answer = dict(row)
    answer["endpoint_key"] = resolve_endpoint(catalog, row["dataset"], row["task"])
    answer["evaluation_id"] = str(row["record_id"])
    answer["eligible"] = bool(row["retained"] and row["domain_eligible"])
    if row["dataset"] in CV_DATASETS:
        rep, fold = row.get("repetition"), row.get("fold")
        if (rep, fold) not in FOLDS:
            raise IncompleteComparison("CV prediction lacks its original repetition/fold")
        expected_suffix = "::repeat:" + str(rep)
        if not answer["evaluation_id"].endswith(expected_suffix):
            raise IncompleteComparison("Repeated CV prediction lost its original repetition identity")
    return answer

def primary_rows(dataset, rows):
    chosen = [r for r in rows if r["fit_population"] == "retained"]
    if dataset not in BLIND_DATASETS and any(not r["eligible"] for r in chosen):
        raise IncompleteComparison("An ineligible row entered the registered retained fit")
    if dataset in BLIND_DATASETS:
        for row in chosen:
            if not row["eligible"] and row["prediction"] != row["training_mean"]:
                raise IncompleteComparison("A blind outside-domain point lacks the fixed TRAIN-mean fallback")
    return chosen

def fold_presence(rows):
    """Require all 25 original folds; never discard a failed or empty fold."""
    observed = {(r.get("repetition"), r.get("fold")) for r in rows}
    if observed != FOLDS:
        raise IncompleteComparison("The repeated-scaffold comparison does not contain every registered fold")

def diagnostic_metrics(rows):
    """New final report metrics; empty subsets remain explicit."""
    if not rows:
        return {"status": "EMPTY_EVALUATION_POPULATION", "n_test_rows": 0}
    y = np.asarray([r["y_true"] for r in rows], float)
    p = np.asarray([r["prediction"] for r in rows], float)
    reference = np.asarray([r["training_mean"] for r in rows], float)
    if not (np.isfinite(y).all() and np.isfinite(p).all() and np.isfinite(reference).all()):
        raise IncompleteComparison("Nonfinite predictions cannot shrink a reporting population")
    denominator = np.abs(y-reference).sum()
    return {"status": "REPORTED", "n_test_rows": len(rows),
            "n_test_molecules": len({r["full_inchikey"] for r in rows}),
            "MAE": float(np.abs(y-p).mean()),
            "RAE": float(np.abs(y-p).sum()/denominator) if denominator > 0 else None}

def fold_rae(rows):
    by_fold = defaultdict(list)
    fold_presence(rows)
    for row in rows:
        by_fold[(row["repetition"], row["fold"])].append(row)
    result = {}
    for key, values in by_fold.items():
        score = diagnostic_metrics(values)["RAE"]
        if score is None:
            raise IncompleteComparison("A registered scaffold fold has zero TRAIN-reference error")
        result[key] = score
    return result

def filtered_labeled_count(coverage):
    """Use producer counts after original finite labels/atom bindings, not source row totals."""
    if "filtered_total_labeled_points" in coverage:
        value = coverage["filtered_total_labeled_points"]
    elif "filtered_labeled_feature_available_points" in coverage:
        value = coverage["filtered_labeled_feature_available_points"]
    elif "eligible_train" in coverage and "eligible_test" in coverage:
        value = coverage["eligible_train"] + coverage["eligible_test"]
    elif "retained_train_atomic_points" in coverage and "retained_test_atomic_points" in coverage:
        value = coverage["retained_train_atomic_points"] + coverage["retained_test_atomic_points"]
    else:
        raise IncompleteComparison("Producer does not supply a finite-label filtered point count")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IncompleteComparison("Invalid original filtered labeled point count")
    return value

def close_endpoint(candidate, predictions, n_filtered_labeled_points, scope_proof):
    """Produce one decision only after the three full primary populations align."""
    dataset = candidate["dataset"]
    primary = {name: primary_rows(dataset, predictions[name]) for name in BASELINES}
    full = {name: [r for r in predictions[name] if r["fit_population"] == "full"] for name in BASELINES}
    align_predictions(full)
    tukey = []
    if dataset in CV_DATASETS:
        for rows in full.values():
            fold_presence(rows)
        for rows in primary.values():
            fold_presence(rows)
        tukey = tukey_cv({name: fold_rae(rows) for name, rows in primary.items()})
    decision = decide_endpoint(primary, n_filtered_labeled_points=n_filtered_labeled_points,
                               scope_proof=scope_proof)
    decision["registered_rule_decision"] = decision["decision"]
    if dataset in APPENDIX_DATASETS and decision["decision"] == "RETAIN":
        decision["decision"] = "APPENDIX"
        decision["reason"] = "PRE_REGISTERED_APPENDIX_ROLE_PRESERVED"
    diagnostics = []
    for name in BASELINES:
        rows = predictions[name]
        full = [r for r in rows if r["fit_population"] == "full"]
        for fit, population, selected in (
            ("retained", "blind_full" if dataset in BLIND_DATASETS else "retained", primary[name]),
            ("full", "full", full),
            ("full", "retained", [r for r in full if r["eligible"]]),
            ("full", "excluded", [r for r in full if not r["eligible"]]),
        ):
            diagnostics.append(dict(model=name, fit_population=fit, evaluation_population=population,
                                    **diagnostic_metrics(selected)))
    return decision, diagnostics, tukey

class ClosedPredictionConsumer:
    """Read each source file once, after native producer accounting is terminal."""
    def __init__(self, catalog):
        self.catalog = catalog
        self.seen_paths = set()
        self.predictions = defaultdict(lambda: defaultdict(list))
        self.coverage = defaultdict(list)
        self.failures = defaultdict(list)
        self.sources = []

    def add_run(self, folder, native_state, expected_model=None, array_job=None):
        import pyarrow.parquet as pq
        folder = Path(folder)
        if native_state not in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "BOOT_FAIL", "PREEMPTED", "DEADLINE"}:
            raise IncompleteComparison("Final reporting cannot read a live or pending producer")
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            self.sources.append({"folder": str(folder), "native_state": native_state,
                                 "status": "UNRESOLVED_NO_CLOSED_PRODUCER_MANIFEST"})
            return
        manifest = json.loads(manifest_path.read_text())
        if array_job is not None and str(manifest.get("array_job")) != str(array_job):
            raise IncompleteComparison("Array artifact does not name the declared native parent")
        self.sources.append({"folder": str(folder), "native_state": native_state,
                             "producer_job": manifest.get("job"), "status": manifest.get("status"),
                             "array_job": manifest.get("array_job"), "array_index": manifest.get("array_index")})
        for record in manifest.get("coverage", []):
            if "dataset" in record and "task" in record:
                endpoint = resolve_endpoint(self.catalog, record["dataset"], record["task"])
                self.coverage[endpoint].append(record)
        for failure in manifest.get("failures", []):
            if failure.get("dataset") and failure.get("task"):
                endpoint = resolve_endpoint(self.catalog, failure["dataset"], failure["task"])
                self.failures[endpoint].append(failure)
        for path in sorted(folder.rglob("*predictions.parquet")):
            if path in self.seen_paths:
                raise IncompleteComparison("A prediction artifact has been scheduled twice")
            self.seen_paths.add(path)
            for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
                for raw in batch.to_pylist():
                    if expected_model is not None and raw["model"] != expected_model:
                        raise IncompleteComparison("Producer model differs from its native job binding")
                    row = bind_native_origin(normalize_prediction(raw, self.catalog),manifest.get("job"),folder,manifest.get("array_job"))
                    self.predictions[row["endpoint_key"]][row["model"]].append(row)

    def screen_once(self, scope_proof, unresolved=None):
        unresolved = {} if unresolved is None else dict(unresolved)
        screen, diagnostics, tukey = [], [], []
        if len(self.catalog) != 96 or len({r["endpoint_key"] for r in self.catalog}) != 96:
            raise IncompleteComparison("Expected the complete frozen 96-endpoint active catalog")
        for candidate in self.catalog:
            key = candidate["endpoint_key"]
            base = {name: candidate[name] for name in ("endpoint_key", "dataset", "target", "level", "split_policy")}
            if candidate["dataset"] == "pKahub" and candidate["target"] == "single_site_mechanism":
                screen.append(dict(base, status="UNRESOLVED", decision="UNRESOLVED",
                                   reason="ORIGINAL_EXPERIMENTAL_SINGLE_SITE_ATOM_ANNOTATIONS_ABSENT",
                                   single_site_molecule_count="UNKNOWN", multi_site_molecule_count="UNKNOWN"))
                continue
            try:
                predictions = self.predictions[key]
                if set(predictions) != set(BASELINES):
                    raise IncompleteComparison("One or more registered baseline results are unfinished")
                counts = {filtered_labeled_count(row) for row in self.coverage[key]
                          if any(name in row for name in ("filtered_total_labeled_points",
                              "filtered_labeled_feature_available_points", "eligible_train", "retained_train_atomic_points"))}
                if len(counts) != 1:
                    raise IncompleteComparison("Missing or inconsistent finite-label filtered point counts")
                decision, impact, comparisons = close_endpoint(candidate, predictions, counts.pop(), scope_proof)
                record = dict(base, status="SCREENED", **{k:v for k,v in decision.items()
                    if k not in ("RAE", "RAE_CI95_low", "RAE_CI95_high", "baseline_order")})
                for index, name in enumerate(BASELINES):
                    for field in ("RAE", "RAE_CI95_low", "RAE_CI95_high"):
                        record[name+"_"+field] = decision[field][index]
                screen.append(record)
                diagnostics.extend(dict(base, **row) for row in impact)
                tukey.extend(dict(base, **row) for row in comparisons)
            except IncompleteComparison as error:
                if key not in unresolved:
                    raise IncompleteComparison(key + ": " + str(error)) from error
                screen.append(dict(base, status="UNRESOLVED", decision="UNRESOLVED",
                                   reason=unresolved[key], producer_failures=json.dumps(self.failures[key], sort_keys=True)))
        return screen, diagnostics, tukey

def resolve_array_run(manifests, parent_job, array_index):
    """Use actual producer array metadata, independent of sacct RawJobID formatting."""
    matches=[(folder,record) for folder,record in manifests
             if str(record.get("array_job"))==str(parent_job)
             and str(record.get("array_index"))==str(array_index)]
    if len(matches)!=1:
        raise IncompleteComparison("Expected one closed producer manifest for the native array element")
    folder,record=matches[0]
    if Path(folder).name!="job_"+str(record.get("job")):
        raise IncompleteComparison("Array producer folder differs from its actual SLURM_JOB_ID")
    return Path(folder)
