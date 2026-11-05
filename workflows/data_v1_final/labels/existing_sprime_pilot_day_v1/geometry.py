"""Real old-Sprime/PM7 pilot bases, original D7 orders and input-bound children.

No generation/optimization and no Common/final-D5 status is manufactured.
The original PM7 cache is reopened; PM7 RMSD/order math is not repeated here.
"""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,stat,struct
from . import contract as C,io as I
from workflows.data_v1_final.conformers.pm7_precache_day_v1 import io as CacheIO,metadata as CacheMeta
from workflows.data_v1_final.conformers.postprocess_day_v1 import worker as OriginalWorker,math_bridge as OriginalMath
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import canonical_children as Child,core as Wire
from workflows.data_v1_final.export.d5_inputs_builder_v1 import geometry as Geometry
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as PC
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,lookup_batch,classify_owner

def gid(source,mid,identity):
    # Exact original common producer physical-ID expressions, not a new ID or
    # a geometry-equivalence join. The source/native identity remains separate.
    text=str(identity) if source=='pm7' else mid+':'+str(identity)
    return source+':'+hashlib.sha256(text.encode()).hexdigest()

class CacheContext:
    """Explicit readonly adapter to the original packet validators, no globals."""
    def __init__(self,p,proof,out,base,roots):
        self.plan=p;self.proof=proof;self.out=out;self.cache_plan=None;self.roots=roots
        self.controls=CacheIO.POP.controls(base,proof)
    def require(self,r,*a,**k):self.authorized([r]);return I.require(r)
    require_pin=require
    geometry_sha=staticmethod(OriginalWorker.IO.geometry_sha)
    def authorized(self,refs):
        for r in refs:
            if r['path'] in I.ALLOWED:continue
            path=pathlib.Path(r['path']);root=next((v for v in self.roots if pathlib.Path(v) in path.parents),None)
            C.need(root is not None,'ONLY_BOUND_REGISTERED_CACHE_OR_REAL_C0_CONTROL_OUTPUTS');I.allow(r,origin=root)
    def read(self,r,limit=512<<20):self.authorized([r]);return I.load_data(r,limit)
    def reference(self,path):
        r=I.pin(path);self.authorized([r]);return r

def original_worker_init(proof):OriginalWorker.initialize({'proof':proof})

def compute(work):
    """Direct original native reader/graph and D7 object under the real Parent."""
    task,cache,sprime,root,claim=work;native=OriginalWorker.SCIENCE
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

def metadata_children(plan,proof,root,budget,base_result,diagnostic_mids):
    """Original renderer/double-hash child object, metadata columns only.

The inherited producer SHA + actual frozen footer/current-same-FD convention
is exactly the original compact project convention. No fresh whole original
Parquet SHA or retained original input body is claimed by this metadata scan.
"""
    import pyarrow as pa,pyarrow.parquet as pq,sqlite3
    from workflows.data_v1_final.labels.full_projection_v1.directory import resolve
    from workflows.data_v1_final.labels.bounded_projection_v1.run import frame
    from workflows.data_v1_final.labels.footer_inventory_v1.footer import footer_only
    from workflows.data_v1_final.export.d5_inputs_builder_v1.children import sources as original_sources
    from workflows.data_v1_final.labels.common_train_normalization_day_v1.authority import check_diagnostic_rows
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import TASK_FAMILIES
    root=pathlib.Path(root);root.mkdir();review=C.meta(plan['source_metadata_frame_review_reference'])
    C.need(review['schema']=='ROOT_PILOT_RAW_METADATA_SOURCE_FRAME_REVIEW_V1' and review['status']=='APPROVED_ORIGINAL_INHERITED_SHA_FOOTER_FD_GUARD'
        and review['reviewer']=='root' and review['node']==proof['request']['node']
        and review['source_inventory_reference']==plan['source_inventory_reference'] and review['footer_manifest_reference']==plan['footer_manifest_reference']
        and review['fresh_original_Parquet_whole_SHA_claimed']is False,'ACTUAL_SAME_STORAGE_NODE_AND_ORIGINAL_FOOTER_SOURCE_GUARD_NOT_HASH_STAGE_ALIAS')
    C.meta(review['actual_same_storage_mapping_probe_reference'])
    protocol_review=C.meta(plan['WP5_input_derivation_authority_reference']);protocols={};families=set();tasks_all=set();objects=original_sources()
    C.need(protocol_review['schema']=='ROOT_BOUNDED_PILOT_WP5_INPUT_DERIVATION_AUTHORITY_V1'
        and protocol_review['status']=='APPROVED_EXACT_ORIGINAL_CALL_INPUTS_WITHIN_PILOT'
        and protocol_review['reviewer']=='root' and protocol_review['pilot_input_review_reference']==plan['pilot_input_review_reference']
        and protocol_review['source_inventory_reference']==plan['source_inventory_reference']
        and protocol_review['actual_per_call_both_input_hashes_required']is True and protocol_review['no_new_QM_UFF_or_graph_repair']is True,
        'NEW_BOUNDED_CALL_INPUT_POLICY_NOT_FALSE_FULL_COMMON_AUTHORITY')
    for item in protocol_review['package_protocol_references']:
        package=C.meta(item['package_reference']);protocol=C.meta(item['protocol_reference']);objects[0].load_protocol(protocol)
        C.need(package['protocol']['path']==item['protocol_reference']['path'] and package['protocol']['sha256']==item['protocol_reference']['sha256'],'EXACT_ORIGINAL_REPRO_PACKAGE_PROTOCOL')
        perturbed={t['name'] for t in protocol['tasks'] if t.get('perturbed')is True}
        C.need(perturbed==set(protocol_review['expected_perturbed_tasks']),'ORIGINAL_PERTURBED_TASK_SET_NOT_NAME_GUESSED')
        protocols[item['package_reference']['sha256']]=(protocol,item['protocol_reference'])
        names={t['name'] for t in protocol['tasks']};C.need(not tasks_all or tasks_all==names,'SAME_ORIGINAL_TWELVE_TASK_SET_ALL_PACKAGES')
        tasks_all=names;families.update(TASK_FAMILIES[t] for t in names)
    db=sqlite3.connect(root/'geometry.sqlite');db.executescript('CREATE TABLE base(gid TEXT PRIMARY KEY,mid TEXT,rid TEXT,src TEXT,row BLOB);CREATE UNIQUE INDEX native_pm7 ON base(rid) WHERE src=\'pm7\';'
        'CREATE TABLE children(gid TEXT PRIMARY KEY,parent TEXT,mid TEXT,row BLOB);CREATE TABLE input_views(gid TEXT PRIMARY KEY,parent TEXT,mid TEXT,row BLOB);'
        'CREATE INDEX children_mid ON children(mid);CREATE INDEX input_views_parent ON input_views(parent);'
        'CREATE TABLE bindings(rid TEXT,task TEXT,geometry_sha TEXT,gid TEXT,unknown INTEGER,source TEXT,physical_row INTEGER,PRIMARY KEY(rid,task));'
        'CREATE TABLE seen(rid TEXT,task TEXT,PRIMARY KEY(rid,task));CREATE TABLE unknown(rid TEXT,task TEXT,row BLOB);')
    for batch in pq.ParquetFile(I.require(base_result['table_references']['geometries'])).iter_batches(batch_size=512,use_threads=False):
        for row in batch.to_pylist():db.execute('INSERT INTO base VALUES(?,?,?,?,?)',(row['geometry_id'],row['molecule_id'],row['native_record_id'],row['geometry_source'],Wire.encode(row)))
    selected_catalog=sqlite_ro(I.require(plan['resolved_coverage_catalog_reference']))
    try:selected_jobs={r[0] for r in selected_catalog.execute('SELECT DISTINCT job FROM selected')}
    finally:selected_catalog.close()
    book=I.load_data(plan['source_inventory_reference'],2<<20);selected=[s for s in book['files'] if s['family'] in families and s['source_job_id'] in selected_jobs]
    selector=I.save(root/'metadata_source_selector.json',{'sources':[{'file_id':s['file_id'],'physical_row_lo':0,'physical_row_hi':s['rows']} for s in selected]})
    directory_cfg=dict(plan,selector_reference=selector,max_actual_RGs_per_source=1)
    directory=resolve(directory_cfg);source_info={r['file_id']:r for r in directory['ranges']};C.need(set(source_info)=={s['file_id'] for s in selected},'ALL_AND_ONLY_SELECTED_JOB_METADATA_SOURCES')
    canonical=sqlite_ro(I.require(plan['canonical_index']));unknown_uuid=0;observations=[];columns=list(Child.COLUMNS)
    try:
        for source in selected:
            budget.check();item=source_info[source['file_id']];path=pathlib.Path(source['path']);before=path.lstat();current=frame(before);expected=item['footer_observed_source_frame']
            C.need(all(current[k]==expected[k] for k in expected if k!='device') and before.st_uid==1278
                and stat.S_ISREG(before.st_mode) and before.st_nlink==1 and not any(q.is_symlink() for q in (path,*path.parents)),
                'ORIGINAL_FROZEN_FOOTER_ALL_NONDEVICE_SOURCE_FIELDS_REAL_UID_REGULAR_NO_SYMLINK')
            with path.open('rb') as stream:
                C.need(frame(os.fstat(stream.fileno()))==current,'RAW_METADATA_SAME_REAL_FD_AT_OPEN')
                alias=current['device']!=expected['device']
                if alias:C.need(footer_only(stream,before.st_size)['actual_footer_sha256']==item['expected_footer_sha256'],'ORIGINAL_DEVICE_ALIAS_EXACT_REHASHED_FOOTER')
                stream.seek(0);parquet=pq.ParquetFile(stream,pre_buffer=False);position=0
                try:
                    C.need(parquet.metadata.num_rows==source['rows'] and parquet.num_row_groups==item['file_row_groups'],'REAL_ORIGINAL_METADATA_ROW_DIRECTORY')
                    for batch in parquet.iter_batches(batch_size=256,columns=columns,use_threads=False):
                        budget.check();owners=lookup_batch(canonical,batch.column(batch.schema.get_field_index('record_id')).to_pylist())
                        for k,row in enumerate(batch.to_pylist()):
                            base=db.execute("SELECT row FROM base WHERE rid=? AND src='pm7'",(row['record_id'],)).fetchone()
                            if base is None:continue
                            owner=owners.get(row['record_id'])
                            if row['calc_type'] not in tasks_all or classify_owner(row,owner,True)!='CANONICAL':continue
                            C.need(row['job_id']==source['source_job_id'],'EXACT_CANONICAL_SOURCE_JOB');db.execute('INSERT INTO seen VALUES(?,?)',(row['record_id'],row['calc_type']))
                            try:
                                protocol,pref=protocols[row['reproduction_package_sha256']]
                                base_value=Wire.decode(base[0]);recipe=next(t for t in protocol['tasks'] if t['name']==row['calc_type'])
                                if recipe.get('perturbed')is True:
                                    value,uuid_unknown=Child.child(row,base_value,source,position+k,protocol,objects);table='children';unknown_uuid+=int(uuid_unknown)
                                else:
                                    # Exact actual program-input view, not a new
                                    # independent conformer or an assertion that
                                    # source float64 equals rendered decimals.
                                    from rdkit import Chem
                                    from workflows.data_v1_final.pprime.geometry import geometry_hash
                                    engine,legacy,archive,_=objects;engine.load_protocol(protocol)
                                    symbols=[Chem.GetPeriodicTable().GetElementSymbol(z) for z in base_value['atomic_numbers']]
                                    rendered=engine.render_inputs(recipe,{'symbols':symbols,'coords':base_value['positions_A']},{'record_id':row['record_id']},protocol)
                                    Child.H.O.input_binding(rendered,row['input_file_sha256'],row['input_bundle_sha256'],archive.bundle)
                                    name='input.mop' if recipe['family']=='mopac' else 'input.xyz'
                                    xyz=Child.H.O.input_coordinates(rendered[name],name,symbols,legacy.f)
                                    C.need(Child.H.O.equal_numbers(xyz,Child.H.O.input_coordinates(rendered['input.xyz'],'input.xyz',symbols,legacy.f)),'ACTUAL_UNPERTURBED_PROGRAM_AND_XYZ_COORDINATES_EQUAL')
                                    occurrence,identity=Child.canonical_occurrence(source,position+k,row)
                                    uuid=None
                                    if row.get('raw_output_locator_json') is not None:
                                        locator=json.loads(row['raw_output_locator_json']);C.need(type(locator)is dict,'ORIGINAL_UNPERTURBED_RAW_LOCATOR_JSON_OBJECT')
                                        if locator.get('execution_id') is not None:
                                            C.need(locator.get('record_id')==row['record_id'] and locator.get('calc_type')==row['calc_type']
                                                and type(locator['execution_id'])is str and locator['execution_id'],'ORIGINAL_UNPERTURBED_UUID_FROM_EXACT_STORED_ROW_ONLY')
                                            uuid=locator['execution_id']
                                    unknown_uuid+=uuid is None
                                    new_gid,_=Geometry.child_identity(base_value,row['record_id'],row['calc_type'],uuid if uuid is not None else occurrence,row['input_bundle_sha256'])
                                    value=dict(base_value,geometry_id=new_gid,parent_geometry_id=base_value['geometry_id'],view_id='actual_wp5_unperturbed_program_input_view_v1',
                                        positions_A=xyz,geometry_sha256=geometry_hash(base_value['atomic_numbers'],xyz),order_energy=None,
                                        actual_input_bundle_sha256=row['input_bundle_sha256'],actual_input_origin='EXACT_ORIGINAL_INPUT_HASH_RECONSTRUCTION_NOT_NEW_CONFORMER',
                                        source_provenance_json=json.dumps({'canonical_occurrence':identity,'original_execution_uuid':uuid,
                                            'original_execution_uuid_state':'ACTUAL_STORED_RAW_LOCATOR' if uuid else 'UNKNOWN_NOT_RETAINED',
                                            'original_input_file_sha256':row['input_file_sha256'],'not_ordinary_N_inflation':True},sort_keys=True));table='input_views'
                                value['actual_protocol_sha256']=pref['sha256'];db.execute('INSERT INTO '+table+' VALUES(?,?,?,?)',(value['geometry_id'],value['parent_geometry_id'],value['molecule_id'],Wire.encode(value)))
                                db.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?)',(row['record_id'],row['calc_type'],value['geometry_sha256'],value['geometry_id'],0,json.dumps(C.reference(source),sort_keys=True),position+k))
                            except Exception as exc:
                                db.execute('INSERT INTO unknown VALUES(?,?,?)',(row['record_id'],row['calc_type'],Wire.encode({'source':C.reference(source),'physical_row':position+k,'error':repr(exc),'original_values_not_modified':True})))
                                db.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?)',(row['record_id'],row['calc_type'],None,None,1,json.dumps(C.reference(source),sort_keys=True),position+k))
                        position+=batch.num_rows;db.commit()
                    C.need(position==source['rows'],'FULL_REQUIRED_METADATA_COLUMN_SCAN_NOT_TRUNCATED')
                finally:parquet.close()
                C.need(frame(os.fstat(stream.fileno()))==current==frame(path.lstat()),'ORIGINAL_SOURCE_STABLE_SAME_FD_AFTER_METADATA_SCAN')
            observations.append({'reference':C.reference(source),'current_storage_frame':current,'footer_reference':plan['footer_manifest_reference'],
                'source_verification':'INHERITED_PRODUCER_SHA_CURRENT_FOOTER_FRAME_MATCHED_STABLE_FSTAT','cross_node_device_alias_footer_rehashed':alias,'original_numeric_columns_parsed':False,'fresh_original_whole_SHA_claimed':False})
        nbase=db.execute("SELECT count(*) FROM base WHERE src='pm7'").fetchone()[0];seen=db.execute('SELECT count(*) FROM seen').fetchone()[0];bad=db.execute('SELECT count(*) FROM unknown').fetchone()[0];nchild=db.execute('SELECT count(*) FROM children').fetchone()[0];nview=db.execute('SELECT count(*) FROM input_views').fetchone()[0]
        I.save(root/'input_binding_census.json',{'expected':nbase*len(tasks_all),'seen':seen,'perturbed_children':nchild,'unperturbed_program_input_views':nview,'unknown':bad,'unknown_UUIDs_not_fabricated':unknown_uuid})
        C.closed_children(nbase*len(tasks_all),seen,bad,nchild+nview)
        diagnostic={}
        for batch in pq.ParquetFile(I.require(base_result['table_references']['orders'])).iter_batches(batch_size=1024,use_threads=False):
            for row in batch.to_pylist():
                if row['molecule_id'] not in diagnostic_mids or row['order_type']!='fixed_random':continue
                key=(row['molecule_id'],row['geometry_source']);prior=diagnostic.get(key)
                if prior is None or row['rank']>prior['rank']:diagnostic[key]=dict(row)
        diagnostic=list(diagnostic.values());mids={r['molecule_id'] for r in diagnostic}
        expected_mids={r[0] for r in db.execute('SELECT DISTINCT mid FROM base')} & diagnostic_mids
        C.need(mids==expected_mids,'ALL_AND_ONLY_GLOBAL20K_DIAGNOSTIC_MIDS_INSIDE_REAL_PILOT')
        base_rows=[Wire.decode(db.execute('SELECT row FROM base WHERE gid=?',(r['geometry_id'],)).fetchone()[0]) for r in diagnostic]
        if mids:check_diagnostic_rows(diagnostic,base_rows,{mid:True for mid in mids},{mid:'TRAIN' for mid in mids},expected=len(mids))
        excluded={r['geometry_id'] for r in diagnostic}
        def all_geometry():
            for (raw,) in db.execute('SELECT row FROM base ORDER BY gid'):yield Wire.decode(raw)
            for (raw,) in db.execute('SELECT row FROM children ORDER BY gid'):yield Wire.decode(raw)
        geometry_ref=I.write_parquet(root/'geometries.parquet',all_geometry(),Wire.schemas()['geometries'])
        atom_counts=I.write_parquet(root/'atom_counts.parquet',({'geometry_id':r['geometry_id'],'n_atoms':len(r['atomic_numbers'])} for r in all_geometry()),Wire.schemas()['atom_counts'])
        def roster():
            source=pq.ParquetFile(I.require(base_result['table_references']['roster']))
            try:
                for batch in source.iter_batches(batch_size=256,use_threads=False):
                    for row in batch.to_pylist():
                        row['child_count']=db.execute('SELECT count(*) FROM children WHERE mid=?',(row['molecule_id'],)).fetchone()[0];yield row
            finally:source.close()
        roster_ref=I.write_parquet(root/'roster.parquet',roster(),Wire.schemas()['roster'])
        key_schema=pa.schema([('molecule_id',pa.string()),('geometry_source',pa.string()),('geometry_id',pa.string())])
        def diagnostic_targets():
            for row in all_geometry():
                if row['geometry_id'] in excluded or row['parent_geometry_id'] in excluded:yield {k:row[k] for k in ('molecule_id','geometry_source','geometry_id')}
            for (raw,) in db.execute('SELECT row FROM input_views ORDER BY gid'):
                row=Wire.decode(raw)
                if row['parent_geometry_id'] in excluded:yield {k:row[k] for k in ('molecule_id','geometry_source','geometry_id')}
        diag_ref=I.write_parquet(root/'diagnostic_base.parquet',({k:r[k] for k in ('molecule_id','geometry_source','geometry_id')} for r in diagnostic),key_schema)
        targets=I.write_parquet(root/'diagnostic_targets.parquet',diagnostic_targets(),key_schema)
        input_views=I.write_parquet(root/'actual_unperturbed_program_input_views.parquet',(Wire.decode(r[0]) for r in db.execute('SELECT row FROM input_views ORDER BY gid')),Wire.schemas()['geometries'])
        db.commit();db.close();db=None;binding_ref=I.allow(I.pin(root/'geometry.sqlite'))
        result=dict(base_result,table_references=dict(base_result['table_references'],geometries=geometry_ref,atom_counts=atom_counts,roster=roster_ref),
            diagnostic_base_reference=diag_ref,diagnostic_target_reference=targets,global_preselected_diagnostic_MIDs=20000,
            actual_in_pilot_diagnostic_MIDs=len(mids),global_D5_diagnostic_geometry_release=False,
            all_in_scope_actual_direct_children_bound=True,unknown_input_bindings=bad,original_execution_UUID_UNKNOWN=unknown_uuid,
            actual_child_census={'expected':nbase*len(tasks_all),'seen':seen,'perturbed_children':nchild,'unperturbed_program_views':nview,'unknown':bad},
            actual_program_input_view_reference=input_views,cell_binding_reference=binding_ref,
            raw_metadata_source_observations=observations,whole_original_raw_Parquet_rehashed=False,
            actual_child_function='DIRECT_ORIGINAL_d5_inputs_compound_day_v1.canonical_children.child',same_parent_candidate_not_external_C0=True)
        result['manifest_reference']=I.save(root/'manifest.json',result);return result
    finally:
        if db is not None:db.close()
        canonical.close()
