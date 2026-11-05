"""Original extraction/mask objects; bounded canonical-row and typed-reader IO."""
import copy,hashlib,json,os,pathlib
from . import contract as C,io as I,domain as D,projection as P
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import reader as R,bindings as B,io as BI
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
from workflows.data_v1_final.export.family_export_day_v1 import transport as T
L=C.F.legacy();S=L['pipeline_v1.source'];MASK=L['pipeline_v1.masks'];CTX=None
def initialize(context):
    global CTX
    CTX=context;C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==context['job_id'] and os.uname().nodename==context['node'],'SAME_REAL_CPU16_PARENT_WORKER')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    I.configure(context['plan'],context['old_plan'])
    for ref in context['registered_references']:BI.ALLOWED[ref['path']]=ref
    BI.ORIGINS.update(context['reader_origins'])
def task_name(code):return next(k for k,v in B.TASKS.items() if v==code)
class RawRows:
    """Ordered sparse row access; producer SHA is provenance, not a new full scan."""
    def __init__(self,ref,expected_rows):
        import pyarrow.parquet as pq
        self.ref=C.reference(ref);self.path=pathlib.Path(ref['path']);self.frame=I.identity(self.path)
        C.need(self.frame[2]==ref['bytes'] and not any(p.is_symlink() for p in (self.path,*self.path.parents)),'RAW_FIXED_SOURCE_SIZE_NO_SYMLINK')
        self.stream=os.fdopen(os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW),'rb');st=os.fstat(self.stream.fileno())
        C.need(st.st_uid==1278 and st.st_nlink==1 and [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==self.frame,'ORIGINAL_RAW_SOURCE_EXACT_CURRENT_FD_OWNER_FRAME')
        self.pq=pq.ParquetFile(self.stream,pre_buffer=False);C.need(self.pq.metadata.num_rows==expected_rows,'INHERITED_REAL_SOURCE_FOOTER_ROWS')
        self.iterator=self.pq.iter_batches(batch_size=1,use_threads=False);self.offset=-1;self.row=None
    def get(self,index):
        C.need(type(index) is int and index>self.offset,'ORIGINAL_RAW_PHYSICAL_ROW_FORWARD_ONLY')
        while self.offset<index:
            batch=next(self.iterator);C.need(batch.nbytes<=128<<20,'UNTRUNCATED_RAW_ROW_SOFTWARE_BOUND');self.row=batch.to_pylist()[0];self.offset+=1
        return self.row
    def close(self):
        st=os.fstat(self.stream.fileno());C.need([st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==self.frame==I.identity(self.path),'SOURCE_PRODUCER_LOCATOR_CURRENT_FD_FRAME_STABLE_NOT_NEW_WHOLESHA')
        self.pq.close();self.stream.close()
def target_row(entries,compact,recipe,raw,n):
    if recipe['input_kind']=='ORIGINAL_REGISTRY_CELL_PARQUET':
        C.need(recipe.get('projection_adapter')=='ORIGINAL_COMPONENT_READER_EXPLICIT_PAIR_AND_NULL_IO_V1',
          'RAW_P_RECIPE_REQUIRES_EXPLICIT_LOSSLESS_PAIR_NULL_PROJECTION')
        row,spec,_=P.prepare(entries,compact,recipe,raw,n);return row,spec
    C.need(recipe['input_kind']=='ORIGINAL_TYPED_FIELD_ENTRIES' and all(e['field']['group']=='D' for e in entries),'NO_TYPED_RECONSTRUCTION_OF_ORDERED_R73_CHANNELS_OR_PAIR_LAYOUT')
    import numpy as np
    virtual={}
    for e in entries:
        selector=recipe['components'][e['field_key']];C.need(selector['value']=={'column':'field_'+str(e['field_id'])}
          and selector.get('reshape') is True,'EXPLICIT_TYPED_FLAT_F64_SELECTOR_NOT_GUESSED_RAW_LAYOUT')
        values=e['values_float64'];C.need(all(v is not None or not m for v,m in zip(values,e['value_mask'])),'NONE_NEVER_BECOMES_VALID_NUMERIC_VALUE')
        virtual['field_'+str(e['field_id'])]=[np.nan if v is None else v for v in values]
        if e['atom_indices'] is not None:virtual['indices_'+str(e['field_id'])]=e['atom_indices']
    return virtual,recipe
def extract(entries,typed,raw,n,recipe,target):
    if recipe['input_kind']=='ORIGINAL_REGISTRY_CELL_PARQUET':return P.projected_target(entries,typed,recipe,raw,n,target)
    compact=K.binary_json_loads(typed['compact_mask_json']);row,spec=target_row(entries,compact,recipe,raw,n);note={}
    arrays=T.target_arrays(row,spec,target,n,compact_loader=lambda cs:compact,annotations=note)
    return arrays,note
def one(work):
    key,group,out=work;cfg=CTX['reader_config'];fields=CTX['field_map'];compiled=CTX['compiled'];recipe=CTX['recipe'];counter=0;parts=0;raws={}
    db=I.connect(CTX['domain_database'],True);bind=I.connect(CTX['binding_database'],True);catalog=I.connect(CTX['coverage_catalog'],True);stage=I.connect(out)
    stage.execute('CREATE TABLE pieces(gid TEXT,part TEXT,n INTEGER,payload BLOB,source_locator TEXT,PRIMARY KEY(gid,part))')
    from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import core as W
    try:
        for owner,z,entries,typed,source in R.records(cfg,group,fields):
            I.F.worker_check(CTX['control']);counter+=1;task=task_name(typed['task_code']);tr=recipe['tasks'][task]
            if tr['geometry_binding']=='ACTUAL_WP5_PROGRAM_INPUT_DOUBLE_HASH':
                hit=bind.execute('SELECT gid,unknown,source,physical_row FROM bindings WHERE rid=? AND task=?',(owner['record_id'],task)).fetchone()
                C.need(hit is not None and hit['unknown']==0 and json.loads(hit['source'])==C.reference(source) and hit['physical_row']==typed['physical_row'],'EXACT_CLOSED_PILOT_CALL_OCCURRENCE')
                gid=hit['gid']
            else:
                C.need(tr['geometry_binding']=='ORIGINAL_NATIVE_PAYLOAD_PM7_BASE' and all(e['field']['group']=='D' for e in entries),'EXPLICIT_D_NATIVE_PAYLOAD_BINDING_NOT_TASK_NAME_VIEW')
                # Lossless core is a binary tree, not JSON-queryable. Exact rid
                # lookup comes from the separate CPU-built native index.
                hit=db.execute('SELECT gid FROM native_bases WHERE rid=?',(owner['record_id'],)).fetchone();C.need(hit is not None,'ACTUAL_NATIVE_RECORD_BASE_INDEX');gid=hit['gid']
            g=db.execute('SELECT row,selected FROM geometries WHERE gid=?',(gid,)).fetchone();C.need(g is not None,'ACTUAL_GID_NOT_DERIVED_FROM_TASK')
            if not g['selected']:continue
            geometry=W.decode(g['row']);C.need(geometry['molecule_id']==owner['molecule_id'] and geometry['atomic_numbers']==z,'CANONICAL_OWNER_NATIVE_ATOM_ORDER_AND_ACTUAL_GEOMETRY')
            raw=None
            if tr['input_kind']=='ORIGINAL_REGISTRY_CELL_PARQUET':
                path=source['path']
                if path not in raws:raws[path]=RawRows(source,source['rows'])
                raw=raws[path].get(typed['physical_row']);C.need(raw['record_id']==owner['record_id'] and raw['molecule_id']==owner['molecule_id'] and raw['calc_type']==task,'ACTUAL_RAW_SOURCE_ROW_TYPED_CANONICAL_OWNER')
                C.need(raw['input_bundle_sha256']==geometry['actual_input_bundle_sha256'] and raw['input_file_sha256']==json.loads(geometry['source_provenance_json'])['original_input_file_sha256'],'RAW_PROGRAM_INPUT_BUNDLE_AND_FILE_DOUBLE_HASH')
            compact=K.binary_json_loads(typed['compact_mask_json'])
            bykey={e['field_key']:e for e in entries}
            partrows=catalog.execute("SELECT ref,lo,hi FROM parts WHERE file=? AND kind='task' AND task=? AND lo<=? AND hi>?",(typed['file_id'],typed['task_code'],typed['physical_row'],typed['physical_row'])).fetchall()
            C.need(len(partrows)==1,'EXACT_CLOSED_TYPED_PART_LOCATOR');typed_part=json.loads(partrows[0][0])
            for tid in tr['targets']:
                target=compiled['ordered_record_targets'].get(tid) or compiled['physical_targets'][tid]
                C.need(target['condition']!='Pprime' and target['geometry_source']==geometry['geometry_source'] and all(m['field_key'] in bykey for m in target['members']),'ALL_TARGET_MEMBERS_IN_ONE_ACTUAL_TASK_CELL')
                arrays,note=extract(entries,typed,raw,len(z),tr,target);spec=tr
                # Exact original typed bits/masks versus original raw extraction
                # are checked, not treated as the same merely by field names.
                for m in target['members']:
                    e=bykey[m['field_key']];cs=spec['components'][m['field_key']]['compact'];C.need(cs['field_id']==e['field_id'],'ORIGINAL_FIELD_IDS_NO_REASSIGNMENT')
                locator={'source_reference':C.reference(source),'physical_row':typed['physical_row'],'row_group':typed['row_group'],'row_within_group':typed['row_within_group'],
                  'record_id':owner['record_id'],'molecule_id':owner['molecule_id'],'task':task,'record_ordinal':owner['record_ordinal'],
                  'typed_part_view_sha256':typed['view_sha256'].hex(),'geometry_sha256':geometry['geometry_sha256'],'atom_order_sha256':geometry['atom_order_sha256'],
                  'actual_input_bundle_sha256':geometry.get('actual_input_bundle_sha256'),'actual_input_file_sha256':json.loads(geometry['source_provenance_json']).get('original_input_file_sha256'),
                  'member_geometry_ids':[gid]*len(target['members']),'actual_task_charge':tr['actual_task_charge'],'actual_charge_authority_reference':tr['actual_charge_authority_reference'],
                  'typed_part_reference':typed_part,'typed_window_lo':partrows[0]['lo'],'typed_window_hi':partrows[0]['hi'],'source_file_id':typed['file_id'],'source_rows':source['rows'],
                  'typed_missing_positions':{e['field_key']:[i for i,v in enumerate(e['values_float64']) if v is None] for e in entries if any(v is None for v in e['values_float64'])},
                  'source_producer_SHA_inherited_not_rehashed':True,'group_key':str(owner['job_id'])}
                stage.execute('INSERT INTO pieces VALUES(?,?,?,?,?)',(gid,tid,len(z),S.pack(arrays,note),json.dumps(locator,sort_keys=True)));parts+=1
            if counter%128==0:stage.commit();I.F.worker_check(CTX['control'])
        stage.commit()
    finally:
        for source in raws.values():source.close()
        stage.close();bind.close();catalog.close();db.close()
    ref=I.pin(out);return {'key':key,'reference':ref,'source_rows':counter,'pieces':parts,'pid':os.getpid(),'new_QM_UFF_calls':0,'all_handles_closed':True}
