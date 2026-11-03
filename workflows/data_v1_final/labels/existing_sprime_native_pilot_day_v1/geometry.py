"""Exact frozen55k, real all-N geometry and fixed random; no D7/cache/HOF."""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,sqlite3
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,geometry as OLD
from workflows.data_v1_final.export.bounded_old_complete_d5_day_v1 import adopt as A,produce as P
from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import hof_resume as H
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as Wire
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import core as Cache
WORKER=P.WORKER;gid=OLD.gid;metadata_children=OLD.metadata_children

def prepare(plan,proof,root,budget):
    import duckdb
    ACCEPTED_CONFIG_REFERENCES.clear()
    review,qa,origin=C.native_origin(plan);base=C.meta(plan['base_cache_plan_reference'])
    path=root/'closed_scalar_preselection';path.mkdir();ctx=A.Context(plan,proof,path,budget)
    receipt=I.load_data(review['failed_receipt_reference'],16<<20)
    C.need(receipt['schema']=='PM7_PRECACHE_DAY_RECEIPT_V1' and str(receipt['job_id'])=='4524738'
      and receipt['startup_proof_reference']==origin['proof_reference'] and receipt['closed_state_reference']==review['closed_state_reference']
      and receipt['HOF_projection_complete']is False and not receipt['state_counts'] and not receipt['unknown'],'EXACT_FAILED_SCALAR_PARENT_NOT_CACHE_OR_HOF_ACCEPTANCE')
    ref=receipt['pilot_preselection_reference'];C.reference(ref);C.need(ref['path']==review['pilot_preselection_locator'],'ONLY_CLOSED_FAILED_RECEIPT_ACTUAL_POSITIVE_PRESELECTION_REF')
    I.allow(ref,origin=review['old_output_root']);ctx.hof_resume_preselection_reference=ref
    C.need(not pathlib.Path(review['closed_state_reference']['path']+'.wal').exists(),'ORIGINAL_CLOSED_DB_NOT_ACTIVE_WAL')
    clone=H.clone(ctx,review['closed_state_reference'],path/'closed_original.duckdb')
    db=duckdb.connect(str(path/'native55k.duckdb'));db.execute('SET threads=16');db.execute("SET memory_limit='3GB'")
    scratch=path/'tmp';scratch.mkdir();db.execute('SET temp_directory='+H.C.q(str(scratch)));db.execute('ATTACH '+H.C.q(clone['path'])+' AS old (READ_ONLY)')
    try:
        for name in ('formal','roster','pilot_scalar_membership','pilot_complete_old_ranked','pilot_priority'):db.execute('CREATE VIEW '+name+' AS SELECT * FROM old.'+name)
        descriptors=I.load_data(base['future_shards_reference'],8<<20)['descriptors']
        pre_ref,priority,diagnostic,_=H.restore_priority(ctx,db,base,review,descriptors)
        pre=I.load_data(pre_ref,8<<20);C.need(len(priority)==55000 and len(diagnostic)==20000,'ORIGINAL_FROZEN55K_AND_GLOBAL20K_UNCHANGED')
        # Fixed55k semijoin first. Never materialize the entire native mother.
        q=H.C.q
        db.execute('CREATE TABLE members AS SELECT m.* FROM read_parquet('+q(pre['tables']['complete_old_mother']['path'])+') m SEMI JOIN pilot_priority p USING(molecule_id)')
        cols=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','smiles','file_group','conformer_id')
        I.require(base['formal_source'])
        db.execute('CREATE TABLE native55k AS SELECT '+','.join('f.'+x for x in cols)+' FROM read_parquet('+q(base['formal_source']['path'])+') f SEMI JOIN pilot_priority p USING(molecule_id)')
        db.execute('CREATE UNIQUE INDEX native_rid ON native55k(record_id)');db.execute('CREATE INDEX native_mid ON native55k(molecule_id)')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM members').fetchone()==(55000,55000),'EXACT55K_NATIVE_PREPARATION_NOT_A_NEW_DRAW')
        C.need(dict(db.execute('SELECT effective_role,count(*) FROM members GROUP BY effective_role').fetchall())==C.PILOT_COUNTS,'ORIGINAL50K_TRAIN5K_ROUTINE_VAL')
        original='SELECT '+','.join('f.'+x for x in cols)+' FROM old.formal f SEMI JOIN pilot_priority p USING(molecule_id)'
        C.need(db.execute('SELECT count(*) FROM (SELECT * FROM native55k EXCEPT ALL '+original+')').fetchone()[0]==0
          and db.execute('SELECT count(*) FROM ('+original+' EXCEPT ALL SELECT * FROM native55k)').fetchone()[0]==0,'CURRENT_WHOLE_SHA_SELECTED_NATIVE_POINTER_FIELDS_EQUAL_ORIGINAL_CLOSED_SOURCE')
        C.need(db.execute('SELECT count(*) FROM (SELECT m.molecule_id FROM members m LEFT JOIN native55k f USING(molecule_id) GROUP BY m.molecule_id,m.S_conformers HAVING count(f.record_id)<>m.S_conformers)').fetchone()[0]==0,'EVERY_FROZEN_MID_ALL_ORIGINAL_PM7_N_POINTERS')
        members=P.parquet_query(ctx,db,'SELECT * FROM members ORDER BY molecule_id',path/'selected55k_members.parquet')
        for name in ('formal','roster','pilot_scalar_membership','pilot_complete_old_ranked','pilot_priority'):db.execute('DROP VIEW '+name)
        db.execute('DETACH old')
    finally:db.close()
    native=I.allow(I.pin(path/'native55k.duckdb'))
    prefix={'schema':'CURRENT_PARENT_FROZEN_OLD55K_NATIVE_INPUTS_V1','preselection_reference':pre_ref,'members_reference':members,'native_catalog_reference':native,
      'old_failed_receipt_reference':review['failed_receipt_reference'],'original_canonical_index_reference':base['formal_source'],
      'actual_parent_job_id':str(proof['job_id']),'PM7_cache_or_HOF_or_D7_accepted':False,'no_new_molecule_selection':True}
    # The accepted closed producer explicitly binds its immutable config.
    # Register that exact transitive input; do not widen any global path guard.
    for origin_entry in C.projection_origins(plan)['projection_origins']:
        manifest=I.load_data(origin_entry['manifest_reference'],512<<20)
        C.need(str(manifest['job_id'])==str(C.meta(origin_entry['proof_reference'])['job_id']),'EXACT_CONFIG_PRODUCER_PARENT')
        config=C.reference(manifest['config']);config_path=pathlib.Path(config['path'])
        C.need(C.RUN in config_path.parents and config_path.suffix=='.json' and 0<config['bytes']<=8<<20,'FINITE_READONLY_CLOSED_PRODUCER_CONFIG')
        I.allow(config,origin=config_path.parent)
        ACCEPTED_CONFIG_REFERENCES[config['path']]=config
    pr=I.save(path/'native_inputs.json',prefix)
    return pr,prefix,{'output_directory':str(root)},proof

def cohort(prefix,old):
    import pyarrow.parquet as pq
    pre=I.load_data(prefix['preselection_reference'],8<<20);rows=pq.read_table(I.require(prefix['members_reference'])).to_pylist()
    members={r['molecule_id']:r for r in rows};C.need(len(rows)==len(members)==55000 and collections.Counter(r['effective_role']for r in rows)==C.PILOT_COUNTS,'EXACT_NATIVE55K_COHORT')
    for r in rows:C.need(r['scalar_complete_old_Sprime']is True,'ONLY_ORIGINAL_COMPLETE_MOTHER_NOT_STATUS_REPLACEMENT')
    ref=pre['tables']['diagnostic20k_molecule_preselection'];I.allow(ref,origin=pathlib.Path(ref['path']).parent)
    diagnostic={r['molecule_id']for r in pq.read_table(I.require(ref),columns=['molecule_id']).to_pylist()}
    C.need(len(diagnostic)==20000,'NO_GLOBAL20K_RESELECTION_OR_DOWNSIZE');return pre,members,diagnostic

def compute(work):
    import numpy as np
    from rdkit.Chem import rdMolDescriptors
    records,sprime,member,root=work;native=WORKER.SCIENCE;mid=member['molecule_id'];by={r['record_id']:r for r in records};observed={}
    C.need(len(by)==len(records)==member['S_conformers']==member['Sprime_conformers']==len(sprime),'ALL_ORIGINAL_NATIVE_AND_ORDINARY_N')
    anchors={r['source_record_id']for r in sprime};C.need(len(anchors)==1 and anchors<=set(by),'UNCHANGED_OLD_UFF_NATIVE_ANCHOR')
    anchor=next(iter(anchors));mol,z,_,raw=P.native_record_and_value(by[anchor],native);observed[anchor]=(mol,z,_,raw)
    signature=native.ordered_graph(mol);smiles=str(native.field(raw,'smiles'));atom_sha=hashlib.sha256(z.astype('<i8').tobytes()).hexdigest()
    for rid,pointer in by.items():
        if rid not in observed:observed[rid]=P.native_record_and_value(pointer,native)
        other,numbers,coords,_=observed[rid]
        C.need(np.array_equal(z,numbers) and signature==native.ordered_graph(other) and np.isfinite(coords).all(),'EXACT_NATIVE_PAYLOAD_GRAPH_ATOM_ORDER_AND_FINITE_F64_ALL_RECORDS')
    _,stereo=native.fix_stereo(mol,smiles);uff=P.checked_uff(sprime,z,mol,stereo,native);bases=[]
    common={'molecule_id':mid,'parent_geometry_id':None,'view_id':None,'atomic_numbers':z.tolist(),'atom_order_sha256':atom_sha,'order_energy':None}
    for rid,pointer in by.items():
        coords=observed[rid][2];bases.append(dict(common,geometry_source='pm7',geometry_id=gid('pm7',mid,rid),native_record_id=rid,sprime_conf_idx=None,
          positions_A=coords.tolist(),geometry_sha256=OLD.OriginalWorker.IO.geometry_sha(z,coords),source_path=pointer['source_path'],source_row_index=pointer['real_index'],
          source_format='native_lmdb',source_provenance_json=json.dumps(pointer,sort_keys=True),energy_source='HOF_NOT_CONSUMED_NATIVE_D4',actual_input_origin='ACTUAL_NATIVE_PAYLOAD_SHA_GRAPH_F64'))
    for value,row in zip(uff,sprime):
        ref=row['__source'];idx=row['sprime_conf_idx'];C.need(value['conformer_id']==idx,'ORIGINAL_UFF_PHYSICAL_ID_NO_RENUMBER')
        bases.append(dict(common,geometry_source='uff_sprime',geometry_id=gid('uff_sprime',mid,idx),native_record_id=None,sprime_conf_idx=idx,
          positions_A=value['coordinates'],geometry_sha256=value['geometry_sha256'],order_energy=float(row['uff_energy_kcal_mol']),source_path=ref['path'],source_bytes=ref['bytes'],source_sha256=ref['sha256'],
          source_row_index=row['__physical_row'],source_format='parquet',original_sprime_conf_idx=idx,source_conformer_id=idx,canonical_sprime_conf_idx=idx,
          identity_namespace='accepted_original_sprime',seed=row['seed'],native_anchor_record_id=anchor,energy_source='ACTUAL_UFF_KCAL_MOL_NOT_USED_FOR_SORTING',
          source_provenance_json=json.dumps({'source':ref,'physical_row':row['__physical_row']},sort_keys=True),actual_input_origin='ACTUAL_ORIGINAL_SPRIME_GRAPH_STEREO_F64'))
    orders=[]
    def no_distance(*args):raise AssertionError('NO_RMSD_ALLOWED_IN_PROVISIONAL_D4')
    for source in ('pm7','uff_sprime'):
        ids=[r['native_record_id']if source=='pm7'else r['sprime_conf_idx']for r in bases if r['geometry_source']==source]
        order=Cache.geometry_orders([{'conformer_id':key,'energy':None}for key in ids],no_distance,mid,source)['fixed_random']
        C.need(len(order)==len(ids)==len(set(order)),'COMPLETE_ORIGINAL_FIXED_RANDOM_PERMUTATION')
        orders.extend({'molecule_id':mid,'geometry_source':source,'order_type':'fixed_random','method':'fixed_random','rank':rank,'geometry_id':gid(source,mid,key)}for rank,key in enumerate(order))
    for row in bases:OLD.Geometry.physical_key(row)
    scaffold=OLD.OriginalMath.scaffold_chunk([(mid,smiles)])[0]
    features={'molecule_id':mid,'elements_atomic_numbers':sorted(set(z.tolist())),'heavy_atoms':int(np.count_nonzero(z!=1)),
      'rotatable_bonds':int(rdMolDescriptors.CalcNumRotatableBonds(__import__('rdkit.Chem',fromlist=['RemoveHs']).RemoveHs(mol))),
      'rings':int(mol.GetRingInfo().NumRings()),'generic_scaffold':scaffold['generic_scaffold'],'scaffold_status':scaffold['scaffold_status']}
    value={'schema':'PROVISIONAL55K_DIRECT_NATIVE_NO_CACHE_MOLECULE_V1','molecule_id':mid,'bases':bases,'orders':orders,'bias_features':features,
      'pm7_count':len(records),'uff_sprime_count':len(sprime),'new_QM_UFF_RMSD_HOF_calls':0,'three_orders_or_D7_complete':False}
    path=pathlib.Path(root)/(hashlib.sha256(mid.encode()).hexdigest()+'.lossless.json')
    with path.open('xb')as f:f.write(Wire.encode(value));f.flush();os.fsync(f.fileno())
    ref=I.pin(path);C.need(Wire.decode(path.read_bytes())==value,'ORIGINAL_COMPLETE_F64_NONE_MASK_NATIVE_PACKET_REOPEN')
    return {'reference':ref,'molecule_id':mid,'pid':os.getpid()}

def build(plan,proof,root,budget,prefix,old,oldproof,cohort):
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    root=pathlib.Path(root);root.mkdir();workers=root/'molecules';workers.mkdir();pre=I.load_data(prefix['preselection_reference'],8<<20)
    db=sqlite3.connect(root/'old_sprime.sqlite');db.execute('CREATE TABLE sprime(mid TEXT,idx INTEGER,row BLOB,PRIMARY KEY(mid,idx))')
    columns=['molecule_id','sprime_conf_idx','coordinates','atom_order_sha256','source_record_id','seed','status','converged','uff_energy_kcal_mol','stereo_signature']
    for ref in pre['old_Sprime_coordinate_source_references']:
        I.allow(ref,origin=pathlib.Path(ref['path']).parent);path=I.require(ref);before=I.S.identity(path);src=pq.ParquetFile(path);offset=0
        try:
            for batch in src.iter_batches(batch_size=256,columns=columns,use_threads=False):
                budget.check()
                for k,row in enumerate(batch.to_pylist()):
                    if row['molecule_id']not in cohort or row['status']!='SUCCESS'or row['converged']is not True:continue
                    C.need(type(row['sprime_conf_idx'])is int and row['sprime_conf_idx']>=0,'REAL_OLD_PHYSICAL_INT64_SPRIME_ID')
                    row.update(__source=ref,__physical_row=offset+k);db.execute('INSERT INTO sprime VALUES(?,?,?)',(row['molecule_id'],row['sprime_conf_idx'],Wire.encode(row)))
                offset+=batch.num_rows;db.commit()
        finally:src.close()
        C.need(I.S.identity(path)==before,'WHOLE_SHA_OLD_SPRIME_FD_FRAME_REMAINS_STABLE')
    native=duckdb.connect(prefix['native_catalog_reference']['path'],read_only=True)
    def work():
        for mid in sorted(cohort):
            budget.check();records=native.execute('SELECT * FROM native55k WHERE molecule_id=? ORDER BY record_id',[mid]).fetch_arrow_table().to_pylist()
            sprime=[Wire.decode(r[0])for r in db.execute('SELECT row FROM sprime WHERE mid=? ORDER BY idx',(mid,))]
            yield records,sprime,cohort[mid],str(workers)
    reports=[]
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=WORKER.initialize,initargs=({'proof':proof},))as pool:
            iterator=iter(work());pending={}
            while True:
                while len(pending)<16 and not I.stop_requested():
                    try:task=next(iterator)
                    except StopIteration:break
                    pending[pool.submit(compute,task)]=task[2]['molecule_id']
                if not pending:break
                done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    mid=pending.pop(future);report=future.result();C.need(report['molecule_id']==mid,'EXACT_NATIVE_WORKER_RETURN_MID');I.allow(report['reference']);reports.append(report)
    finally:db.close();native.close()
    C.need(len(reports)==55000 and len({r['molecule_id']for r in reports})==55000,'NO_PARTIAL_NATIVE_GEOMETRY_ACCEPTANCE')
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
                else:yield {'logical_ordinal':k,'molecule_id':v['molecule_id'],'PM7_N':v['pm7_count'],'UFF_N':v['uff_sprime_count'],'child_count':0}
        tables[kind]=I.write_parquet(root/(kind+'.parquet'),rows(),schemas[kind])
    feature_schema=pa.schema([('molecule_id',pa.string()),('elements_atomic_numbers',pa.list_(pa.int64())),
        ('heavy_atoms',pa.int64()),('rotatable_bonds',pa.int64()),('rings',pa.int64()),('generic_scaffold',pa.string()),('scaffold_status',pa.string())])
    features=I.write_parquet(root/'bias_features.parquet',(Wire.decode(I.require(r['reference']).read_bytes())['bias_features'] for r in sorted(reports,key=lambda r:r['molecule_id'])),feature_schema)
    return {'schema':'PROVISIONAL_NATIVE55K_FIXED_RANDOM_BASE_GEOMETRIES_V1','table_references':tables,'molecules':55000,
        'actual_parent_job_id':str(proof['job_id']),'bias_features_reference':features,'new_PM7_RMSD_recomputed':False,'new_QM_UFF_calls':0,
        'ordinary_base_N_preserved':True,'N1_second_UFF_not_created':True,'source_worker_report_references':[r['reference'] for r in reports],
        'D5_full_guide_nested_geometry_coverage':False,'available_orders':['fixed_random'],'full_three_order':False,'D7':False,'three_orders_or_D7_complete':False,'PM7_HOF_RMSD_cache_required':False,'final_Common':False}


def field_schema_rows(fields,registry):
    """Schema whitelist only; never copy observed_audit/counts/values/MID."""
    names=('field_key','registry_id','task','group','level','source_path','component','unit','source_unit','shape')
    by={r['field_key']:r for r in registry['fields']};ids=set();out=[]
    for field in sorted(fields,key=lambda r:r['field_id']):
        fid=field['field_id'];C.need(type(fid)is int and fid not in ids,'UNIQUE_ORIGINAL_FIELD_ID');ids.add(fid)
        source=by[field['field_key']]
        C.need(source['status']=='enabled' and all(field.get(k)==source.get(k)for k in names),'ACTUAL_FIELD_MAP_AND_REGISTRY_SCHEMA_UNITS_EXACT')
        value={'field_id':fid,**{k:source.get(k)for k in names},'layout':source.get('source_semantic_layout')}
        C.need(field.get('source_semantic_layout')==value['layout'],'EXACT_ORIGINAL_DECLARED_LAYOUT_NOT_REPAIRED');out.append(value)
    C.need(ids==set(range(146)),'EXACT146_FIELD_SCHEMA_NOT_A_TARGET_SUBSET');return out

def schema_header(plan,proof,root):
    fields=I.load_data(plan['field_map_reference'],2<<20);registry=I.load_data(plan['base_registry_reference'],16<<20)
    rows=field_schema_rows(fields,registry)
    return I.save(root/'field_schema_only_header.json',{'schema':'ACTUAL_CPU146_FIELD_SCHEMA_ONLY_QA_V1',
      'status':'ACTUAL_CPU_FIELD_SCHEMA_EXTRACTED_NOT_NATIVE_PRINTED_UNIT_VALIDATION','fields':rows,
      'actual_input_references':{'field_map':plan['field_map_reference'],'registry':plan['base_registry_reference'],'original_config':plan['original_coverage_config_reference']},
      'actual_parent_job_id':str(proof['job_id']),'actual_node':proof['request']['node'],'uid':1278,
      'native_printed_units_verified':False,'actual_parent_C0_claimed':False,'numerical_statistics_or_MID_or_coordinates_included':False,'final_release':False})

# This map is populated only by prepare's exact accepted-manifest/current-job
# proof chain and original I.allow registration. It is not a path discovery list.
ACCEPTED_CONFIG_REFERENCES={}
AUTHORITY_KEYS=('canonical_index','field_map_reference','source_inventory_reference','logical_group_plan_reference')

def normalize_config_authorities(value,plan):
    """A read-only view: alias only same positive bytes/SHA at another path."""
    result=dict(value)
    for key in AUTHORITY_KEYS:
        before=value[key];after=plan[key]
        C.need(type(before)is dict and type(after)is dict and set(before)==set(after)=={'path','bytes','sha256'},
            'EXACT_THREE_KEY_INHERITED_NUMERIC_AUTHORITY:'+key)
        C.reference(before);C.reference(after)
        C.need(type(before['bytes'])is int and before['bytes']>0 and type(after['bytes'])is int and after['bytes']>0,
            'POSITIVE_NUMERIC_AUTHORITY_BYTES:'+key)
        C.need(before['bytes']==after['bytes'] and before['sha256']==after['sha256'],
            'INHERITED_AUTHORITY_CONTENT_MISMATCH_HOLD:'+key)
        if before['path']!=after['path']:result[key]=dict(after)
        else:C.need(before==after,'UNCHANGED_SAME_PATH_AUTHORITY:'+key)
    return result

class AcceptedConfigIO:
    """Only admitted config load_data has an identity-preserving metadata view."""
    def __init__(self,plan,accepted,original):self.plan=plan;self.accepted=dict(accepted);self.original=original
    def __getattr__(self,name):return getattr(self.original,name)
    def load_data(self,reference,maximum=64<<20):
        raw=self.original.load_data(reference,maximum)
        key=reference.get('path') if type(reference)is dict else None
        if key not in self.accepted:return raw
        C.need(reference==self.accepted[key]==self.original.ALLOWED.get(key),'ONLY_EXACT_PREPARE_REGISTERED_CLOSED_PRODUCER_CONFIG')
        return normalize_config_authorities(raw,self.plan)

def coverage_function(plan,accepted):
    """Same old build code; only a private globals-copy I binding differs."""
    import types
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import coverage as original
    old=original.build;globals_copy=dict(old.__globals__);globals_copy['I']=AcceptedConfigIO(plan,accepted,I)
    function=types.FunctionType(old.__code__,globals_copy,old.__name__,old.__defaults__,old.__closure__)
    function.__kwdefaults__=old.__kwdefaults__
    return function

class CoverageAdapter:
    def build(self,plan,proof,root,budget,members):
        function=coverage_function(plan,ACCEPTED_CONFIG_REFERENCES)
        return function(plan,proof,root,budget,members)
    def __getattr__(self,name):
        from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import coverage as original
        return getattr(original,name)
COVERAGE=CoverageAdapter()

# NATIVE_RESOURCE_CENSUS_R5: private resource IO only; old scientific globals stay untouched.
def retry_whole_census(original,root,record):
    """At most three complete original inventories; never treat missing as zero."""
    import traceback
    for attempt in range(1,4):
        try:
            value=original(root)
            if attempt>1:record({'status':'WHOLE_ORIGINAL_CENSUS_SUCCEEDED','attempt':attempt,'bytes':value})
            return value
        except FileNotFoundError as exc:
            record({'status':'WHOLE_ORIGINAL_CENSUS_FILE_NOT_FOUND','attempt':attempt,
                'path':str(root),'missing_filename':exc.filename,'error':repr(exc),'traceback':traceback.format_exc(),
                'missing_bytes_assumed_zero':False,'maximum_complete_attempts':3})
            if attempt==3:raise

class ResourceStopEvidence:
    """Keep original STOP behavior, adding the actual active exception context."""
    def __init__(self,original):self.original=original
    def __getattr__(self,name):return getattr(self.original,name)
    def mark_stop(self,reason,observation):
        import sys,traceback
        error=sys.exc_info()[1]
        if reason=='COMMON_TRAIN_RESOURCE_OBSERVATION_UNKNOWN' and error is not None:
            observation=dict(observation,actual_exception_type=type(error).__name__,missing_filename=getattr(error,'filename',None),
                traceback=traceback.format_exc(),historical177_cause_inferred=False)
        return self.original.mark_stop(reason,observation)

def budget_function(name,census):
    """Exact old method code/defaults/closure; two explicit private IO bindings."""
    import types
    old=getattr(I.Budget,name);globals_copy=dict(old.__globals__);globals_copy['unique_bytes']=census
    if name=='_observe':globals_copy['R']=ResourceStopEvidence(old.__globals__['R'])
    result=types.FunctionType(old.__code__,globals_copy,old.__name__,old.__defaults__,old.__closure__)
    result.__kwdefaults__=old.__kwdefaults__;return result

class ResourceBudget(I.Budget):
    """Original budget, quota, immutable refs and thresholds; bounded recensus only."""
    def __init__(self,plan,proof,root):
        import threading
        self.census_lock=threading.RLock();self.census_sequence=0
        def census(path):
            C.need(pathlib.Path(path)==self.root,'ONLY_ACTUAL_CURRENT_PARENT_OUTPUT_CENSUS')
            with self.census_lock:return retry_whole_census(I.unique_bytes,path,self.record_census)
        self.native_census=census
        self.native_observe=budget_function('_observe',census);self.native_check=budget_function('check',census)
        super().__init__(plan,proof,root)
    def record_census(self,event):
        # This bounded metadata writer must not recursively invoke the inventory
        # it is documenting. Max128*64KiB fits the existing64MiB admin reserve.
        import stat
        self.census_sequence+=1;C.need(self.census_sequence<=128,'BOUNDED_RESOURCE_CENSUS_EVENTS_EXHAUSTED_STOP')
        directory=self.root/'resource_census_events';directory.mkdir(exist_ok=True)
        frame=directory.lstat();C.need(stat.S_ISDIR(frame.st_mode) and frame.st_uid==1278,'OWN_CURRENT_RESOURCE_EVENT_DIRECTORY')
        value={'schema':'NATIVE_PARENT_COMPLETE_RESOURCE_CENSUS_EVENT_V1','scientific_adoption':False,
            'observed_unix_seconds':I.time.time(),**event}
        raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode();C.need(len(raw)<=64<<10,'BOUNDED_RESOURCE_CENSUS_EVENT')
        path=directory/('event_%06d.json'%self.census_sequence)
        with path.open('xb') as stream:C.need(stream.write(raw)==len(raw),'WHOLE_RESOURCE_EVENT_WRITE');stream.flush();os.fsync(stream.fileno())
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        I.allow(I.pin(path))
    def _observe(self):return self.native_observe(self)
    def check(self,*,force=False,dispatch=True):return self.native_check(self,force=force,dispatch=dispatch)
