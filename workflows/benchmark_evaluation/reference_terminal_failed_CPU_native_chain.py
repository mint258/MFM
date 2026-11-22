import ast,copy,json,os,re,socket,subprocess,sys,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119")
b1=root.parent/"benchmark_B1_20261119"
control=root.parent.parent/"control"
quota=control/"benchmark_B0_quota_20261119.json"
cache=b1/"reference_failed_CPU_resume_preparation/job_4538156/proposed_sources.json"
base=b1/"reference_failed_CPU_resume_preparation/job_4538156/source_view"
def safe():
    for local in (Path("/"),Path("/tmp")):
        s=os.statvfs(local)
        if s.f_bavail*s.f_frsize < max(10*1024**3,s.f_blocks*s.f_frsize//10)+64*1024**2 or s.f_favail<2000:
            raise RuntimeError("Actual CPU root/tmp system/Slurm reserve is insufficient")
    protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
if socket.gethostname().split(".")[0] not in {"compute-0-"+str(i) for i in range(8,20)}-{"compute-0-14","compute-0-18"}:
    raise ValueError("Metadata controller must run on an approved actual CPU node")
if cache.stat().st_uid!=1278 or not base.is_dir():raise ValueError("Owned current source capsule and explicit validated source view required")
sources=json.loads(cache.read_text())
sources["workflows/benchmark_evaluation/reference_terminal_failed_CPU_native_chain.py"]=Path(__file__).read_text()
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[];sys.modules[package.__name__]=package
modules={}
for name in ("infrastructure_handover","reference_closed_fold_resume"):
    module=types.ModuleType(package.__name__+"."+name);module.__package__=package.__name__;sys.modules[module.__name__]=module
    exec(compile(sources["workflows/benchmark_evaluation/"+name+".py"],module.__name__,"exec"),module.__dict__);modules[name]=module
h=modules["infrastructure_handover"];resume=modules["reference_closed_fold_resume"]
original_jobs=(4537812,4537813,4537814,4537817,4537818)
frozen_tasks={"4537812":["Absorption max (nm)"],"4537813":["Lifetime (ns)"],"4537814":["Quantum yield"],"4537817":["emi FWHM (nm)"],"4537818":["G4MP2_absolute","G4MP2_minus_B3LYP"]}
targets=json.loads(os.environ["BENCHMARK_REFERENCE_ACTUAL_CPU_TARGETS"])
if set(targets)!={str(job) for job in original_jobs}:raise ValueError("All five original sources require explicit CPU resource targets")
for target in targets.values():
    if set(target)!={"target_node","allocated_CPUs"} or target["target_node"] not in resume.CPU_RESUME_NODES or type(target["allocated_CPUs"]) is not int or target["allocated_CPUs"] not in {16,32}:
        raise ValueError("Only recorded demand-based eligible development CPU allocations")
registry=json.loads((b1/"reference_CPU_native_chain/job_4537810/reference_tabpfn_CPU_plan.json").read_text())
registry_by_job={int(r["new_native_job"]):r for r in registry["models"]}
def run(*args):
    return subprocess.run(args,text=True,capture_output=True,check=True,timeout=40).stdout.strip()
def reconcile_source_native(job,observed,accounting,prior):
    if observed.returncode==0:
        fields=h.native_fields(observed.stdout)
        if fields.get("JobId")!=str(job) or fields.get("UserId")!="zixiao(1278)" or fields.get("Restarts")!="0":
            raise ValueError("Current source native identity/owner/restart differs")
        return observed.stdout,"CURRENT_SCONTROL"
    if "Invalid job id" not in observed.stderr:raise ValueError("Current native source query failed without explicit purged-handle evidence")
    fields=resume.require_terminal_failure(prior,job)
    rows=[row.split("|") for row in accounting.splitlines() if row.split("|")[0]==str(job)]
    if (len(rows)!=1 or len(rows[0])<9 or rows[0][1:3]!=["zixiao","1278"] or rows[0][3]!=fields["JobState"]
        or rows[0][5]!=fields["RunTime"] or rows[0][6]!=fields["NodeList"]):
        raise ValueError("Fresh exact accounting must confirm the original observed owned failed source, duration and node")
    return prior,"OBSERVED_SCONTROL_FIELDS_20261121T181518Z_PLUS_CURRENT_SACCT"

original_timeout_native_fields={"4537812":"JobId=4537812 UserId=zixiao(1278) JobState=TIMEOUT Restarts=0 ExitCode=0:15 RunTime=12:00:12 NodeList=compute-0-10 StdOut=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_TabPFN_CPU_primary_4537812.log","4537813":"JobId=4537813 UserId=zixiao(1278) JobState=TIMEOUT Restarts=0 ExitCode=0:15 RunTime=12:00:12 NodeList=compute-0-8 StdOut=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_TabPFN_CPU_primary_4537813.log","4537814":"JobId=4537814 UserId=zixiao(1278) JobState=TIMEOUT Restarts=0 ExitCode=0:15 RunTime=12:00:12 NodeList=compute-0-8 StdOut=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_TabPFN_CPU_primary_4537814.log","4537817":"JobId=4537817 UserId=zixiao(1278) JobState=TIMEOUT Restarts=0 ExitCode=0:15 RunTime=12:00:12 NodeList=compute-0-8 StdOut=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_TabPFN_CPU_primary_4537817.log","4537818":"JobId=4537818 UserId=zixiao(1278) JobState=TIMEOUT Restarts=0 ExitCode=0:15 RunTime=12:00:12 NodeList=compute-0-8 StdOut=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_TabPFN_CPU_primary_4537818.log"}
current_accounting=run("ssh","-n","-oBatchMode=yes","-oConnectTimeout=10","sonmi","sacct -X -n -P -j 4537812,4537813,4537814,4537817,4537818 -o JobID,User,UID,State,ExitCode,Elapsed,NodeList,Start,End")
observation_origins={}
observations={};failed=[];successful=[]
for job in original_jobs:
    observed=subprocess.run(["scontrol","show","job",str(job),"-o"],text=True,capture_output=True,timeout=20)
    raw,origin=reconcile_source_native(job,observed,current_accounting,original_timeout_native_fields[str(job)])
    observation_origins[str(job)]=origin;fields=h.native_fields(raw)
    if fields.get("JobId")!=str(job) or fields.get("UserId")!="zixiao(1278)" or fields.get("Restarts")!="0":
        raise ValueError("Original native source identity/owner/restart changed")
    if fields.get("JobState")=="COMPLETED" and fields.get("ExitCode")=="0:0":successful.append(job)
    else:resume.require_terminal_failure(raw,job);failed.append(job)
    queue=subprocess.run(["squeue","-h","-j",str(job),"-o","%i|%T"],text=True,capture_output=True,timeout=20)
    if queue.stdout.strip() or (queue.returncode and "Invalid job id" not in queue.stderr):raise ValueError("Never continue a running/completing/queued or unobserved original source")
    observations[str(job)]=raw
if not failed:
    print("ALL_ORIGINAL_SOURCES_COMPLETED_NO_REPAIR_OR_REBINDING",flush=True);raise SystemExit(0)
for job in failed:
    row=registry_by_job[job]
    if row["feature_group"]!="Pprime" or row["dataset"] not in {"Joung2020","C7H10O2"}:
        raise ValueError("Only original frozen reference primary configurations")
    source=Path(row["captured_registered_program"])
    if source.stat().st_uid!=1278 or not source.resolve().is_relative_to(b1.resolve()):
        raise ValueError("Original registered model source ownership changed")
    if row["dataset"]=="Joung2020":
        tree=ast.parse(source.read_text())
        assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="registered_tasks" for t in n.targets)]
        if len(assignments)!=1:raise ValueError("Original frozen task selector is ambiguous")
        tasks=ast.literal_eval(assignments[0].value);selected=int(row["model_environment"]["BENCHMARK_TASK_INDEX"])
        derived=[tasks[selected]]
    else:
        binding=json.loads((b1/"C1_Pprime_reference_features/job_4537149/Pprime/C7H10O2_cv_binding.json").read_text())
        derived=sorted({name for spec in binding["source_groups"] if spec["dataset"]=="C7H10O2" for name in spec["endpoint_counts"]})
    if sorted(derived)!=sorted(frozen_tasks[str(job)]):raise ValueError("Original frozen input task roster changed")
    stdout=control/("C1_reference_TabPFN_CPU_primary_"+str(job)+".log")
    if h.native_fields(observations[str(job)]).get("StdOut")!=str(stdout) or stdout.stat().st_uid!=1278:
        raise ValueError("Actual original producer log ownership/path changed")
reports=(4537850,4537860,4537861)
def detail(job):
    raw=run("scontrol","show","job",str(job),"-o");fields=h.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0":
        raise ValueError("Only exact owned never-started report jobs may change")
    return fields
before={job:detail(job) for job in reports}
safe();out=b1/"reference_terminal_failed_CPU_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
ledger=dict(status="ORIGINAL_TERMINAL_FAILURES_CONFIRMED_PREPARING_HELD_CPU_CONTINUATIONS",
    job=os.environ["SLURM_JOB_ID"],node=socket.gethostname().split(".")[0],failed_original_sources=failed,successful_original_sources=successful,
    original_native_records=observations,original_native_record_origins=observation_origins,current_original_source_accounting=current_accounting,original_frozen_tasks=frozen_tasks,actual_CPU_targets=targets,
    mapping={},new_jobs=[],held_reports=[],cancelled_reports=[],released=[],source_groups=104,scientific_cells=561,
    benchmark_NFS_pool_bytes=40*1024**3,maximum_parallel_CPU_models=5,
    repair_attempt=1,source_models_cancelled=False,closed_folds_replayed=False,
    original_CUDA_templates_preserved_for_conditional_seed26=True,TDC_third_repair_submitted=False)
def write(name,text):
    safe();path=out/name;path.write_text(text,encoding="utf-8");return path
def save():
    write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save()
claim=control/"benchmark_reference_terminal_failed_resume_claim.json";safe()
with claim.open("x") as f:f.write(json.dumps(dict(controller_job=os.environ["SLURM_JOB_ID"],original_jobs=original_jobs,failed_sources=failed,targets=targets),indent=2)+"\n")
ledger["exclusive_own_source_claim"]=str(claim);save()
for job in reports:
    detail(job);run("scontrol","hold",str(job));ledger["held_reports"].append(job);save()
def submit(script,name,dependency="",source=None):
    subprocess.run(["bash","-n"],input=script,text=True,capture_output=True,check=True)
    ast.parse(script.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0])
    path=write(name,script)
    exports="ALL,BENCHMARK_SOURCE_CACHE="+str(out/"proposed_sources.json")
    args=["sbatch","--parsable","--hold"]
    if source is not None:
        target=targets[str(source)]
        args+=["--nodelist="+target["target_node"],"--cpus-per-task="+str(target["allocated_CPUs"])]
        exports+=",BENCHMARK_REFERENCE_RESUME_PLAN="+str(out/("resume_"+str(source)+".json"))
    else:args+=["--exclude=compute-0-[0-7,14,18,20-22]"]
    args+=["--export="+exports]
    if dependency:args+=["--dependency="+dependency]
    value=run(*(args+[str(path)]))
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",value):raise ValueError("An exact actual held native identity is required")
    job=int(value.split(";")[0]);ledger["new_jobs"].append(dict(job=job,script=str(path),dependency=dependency,original_terminal_failed_CPU_source=source));save();return job
mapping={};plans={};previous=None
# Ordering uses only declared task workload, never baseline/model results.
for old in (4537818,4537813,4537817,4537814,4537812):
    if old not in failed:continue
    original=registry_by_job[old]
    new=submit(sources["workflows/benchmark_evaluation/reference_terminal_failure_CPU_resume.sbatch"],
        "reference_CPU_resume_"+str(old)+".sbatch","",old)
    target=targets[str(old)]
    plan=dict(schema=resume.CPU_RESUME_SCHEMA,source_job=old,new_native_job=new,repair_attempt=1,
        dataset=original["dataset"],feature_group=original["feature_group"],model_seed=20261025,
        benchmark_NFS_pool_bytes=40*1024**3,maximum_parallel_CPU_models=5,
        source_native_record=observations[str(old)],frozen_task_names=frozen_tasks[str(old)],
        model_environment=original["model_environment"],captured_registered_program=original["captured_registered_program"],
        prepared_CPU_program=original["prepared_CPU_program"],**target)
    resume.validate_cpu_resume_plan(plan,new,actual_node=target["target_node"],allocated_cpus=target["allocated_CPUs"])
    write("resume_"+str(old)+".json",json.dumps(plan,indent=2)+"\n")
    mapping[old]=new;plans[old]=plan;ledger["mapping"][str(old)]=new;previous=new;save()
old_specs=json.loads(sources["workflows/benchmark_evaluation/c1_producer_bindings.json"])
updated=copy.deepcopy(old_specs)
if len(old_specs)!=104 or len({(r["dataset"],r["feature_group"],r["learner"],r["job"]) for r in old_specs})!=104:
    raise ValueError("The original104 unique C1 source groups are mandatory")
for old,new in mapping.items():
    rows=[row for row in updated if int(row["job"])==old]
    if len(rows)!=1:raise ValueError("Each actual failed CPU primary must occur exactly once")
    row=rows[0];original=registry_by_job[old]
    if (row["dataset"],row["feature_group"],row["learner"],row["folder"],row.get("primary_execution_backend"))!=(
        original["dataset"],"Pprime","TabPFN","reference_cv_models/job_"+str(old),"CPU"):
        raise ValueError("Failed source is not the exact original selected CPU primary")
    target=targets[str(old)]
    row.update(job=new,folder="reference_cv_models/job_"+str(new),primary_execution_backend="CPU",
        actual_terminal_failed_CPU_source=old,actual_primary_CPU_node=target["target_node"],
        actual_native_CPUs=target["allocated_CPUs"],closed_fold_continuation=True,
        original_closed_fold_CPU_origins_preserved_in_resume_manifest=True)
if [(r["dataset"],r["feature_group"],r["learner"]) for r in updated]!=[(r["dataset"],r["feature_group"],r["learner"]) for r in old_specs]:
    raise ValueError("No C1 source configuration may be dropped/reordered/reselected")
if any(a!=b for a,b in zip(old_specs,updated) if int(a["job"]) not in mapping):
    raise ValueError("Unselected completed source binding changed")
if len({int(r["job"]) for r in updated})!=len({int(r["job"]) for r in old_specs}):
    raise ValueError("Duplicate new native source identity")
sources["workflows/benchmark_evaluation/c1_producer_bindings.json"]=json.dumps(updated,indent=2)+"\n"
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]);changed=[]
for model in index["GPU_downstream_neural"]["models"]:
    old=int(model["job"])
    if old not in mapping:continue
    original=registry_by_job[old]
    if ast.dump(ast.parse(Path(model["program"]).read_text()))!=ast.dump(ast.parse(Path(original["captured_registered_program"]).read_text())):raise ValueError("Original CUDA seed26 template scientific AST must remain exact")
    target=targets[str(old)]
    model.update(job=mapping[old],primary_execution_backend="CPU",actual_terminal_failed_CPU_source=old,
        actual_primary_CPU_node=target["target_node"],actual_native_CPUs=target["allocated_CPUs"],
        actual_primary_script=str(out/("reference_CPU_resume_"+str(old)+".sbatch")),
        actual_primary_resume_plan=str(out/("resume_"+str(old)+".json")),
        future_confirmation_GPU_template_preserved=True,closed_fold_continuation=True)
    changed.append(old)
if set(changed)!=set(mapping):raise ValueError("Every new primary must retain its original future CUDA confirmation template")
# Keep the original native report body; replace only its one source-binding literal.
primary_source=b1/"reference_idle_GPU7_handover/job_4537843/c1_primary_comparisons.sbatch"
primary=h.replace_primary_specs(primary_source.read_text(),updated)
dependency="afterok:"+":".join(str(v) for v in mapping.values())
primary_job=submit(primary,"c1_primary_comparisons.sbatch",dependency)
def unwrap(text,tag):
    if text.startswith("#!"):return text
    lines=text.splitlines()
    if not lines[0].startswith("sbatch ") or lines[-1]!=tag:raise ValueError("Original native wrapper format changed")
    raw="\n".join(lines[1:-1])+"\n"
    if not raw.startswith("#!"):raise ValueError("Preserve original raw native script")
    return raw
prep=unwrap(sources["workflows/benchmark_evaluation/c1_conditional_sources_prepare.sbatch"],"COND_C1_PREP")
prep,count=re.subn(r"(?m)^export BENCHMARK_SOURCE_CACHE=.*$","export BENCHMARK_SOURCE_CACHE="+str(out/"proposed_sources.json"),prep)
if count!=1:raise ValueError("Exactly one original preparation cache required")
prep_job=submit(prep,"c1_conditional_sources_prepare.sbatch","afterok:"+str(primary_job))
dispatch=sources["workflows/benchmark_evaluation/c1_conditional_chain_dispatch.sbatch"]
token="conditional_preparation/C1/job_4537860/manifest.json"
if dispatch.count(token)!=1:raise ValueError("Current active-allocation-gated conditional preparation identity changed")
dispatch=dispatch.replace(token,"conditional_preparation/C1/job_"+str(prep_job)+"/manifest.json")
dispatch_job=submit(dispatch,"c1_conditional_chain_dispatch.sbatch","afterok:"+str(prep_job))
sources["workflows/benchmark_evaluation/c1_primary_comparisons.sbatch"]="sbatch --parsable --dependency="+dependency+" <<'C1PRIMARYREPORT'\n"+primary+"\nC1PRIMARYREPORT\n"
sources["workflows/benchmark_evaluation/c1_conditional_sources_prepare.sbatch"]="sbatch --parsable --dependency=afterok:"+str(primary_job)+" <<'COND_C1_PREP'\n"+prep+"\nCOND_C1_PREP\n"
sources["workflows/benchmark_evaluation/c1_conditional_chain_dispatch.sbatch"]=dispatch
ledger.update(status="ACTUAL_HELD_CPU_AND_REPORT_IDENTITIES_RECORDED",primary_job=primary_job,conditional_preparation_job=prep_job,
    conditional_controller_job=dispatch_job,source_cache=str(out/"proposed_sources.json"))
index["C1_reference_terminal_failed_CPU_continuation_20261122"]=copy.deepcopy(ledger)
for key,job in (("C1_primary_consumer",primary_job),("C1_conditional_automatic_chain",dispatch_job)):
    index[key]=dict(previous_pending_definition=index.get(key),current_job=job,source_cache=str(out/"proposed_sources.json"))
index["C1_conditional_automatic_chain"]["preparation_job"]=prep_job
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
write("proposed_sources.json",json.dumps(sources,ensure_ascii=False,indent=2)+"\n");save()
paths=sorted({str(path.relative_to(base)) for path in base.rglob("*") if path.is_file()}|set(sources))
safe();view=out/"source_view";view.mkdir()
for number,name in enumerate(paths):
    if number%128==0:safe()
    destination=view/name;destination.parent.mkdir(parents=True,exist_ok=True)
    if name in sources:destination.write_text(sources[name],encoding="utf-8")
    else:os.link(base/name,destination)
check_module=types.ModuleType("source_check");check_module.__file__=str(view/"tools/check_repository.py")
exec(compile(sources["tools/check_repository.py"],check_module.__file__,"exec"),check_module.__dict__)
check=check_module.check(view,paths,verify_export=False);write("source_check.json",json.dumps(check,indent=2)+"\n")
if check["status"]!="PASS":raise ValueError("Full recorded C1 source tree must pass before any activation")
ledger["source_check"]=check;save()
for old in reports:
    detail(old);run("scancel",str(old));ledger["cancelled_reports"].append(old);save()
for item in ledger["new_jobs"]:
    job=item["job"]
    if detail(job).get("Reason")!="JobHeldUser":raise ValueError("Only fully recorded owned held jobs may be released")
    run("scontrol","release",str(job));ledger["released"].append(job);save()
ledger["status"]="ORIGINAL_TERMINAL_FAILED_REFERENCE_CPU_CONTINUATIONS_AND_COMPLETE_C1_CHAIN_RELEASED";save()
print(json.dumps({k:ledger[k] for k in ("status","job","failed_original_sources","successful_original_sources","mapping","primary_job","conditional_preparation_job","conditional_controller_job","source_cache","source_check","cancelled_reports","released","actual_CPU_targets")}),flush=True)
