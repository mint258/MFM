"""Owner-complete payload pilot/full shards, preserving frozen readers and rules."""
from __future__ import annotations
import argparse, collections, concurrent.futures, hashlib, json, math, multiprocessing, os, sqlite3, time
from pathlib import Path
from .payload import evaluate,quality_stop_fields,worst_preview
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import (
 RUN,TASKS,TASK_FAMILIES,ROLES,load,ref,require,need,new_root,identity,small_ref,sqlite_ro,lookup_batch,classify_owner,save,unique_bytes)
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import (
 start_observer,drain_submit,stop_requested,soft_worker_rss)
from workflows.data_v1_final.labels.streaming_v1.support import legacy
from workflows.data_v1_final.labels.streaming_v1 import compact
from workflows.data_v1_final.labels.size_cpu_v2.aggregate import pair_keys
WORK={}

def guard(cfg,path,proof_path,cap):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    provisional=load(proof_path);request=provisional['request'];binding_ref=request['producer_resource_binding_reference']
    binding=load(require(binding_ref));need(binding['schema']=='LABEL_PAYLOAD_AUDIT_RESOURCE_BINDING_V1','PAYLOAD_RESOURCE_BINDING')
    need(binding['scientific_config_reference']==small_ref(path),'EXACT_PAYLOAD_CONFIG')
    need(request['estimated_peak_output_bytes']>=cap,'DECLARED_OUTPUT_CAP')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=binding['scope_key'],
      expected_scope_parameters=binding['scope_parameters'],required_references=[small_ref(path),binding_ref,*cfg['sources'].values()])
    refs={p['path']:p for p in request['source_references']}
    for p in Path(__file__).parent.glob('*.py'):need(refs.get(str(p))==small_ref(p),'ACTUAL_PAYLOAD_SOURCE_PIN')
    start_observer(proof,binding)

def init_worker(cfg,plan,root,stop,barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    common,masks=legacy(cfg)
    registry=load(cfg['sources']['registry']['path'])
    enabled=sorted((f for f in registry['fields'] if f['status']=='enabled'),key=lambda f:f['field_key'])
    need(len(enabled)==146,'UNCHANGED_146_ENABLED_COMPONENTS')
    ids={f['field_key']:i for i,f in enumerate(enabled)}
    fields=[dict(f,field_id=ids.get(f['field_key'])) for f in registry['fields']]
    calibration={}
    if cfg['calibration'] is not None:
        require(cfg['calibration']);cal=load(cfg['calibration']['path'])
        need(cal['mode']==plan['mode'] and cal['coverage_fingerprint']==plan['coverage_fingerprint'],'CALIBRATION_SCOPE_MISMATCH')
        calibration=cal['fields']
    WORK.update(cfg=cfg,plan=plan,root=root,stop=stop,barrier=barrier,common=common,masks=masks,fields=fields,fields_by_id={f['field_id']:f for f in fields if f['status']=='enabled'},calibration=calibration)

def source_columns(family):
    common=['record_id','molecule_id','attempt_id','job_id','task_id','status']
    if family=='D20':return common+['values_float64','valid_mask','descriptor_names']
    if family=='D3':return common+['PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2','issues']
    return common+['calc_type','lane','total_atoms','values','numeric_issues','converged','scf_iterations',
      'precision_by_field_json','source_status','failure_code','raw_audit_selected','raw_output_locator_json','software_version_id','input_bundle_sha256','input_file_sha256','reproduction_package_sha256']

def json_safe(value):
    if isinstance(value,float) and not math.isfinite(value):return repr(value)
    if isinstance(value,list):return [json_safe(v) for v in value]
    if isinstance(value,dict):return {k:json_safe(v) for k,v in value.items()}
    return value

def bounded_worst(store,key,record,cap=20):
    rows=store.setdefault(key,[]);rows.append(record)
    rows.sort(key=lambda r:(-r.get('score',0),r.get('record_ordinal',0)))
    del rows[cap:]

def run_group(item):
    group,warmup=item;cfg=WORK['cfg'];need(not WORK['stop'].is_set(),'SOURCE_FAILURE_NO_NEXT_GROUP')
    if warmup:WORK['barrier'].wait(timeout=120)
    root=Path(WORK['root'])/('group_'+str(group['group_index']).zfill(4));root.mkdir(mode=0o700)
    started=time.monotonic();index=sqlite_ro(WORK['plan']['canonical_index']['path']);outdb=sqlite3.connect(root/'scalar_extrema.sqlite')
    outdb.execute('PRAGMA journal_mode=OFF');outdb.execute('PRAGMA cache_size=-8192')
    outdb.execute('CREATE TABLE molecules(molecule_id TEXT PRIMARY KEY) WITHOUT ROWID')
    outdb.execute('CREATE TABLE extrema(fid INTEGER,molecule_id TEXT,role TEXT,min_abs REAL,max_abs REAL,min_ordinal INTEGER,max_ordinal INTEGER,signs INTEGER,n INTEGER,PRIMARY KEY(fid,molecule_id)) WITHOUT ROWID')
    selected=None;selected_array=None;outputs=[];writer=None;coverage=None;handle=None;opened=closed=0;maxrss=0;buffers=[];cover=[];processed=0;budget_mark=0
    counts=collections.Counter();raw_counts=collections.Counter();stats=collections.defaultdict(collections.Counter);structural=collections.Counter();worst={};raw_candidates=[];raw_by_task=collections.Counter();field_observations=collections.defaultdict(collections.Counter)
    import pyarrow as pa
    import pyarrow.parquet as pq
    if group.get('owner_index') is not None:
        p=require(group['owner_index']);h=pq.ParquetFile(p)
        try:selected={r['record_id'] for batch in h.iter_batches(batch_size=1024,columns=['record_id'],use_threads=False) for r in batch.to_pylist()}
        finally:h.close()
        need(len(selected)==group['expected_records'],'PILOT_SELECTION_MASS')
        selected_array=pa.array(sorted(selected),type=pa.string())
    task_fields={task:[f for f in WORK['fields'] if f['task']==task] for task in TASKS}
    cap=cfg['group_output_cap_bytes'];mask_schema=compact.arrow_schema()
    cov_schema=pa.schema([('record_ordinal',pa.uint64()),('task_code',pa.uint8()),('role_code',pa.uint8()),('review_flags',pa.uint16())])
    def flush():
        nonlocal buffers,cover,writer,coverage
        if not buffers:return
        table=pa.Table.from_pylist(buffers,schema=mask_schema);ct=pa.Table.from_pylist(cover,schema=cov_schema)
        need(unique_bytes(root)+table.nbytes*2+ct.nbytes*2+(8<<20)<=cap,'GROUP_OUTPUT_CAP')
        if writer is None:writer=pq.ParquetWriter(root/'candidate_masks.parquet',mask_schema,compression='zstd')
        if coverage is None:coverage=pq.ParquetWriter(root/'coverage.parquet',cov_schema,compression='zstd')
        writer.write_table(table,row_group_size=4096);coverage.write_table(ct,row_group_size=4096);buffers=[];cover=[];outdb.commit()
    try:
        for source in group['label_files']:
            need(not WORK['stop'].is_set(),'SOURCE_FAILURE_BEFORE_NEXT_FILE');path=require(source,content=False);before=identity(path)
            handle=pq.ParquetFile(path);opened+=1
            try:
                for batch in handle.iter_batches(batch_size=cfg['source_read_batch_records'],columns=source_columns(source['family']),use_threads=False):
                    need(not WORK['stop'].is_set(),'SOURCE_FAILURE_BEFORE_NEXT_BATCH')
                    maxrss=max(maxrss,soft_worker_rss(cfg['worker_rss_stop_bytes']))
                    # Filter IDs in Arrow before converting large CELL payloads to Python.
                    if selected is not None:
                        import pyarrow.compute as pc
                        batch=batch.filter(pc.is_in(batch.column('record_id'),value_set=selected_array))
                    if not batch.num_rows:continue
                    owners=lookup_batch(index,batch.column('record_id').to_pylist());rows=batch.to_pylist()
                    for row in rows:
                        owner=owners.get(row['record_id']);quantum=source['family'] not in ('D20','D3')
                        if classify_owner(row,owner,quantum)!='CANONICAL':continue
                        need(owner['job_id']==group['source_job_id'],'OWNER_GROUP_DIFFERS')
                        task=row['calc_type'] if quantum else source['family'];need(TASK_FAMILIES[task]==source['family'],'TASK_FAMILY')
                        row['total_atoms']=owner['total_atoms'];row['calc_type']=task
                        items,observations,issues,raw,scores=evaluate(row,source['family'],task_fields[task],WORK['common'],WORK['masks'],pair_keys,WORK['calibration'])
                        raw_counts.update(raw);counts[task]+=1;processed+=1
                        if task=='D20':outdb.execute('INSERT OR IGNORE INTO molecules VALUES(?)',(owner['molecule_id'],))
                        for obs in observations:
                            c=field_observations[obs['field_key']];c['records']+=1;c['numeric_leaves']+=obs['numeric_leaves'];c['zero_leaves']+=obs['zero_leaves']
                            c['nonnumeric_or_nonfinite_leaves']+=obs['nonnumeric_or_nonfinite_leaves'];c['layout_accepted_records']+=obs['layout_accepted']
                            if obs['reason']:c['reason:'+obs['reason'].split(':',1)[0]]+=1
                        bad_rids={x['registry_id'] for x in issues};obs_by_key={o['field_key']:o for o in observations}
                        for issue in issues:structural[str(issue['registry_id'])+'|'+issue['reason']]+=1
                        for entry in items:
                            fid=entry['field_id'];c=stats[str(fid)];c['records']+=1
                            c['source_valid_records']+=bool(any(entry['source_value_mask']));c['valid_records']+=bool(any(entry['value_mask']))
                            role_prefix='role:'+owner['new_role']+':'
                            c[role_prefix+'records']+=1;c[role_prefix+'valid_records']+=bool(any(entry['value_mask']))
                            c[role_prefix+'newly_masked_records']+=any(a and not b for a,b in zip(entry['source_value_mask'],entry['value_mask']))
                            c['newly_masked_records']+=any(a and not b for a,b in zip(entry['source_value_mask'],entry['value_mask']))
                            field=WORK['fields_by_id'][fid]
                            obs=obs_by_key[entry['field_key']]
                            c['new_payload_structural_invalid_records']+=obs['payload_structural_failure']
                            for name in ('source_reasons','new_reasons','review_reasons'):
                                for reason in set(entry[name]):c[name+':'+reason.split(':',1)[0]]+=1
                            val=[v for v,keep in zip(entry['values_float64'],entry['value_mask']) if keep]
                            reasons=set(entry['source_reasons']+entry['new_reasons']+entry['review_reasons'])
                            if field['registry_id'] in bad_rids:reasons.add('STRUCTURAL_PAYLOAD_REVIEW_ONLY')
                            for reason in reasons:
                                score=scores.get(fid) if reason in ('ROBUST_Z_GT20_REVIEW_ONLY','ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY') else 1.0
                                bounded_worst(worst,str(fid)+'|'+reason,worst_preview(entry,owner,reason,score or 0,cfg['preview_leaves']))
                            if field['level']=='molecule' and len(val)==1:
                                bounded_worst(worst,str(fid)+'|STORED_SCALAR_MAGNITUDE_EXTREME_REVIEW_ONLY',worst_preview(entry,owner,'STORED_SCALAR_MAGNITUDE_EXTREME_REVIEW_ONLY',abs(val[0]),cfg['preview_leaves']))
                                if val[0]!=0:
                                    a=abs(val[0]);ordinal=owner['record_ordinal'];sign=1 if val[0]>0 else 2
                                    outdb.execute('INSERT INTO extrema VALUES(?,?,?,?,?,?,?,?,1) ON CONFLICT(fid,molecule_id) DO UPDATE SET min_ordinal=CASE WHEN excluded.min_abs<min_abs THEN excluded.min_ordinal ELSE min_ordinal END,max_ordinal=CASE WHEN excluded.max_abs>max_abs THEN excluded.max_ordinal ELSE max_ordinal END,min_abs=min(min_abs,excluded.min_abs),max_abs=max(max_abs,excluded.max_abs),signs=signs|excluded.signs,n=n+1',
                                      (fid,owner['molecule_id'],owner['new_role'],a,a,ordinal,ordinal,sign))
                        if row.get('raw_audit_selected') and row.get('raw_output_locator_json') is not None and len(raw_candidates)<cfg['raw_candidates_per_group'] and raw_by_task[task]<cfg['raw_candidates_per_task']:
                            raw_by_task[task]+=1
                            raw_candidates.append({'source_file':source,'status':row['status'],'input_bundle_sha256':row.get('input_bundle_sha256'),'input_file_sha256':row.get('input_file_sha256'),'reproduction_package_sha256':row.get('reproduction_package_sha256'),'record_ordinal':owner['record_ordinal'],'record_id':owner['record_id'],'molecule_id':owner['molecule_id'],'task':task,'raw_locator_json':row['raw_output_locator_json'],'software_version_id':row.get('software_version_id'),'precision_metadata_json':row.get('precision_by_field_json'),'raw_archive_opened':False})
                        buffers.append(compact.encode(owner['record_ordinal'],TASKS[task],items))
                        cover.append({'record_ordinal':owner['record_ordinal'],'task_code':TASKS[task],'role_code':ROLES[owner['new_role']],'review_flags':0})
                        if len(buffers)>=cfg['output_batch_records']:flush()
                    rows=None;batch=None;owners=None
                    need(unique_bytes(root)+(8<<20)<=cap,'GROUP_OUTPUT_CAP')
                    if processed-budget_mark>=1024:
                        need(unique_bytes(WORK['root'])+(512<<20)<=cfg['shard_output_cap_bytes'],'SHARD_LIVE_OUTPUT_SOFT_CAP')
                        budget_mark=processed
            finally:handle.close();handle=None;closed+=1
            need(identity(path)==before,'READ_ONLY_SOURCE_CHANGED')
        flush();writer.close();writer=None;coverage.close();coverage=None;outdb.commit()
        need(all(counts[t]==group['expected_records'] for t in TASKS),'WHOLE_OWNER_14_TASK_COUNTS')
        mols=outdb.execute('SELECT count(*) FROM molecules').fetchone()[0]
        if group.get('expected_molecules') is not None:need(mols==group['expected_molecules'],'WHOLE_PILOT_MOLECULE_COUNT')
        jumps=[];jump_counts=collections.Counter()
        for fid,mid,role,lo,hi,oid_min,oid_max,sign,n in outdb.execute('SELECT * FROM extrema WHERE n>=2 AND signs IN (1,2) AND max_abs/min_abs>1000'):
            jump_counts[str(fid)]+=1
            row={'field_id':fid,'molecule_id':mid,'role':role,'min_abs':lo,'max_abs':hi,'min_record_ordinal':oid_min,'max_record_ordinal':oid_max,'count':n,'ratio':hi/lo,'review_only':True}
            bounded_worst(worst,str(fid)+'|WITHIN_MOLECULE_JUMP_REVIEW_ONLY',dict(row,record_ordinal=oid_min,score=hi/lo))
            if len(jumps)<cfg['within_molecule_examples_per_group']:jumps.append(row)
        outdb.close();outdb=None
        details={'worst20_by_field_reason':worst,'within_molecule_jump_counts':dict(jump_counts),'within_molecule_examples':jumps,'within_molecule_examples_may_be_truncated':len(jumps)>=cfg['within_molecule_examples_per_group'],'raw_precision_candidates':raw_candidates,'native_print_precision_verified':False,'actual_frame_verified':False}
        save(root/'details.json',json_safe(details));report={'schema':'LABEL_PAYLOAD_GROUP_REPORT_V1','status':'OWNER_PAYLOAD_SCANNED',
          'group_index':group['group_index'],'source_job_id':group['source_job_id'],'pid':os.getpid(),'records':group['expected_records'],'molecules':mols,
          'task_counts':dict(counts),'raw_payload_counts':dict(raw_counts),'field_stats':{k:dict(v) for k,v in stats.items()},'all_component_observations':{k:dict(v) for k,v in field_observations.items()},
          'structural_review_counts':dict(structural),'candidate_masks':ref(root/'candidate_masks.parquet'),'coverage':ref(root/'coverage.parquet'),
          'scalar_extrema_statistics_not_training_labels':ref(root/'scalar_extrema.sqlite'),'details':ref(root/'details.json'),
          'source_opens':opened,'source_closes':closed,'max_simultaneous_source_handles':1,'max_rss_bytes':maxrss,
          'elapsed_seconds':time.monotonic()-started,'unique_output_bytes':unique_bytes(root),'normal_raw_array_values_copied':False,
          'mask_candidates_frozen':False,'normalization_completed':False,'robust_z_state':'MATCHED_PILOT_TRAIN_REFERENCE' if WORK['calibration'] else 'PENDING_MATCHED_FULL_TRAIN_CALIBRATION'}
        save(root/'report.json',report);return {'report':ref(root/'report.json'),'pid':os.getpid(),'group_index':group['group_index']}
    except BaseException as exc:
        WORK['stop'].set()
        save(root/'failure.json',{'status':'PAYLOAD_GROUP_FAILED_PARTIALS_PRESERVED','error':str(exc),'type':type(exc).__name__,'task_counts':dict(counts)})
        raise
    finally:
        if handle is not None:handle.close()
        if writer is not None:writer.close()
        if coverage is not None:coverage.close()
        if outdb is not None:outdb.close()
        index.close()

def pre_scan_fixture_gate(root,proof_path):
    """Run the original six synthetic tests after admission, before data I/O."""
    import contextlib,importlib,io,traceback,unittest
    module_name='workflows.data_v1_final.labels.payload_audit_v1.test_payload'
    expected_path=Path(__file__).absolute().with_name('test_payload.py')
    source=small_ref(expected_path);request=load(proof_path)['request']
    need(source in request['source_references'],'ORIGINAL_FIXTURE_SOURCE_NOT_AUTHORIZED')
    stream=io.StringIO();discovered=None;result=None;exception=None;started=time.monotonic()
    try:
        with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
            module=importlib.import_module(module_name)
            need(Path(module.__file__).absolute()==expected_path,'ACTUAL_ORIGINAL_FIXTURE_MODULE_DIFFERS')
            loader=unittest.TestLoader();suite=loader.loadTestsFromModule(module)
            discovered=suite.countTestCases()
            need(not loader.errors and discovered==6,'EXACT_SIX_ORIGINAL_FIXTURES_REQUIRED')
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    except BaseException as exc:
        exception=type(exc).__name__+': '+str(exc);traceback.print_exc(file=stream)
    counts={'expected':6,'discovered':discovered,'run':result.testsRun if result is not None else 0,
      'failures':len(result.failures) if result is not None else 0,'errors':len(result.errors) if result is not None else 0,
      'skipped':len(result.skipped) if result is not None else 0,
      'expected_failures':len(result.expectedFailures) if result is not None else 0,
      'unexpected_successes':len(result.unexpectedSuccesses) if result is not None else 0}
    source_unchanged=small_ref(expected_path)==source
    passed=(exception is None and result is not None and result.wasSuccessful() and source_unchanged
      and counts['discovered']==counts['run']==6 and all(counts[k]==0 for k in
      ('failures','errors','skipped','expected_failures','unexpected_successes')))
    transcript=stream.getvalue();receipt={'schema':'LABEL_PAYLOAD_PRE_SCAN_FIXTURE_GATE_V1',
      'status':'PASS' if passed else 'FAIL_NO_REAL_PAYLOAD_STARTED','module':module_name,'source_reference':source,
      'source_unchanged_after_execution':source_unchanged,'counts':counts,'exception':exception,
      'transcript':transcript,'elapsed_seconds':time.monotonic()-started,
      'fresh_central_admission_completed':True,'scientific_payload_or_SQLite_opened':False}
    receipt_ref=save(Path(root)/'pre_scan_fixture_gate.json',receipt)
    print('BEGIN_PAYLOAD_PRE_SCAN_SIX_FIXTURES',flush=True)
    print(transcript,end='' if transcript.endswith('\n') else '\n',flush=True)
    print(json.dumps({'fixture_gate':receipt['status'],'counts':counts,'source_reference':source,'receipt':receipt_ref}),flush=True)
    print('END_PAYLOAD_PRE_SCAN_SIX_FIXTURES',flush=True)
    need(passed,'SIX_FIXTURES_MUST_ALL_PASS_BEFORE_REAL_PAYLOAD')
    return receipt_ref

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','output','startup-proof'):p.add_argument('--'+key,required=True)
    p.add_argument('--shard-id',type=int,required=True);a=p.parse_args();cfg=load(a.config)
    guard(cfg,a.config,a.startup_proof,cfg['shard_output_cap_bytes'])
    root=new_root(a.output);receipts=[]
    try:
        fixture_gate=pre_scan_fixture_gate(root,a.startup_proof)
        for pin in cfg['sources'].values():require(pin)
        plan=load(cfg['sources']['plan']['path']);require(plan['canonical_index'],content=False)
        groups=[g for g in plan['groups'] if g['shard_id']==a.shard_id];need(len(groups)>=16 or plan['mode']=='full','SIXTEEN_ACTUAL_PILOT_WORKERS')
        ctx=multiprocessing.get_context('spawn');stop=ctx.Event();barrier=ctx.Barrier(16)
        # Full shards are grouped whole-owner; first pilot is exactly16 groups.
        need(len(groups)>=16,'FULL_SHARD_MUST_HAVE_16_GROUP_TASKS_USE_FEWER_SHARDS')
        with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=init_worker,initargs=(cfg,plan,str(root),stop,barrier)) as executor:
            drain_submit([(g,i<16) for i,g in enumerate(groups)],executor,run_group,receipts,stop_requested,stop)
        need(len({r['pid'] for r in receipts})==16,'SIXTEEN_REAL_PAYLOAD_WORKERS')
        need(unique_bytes(root)+(8<<20)<=cfg['shard_output_cap_bytes'],'SHARD_OUTPUT_CAP')
        result={'schema':'LABEL_PAYLOAD_SHARD_MANIFEST_V1','status':'PAYLOAD_SHARD_SCANNED_REDUCTION_REQUIRED','mode':plan['mode'],
          'config':ref(a.config),'plan':cfg['sources']['plan'],'shard_id':a.shard_id,'groups':sorted(receipts,key=lambda r:r['group_index']),
          'pre_scan_fixture_gate':fixture_gate,'pre_scan_fixture_tests_passed':6,
          'candidate_masks_frozen':False,'normalization_completed':False,'guide_1_5_completed':False,'unique_output_bytes':unique_bytes(root)}
        save(root/'manifest.json',result);print(json.dumps({'status':result['status'],'groups':len(receipts),'pre_scan_fixture_tests_passed':6}))
    except BaseException as exc:
        save(root/'failure.json',{'status':'PAYLOAD_SHARD_FAILED_NO_AUTORETRY','error':str(exc),'closed_group_receipts':receipts});raise
if __name__=='__main__':main()