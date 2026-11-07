"""Readonly close/index with complete initial-resource failure diagnostics."""
from __future__ import annotations
import argparse,pathlib,sys,traceback
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import contract as C,runtime_io as R
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1.close_index import terminal_batch,completion
from workflows.data_v1_final.conformers.formal_cpu_auto_close_index_v2 import admission as OLD_A
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import quota_edge as A
OPTIONS=('config','root-preflight','quota-reuse-review','descriptor','catalog','output')
FILES=C.FILES


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('close',))
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=name in {'config','root-preflight','quota-reuse-review','output'})
    args=p.parse_args();value,proof,session,config_ref=R.admit(__file__,args,args.mode,OPTIONS)
    here=pathlib.Path(__file__).absolute().parent;R.authorized(proof,[C.ref(here/n) for n in FILES])
    C.need(C.source_inverse_proof()['inverse_bytes_and_AST_equal'] is True,'UNCHANGED_TERMINAL_CLASSIFICATION_AND_INDEX')
    R.new_output_directory(args.output,value);budget=None;attempts=[];failure=None;initial=None
    try:
        def save(row):
            attempts.append(row);R.write_json_new(R.OUT/('initial_quota_attempt_%02d.json'%len(attempts)),row)
        A.strict_preprobe(proof,session,save)
        budget=R.Budget(proof,session,value,R.OUT)
        initial=budget.observe()
        R.write_json_new(R.OUT/'initial_budget_observation.json',{'stop':initial,'report':budget.report()})
        C.need(initial is None,'FRESH_SHARED_ACCOUNT_QUOTA_REQUIRED')
        budget.start_monitor()
        if args.mode=='close':terminal_batch(C.read(R.input_ref(args.root_preflight,args.descriptor)),config_ref,value,proof)
        else:completion(C.read(R.input_ref(args.root_preflight,args.catalog)),config_ref,value,proof)
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()};raise
    finally:
        if budget is not None:budget.close_monitor()
        R.write_json_new(R.OUT/'resource_observations.json',{'schema':'ACTUAL_CLOSE_INITIAL_AND_FINAL_RESOURCE_OBSERVATIONS_V2',
            'job_id':str(proof['job_id']),'startup_proof_reference':C.ref(args.root_preflight),'new_source_references':[C.ref(here/n) for n in FILES],
            'initial_quota_attempts':attempts,'initial_budget_stop':initial,'budget_constructed':budget is not None,
            'budget':budget.report() if budget is not None else None,'failure':failure,'freshness_relaxed':False,
            'latched_budget_stop_cleared':False,'resource_signals_sent':False,'new_UFF_QM_calls':0,
            'old4521632_initial_failure_cause':'UNKNOWN_OLD_REPORT_NOT_WRITTEN','scientific_quality_release':False})


if __name__=='__main__':main()
