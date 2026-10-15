"""Pure metadata checks: no datasets, models, schedulers, Slurm mutation or GPU."""
import ast,itertools,json,time
from pathlib import Path
from prepare import ROOT,save,sha
old=ast.parse((ROOT/'scripts/s_convergence_root_v2.py').read_text())
new=ast.parse((ROOT/'scripts/s_convergence_root_v3.py').read_text())
oldf={n.name:n for n in old.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
newf={n.name:n for n in new.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
for name in oldf:
    if name!='main':assert ast.dump(oldf[name])==ast.dump(newf[name]),name
scope={};exec(compile(ast.Module(body=[newf['choose_pending_condition']],type_ignores=[]),'<metadata-only>','exec'),scope)
choose=scope['choose_pending_condition']
names=['B1_seed0','B1_seed1','B3_seed0'];configs={n:{'epochs':3 if n=='B3_seed0' else 1} for n in names}
nodes=['compute-0-21','compute-0-20','compute-0-22'];cases=0
for states in itertools.product(['PENDING','ACTIVE','COMPLETE','ROOT_REPAIR_REQUIRED','GUIDE_SCIENTIFIC_STOP'],repeat=3):
    conditions={n:{'state':s,'consumed_records':6440960 if n=='B1_seed1' else 5800000} for n,s in zip(names,states)}
    for eligible in itertools.product([False,True],repeat=3):
        ready=[n for n in names if conditions[n]['state']=='PENDING'];initial=set(ready);assigned=[]
        for node,ok in zip(nodes,eligible):
            if not ok or not ready:continue
            chosen=choose(ready,node,conditions,configs)
            assert chosen in initial and chosen not in assigned
            if node=='compute-0-21' and 'B3_seed0' in ready:assert chosen=='B3_seed0'
            if node!='compute-0-21' and any(n.startswith('B1_') for n in ready):assert chosen.startswith('B1_')
            assigned.append(chosen);ready.remove(chosen)
        assert len(assigned)==min(len(initial),sum(eligible));cases+=1
binding=json.loads((ROOT/'formal_s/controller_binding_v2.json').read_text())
for ref in binding['sources']+binding['configurations']:assert sha(ref['path'])==ref['sha256']
assert binding['run_plan_sha256']==sha(ROOT/'formal_s/run_plan_v2.json')
out=ROOT/'formal_s/metadata_scheduling_v3_validation.json';assert not out.exists()
save(out,{'status':'PURE_METADATA_SCHEDULING_WORK_CONSERVATION_AND_UNCHANGED_SUBMISSION_GUARDS_PASS','timestamp':time.time(),'cases':cases,'unchanged_functions':[n for n in oldf if n!='main'],'old_controller_source_sha256':sha(ROOT/'scripts/s_convergence_root_v2.py'),'new_controller_source_sha256':sha(ROOT/'scripts/s_convergence_root_v3.py'),'scientific_sources_configs_and_run_plan_verified_unchanged':True,'no_new_scientific_updates_executed':True})
print('METADATA_SCHEDULING_PASS',cases,'UNCHANGED_RESOURCE_QUOTA_AND_SUBMISSION_GUARDS')
