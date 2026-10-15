#!/usr/bin/env python3
"""Read-only old-pilot PM7-B parser delta2: drain zstd stdout before close/wait; no nonzero waiver.
Existing all-task G5 remains authoritative for unchanged field/source evidence.
This checks parser2 versus frozen parser1 with identical verified native context.
"""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,hashlib,json,multiprocessing,os,shutil,stat,struct,subprocess,tarfile,tempfile,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
GEOMETRY=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/c_engineering/xyz/analysis_geometry.parquet')
SHAS={'wp5_parser.py':'aafa3c2808ccfa3a6bcea49f9807563351f0252e5e9f7cd57d86e40ddc291aa3',
 'wp5_parser_v2.py':'33d5cb65429f6f969d8739c2f244cf8249f35d23792dca4e73cd52ffe4eaaf6f',
 'wp5_engine_v3.py':'53c09b68938ead8449f0da2ec7a03337df3125826080ece58fabe107cdd9f26b'}
PANEL_SHA='034fec487d36b2821be135ef72ed76a2bc5f96ed93f2f9669cbfb5fa73e66ee9'
_C={}
HB='hydrogen_bond_energy_kcal_mol'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def bits(a,b):
    if type(a)!=type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(bits(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(bits(x,y) for x,y in zip(a,b))
    if type(a) is float:return struct.pack('>d',a)==struct.pack('>d',b)
    return a==b
def numeric(v):
    import math
    if type(v) is float:return int(math.isfinite(v))
    if type(v) is int:return 1
    if isinstance(v,(list,dict)):return sum(numeric(x) for x in (v.values() if isinstance(v,dict) else v))
    return 0
def save(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def init(options,barrier):
    global _C
    _C=options
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);barrier.wait(timeout=180)
def verified_context(rid):
    import numpy as np
    from rdkit import Chem
    row=_C['rows'][rid];g=_C['geometry'][rid]
    z=np.asarray(g['atomic_numbers'],dtype='<i8');xyz=np.asarray(g['positions_A'],dtype='<f8')
    if xyz.shape!=(len(z),3) or not np.isfinite(xyz).all():raise ValueError('C5_NATIVE_COORDINATES_INVALID')
    if sha_bytes(z.tobytes())!=g['native_atom_order_sha256'] or sha_bytes(xyz.tobytes())!=g['native_coordinates_sha256']:raise ValueError('C5_NATIVE_ORDER_OR_COORDINATE_SHA_DIFFERS')
    symbols=[Chem.GetPeriodicTable().GetElementSymbol(int(x)) for x in z]
    if symbols!=g['elements']:raise ValueError('C5_ELEMENT_SYMBOL_ORDER_DIFFERS')
    # Exact frozen read_native lines127-134: lower pairs <= actual cutoff, then
    # AddHs(source SMILES) bonds only if original native atom sequence matches.
    pairs=list(zip(*np.tril_indices(len(z),-1)))
    keep=[(int(i),int(j)) for i,j in pairs if np.linalg.norm(xyz[i]-xyz[j])<=_C['pair_cutoff_A']]
    mol=Chem.MolFromSmiles(row['smiles']) if row.get('smiles') else None
    source_h=Chem.AddHs(mol) if mol is not None else None
    if source_h is not None and source_h.GetNumAtoms()==len(z) and all(source_h.GetAtomWithIdx(i).GetAtomicNum()==int(z[i]) for i in range(len(z))):
        keep.extend((max(b.GetBeginAtomIdx(),b.GetEndAtomIdx()),min(b.GetBeginAtomIdx(),b.GetEndAtomIdx())) for b in source_h.GetBonds())
    return symbols,sorted(set(keep))
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def review_one(receipt_path):
    if time.time()>=_C['deadline']:raise TimeoutError('PILOT_DELTA_INTERNAL46H_BOUND')
    import pyarrow.parquet as pq,wp5_parser as before,wp5_parser_v2 as after
    receipt=json.loads(Path(receipt_path).read_text());ref=receipt['parquet']
    if Path(ref['path']).stat().st_size!=ref['bytes'] or sha(ref['path'])!=ref['sha256']:raise ValueError('OLD_PILOT_PARQUET_CHANGED')
    details=[json.loads(r['details_json']) for r in pq.read_table(ref['path'],columns=['details_json'],use_threads=False).to_pylist()]
    b=[d for d in details if d['task']=='pm7_B']
    if len(b)!=receipt['records'] or len({d['record_id'] for d in b})!=len(b):raise ValueError('OLD_PILOT_B_SLOTS_NOT_CLOSED')
    reference=receipt.get('archive');targets={};result=[];sources={};issues=[]
    for d in b:
        rid=d['record_id'];binding=d.get('archive');files=[f for f in d.get('archived_files',[]) if f['name']=='input.out']
        if len(files)>1:raise ValueError('DUPLICATE_B_OUT_REFERENCE')
        if not binding or not files:
            result.append({'record_id':rid,'molecule_id':d['molecule_id'],'source_status':d['status'],'availability':'SOURCE_NOT_ARCHIVED',
              'old_HB':d.get('values',{}).get(HB),'new_HB':None,'fallback_applied':False,'native_token':None,'rounding_decimal_places':None,
              'input_out_sha256':None,'old_parser_error':None,'new_parser_error':None,'non_HB_fields_compared':0,'non_HB_numeric_values':0,'non_HB_differences_json':'[]','proof_json':None})
            continue
        if not reference or binding['path']!=reference['path'] or binding['sha256']!=reference['sha256']:raise ValueError('OLD_CALL_ARCHIVE_BINDING_DIFFERS')
        name=binding['member_prefix']+'/input.out'
        if name in targets:raise ValueError('DUPLICATE_B_MEMBER_REFERENCE')
        targets[name]=(d,files[0])
    if targets:
        path=Path(reference['path'])
        if path.stat().st_size!=reference['bytes'] or sha(path)!=reference['sha256']:raise ValueError('OLD_PILOT_ARCHIVE_CHANGED')
        process=subprocess.Popen([_C['zstd_executable'],'-d','-c',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdout,mode='r|') as tar:
                for member in tar:
                    if member.name not in targets:continue
                    if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:raise ValueError('INVALID_B_ARCHIVE_MEMBER')
                    if member.name in sources:raise ValueError('DUPLICATE_B_ARCHIVE_MEMBER')
                    detail,binding=targets[member.name];data=tar.extractfile(member).read()
                    if len(data)!=binding['bytes'] or sha_bytes(data)!=binding['sha256']:raise ValueError('B_OUT_BYTES_OR_SHA_CHANGED')
                    sources[member.name]=data
            # tarfile stops at tar EOF before zstd necessarily emits final padding.
            # Drain producer stdout fully; never close a live valid pipe early.
            drained=0
            while True:
                padding=process.stdout.read(1<<20)
                if not padding:break
                drained+=len(padding)
            process.stdout.close();stderr=process.stderr.read().decode(errors='replace');returncode=process.wait()
            if returncode!=0:
                evidence={'receipt_path':str(receipt_path),'archive_path':str(path),'expected_archive_sha256':reference['sha256'],
                  'argv':[str(_C['zstd_executable']),'-d','-c',str(path)],'returncode':returncode,'stderr':stderr,
                  'stdout_bytes_drained_after_tar_eof':drained,'worker_pid':os.getpid(),'QM_started':False}
                failure_path=Path(_C['decode_failure_dir'])/(str(os.getpid())+'_'+sha_bytes(str(receipt_path).encode())[:20]+'.json')
                save(failure_path,evidence)
                raise ValueError('OLD_ARCHIVE_ZSTD_FAILED:'+json.dumps(evidence,sort_keys=True))
        finally:
            if process.poll() is None:process.kill();process.wait()
            if process.stdout:process.stdout.close()
            if process.stderr:process.stderr.close()
    folder=Path(tempfile.mkdtemp(prefix=f'wp5HB_{os.getuid()}_{os.environ["SLURM_JOB_ID"]}_{os.getpid()}_',dir='/tmp'))
    try:
        for name,(d,binding) in targets.items():
            rid=d['record_id'];base={'record_id':rid,'molecule_id':d['molecule_id'],'source_status':d['status'],
              'old_HB':None,'new_HB':None,'fallback_applied':False,'native_token':None,'rounding_decimal_places':None,
              'input_out_sha256':None,'old_parser_error':None,'new_parser_error':None,'non_HB_fields_compared':0,'non_HB_numeric_values':0,'non_HB_differences_json':'[]','proof_json':None}
            if name not in sources:
                base['availability']='BOUND_MEMBER_NOT_PRESENT';result.append(base);issues.append(rid+':BOUND_MEMBER_NOT_PRESENT');continue
            data=sources[name];target=folder/sha_bytes(rid.encode())[:24];target.mkdir();(target/'input.out').write_bytes(data)
            symbols,pairs=verified_context(rid);old=new=None
            try:old=before.parse_mopac(target,symbols,pair_indices=pairs,reconstruct_mulliken=False)
            except Exception as exc:base['old_parser_error']=type(exc).__name__+':'+str(exc)
            try:new=after.parse_mopac(target,symbols,pair_indices=pairs,reconstruct_mulliken=False)
            except Exception as exc:base['new_parser_error']=type(exc).__name__+':'+str(exc)
            base['availability']='INPUT_OUT_READ_AND_SHA_VERIFIED';base['input_out_sha256']=binding['sha256']
            if old is None or new is None:
                base['availability']='NATIVE_PARSE_FAILED_NOT_NUMERIC_EVIDENCE'
                if base['old_parser_error']!=base['new_parser_error']:issues.append(rid+':PARSER_ERROR_DELTA')
                result.append(base);continue
            differences=[k for k in set(old)|set(new) if k!=HB and (k not in old or k not in new or not bits(old[k],new[k]))]
            base['non_HB_fields_compared']=len(set(old)|set(new))-1
            base['non_HB_numeric_values']=sum(numeric(v) for k,v in old.items() if k!=HB)
            base['non_HB_differences_json']=json.dumps(differences,sort_keys=True);base['old_HB']=old.get(HB);base['new_HB']=new.get(HB)
            proof=after.context()['hydrogen_bond_energy_source'];base['proof_json']=json.dumps(proof,sort_keys=True)
            base['fallback_applied']=proof['fallback_applied'];base['native_token']=proof['source_token'];base['rounding_decimal_places']=proof['rounding_decimal_places']
            if differences:issues.append(rid+':NON_HB_BITS_CHANGED')
            if old.get(HB) is not None and not bits(old[HB],new.get(HB)):issues.append(rid+':EXISTING_HB_CHANGED')
            result.append(base)
    finally:
        if folder.parent!=Path('/tmp') or not folder.name.startswith(f'wp5HB_{os.getuid()}_{os.environ["SLURM_JOB_ID"]}_{os.getpid()}_'):raise ValueError('LOCAL_DELTA_CLEANUP_SCOPE')
        for p in [folder,*folder.rglob('*')]:
            info=p.lstat()
            if info.st_uid!=os.getuid() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):raise ValueError('LOCAL_DELTA_CLEANUP_OWNER_OR_TYPE')
        shutil.rmtree(folder)
    return {'rows':result,'issues':issues,'pid':os.getpid(),'receipt':{'path':str(receipt_path),'sha256':sha(receipt_path)},'local_scratch_cleaned':not folder.exists()}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workers',type=int,default=24);p.add_argument('--geometry',type=Path,default=GEOMETRY)
    p.add_argument('--pilot-root',type=Path,default=OLD/'wp4_native_full_v4');p.add_argument('--panel',type=Path,default=OLD/'wp4_native_panel/pilot_panel.parquet')
    p.add_argument('--protocol',type=Path,default=ROOT/'configs/protocol.json');p.add_argument('--out',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    refs=[]
    for name,expected in SHAS.items():
        path=Path(__file__).with_name(name)
        if sha(path)!=expected:raise ValueError('PARSER_DELTA_SOURCE_CHANGED:'+name)
        refs.append({'path':str(path),'sha256':expected})
    if a.check:ast.parse(Path(__file__).read_text());assert bits([-0.0,None],[-0.0,None]);assert not bits(-0.0,0.0);print('PILOT_B_DELTA_SCOPE_AST_PASS_NO_QM');return
    if not os.environ.get('SLURM_JOB_ID') or not 24<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK','0')):raise ValueError('PILOT_DELTA_ACTUAL24CPU_REQUIRED')
    if sha(a.panel)!=PANEL_SHA:raise ValueError('ORIGINAL10020_PANEL_CHANGED')
    import pyarrow as pa,pyarrow.parquet as pq
    config=json.loads(a.protocol.read_text());native=config['frozen_dependencies']['native_lifecycle']
    if sha(native['path'])!=native['sha256']:raise ValueError('PINNED_NATIVE_CONTEXT_SOURCE_CHANGED')
    rows=pq.read_table(a.panel).to_pylist();geometry=pq.read_table(a.geometry,columns=['record_id','atomic_numbers','elements','positions_A','native_atom_order_sha256','native_coordinates_sha256']).to_pylist()
    if len(rows)!=10020 or len(geometry)!=10020 or {r['record_id'] for r in rows}!={g['record_id'] for g in geometry}:raise ValueError('PILOT_GEOMETRY10020_IDENTITY_NOT_CLOSED')
    receipts=sorted(a.pilot_root.glob('bucket_*/molecules/*/receipt.json'))
    if len(receipts)!=1441:raise ValueError('OLD1441_MOLECULE_FRAME_CHANGED')
    options={'rows':{r['record_id']:r for r in rows},'geometry':{g['record_id']:g for g in geometry},
      'pair_cutoff_A':config['pair_cutoff_A'],'zstd_executable':config['zstd_executable'],'deadline':time.time()+46*3600}
    out=a.out or ROOT/'gates/G5_hydrogen_delta'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    (out/'decode_failures').mkdir();options['decode_failure_dir']=str(out/'decode_failures')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers);allrows=[];issues=[];pids=set();bindings=[];clean=True
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(options,barrier)) as pool:
        for result in pool.map(review_one,receipts,chunksize=1):
            allrows.extend(result['rows']);issues.extend(result['issues']);pids.add(result['pid']);bindings.append(result['receipt']);clean=clean and result['local_scratch_cleaned']
    ids=[r['record_id'] for r in allrows]
    if len(ids)!=10020 or len(set(ids))!=10020 or set(ids)!=set(options['rows']):raise ValueError('PILOT_B_DELTA10020_RECORDS_NOT_CLOSED')
    schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('source_status',pa.string()),('availability',pa.string()),
      ('old_HB',pa.float64()),('new_HB',pa.float64()),('fallback_applied',pa.bool_()),('native_token',pa.string()),('rounding_decimal_places',pa.int32()),
      ('input_out_sha256',pa.string()),('old_parser_error',pa.string()),('new_parser_error',pa.string()),('non_HB_fields_compared',pa.int32()),
      ('non_HB_numeric_values',pa.int64()),('non_HB_differences_json',pa.string()),('proof_json',pa.large_string())])
    path=out/'pilot_B_hydrogen_delta.parquet';pq.write_table(pa.Table.from_pylist(allrows,schema=schema),path,compression='zstd')
    counts=collections.Counter(r['availability'] for r in allrows)
    passed=not issues and clean and len(pids)>=16
    report={'schema':'WP5_G5_PM7_B_HYDROGEN_DELTA_V1','status':'PASS_DELTA_WITH_DISCLOSED_HISTORICAL_GAPS' if passed else 'NOT_PASS',
      'QM_started':False,'LMDB_opened':False,'records':10020,'molecules':1441,'requested_B_output_sources':10020,'source_availability':dict(counts),
      'new_native_HB_values':sum(r['fallback_applied'] for r in allrows),'unchanged_non_HB_parser_fields':sum(r['non_HB_fields_compared'] for r in allrows),
      'unchanged_non_HB_numeric_values':sum(r['non_HB_numeric_values'] for r in allrows),'issues':issues,'effective_worker_pids':sorted(pids),'scratch_cleaned':clean,
      'missingness_policy':'SOURCE_NOT_ARCHIVED or BOTH_PARSE_FAILED are not numeric regression PASS. Approved old raw exception remains explicit. Missing AUX-sensitive fields have no new numeric evidence.',
      'source_scope':'Only actual retained PM7-B input.out. Old and new production parsers use identical C5 source atom order/native coordinates and pinned lower-pair<=cutoff plus matching source-SMILES-H bonds context. No other11 task parsing or getter/QM recomputation.',
      'authorized_delta':'HB old NULL may become the actual first contribution of the printed kcal/mol summary, with native precision. Every nonHB parsed field and prior nonNULL HB must preserve exact type/shape/Float64 bits.',
      'processing_sources':refs,'native_context_source':native,'geometry':{'path':str(a.geometry),'sha256':sha(a.geometry)},'panel':{'path':str(a.panel),'sha256':sha(a.panel)},
      'prior_full_G5':{'path':str(ROOT/'gates/G5_parser_regression/job_4513891/report.json'),'sha256':sha(ROOT/'gates/G5_parser_regression/job_4513891/report.json')},
      'pilot_receipts':bindings,'result':{'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size},'script_sha256':sha(__file__)}
    save(out/'report.json',report);print(json.dumps({'status':report['status'],'report':str(out/'report.json'),'new_native_HB_values':report['new_native_HB_values']}))
    if not passed:raise SystemExit(2)
if __name__=='__main__':main()
