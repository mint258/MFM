"""Fresh bounded original-source projection to compact views; no old book writes."""
import argparse,collections,concurrent.futures as cf,json,multiprocessing as mp,time
from pathlib import Path
from . import contract as C,runtime as I
from .project import initialize,worker
from workflows.data_v1_final.labels.full_projection_v1.directory import resolve
from workflows.data_v1_final.labels.bounded_projection_v1.parts import Ledger,pin,publish_bytes
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import stop_requested


def execute(cfg,proof,binding,root,gate,budget):
    I.require(cfg['canonical_index']);actual=resolve(cfg);ranges=actual['ranges'];C.need(ranges,'NONEMPTY_FROZEN_SOURCE_TILE')
    plan=publish_bytes(root/'actual_range_plan.json',(json.dumps(actual,sort_keys=True,separators=(',',':'))+'\n').encode())
    (root/'parts').mkdir();db=Ledger(root/'state.sqlite',True,data_cap=cfg['whole_output_cap_bytes']-(1<<30)-(64<<20),inode_cap=cfg['output_inode_cap']-128,ranges=ranges);db.close()
    shards=[{'shard_id':i,'sources':[]} for i in range(16)];weights=[0]*16
    for r in sorted(ranges,key=lambda r:(-(r['physical_row_hi']-r['physical_row_lo']),r['file_id'])):
        k=min(range(16),key=lambda i:(weights[i],i));shards[k]['sources'].append({'file_id':r['file_id'],'ranges':[r]});weights[k]+=r['physical_row_hi']-r['physical_row_lo']
    budget.attach_ledger(root/'state.sqlite');ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(cfg,str(root),barrier)) as pool:
        refs=list(pool.map(worker,shards,chunksize=1))
    workers=[I.load(I.require(r)) for r in refs];C.need(len(workers)==len({r['pid'] for r in workers})==16,'ACTUAL_SIXTEEN_INDEPENDENT_WORKERS')
    db=Ledger(root/'state.sqlite')
    try:snapshot=db.snapshot()
    finally:db.close()
    window_refs=[];closed=[];stats=collections.defaultdict(collections.Counter);classes=collections.defaultdict(collections.Counter)
    for row in snapshot['closed_windows']:
        window=I.load(I.require(row['receipt']));C.need(window['schema']=='COMPACT_NUMERIC_PHYSICAL_WINDOW_V1' and window['all_part_reopen_bits_verified'],'EXACT_NEW_COMPACT_WINDOW')
        window_refs.append(row['receipt']);closed.append({'file_id':window['file_id'],'lo':window['physical_row_lo'],'hi':window['physical_row_hi'],'all_part_reopen_bits_verified':True})
        kind=window['source_reference']['source_kind'];classes[kind].update(window['physical_classifications'])
        for fid,s in window['field_stats'].items():stats[fid].update(s)
    from .bindings import quality_stop_fields
    # Per-batch rates never substitute a complete full-population denominator.
    denom=4251 if cfg['mode']=='pilot512' else 11231854;holds=sorted(set(quality_stop_fields(stats,denom,.01))
      |{fid for fid,s in stats.items() if s['records'] and (s['newly_masked_records']/s['records']>.01 or s['new_payload_structural_invalid_records']/s['records']>.01)})
    errors=[e for r in workers for e in r['errors']];unknown=snapshot['unpublished_tickets']
    if not window_refs:status='RESOURCE_STOP_WITHOUT_CLOSED_WINDOW_HOLD'
    elif holds:status='QUALITY_HOLD'
    elif errors or unknown:status='UNKNOWN_OR_ERROR_HOLD_NO_CURSOR_ACCEPTANCE'
    else:status='CLOSED_WINDOWS_ACTUAL_PARENT_ACCOUNTING_REQUIRED'
    cursor=I.load(I.require(cfg['selector_reference']))['sources'];byrange={r['range_id']:r for r in ranges}
    observed=[{'file_id':byrange[r['range_id']]['file_id'],'next_physical_row':r['next_physical_row'],'tile_stop':r['physical_row_hi']} for r in snapshot['ranges']]
    result={'schema':C.BATCH,'status':status,'config':I.small_ref(cfg['config_path']),'job_id':str(proof['job_id']),'mode':cfg['mode'],
      'fixture_gate':gate,'actual_range_plan':plan,'worker_reports':refs,'verified_window_receipts':window_refs,'closed_physical_intervals':closed,
      'source_cursors':observed,'field_stats':{k:dict(v) for k,v in stats.items()},'physical_classifications':{k:dict(v) for k,v in classes.items()},
      'quality_hold_fields':holds,'errors':errors,'unpublished_tickets':unknown,'resource_soft_stop':stop_requested(),
      'new_cursors_do_not_touch_old_books':True,'old1904_state':'TIMEOUT','full_global_coverage':False,'candidate_masks_are_final':False,
      'final_Common_D4':False,'native_text_or_precision_or_frame_recovery_claimed':False,'normalization_completed':False,
      'original_Parquet_whole_SHA_state':'INHERITED_PRODUCER_SHA_WITH_CURRENT_SAME_FD_FRAME_AND_FOOTER_VALIDATION',
      'partial_windows_and_all_costs_retained':True,'automatic_retry':False,'automatic_next_batch':False,'charged_output_bytes':I.unique_bytes(root)+(64<<20)+(2<<20)}
    C.need(result['charged_output_bytes']<=cfg['whole_output_cap_bytes'],'WHOLE_OUTPUT_WITH_OBSERVER_AND_METADATA_RESERVE')
    I.save(root/'manifest.json',result)
    C.need(window_refs and not holds and not errors and not unknown,'HOLD_NO_ACCEPTANCE_OR_AUTOMATIC_RETRY');return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','startup-proof','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();cfg,proof,binding=I.guard(a.config,a.startup_proof,'project');root=I.new_root(a.output)
    try:
        gate=I.fixtures(root);cfg['config_path']=a.config
        # First real DATA is after fresh proof, exact SOURCE inverse and three pure methods.
        budget=I.Budget(cfg,proof,binding,root)
        try:return execute(cfg,proof,binding,root,gate,budget)
        finally:budget.close()
    except BaseException as exc:I.failed(root,exc);raise

if __name__=='__main__':raise SystemExit(main())