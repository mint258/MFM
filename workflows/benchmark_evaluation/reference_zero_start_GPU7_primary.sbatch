#!/bin/bash
#SBATCH --job-name=C1-reference-zero-start-GPU7-primary
#SBATCH --partition=gpu
#SBATCH --nodelist=compute-0-7
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_zero_start_GPU7_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd "$repo"
/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python -B - <<'PY'
import ast,json,os,sys,types
from pathlib import Path
b1=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119")
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"]);plan_path=Path(os.environ["BENCHMARK_ZERO_START_GPU_PLAN"])
for path in (cache,plan_path):
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:raise ValueError("Owned immutable zero-start GPU source authorization required")
sources=json.loads(cache.read_text());plan=json.loads(plan_path.read_text())
old=int(os.environ["BENCHMARK_ZERO_START_CPU_JOB"])
matches=[r for r in plan["models"] if int(r["source_CPU_job"])==old]
if len(matches)!=1 or str(matches[0]["replacement_GPU_job"])!=os.environ["SLURM_JOB_ID"]:raise ValueError("Actual replacement GPU job identity differs")
row=matches[0]
if row["source_CPU_native_state"]!="PENDING_ZERO_RUNTIME_HELD" or row["source_CPU_model_fits_started"]!=0 or plan["maximum_concurrent_GPU7_models"]!=1 or plan["benchmark_NFS_pool_bytes"]!=40*1024**3:
    raise ValueError("No running or previously fitted model may be replayed")
helper={};exec(compile(sources["workflows/benchmark_evaluation/reference_cpu_primary.py"],"reference_cpu_primary","exec"),helper)
for name in ("captured_registered_program","prepared_CPU_program"):
    path=Path(row[name])
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:raise ValueError("Original source ownership differs")
program=Path(row["captured_registered_program"]).read_text()
expected_cpu=helper["prepare_reference_cpu_source"](program,row["dataset"],row["feature_group"])
if ast.dump(ast.parse(expected_cpu),include_attributes=False)!=ast.dump(ast.parse(Path(row["prepared_CPU_program"]).read_text()),include_attributes=False):
    raise ValueError("Only the exact original model with execution-device change may run")
allowed={"BENCHMARK_MODEL","BENCHMARK_TASK_INDEX","REFERENCE_BINDING_JOB","TABPFN_ALLOW_CPU_LARGE_DATASET","LOKY_MAX_CPU_COUNT"}
if set(row["model_environment"])-allowed:raise ValueError("Unregistered original model selector")
for key,value in row["model_environment"].items():os.environ[key]=str(value)
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
module=types.ModuleType(package.__name__+".gpu_runtime");module.__package__=package.__name__;sys.modules[module.__name__]=module
exec(compile(sources["workflows/benchmark_evaluation/gpu_runtime.py"],module.__name__,"exec"),module.__dict__)
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119")
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
runtime=module.GpuRuntime(root,quota,gpu_uuid="GPU-9db54192-dd3f-3177-e56f-dcd161ff932c",expected_node="compute-0-7",learner="TabPFN")
torch_module=None
try:
    import torch
    torch_module=torch
    if not torch.cuda.is_available():raise RuntimeError("Actual GPU7 CUDA unavailable before model execution")
    torch.set_float32_matmul_precision("highest");torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    namespace={"__name__":"__main__","_gpu_runtime":runtime}
    exec(compile(program,str(row["captured_registered_program"]),"exec"),namespace)
    report=namespace["report"];model_output=namespace["out"]
    report.update(primary_execution_backend="GPU",zero_start_CPU_primary_reassignment_of_job=old,actual_GPU_node="compute-0-7",
        model_AST_identical_to_original_registered_GPU_program=True,CPU_and_GPU_model_source_equal_except_device=True)
    runtime.protect(root,16*1024**2,quota,own_concurrent_bytes=40*1024**3)
    (model_output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
except BaseException as error:
    try:runtime.finish("FAILED_WITH_NATIVE_ERROR",repr(error),torch_module)
    except Exception as closing:print("GPU_NATIVE_ERROR_RECORD_CAPACITY_PROTECTED",repr(closing),flush=True)
    raise
else:runtime.finish("MODEL_BODY_CLOSED_STATISTICS_DEFERRED_TO_CPU",torch_module=torch_module)
PY
