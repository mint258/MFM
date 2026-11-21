sbatch <<'CONFIRMREPORT'
#!/bin/bash
#SBATCH --job-name=C1-seed2-first-report
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1-seed2-first-report_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
findmnt -T "$PWD"
df -B1 "$PWD" /tmp
df -Pi "$PWD" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,os,re,subprocess
from collections import defaultdict
from pathlib import Path
from workflows.benchmark_data.admission import protect
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"]);sources=json.loads(cache.read_text())
root=Path(json.loads(sources["configs/benchmark_data/B0.DELIVERY.json"])["data_root"])
b1=root.parent/"benchmark_B1_20261119"
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():protect(root,128*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
import sys,types
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
for name in ("selection","reporting","comparisons","c1_reporting","confirmation_consumer","confirmation_io"):
    module=types.ModuleType(package.__name__+"."+name);module.__package__=package.__name__;sys.modules[module.__name__]=module
    exec(compile(sources["workflows/benchmark_evaluation/"+name+".py"],module.__name__,"exec"),module.__dict__)
from workflows.benchmark_evaluation.selection import IncompleteComparison
from workflows.benchmark_evaluation.reporting import resolve_array_run,CV_DATASETS
from workflows.benchmark_evaluation.c1_reporting import TERMINAL,fit_metadata_summary
from workflows.benchmark_evaluation.confirmation_io import selected_predictions,selected_fit_metadata
from workflows.benchmark_evaluation.confirmation_consumer import summarize_confirmation
bindings_path=Path(os.environ["BENCHMARK_CONFIRMATION_BINDINGS_JSON"]).resolve()
if not bindings_path.is_relative_to(b1.resolve()):raise IncompleteComparison("Dispatch bindings must stay under the owned shared benchmark root")
bindings=json.loads(bindings_path.read_text());stage=bindings["stage"]
if stage not in {"B1","C1"}:raise IncompleteComparison("Unregistered confirmation report stage")
preparation_path=Path(bindings["preparation_manifest"]).resolve()
if not preparation_path.is_relative_to(b1.resolve()):raise IncompleteComparison("Source preparation is outside its owned shared root")
preparation=json.loads(preparation_path.read_text())
if preparation["stage"]!=stage or preparation["status"]!="CONDITIONAL_NEURAL_SOURCE_PREPARATION_CLOSED":
    raise IncompleteComparison("Required conditional source preparation is not closed")
screen_path=Path(preparation["frozen_B1_roster"])
def read_csv(path):
    with path.open(newline="") as stream:return list(csv.DictReader(stream))
def truth(value):return value is True or str(value).lower()=="true"
plan_path=screen_path.parent/"B1_Chemprop_seed2_plan.csv" if stage=="B1" else Path(preparation["C1_primary_manifest"]).parent/"C1_TabPFN_seed2_plan.csv"
plan=read_csv(plan_path)
def cell(row):
    return (row["endpoint_key"],row["model"]) if stage=="B1" else (row["endpoint_key"],row["feature_group"],row["learner"])
plans={cell(row):row for row in plan}
if len(plans)!=len(plan):raise IncompleteComparison("Duplicate required confirmation cell")
prepared={str(group["primary_job"]):group for group in preparation["prepared_native_groups"]}
dispatch={str(group["primary_job"]):group for group in bindings["groups"]}
if set(dispatch)!=set(prepared):raise IncompleteComparison("Every prepared group needs its actual native dispatch record")
failures={cell(row):row for row in bindings.get("unresolved_cells",[])}
if not set(failures).issubset(plans):raise IncompleteComparison("A failure record introduces an unplanned task")
for key,failure in failures.items():
    if not failure.get("native_failure_reason") or not failure.get("sources"):
        raise IncompleteComparison("An unresolved confirmation requires actual source failure evidence")
    if (not failure.get("native_feature_population_unavailable")
        and len(set(str(job) for job in failure.get("attempt_jobs",[])))<2
        and float(failure.get("repair_elapsed_seconds",0))<14400):
        raise IncompleteComparison("Do not finalize a still-repairable confirmation failure")
catalog_path=b1/"endpoint_catalog/job_4536889/candidate_endpoints.csv"
catalog=read_csv(catalog_path)
b1_specs=json.loads(sources["workflows/benchmark_evaluation/b1_producer_bindings.json"])
c1_specs=json.loads(sources["workflows/benchmark_evaluation/c1_producer_bindings.json"])
b1_by_job={str(spec["job"]):spec for spec in b1_specs};c1_by_job={str(spec["job"]):spec for spec in c1_specs}
new_specs=[]
for primary_job,group in dispatch.items():
    original=(b1_by_job if stage=="B1" else c1_by_job)[primary_job]
    for run in group["runs"]:
        spec=dict(original,job=int(run["job"]),array=bool(run.get("array",original.get("array",False))))
        if run.get("indices") is not None:spec["indices"]=list(run["indices"])
        if spec.get("array"):spec.pop("folder",None)
        else:spec["folder"]=str(Path(original["folder"]).parent/("job_"+str(spec["job"])))
        spec["primary_job"]=primary_job;new_specs.append(spec)
reused=[]
if stage=="B1":
    for row in preparation["reused_native_confirmations"]:
        reused.append(dict(job=int(row["confirmation_native_job"]),folder="B1_Chemprop_NMR/job_"+str(row["confirmation_native_job"]),model="Chemprop-v2",reuse_cell=cell(row)))
all_specs=b1_specs+(c1_specs if stage=="C1" else [])+new_specs+reused
job_ids=sorted({str(spec["job"]) for spec in all_specs})
raw=subprocess.check_output(["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10","sonmi",
    "sacct","-j",",".join(job_ids),"-X","--noheader","--parsable2","-o","JobID,JobIDRaw,State,ExitCode,NodeList"],text=True,timeout=60)
accounting={}
for line in raw.splitlines():
    fields=line.strip().split("|")
    if len(fields)<5:continue
    name,actual,state,exit_code,node=fields[:5]
    if not re.fullmatch(r"[0-9]+(?:_[0-9]+)?",name):continue
    if name in accounting:raise IncompleteComparison("Duplicate native source accounting identity")
    accounting[name]=dict(actual_job=actual,state=state.split()[0].rstrip("+"),exit_code=exit_code,node=node)
for parent in job_ids:
    records=[record for name,record in accounting.items() if name==parent or name.startswith(parent+"_")]
    if not records or any(record["state"] not in TERMINAL for record in records):
        raise IncompleteComparison("A declared comparison source remains active or has no native accounting: "+parent)
array_manifests=None
def native_runs(spec):
    global array_manifests
    if spec.get("array"):
        if array_manifests is None:
            array_manifests=[(path.parent,json.loads(path.read_text())) for path in (b1/"reference_cv_models").glob("job_*/manifest.json")]
        for index in spec.get("indices",range(5)):
            identity=str(spec["job"])+"_"+str(index)
            if identity not in accounting:raise IncompleteComparison("A native array element lacks its actual accounting")
            native=accounting[identity]
            yield resolve_array_run(array_manifests,spec["job"],index),native,dict(array_parent=spec["job"],array_index=index)
    else:
        identity=str(spec["job"])
        if identity not in accounting:raise IncompleteComparison("A native source lacks actual accounting")
        yield b1/spec["folder"],accounting[identity],{}
successful=[row for row in plan if cell(row) not in failures]
wanted={row["endpoint_key"]:row for row in successful}
original_significant=defaultdict(list)
registered=defaultdict(list)
if stage=="B1":
    for row in read_csv(screen_path.parent/"B1_Chemprop_paired_comparisons.csv"):
        key=(row["endpoint_key"],"Chemprop-v2")
        if key in plans and truth(row["significant_improvement"]):original_significant[key].append(row["reference_model"])
else:
    for row in read_csv(Path(preparation["C1_primary_manifest"]).parent/"C1_registered_paired_comparisons.csv"):
        key=(row["endpoint_key"],row["feature_group"],row["learner"])
        if key not in plans:continue
        registered[key].append(row["comparison"])
        if truth(row["significant_improvement"]):original_significant[key].append(row["comparison"])
def query(row,models=None):
    result=dict(endpoint_key=row["endpoint_key"],dataset=row["dataset"],producer_task=row["producer_task"])
    if models is not None:result["models"]=list(models)
    return result
baseline_queries=[]
for key,row in wanted.items():
    models={"Chemprop-v2"} if stage=="B1" else {"LightGBM-RDKit2D"}
    if stage=="B1" and row.get("reference_model"):models.add(row["reference_model"])
    if stage=="B1":models.update(original_significant[(key,"Chemprop-v2")])
    baseline_queries.append(query(row,sorted(models)))
baseline=defaultdict(list);original_c1=defaultdict(list);candidate=defaultdict(list)
candidate_meta=defaultdict(list);candidate_sources=defaultdict(list);source_log=[]
def append_rows(destination,found):
    for key,values in found.items():destination[key].extend(values)
def load_runs(spec,queries,kind,destination,metadata=False):
    if not queries:return
    for folder,native,array in native_runs(spec):
        safe()
        found,source=selected_predictions(folder,catalog,queries,kind=kind,spec=spec,
            native_state=native["state"],expected_job=native["actual_job"],**array)
        append_rows(destination,found);source_log.append(source)
        for identity in found:candidate_sources[identity].append(source) if metadata else None
        if metadata:
            records=selected_fit_metadata(folder,queries,spec,native_state=native["state"])
            for endpoint,values in records.items():
                identity=(endpoint,"Chemprop-v2") if kind=="B1" else (endpoint,spec["feature_group"],spec["learner"])
                candidate_meta[identity].extend(values)
for spec in b1_specs:
    load_runs(spec,baseline_queries,"B1",baseline)
needed_c1=set()
if stage=="C1":
    for row in successful:
        key=cell(row);needed_c1.add(key)
        for name in registered[key]:
            if name=="SAME_NATIVE_FEATURES_LIGHTGBM":needed_c1.add((key[0],key[1],"LightGBM"))
            elif name=="D_SAME_LEARNER":needed_c1.add((key[0],"D",key[2]))
    for spec in c1_specs:
        available_datasets={"TDC_ADMET","ASAP_Polaris2025"} if spec["dataset"]=="tdc_asap" else {spec["dataset"]}
        queries=[query(wanted[key]) for key,feature,learner in needed_c1
            if feature==spec["feature_group"] and learner==spec["learner"] and wanted[key]["dataset"] in available_datasets]
        load_runs(spec,queries,"C1",original_c1)
for spec in new_specs:
    group=prepared[str(spec["primary_job"])]
    selected=[row for row in group["required_tasks"] if cell(row) not in failures]
    queries=[query(row,["Chemprop-v2"] if stage=="B1" else None) for row in selected]
    load_runs(spec,queries,stage,candidate,metadata=True)
for spec in reused:
    row=plans[tuple(spec["reuse_cell"])]
    if cell(row) not in failures:load_runs(spec,[query(row,["Chemprop-v2"])],"B1",candidate,metadata=True)
records=[]
for key,row in plans.items():
    if key in failures:
        failure=failures[key]
        evidence=dict(status="UNRESOLVED",model_seed=20261026,split_and_statistics_seed=20261025,
            sources=failure["sources"],native_failure_reason=failure["native_failure_reason"])
    else:
        if key not in candidate:raise IncompleteComparison("Required second-seed predictions are absent: "+repr(key))
        references={}
        if stage=="B1":
            primary=baseline[key]
            for name in sorted(set(original_significant[key])|({row["reference_model"]} if row.get("reference_model") else set())):
                references[name]=baseline[(key[0],name)]
        else:
            primary=original_c1[key]
            for name in registered[key]:
                if name=="B1_LightGBM_RDKit2D":references[name]=baseline[(key[0],"LightGBM-RDKit2D")]
                elif name=="SAME_NATIVE_FEATURES_LIGHTGBM":references[name]=original_c1[(key[0],key[1],"LightGBM")]
                elif name=="D_SAME_LEARNER":references[name]=original_c1[(key[0],"D",key[2])]
                else:raise IncompleteComparison("Unregistered original C1 contrast")
        fit=fit_metadata_summary(candidate_meta[key],row["dataset"] in CV_DATASETS)
        evidence=summarize_confirmation(primary,candidate[key],references,sources=candidate_sources[key],
            scaffold_cv=row["dataset"] in CV_DATASETS,fit_metadata=fit)
        evidence["original_significant_comparisons"]=original_significant[key]
        for comparison in evidence["comparisons"]:
            comparison["original_primary_significant"]=comparison["comparison"] in original_significant[key]
    record=dict(endpoint_key=key[0],evidence=evidence)
    if stage=="B1":record["model"]=key[1]
    else:record.update(feature_group=key[1],learner=key[2])
    records.append(record)
out=b1/"conditional_evidence"/stage/("job_"+os.environ["SLURM_JOB_ID"])
if list(out.parent.glob("job_*/manifest.json")):raise IncompleteComparison("This stage already has a closed confirmation report; no score replay")
safe();out.mkdir(parents=True)
report=dict(status="CONDITIONAL_CONFIRMATION_STAGE_REPORT_CLOSED",stage=stage,job=os.environ["SLURM_JOB_ID"],
    frozen_B1_roster=str(screen_path),C1_primary_manifest=preparation["C1_primary_manifest"],
    preparation_manifest=str(preparation_path),dispatch_bindings=str(bindings_path),required_configurations=len(plan),
    records=records,native_accounting=accounting,all_declared_producers_terminal=True,
    original_TEST_binding_enforced=True,original_primary_scores_recomputed=False,
    source_files=source_log,final_C1_table=False,final_SHA_produced=False)
safe();(out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
print("CONDITIONAL_CONFIRMATION_STAGE_REPORT_CLOSED",out/"manifest.json","records",len(records),flush=True)

PY
CONFIRMREPORT
