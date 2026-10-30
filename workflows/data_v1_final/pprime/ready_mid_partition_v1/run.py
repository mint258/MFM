"""One actual generic16 Parent: Source3 then immutable ready-MID assignment."""
import argparse,io,json,pathlib,re,types,unittest
from . import contract as C,planner as P
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.io import Store
def fixtures(root,store):
    from . import test_v1
    test_v1.WORKSPACE=root;suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries)
    C.need(suite.countTestCases()==3,'EXACT_THREE_SAME_PARENT_PLANNER_BOUNDARIES');log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    ref=store.json(root/'Source3.json',{'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
      'skipped':len(result.skipped),'transcript':log.getvalue(),'native_init_invoke_calls':0,'scientific_DATA_read':False})
    C.need(result.wasSuccessful()and result.testsRun==3 and not result.skipped,'PLANNER_SOURCE3_FAILED_NO_DATA');return ref
def observer_binding(plan,proof,out,binding):
    """Only observer metadata moves; the scientific root/cap never changes."""
    root=pathlib.Path(out);partition=plan['partition_id'];job=str(proof['job_id'])
    C.need(root==pathlib.Path(plan['output_directory'])and root.parent==C.ROOT/'artifacts/pprime_ready_mid_partition_v1'
      and type(partition)is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',partition)
      and job.isascii()and job.isdecimal()and str(int(job))==job and int(job)>0,
      'EXACT_ACTUAL_PLANNER_ROOT_SAFE_PARTITION_AND_JOB_RESOURCE_PATH')
    C.need(binding['resource_evidence_output']==str(root)+'_resource_observation','ONLY_ORIGINAL_OBSERVER_OUTPUT_BINDING_ADAPTED')
    target=C.ROOT/'artifacts/labels/source_status_v1/_pprime_partition_resource'/(partition+'_j'+job)
    C.need(not any(p.is_symlink()for p in(target,*target.parents)),'NO_RESOURCE_OBSERVER_DIRECTORY_SYMLINK')
    return dict(binding,resource_evidence_output=str(target))
class ObserverMetadataRoute:
    def __init__(self,original,plan,proof,out):self.original,self.plan,self.proof,self.out=original,plan,proof,out
    def __getattr__(self,name):return getattr(self.original,name)
    def start_observer(self,proof,binding):
        C.need(proof==self.proof,'SAME_ACTUAL_PLANNER_OBSERVER_PROOF')
        return self.original.start_observer(proof,observer_binding(self.plan,proof,self.out,binding))
def observer_constructor(plan,proof,out):
    """Original entire constructor; private R.start_observer routing only."""
    source=C.Resource.Budget.__init__;namespace=dict(source.__globals__);original_factory=namespace['private_io_function']
    def private_factory(original,*args,**kwargs):
        function=original_factory(original,*args,**kwargs)
        if original is C.Resource.B.Budget.__init__:
            scope=dict(function.__globals__);scope['R']=ObserverMetadataRoute(scope['R'],plan,proof,out)
            routed=types.FunctionType(function.__code__,scope,function.__name__,function.__defaults__,function.__closure__)
            routed.__kwdefaults__=function.__kwdefaults__;return routed
        return function
    namespace['private_io_function']=private_factory
    routed=types.FunctionType(source.__code__,namespace,source.__name__,source.__defaults__,source.__closure__)
    routed.__kwdefaults__=source.__kwdefaults__;return routed
class Budget:
    """Existing frozen resource object; positional IO check adapter only."""
    def __init__(self,plan,proof,out):
        cfg=dict(plan,cache_transitive_output_origins=[],accepted_prior_output_roots=[])
        C.Resource.B.configure(cfg);self.original=C.Resource.Budget.__new__(C.Resource.Budget)
        observer_constructor(plan,proof,out)(self.original,plan,proof,out)
    def check(self,dispatch=True,force=False):return self.original.check(dispatch=dispatch,force=force)
    def close(self):return self.original.close()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--startup-proof',required=True);a=parser.parse_args()
    plan=C.validate(C.meta(C.Q.pin(a.plan)))
    proof=require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.parameters(plan),
      expected_kind='analysis',expected_source=C.HERE/'run.py',expected_execution_argv=[C.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof],
      required_references=[C.Q.pin(a.plan),*plan['source_references']])
    C.need(proof['request']['cpus']==16 and proof['request']['node']==plan['node'] and proof['request']['wall_seconds']==86400
      and proof['request']['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'and proof['request']['pilot']is False
      and proof['request']['estimated_peak_output_bytes']==plan['whole_output_cap_bytes']
      and proof['request']['data_references']==plan['data_references'],'REAL_GENERIC16_NO_MEM_EXACT_PLANNER_DATA')
    out=pathlib.Path(plan['output_directory']);C.need(not out.exists()and not any(p.is_symlink()for p in(out,*out.parents)),'FRESH_PLANNER_OUTPUT_ONLY')
    out.mkdir(parents=True);store=Store(out,plan['whole_output_cap_bytes']-(512<<20));budget=None
    try:
        gate=fixtures(out,store)
        for ref in C.sources():C.need(ref in proof['request']['source_references'],'ALL_CURRENT_RUNTIME_SOURCE_PINS')
        budget=Budget(plan,proof,out);budget.check(force=True);qa=P.build(plan,proof,out,budget,store);budget.check(force=True,dispatch=False)
        store.json(out/'receipt.json',{'schema':'PPRIME_READY_MID_PARTITION_RECEIPT_V1','status':'CPU_ASSIGNMENTS_CLOSED_REQUIRES_ACTUAL_C0_AND_ROOT_REVIEW',
          'job_id':str(proof['job_id']),'uid':1278,'node':plan['node'],'plan_reference':C.Q.pin(a.plan),'startup_proof_reference':C.Q.pin(a.startup_proof),
          'Source3_reference':gate,'partition_QA_reference':qa,'native_init_invoke_calls':0,'active_DB_read':False,'actual_once_writes':0,
          'scientific_or_Model_or_generation_release':False,'charged_closed_output_bytes':store.charged})
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':main()
