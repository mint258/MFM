"""Fresh closed candidate delta from actual177 diagnostics; no chemistry or old-data writes."""
import argparse
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import struct
import traceback
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.guard import Guard
from ..pubchem_alpha_technical_unknown_audit_v1.scan import frame
from ..pubchem_closed500_bulk_v2 import schema as original
from .runtime import VERSION,admit,actual_parent,read
from .records import initialize,convert


def source(plan):
    ref=plan['native_diagnostic_receipt_reference'];d=read(ref);review=read(plan['native_diagnostic_actual_reference'])
    Q.need(review['schema']=='ROOT_ALPHA_GENERIC_UNKNOWN_NATIVE_DIAGNOSTIC_ACTUAL_ACCEPTANCE_V1'
        and review['status']=='APPROVED_TECHNICAL_SHARED_LIBRARY_DIAGNOSTIC_3642' and review['reviewer']=='root'
        and review['producer_receipt_reference']==ref and review['diagnostic_rows']==3642
        and review['exact_non_generic_match_rows']==3642 and review['raw_graph_X_key_FP_policy_unchanged'] is True
        and review['original_UNKNOWN_rows_preserved']==46201 and review['pool_minCID_baseline_changed'] is False
        and review['scientific_population_recovery_accepted'] is False,'Actual technical diagnostic review, not prior population adoption')
    parent=actual_parent(review)
    Q.need(str(parent['JobIDRaw'])=='1885177' and d['schema']=='PUBCHEM_ALPHA_GENERIC_UNKNOWN_DIAGNOSTIC_PRODUCER_V1'
        and d['profile_admission']['job_id']=='1885177' and d['profile_admission']['uid']==1264
        and d['diagnostic_counts']=={'REPAIRED_CANDIDATE_NON_GENERIC_EXACT':3642}
        and d['source_original_UNKNOWN_rows']==46201 and d['original_UNKNOWNs_modified']==0
        and d['pool_minCID_baseline_or_source_scope_changed'] is False
        and d['scientific_acceptance'] is False and d['DATA']==review['producer_closed_DATA_SHA_reference'],
        'Exact actual3642 original diagnostic output and full old UNKNOWN retention')
    read(review['shared_library119_actual_review_reference'])
    Q.need(d['DATA']['rows']==3642,'Complete exact3642 DATA scope')
    return d['DATA']


def execute(plan,out,guard):
    import pyarrow as pa
    import pyarrow.parquet as pq
    data_ref=source(plan);path=Path(data_ref['path']);before=frame(path.lstat())
    expected=original.original_schema().append(pa.field('cid',pa.int64())).append(pa.field('source_fragment_id',pa.string()))
    candidate_path=out/'recovery_delta_candidates.parquet';aliases_path=out/'recovery_delta_aliases.parquet'
    lineage_path=out/'recovery_source_lineage.DATA.jsonl'
    directory=out/'workers';directory.mkdir();ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
    digest=hashlib.sha256();seen_cids=set();seen_ordinals=set();seen_floats=[];aliases=[];buffer=[];n=offset=0;pending=deque();worker_rows=Counter()
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream, \
         pq.ParquetWriter(candidate_path,expected,compression='zstd') as writer, lineage_path.open('xb') as lineage, \
         ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(barrier,str(directory))) as pool:
        Q.need(frame(os.fstat(stream.fileno()))==before,'Exact current opened native DATA frame')
        def drain():
            nonlocal n,buffer
            row,alias,link=pending.popleft().result()
            Q.need(set(row)==set(expected.names) and row['cid'] not in seen_cids and row['ordinal'] not in seen_ordinals,
                'Every recovered positive CID/source ordinal exactly once; full-key duplicates remain allowed')
            seen_cids.add(row['cid']);seen_ordinals.add(row['ordinal'])
            worker_rows[link['materializer_worker_pid']]+=1
            link['delta_Parquet_physical_row_0based']=n;lineage.write(Q.canonical(link)+b'\n');aliases.append(alias)
            seen_floats.append(link['binary64_features_hex']);buffer.append(row);n+=1
            if len(buffer)==256:writer.write_table(pa.Table.from_pylist(buffer,schema=expected),row_group_size=256);buffer=[]
            if n%256==0:guard.check()
        for line,raw in enumerate(stream,1):
            Q.need(raw.endswith(b'\n'),'Complete original native DATA line')
            digest.update(raw);pending.append(pool.submit(convert,raw,data_ref,line,offset));offset+=len(raw)
            if len(pending)>=32:drain()
        while pending:drain()
        if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=expected),row_group_size=256)
        lineage.flush();os.fsync(lineage.fileno())
        Q.need(frame(os.fstat(stream.fileno()))==before==frame(path.lstat()) and offset==data_ref['bytes']==before['st_size']
            and digest.hexdigest()==data_ref['sha256'] and n==3642,'Fresh full native282MB SHA/frame and exact per-row3642 validation')
    alias_schema=pa.schema([('cid',pa.int64()),('full_key',pa.string()),('source_ordinal',pa.int64()),('source_fragment_id',pa.string())])
    pq.write_table(pa.Table.from_pylist(aliases,schema=alias_schema),aliases_path,compression='zstd')
    candidates=pq.ParquetFile(candidate_path)
    Q.need(candidates.metadata.num_rows==pq.ParquetFile(aliases_path).metadata.num_rows==3642
        and candidates.schema_arrow.equals(expected,check_metadata=True),'Actual typed candidate/alias output schema and row census')
    i=0
    for batch in candidates.iter_batches(columns=['cid',*original.FLOAT_FEATURES],batch_size=256):
        for row in batch.to_pylist():
            Q.need({k:struct.pack('>d',row[k]).hex() for k in original.FLOAT_FEATURES}==seen_floats[i],
                'All three recovered F64 values preserved bitwise in actual Parquet readback')
            i+=1
    candidates.close();Q.need(i==3642,'Complete F64 readback')
    workers=[Q.reference(p) for p in sorted(directory.glob('worker_*.json'))]
    Q.need(len(workers)==16,'All sixteen actual metadata/typed-delta workers')
    return dict(schema='PUBCHEM_GENERIC_RECOVERY_CANDIDATE_DELTA_V1',population_version=VERSION,candidate_rows=3642,
        candidates=dict(Q.reference(candidate_path),rows=3642),aliases=dict(Q.reference(aliases_path),rows=3642),
        source_lineage=dict(Q.reference(lineage_path),rows=3642),source_native_DATA_reference=data_ref,
        source_native_DATA_fresh_full_SHA_verified=True,source_native_DATA_current_frame=before,
        actual_worker_proofs=workers,actual_materializer_rows_by_pid=dict(worker_rows),
        all_per_row_native_strict_statuses_verified=True,all_recovered_F64_readback_bits_equal=True,
        original_rows_modified=0,original_UNKNOWN_rows_preserved=46201,other42502_plus57_chemistry_attempted=False,
        old_typed_or_old_pool_or_old_baseline_bodies_opened=False,new_chemistry_calls=0,
        fullkey_internal_duplicates_not_removed_yet=True,population_materialized=False,scientific_acceptance=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path)
    p.add_argument('--startup-proof',required=True,type=Path);a=p.parse_args();plan=Q.load(a.plan);proof=Q.load(a.startup_proof)
    authority=admit(plan,proof,a.plan,a.startup_proof,'PUBCHEM_ALPHA_GENERIC_RECOVERY_DELTA_PLAN_V1','pubchem_alpha_generic_recovery_delta_v1')
    Q.need(plan['workers']==16,'Sixteen effective metadata workers')
    refs=proof['request']['source_references']
    Q.need(Q.reference(original.__file__) in refs,'Exact borrowed original Arrow schema source')
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False);result=execute(plan,out,guard)
        Q.write(out/'receipt.json',dict(schema='PUBCHEM_GENERIC_RECOVERY_DELTA_PRODUCER_V1',
            status='CANDIDATE_DELTA_CLOSED_PENDING_ROOT_ACTUAL_C0',population_version=VERSION,
            plan_reference=Q.reference(a.plan),startup_proof_reference=Q.reference(a.startup_proof),profile_admission=authority,
            native_diagnostic_receipt_reference=plan['native_diagnostic_receipt_reference'],
            native_diagnostic_actual_reference=plan['native_diagnostic_actual_reference'],result=result,
            old_pool_minCID_baseline_or_original_UNKNOWN_changed=False,population_recovery_accepted=False,
            actual_parent_C0_pending_root_readback=True,runtime=guard.receipt()))
    except BaseException as exc:
        if out.is_dir():Q.write(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),
            partials_retained=True,old_sources_or_population_changed=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
