"""Exact existing512 source projection. No new UFF/QM, full scan, fitting or submit."""
from __future__ import annotations
import argparse, collections, concurrent.futures, hashlib, json, multiprocessing, os, struct, time, unittest, io
from pathlib import Path
from .projection import (cache_row,component_map,decode,encode,scientific_cells,
                         source_float_signature,verify_cache_row)
from workflows.data_v1_final.labels.payload_audit_v1.run import source_columns,pre_scan_fixture_gate
from workflows.data_v1_final.labels.payload_audit_v1.payload import evaluate,quality_stop_fields
from workflows.data_v1_final.labels.streaming_v1.support import legacy
from workflows.data_v1_final.labels.streaming_v1 import compact
from workflows.data_v1_final.labels.size_cpu_v2.aggregate import pair_keys
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import (
 TASKS,load,small_ref,require,need,new_root,identity,save,ref,unique_bytes,sqlite_ro,lookup_batch,classify_owner)
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import (
 start_observer,drain_submit,stop_requested,soft_worker_rss)

SCOPE='label_lossless_projection_512_v1'
PARAMETERS={'records':4251,'molecules':512,'source_groups':16,'task_slots':14,
 'enabled_components':146,'declared_components':264,'source_selection':'existing_canonical_512',
 'new_UFF_QM_calls':0,'final_D4':False,'full_population':False,'candidate_masks_only':True}
WORK={}
BASE_COLUMNS=['record_id','molecule_id','attempt_id','job_id','task_id','source_path','real_index',
 'atomic_numbers','positions_A','bond_pairs','bond_order_codes','conformer_id','geometry_status',
 'source_payload_sha256','source_native_geometry_sha256','native_atom_order_sha256','stored_bond_graph_sha256']


def guard(cfg,path,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    need(cfg['schema']=='LOSSLESS_LABEL_PROJECTION_CONFIG_V1' and cfg['mode']=='pilot'
         and cfg['workers']==16 and cfg['scope_parameters']==PARAMETERS,'EXACT_PILOT_CONFIGURATION')
    request=load(proof_path)['request'];bp=request['producer_resource_binding_reference'];binding=load(require(bp))
    need(binding['schema']=='LOSSLESS_LABEL_PROJECTION_RESOURCE_BINDING_V1','EXACT_NEW_RESOURCE_BINDING')
    need(binding['scientific_config_reference']==small_ref(path),'EXACT_NEW_CONFIG')
    need(binding['scope_key']==SCOPE and binding['scope_parameters']==PARAMETERS,'EXACT_512_SCOPE')
    need(request['pilot'] is True and request['cpus']==16 and request['wall_seconds']<=7200,'PILOT_ONLY_RESOURCE_SCOPE')
    need(request['estimated_peak_output_bytes']>=cfg['whole_output_cap_bytes'],'DECLARED_OUTPUT_CAP')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=SCOPE,
       expected_scope_parameters=PARAMETERS,required_references=[small_ref(path),bp,*cfg['small_references']])
    refs={p['path']:p for p in request['source_references']}
    for pin in cfg['source_references']:
        need(refs.get(pin['path'])==pin,'ACTUAL_SOURCE_NOT_AUTHORIZED');require(pin)
    start_observer(proof,binding);return proof


def fixtures(root,proof):
    inherited=pre_scan_fixture_gate(root,proof)
    from . import test_projection
    source=small_ref(test_projection.__file__);need(source in load(proof)['request']['source_references'],'NEW_FIXTURE_SOURCE_PIN')
    loader=unittest.TestLoader();suite=loader.loadTestsFromModule(test_projection);stream=io.StringIO()
    need(not loader.errors and suite.countTestCases()==3,'EXACT_THREE_CACHE_FIXTURES')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    passed=(result.testsRun==3 and result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses)
    receipt=save(root/'projection_fixture_gate.json',{'status':'PASS' if passed else 'FAIL_NO_BODY',
       'tests_run':result.testsRun,'source':source,'transcript':stream.getvalue(),'original_six_gate':inherited,
       'scientific_bodies_opened':False})
    print(stream.getvalue(),flush=True);need(passed,'CACHE_FIXTURES_MUST_PASS_BEFORE_BODY');return receipt


def initialize(cfg,root,stop,barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    common,masks=legacy(cfg['science']);fields=load(require(cfg['science']['sources']['registry']))['fields']
    enabled=sorted((f for f in fields if f['status']=='enabled'),key=lambda f:f['field_key'])
    need(len(fields)==264 and len(enabled)==146,'UNCHANGED_264_146_MAPPING')
    ids={f['field_key']:i for i,f in enumerate(enabled)};fields=[dict(f,field_id=ids.get(f['field_key'])) for f in fields]
    calibration=load(require(cfg['science']['calibration']))
    need(calibration['mode']=='pilot' and calibration['coverage_fingerprint']==cfg['coverage_fingerprint'],'EXACT_PILOT_CALIBRATION')
    WORK.update(cfg=cfg,root=root,stop=stop,barrier=barrier,common=common,masks=masks,fields=fields,calibration=calibration['fields'])


def schema(pa):
    return pa.schema([('row_kind',pa.string()),('record_ordinal',pa.uint64()),('task_code',pa.uint8()),
      ('record_id',pa.string()),('molecule_id',pa.string()),('tree_json',pa.large_string()),
      ('values_float64',pa.large_list(pa.float64())),('scientific_signature',pa.string())])


def run_group(group):
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    WORK['barrier'].wait(timeout=120);cfg=WORK['cfg'];root=Path(WORK['root'])/('group_'+str(group['group_index']).zfill(4));root.mkdir(mode=0o700)
    started=time.monotonic();index=sqlite_ro(cfg['canonical_index']['path']);handle=None;writer=None
    opened=closed=0;buffers=[];buffer_bytes=0;rows_written=0;digest=hashlib.sha256();counts=collections.Counter();stats=collections.defaultdict(collections.Counter)
    source_schema={};seen=set();base_seen=set();molecules=set();maxrss=0;input_bytes=0
    selected_path=require(group['owner_index']);selection=pq.ParquetFile(selected_path);opened+=1
    try:
        selected={r['record_id'] for b in selection.iter_batches(batch_size=1024,columns=['record_id'],use_threads=False) for r in b.to_pylist()}
    finally:selection.close();closed+=1
    need(len(selected)==group['expected_records'],'EXACT_ORIGINAL_OWNER_SELECTION')
    selected_array=pa.array(sorted(selected),type=pa.string());task_fields={t:[f for f in WORK['fields'] if f['task']==t] for t in TASKS}
    def flush():
        nonlocal writer,buffers,buffer_bytes
        if not buffers:return
        table=pa.Table.from_pylist(buffers,schema=schema(pa))
        need(unique_bytes(root)+table.nbytes*2+(8<<20)<=cfg['group_output_cap_bytes'],'CACHE_GROUP_CAP_NO_TRUNCATION')
        if writer is None:writer=pq.ParquetWriter(root/'cache.parquet',schema(pa),compression='zstd',use_dictionary=True)
        writer.write_table(table,row_group_size=64);buffers=[];buffer_bytes=0
    def put(kind,owner,task,payload):
        nonlocal buffer_bytes,rows_written
        row=cache_row(kind,owner,task,payload);size=len(row['tree_json'].encode('utf-8'))+8*len(row['values_float64'])
        need(size<=cfg['row_serialized_cap_bytes'],'CACHE_SINGLE_ROW_CAP_NO_TRUNCATION')
        digest.update((kind+'|'+str(owner['record_ordinal'])+'|'+str(task)+'|'+row['scientific_signature']).encode())
        buffers.append(row);buffer_bytes+=size;rows_written+=1
        if len(buffers)>=64 or buffer_bytes>=8<<20:flush()
    try:
        sources=[(p,'base_geometry') for p in group['base_files']]+[(p,p['family']) for p in group['label_files']]
        for source,family in sources:
            need(not WORK['stop'].is_set() and not stop_requested(),'SOFT_STOP_BEFORE_NEXT_SOURCE_PARTIALS_RETAINED')
            path=require(source,content=False);before=identity(path);input_bytes+=source['bytes'];handle=pq.ParquetFile(path);opened+=1
            source_schema[source['path']]=str(handle.schema_arrow)
            physical_start=0
            try:
                for row_group in range(handle.num_row_groups):
                    row_in_group=0
                    for original in handle.iter_batches(batch_size=cfg['source_read_batch_records'],row_groups=[row_group],
                           columns=BASE_COLUMNS if family=='base_geometry' else source_columns(family),use_threads=False):
                        maxrss=max(maxrss,soft_worker_rss(cfg['worker_rss_stop_bytes']))
                        # Preserve the original physical row ordinal through Arrow predicate filtering.
                        flags=pc.is_in(original.column('record_id'),value_set=selected_array)
                        original_positions=[i for i,v in enumerate(flags.to_pylist()) if v]
                        batch=original.filter(flags);owners=lookup_batch(index,batch.column('record_id').to_pylist())
                        for i,row in enumerate(batch.to_pylist()):
                            owner=owners.get(row['record_id']);quantum=family not in ('base_geometry','D20','D3')
                            if classify_owner(row,owner,quantum)!='CANONICAL':continue
                            need(owner['job_id']==group['source_job_id'],'CANONICAL_OWNER_GROUP_CHANGED')
                            position=row_in_group+original_positions[i]
                            provenance={'source_reference':source,'source_verification':'INHERITED_PRODUCER_SHA_STABLE_FSTAT_THIS_PASS',
                              'row_group':row_group,'row_within_group':position,'physical_row_ordinal':physical_start+position,
                              'owner':owner,'original_storage_schema':source_schema[source['path']],
                              'actual_frame_origin':'PENDING_CONTROLLED_READBACK','source_role_only_not_final_common':True}
                            if family=='base_geometry':
                                need(owner['record_id'] not in base_seen,'DUPLICATE_BASE_GEOMETRY');base_seen.add(owner['record_id'])
                                molecules.add(owner['molecule_id']);z=row['atomic_numbers'];need(len(z)==owner['total_atoms'],'BASE_NATOM')
                                need(all(type(v) is int and 1<=v<=118 for v in z),'BASE_ATOMIC_NUMBER_TYPE_DOMAIN')
                                need(len(row['positions_A'])==len(z) and all(len(p)==3 for p in row['positions_A']),'BASE_POSITION_SHAPE')
                                atom_sha=hashlib.sha256(b''.join(struct.pack('<q',int(v)) for v in z)).hexdigest()
                                need(atom_sha==row['native_atom_order_sha256'],'BASE_ORIGINAL_ATOM_ORDER')
                                need(row['geometry_status']=='ORIGINAL_PM7_GEOMETRY','BASE_ORIGINAL_PM7_GEOMETRY')
                                put('base',owner,255,{'provenance':provenance,'original_geometry':row,
                                  'source_float_bits':source_float_signature(batch,i)})
                                continue
                            task=row.get('calc_type',family);key=(owner['record_id'],task)
                            need(task in TASKS and key not in seen,'UNEXPECTED_OR_DUPLICATE_CANONICAL_TASK');seen.add(key);counts[task]+=1
                            row['total_atoms']=owner['total_atoms'];row['calc_type']=task;fields=task_fields[task]
                            extra=cfg['extra_geometry_registry_ids'].get(task,[]);rids={f['registry_id'] for f in fields}|set(extra)
                            cells,decoded,positions,duplicates=scientific_cells(row,family,fields,WORK['common'],extra)
                            mapping=component_map(row,family,fields,WORK['common'],decoded,positions,duplicates)
                            items,observations,issues,raw,scores=evaluate(row,family,fields,WORK['common'],WORK['masks'],pair_keys,WORK['calibration'])
                            for item in items:
                                s=stats[str(item['field_id'])];s['newly_masked_records']+=any(a and not b for a,b in zip(item['source_value_mask'],item['value_mask']))
                            for obs in observations:
                                if obs['declaration']=='enabled':
                                    fid=next(f['field_id'] for f in fields if f['field_key']==obs['field_key'])
                                    stats[str(fid)]['new_payload_structural_invalid_records']+=obs['payload_structural_failure']
                            put('task',owner,TASKS[task],{'provenance':provenance,'task':task,'cells':cells,'component_map':mapping,
                              'source_status_and_precision':{k:v for k,v in row.items() if k not in ('values','values_float64','valid_mask','descriptor_names')
                               and k not in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2')},
                              'source_float_bits':source_float_signature(batch,i,rids if quantum else None),
                              'original_compact_candidate':compact.encode(owner['record_ordinal'],TASKS[task],items),
                              'field_observations':observations,'structural_reviews':issues,'raw_counts':raw,
                              'scientific_values_changed':False,'candidate_masks_frozen':False})
                        row_in_group+=original.num_rows
                    physical_start+=handle.metadata.row_group(row_group).num_rows
            finally:handle.close();handle=None;closed+=1
            need(identity(path)==before,'SOURCE_CHANGED_DURING_READ')
        need(base_seen==selected and all(counts[t]==len(selected) for t in TASKS),'EXACT_BASE_AND_14_TASK_COVERAGE')
        need(len(molecules)==group['expected_molecules'],'EXACT_ORIGINAL_COMPLETE_MOLECULE_MASS')
        flush();writer.close();writer=None
        reread=pq.ParquetFile(root/'cache.parquet');opened+=1;actual_digest=hashlib.sha256();actual_rows=0
        try:
            for batch in reread.iter_batches(batch_size=16,use_threads=False):
                for row in batch.to_pylist():
                    verify_cache_row(row);actual_rows+=1
                    actual_digest.update((row['row_kind']+'|'+str(row['record_ordinal'])+'|'+str(row['task_code'])+'|'+row['scientific_signature']).encode())
        finally:reread.close();closed+=1
        need(actual_rows==rows_written and actual_digest.digest()==digest.digest(),'CACHE_REOPEN_BIT_KEY_ORDER_MASS_SIGNATURE')
        report={'schema':'LOSSLESS_LABEL_PROJECTION_GROUP_V1','status':'CACHE_REOPEN_VERIFIED_NOT_FINAL_LABELS',
          'group_index':group['group_index'],'source_job_id':group['source_job_id'],'pid':os.getpid(),
          'records':len(selected),'molecules':len(molecules),'molecule_ids':sorted(molecules),
          'task_counts':dict(counts),'cache_rows':rows_written,'cache':ref(root/'cache.parquet'),
          'typed_scientific_stream_sha256':digest.hexdigest(),'field_stats':dict(stats),'opens':opened,'closes':closed,
          'max_simultaneous_parquet_handles':1,'source_referenced_compressed_bytes':input_bytes,
          'actual_storage_read_bytes':'NOT_MEASURED_BY_PRODUCER_REF_SUM','max_worker_rss_bytes':maxrss,
          'elapsed_seconds':time.monotonic()-started,'unique_output_bytes':unique_bytes(root),
          'source_schemas':source_schema,'full_population':False,'normalization_completed':False,
          'native_program_precision_verified':False,'actual_frame_origin_verified':False}
        save(root/'report.json',report);return {'group_index':group['group_index'],'pid':os.getpid(),'report':ref(root/'report.json')}
    except BaseException as exc:
        WORK['stop'].set();save(root/'failure.json',{'error':str(exc),'partial_outputs_preserved':True,'automatic_retry':False});raise
    finally:
        if handle is not None:handle.close()
        if writer is not None:writer.close()
        index.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','output','startup-proof'):p.add_argument('--'+key,required=True)
    a=p.parse_args();cfg=load(a.config);guard(cfg,a.config,a.startup_proof)
    root=new_root(a.output);receipts=[];started=time.monotonic()
    try:
        gate=fixtures(root,a.startup_proof)
        for pin in cfg['small_references']:require(pin)
        # No body hash before fixtures; producer SHA is inherited, stable fstat is observed.
        for pin in cfg['data_references']:require(pin,content=False)
        groups=load(cfg['owner_plan']['path'])['groups'];need(len(groups)==16,'EXACT_SIXTEEN_OWNERS')
        ctx=multiprocessing.get_context('spawn');stop=ctx.Event();barrier=ctx.Barrier(16)
        with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,
              initargs=(cfg,str(root),stop,barrier)) as pool:
            drain_submit(groups,pool,run_group,receipts,stop_requested,stop)
        need(len(receipts)==len({r['pid'] for r in receipts})==16,'SIXTEEN_ACTUAL_WORKERS')
        stats=collections.defaultdict(collections.Counter);molecules=set();records=0
        for item in receipts:
            report=load(require(item['report']))
            need(not (molecules&set(report['molecule_ids'])),'MOLECULE_SPLIT_ACROSS_OWNERS')
            molecules.update(report['molecule_ids']);records+=report['records']
            for fid,s in report['field_stats'].items():stats[fid].update(s)
        need(records==4251 and len(molecules)==512 and len(stats)==146,'EXACT_512_FINAL_PILOT_MASS')
        stopped=quality_stop_fields(stats,4251,.01)
        need(unique_bytes(root)+(64<<20)<=cfg['whole_output_cap_bytes'],'WHOLE_CACHE_BUDGET_NO_TRUNCATION')
        result={'schema':'LOSSLESS_LABEL_PROJECTION_PILOT_V1','status':'QUALITY_HOLD' if stopped else 'PILOT_CACHE_CLOSED_FULL_NOT_AUTHORIZED',
          'scope_parameters':PARAMETERS,'config':small_ref(a.config),'groups':receipts,'fixture_gate':gate,
          'quality_stop_fields':stopped,'field_stats':dict(stats),'unique_output_bytes':unique_bytes(root),
          'elapsed_seconds':time.monotonic()-started,'final_common_D4':False,'registry_final':False,
          'native_program_precision_verified':False,'actual_frame_origin_verified':False,'full_population':False,
          'source_whole_sha_state':'INHERITED_PRODUCER_NOT_REHASHED_THIS_PASS'}
        save(root/'manifest.json',result);need(not stopped,'ONE_PERCENT_QUALITY_HOLD_PRESERVED_CACHE')
        print(json.dumps({'status':result['status'],'groups':16,'bytes':result['unique_output_bytes']}))
    except BaseException as exc:
        save(root/'failure.json',{'error':str(exc),'closed_group_receipts':receipts,'automatic_retry':False});raise

if __name__=='__main__':main()
