"""Move only never-started registered reference TabPFN primary jobs to CPU."""
import ast
import copy

REFERENCE_DATASETS=frozenset({"C7H10O2","PPE1694","Joung2020"})
REFERENCE_GROUPS=frozenset({"Pprime","Pprime_plus_D"})

def prepare_reference_cpu_source(source, dataset, feature_group):
    if dataset not in REFERENCE_DATASETS or feature_group not in REFERENCE_GROUPS:
        raise ValueError("Only registered reference native-P primary groups are covered")
    tree=ast.parse(source)
    expected="C1_Pprime_reference_features/job_4537149/"+feature_group+"/"+dataset+"_cv_binding.json"
    bindings=[node for node in tree.body if isinstance(node,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=="binding_path" for t in node.targets)]
    if len(bindings)!=1 or not any(isinstance(v,ast.Constant) and v.value==expected for v in ast.walk(bindings[0].value)):
        raise ValueError("Actual captured reference binding differs from its registered group")
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
           and isinstance(n.func,ast.Attribute) and n.func.attr=="create_default_for_version"
           and isinstance(n.func.value,ast.Name) and n.func.value.id=="TabPFNRegressor"]
    if len(calls)!=1:
        raise ValueError("Exactly one original TabPFN regressor constructor is required")
    call=calls[0]
    if len(call.args)!=1 or ast.dump(call.args[0],include_attributes=False)!=ast.dump(ast.parse("ModelVersion.V2",mode="eval").body,include_attributes=False):
        raise ValueError("Preserve the pinned V2 checkpoint family")
    devices=[kw for kw in call.keywords if kw.arg=="device"]
    if len(devices)!=1 or not isinstance(devices[0].value,ast.Constant) or devices[0].value.value!="cuda":
        raise ValueError("Only an original registered CUDA constructor may be rebound once")
    if not any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.endswith("tabpfn-v2-regressor.ckpt") for n in ast.walk(tree)):
        raise ValueError("The accepted offline V2 checkpoint path is required")
    before=copy.deepcopy(tree)
    devices[0].value=ast.Constant(value="cpu")
    ast.fix_missing_locations(tree)
    prepared=ast.unparse(tree)+"\n"
    compile(prepared,"registered_reference_TabPFN_CPU_primary","exec")
    # Restore the single permitted execution-device difference for full AST equality.
    restored=ast.parse(prepared)
    restored_call=next(n for n in ast.walk(restored) if isinstance(n,ast.Call)
        and isinstance(n.func,ast.Attribute) and n.func.attr=="create_default_for_version"
        and isinstance(n.func.value,ast.Name) and n.func.value.id=="TabPFNRegressor")
    next(kw for kw in restored_call.keywords if kw.arg=="device").value=ast.Constant(value="cuda")
    if ast.dump(before,include_attributes=False)!=ast.dump(restored,include_attributes=False):
        raise ValueError("Model source changed beyond the registered execution device")
    return prepared

def remap_reference_cpu_specs(specs,mapping):
    mapping={int(k):int(v) for k,v in mapping.items()}
    if not mapping or any(k<=0 or v<=0 or k==v for k,v in mapping.items()) or len(set(mapping.values()))!=len(mapping):
        raise ValueError("Use distinct actual new native model IDs")
    if any(sum(int(row["job"])==old for row in specs)!=1 for old in mapping):
        raise ValueError("Each original registered source must occur exactly once")
    answer=copy.deepcopy(specs)
    for row in answer:
        old=int(row["job"])
        if old not in mapping:continue
        if row["dataset"] not in REFERENCE_DATASETS or row["feature_group"] not in REFERENCE_GROUPS or row["learner"]!="TabPFN":
            raise ValueError("Only molecular reference primary TabPFN groups may change backend")
        if row["folder"]!="reference_cv_models/job_"+str(old):
            raise ValueError("Actual original reference output identity differs")
        row.update(job=mapping[old],folder="reference_cv_models/job_"+str(mapping[old]),
            zero_start_resource_reassignment_of_job=old,primary_execution_backend="CPU")
    return answer

def bounded_cpu_predecessors(original_jobs, maximum_parallel=8):
    jobs=[int(j) for j in original_jobs]
    if not jobs or any(j<=0 for j in jobs) or len(jobs)!=len(set(jobs)):
        raise ValueError("Unique actual original native model IDs are required")
    if type(maximum_parallel) is not int or not 1<=maximum_parallel<=8:
        raise ValueError("At most eight 4GiB CPU primary slots fit the existing40GiB pool")
    return {job:(None if i<maximum_parallel else jobs[i-maximum_parallel])
            for i,job in enumerate(jobs)}
