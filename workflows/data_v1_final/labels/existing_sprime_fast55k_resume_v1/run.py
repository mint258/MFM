"""Same original fast55k execute code with only explicit private IO bindings."""
import argparse,os,types
from pathlib import Path
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import run as ORIGINAL
I=ORIGINAL.I
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
def execute(plan,proof,root,gate,budget):
    old=ORIGINAL.execute;namespace=dict(old.__globals__,C=C,G=G,V=G.COVERAGE)
    function=types.FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__);function.__kwdefaults__=old.__kwdefaults__
    C.need(function.__code__ is old.__code__ and G.build is ORIGINAL.G.build and G.cohort is ORIGINAL.G.cohort
      and G.metadata_children is ORIGINAL.G.metadata_children and G.STATISTICS is ORIGINAL.T and G.ELIGIBILITY is ORIGINAL.E,
      'ORIGINAL_GEOMETRY_SELECTION_171GROUP_MATH_AND_INDEPENDENT_TRAIN_ROUTE_OBJECTS')
    return function(plan,proof,root,gate,budget)
def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--plan',required=True);a.add_argument('--startup-proof',required=True);a=a.parse_args()
    plan=C.plan(C.meta(C.P.pin(a.plan)));plan=dict(plan,plan_path=a.plan,startup_proof_path=a.startup_proof)
    proof=require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=plan['scope_parameters'],expected_kind='analysis',
      expected_source=Path(__file__),expected_execution_argv=[C.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof],
      required_references=[C.P.pin(a.plan),*plan['source_references']])
    C.need(proof['request']['cpus']==16 and proof['request']['node']==plan['node'] and proof['request']['wall_seconds']==86400
      and proof['request']['estimated_peak_output_bytes']==plan['whole_output_cap_bytes'] and proof['request']['pilot']is False
      and proof['request']['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and {r['path']:r for r in proof['request']['data_references']}=={r['path']:r for r in plan['data_references']},'REAL16CPU_CURRENT_PARENT_SCOPE')
    C.need(all(os.environ.get(k)=='1'for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'SINGLE_LIBRARY_THREADS')
    I.configure(plan);root=I.new_root(plan['output_directory']);budget=None
    try:
        gate=ORIGINAL.fixtures(root);I.configure(plan);budget=G.ResourceBudget(plan,proof,root);budget.check(force=True)
        ref=execute(plan,proof,root,gate,budget);return 1 if I.load_data(ref,8<<20)['held']else 0
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':raise SystemExit(main())
