#!/bin/bash
#SBATCH --job-name=benchmark-reference-idle-GPU7-handover
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-10
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_reference_idle_GPU7_handover_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=''
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import fcntl,json,os,socket,time
from pathlib import Path
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.storage_reservations import current_concurrent
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119")
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():
    forecast=0
    for folder in (root/"labels/Pprime/shared_v1",root/"directive19/uniform_Sprime/labels/Pprime/shared_v1"):
        access=json.loads((folder/"access.json").read_text())
        if not (access.get("immutable") and access.get("cross_node_read_allowed")):
            forecast+=max(0,80000000000-sum(p.stat().st_size for p in folder.glob("*.sqlite")))
    protect(root,64*1024**2+forecast,quota,own_concurrent_bytes=40*1024**3)
    return forecast



import ast,copy,re,subprocess,sys,types
b1=root.parent/"benchmark_B1_20261119";cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"])
if not cache.resolve().is_relative_to(b1.resolve()) or cache.stat().st_uid!=1278:raise ValueError("Owned validated source capsule required")
sources=json.loads(cache.read_text())
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
helpers={}
for name in ("infrastructure_handover","reference_cpu_primary","reference_gpu_handover"):
    module=types.ModuleType(package.__name__+"."+name);module.__package__=package.__name__;sys.modules[module.__name__]=module
    exec(compile(sources["workflows/benchmark_evaluation/"+name+".py"],module.__name__,"exec"),module.__dict__);helpers[name]=module.__dict__
h=helpers["infrastructure_handover"];move=helpers["reference_gpu_handover"]
old_plan=json.loads((b1/"reference_CPU_native_chain/job_4537810/reference_tabpfn_CPU_plan.json").read_text())
safe();out=b1/"reference_idle_GPU7_handover"/("job_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
ledger=dict(status="INSPECTING_ACTUAL_GPU_TAIL_AND_PENDING_CPU_SOURCES",job=os.environ["SLURM_JOB_ID"],original_GPU_tail=4537316,new_jobs=[],mapping={},held=[],cancelled=[],released=[],skipped=[],source_groups=104,scientific_cells=561,benchmark_NFS_pool_bytes=40*1024**3,NFS_joint_pool_bytes=200546101981,maximum_concurrent_GPU7_models=1,maximum_concurrent_CPU_models=8,conservative_model_peak_bytes=36*1024**3,TDC_capped_nine_preserved=True,third_TDC_repair_submitted=False,existing_running_CPU_sources_untouched=True)
def save():
    safe();(out/"manifest.json").write_text(json.dumps(ledger,indent=2)+"\n")
def run(*args):return subprocess.run(args,text=True,capture_output=True,check=True,timeout=40).stdout.strip()
def write(name,value):
    safe();p=out/name;p.write_text(value,encoding="utf-8");return p
def observe(job):
    result=subprocess.run(["scontrol","show","job",str(job),"-o"],text=True,capture_output=True,timeout=20)
    write("job_"+str(job)+".observed.txt",result.stdout+result.stderr)
    if result.returncode:return None
    return result.stdout
def detail(job):
    raw=observe(job)
    if raw is None:raise ValueError("Native pending handle missing; never replay on missing observation")
    f=h["require_owned_pending"](raw)
    if f.get("Restarts")!="0":raise ValueError("Only never-restarted pending sources may be changed")
    return f
def submit(raw,name,dependency="",old_CPU=None):
    subprocess.run(["bash","-n"],input=raw,text=True,capture_output=True,check=True)
    ast.parse(raw.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0]);path=write(name,raw)
    export="ALL,BENCHMARK_SOURCE_CACHE="+str(out/"proposed_sources.json")
    if old_CPU is not None:export+=",BENCHMARK_ZERO_START_GPU_PLAN="+str(out/"reference_GPU7_zero_start_CPU_plan.json")+",BENCHMARK_ZERO_START_CPU_JOB="+str(old_CPU)
    args=["sbatch","--parsable","--hold","--export="+export]
    if old_CPU is None:args+=["--exclude=compute-0-[0-7,14,18,20-22]"]
    if dependency:args+=["--dependency="+dependency]
    value=run(*(args+[str(path)]))
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",value):raise ValueError("An exact held native replacement identity is required")
    job=int(value.split(";")[0]);ledger["new_jobs"].append(dict(job=job,script=str(path),dependency=dependency,source_CPU_job=old_CPU));save();return job
save()
tail=observe(4537316)
if tail is not None:
    fields=h["native_fields"](tail)
    if fields.get("JobId")!="4537316" or fields.get("UserId")!="zixiao(1278)" or fields.get("JobState") not in move["TERMINAL"]:
        raise ValueError("The original actual GPU7 tail must be terminal; never reroute on observer timeout")
    ledger["original_GPU_tail_native_record"]=tail
else:
    accounting=run("ssh","-n","-oBatchMode=yes","-oConnectTimeout=10","sonmi","sacct -X -n -P -j 4537316 -o JobID,User,UID,State,ExitCode")
    records=[r.split("|") for r in accounting.splitlines() if r.split("|")[0]=="4537316"]
    if len(records)!=1 or records[0][1:3]!=["zixiao","1278"] or records[0][3] not in move["TERMINAL"]:raise ValueError("Closed original GPU tail ownership and native terminal evidence required")
    ledger["original_GPU_tail_native_record"]=accounting
feature=json.loads((b1/"C1_Pprime_reference_features/job_4537149/manifest.json").read_text())
if feature.get("job")!="4537797" or feature.get("status")!="C1_PPRIME_REFERENCE_OPTICAL_AND_ATOMIC_FEATURES_CLOSED":raise ValueError("Closed actual reference feature source7797 required")
candidates=[int(r["new_native_job"]) for r in old_plan["models"] if r["original_CPU_predecessor"] is not None]
observations={job:observe(job) for job in candidates}
eligible,skipped=move["select_zero_start_cpu_successors"](old_plan,observations)
ledger["skipped"]=skipped;ledger["eligible_CPU_jobs"]=[r["new_native_job"] for r in eligible];save()
if not eligible:
    ledger["status"]="NO_ZERO_START_CPU_SUCCESSORS_NO_JOB_CHANGES";save();print(json.dumps(ledger),flush=True);raise SystemExit(0)
for row in eligible:
    old=int(row["new_native_job"])
    for kind in ("reference_cv_models","reference_CPU_runtime"):
        if (b1/kind/("job_"+str(old))).exists():raise ValueError("Scientific/admission output exists; preserve that original source")
reports=(4537826,4537827,4537828);before={j:detail(j) for j in reports}
claim=root.parent.parent/"control/benchmark_reference_GPU7_after7316_claim.json"
safe()
with claim.open("x") as f:f.write(json.dumps(dict(controller_job=os.environ["SLURM_JOB_ID"],GPU_tail_job=4537316,eligible_CPU_jobs=ledger["eligible_CPU_jobs"],GPU_tail_native=ledger["original_GPU_tail_native_record"],attempt=1),indent=2)+"\n")
ledger["exclusive_transfer_claim"]=str(claim);save()
for old in ledger["eligible_CPU_jobs"]+list(reports):
    detail(old);run("scontrol","hold",str(old));ledger["held"].append(old);save()
# A source that raced into RUNNING after the first observation is never cancelled.
for old in ledger["eligible_CPU_jobs"]:detail(old)
gpu_plan=dict(schema="REFERENCE_ZERO_START_CPU_TO_IDLE_GPU7_PLAN_V1",original_CPU_plan=str(b1/"reference_CPU_native_chain/job_4537810/reference_tabpfn_CPU_plan.json"),maximum_concurrent_GPU7_models=1,maximum_concurrent_CPU_models=8,benchmark_NFS_pool_bytes=40*1024**3,models=[])
mapping={};previous=None
wrapper=sources["workflows/benchmark_evaluation/reference_zero_start_GPU7_primary.sbatch"]
for source in eligible:
    old=int(source["new_native_job"]);row=copy.deepcopy(source)
    new=submit(wrapper,"reference_GPU7_from_CPU_"+str(old)+".sbatch","" if previous is None else "afterany:"+str(previous),old)
    row.update(source_CPU_job=old,replacement_GPU_job=new,source_CPU_native_state="PENDING_ZERO_RUNTIME_HELD",source_CPU_model_fits_started=0)
    gpu_plan["models"].append(row);mapping[old]=new;ledger["mapping"][str(old)]=new;previous=new;save()
specs=json.loads(sources["workflows/benchmark_evaluation/c1_producer_bindings.json"])
updated=move["remap_zero_start_cpu_to_gpu_specs"](specs,mapping)
if len(updated)!=104:raise ValueError("The original104 source groups must remain")
sources["workflows/benchmark_evaluation/c1_producer_bindings.json"]=json.dumps(updated,indent=2)+"\n"
base_chain=b1/"reference_CPU_native_chain/job_4537810"
primary=h["replace_primary_specs"]((base_chain/"c1_primary_comparisons.sbatch").read_text(),updated)
dependency=h["remap_dependency"](before[4537826].get("Dependency"),mapping)
primary_job=submit(primary,"c1_primary_comparisons.sbatch",dependency or "")
prep=(base_chain/"c1_conditional_sources_prepare.sbatch").read_text()
prep=re.sub(r"(?m)^export BENCHMARK_SOURCE_CACHE=.*$","export BENCHMARK_SOURCE_CACHE="+str(out/"proposed_sources.json"),prep)
prep_job=submit(prep,"c1_conditional_sources_prepare.sbatch","afterok:"+str(primary_job))
controller=(base_chain/"c1_conditional_chain_dispatch.sbatch").read_text()
token="conditional_preparation/C1/job_4537827/manifest.json"
if controller.count(token)!=1:raise ValueError("Exactly one original conditional preparation path required")
controller=controller.replace(token,"conditional_preparation/C1/job_"+str(prep_job)+"/manifest.json")
controller_job=submit(controller,"c1_conditional_chain_dispatch.sbatch","afterok:"+str(prep_job))
sources["workflows/benchmark_evaluation/c1_primary_comparisons.sbatch"]="sbatch --parsable --dependency="+(dependency or "")+" <<'C1PRIMARYREPORT'\n"+primary+"\nC1PRIMARYREPORT\n"
sources["workflows/benchmark_evaluation/c1_conditional_sources_prepare.sbatch"]="sbatch --parsable --dependency=afterok:"+str(primary_job)+" <<'COND_C1_PREP'\n"+prep+"\nCOND_C1_PREP\n"
sources["workflows/benchmark_evaluation/c1_conditional_chain_dispatch.sbatch"]=controller
gpu_plan["status"]="ACTUAL_GPU_REPLACEMENTS_RECORDED_BEFORE_RELEASE";gpu_plan["controller_job"]=int(os.environ["SLURM_JOB_ID"])
write("reference_GPU7_zero_start_CPU_plan.json",json.dumps(gpu_plan,indent=2)+"\n")
sources["workflows/benchmark_evaluation/reference_GPU7_zero_start_CPU_plan.json"]=json.dumps(gpu_plan,indent=2)+"\n"
ledger.update(status="ACTUAL_GPU7_AND_REPORT_IDENTITIES_RECORDED",primary_job=primary_job,conditional_preparation_job=prep_job,controller_job=controller_job,source_cache=str(out/"proposed_sources.json"),GPU_plan=str(out/"reference_GPU7_zero_start_CPU_plan.json"))
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]);changed=[]
for model in index["GPU_downstream_neural"]["models"]:
    old=int(model["job"])
    if old in mapping:
        original_source=model["source_file"];row=next(r for r in gpu_plan["models"] if r["source_CPU_job"]==old)
        model.update(job=mapping[old],primary_execution_backend="GPU",superseded_zero_start_CPU_primary=old,
          node="compute-0-7",target_node="compute-0-7",uuid="GPU-9db54192-dd3f-3177-e56f-dcd161ff932c",
          python=str(b1/"environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python"),
          program=row["captured_registered_program"],original_GPU_template_source_file=original_source,
          source_file="workflows/benchmark_evaluation/reference_zero_start_GPU7_primary.sbatch",actual_primary_script=str(out/("reference_GPU7_from_CPU_"+str(old)+".sbatch")),future_confirmation_GPU_template_preserved=True)
        changed.append(old)
if set(changed)!=set(mapping):raise ValueError("All actual primary sources and their future templates must remain")
index["C1_reference_idle_GPU7_handover_20261121"]=dict(ledger,model_source_identical_to_original_registered_GPU=True,no_checkpoint_seed_population_budget_change=True)
for key,job in (("C1_primary_consumer",primary_job),("C1_conditional_automatic_chain",controller_job)):
    index[key]=dict(previous_pending_definition=index.get(key),current_job=job,source_cache=str(out/"proposed_sources.json"))
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
write("proposed_sources.json",json.dumps(sources,ensure_ascii=False,indent=2)+"\n");save()
base=cache.parent/"source_view"
if not base.is_dir():raise ValueError("Validated immutable base source view required")
paths=sorted({str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}|set(sources))
safe();view=out/"source_view";view.mkdir()
for number,name in enumerate(paths):
    if number%128==0:safe()
    target=view/name;target.parent.mkdir(parents=True,exist_ok=True)
    if name in sources:target.write_text(sources[name],encoding="utf-8")
    else:os.link(base/name,target)
check_module=types.ModuleType("source_check");check_module.__file__=str(view/"tools/check_repository.py")
exec(compile(sources["tools/check_repository.py"],check_module.__file__,"exec"),check_module.__dict__)
check=check_module.check(view,paths,verify_export=False);write("source_check.json",json.dumps(check,indent=2)+"\n")
if check["status"]!="PASS":print(json.dumps(check),flush=True);raise ValueError("Recorded idleGPU7 source tree must pass before activation")
ledger["source_check"]=check;save()
for old in ledger["eligible_CPU_jobs"]+list(reports):
    detail(old);run("scancel",str(old));ledger["cancelled"].append(old);save()
for item in ledger["new_jobs"]:
    job=item["job"]
    if detail(job)["Reason"]!="JobHeldUser":raise ValueError("Only fully recorded new held jobs may be released")
    run("scontrol","release",str(job));ledger["released"].append(job);save()
ledger["status"]="IDLE_GPU7_ZERO_START_CPU_SUCCESSORS_REASSIGNED_AND_RELEASED";save()
print(json.dumps({k:ledger[k] for k in ("status","job","mapping","skipped","primary_job","conditional_preparation_job","controller_job","source_cache","cancelled","released","source_check")}),flush=True)

PY
