"""Unchanged terminal classifier with actual per-node resources and failure facts."""
import argparse,pathlib,sys,traceback
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.sprime_multinode_resource_v2 import contract as C,runtime_io as R,edge as E
from workflows.data_v1_final.conformers.sprime_multinode_resource_v2.close_index import terminal_batch
OPTIONS=('config','root-preflight','quota-reuse-review','descriptor','output')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('close',))
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args();value,proof,session,cr=R.admit(__file__,a,'close',OPTIONS);C.source_inverse_proof();R.new_output_directory(a.output,value)
    budget=None;initial=None;attempts=[];failure=None
    try:
        E.strict_preprobe(proof,session,lambda row:(attempts.append(row),R.write_json_new(R.OUT/('quota_preprobe_%02d.json'%len(attempts)),row)))
        budget=R.Budget(proof,session,value,R.OUT);initial=budget.observe();C.need(initial is None,'FRESH_ACTUAL_QUOTA_BEFORE_TERMINAL_READBACK');budget.start_monitor()
        terminal_batch(C.read(R.input_ref(a.root_preflight,a.descriptor)),cr,value,proof)
    except BaseException as exc:failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()};raise
    finally:
        if budget is not None:budget.close_monitor()
        R.write_json_new(R.OUT/'resource_observations.json',{'schema':'ACTUAL_MULTINODE_CLOSE_RESOURCES_V2','job_id':str(proof['job_id']),
            'startup_proof_reference':C.ref(a.root_preflight),'initial_quota_attempts':attempts,'initial_budget_stop':initial,
            'budget':budget.report() if budget else None,'failure':failure,'freshness_relaxed':False,'latched_budget_stop_cleared':False,'new_UFF_QM_calls':0,'scientific_quality_release':False})
if __name__=='__main__':main()
