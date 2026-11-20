sbatch --parsable --dependency=afterok:4537386 <<'COND_B1_PREP'
#!/bin/bash
#SBATCH --job-name=B1-conditional-neural-source-prep
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:10:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_conditional_prepare_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
export BENCHMARK_SOURCE_CACHE=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/source_check/job_4537323_step_3/proposed_sources.json
export BENCHMARK_CONFIRMATION_STAGE=B1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import ast,csv,json,os,shlex,socket,sys,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
cache=Path(os.environ["BENCHMARK_SOURCE_CACHE"])
sources=json.loads(cache.read_text())
entry=json.loads(sources["configs/benchmark_data/B0.DELIVERY.json"])
root=Path(entry["data_root"]);b1=root.parent/"benchmark_B1_20261119"
quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
def safe():protect(root,16*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
stage=os.environ["BENCHMARK_CONFIRMATION_STAGE"]
if stage not in ("B1","C1"):raise ValueError("Registered confirmation stage required")
package=types.ModuleType("workflows.benchmark_evaluation");package.__path__=[]
sys.modules[package.__name__]=package
for name in ("selection","confirmation","gpu_runtime","confirmation_dispatch"):
    module=types.ModuleType(package.__name__+"."+name);module.__package__=package.__name__
    sys.modules[module.__name__]=module
    exec(compile(sources["workflows/benchmark_evaluation/"+name+".py"],module.__name__,"exec"),module.__dict__)
from workflows.benchmark_evaluation.confirmation_dispatch import planned_jobs,prepare_job_source
from workflows.benchmark_evaluation.selection import IncompleteComparison
def one(pattern):
    paths=list(b1.glob(pattern))
    if len(paths)!=1:raise IncompleteComparison("One closed source required: "+pattern)
    return paths[0]
def rows(path):
    with path.open(newline="") as stream:return list(csv.DictReader(stream))
screen_path=one("B1_task_screen/job_*/B1_task_screen.csv")
screen_manifest=json.loads((screen_path.parent/"manifest.json").read_text())
if screen_manifest.get("status")!="FINAL_B1_SINGLE_SCREEN_CLOSED" or screen_manifest["active_endpoints"]!=96:
    raise IncompleteComparison("The registered B1 screen has not closed")
roster={r["endpoint_key"]:r for r in rows(screen_path)}
primary_manifest=None
if stage=="B1":
    plan=rows(screen_path.parent/"B1_Chemprop_seed2_plan.csv")
else:
    primary_manifest=one("C1_primary_comparisons/job_*/manifest.json")
    primary=json.loads(primary_manifest.read_text())
    if primary.get("status")!="C1_PRIMARY_STATISTICS_CLOSED_CONDITIONAL_CONFIRMATION_REQUIRED":
        raise IncompleteComparison("The C1 primary comparison has not closed")
    plan=rows(primary_manifest.parent/"C1_TabPFN_seed2_plan.csv")
index=json.loads(sources["workflows/benchmark_evaluation/native_jobs_20261120.json"])
c1_specs=json.loads(sources["workflows/benchmark_evaluation/c1_producer_bindings.json"])
b1_specs=json.loads(sources["workflows/benchmark_evaluation/b1_producer_bindings.json"])
c1_by_job={str(s["job"]):s for s in c1_specs}
b1_by_job={str(s["job"]):s for s in b1_specs}
templates={}
def gpu_dataset(name):
    for prefix,dataset in (("Bio","Biogen_ADME"),("pKa","pKahub"),("Expansion","ExpansionRx"),
                           ("C7","C7H10O2"),("PPE","PPE1694"),("NMR","NMRShiftDB2"),("Joung","Joung2020")):
        if name.startswith(prefix):return dataset
    raise IncompleteComparison("No registered original GPU dataset for "+name)
for model in index["GPU_downstream_neural"]["models"]:
    job=str(model["job"])
    if int(model.get("model_seed",20261025))!=20261025:continue
    if model["learner"]=="Chemprop-v2" and job not in b1_by_job:continue
    if model["learner"]=="TabPFN" and job not in c1_by_job:continue
    if model["learner"]=="TabPFN":
        spec=c1_by_job[job];dataset=spec["dataset"];feature=spec["feature_group"]
    else:
        dataset=gpu_dataset(model["name"]);feature=None;spec=b1_by_job[job]
    templates[job]=dict(model,primary_job=job,template_id="native_"+job,default_dataset=dataset,
        feature_group=feature,original_folder=spec.get("folder"),original_array=bool(spec.get("array")))
base_prefix=b1/"environments/gpu_cu118_job_4536985_step_24"
original_cpu=(
    (4536913,"Chemprop-v2","MoleculeACE",None,"b1_chemprop_official.sbatch"),
    (4536954,"Chemprop-v2","TDC_ADMET",None,"b1_chemprop_tdc_asap.sbatch"),
    (4536899,"TabPFN","MoleculeACE","D","c1_d_tabpfn_moleculeace.sbatch"),
    (4536921,"TabPFN","PharmaBench","D","c1_d_tabpfn_pharmabench.sbatch"),
    (4536980,"TabPFN","TDC_ADMET","D","c1_d_tabpfn_tdc_asap.sbatch"),
    (4537010,"TabPFN","Biogen_ADME","D","c1_d_tabpfn_biogen.sbatch"),
    (4537011,"TabPFN","pKahub","D","c1_d_tabpfn_pka.sbatch"),
    (4537081,"TabPFN","ExpansionRx","D","c1_d_expansion_tabpfn.sbatch"))
for job,learner,dataset,feature,filename in original_cpu:
    spec=(b1_by_job if learner=="Chemprop-v2" else c1_by_job)[str(job)]
    templates[str(job)]=dict(primary_job=str(job),learner=learner,feature_group=feature,
        template_id="native_"+str(job),default_dataset=dataset,source_file=filename,
        node="compute-0-5",uuid="GPU-dac07d74-6269-c7db-8832-340dd3c0b377",
        python=str(base_prefix/("chemprop" if learner=="Chemprop-v2" else "tabpfn")/"bin/python"),
        original_folder=spec["folder"],original_array=False,exports=[])
bindings=[]
for row in plan:
    key=row["endpoint_key"];role=roster[key]["decision"]
    if row["reason"]=="FINAL_SIGNIFICANT_IMPROVEMENT":
        if role not in ("RETAIN","APPENDIX"):raise IncompleteComparison("A nonfinal role cannot acquire a confirmation fit")
    elif row["reason"]!="SOURCE_BINDING_ERROR_REQUIRED_REDO_OF_TRAINED_1H_SAMPLES":
        raise IncompleteComparison("Unregistered confirmation reason")
    if row.get("confirmation_native_job") not in (None,""):continue
    job=str(row["primary_source_job"]);template=templates[job]
    learner=row["model"] if stage=="B1" else row["learner"]
    feature=None if stage=="B1" else row["feature_group"]
    if template["learner"]!=learner or template["feature_group"]!=feature:
        raise IncompleteComparison("Original native configuration differs from the required neural plan")
    bindings.append(dict(dataset=row["dataset"],producer_task=row["producer_task"],learner=learner,
        feature_group=feature,primary_job=job,template_id=template["template_id"]))
groups,reused=planned_jobs(plan,bindings,baseline=stage=="B1")
out=b1/"conditional_preparation"/stage/("job_"+os.environ["SLURM_JOB_ID"])
safe();out.mkdir(parents=True,exist_ok=False)
runtime_source=sources["workflows/benchmark_evaluation/gpu_runtime.py"]
repo="/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119"
pythonpath=repo+":"+str(root/"runtime_deps")+":/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
def render_gpu(template,program_path,number,environment):
    learner=template["learner"];cpus=4 if learner=="Chemprop-v2" else 2
    node=template["node"];uuid=template["uuid"]
    if node not in ({"compute-0-"+str(i) for i in range(8)}|{"compute-0-20","compute-0-22"}):raise IncompleteComparison("Unregistered confirmation GPU placement")
    if not str(program_path).startswith(str(out)+"/"):raise IncompleteComparison("Prepared source must stay in its owned shared output")
    lines=["#!/bin/bash","#SBATCH --job-name="+stage+"-seed2-"+str(number),
        "#SBATCH --partition=gpu","#SBATCH --nodelist="+node,"#SBATCH --cpus-per-task="+str(cpus),
        "#SBATCH --ntasks=1","#SBATCH --nodes=1","#SBATCH --time=12:00:00"]
    if template["original_array"]:lines.append("#SBATCH --array=0-4%1")
    lines+=["#SBATCH --output="+str(out/("GPU_group_"+str(number)+"_%j.log")),"set -euo pipefail",
        "export PYTHONPATH="+shlex.quote(pythonpath),
        "export OMP_NUM_THREADS="+str(cpus)+" MKL_NUM_THREADS="+str(cpus)+" OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1"]
    for key,value in sorted(environment.items()):
        if key not in {"BENCHMARK_MODEL","BENCHMARK_TASK_INDEX","REFERENCE_BINDING_JOB","TABPFN_ALLOW_CPU_LARGE_DATASET","LOKY_MAX_CPU_COUNT"}:raise IncompleteComparison("Unregistered original model environment selector")
        lines.append("export "+key+"="+shlex.quote(str(value)))
    lines+=["cd "+shlex.quote(repo),"findmnt -T "+shlex.quote(str(root)),
        "df -B1 "+shlex.quote(str(root))+" /tmp","df -Pi "+shlex.quote(str(root))+" /tmp",
        shlex.quote(template["python"])+" -B - <<'PY'"]
    body="import sys,types\nfrom pathlib import Path\npackage=types.ModuleType('workflows.benchmark_evaluation');package.__path__=[];sys.modules[package.__name__]=package\n"
    body+="module=types.ModuleType(package.__name__+'.gpu_runtime');module.__package__=package.__name__;sys.modules[module.__name__]=module\n"
    body+="exec(compile("+repr(runtime_source)+",module.__name__,'exec'),module.__dict__)\n"
    body+="_gpu_runtime=module.GpuRuntime(Path("+repr(str(root))+"),Path("+repr(str(quota))+"),gpu_uuid="+repr(uuid)+",expected_node="+repr(node)+",learner="+repr(learner)+")\n"
    body+="_torch=None\ntry:\n    import torch\n    _torch=torch\n    if not torch.cuda.is_available():raise RuntimeError('Actual CUDA runtime unavailable before confirmation fitting')\n"
    body+="    torch.set_float32_matmul_precision('highest')\n    torch.backends.cuda.matmul.allow_tf32=False\n    torch.backends.cudnn.allow_tf32=False\n"
    body+="    program=Path("+repr(str(program_path))+").read_text()\n    exec(compile(program,"+repr(str(program_path))+",'exec'),globals())\n"
    body+="except BaseException as error:\n    try:_gpu_runtime.finish('FAILED_WITH_NATIVE_ERROR',repr(error),_torch)\n    except Exception as closing_error:print('CONFIRMATION_NATIVE_ERROR_CAPACITY_PROTECTED',repr(closing_error),flush=True)\n    raise\n"
    body+="else:\n    _gpu_runtime.finish('MODEL_BODY_CLOSED_STATISTICS_DEFERRED_TO_CPU',torch_module=_torch)\n"
    ast.parse(body);lines.extend((body,"PY",""))
    return "\n".join(lines)
prepared=[];failures=[]
for number,group in enumerate(groups):
    template=templates[str(group["primary_job"])]
    try:
        if template.get("program"):
            source=Path(template["program"]).read_text()
        else:
            wrapper=sources["workflows/benchmark_evaluation/"+template["source_file"]]
            source=wrapper.split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0]
        if template.get("source_file")=="c1_d_tabpfn_pharmabench.sbatch":
            checkpoint=b1/"C1_D_TABPFN/job_4536921/tabpfn-v2-classifier.ckpt"
            if not checkpoint.is_file():raise IncompleteComparison("The original closed public classifier checkpoint is unavailable")
            begin=source.index("import urllib.request,urllib.error\n")
            end=source.index("tasks=defaultdict(list);coverage=",begin)
            replacement="classifier_checkpoint=Path("+repr(str(checkpoint))+")\nclassifier_access=[dict(status='REUSED_CLOSED_PUBLIC_V2_CLASSIFIER_WEIGHT',source=str(classifier_checkpoint))]\n"
            source=source[:begin]+replacement+source[end:]
        program,declaration=prepare_job_source(group,source,default_dataset=template["default_dataset"])
        program_path=out/("group_"+str(number)+".py")
        script_path=out/("group_"+str(number)+".sbatch")
        environment={}
        for export in template.get("exports",[]):
            words=shlex.split(export)
            if not words or words[0]!="export":raise IncompleteComparison("Unsupported original environment declaration")
            for word in words[1:]:
                key,value=word.split("=",1);environment[key]=value
        environment.setdefault("BENCHMARK_MODEL","Chemprop-v2" if template["learner"]=="Chemprop-v2" else "C1-TabPFN-"+template["feature_group"])
        if template["learner"]=="TabPFN":
            environment.setdefault("TABPFN_ALLOW_CPU_LARGE_DATASET","1");environment.setdefault("LOKY_MAX_CPU_COUNT","2")
        script=render_gpu(template,program_path,number,environment)
        safe()
        with program_path.open("x") as stream:stream.write(program)
        with script_path.open("x") as stream:stream.write(script)
        prepared.append(dict(group,program=str(program_path),script=str(script_path),
            node=template["node"],uuid=template["uuid"],python=template["python"],
            original_folder=template["original_folder"],array=template["original_array"],
            environment=environment,declaration=declaration,actual_GPU_job_submitted=False))
    except Exception as error:
        failures.append(dict(group=group,error=repr(error),status="UNRESOLVED_SOURCE_PREPARATION"))
report=dict(status="CONDITIONAL_NEURAL_SOURCE_PREPARATION_CLOSED" if not failures else "CONDITIONAL_NEURAL_SOURCE_PREPARATION_PARTIAL",
    stage=stage,job=os.environ["SLURM_JOB_ID"],node=socket.gethostname(),frozen_B1_roster=str(screen_path),
    C1_primary_manifest=str(primary_manifest) if primary_manifest else None,source_cache=str(cache),
    required_configuration_rows=len(plan),prepared_native_groups=prepared,reused_native_confirmations=reused,
    failures=failures,actual_GPU_fits_launched=False,scientific_scores_read_for_QA=False,task_roster_reselection=False)
safe();(out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
print("CONDITIONAL_SOURCES_PREPARED",out/"manifest.json","groups",len(prepared),"reused",len(reused),"failures",len(failures),flush=True)
if failures:raise SystemExit(1)

PY
COND_B1_PREP
