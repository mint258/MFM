"""Change only concurrency and private paths; preserve the v3 exact kernels."""
import pathlib,types
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v3 import runtime as V3
P=V3.P;C=P.C;WORKERS=16
fixtures=V3.fixtures

class FreshMemoryBinding(P.MemoryBinding):
    def start_observer(self,proof,binding):
        return P.I.R.start_observer(proof,dict(binding,resource_evidence_output=
            str(P.ROOT)+'_stats_resume_v4_resource_observation'))

def configure(root,admin,origin):
    P.ROOT=root;P.ADMIN=admin;P.ORIGIN=origin;P.MemoryBinding=FreshMemoryBinding
    V3.H.WORKERS=WORKERS

def continuation_function(*args):
    original=P.continuation_function
    old="statsroot=root/'statistics_resume_v1';statsroot.mkdir()"
    new="statsroot=root/'statistics_resume_v4';statsroot.mkdir()"
    C.need(original.__code__.co_consts.count(old)==1,'ONE_PRIVATE_STATISTICS_DIRECTORY')
    code=original.__code__.replace(co_consts=tuple(new if v==old else v for v in original.__code__.co_consts))
    function=types.FunctionType(code,dict(original.__globals__,Statistics=V3.Statistics),
        original.__name__,original.__defaults__,original.__closure__)
    execute=function(*args);execute.__globals__['next_route']=V3.next_route
    return execute

def reconfiguration(envelope,origin):
    review=C.meta(envelope['concurrency16_continuation_reference'])
    exit=C.meta(review['prior_statistics_exit_reference'])
    proof=C.meta(review['prior_statistics_proof_reference'])
    receipt=C.meta(review['prior_statistics_receipt_reference'])
    stop=C.meta(review['actual_soft_stop_reference']);gate=C.meta(receipt['fixture_gate'])
    C.need(review['schema']=='ROOT_D4_SAFE_STATISTICS_CONCURRENCY_CONTINUATION_V1'
      and review['reviewer']=='root'and review['workers_before']==8 and review['workers_after']==WORKERS
      and review['scientific_methods_or_quality_rules_changed']is False
      and review['completed_group_reports_regenerated']is False and review['new_QM_UFF_calls']==0,
      'RESOURCE_ONLY_EIGHT_TO_SIXTEEN_WORKERS')
    C.need(exit['exit_code']==1 and exit['actual_pid']==proof['pid']
      and str(exit['actual_start_ticks'])==str(proof['start_ticks'])
      and receipt['startup_proof_reference']==review['prior_statistics_proof_reference']
      and receipt['checkpoint_reference']==origin['actual_checkpoint_reference']
      and receipt['held']is False and receipt['errors']==[]and receipt['numeric_repetitions']==[]
      and gate['status']=='PASS'and gate['tests']==6 and gate['errors']==gate['failures']==0,
      'REAL_CLOSED_PARTIAL_NOT_QUALITY_FAILURE_OR_COMPLETE_DELIVERY')
    C.need(proof['uid']==1278 and proof['node']=='sonmi'and proof['Slurm_job_id']is None
      and not pathlib.Path('/proc/'+str(proof['pid'])).exists(),
      'REAL_PREVIOUS_PROCESS_ABSENT_NO_DUPLICATE')
    C.need(stop['reason']=='ROOT_REQUESTED_D4_SAFE_CONCURRENCY_8_TO16'
      and stop['observation']['actual_pid']==proof['pid']and stop['forced_signals_sent']is False,
      'EXPLICIT_ROOT_NATURAL_DRAIN_NOT_FALSE_RESOURCE_PRESSURE')
    return review
