"""16-worker actual footer directory. Never source data pages or numeric labels."""
from __future__ import annotations
import argparse,concurrent.futures as cf,gzip,hashlib,io,json,multiprocessing as mp,os,socket,stat,time,unittest
from pathlib import Path
from .footer import footer_only,parse_metadata,records,pack_records
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import (
 RUN,need,load,small_ref,require,new_root,save,ref,unique_bytes)
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import (
 start_observer,stop_requested,soft_worker_rss,mark_stop)
SCOPE='labels_wp5_footer_inventory_v1'
PARAMETERS={'label_files':2024,'base_files':184,'files':2208,'workers':16,
 'label_physical_rows':157254650,'inherited_label_canonical_rows':157245956,'inherited_label_shadow_rows':8694,
 'base_producer_physical_rows':11232475,'inherited_base_canonical_rows':11231854,'inherited_base_difference':621,
 'producer_source_bytes':575920810664,'data_page_or_value_reads':False,'new_masks':False,'final_D4':False}
WORK={}


def frame(s):return {'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'uid':s.st_uid}


def guard(cfg,path,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    need(cfg['schema']=='WP5_FOOTER_INVENTORY_CONFIG_V1' and cfg['scope_parameters']==PARAMETERS,'EXACT_FOOTER_CONFIG')
    request=load(proof_path)['request'];bp=request['producer_resource_binding_reference'];binding=load(require(bp))
    need(binding['schema']=='WP5_FOOTER_INVENTORY_RESOURCE_BINDING_V1'
      and binding['scientific_config_reference']==small_ref(path) and binding['scope_key']==SCOPE
      and binding['scope_parameters']==PARAMETERS,'NEW_EXACT_FOOTER_BINDING')
    need(binding['resource_authority_reference']==request['queue_authority_reference'],'CURRENT_RESOURCE_AUTHORITY_BINDING')
    need(cfg['workers']==16 and cfg['whole_output_cap_bytes']==512<<20
      and cfg['compressed_member_data_cap_bytes']==432<<20,'EXACT_BOUNDED_METADATA_OUTPUT_ENVELOPE')
    need(request['pilot'] is False and request['cpus']==16 and request['wall_seconds']<=3600
      and request['estimated_peak_output_bytes']>=cfg['whole_output_cap_bytes'],'EXACT_FOOTER_NONPILOT_ENVELOPE')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=SCOPE,
      expected_scope_parameters=PARAMETERS,required_references=[small_ref(path),bp,*cfg['small_references']])
    allowed={p['path']:p for p in request['source_references']}
    for p in cfg['source_references']:need(allowed.get(p['path'])==p,'ACTUAL_FOOTER_SOURCE_PIN');require(p)
    start_observer(proof,binding);return proof


def fixtures(root):
    from .test_footer import FooterBoundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(FooterBoundaries);stream=io.StringIO()
    need(suite.countTestCases()==3,'EXACT_THREE_FOOTER_BOUNDARIES')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    passed=(result.testsRun==3 and result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses)
    output=save(root/'fixtures3.json',{'status':'PASS' if passed else 'FAIL_NO_SOURCE_OPENED','tests_run':result.testsRun,
      'transcript':stream.getvalue(),'actual_source_file_opened':False})
    print(stream.getvalue(),flush=True);need(passed,'THREE_FOOTER_BOUNDARIES_BEFORE_SOURCES');return output


def initialize(cfg,root,barrier,compressed_counter):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    WORK.update(cfg=cfg,root=root,barrier=barrier,counter=compressed_counter)


def inspect(source):
    """The only original-file read path: explicit footer-only envelope."""
    path=Path(source['path']);need(path.is_absolute() and not path.is_symlink(),'LITERAL_REGULAR_SOURCE')
    with path.open('rb') as original:
        before=os.fstat(original.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_size==source['bytes'],'CURRENT_SOURCE_OWNER_SIZE_TYPE')
        only=footer_only(original,before.st_size,WORK['cfg']['one_footer_cap_bytes'])
        metadata=parse_metadata(only)
        head={'type':'source','source':source,'current_source_frame':frame(before),
          'current_footer_sha256':only['actual_footer_sha256'],'footer_start':only['footer_start'],
          'footer_bytes':only['footer_bytes'],'actual_read_intervals':only['actual_source_read_intervals'],
          'actual_metadata_bytes_read':only['actual_source_metadata_bytes_read'],
          'source_wholebody_SHA_basis':'INHERITED_PRODUCER_LINEAGE_NOT_HASHED_THIS_JOB',
          'data_pages_available_to_Arrow_parser':False,'statistics_minmax_accessed':False}
        def items():
            yield head
            yield from records(metadata,source['rows'])
        raw,end,line_count=pack_records(items(),WORK['cfg']['one_source_serialized_cap_bytes'])
        after=os.fstat(original.fileno());after_path=path.lstat()
        need(frame(before)==frame(after)==frame(after_path),'SOURCE_FRAME_OR_PATH_CHANGED_DURING_FOOTER_READ')
    return raw,end,{'source_frame_before_after':frame(before),'actual_footer_sha256':only['actual_footer_sha256'],
      'footer_start':only['footer_start'],'footer_bytes':only['footer_bytes'],
      'actual_source_metadata_bytes_read':only['actual_source_metadata_bytes_read'],'records':line_count}


def worker(shard):
    WORK['barrier'].wait(timeout=120);cfg=WORK['cfg'];root=Path(WORK['root'])
    stream_path=root/('footer_shard_'+str(shard['shard_id']).zfill(2)+'.jsonl.gz')
    completed=[];errors=[];pending=[];maxrss=0;started=time.monotonic()
    with stream_path.open('xb') as target:
        for position,source in enumerate(shard['files']):
            if stop_requested():pending.extend(s['file_id'] for s in shard['files'][position:]);break
            try:
                maxrss=max(maxrss,soft_worker_rss(cfg['worker_rss_soft_cap_bytes']))
                if stop_requested():pending.extend(s['file_id'] for s in shard['files'][position:]);break
                raw,end,observed=inspect(source);compressed=gzip.compress(raw,compresslevel=6,mtime=0)
                need(hashlib.sha256(gzip.decompress(compressed)).digest()==hashlib.sha256(raw).digest(),'FOOTER_MEMBER_CRC_OR_RAW_SIGNATURE')
                with WORK['counter'].get_lock():
                    if WORK['counter'].value+len(compressed)>cfg['compressed_member_data_cap_bytes']:
                        mark_stop('FOOTER_OUTPUT_CAP_NO_NEXT_FILE',{'used':WORK['counter'].value,'next_member':len(compressed)})
                        pending.extend(s['file_id'] for s in shard['files'][position:]);break
                    # Reserve before IO; failed partial writes keep their reservation.
                    # Otherwise another worker could spend the same bytes after an IO error.
                    WORK['counter'].value+=len(compressed)
                    lo=target.tell();need(target.write(compressed)==len(compressed),'SHORT_METADATA_MEMBER_WRITE')
                    target.flush();os.fsync(target.fileno());hi=target.tell()
                completed.append({'file_id':source['file_id'],'source_kind':source['source_kind'],'family':source['family'],
                  'producer_reference':{k:source[k] for k in ('path','bytes','sha256')},
                  'gzip_member_byte_lo':lo,'gzip_member_byte_hi':hi,'gzip_member_sha256':hashlib.sha256(compressed).hexdigest(),
                  'uncompressed_member_sha256':hashlib.sha256(raw).hexdigest(),'uncompressed_member_bytes':len(raw),
                  **observed,**{k:v for k,v in end.items() if k!='type'}})
            except Exception as exc:
                errors.append({'file_id':source['file_id'],'source_reference':{k:source[k] for k in ('path','bytes','sha256')},
                  'status':'FOOTER_PENDING_NOT_LABEL_FAILURE','error':type(exc).__name__+':'+str(exc),'automatic_retry':False})
    report={'schema':'WP5_FOOTER_SHARD_V1','status':'ALL_ASSIGNED_FOOTERS_OBSERVED' if not(errors or pending) else 'FOOTER_SHARD_PARTIAL_PENDING',
      'shard_id':shard['shard_id'],'pid':os.getpid(),'expected_files':len(shard['files']),
      'runtime':{'pid':os.getpid(),'parent_pid':os.getppid(),'uid':os.getuid(),
                 'node':socket.gethostname().split('.')[0],'job_id':os.environ.get('SLURM_JOB_ID')},
      'inventory':ref(stream_path),'completed':completed,'errors':errors,'pending_file_ids':pending,
      'max_worker_rss_bytes':maxrss,'elapsed_seconds':time.monotonic()-started,
      'actual_wholebody_SHA_computed':False,'source_values_or_data_pages_read':False}
    p=root/('footer_shard_'+str(shard['shard_id']).zfill(2)+'.json');save(p,report)
    return {'shard_id':shard['shard_id'],'pid':os.getpid(),'report':ref(p)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','startup-proof','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();cfg=load(a.config);guard(cfg,a.config,a.startup_proof);root=new_root(a.output);start=time.monotonic()
    try:
        test=fixtures(root);book=load(require(cfg['source_inventory_reference']));files=book['files']
        need(len(files)==2208 and len({s['path'] for s in files})==2208,'EXACT_UNIQUE_2208_SOURCES')
        by_id={s['file_id']:s for s in files};assigned=[i for s in book['shards'] for i in s['file_ids']]
        need(len(book['shards'])==16 and len(assigned)==len(set(assigned))==2208 and set(assigned)==set(by_id),'EXACT_DISJOINT_SOURCE_SHARDS')
        shards=[{'shard_id':s['shard_id'],'files':[by_id[i] for i in s['file_ids']]} for s in book['shards']]
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16);counter=ctx.Value('Q',0)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,
              initargs=(cfg,str(root),barrier,counter)) as pool:
            receipts=list(pool.map(worker,shards,chunksize=1))
        need(len({r['pid'] for r in receipts})==16,'SIXTEEN_REAL_FOOTER_WORKERS')
        completed=[];errors=[];pending=[];stream_bytes=0
        for row in receipts:
            report=load(require(row['report']),limit=8<<20);completed.extend(report['completed']);errors.extend(report['errors']);pending.extend(report['pending_file_ids'])
            stream_bytes+=report['inventory']['bytes']
        ids=[r['file_id'] for r in completed];all_ids={s['file_id'] for s in files}
        need(len(ids)==len(set(ids)) and set(ids)|{e['file_id'] for e in errors}|set(pending)==all_ids,'NO_SILENT_SOURCE_FILE_DROP')
        labels=[r for r in completed if r['source_kind']=='label'];base=[r for r in completed if r['source_kind']=='base']
        closed=(len(labels)==2024 and len(base)==184 and not(errors or pending))
        if closed:
            need(sum(r['physical_rows'] for r in labels)==157254650 and sum(r['physical_rows'] for r in base)==11232475,'ACTUAL_FOOTER_PHYSICAL_MASS')
        need(unique_bytes(root)+(64<<20)+(1<<20)<=cfg['whole_output_cap_bytes'],'WHOLE_FOOTER_OUTPUT_CAP')
        need(len(list(root.rglob('*')))+1<=128,'BOUNDED_METADATA_INODE_COUNT')
        result={'schema':'WP5_FOOTER_INVENTORY_V1','status':'ALL2208_SOURCE_FOOTERS_OBSERVED_VALUES_PENDING' if closed else 'FOOTER_INVENTORY_PARTIAL_PENDING',
          'config':small_ref(a.config),'source_inventory_reference':cfg['source_inventory_reference'],'fixture_gate':test,
          'actual_worker_pids':sorted({r['pid'] for r in receipts}),'shards':receipts,'observed_files':len(completed),
          'observed_label_files':len(labels),'observed_base_files':len(base),'actual_label_footer_rows':sum(r['physical_rows'] for r in labels),
          'actual_base_footer_rows':sum(r['physical_rows'] for r in base),
          'inherited_label_canonical_rows':157245956,'inherited_label_shadow_rows':8694,
          'inherited_base_canonical_rows':11231854,'base_difference_from_inherited_metadata':621,
          'canonical_owner_body_join_performed':False,'differences_not_reclassified_from_footers':True,
          'actual_row_groups':sum(r['row_groups'] for r in completed),'actual_column_chunks':sum(r['column_chunks'] for r in completed),
          'actual_source_metadata_bytes_read':sum(r['actual_source_metadata_bytes_read'] for r in completed),
          'metadata_read_byte_count_scope':'completed_sources_only; failed attempts not included',
          'compressed_append_reserved_bytes_including_failed_writes':counter.value,'actual_compressed_stream_bytes':stream_bytes,
          'compressed_closed_member_bytes':sum(r['gzip_member_byte_hi']-r['gzip_member_byte_lo'] for r in completed),
          'unique_output_bytes':unique_bytes(root),
          'errors':errors,'pending_file_ids':pending,'elapsed_seconds':time.monotonic()-start,
          'current_wholebody_SHA_verified':False,'data_page_or_payload_values_read':False,
          'native_program_precision_verified':False,'actual_frame_origin_verified':False,
          'new_masks_created':False,'guide1p5_complete':False,'normalization_completed':False,'final_common_D4':False}
        save(root/'manifest.json',result);print(json.dumps({'status':result['status'],'files':len(completed),'row_groups':result['actual_row_groups']}))
        if not closed:raise RuntimeError('FOOTER_PARTIAL_PRESERVED_NO_AUTOMATIC_RETRY')
    except BaseException as exc:
        save(root/'failure.json',{'error':type(exc).__name__+':'+str(exc),'partials_preserved':True,'automatic_retry':False});raise

if __name__=='__main__':main()
