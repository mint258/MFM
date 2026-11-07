"""Independent all-role D27 typed coverage, original masks, TRAIN-only F64 leaves."""
import collections
import hashlib
import heapq
import json
import os
from pathlib import Path
import struct
import uuid
from ..common import load,reference,dump_new
from ..portable_sources_v1.transport import bind_plan,verify
from .inventory import need
from .inputs import N
from . import science
WORK={}


def initialize(plan,arrays,root,stop):
    import numpy as np
    import pyarrow as pa
    bind_plan(plan);pa.set_cpu_count(1);pa.set_io_thread_count(1)
    codec,calibration,support=science.load(plan)
    shape={'fit':('u1',(N,)),'owner':('u1',(N,32)),'role':('u1',(N,)),
        'atoms':('<u4',(N,)),'group':('<u2',(N,))}
    mapped={key:np.memmap(ref['path'],dtype=shape[key][0],mode='r',shape=shape[key][1])for key,ref in arrays.items()}
    fields=load(verify(plan['field_map_reference']));byid={f['field_id']:f for f in fields if f['task']in('D20','D3')}
    need(set(byid)==set(range(27))and not any(f['element_reference_eligible']for f in byid.values()),'Original D27 field scope required')
    WORK.update(plan=plan,arrays=mapped,root=Path(root),stop=stop,codec=codec,calibration=calibration,support=support,byid=byid)


def sidecar_frames():
    return {key:(Path(value.filename).stat().st_dev,Path(value.filename).stat().st_ino,Path(value.filename).stat().st_size,
        Path(value.filename).stat().st_mtime_ns,Path(value.filename).stat().st_ctime_ns)for key,value in WORK['arrays'].items()}


def check():
    need(not WORK['stop'].is_set(),'Shared actual Alpha resource stop; no new scientific group')


def part_rows(part,window):
    import pyarrow.parquet as pq
    path=verify(part['reference']);before=path.stat();digest=hashlib.sha256();count=0;previous=-1
    with pq.ParquetFile(path)as table:
        for batch in table.iter_batches(batch_size=64,use_threads=False):
            check()
            for row in batch.to_pylist():
                WORK['codec'].validate_row_buffers(row)
                need(WORK['codec'].row_signature(row)==row['view_sha256']and row['file_id']==window['source_reference']['file_id']
                    and window['physical_row_lo']<=row['physical_row']<window['physical_row_hi']and row['physical_row']>previous,
                    'Exact typed row signature, physical source and monotone part order required')
                previous=row['physical_row'];count+=1;digest.update(row['view_sha256']);yield row
    after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)and count==part['rows']
        and digest.hexdigest()==part['typed_stream_sha256'],'Whole source part frame/typed stream/row mass changed')


def group(item):
    g,scope=item;index=g['group_index'];base=WORK['root']/('group_%03d'%index);base.mkdir(exist_ok=True)
    closed=base/'manifest.json'
    if closed.exists():
        old=load(closed);need(old['scope_fingerprint']==scope and old['source_job_id']==g['source_job_id'],'Closed group scope mismatch')
        for ref in [old['coverage_ordinals'],*old['fields'].values()]:verify(ref)
        return reference(closed)
    directory=base/('attempt_'+uuid.uuid4().hex);directory.mkdir();handles={i:(directory/('field_%02d.f64'%i)).open('xb')for i in range(27)}
    before_sidecars=sidecar_frames()
    seen={'D20':set(),'D3':set()};leaves=collections.Counter();masks=collections.defaultdict(collections.Counter)
    hashes={i:hashlib.sha256()for i in range(27)};counts=collections.Counter();arr=WORK['arrays'];codec=WORK['codec']
    try:
        for window in g['windows']:
            check();actual=load(verify(window['window_reference']))
            need(actual['source_reference']==window['source_reference']and actual['parts']==window['parts']
                and actual['physical_row_lo']==window['physical_row_lo']and actual['physical_row_hi']==window['physical_row_hi']
                and actual['all_part_reopen_bits_verified']is True,'Exact original closed window metadata required')
            family=window['source_reference']['family'];streams=[part_rows(p,window)for p in window['parts']]
            try:
                for row in heapq.merge(*streams,key=lambda r:r['physical_row']):
                    i=row['record_ordinal'];need(0<=i<N and int(arr['group'][i])==index
                        and arr['owner'][i].tobytes()==row['owner_sha256']and int(arr['role'][i])==row['role_code'],
                        'Canonical exact owner tuple/ordinal/role/source-job binding required')
                    need(i not in seen[family],'Duplicate canonical D27 family row');seen[family].add(i)
                    entries=codec.unpack_entries(row,WORK['byid']);expected=list(range(20))if family=='D20'else list(range(20,27))
                    need(row['row_kind']=='task'and row['task_code']==(0 if family=='D20'else 1)
                        and sorted(e['field_id']for e in entries)==expected,'Every original D field exactly once per family record')
                    need(codec.B.compact.encode(i,row['task_code'],entries)==codec.binary_json_loads(row['compact_mask_json']),
                        'Full original source/new/review reasons and sparse leaf masks must match')
                    fit=bool(arr['fit'][i]);role='TRAIN'if fit else'FULL';counts['FIT_family_rows'if fit else'EXCLUDED_family_rows']+=1
                    for e in entries:
                        fid=e['field_id'];n=len(e['values_float64']);natoms=int(arr['atoms'][i])
                        shape_ok=(n==0 and e['atom_indices']in(None,[]))or(n==natoms and e['atom_indices']==list(range(natoms)))if fid==24 else n in(0,1)
                        need(shape_ok,'Original D scalar/atom observation cardinality required')
                        valid=WORK['calibration'].train_values(role,e['values_float64'],e['value_mask'])
                        raw=struct.pack('<'+'d'*len(valid),*valid);handles[fid].write(raw);leaves[fid]+=len(valid)
                        header=struct.pack('<QBHI',i,row['task_code'],fid,len(e['value_mask']))+role.encode()+bytes(e['value_mask'])
                        hashes[fid].update(header);hashes[fid].update(raw)
                        masks[fid]['records']+=1;masks[fid]['fit_records']+=fit
                        masks[fid]['source_ineligible_records']+=not any(e['source_value_mask'])
                        masks[fid]['newly_masked_records']+=any(a and not b for a,b in zip(e['source_value_mask'],e['value_mask']))
                        masks[fid]['final_masked_records']+=any(not keep for keep in e['value_mask'])
                        masks[fid]['review_records']+=bool(e['review_reasons'])
                        for name,key in [('source_reasons','source:'),('new_reasons','new:'),('review_reasons','review:')]:
                            for reason in sorted(set(e[name])):masks[fid][key+str(reason)]+=1
            finally:
                for stream in streams:stream.close()
        need(seen['D20']==seen['D3']and len(seen['D20'])==g['expected_records'],'Both D family canonical keys must equal the whole original logical group')
        for handle in handles.values():handle.flush();os.fsync(handle.fileno())
    finally:
        for handle in handles.values():handle.close()
    ordpath=directory/'coverage.u64'
    import numpy as np
    with ordpath.open('xb')as handle:
        np.asarray(sorted(seen['D20']),dtype='<u8').tofile(handle);handle.flush();os.fsync(handle.fileno())
    fields={str(fid):{**reference(directory/('field_%02d.f64'%fid)),'leaves':leaves[fid]}for fid in range(27)}
    need(all(ref['bytes']==8*ref['leaves']for ref in fields.values()),'All TRAIN valid F64 leaves must close exactly')
    need(sidecar_frames()==before_sidecars,'Immutable eligibility sidecars changed while reading')
    result={'schema':'PUBCHEM_D27_TYPED_COVERAGE_GROUP_V1','status':'COMPLETE_ALL_ORIGINAL_GROUP_D27_ROWS',
        'scope_fingerprint':scope,'source_job_id':g['source_job_id'],'group_index':index,'records':len(seen['D20']),
        'coverage_ordinals':reference(ordpath),'fields':fields,'field_mask_counts':{str(k):dict(v)for k,v in masks.items()},
        'field_input_sha256':{str(k):v.hexdigest()for k,v in hashes.items()},'record_counts':dict(counts),
        'observed_worker_pid':os.getpid(),'original_mask_and_float64_bits_preserved':True,'R_N_used_for_fit':False}
    dump_new(closed,result);return reference(closed)
