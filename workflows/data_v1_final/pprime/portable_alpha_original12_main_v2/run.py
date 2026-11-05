"""Actual Main CPU16 component export; never acquire production claims."""
import argparse,os,pathlib,sys,traceback
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
from . import contract as C,io as I,packets
Q=C.Q

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.meta(Q.pin(a.plan));b=C.bootstrap(plan);params=C.parameters(plan)
    C.need(plan['schema']=='PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_PLAN_V1' and plan['scope_parameters']==params
      and plan['data_references']==b['data'],'EXACT_DECLARED_CURRENT_COMPONENT_PORTABLE_EXPORT')
    argv=[Q.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof]
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=C.KEY,expected_scope_parameters=params,
      expected_execution_argv=argv,expected_source=C.HERE/'run.py',required_references=[Q.pin(a.plan),*plan['source_references']])
    req=proof['request'];review=C.meta(req['scope']['review'])
    C.need(req['node']==plan['node'] and req['cpus']==16 and req['wall_seconds']==plan['wall_seconds']==C.WALL
      and req['pilot'] is False and req['data_references']==plan['data_references']
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and req['estimated_peak_output_bytes']==plan['output_cap_bytes']
      and review['portable_original12_export_authorized'] is True and review['native_invocations_authorized'] is False
      and review['preclaim_authorized'] is False,'ACTUAL_NO_QM_NO_CLAIM_EXPORT_PARENT')
    C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py'
      and sys.argv==[str(C.HERE/'run.py'),*argv[4:]],'PRIMARY_EXACT_EXPORT_ENTRY')
    for ref in C.sources(plan):C.need(ref in req['source_references'],'FROZEN_ORIGINAL_AND_NEW_EXPORT_SOURCE')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';out=C.M.fresh(plan['output_directory'],'artifacts')
    C.need(C.BASE in out.parents,'FRESH_PORTABLE_EXPORT_ROOT');out.mkdir(parents=True,mode=0o700)
    from workflows.data_v1_final.pprime.formal_packed_day_v1 import run as OriginalRun
    OriginalRun.source_boundary.verify_sources();fixture=OriginalRun.fixtures(out)
    store=I.Store(out,plan['output_cap_bytes']-(2<<20));budget=I.Budget(plan,proof,out,store)
    plan=dict(plan,plan_path=a.plan,proof_path=a.startup_proof)
    try:
        budget.check(force=True);result=packets.execute(plan,proof,out,b,store,budget)
        store.json(out/'receipt.json',{'schema':'PPRIME_ALPHA_PORTABLE_MAIN_EXPORT_RECEIPT_V1','job_id':str(proof['job_id']),
          'uid':1278,'node':plan['node'],'plan_reference':Q.pin(a.plan),'startup_proof_reference':Q.pin(a.startup_proof),
          **result,'Source3_reference':fixture,'resource_report':budget.report(),'scientific_PASS':False,'final_Common_or_training_admission':False})
    except BaseException as exc:
        store.json(out/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'preserve_all_outputs':True,
          'production_claims_created':0,'automatic_native_retry':False});raise
    finally:budget.check(dispatch=False,force=True)

if __name__=='__main__':main()
