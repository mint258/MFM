"""WP5 dictionary-Zstd metadata only: no raw/scientific/staged BLOB fetch."""
from __future__ import annotations
import hashlib,json,os,pathlib,sqlite3,stat
from . import contract as C
COLUMNS=('record_id','calc_type','execution_id','molecule_id','dict_id','source_status','scope_status',
         'retention_reason','input_bundle_sha256','hex(raw_sha256) AS raw_sha256','raw_bytes','metadata_bytes',
         'length(raw_frame) AS raw_frame_bytes','length(metadata_frame) AS metadata_frame_bytes')
ROW_SQL='SELECT '+','.join(COLUMNS)+' FROM records WHERE record_id=? AND calc_type=? AND execution_id=?'
FRAME_SQL='SELECT metadata_frame FROM records WHERE record_id=? AND calc_type=? AND execution_id=?'


def frame(path):
    p=pathlib.Path(path);s=p.lstat()
    C.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and not any(q.is_symlink() for q in (p,*p.parents)), 'OWN_REGULAR_LITERAL_DATA')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def declared(ref,references):
    ref=C.triple(ref);C.need(ref in references,'DATA_MUST_BE_DECLARED_BEFORE_ANY_OPEN')
    p=pathlib.Path(ref['path']);before=frame(p);C.need(before[2]==ref['bytes'],'INHERITED_DATA_SIZE_DIFFERS')
    return p,before


def readonly(ref,references):
    p,before=declared(ref,references)
    C.need(all(not pathlib.Path(str(p)+s).exists() for s in ('-wal','-shm','-journal')),'CLOSED_SQLITE_NO_SIDECAR')
    db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5);db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-2048');db.execute('BEGIN')
        C.need(frame(p)==before,'SQLITE_IDENTITY_CHANGED_ON_OPEN')
    except BaseException:db.close();raise
    return db,p,before


def scalar_row(db,key):
    C.need(len(key)==3 and all(type(x) is str and x for x in key),'THREE_EXPLICIT_EXECUTION_KEY_STRINGS')
    row=db.execute(ROW_SQL,key).fetchone()
    return dict(row) if row is not None else None


def no_duplicates(pairs):
    out={}
    for key,value in pairs:
        C.need(key not in out,'DUPLICATED_METADATA_JSON_KEY');out[key]=value
    return out


def decode_metadata(frame_bytes,raw_bytes,decompress):
    C.need(type(raw_bytes) is int and 0<raw_bytes<=C.METADATA_CAP,'METADATA_RAW_CAP_BEFORE_DECOMPRESS')
    C.need(type(frame_bytes) is bytes and 0<len(frame_bytes)<=C.FRAME_CAP,'METADATA_FRAME_CAP_BEFORE_DECOMPRESS')
    raw=decompress(frame_bytes,raw_bytes)
    C.need(type(raw) is bytes and len(raw)==raw_bytes,'EXACT_METADATA_DECOMPRESSED_SIZE')
    return json.loads(raw,object_pairs_hook=no_duplicates)


def dictionaries(reference,references):
    manifest=C.meta(reference);result={};base=pathlib.Path(reference['path']).parent
    for item in manifest['dictionaries']:
        path=pathlib.Path(item['path']);path=path if path.is_absolute() else base/path
        ref=C.triple({**item,'path':str(path)});p,before=declared(ref,references)
        C.need(ref['bytes']<=C.METADATA_CAP,'SMALL_DECLARED_DICTIONARY_CAP')
        with p.open('rb') as f:data=f.read(C.METADATA_CAP+1)
        C.need(frame(p)==before and len(data)==ref['bytes'] and hashlib.sha256(data).hexdigest()==ref['sha256'],'ACTUAL_DICTIONARY_BYTES_AND_SHA')
        result[item['calc_type']]={**item,'path':str(p),'data':data,'dict_id':item.get('dict_id',item['sha256'])}
    C.need(set(result)==set(C.CALCS),'EXACT12_ACTUAL_DICTIONARIES')
    return result


def archive_header(db,plan,dicts):
    bounds=db.execute('SELECT count(*),coalesce(sum(length(CAST(key AS BLOB))+length(CAST(value AS BLOB))),0) FROM metadata').fetchone()
    C.need(bounds[0]<=128 and bounds[1]<=64<<10,'BOUNDED_ARCHIVE_HEADER_BEFORE_FETCH')
    info=dict(db.execute('SELECT key,value FROM metadata'))
    C.need(info.get('format')=='WP5_OUTPUT_ONLY_DICT_ZSTD_V2'
        and info.get('policy')=='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
        and info.get('input_bodies_saved')=='false','EXACT_WP5_NO_INPUT_ZSTD_SCHEMA')
    inputs=plan['input_authority_references']
    C.need(info['dictionary_manifest_sha256']==inputs['dictionary_manifest']['sha256']
        and info['audit_membership_sha256']==inputs['audit_membership']['sha256'],'ARCHIVE_DICTIONARY_AND_ORIGINAL_AUDIT_BINDING')
    bounds=db.execute('SELECT count(*),coalesce(sum(length(dict_id)+length(calc_type)+length(sha256)+length(path)),0) FROM dictionaries').fetchone()
    C.need(bounds[0]==12 and bounds[1]<=64<<10,'BOUNDED_ARCHIVE_DICTIONARY_TABLE_BEFORE_FETCH')
    stored={r['calc_type']:dict(r) for r in db.execute('SELECT dict_id,calc_type,sha256,path FROM dictionaries')}
    C.need(set(stored)==set(C.CALCS),'ARCHIVE_EXACT12_DICTIONARY_TYPES')
    for calc,d in dicts.items():
        C.need(stored[calc]['dict_id']==d['dict_id'] and stored[calc]['sha256']==d['sha256']
             and pathlib.Path(stored[calc]['path'])==pathlib.Path(d['path']),'EXACT_ARCHIVE_DICTIONARY_ID_PATH_SHA')
    return info


def metadata_one(db,item,plan,dicts,zstd,header):
    key=tuple(item[k] for k in ('record_id','calc_type','execution_id'));row=scalar_row(db,key)
    result={'key':dict(zip(('record_id','calc_type','execution_id'),key)), 'owner':item['owner'],
        'archive_reference':item['archive_reference'],'raw_frame_fetched':False,'native_tokens_and_frame':'PENDING',
        'input_body_state':'HASH_ONLY_NOT_SAVED'}
    if row is None:return {**result,'status':'RAW_KEY_MISSING','field_content':'NOT_READ'}
    C.need(row['molecule_id']==item['owner']['molecule_id'],'RAW_KEY_MOLECULE_DIFFERS')
    C.need(type(row['metadata_bytes']) is int and 0<row['metadata_bytes']<=C.METADATA_CAP
        and type(row['metadata_frame_bytes']) is int and 0<row['metadata_frame_bytes']<=C.FRAME_CAP,'METADATA_CAP_BEFORE_BLOB_FETCH')
    C.need(row['dict_id']==dicts[key[1]]['dict_id'],'RECORD_DICTIONARY_ID_DIFFERS')
    data=db.execute(FRAME_SQL,key).fetchone()
    C.need(data is not None and len(data[0])==row['metadata_frame_bytes'],'SAME_SNAPSHOT_METADATA_FRAME_BYTES')
    d=dicts[key[1]]
    meta=decode_metadata(data[0],row['metadata_bytes'],lambda f,n:zstd.decompress(f,d['data'],n))
    C.need(meta['record_id']==key[0] and meta['calc_type']==key[1] and meta['execution_id']==key[2]
        and meta['molecule_id']==item['owner']['molecule_id'] and meta['audit_selected'] is True,'EXACT_METADATA_EXECUTION_AND_AUDIT_MEMBER')
    C.need(meta['input_bodies_saved'] is False and meta['source_status']==row['source_status']
        and meta['scope_status']==row['scope_status'],'SOURCE_STATUS_AND_NO_INPUT_METADATA')
    context=meta['context'];owner=item['owner']
    for name in ('attempt_id','job_id','lane'):
        C.need(type(context[name]) is int and context[name]==owner[name],'EXACT_NATIVE_CONTEXT:'+name)
    # This is the original catalog_v3's explicit task_id projection, not generic loose ID equality.
    C.need(type(context['task_id']) in (int,str) and str(context['task_id'])==owner['task_id']
        and context['execution_id']==key[2],'CATALOG_V3_EXPLICIT_TASK_ID_PROJECTION')
    C.need(meta['audit_membership_sha256']==plan['input_authority_references']['audit_membership']['sha256']
        and meta['reproduction_package_sha256']==header['reproduction_package_sha256']
        and meta['input_bundle_sha256']==row['input_bundle_sha256'],'METADATA_AUDIT_PACKAGE_INPUT_HASH_BINDING')
    members=meta['output_file_manifest']
    C.need(type(members) is list and len(members)<=128,'BOUNDED_DECLARED_OUTPUT_MEMBER_LIST')
    for member in members:
        C.need(type(member['name']) is str and type(member['bytes']) is int and member['bytes']>=0
            and type(member['sha256']) is str and len(member['sha256'])==64,'EXPLICIT_DECLARED_MEMBER_REFERENCE')
    result.update(status='RAW_ROW_PRESENT_METADATA_VERIFIED',scalar_observation=row,
        input_file_sha256=meta.get('input_file_sha256'),input_bundle_sha256=meta['input_bundle_sha256'],
        source_reference=meta.get('source_reference'),software=meta.get('software'),software_version_id=meta.get('software_version_id'),
        keywordSHA=meta.get('keywordSHA'),reproduction_package_sha256=meta['reproduction_package_sha256'],
        audit_membership_sha256=meta['audit_membership_sha256'],output_members=members,
        member_state='MEMBER_DECLARED_NOT_READ',field_content='NATIVE_TOKEN_NOT_READ',
        task_id_projection='catalog_v3:str(context.task_id); native type/value preserved',native_context=context)
    if not (type(result['input_bundle_sha256']) is str and len(result['input_bundle_sha256'])==64 and result['input_file_sha256']):
        result['input_body_state']='INPUT_HASH_MISSING_NO_BODY'
    C.need(len(json.dumps(result,allow_nan=False).encode())<=64<<10,'BOUNDED_FULL_ROW_NO_TRUNCATION')
    return result