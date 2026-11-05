"""Whole-MID lookup of closed identity locators; no numerical source bodies."""
import contextlib,json,pathlib,os,stat
from .build_index import need,opened,sqlite_ro
CACHE={}
P=pathlib.Path

@contextlib.contextmanager
def closed_db(ref):
    # These newly derived locator DBs deliberately have frame references,
    # unlike immutable scientific source triples which keep original SHA.
    p=P(ref['path'])
    need(ref['closed'] is True and ref['whole_file_SHA_recomputed'] is False
         and p.is_absolute() and '..' not in p.parts,
         'CLOSED_DERIVED_INDEX_FRAME_REFERENCE')
    def frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid()==1278
             and before.st_size==ref['bytes'] and frame(before)==frame(p.lstat()),
             'EXACT_CLOSED_DERIVED_INDEX_SAME_FD_FRAME')
        db=sqlite_ro(P('/proc/self/fd')/str(f.fileno()))
        try:yield db
        finally:
            db.close()
            need(frame(os.fstat(f.fileno()))==frame(before)==frame(p.lstat()),'DERIVED_INDEX_CHANGED_DURING_READ')


def chunks(values,n=256):
    for a in range(0,len(values),n):yield values[a:a+n]


def locators_for_mids(manifest_path,mids,*,domains=(0,1),families=None):
    """Final Common is joined by the caller, after indexing all original sources.

    Native keys and input views are obtained from original QC/base pointer
    columns, never by splitting record IDs or assigning a synthetic owner.
    """
    if manifest_path not in CACHE:
        m=json.loads(P(manifest_path).read_text());need(m['schema']=='D6_FULL_ORIGINAL_PHYSICAL_LOCATOR_INDEX_V1','CLOSED_LOCATOR_SCHEMA')
        with opened(m['files_reference'],hash_content=False) as (f,_):files={v['id']:v for v in json.load(f)}
        rg_rows={int(k):v for k,v in m['QC_row_groups'].items()}
        for partition in m['partitions']:
            for item in partition['files']:rg_rows[item['file_id']]=item['row_group_rows']
        storages=[m['QC_locations'],*[v['storage'] for v in m['partitions']]]
        CACHE[manifest_path]=(m,files,rg_rows,storages)
    m,files,rg_rows,storages=CACHE[manifest_path]
    with closed_db(m['identity_database']) as ids,opened(m['canonical_reference'],hash_content=False) as (f,_):
        can=sqlite_ro(P('/proc/self/fd')/str(f.fileno()))
        try:
            keys={d:{} for d in domains};owners={d:{} for d in domains};pointers={}
            for domain in keys:
                for part in chunks(list(dict.fromkeys(mids))):
                    marks=','.join('?'*len(part))
                    for mid,ordinal in ids.execute('SELECT mid,ordinal FROM mid_records WHERE domain=? AND mid IN ('+marks+')',(domain,*part)):keys[domain][ordinal]=mid
                for part in chunks(list(keys[domain])):
                    marks=','.join('?'*len(part))
                    if domain==0:
                        cols='record_ordinal,record_id,molecule_id,attempt_id,job_id,task_id,lane,total_atoms,new_role'
                        for row in can.execute('SELECT '+cols+' FROM records WHERE record_ordinal IN ('+marks+')',part):owners[domain][row[0]]=dict(zip(cols.split(','),row))
                    else:
                        for row in ids.execute('SELECT ordinal,record_id,mid,role,source_record_id,geometry_source FROM pprime_records WHERE ordinal IN ('+marks+')',part):
                            owners[domain][row[0]]=dict(zip(('record_ordinal','record_id','molecule_id','effective_role','source_record_id','geometry_source'),row))
            # Pointer metadata is read first, so every label locator can carry
            # its real base/native witness without rereading numerical arrays.
            for storage in storages:
                with closed_db(storage) as db:
                    for domain,entries in keys.items():
                        for part in chunks(list(entries)):
                            marks=','.join('?'*len(part))
                            for ordinal,file_id,locator in db.execute('SELECT ordinal,file,locator FROM pointers WHERE domain=? AND ordinal IN ('+marks+')',(domain,*part)):
                                value=json.loads(locator);key=(domain,ordinal)
                                need(key not in pointers or pointers[key]['original_native_pointer']==value,'CONFLICTING_ORIGINAL_NATIVE_POINTER')
                                pointers[key]=dict(original_native_pointer=value,pointer_source_reference=files[file_id]['reference'])
            for storage in storages:
                with closed_db(storage) as db:
                    for domain,entries in keys.items():
                        for part in chunks(list(entries)):
                            marks=','.join('?'*len(part))
                            for ordinal,file_id,rg,row,task,oid in db.execute('SELECT ordinal,file,rg,r,task,owner FROM locations WHERE domain=? AND ordinal IN ('+marks+') ORDER BY file,rg,r',(domain,*part)):
                                entry=files[file_id]
                                if families is not None and entry['family'] not in families:continue
                                owner=owners[domain][ordinal]
                                observed=json.loads(db.execute('SELECT tuple_json FROM observed_owners WHERE id=?',(oid,)).fetchone()[0])
                                pointer=pointers.get((domain,ordinal));need(pointer is not None,'MISSING_ORIGINAL_BASE_NATIVE_WITNESS')
                                result=dict(source_domain='WP5' if domain==0 else 'Pprime',molecule_id=entries[ordinal],
                                  record_id=owner['record_id'],canonical_or_QC_identity=owner,source_reference=entry['reference'],
                                  family=entry['family'],row_group=rg,row_within_group=row,
                                  physical_row_ordinal=sum(rg_rows[file_id][:rg])+row,task_code=task,observed_job_owner=observed,**pointer)
                                if domain==1:
                                    result['input_view']=owner['geometry_source'];result['native_key']=owner['source_record_id']
                                else:
                                    need('geometry_status' in pointer['original_native_pointer'],'UNOBSERVED_WP5_INPUT_VIEW')
                                    result['input_view']=pointer['original_native_pointer']['geometry_status'];result['native_key']=owner['record_id']
                                yield result
        finally:can.close()

def aligned_row(locator,row):
    """Identity check at the one numerical read; never infer IDs from strings."""
    need(row.get('record_id')==locator['record_id'],'PHYSICAL_ROW_RECORD_ID_CHANGED')
    if 'molecule_id' in row:
        need(row['molecule_id']==locator['molecule_id'],'PHYSICAL_ROW_MOLECULE_ID_CHANGED')
    return row


def iter_source_rows(locators,columns):
    """Yield (locator, original scientific row), opening each row group once.

    columns may be a list or a callable(locator)->column names; identities are
    added automatically. This is the shared D4/D6 source traversal seam.
    """
    import collections
    import pyarrow.parquet as pq
    groups=collections.defaultdict(list);references={}
    for location in locators:
        ref=location['source_reference'];path=ref['path']
        need(path not in references or references[path]==ref,'CONFLICTING_SOURCE_FILE_REFERENCE')
        references[path]=ref;groups[(path,location['row_group'])].append(location)
    for path,rg in sorted(groups):
        selected=groups[(path,rg)]
        with opened(references[path],hash_content=False) as (source,_):
            table=pq.ParquetFile(source,pre_buffer=False)
            try:
                names=set(table.schema_arrow.names);requested={'record_id'}
                if 'molecule_id' in names:requested.add('molecule_id')
                for locator in selected:
                    requested.update(columns(locator) if callable(columns) else names if columns is None else columns)
                need(requested<=names,'SOURCE_REQUIRED_SCIENTIFIC_COLUMNS_MISSING')
                offsets=[location['row_within_group'] for location in selected]
                need(all(type(i) is int and 0<=i<table.metadata.row_group(rg).num_rows for i in offsets),'SOURCE_ROW_GROUP_OFFSET_INVALID')
                byrow={}
                for location in selected:byrow.setdefault(location['row_within_group'],[]).append(location)
                offset=0
                for batch in table.iter_batches(batch_size=16,row_groups=[rg],columns=sorted(requested),use_threads=False):
                    end=offset+batch.num_rows
                    for index in sorted(i for i in byrow if offset<=i<end):
                        row=batch.slice(index-offset,1).to_pylist()[0]
                        for location in byrow[index]:yield location,aligned_row(location,row)
                    offset=end
            finally:table.close()
