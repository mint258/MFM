#!/bin/bash
#SBATCH --job-name=approved-pKa-atomic-supplement
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,18,20-22]
#SBATCH --cpus-per-task=4
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=06:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/approved_pKa_atomic_supplement_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
export BENCHMARK_SOURCE_CACHE=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/approved_pka_atomic_sources/job_4537641/proposed_sources.json
export BENCHMARK_APPROVED_PKA_PROGRAM=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/approved_pka_atomic_sources/job_4537641/approved_pka_atomic.py
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'ATOMICPY'
import json,os,sys,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"])
sources=json.loads(cache.read_text())
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
for name in ("selection","reporting","comparisons","c1_reporting","pprime_features","approved_pka_atomic"):
    mod=types.ModuleType(package.__name__+"."+name);mod.__package__=package.__name__;sys.modules[mod.__name__]=mod
    source=sources["workflows/benchmark_evaluation/"+name+".py"]
    exec(compile(source,mod.__name__,"exec"),mod.__dict__)
entry=Path("configs/benchmark_data/B0.DELIVERY.json")
root=Path(json.loads(entry.read_text())["data_root"])
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=40*1024**3)
safe()
b1=root.parent/"benchmark_B1_20261119"
out=b1/"approved_pka_atomic_supplement"/("job_"+os.environ["SLURM_JOB_ID"])
sys.modules[package.__name__+".approved_pka_atomic"].run(entry,out,Path(os.environ["BENCHMARK_APPROVED_PKA_PROGRAM"]),safe)
ATOMICPY
