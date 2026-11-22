#!/bin/bash
#SBATCH --job-name=C1-reference-terminal-failure-CPU-resume
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=16
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=2-00:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_terminal_failure_CPU_resume_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK" MKL_NUM_THREADS="$SLURM_CPUS_PER_TASK" OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd "$repo"
/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python -B - <<'PY'
import ast,json,os,socket,subprocess,time,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
b1=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119")
root=b1.parent/"benchmark_B0_20261119";quota=b1.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():protect(root,4*1024**3,quota,own_concurrent_bytes=40*1024**3)
safe()
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"]);plan_path=Path(os.environ["BENCHMARK_REFERENCE_RESUME_PLAN"])
for path in (cache,plan_path):
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:
        raise ValueError("Owned immutable CPU continuation source and actual failed-source plan required")
sources=json.loads(cache.read_text());plan=json.loads(plan_path.read_text())
resume=types.ModuleType("reference_closed_fold_resume")
exec(compile(sources["workflows/benchmark_evaluation/reference_closed_fold_resume.py"],resume.__name__,"exec"),resume.__dict__)
cpus=int(os.environ["SLURM_CPUS_PER_TASK"]);actual_node=socket.gethostname().split(".")[0]
old,target=resume.validate_cpu_resume_plan(plan,os.environ["SLURM_JOB_ID"],actual_node=actual_node,allocated_cpus=cpus)
observed=subprocess.run(["scontrol","show","job",str(old),"-o"],text=True,capture_output=True,timeout=20)
if observed.returncode==0:resume.require_terminal_failure(observed.stdout,old)
elif "Invalid job id" not in observed.stderr:raise RuntimeError("Current original native state cannot be established")
queue=subprocess.run(["squeue","-h","-j",str(old),"-o","%i|%T"],text=True,capture_output=True,timeout=20)
if queue.stdout.strip() or (queue.returncode and "Invalid job id" not in queue.stderr):
    raise RuntimeError("An active or unobserved original source cannot be replayed")
registry=json.loads((b1/"reference_CPU_native_chain/job_4537810/reference_tabpfn_CPU_plan.json").read_text())
rows=[r for r in registry["models"] if int(r["new_native_job"])==old]
if len(rows)!=1:raise ValueError("Exactly one original registered CPU source is required")
row=rows[0]
for key in ("dataset","feature_group","model_environment","captured_registered_program","prepared_CPU_program"):
    if plan.get(key)!=row[key]:raise ValueError("The immutable original source or model selector changed")
stdout=b1.parent.parent/"control"/("C1_reference_TabPFN_CPU_primary_"+str(old)+".log")
native_fields=resume.require_terminal_failure(plan["source_native_record"],old)
if native_fields.get("StdOut")!=str(stdout) or not stdout.is_file() or stdout.stat().st_uid!=1278:
    raise ValueError("Actual owned original producer log is required")
helper={};exec(compile(sources["workflows/benchmark_evaluation/reference_cpu_primary.py"],"reference_cpu_primary","exec"),helper)
for key in ("captured_registered_program","prepared_CPU_program"):
    path=Path(row[key])
    if not path.resolve().is_relative_to(b1.resolve()) or path.stat().st_uid!=1278:raise ValueError("Original model source ownership differs")
original=Path(row["captured_registered_program"]).read_text()
expected_cpu=helper["prepare_reference_cpu_source"](original,row["dataset"],row["feature_group"])
if ast.dump(ast.parse(expected_cpu))!=ast.dump(ast.parse(Path(row["prepared_CPU_program"]).read_text())):
    raise ValueError("Original CPU and CUDA model sources must match except device")
gpu_program=resume.prepare_resume_source(original,row["dataset"],row["feature_group"])
program=helper["prepare_reference_cpu_source"](gpu_program,row["dataset"],row["feature_group"])
closed=resume.collect_closed_folds(b1/"reference_cv_models"/("job_"+str(old)),plan["source_native_record"],old,
    stdout.read_text(),row["dataset"],"C1-TabPFN-Pprime",plan["frozen_task_names"],uid=1278)
allowed={"BENCHMARK_MODEL","BENCHMARK_TASK_INDEX","REFERENCE_BINDING_JOB","TABPFN_ALLOW_CPU_LARGE_DATASET","LOKY_MAX_CPU_COUNT"}
if set(row["model_environment"])-allowed:raise ValueError("Unregistered original model environment")
for key,value in row["model_environment"].items():os.environ[key]=str(value)
if os.environ.get("BENCHMARK_MODEL")!="C1-TabPFN-Pprime" or os.environ.get("TABPFN_ALLOW_CPU_LARGE_DATASET")!="1":
    raise ValueError("Original primary CPU model and large-data permission required")
safe();runtime=b1/"reference_CPU_runtime"/("job_"+os.environ["SLURM_JOB_ID"]);runtime.mkdir(parents=True,exist_ok=False)
safe();temporary=runtime/"tmp";temporary.mkdir()
for key in ("TMPDIR","TEMP","TMP"):os.environ[key]=str(temporary)
import tempfile
tempfile.tempdir=str(temporary)
context=resume.ResumeContext(b1,old,int(os.environ["SLURM_JOB_ID"]),closed,safe,uid=1278)
admission=dict(status="ORIGINAL_TERMINAL_FAILED_CPU_CONTINUATION_ADMITTED",job=os.environ["SLURM_JOB_ID"],
    original_terminal_failed_CPU_source=old,node=actual_node,allocated_CPUs=cpus,maximum_parallel_CPU_models=5,
    closed_original_folds=len(closed),model_seed=20261025,joint_benchmark_NFS_pool_bytes=40*1024**3,
    actual_execution_backend="CPU",GPU_requested=False,CUDA_visible_devices=os.environ["CUDA_VISIBLE_DEVICES"],
    original_scientific_AST_equal_except_resume_control_and_execution_device=True)
safe();(runtime/"admission.json").write_text(json.dumps(admission,indent=2)+"\n")
import torch
torch.set_num_threads(cpus);torch.set_float32_matmul_precision("highest")
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
namespace={"__name__":"__main__","_gpu_runtime":types.SimpleNamespace(protect=protect),"_reference_resume":context}
started=time.monotonic()
try:
    exec(compile(program,"registered_reference_terminal_failure_CPU_resume","exec"),namespace)
    report=namespace["report"];model_output=namespace["out"]
    report.update(primary_execution_backend="CPU",actual_native_CPUs=cpus,actual_CPU_node=actual_node,
        actual_terminal_failed_CPU_source=old,repair_attempt=1,no_closed_fold_model_or_statistic_replayed=True,
        original_model_AST_unchanged_except_closed_fold_control_and_execution_device=True)
    safe();(model_output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
except BaseException as error:
    safe();(runtime/"failure.json").write_text(json.dumps(dict(status="FAILED",job=os.environ["SLURM_JOB_ID"],
        actual_terminal_failed_CPU_source=old,error=repr(error)),indent=2)+"\n")
    raise
else:
    safe();(runtime/"finished.json").write_text(json.dumps(dict(status="MODEL_BODY_CLOSED_STATISTICS_DEFERRED_TO_CPU",
        job=os.environ["SLURM_JOB_ID"],actual_terminal_failed_CPU_source=old,
        elapsed_seconds=time.monotonic()-started,CUDA_context_initialized=torch.cuda.is_initialized()),indent=2)+"\n")
PY
