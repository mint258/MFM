"""CPU execution adaptation for already required, never-started C1 seed26 groups."""
import ast
import copy

CPU_NODES=frozenset({"compute-0-8","compute-0-11","compute-0-12","compute-0-13","compute-0-16","compute-0-19"})
CPU_SLOTS=("compute-0-8","compute-0-11","compute-0-12","compute-0-12","compute-0-13","compute-0-16","compute-0-16","compute-0-19")
CLOSED_BIOGEN_PRIMARY=frozenset({4537679,4537680,4537010})

def validate_required_group(group):
    primary=int(group["primary_job"])
    if primary in CLOSED_BIOGEN_PRIMARY or group.get("feature_group") not in {"D","Pprime","Pprime_plus_D"} or group.get("learner")!="TabPFN" or group.get("array") is not False:
        raise ValueError("Only remaining registered nonarray TabPFN confirmation groups are covered")
    rows=group.get("required_tasks",[])
    if not rows:raise ValueError("Actual required confirmation tasks are mandatory")
    tasks=[]
    for row in rows:
        if (row.get("feature_group")!=group["feature_group"] or row.get("learner")!="TabPFN"
            or str(row.get("primary_source_job"))!=str(primary) or int(row.get("confirmation_seed",0))!=20261026
            or int(row.get("primary_seed",0))!=20261025 or int(row.get("fold_and_statistics_seed",0))!=20261025
            or row.get("reason")!="FINAL_SIGNIFICANT_IMPROVEMENT" or row.get("frozen_B1_role") not in {"RETAIN","APPENDIX"}
            or str(row.get("task_roster_reselection")).lower()!="false"
            or str(row.get("original_labels_or_masks_changed")).lower()!="false"
            or not row.get("dataset") or not row.get("producer_task")):
            raise ValueError("Keep the exact registered required seed26 configurations")
        tasks.append((row["dataset"],row["producer_task"]))
    if len(set(tasks))!=len(tasks):raise ValueError("A confirmation task may occur only once")
    return tuple(sorted(tasks))

def prepare_required_cpu_source(source,group,cpus):
    if type(cpus) is not int or cpus not in {16,32}:raise ValueError("Demand-allocated16 or32 CPUs required")
    tasks=validate_required_group(group);tree=ast.parse(source);before=copy.deepcopy(tree)
    assignments={name:[n.value for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
        for name in ("MODEL_SEED","SEED","__confirmation_declaration","__confirmation_selected")}
    if any(len(values)!=1 for values in assignments.values()):raise ValueError("One original seed and confirmation declaration required")
    literal=lambda name:ast.literal_eval(assignments[name][0])
    if literal("MODEL_SEED")!=20261026 or literal("SEED")!=20261025:raise ValueError("Frozen model and statistics seeds required")
    declaration=literal("__confirmation_declaration")
    if (declaration.get("model_seed")!=20261026 or declaration.get("split_and_statistics_seed")!=20261025
        or declaration.get("reason")!="FINAL_SIGNIFICANT_IMPROVEMENT"
        or tuple(sorted(map(tuple,declaration.get("selected_original_tasks",[]))))!=tasks
        or declaration.get("task_roster_reselection") is not False or declaration.get("primary_fit_population_only") is not True
        or declaration.get("original_model_budget_unchanged") is not True):raise ValueError("Original tasks, fit population and budget required")
    selected=assignments["__confirmation_selected"][0]
    if not(isinstance(selected,ast.Call) and isinstance(selected.func,ast.Name) and selected.func.id=="frozenset"
        and len(selected.args)==1 and tuple(sorted(map(tuple,ast.literal_eval(selected.args[0]))))==tasks):raise ValueError("Original task filter differs")
    def constructors(t):
        return [n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="create_default_for_version"]
    calls=constructors(tree)
    if len(calls)!=1:raise ValueError("Exactly one pinned V2 constructor required")
    call=calls[0];owner=call.func.value
    if not ((isinstance(owner,ast.Name) and owner.id=="TabPFNRegressor") or
        (isinstance(owner,ast.IfExp) and isinstance(owner.body,ast.Name) and owner.body.id=="TabPFNClassifier"
         and isinstance(owner.orelse,ast.Name) and owner.orelse.id=="TabPFNRegressor")):raise ValueError("Original V2 class selector required")
    if len(call.args)!=1 or ast.dump(call.args[0])!=ast.dump(ast.parse("ModelVersion.V2",mode="eval").body):raise ValueError("Pinned V2 weights required")
    kw={k.arg:k for k in call.keywords}
    if not {"device","random_state","n_preprocessing_jobs","model_path"}.issubset(kw):raise ValueError("Original model keyword configuration required")
    if not(isinstance(kw["device"].value,ast.Constant) and kw["device"].value.value=="cuda"):raise ValueError("Only original CUDA source covered")
    if not(isinstance(kw["random_state"].value,ast.Name) and kw["random_state"].value.id=="MODEL_SEED"):raise ValueError("Original model seed required")
    original_preprocessing=copy.deepcopy(kw["n_preprocessing_jobs"].value)
    uses_cpus=isinstance(original_preprocessing,ast.Name) and original_preprocessing.id=="cpus"
    if uses_cpus:
        cpu_assign=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="cpus" for t in n.targets)]
        expected=ast.parse("int(os.environ['SLURM_CPUS_PER_TASK'])",mode="eval").body
        if len(cpu_assign)!=1 or ast.dump(cpu_assign[0])!=ast.dump(expected):raise ValueError("Original allocated CPU selector required")
    elif not(isinstance(original_preprocessing,ast.Constant) and type(original_preprocessing.value) is int and original_preprocessing.value==2):
        raise ValueError("Original effective preprocessing parallelism must be2")
    if not any(isinstance(n,ast.Constant) and n.value=="smoke100/job_4536865/model_cache/tabpfn-v2-regressor.ckpt" for n in ast.walk(tree)):
        raise ValueError("Existing accepted offline V2 regression checkpoint required")
    def threads(t):
        return [n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
            and n.func.attr=="set_num_threads" and isinstance(n.func.value,ast.Name) and n.func.value.id=="torch"]
    ts=threads(tree)
    if len(ts)>1:raise ValueError("At most one original Torch thread selector covered")
    original_thread=copy.deepcopy(ts[0].args) if ts else []
    if ts:
        if len(ts[0].args)!=1:raise ValueError("One original Torch thread argument required")
        arg=ts[0].args[0]
        if isinstance(arg,ast.Constant) and type(arg.value) is int and arg.value==2:ts[0].args[0]=ast.Constant(value=cpus)
        elif not(uses_cpus and isinstance(arg,ast.Name) and arg.id=="cpus"):raise ValueError("Unregistered original Torch thread selector")
    kw["device"].value=ast.Constant(value="cpu")
    kw["n_preprocessing_jobs"].value=ast.Constant(value=2)
    ast.fix_missing_locations(tree);prepared=ast.unparse(tree)+"\n";compile(prepared,"required_seed26_CPU","exec")
    restored=ast.parse(prepared);rc=constructors(restored)[0]
    next(k for k in rc.keywords if k.arg=="device").value=ast.Constant(value="cuda")
    next(k for k in rc.keywords if k.arg=="n_preprocessing_jobs").value=original_preprocessing
    if original_thread:threads(restored)[0].args=original_thread
    if ast.dump(before,include_attributes=False)!=ast.dump(restored,include_attributes=False):raise ValueError("Change beyond backend and execution resources")
    return prepared

def validate_cpu_runtime(node,allocated,expected_node,expected_cpus,visible):
    if node not in CPU_NODES or node!=expected_node or type(allocated) is not int or allocated!=expected_cpus or allocated not in {16,32} or visible!="":
        raise ValueError("Exact eligible CPU node, demand allocation and disabled CUDA required")

def assign_slots(rows):
    if not rows or len({r["original_GPU_job"] for r in rows})!=len(rows):raise ValueError("Distinct original native identities required")
    answer=copy.deepcopy(rows)
    for index,row in enumerate(answer):
        row["CPU_slot"]=index%len(CPU_SLOTS);row["node"]=CPU_SLOTS[row["CPU_slot"]]
        datasets={r["dataset"] for r in row["group"]["required_tasks"]}
        row["allocated_CPUs"]=16 if datasets.issubset({"MoleculeACE","PharmaBench"}) else 32
    return answer

def resolve_confirmation_environment(group,program,environment):
    """Preserve registered task selectors and select the required original learner."""
    if group.get("learner")!="TabPFN" or group.get("feature_group") not in {"D","Pprime","Pprime_plus_D"}:
        raise ValueError("Registered C1 TabPFN group required")
    allowed={"BENCHMARK_MODEL","BENCHMARK_TASK_INDEX","REFERENCE_BINDING_JOB","TABPFN_ALLOW_CPU_LARGE_DATASET","LOKY_MAX_CPU_COUNT","C1_MODEL"}
    if set(environment)-allowed:raise ValueError("Unregistered original model environment selector")
    result={key:str(value) for key,value in environment.items()}
    if (result.get("BENCHMARK_MODEL")!="C1-TabPFN-"+group["feature_group"]
        or result.get("TABPFN_ALLOW_CPU_LARGE_DATASET")!="1" or result.get("LOKY_MAX_CPU_COUNT")!="2"):
        raise ValueError("Exact original model and context/preprocessing permission required")
    datasets={row["dataset"] for row in group["required_tasks"]}
    if "BENCHMARK_TASK_INDEX" in result and (datasets!={"Joung2020"} or not result["BENCHMARK_TASK_INDEX"].isdigit()
        or not 0<=int(result["BENCHMARK_TASK_INDEX"])<=8):raise ValueError("Exact original Joung environment selector required")
    if "REFERENCE_BINDING_JOB" in result and (datasets!={"PPE1694"} or result["REFERENCE_BINDING_JOB"]!="4536997"):
        raise ValueError("Exact original PPE source binding required")
    tree=ast.parse(program)
    selectors=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="model_name" for t in n.targets)
        and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=="get"
        and ast.unparse(n.value.func.value)=="os.environ"]
    if len(selectors)>1:raise ValueError("Ambiguous actual learner selector")
    if selectors:
        selector=selectors[0]
        if not selector.args or not isinstance(selector.args[0],ast.Constant):raise ValueError("Literal actual learner selector required")
        key=selector.args[0].value
        if key=="C1_MODEL":
            if datasets!={"ExpansionRx"}:raise ValueError("C1_MODEL belongs only to the original ExpansionRx source")
            if result.get("C1_MODEL","TabPFN-V2")!="TabPFN-V2":raise ValueError("Never run the LightGBM fallback as a TabPFN confirmation")
            result["C1_MODEL"]="TabPFN-V2"
        elif key!="BENCHMARK_MODEL":raise ValueError("Unregistered actual learner selector")
    if datasets=={"ExpansionRx"} and (not selectors or selectors[0].args[0].value!="C1_MODEL"):
        raise ValueError("Original ExpansionRx learner selector required")
    if "C1_MODEL" in result and datasets!={"ExpansionRx"}:raise ValueError("Unexpected inherited model selector")
    return result
