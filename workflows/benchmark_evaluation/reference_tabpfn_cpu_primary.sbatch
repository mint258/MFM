#!/bin/bash
#SBATCH --job-name=C1-reference-TabPFN-CPU-primary
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_TabPFN_CPU_primary_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd "$repo"
/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python -B - <<'PY'
import ast,json,os,socket,time,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
entry=json.loads(Path("configs/benchmark_data/B0.DELIVERY.json").read_text())
root=Path(entry["data_root"]);b1=root.parent/"benchmark_B1_20261119"
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():protect(root,4*1024**3,quota,own_concurrent_bytes=40*1024**3)
safe()
if int(os.environ["SLURM_CPUS_PER_TASK"])!=2 or socket.gethostname() not in {"compute-0-"+str(i) for i in range(8,20)}-{"compute-0-14","compute-0-18"}:
    raise ValueError("Exactly2 allocated CPUs on an eligible development CPU node required")
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"]);plan_path=Path(os.environ["BENCHMARK_REFERENCE_CPU_PLAN"])
for path in (cache,plan_path):
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:raise ValueError("Owned immutable reference primary authorization required")
sources=json.loads(cache.read_text());plan=json.loads(plan_path.read_text())
if plan["maximum_parallel_CPU_models"]!=8 or plan["declared_joint_benchmark_NFS_pool_bytes"]!=40*1024**3:raise ValueError("Existing joint disk peak must cover bounded slots")
original_job=int(os.environ["BENCHMARK_ORIGINAL_GPU_MODEL"])
rows=[row for row in plan["models"] if int(row["original_GPU_job"])==original_job]
if len(rows)!=1 or str(rows[0]["new_native_job"])!=os.environ["SLURM_JOB_ID"]:raise ValueError("Actual new native source identity differs")
row=rows[0]
if row["original_model_fits_started"]!=0 or row["original_native_state"]!="PENDING_ZERO_RUNTIME":raise ValueError("Only zero-start primary resource changes allowed")
helper={};exec(compile(sources["workflows/benchmark_evaluation/reference_cpu_primary.py"],"reference_cpu_primary","exec"),helper)
for name in ("captured_registered_program","prepared_CPU_program"):
    path=Path(row[name])
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:raise ValueError("Registered original program ownership differs")
original=Path(row["captured_registered_program"]).read_text();program=Path(row["prepared_CPU_program"]).read_text()
expected=helper["prepare_reference_cpu_source"](original,row["dataset"],row["feature_group"])
if ast.dump(ast.parse(program),include_attributes=False)!=ast.dump(ast.parse(expected),include_attributes=False):raise ValueError("Only the original model with CPU device may execute")
allowed={"BENCHMARK_MODEL","BENCHMARK_TASK_INDEX","TABPFN_ALLOW_CPU_LARGE_DATASET","LOKY_MAX_CPU_COUNT","REFERENCE_BINDING_JOB"}
if set(row["model_environment"])-allowed:raise ValueError("Unregistered model environment key")
for key,value in row["model_environment"].items():os.environ[key]=str(value)
if os.environ.get("BENCHMARK_MODEL")!="C1-TabPFN-"+row["feature_group"] or os.environ.get("TABPFN_ALLOW_CPU_LARGE_DATASET")!="1":raise ValueError("Original reference model selection and CPU large-data authorization required")
safe();runtime=b1/"reference_CPU_runtime"/("job_"+os.environ["SLURM_JOB_ID"]);runtime.mkdir(parents=True,exist_ok=False)
safe();temporary=runtime/"tmp";temporary.mkdir();os.environ["TMPDIR"]=str(temporary);os.environ["TEMP"]=str(temporary);os.environ["TMP"]=str(temporary)
import tempfile
tempfile.tempdir=str(temporary)
admission=dict(status="REGISTERED_REFERENCE_CPU_PRIMARY_ADMITTED",job=os.environ["SLURM_JOB_ID"],original_GPU_job=original_job,node=socket.gethostname(),allocated_CPUs=2,CUDA_visible_devices=os.environ["CUDA_VISIBLE_DEVICES"],maximum_parallel_CPU_models=8,CPU_slot=row["CPU_slot"],native_predecessor=row["new_CPU_predecessor"],joint_benchmark_NFS_pool_bytes=40*1024**3,full_model_AST_equal_except_device=True,model_seed=20261025,new_environment_or_checkpoint_download=False)
safe();(runtime/"admission.json").write_text(json.dumps(admission,indent=2)+"\n")
namespace={"__name__":"__main__","_gpu_runtime":types.SimpleNamespace(protect=protect)}
import torch
torch.set_num_threads(2);torch.set_float32_matmul_precision("highest")
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
started=time.monotonic()
try:
    exec(compile(program,str(row["prepared_CPU_program"]),"exec"),namespace)
    native_report=namespace["report"];model_output=namespace["out"]
    native_report.update(primary_execution_backend="CPU",zero_start_resource_reassignment_of_job=original_job,actual_native_CPUs=2,full_model_AST_equal_except_execution_device=True)
    safe();(model_output/"manifest.json").write_text(json.dumps(native_report,indent=2)+"\n")
except BaseException as error:
    safe();(runtime/"failure.json").write_text(json.dumps(dict(status="FAILED",job=os.environ["SLURM_JOB_ID"],original_GPU_job=original_job,error=repr(error)),indent=2)+"\n")
    raise
else:
    safe();(runtime/"finished.json").write_text(json.dumps(dict(status="MODEL_SOURCE_CLOSED_NATIVE_PRIMARY",job=os.environ["SLURM_JOB_ID"],original_GPU_job=original_job,elapsed_seconds=time.monotonic()-started,CUDA_context_initialized=torch.cuda.is_initialized()),indent=2)+"\n")
PY
