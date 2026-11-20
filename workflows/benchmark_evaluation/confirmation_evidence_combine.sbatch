sbatch <<'CONFIRMREPORT'
#!/bin/bash
#SBATCH --job-name=C1-confirmation-evidence-join
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1-confirmation-evidence-join_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
findmnt -T "$PWD"
df -B1 "$PWD" /tmp
df -Pi "$PWD" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,os,sys,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"]);sources=json.loads(cache.read_text())
root=Path(json.loads(sources["configs/benchmark_data/B0.DELIVERY.json"])["data_root"]);b1=root.parent/"benchmark_B1_20261119"
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():protect(root,16*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
for name in ("selection","reporting","comparisons","c1_reporting","confirmation_combination"):
    module=types.ModuleType(package.__name__+"."+name);module.__package__=package.__name__;sys.modules[module.__name__]=module
    exec(compile(sources["workflows/benchmark_evaluation/"+name+".py"],module.__name__,"exec"),module.__dict__)
from workflows.benchmark_evaluation.confirmation_combination import combine_stage_reports
from workflows.benchmark_evaluation.selection import IncompleteComparison
reports=[];paths={}
for stage in ("B1","C1"):
    path=Path(os.environ["BENCHMARK_"+stage+"_CONFIRMATION_REPORT"]).resolve()
    if not path.is_relative_to(b1.resolve()):raise IncompleteComparison("Stage evidence must stay in the owned shared output")
    report=json.loads(path.read_text())
    if report["stage"]!=stage:raise IncompleteComparison("Actual stage source differs from its declared original role")
    reports.append(report);paths[stage]=str(path)
combined=combine_stage_reports(reports)
out=b1/"conditional_evidence"/"combined"/("job_"+os.environ["SLURM_JOB_ID"])
if list(out.parent.glob("job_*/manifest.json")):raise IncompleteComparison("Combined evidence already closed")
safe();out.mkdir(parents=True)
combined.update(job=os.environ["SLURM_JOB_ID"],stage_reports=paths)
safe();(out/"manifest.json").write_text(json.dumps(combined,indent=2)+"\n")
print("CONDITIONAL_CONFIRMATION_REPORT_CLOSED",out/"manifest.json",flush=True)

PY
CONFIRMREPORT
