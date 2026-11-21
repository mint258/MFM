"""Activate only the40 actual zero-start required confirmation groups in eight CPU slots."""
import copy,json,os,re,subprocess,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
if os.getuid()!=1278:raise ValueError("Exact native owner required")
base=b1/"C1_required_confirmation_CPU_pool_preparation/job_4538284"
prepared=json.loads((base/"manifest.json").read_text())
if prepared.get("status")!="REQUIRED_CONFIRMATION_CPU_POOL_PREPARED_NOT_ACTIVATED" or prepared.get("tests")!=304 or prepared.get("source_check",{}).get("status")!="PASS":
    raise ValueError("Closed304-test actual40-source CPU pool preparation required")
sources=json.loads((base/"proposed_sources.json").read_text());original=copy.deepcopy(sources)
def load_module(name,filename):
    m=types.ModuleType(name);exec(compile(sources[filename],name,"exec"),m.__dict__);return m
h=load_module("infrastructure","workflows/benchmark_evaluation/infrastructure_handover.py")
helper=load_module("confirmation_cpu_pool","workflows/benchmark_evaluation/confirmation_cpu_pool.py")
binding_helper=load_module("biogen_confirmation_cpu","workflows/benchmark_evaluation/biogen_confirmation_cpu.py")
chain=load_module("conditional_chain","workflows/benchmark_evaluation/conditional_chain.py")
transport=load_module("native_slurm_transport","workflows/benchmark_evaluation/native_slurm_transport.py")
def command(*args):return subprocess.run(args,text=True,capture_output=True,check=True,timeout=60).stdout.strip()
preparation=json.loads((b1/"conditional_preparation/C1/job_4538209/manifest.json").read_text())
old_bindings_path=b1/"C1_Biogen_confirmation_CPU_native_chain/job_4538268/dispatch_bindings.json"
bindings=json.loads(old_bindings_path.read_text());groups=preparation["prepared_native_groups"]
cpu_models=json.loads((base/"prepared_CPU_models.json").read_text())
if len(groups)!=43 or len(bindings["groups"])!=43 or len(cpu_models)!=40 or sum(len(row["group"]["required_tasks"]) for row in cpu_models)!=162:
    raise ValueError("Exact complete175 configuration chain with162 pending configurations required")
selected={row["original_GPU_job"] for row in cpu_models}
expected=set(range(4538216,4538259))-{4538218,4538219,4538220}
if selected!=expected or len({r["CPU_slot"] for r in cpu_models})!=8:raise ValueError("Exact40 zero-start identities and eight CPU slots required")
for row in cpu_models:
    index=row["group_index"];group=groups[index];bound=bindings["groups"][index]
    if row["group"]!=group or str(bound["primary_job"])!=str(group["primary_job"]) or len(bound["runs"])!=1 or int(bound["runs"][0]["job"])!=row["original_GPU_job"]:
        raise ValueError("Original group/task/source binding changed")
reports=[4538272,4538273,4538274];all_old=sorted(selected)+reports
def pending(job,allow_own_hold=False):
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0":raise ValueError("Exact owned never-started identity required")
    if not allow_own_hold and fields.get("Reason")=="JobHeldUser":raise ValueError("Preserve pre-existing user holds")
    return raw,fields
records={}
for job in all_old:
    raw,fields=pending(job);records[str(job)]=raw
    if job in selected:
        row=next(r for r in cpu_models if r["original_GPU_job"]==job)
        if fields.get("Command")!=row["group"]["script"] or fields.get("ReqNodeList")!=row["group"]["node"]:
            raise ValueError("Original actual GPU source placement changed")
closed=[4538208,4538209,4538284,4538269,4538270,4538271]
native=transport.native_control(["sacct","-n","-X","-j",",".join(map(str,closed)),"--format=JobID,User,State,ExitCode","--parsable2"])
actual={int(p[0]):p for line in native.splitlines() if len(p:=line.strip().split("|"))>=4 and p[0].isdigit()}
if set(actual)!=set(closed) or any(p[1:4]!=["zixiao","COMPLETED","0:0"] for p in actual.values()):
    raise ValueError("Preserve closed primary statistics, source preparation and all13 Biogen model configurations")
out=b1/"C1_required_confirmation_CPU_pool_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
def write(name,value):
    safe();path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
write("native_controller.py",__controller_source__);write("original_native_records.json",json.dumps(records,indent=2)+"\n")
ledger=dict(status="PREPARING_ZERO_START_REQUIRED_CONFIRMATION_CPU_POOL",job=os.environ["SLURM_JOB_ID"],preparation_job=4538284,tests=304,
    primary_statistics_unchanged=4538208,source_preparation_unchanged=4538209,full_required_configurations=175,total_native_groups=43,
    preserved_closed_Biogen_jobs=[4538269,4538270,4538271],preserved_closed_Biogen_configurations=13,CPU_required_configurations=162,CPU_native_groups=40,
    selected_zero_start_GPU_jobs=sorted(selected),original_reports=reports,original_bindings=str(old_bindings_path),
    original_native_records=str(out/"original_native_records.json"),closed_native_accounting=native,
    benchmark_NFS_pool_bytes=40*1024**3,maximum_parallel_CPU_models=8,original_effective_preprocessing_jobs=2,
    original_programs_weights_seeds_tasks_folds_masks_population_preserved=True,healthy_running_jobs_never_cancelled=True,
    held_old=[],new_native_jobs=[],cancelled_zero_start=[],released=[])
def save():write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save()
for job in all_old:
    pending(job);command("scontrol","hold",str(job));ledger["held_old"].append(job);save()
for job in all_old:
    _,fields=pending(job,True)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("All affected old zero-start jobs must be held")
cache=out/"proposed_sources.json";plan_path=out/"CPU_confirmation_plan.json"
script=write("confirmation_cpu_pool.sbatch",sources["workflows/benchmark_evaluation/confirmation_cpu_pool.sbatch"])
models=[];replacement={};previous={}
for row in cpu_models:
    helper.validate_required_group(row["group"])
    expected=helper.prepare_required_cpu_source(Path(row["original_program"]).read_text(),row["group"],row["allocated_CPUs"])
    if expected!=Path(row["prepared_CPU_program"]).read_text():raise ValueError("Prepared CPU source changed")
    slot=row["CPU_slot"];dependency="afterok:"+os.environ["SLURM_JOB_ID"]
    if slot in previous:dependency+=",afterany:"+str(previous[slot])
    response=transport.native_control(["sbatch","--parsable","--hold","--dependency="+dependency,
        "--nodelist="+row["node"],"--cpus-per-task="+str(row["allocated_CPUs"]),
        "--export=ALL,BENCHMARK_SOURCE_CACHE="+str(cache)+",BENCHMARK_CONFIRMATION_CPU_PLAN="+str(plan_path)+",BENCHMARK_CONFIRMATION_CPU_PYTHON="+row["python"],str(script)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",response):raise ValueError("Actual held CPU identity required")
    job=int(response.split(";")[0]);replacement[row["original_GPU_job"]]=job;previous[slot]=job
    models.append(dict(row,new_native_job=job,original_native_state="PENDING_ZERO_RUNTIME",original_model_fits_started=0,dependency=dependency))
    ledger["new_native_jobs"].append(dict(job=job,kind="CPU_required_confirmation",node=row["node"],allocated_CPUs=row["allocated_CPUs"],
        CPU_slot=slot,original_GPU_job=row["original_GPU_job"],dependency=dependency));save()
plan=dict(schema="C1_REQUIRED_CONFIRMATION_CPU_POOL_V1",job=os.environ["SLURM_JOB_ID"],models=models,
    maximum_parallel_CPU_models=8,benchmark_NFS_pool_bytes=40*1024**3,frozen_primary_statistics_job=4538208,full_required_configurations=175,
    preserved_closed_Biogen_jobs=[4538269,4538270,4538271],CPU_preprocessing_jobs=2)
write("CPU_confirmation_plan.json",json.dumps(plan,indent=2)+"\n")
new_bindings=binding_helper.rebind_confirmation_runs(bindings,replacement)
if len(new_bindings["groups"])!=43 or [str(g["primary_job"]) for g in new_bindings["groups"]]!=[str(g["primary_job"]) for g in bindings["groups"]]:
    raise ValueError("All43 original primary identities and order must stay")
for i in (2,3,4):
    if new_bindings["groups"][i]!=bindings["groups"][i]:raise ValueError("Completed Biogen source was modified")
bindings_path=write("dispatch_bindings.json",json.dumps(new_bindings,indent=2)+"\n")
active_jobs=list(replacement.values())
if len(set(active_jobs))!=40:raise ValueError("Exactly40 new native model identities required")
def submit_report(name,raw,dependency,kind):
    subprocess.run(["bash","-n"],input=raw,text=True,capture_output=True,check=True);path=write(name,raw)
    value=transport.native_control(["sbatch","--parsable","--hold","--dependency="+dependency,str(path)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",value):raise ValueError("Actual held report identity required")
    job=int(value.split(";")[0]);ledger["new_native_jobs"].append(dict(job=job,kind=kind,dependency=dependency));save();return job
# Closed, possibly purged Biogen IDs stay in durable source bindings, never new Slurm dependencies.
for name in ("workflows/benchmark_evaluation/c1_confirmation_report.sbatch","workflows/benchmark_evaluation/c1_final_confirmed_results_export.sbatch"):
    sources[name]=sources[name].replace("#SBATCH --nodelist=compute-0-13\n","#SBATCH --nodelist=compute-0-12\n",1)
report_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/c1_confirmation_report.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_CONFIRMATION_BINDINGS_JSON=str(bindings_path)))
new_report=submit_report("first_C1_confirmation_report.sbatch",report_source,"afterany:"+":".join(map(str,active_jobs)),"confirmation_report")
report_manifest=b1/"conditional_evidence/C1"/("job_"+str(new_report))/"manifest.json"
combine_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/confirmation_evidence_combine.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_B1_CONFIRMATION_REPORT=str(b1/"conditional_evidence/B1/job_4537462/manifest.json"),
         BENCHMARK_C1_CONFIRMATION_REPORT=str(report_manifest)))
new_combine=submit_report("combine_confirmation_evidence.sbatch",combine_source,"afterok:"+str(new_report),"evidence_combine")
evidence=b1/"conditional_evidence/combined"/("job_"+str(new_combine))/"manifest.json"
final_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/c1_final_confirmed_results_export.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_CONFIRMATION_EVIDENCE_JSON=str(evidence)))
new_final=submit_report("final_C1_results.sbatch",final_source,"afterok:"+str(new_combine),"final_export")
ledger.update(replacement={str(k):v for k,v in replacement.items()},active_model_jobs=active_jobs,
    new_confirmation_report=new_report,new_evidence_combination=new_combine,new_final_export=new_final,
    source_cache=str(cache),bindings_path=str(bindings_path),CPU_plan=str(plan_path),all_native_IDs_recorded_before_activation=True);save()
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
if index["C1_conditional_automatic_chain"].get("current_job")!=4538268 or index["C1_primary_consumer"].get("current_job")!=4538208:
    raise ValueError("Current registered normal chain differs")
previous_chain=index["C1_conditional_automatic_chain"]
index["C1_conditional_automatic_chain"]=dict(previous_completed_mixed_dispatcher=previous_chain,current_job=int(os.environ["SLURM_JOB_ID"]),
    preparation_job=4538209,primary_report=4538208,source_cache=str(cache),active_bindings=str(bindings_path),
    all_remaining_zero_start_confirmations_CPU_pool=True,preserved_closed_Biogen_jobs=[4538269,4538270,4538271],
    maximum_running_CPU_models=8,confirmation_report=new_report,evidence_combination=new_combine,final_export=new_final,
    final_export_pretraining_overlap_status_explicit=True,original_GPU_programs_retained_for_idle_GPU_handover=True)
index["C1_remaining_required_confirmation_CPU_pool_20261122"]=dict(ledger)
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
sources["workflows/benchmark_evaluation/c1_confirmation_cpu_pool_native_handover.py"]=__controller_source__
for name in ("workflows/benchmark_evaluation/c1_producer_bindings.json","workflows/benchmark_evaluation/c1_primary_comparisons.sbatch",
    "workflows/benchmark_evaluation/c1_conditional_sources_prepare.sbatch","workflows/benchmark_evaluation/conditional_chain.py"):
    if sources[name]!=original[name]:raise ValueError("Frozen primary source or original GPU dispatch logic changed")
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
if check["status"]!="PASS":raise ValueError("Complete recorded CPU pool source tree must pass before retiring old zero-start handles")
ledger["source_check"]=check;save()
for job in all_old:pending(job,True)
for job in all_old:
    pending(job,True);command("scancel",str(job));ledger["cancelled_zero_start"].append(job);save()
new_jobs=[int(item["job"]) for item in ledger["new_native_jobs"]]
for job in new_jobs:
    _,fields=pending(job,True)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("Only exact recorded held jobs may be released")
ledger["status"]="FULL175_CONFIRMATION_CHAIN_RECORDED_BEFORE_CPU_POOL_RELEASE";save()
for job in new_jobs:
    transport.native_control(["scontrol","release",str(job)]);ledger["released"].append(job);save()
ledger["status"]="REQUIRED_CONFIRMATION_CPU_POOL_AND_FULL_REPORT_CHAIN_RELEASED";save()
print(json.dumps({k:v for k,v in ledger.items() if k not in {"closed_native_accounting","new_native_jobs"}}),flush=True)
