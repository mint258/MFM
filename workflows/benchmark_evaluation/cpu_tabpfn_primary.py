"""Use the original CPU TabPFN model body while deferring joint C1 statistics."""
import ast
import copy

ALLOWED_TABULAR_CPU = frozenset((dataset,feature) for dataset in ('Biogen_ADME','PharmaBench','tdc_asap','pKahub','MoleculeACE','ExpansionRx') for feature in ('Pprime','Pprime_plus_D'))

def model_calls(source):
    class Device(ast.NodeTransformer):
        def visit_keyword(self,node):
            node=self.generic_visit(node)
            if node.arg=="device" and isinstance(node.value,ast.Constant) and node.value.value in {"cpu","cuda"}:
                node.value=ast.Constant(value="REGISTERED_EXECUTION_DEVICE")
            return node
    selected=[]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {"create_default_for_version","fit","predict","predict_proba"}:
            selected.append(ast.dump(Device().visit(copy.deepcopy(node)),include_attributes=False))
    return selected

def defer_cpu_statistics(source):
    class Stats(ast.NodeTransformer):
        def visit_FunctionDef(self,node):
            if node.name in {"score","mean_reference_metrics"}:
                result=ast.parse("def "+node.name+"(*args, **kwargs):\n"
                    "    return dict(metric_status='PENDING_CPU_STATISTICS', n_test_rows=len(args[0]), bootstrap_draws=0, CPU_statistics_deferred=True)\n").body[0]
                return ast.copy_location(result,node)
            return self.generic_visit(node)
        def visit_Assign(self,node):
            node=self.generic_visit(node)
            if any(isinstance(target,ast.Name) and target.id in {"official_score","official_value"} for target in node.targets):
                node.value=ast.Constant(value=None)
            return node
        def visit_If(self,node):
            if any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=="TextTestRunner" for x in ast.walk(node.test)):
                return ast.copy_location(ast.Pass(),node)
            return self.generic_visit(node)
    tree=Stats().visit(ast.parse(source));ast.fix_missing_locations(tree)
    result=ast.unparse(tree)+"\n";compile(result,"CPU_TabPFN_same_model_body","exec")
    if model_calls(source)!=model_calls(result):
        raise ValueError("Statistics deferral changed a model constructor, fit, or prediction")
    return result

def remap_tabpfn_cpu_specs(specs,mapping):
    mapping={int(k):int(v) for k,v in mapping.items()}
    if not mapping or any(k<=0 or v<=0 or k==v for k,v in mapping.items()) or len(set(mapping.values()))!=len(mapping):
        raise ValueError("Use actual distinct replacement IDs")
    if any(sum(int(row["job"])==old for row in specs)!=1 for old in mapping):
        raise ValueError("Each original source must occur exactly once before mutation")
    result=copy.deepcopy(specs);seen={key:0 for key in mapping}
    for row in result:
        old=int(row["job"])
        if old not in mapping:continue
        if row["learner"]!="TabPFN" or (row["dataset"],row["feature_group"]) not in ALLOWED_TABULAR_CPU:
            raise ValueError("Only registered official tabular primary groups may change execution backend")
        token="/job_"+str(old)
        if not row["folder"].endswith(token):raise ValueError("Original folder/source identity differs")
        seen[old]+=1;new=mapping[old]
        row.update(job=new,folder=row["folder"][:-len(token)]+"/job_"+str(new),
            zero_start_resource_reassignment_of_job=old,primary_execution_backend="CPU")
    if any(n!=1 for n in seen.values()):raise ValueError("Every original group must occur exactly once")
    return result

def failed_reporting_keys(manifest, accounting, expected_job):
    """Authorize only native closed, report-only failed TDC/ASAP task continuations."""
    if (str(manifest.get("job"))!=str(expected_job)
        or manifest.get("status")!="C1_Pprime_TABPFN_TDC_ASAP_CLOSED"
        or manifest.get("tasks_expected")!=23):
        raise ValueError("The exact original TDC/ASAP producer manifest is required")
    records=[line.strip().split("|") for line in accounting.splitlines()
             if line.strip().split("|")[0]==str(expected_job)]
    if len(records)!=1 or records[0][1:3]!=["COMPLETED","0:0"]:
        raise ValueError("The original native producer must actually be closed before continuation")
    failures=manifest.get("failures",[])
    if not failures or manifest.get("tasks_completed")+len(failures)!=23:
        raise ValueError("Every original task must have a closed success or explicit failure")
    keys=[]
    for row in failures:
        if (row.get("status")!="FIRST_ATTEMPT_FAILED" or row.get("error")!="KeyError('MAE')"
            or row.get("dataset") not in {"TDC_ADMET","ASAP_Polaris2025"} or not row.get("task")):
            raise ValueError("Only the actual pending-statistics official-MAE report error is covered")
        keys.append((row["dataset"],row["task"]))
    if len(set(keys))!=len(keys):raise ValueError("Duplicate failed task identities")
    return tuple(sorted(keys))

def prepare_failed_reporting_source(original, manifest, accounting, expected_job):
    keys=failed_reporting_keys(manifest,accounting,expected_job)
    source=defer_cpu_statistics(original)
    class Subset(ast.NodeTransformer):
        loops=0
        reports=0
        def visit_For(self,node):
            node=self.generic_visit(node)
            if (isinstance(node.target,ast.Name) and node.target.id=="endpoint"
                and ast.dump(node.iter,include_attributes=False)==ast.dump(ast.parse("sorted(coverage)",mode="eval").body,include_attributes=False)):
                self.loops+=1
                node.body=ast.parse("if (group,endpoint) not in _failed_report_task_keys:\n    continue\n").body+node.body
            return node
        def visit_Dict(self,node):
            node=self.generic_visit(node)
            for i,key in enumerate(node.keys):
                if isinstance(key,ast.Constant) and key.value=="status" and isinstance(node.values[i],ast.Constant) and node.values[i].value=="FIRST_ATTEMPT_FAILED":
                    node.values[i]=ast.Constant(value="UNRESOLVED_AFTER_ALLOWED_REPORT_REPAIR")
            return node
        def visit_Assign(self,node):
            node=self.generic_visit(node)
            if any(isinstance(t,ast.Name) and t.id=="report" for t in node.targets):
                if not isinstance(node.value,ast.Dict):raise ValueError("One registered report dictionary is required")
                matches=[i for i,k in enumerate(node.value.keys) if isinstance(k,ast.Constant) and k.value=="tasks_expected"]
                if len(matches)!=1:raise ValueError("One original report task count is required")
                node.value.values[matches[0]]=ast.Constant(value=len(keys));self.reports+=1
                node.value.keys += [ast.Constant(value=k) for k in ("continuation_of_native_job","failed_task_subset","successful_original_predictions_replayed","fixed_weight_context_inference","training_rollback")]
                node.value.values += [ast.Constant(value=int(expected_job)),ast.parse(repr(list(keys)),mode="eval").body,ast.Constant(value=False),ast.Constant(value=True),ast.Constant(value=False)]
            return node
    visitor=Subset();tree=visitor.visit(ast.parse(source))
    if (visitor.loops,visitor.reports)!=(1,1):raise ValueError("Exactly one registered task loop and report must be filtered")
    tree.body.insert(0,ast.parse("_failed_report_task_keys = "+repr(set(keys))).body[0])
    ast.fix_missing_locations(tree);result=ast.unparse(tree)+"\n"
    compile(result,"failed_reporting_tasks_only","exec")
    if model_calls(original)!=model_calls(result):raise ValueError("Failed-only continuation changed model configuration")
    return result,keys
