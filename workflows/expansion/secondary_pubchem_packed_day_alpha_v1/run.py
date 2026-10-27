"""Original group with only resource STOP-event removal for natural drain."""
import argparse,copy,json,multiprocessing as mp,os,time,traceback
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import run as ORIGINAL,source,kernel,journal,materialize_shards
from . import contracts as C,runtime as R
from .resource import require_startup
scientific=ORIGINAL.scientific;differences=ORIGINAL.differences

def run_group(pool,records,group,out,budget,worker_stop,reference=None):
    writer=journal.Writer(out,group,budget);pending=deque();seen=compared=mismatches=0
    detail=(out/(group+'.comparison.jsonl')).open('xb') if reference is not None else None
    def collect():
        nonlocal compared,mismatches
        original,future=pending.popleft();error=None
        try:value=future.result()
        except Exception as exc:value=None;error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        value=writer.complete(original,value,error)
        if reference is not None:
            ordinal=original['ordinal'];Q.need(ordinal in reference,'ALPHA_ORDINAL_NOT_IN_FIXED_MAIN_REFERENCE')
            diff=differences(scientific(reference[ordinal]),scientific(value));compared+=1;mismatches+=bool(diff)
            journal.append(detail,{'ordinal':ordinal,'scientific_equal':not diff,'different_field_paths':diff,
                'worker_timing_PID_traceback_source_paths_excluded_as_provenance':True},budget,drain=True)
    try:
        for original in records:
            if budget.stop.is_set():break
            budget.check();writer.dispatch(original)  # Complete source row is durable BEFORE submit.
            pending.append((original,pool.submit(kernel.chemical_task,original)));seen+=1
            if len(pending)>=32:collect()
        while pending:
            collect()
    finally:
        while pending:collect()
        result=writer.close()
        if detail is not None:detail.flush();os.fsync(detail.fileno());detail.close()
    result['expected_reference_rows']=len(reference) if reference is not None else None
    result['comparison']={'compared_rows':compared,'scientific_mismatches':mismatches,
        'method':'ALL_FIELDS_TYPED_BINARY64_NO_NUMERIC_TOLERANCE','Main_body_unchanged':True,
        'different_part_path_is_declared_physical_relocation_not_scientific_field':True}
    result['actual_input_rows_dispatched']=seen
    source.write_json(out/(group+'.receipt.json'),result)
    return result



def fixtures(out):
    import io,unittest
    from . import test_v1,source_inverse
    original=ORIGINAL.fixtures(out);test_v1.TEST_ROOT=out/'day32_synthetic';test_v1.TEST_ROOT.mkdir()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);Q.need(suite.countTestCases()==3,'EXACT_THREE_NEW_DAY32_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    result={'schema':'ALPHA_DAY32_SAME_PARENT_SOURCE_PREFLIGHT_V1','old_fixtures5':original,'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),
      'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
      'source_inverse':source_inverse.proof(),'scientific_DATA_or_chemical_calls_before_gate':0}
    ref=source.write_json(out/'day32_fixtures3.json',result)
    Q.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'ALL_SOURCE_PURES_IN_THIS_PARENT_BEFORE_DATA');return ref

def run(plan,proof,out,gate,budget):
    inventory,parts=source.load_inventory(plan['science'],budget);manifest=materialize_shards.validate(Q.load_ref(plan['science']['full_shard_manifest_reference']))
    ctx=mp.get_context('spawn');stop=ctx.Event();barrier=ctx.Barrier(32);closed=[];partial=[];claimed=[];counts=Counter({'accepted':0,'chemReject':0,'technicalUnresolved':0})
    with ProcessPoolExecutor(max_workers=32,mp_context=ctx,initializer=kernel.initialize,initargs=(stop,barrier,str(out/'worker_logs'))) as pool:
        for index in plan['descriptor_indices']:
            if budget.stop.is_set():break
            member=manifest['shards'][index];science={**plan['science'],**member};chosen=ORIGINAL.validate_requested_parts(science,parts)
            chunk=out/('chunk_%06d'%index);chunk.mkdir();claim=materialize_shards.claim(science,proof);claimed.append(index)
            def rows():
                for part in chosen:
                    for original in source.iter_part(part,budget):
                        if budget.stop.is_set():return
                        yield original
            result=run_group(pool,rows(),'full_shard',chunk,budget,stop)
            expected=member['last_ordinal']-member['first_ordinal']+1
            complete=result['completed_rows']==result['dispatched_rows']==expected and sum(result['counts'].values())==expected
            receipt={'schema':'ALPHA_PACKED_DAY32_ORIGINAL_DESCRIPTOR_CHECKPOINT_V1','status':'ORIGINAL_DESCRIPTOR_ROWS_CLOSED_NOT_CHILD_C0' if complete else 'PARTIAL_ORIGINAL_DESCRIPTOR_HOLD_NO_AUTO_RETRY',
              'actual_parent_job_id':str(proof['job_id']),'actual_parent_plan_reference':proof['plan_reference'],'original_descriptor':member,'original_claim_reference':claim,
              'result':result,'expected_rows':expected,'source_row_conservation':complete,'unread_rows':expected-result['dispatched_rows'],'technical_unknown_is_chemical_exclusion':False,
              'full_pool_or_filtered_dedup1M_release':False,'fake_child_Slurm_job_or_accounting':False}
            ref=source.write_json(chunk/'checkpoint.json',receipt);counts.update(result['counts']);(closed if complete else partial).append({'index':index,'reference':ref})
            source.write_json(out/('cursor_after_%06d.json'%index),{'schema':'ALPHA_DAY32_IMMUTABLE_INTERNAL_PROGRESS_V1','parent_job_id':str(proof['job_id']),
              'closed_descriptors':closed,'partial_descriptors':partial,'counts':dict(counts),'Root_terminal_accounting_pending':True,'not_child_C0':True})
            if not complete:break
    logs=[source.pin(p) for p in sorted((out/'worker_logs').glob('*.log'))];remaining=[i for i in plan['descriptor_indices'] if i not in claimed]
    receipt={'schema':'ALPHA_PUBCHEM_PACKED_DAY32_ACTUAL_PARENT_RECEIPT_V1','status':'ALL_ASSIGNED_DESCRIPTORS_ROWS_CLOSED_NOT_POOL_RELEASE' if not remaining and not partial else 'DAY_INTERNAL_CHECKPOINTS_PARTIAL_OR_REMAINDER_RETAINED',
      'endpoint':Q.ENDPOINT,'uid':1264,'node':proof['node'],'job_id':str(proof['job_id']),'actual_cpus':32,'plan_reference':proof['plan_reference'],
      'startup_proof_reference':Q.ref(plan['startup_proof_path']),'cutover_review_reference':plan['cutover_review_reference'],'assignment_token':plan['assignment_token'],
      'original_full_shard_manifest_reference':plan['science']['full_shard_manifest_reference'],'fixture_reference':gate,'closed_descriptors':closed,'partial_descriptors':partial,
      'claimed_original_indices':claimed,'never_claimed_remaining_indices':remaining,'counts':dict(counts),'native_worker_log_references':logs,
      'runtime_budget':budget.receipt(),'all_source_mask_value_and_chemistry_rules_unchanged':True,'no_auto_retry_or_new_epoch':True,
      'per_descriptor_fake_child_C0':False,'parent_terminal_accounting_pending':True,'full_source_pool_release_authorized':False,
      'guide_filtered_dedup_1M_reference_completed':False,'UFF_QM_training_calls':0,'old_source_claims_controller_grant_deadline_and_costs_preserved':True}
    for ref in plan['source_references']:Q.verify(ref)
    Q.need(R.owned_bytes(out)+(128<<20)<=plan['output_cap_bytes'],'WHOLE_PARENT_OUTPUT_ADMIN_DRAIN_CAP')
    source.write_json(out/'receipt.json',receipt);return 3 if partial else 0

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan,proof=require_startup(a.plan,a.startup_proof);out=Q.literal(plan['output_directory']);Q.need(not out.exists(),'FRESH_PARENT_OUTPUT');out.mkdir(mode=0o700,parents=True);budget=None
    try:
        gate=fixtures(out);scope=kernel.verify_source(plan['science']);source.write_json(out/'original_scientific_source_scope.json',scope)
        budget=R.Budget(plan,proof,out);return run(plan,proof,out,gate,budget)
    except BaseException as exc:
        source.write_json(out/'failure.json',{'schema':'ALPHA_DAY32_FAILURE_PRESERVED_V1','status':'HOLD_NO_AUTOMATIC_RETRY','actual_parent_job_id':str(proof['job_id']),
          'error_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'runtime_budget':budget.receipt() if budget else None,
          'all_old_and_partial_outputs_and_claims_retained':True,'parent_accounting_pending':True});raise
    finally:
        if budget is not None:budget.finish()
if __name__=='__main__':raise SystemExit(main())
