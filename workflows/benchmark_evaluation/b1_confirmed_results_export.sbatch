sbatch --parsable --dependency=afterok:4537462 <<'B1CONFIRMEDCSV'
#!/bin/bash
#SBATCH --job-name=B1-confirmed-neural-results-export
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_confirmed_results_export_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,io,json,os,sys,types
from collections import Counter
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():
    future=0
    for folder in (root/"labels/Pprime/shared_v1",root/"directive19/uniform_Sprime/labels/Pprime/shared_v1"):
        access=json.loads((folder/"access.json").read_text())
        if not (access.get("immutable") and access.get("cross_node_read_allowed")):
            future+=max(0,80000000000-sum(p.stat().st_size for p in folder.glob("*.sqlite")))
    protect(root,16*1024**2+future+36706053853,quota,own_concurrent_bytes=40*1024**3)
safe()
cache=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/source_check/B0_refresh_a2a7/proposed_sources.json")
sources=json.loads(cache.read_text())
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
for name in ("selection","finalization"):
    module=types.ModuleType(package.__name__+"."+name);module.__package__=package.__name__;sys.modules[module.__name__]=module
    exec(compile(sources["workflows/benchmark_evaluation/"+name+".py"],module.__name__,"exec"),module.__dict__)
from workflows.benchmark_evaluation.selection import IncompleteComparison
from workflows.benchmark_evaluation.finalization import finalize_baseline_confirmations,cell_key
evidence_path=b1/"conditional_evidence/B1/job_4537462/manifest.json"
evidence=json.loads(evidence_path.read_text())
if (evidence.get("status")!="CONDITIONAL_CONFIRMATION_STAGE_REPORT_CLOSED" or evidence.get("stage")!="B1"
    or evidence.get("all_declared_producers_terminal") is not True
    or evidence.get("original_TEST_binding_enforced") is not True
    or evidence.get("original_primary_scores_recomputed") is not False):
    raise IncompleteComparison("Original first-CPU confirmation evidence is not closed")
terminal={"COMPLETED","FAILED","CANCELLED","TIMEOUT","OUT_OF_MEMORY","NODE_FAIL","BOOT_FAIL","PREEMPTED","DEADLINE"}
if not evidence.get("native_accounting") or any(row["state"] not in terminal for row in evidence["native_accounting"].values()):
    raise IncompleteComparison("A declared confirmation source is still active")
screen_path=Path(evidence["frozen_B1_roster"])
if screen_path!=b1/"B1_task_screen/job_4537430/B1_task_screen.csv":
    raise IncompleteComparison("Confirmation evidence changed its frozen primary roster")
def rows(path):
    with path.open(newline="") as stream:return list(csv.DictReader(stream))
screen=rows(screen_path);plans=rows(screen_path.parent/"B1_Chemprop_seed2_plan.csv")
indexed={}
for record in evidence["records"]:
    key=cell_key(record,True)
    if key in indexed:raise IncompleteComparison("Duplicate original confirmation evidence")
    indexed[key]=record["evidence"]
table=finalize_baseline_confirmations(screen,plans,indexed)
out=b1/"B1_confirmation_results"/("job_"+os.environ["SLURM_JOB_ID"])
if list(out.parent.glob("job_*/manifest.json")):
    raise IncompleteComparison("Baseline confirmations already exported; no repeat finalization")
safe();out.mkdir(parents=True)
fields=list(dict.fromkeys(key for row in table for key in row))
stream=io.StringIO(newline="");writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n")
writer.writeheader();writer.writerows(table);payload=stream.getvalue().encode("utf-8")
safe()
with (out/"B1_Chemprop_confirmation_results.csv").open("xb") as target:target.write(payload)
report=dict(status="B1_NEURAL_CONFIRMATION_RESULTS_CLOSED",job=os.environ["SLURM_JOB_ID"],
    evidence_source=str(evidence_path),frozen_B1_roster=str(screen_path),required_configurations=len(plans),
    result_csv=str(out/"B1_Chemprop_confirmation_results.csv"),
    confirmation_states=dict(Counter(row["confirmation_status"] for row in table)),
    original_primary_scores_recomputed=False,new_statistics_computed=False,
    task_roster_reselection=False,original_TEST_binding_enforced=True,new_SHA_produced=False,
    statistics_source="Closed firstCPU7462 evidence; formatting only, no metric or contrast replay")
safe();(out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
print("B1_NEURAL_CONFIRMATIONS_EXPORTED",json.dumps(report),flush=True)

PY
B1CONFIRMEDCSV
