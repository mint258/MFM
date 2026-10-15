#!/usr/bin/env python3
"""New-policy physical storage prototype from immutable full-output G6 witnesses.

No QM, no source/archive mutation, no input body written. Output-only TEST
containers measure retained-case SQLite footprint; a second policy container
proves ordinary successful calls create no shared record row. Trace columns
use the production Parquet v2 Arrow types. Root sole submission.
"""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,json,multiprocessing,os,pickle,re,socket,sqlite3,sys,time
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
DEPS=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(DEPS/'deps'),str(DEPS/'scripts/deps')]
import wp5_archive_v4 as OLD
import wp5_archive_v5 as NEW
import wp5_scf_metadata_v2 as SCF
NODES={'compute-0-'+str(n) for n in (12,13,14,17,18,19)}
FAIL={'CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}
TRACE=('status','software_version_id','elapsed_seconds','scf_iterations','converged','input_file_sha256','input_bundle_sha256',
 'raw_audit_selected','reproduction_package_sha256','precision_by_field_json','registry_source_evidence_json','raw_output_locator_json')
BARRIER=None
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':OLD.file_sha(p)}
def save(p,j):
    with Path(p).open('x') as h:json.dump(j,h,indent=2,allow_nan=False);h.write('\n')
def ro(p):
    db=sqlite3.connect('file:'+quote(str(Path(p).absolute()),safe='/')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;return db
def init(barrier):
    global BARRIER;BARRIER=barrier
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    BARRIER.wait(timeout=180)
def normal_status(value):
    if value in {'SUCCESS',*FAIL}:return value
    if value in {'RESOURCE_LIMIT_FAILED','SOURCE_READ_FAILED','QM_EXIT_OR_SCF_FAILED'}:return 'CALCULATION_FAILED'
    raise ValueError('Unmapped original actual calculation status:'+str(value))
def precision_from_actual_output(calc,outputs,inputs,parser):
    """Exact existing parser's printed precision rules; no AUX/numerical reparse."""
    if not calc.startswith('xtb_'):return {}
    bodies={f['name']:f['data'] for f in outputs};xyz=next((f['data'] for f in inputs if f['name']=='input.xyz'),None)
    if xyz is None:return None # historical unknown, not an invented precision
    symbols=[line.split()[0] for line in xyz.decode().splitlines()[2:] if line.strip()]
    text=bodies.get('process.out',b'').decode(errors='replace')
    raw=json.loads(bodies['xtbout.json']) if 'xtbout.json' in bodies else {}
    table,_=parser.d4_table(text,symbols);rounding={}
    if table:
        if raw.get('partial charges') is None:rounding['charges_e']=table['rounding_decimal_places']['charges_e']
        rounding.update({k:v for k,v in table['rounding_decimal_places'].items() if k!='charges_e'})
    if raw.get('dipole / a.u.') is None and 'molecular dipole:' in text:
        hit=re.search(r'full:\s*('+parser.FLOAT+r')\s+('+parser.FLOAT+r')\s+('+parser.FLOAT+r')',text.split('molecular dipole:')[-1])
        if hit:rounding['dipole_Debye']=min(parser.decimal_places(v) for v in hit.groups())
    orbs=raw.get('orbital energies / eV',[]);occ=raw.get('fractional occupation',[])
    filled=[i for i,x in enumerate(occ) if x>1e-6];h=max(filled) if filled else None
    for key,marker,available in (('homo_eV','HOMO',h is not None and h<len(orbs)),('lumo_eV','LUMO',h is not None and h+1<len(orbs))):
        if available:continue
        lines=[x for x in text.splitlines() if re.search(r'\('+marker+r'\)',x)]
        for line in lines[-1:]:
            nums=[token for token in line.split() if re.fullmatch(parser.FLOAT,token)]
            if len(nums)>=3:rounding[key]=parser.decimal_places(nums[-1])
    return rounding
def restore_detail(row,entries,parquet):
    """Decode exact existing cells solely to generate source/coverage metadata."""
    by_id={int(e['registry_id']):e for e in entries};detail={}
    for c in row['values']:
        e=by_id[int(c['registry_id'])];v=parquet.decode(c)
        if v is parquet.MISSING:continue
        parts=e['source_path'].split('.')
        if parts[0] in ('detail','details'):parts=parts[1:]
        place=detail
        for key in parts[:-1]:
            if key not in place or not isinstance(place[key],dict):place[key]={}
            place=place[key]
        place[parts[-1]]=v
    detail['task']=row['calc_type'];detail['record_id']=row['record_id'];detail['molecule_id']=row['molecule_id']
    return detail
def worker(arg):
    import pyarrow as pa,pyarrow.parquet as pq
    import wp5_parquet_v2 as PARQ
    import wp5_engine_v2 as ENGINE
    import wp5_parser as PARSER
    rank,molecules,manifest,audit_ids,out,protocol,audit_ref=arg
    registry_entries=PARQ.registry(read(protocol)['registry']['path']);ENGINE.REGISTRY=registry_entries
    root=Path(out)/('worker_%02d'%rank);root.mkdir()
    all_writer=NEW.ArchiveWriter(root/'retained_case_measurement_TEST.sqlite',manifest,recipe_manifest=protocol,audit_membership=audit_ref)
    policy_writer=NEW.ArchiveWriter(root/'user_policy_TEST.sqlite',manifest,recipe_manifest=protocol,audit_membership=audit_ref)
    trace_schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('calc_type',pa.string()),('size_stratum',pa.string()),('file_group',pa.int8())]+[PARQ.SCHEMA.field(name) for name in TRACE])
    cases=[];trace_rows=[];stage_extra=[];readers={};detail_cache={};errors=[]
    try:
        for item in molecules:
            path=item['archive_path'];reader=readers.get(path)
            if reader is None:reader=readers[path]=OLD.ArchiveReader(path,manifest)
            details=detail_cache.get(path)
            if details is None:
                details={};export=read(Path(path).parent/'export_completion.json')
                for family in export['families']:
                    pp=Path(family['path']);schema=pq.read_schema(pp)
                    if not {'record_id','calc_type','elapsed_seconds','status'}.issubset(schema.names):continue
                    if pp.stat().st_size!=family['bytes'] or OLD.file_sha(pp)!=family['sha256']:raise ValueError('Immutable family reference changed')
                    wanted=['record_id','molecule_id','calc_type','elapsed_seconds','status','values']
                    for r in pq.read_table(pp,columns=wanted,use_threads=False).to_pylist():
                        details[(r['record_id'],r['calc_type'])]={**r,'file_group':family['file_group']}
                detail_cache[path]=details
            keys=[dict(r) for r in reader.db.execute('SELECT record_id,calc_type FROM records WHERE molecule_id=?',(item['molecule_id'],))]
            if len(keys)!=12*item['records']:raise ValueError('Closed whole-molecule raw slot count differs')
            all_writer.begin_molecule(item['molecule_id']);policy_writer.begin_molecule(item['molecule_id']);mol_trace=[]
            for key in keys:
                rid,calc=key['record_id'],key['calc_type'];raw=reader.get(rid,calc);source=raw['metadata'];outputs=raw['output_files']
                if outputs is None:raise ValueError('Full G6 output witness unavailable')
                top=details[(rid,calc)]
                if raw['scope_status']!=top['status']:raise ValueError('Raw vs actual permanent parsed status differs')
                status=normal_status(raw['scope_status']);scf=SCF.extract_scf(calc,outputs,status=status,source_status=raw['source_status'])
                inputs=raw['input_files']
                hashes=[{'name':f['name'],'sha256':f['sha256']} for f in sorted(inputs,key=lambda x:x['name'])]
                bundle_sha=OLD.digest(OLD.bundle(inputs)[0]) if inputs else None
                sid=1 if calc.startswith('pm7_') else 2
                trace={'record_id':rid,'molecule_id':item['molecule_id'],'calc_type':calc,
                       'size_stratum':item['size_stratum'],'file_group':top['file_group'],
                       'status':status,'software_version_id':sid,'elapsed_seconds':top['elapsed_seconds'],
                       'scf_iterations':scf['scf_iterations'],'converged':scf['converged'],
                       'input_file_sha256':hashes,'input_bundle_sha256':bundle_sha}
                if not hashes:trace['input_bundle_sha256']=None
                execution='G3_TEST:'+item['node']+':'+OLD.digest(path.encode())[:12]
                meta={k:v for k,v in source.items() if k not in {'input_file_manifest','output_file_manifest','is_minimum','input_origin','input_missing_reason'}}
                record={**meta,**trace,'source_status':raw['source_status'],'scope_status':status,'execution_id':execution,
                        'scf_metadata':scf,'audit_selected':True,
                        'files':[{**f,'role':'output'} for f in outputs]}
                measured=all_writer.put_record(record)
                selected=rid in audit_ids;record['audit_selected']=selected
                retained=policy_writer.put_record(record)
                expected=status in FAIL or selected
                if retained['output_retained']!=expected:raise ValueError('User retention differs')
                if not expected and retained.get('container_path') is not None:raise ValueError('Ordinary success has container locator')
                original=reader.db.execute('SELECT length(raw_frame) FROM records WHERE record_id=? AND calc_type=?',(rid,calc)).fetchone()[0]
                if measured['raw_frame_bytes']!=original:raise ValueError('Full scientific output bundle compression differs')
                extra=[f for f in outputs if f['name'] not in {'input.out','process.out','input.aux'}]
                aux=[f for f in outputs if f['name']=='input.aux'];d=all_writer.dicts[calc]['data']
                extra_bytes=len(all_writer.zstd.compress(OLD.bundle(extra)[0],d)) if extra else 0
                aux_bytes=sum(f['byte_count'] for f in aux)
                aux_frame=len(all_writer.zstd.compress(OLD.bundle(aux)[0],d)) if aux else 0
                detail=restore_detail(top,registry_entries,PARQ);detail['status']=status;detail['source_status']=raw['source_status']
                detail['provenance']=trace;detail['raw_audit_selected']=selected
                detail['reproduction_package_sha256']=None # Actual package not yet created at original G6; reserve immutable 64-hex width below
                detail['precision_by_field']=precision_from_actual_output(calc,outputs,inputs,PARSER)
                detail['registry_source_evidence']=ENGINE.concise_source_evidence(detail,files=outputs)
                detail['raw_ref']=retained
                encoded=PARQ.task_row(rid,item['molecule_id'],calc,detail,[],item['atoms'])
                for field in TRACE:
                    if field in encoded:trace[field]=encoded[field]
                # Package SHA is a width/entropy reservation, not a false original
                # source fact. Hash actual immutable protocol to measure the same
                # 64-hex column type; actual production package replaces it.
                trace['reproduction_package_sha256']=OLD.file_sha(protocol)
                trace_rows.append(trace);mol_trace.append(trace)
                cases.append({'record_id':rid,'molecule_id':item['molecule_id'],'calc_type':calc,'node':item['node'],
                    'file_group':top['file_group'],'size_stratum':item['size_stratum'],'atoms':item['atoms'],
                    'source_status':raw['source_status'],'scope_status':status,'audit_selected':selected,
                    'actual_policy_retained':expected,'execution_id':execution,'raw_frame_bytes':measured['raw_frame_bytes'],
                    'metadata_frame_bytes':measured['metadata_frame_bytes'],'logical_raw_bytes':measured['logical_raw_bytes'],
                    'extra_frame_bytes':extra_bytes,'extra_atoms2_ratio':extra_bytes/(item['atoms']**2),
                    'AUX_raw_bytes':aux_bytes,'AUX_compressed_bytes':aux_frame,
                    'input_sha_state':'ORIGINAL_STORED_INPUT_MEMBER_SHA' if hashes else 'UNKNOWN_NO_ORIGINAL_MEMBER',
                    'scf_iterations':scf['scf_iterations'],'converged':scf['converged']})
            all_writer.commit_molecule();policy_writer.commit_molecule()
            wire=pickle.dumps(mol_trace,protocol=5);d=all_writer.dicts['pm7_B']
            frame=all_writer.zstd.compress(wire,d['data'])
            stage_extra.append({'molecule_id':item['molecule_id'],'node':item['node'],'records':item['records'],
                 'size_stratum':item['size_stratum'],'trace_pickle_compressed_bytes':len(frame),'trace_pickle_uncompressed_bytes':len(wire)})
    except Exception as e:errors.append({'type':type(e).__name__,'error':str(e)});raise
    finally:
        all_writer.close();policy_writer.close()
        for r in readers.values():r.close()
    paths=[]
    for key,name,kept in (('measurement','retained_case_measurement_TEST.sqlite',len(cases)),('policy','user_policy_TEST.sqlite',sum(c['actual_policy_retained'] for c in cases))):
        path=root/name;rd=NEW.ArchiveReader(path,manifest)
        try:
            actual=rd.db.execute('SELECT count(*) FROM records').fetchone()[0]
            if actual!=kept:raise ValueError('Ordinary success stub inserted or retained count differs')
            frame_bytes=rd.db.execute('SELECT coalesce(sum(length(raw_frame)+length(metadata_frame)),0) FROM records').fetchone()[0]
            for c in cases:
                should=key=='measurement' or c['actual_policy_retained']
                if should:
                    got=rd.get(c['record_id'],c['calc_type'],c['execution_id'])
                    if got['input_files'] or got['input_bodies_saved']:raise ValueError('Forbidden input body persisted')
                    if got['raw_sha256']!=OLD.digest(OLD.bundle(got['output_files'])[0]):raise ValueError('Output readback SHA differs')
                else:
                    exists=rd.db.execute('SELECT count(*) FROM records WHERE record_id=? AND calc_type=?',(c['record_id'],c['calc_type'])).fetchone()[0]
                    if exists:raise ValueError('Ordinary success shared container row')
            paths.append({**ref(path),'measurement_kind':key,'retained_calls':actual,'frame_bytes':frame_bytes,
               'physical_nonframe_bytes':path.stat().st_size-frame_bytes,
               'physical_nonframe_bytes_per_retained_call':(path.stat().st_size-frame_bytes)/actual if actual else None,
               'full_raw_member_SHA_readback':True,'input_body_count':0})
        finally:rd.close()
    trace_refs=[]
    for s in sorted({r['size_stratum'] for r in trace_rows}):
        rows=[r for r in trace_rows if r['size_stratum']==s];path=root/('trace_'+s+'.parquet')
        table=pa.Table.from_pylist(rows,schema=trace_schema)
        pq.write_table(table,path,compression='zstd',compression_level=3,store_schema=True)
        back=pq.read_table(path,use_threads=False)
        if not table.equals(back):raise ValueError('Trace typed Parquet readback differs')
        trace_refs.append({**ref(path),'size_stratum':s,'rows':len(rows),'float64_metadata_exact_readback':True})
    return {'worker_pid':os.getpid(),'cases':cases,'stage_extra':stage_extra,'archives':paths,'trace_files':trace_refs,'errors':errors}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--check',action='store_true')
    ap.add_argument('--reports',nargs='+');ap.add_argument('--audit-manifest');ap.add_argument('--protocol',default=str(ROOT/'configs/protocol.json'))
    ap.add_argument('--dictionaries',default=str(ROOT/'dictionaries/job_4513894/dictionary_manifest.json'))
    ap.add_argument('--workers',type=int,default=16);ap.add_argument('--output');a=ap.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());assert normal_status('RESOURCE_LIMIT_FAILED')=='CALCULATION_FAILED'
        print('NEW_POLICY_BENCHMARK_AST_CHECK_PASS_NO_QM');return
    if a.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers or socket.gethostname().split('.')[0] not in NODES:raise ValueError('Authorized node >=16 actual allocated workers required')
    if not a.reports or not a.output or not a.audit_manifest:ap.error('--reports --audit-manifest --output required')
    import pyarrow.parquet as pq,pyarrow as pa
    output=Path(a.output).absolute()
    if not output.is_relative_to(ROOT):raise ValueError('Only current WP5 prototype output')
    output.mkdir(parents=True,exist_ok=False)
    audit=read(a.audit_manifest)
    if audit['status']!='AUDIT_MEMBERSHIP_CLOSED':raise ValueError('Actual formal audit membership must close')
    selected=audit['selected_records'];path=Path(selected['path'])
    if path.stat().st_size!=selected['bytes'] or OLD.file_sha(path)!=selected['sha256']:raise ValueError('Actual audit membership reference differs')
    audit_ids=set(pq.read_table(path,columns=['record_id'],use_threads=False)['record_id'].to_pylist())
    if len(audit_ids)!=selected['rows']:raise ValueError('MANIFEST_AUDIT_RECORD_IDS_NOT_UNIQUE')
    molecules=[];sources=[];source_metadata=[];seen_archives=set()
    for rp in a.reports:
        report=read(rp)
        if report['status'] not in {'G6_FULL_CHAIN_PASSED','G6_FULL_CHAIN_PASSED_WITH_RECORDED_SCIENTIFIC_OUTCOMES'} or report.get('issues'):raise ValueError('Only actual closed full-output G6 witness')
        root=Path(report.get('source_run') or Path(rp).parent);selection=read(root/'selected_molecules.json')
        rows=selection if isinstance(selection,list) else selection.get('selected_molecules',selection.get('molecules',selection.get('rows',[])))
        atom={r['molecule_id']:int(r.get('max_total_atoms',r.get('total_atoms'))) for r in rows}
        measured=pq.read_table(Path(rp).parent/'raw_compression_by_record.parquet',columns=['molecule_id','size_stratum'],use_threads=False).to_pylist()
        strata={r['molecule_id']:r['size_stratum'] for r in measured}
        queue_path=Path(report.get('queue') or root/'queue.sqlite');db=ro(queue_path)
        try:
            actual=[dict(r) for r in db.execute('SELECT molecule_id,state,record_count,archive_path FROM molecules')]
            if len(actual)!=20 or any(r['state']!='COMPLETE' for r in actual):raise ValueError('Source20 whole molecules not closed')
            source_metadata.append({'kind':'permanent_queue_metadata','path':str(queue_path),'molecules':20,
                'physical_bytes':queue_path.stat().st_size,'bytes_per_molecule_upper_witness':queue_path.stat().st_size/20,
                'contains_no_scientific_wire_body':True,'source_layout':'Actual old completed queue; conservative current checkpoint metadata witness'})
            for r in actual:molecules.append({'molecule_id':r['molecule_id'],'archive_path':r['archive_path'],'records':r['record_count'],
                 'node':report['node'],'size_stratum':strata[r['molecule_id']],'atoms':atom[r['molecule_id']]})
        finally:db.close()
        for r in actual:
            archive_path=r['archive_path']
            if archive_path in seen_archives:continue
            seen_archives.add(archive_path);sql=ro(archive_path)
            try:
                count=sql.execute('SELECT count(*) FROM completion_receipts').fetchone()[0]
                if count<=0:raise ValueError('Source SCI completion metadata count unavailable')
                measured_pages={row['name']:row['bytes'] for row in sql.execute("SELECT name,sum(pgsize) AS bytes FROM dbstat WHERE name IN ('completion_receipts','molecules','parquet_exports') GROUP BY name")}
                if not {'completion_receipts','molecules','parquet_exports'}.issubset(measured_pages):raise ValueError('Source SQLite exact metadata page attribution unavailable')
                amount=sum(measured_pages.values())
                source_metadata.append({'kind':'permanent_archive_SCI_completion_metadata','path':archive_path,'molecules':count,
                    'physical_bytes':amount,'bytes_per_molecule_upper_witness':amount/count,'table_page_bytes':measured_pages,
                    'raw_record_frames_and_row_pages_excluded':True,'source_layout':'Actual old SCI receipts/exports; conservatively separately molecule-weighted; not per-call raw stub'})
            finally:sql.close()
        sources.append({**ref(rp),'node':report['node']})
    batches=[molecules[i::a.workers] for i in range(a.workers)]
    if any(not x for x in batches):raise ValueError('Insufficient actual molecules for effective workers')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers);start=time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(barrier,)) as pool:
        results=list(pool.map(worker,[(i,b,a.dictionaries,audit_ids,str(output),a.protocol,a.audit_manifest) for i,b in enumerate(batches)],chunksize=1))
    cases=[r for w in results for r in w['cases']];pids={w['worker_pid'] for w in results}
    if len(pids)!=a.workers or len(cases)!=12*sum(m['records'] for m in molecules):raise ValueError('MANIFEST_NEW_POLICY_BENCHMARK_WORKER_OR_RAW_ROW_CLOSURE')
    pq.write_table(pa.Table.from_pylist(cases),output/'cases.parquet',compression='zstd')
    report={'schema':'WP5_NEW_RAW_POLICY_PHYSICAL_BENCHMARK_V1','status':'NEW_POLICY_PHYSICAL_BENCHMARK_CLOSED',
       'policy':NEW.POLICY,'QM_started':False,'LMDB_created':False,'ordinary_success_container_rows':0,'inputs_saved':0,
       'scope':'Output-only prototype physical measurement from actual immutable pre-override G6 full outputs; never claims those runs used new policy or passed new G6/50-double test',
       'source_reports':sources,'dictionary':ref(a.dictionaries),'audit_manifest':ref(a.audit_manifest),
       'source_modules':[ref(ROOT/'scripts'/name) for name in ('wp5_archive_v4.py','wp5_archive_v5.py','wp5_parquet_v2.py','wp5_engine_v2.py','wp5_parser.py','wp5_registry_coverage.py','wp5_scf_metadata_v2.py')],
       'actual_worker_count':len(pids),'worker_pids':sorted(pids),'node_observations':len(molecules),
       'distinct_molecules':len({m['molecule_id'] for m in molecules}),'case_observations':len(cases),
       'cases':ref(output/'cases.parquet'),'workers':results,'source_all_molecule_metadata_page_witnesses':source_metadata,'seconds':time.time()-start,
       'software_version_ids':{'1':'Actual frozen MOPAC family version','2':'Actual frozen xTB family version'},
       'trace_increment_model':'All production2 added trace/precision/registry-source/locator columns measured. Separate trace table repeats identities conservatively; permanent science values unchanged. Package SHA column uses actual protocol-SHA entropy/width reservation, clearly not original package provenance.',
       'stage_increment_model':'Actual trace-only pickle5/zstd addition; stage science baseline measured from existing G6 durable receipts; no legacy wire reconstruction',
       'source_sha256':OLD.file_sha(__file__)}
    save(output/'report.json',report);print(json.dumps({'status':report['status'],'cases':len(cases),'workers':len(pids),'report':str(output/'report.json')}))
if __name__=='__main__':main()
