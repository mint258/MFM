"""Original formal execute code with private closed-input and resource bindings."""
import argparse,multiprocessing as mp,os,pathlib,sys,traceback,types
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from workflows.data_v1_final.pprime.formal_packed_day_v1 import run as Old
from . import contract as C,adopt as P,io as I
Q=C.Q

def execute(plan,proof,out,store,budget,roles,event,b):
    state=dict(Old.__dict__);state.update(P=P,I=I.execution_io(b['adoption']['header']['index_reference'],out))
    original=Old.execute
    run=types.FunctionType(original.__code__,state,original.__name__,original.__defaults__,original.__closure__)
    run.__kwdefaults__=original.__kwdefaults__
    C.need(run.__code__ is original.__code__ and state['worker'] is Old.worker and state['C'] is Old.C
      and Old.P is not P and Old.I is I.Old and state['I'] is not Old.I,
      'ENTIRE_ORIGINAL_EXECUTE_WORKER_SCIENCE_AND_GLOBAL_ONCE_WITH_PRIVATE_IO_ONLY')
    return run(plan,proof,out,store,budget,roles,event,b)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.meta(Q.pin(a.plan));params=C.parameters(plan['node'])
    C.need(plan['schema']=='PPRIME_FORMAL_PACKED_DAY_PLAN_V1' and plan['scope_parameters']==params,'EXACT_CLOSED_PREPARATION_RESUME_PLAN')
    b=C.bootstrap(plan);C.need(plan['data_references']==b['data'],'EXACT_ORIGINAL_PLUS_ADOPTED_CLOSED_DATA_LOCATORS')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof]
    proof=require_startup(a.startup_proof,expected_kind='qm',expected_scope_key=C.KEY,expected_scope_parameters=params,
      expected_execution_argv=argv,expected_source=C.HERE/'run.py',required_references=[Q.pin(a.plan),*plan['source_references']])
    req=proof['request'];C.need(req['node']==plan['node'] and req['cpus']==16 and req['wall_seconds']==C.WALL and req['pilot'] is False
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP
      and req['data_references']==b['data'],'ACTUAL_FRESH_CPU16_DAY_ORIGINAL64G_CAP_NO_MEM')
    C.precision(plan,C.meta(req['scope']['review']))
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py'
      and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'PRIMARY_MODULE_FULL_ARGV')
    for ref in C.sources(plan):C.need(ref in req['source_references'],'ORIGINAL_SCIENTIFIC_AND_PRIVATE_ADAPTER_SOURCE_PINS')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';out=C.M.fresh(plan['output_directory'],'artifacts')
    C.need(C.BASE in out.parents and out!=C.OLD_OUTPUT,'FRESH_ORIGINAL_FORMAL_OUTPUT_ROOT');out.mkdir(parents=True,mode=0o700)
    Old.source_boundary.verify_sources();Old.fixtures(out)
    store=I.Store(out,4<<30);roles=I.Roles();event=mp.get_context('spawn').Event();budget=I.Budget(plan,proof,out,roles,store)
    plan=dict(plan,plan_path=a.plan,proof_path=a.startup_proof)
    try:
        budget.check(force=True);result=execute(plan,proof,out,store,budget,roles,event,b)
        return 0 if not C.meta(result)['failures'] else 3
    except BaseException as exc:
        event.set();store.json(out/'failure.DATA.json',{'error':repr(exc),'traceback':traceback.format_exc(),
          'old_failed_parent_preserved':True,'all_consumed_once_outcomes_preserved':True,'automatic_native_retry':False});raise
    finally:budget.check(dispatch=False,force=True)

if __name__=='__main__':raise SystemExit(main())
