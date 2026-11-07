"""Explicit new compiled worker implementation; original scientific code object kept."""
import argparse
import functools
from pathlib import Path
import os
import sys
from types import FunctionType
from ..alpha_runtime_v1 import common as Q,profile
from ..exact_nn_cached_v1 import run as scientific
from . import authority,workers,namespace

MODULE='workflows.expansion.exact_nn_popcount_production_v1.entry'


def admit(plan_path,proof_path,module=MODULE):
    plan=Q.load(plan_path);proof=Q.load(proof_path);request=proof['request'];argv=plan['execution_argv']
    Q.need(all(r['bytes']<=2<<20 for r in plan['code_references']),'Code references must be small actual sources')
    actual=profile.admit(plan,minimum_workers=16)
    Q.need(proof['uid']==os.getuid()==actual['uid']==1264 and proof['endpoint']==plan['endpoint']==Q.ENDPOINT
        and str(proof['job_id'])==actual['job_id']==os.environ.get('SLURM_JOB_ID')
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and request['producer_plan_reference']==Q.reference(plan_path)and request['execution_argv']==argv
        and request['scope_key']==plan['scope_key']and len(argv)==9 and argv[0]==sys.executable
        and argv[1:3]==['-I','-B']and argv[4]==module
        and argv[5:]==sys.argv[1:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],'Actual Alpha plan/proof/boot/job and isolated entry argv required')
    refs=[Q.reference(p)for p in Path(__file__).parent.glob('*.py')]+[Q.reference(scientific.__file__),Q.reference(Path(argv[3]))]
    Q.need(all(r in plan['code_references']and r in request['source_references']for r in refs),'Every new production entry/worker and original run/guarded entry source pinned')
    return plan,actual,refs


def full_query(plan):
    Q.need(plan['schema']=='PUBCHEM_EXACT_CACHED_NN_PLAN_V1'and 'max_queries'not in plan,'Full pool only; no max_queries override')
    q=authority.read(plan['query_manifest'])
    Q.need(q['schema']=='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1'and q['status']=='COMPLETE'
        and q['fingerprint_recipe']==scientific.RECIPE and q['targets_present']is False and q['downstream_features_present']is False
        and type(q['projection']['rows'])is int and q['projection']['rows']>=10000000,'Closed full typed pool must cover at least10M queue candidates; no costpilot/sample/prefix')
    return q


def clone_run(batcher):
    original=scientific.run;globals_copy={**original.__globals__,'exact_batches':batcher}
    result=FunctionType(original.__code__,globals_copy,original.__name__,original.__defaults__,original.__closure__)
    result.__kwdefaults__=original.__kwdefaults__;result.__annotations__=original.__annotations__
    changes=[k for k in globals_copy if globals_copy[k]is not original.__globals__[k]]
    Q.need(result.__code__ is original.__code__ and changes==['exact_batches'],'Only native batch global may change; Guard/science code remains unchanged')
    return result


def execute(plan_path,proof_path):
    plan,actual,refs=admit(plan_path,proof_path);q=full_query(plan)
    adopted,packed=authority.adopted(plan['backend_adoption_reference'])
    integration,_=authority.integration(plan['worker_entry_actual_review_reference'],plan['backend_adoption_reference'])
    Q.need(plan['reference_manifest']==adopted['reference_manifest_reference'],'Only validated196 full Common reference')
    for name,binding in adopted['source_bindings'].items():
        if name=='run.py':Q.need(Q.reference(scientific.__file__)==binding['execution_reference'],'Exact original scientific run source must remain unchanged')
    scientific.allocation_guard(plan)
    out=Path(plan['output_directory']);guard=scientific.Guard(plan,out);guard.poll(True,1<<20)
    value=namespace.binding(plan,adopted,q);lock,marker,resume_ref=namespace.establish(plan,value)
    try:
        batcher=functools.partial(workers.exact_batches,backend_adoption_reference=plan['backend_adoption_reference'])
        run=clone_run(batcher);result=run(plan_path)
        Q.need(result['status']=='COMPLETE'and result['queries']==q['projection']['rows']
            and result['reference_molecules']==authority.N,'Original complete typed full-pool final gate remains mandatory')
        metrics=Path(result['worker_metrics']['path']);suffix='.workers.jsonl'
        Q.need(metrics.parent==out and metrics.name.endswith(suffix),'Actual original scientific receipt suffix required')
        original_receipt=out/(metrics.name[:-len(suffix)]+'.receipt.json')
        Q.need(Q.load(original_receipt)==result,'Bind actual closed original scientific receipt without rewriting it')
        wrapper=out/(metrics.name[:-len(suffix)]+'.compiled_backend_wrapper.json')
        guard.poll(True,1<<20)
        return Q.write(wrapper,dict(schema='ALPHA_COMPILED_FULL_POOL_EXECUTION_METADATA_V1',
            status='FULL_POOL_EXECUTION_COMPLETE_PENDING_ROOT_ACTUAL_C0_REVIEW',actual_parent=actual,
            original_scientific_receipt_reference=Q.reference(original_receipt),backend_adoption_reference=plan['backend_adoption_reference'],
            worker_entry_actual_review_reference=plan['worker_entry_actual_review_reference'],build_manifest_reference=adopted['build_manifest_reference'],
            binary_reference=adopted['binary_reference'],cache_namespace_manifest_reference=marker,resume_actual_review_reference=resume_ref,
            original_run_code_object_preserved=True,only_injected_global='exact_batches',RDKit_nearest_engine_used=False,
            native_worker_source_reference=Q.reference(workers.__file__),source_references=refs,
            plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(proof_path),
            actual_worker_pids_this_attempt=result['worker_pids_observed'],new_distinct_queries_this_attempt=result['new_distinct_queries_computed_this_attempt'],
            no_automatic_scientific_retry=True,production_or_training_release_automatically_approved=False))
    finally:lock.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();execute(a.plan,a.startup_proof)


if __name__=='__main__':main()
