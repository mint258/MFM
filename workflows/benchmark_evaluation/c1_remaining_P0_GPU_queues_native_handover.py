"""Queue only still-unstarted registered C1 tails on the released original GPU5/6 cards; preserve all live models."""
import copy,csv,io,json,os,re,shlex,subprocess,sys,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
os.environ["BENCHMARK_NATIVE_SLURM_ACCOUNTING_CONFIG"]="/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/native_accounting_slurm_direct_20261122.conf"
safe()
if os.getuid()!=1278:raise ValueError("Exact native owner required")
preparation_job=int(os.environ["BENCHMARK_IDLE_GPU_PREPARATION_JOB"])
base=b1/"C1_remaining_P0_GPU_queue_preparation"/("job_"+str(preparation_job))
prepared=json.loads((base/"manifest.json").read_text())
if prepared.get("status")!="FOUR_ORIGINAL_GPU_QUEUE_CANDIDATES_PREPARED_NOT_ACTIVATED" or prepared.get("tests")!=327 or prepared.get("source_check",{}).get("status")!="PASS":
    raise ValueError("Closed327-test original GPU queue preparation required")
sources=json.loads((base/"proposed_sources.json").read_text());original=copy.deepcopy(sources)
def module(name,path):
    m=types.ModuleType(name);exec(compile(sources[path],name,"exec"),m.__dict__);return m
h=module("infrastructure","workflows/benchmark_evaluation/infrastructure_handover.py")
helper=module("confirmation_cpu_pool","workflows/benchmark_evaluation/confirmation_cpu_pool.py")
rebinder=module("biogen_confirmation_cpu","workflows/benchmark_evaluation/biogen_confirmation_cpu.py")
chain=module("conditional_chain","workflows/benchmark_evaluation/conditional_chain.py")
transport=module("native_slurm_transport","workflows/benchmark_evaluation/native_slurm_transport.py")
def command(*args):
    options={}
    if args[0]=="srun":
        options["env"]={k:v for k,v in os.environ.items() if not k.startswith(("SLURM_","SBATCH_"))}
    return subprocess.run(args,text=True,capture_output=True,check=True,timeout=60,**options).stdout.strip()
old_base=b1/"C1_GPU_prefit_guard_repair_native_chain/job_4538468"
bindings=json.loads((old_base/"dispatch_bindings.json").read_text());rows=json.loads((base/"prepared_GPU_models.json").read_text())
original_slots=json.loads((b1/"C1_required_confirmation_CPU_pool_native_chain/job_4538288/CPU_confirmation_plan.json").read_text())["models"]
if len(bindings["groups"])!=43 or len(rows)!=4 or {r["replaced_CPU_job"] for r in rows}!={4538349,4538350,4538352,4538353}:
    raise ValueError("Full175/43 registered chain and three exact pending tails required")
reports=[4538473,4538474,4538475,4538476]
for row in rows:row["original_CPU_slot"]=row["CPU_slot"]
all_ids=[int(run["job"]) for group in bindings["groups"] for run in group["runs"]]
if len(all_ids)!=43 or len(set(all_ids))!=43:raise ValueError("Exactly43 distinct actual model sources required")
native=transport.native_control(["sacct","-n","-X","-j",",".join(map(str,all_ids+[preparation_job,4538208,4538209,4537555,4537556])),
    "--format=JobID,User,State,ExitCode,NodeList","--parsable2"])
actual={int(p[0]):dict(user=p[1],state=p[2],exit_code=p[3],node=p[4]) for line in native.splitlines()
    if len(p:=line.strip().split("|"))>=5 and p[0].isdigit()}
if set(actual)!=set(all_ids+[preparation_job,4538208,4538209,4537555,4537556]) or any(v["user"]!="zixiao" for v in actual.values()):raise ValueError("Exact native owned source accounting required")
for job in all_ids:
    if actual[job]["state"] not in {"COMPLETED","RUNNING","PENDING"} or (actual[job]["state"]=="COMPLETED" and actual[job]["exit_code"]!="0:0"):
        raise ValueError("Diagnose a new source failure before changing unrelated capacity")
for job in (preparation_job,4538208,4538209,4537555,4537556,4538471,4538472):
    if actual[job]["state"]!="COMPLETED" or actual[job]["exit_code"]!="0:0":raise ValueError("Closed successful preparation and primary statistics required")
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
sys.modules[package.__name__+".confirmation_cpu_pool"]=helper
gpu_helper=types.ModuleType(package.__name__+".idle_gpu_confirmation");gpu_helper.__package__=package.__name__;sys.modules[gpu_helper.__name__]=gpu_helper
exec(compile(sources["workflows/benchmark_evaluation/idle_gpu_confirmation.py"],gpu_helper.__name__,"exec"),gpu_helper.__dict__)
rows=gpu_helper.select_pending_rows(rows,actual)
if not rows:
    print(json.dumps(dict(status="NO_STILL_UNSTARTED_REGISTERED_GPU_CANDIDATES",models_restarted=False,old_report_chain_unchanged=reports)),flush=True)
    raise SystemExit(0)
selected={r["replaced_CPU_job"] for r in rows}
def pending(job,own_hold=False):
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0":raise ValueError("Exact owned never-started native identity required")
    if not own_hold and fields.get("Reason")=="JobHeldUser":raise ValueError("Preserve pre-existing user holds")
    return raw,fields
resources={};GPU_observations={}
probe="import json,os,socket,subprocess; print(json.dumps(dict(node=socket.gethostname().split('.')[0],cards=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True),contexts=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True),capacity={p:dict(total=os.statvfs(p).f_blocks*os.statvfs(p).f_frsize,available=os.statvfs(p).f_bavail*os.statvfs(p).f_frsize,inodes=os.statvfs(p).f_favail) for p in ['/', '/tmp', '/share/home/zixiao/descriptor_analysis']},MemAvailable=[l.strip() for l in open('/proc/meminfo') if l.startswith('MemAvailable:')])))"
for row in {r["node"]:r for r in rows}.values():
    node=row["node"];uuid=row["uuid"]
    resource=h.native_fields(command("scontrol","show","node",node,"-o"))
    if resource.get("NodeName")!=node or node not in {"compute-0-5","compute-0-6"} or "gpu" not in resource.get("Partitions","").split(",") or int(resource["CPUTot"])-int(resource["CPUAlloc"])<2:
        raise ValueError("Actual native gpu-partition two-CPU availability required")
    observed=json.loads(command("srun","--partition=gpu","--nodelist="+node,"--ntasks=1","--cpus-per-task=1","--input=none","--export=PATH=/usr/bin:/bin,LC_ALL=C","--chdir=/","--immediate=10","--time=00:01:00","--job-name=C1-readonly-GPU-OS-probe","/usr/bin/python3","-I","-S","-c",probe))
    cards=list(csv.reader(io.StringIO(observed["cards"])));contexts=list(csv.reader(io.StringIO(observed["contexts"])))
    if observed["node"]!=node or len(cards)!=1 or cards[0][0].strip()!=uuid or contexts:
        raise ValueError("The target physical small-task GPU must have no compute context")
    card=cards[0]
    if float(card[1])>float(card[2])*.30 or float(card[2])-float(card[1])<18432 or float(card[3])>5:
        raise ValueError("Actual idle GPU VRAM/activity admission required")
    for target in ("/","/tmp"):
        st=observed["capacity"][target]
        if st["available"]<max(10*1024**3,st["total"]//10)+1024**3 or st["inodes"]<2000:raise ValueError("Native root/tmp system/Slurm reserve required")
    if observed["capacity"]["/share/home/zixiao/descriptor_analysis"]["available"]<40*1024**3:raise ValueError("Actual target NFS capacity required")
    resources[node]=resource;GPU_observations[node]=observed
records={}
for row in rows:
    job=row["replaced_CPU_job"];bound=bindings["groups"][row["group_index"]]
    if len(bound["runs"])!=1 or int(bound["runs"][0]["job"])!=job or str(bound["primary_job"])!=str(row["group"]["primary_job"]):
        raise ValueError("Current registered tail source changed")
    for other in all_ids:
        if other in selected or actual[other]["state"]!="PENDING":continue
        other_raw=command("scontrol","show","job",str(other),"-o");other_fields=h.require_owned_pending(other_raw)
        if str(job) in re.findall(r"after(?:any|ok|notok):([0-9]+)",other_fields.get("Dependency","")):raise ValueError("Do not orphan any unselected pending successor")
    raw,fields=pending(job);records[str(job)]=raw
    if actual[job]["state"]!="PENDING" or fields.get("Command")!=str(b1/"C1_confirmation_environment_repair_native_chain/job_4538337/confirmation_cpu_pool.sbatch") or fields.get("ReqNodeList")!=helper.CPU_SLOTS[row["original_CPU_slot"]]:
        raise ValueError("Exact original pending queue-tail script and placement required")
for job in reports:
    raw,_=pending(job);records[str(job)]=raw
out=b1/"C1_remaining_P0_GPU_queues_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
def write(name,value):
    safe();path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
write("native_controller.py",__controller_source__);write("zero_start_native_records.json",json.dumps(records,indent=2)+"\n")
ledger=dict(status="PREPARING_STILL_UNSTARTED_C1_TAILS_IN_TWO_RELEASED_GPU_QUEUES",job=os.environ["SLURM_JOB_ID"],preparation_job=preparation_job,tests=327,
    full_required_configurations=175,total_native_groups=43,replacement_groups=len(rows),replacement_configurations=len(rows),maximum_parallel_CPU_models=11,maximum_parallel_GPU_models=2,
    original_eight_CPU_slots_preserved=True,GPU_node_resource_fields=resources,actual_GPU_observations=GPU_observations,
    completed_protected_predecessors={str(j):actual[j] for j in (4537555,4537556)},
    no_unselected_CPU_dependencies_changed=True,no_active_model_restarted=True,
    benchmark_NFS_pool_bytes=40*1024**3,temporary_forecast_per_model_bytes=1024**3,maximum_model_temporary_forecast_bytes=13*1024**3,
    selected_zero_start_CPU_jobs=sorted(selected),old_reports=reports,source_accounting=native,
    preserved_RUNNING=[j for j in all_ids if actual[j]["state"]=="RUNNING"],held_old=[],new_native_jobs=[],cancelled_zero_start=[],released=[])
def save():write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save()
for job in sorted(selected)+reports:
    pending(job);command("scontrol","hold",str(job));ledger["held_old"].append(job);save()
for job in sorted(selected)+reports:
    _,fields=pending(job,True)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("Only exact newly owned holds may be changed")
cache=out/"proposed_sources.json";plan_path=out/"GPU_confirmation_plan.json"
models=[];replacement={};previous={}
for row in rows:
    raw=Path(row["original_program"]).read_text()
    if (helper.prepare_required_cpu_source(raw,row["group"],32)!=Path(row["prepared_CPU_program"]).read_text()
        or helper.resolve_confirmation_environment(row["group"],raw,row["group"]["environment"])!=row["execution_environment"]):
        raise ValueError("Exact already-required original CUDA body/selectors and original32CPU adaptation must remain")
    script=write("GPU_group_"+str(row["group_index"])+".sbatch",Path(row["prepared_GPU_script"]).read_text())
    subprocess.run(["bash","-n"],input=script.read_text(),text=True,capture_output=True,check=True)
    dependency="afterok:"+os.environ["SLURM_JOB_ID"]
    if row["node"] in previous:dependency+=",afterany:"+str(previous[row["node"]])
    response=transport.native_control(["sbatch","--parsable","--hold","--dependency="+dependency,str(script)])
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",response):raise ValueError("Actual held native GPU identity required")
    job=int(response.split(";")[0]);replacement[row["replaced_CPU_job"]]=job;previous[row["node"]]=job
    models.append(dict(row,new_native_job=job,original_native_state="PENDING_ZERO_RUNTIME",original_model_fits_started=0,dependency=dependency))
    ledger["new_native_jobs"].append(dict(job=job,kind="REQUIRED_CONFIRMATION_ON_ACTUALLY_IDLE_GPU",node=row["node"],uuid=row["uuid"],allocated_CPUs=2,replaced_CPU_job=row["replaced_CPU_job"],dependency=dependency));save()
write("GPU_confirmation_plan.json",json.dumps(dict(models=models,full_required_configurations=175,total_native_groups=43,benchmark_NFS_pool_bytes=40*1024**3),indent=2)+"\n")
new_bindings=rebinder.rebind_confirmation_runs(bindings,replacement)
for group in new_bindings["groups"]:
    for run in group["runs"]:
        old=next((old for old,new in replacement.items() if int(run["job"])==new),None)
        if old is not None:
            row=next(r for r in rows if r["replaced_CPU_job"]==old)
            run.update(zero_start_GPU_job=row["original_GPU_job"],replaced_zero_start_CPU_job=old,execution_backend="GPU",GPU_node=row["node"],GPU_uuid=row["uuid"])
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
publisher_raw=sources["workflows/benchmark_evaluation/c1_final_byte_publication.sbatch"]
publisher_raw=publisher_raw.replace("4538473",str(new_report)).replace("4538474",str(new_combine)).replace("4538475",str(new_final))
publisher_raw=publisher_raw.replace("C1_GPU_prefit_guard_repair_native_chain/job_4538468","C1_remaining_P0_GPU_queues_native_chain/job_"+os.environ["SLURM_JOB_ID"])
new_publication=submit_report("final_byte_publication.sbatch",publisher_raw,"afterok:"+str(new_final),"final_byte_publication")
sources["workflows/benchmark_evaluation/c1_final_byte_publication.sbatch"]=publisher_raw

ledger.update(replacement={str(k):v for k,v in replacement.items()},active_model_dependencies=active,new_confirmation_report=new_report,
    new_evidence_combination=new_combine,new_final_export=new_final,source_cache=str(cache),bindings_path=str(bindings_path),
    GPU_plan=str(plan_path),new_final_byte_publication=new_publication,all_native_IDs_recorded_before_activation=True);save()
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
cpu19_path=b1/"C1_CPU19_existing_job_parallel_admission/allocation_4538340_step_2/manifest.json"
cpu19=json.loads(cpu19_path.read_text())
if cpu19.get("status")!="OWNED_ZERO_START_SERIAL_WAIT_REMOVED_EXISTING_ID_PRESERVED":raise ValueError("Preserve CPU19 same-ID operation proof")
index["C1_CPU19_same_native_ID_parallel_admission_20261122"]=dict(cpu19,manifest=str(cpu19_path))
index["C1_optional_CPU15_slot9_reuse_not_activated_20261122"]=dict(status="UNRESOLVED_OPTIONAL_RESOURCE_PREPARATION_ONLY",preparation_job=4538488,metadata_count_guard_job=4538490,unused_zero_start_controllers_retired=[4538489,4538491],actual_failed_tests=383,extra_B0_fixture_errors=11,required_scientific_source_8356_unchanged=True,scientific_models_cancelled=[],third_optional_repair=False)
if index["C1_conditional_automatic_chain"].get("current_job")!=4538468 or index["C1_primary_consumer"].get("current_job")!=4538208:raise ValueError("Current native chain changed externally")
prior=index["C1_conditional_automatic_chain"]
index["C1_conditional_automatic_chain"]=dict(previous_completed_CPU_dispatcher=prior,current_job=int(os.environ["SLURM_JOB_ID"]),
    preparation_job=4538209,primary_report=4538208,source_cache=str(cache),active_bindings=str(bindings_path),maximum_running_CPU_models=11,
    confirmation_report=new_report,evidence_combination=new_combine,final_export=new_final,final_byte_publication=new_publication,maximum_running_GPU_models=2,final_export_pretraining_overlap_status_explicit=True,
    full_required_configurations=175,original_eight_CPU_slots_preserved=True,actual_environment_source_repair_closed=True)
index["C1_remaining_zero_start_tails_two_released_GPU_queues_20261122"]=dict(ledger)
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
sources["workflows/benchmark_evaluation/c1_remaining_P0_GPU_queues_native_handover.py"]=__controller_source__
write("proposed_sources.json",json.dumps(sources,ensure_ascii=False,indent=2)+"\n")
check=copy.deepcopy(prepared["source_check"])
check["actual_native_bindings_recorded_before_activation"]=True
check["targeted_actual_controller_compile"]=True
check["post_preparation_changes"]="Only native queue dependencies/IDs, full43 bindings, index and equivalent report/publisher export paths. All scientific bodies unchanged."
write("source_check.json",json.dumps(check,indent=2)+"\n")
ledger["source_check"]=check;save()
for job in sorted(selected)+reports:pending(job,True)
for job in sorted(selected)+reports:
    pending(job,True);command("scancel",str(job));ledger["cancelled_zero_start"].append(job);save()
new_jobs=[int(r["job"]) for r in ledger["new_native_jobs"]]
for job in new_jobs:
    raw=command("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0" or fields.get("Reason")!="JobHeldUser":raise ValueError("Exact owned held new activation identity required")
ledger["status"]="FULL175_TWO_GPU_QUEUES_AND_FINAL_PUBLICATION_IDS_RECORDED_BEFORE_RELEASE";save()
for job in new_jobs:
    transport.native_control(["scontrol","release",str(job)]);ledger["released"].append(job);save()
ledger["status"]="RELEASED_GPU_QUEUES_AND_COMPLETE_FINAL_PUBLICATION_CHAIN_RELEASED";save()
index["C1_remaining_zero_start_tails_two_released_GPU_queues_20261122"]=copy.deepcopy(ledger)
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
write("proposed_sources.json",json.dumps(sources,ensure_ascii=False,indent=2)+"\n")

print(json.dumps({k:v for k,v in ledger.items() if k not in {"source_accounting","new_native_jobs"}}),flush=True)
