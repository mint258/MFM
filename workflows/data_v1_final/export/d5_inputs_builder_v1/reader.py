"""Only original native read/graph, exact ordinary packet rows and HOF reader."""
from __future__ import annotations
import contextlib,gzip,hashlib,json,os,pathlib,stat
from . import contract as C,io as I,geometry as G
SOURCE_FRAMES={};NATIVE_FRAMES={}


@contextlib.contextmanager
def source_fd(reference,declared,check):
    ref=C.reference(reference);C.need(ref in declared,'SOURCE_BEFORE_ANY_OPEN_DECLARED')
    prior=SOURCE_FRAMES.get(ref['path'])
    if prior is None:
        with I.held(ref,declared,check) as (path,fd,frame):
            SOURCE_FRAMES[ref['path']]=(ref,frame);yield path,fd,frame
        return
    path=I.R.literal(ref['path']);frame=I.R.frame(path.lstat())
    C.need(prior==(ref,frame),'CACHED_WHOLE_SHA_SOURCE_FRAME_UNCHANGED')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        C.need(I.R.frame(os.fstat(fd))==frame,'CACHED_HASH_SOURCE_FD_EQUALS_PATH');check();yield path,fd,frame
    finally:
        try:C.need(I.R.frame(os.fstat(fd))==frame==I.R.frame(path.lstat()),'CACHED_HASH_SOURCE_STABLE_AFTER_READ')
        finally:os.close(fd)


def native_record(pointer,native):
    project=pathlib.Path('/share/home/zixiao/descriptor_analysis');p=pathlib.Path(pointer['source_path'])
    p=p if p.is_absolute() else project/p
    C.need(project in p.parents and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'ORIGINAL_PROJECT_LITERAL_NATIVE_PATH')
    C.need(type(pointer['real_index']) is int and pointer['real_index']>=0 and type(pointer['total_atoms']) is int
        and pointer['total_atoms']>0 and len(pointer['record_payload_sha256'])==64,'EXACT_CANONICAL_NATIVE_POINTER')
    before=p.lstat();C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278,'ORIGINAL_REGULAR_UID_NATIVE_FILE')
    C.need(NATIVE_FRAMES.setdefault(str(p),I.R.frame(before))==I.R.frame(before),'CACHED_ORIGINAL_LMDB_FRAME_UNCHANGED')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        C.need(I.R.frame(os.fstat(fd))==I.R.frame(before),'ACTUAL_NATIVE_FD_BEFORE_ORIGINAL_READER')
        raw=native.read(pointer)  # Actual original LMDB payload SHA and total_atoms guards.
        mol,z,xyz=native.graph(raw)
        C.need(len(z)==pointer['total_atoms'] and I.R.frame(os.fstat(fd))==I.R.frame(before)==I.R.frame(p.lstat()),'NATIVE_FRAME_AND_ATOM_COUNT_STABLE')
        return mol,z,xyz
    finally:os.close(fd)


def physical_row(row,declared,check):
    ref=C.reference({'path':row['source_path'],'bytes':row['source_bytes'],'sha256':row['source_sha256']})
    index=row['source_row_index'];C.need(type(index) is int and index>=0,'EXACT_ORIGINAL_PHYSICAL_ROW_INDEX')
    with source_fd(ref,declared,check) as (_,fd,_):
        if row['source_format']=='reproduction_json_gz':
            with os.fdopen(os.dup(fd),'rb') as raw:
                with gzip.GzipFile(fileobj=raw,mode='rb') as stream:
                    data=stream.read(I.ROW_CAP+1);C.need(len(data)<=I.ROW_CAP and stream.read(1)==b'','FULL_PACKET_GZIP_EOF_CRC_AND_CAP')
            packet=json.loads(data);C.need(row['source_member']=='conformers' and packet['summary']['molecule_id']==row['molecule_id'],'EXACT_ORIGINAL_PACKET_MEMBER_AND_MID')
            result=packet['conformers'][index]
        elif row['source_format']=='parquet':
            import pyarrow.parquet as pq
            packet=None;result=None;offset=0
            with os.fdopen(os.dup(fd),'rb') as raw:
                p=pq.ParquetFile(raw)
                try:
                    groups=[];group_offset=0
                    for group in range(p.num_row_groups):
                        size=p.metadata.row_group(group).num_rows
                        if group_offset<=index<group_offset+size:
                            groups=[group];offset=group_offset;break
                        group_offset+=size
                    C.need(groups,'EXACT_ORIGINAL_PARQUET_PHYSICAL_ROW_GROUP')
                    for batch in p.iter_batches(batch_size=I.BATCH_ROWS,row_groups=groups,use_threads=False):
                        check();C.need(batch.nbytes<=I.ROW_CAP,'PHYSICAL_SOURCE_BATCH_NO_TRUNCATION')
                        if offset<=index<offset+len(batch):result=batch.slice(index-offset,1).to_pylist()[0];break
                        offset+=len(batch)
                finally:p.close()
            C.need(result is not None,'EXACT_PHYSICAL_ROW_EXISTS')
        else:raise ValueError('UNSUPPORTED_PHYSICAL_FORMAT_NO_PICKLE_FALLBACK')
    C.need(result['molecule_id']==row['molecule_id'] and result['status']=='SUCCESS' and result['converged'] is True
        and result['source_record_id']==row['native_anchor_record_id'] and result['atom_order_sha256']==row['atom_order_sha256']
        and result['seed']==row['seed'],'EXACT_ORDINARY_SOURCE_ROW_STATUS_ATOM_ANCHOR_SEED')
    if row.get('original_sprime_conf_idx') is not None:
        C.need(result['sprime_conf_idx']==row['original_sprime_conf_idx'],'ORIGINAL_PHYSICAL_INDEX_NOT_KERNEL_RANK')
    else:
        C.need(packet is not None and result['sprime_conf_idx']==row['kernel_sprime_conf_idx']
            and result['candidate_id']==row['candidate_id'] and result['origin']==row['origin'],'EXACT_GENERATED_NATIVE_EVENT_ROW_BEFORE_CANONICAL_MAPPING')
    if row.get('geometry_sha256') is not None:C.need(result.get('geometry_sha256')==row['geometry_sha256'],'FROZEN_GENERATED_GEOMETRY_SHA')
    if row.get('once_ledger_path') is not None:
        ledger=C.reference({'path':row['once_ledger_path'],'bytes':row['once_ledger_bytes'],'sha256':row['once_ledger_sha256']})
        value=I.json_body(ledger,declared,check,8<<20)
        C.need(value['task_key']==row['task_key'] and value['molecule_id']==row['molecule_id'],'ACTUAL_ORIGINAL_ONCE_TASK_IDENTITY_NOT_NEW_CLAIM')
        C.need(value['schema'] in ('SPRIME_DISPATCH_INTENT_V3','SPRIME_PILOT_ATTEMPT_IMPORTED_V1','SPRIME_ONCE_ATTEMPT_STARTED_V1'),
            'ORIGINAL_ORDINARY_ATTEMPT_SCHEMA_NOT_N1_GENERATION')
        if value['schema']=='SPRIME_DISPATCH_INTENT_V3':
            from workflows.data_v1_final.conformers.formal_cpu_auto_v3.contract import KERNEL_SHA
            C.need(value['seed']==row['seed'] and value['kernel_sha256']==KERNEL_SHA,'EXACT_ORIGINAL_DISPATCH_KERNEL_AND_SEED')
    return result,packet


def hof_values(task,declared,check):
    from workflows.data_v1_final.conformers.statistics_v1 import profile_common as PC
    owner=task['canonical_HOF_owner'];result={};observations=[]
    if owner is None:return {},[{'state':'UNKNOWN_CURRENT_CANONICAL_HOF_OWNER'}]
    targets={r['record_id']:dict(r,**{k:owner[k] for k in ('attempt_id','job_id','task_id','lane')}) for r in task['records']}
    for ref in task['canonical_HOF_files']:
        selected={k:r for k,r in targets.items() if r['file_group']==ref['source_file_group'] and r['job_id']==ref['source_job_id']}
        if not selected:continue
        with source_fd(ref,declared,check):observed=PC.read_hof_file({'ref':ref,'owners':selected})
        C.need(not set(result)&set(observed['hof']),'NO_DUPLICATE_CANONICAL_HOF_OWNER_CELLS')
        result.update(observed['hof']);observations.append({k:v for k,v in observed.items() if k!='hof'})
    return result,observations
