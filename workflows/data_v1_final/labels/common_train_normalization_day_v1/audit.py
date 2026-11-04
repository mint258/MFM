"""One original-Parquet pass: unchanged raw evaluator, all-population guide1.5."""
import collections,hashlib,heapq,json,math,os,sqlite3,struct,time
from pathlib import Path
from . import contract as C,io as I,bindings as B,reader as R
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity,lookup_batch,sqlite_ro

WORK={}

def day_group(item):
    cfg,item=item
    initialize(cfg)
    return group(item)

def initialize(cfg):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);I.configure(cfg)
    common,masks=B.legacy(cfg['science']);registry=I.load_data(cfg['science']['sources']['registry'],2<<20)
    enabled=sorted((f for f in registry['fields'] if f['status']=='enabled'),key=lambda f:f['field_key'])
    C.need(len(registry['fields'])==264 and len(enabled)==146,'ORIGINAL264_AND146_FIELD_ID_ASSIGNMENT')
    ids={f['field_key']:i for i,f in enumerate(enabled)};fields=[dict(f,field_id=ids.get(f['field_key'])) for f in registry['fields']]
    field_map=I.load_data(cfg['field_map_reference'],2<<20)
    C.need([f['field_key'] for f in enabled]==[f['field_key'] for f in field_map],'ORIGINAL_REGISTRY_SORTED_FIELD_MAP')
    WORK.update(cfg=cfg,common=common,masks=masks,fields=field_map,
      task_fields={task:[f for f in fields if f['task']==task] for task in B.TASKS},
      calibration=I.load_data(cfg['diagnostic_median_MAD_reference'])['fields'],
      sources={s['path']:s for s in I.load_data(cfg['source_inventory_reference'],2<<20)['files']})

def exact_cache_parity(items,cached):
    """IEEE bits/None/owned indices/reasons/masks; never allclose or print tolerance."""
    a=K.pack_entries(sorted(items,key=lambda e:e['field_id']));b=K.pack_entries(sorted(cached,key=lambda e:e['field_id']))
    C.need(a==b,'RAW_ORIGINAL_EVALUATOR_VS_TYPED_CACHE_EXACT_VALUES_INDICES_MASKS_REASONS_CHANGED')
    return hashlib.sha256(K.canonical({k:(v.hex() if type(v)is bytes else v) for k,v in a.items()})).hexdigest()

def save_worst(path,value):
    # Review-score overflow is retained as original IEEE bits, never clipped/floored.
    return I.save(path,{'schema':'COMMON_TRAIN_WORST20_TYPED_F64_DATA_V1','typed_binary_json':K.binary_json_dumps(value)})

def load_worst(reference):
    obj=I.load_data(reference,128<<20);C.need(obj['schema']=='COMMON_TRAIN_WORST20_TYPED_F64_DATA_V1','EXACT_TYPED_WORST20_DATA')
    return K.binary_json_loads(obj['typed_binary_json'])

def quality_fields(stats,denominator=None,active_field_ids=None):
    holds=set();active=None if active_field_ids is None else set(active_field_ids)
    for fid,c in stats.items():
        if active is not None and int(fid) not in active:continue
        n=c.get('records',denominator);C.need(type(n)is int and n>=0,'ACTUAL_THIS_FIELD_ORIGINAL_TASK_SCOPE_DENOMINATOR')
        holds.update(B.quality_stop_fields({fid:c},n,.01))
        if n and c.get('masked_records_any_leaf',n-c['final_valid_records'])/n>.01:holds.add(fid)
    return sorted(holds)

def worst_add(worst,field,item,owner,score):
    """Original scan_v2 severity and (severity, ordinal) top20 ordering."""
    for reason in set(item['source_reasons']+item['new_reasons']+item['review_reasons']):
        severity=score if score is not None and reason in {'ROBUST_Z_GT20_REVIEW_ONLY','ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY'} else 1.0
        basis='robust_z_or_zero_MAD_absolute_deviation' if severity==score and score is not None else 'binary_evidence_issue_equal_severity_then_ordinal'
        if reason=='PHYSICAL_DEFINITION_RANGE':
            bounds=field['physical_range'];distance=[]
            for value in item['values_float64']:
                if value is None or not math.isfinite(value):continue
                if bounds['lower'] is not None and value<bounds['lower']:distance.append(bounds['lower']-value)
                if bounds['upper'] is not None and value>bounds['upper']:distance.append(value-bounds['upper'])
            severity=max(distance,default=0.0);basis='distance_outside_definition_bound_in_field_units'
        if reason=='NEUTRAL_ATOMIC_CHARGE_SUM_OUTSIDE_SOURCE_ROUNDING_TOLERANCE':
            severity=abs(math.fsum(v for v in item['values_float64'] if v is not None and math.isfinite(v)));basis='absolute_neutral_charge_sum_e'
        record=B.worst_preview(item,owner,reason,severity,32);record.update(score_reason=reason,score_basis=basis)
        entry=(severity,int(owner['record_ordinal']),record);heap=worst[(field['field_id'],reason)]
        if len(heap)<20:heapq.heappush(heap,entry)
        elif entry[:2]>heap[0][:2]:heapq.heapreplace(heap,entry)

class Sink:
    """Bounded per-part writer; all selected rows survive without preview truncation."""
    def __init__(self,root,name,schema):
        self.root=Path(root);self.name=name;self.schema=schema;self.part=0;self.rows=0;self.stream=None;self.writer=None;self.refs=[];self.part_rows=0;self.digest=hashlib.sha256()
    def add(self,rows):
        import pyarrow as pa,pyarrow.parquet as pq
        if not rows:return
        table=pa.Table.from_pylist(rows,schema=self.schema);C.need(table.nbytes<=64<<20,'FINITE_AUDIT_BATCH_NOT_TRUNCATION')
        if self.writer is None:
            self.path=self.root/(self.name+'_%06d.parquet'%self.part);self.stream=self.path.open('xb');self.writer=pq.ParquetWriter(self.stream,self.schema,compression='zstd')
        self.writer.write_table(table,row_group_size=128);self.rows+=len(rows);self.part_rows+=len(rows)
        for row in rows:self.digest.update(K.binary_json_dumps(row).encode())
        if self.stream.tell()>=64<<20:self.close_part()
    def close_part(self):
        if self.writer is None:return
        self.writer.close();self.stream.flush();os.fsync(self.stream.fileno());self.stream.close();self.writer=self.stream=None
        ref=I.pin(self.path);I.ALLOWED[ref['path']]=ref
        import pyarrow.parquet as pq
        p=I.require(ref);before=identity(p);handle=pq.ParquetFile(p,pre_buffer=False);observed=hashlib.sha256();n=0
        try:
            for batch in handle.iter_batches(batch_size=128,use_threads=False):
                for row in batch.to_pylist():observed.update(K.binary_json_dumps(row).encode());n+=1
        finally:handle.close()
        C.need(before==identity(p) and n==self.part_rows and observed.digest()==self.digest.digest(),'AUDIT_OUTPUT_REOPEN_EXACT_TYPED_BITS_MASKS_IDS_AND_ROW_MASS')
        self.refs.append(dict(ref,rows=n,typed_stream_sha256=observed.hexdigest()));self.part+=1;self.part_rows=0;self.digest=hashlib.sha256()
        C.need(I.unique_bytes(I.ROOT)+(64<<20)<=I.CAP,'AUDIT_PART_WHOLE_OUTPUT_CAP')
    def finish(self):self.close_part();return self.refs

def group(group):
    import pyarrow as pa,pyarrow.parquet as pq
    cfg=WORK['cfg'];C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_AUDIT_BEFORE_GROUP')
    root=Path(cfg['audit_root'])/('group_%04d'%group['group_index']);root.mkdir();start=time.monotonic()
    fields=WORK['fields'];byid={f['field_id']:f for f in fields};counts=collections.defaultdict(collections.Counter)
    raw_counts=collections.Counter();unknown=collections.Counter();roles=collections.Counter();worst=collections.defaultdict(list);opened=closed=processed=0
    cache=iter(R.records(cfg,group,fields));current=next(cache,None);index=sqlite_ro(cfg['canonical_index']['path'])
    extrema=sqlite3.connect(root/'scalar_extrema.sqlite');extrema.execute('PRAGMA journal_mode=OFF');extrema.execute('PRAGMA cache_size=-8192')
    extrema.execute('CREATE TABLE extrema(fid INTEGER,mid TEXT,min_abs REAL,max_abs REAL,min_ord INTEGER,max_ord INTEGER,signs INTEGER,n INTEGER,PRIMARY KEY(fid,mid)) WITHOUT ROWID')
    masks=Sink(root,'full_population_masks',B.compact.arrow_schema())
    auditschema=pa.schema([('record_ordinal',pa.uint64()),('task_code',pa.uint8()),('source_reference_json',pa.large_string()),('physical_row',pa.uint64()),
      ('cache_view_sha256',pa.binary(32)),('raw_cache_exact_numeric_mask_sha256',pa.string()),('original_status',pa.string()),('raw_output_locator_json',pa.large_string()),
      ('input_file_sha256',pa.string()),('reproduction_package_sha256',pa.string())])
    audits=Sink(root,'typed_one_percent_source_locators',auditschema);maskbuf=[];auditbuf=[]
    try:
        for reference in group['label_files']:
            source=WORK['sources'][reference['path']]
            p=I.require(source,content=False);before=identity(p);stream=p.open('rb');s=os.fstat(stream.fileno());h=hashlib.sha256()
            try:
                C.need(before==[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns],'RAW_CURRENT_OPEN_FD_FRAME')
                for b in iter(lambda:stream.read(1<<20),b''):h.update(b)
                C.need(h.hexdigest()==source['sha256'],'RAW_FULL_ORIGINAL_PARQUET_SAME_FD_SHA');stream.seek(0)
                handle=pq.ParquetFile(stream,pre_buffer=False);opened+=1;physical=0
                try:
                    for batch in handle.iter_batches(batch_size=128,columns=B.source_columns(source['family']),use_threads=False):
                        C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_AUDIT_INCOMPLETE_GROUP_NO_ACCEPTANCE')
                        rows=batch.to_pylist();owners=lookup_batch(index,[r['record_id'] for r in rows])
                        for row in rows:
                            pos=physical;physical+=1;owner=owners.get(row['record_id'])
                            if B.classify_owner(row,owner,source['family'] not in ('D20','D3'))!='CANONICAL':continue
                            C.need(current is not None,'RAW_CANONICAL_ROW_WITHOUT_CACHE')
                            bound,numbers,cached,wire,wire_source=current
                            C.need(wire_source['path']==source['path'] and wire['physical_row']==pos and owner['record_ordinal']==wire['record_ordinal']
                              and K.owner_signature(owner)==wire['owner_sha256'],'RAW_CACHE_FILE_PHYSICAL_FIVE_KEY_OWNER_BINDING')
                            owner=bound;task=row.get('calc_type',source['family']);row['calc_type']=task;row['total_atoms']=owner['total_atoms']
                            items,observations,structural,raw,scores=B.evaluate(row,source['family'],WORK['task_fields'][task],WORK['common'],WORK['masks'],B.pair_keys,{})
                            digest=exact_cache_parity(items,cached);raw_counts.update(raw);obs={o['field_key']:o for o in observations}
                            processed+=1;roles[owner['effective_role']]+=1
                            for item in items:
                                fid=item['field_id'];field=byid[fid];score=B.reference_review(item,WORK['calibration']);c=counts[str(fid)]
                                c['records']+=1;c['source_valid_records']+=int(any(item['source_value_mask']));c['final_valid_records']+=int(any(item['value_mask']))
                                c['source_numeric_leaf_slots']+=len(item['values_float64']);c['source_eligible_leaves']+=sum(item['source_value_mask']);c['final_eligible_leaves']+=sum(item['value_mask'])
                                c['source_masked_records_any_leaf']+=int(not item['source_value_mask'] or not all(item['source_value_mask']))
                                c['masked_records_any_leaf']+=int(not item['value_mask'] or not all(item['value_mask']))
                                c['source_masked_leaves']+=len(item['source_value_mask'])-sum(item['source_value_mask'])
                                c['final_masked_leaves']+=len(item['value_mask'])-sum(item['value_mask'])
                                c['newly_masked_records']+=int(any(a and not b for a,b in zip(item['source_value_mask'],item['value_mask'])))
                                c['newly_masked_leaves']+=sum(a and not b for a,b in zip(item['source_value_mask'],item['value_mask']))
                                c['new_payload_structural_invalid_records']+=int(obs[item['field_key']]['payload_structural_failure'])
                                c['review_records']+=int(bool(item['review_reasons'] or item.get('structural_review')))
                                c['Common_TRAIN_fit_records']+=int(owner['fit_eligible'])
                                for kind in ('source','new','review'):
                                    for reason in set(item[kind+'_reasons']):c[kind+'_reason:'+reason]+=1
                                valid=[v for v,keep in zip(item['values_float64'],item['value_mask']) if keep]
                                c['Common_TRAIN_valid_leaves']+=len(valid) if owner['fit_eligible'] else 0
                                worst_add(worst,field,item,owner,score)
                                if field['level']=='molecule' and len(valid)==1 and valid[0]!=0:
                                    v=valid[0];a=abs(v);ordinal=owner['record_ordinal'];sign=1 if v>0 else 2
                                    extrema.execute('INSERT INTO extrema VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(fid,mid) DO UPDATE SET min_ord=CASE WHEN excluded.min_abs<min_abs THEN excluded.min_ord ELSE min_ord END,max_ord=CASE WHEN excluded.max_abs>max_abs THEN excluded.max_ord ELSE max_ord END,min_abs=min(min_abs,excluded.min_abs),max_abs=max(max_abs,excluded.max_abs),signs=signs|excluded.signs,n=n+1',
                                      (fid,owner['molecule_id'],a,a,ordinal,ordinal,sign))
                                if field['level'] in ('molecule_vector','molecule_tensor','atom_vector'):
                                    unknown['SOURCE_PROPERTY_UNIT_SIGN_BASIS_AXES_NOT_JOINT_RELEASED:'+str(fid)]+=1
                                if field['registry_id'] in (52,196,265,332,399,669):unknown['INDEPENDENT_DIPOLE_NORM_NOT_STORED:'+str(fid)]+=1
                                if row.get('converged') is None and source['family'] not in ('D20','D3'):unknown['CONVERGENCE_EVIDENCE_UNKNOWN:'+str(fid)]+=1
                            maskbuf.append(B.compact.encode(owner['record_ordinal'],B.TASKS[task],items))
                            selected=int.from_bytes(hashlib.sha256((str(cfg['raw_source_audit_seed'])+'|'+owner['record_id']).encode()).digest()[:8],'little')%10000<cfg['raw_source_audit_basis_points']
                            if selected:
                                if row.get('raw_output_locator_json') is None:unknown['SELECTED_TYPED_AUDIT_NATIVE_RAW_LOCATOR_ABSENT:'+task]+=1
                                auditbuf.append({'record_ordinal':owner['record_ordinal'],'task_code':B.TASKS[task],'source_reference_json':K.canonical(C.reference(source)).decode(),
                                  'physical_row':pos,'cache_view_sha256':wire['view_sha256'],'raw_cache_exact_numeric_mask_sha256':digest,'original_status':row['status'],
                                  'raw_output_locator_json':row.get('raw_output_locator_json'),'input_file_sha256':row.get('input_file_sha256'),'reproduction_package_sha256':row.get('reproduction_package_sha256')})
                            if len(maskbuf)>=128:masks.add(maskbuf);maskbuf=[]
                            if len(auditbuf)>=128:audits.add(auditbuf);auditbuf=[]
                            current=next(cache,None)
                        I.R.soft_worker_rss(cfg['worker_rss_stop_bytes'])
                        C.need(I.unique_bytes(root)<cfg['audit_group_cap_bytes'],'FINITE_COMPLETE_AUDIT_GROUP_CAP_NO_PREVIEW_TRUNCATION')
                    C.need(physical==source['rows'],'RAW_FULL_PHYSICAL_ROW_COUNT')
                finally:handle.close();closed+=1
                t=os.fstat(stream.fileno());C.need(before==[t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns]==identity(p),'RAW_SAME_FD_AFTER_FULL_READ_STABLE')
            finally:stream.close()
        C.need(current is None,'CACHE_ROW_WITHOUT_ORIGINAL_CANONICAL_RAW_ROW')
        expected=index.execute('SELECT count(*) FROM records WHERE job_id=?',(group['source_job_id'],)).fetchone()[0]
        C.need(processed==expected*14 and len(counts)==146 and all(s['records']==expected for s in counts.values()),'ALL_POPULATION146_FIELD_14TASK_MASS')
        masks.add(maskbuf);audits.add(auditbuf);maskrefs=masks.finish();auditrefs=audits.finish();extrema.commit()
        jump_schema=pa.schema([('field_id',pa.uint16()),('molecule_id',pa.string()),('min_abs',pa.float64()),('max_abs',pa.float64()),
          ('min_record_ordinal',pa.uint64()),('max_record_ordinal',pa.uint64()),('factor',pa.float64()),('reason',pa.string())])
        jumps=Sink(root,'within_molecule_jump_reviews',jump_schema);batch=[]
        for fid,mid,a,b,lo,hi,signs,n in extrema.execute('SELECT * FROM extrema ORDER BY fid,mid'):
            if n>=2 and signs in (1,2) and b/a>1000:
                batch.append({'field_id':fid,'molecule_id':mid,'min_abs':a,'max_abs':b,'min_record_ordinal':lo,'max_record_ordinal':hi,'factor':b/a,'reason':'WITHIN_MOLECULE_JUMP_REVIEW_ONLY'})
                if len(batch)>=128:jumps.add(batch);batch=[]
        jumps.add(batch);jumprefs=jumps.finish()
        detail=save_worst(root/'worst20_per_field_reason.json',{'top20_by_field_reason':{str(fid)+'|'+reason:[x[2] for x in sorted(heap,reverse=True)] for (fid,reason),heap in worst.items()}})
        report={'schema':'COMMON_TRAIN_ALL_POPULATION_AUDIT_GROUP_V1','status':'COMPLETE_RAW_CACHE_EXACT_PARITY_AND_ORIGINAL_RULES',
          'group_index':group['group_index'],'source_job_id':group['source_job_id'],'records':expected,'task_rows':processed,'field_counts':{k:dict(v) for k,v in counts.items()},
          'role_task_counts':dict(roles),'raw_payload_counts':dict(raw_counts),'physical_QA_UNKNOWN_counts':dict(unknown),'masks':maskrefs,
          'typed_one_percent_audit_source_locator_parts':auditrefs,'one_percent_selected_task_rows':audits.rows,'within_molecule_jump_parts':jumprefs,
          'worst20_reference':detail,'opens':opened,'closes':closed,'whole_raw_sources_SHA_current_FD_verified':True,'elapsed_seconds':time.monotonic()-start,
          'original_values_and_masks_modified':False,'independent_dipole_norm_claimed':False,'physical_QA_UNKNOWN_not_numeric_failure_or_acceptance':True}
        return I.save(root/'report.json',report)
    finally:
        cache.close();index.close();extrema.close()
        if masks.writer is not None:masks.close_part()
        if audits.writer is not None:audits.close_part()

def reduce(references,root,fields,field_scope,expected_field_stats):
    reports=[I.load_data(r,16<<20) for r in references];C.need([r['group_index'] for r in reports]==list(range(171)),'ALL_ORIGINAL171_AUDIT_GROUPS_ORDERED')
    counts=collections.defaultdict(collections.Counter);unknown=collections.Counter();role=collections.Counter();worst=collections.defaultdict(list)
    for row in reports:
        C.need(row['status']=='COMPLETE_RAW_CACHE_EXACT_PARITY_AND_ORIGINAL_RULES' and row['opens']==row['closes'],'CLOSED_AUDIT_HANDLES_AND_COMPLETE_GROUP')
        for fid,c in row['field_counts'].items():counts[fid].update(c)
        unknown.update(row['physical_QA_UNKNOWN_counts']);role.update(row['role_task_counts'])
        detail=load_worst(row['worst20_reference'])
        for key,items in detail['top20_by_field_reason'].items():
            heap=worst[key]
            for record in items:
                item=(record['score'],record['record_ordinal'],record)
                if len(heap)<20:heapq.heappush(heap,item)
                elif item[:2]>heap[0][:2]:heapq.heapreplace(heap,item)
    C.need(len(counts)==146 and all(c['records']==expected_field_stats[fid]['records'] for fid,c in counts.items())
      and sum(role.values())==157245956,'FULL_THIS_FIELD_ORIGINAL_APPLICABLE_TASK_DENOMINATOR_NOT_ALL_TASKS_OR_COMMON')
    holds=quality_fields(counts,active_field_ids=field_scope['active_field_ids'])
    final={fid:{**dict(c),'scope_records':c['records'],'applicable_to_released_exposure_scope':int(fid) in field_scope['active_field_ids'],
      'new_mask_fraction':c['newly_masked_records']/c['records'],'source_invalid_record_fraction':c['source_masked_records_any_leaf']/c['records'],
      'final_masked_record_fraction':c['masked_records_any_leaf']/c['records'],
      'new_payload_structural_invalid_fraction':c['new_payload_structural_invalid_records']/c['records']} for fid,c in counts.items()}
    detail=save_worst(Path(root)/'worst20_full_population_per_field_reason.json',{'top20_by_field_reason':{key:[v[2] for v in sorted(heap,reverse=True)] for key,heap in worst.items()}})
    names={str(f['field_id']):f['field_key'] for f in fields}
    lines=['# Whole-population validity-mask audit','',
      'Actual CPU numeric audit. Physical unit/sign/basis/property-axis and joint policy remain pending; this report does not publish D4.',
      '','11231854 canonical records per field; 157245956 task rows. Original sources/labels are unchanged. TRAIN median/MAD uses actual final Common effectiveTRAIN anti-D5 eligibility.',
      '','Record-mask means any masked leaf or empty field; remaining valid leaves are preserved. Scope is each original enabled field own task, not all task rows and not a Common-only denominator.',
      '','|field_id|field_key|applicable exposure|scope records|source invalid records|final invalid records|newly masked records|review records|structural invalid records|',
      '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for fid,c in sorted(final.items(),key=lambda kv:int(kv[0])):
        lines.append('|'+ '|'.join(map(str,(fid,names[fid],c['applicable_to_released_exposure_scope'],c['scope_records'],c['source_masked_records_any_leaf'],c['masked_records_any_leaf'],c['newly_masked_records'],c['review_records'],c['new_payload_structural_invalid_records'])))+'|')
    lines.extend(['','Guide final masked OR original new-mask/structural-invalid strict >1% stop fields: '+repr(holds),
      '','Per-field reasons (record counts; review codes do not automatically mask):',''])
    for fid,c in sorted(final.items(),key=lambda kv:int(kv[0])):
        reasons={k:v for k,v in c.items() if k.startswith(('source_reason:','new_reason:','review_reason:'))}
        lines.append(names[fid]+': '+json.dumps(reasons,sort_keys=True))
    lines.extend(['','Worst20 for every field/reason, including exact typed score bits and source locators, are scientific DATA: '+json.dumps(detail,sort_keys=True),
      '','Within-molecule jump parts and deterministic1% original source/task locators are in the exact group-report references. Native raw archive availability/CRC was not revalidated; absent original raw locators remain UNKNOWN.',
      '','Independent dipole norm is not stored. All physical UNKNOWN counters remain separate from numeric masks: '+json.dumps(dict(unknown),sort_keys=True),''])
    md=I.write_text(Path(root)/'validity_masks.md','\n'.join(lines))
    return I.save(Path(root)/'manifest.json',{'schema':'FINAL_COMMON_TRAIN_GUIDE1_5_FULL_POPULATION_AUDIT_V1',
      'status':'QUALITY_STOP_REPORT_AWAIT_USER' if holds else 'NUMERIC_MASK_AUDIT_COMPLETE_PENDING_ROOT_AND_PHYSICAL_POLICY_REVIEW',
      'records':11231854,'task_rows':157245956,'group_reports':references,'field_counts':final,'quality_hold_fields':holds,'field_scope':field_scope,
      'effective_role_task_counts':dict(role),'physical_QA_UNKNOWN_counts':dict(unknown),'worst20_reference':detail,'validity_masks_report_reference':md,
      'source_arrays_statuses_masks_preserved':True,'robust_z_threshold':20,'new_mask_fraction_stop_strictly_greater_than':.01,
      'final_masked_fraction_stop_strictly_greater_than':.01,'existing_failure_masks_not_automatically_exempted':True,
      'mask_fraction_unit':'CANONICAL_RECORD_WITH_ANY_MASKED_LEAF_OR_EMPTY_FIELD; valid remaining leaves preserved',
      'UNKNOWN_not_promoted_or_silently_valid':True,'original_raw_archives_modified':False,'native_raw_archive_availability_or_CRC_revalidated':False,
      'full_population_recomputed_cache_bits_None_indices_original_masks_exact':True,'all_selected_one_percent_source_locators_retained':True,
      'new_threshold_or_waiver_applied':False,'physical_unit_sign_basis_axes_accepted':False,'D4_published':False})
