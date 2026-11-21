import copy,json,os,re,subprocess,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
if os.getuid()!=1278:raise ValueError("Exact native owner required")
base=b1/"C1_Biogen_confirmation_CPU_preparation/job_4538266"
prepared=json.loads((base/"manifest.json").read_text())
if prepared.get("status")!="BIOGEN_REQUIRED_CONFIRMATION_CPU_PREPARED_NOT_ACTIVATED" or prepared.get("tests")!=293 or prepared.get("source_check",{}).get("status")!="PASS":
    raise ValueError("Closed293-test CPU source and queue preparation required")
sources=json.loads((base/"proposed_sources.json").read_text());original=copy.deepcopy(sources)
def load_module(name,filename):
    m=types.ModuleType(name);exec(compile(sources[filename],name,"exec"),m.__dict__);return m
h=load_module("infrastructure","workflows/benchmark_evaluation/infrastructure_handover.py")
helper=load_module("biogen_confirmation_cpu","workflows/benchmark_evaluation/biogen_confirmation_cpu.py")
chain=load_module("conditional_chain","workflows/benchmark_evaluation/conditional_chain.py")
transport=load_module("native_slurm_transport","workflows/benchmark_evaluation/native_slurm_transport.py")
def command(*args):return subprocess.run(args,text=True,capture_output=True,check=True,timeout=60).stdout.strip()
preparation_path=b1/"conditional_preparation/C1/job_4538209/manifest.json"
preparation=json.loads(preparation_path.read_text())
state_path=b1/"conditional_dispatch/C1/job_4538215/dispatch_state.json"
state=json.loads(state_path.read_text());groups=preparation["prepared_native_groups"];bindings=state["bindings"]
cpu_models=json.loads((base/"prepared_CPU_models.json").read_text())
if (preparation.get("required_configuration_rows")!=175 or len(groups)!=43 or len(bindings.get("groups",[]))!=43
    or state.get("status")!="C1_CONDITIONAL_CHAIN_RELEASED" or len(cpu_models)!=3
    or {row["original_GPU_job"] for row in cpu_models}!={4538218,4538219,4538220}
    or (state.get("report_job"),state.get("combination_job"),state.get("final_export_job"))!=(4538259,4538260,4538261)):
    raise ValueError("One exact complete original175-configuration current chain required")
if sum(len(row["group"]["required_tasks"]) for row in cpu_models)!=13:raise ValueError("Only13 already required CPU configurations")
gpu_jobs=[];ordered=[]
for group,binding in zip(groups,bindings["groups"]):
    if str(group["primary_job"])!=str(binding["primary_job"]) or len(binding["runs"])!=1 or binding["runs"][0].get("array") is not False:
        raise ValueError("Original nonarray primary-to-actual-source binding differs")
    job=int(binding["runs"][0]["job"]);gpu_jobs.append(job);ordered.append(dict(job=job,uuid=group["uuid"]))
if gpu_jobs!=list(range(4538216,4538259)):raise ValueError("Exact actual43 GPU identities required")
reports=[4538259,4538260,4538261];all_old=gpu_jobs+reports;selected={row["original_GPU_job"] for row in cpu_models}
def pending(job,allow_own_hold=False):
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0":raise ValueError("Exact owned never-started native identity required")
    if not allow_own_hold and fields.get("Reason")=="JobHeldUser":raise ValueError("Preserve pre-existing user holds")
    return raw,fields
records={}
for job in all_old:
    raw,fields=pending(job);records[str(job)]=raw
    if job in gpu_jobs:
        group=groups[gpu_jobs.index(job)]
        if fields.get("Command")!=group["script"] or fields.get("ReqNodeList")!=group["node"]:raise ValueError("Original native GPU source/placement was changed externally")
native=transport.native_control(["sacct","-n","-X","-j","4538208,4538209,4538266","--format=JobID,User,State,ExitCode","--parsable2"])
actual={int(p[0]):p for line in native.splitlines() if len(p:=line.strip().split("|"))>=4 and p[0].isdigit()}
if set(actual)!={4538208,4538209,4538266} or any(p[1:4]!=["zixiao","COMPLETED","0:0"] for p in actual.values()):
    raise ValueError("Keep original full statistics and confirmation preparation successful")
out=b1/"C1_Biogen_confirmation_CPU_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
def write(name,value):
    safe();path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
write("native_controller.py",__controller_source__);write("original_native_records.json",json.dumps(records,indent=2)+"\n")
ledger=dict(status="PREPARING_OWNED_ZERO_START_BIOGEN_CPU_HANDOVER",job=os.environ["SLURM_JOB_ID"],preparation_job=4538266,tests=293,
    primary_statistics_unchanged=4538208,source_preparation_unchanged=4538209,original_dispatcher_unchanged=4538215,
    full_required_configurations=175,total_native_groups=43,CPU_required_configurations=13,CPU_native_groups=3,remaining_GPU_groups=40,
    selected_zero_start_GPU_jobs=sorted(selected),original_reports=reports,old_native_records=str(out/"original_native_records.json"),
    original_statistics_native_accounting=native,benchmark_NFS_pool_bytes=40*1024**3,maximum_parallel_CPU_models=3,
    original_GPU_programs_weights_seeds_tasks_primary_IDs_folds_masks_population_preserved=True,healthy_running_jobs_never_cancelled=True,
    held_old=[],new_native_jobs=[],GPU_dependencies_updated={},cancelled_zero_start=[],released=[])
def save():write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save()
for job in all_old:
    pending(job);command("scontrol","hold",str(job));ledger["held_old"].append(job);save()
for job in all_old:
    _,fields=pending(job,True)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("All affected old zero-start jobs must be held before mutation")
queues={}
for node in sorted({group["node"] for group in groups}):
    queues[node]=command("squeue","--array","-h","-p","gpu","-w",node,"-t","RUNNING,COMPLETING,CONFIGURING,SUSPENDED,RESIZING","-o","%i|%u|%T")
barriers=chain.protected_gpu_predecessors(groups,queues)
dependencies=helper.remaining_gpu_dependencies(ordered,selected,barriers)
if len(dependencies)!=40:raise ValueError("Every remaining GPU job must keep an ordered protected predecessor")
ledger["fresh_protected_GPU_predecessors"]=barriers;write("fresh_protected_GPU_queues.json",json.dumps(queues,indent=2)+"\n");save()
cache=out/"proposed_sources.json";plan_path=out/"CPU_confirmation_plan.json"
cpu_script=write("biogen_confirmation_cpu.sbatch",sources["workflows/benchmark_evaluation/biogen_confirmation_cpu.sbatch"])
models=[];replacement={}
for row in cpu_models:
    helper.validate_biogen_group(row["group"])
    expected=helper.prepare_biogen_confirmation_cpu_source(Path(row["original_program"]).read_text(),row["group"],16)
    if expected!=Path(row["prepared_CPU_program"]).read_text():raise ValueError("The actual prepared CPU source no longer matches")
    response=transport.native_control(["sbatch","--parsable","--hold","--dependency=afterok:"+os.environ["SLURM_JOB_ID"],
        "--nodelist="+row["node"],"--export=ALL,BENCHMARK_SOURCE_CACHE="+str(cache)+",BENCHMARK_CONFIRMATION_CPU_PLAN="+str(plan_path)+",BENCHMARK_CONFIRMATION_CPU_PYTHON="+row["python"],str(cpu_script)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",response):raise ValueError("Actual held CPU identity required")
    job=int(response.split(";")[0]);replacement[row["original_GPU_job"]]=job
    item=dict(row,new_native_job=job,original_native_state="PENDING_ZERO_RUNTIME",original_model_fits_started=0)
    models.append(item);ledger["new_native_jobs"].append(dict(job=job,kind="CPU_required_confirmation",node=row["node"],allocated_CPUs=16,original_GPU_job=row["original_GPU_job"]))
    save()
plan=dict(schema="C1_BIOGEN_REQUIRED_CONFIRMATION_CPU_V1",job=os.environ["SLURM_JOB_ID"],models=models,
    maximum_parallel_CPU_models=3,benchmark_NFS_pool_bytes=40*1024**3,frozen_primary_statistics_job=4538208,full_required_configurations=175)
write("CPU_confirmation_plan.json",json.dumps(plan,indent=2)+"\n")
new_bindings=helper.rebind_confirmation_runs(bindings,replacement)
if len(new_bindings["groups"])!=43 or {str(g["primary_job"]) for g in new_bindings["groups"]}!={str(g["primary_job"]) for g in bindings["groups"]}:
    raise ValueError("All43 original primary identities must stay")
bindings_path=write("dispatch_bindings.json",json.dumps(new_bindings,indent=2)+"\n")
remaining=[job for job in gpu_jobs if job not in selected];active_jobs=remaining+list(replacement.values())
if len(set(active_jobs))!=43:raise ValueError("Exactly43 actual active model groups required")
def submit_report(name,raw,dependency,kind):
    subprocess.run(["bash","-n"],input=raw,text=True,capture_output=True,check=True)
    path=write(name,raw)
    value=transport.native_control(["sbatch","--parsable","--hold","--dependency="+dependency,str(path)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",value):raise ValueError("Actual held report identity required")
    job=int(value.split(";")[0]);ledger["new_native_jobs"].append(dict(job=job,kind=kind,dependency=dependency));save();return job
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
ledger.update(replacement={str(k):v for k,v in replacement.items()},remaining_GPU_jobs=remaining,active_model_jobs=active_jobs,
    new_confirmation_report=new_report,new_evidence_combination=new_combine,new_final_export=new_final,source_cache=str(cache),
    bindings_path=str(bindings_path),CPU_plan=str(plan_path),all_model_and_report_IDs_recorded_before_activation=True)
save()
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
if index["C1_conditional_automatic_chain"].get("current_job")!=4538215 or index["C1_primary_consumer"].get("current_job")!=4538208:
    raise ValueError("Current normal registered chain differs")
previous=index["C1_conditional_automatic_chain"]
index["C1_conditional_automatic_chain"]=dict(previous_completed_GPU_dispatcher=previous,current_job=int(os.environ["SLURM_JOB_ID"]),
    preparation_job=4538209,primary_report=4538208,source_cache=str(cache),active_bindings=str(bindings_path),mixed_CPU_GPU_confirmation=True,
    confirmation_report=new_report,evidence_combination=new_combine,final_export=new_final,final_export_pretraining_overlap_status_explicit=True)
index["C1_Biogen_required_confirmation_CPU_handover_20261122"]=dict(ledger)
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
sources["workflows/benchmark_evaluation/c1_biogen_confirmation_cpu_native_handover.py"]=__controller_source__
for name in ("workflows/benchmark_evaluation/c1_producer_bindings.json","workflows/benchmark_evaluation/c1_primary_comparisons.sbatch",
             "workflows/benchmark_evaluation/c1_conditional_sources_prepare.sbatch","workflows/benchmark_evaluation/conditional_chain.py"):
    if sources[name]!=original[name]:raise ValueError("Primary scientific source or original GPU dispatch semantics changed")
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
if check["status"]!="PASS":raise ValueError("Complete recorded mixed-backend source tree must pass before dependency or cancellation changes")
ledger["source_check"]=check;save()
for job in all_old:pending(job,True)
for job in remaining:
    pending(job,True);base_dep=dependencies[str(job)]
    dependency=(base_dep+"," if base_dep else "")+"afterok:"+os.environ["SLURM_JOB_ID"]
    command("scontrol","update","JobId="+str(job),"Dependency="+dependency)
    ledger["GPU_dependencies_updated"][str(job)]=dependency;save()
for job in sorted(selected)+reports:
    pending(job,True);command("scancel",str(job));ledger["cancelled_zero_start"].append(job);save()
new_jobs=[int(item["job"]) for item in ledger["new_native_jobs"]]
for job in remaining+new_jobs:
    _,fields=pending(job,True)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("Only exact recorded held jobs may be released")
ledger["status"]="FULL_MIXED_CONFIRMATION_CHAIN_RECORDED_BEFORE_RELEASE";save()
for job in remaining+new_jobs:
    transport.native_control(["scontrol","release",str(job)]);ledger["released"].append(job);save()
ledger["status"]="BIOGEN_REQUIRED_CPU_CONFIRMATIONS_AND_PROTECTED_GPU_CHAIN_RELEASED";save()
print(json.dumps({k:v for k,v in ledger.items() if k not in {"GPU_dependencies_updated","held_old","original_statistics_native_accounting"}}),flush=True)
