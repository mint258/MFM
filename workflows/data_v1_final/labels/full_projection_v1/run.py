"""Root-approved finite continuation over the full source directory, never D4."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,io,json,multiprocessing as mp,time,unittest
from pathlib import Path
from .control import CALIBRATION,SCOPE,DispatchBook,need,review_contract
from .directory import resolve
from .coverage import write_sidecar
from workflows.data_v1_final.labels.bounded_projection_v1.run import initialize,worker
from workflows.data_v1_final.labels.bounded_projection_v1.parts import Ledger,pin,publish_bytes
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import load,require,small_ref,new_root,save,unique_bytes
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import start_observer


def guard(cfg,path,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    request=load(proof_path)['request'];bp=request['producer_resource_binding_reference'];binding=load(require(bp))
    need(cfg['schema']=='FULL_LABEL_PROJECTION_BATCH_CONFIG_V1' and cfg['full_population_authorized'] is True
      and cfg['norm_fit_allowed'] is False and cfg['logical_statistics_partition_reference'] is None,'SOURCE_CACHE_ONLY_NO_FINAL_FIT')
    need(cfg['calibration_state']==CALIBRATION and cfg['review_calibration_reference'] is None,'NO_512_CALIBRATION_SUBSTITUTION')
    need(cfg['row_serialized_cap_bytes']==64<<20 and cfg['worker_rss_stop_bytes']==3<<30 and cfg['typed_part_cap_bytes']==128<<20
      and cfg['sidecar_reserve_bytes']==2<<30 and cfg['observer_reserve_bytes']==64<<20 and cfg['admin_reserve_bytes']==1<<30
      and 8<<30<=cfg['whole_output_cap_bytes']<=32<<30,'UNCHANGED_SOFTWARE_LIMITS_AND_FINITE_TICKET')
    master=load(require(cfg['master_reference']));review=load(require(cfg['full_review_reference']))
    review_contract(master,review,cfg['master_reference'])
    need(binding['schema']=='FULL_LABEL_PROJECTION_BATCH_RESOURCE_BINDING_V1' and binding['scope_key']==SCOPE
      and binding['scientific_config_reference']==small_ref(path) and binding['scope_parameters']==cfg['scope_parameters']
      and binding['resource_authority_reference']==request['queue_authority_reference']==review['resource_authority_reference']
      and binding['memavailable_soft_floor_bytes']==4<<30,'EXACT_FULL_SOURCE_BATCH_RESOURCE_BINDING')
    need(request['pilot'] is False and request['cpus']==16 and request['wall_seconds']<=172800
      and request['estimated_peak_output_bytes']>=cfg['whole_output_cap_bytes'],'HONEST_NONPILOT_16CPU_NOMEM_MAX48H')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=SCOPE,
      expected_scope_parameters=cfg['scope_parameters'],required_references=[small_ref(path),bp,*cfg['small_references']])
    refs={r['path']:r for r in request['source_references']}
    for r in cfg['source_references']:need(refs.get(r['path'])==r,'ACTUAL_ROOT_TRANSITIVE_SOURCE_PIN');require(r)
    # Central startup supplies current quota, not a stale preparation-time free
    # value. Root must separately account every other outstanding storage scope.
    need(proof['account_free_bytes']>=200000000000+cfg['whole_output_cap_bytes'],'FRESH_QUOTA_RESERVE_AND_CURRENT_STAGE')
    start_observer(proof,binding);return proof


def fixtures(root):
    from .test_full import FullProjectionBoundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(FullProjectionBoundaries);need(suite.countTestCases()==6,'EXACT_SIX_NEW_ORGANIZATION_BOUNDARIES')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    passed=result.testsRun==6 and result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
    receipt=save(root/'full_organization_fixture_gate.json',{'status':'PASS' if passed else 'FAIL_NO_BODY',
      'tests_run':result.testsRun,'transcript':stream.getvalue(),'source_reference':small_ref(Path(__file__).with_name('test_full.py')),
      'real_label_Parquet_canonical_SQLite_or_footer_stream_opened':False,
      'frozen13_fixture_and_numeric_parity_evidence':'BOUND_ACTUAL_ACCEPTED_BOUNDED_PARENT_NOT_RERUN_HERE'})
    print(stream.getvalue(),flush=True);need(passed,'NEW_CONTROL_FIXTURES_BEFORE_ANY_REAL_BODY');return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','startup-proof','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();started=time.monotonic();cfg=load(a.config);proof=guard(cfg,a.config,a.startup_proof);root=new_root(a.output)
    timings={'fresh_guard_small_pin_seconds':time.monotonic()-started}
    try:
        phase=time.monotonic();gate=fixtures(root);timings['six_organization_fixture_seconds']=time.monotonic()-phase
        selectors=load(require(cfg['selector_reference']))['sources'];phase=time.monotonic()
        database=Path(cfg['dispatch_book_path']);bodies={r['path']:r for r in proof['request']['data_references']}
        need(str(database) in bodies,'INITIAL_MUTABLE_METADATA_BOOK_LOCATOR_REQUIRED')
        require(bodies[str(database)])  # Exact post-claim state, before one RUNNING transition.
        authority=DispatchBook(database)
        try:
            need(authority.metadata()['master']==cfg['master_reference'] and authority.metadata()['review']==cfg['full_review_reference'],'FULL_DISPATCH_AUTHORITY_IDENTITY')
            state=authority.snapshot();review=load(require(cfg['full_review_reference']))
            written=sum(b['charged_bytes'] for b in state['batches'] if b['state']=='ACTUAL_C0_CLOSED')
            remaining=state['metadata']['cap']-written
            need(proof['account_free_bytes']>=200000000000+remaining+review['other_storage_scope_unwritten_cap_upper_bound_bytes'],
              'FRESH_FREE_MUST_COVER_REMAINING_APPROVED_FULL_CACHE_PLUS_ALL_OTHER_RESERVATIONS')
            authority.assert_claim(cfg['batch_name'],small_ref(a.config),selectors);authority.running(cfg['batch_name'])
        finally:authority.close()
        timings['dispatch_intent_metadata_verify_seconds']=time.monotonic()-phase;phase=time.monotonic()
        # Frozen canonical index is checked as a whole per allocation. This is
        # real repeated IO and must be included in full batch-chain cost.
        require(cfg['canonical_index']);timings['canonical_index_whole_SHA_seconds']=time.monotonic()-phase;phase=time.monotonic()
        actual=resolve(cfg);timings['actual_footer_member_directory_seconds']=time.monotonic()-phase
        raw=(json.dumps(actual,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=64<<20,'BOUNDED_ACTUAL_DIRECTORY_METADATA_CAP')
        plan=publish_bytes(root/'actual_range_plan.json',raw);del raw
        ranges=actual['ranges'];need(len(ranges)==len(selectors)==cfg['scope_parameters']['selected_source_files'],'ONE_TILE_EACH_EXACT_SELECTED_SOURCE')
        (root/'parts').mkdir(mode=0o700)
        ledger=Ledger(root/'state.sqlite',True,
          data_cap=cfg['whole_output_cap_bytes']-cfg['admin_reserve_bytes']-cfg['observer_reserve_bytes']-cfg['sidecar_reserve_bytes'],
          inode_cap=cfg['output_inode_cap']-128,ranges=ranges);ledger.close()
        shards=[{'shard_id':i,'sources':[]} for i in range(16)]
        # Up to one file per process; empty terminal partitions still spawn and
        # join the same barrier, so actual workers remain16 without dummy data.
        for i,r in enumerate(sorted(ranges,key=lambda r:r['file_id'])):shards[i]['sources'].append({'file_id':r['file_id'],'ranges':[r]})
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        phase=time.monotonic()
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(cfg,str(root),barrier)) as pool:
            workers=list(pool.map(worker,shards,chunksize=1))
        timings['source_decode_projection_atomic_parts_reopen_pool_seconds']=time.monotonic()-phase
        reports=[load(require(r)) for r in workers];need(len({r['pid'] for r in reports})==16,'SIXTEEN_ACTUAL_WORKER_PIDS')
        ledger=Ledger(root/'state.sqlite');snapshot=ledger.snapshot();ledger.close()
        windows=publish_bytes(root/'closed_window_index.json',(json.dumps(snapshot['closed_windows'],sort_keys=True,indent=2)+'\n').encode())
        phase=time.monotonic();sidecar=write_sidecar(root,cfg,snapshot);timings['metadata_only_mask_role_sidecar_seconds']=time.monotonic()-phase
        byrange={r['range_id']:r for r in ranges}
        cursors=[{'file_id':byrange[c['range_id']]['file_id'],'next_physical_row':c['next_physical_row'],
          'tile_stop_physical_row':c['physical_row_hi']} for c in snapshot['ranges']]
        spans=[{'file_id':byrange[w['range_id']]['file_id'],'lo':w['lo'],'hi':w['hi']} for w in snapshot['closed_windows']]
        stats=collections.defaultdict(collections.Counter)
        for key,value in sidecar['field_stats_by_source_role'].items():stats[str(json.loads(key)[1])].update(value)
        hold=sorted(fid for fid,s in stats.items() if s['newly_masked_fields']/11231854>.01
          or s['new_payload_structural_invalid_records']/11231854>.01
          or s['records'] and (s['newly_masked_fields']/s['records']>.01 or s['new_payload_structural_invalid_records']/s['records']>.01))
        errors=[e for report in reports for e in report['errors']]
        pending=errors or snapshot['unpublished_tickets']
        used=unique_bytes(root)+cfg['observer_reserve_bytes']+(2<<20);inodes=len(list(root.rglob('*')))+16
        need(used<=cfg['whole_output_cap_bytes'] and inodes<=cfg['output_inode_cap'],'WHOLE_BATCH_WITH_PARTIALS_OBSERVER_AND_MANIFEST_RESERVES')
        result={'schema':'FULL_LABEL_PROJECTION_BATCH_V1','status':'QUALITY_HOLD' if hold else 'UNPUBLISHED_OR_ERROR_HOLD' if pending else 'BATCH_CLOSED_CURSOR_ADVANCE_REQUIRED',
          'config':small_ref(a.config),'job_id':str(proof['job_id']),'scope_parameters':cfg['scope_parameters'],
          'master_reference':cfg['master_reference'],'full_review_reference':cfg['full_review_reference'],
          'actual_range_plan':plan,'fixture_gate':gate,'worker_reports':workers,'closed_window_index_reference':windows,
          'source_cursors':cursors,'closed_physical_intervals':spans,'sidecar':sidecar,'quality_hold_fields':hold,'errors':errors,
          'unpublished_tickets':snapshot['unpublished_tickets'],'budget_ticket':{k:v for k,v in snapshot.items() if k not in ('ranges','closed_windows','unpublished_tickets')},
          'tile_remainders_pending_not_task_missing':[c for c in snapshot['ranges'] if not c['complete']],
          'charged_output_bytes_including_manifest_reserve':used,'charged_output_inodes_including_manifest_reserve':inodes,
          'partial_observed_rates_are_not_full_population_pass':True,'full_population_completed':False,
          'calibration_state':CALIBRATION,'logical_statistics_partition_reference':None,'candidate_masks_frozen':False,
          'normalization_completed':False,'guide1p5_complete':False,'registry_final':False,
          'original_wholebody_SHA_state':'INHERITED_PRODUCER_NOT_REHASHED_THIS_PASS','elapsed_seconds':time.monotonic()-started,
          'phase_seconds':timings,'verification_and_metadata_bytes':{'canonical_index_bytes_whole_SHA_verified':cfg['canonical_index']['bytes'],
            'footer_selected_compressed_member_bytes_read':sum(r['compressed_member_bytes_read'] for r in actual['source_metadata_member_observations']),
            'footer_selected_raw_member_bytes_parsed':sum(r['raw_member_bytes_read'] for r in actual['source_metadata_member_observations']),
            'source_device_alias_extra_footer_bytes':sum(r['cross_node_device_alias_extra_footer_bytes_read'] for r in reports),
            'source_physical_storage_read_bytes':'NOT_MEASURED'},
          'automatic_retry':False,'automatic_next_batch':False}
        need(len(json.dumps(result,sort_keys=True,indent=2).encode())<=2<<20,'SMALL_CLOSED_BATCH_MANIFEST_LIMIT')
        save(root/'manifest.json',result);print(json.dumps({'status':result['status'],'rows':sidecar['rows'],'sources':len(cursors)}),flush=True)
        need(not hold and not pending,'HOLD_PRESERVES_PARTS_AND_EXCLUSIVE_DISPATCH_LEASE')
    except BaseException as exc:
        save(root/'failure.json',{'error':type(exc).__name__+':'+str(exc),'partials_preserved':True,'automatic_retry':False,
          'dispatch_lease_not_automatically_released':True});raise

if __name__=='__main__':main()
