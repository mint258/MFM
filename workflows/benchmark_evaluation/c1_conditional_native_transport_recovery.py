import copy,json,os,re,subprocess,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():
    for path in (Path("/"),Path("/tmp")):
        st=os.statvfs(path)
        if st.f_bavail*st.f_frsize<max(10*1024**3,st.f_blocks*st.f_frsize//10)+64*1024**2 or st.f_favail<2000:raise RuntimeError("Actual root/tmp reserve insufficient")
    protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
if os.getuid()!=1278:raise ValueError("Exact native owner required")
base=b1/"C1_native_transport_preparation/job_4538212";prepared=json.loads((base/"manifest.json").read_text())
if prepared.get("status")!="C1_NATIVE_TRANSPORT_PREPARED_NOT_ACTIVATED" or prepared.get("tests")!=281 or prepared.get("source_check",{}).get("status")!="PASS":raise ValueError("Closed281-test transport preparation required")
sources=json.loads((base/"proposed_sources.json").read_text());original=copy.deepcopy(sources)
transport=types.ModuleType("native_slurm_transport")
exec(compile(sources["workflows/benchmark_evaluation/native_slurm_transport.py"],transport.__name__,"exec"),transport.__dict__)
native=transport.native_control(["sacct","-n","-X","-j","4538208,4538209,4538210,4538212","--format=JobID,User,State,ExitCode,Elapsed,NodeList","--parsable2"])
records={int(fields[0]):fields for line in native.splitlines() if len(fields:=line.strip().split("|"))>=6 and fields[0].isdigit()}
if set(records)!={4538208,4538209,4538210,4538212}:raise ValueError("Exact native accounting identities required")
for job in (4538208,4538209,4538212):
    if records[job][1:4]!=["zixiao","COMPLETED","0:0"]:raise ValueError("Closed primary/preparation and transport tests must remain successful")
if records[4538210][1:5]!=["zixiao","FAILED","1:0","00:00:01"]:raise ValueError("Exact failed prewire dispatcher required")
queue=subprocess.run(["squeue","-h","-j","4538210","-o","%i|%T"],text=True,capture_output=True,timeout=30)
if queue.stdout.strip() or not((queue.returncode==0 and not queue.stderr.strip()) or (queue.returncode==1 and queue.stderr.strip()=="slurm_load_jobs error: Invalid job id specified")):raise ValueError("Cannot establish failed dispatcher absence")
failed=b1/"conditional_dispatch/C1/job_4538210"
if not failed.is_dir() or {p.name for p in failed.iterdir()}!={"protected_gpu_queues.json"}:raise ValueError("Do not rerun a dispatcher with any native submission records")
primary_path=b1/"C1_primary_comparisons/job_4538208/manifest.json"
prep_path=b1/"conditional_preparation/C1/job_4538209/manifest.json"
primary=json.loads(primary_path.read_text());prep=json.loads(prep_path.read_text())
if primary.get("reported_configuration_rows")!=561 or primary.get("required_TabPFN_confirmation_configurations")!=175:raise ValueError("Full primary normal report required")
if prep.get("required_configuration_rows")!=175 or len(prep.get("prepared_native_groups",[]))!=43 or prep.get("failures"):raise ValueError("Keep the one existing successful preparation")
config=subprocess.check_output(["scontrol","show","config"],text=True,timeout=30)
if not re.search(r"(?m)^ClusterName\s*=\s*sonmi\s*$",config) or not re.search(r"(?m)^SlurmctldHost\[0\]\s*=\s*sonmi\s*$",config):raise ValueError("Actual local native controller must be the same established sonmi cluster")
out=b1/"C1_native_transport_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
def write(name,value):
    safe();path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
write("native_controller.py",__controller_source__)
ledger=dict(status="PREPARING_FAILED_PREWIRE_DISPATCH_ONLY_RECOVERY",job=os.environ["SLURM_JOB_ID"],failed_dispatcher=4538210,
    source_preparation=4538212,tests=281,native_accounting=native,primary_unchanged=4538208,preparation_unchanged=4538209,
    primary_configurations=561,required_confirmation_configs=175,prepared_groups=43,old_dispatcher_submitted_any_job=False,
    normal_primary_result_states=primary.get("result_states"),model_group_code_seeds_masks_folds_population_and_GPU_protections_unchanged=True,
    local_native_cluster="sonmi",only_readonly_refused_accounting_bounded_retry=True,submission_and_release_never_retried=True,
    benchmark_NFS_pool_bytes=40*1024**3,dispatch_transport_repair_attempt=1)
def save():write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save();raw=sources["workflows/benchmark_evaluation/c1_conditional_chain_dispatch.sbatch"]
if raw.count("#SBATCH --nodelist=compute-0-13")!=1:raise ValueError("Actual metadata recovery must run on verified CPU13")
subprocess.run(["bash","-n"],input=raw,text=True,capture_output=True,check=True)
script=write("c1_conditional_chain_dispatch.sbatch",raw);cache=out/"proposed_sources.json"
value=transport.native_control(["sbatch","--parsable","--hold","--dependency=afterok:"+os.environ["SLURM_JOB_ID"],"--export=ALL,BENCHMARK_SOURCE_CACHE="+str(cache),str(script)])
if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",value):raise ValueError("One actual held native dispatcher ID required")
new=int(value.split(";")[0]);ledger.update(new_dispatcher=new,source_cache=str(cache));save()
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
previous=index["C1_conditional_automatic_chain"]
if previous.get("current_job")!=4538210 or previous.get("preparation_job")!=4538209 or index["C1_primary_consumer"].get("current_job")!=4538208:raise ValueError("Current recorded full chain differs")
index["C1_conditional_automatic_chain"]=dict(previous_failed_definition=previous,current_job=new,preparation_job=4538209,primary_report=4538208,
    source_cache=str(cache),metadata_node="compute-0-13",native_local_submission=True,final_export_pretraining_overlap_status_explicit=True)
index["C1_native_control_transport_recovery_20261122"]=dict(ledger)
index["C1_closed_primary_statistics_20261122"]=dict(job=4538208,manifest=str(primary_path),reported_configuration_rows=561,
    required_TabPFN_confirmation_configurations=175,result_states=primary.get("result_states"),native_state="COMPLETED",exit_code="0:0",elapsed="00:03:41",
    normal_new_statistics=True,independent_numeric_QA=False,confirmation_preparation_job=4538209,prepared_groups=43)
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
sources["workflows/benchmark_evaluation/c1_conditional_native_transport_recovery.py"]=__controller_source__
for name in ("workflows/benchmark_evaluation/c1_producer_bindings.json","workflows/benchmark_evaluation/c1_primary_comparisons.sbatch","workflows/benchmark_evaluation/c1_conditional_sources_prepare.sbatch"):
    if sources[name]!=original[name]:raise ValueError("Closed primary/preparation/model binding changed")
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
if check["status"]!="PASS":raise ValueError("Recorded complete source tree must pass before release")
ledger["source_check"]=check;save()
h=types.ModuleType("infrastructure");exec(compile(sources["workflows/benchmark_evaluation/infrastructure_handover.py"],h.__name__,"exec"),h.__dict__)
info=subprocess.check_output(["scontrol","show","job",str(new),"-o"],text=True,timeout=30);fields=h.require_owned_pending(info)
if fields.get("JobId")!=str(new) or fields.get("Restarts")!="0" or fields.get("Reason")!="JobHeldUser":raise ValueError("Only the exact newly recorded owned zero-start dispatcher may be released")
transport.native_control(["scontrol","release",str(new)])
ledger["status"]="FAILED_PREWIRE_DISPATCH_RECOVERED_NATIVE_LOCAL_CONTROLLER_RECORDED_AND_RELEASED";save()
print(json.dumps(ledger),flush=True)
