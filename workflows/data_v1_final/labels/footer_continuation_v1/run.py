"""Reuse closed footer metadata, inspect only pending original sources."""
from __future__ import annotations
import argparse,concurrent.futures as cf,io,json,multiprocessing as mp,os,stat,time,unittest
from pathlib import Path
from .resume import SCOPE,partition,data_cap
from workflows.data_v1_final.labels.footer_inventory_v1 import run as frozen
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import (
 load,need,require,small_ref,new_root,save,unique_bytes,ref)


def guard(cfg,path,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    need(cfg['schema']=='WP5_FOOTER_CONTINUATION_CONFIG_V1','EXACT_NEW_FOOTER_CONTINUATION_CONFIG')
    request=load(proof_path)['request'];bp=request['producer_resource_binding_reference'];binding=load(require(bp))
    need(binding['schema']=='WP5_FOOTER_CONTINUATION_RESOURCE_BINDING_V1'
      and binding['scientific_config_reference']==small_ref(path) and binding['scope_key']==SCOPE
      and binding['scope_parameters']==cfg['scope_parameters']
      and binding['resource_authority_reference']==request['queue_authority_reference'],'EXACT_CURRENT_CONTINUATION_BINDING')
    need(request['pilot'] is False and request['cpus']==16 and request['wall_seconds']<=3600
      and request['estimated_peak_output_bytes']>=8<<30 and cfg['whole_output_cap_bytes']==8<<30,'EXACT_NONPILOT_CPU16_EIGHT_GIB_CAP')
    need(cfg['one_footer_cap_bytes']==128<<20 and cfg['one_source_serialized_cap_bytes']==64<<20
      and cfg['worker_rss_soft_cap_bytes']==3<<30,'UNCHANGED_PARSER_WORKER_SOFTWARE_CAPS')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=SCOPE,
      expected_scope_parameters=cfg['scope_parameters'],required_references=[small_ref(path),bp,*cfg['small_references']])
    sources={p['path']:p for p in request['source_references']}
    for r in cfg['source_references']:need(sources.get(r['path'])==r,'EXACT_CURRENT_CODE_OR_SMALL_INPUT');require(r)
    frozen.start_observer(proof,binding);return proof


def fixtures(root):
    original=frozen.fixtures(root)
    from .test_resume import ResumeBoundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ResumeBoundaries);need(suite.countTestCases()==2,'EXACT_TWO_RESUME_BOUNDARIES')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    passed=(result.testsRun==2 and result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses)
    receipt=save(root/'resume_fixtures2.json',{'status':'PASS' if passed else 'FAIL_NO_ORIGINAL_SOURCE_OPENED',
      'tests_run':result.testsRun,'transcript':stream.getvalue(),'original_three':original,
      'actual_source_Parquet_opened':False,'inherited_stream_body_hashed':False})
    print(stream.getvalue(),flush=True);need(passed,'RESUME_BOUNDARIES_BEFORE_ANY_BODY');return original,receipt


def load_previous(cfg):
    book=load(require(cfg['source_inventory_reference']));plan=load(require(cfg['pending_plan_reference']))
    reports={r['report']['path']:load(require(r['report'])) for r in plan['layers']}
    completed,pending,streams,jobs=partition(book,plan['layers'],reports)
    need(len(book['files'])==2208 and len(completed)==cfg['scope_parameters']['reused_completed_files']
      and len(pending)==cfg['scope_parameters']['pending_sources_only'],'EXACT_ACTUAL_REUSE_AND_PENDING_COUNTS')
    cap,charge=data_cap(cfg['whole_output_cap_bytes'],streams,[r['report'] for r in plan['layers']],jobs)
    need(cap==cfg['compressed_member_data_cap_bytes'] and charge==cfg['charged_inherited_metadata_bytes'],'UNCHANGED_CUMULATIVE_CAP_ACCOUNTING')
    # These are produced footer-metadata streams, NOT original Parquet files.
    for r in streams:require(r)
    current_frames=[]
    for file_id,row in sorted(completed.items()):
        source=Path(row['producer_reference']['path']);s=source.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid()
          and frozen.frame(s)==row['source_frame_before_after'],'REUSED_SOURCE_CURRENT_FSTAT_OR_PATH_CHANGED')
        current_frames.append({'file_id':file_id,'current_source_frame':frozen.frame(s),
          'original_source_opened':False,'metadata_inventory_reference':row['inventory_reference']})
    byid={r['file_id']:r for r in book['files']};assigned=[i for s in plan['shards'] for i in s['file_ids']]
    need(len(plan['shards'])==16 and len(assigned)==len(set(assigned)) and set(assigned)==set(pending),
      'ONLY_UNHANDLED_SOURCES_ASSIGNED_ONCE')
    shards=[{'shard_id':s['shard_id'],'files':[byid[i] for i in s['file_ids']]} for s in plan['shards']]
    return book,plan,reports,completed,pending,streams,current_frames,shards


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','startup-proof','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args();cfg=load(a.config);proof=guard(cfg,a.config,a.startup_proof);root=new_root(a.output);started=time.monotonic()
    try:
        original_gate,resume_gate=fixtures(root)
        book,plan,reports,reused,pending,old_streams,frames,shards=load_previous(cfg)
        reuse_receipt=save(root/'reuse_verification.json',{'schema':'WP5_CLOSED_FOOTER_REUSE_VERIFIED_V1','status':'VERIFIED',
          'job_id':str(proof['job_id']),'uid':os.getuid(),'old_metadata_streams_fullSHA_verified':old_streams,
          'reused_files':len(reused),'current_source_fstat_verifications':frames,
          'reused_original_Parquet_open_calls':0,'reused_original_footer_read_bytes':0,
          'pending_original_source_files':len(pending),'previous_terminal_evidence_retained':plan['history_references']})
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16);counter=ctx.Value('Q',0)
        # Original initialize/worker/inspect/footer functions, unmodified.
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=frozen.initialize,
              initargs=(cfg,str(root),barrier,counter)) as pool:
            results=list(pool.map(frozen.worker,shards,chunksize=1))
        need(len(results)==len({r['pid'] for r in results})==16,'SIXTEEN_ACTUAL_CONTINUATION_WORKERS')
        new_layers=[{'report':r['report'],'assigned_file_ids':next(s['file_ids'] for s in plan['shards'] if s['shard_id']==r['shard_id'])} for r in results]
        layers=plan['layers']+new_layers;new_errors=[];new_completed=[];new_pending=[];stream_bytes=0
        for r in results:
            report=load(require(r['report']));reports[r['report']['path']]=report
            new_errors.extend(report['errors']);new_completed.extend(report['completed']);new_pending.extend(report['pending_file_ids']);stream_bytes+=report['inventory']['bytes']
        # Error sources also remain pending; their exact errors are retained and
        # a later resume refuses automatic retry until separately reviewed.
        done_ids=[r['file_id'] for r in new_completed];error_ids=[r['file_id'] for r in new_errors]
        need(len(done_ids)==len(set(done_ids)) and not(set(done_ids)&set(reused))
          and set(done_ids)|set(new_pending)|set(error_ids)==set(pending),'NO_SOURCE_REUSE_OR_SILENT_PENDING_DROP')
        all_completed=[*reused.values(),*new_completed]
        labels=[r for r in all_completed if r['source_kind']=='label'];base=[r for r in all_completed if r['source_kind']=='base']
        remaining=sorted(set(pending)-set(done_ids));closed=(len(labels)==2024 and len(base)==184 and not(remaining or new_errors))
        if closed:
            need(sum(r['physical_rows'] for r in labels)==157254650 and sum(r['physical_rows'] for r in base)==11232475,
              'EXACT_FULL_ACTUAL_FOOTER_PHYSICAL_MASS')
        need(cfg['charged_inherited_metadata_bytes']+unique_bytes(root)+(80<<20)<=cfg['whole_output_cap_bytes'],'CUMULATIVE_EIGHT_GIB_CAP')
        need(len(list(root.rglob('*')))+2<=128,'NEW_OUTPUT_INODE_CAP')
        result={'schema':'WP5_FOOTER_CONTINUATION_V1','status':'ALL2208_SOURCE_FOOTERS_OBSERVED_VALUES_PENDING' if closed else 'FOOTER_INVENTORY_PARTIAL_PENDING',
          'config':small_ref(a.config),'source_inventory_reference':cfg['source_inventory_reference'],'previous_manifest_reference':cfg['previous_manifest_reference'],
          'current_job_id':str(proof['job_id']),'original_three_fixture_gate':original_gate,'resume_fixture_gate':resume_gate,'reuse_verification':reuse_receipt,
          'actual_worker_pids':sorted({r['pid'] for r in results}),'new_shards':results,'layers':layers,
          'reused_files':len(reused),'newly_observed_files':len(new_completed),'observed_files':len(all_completed),
          'observed_label_files':len(labels),'observed_base_files':len(base),'actual_label_footer_rows':sum(r['physical_rows'] for r in labels),
          'actual_base_footer_rows':sum(r['physical_rows'] for r in base),'inherited_label_canonical_rows':157245956,
          'inherited_label_shadow_rows':8694,'inherited_base_canonical_rows':11231854,'base_difference_from_inherited_metadata':621,
          'canonical_owner_body_join_performed':False,'differences_not_reclassified_from_footers':True,
          'actual_row_groups':sum(r['row_groups'] for r in all_completed),'actual_column_chunks':sum(r['column_chunks'] for r in all_completed),
          'actual_source_metadata_bytes_read':sum(r['actual_source_metadata_bytes_read'] for r in all_completed),
          'current_job_original_footer_bytes_read_completed_only':sum(r['actual_source_metadata_bytes_read'] for r in new_completed),
          'metadata_read_byte_count_scope':'completed sources; failed attempts not included; old407 inherited, not reread',
          'current_job_new_stream_bytes':stream_bytes,'compressed_append_reserved_bytes_including_failed_writes':counter.value,
          'charged_inherited_metadata_bytes':cfg['charged_inherited_metadata_bytes'],'unique_new_output_bytes_before_manifest':unique_bytes(root),
          'errors':new_errors,'pending_file_ids':remaining,'elapsed_seconds':time.monotonic()-started,
          'reused_original_Parquet_open_calls':0,'current_wholebody_SHA_verified':False,'data_page_or_payload_values_read':False,
          'native_program_precision_verified':False,'actual_frame_origin_verified':False,'new_masks_created':False,
          'guide1p5_complete':False,'normalization_completed':False,'final_common_D4':False,'eight_GiB_is_cap_not_full_guarantee':True}
        save(root/'manifest.json',result);print(json.dumps({'status':result['status'],'reused':len(reused),'new':len(new_completed),'pending':len(remaining)}))
        if not closed:raise RuntimeError('FOOTER_CONTINUATION_PARTIAL_PRESERVED_NO_AUTOMATIC_RETRY')
    except BaseException as exc:
        save(root/'failure.json',{'error':type(exc).__name__+':'+str(exc),'partials_preserved':True,'previous_FAILED_not_rewritten':True,'automatic_retry':False});raise

if __name__=='__main__':main()
