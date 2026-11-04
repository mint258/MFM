"""CPU-only prefix readback, one exact tail intent, original kernel/Writer, logical closure."""
import argparse,contextlib,json,multiprocessing as mp,os,traceback
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor,Future
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import source,kernel,journal,run as ORIGINAL
from secondary_pubchem_packed_day_alpha_v1 import run as DAY
from . import contract as C
from .runtime import Budget,Stop,frame
from .resource import require_startup

def equal(a,b):return not ORIGINAL.differences(a,b)
def check_running(budget):
    budget.check()
    if budget.stop.is_set():raise Stop(budget.reason)
def opened_frame(stream):
    s=os.fstat(stream.fileno());return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid)
@contextlib.contextmanager
def held(ref,budget):
    path=source.verify(ref,budget);before=frame(path)
    with path.open('rb') as stream:
        Q.need(opened_frame(stream)==before,'SAME_VERIFIED_FD_BEFORE_READ')
        yield stream,before
        Q.need(opened_frame(stream)==before==frame(path),'SAME_VERIFIED_FD_AFTER_EOF_READ')
def parquet_rows(stream):
    import pyarrow.parquet as pq
    p=pq.ParquetFile(stream)
    Q.need(p.schema_arrow.equals(kernel.output_schema(),check_metadata=True),'UNCHANGED_ORIGINAL_ARROW_SCHEMA')
    for batch in p.iter_batches(batch_size=64,use_threads=False):
        yield from batch.to_pylist()
def verify_fragment(result,raw_records,lo,hi,budget):
    """Replay actual durable input/result events and every typed Parquet row; no chemical_task."""
    pending=deque();counts=Counter({k:0 for k in C.KEYS});dispatched=completed=0;next_ordinal=lo
    with held(result['features'],budget) as (pf,pframe),held(result['full_dispatch_and_result_journal'],budget) as (jf,jframe):
        rows=iter(parquet_rows(pf))
        while True:
            check_running(budget);raw=jf.readline((32<<20)+1)
            if not raw:break
            Q.need(len(raw)<=32<<20 and raw.endswith(b'\n'),'WHOLE_ORIGINAL_BOUNDED_JOURNAL_LINE')
            event=json.loads(raw,object_pairs_hook=Q.pairs_unique);kind=event['event']
            if kind=='DISPATCH_DURABLE_BEFORE_SUBMIT':
                Q.need(len(pending)<64 and event['ordinal']==next_ordinal and next_ordinal<=hi,'STRICT_CONTIGUOUS_DISPATCH_NO_OVERLAP')
                original=next(raw_records);Q.need(original['ordinal']==next_ordinal and equal(original,event['input']),'SOURCE_BYTE_ORDINAL_IDENTITY')
                pending.append(original);next_ordinal+=1;dispatched+=1
            else:
                Q.need(kind=='COMPLETE_RESULT_DURABLE_BEFORE_PARQUET' and pending,'ONLY_DURABLE_PAIRED_COMPLETES')
                original=pending.popleft();value=event['value']
                Q.need(event['ordinal']==original['ordinal'] and equal(value['input'],original) and value['category'] in C.KEYS,'RESULT_ORIGINAL_IDENTITY')
                row=next(rows);Q.need(equal(kernel.parquet_row(value,'full_shard'),row),'ALL_ORIGINAL_TYPED_FIELDS_BINARY64_EQUAL')
                counts[value['category']]+=1;completed+=1
        Q.need(not pending and next(rows,None) is None and dispatched==completed==hi-lo+1
          and result['completed_rows']==result['dispatched_rows']==result['actual_input_rows_dispatched']==completed
          and result['last_completed_ordinal']==result['last_dispatched_ordinal']==hi
          and dict(counts)==result['counts'],'EXACT_FRAGMENT_EOF_ROW_MASS_AND_NO_PENDING_WORK')
    return {'rows':completed,'first_ordinal':lo,'last_ordinal':hi,'counts':dict(counts),
      'Parquet_reference':result['features'],'journal_reference':result['full_dispatch_and_result_journal'],
      'Parquet_frame':list(pframe),'journal_frame':list(jframe),'all_typed_fields_binary64_and_source_bytes_verified':True}
def run_tail(pool,records,out,budget,workers):
    """Resource-only pending width16/32/64, original ordered durable dispatch/result objects."""
    writer=journal.Writer(out,'full_shard',budget);pending=deque();seen=0
    def collect():
        original,future=pending.popleft();value=None;error=None
        try:value=future.result()
        except Exception as exc:error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        writer.complete(original,value,error)
    try:
        for original in records:
            if budget.stop.is_set():break
            check_running(budget);writer.dispatch(original);seen+=1
            try:future=pool.submit(kernel.chemical_task,original)
            except Exception as exc:
                failed=Future();failed.set_exception(exc);pending.append((original,failed))
                budget.mark('POOL_SUBMIT_FAILURE_RETAIN_UNKNOWN_NO_RETRY');break
            pending.append((original,future))
            if len(pending)>=workers:collect()
    except Stop:pass
    finally:
        while pending:collect()
        result=writer.close()
    result['actual_input_rows_dispatched']=seen
    result['technical_unknown_is_chemical_exclusion']=False
    return result
def run(plan,proof,out,budget):
    # Direct old scientific objects. No global/module monkeypatch and no old claim() call.
    Q.need(source.iter_part is ORIGINAL.source.iter_part and kernel.chemical_task is ORIGINAL.kernel.chemical_task
      and journal.Writer is ORIGINAL.journal.Writer and kernel.parquet_row is ORIGINAL.kernel.parquet_row
      and kernel.output_schema is ORIGINAL.kernel.output_schema,'DIRECT_ORIGINAL_READER_KERNEL_WRITER_SCHEMA_OBJECTS')
    science=plan['science'];scope=kernel.verify_source(science)
    Q.need(scope['scientific_source_bytes_modified'] is False,'EXISTING_ORIGINAL_SOURCE_PROOF')
    inventory,parts=source.load_inventory(science,budget);prefixes=[];iterators=[];checkpoints=[]
    try:
        # Both prefixes close before creating the sole tail intent or any chemical pool.
        for spec in C.TAILS:
            cp,old_plan=C.checkpoint(spec);Q.need(old_plan['science']==science,'EXACT_OLD_SCIENTIFIC_PLAN')
            raw=iter(source.iter_part(parts[spec['index']],budget));iterators.append(raw);checkpoints.append(cp)
            prefix=verify_fragment(cp['result'],raw,spec['first'],spec['last_prefix'],budget)
            Q.need(prefix['counts']==spec['counts'] and prefix['rows']==spec['prefix_rows'],'RETAIN_ALL_OLD_ROWS_AND15_UNKNOWN')
            prefixes.append(prefix)
        check_running(budget);C.INTENT.parent.mkdir(parents=True,exist_ok=True)
        # One immutable intent for both exact suffixes; it never modifies original claim namespace.
        intent=source.write_json(C.INTENT,{'schema':'ORIGINAL_CONSUMED363_412_SINGLE_TAIL_INTENT_V1',
          'job_id':proof['job_id'],'plan_reference':proof['plan_reference'],'tail_specs':plan['tail_specs'],
          'prefix_readbacks':prefixes,'old_claim_references':[c['original_claim_reference'] for c in checkpoints],
          'original_claims_untouched':True,'automatic_retry':False})
        ctx=mp.get_context('spawn');stop=ctx.Event();barrier=ctx.Barrier(plan['cpus']);logical=[];tails=[]
        with ProcessPoolExecutor(max_workers=plan['cpus'],mp_context=ctx,initializer=kernel.initialize,
                initargs=(stop,barrier,str(out/'worker_logs'))) as pool:
            for spec,cp,raw,prefix in zip(C.TAILS,checkpoints,iterators,prefixes):
                if budget.stop.is_set():break
                chunk=out/('chunk_%06d_tail'%spec['index']);chunk.mkdir()
                # raw remains parked just after the last verified prefix input. Next yields first unread.
                def suffix(records=raw,s=spec):
                    count=0
                    for row in records:
                        Q.need(row['ordinal']==s['last_prefix']+1+count and row['ordinal']<=s['last'],'EXACT_UNREAD_SUFFIX_NO_OLD_CID_DISPATCH')
                        count+=1;yield row
                    Q.need(count==s['tail_rows'],'WHOLE_EXACT_SUFFIX_EOF')
                result=run_tail(pool,suffix(),chunk,budget,plan['cpus'])
                complete=result['completed_rows']==result['dispatched_rows']==result['actual_input_rows_dispatched']==spec['tail_rows']
                tailref=source.write_json(chunk/'tail_result.json',{'schema':'EXACT_ORIGINAL_CONSUMED_DESCRIPTOR_TAIL_RESULT_V1',
                  'new_parent_job_id':proof['job_id'],'new_parent_plan_reference':proof['plan_reference'],'original_checkpoint_reference':spec['checkpoint_reference'],
                  'tail_intent_reference':intent,'first_ordinal':spec['last_prefix']+1,'last_ordinal':spec['last'],'result':result,
                  'status':'TAIL_ROWS_WRITTEN_PENDING_READBACK' if complete else 'PARTIAL_NO_AUTO_RETRY','pool_release':False})
                tails.append(tailref)
                if not complete or budget.stop.is_set():break
                # Readback only, no second chemistry: skip already verified old prefix in raw TSV.
                again=iter(source.iter_part(parts[spec['index']],budget))
                try:
                    for unused in range(spec['prefix_rows']):next(again)
                    tail=verify_fragment(result,again,spec['last_prefix']+1,spec['last'],budget)
                    Q.need(next(again,None) is None,'SOURCE_PART_EOF_AFTER_NEW_TAIL')
                finally:again.close()
                for key,ref in (('Parquet_frame',prefix['Parquet_reference']),('journal_frame',prefix['journal_reference'])):
                    Q.need(list(frame(ref['path']))==prefix[key],'OLD_PREFIX_FRAME_UNCHANGED_AFTER_TAIL')
                counts={k:prefix['counts'][k]+tail['counts'][k] for k in C.KEYS}
                Q.need(prefix['last_ordinal']+1==tail['first_ordinal'] and prefix['rows']+tail['rows']==250000 and sum(counts.values())==250000,'LOGICAL_ORIGINAL_DESCRIPTOR_NO_HOLE_OVERLAP')
                logical.append(source.write_json(out/('logical_descriptor_%06d.json'%spec['index']),{
                  'schema':'ORIGINAL_PUBCHEM_DESCRIPTOR_FRAGMENT_CLOSURE_V1','descriptor_index':spec['index'],
                  'original_descriptor':cp['original_descriptor'],'original_claim_reference':cp['original_claim_reference'],
                  'old_checkpoint_reference':spec['checkpoint_reference'],'old_partial_parent_job_id':spec['parent'],
                  'old_partial_parent_state':'FAILED','old_partial_parent_exit':'3:0','old_accounting_reference':plan['old_accounting_reference'],
                  'new_parent_job_id':proof['job_id'],'new_parent_accounting_pending':True,'tail_intent_reference':intent,
                  'fragments':[prefix,tail],'logical_rows':250000,'counts':counts,'source_row_conservation':True,
                  'old_prefix_rows_and_UNKNOWN_reused_readonly':True,'old_facts_modified':False,'pool_release':False}))
        return {'status':'TWO_LOGICAL_DESCRIPTORS_CPU_CLOSED_ACCOUNTING_PENDING' if len(logical)==2 else 'TAIL_PARTIAL_OR_RESOURCE_STOP_NO_AUTO_RETRY',
          'logical_descriptors':logical,'tail_result_references':tails,'intent_reference':intent,'original_source_proof':scope}
    finally:
        for raw in iterators:raw.close()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan,proof=require_startup(a.plan,a.startup_proof);out=Q.literal(plan['output_directory']);Q.need(not out.exists(),'FRESH_OUTPUT_ONLY')
    out.mkdir(parents=True,mode=0o700);budget=None
    try:
        budget=Budget(plan,proof,out);result=run(plan,proof,out,budget)
        result.update(schema='ALPHA_ORIGINAL_CONSUMED_PARTIAL_TAIL_PARENT_RECEIPT_V1',endpoint=Q.ENDPOINT,uid=1264,
          node=plan['node'],cpus=plan['cpus'],job_id=proof['job_id'],plan_reference=proof['plan_reference'],
          startup_proof_reference=Q.ref(a.startup_proof),old_accounting_reference=plan['old_accounting_reference'],
          runtime_budget=budget.receipt(),pool_release=False,old_claims_results_and_FAILED_costs_preserved=True,
          no_new_500_epoch_or_old_row_recomputation=True,cost_reference=plan['cost_reference'],cost_gate_reference=plan['cost_gate_reference'])
        ref=source.write_json(out/'receipt.json',result);print(Q.canonical({'receipt_reference':ref,'status':result['status']}).decode())
        return 0 if result['status']=='TWO_LOGICAL_DESCRIPTORS_CPU_CLOSED_ACCOUNTING_PENDING' else 3
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'ALPHA_EXACT_TAIL_FAILURE_V1','job_id':proof['job_id'],
          'error':type(exc).__name__+': '+str(exc),'old_results_and_claims_modified':False,'no_automatic_retry':True,
          'tail_intent_may_already_be_consumed':C.INTENT.exists(),'runtime_budget':budget.receipt() if budget else None})
        raise
    finally:
        if budget:budget.finish()
if __name__=='__main__':raise SystemExit(main())
