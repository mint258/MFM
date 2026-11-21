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
