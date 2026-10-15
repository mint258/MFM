#!/usr/bin/env python3
"""Read-only current G6 storage wire audit. No QM/LMDB/source edits/deletion."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,hashlib,json,multiprocessing,os,sqlite3,time
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
import wp5_archive_v4 as A
BARRIER=None;DEADLINE=None
CACHE_NAMES={'xtbrestart','input.res','input.den'}
REQUIRED={'input.out','input.aux','process.out','xtbout.json','wbo','gradient','fod'}
SOURCE_HASHES={'wp5_engine.py':'33fc5f7917b3e96846dccea9dc4b771a0f1f0c82d431fd35ddf9cfa61e7537cb',
'wp5_archive_v4.py':'56039c79a353a0c2c1459add065f6aa46ca0514e2b8bee18fbf5ccd97c94939b',
'wp5_runner_v6.py':'85560d96a67e16387916e2667f3512ad9e1189c865e0d945ac0ff138a821cd8d'}
def read(p):return json.loads(Path(p).read_text())
def ro(p):
    db=sqlite3.connect('file:'+quote(str(Path(p).absolute()),safe='/')+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');return db
def init(barrier,deadline):
    global BARRIER,DEADLINE
    BARRIER=barrier;DEADLINE=deadline

def classify(name,data,role):
    try:data.decode('utf-8');utf8=True
    except UnicodeDecodeError:utf8=False
    binary=(b'\x00' in data) or not utf8
    candidate=role=='output' and name in CACHE_NAMES and binary
    return {'utf8_strict':utf8,'has_NUL':b'\x00' in data,'known_restart_cache_name':name in CACHE_NAMES,
            'candidate_cache_only':candidate,'parser_source_artifact':name in REQUIRED,
            'classification':'INPUT_ALWAYS' if role=='input' else ('BINARY_RESTART_CANDIDATE' if candidate else ('TEXT_OUTPUT_PRESERVE' if not binary else 'UNKNOWN_BINARY_PRESERVE'))}

def lane(items,manifest,level):
    BARRIER.wait(timeout=120)
    result={'pid':os.getpid(),'cases':[],'members':[],'errors':[]};readers={}
    try:
        for item in items:
            path=item['archive_path'];reader=readers.get(path)
            if reader is None:reader=readers[path]=A.ArchiveReader(path,manifest)
            legacy={};legacy_path=None
            bucket=int(hashlib.sha256(item['molecule_id'].encode()).hexdigest()[:16],16)%16
            key=hashlib.sha256(item['molecule_id'].encode()).hexdigest()[:24]
            candidate=ROOT.parent/'phase1_dataset_rebuild_20261010'/f'wp4_native_full_v4/bucket_{bucket}/molecules/{key}/results.parquet'
            if candidate.exists():
                import pyarrow.parquet as pq
                oldrows=pq.read_table(candidate,columns=['record_id','task','aux_bytes','payload_sha256'],use_threads=False).to_pylist()
                legacy={(r['record_id'],r['task']):r for r in oldrows};legacy_path=str(candidate)
            if time.monotonic()>=DEADLINE:raise TimeoutError('INTERNAL46H_METADATA_AUDIT_DEADLINE')
            for rid,calc in reader.db.execute('SELECT record_id,calc_type FROM records WHERE molecule_id=? ORDER BY record_id,calc_type',(item['molecule_id'],)):
                try:
                    if time.monotonic()>=DEADLINE:raise TimeoutError('INTERNAL46H_METADATA_AUDIT_DEADLINE')
                    raw=reader.get(rid,calc);d=reader.dicts[calc]['data'];meta=raw['metadata']
                    inputs=raw['input_files'];outputs=raw['output_files']
                    if outputs is None:raise ValueError('SOURCE_ALL_RAW_OUTPUT_NOT_RETAINED')
                    packed=reader.db.execute('SELECT input_bytes,raw_bytes,metadata_bytes,length(input_frame),length(raw_frame),length(metadata_frame),length(CAST(output_manifest AS BLOB)) FROM records WHERE record_id=? AND calc_type=?',(rid,calc)).fetchone()
                    full_frame=len(reader.zstd.compress(A.bundle(outputs)[0],d))
                    # Exact ALL G6 compression comparison; no claim additive per-file frames.
                    if full_frame!=packed[4]:raise ValueError('ACTUAL_STORED_FRAME_RECOMPRESSION_SIZE_DIFFERS')
                    kept=[];cache=[];aux=[]
                    for role,files in (('input',inputs),('output',outputs)):
                        for f in files:
                            c=classify(f['name'],f['data'],role)
                            frame=len(reader.zstd.compress(A.bundle([f])[0],d))
                            member={k:v for k,v in f.items() if k!='data'}
                            member.update(record_id=rid,molecule_id=item['molecule_id'],calc_type=calc,
                                size_stratum=item['size_stratum'],node=item['node'],role=role,
                                atoms=item['atoms'],standalone_bundle_compressed_bytes=frame,**c)
                            result['members'].append(member)
                            if role=='output':
                                (cache if c['candidate_cache_only'] else kept).append(f)
                                if f['name']=='input.aux':aux.append(f)
                    kept_frame=len(reader.zstd.compress(A.bundle(kept)[0],d)) if kept else len(reader.zstd.compress(A.bundle([])[0],d))
                    no_manifest=dict(meta);no_manifest.pop('output_file_manifest',None)
                    meta_no_manifest_frame=len(reader.zstd.compress(A.canonical(no_manifest),d))
                    case={'record_id':rid,'molecule_id':item['molecule_id'],'calc_type':calc,'size_stratum':item['size_stratum'],
                        'node':item['node'],'atoms':item['atoms'],'source_status':raw['source_status'],'scope_status':raw['scope_status'],
                        'is_minimum':bool(meta.get('is_minimum')),'archive_path':path,'input_frame_bytes':packed[3],
                        'full_output_frame_bytes':packed[4],'metadata_frame_bytes':packed[5],
                        'uncompressed_SQL_output_manifest_bytes':packed[6],
                        'metadata_without_duplicate_output_manifest_frame_bytes':meta_no_manifest_frame,
                        'output_without_binary_restart_candidate_frame_bytes':kept_frame,
                        'joint_binary_restart_candidate_saved_bytes':packed[4]-kept_frame,
                        'candidate_names':[f['name'] for f in cache],
                        'AUX_raw_bytes':sum(f['byte_count'] for f in aux),
                        'AUX_compressed_bundle_bytes':len(reader.zstd.compress(A.bundle(aux)[0],d)) if aux else 0,
                        'input_names':[f['name'] for f in inputs],
                        'input_recipe_snapshot_present':any(f['name']=='input_recipe.json' for f in inputs),
                        'all_source_members_SHA_verified':True}
                    old=legacy.get((rid,calc),{})
                    old_aux=old.get('aux_bytes');new_aux=case['AUX_raw_bytes']
                    case.update(legacy_source_results=legacy_path,legacy_AUX_raw_bytes=old_aux,
                        legacy_source_payload_match=(old['payload_sha256']==meta.get('source_payload_sha256')) if old else None,
                        current_to_legacy_AUX_byte_ratio=(new_aux/old_aux) if old_aux and new_aux else None,
                        legacy_recipe_context='OLD_PILOT_PM7_B_WITH_POLAR_OTHER_TASK_KEYWORDS_UNCHANGED')
                    result['cases'].append(case)
                except Exception as exc:result['errors'].append({'record_id':rid,'calc_type':calc,'archive_path':path,'error':str(exc)})
    finally:
        for reader in readers.values():reader.close()
    return result

def aggregate(rows,keys,fields):
    groups={}
    for row in rows:
        key=tuple(row[k] for k in keys)
        if key not in groups:groups[key]={**dict(zip(keys,key)),'observations':0,**{f:0 for f in fields}}
        out=groups[key];out['observations']+=1
        for f in fields:out[f]+=row[f]
    return list(groups.values())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,action='append',default=[])
    ap.add_argument('--dictionaries',type=Path,default=ROOT/'dictionaries/job_4513894/dictionary_manifest.json')
    ap.add_argument('--output',type=Path);ap.add_argument('--workers',type=int,default=24);ap.add_argument('--level',type=int,default=3)
    ap.add_argument('--check',action='store_true');args=ap.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text())
        assert classify('xtbrestart',b'\x00binary','output')['candidate_cache_only']
        assert not classify('gradient',b'\x00','output')['candidate_cache_only']
        assert not classify('input.res',b'text','output')['candidate_cache_only']
        assert not classify('input.res',b'\x00','input')['candidate_cache_only']
        print('STORAGE_WIRE_AUDIT_AST_CLASSIFICATION_PASS_NO_QM_NO_DATA');return
    if args.level!=3:raise ValueError('Actual archive compression level must remain3')
    if args.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<args.workers:raise ValueError('Allocated >=16 actual workers required')
    if not args.report or args.output is None:raise ValueError('Source reports and new output required')
    args.output.mkdir(parents=True,exist_ok=False);started=time.time();sources=[];molecules=[];queues=[];archives={}
    for name,expected in SOURCE_HASHES.items():
        path=ROOT/'scripts'/name;actual=A.file_sha(path)
        if actual!=expected:raise ValueError('ACTIVE_SOURCE_HASH_DIFFERS:'+name)
        sources.append({'path':str(path),'sha256':actual})
    for rp in args.report:
        report=read(rp)
        if report['status'] not in ('G6_FULL_CHAIN_PASSED','G6_FULL_CHAIN_PASSED_WITH_RECORDED_SCIENTIFIC_OUTCOMES') or report.get('issues'):raise ValueError('Only closed valid G6 report')
        cohort=Path(report.get('source_run') or rp.parent);qp=Path(report.get('queue') or cohort/'queue.sqlite')
        selection=read(cohort/'selected_molecules.json')
        selected=selection if isinstance(selection,list) else selection.get('selected_molecules',selection.get('molecules',selection.get('rows',[])))
        size={r['molecule_id']:int(r.get('max_total_atoms',r.get('total_atoms'))) for r in selected}
        import pyarrow.parquet as pq
        frame=pq.read_table(rp.parent/'raw_compression_by_record.parquet',columns=['molecule_id','size_stratum'],use_threads=False).to_pylist()
        strata={r['molecule_id']:r['size_stratum'] for r in frame}
        db=ro(qp)
        try:
            rows=[dict(r) for r in db.execute('SELECT molecule_id,state,archive_path,export_json,receipt_json FROM molecules ORDER BY molecule_id')]
            if len(rows)!=20 or any(r['state']!='COMPLETE' for r in rows):raise ValueError('Latest20 molecule queue not closed')
            export_bytes=sum(len(r['export_json'].encode()) if r['export_json'] else 0 for r in rows)
            unique={r['export_json'] for r in rows if r['export_json']}
            queues.append({'path':str(qp),'node':report['node'],'physical_bytes':qp.stat().st_size,
                'molecules':len(rows),'export_JSON_repeated_bytes':export_bytes,
                'unique_export_JSON_bytes':sum(len(s.encode()) for s in unique),'unique_export_JSON_values':len(unique),
                'candidate_normalize_saved_uncompressed_bytes':export_bytes-sum(len(s.encode()) for s in unique),
                'stage_compressed_wire_bytes':sum(json.loads(r['receipt_json'])['stage_compressed_wire_bytes'] for r in rows)})
            for r in rows:
                p=Path(r['archive_path']);archives[str(p)]={'path':str(p),'bytes':p.stat().st_size}
                molecules.append({'molecule_id':r['molecule_id'],'archive_path':str(p),'node':report['node'],
                    'atoms':size[r['molecule_id']],'size_stratum':strata[r['molecule_id']]})
        finally:db.close()
        sources.append({'path':str(rp),'sha256':A.file_sha(rp)})
    batches=[molecules[i::args.workers] for i in range(args.workers)]
    if any(not b for b in batches):raise ValueError('Insufficient independent molecules for effective workers')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(args.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,initializer=init,initargs=(barrier,time.monotonic()+46*3600)) as pool:
        results=list(pool.map(lane,batches,[args.dictionaries]*args.workers,[args.level]*args.workers,chunksize=1))
    cases=[r for worker in results for r in worker['cases']];members=[r for worker in results for r in worker['members']];errors=[r for worker in results for r in worker['errors']]
    case_fields=['input_frame_bytes','full_output_frame_bytes','metadata_frame_bytes','uncompressed_SQL_output_manifest_bytes',
        'metadata_without_duplicate_output_manifest_frame_bytes','output_without_binary_restart_candidate_frame_bytes',
        'joint_binary_restart_candidate_saved_bytes','AUX_raw_bytes','AUX_compressed_bundle_bytes']
    import pyarrow as pa,pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(cases),args.output/'cases.parquet',compression='zstd')
    pq.write_table(pa.Table.from_pylist(members),args.output/'members.parquet',compression='zstd')
    aux_comparisons=[]
    for calc,stratum in sorted({(r['calc_type'],r['size_stratum']) for r in cases if r['AUX_raw_bytes']}):
        rows=[r for r in cases if r['calc_type']==calc and r['size_stratum']==stratum and r['current_to_legacy_AUX_byte_ratio'] is not None]
        ratios=[r['current_to_legacy_AUX_byte_ratio'] for r in rows]
        aux_comparisons.append({'calc_type':calc,'size_stratum':stratum,'paired_cases':len(rows),
            'current_raw_AUX_bytes':sum(r['AUX_raw_bytes'] for r in rows),
            'legacy_raw_AUX_bytes':sum(r['legacy_AUX_raw_bytes'] for r in rows),
            'ratio_min':min(ratios) if ratios else None,'ratio_max':max(ratios) if ratios else None,
            'ratio_mean':sum(ratios)/len(ratios) if ratios else None,
            'source_payload_mismatches':sum(r['legacy_source_payload_match'] is False for r in rows)})
    report={'status':'READ_ONLY_STORAGE_WIRE_AUDIT_COMPLETE' if not errors else 'AUDIT_HAS_ERRORS','job_id':os.environ.get('SLURM_JOB_ID'),
        'source_sha256':A.file_sha(__file__),'source_bindings':sources,'dictionary_manifest_sha256':A.file_sha(args.dictionaries),
        'worker_pids':sorted({r['pid'] for r in results}),'actual_worker_count':len({r['pid'] for r in results}),
        'elapsed_seconds':time.time()-started,'molecule_observations':len(molecules),'case_observations':len(cases),
        'errors':errors,'queues':queues,'archives':list(archives.values()),'AUX_size_paired_comparisons':aux_comparisons,
        'case_by_task_stratum':aggregate(cases,['calc_type','size_stratum'],case_fields),
        'member_by_task_stratum_name_role_class':aggregate(members,['calc_type','size_stratum','name','role','classification'],['byte_count','standalone_bundle_compressed_bytes']),
        'scope_changed':False,'QM_started':False,'LMDB_read_or_written':False,'files_deleted':False,
        'candidate_exclusion_rule':'Exact known restart name AND actual bytes binary; other outputs and all inputs kept. Candidate measurement only, not approved production scope.',
        'standalone_compression_warning':'Per-file compressed bytes are diagnostic and not additive replacement for joint-bundle measured saving.',
        'stage_has_no_raw_body':'Frozen engine passes raw_sink, raw_records empty; frozen archive metadata excludes files. Existing retired stage not reconstructed.',
        'references':['https://openmopac.net/Manual/Running_MOPAC.html','https://openmopac.net/Manual/restart.html','https://openmopac.net/Manual/t%3Dn.html','https://xtb-docs.readthedocs.io/en/latest/commandline.html']}
    report['outputs']=[{'path':str(args.output/name),'bytes':(args.output/name).stat().st_size,'sha256':A.file_sha(args.output/name)} for name in ('cases.parquet','members.parquet')]
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','actual_worker_count','elapsed_seconds','case_observations','scope_changed')}))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
