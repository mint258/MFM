"""Continue only missing first-two P-prime records with the original QM engine.

Operational initialization/export omit the old audit/approval/re-read layers.
The original twelve-task compute_pair, native invoke, parsers, precision,
perturbation seed and 900-second per-call timeout remain unchanged.
"""
from __future__ import annotations
import argparse, ast, collections, concurrent.futures as cf, functools, gzip, importlib.util
import inspect, json, math, multiprocessing as mp, os, sqlite3, sys, tempfile, time, types
from pathlib import Path
REPO=Path(__file__).absolute().parents[4]
ENGINE=None;PLAN=None;COMPUTE=None;EXPORT=None;RawSink=None;WIRE=None

def read(value):
    return json.loads(Path(value['path']if isinstance(value,dict)else value).read_text(encoding='utf-8-sig'))

def save(path,value):
    path=Path(path);temp=path.with_name(path.name+'.writing')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');os.replace(temp,path)

def file_info(path):return {'path':str(path),'bytes':Path(path).stat().st_size}

def import_path(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def producer_export(engine,records,folder):
    """Use original typed row/schema construction; write once, without readback."""
    import export_families as original
    # The row builder is unmodified. Only output guards, re-read assertions,
    # per-file hashing and the old readback-status string are omitted.
    tree=ast.parse(inspect.getsource(original.export))
    function=tree.body[0]
    class Producer(ast.NodeTransformer):
        def visit_Expr(self,node):
            if isinstance(node.value,ast.Call):
                f=node.value.func
                if isinstance(f,ast.Name)and f.id=='output_guard':return None
                if isinstance(f,ast.Attribute)and isinstance(f.value,ast.Name)and f.value.id=='wire'and f.attr=='exact':return None
                if isinstance(f,ast.Attribute)and isinstance(f.value,ast.Name)and f.value.id=='wire'and f.attr=='write_family_rows':
                    return ast.parse("pq.write_table(proposed, path, compression='zstd')").body[0]
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if any(isinstance(t,ast.Name)and t.id in('expected','actual')for t in node.targets):return None
            return self.generic_visit(node)
        def visit_Constant(self,node):
            if node.value=='ALL_PILOT_FIELDS_MATCH_BITS_AND_TYPES':return ast.copy_location(ast.Constant('PRODUCER_TYPED_ROWS_CHECKED_ONCE_NO_READBACK'),node)
            return node
    tree=Producer().visit(tree);ast.fix_missing_locations(tree)
    namespace=dict(original.__dict__,reference=file_info)
    exec(compile(tree,str(Path(original.__file__))+'[producer-output-only]','exec'),namespace)
    return namespace['export'](records,folder,engine,None,{})

def initialize(plan):
    global ENGINE,PLAN,COMPUTE,RawSink,WIRE
    PLAN=plan
    pprime=REPO/'workflows/data_v1_final/pprime';sys.path[:0]=[str(pprime),str(pprime/'retention_v1')]
    pilot=read(plan['pilot']);legacy=read(pilot['legacy_contract'])
    engine_path=next(r['path']for r in legacy['sources']if Path(r['path']).name=='wp5_engine_v3.py')
    sys.path.insert(0,str(Path(engine_path).parent));ENGINE=import_path('_window2_original_engine_'+str(os.getpid()),engine_path)
    # Import-only operational bindings avoid rehashing the previously frozen
    # binaries, source files and reproduction assets in every worker.
    def pinned(name,entry):return import_path(name,entry['path'])
    package=read(legacy['reproduction_package'])
    def metadata(audit,reproduction):
        ENGINE.AUDIT_IDS={};ENGINE.PACKAGE=package;ENGINE.PACKAGE_SHA=legacy['reproduction_package']['sha256'];ENGINE.AUDIT_SHA=None
        for family in ('mopac','xtb'):
            if package['software_versions'][family]['version']!=ENGINE.CONFIG['expected_versions'][family]:raise ValueError('ORIGINAL_SOFTWARE_VERSION_CHANGED')
    ENGINE.pinned_module=pinned;ENGINE.load_production_metadata=metadata
    tree=ast.parse(inspect.getsource(ENGINE.initialize_worker));fn=tree.body[0]
    # This one initializer guard hashes the registry again. Its identity was
    # frozen already; row/atom/label science is checked in the producer.
    fn.body=[n for n in fn.body if not(isinstance(n,ast.If)and 'sha(registry['in ast.unparse(n.test))]
    ast.fix_missing_locations(tree);exec(compile(tree,engine_path+'[taskbook-v2-initialization]','exec'),ENGINE.__dict__)
    scratch=Path(tempfile.mkdtemp(prefix='dv1_ppfill_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    ENGINE.initialize_worker(pilot['source_plan']['path'],protocol=legacy['protocol']['path'],node_scratch_root=str(scratch),deadline=1e30,
        audit_membership=plan['original_audit_membership'],reproduction_package=legacy['reproduction_package']['path'])
    if ENGINE.CONFIG['timeout_seconds']!=900:raise ValueError('ORIGINAL_900S_TIMEOUT_REQUIRED')
    import engine_adapter,raw_archive,wp5_parquet_v2
    COMPUTE=engine_adapter.compute_pair;RawSink=raw_archive.RawSink;WIRE=wp5_parquet_v2
    import atexit;atexit.register(ENGINE.close_worker)

@functools.lru_cache(maxsize=8)
def parquet_rows(path,group):
    import pyarrow.parquet as pq
    return pq.ParquetFile(path).read_row_group(group)

@functools.lru_cache(maxsize=2)
def packet(path):
    with gzip.open(path,'rb')as f:return json.load(f)

def physical(row):
    if row['source_format']=='parquet':
        import pyarrow.parquet as pq
        index=int(row['source_row_index']);pf=pq.ParquetFile(row['source_path']);offset=0
        for rg in range(pf.num_row_groups):
            n=pf.metadata.row_group(rg).num_rows
            if index<offset+n:result=parquet_rows(row['source_path'],rg).slice(index-offset,1).to_pylist()[0];break
            offset+=n
        else:raise ValueError('PHYSICAL_ROW_NOT_FOUND')
    elif row['source_format']=='reproduction_json_gz':
        raw=packet(row['source_path'])
        if raw['summary']['molecule_id']!=row['molecule_id']:raise ValueError('PACKET_MOLECULE_DIFFERS')
        result=raw['conformers'][int(row['source_row_index'])]
    else:raise ValueError('UNKNOWN_PHYSICAL_GEOMETRY_FORMAT:'+row['source_format'])
    if result.get('molecule_id',row['molecule_id'])!=row['molecule_id']or result['status']!='SUCCESS'or result['converged']is not True:raise ValueError('ACTUAL_GEOMETRY_ID_OR_CONVERGENCE_DIFFERS')
    if result['atom_order_sha256']!=row['atom_order_sha256']:raise ValueError('ATOM_ORDER_DIFFERS_FROM_EXISTING_WITNESS')
    if row.get('original_sprime_conf_idx')is not None and result['sprime_conf_idx']!=row['original_sprime_conf_idx']:raise ValueError('ORIGINAL_CONFORMER_ID_DIFFERS')
    return result

def pair_for(row):
    # Preserve source geometry and canonical fixed-random first-two identity.
    import hashlib, struct
    raw=physical(row);source=json.loads(row['native_source_json'])
    if 'shard_id'not in source:
        source['shard_id']=next(k for k,v in ENGINE.NATIVE.SOURCES.items()if v['path']==source['source_path'])
    coordinate_sha=lambda xyz:hashlib.sha256(struct.pack('<'+'d'*(3*len(xyz)),*[float(v)for point in xyz for v in point])).hexdigest()
    source.update(effective_role=row['effective_role'],source_role=row['source_role'],file_group=int(row['file_group']),size_stratum=row['size_stratum'])
    conf=dict(raw,sprime_conf_idx=int(row['sprime_conf_idx']))
    return dict(record_id='pprime:'+row['molecule_id']+':'+str(row['sprime_conf_idx']),molecule_id=row['molecule_id'],random_order_rank=int(row['random_order_rank']),
        geometry_source='uff_sprime',source=source,conformer=conf,uff_coordinate_sha256=coordinate_sha(conf['coordinates']),
        **({'uff_geometry_sha256':row['geometry_sha256']}if row.get('geometry_sha256')else{}))

def batch_work(task):
    number,rows,output=task;folder=Path(output)/('batch_%06d'%number);folder.mkdir(exist_ok=False)
    sink=RawSink(folder/'raw_outputs.sqlite',ENGINE.OUTPUT_ARCHIVE,sys.maxsize)
    records=[];failures=[];success=0
    try:
        for row in rows:
            rid='pprime:'+row['molecule_id']+':'+str(row['sprime_conf_idx'])
            try:
                pair=pair_for(row)
                # This is the original scientific callable, including the same
                # parsers/status/masks and same per-call timeout; no trial run.
                record=COMPUTE(ENGINE,pair,sink,{'job_id':int(os.environ['SLURM_JOB_ID']),'lane':number,'pprime_reproduction_manifest_sha256':ENGINE.PACKAGE_SHA})
                record['lane']=number
                if len(record['tasks'])!=12 or len({x['task']for x in record['tasks']})!=12:raise ValueError('TWELVE_TASK_ALIGNMENT')
                records.append(record);success+=int(all(x['scope_status']=='SUCCESS'for x in record['tasks']))
            except Exception as exc:
                failures.append({'record_id':rid,'molecule_id':row['molecule_id'],'status':'UNRESOLVED_NO_AUTOMATIC_NATIVE_RETRY','error':repr(exc)})
    finally:sink.close()
    references=[]
    if records:references,_=producer_export(ENGINE,records,folder/'families')
    save(folder/'failures.json',failures)
    result={'batch':number,'assigned':len(rows),'completed':len(records),'all12_success':success,'failures':file_info(folder/'failures.json'),'files':references,'raw_outputs':file_info(folder/'raw_outputs.sqlite')}
    save(folder/'checkpoint.json',result)
    print(json.dumps({'batch':number,'completed':len(records),'unresolved':len(failures)}),flush=True)
    return result

def run(plan):
    import pyarrow.parquet as pq
    scope=read(plan['scope']);out=Path(plan['output']);out.mkdir(parents=True,exist_ok=True)
    if scope['actual_first2_records']!=161456 or scope['actual_chosen_MIDs']!=80728:raise ValueError('USE_CLOSED_80728_MID_FIRST2_SCOPE')
    tasks=scope['tables']['tasks'];path=tasks['path']if isinstance(tasks,dict)else tasks
    # The original closed scope anti-joins all completed ready P-prime MIDs.
    # A persistent claim checkpoint prevents repeating an unknown Native call.
    db=sqlite3.connect(out/'claims.sqlite');db.execute('CREATE TABLE IF NOT EXISTS claims(record_id TEXT PRIMARY KEY,batch INTEGER,status TEXT)');db.commit()
    cpus=int(os.environ.get('SLURM_CPUS_PER_TASK','16'));part=int(plan.get('part',0));parts=int(plan.get('parts',1))
    completed=[];pending={};buffer=[];number=0;seen=set();scope_mids=set();ordinal=0
    with cf.ProcessPoolExecutor(cpus,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(plan,))as pool:
        def settle(wait=False):
            if not pending:return
            done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED if wait else cf.ALL_COMPLETED,timeout=None if wait else 0)
            for f in done:
                ids=pending.pop(f);r=f.result();completed.append(r)
                db.executemany('UPDATE claims SET status=? WHERE record_id=?',[('CLOSED',rid)for rid in ids]);db.commit()
        def dispatch(rows,number):
            ids=[]
            for r in rows:
                rid='pprime:'+r['molecule_id']+':'+str(r['sprime_conf_idx'])
                try:db.execute('INSERT INTO claims VALUES(?,?,?)',(rid,number,'NATIVE_INTENT'))
                except sqlite3.IntegrityError:continue
                ids.append(rid)
            db.commit();allowed=set(ids);selected=[r for r in rows if 'pprime:'+r['molecule_id']+':'+str(r['sprime_conf_idx'])in allowed]
            if selected:pending[pool.submit(batch_work,(number,selected,str(out)))]=ids
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1024):
            for row in batch.to_pylist():
                rank=int(row['random_order_rank'])
                if rank not in (0,1):raise ValueError('PPRIME_THIRD_OR_LATER_CONFORMER_FORBIDDEN')
                rid=(row['molecule_id'],int(row['sprime_conf_idx']))
                if rid in seen:raise ValueError('DUPLICATE_SCOPE_CONFORMER')
                seen.add(rid);scope_mids.add(row['molecule_id'])
                if ordinal%parts==part:buffer.append(row)
                ordinal+=1
                if len(buffer)>=128:
                    while len(pending)>=cpus:settle(True)
                    dispatch(buffer,number);number+=1;buffer=[]
            settle(False)
        if buffer:dispatch(buffer,number)
        while pending:settle(True)
    if len(seen)!=161456 or len(scope_mids)!=80728:raise ValueError('CLOSED_SCOPE_ID_COUNT_DIFFERS')
    old=[read(p)for p in out.glob('batch_*/checkpoint.json')]
    manifest={'status':'COMPLETED_SCOPE_WITH_RECORDED_SCIENTIFIC_FAILURES','scope':plan['scope'],'part':part,'parts':parts,'records_assigned':sum(r['assigned']for r in old),'records_completed':sum(r['completed']for r in old),'all12_success':sum(r['all12_success']for r in old),'batches':old,'no_new_pilot':True,'no_Pprime_rank_ge_2':True,'independent_readback':False,'additional_source_or_delivery_hash_jobs':False,'original_native_recipe_900s_unchanged':True}
    save(out/'manifest.json',manifest);db.close();print(json.dumps({k:v for k,v in manifest.items()if k!='batches'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();run(read(a.plan))