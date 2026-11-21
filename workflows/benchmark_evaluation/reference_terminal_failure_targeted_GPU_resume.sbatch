#!/bin/bash
#SBATCH --job-name=C1-reference-terminal-failure-targeted-GPU-resume
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_terminal_failure_targeted_GPU_resume_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd "$repo"
benchmark_reference_gpu_python="${BENCHMARK_REFERENCE_GPU_PYTHON:?Select an already validated private GPU environment}"
case "$benchmark_reference_gpu_python" in
  "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python"|"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu128_job_4537025_step_5/tabpfn/bin/python") ;;
  *) echo "Unregistered private CUDA environment" >&2; exit 2 ;;
esac
"$benchmark_reference_gpu_python" -B - <<'PY'
import ast,json,os,socket,subprocess,sys,types
from pathlib import Path
b1=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119")
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"]);plan_path=Path(os.environ["BENCHMARK_REFERENCE_RESUME_PLAN"])
for path in (cache,plan_path):
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:
        raise ValueError("Owned source capsule and actual terminal-failure continuation plan required")
sources=json.loads(cache.read_text());plan=json.loads(plan_path.read_text())
resume=types.ModuleType("reference_closed_fold_resume")
exec(compile(sources["workflows/benchmark_evaluation/reference_closed_fold_resume.py"],resume.__name__,"exec"),resume.__dict__)
old,target=resume.validate_targeted_resume_plan(plan,os.environ["SLURM_JOB_ID"],
    actual_node=socket.gethostname().split(".")[0],registered_python=os.environ["BENCHMARK_REFERENCE_GPU_PYTHON"])
observed=subprocess.run(["scontrol","show","job",str(old),"-o"],text=True,capture_output=True,timeout=20)
if observed.returncode==0:resume.require_terminal_failure(observed.stdout,old)
elif "Invalid job id" not in observed.stderr:raise RuntimeError("Current source native state cannot be established")
queue=subprocess.run(["squeue","-h","-j",str(old),"-o","%i|%T"],text=True,capture_output=True,timeout=20)
if queue.stdout.strip() or (queue.returncode and "Invalid job id" not in queue.stderr):
    raise RuntimeError("An active or unobserved original source cannot be replayed")
registry=json.loads((b1/"reference_CPU_native_chain/job_4537810/reference_tabpfn_CPU_plan.json").read_text())
rows=[row for row in registry["models"] if int(row["new_native_job"])==old]
if len(rows)!=1:raise ValueError("Exactly one original registered CPU source is required")
row=rows[0]
for key in ("dataset","feature_group","model_environment","captured_registered_program","prepared_CPU_program"):
    if plan.get(key)!=row[key]:raise ValueError("The immutable original model selector or source changed")
source=b1/"reference_cv_models"/("job_"+str(old))
stdout=b1.parent.parent/"control"/("C1_reference_TabPFN_CPU_primary_"+str(old)+".log")
native_fields=resume.require_terminal_failure(plan["source_native_record"],old)
if native_fields.get("StdOut")!=str(stdout):raise ValueError("The original actual producer log is required")
if not stdout.is_file() or stdout.stat().st_uid!=1278:raise ValueError("Original native closure log unavailable")
helper={};exec(compile(sources["workflows/benchmark_evaluation/reference_cpu_primary.py"],"reference_cpu_primary","exec"),helper)
for key in ("captured_registered_program","prepared_CPU_program"):
    path=Path(row[key])
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:raise ValueError("Original model source ownership differs")
original=Path(row["captured_registered_program"]).read_text()
expected_cpu=helper["prepare_reference_cpu_source"](original,row["dataset"],row["feature_group"])
if ast.dump(ast.parse(expected_cpu))!=ast.dump(ast.parse(Path(row["prepared_CPU_program"]).read_text())):
    raise ValueError("Original CPU and registered GPU scientific sources must match except execution device")
program=resume.prepare_resume_source(original,row["dataset"],row["feature_group"])
closed=resume.collect_closed_folds(source,plan["source_native_record"],old,stdout.read_text(),
    row["dataset"],"C1-TabPFN-Pprime",plan["frozen_task_names"],uid=1278)
allowed={"BENCHMARK_MODEL","BENCHMARK_TASK_INDEX","REFERENCE_BINDING_JOB","TABPFN_ALLOW_CPU_LARGE_DATASET","LOKY_MAX_CPU_COUNT"}
if set(row["model_environment"])-allowed:raise ValueError("Unregistered original model environment")
for key,value in row["model_environment"].items():os.environ[key]=str(value)
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
module=types.ModuleType(package.__name__+".gpu_runtime");module.__package__=package.__name__;sys.modules[module.__name__]=module
exec(compile(sources["workflows/benchmark_evaluation/gpu_runtime.py"],module.__name__,"exec"),module.__dict__)
root=b1.parent/"benchmark_B0_20261119"
quota=b1.parent.parent/"control/benchmark_B0_quota_20261119.json"
runtime=module.GpuRuntime(root,quota,gpu_uuid=target["gpu_uuid"],expected_node=target["target_node"],learner="TabPFN")
guard=lambda:runtime.protect(root,16*1024**2,quota,own_concurrent_bytes=40*1024**3)
context=resume.ResumeContext(b1,old,int(os.environ["SLURM_JOB_ID"]),closed,guard,uid=1278)
torch_module=None
try:
    import torch
    torch_module=torch
    if not torch.cuda.is_available():raise RuntimeError("Actual selected GPU CUDA unavailable")
    torch.set_float32_matmul_precision("highest");torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    namespace={"__name__":"__main__","_gpu_runtime":runtime,"_reference_resume":context}
    exec(compile(program,"registered_reference_terminal_failure_resume","exec"),namespace)
    report=namespace["report"];model_output=namespace["out"]
    report.update(primary_execution_backend="GPU",actual_GPU_node=target["target_node"],actual_GPU_UUID=target["gpu_uuid"],actual_GPU_python=target["gpu_python"],
        actual_terminal_failed_CPU_source=old,repair_attempt=1,
        original_model_AST_unchanged_except_closed_fold_continuation=True,
        no_closed_fold_model_or_statistic_replayed=True)
    guard();(model_output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
except BaseException as error:
    try:runtime.finish("FAILED_WITH_NATIVE_ERROR",repr(error),torch_module)
    except Exception as closing:print("GPU_NATIVE_ERROR_RECORD_CAPACITY_PROTECTED",repr(closing),flush=True)
    raise
else:runtime.finish("MODEL_BODY_CLOSED_STATISTICS_DEFERRED_TO_CPU",torch_module=torch_module)
PY
