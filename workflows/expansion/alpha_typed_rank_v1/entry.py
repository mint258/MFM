"""Native Alpha proof+CPP full-pool gate, direct original rank, closed N audit."""
import argparse
import os
import sys
from pathlib import Path
from ..alpha_runtime_v1 import common as Q,profile
from ..alpha_runtime_v1.guard import Guard
from ..exact_nn_cached_v1 import typed_rank as original
from . import authority,closed_N_audit

MODULE='workflows.expansion.alpha_typed_rank_v1.entry'


def execute(plan_path,proof_path):
    plan=Q.load(plan_path);proof=Q.load(proof_path);actual=profile.admit(plan,minimum_workers=16);request=proof['request']
    Q.need(plan['schema']=='PUBCHEM_TYPED_EXACT_RANK_PLAN_V1'and plan['scope_key']=='alpha_typed_rank_closed_N_v1'
      and proof['uid']==actual['uid']==os.getuid()==1264 and proof['endpoint']==actual['endpoint']==Q.ENDPOINT
      and str(proof['job_id'])==actual['job_id']==os.environ.get('SLURM_JOB_ID')
      and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
      and request['producer_plan_reference']==Q.reference(plan_path)and request['execution_argv']==plan['execution_argv']
      and request['scope_key']==plan['scope_key']and len(plan['execution_argv'])==9 and plan['execution_argv'][0]==sys.executable
      and plan['execution_argv'][1:3]==['-I','-B']and plan['execution_argv'][4]==MODULE
      and plan['execution_argv'][5:]==sys.argv[1:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],
      'Actual Alpha plan/Slurm/source startup proof required')
    paths=[*Path(__file__).parent.glob('*.py'),Path(original.__file__),Path(original.create_queues.__code__.co_filename)]
    Q.need(all(Q.reference(p)in request['source_references']and Q.reference(p)in plan['code_references']for p in paths),
      'Actual new entry/audit and unchanged original rank/queue source pins required')
    deployment=authority.read(plan['rank_deployment_reference']);executed=authority.deployed(deployment)
    Q.need(Q.reference(original.__file__)==executed['typed_rank.py']
      and Q.reference(Path(original.create_queues.__code__.co_filename))==executed['external_sort.py'],
      'Imported original bodies must be the real colocated rank capsule before large work')
    from .. import exact_nn_cached_v1 as package
    namespace=authority.read(deployment['rank_namespace_manifest_reference'])
    Q.need(list(package.__path__)==namespace['exact_nn_cached_v1_search_paths']
      and namespace['namespace_source_reference']in request['source_references'],
      'Actual package search order/source must match explicit capsule namespace and startup pins')
    chosen=authority.partition(plan['storage_partition_actual_review_reference'],plan['storage_partition_key'])
    for key in ('output_scope_root','output_cap_bytes','other_future_reserved_bytes','minimum_free_bytes'):
        Q.need(plan[key]==chosen[key],'Exact chosen private storage partition binding')
    out=Path(plan['output_directory']);scope=Path(plan['output_scope_root'])
    Q.need(out.is_absolute()and scope in out.parents and not out.exists()
      and 0<plan['sql_memory_bytes']<plan['parent_rss_cap_bytes']<=plan['software_rss_budget_bytes'],
      'Fresh private rank attempt and actual SQL/tree budget required')
    wrapper,native,query=authority.inputs(plan['compiled_execution_wrapper_reference'],plan['compiled_full_pool_actual_review_reference'])
    Q.need(plan['novelty_receipt']==wrapper['original_scientific_receipt_reference'],'Original rank consumes original scientific receipt, not CPP wrapper')
    guard=Guard(plan);lock=None
    try:
        out.mkdir(parents=True)
        import fcntl
        lock=(out/'entry.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Direct call; no FunctionType/private globals, no changes to old files.
        rank=original.run(plan_path)
        audit_ref,audit=closed_N_audit.audit(rank,plan,out/'closed_N_audit',guard.check)
        success=audit['strict_N_order_independent_of_query_row_order']
        result=Q.write(out/'alpha_rank_execution_wrapper.json',dict(schema='ALPHA_TYPED_RANK_WITH_CLOSED_N_AUDIT_V1',
          status='COMPLETE_PENDING_ACTUAL_C0_AND_ROOT_REVIEW'if success else'REJECT_STRICT_SAME_N_CLAIM_DUPLICATE_TUPLES',
          original_rank_receipt_reference=Q.reference(out/'receipt.json'),closed_N_audit_reference=audit_ref,
          original_typed_rank_directly_called=True,original_create_queues_modified=False,
          original_rank_source_bindings=deployment['original_rank_source_bindings'],
          compiled_execution_wrapper_reference=plan['compiled_execution_wrapper_reference'],
          compiled_full_pool_actual_review_reference=plan['compiled_full_pool_actual_review_reference'],
          storage_partition_actual_review_reference=plan['storage_partition_actual_review_reference'],
          strict_same_N_claim_pending_Root_actual_review=success,queue_UFF_or_training_release=False,
          actual_parent=actual,plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(proof_path),runtime=guard.receipt()))
        Q.need(success,'Complete original N sorting tuple has duplicates; preserve ranking/audit, do not add a tie rule')
        return result
    finally:
        if lock is not None:lock.close()
        guard.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();execute(a.plan,a.startup_proof)


if __name__=='__main__':main()
