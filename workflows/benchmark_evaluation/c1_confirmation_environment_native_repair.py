"""Repair actual pre-fit environment failures and wrong-learner Expansion sources only."""
import copy,json,os,re,subprocess,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
if os.getuid()!=1278:raise ValueError("Exact native owner required")
base=b1/"C1_confirmation_environment_repair_preparation/job_4538335"
prepared=json.loads((base/"manifest.json").read_text())
if prepared.get("status")!="CONFIRMATION_ENVIRONMENT_REPAIR_PREPARED_NOT_ACTIVATED" or prepared.get("tests")!=311 or prepared.get("source_check",{}).get("status")!="PASS":
    raise ValueError("Closed311-test actual40-environment source preparation required")
sources=json.loads((base/"proposed_sources.json").read_text());original=copy.deepcopy(sources)
def load_module(name,filename):
    m=types.ModuleType(name);exec(compile(sources[filename],name,"exec"),m.__dict__);return m
h=load_module("infrastructure","workflows/benchmark_evaluation/infrastructure_handover.py")
helper=load_module("confirmation_cpu_pool","workflows/benchmark_evaluation/confirmation_cpu_pool.py")
binding_helper=load_module("biogen_confirmation_cpu","workflows/benchmark_evaluation/biogen_confirmation_cpu.py")
chain=load_module("conditional_chain","workflows/benchmark_evaluation/conditional_chain.py")
transport=load_module("native_slurm_transport","workflows/benchmark_evaluation/native_slurm_transport.py")
def command(*args):return subprocess.run(args,text=True,capture_output=True,check=True,timeout=60).stdout.strip()
old_base=b1/"C1_required_confirmation_CPU_pool_native_chain/job_4538288"
bindings=json.loads((old_base/"dispatch_bindings.json").read_text())
old_plan=json.loads((old_base/"CPU_confirmation_plan.json").read_text())
rows=json.loads((base/"prepared_CPU_models.json").read_text())
if len(rows)!=40 or len(old_plan["models"])!=40 or len(bindings["groups"])!=43:raise ValueError("Complete current175 configuration source chain required")
old_by_index={r["group_index"]:r for r in old_plan["models"]}
selected=[]
for row in rows:
    old=old_by_index[row["group_index"]]
    if (int(old["new_native_job"])!=row["replaced_CPU_job"] or old["CPU_slot"]!=row["CPU_slot"]
        or old["node"]!=row["node"] or old["allocated_CPUs"]!=row["allocated_CPUs"] or old["group"]!=row["group"]):
        raise ValueError("Registered source/resource binding changed")
    if {r["dataset"] for r in row["group"]["required_tasks"]} in ({"Joung2020"},{"ExpansionRx"}):selected.append(row)
if len(selected)!=25 or sum(len(r["group"]["required_tasks"]) for r in selected)!=36:
    raise ValueError("Only23 Joung pre-fit configurations and13 true Expansion TabPFN configurations need this repair")
selected_ids={r["replaced_CPU_job"] for r in selected}
reports=[4538329,4538330,4538331]
own_held={4538298,4538301,4538302,4538305,4538306,4538309,4538310,4538311,4538313,4538314,4538317,4538318,4538319,4538321,4538322,4538325,4538326,4538327,4538329,4538330,4538331}
all_ids=[r["replaced_CPU_job"] for r in rows]+[4538208,4538209,4538335,4538269,4538270,4538271]
native=transport.native_control(["sacct","-n","-X","-j",",".join(map(str,all_ids)),"--format=JobID,User,State,ExitCode,NodeList","--parsable2"])
accounting={int(p[0]):dict(user=p[1],state=p[2],exit_code=p[3],node=p[4]) for line in native.splitlines()
    if len(p:=line.strip().split("|"))>=5 and p[0].isdigit()}
if set(accounting)!=set(all_ids) or any(r["user"]!="zixiao" for r in accounting.values()):raise ValueError("Exact durable owned source identities required")
for job in (4538208,4538209,4538335,4538269,4538270,4538271):
    if accounting[job]["state"]!="COMPLETED" or accounting[job]["exit_code"]!="0:0":raise ValueError("Preserve successful closed primary and Biogen outputs")
def pending(job):
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0":raise ValueError("Owned zero-start exact native identity required")
    if fields.get("Reason")=="JobHeldUser" and job not in own_held:raise ValueError("Preserve unowned pre-existing user hold")
    return raw,fields
proofs={};pending_old=[];preserved_active=[]
for row in rows:
    job=row["replaced_CPU_job"];record=accounting[job];is_selected=job in selected_ids
    if record["state"]=="PENDING":
        raw,fields=pending(job)
        if fields.get("Command")!=str(old_base/"confirmation_cpu_pool.sbatch") or fields.get("ReqNodeList")!=row["node"]:raise ValueError("Exact original CPU script/placement required")
        pending_old.append(job);proofs[str(job)]=dict(kind="PENDING_ZERO_RUNTIME",native=raw)
        if is_selected:row["original_native_state"]="PENDING_ZERO_RUNTIME"
    elif is_selected and {r["dataset"] for r in row["group"]["required_tasks"]}=={"Joung2020"}:
        log=root.parent.parent/"control"/("C1_confirmation_CPU_pool_"+str(job)+".log")
        text=log.read_text()
        if record["state"]!="FAILED" or record["exit_code"]!="1:0" or "ValueError: Unregistered original model environment selector" not in text:
            raise ValueError("Actual pre-fit environment failure required; no trained model may be restarted")
        if (b1/"confirmation_CPU_runtime"/("job_"+str(job))).exists():raise ValueError("Pre-fit failed source unexpectedly admitted model runtime")
        row["original_native_state"]="FAILED_BEFORE_MODEL_EXECUTION"
        proofs[str(job)]=dict(kind=row["original_native_state"],native=record,log=str(log),runtime_never_admitted=True)
    elif is_selected and {r["dataset"] for r in row["group"]["required_tasks"]}=={"ExpansionRx"}:
        if record["state"]!="COMPLETED" or record["exit_code"]!="0:0":raise ValueError("Exact completed wrong-learner source required")
        folder=b1/("C1_D_ExpansionRx" if row["group"]["feature_group"]=="D" else "C1_Pprime_plus_D_ExpansionRx")/("job_"+str(job))
        meta=json.loads((folder/"manifest.json").read_text())
        log=root.parent.parent/"control"/("C1_confirmation_CPU_pool_"+str(job)+".log");text=log.read_text()
        if meta.get("model")!="LightGBM" or "TASK_CLOSED LightGBM" not in text or "TASK_CLOSED TabPFN" in text:
            raise ValueError("Wrong actual LightGBM selector, with no required TabPFN fit, must be proved")
        row["original_native_state"]="COMPLETED_WRONG_LEARNER_NO_TABPFN_FITS"
        proofs[str(job)]=dict(kind=row["original_native_state"],native=record,actual_model=meta["model"],requested_model="TabPFN",
            diagnostic_source_preserved=str(folder),no_required_TabPFN_model_fitted=True)
    elif not is_selected and record["state"]=="RUNNING":
        raw=command("scontrol","show","job",str(job),"-o");fields=h.native_fields(raw)
        if fields.get("UserId")!="zixiao(1278)" or fields.get("JobState")!="RUNNING" or fields.get("Command")!=str(old_base/"confirmation_cpu_pool.sbatch"):
            raise ValueError("Preserve exact owned running original CPU source")
        preserved_active.append(job);proofs[str(job)]=dict(kind="PRESERVE_RUNNING_WITHOUT_MUTATION",native=raw)
    elif not is_selected and record["state"]=="COMPLETED" and record["exit_code"]=="0:0":
        proofs[str(job)]=dict(kind="PRESERVE_CLOSED_WITHOUT_READBACK",native=record)
    else:raise ValueError("Unexpected actual original source state requires diagnosis before any mutation: "+str(job)+" "+str(record))
for job in reports:
    raw,_=pending(job);pending_old.append(job);proofs[str(job)]=dict(kind="OWN_HELD_ZERO_START_REPORT",native=raw)
out=b1/"C1_confirmation_environment_repair_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
def write(name,value):
    safe();path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
write("native_controller.py",__controller_source__);write("actual_source_proofs.json",json.dumps(proofs,indent=2)+"\n")
ledger=dict(status="PREPARING_FAILED_OR_ZERO_START_ENVIRONMENT_REPAIR",job=os.environ["SLURM_JOB_ID"],preparation_job=4538335,tests=311,
    original_primary_statistics_unchanged=4538208,original_source_preparation_unchanged=4538209,full_required_configurations=175,total_native_groups=43,
    replacement_groups=25,replacement_required_configurations=36,preserved_other_CPU_groups=15,preserved_Biogen_jobs=[4538269,4538270,4538271],
    maximum_parallel_CPU_models=8,benchmark_NFS_pool_bytes=40*1024**3,actual_repair_attempt=1,source_repair_diagnosis_started_UTC="2026-11-21T23:36:00Z",
    source_repair_diagnosis_four_hour_limit_UTC="2026-11-22T03:36:00Z",new_TabPFN_fits_are_first_required_fits=True,
    wrong_LightGBM_outputs_retained_as_diagnostic_not_confirmation=True,source_proofs=str(out/"actual_source_proofs.json"),
    native_accounting=native,preserved_running_unchanged=preserved_active,held_pending=[],new_native_jobs=[],cancelled_zero_start=[],released=[])
def save():write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save()
for job in pending_old:
    _,fields=pending(job)
    if fields.get("Reason")!="JobHeldUser":command("scontrol","hold",str(job));own_held.add(job)
    ledger["held_pending"].append(job);save()
for job in pending_old:
    _,fields=pending(job)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("Exact affected zero-start sources must remain held")
cache=out/"proposed_sources.json";plan_path=out/"CPU_confirmation_plan.json"
script=write("confirmation_cpu_pool.sbatch",sources["workflows/benchmark_evaluation/confirmation_cpu_pool.sbatch"])
models=[];replacement={};previous={};valid_pending_dependencies={}
for row in rows:
    old=row["replaced_CPU_job"];slot=row["CPU_slot"]
    if old not in selected_ids:
        if accounting[old]["state"]=="COMPLETED":continue
        if accounting[old]["state"]=="PENDING":
            dependency="afterok:"+os.environ["SLURM_JOB_ID"]
            if slot in previous:dependency+=",afterany:"+str(previous[slot])
            valid_pending_dependencies[old]=dependency
        previous[slot]=old;continue
    expected=helper.prepare_required_cpu_source(Path(row["original_program"]).read_text(),row["group"],row["allocated_CPUs"])
    env=helper.resolve_confirmation_environment(row["group"],Path(row["original_program"]).read_text(),row["group"]["environment"])
    if expected!=Path(row["prepared_CPU_program"]).read_text() or env!=row["execution_environment"]:raise ValueError("Exact repaired environment/source proof required")
    dependency="afterok:"+os.environ["SLURM_JOB_ID"]
    if slot in previous:dependency+=",afterany:"+str(previous[slot])
    response=transport.native_control(["sbatch","--parsable","--hold","--dependency="+dependency,"--nodelist="+row["node"],"--cpus-per-task="+str(row["allocated_CPUs"]),
        "--export=ALL,BENCHMARK_SOURCE_CACHE="+str(cache)+",BENCHMARK_CONFIRMATION_CPU_PLAN="+str(plan_path)+",BENCHMARK_CONFIRMATION_CPU_PYTHON="+row["python"],str(script)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",response):raise ValueError("Actual held replacement native ID required")
    job=int(response.split(";")[0]);replacement[old]=job;previous[slot]=job
    models.append(dict(row,new_native_job=job,original_model_fits_started=0,dependency=dependency))
    ledger["new_native_jobs"].append(dict(job=job,kind="FIRST_REQUIRED_TABPFN_ENVIRONMENT_REPAIR",replaced_CPU_job=old,
        node=row["node"],allocated_CPUs=row["allocated_CPUs"],CPU_slot=slot,dependency=dependency));save()
if len(models)!=25:raise ValueError("Only25 affected original groups may acquire first required fits")
plan=dict(schema="C1_REQUIRED_CONFIRMATION_CPU_POOL_V1",job=os.environ["SLURM_JOB_ID"],models=models,maximum_parallel_CPU_models=8,
    benchmark_NFS_pool_bytes=40*1024**3,frozen_primary_statistics_job=4538208,full_required_configurations=175,
    unaffected_CPU_sources_preserved=True,preserved_Biogen_jobs=[4538269,4538270,4538271],CPU_preprocessing_jobs=2)
write("CPU_confirmation_plan.json",json.dumps(plan,indent=2)+"\n")
new_bindings=binding_helper.rebind_confirmation_runs(bindings,replacement)
for group in new_bindings["groups"]:
    for run in group["runs"]:
        old=next((old for old,new in replacement.items() if int(run["job"])==new),None)
        if old is not None:
            row=next(r for r in selected if r["replaced_CPU_job"]==old)
            run.update(zero_start_GPU_job=row["original_GPU_job"],replaced_CPU_job=old,actual_first_required_TabPFN_fit=True)
if len(new_bindings["groups"])!=43 or [str(g["primary_job"]) for g in new_bindings["groups"]]!=[str(g["primary_job"]) for g in bindings["groups"]]:
    raise ValueError("All43 frozen primary identities must remain")
bindings_path=write("dispatch_bindings.json",json.dumps(new_bindings,indent=2)+"\n")
active_jobs=list(replacement.values())+[r["replaced_CPU_job"] for r in rows if r["replaced_CPU_job"] not in selected_ids and accounting[r["replaced_CPU_job"]]["state"] in {"RUNNING","PENDING"}]
def submit_report(name,raw,dependency,kind):
    subprocess.run(["bash","-n"],input=raw,text=True,capture_output=True,check=True);path=write(name,raw)
    value=transport.native_control(["sbatch","--parsable","--hold","--dependency="+dependency,str(path)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",value):raise ValueError("Actual held new report ID required")
    job=int(value.split(";")[0]);ledger["new_native_jobs"].append(dict(job=job,kind=kind,dependency=dependency));save();return job
report_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/c1_confirmation_report.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_CONFIRMATION_BINDINGS_JSON=str(bindings_path)))
new_report=submit_report("first_C1_confirmation_report.sbatch",report_source,"afterany:"+":".join(map(str,active_jobs)),"confirmation_report")
report_manifest=b1/"conditional_evidence/C1"/("job_"+str(new_report))/"manifest.json"
combine_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/confirmation_evidence_combine.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_B1_CONFIRMATION_REPORT=str(b1/"conditional_evidence/B1/job_4537462/manifest.json"),BENCHMARK_C1_CONFIRMATION_REPORT=str(report_manifest)))
new_combine=submit_report("combine_confirmation_evidence.sbatch",combine_source,"afterok:"+str(new_report),"evidence_combine")
evidence=b1/"conditional_evidence/combined"/("job_"+str(new_combine))/"manifest.json"
final_source=chain.script_with_exports(sources["workflows/benchmark_evaluation/c1_final_confirmed_results_export.sbatch"],
    dict(BENCHMARK_SOURCE_CACHE=str(cache),BENCHMARK_CONFIRMATION_EVIDENCE_JSON=str(evidence)))
new_final=submit_report("final_C1_results.sbatch",final_source,"afterok:"+str(new_combine),"final_export")
ledger.update(replacement={str(k):v for k,v in replacement.items()},preserved_pending_dependencies={str(k):v for k,v in valid_pending_dependencies.items()},
    active_model_dependencies=active_jobs,new_confirmation_report=new_report,new_evidence_combination=new_combine,new_final_export=new_final,
    source_cache=str(cache),bindings_path=str(bindings_path),CPU_plan=str(plan_path),all_native_IDs_recorded_before_activation=True);save()
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
if index["C1_conditional_automatic_chain"].get("current_job")!=4538288 or index["C1_primary_consumer"].get("current_job")!=4538208:raise ValueError("Current native chain changed externally")
previous_chain=index["C1_conditional_automatic_chain"]
index["C1_conditional_automatic_chain"]=dict(previous_completed_CPU_dispatcher=previous_chain,current_job=int(os.environ["SLURM_JOB_ID"]),
    preparation_job=4538209,primary_report=4538208,source_cache=str(cache),active_bindings=str(bindings_path),actual_environment_repair_attempt=1,
    original_C1_MODEL_TabPFN_V2_selected=True,BENCHMARK_TASK_INDEX_preserved=True,maximum_running_CPU_models=8,
    confirmation_report=new_report,evidence_combination=new_combine,final_export=new_final,final_export_pretraining_overlap_status_explicit=True)
index["C1_CPU_environment_first_fit_repair_20261122"]=dict(ledger)
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
sources["workflows/benchmark_evaluation/c1_confirmation_environment_native_repair.py"]=__controller_source__
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
if check["status"]!="PASS":raise ValueError("Full repaired source tree must pass before any old zero-start retirement")
ledger["source_check"]=check;save()
for job in pending_old:pending(job)
for job,dependency in valid_pending_dependencies.items():
    pending(job);command("scontrol","update","JobId="+str(job),"Dependency="+dependency)
for job in [j for j in pending_old if j in selected_ids]+reports:
    pending(job);command("scancel",str(job));ledger["cancelled_zero_start"].append(job);save()
new_jobs=[int(item["job"]) for item in ledger["new_native_jobs"]]
for job in new_jobs+list(valid_pending_dependencies):
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Reason")!="JobHeldUser" or fields.get("Restarts")!="0":raise ValueError("Exact held activation identity required")
ledger["status"]="FULL175_ENVIRONMENT_REPAIR_CHAIN_RECORDED_BEFORE_RELEASE";save()
for job in new_jobs+list(valid_pending_dependencies):
    transport.native_control(["scontrol","release",str(job)]);ledger["released"].append(job);save()
ledger["status"]="FIRST_REQUIRED_TABPFN_ENVIRONMENT_REPAIR_AND_FULL_REPORT_CHAIN_RELEASED";save()
print(json.dumps({k:v for k,v in ledger.items() if k not in {"native_accounting","new_native_jobs"}}),flush=True)
