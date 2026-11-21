#!/bin/bash
#SBATCH --job-name=C1-conditional-chain-dispatch
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_conditional_chain_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,os,shlex,socket,subprocess,sys,time,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
b1=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119")
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"])
sources=json.loads(cache.read_text())
root=Path(json.loads(sources["configs/benchmark_data/B0.DELIVERY.json"])["data_root"])
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():
    for path in (Path("/"),Path("/tmp")):
        stat=os.statvfs(path);total=stat.f_blocks*stat.f_frsize
        if stat.f_bavail*stat.f_frsize < max(10*1024**3,total//10)+16*1024**2 or stat.f_favail<2000:
            raise RuntimeError("Actual root/tmp system and Slurm reserve is insufficient")
    forecast=0
    for folder in (root/"labels/Pprime/shared_v1",root/"directive19/uniform_Sprime/labels/Pprime/shared_v1"):
        access=json.loads((folder/"access.json").read_text())
        if not (access.get("immutable") and access.get("cross_node_read_allowed")):
            forecast+=max(0,80000000000-sum(p.stat().st_size for p in folder.glob("*.sqlite")))
    protect(root,16*1024**2+forecast,quota,own_concurrent_bytes=40*1024**3)
safe()
module=types.ModuleType("conditional_chain")
exec(compile(sources["workflows/benchmark_evaluation/conditional_chain.py"],"conditional_chain","exec"),module.__dict__)
preparation_path=b1/"conditional_preparation/C1/job_4537716/manifest.json"
preparation=json.loads(preparation_path.read_text())
module.validated_groups(preparation,b1)
out=b1/"conditional_dispatch/C1"/("job_"+os.environ["SLURM_JOB_ID"])
safe();out.mkdir(parents=True,exist_ok=False)
def write(path,value):
    safe()
    payload=value if isinstance(value,str) else json.dumps(value,indent=2)+"\n"
    with path.open("w") as stream:stream.write(payload)
def command(args):
    return subprocess.check_output(["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10","sonmi",shlex.join(args)],
        text=True,timeout=60).strip()
def submit(path,dependency):
    safe()
    args=["sbatch","--parsable","--hold"]
    if dependency:args+=["--dependency="+dependency]
    args.append(str(path))
    response=command(args)
    return response.split(";",1)[0]
def release(job):
    safe()
    command(["scontrol","release",str(job)])
scripts=dict(report=sources["workflows/benchmark_evaluation/c1_confirmation_report.sbatch"],
    combine=sources["workflows/benchmark_evaluation/confirmation_evidence_combine.sbatch"],
    final=sources["workflows/benchmark_evaluation/c1_final_confirmed_results_export.sbatch"])
gate=types.ModuleType("infrastructure_handover")
exec(compile(sources["workflows/benchmark_evaluation/infrastructure_handover.py"],"infrastructure_handover","exec"),gate.__dict__)
atomic_path=b1/"approved_pka_atomic_supplement/job_4537644/manifest.json"
atomic=json.loads(atomic_path.read_text())
native_atomic=command(["sacct","-j","4537644","-X","-n","-P","-o","JobID,State,ExitCode"])
precondition=gate.closed_atomic_prerequisite(atomic,native_atomic)
write(out/"closed_atomic_prerequisite.json",dict(precondition,manifest=str(atomic_path),native_accounting=native_atomic))
result=module.wire(preparation,preparation_path,b1,out,cache,scripts,submit,release,write,final_prerequisite_jobs=[])
print("C1_CONDITIONAL_CHAIN_RELEASED",out/"dispatch_state.json","final_export",result["final_export_job"],flush=True)
PY
