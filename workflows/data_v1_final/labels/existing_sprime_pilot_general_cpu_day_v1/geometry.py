"""Truthful general CPU native context; all original numerical objects retained."""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,stat,struct,socket
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,geometry as OLD
from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import worker_context as WORKER
CacheIO=OLD.CacheIO;CacheMeta=OLD.CacheMeta;OriginalWorker=OLD.OriginalWorker;OriginalMath=OLD.OriginalMath
Child=OLD.Child;Wire=OLD.Wire;Geometry=OLD.Geometry;PC=OLD.PC
sqlite_ro=OLD.sqlite_ro;lookup_batch=OLD.lookup_batch;classify_owner=OLD.classify_owner
CacheContext=OLD.CacheContext;gid=OLD.gid;metadata_children=OLD.metadata_children

def validate_worker_identity(proof,facts):
    req=proof['request'];C.need(facts['uid']==1278 and facts['node']==req['node'] and req['node'] in WORKER.I.M.ANALYSIS_NODES
        and req['cpus']==16 and facts['cpus']==16 and facts['job_id']==str(proof['job_id'])
        and facts['partition']=='cpu' and facts['cuda_visible_devices']=='' and facts['boot_id']==proof['boot_id'],
        'TRUTHFUL_GENERAL_CPU16_CURRENT_WORKER_NOT_FAKE_OLD14_OR18')

def original_worker_init(proof):
    facts={'uid':os.getuid(),'node':socket.gethostname().split('.')[0],'cpus':int(os.environ.get('SLURM_CPUS_PER_TASK','0')),
        'job_id':os.environ.get('SLURM_JOB_ID'),'partition':os.environ.get('SLURM_JOB_PARTITION'),
        'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    validate_worker_identity(proof,facts)
    WORKER.initialize({'proof':proof})

def compute(work):
    """Direct original native reader/graph and D7 object under the real Parent."""
    task,cache,sprime,root,claim=work;native=WORKER.SCIENCE
    by={r['conformer_id']:r for r in cache['pm7']};C.need(set(by)=={r['record_id'] for r in task['records']},'ALL_ORIGINAL_PM7_RECORDS_IN_VALIDATED_CACHE')
    for pointer in task['records']:
        value=native.read(pointer);mol,z,xyz=native.graph(value);actual=CacheIO.POPIO.H.profile_common().IO.geometry_sha(z,xyz)
        C.need(actual==by[pointer['record_id']]['geometry_sha256'] and z.tolist()==cache['atomic_numbers'],
            'CURRENT_NATIVE_PAYLOAD_GRAPH_ATOMS_F64_EQUAL_ORIGINAL_CACHE_NOT_ONLY_OLD_PARENT_STATUS')
    d7_task={'meta':dict(task['meta'],S_conformers=len(task['records']),Sprime_conformers=len(sprime)),
        'records':task['records'],'sprime':sprime,'hof':task['hof']}
    d7=OriginalWorker.d7(d7_task,cache,native)
    C.need(d7['status']=='D7_MOLECULE_PROFILE_COMPLETE' and d7['hof_range_complete'] is True
        and all(d7['orders'][s].get('status')=='COMPLETE' for s in ('pm7','uff_sprime')),'REAL_BOTH_SOURCE_THREE_ORDERS_AND_CANONICAL_HOF_NOT_PENDING')
    bases=[];mid=task['meta']['molecule_id'];pointers={r['record_id']:r for r in task['records']}
    for row in cache['pm7']:
        pointer=pointers[row['conformer_id']];rid=pointer['record_id'];xyz=row['coordinates'];z=cache['atomic_numbers']
        bases.append({'molecule_id':mid,'geometry_source':'pm7','geometry_id':gid('pm7',mid,rid),'native_record_id':rid,'sprime_conf_idx':None,
            'parent_geometry_id':None,'view_id':None,'positions_A':xyz,'atomic_numbers':z,'geometry_sha256':row['geometry_sha256'],
            'atom_order_sha256':cache['atom_order_sha256'],'order_energy':task['hof'][rid]['value_kcal_mol'],
            'source_path':pointer['source_path'],'source_row_index':pointer['real_index'],'source_format':'native_lmdb',
            'source_provenance_json':json.dumps(pointer,sort_keys=True),'actual_input_origin':'ORIGINAL_PAYLOAD_REOPENED_AND_EQUAL_CACHED_F64',
            'energy_source':'CANONICAL_PM7_B_REGISTRY60_KCAL_MOL'})
    for row in sprime:
        index=row['sprime_conf_idx'];bases.append({'molecule_id':mid,'geometry_source':'uff_sprime','geometry_id':gid('uff_sprime',mid,index),
            'native_record_id':None,'sprime_conf_idx':index,'parent_geometry_id':None,'view_id':None,'positions_A':row['coordinates'],
            'atomic_numbers':cache['atomic_numbers'],'geometry_sha256':d7['geometry_hashes']['uff_sprime'][str(index)],
            'atom_order_sha256':row['atom_order_sha256'],'order_energy':float(row['uff_energy_kcal_mol']),
            'source_path':row['__source']['path'],'source_sha256':row['__source']['sha256'],'source_bytes':row['__source']['bytes'],
            'source_row_index':row['__physical_row'],'source_format':'parquet','original_sprime_conf_idx':index,'source_conformer_id':index,
            'canonical_sprime_conf_idx':index,'identity_namespace':'accepted_original_sprime','seed':row['seed'],
            'native_anchor_record_id':row['source_record_id'],'source_provenance_json':json.dumps({'source':row['__source'],'physical_row':row['__physical_row']},sort_keys=True),
            'actual_input_origin':'ACTUAL_OLD_SPRIME_ROW_GRAPH_STEREO_CHECKED','energy_source':'ACTUAL_UFF_KCAL_MOL'})
    orders=[]
    for source in ('pm7','uff_sprime'):
        for kind in ('fixed_random','energy','diversity'):
            ids=d7['orders'][source][kind]
            C.need(len(ids)==len(task['records']) and len(set(ids))==len(ids),'ORIGINAL_N_ALL_THREE_NATIVE_ORDER_PERMUTATIONS')
            orders.extend({'molecule_id':mid,'geometry_source':source,'order_type':kind,'method':kind,'rank':rank,'geometry_id':gid(source,mid,key)} for rank,key in enumerate(ids))
    for row in bases:Geometry.physical_key(row)
    anchor=native.read(task['records'][0]);smiles=str(native.field(anchor,'smiles'))
    scaffold=OriginalMath.scaffold_chunk([(mid,smiles)])
    C.need(len(scaffold)==1 and scaffold[0]['molecule_id']==mid,'ORIGINAL_SCAFFOLD_FUNCTION_EXACT_MID')
    features={'molecule_id':mid,'elements_atomic_numbers':sorted(set(cache['atomic_numbers'])),
        **{key:d7[key] for key in ('heavy_atoms','rotatable_bonds','rings')},
        'generic_scaffold':scaffold[0]['generic_scaffold'],'scaffold_status':scaffold[0]['scaffold_status']}
    value={'schema':'BOUNDED_EXISTING_SPRIME_ORDINARY_MOLECULE_V1','molecule_id':mid,'bases':bases,'orders':orders,'d7':d7,'bias_features':features,
        'source_cache_claim_reference':claim,'same_parent_new_geometry_or_optimization':False,'new_QM_UFF_calls':0,'final_Common':False}
    raw=Wire.encode(value);path=pathlib.Path(root)/(hashlib.sha256(mid.encode()).hexdigest()+'.lossless.json')
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    r=I.pin(path);C.need(Wire.decode(path.read_bytes())==value,'FULL_LOSSLESS_MOLECULE_F64_REOPEN')
    return {'reference':r,'molecule_id':mid,'pid':os.getpid()}

def build(plan,proof,root,budget,prefix,old,oldproof,cohort):
    """Close exactly the selected55k from real immutable cache and old rows."""
    import pyarrow as pa,pyarrow.parquet as pq,sqlite3
    root=pathlib.Path(root);root.mkdir();workers=root/'molecules';workers.mkdir()
    review,_,_=C.prefix_origin(plan);base=C.meta(old['base_cache_plan_reference'])
    producer_meta,producer_io=C.prefix_adapter(oldproof['request'])
    origins=producer_io.registered_origins(old,proof)
    origins[str(oldproof['job_id'])]={'job_id':str(oldproof['job_id']),'kind':'day','root':old['output_directory'],'request':oldproof['request'],'proof':oldproof}
    roots=[r['root'] for r in origins.values()]+[str(PC.BASE),str(C.RUN/'artifacts/conformers/pm7_hof_augmentation32_v1')]
    ctx=CacheContext(old,proof,root,base,roots);db=sqlite3.connect(root/'selected.sqlite')
    db.executescript('CREATE TABLE cache(mid TEXT PRIMARY KEY,row BLOB);CREATE TABLE sprime(mid TEXT,idx INTEGER,row BLOB,PRIMARY KEY(mid,idx));')
    for ref in prefix['catalog_part_references']:
        path=I.require(ref);src=pq.ParquetFile(path)
        try:
            for batch in src.iter_batches(batch_size=512,use_threads=False):
                budget.check()
                for row in batch.to_pylist():
                    item=json.loads(row['row_json']);mid=row['molecule_id'];C.need(mid in cohort,'NO_EXTRA_MID_IN_EXACT55K_PRIORITY_PREFIX')
                    db.execute('INSERT INTO cache VALUES(?,?)',(mid,Wire.encode(item)))
        finally:src.close()
    C.need(db.execute('SELECT count(*) FROM cache').fetchone()[0]==55000,'EXACT_NO_DUPLICATE55K_CACHE_ROWS')
    pre=I.load_data(prefix['preselection_reference'],8<<20);oldrefs=pre['old_Sprime_coordinate_source_references']
    columns=['molecule_id','sprime_conf_idx','coordinates','atom_order_sha256','source_record_id','seed','status','converged','uff_energy_kcal_mol','stereo_signature']
    for ref in oldrefs:
        I.allow(ref,origin=pathlib.Path(ref['path']).parent);path=I.require(ref);src=pq.ParquetFile(path);offset=0
        try:
            for batch in src.iter_batches(batch_size=256,columns=columns,use_threads=False):
                budget.check()
                for k,row in enumerate(batch.to_pylist()):
                    if row['molecule_id'] not in cohort or row['status']!='SUCCESS' or row['converged']is not True:continue
                    C.need(type(row['sprime_conf_idx'])is int and row['sprime_conf_idx']>=0,'REAL_OLD_SPRIME_INT64_NO_RENUMBER')
                    row.update(__source=ref,__physical_row=offset+k);db.execute('INSERT INTO sprime VALUES(?,?,?)',(row['molecule_id'],row['sprime_conf_idx'],Wire.encode(row)))
                offset+=batch.num_rows
                db.commit()
        finally:src.close()
        I.require(ref)
    reports=[]
    def work():
        for mid in sorted(cohort):
            budget.check();row=Wire.decode(db.execute('SELECT row FROM cache WHERE mid=?',(mid,)).fetchone()[0]);lr=row.get('claim_reference')
            if lr is None:
                C.need(row['state']=='IMPORTED_EXISTING32' and row['origin_kind']=='LEGACY32' and mid in ctx.controls[0],
                    'ONLY_REAL_ORIGINAL32_TWO_C0_AUTHORITIES_WITHOUT_NEW_CLAIM_NO_INFERRED_WORKER_START')
                g,h=ctx.controls;packet=CacheIO.BI.read_packet(g[mid]['packet_reference']);extra=ctx.read(h[mid]['packet_reference'],128<<20)
                task={'cache_key':row['cache_key'],'records':packet['source_records'],'hof':extra['hof_by_record'],
                    'meta':dict(cohort[mid],records=len(packet['source_records']))}
                cache=CacheIO.control32_packet(ctx,task)
                lr={'original_geometry32_reference':g[mid]['packet_reference'],'original_HOF32_reference':h[mid]['packet_reference'],
                    'new_claim_or_worker_start_inferred':False}
            else:
                ctx.authorized([lr]);claim=ctx.read(lr)
                ctx.authorized([claim['task_reference']]);task=ctx.read(claim['task_reference']);_,cache=producer_io.packet_from_claim(ctx,task,claim,lr,origins)
            C.need(task['meta']['molecule_id']==mid and len(task['records'])==cohort[mid]['S_conformers'],'EXACT_PILOT_OLD_EXPECTED_N_AND_CACHE_NATIVE_RECORDS')
            sprime=[Wire.decode(r[0]) for r in db.execute('SELECT row FROM sprime WHERE mid=? ORDER BY idx',(mid,))]
            C.need(len(sprime)==cohort[mid]['Sprime_conformers']==len(task['records']),'EXACT_OLD_COMPLETE_COUNT_NO_NEW_OR_CLONED_UFF')
            task=dict(task,meta=dict(task['meta'],split_role=cohort[mid]['source_role'],effective_role=cohort[mid]['effective_role']))
            yield task,cache,sprime,str(workers),lr
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=original_worker_init,initargs=(proof,)) as pool:
            iterator=iter(work());pending={}
            while True:
                while len(pending)<16:
                    budget.check()
                    try:task=next(iterator)
                    except StopIteration:break
                    pending[pool.submit(compute,task)]=task[0]['meta']['molecule_id']
                if not pending:break
                done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    mid=pending.pop(future);report=future.result();C.need(report['molecule_id']==mid,'EXACT_WORKER_MID_RETURN');I.allow(report['reference']);reports.append(report)
    finally:db.close()
    C.need(len(reports)==55000 and len({r['molecule_id'] for r in reports})==55000,'NO_PARTIAL_PILOT_GEOMETRY_ORDER_CLOSURE')
    schemas=Wire.schemas();tables={}
    for kind in ('geometries','orders','atom_counts','audit_identity','roster'):
        def rows():
            for k,report in enumerate(sorted(reports,key=lambda r:r['molecule_id'])):
                budget.check();v=Wire.decode(I.require(report['reference']).read_bytes())
                if kind=='geometries':yield from v['bases']
                elif kind=='orders':yield from v['orders']
                elif kind=='atom_counts':yield from ({'geometry_id':b['geometry_id'],'n_atoms':len(b['atomic_numbers'])} for b in v['bases'])
                elif kind=='audit_identity':
                    for b in v['bases']:
                        if b['geometry_source']=='uff_sprime':yield {'molecule_id':v['molecule_id'],'geometry_id':b['geometry_id'],'physical_identity_json':json.dumps({'namespace':'accepted_original_sprime','source_conformer_id':b['sprime_conf_idx']},sort_keys=True)}
                else:yield {'logical_ordinal':k,'molecule_id':v['molecule_id'],'PM7_N':v['d7']['pm7_count'],'UFF_N':v['d7']['uff_sprime_count'],'child_count':0}
        tables[kind]=I.write_parquet(root/(kind+'.parquet'),rows(),schemas[kind])
    feature_schema=pa.schema([('molecule_id',pa.string()),('elements_atomic_numbers',pa.list_(pa.int64())),
        ('heavy_atoms',pa.int64()),('rotatable_bonds',pa.int64()),('rings',pa.int64()),('generic_scaffold',pa.string()),('scaffold_status',pa.string())])
    features=I.write_parquet(root/'bias_features.parquet',(Wire.decode(I.require(r['reference']).read_bytes())['bias_features'] for r in sorted(reports,key=lambda r:r['molecule_id'])),feature_schema)
    return {'schema':'PROVISIONAL_EXISTING_SPRIME_PILOT_BASE_ORDERS_V1','table_references':tables,'molecules':55000,
        'actual_parent_job_id':str(proof['job_id']),'bias_features_reference':features,'new_PM7_RMSD_recomputed':False,'new_QM_UFF_calls':0,
        'ordinary_base_N_preserved':True,'N1_second_UFF_not_created':True,'source_worker_report_references':[r['reference'] for r in reports],
        'D5_full_guide_nested_geometry_coverage':False,'final_Common':False}

