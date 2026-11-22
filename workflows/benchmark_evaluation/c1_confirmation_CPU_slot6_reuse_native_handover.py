"""Reuse the closed CPU slot6 for one verified zero-runtime required queue tail."""
import copy,json,os,re,subprocess,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
if os.getuid()!=1278:raise ValueError("Exact native owner required")
base=b1/"C1_confirmation_CPU_slot6_reuse_preparation/job_4538388"
prepared=json.loads((base/"manifest.json").read_text())
if prepared.get("status")!="CPU_SLOT6_REUSE_PREPARED_NOT_ACTIVATED" or prepared.get("tests")!=312 or prepared.get("source_check",{}).get("status")!="PASS":
    raise ValueError("Closed312-test exact three-tail capacity preparation required")
sources=json.loads((base/"proposed_sources.json").read_text());original=copy.deepcopy(sources)
def module(name,path):
    m=types.ModuleType(name);exec(compile(sources[path],name,"exec"),m.__dict__);return m
h=module("infrastructure","workflows/benchmark_evaluation/infrastructure_handover.py")
helper=module("confirmation_cpu_pool","workflows/benchmark_evaluation/confirmation_cpu_pool.py")
rebinder=module("biogen_confirmation_cpu","workflows/benchmark_evaluation/biogen_confirmation_cpu.py")
chain=module("conditional_chain","workflows/benchmark_evaluation/conditional_chain.py")
transport=module("native_slurm_transport","workflows/benchmark_evaluation/native_slurm_transport.py")
def command(*args):return subprocess.run(args,text=True,capture_output=True,check=True,timeout=60).stdout.strip()
old_base=b1/"C1_confirmation_extra_CPU_capacity_native_chain/job_4538371"
bindings=json.loads((old_base/"dispatch_bindings.json").read_text());rows=json.loads((base/"prepared_CPU_models.json").read_text())
original_slots=json.loads((b1/"C1_required_confirmation_CPU_pool_native_chain/job_4538288/CPU_confirmation_plan.json").read_text())["models"]
if len(bindings["groups"])!=43 or len(rows)!=1 or {r["replaced_CPU_job"] for r in rows}!={4538357}:
    raise ValueError("Full175/43 registered chain and three exact pending tails required")
selected={r["replaced_CPU_job"] for r in rows};reports=[4538375,4538376,4538377]
all_ids=[int(run["job"]) for group in bindings["groups"] for run in group["runs"]]
if len(all_ids)!=43 or len(set(all_ids))!=43:raise ValueError("Exactly43 distinct actual model sources required")
native=transport.native_control(["sacct","-n","-X","-j",",".join(map(str,all_ids+[4538388,4538208,4538209])),
    "--format=JobID,User,State,ExitCode,NodeList","--parsable2"])
actual={int(p[0]):dict(user=p[1],state=p[2],exit_code=p[3],node=p[4]) for line in native.splitlines()
    if len(p:=line.strip().split("|"))>=5 and p[0].isdigit()}
if set(actual)!=set(all_ids+[4538388,4538208,4538209]) or any(v["user"]!="zixiao" for v in actual.values()):raise ValueError("Exact native owned source accounting required")
for job in all_ids:
    if actual[job]["state"] not in {"COMPLETED","RUNNING","PENDING"} or (actual[job]["state"]=="COMPLETED" and actual[job]["exit_code"]!="0:0"):
        raise ValueError("Diagnose a new source failure before changing unrelated capacity")
for job in (4538388,4538208,4538209,4538327):
    if actual[job]["state"]!="COMPLETED" or actual[job]["exit_code"]!="0:0":raise ValueError("Closed successful preparation and primary statistics required")
def pending(job,own_hold=False):
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0":raise ValueError("Exact owned never-started native identity required")
    if not own_hold and fields.get("Reason")=="JobHeldUser":raise ValueError("Preserve pre-existing user holds")
    return raw,fields
resource=h.native_fields(command("scontrol","show","node","compute-0-16","-o"))
if resource.get("NodeName")!="compute-0-16" or int(resource["CPUTot"])-int(resource["CPUAlloc"])<32:raise ValueError("Actual32 allocatable CPUs required on the released slot")
records={}
for row in rows:
    job=row["replaced_CPU_job"];bound=bindings["groups"][row["group_index"]]
    if len(bound["runs"])!=1 or int(bound["runs"][0]["job"])!=job or str(bound["primary_job"])!=str(row["group"]["primary_job"]):
        raise ValueError("Current registered tail source changed")
    same_slot=[r for r in original_slots if r["CPU_slot"]==row["original_CPU_slot"]]
    if same_slot[-1]["group_index"]!=row["group_index"]:raise ValueError("No remaining CPU successor may bypass its active predecessor")
    raw,fields=pending(job);records[str(job)]=raw
    if actual[job]["state"]!="PENDING" or fields.get("Command")!=str(b1/"C1_confirmation_environment_repair_native_chain/job_4538337/confirmation_cpu_pool.sbatch") or fields.get("ReqNodeList")!=helper.CPU_SLOTS[row["original_CPU_slot"]]:
        raise ValueError("Exact original pending queue-tail script and placement required")
for job in reports:
    raw,_=pending(job);records[str(job)]=raw
out=b1/"C1_confirmation_CPU_slot6_reuse_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
def write(name,value):
    safe();path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
write("native_controller.py",__controller_source__);write("zero_start_native_records.json",json.dumps(records,indent=2)+"\n")
ledger=dict(status="PREPARING_ONE_ZERO_START_CPU_TAIL_IN_RELEASED_SLOT6",job=os.environ["SLURM_JOB_ID"],preparation_job=4538388,tests=312,
    full_required_configurations=175,total_native_groups=43,replacement_groups=1,replacement_configurations=1,maximum_parallel_CPU_models=11,
    original_eight_CPU_slots_preserved=True,reused_completed_slot=6,closed_slot_source=4538327,closed_slot_accounting=actual[4538327],CPU_node_resource_fields=resource,no_unselected_CPU_dependencies_changed=True,no_active_model_restarted=True,
    benchmark_NFS_pool_bytes=40*1024**3,temporary_forecast_per_model_bytes=1024**3,maximum_CPU_temporary_forecast_bytes=11*1024**3,
    selected_zero_start_CPU_jobs=sorted(selected),old_reports=reports,source_accounting=native,
    preserved_RUNNING=[j for j in all_ids if actual[j]["state"]=="RUNNING"],held_old=[],new_native_jobs=[],cancelled_zero_start=[],released=[])
def save():write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save()
for job in sorted(selected)+reports:
    pending(job);command("scontrol","hold",str(job));ledger["held_old"].append(job);save()
for job in sorted(selected)+reports:
    _,fields=pending(job,True)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("Only exact newly owned holds may be changed")
cache=out/"proposed_sources.json";plan_path=out/"CPU_confirmation_plan.json"
script=write("confirmation_cpu_pool.sbatch",sources["workflows/benchmark_evaluation/confirmation_cpu_pool.sbatch"])
models=[];replacement={}
for row in rows:
    helper.validate_cpu_runtime(row["node"],row["allocated_CPUs"],row["node"],row["allocated_CPUs"],"")
    raw=Path(row["original_program"]).read_text()
    if (helper.prepare_required_cpu_source(raw,row["group"],row["allocated_CPUs"])!=Path(row["prepared_CPU_program"]).read_text()
        or helper.resolve_confirmation_environment(row["group"],raw,row["group"]["environment"])!=row["execution_environment"]):
        raise ValueError("Exact already-required scientific program and environment must remain")
    response=transport.native_control(["sbatch","--parsable","--hold","--dependency=afterok:"+os.environ["SLURM_JOB_ID"],
        "--nodelist="+row["node"],"--cpus-per-task="+str(row["allocated_CPUs"]),
        "--export=ALL,BENCHMARK_SOURCE_CACHE="+str(cache)+",BENCHMARK_CONFIRMATION_CPU_PLAN="+str(plan_path)+",BENCHMARK_CONFIRMATION_CPU_PYTHON="+row["python"],str(script)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",response):raise ValueError("Actual held native CPU identity required")
    job=int(response.split(";")[0]);replacement[row["replaced_CPU_job"]]=job
    models.append(dict(row,new_native_job=job,original_native_state="PENDING_ZERO_RUNTIME",original_model_fits_started=0))
    ledger["new_native_jobs"].append(dict(job=job,kind="ADDITIONAL_CPU_REQUIRED_CONFIRMATION",node=row["node"],allocated_CPUs=row["allocated_CPUs"],
        replaced_CPU_job=row["replaced_CPU_job"],CPU_slot=row["CPU_slot"]));save()
plan=dict(schema="C1_REQUIRED_CONFIRMATION_CPU_POOL_V1",job=os.environ["SLURM_JOB_ID"],models=models,maximum_parallel_CPU_models=11,
    benchmark_NFS_pool_bytes=40*1024**3,frozen_primary_statistics_job=4538208,full_required_configurations=175,
    original_eight_slots_and_all_unselected_sources_unchanged=True,CPU_preprocessing_jobs=2)
write("CPU_confirmation_plan.json",json.dumps(plan,indent=2)+"\n")
new_bindings=rebinder.rebind_confirmation_runs(bindings,replacement)
for group in new_bindings["groups"]:
    for run in group["runs"]:
        old=next((old for old,new in replacement.items() if int(run["job"])==new),None)
        if old is not None:
            row=next(r for r in rows if r["replaced_CPU_job"]==old)
            run.update(zero_start_GPU_job=row["original_GPU_job"],replaced_zero_start_CPU_job=old,execution_backend="CPU")
if len(new_bindings["groups"])!=43 or [str(g["primary_job"]) for g in new_bindings["groups"]]!=[str(g["primary_job"]) for g in bindings["groups"]]:
    raise ValueError("Keep complete43 original primary source identities")
bindings_path=write("dispatch_bindings.json",json.dumps(new_bindings,indent=2)+"\n")
active=[replacement.get(j,j) for j in all_ids if actual[j]["state"] in {"RUNNING","PENDING"}]
def submit_report(name,raw,dependency,kind):
    subprocess.run(["bash","-n"],input=raw,text=True,capture_output=True,check=True);path=write(name,raw)
    response=transport.native_control(["sbatch","--parsable","--hold","--dependency="+dependency,str(path)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",response):raise ValueError("Actual held new report identity required")
    job=int(response.split(";")[0]);ledger["new_native_jobs"].append(dict(job=job,kind=kind,dependency=dependency));save();return job
report_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/c1_confirmation_report.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_CONFIRMATION_BINDINGS_JSON=str(bindings_path)))
new_report=submit_report("first_C1_confirmation_report.sbatch",report_source,"afterany:"+":".join(map(str,active)),"confirmation_report")
report_manifest=b1/"conditional_evidence/C1"/("job_"+str(new_report))/"manifest.json"
combine_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/confirmation_evidence_combine.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_B1_CONFIRMATION_REPORT=str(b1/"conditional_evidence/B1/job_4537462/manifest.json"),BENCHMARK_C1_CONFIRMATION_REPORT=str(report_manifest)))
new_combine=submit_report("combine_confirmation_evidence.sbatch",combine_source,"afterok:"+str(new_report),"evidence_combine")
evidence=b1/"conditional_evidence/combined"/("job_"+str(new_combine))/"manifest.json"
final_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/c1_final_confirmed_results_export.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_CONFIRMATION_EVIDENCE_JSON=str(evidence)))
new_final=submit_report("final_C1_results.sbatch",final_source,"afterok:"+str(new_combine),"final_export")
ledger.update(replacement={str(k):v for k,v in replacement.items()},active_model_dependencies=active,new_confirmation_report=new_report,
    new_evidence_combination=new_combine,new_final_export=new_final,source_cache=str(cache),bindings_path=str(bindings_path),
    CPU_plan=str(plan_path),all_native_IDs_recorded_before_activation=True);save()
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
if index["C1_conditional_automatic_chain"].get("current_job")!=4538371 or index["C1_primary_consumer"].get("current_job")!=4538208:raise ValueError("Current native chain changed externally")
prior=index["C1_conditional_automatic_chain"]
index["C1_conditional_automatic_chain"]=dict(previous_completed_extra_CPU_dispatcher=prior,current_job=int(os.environ["SLURM_JOB_ID"]),
    preparation_job=4538209,primary_report=4538208,source_cache=str(cache),active_bindings=str(bindings_path),maximum_running_CPU_models=11,
    confirmation_report=new_report,evidence_combination=new_combine,final_export=new_final,final_export_pretraining_overlap_status_explicit=True,
    full_required_configurations=175,original_eight_CPU_slots_preserved=True,actual_environment_source_repair_closed=True)
index["C1_reuse_completed_slot6_for_zero_start_tail_20261122"]=dict(ledger)
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
sources["workflows/benchmark_evaluation/c1_confirmation_CPU_slot6_reuse_native_handover.py"]=__controller_source__
write("proposed_sources.json",json.dumps(sources,ensure_ascii=False,indent=2)+"\n")
view=out/"source_view";safe();view.mkdir();base_view=base/"source_view"
paths=sorted({str(p.relative_to(base_view)) for p in base_view.rglob("*") if p.is_file()}|set(sources))
for number,name in enumerate(paths):
    if number%128==0:safe()
    target=view/name;target.parent.mkdir(parents=True,exist_ok=True)
    if name in sources:target.write_text(sources[name],encoding="utf-8")
    else:os.link(base_view/name,target)
checker=types.ModuleType("source_check");checker.__file__=str(view/"tools/check_repository.py")
exec(compile(sources["tools/check_repository.py"],checker.__file__,"exec"),checker.__dict__)
check=checker.check(view,paths,verify_export=False);write("source_check.json",json.dumps(check,indent=2)+"\n")
if check["status"]!="PASS":raise ValueError("Full extra CPU capacity source tree must pass before cancellation or activation")
ledger["source_check"]=check;save()
for job in sorted(selected)+reports:pending(job,True)
for job in sorted(selected)+reports:
    pending(job,True);command("scancel",str(job));ledger["cancelled_zero_start"].append(job);save()
new_jobs=[int(r["job"]) for r in ledger["new_native_jobs"]]
for job in new_jobs:
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0" or fields.get("Reason")!="JobHeldUser":raise ValueError("Exact owned held new activation identity required")
ledger["status"]="FULL175_WITH_RELEASED_SLOT6_RECORDED_BEFORE_RELEASE";save()
for job in new_jobs:
    transport.native_control(["scontrol","release",str(job)]);ledger["released"].append(job);save()
ledger["status"]="RELEASED_SLOT6_REQUIRED_MODEL_AND_FULL_REPORT_CHAIN_RELEASED";save()
print(json.dumps({k:v for k,v in ledger.items() if k not in {"source_accounting","new_native_jobs"}}),flush=True)
