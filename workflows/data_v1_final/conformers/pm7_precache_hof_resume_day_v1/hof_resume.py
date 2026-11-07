"""Exact closed-byte adoption and remaining original HOF source orchestration."""
import ast,base64,collections,hashlib,inspect,json,os,pathlib,stat
from . import metadata as M
from workflows.data_v1_final.conformers.postprocess_day_v1 import hof as ORIGINAL_HOF
from workflows.data_v1_final.conformers.pm7_precache_day_v1 import pilot_prepare as PRIORITY
PC=ORIGINAL_HOF.PC;H=ORIGINAL_HOF.H;C=ORIGINAL_HOF.C

def stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)

def clone(ctx,reference,target):
    """Same currently stable input FD, full SHA, fresh output; no DB row rewrite."""
    M.shape(reference);M.need(reference['bytes']>0,'POSITIVE_CLOSED_DATA_NOT_ZERO_SOURCE')
    source=pathlib.Path(reference['path']);target=pathlib.Path(target)
    M.need(ctx.out in target.parents and not target.exists() and not any(p.is_symlink() for p in (source,*source.parents,target,*target.parents)),
      'ONLY_FIXED_OLD_REGULAR_INPUT_AND_FRESH_CURRENT_OUTPUT')
    before=source.lstat();M.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_nlink==1
      and before.st_size==reference['bytes'],'CURRENT_CLOSED_SINGLE_LINK_INPUT_FRAME')
    token='closed-copy:'+str(target);ctx.reserve(token,reference['bytes'])
    try:
        target.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();size=0
        infd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW);outfd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(infd,'rb') as src,os.fdopen(outfd,'wb') as dst:
            M.need(stamp(os.fstat(src.fileno()))==stamp(before),'ACTUAL_INPUT_FD_EQUALS_PATH_FRAME')
            while block:=src.read(1<<20):
                ctx.check();dst.write(block);h.update(block);size+=len(block)
            dst.flush();os.fsync(dst.fileno())
            M.need(stamp(os.fstat(src.fileno()))==stamp(before)==stamp(source.lstat())
              and size==reference['bytes'] and h.hexdigest()==reference['sha256'],'FULL_CLOSED_SOURCE_SHA_AND_FD_STABLE')
        fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        result=ctx.reference(target);M.need(result['bytes']==reference['bytes'] and result['sha256']==reference['sha256'],
          'WHOLE_COPY_BYTES_AND_SHA_EQUALS_FAILED_ORIGINAL_NOT_NEW_SCIENCE')
        ctx.commit_closed_copy(target,size)
        return result
    finally:ctx.release(token)


def ordered_prefix(needed,notes,expected):
    M.need(type(notes)is list and len(notes)==expected and len(notes)<=len(needed),'EXACT_CLOSED_SOURCE_PREFIX_COUNT')
    seen=set()
    for source,note in zip(needed,notes):
        key=M.canonical(note['source'])
        M.need(key not in seen and note['source']==source and note['status']=='ORIGINAL_SCALAR_READER_CLOSED',
          'ONLY_EXACT_ORIGINAL_NEEDED_SOURCE_ORDER_NO_DUPLICATE_GAP_OR_POLLUTION')
        seen.add(key)
    return needed[len(notes):]

def adopt(ctx,base,registered):
    review,qa,origin=M.hof_reuse(ctx.plan,registered)
    for key in ('closed_state_reference','observations_reference','failed_receipt_reference'):ctx.authorized([review[key]])
    receipt=ctx.read(review['failed_receipt_reference'])
    oldargv=origin['request']['execution_argv'];planpath=oldargv[oldargv.index('--plan')+1]
    oldplanref=next(r for r in origin['request']['source_references'] if r['path']==planpath)
    M.need(receipt['schema']=='PM7_PRECACHE_DAY_RECEIPT_V1' and str(receipt['job_id'])==origin['job_id']=='4524738'
      and receipt['plan_reference']==oldplanref and receipt['startup_proof_reference']==origin['proof_reference']
      and receipt['closed_state_reference']==review['closed_state_reference']
      and receipt['hof_projection_reference']==review['observations_reference']
      and receipt['HOF_projection_complete'] is False and not receipt['state_counts'] and not receipt['unknown'],
      'CPU_WHOLE_SHA_FAILED_RECEIPT_EXACT_PARENT_AND_ZERO_MOLECULES_NOT_OLD_C0')
    pre=receipt['pilot_preselection_reference'];M.shape(pre)
    M.need(pre['bytes']>0 and pre['path']==review['pilot_preselection_locator'],
      'ONLY_ACTUAL_FAILED_RECEIPT_POSITIVE_PRESELECTION_REF_AT_FIXED_LOCATOR')
    ctx.hof_resume_preselection_reference=pre
    ctx.write_json_new(ctx.out/'closed_preselection_transitive_authority.json',{
      'schema':'PM7_CPU_RESOLVED_FAILED_PRESELECTION_TRANSITIVE_AUTHORITY_V1',
      'Root_review_reference':ctx.plan['hof_closed_prefix_reuse_review_reference'],
      'actual_whole_SHA_failed_receipt_reference':review['failed_receipt_reference'],
      'derived_preselection_reference':pre,'new_actual_parent_job_id':str(ctx.proof['job_id']),
      'old_FAILED_not_C0':True,'table_refs_require_same_closed_container_and_fixed_subtree':True})
    state=pathlib.Path(review['closed_state_reference']['path'])
    wal=pathlib.Path(str(state)+'.wal');M.need(not wal.exists() and not wal.is_symlink(),'OLD_DUCKDB_CLOSED_NO_WAL')
    clone_ref=clone(ctx,review['closed_state_reference'],ctx.out/'work.duckdb')
    return review,qa,origin,clone_ref

def validate_db(ctx,db,base,review,qa):
    for table,count in qa['actual_table_row_counts'].items():
        M.need(table in ('formal','roster','hof','hof_owners','pilot_priority'),'ONLY_DECLARED_OLD_SQL_TABLES')
        M.need(db.execute('SELECT count(*) FROM '+table).fetchone()[0]==count,'EXACT_FAILED_CLOSED_SQL_MASS:'+table)
    M.need(db.execute('SELECT count(DISTINCT record_id) FROM formal').fetchone()[0]==11231854
      and db.execute('SELECT count(DISTINCT molecule_id) FROM roster').fetchone()[0]==1220466
      and db.execute('SELECT count(DISTINCT molecule_id) FROM hof_owners').fetchone()[0]==1220466,
      'FORMAL_ROSTER_CANONICAL_OWNER_UNIQUE_FULL_POPULATION')
    M.need(db.execute('SELECT count(*) FROM hof h ANTI JOIN formal f USING(record_id)').fetchone()[0]==0,
      'NO_FOREIGN_HOF_RECORDS_IN_CLOSED_DATABASE')
    roles=dict(db.execute('SELECT effective_role,count(*) FROM pilot_priority GROUP BY effective_role').fetchall())
    M.need(roles=={'TRAIN':50000,'VAL':5000},'FROZEN55K_ROLE_COUNTS_NOT_NEW_SELECTION')
    authority=C.meta(base['hof_authority_review']);projection=C.meta(authority['projection_receipt_reference'])
    M.need(authority['schema']=='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1'
      and authority['status']=='VERIFIED_FROZEN_PM7_B_SCALAR_READER' and authority['registry_id']==60
      and authority['unit']=='kcal/mol' and authority['native_energy_fallback_allowed'] is False
      and projection['status']=='CATALOG_METADATA_PROJECTION_VERIFIED'
      and projection['source_files']==authority['source_files_reference'],'EXACT_ORIGINAL_HOF_AUTHORITY')
    owner=ctx.require(authority['latest_owner_reference'])
    canonical='SELECT * FROM read_parquet('+C.q(str(owner))+") WHERE state='COMPLETE' AND receipt_context_consistent AND export_published"
    M.need(db.execute('SELECT count(*) FROM (SELECT * FROM hof_owners EXCEPT ALL '+canonical+')').fetchone()[0]==0
      and db.execute('SELECT count(*) FROM ('+canonical+' EXCEPT ALL SELECT * FROM hof_owners)').fetchone()[0]==0,
      'EXACT_CURRENT_CANONICAL_OWNER_TABLE_EQUALS_CLOSED_PREFIX')
    sources=ctx.read(projection['source_files'],64<<20);needed=[]
    for source in sources:
        if source['family']!='pm7_neutral':continue
        count=db.execute('SELECT count(*) FROM formal r JOIN hof_owners o USING(molecule_id) WHERE r.file_group=? AND o.job_id=?',
          [source['source_file_group'],source['source_job_id']]).fetchone()[0]
        if count:needed.append(source)
    observations=ctx.read(review['observations_reference'],128<<20)
    M.need(observations['schema']=='POSTPROCESS_CANONICAL_HOF_SOURCE_OBSERVATIONS_V1'
      and observations['reader_complete'] is False and observations['native_energy_fallback'] is False
      and observations['authority_reference']==base['hof_authority_review']
      and len(needed)==qa['needed_owner_source_groups']==184,'OLD_FALSE_FLAG_AND_ORIGINAL184_NEEDED_SOURCES')
    remaining=ordered_prefix(needed,observations['sources'],180)
    M.need(len(remaining)==4 and sum(n['observed_records']-n['duplicate_records'] for n in observations['sources'])==10277940,
      'EXACT180_COMMITTED_SOURCE_MASS_AND_ONLY4_REMAINING')
    return observations['sources'],remaining,needed

def project_remaining(ctx,db,base,observations,remaining):
    """The original reader/validate/canonical/row upsert and failure body intact."""
    pc=H.profile_common();observations=list(observations)
    for source in remaining:
        if ctx.observe() is not None:break
        targets=db.execute('SELECT r.record_id,r.molecule_id,r.total_atoms,o.attempt_id,o.job_id,o.task_id,o.lane FROM formal r JOIN hof_owners o USING(molecule_id) WHERE r.file_group=? AND o.job_id=?',
          [source['source_file_group'],source['source_job_id']]).fetch_arrow_table().to_pylist()
        if not targets:continue
        wanted={r['record_id']:r for r in targets};note={'source':source,'target_records':len(wanted)}
        try:
            # Original reader verifies inherited full-readback authority, stable
            # current UID/size/frame, exact current-owner five-key/lane/atoms,
            # registry60/f64/convergence and scalar-only physical leaf pruning.
            result=pc.read_hof_file({'ref':source,'owners':wanted});values=result['hof'];duplicates=[]
            for rid,value in values.items():
                PC.validate_hof(value);old=db.execute('SELECT 1 FROM hof WHERE record_id=?',[rid]).fetchone()
                if old:db.execute('UPDATE hof SET duplicate=TRUE WHERE record_id=?',[rid]);duplicates.append(rid)
                else:db.execute('INSERT INTO hof VALUES(?,?,FALSE)',[rid,C.canonical(value).decode()])
            note.update(status='ORIGINAL_SCALAR_READER_CLOSED',observed_records=len(values),duplicate_records=len(duplicates),current_identity=result['identity'],projected_columns=result['projected_columns'])
        except Exception as exc:
            note.update(status='SOURCE_HOF_PENDING_GEOMETRY_NOT_DROPPED',error=repr(exc))
            for rid in wanted:db.execute('INSERT INTO hof VALUES(?,?,FALSE) ON CONFLICT(record_id) DO UPDATE SET duplicate=TRUE',
              [rid,C.canonical(PC.missing_hof('CANONICAL_HOF_SOURCE_READ_OR_VALIDATION_FAILED')).decode()])
        observations.append(note);db.commit()
    complete=ctx.stop is None and len(observations)==184
    ref=ctx.write_json_new(ctx.out/'hof_projection_observations.json',{'schema':'POSTPROCESS_CANONICAL_HOF_SOURCE_OBSERVATIONS_V1',
      'sources':observations,'reader_complete':complete,'authority_reference':base['hof_authority_review'],'native_energy_fallback':False,
      'inherited_failed_prefix_review_reference':ctx.plan['hof_closed_prefix_reuse_review_reference'],
      'original_failed_parent_reader_complete':False,'inherited_sources_not_read_or_projected_again':180,
      'actual_new_sources_processed':len(observations)-180,
      'actual_new_sources_reader_closed':sum(n['status']=='ORIGINAL_SCALAR_READER_CLOSED' for n in observations[180:]),
      'current_parent_job_id':str(ctx.proof['job_id'])})
    return ref,complete

def restore_priority(ctx,db,base,review,descriptors):
    """Copy frozen selected tables byte-for-byte; never rerank or reselect MIDs."""
    pre_ref=ctx.hof_resume_preselection_reference
    M.need(pre_ref['path']==review['pilot_preselection_locator'],'CPU_RECEIPT_RESOLVED_PRESELECTION_ONLY')
    pre=ctx.read(pre_ref,8<<20);root=pathlib.Path(review['old_output_root'])/'pilot_preselection'
    M.need(pre['schema']=='EXISTING_COMPLETE_SPRIME_PILOT_PRESELECTION_V1' and pre['pilot_ready_scalar_only'] is True
      and pre['pilot_counts']=={'TRAIN':50000,'VAL':5000} and pre['seed']==20261025
      and pre['Root_policy_reference']==ctx.plan['pilot_priority_review_reference']
      and pre['original_per_molecule_reference']==base['per_molecule'],'EXACT_ORIGINAL_FROZEN55K_SELECTION_AUTHORITY')
    allowed={'full_population_membership','complete_old_mother','pilot55k','diagnostic20k_molecule_preselection',
      'train_120000','train_240000','train_600000'}
    M.need(set(pre['tables'])<=allowed and {'full_population_membership','complete_old_mother','pilot55k','diagnostic20k_molecule_preselection'}<=set(pre['tables']),
      'FINITE_ORIGINAL_SELECTED_TABLE_SET_NO_DYNAMIC_SOURCE_DISCOVERY')
    target=ctx.out/'pilot_preselection';target.mkdir();tables={};frames={}
    for key,ref in pre['tables'].items():
        M.shape(ref);M.need(ref['bytes']>0 and pathlib.Path(ref['path'])==root/(key+'.parquet'),'BOUND_FAILED_PARENT_PRESELECTION_TABLE_LOCATOR')
        # Authority is the exact closed, whole-SHA preselection container plus
        # this Root-reviewed finite original-output subtree, not arbitrary IO.
        tables[key]=clone(ctx,ref,target/(key+'.parquet'))
        frames[key]=stamp(pathlib.Path(tables[key]['path']).lstat())
    expected_queries={'full_population_membership':'SELECT * FROM pilot_scalar_membership',
      'complete_old_mother':'SELECT * FROM pilot_complete_old_ranked','pilot55k':'SELECT * FROM pilot_priority'}
    for n in (120000,240000,600000):
        expected_queries['train_'+str(n)]="SELECT molecule_id,effective_role,selection_rank FROM pilot_complete_old_ranked WHERE effective_role='TRAIN' AND selection_rank<"+str(n)
    for key,ref in tables.items():
        if key=='diagnostic20k_molecule_preselection':continue
        query=expected_queries[key];actual='SELECT * FROM read_parquet('+C.q(ref['path'])+')'
        M.need(db.execute('SELECT count(*) FROM ('+actual+' EXCEPT ALL '+query+')').fetchone()[0]==0
          and db.execute('SELECT count(*) FROM ('+query+' EXCEPT ALL '+actual+')').fetchone()[0]==0,
          'ALL_COPIED_PRESELECTION_TABLE_IDS_ROLES_RANKS_EQUAL_ORIGINAL_CLOSED_SQL:'+key)
    import pyarrow.parquet as pq
    selected=pq.read_table(tables['pilot55k']['path'],columns=['molecule_id','effective_role','selection_rank']).to_pylist()
    frozen=db.execute('SELECT molecule_id,effective_role,selection_rank FROM pilot_priority').fetchall()
    M.need(len(selected)==55000 and {(r['molecule_id'],r['effective_role'],r['selection_rank']) for r in selected}==set(frozen),
      'EXACT_OLD_DATABASE_AND_COPIED55K_IDS_ROLES_RANKS')
    copied=dict(pre,tables=tables,original_preselection_reference=pre_ref,
      copied_into_actual_parent_job_id=str(ctx.proof['job_id']),no_new_MID_ranking_or_selection=True)
    result=ctx.write_json_new(target/'preselection.json',copied);priority={r['molecule_id'] for r in selected}
    diagnostic_rows=pq.read_table(tables['diagnostic20k_molecule_preselection']['path'],columns=['molecule_id']).to_pylist()
    diagnostic={r['molecule_id'] for r in diagnostic_rows}
    M.need(len(diagnostic_rows)==len(diagnostic)==20000,'EXACT_ALREADY_FROZEN_GLOBAL20K_CANDIDATE_IDS_NOT_RESELECTED')
    import pyarrow as pa
    db.register('resume_diagnostic_candidates',pa.table({'molecule_id':sorted(diagnostic)}))
    M.need(db.execute('SELECT count(*) FROM resume_diagnostic_candidates d ANTI JOIN roster r USING(molecule_id)').fetchone()[0]==0,
      'NO_FROZEN_DIAGNOSTIC_MID_OUTSIDE_ORIGINAL_ROSTER')
    counts={};diagnostic_counts={}
    for i,d in enumerate(descriptors):
        count=db.execute('SELECT count(*) FROM roster r JOIN pilot_priority p USING(molecule_id) WHERE r.file_group=? AND r.shard_index=?',
          [d['file_group'],d['shard_index']]).fetchone()[0]
        if count:counts[i]=count
        extra=db.execute('SELECT count(*) FROM roster r JOIN resume_diagnostic_candidates d USING(molecule_id) '
          'ANTI JOIN pilot_priority p USING(molecule_id) WHERE r.file_group=? AND r.shard_index=?',
          [d['file_group'],d['shard_index']]).fetchone()[0]
        if extra:diagnostic_counts[i]=extra
    M.need(sum(counts.values())==55000,'EXACT_247_DESCRIPTOR_PRIORITY_PARTITION')
    db.unregister('resume_diagnostic_candidates')
    M.need(all(stamp(pathlib.Path(ref['path']).lstat())==frames[key] for key,ref in tables.items()),
      'ALL_WHOLE_SHA_COPIED_SELECTION_FILES_CURRENT_FRAMES_STABLE_THROUGH_SQL_AND_ID_READBACK')
    M.need(sum(diagnostic_counts.values())==len(diagnostic-priority),'EXACT_DISJOINT_DIAGNOSTIC_EXTRA_DESCRIPTOR_PARTITION')
    return result,priority,diagnostic,scheduled_segments(descriptors,counts,diagnostic_counts)

def scheduled_segments(descriptors,primary_counts,diagnostic_extra_counts):
    """Only scheduling; original descriptor count/order and select_phase object."""
    original=PRIORITY.segments(descriptors,primary_counts);result=[r for r in original if r['phase']=='PILOT_PRIORITY']
    for phase in ('DIAGNOSTIC_CANDIDATE_PRIORITY','ORIGINAL_REMAINDER'):
        for i,d in enumerate(descriptors):
            extra=diagnostic_extra_counts.get(i,0);primary=primary_counts.get(i,0)
            M.need(type(extra)is int and 0<=extra<=d['molecules']-primary,'DISJOINT_EXISTING_DIAGNOSTIC_CANDIDATES_ONLY')
            count=extra if phase=='DIAGNOSTIC_CANDIDATE_PRIORITY' else d['molecules']-primary-extra
            if count:result.append({'descriptor_ordinal':i,'phase':phase,'molecules':count})
    M.need(set(diagnostic_extra_counts)<=set(range(len(descriptors)))
      and sum(r['molecules'] for r in result)==sum(d['molecules'] for d in descriptors),'THREE_DISJOINT_PHASES_EXACT_ORIGINAL_MOTHER_UNION')
    return result

def select_scheduled(metas,by,primary,diagnostic,phase):
    if phase=='PILOT_PRIORITY':return PRIORITY.select_phase(metas,by,primary,'PILOT_PRIORITY')
    if phase=='DIAGNOSTIC_CANDIDATE_PRIORITY':return PRIORITY.select_phase(metas,by,diagnostic-primary,'PILOT_PRIORITY')
    M.need(phase=='ORIGINAL_REMAINDER','EXACT_THREE_SCHEDULING_PHASES')
    return PRIORITY.select_phase(metas,by,primary|diagnostic,'ORIGINAL_REMAINDER')

def source_proof():
    witness=M.meta(M.pin(M.HERE/'source_origin.json'));refs=[]
    for item in witness['files']:
        actual=M.pin(M.REPO/item['relative_path']);M.need(actual['bytes']==item['bytes'] and actual['sha256']==item['sha256'],
          'EXACT_ORIGINAL_SOURCE_NOT_REWRITTEN:'+item['relative_path']);refs.append(actual)
    inverses=[]
    for delta in witness['exact_source_inverse_deltas']:
        original=(base64.b64decode(delta['original_source_base64'],validate=True)
          if delta['original_relative_path']==delta['current_relative_path']
          else (M.REPO/delta['original_relative_path']).read_bytes())
        current=(M.REPO/delta['current_relative_path']).read_bytes()
        M.need(len(original)==delta['original_bytes'] and hashlib.sha256(original).hexdigest()==delta['original_sha256']
          and len(current)==delta['current_bytes'] and hashlib.sha256(current).hexdigest()==delta['current_sha256'],
          'ENTIRE_OLD_AND_NEW_SOURCE_BYTES_PINNED:'+delta['current_relative_path'])
        lo,tail=delta['prefix_bytes'],delta['suffix_bytes'];old=base64.b64decode(delta['original_delta_base64'],validate=True)
        new=base64.b64decode(delta['current_delta_base64'],validate=True)
        oldhi=len(original)-tail;newhi=len(current)-tail
        M.need(original[lo:oldhi]==old and current[lo:newhi]==new
          and original[:lo]+new+original[oldhi:]==current
          and current[:lo]+old+current[newhi:]==original,'ONLY_DECLARED_EXACT_SOURCE_IO_ADAPTER_DELTA')
        restored=current[:lo]+old+current[newhi:]
        M.need(ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(original),include_attributes=False),
          'WHOLE_INVERSE_MODULE_AST_NO_FUNCTION_SKIPPED')
        inverses.append(delta['current_relative_path'])
    old=pathlib.Path(ORIGINAL_HOF.__file__).read_text();new=inspect.getsource(project_remaining)
    start='        targets=db.execute(';end='        observations.append(note);db.commit()'
    def body(text):
        M.need(text.count(start)==1 and text.count(end)==1,'UNIQUE_WHOLE_ORIGINAL_HOF_ROW_BODY')
        return text[text.index(start):text.index(end)+len(end)]
    M.need(body(old)==body(new),'ORIGINAL_TARGET_READER_VALIDATE_F64_UPSERT_DUPLICATE_AND_FAILURE_BODY_BYTES')
    # The actual original values() object remains in CACHE.task; no aliases,
    # new values/precision/missing policy or native energy are substituted.
    M.need(ORIGINAL_HOF.values is __import__(ORIGINAL_HOF.__name__,fromlist=['values']).values,
      'DIRECT_ORIGINAL_HOF_VALUE_AND_REASON_OBJECT')
    return {'status':'ORIGINAL_HOF_ROW_BODY_BYTES_AND_DIRECT_READER_OBJECTS',
      'original_source_references':refs,'new_HOF_values_function':False,'closed10m_reprojected':False,
      'whole_source_byte_and_AST_inverse_modules':inverses,
      'new_QM_UFF_calls':0,'original180_retained_as_FAILED_origin':True}
