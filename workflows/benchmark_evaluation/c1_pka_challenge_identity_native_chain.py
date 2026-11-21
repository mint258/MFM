import ast,copy,json,os,re,subprocess,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119");b1=root.parent/"benchmark_B1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():
    for local in (Path("/"),Path("/tmp")):
        st=os.statvfs(local)
        if st.f_bavail*st.f_frsize<max(10*1024**3,st.f_blocks*st.f_frsize//10)+64*1024**2 or st.f_favail<2000:raise RuntimeError("Actual root/tmp reserve insufficient")
    protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
base=b1/"C1_pKa_challenge_identity_preparation/job_4538206"
prepared=json.loads((base/"manifest.json").read_text())
if prepared.get("tests")!=274 or prepared.get("source_check",{}).get("status")!="PASS":raise ValueError("Closed274-test pKa report preparation required")
identity=prepared.get("actual_six_identity_bindings",{})
bindings=identity.get("actual_identity_bindings",[])
if (prepared.get("status")!="C1_PKA_CHALLENGE_IDENTITY_PREPARED_NOT_ACTIVATED" or len(bindings)!=6
    or {int(row["source_job"]) for row in bindings}!={4536951,4537133,4537145}
    or any(row.get("outside_original_ids_after_binding")!=0 or not row.get("original_record_ID_and_challenge_fields_unchanged") for row in bindings)
    or identity.get("prediction_label_TRAIN_mean_or_metric_columns_read") is not False):
    raise ValueError("All six exact IDs-only actual error interfaces must be validated before the second report repair")
sources=json.loads((base/"proposed_sources.json").read_text());original=copy.deepcopy(sources)
helper=types.ModuleType("infrastructure")
exec(compile(sources["workflows/benchmark_evaluation/infrastructure_handover.py"],helper.__name__,"exec"),helper.__dict__)
def command(*args):return subprocess.run(args,text=True,capture_output=True,check=True,timeout=60).stdout.strip()
def pending(job):
    raw=command("scontrol","show","job",str(job),"-o");fields=helper.require_owned_pending(raw)
    if fields.get("JobId")!=str(job) or fields.get("Restarts")!="0":raise ValueError("Exact owned never-started metadata identity required")
    return raw,fields
def accounting(ids):
    value=command("ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10","sonmi","sacct","-n","-X","-j",",".join(map(str,ids)),"--format=JobID,User,UID,State,ExitCode,Elapsed,NodeList","--parsable2")
    rows={}
    for line in value.splitlines():
        fields=line.strip().split("|")
        if len(fields)<7 or not fields[0].isdigit():continue
        job=int(fields[0])
        if job in rows:raise ValueError("Duplicate actual accounting identity")
        rows[job]=fields[:7]
    if set(rows)!=set(ids):raise ValueError("Missing or additional native accounting rows")
    if any(row[1]!="zixiao" or row[2]!="1278" for row in rows.values()):raise ValueError("Actual native owner differs")
    return value,rows
models=[4538159,4538160,4538161,4538162,4538163]
raw_accounting,rows=accounting(models+[4538196,4538206])
for job in models+[4538206]:
    if rows[job][3:5]!=["COMPLETED","0:0"]:raise ValueError("Existing primary models and preparation must be successful")
if rows[4538196][3:5]!=["FAILED","1:0"] or rows[4538196][5]!="00:04:22":raise ValueError("Exact failed report identity required")
def require_absent_failed_report(code,stdout,stderr):
    if stdout.strip():raise ValueError("Failed report is active or requeued")
    if code==0 and not stderr.strip():return
    if code==1 and stderr.strip()=="slurm_load_jobs error: Invalid job id specified":return
    raise ValueError("Cannot establish failed-report absence from an unrelated queue/query error")
queue_fixtures=[(0,"","",True),(1,"","slurm_load_jobs error: Invalid job id specified\n",True),
    (0,"4538196|RUNNING\n","",False),(1,"","Connection refused",False),
    (1,"4538196|RUNNING\n","slurm_load_jobs error: Invalid job id specified",False),
    (1,"","other Invalid job id specified",False)]
for code,stdout,stderr,accepted in queue_fixtures:
    try:require_absent_failed_report(code,stdout,stderr);actual=True
    except ValueError:actual=False
    if actual!=accepted:raise ValueError("Purged queue transport fixture failed")
queue_result=subprocess.run(["squeue","-h","-j","4538196","-o","%i|%T"],text=True,capture_output=True,timeout=30)
require_absent_failed_report(queue_result.returncode,queue_result.stdout,queue_result.stderr)
failed_out=b1/"C1_primary_comparisons/job_4538196"
if not failed_out.is_dir() or list(failed_out.iterdir()):raise ValueError("Failed binding report must not have published result/statistic files")
old_jobs=[4538197,4538198];old_records={}
for job,dependency in ((4538197,"afterok:4538196"),(4538198,"afterok:4538197")):
    raw,fields=pending(job)
    if helper.clean_dependency(fields.get("Dependency"))!=dependency or fields.get("Reason")=="JobHeldUser":raise ValueError("Unexpected original dependency or user hold")
    old_records[str(job)]=raw
out=b1/"C1_pKa_challenge_identity_native_chain"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
def write(name,value):
    safe();path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8");return path
write("native_controller.py",__controller_source__)
ledger=dict(status="PREPARING_SECOND_FAILED_REPORT_IDENTITY_RECOVERY",job=os.environ["SLURM_JOB_ID"],
    failed_primary_report=4538196,old_zero_start_metadata=old_records,native_accounting=raw_accounting,
    primary_models_unchanged=models,all_primary_models_successful=True,source_groups=104,primary_configurations=561,
    native_source_predictions_labels_TASKs_masks_seeds_and_fit_code_unchanged=True,
    failed_report_no_closed_statistics=True,report_repair_attempt=2,preparation_job=4538206,tests=274,
    previous_pre_activation_metadata_transport_failure=4538194,preparation_iterator_failure=4538203,purged_queue_transport_fixture_groups=6,
    old_failed_report_queue_observation=dict(returncode=queue_result.returncode,stdout=queue_result.stdout,stderr=queue_result.stderr),
    benchmark_NFS_pool_bytes=40*1024**3,new_native_jobs=[])
def save():write("manifest.json",json.dumps(ledger,indent=2)+"\n")
save()
for job in old_jobs:pending(job);command("scontrol","hold",str(job))
cache=out/"proposed_sources.json"
def unwrap(raw,tag):
    prefix=raw.split("\n",1)[0]
    if not prefix.startswith("sbatch --parsable ") or "<<'"+tag+"'" not in prefix:raise ValueError("Registered submission wrapper required")
    script=raw.split("\n",1)[1].rsplit("\n"+tag,1)[0]
    if not script.startswith("#!/bin/bash"):raise ValueError("Native executable header required")
    return script
def submit_held(name,raw,dependency):
    subprocess.run(["bash","-n"],input=raw,text=True,capture_output=True,check=True)
    ast.parse(raw.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0])
    path=write(name,raw)
    value=command("sbatch","--parsable","--hold","--dependency="+dependency,"--export=ALL,BENCHMARK_SOURCE_CACHE="+str(cache),str(path))
    if not re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_-]+)?",value):raise ValueError("Actual held native ID required")
    job=int(value.split(";")[0]);ledger["new_native_jobs"].append(dict(job=job,script=str(path),dependency=dependency));save();return job
primary_name="workflows/benchmark_evaluation/c1_primary_comparisons.sbatch"
primary=unwrap(sources[primary_name],"C1PRIMARYREPORT")
new_primary=submit_held("c1_primary_comparisons.sbatch",primary,"afterok:"+os.environ["SLURM_JOB_ID"])
old_prefix=sources[primary_name].split("\n",1)[0]
sources[primary_name]=sources[primary_name].replace(old_prefix,"sbatch --parsable --dependency=afterok:"+os.environ["SLURM_JOB_ID"]+" <<'C1PRIMARYREPORT'",1)
prep_name="workflows/benchmark_evaluation/c1_conditional_sources_prepare.sbatch"
prep=sources[prep_name]
old_prep_prefix=prep.split("\n",1)[0]
prep=prep.replace(old_prep_prefix,"sbatch --parsable --dependency=afterok:"+str(new_primary)+" <<'COND_C1_PREP'",1)
prep,count=re.subn(r"(?m)^export BENCHMARK_SOURCE_CACHE=.*$","export BENCHMARK_SOURCE_CACHE="+str(cache),prep)
if count!=1:raise ValueError("Exactly one source cache binding required")
sources[prep_name]=prep
new_prep=submit_held("c1_conditional_sources_prepare.sbatch",unwrap(prep,"COND_C1_PREP"),"afterok:"+str(new_primary))
dispatch_name="workflows/benchmark_evaluation/c1_conditional_chain_dispatch.sbatch"
dispatch=sources[dispatch_name];old_path='preparation_path=b1/"conditional_preparation/C1/job_4538197/manifest.json"'
if dispatch.count(old_path)!=1:raise ValueError("Exact prior preparation binding required")
dispatch=dispatch.replace(old_path,'preparation_path=b1/"conditional_preparation/C1/job_'+str(new_prep)+'/manifest.json"',1)
if dispatch.replace('preparation_path=b1/"conditional_preparation/C1/job_'+str(new_prep)+'/manifest.json"',old_path,1)!=original[dispatch_name]:raise ValueError("GPU protection or dispatch logic changed")
sources[dispatch_name]=dispatch
new_dispatch=submit_held("c1_conditional_chain_dispatch.sbatch",dispatch,"afterok:"+str(new_prep))
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
if index["C1_primary_consumer"].get("current_job")!=4538196 or index["C1_conditional_automatic_chain"].get("current_job")!=4538198 or index["C1_conditional_automatic_chain"].get("preparation_job")!=4538197:raise ValueError("Current registered metadata chain differs")
before_GPU=copy.deepcopy(index["GPU_downstream_neural"])
index["C1_primary_consumer"]=dict(previous_failed_definition=index["C1_primary_consumer"],current_job=new_primary,source_cache=str(cache),failed_report=4538196,report_repair_attempt=2,model_jobs_unchanged=True)
index["C1_conditional_automatic_chain"]=dict(previous_pending_definition=index["C1_conditional_automatic_chain"],current_job=new_dispatch,preparation_job=new_prep,primary_report=new_primary,source_cache=str(cache),final_export_pretraining_overlap_status_explicit=True)
ledger.update(primary_job=new_primary,conditional_preparation_job=new_prep,controller_job=new_dispatch,source_cache=str(cache))
index["C1_pKa_challenge_identity_recovery_20261122"]=dict(ledger)
if index["GPU_downstream_neural"]!=before_GPU:raise ValueError("GPU model/confirmation templates changed")
sources["workflows/benchmark_evaluation/native_jobs_20261120.json"]=json.dumps(index,indent=2)+"\n"
sources["workflows/benchmark_evaluation/c1_pka_challenge_identity_native_chain.py"]=__controller_source__
if sources["workflows/benchmark_evaluation/c1_producer_bindings.json"]!=original["workflows/benchmark_evaluation/c1_producer_bindings.json"]:raise ValueError("104primarysourcebindingschanged")
write("proposed_sources.json",json.dumps(sources,ensure_ascii=False,indent=2)+"\n")
view=out/"source_view";safe();view.mkdir()
base_view=base/"source_view"
paths=sorted({str(p.relative_to(base_view)) for p in base_view.rglob("*") if p.is_file()}|set(sources))
for number,name in enumerate(paths):
    if number%128==0:safe()
    target=view/name;target.parent.mkdir(parents=True,exist_ok=True)
    if name in sources:target.write_text(sources[name],encoding="utf-8")
    else:os.link(base_view/name,target)
checker=types.ModuleType("source_check");checker.__file__=str(view/"tools/check_repository.py")
exec(compile(sources["tools/check_repository.py"],checker.__file__,"exec"),checker.__dict__)
check=checker.check(view,paths,verify_export=False);write("source_check.json",json.dumps(check,indent=2)+"\n")
if check["status"]!="PASS":raise ValueError("Complete recorded source tree must pass before activation")
ledger["source_check"]=check;save()
for job in old_jobs:pending(job)
for job in old_jobs:command("scancel",str(job));ledger.setdefault("cancelled_owned_zero_start_metadata",[]).append(job);save()
for job in (new_primary,new_prep,new_dispatch):
    _,fields=pending(job)
    if fields.get("Reason")!="JobHeldUser":raise ValueError("Only recorded new held metadata job may be released")
for job in (new_primary,new_prep,new_dispatch):command("scontrol","release",str(job));ledger.setdefault("released",[]).append(job);save()
ledger["status"]="FAILED_PKA_CHALLENGE_IDENTITY_REPAIRED_FULL104SOURCE_CHAIN_RECORDED_AND_RELEASED";save()
print(json.dumps(ledger),flush=True)
