"""Same original fast55k execute code with only explicit private IO bindings."""
import argparse,os,types,sys,unittest,io
from pathlib import Path
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import run as ORIGINAL
I=ORIGINAL.I;B=ORIGINAL.B

def fixtures(root):
    from . import test_boundaries
    from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import source_inverse
    from workflows.data_v1_final.labels.common_train_normalization_day_v1 import test_boundaries as original
    import subprocess
    checker=C.REPO/'tools/check_repository.py';C.need(C.P.pin(checker)in I.ALLOWED.values(),'EXACT_ORIGINAL_REPOSITORY_CHECKER_SOURCE')
    checked=subprocess.run([sys.executable,'-B',str(checker)],cwd=str(C.REPO),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    C.need(len(checked.stdout)+len(checked.stderr)<=2<<20,'BOUNDED_COMPLETE_REPOSITORY_CHECKER_TRANSCRIPT')
    I.save(root/'repository_checker.json',{'returncode':checked.returncode,'stdout':checked.stdout.decode('utf-8','replace'),'stderr':checked.stderr.decode('utf-8','replace'),'actual_same_parent_before_DATA':True,'checker_reference':C.P.pin(checker)})
    # Repository commits stay blocked if this optional node lacks git. The
    # mandatory original/native scientific source tests below still run.
    missing_git=checked.returncode!=0 and b"No such file or directory: 'git'" in checked.stderr
    if missing_git:I.save(root/'repository_check_deferred.json',{'status':'UNRESOLVED_NODE_GIT_ABSENT_COMMIT_BLOCKED','scientific_source_tests_still_required':True,'checker_pass_claimed':False})
    else:C.need(checked.returncode==0,'ORIGINAL_REPOSITORY_CHECKER_FAILED_NO_DATA')
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (original.Boundaries,test_boundaries.Boundaries)])
    C.need(suite.countTestCases()==6,'EXACT_ORIGINAL3_AND_NEW3_IN_ONE_PARENT_BEFORE_DATA_AND_BUDGET')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=I.save(root/'preflight.json',{'schema':'EXISTING_SPRIME_PILOT_SIX_BOUNDARIES_V1',
        'status':'PASS' if result.wasSuccessful() and result.testsRun==6 and not result.skipped else 'FAIL_NO_DATA',
        'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'transcript':stream.getvalue(),
        'source_inverse':source_inverse.proof(),'original_objects':B.verify(),'scientific_DATA_read':False})
    C.need(result.wasSuccessful() and result.testsRun==6 and not result.skipped,'SIX_BOUNDARIES_FAILED_NO_DATA');return ref


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
        gate=fixtures(root);I.configure(plan);budget=G.ResourceBudget(plan,proof,root);budget.check(force=True)
        ref=execute(plan,proof,root,gate,budget);return 1 if I.load_data(ref,8<<20)['held']else 0
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':raise SystemExit(main())
