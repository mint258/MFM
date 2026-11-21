"""Resume only terminally failed reference primary fits, preserving closed fold bytes."""
import ast
import copy
import json
import os
import re
from pathlib import Path

FAILED_STATES=frozenset({"FAILED","TIMEOUT","OUT_OF_MEMORY","NODE_FAIL","BOOT_FAIL","PREEMPTED"})
SCIENTIFIC_FUNCTIONS=("eligible","matrix","mean_reference_metrics","fixed_population","fit_predict")

def require_terminal_failure(native, source_job):
    if not re.fullmatch(r"[1-9][0-9]*",str(source_job)):raise ValueError("Actual positive source job required")
    fields=dict(re.findall(r"([A-Za-z][A-Za-z0-9_]*)=(\S+)",native))
    if (fields.get("JobId")!=str(source_job) or fields.get("UserId")!="zixiao(1278)"
        or fields.get("Restarts")!="0" or fields.get("JobState") not in FAILED_STATES):
        raise ValueError("Only the actual owned terminal failure, without requeue, permits continuation")
    if fields.get("RunTime") in {None,"00:00:00","0:00"}:
        raise ValueError("A previously running reference producer is required")
    return fields

def _identity(record):
    return (record["dataset"],record["task"],record["model"],int(record["repetition"]),
            int(record["fold"]),record["fit_population"])

def _owned_file(path, root, uid):
    path=Path(path);root=Path(root).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file() or path.stat().st_uid!=uid:
        raise ValueError("Only owned original fold files inside the failed producer are reusable")
    return path

def collect_closed_folds(source_root, native, source_job, log_text, dataset, model, allowed_tasks, uid=None):
    """Consume the failed producer's own closure records, without reading prediction numbers."""
    require_terminal_failure(native,source_job)
    source_root=Path(source_root).resolve();uid=os.getuid() if uid is None else uid
    if source_root.name!="job_"+str(source_job) or source_root.parent.name!="reference_cv_models":
        raise ValueError("The original actual source directory is required")
    if dataset not in {"C7H10O2","Joung2020"} or model!="C1-TabPFN-Pprime" or not allowed_tasks:
        raise ValueError("Only the original outstanding primary task set is covered")
    tasks=set(allowed_tasks);closed=[];seen=set()
    pattern=re.compile(r"^REFERENCE_CV_MODEL_FIT_CLOSED (\S+) (.+) (C1-TabPFN-Pprime) ([0-4]) ([0-4]) retained seconds [0-9.]+$")
    for line in log_text.splitlines():
        if not line.startswith("REFERENCE_CV_MODEL_FIT_CLOSED "):continue
        match=pattern.fullmatch(line)
        if match is None:raise ValueError("A malformed producer closure cannot be guessed or replayed")
        group,task,learner,rep,fold=match.groups()
        key=(group,task,learner,int(rep),int(fold),"retained")
        if group!=dataset or learner!=model or task not in tasks or key in seen:
            raise ValueError("Duplicate or out-of-scope producer closure")
        seen.add(key)
        relative=Path(group)/task/("r"+rep+"_f"+fold+"_retained")
        folder=source_root/relative
        result=_owned_file(folder/"results.json",source_root,uid)
        prediction=_owned_file(folder/"predictions.parquet",source_root,uid)
        record=json.loads(result.read_text())
        if _identity(record)!=key or not isinstance(record.get("results"),list) or not record["results"]:
            raise ValueError("The closed fold identity must remain the producer's original identity")
        for metric in record["results"]:
            if (_identity(metric)!=key or metric.get("seed")!=20261025
                or metric.get("evaluation_population")!="retained"
                or metric.get("metric_status")!="PENDING_CPU_STATISTICS"):
                raise ValueError("Reuse the original deferred-statistics primary fold only")
        closed.append(dict(key=list(key),relative_directory=relative.as_posix(),record=record,
            source_job=int(source_job),source_results=str(result),source_predictions=str(prediction)))
    return closed

class ResumeContext:
    def __init__(self, owned_root, source_job, new_job, closed, protect_write, uid=None):
        self.root=Path(owned_root).resolve();self.source_job=int(source_job);self.new_job=int(new_job)
        if min(self.source_job,self.new_job)<=0 or self.source_job==self.new_job:
            raise ValueError("Distinct actual source and continuation jobs are required")
        self.uid=os.getuid() if uid is None else uid
        self.closed={tuple(row["key"]):copy.deepcopy(row) for row in closed}
        if len(self.closed)!=len(closed):raise ValueError("A closed fold must have one native origin")
        self.protect_write=protect_write;self.out=None;self.used={}
    def initialize(self,out):
        expected=self.root/"reference_cv_models"/("job_"+str(self.new_job))
        if self.out is not None or Path(out).resolve()!=expected or not expected.is_dir():
            raise ValueError("Use the new actual native job directory exactly once")
        self.out=expected
    def reuse(self,fitdir,dataset,task,model,repetition,fold,fit_population):
        if self.out is None:raise ValueError("Continuation must initialize its exclusive new output")
        key=(dataset,task,model,int(repetition),int(fold),fit_population)
        expected=self.out/dataset/task/("r%d_f%d_%s"%(repetition,fold,fit_population))
        if not expected.resolve().is_relative_to(self.out) or Path(fitdir).resolve()!=expected:
            raise ValueError("The original loop must request its exact frozen fold directory")
        if key in self.used:raise ValueError("A closed fit cannot be consumed twice")
        row=self.closed.get(key)
        if row is None:return None
        source=self.root/"reference_cv_models"/("job_"+str(self.source_job))
        if row["source_job"]!=self.source_job or row["relative_directory"]!=expected.relative_to(self.out).as_posix() or _identity(row["record"])!=key:
            raise ValueError("Closed fit native origin or original fold identity changed")
        paths=[_owned_file(row[name],source,self.uid) for name in ("source_results","source_predictions")]
        if any(path.parent.resolve()!=(source/row["relative_directory"]).resolve() for path in paths):
            raise ValueError("Both original fold files must belong to the same native origin")
        if expected.exists():raise ValueError("Never overwrite a previously created continuation fold")
        self.protect_write();expected.mkdir()
        for path,name in zip(paths,("results.json","predictions.parquet")):
            self.protect_write();os.link(path,expected/name)
        self.used[key]=dict(source_job=self.source_job,source_directory=str(paths[0].parent),
            continuation_job=self.new_job,continuation_directory=str(expected),key=list(key))
        print("REFERENCE_CV_CLOSED_FOLD_REUSED",dataset,task,model,repetition,fold,fit_population,
              "source_job",self.source_job,flush=True)
        return copy.deepcopy(row["record"])
    def provenance(self):
        if set(self.used)!=set(self.closed):raise ValueError("Every selected closed fold must be consumed exactly once")
        return dict(reference_closed_fold_resume=dict(source_job=self.source_job,continuation_job=self.new_job,
            reused_closed_folds=list(self.used.values()),closed_predictions_hardlinked_without_numeric_readback=True,
            closed_statistics_not_recomputed=True,model_seed=20261025,gradient_training_rollback=False))

def prepare_resume_source(source,dataset,feature_group):
    """Insert continuation control only; reverse it to prove full original scientific AST equality."""
    if dataset not in {"C7H10O2","Joung2020"} or feature_group!="Pprime":
        raise ValueError("Only the original five outstanding Pprime reference primaries are covered")
    original=ast.parse(source)
    reserved={"_reference_resume","_closed_reference_fold"}
    if any(isinstance(node,ast.Name) and node.id in reserved for node in ast.walk(original)):
        raise ValueError("The registered original source must not already contain a continuation")
    expected="C1_Pprime_reference_features/job_4537149/"+feature_group+"/"+dataset+"_cv_binding.json"
    bindings=[node for node in original.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="binding_path" for t in node.targets)]
    seeds=[node for node in original.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SEED" for t in node.targets)]
    if len(bindings)!=1 or not any(isinstance(n,ast.Constant) and n.value==expected for n in ast.walk(bindings[0])):
        raise ValueError("Original frozen dataset and feature binding differs")
    if len(seeds)!=1 or not isinstance(seeds[0].value,ast.Constant) or seeds[0].value.value!=20261025:
        raise ValueError("The original single model seed is required")
    functions={node.name:node for node in original.body if isinstance(node,ast.FunctionDef)}
    if any(name not in functions for name in SCIENTIFIC_FUNCTIONS):
        raise ValueError("Every original scientific function is required")
    calls=[n for n in ast.walk(original) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
        and isinstance(n.func.value,ast.Name) and n.func.value.id=="TabPFNRegressor" and n.func.attr=="create_default_for_version"]
    if len(calls)!=1 or len(calls[0].args)!=1 or ast.dump(calls[0].args[0])!=ast.dump(ast.parse("ModelVersion.V2",mode="eval").body):
        raise ValueError("The original fixed offline V2 model is required")
    devices=[kw for kw in calls[0].keywords if kw.arg=="device"]
    if len(devices)!=1 or not isinstance(devices[0].value,ast.Constant) or devices[0].value.value!="cuda":
        raise ValueError("Use the captured original registered CUDA model")
    if not any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.endswith("tabpfn-v2-regressor.ckpt") for n in ast.walk(original)):
        raise ValueError("The original offline checkpoint must remain")
    def method(node,owner,name):
        return (isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
            and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name)
            and node.value.func.value.id==owner and node.value.func.attr==name)
    initialize=ast.parse("_reference_resume.initialize(out)").body[0]
    reuse=ast.parse("_closed_reference_fold = _reference_resume.reuse(fitdir,group,task,model_name,repetition,fold,fit_population)\nif _closed_reference_fold is not None:\n    results.extend(_closed_reference_fold['results'])\n    completed_fits += 1\n    continue\n").body
    metadata=ast.parse("report.update(**_reference_resume.provenance())").body[0]
    counts=dict(output=0,fold=0,report=0)
    class Insert(ast.NodeTransformer):
        def visit_Expr(self,node):
            if method(node,"out","mkdir"):
                counts["output"]+=1;return [node,copy.deepcopy(initialize)]
            if method(node,"fitdir","mkdir"):
                counts["fold"]+=1;return copy.deepcopy(reuse)+[node]
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if any(isinstance(t,ast.Name) and t.id=="report" for t in node.targets):
                counts["report"]+=1;return [node,copy.deepcopy(metadata)]
            return self.generic_visit(node)
    changed=Insert().visit(copy.deepcopy(original));ast.fix_missing_locations(changed)
    if counts!={"output":1,"fold":1,"report":1}:raise ValueError("Exact original fold loop and report insertion points are required")
    prepared=ast.unparse(changed)+"\n";reparsed=ast.parse(prepared)
    inserted_exprs={ast.dump(initialize),ast.dump(metadata)}
    class Remove(ast.NodeTransformer):
        def visit_Expr(self,node):
            if ast.dump(node) in inserted_exprs:return None
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=="_closed_reference_fold":return None
            return self.generic_visit(node)
        def visit_If(self,node):
            if ast.dump(node.test)==ast.dump(reuse[1].test):return None
            return self.generic_visit(node)
    restored=Remove().visit(copy.deepcopy(reparsed));ast.fix_missing_locations(restored)
    if ast.dump(restored)!=ast.dump(original):raise ValueError("Scientific source changed beyond the exact continuation control")
    for name in SCIENTIFIC_FUNCTIONS:
        actual=next(n for n in reparsed.body if isinstance(n,ast.FunctionDef) and n.name==name)
        if ast.dump(actual)!=ast.dump(functions[name]):raise ValueError("An original scientific function changed")
    compile(prepared,"registered_reference_closed_fold_resume","exec")
    return prepared

def validate_resume_plan(plan,new_job):
    allowed={4537812:"Joung2020",4537813:"Joung2020",4537814:"Joung2020",4537817:"Joung2020",4537818:"C7H10O2"}
    old=int(plan.get("source_job",0))
    if not re.fullmatch(r"[1-9][0-9]*",str(new_job)):raise ValueError("Actual positive continuation job required")
    if (plan.get("schema")!="REFERENCE_TERMINAL_FAILED_CLOSED_FOLD_RESUME_V1" or old not in allowed
        or str(plan.get("new_native_job"))!=str(new_job) or int(new_job)==old
        or plan.get("repair_attempt")!=1 or plan.get("dataset")!=allowed[old]
        or plan.get("feature_group")!="Pprime" or plan.get("model_seed")!=20261025
        or plan.get("benchmark_NFS_pool_bytes")!=40*1024**3 or plan.get("maximum_concurrent_GPU7_models")!=1):
        raise ValueError("Only a first terminal-failure continuation of the exact five original primaries is covered")
    require_terminal_failure(plan["source_native_record"],old)
    tasks=plan.get("frozen_task_names")
    if not isinstance(tasks,list) or not tasks or any(not isinstance(task,str) or not task for task in tasks) or len(set(tasks))!=len(tasks):
        raise ValueError("The original frozen endpoint task identities are required")
    return old

TARGETED_RESUME_SCHEMA="REFERENCE_TERMINAL_FAILED_TARGETED_GPU_RESUME_V2"
TARGETED_GPU_NODES=frozenset("compute-0-"+str(index) for index in range(8))|{"compute-0-20","compute-0-22"}
TARGETED_GPU_PYTHONS=frozenset(("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python","/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu128_job_4537025_step_5/tabpfn/bin/python"))

def validate_targeted_resume_plan(plan,new_job,*,actual_node,registered_python):
    """Bind a failed-only continuation to one actual approved GPU allocation and existing environment."""
    if not isinstance(plan,dict):raise ValueError("An explicit targeted GPU plan object is required")
    if (plan.get("schema")!=TARGETED_RESUME_SCHEMA
        or type(plan.get("maximum_concurrent_reference_GPU_models")) is not int
        or plan.get("maximum_concurrent_reference_GPU_models")!=1
        or "maximum_concurrent_GPU7_models" in plan):
        raise ValueError("A single targeted GPU continuation requires its explicit V2 plan")
    node=plan.get("target_node")
    uuid=plan.get("gpu_uuid")
    python=plan.get("gpu_python")
    if not isinstance(node,str) or node not in TARGETED_GPU_NODES or actual_node!=node:
        raise ValueError("The actual allocated permitted development node must match the selected GPU target")
    if (not isinstance(uuid,str) or not re.fullmatch(
        r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",uuid)):
        raise ValueError("An exact actual GPU UUID is required")
    if not isinstance(python,str) or python not in TARGETED_GPU_PYTHONS or registered_python!=python:
        raise ValueError("Use exactly one already validated private TabPFN CUDA environment")
    # Reuse every original source/seed/attempt/terminal-state invariant without relaxing the old GPU7 entry.
    common=copy.deepcopy(plan)
    common["schema"]="REFERENCE_TERMINAL_FAILED_CLOSED_FOLD_RESUME_V1"
    common["maximum_concurrent_GPU7_models"]=1
    old=validate_resume_plan(common,new_job)
    return old,dict(target_node=node,gpu_uuid=uuid,gpu_python=python)
