"""Read-only exact keys; bounded bodies, original WP5 decompressor and unbundle."""
from __future__ import annotations
import contextlib,hashlib,json,os,pathlib,sqlite3,stat,struct
from workflows.data_v1_final.export.native_availability_v1 import reader as I
from . import contract as C


def fd_frame(fd):
    s=os.fstat(fd);return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


@contextlib.contextmanager
def held(reference,references,check,whole_sha=True):
    ref=C.triple(reference);p,before=I.declared(ref,references)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        C.need(fd_frame(fd)==before,'OPEN_FD_IDENTITY_EQUALS_LITERAL_PATH')
        if whole_sha:
            h=hashlib.sha256();total=0
            while True:
                check();block=os.read(fd,1<<20)
                if not block:break
                total+=len(block);h.update(block)
            C.need(total==ref['bytes'] and h.hexdigest()==ref['sha256'],'ACTUAL_WHOLE_DECLARED_DATA_SHA')
            os.lseek(fd,0,os.SEEK_SET)
        C.need(fd_frame(fd)==before and I.frame(p)==before,'STABLE_FD_AND_PATH_AFTER_SHA')
        yield p,fd,before
    finally:
        try:C.need(fd_frame(fd)==before and I.frame(p)==before,'STABLE_FD_AND_PATH_AT_CLOSE')
        finally:os.close(fd)


@contextlib.contextmanager
def archive(reference,references,check,whole_sha):
    with held(reference,references,check,whole_sha) as (p,fd,before):
        C.need(all(not pathlib.Path(str(p)+suffix).exists() for suffix in ('-wal','-shm','-journal')),'CLOSED_SQLITE_NO_SIDECARS')
        db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-2048');db.execute('BEGIN')
            C.need(fd_frame(fd)==before and I.frame(p)==before,'SQLITE_OPENS_SAME_HASHED_LITERAL_FILE')
            yield db
        finally:db.close()


def metadata(db,item,old_plan,dicts,zstd,header):
    observed=I.metadata_one(db,item,old_plan,dicts,zstd,header)
    C.need(observed['status']=='RAW_ROW_PRESENT_METADATA_VERIFIED','EXACT_PRIOR_METADATA_BINDING')
    row=I.scalar_row(db,C.key(item));frame=db.execute(I.FRAME_SQL,C.key(item)).fetchone()[0]
    meta=I.decode_metadata(frame,row['metadata_bytes'],lambda b,n:zstd.decompress(b,dicts[item['calc_type']]['data'],n))
    C.need(type(meta['file_group']) is int and meta['file_group']>=0
        and type(meta['source_payload_sha256']) is str and C.re.fullmatch('[0-9a-f]{64}',meta['source_payload_sha256']),
        'ORIGINAL_EXPLICIT_SOURCE_GROUP_AND_PAYLOAD_SHA')
    pointer=meta['source_reference']
    C.need(type(pointer) is dict and set(pointer)=={'shard_id','real_index'}
        and type(pointer['shard_id']) is int and 0<=pointer['shard_id']<=10
        and type(pointer['real_index']) is int and pointer['real_index']>=0,'EXACT_ORIGINAL_SOURCE_POINTER_TYPES')
    return row,meta,observed


def raw_limits(row):
    C.need(type(row['raw_bytes']) is int and 0<row['raw_bytes']<=C.RAW_CAP,'RAW_BUNDLE_CAP_BEFORE_BLOB')
    C.need(type(row['raw_frame_bytes']) is int and 0<row['raw_frame_bytes']<=C.FRAME_CAP,'RAW_FRAME_CAP_BEFORE_BLOB')
    C.need(type(row['raw_sha256']) is str and C.re.fullmatch('[0-9a-fA-F]{64}',row['raw_sha256']) is not None,'EXACT_RAW_SHA_BEFORE_BLOB')


def decode_raw(frame,row,dictionary,zstd,unbundle):
    raw_limits(row)
    C.need(type(frame) is bytes and len(frame)==row['raw_frame_bytes'],'EXACT_RAW_FRAME_LENGTH')
    raw=zstd.decompress(frame,dictionary,row['raw_bytes'])
    C.need(type(raw) is bytes and len(raw)==row['raw_bytes'] and hashlib.sha256(raw).hexdigest().upper()==row['raw_sha256'].upper(),
        'ORIGINAL_EXACT_RAW_BUNDLE_SHA')
    files,manifest=unbundle(raw)
    C.need(type(files) is list and type(manifest) is list and len(files)==len(manifest)<=128
        and len({f['name'] for f in files})==len(files),'BOUNDED_WHOLE_UNIQUE_OUTPUT_MEMBER_SET')
    for f,m in zip(files,manifest):
        C.need(type(m['bytes']) is int and m['bytes']>=0 and m['bytes']==f['byte_count']
            and m['name']==f['name'] and C.re.fullmatch('[0-9a-f]{64}',m['sha256']) is not None
            and m['sha256']==f['sha256'],'EXACT_EACH_ORIGINAL_MEMBER_DECLARATION')
    for f in files:
        p=pathlib.PurePosixPath(f['name'])
        C.need(p.name==str(p) and f['name'] not in {'input.xyz','input.mop','native.inp','input_recipe.json'}
            and type(f['byte_count']) is int and 0<=f['byte_count']<=C.MEMBER_CAP,'OUTPUT_ONLY_BOUNDED_BASENAME')
    return raw,files,manifest


def raw(db,item,row,meta,dictionary,zstd,unbundle):
    raw_limits(row)
    fetched=db.execute('SELECT raw_frame FROM records WHERE record_id=? AND calc_type=? AND execution_id=?',C.key(item)).fetchone()
    C.need(fetched is not None,'NO_LATEST_OR_PARTIAL_EXECUTION_FALLBACK')
    body,files,manifest=decode_raw(fetched[0],row,dictionary,zstd,unbundle)
    C.need(manifest==meta['output_file_manifest'],'EXACT_METADATA_AND_RAW_MEMBER_MANIFEST')
    return body,files


def bytes_data(path,data):
    C.need(type(data) is bytes,'EXACT_DATA_BYTES')
    with pathlib.Path(path).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def json_data(path,value):
    data=(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode()
    C.need(len(data)<=C.ROW_CAP,'FULL_RECORD_EVIDENCE_CAP_NO_TRUNCATION')
    return bytes_data(path,data)


def scientific_bytes(value):
    from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import encode,decode,signature
    tree,values=encode(value)
    C.need(signature(decode(tree,values))==signature(value),'ORIGINAL_LOSSLESS_CODEC_ROUNDTRIP')
    result={'schema':'NATIVE_BODY_FRAME32_LOSSLESS_DATA_EVIDENCE_V1','tree_json':tree,
        'values_float64_bits_little_endian':[struct.pack('<d',v).hex() for v in values],
        'scientific_signature':signature(value),'binary64_is_parser_output_not_inferred_native_precision':True}
    data=(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n').encode()
    C.need(len(data)<=C.ROW_CAP,'FULL_RECORD_EVIDENCE_CAP_NO_TRUNCATION')
    return data


def base_rows(ref,locators,references,check):
    import numpy as np
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    wanted={r['record_id']:r for r in locators};out={}
    names=['record_id','molecule_id','attempt_id','job_id','task_id','atomic_numbers','positions_A',
        'source_payload_sha256','source_native_geometry_sha256','native_atom_order_sha256','geometry_status']
    with held(ref,references,check,True) as (p,fd,before):
        with os.fdopen(os.dup(fd),'rb') as stream:
            f=pq.ParquetFile(stream);physical=0
            try:
                for group in range(f.num_row_groups):
                    local=0
                    # Columnar I/O decodes bounded batches; only selected32 rows are materialized/diagnosed.
                    for batch in f.iter_batches(batch_size=64,row_groups=[group],columns=names,use_threads=False):
                        check();flags=pc.is_in(batch.column('record_id'),value_set=pa.array(sorted(wanted)))
                        positions=[i for i,b in enumerate(flags.to_pylist()) if b]
                        for row,position in zip(batch.filter(flags).to_pylist(),positions):
                            rid=row['record_id'];loc=wanted[rid];owner=loc['owner']
                            C.need(rid not in out and row['molecule_id']==owner['molecule_id']
                                and row['attempt_id']==owner['attempt_id'] and row['job_id']==owner['job_id']
                                and type(row['attempt_id']) is type(owner['attempt_id']) and type(row['job_id']) is type(owner['job_id'])
                                and str(row['task_id'])==owner['task_id'],'EXACT_SELECTED_BASE_CANONICAL_OWNER')
                            z=row['atomic_numbers'];coords=row['positions_A']
                            C.need(type(z) is list and len(z)==owner['total_atoms'] and 0<len(z)<=2048
                                and all(type(v) is int and 1<=v<=118 for v in z),'BASE_EXACT_ATOM_COUNT_AND_DOMAIN')
                            x=np.asarray(coords,dtype=np.float64)
                            C.need(x.shape==(len(z),3) and np.isfinite(x).all()
                                and row['geometry_status']=='ORIGINAL_PM7_GEOMETRY','BASE_ORIGINAL_FINITE_NATIVE_GEOMETRY')
                            C.need(hashlib.sha256(np.asarray(z,dtype='<i8').tobytes()).hexdigest()==row['native_atom_order_sha256']
                                and hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()==row['source_native_geometry_sha256']
                                and row['source_payload_sha256']==loc['source_payload_sha256'],'BASE_ORIGINAL_ATOM_COORDINATE_AND_PAYLOAD_SHA')
                            from rdkit import Chem
                            symbols=[Chem.GetPeriodicTable().GetElementSymbol(v) for v in z]
                            out[rid]={'row':row,'symbols':symbols,'provenance':{'source_reference':ref,
                                'current_whole_SHA_verified':True,'stable_frame':list(before),'row_group':group,
                                'row_within_group':local+position,'physical_row_ordinal':physical+local+position,
                                'original_payload_sha256':loc['source_payload_sha256'],'owner':owner,
                                'atom_order_sha256':row['native_atom_order_sha256'],
                                'coordinates_sha256':row['source_native_geometry_sha256'],
                                'whole_LMDB_SHA':'NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED_NO_LMDB_OPEN'}}
                        local+=batch.num_rows
                    physical+=local
            finally:f.close()
    C.need(set(out)==set(wanted),'EXACT_BASE32_SUBSET_NO_MISSING_OR_DUPLICATE')
    return out
