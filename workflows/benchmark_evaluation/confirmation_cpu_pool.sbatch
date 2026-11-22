#!/bin/bash
#SBATCH --job-name=C1-required-confirmation-CPU-pool
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=16
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=2-00:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_confirmation_CPU_pool_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK" MKL_NUM_THREADS="$SLURM_CPUS_PER_TASK" OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd "$repo"
"$BENCHMARK_CONFIRMATION_CPU_PYTHON" -B - <<'PY'
import ast,json,os,socket,sys,tempfile,time,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():protect(root,1024**3,quota,own_concurrent_bytes=40*1024**3)
safe()
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"]);plan_path=Path(os.environ["BENCHMARK_CONFIRMATION_CPU_PLAN"])
for path in (cache,plan_path):
    if not path.resolve().is_relative_to(b1.resolve()) or path.is_symlink() or path.stat().st_uid!=1278:raise ValueError("Owned immutable CPU confirmation authorization required")
sources=json.loads(cache.read_text());plan=json.loads(plan_path.read_text())
if (plan.get("schema")!="C1_REQUIRED_CONFIRMATION_CPU_POOL_V1" or plan.get("maximum_parallel_CPU_models")!=11
    or plan.get("benchmark_NFS_pool_bytes")!=40*1024**3 or not 1<=len(plan.get("models",[]))<=40
    or plan.get("frozen_primary_statistics_job")!=4538208 or plan.get("full_required_configurations")!=175):
    raise ValueError("Exact bounded CPU pool execution authorization required")
rows=[row for row in plan["models"] if str(row["new_native_job"])==os.environ["SLURM_JOB_ID"]]
if len(rows)!=1:raise ValueError("One actual new native CPU identity required")
row=rows[0]
if row.get("original_native_state") not in {"PENDING_ZERO_RUNTIME","FAILED_BEFORE_MODEL_EXECUTION","COMPLETED_WRONG_LEARNER_NO_TABPFN_FITS"} or row.get("original_model_fits_started")!=0:
    raise ValueError("Never restart a model that has started")
helper=types.ModuleType("confirmation_cpu_pool")
exec(compile(sources["workflows/benchmark_evaluation/confirmation_cpu_pool.py"],helper.__name__,"exec"),helper.__dict__)
helper.validate_cpu_runtime(socket.gethostname(),int(os.environ["SLURM_CPUS_PER_TASK"]),row["node"],row["allocated_CPUs"],os.environ["CUDA_VISIBLE_DEVICES"])
if row["python"]!=os.environ["BENCHMARK_CONFIRMATION_CPU_PYTHON"] or str(Path(sys.executable).absolute())!=str(Path(row["python"]).absolute()):
    raise ValueError("Keep the group's original private Python environment")
for key in ("original_program","prepared_CPU_program"):
    path=Path(row[key])
    if not path.resolve().is_relative_to(b1.resolve()) or path.is_symlink() or path.stat().st_uid!=1278:raise ValueError("Exact owned source paths required")
original=Path(row["original_program"]).read_text();program=Path(row["prepared_CPU_program"]).read_text()
expected=helper.prepare_required_cpu_source(original,row["group"],cpus=row["allocated_CPUs"])
if ast.dump(ast.parse(program),include_attributes=False)!=ast.dump(ast.parse(expected),include_attributes=False):
    raise ValueError("Only the admitted device/thread adaptation may execute")
execution_environment=helper.resolve_confirmation_environment(row["group"],original,row["group"]["environment"])
if row.get("execution_environment")!=execution_environment:raise ValueError("Declared original task/actual learner environment differs")
for key in ("C1_MODEL","BENCHMARK_MODEL","BENCHMARK_TASK_INDEX","REFERENCE_BINDING_JOB"):
    os.environ.pop(key,None)
for key,value in execution_environment.items():os.environ[key]=value
safe();runtime=b1/"confirmation_CPU_runtime"/("job_"+os.environ["SLURM_JOB_ID"]);runtime.mkdir(parents=True,exist_ok=False)
safe();temporary=runtime/"tmp";temporary.mkdir()
for key in ("TMPDIR","TMP","TEMP","XDG_CACHE_HOME","MPLCONFIGDIR","CUDA_CACHE_PATH"):
    target=temporary/key.lower();safe();target.mkdir();os.environ[key]=str(target)
tempfile.tempdir=os.environ["TMPDIR"]
admission=dict(status="REQUIRED_CPU_POOL_CONFIRMATION_ADMITTED",job=os.environ["SLURM_JOB_ID"],primary_job=row["group"]["primary_job"],
    original_zero_start_GPU_job=row["original_GPU_job"],replaced_CPU_job=row.get("replaced_CPU_job"),node=socket.gethostname(),allocated_CPUs=row["allocated_CPUs"],
    model_seed=20261026,fold_and_statistics_seed=20261025,required_configurations=len(row["group"]["required_tasks"]),
    maximum_parallel_CPU_models=11,benchmark_NFS_pool_bytes=40*1024**3,full_AST_equal_except_execution_resources=True,
    original_private_environment_and_offline_V2_weights=True,new_geometry_or_features=False,execution_environment=execution_environment)
safe();(runtime/"admission.json").write_text(json.dumps(admission,indent=2)+"\n")
namespace={"__name__":"__main__","_gpu_runtime":types.SimpleNamespace(protect=protect)}
import torch
torch.set_num_threads(row["allocated_CPUs"]);torch.set_float32_matmul_precision("highest")
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
started=time.monotonic()
try:
    exec(compile(program,str(row["prepared_CPU_program"]),"exec"),namespace)
except BaseException as error:
    safe();(runtime/"failure.json").write_text(json.dumps(dict(status="FAILED_WITH_NATIVE_ERROR",job=os.environ["SLURM_JOB_ID"],
        original_zero_start_GPU_job=row["original_GPU_job"],primary_job=row["group"]["primary_job"],error=repr(error)),indent=2)+"\n")
    raise
else:
    safe();(runtime/"finished.json").write_text(json.dumps(dict(status="REQUIRED_MODEL_SOURCE_CLOSED_STATISTICS_DEFERRED",job=os.environ["SLURM_JOB_ID"],
        primary_job=row["group"]["primary_job"],elapsed_seconds=time.monotonic()-started,CUDA_context_initialized=torch.cuda.is_initialized()),indent=2)+"\n")
PY
