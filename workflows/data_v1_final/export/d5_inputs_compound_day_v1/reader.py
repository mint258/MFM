"""Original native/packet readers plus explicit Root-accepted cache/native-Z IO."""
from __future__ import annotations
import gzip,hashlib,json,os,pathlib,struct
from workflows.data_v1_final.export.d5_inputs_builder_v1 import contract as C,io as I,reader as Original
source_fd=Original.source_fd;native_record=Original.native_record
SOURCE_FRAMES=Original.SOURCE_FRAMES;NATIVE_FRAMES=Original.NATIVE_FRAMES


def verified_atom_view(result,row,atomic_numbers):
    C.need(type(atomic_numbers) is list and atomic_numbers and all(type(z) is int and 0<z<=118 for z in atomic_numbers),'REAL_NATIVE_ATOMIC_SEQUENCE_REQUIRED')
    digest=hashlib.sha256(struct.pack('<'+'q'*len(atomic_numbers),*atomic_numbers)).hexdigest()
    C.need(digest==row['atom_order_sha256']==result['atom_order_sha256'],'ACTUAL_NATIVE_Z_EXACT_ORIGINAL_ATOM_ORDER_SHA')
    if result.get('atomic_numbers') is not None:C.need(result['atomic_numbers']==atomic_numbers,'EXISTING_PACKET_Z_MUST_EQUAL_NATIVE_SEQUENCE')
    else:
        C.need(row['source_format']=='parquet','ONLY_OLD_NATIVE_PARQUET_OMITTED_Z_LOCAL_VIEW')
        result=dict(result,atomic_numbers=list(atomic_numbers))
    return result

def physical_row(row,declared,check,*,atomic_numbers):
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
        C.need(value['schema'] in ('SPRIME_DISPATCH_INTENT_V3','SPRIME_PILOT_ATTEMPT_IMPORTED_V1','SPRIME_ONCE_ATTEMPT_STARTED_V1','SPRIME_HISTORICAL_ATTEMPT_IMPORTED_V3'),
            'ORIGINAL_ORDINARY_ATTEMPT_SCHEMA_NOT_N1_GENERATION')
        if value['schema']=='SPRIME_DISPATCH_INTENT_V3':
            from workflows.data_v1_final.conformers.formal_cpu_auto_v3.contract import KERNEL_SHA
            C.need(value['seed']==row['seed'] and value['kernel_sha256']==KERNEL_SHA,'EXACT_ORIGINAL_DISPATCH_KERNEL_AND_SEED')
    result=verified_atom_view(result,row,atomic_numbers)
    if row.get('once_ledger_path') is not None and value['schema']=='SPRIME_HISTORICAL_ATTEMPT_IMPORTED_V3':
        from workflows.data_v1_final.conformers.formal_cpu_auto_v3.contract import KERNEL_SHA
        C.need(value['science_result_observed'] is True and value['execution_resolution']=='DURABLE_PACKAGE_VALIDATED'
            and value['seed']==row['seed'] and value['kernel_sha256']==KERNEL_SHA
            and C.reference(value['package_reference'])==ref and value['new_scientific_attempt'] is False and value['new_seed'] is False,
            'HISTORICAL_IMPORTED_REAL_PACKAGE_KERNEL_SEED_NOT_A_NEW_ATTEMPT')
    return result,packet

def hof_values(task,declared,check):
    """One actual accepted postprocess packet, not a full label-file scan/MID."""
    from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.contract import validate_hof
    ref=task['accepted_postprocess_packet_reference']
    with source_fd(ref,declared,check) as (_,fd,_):
        with os.fdopen(os.dup(fd),'rb') as f:
            with gzip.GzipFile(fileobj=f,mode='rb') as stream:
                raw=stream.read(I.ROW_CAP+1);C.need(len(raw)<=I.ROW_CAP and stream.read(1)==b'','ACTUAL_ACCEPTED_CACHE_EOF_CRC_BOUND')
    v=json.loads(raw);cache=v['cache'];mid=task['molecule_id']
    C.need(v['molecule_id']==mid and v['status']=='DURABLE_READONLY_MOLECULE_RESULT' and v['common'] is True
        and v['runtime']['job_id']==task['accepted_postprocess_job_id'] and v['new_UFF_calls']==v['new_QM_calls']==0
        and v['production_once_written'] is False and v['d7']['status']=='D7_MOLECULE_PROFILE_COMPLETE',
        'EXACT_ACTUAL_C0_POSTPROCESS_MOLECULE_NOT_UNRELATED_GEOMETRY_CACHE')
    source={r['record_id']:r for r in cache['source_records']};records={r['record_id']:r for r in task['records']}
    C.need(len(source)==len(cache['source_records'])==len(records)==task['expected_PM7_N'] and set(source)==set(records)
        and all(all(source[k].get(n)==x for n,x in records[k].items()) for k in records),
        'ACCEPTED_CACHE_EXACT_ALL_NATIVE_RECORD_POINTERS_NO_ROW_ASSOCIATION_GUESS')
    values=cache['hof_by_record'];C.need(set(values)==set(records) and values==v['d7']['hof_by_record'],'FULL_SAME_CANONICAL_HOF_RECORD_DOMAIN')
    for r in values.values():validate_hof(r)
    return values,[{'state':'ACTUAL_ROOT_ACCEPTED_POSTPROCESS_C0_HOF_REUSE','packet_reference':ref,
        'postprocess_entry_reference':task['accepted_postprocess_entry_reference'],'original_scalar_reader_and_values_unchanged':True}]


class ChildEvidence:
    """Exact original JSONL/staging records, indexed once per actual source SHA."""
    def __init__(self,path):
        import sqlite3
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE sources(path TEXT PRIMARY KEY,bytes INTEGER,sha TEXT,kind TEXT)')
        self.db.execute('CREATE TABLE records(path TEXT,rid TEXT,value BLOB,PRIMARY KEY(path,rid))')
    def load(self,ref,kind,declared,check,pprime=None):
        ref=C.reference(ref);prior=self.db.execute('SELECT bytes,sha,kind FROM sources WHERE path=?',(ref['path'],)).fetchone()
        if prior is not None:
            C.need(prior==(ref['bytes'],ref['sha256'],kind),'EXACT_CHILD_SOURCE_INDEX_REF_AND_FORMAT');return
        from .core import encode
        def records():
            if kind=='pairs':yield from I.jsonl(ref,declared,check)
            else:
                with I.held(ref,declared,check) as (_,fd,_):
                    with os.fdopen(os.dup(fd),'rb') as f:
                        for raw in f:
                            check();C.need(0<len(raw)<=I.ROW_CAP,'FULL_ORIGINAL_STAGING_ROW_BOUND');yield pprime.read_staging(raw)
        for row in records():
            check();C.need(type(row['record_id']) is str and row['record_id'],'ORIGINAL_CHILD_NATIVE_RECORD_ID')
            self.db.execute('INSERT INTO records VALUES(?,?,?)',(ref['path'],row['record_id'],encode(row)))
        self.db.execute('INSERT INTO sources VALUES(?,?,?,?)',(ref['path'],ref['bytes'],ref['sha256'],kind));self.db.commit()
    def rows(self,ref,rid,kind,declared,check,pprime=None):
        self.load(ref,kind,declared,check,pprime)
        from .core import decode
        for (raw,) in self.db.execute('SELECT value FROM records WHERE path=? AND rid=?',(ref['path'],rid)):
            check();yield decode(raw)
    def pair_rows(self,ref,rid,declared,check):return self.rows(ref,rid,'pairs',declared,check)
    def staging_rows(self,ref,rid,declared,check,pprime):return self.rows(ref,rid,'staging',declared,check,pprime)
    def close(self):self.db.close()
