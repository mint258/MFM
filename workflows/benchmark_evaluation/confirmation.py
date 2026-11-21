"""Prepare only approved neural confirmation fits, preserving original split/statistics seeds."""
import ast
from .selection import IncompleteComparison,SEED

REASONS=frozenset(("FINAL_SIGNIFICANT_IMPROVEMENT","TRAINING_ROLLBACK_REDO"))

def prepare_confirmation_source(source,learner,selected_tasks,*,default_dataset,reason):
    if learner not in ("Chemprop-v2","TabPFN") or reason not in REASONS:
        raise ValueError("A registered neural second-seed reason is required")
    selected=sorted(set((str(row["dataset"]),str(row["producer_task"])) for row in selected_tasks))
    if not selected or any(not dataset or not task for dataset,task in selected):
        raise ValueError("Original source dataset/task names are required")
    tree=ast.parse(source)
    def name_of(call):
        return call.func.id if isinstance(call.func,ast.Name) else call.func.attr if isinstance(call.func,ast.Attribute) else ""
    forbidden={"scaffold_folds","train_test_split","KFold","GroupKFold","StratifiedKFold","RepeatedKFold"}
    if any(isinstance(node,ast.Call) and name_of(node) in forbidden for node in ast.walk(tree)):
        raise IncompleteComparison("Confirmation sources must consume frozen original folds, not generate a split")
    class Adapter(ast.NodeTransformer):
        task_loops=0
        def visit_For(self,node):
            target_names={n.id for n in ast.walk(node.target) if isinstance(n,ast.Name)}
            fits=any(isinstance(n,ast.Call) and name_of(n) in {"train_predict","fit_predict","fit"}
                     for statement in node.body for n in ast.walk(statement))
            node=self.generic_visit(node)
            variables=target_names & {"task","endpoint","nucleus"}
            if fits and variables:
                if len(variables)!=1:raise IncompleteComparison("Ambiguous original task loop")
                variable=next(iter(variables))
                condition=ast.parse("if not __confirmation_included__(locals().get('group',__confirmation_default_dataset),"+variable+"): continue").body[0]
                node.body.insert(0,condition);self.task_loops+=1
            if target_names & {"fit_population","population"}:
                literals={e.value for e in ast.walk(node.iter) if isinstance(e,ast.Constant) and isinstance(e.value,str)}
                if {"retained","full"}.issubset(literals):
                    node.iter=ast.Tuple(elts=[ast.Constant(value="retained")],ctx=ast.Load())
            return node
        def visit_Call(self,node):
            node=self.generic_visit(node)
            callname=name_of(node)
            if callname in {"seed_everything","manual_seed","manual_seed_all"}:
                if node.args and isinstance(node.args[0],ast.Name) and node.args[0].id=="SEED":
                    node.args[0]=ast.Name(id="MODEL_SEED",ctx=ast.Load())
            for keyword in node.keywords:
                if keyword.arg=="random_state" or (callname=="dict" and keyword.arg in {"seed","random_seed","model_seed"}):
                    if isinstance(keyword.value,ast.Name) and keyword.value.id=="SEED":
                        keyword.value=ast.Name(id="MODEL_SEED",ctx=ast.Load())
            return node
        def visit_Dict(self,node):
            node=self.generic_visit(node)
            for index,key in enumerate(node.keys):
                if isinstance(key,ast.Constant) and key.value in {"seed","random_seed","model_seed"}:
                    value=node.values[index]
                    if isinstance(value,ast.Name) and value.id=="SEED":node.values[index]=ast.Name(id="MODEL_SEED",ctx=ast.Load())
            return node
        def visit_Assign(self,node):
            node=self.generic_visit(node)
            names={target.id for target in node.targets if isinstance(target,ast.Name)}
            if "report" in names:
                if isinstance(node.value,ast.Dict):
                    node.value.keys.append(ast.Constant(value="conditional_confirmation"))
                    node.value.values.append(ast.Name(id="__confirmation_declaration",ctx=ast.Load()))
                elif isinstance(node.value,ast.Call) and name_of(node.value)=="dict":
                    node.value.keywords.append(ast.keyword(arg="conditional_confirmation",value=ast.Name(id="__confirmation_declaration",ctx=ast.Load())))
            return node
    adapter=Adapter();tree=adapter.visit(tree)
    if adapter.task_loops!=1:
        raise IncompleteComparison("Expected one original model task loop; found "+str(adapter.task_loops))
    declaration=dict(model_seed=SEED+1,split_and_statistics_seed=SEED,reason=reason,
                     selected_original_tasks=selected,task_roster_reselection=False,
                     primary_fit_population_only=True,original_model_budget_unchanged=True)
    prelude=ast.parse("MODEL_SEED="+repr(SEED+1)+"\n"+
        "__confirmation_default_dataset="+repr(default_dataset)+"\n"+
        "__confirmation_selected=frozenset("+repr(selected)+")\n"+
        "__confirmation_declaration="+repr(declaration)+"\n"+
        "def __confirmation_included__(dataset,task):\n"+
        "    return (str(dataset),str(task)) in __confirmation_selected\n").body
    position=0
    while position<len(tree.body) and (
            isinstance(tree.body[position],ast.ImportFrom) and tree.body[position].module=="__future__"
            or isinstance(tree.body[position],ast.Expr) and isinstance(tree.body[position].value,ast.Constant)
               and isinstance(tree.body[position].value.value,str)):
        position+=1
    tree.body[position:position]=prelude;ast.fix_missing_locations(tree)
    result=ast.unparse(tree)+"\n"
    compile(result,"registered_neural_confirmation","exec")
    return result
