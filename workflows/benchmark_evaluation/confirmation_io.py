"""Load only registered original task predictions for new second-seed comparisons."""
from collections import defaultdict
from pathlib import Path
import json
from .selection import IncompleteComparison
from .reporting import normalize_prediction,primary_rows,bind_native_origin,resolve_endpoint
from .c1_reporting import native_primary_row,TERMINAL

def closed_manifest(folder,native_state,*,expected_job=None,array_parent=None,array_index=None):
    if native_state not in TERMINAL:
        raise IncompleteComparison("Second-seed comparisons cannot read a live producer")
    folder=Path(folder);path=folder/"manifest.json"
    if not path.is_file():raise IncompleteComparison("A comparison source lacks a closed producer manifest")
    manifest=json.loads(path.read_text())
    if expected_job is not None and str(manifest.get("job"))!=str(expected_job):
        raise IncompleteComparison("Comparison source differs from its actual native job")
    if array_parent is not None and (str(manifest.get("array_job"))!=str(array_parent)
            or str(manifest.get("array_index"))!=str(array_index)):
        raise IncompleteComparison("Comparison source differs from its actual native array element")
    return manifest

def selected_predictions(folder,catalog,queries,*,kind,spec,native_state,expected_job=None,
                         array_parent=None,array_index=None):
    """Arrow filters avoid decoding unrelated original endpoints for score replay."""
    import pyarrow.dataset as ds
    if kind not in {"B1","C1"}:raise ValueError("Original B1 or C1 binding kind is required")
    manifest=closed_manifest(folder,native_state,expected_job=expected_job,
        array_parent=array_parent,array_index=array_index)
    wanted={q["endpoint_key"]:q for q in queries}
    if len(wanted)!=len(queries):
        raise IncompleteComparison("Duplicate endpoint query would reread a comparison population")
    for key,query in wanted.items():
        if resolve_endpoint(catalog,query["dataset"],query["producer_task"])!=key:
            raise IncompleteComparison("Query changed its original task/endpoint binding")
        query_models=list(query.get("models") or ([query["model"]] if query.get("model") else []))
        if kind=="B1" and not query_models:
            raise IncompleteComparison("A baseline comparison must name each task's actual models")
    output=defaultdict(list);read_paths=[]
    for path in sorted(Path(folder).rglob("*predictions.parquet")):
        dataset=ds.dataset(path,format="parquet")
        names=set(dataset.schema.names)
        if not {"task","record_id","full_inchikey","y_true","prediction","training_mean"}.issubset(names):
            raise IncompleteComparison("Original prediction source lacks required experimental binding columns")
        if kind=="B1" and not {"dataset","model","fit_population"}.issubset(names):
            raise IncompleteComparison("Baseline source lacks original model/population identity")
        identity_columns=["task"]+(["dataset"] if "dataset" in names else [])
        identities=dataset.scanner(columns=identity_columns,use_threads=False).to_table()
        native_tasks=identities.group_by(identity_columns,use_threads=False).aggregate([]).to_pylist()
        expression=None
        for native in native_tasks:
            dataset_name=native.get("dataset",spec.get("dataset"))
            key=resolve_endpoint(catalog,dataset_name,native["task"])
            query=wanted.get(key)
            if query is None or dataset_name!=query["dataset"]:continue
            clause=ds.field("task")==native["task"]
            if "dataset" in names:clause=clause&(ds.field("dataset")==dataset_name)
            if kind=="B1":
                models=list(query.get("models") or [query["model"]])
                clause=clause&ds.field("model").isin(models)
            expression=clause if expression is None else expression|clause
        if expression is None:continue
        if "fit_population" in names:expression=expression&(ds.field("fit_population")=="retained")
        seen=False
        for batch in dataset.scanner(filter=expression,batch_size=4096,use_threads=False).to_batches():
            for raw in batch.to_pylist():
                if kind=="B1":
                    row=normalize_prediction(raw,catalog)
                    chosen=primary_rows(row["dataset"],[row])
                    if not chosen:continue
                    identity=(row["endpoint_key"],row["model"])
                else:
                    row=native_primary_row(raw,catalog,spec)
                    if row is None:continue
                    identity=(row["endpoint_key"],spec["feature_group"],spec["learner"])
                original_dataset=row["dataset"]
                if row["endpoint_key"] not in wanted or wanted[row["endpoint_key"]]["dataset"]!=original_dataset:
                    raise IncompleteComparison("A query changed its original source task/endpoint binding")
                row=bind_native_origin(row,manifest["job"],folder,array_parent)
                output[identity].append(row);seen=True
        if seen:read_paths.append(str(path))
    return output,dict(folder=str(folder),producer_job=manifest["job"],native_state=native_state,
        array_parent=array_parent,array_index=array_index,selected_queries=list(queries),
        selected_prediction_files=read_paths,primary_scores_recomputed=False)

def selected_fit_metadata(folder,queries,spec,*,native_state):
    """Copy actual fit sizes/version context; ignore previously produced score values."""
    import csv
    closed_manifest(folder,native_state)
    wanted={(q["dataset"],q["producer_task"]):q["endpoint_key"] for q in queries}
    result=defaultdict(list)
    for path in sorted(Path(folder).glob("*partial_results.csv")):
        with path.open(newline="") as stream:
            for record in csv.DictReader(stream):
                dataset=record.get("dataset") or spec.get("dataset")
                key=wanted.get((dataset,record.get("task")))
                if key is None:continue
                if record.get("fit_population","retained")!="retained":continue
                if record.get("evaluation_population","retained") in {"full","excluded"}:continue
                result[key].append({name:record[name] for name in (
                    "n_train","feature_count","subsampling_ensemble","context_cap","task_type",
                    "repetition","fold","fit_population","evaluation_population") if name in record})
    return result
