"""Move only three never-started Biogen seed26 groups to admitted development CPUs."""
import ast
import copy

BIO_PRIMARY_FEATURES={4537679:"Pprime",4537680:"Pprime_plus_D",4537010:"D"}
CPU_NODES=frozenset({"compute-0-12","compute-0-13","compute-0-16"})
GIB=1024**3

def validate_biogen_group(group):
    primary=int(group["primary_job"])
    if primary not in BIO_PRIMARY_FEATURES or group.get("feature_group")!=BIO_PRIMARY_FEATURES[primary] or group.get("learner")!="TabPFN" or group.get("array") is not False:
        raise ValueError("Only the three registered nonarray Biogen TabPFN confirmation groups are covered")
    rows=group.get("required_tasks",[])
    if not rows:raise ValueError("Actual required confirmation tasks are mandatory")
    tasks=[]
    for row in rows:
        if (row.get("dataset")!="Biogen_ADME" or row.get("feature_group")!=group["feature_group"] or row.get("learner")!="TabPFN"
            or str(row.get("primary_source_job"))!=str(primary) or int(row.get("confirmation_seed",0))!=20261026
            or int(row.get("primary_seed",0))!=20261025 or int(row.get("fold_and_statistics_seed",0))!=20261025
            or row.get("reason")!="FINAL_SIGNIFICANT_IMPROVEMENT" or row.get("frozen_B1_role")!="APPENDIX"
            or str(row.get("task_roster_reselection")).lower()!="false"
            or str(row.get("original_labels_or_masks_changed")).lower()!="false"):
            raise ValueError("Keep the exact registered required seed26 Biogen configurations")
        tasks.append(("Biogen_ADME",row["producer_task"]))
    if len(set(tasks))!=len(tasks):raise ValueError("A confirmation task may occur only once")
    return tuple(sorted(tasks))

def prepare_biogen_confirmation_cpu_source(source,group,cpus=16):
    if type(cpus) is not int or cpus!=16:raise ValueError("Exactly16 demand-allocated CPUs are covered")
    tasks=validate_biogen_group(group);tree=ast.parse(source);before=copy.deepcopy(tree)
    assignments={name:[n.value for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
        for name in ("MODEL_SEED","SEED","__confirmation_default_dataset","__confirmation_declaration","__confirmation_selected")}
    if any(len(values)!=1 for values in assignments.values()):raise ValueError("One original seed and confirmation declaration is required")
    literal=lambda name:ast.literal_eval(assignments[name][0])
    if literal("MODEL_SEED")!=20261026 or literal("SEED")!=20261025 or literal("__confirmation_default_dataset")!="Biogen_ADME":
        raise ValueError("Preserve modelseed26 and frozen split/statistics seed25")
    declaration=literal("__confirmation_declaration")
    if (declaration.get("model_seed")!=20261026 or declaration.get("split_and_statistics_seed")!=20261025
        or declaration.get("reason")!="FINAL_SIGNIFICANT_IMPROVEMENT"
        or tuple(sorted(map(tuple,declaration.get("selected_original_tasks",[]))))!=tasks
        or declaration.get("task_roster_reselection") is not False
        or declaration.get("primary_fit_population_only") is not True
        or declaration.get("original_model_budget_unchanged") is not True):
        raise ValueError("Original selected tasks, fit population and budget must remain")
    selected=assignments["__confirmation_selected"][0]
    if not(isinstance(selected,ast.Call) and isinstance(selected.func,ast.Name) and selected.func.id=="frozenset"
           and len(selected.args)==1 and tuple(sorted(map(tuple,ast.literal_eval(selected.args[0]))))==tasks):
        raise ValueError("Original runtime task filter differs")
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="create_default_for_version"]
    if len(calls)!=1:raise ValueError("Exactly one original TabPFN constructor required")
    call=calls[0];owner=call.func.value
    if not(isinstance(owner,ast.IfExp) and isinstance(owner.body,ast.Name) and owner.body.id=="TabPFNClassifier"
        and isinstance(owner.orelse,ast.Name) and owner.orelse.id=="TabPFNRegressor"):
        raise ValueError("Preserve original TabPFN class selector")
    if len(call.args)!=1 or ast.dump(call.args[0])!=ast.dump(ast.parse("ModelVersion.V2",mode="eval").body):
        raise ValueError("Pinned V2 checkpoint family required")
    keywords={kw.arg:kw for kw in call.keywords}
    if not {"device","random_state","n_preprocessing_jobs","model_path"}.issubset(keywords):raise ValueError("Original model keyword configuration required")
    if not(isinstance(keywords["device"].value,ast.Constant) and keywords["device"].value.value=="cuda"):
        raise ValueError("Only one original CUDA model may change backend")
    if not(isinstance(keywords["random_state"].value,ast.Name) and keywords["random_state"].value.id=="MODEL_SEED"):
        raise ValueError("Original candidate model seed must remain")
    if ast.literal_eval(keywords["n_preprocessing_jobs"].value)!=2:raise ValueError("Original preprocessing job count must remain2")
    if not any(isinstance(n,ast.Constant) and n.value=="smoke100/job_4536865/model_cache/tabpfn-v2-regressor.ckpt" for n in ast.walk(tree)):
        raise ValueError("Accepted offline V2 regression weight path required")
    threads=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="set_num_threads"
        and isinstance(n.func.value,ast.Name) and n.func.value.id=="torch"]
    if len(threads)!=1 or len(threads[0].args)!=1 or ast.literal_eval(threads[0].args[0])!=2:
        raise ValueError("One original two-thread execution selector required")
    keywords["device"].value=ast.Constant(value="cpu");threads[0].args[0]=ast.Constant(value=cpus)
    ast.fix_missing_locations(tree);prepared=ast.unparse(tree)+"\n";compile(prepared,"Biogen_required_seed26_CPU","exec")
    restored=ast.parse(prepared)
    restored_call=next(n for n in ast.walk(restored) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="create_default_for_version")
    next(kw for kw in restored_call.keywords if kw.arg=="device").value=ast.Constant(value="cuda")
    next(n for n in ast.walk(restored) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="set_num_threads"
         and isinstance(n.func.value,ast.Name) and n.func.value.id=="torch").args[0]=ast.Constant(value=2)
    if ast.dump(before,include_attributes=False)!=ast.dump(restored,include_attributes=False):
        raise ValueError("Source changed beyond device and allocated thread count")
    return prepared

def validate_cpu_runtime(node,allocated,expected_node,visible):
    if node not in CPU_NODES or node!=expected_node or type(allocated) is not int or allocated!=16 or visible!="":
        raise ValueError("Exact eligible CPU node,16 allocated CPUs and disabled CUDA required")

def remaining_gpu_dependencies(ordered,removed,barriers):
    jobs=[str(row["job"]) for row in ordered];removed={str(job) for job in removed}
    if len(set(jobs))!=len(jobs) or not removed or not removed.issubset(jobs):
        raise ValueError("Distinct actual GPU jobs and exact removed subset required")
    if any(not job.isdigit() or int(job)<=0 for job in jobs):raise ValueError("Native job IDs required")
    previous={};result={}
    for row in ordered:
        job=str(row["job"]);uuid=row["uuid"]
        if job in removed:continue
        predecessors=[previous[uuid]] if uuid in previous else list(map(str,barriers.get(uuid,[])))
        if any(not p.isdigit() or int(p)<=0 or p in removed for p in predecessors):raise ValueError("Protected native barriers must remain")
        result[job]="afterany:"+":".join(predecessors) if predecessors else None
        previous[uuid]=job
    return result

def rebind_confirmation_runs(bindings,replacements):
    replacements={int(old):int(new) for old,new in replacements.items()}
    if not replacements or any(old<=0 or new<=0 or old==new for old,new in replacements.items()) or len(set(replacements.values()))!=len(replacements):
        raise ValueError("Distinct actual CPU replacement identities required")
    answer=copy.deepcopy(bindings);seen={old:0 for old in replacements}
    original_ids={int(run["job"]) for group in bindings["groups"] for run in group["runs"]}
    if set(replacements.values())&original_ids:raise ValueError("A new CPU identity collides with an existing native run")
    for group in answer["groups"]:
        for run in group["runs"]:
            old=int(run["job"])
            if old not in replacements:continue
            if run.get("array") is not False:raise ValueError("Only exact nonarray confirmation runs may change backend")
            run.update(job=replacements[old],zero_start_GPU_job=old,execution_backend="CPU")
            seen[old]+=1
    if any(value!=1 for value in seen.values()):raise ValueError("Each old native group must occur exactly once")
    return answer
