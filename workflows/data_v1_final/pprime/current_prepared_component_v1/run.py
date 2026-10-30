"""Exact v3 execution/main with isolated component admission and same workers/once."""
import types
from . import contract as C,authority as A
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import run as Original,io as OldIO
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import worker

def private_function(old,**bindings):
    namespace=dict(old.__globals__,**bindings);result=types.FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__)
    result.__kwdefaults__=old.__kwdefaults__;return result

class Budget(OldIO.Budget):
    def __init__(self,*args,**kwargs):return private_function(OldIO.Budget.__init__,C=C)(self,*args,**kwargs)
class IO:
    Budget=Budget
    def __getattr__(self,name):return getattr(OldIO,name)
I=IO()

def execution(plan,proof,out,local,b,store,budget,event):
    qa=A.verify_component(plan,proof,budget)
    store.json(out/'closed_component_independent_CPU_QA.json',qa)
    # This is the exact original execution body, not a second engine or once domain.
    function=private_function(Original.execution,C=C)
    return function(plan,proof,out,local,b,store,budget,event)

def fixtures(out):
    from . import test_v1
    import io,unittest
    test_v1.WORKSPACE=out;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries)
    C.need(suite.countTestCases()==3,'SAME_THREE_SOURCE_METHODS_NOT_NEW_QM_DIAGNOSTICS')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=C.Q.write_new(out/'source3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
      'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
      'before_DATA_Native':True,'original_worker_inverse':worker.inverse(),'component_does_not_claim_prep_parent_C0':True})
    C.need(r.wasSuccessful()and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED');return ref

def main():return private_function(Original.main,C=C,I=I,execution=execution,fixtures=fixtures)()
if __name__=='__main__':raise SystemExit(main())
