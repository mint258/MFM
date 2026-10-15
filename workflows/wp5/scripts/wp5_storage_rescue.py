"""Recover CLOSED G3 files after driver finalize failed; metadata/raw read-only.

No dictionary retraining, no science Parquet rewriting, no QM/LMDB. Missing
retired staging measurements are NULL; G6 actual staged wire drives final budget.
Original failed driver and files remain unchanged. Root sole submission.
"""
from __future__ import annotations
import argparse,ast,concurrent.futures,json,multiprocessing,os,socket,sys,time
from collections import defaultdict
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
DEPS=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(DEPS/'deps'),str(DEPS/'scripts/deps')]
import wp5_archive_v4 as A
BARRIER=None
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    p=Path(path);q=p.with_name(p.name+'.pending');q.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');q.replace(p)
def init(barrier):
    global BARRIER;BARRIER=barrier
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);BARRIER.wait(timeout=240)
def recover_worker(item):
    import pyarrow.parquet as pq
    rank,root,manifest,out=item;directory=Path(root)/f'worker_{rank:02d}'
    metrics=[];staged=[];aux_ratios=[];refs=None;archives={};source_cache={};minimum_seen=set();codec=A.Zstd();dicts=A.load_dictionaries(manifest)
    for policy in ('ALL','SELECTIVE'):
        path=directory/(policy+'.sqlite')
        reader=A.ArchiveReader(path,manifest)
        try:
            if reader.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Original G3 worker container integrity fails')
            if reader.db.execute('SELECT count(*) FROM parsed_molecules').fetchone()[0]!=0:raise ValueError('Worker has not completed retirement/validation')
            exports=[json.loads(r[0]) for r in reader.db.execute('SELECT references_json FROM parquet_exports')]
            if len(exports)!=1:raise ValueError('Expected one immutable complete family reference set per worker')
            recovered=exports[0]
            if refs is None:
                refs=recovered
                for ref in refs:
                    p=Path(ref['path'])
                    if p.stat().st_size!=ref['bytes'] or A.file_sha(p)!=ref['sha256']:raise ValueError('Scientific Parquet source SHA/bytes changed')
                    if pq.ParquetFile(p).metadata.num_rows!=ref['rows']:raise ValueError('Scientific Parquet physical rows changed')
            elif recovered!=refs:raise ValueError('ALL/SELECTIVE family reference sets differ')
            for row in reader.db.execute('SELECT * FROM records ORDER BY molecule_id,record_id,calc_type'):
                rid,task,mid=row['record_id'],row['calc_type'],row['molecule_id'];raw=reader.get(rid,task);meta=raw['metadata']
                original_ref=meta['source_reference']['source_Parquet'];key=original_ref['path']
                if key not in source_cache:
                    p=Path(key)
                    if p.stat().st_size!=original_ref['bytes'] or A.file_sha(p)!=original_ref['sha256']:raise ValueError('Original scientific reference Parquet changed')
                    source_cache[key]={(v['record_id'],v['task']):json.loads(v['details_json']) for v in pq.read_table(p,columns=['record_id','task','details_json'],use_threads=False).to_pylist()}
                detail=source_cache[key][(rid,task)]
                full=meta['output_file_manifest'];expected={f['name']:f for f in detail.get('archived_files',[])}
                if set(expected)!={f['name'] for f in full}:raise ValueError('Recovered original output member names differ')
                for f in full:
                    old=expected[f['name']]
                    if (f['bytes'],f['sha256'])!=(old['bytes'],old['sha256']):raise ValueError('Original output per-member SHA differs')
                # Input bundles and each retained output byte already verified by get().
                if raw['input_origin']!='RECONSTRUCTED_INPUT':raise ValueError('Legacy input origin was mislabeled')
                aux_size=detail.get('aux_bytes');actual_aux=sum(f['bytes'] for f in full if f['name'].endswith('.aux'))
                missing=max(0,aux_size-actual_aux) if aux_size is not None else None
                known=sum(f['bytes'] for f in full)
                inputs=sum(f['byte_count'] for f in raw['input_files'] if f['name']!='input_recipe.json')
                total=detail.get('raw_total_bytes');residual=max(0,total-known-inputs-(missing or 0)) if total is not None else None
                metrics.append({'container_path':str(path),'record_id':rid,'molecule_id':mid,'calc_type':task,'policy':policy,
                    'dict_id':row['dict_id'],'input_sha256':bytes(row['input_sha256']).hex(),'raw_sha256':bytes(row['raw_sha256']).hex(),
                    'retention_reason':row['retention_reason'],'output_retained':row['raw_frame'] is not None,
                    'input_frame_bytes':len(row['input_frame']),'raw_frame_bytes':len(row['raw_frame']) if row['raw_frame'] is not None else 0,
                    'metadata_frame_bytes':len(row['metadata_frame']),'input_bundle_bytes':row['input_bytes'],'raw_bundle_bytes':row['raw_bytes'],
                    'size_stratum':meta['size_stratum'],'is_minimum':bool(meta['is_minimum']),
                    'source_status':row['source_status'],'scope_status':row['scope_status'],
                    'formal_excluded_calibration_only':bool(meta['formal_excluded_calibration_only']),
                    'missing_aux_raw_bytes':missing,'unclassified_unstored_scratch_bytes':residual})
                if policy=='ALL' and actual_aux:
                    files=[f for f in raw['output_files'] if f['name'].endswith('.aux')]
                    frame=codec.compress(A.bundle(files)[0],dicts[task]['data'])
                    aux_ratios.append({'calc_type':task,'size_stratum':meta['size_stratum'],'raw_aux_bytes':actual_aux,
                        'dict_aux_bundle_bytes':len(frame),'ratio':len(frame)/actual_aux,
                        'recovered_by_lossless_compression_of_already_retained_AUX_bytes':True})
            for mid,n,wire in reader.db.execute('SELECT molecule_id,record_count,wire_sha256 FROM completion_receipts'):
                staged.append({'policy':policy,'molecule_id':mid,'record_count':n,'wire_sha256':wire,
                    'compressed_wire_bytes':None,'uncompressed_wire_bytes':None,
                    'missing_reason':'Temporary wire retired and VACUUM completed; size was only returned through lost driver IPC, not durable receipt. Actual G6 wire replaces this estimate.'})
            archives[policy]={'path':str(path),'bytes':path.stat().st_size,'sha256':A.file_sha(path)}
        finally:reader.close()
    codec.close()
    info={'worker_pid':os.getpid(),'original_worker_rank':rank,'metrics':metrics,'staged':staged,'family_files':refs,
        'aux_ratios':aux_ratios,'issues':[],'archives':archives,
        'verified_typed_family_rows':sum(r['rows'] for r in refs),
        'typed_roundtrip_evidence':'Original frozen worker retires temporary wire only after exact Arrow/f64 readback; completion+export catalog and zero staged rows prove predecessor control flow. Source files SHA and physical rows rechecked here.',
        'raw_input_and_original_member_readback_reverified':True}
    save(Path(out)/f'recovered_worker_{rank:02d}.json',info);return info
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');p.add_argument('--workers',type=int,default=16)
    p.add_argument('--source-root',default=str(ROOT/'gates/g3/job_4513894'));p.add_argument('--output')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('AST_PASS_RECOVERY_NO_QM_PARQUET_WRITE');return
    if a.workers!=16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<16:raise ValueError('Exactly16 allocated effective file recovery workers')
    if socket.gethostname().split('.')[0] not in {f'compute-0-{n}' for n in range(14,20)}:raise ValueError('WP5 nodes14..19 only')
    job=os.environ['SLURM_JOB_ID'];source=Path(a.source_root);out=Path(a.output or ROOT/'gates/g3'/f'rescue_{job}').absolute()
    if out.exists() or not out.is_relative_to(ROOT):raise ValueError('Fresh own recovery output required')
    out.mkdir(parents=True);start=time.monotonic();original_job=source.name.removeprefix('job_')
    manifest=ROOT/'dictionaries'/('job_'+original_job)/'dictionary_manifest.json'
    dictionary_sha=A.file_sha(manifest);dictionary_data=read(manifest);A.load_dictionaries(manifest)
    if len(dictionary_data['dictionaries'])!=12:raise ValueError('Original actual12 dictionaries required')
    closure=read(source/'formal_pilot_source_context.context_closure.json')
    if (closure['formal_eligible_pilot_records']+closure['known_excluded_calibration_only_records'])!=10020 or closure['unknown_pilot_records'] or closure['overlap_records']:
        raise ValueError('MANIFEST_SOURCE_CONTEXT_NOT_CLOSED')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(barrier,)) as pool:
        workers=list(pool.map(recover_worker,[(i,str(source),str(manifest),str(out)) for i in range(a.workers)],chunksize=1))
    pids=sorted({w['worker_pid'] for w in workers})
    if len(pids)!=16:raise ValueError('Actual16 recovery PIDs not observed')
    metrics=[r for w in workers for r in w['metrics']];all_rows=[r for r in metrics if r['policy']=='ALL'];keys={(r['record_id'],r['calc_type']) for r in all_rows}
    if len(all_rows)!=120240 or len(keys)!=120240:raise ValueError('MANIFEST_SOURCE120240_NOT_CLOSED')
    mols={r['molecule_id'] for r in all_rows};ids={r['record_id'] for r in all_rows}
    if (len(mols),len(ids))!=(1441,10020):raise ValueError('MANIFEST_SOURCE10020_1441_NOT_CLOSED')
    recipe=source/'formal_input_recipe_snapshot.json';consolidated={}
    for policy in ('ALL','SELECTIVE'):
        old=source/(policy+'_consolidated.sqlite')
        if old.is_file():
            reader=A.ArchiveReader(old,manifest)
            try:
                if reader.db.execute('SELECT count(*) FROM records').fetchone()[0]!=120240 or reader.db.execute('SELECT count(*) FROM molecules').fetchone()[0]!=1441:raise ValueError('Existing complete science archive counts changed')
                for rid,task in reader.db.execute('SELECT record_id,calc_type FROM records'):reader.get(rid,task)
            finally:reader.close()
            consolidated[policy]={'path':str(old),'bytes':old.stat().st_size,'sha256':A.file_sha(old),
                'raw_records':120240,'molecules':1441,'reused_original_complete_archive':True,'source_not_mutated':True}
        else:
            consolidated[policy]=A.consolidate_archives([w['archives'][policy]['path'] for w in workers],out/(policy+'_consolidated.sqlite'),manifest,recipe,policy=policy,verify_raw=True)
    # Finish only the technical common-reference/epoch fixture under corrected module.
    fixture=source/'consolidation_fixture';lanes=[fixture/f'lane_{i:02d}.sqlite' for i in range(16)]
    if not all(p.is_file() for p in lanes):raise ValueError('Original16 actual technical fixture lanes absent')
    merged=A.consolidate_archives(lanes,out/'technical_fixture_consolidated.sqlite',manifest,recipe,policy='ALL',verify_raw=True)
    reader=A.ArchiveReader(merged['path'],manifest)
    try:
        exports=reader.db.execute('SELECT count(*) FROM parquet_exports').fetchone()[0]
        catalog=json.loads(reader.db.execute("SELECT value FROM metadata WHERE key='consolidation_source_catalog'").fetchone()[0])
        epochs=[r['verified_epoch'] for s in catalog for r in s['parquet_export_verification_epochs']]
        if exports!=1 or len(catalog)!=16 or len(epochs)!=16 or len(set(epochs))<2:raise ValueError('Recovered technical common-ref/epoch preservation failed')
    finally:reader.close()
    counts={};all_counts={};isolated={}
    for key in {r['size_stratum'] for r in all_rows}:
        cases=[r for r in all_rows if r['size_stratum']==key]
        def group(values):return {'records':len({r['record_id'] for r in values}),'molecules':len({r['molecule_id'] for r in values})}
        counts[key]=group([r for r in cases if not r['formal_excluded_calibration_only']]);all_counts[key]=group(cases)
        isolated[key]=group([r for r in cases if r['formal_excluded_calibration_only']])
    memory_path=source/'memory_observations.json'
    report={'status':'G3_ALL_PILOT12_ARCHIVE_AND_FAMILY_BENCHMARK_CLOSED','recovery_status':'FILES_CLOSED_DRIVER_FINALIZE_REPAIRED_NO_SCIENCE_RECOMPUTE',
        'original_driver_status':'FAILED_AFTER_SCIENTIFIC_WORKERS_CLOSED','original_driver_job_id':original_job,'recovery_job_id':job,
        'records':10020,'molecules':1441,'calc_rows':120240,'actual_reader_pids':None,'actual_benchmark_worker_pids':None,
        'actual_recovery_pids':pids,'original_worker_pids_are_not_reconstructed':True,
        'dictionary_manifest':{'path':str(manifest),'sha256':dictionary_sha},'sample_strata':counts,
        'all_pilot_sample_strata':all_counts,'calibration_only_strata':isolated,'formal_context_closure':closure,
        'workers':workers,'consolidated':consolidated,'consolidation_fixture':{'merge':merged,'same_references_distinct_epochs':'PASS','raw_members':'READBACK_PASS'},
        'seconds':time.monotonic()-start,'formal_sample_context':{'path':str(source/'formal_pilot_source_context.parquet'),'records':10020,'sha256':A.file_sha(source/'formal_pilot_source_context.parquet')},
        'family_float64_bit_and_row_roundtrip':'PREDECESSOR_VALIDATION_PROVEN_BY_RETIREMENT_AND_FROZEN_CONTROL_FLOW',
        'verified_family_rows':sum(w['verified_typed_family_rows'] for w in workers),
        'source_input_origin':'RECONSTRUCTED_INPUT_NOT_HISTORICAL_ORIGINAL','scientific_raw_scope_complete':False,
        'scope_limit':'Old raw lacked most AUX and new full-directory outputs. Actual G6 complete members supply missing-byte calibration. Legacy retired wire sizes cannot be recovered and remain NULL.',
        'staging_measurements_original_lost':True,'use_actual_G6_staging_in_final_model':True,
        'source_failed_driver_code':{'path':str(ROOT/'scripts/wp5_storage_gate_v4.py'),'sha256':A.file_sha(ROOT/'scripts/wp5_storage_gate_v4.py')},
        'corrected_archive_source':{'path':str(Path(A.__file__)),'sha256':A.file_sha(A.__file__)},
        'original_memory_observations':read(memory_path) if memory_path.is_file() else None,
        'dictionaries_retrained':False,'science_parquet_rewritten':False,'QM_started':False,'LMDB_created':False,
        'original_source_files_written_or_deleted':False,'source_sha256':A.file_sha(__file__)}
    save(out/'benchmark.json',report)
    if A.file_sha(manifest)!=dictionary_sha:raise ValueError('Original dictionary manifest changed during recovery')
    print(json.dumps({'status':report['recovery_status'],'path':str(out/'benchmark.json'),'records':10020,'molecules':1441,'actual_workers':len(pids),'stage_original_size':'NULL_G6_ACTUAL_REQUIRED'}))
if __name__=='__main__':main()
