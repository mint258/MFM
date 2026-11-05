"""Current fill pairs, original NoInvoke/input hashes, original physical once."""
import hashlib,json,pathlib
from . import contract as C
from .source_io import SourceIO
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as Original,io as I
q=Original.q
_hash_closures=Original._hash_closures


def build(plan,proof,out,b,budget,store):
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    h=C.meta(plan['_active_shard_header_reference']);scope=b['fill_scope'];component=h['component_index']
    C.need(h['schema']=='PPRIME_FILL_FIXED_RANDOM_COMPONENT_V1' and h['tasks_reference']==scope['tables']['tasks'],'EXACT_CURRENT_CLOSED_FILL_COMPONENT')
    reader=SourceIO(plan,b,budget);folder=pathlib.Path(out)/'prepare';folder.mkdir();path=folder/'prepared.duckdb'
    db=duckdb.connect(str(path));db.execute('SET threads=16');db.execute('CREATE TABLE pairs(rid VARCHAR PRIMARY KEY,mid VARCHAR,rank BIGINT,pair BLOB,hashes BLOB)')
    audit_rows=[];consumed=[];selected_mids=set();count=0
    try:
        task_path=reader.hold(h['tasks_reference'])
        cursor=db.cursor();cursor.execute('SELECT * FROM read_parquet('+q(task_path)+') WHERE component_index=? ORDER BY molecule_id,random_order_rank',[component])
        names=[v[0]for v in cursor.description]
        while rows:=cursor.fetchmany(128):
            for values in rows:
                row=dict(zip(names,values));pair,audit=reader.pair(row)
                key=C.record_once_key(pair,plan['original_protocol_reference']);claim=C.ledger(plan)/'physical_records_v1'/(key+'.json')
                if claim.exists():
                    prior=C.meta(C.Q.pin(claim))
                    C.need(prior['record_once_key']==key and prior['record_id']==pair['record_id'] and prior['original_protocol_reference']==plan['original_protocol_reference'],'ACTUAL_EXISTING_PHYSICAL_CLAIM_NO_RETRY')
                    consumed.append(dict(record_id=pair['record_id'],physical_once_key=key,claim_reference=C.Q.pin(claim),status='CONSUMED_ORIGINAL_PHYSICAL_KEY_NO_REINVOKE'))
                    continue
                db.execute('INSERT INTO pairs VALUES(?,?,?,?,NULL)',[pair['record_id'],pair['molecule_id'],pair['random_order_rank'],C.O.canonical(pair)])
                audit_rows.append(audit);selected_mids.add(pair['molecule_id']);count+=1
        cursor.close();C.need(count+len(consumed)==h['conformer_records'] and count<=C.MAX_RECORDS,'ALL_ASSIGNED_FIRST2_REMAINING_OR_ALREADY_CONSUMED')
        selected=[dict(record_id=r['record_id'],file_group=r['legacy_engine_file_group'],size_stratum=r['size_stratum'])for r in audit_rows if r['selected']]
        selected_ids={r['record_id']for r in selected}
        for r in audit_rows:r['retain_all_twelve_raw']=r['record_id']in selected_ids
        schema=pa.schema([('record_id',pa.string()),('file_group',pa.int64()),('size_stratum',pa.string())]);sink=pa.BufferOutputStream()
        pq.write_table(pa.Table.from_pylist(selected,schema=schema),sink,compression='zstd')
        selected_ref=store.write(folder/'audit_selected.parquet',sink.getvalue().to_pybytes())
        audit=store.json(folder/'audit_membership.json',dict(schema='WP5_STRATIFIED_RECORD_AUDIT_V1',status='AUDIT_MEMBERSHIP_CLOSED',selected_records=dict(selected_ref,rows=len(selected)),seed=20261010,audit_policy=plan['retention_policy_reference'],scope='same original stable physical threshold100/10000; original/fill namespaces retained'))
        source_audit=store.json(folder/'source_audit.DATA.json',audit_rows)
        consumed_ref=store.json(folder/'consumed_prior.DATA.json',consumed)
        # No pilot replay: it is already in the entirely anti-joined old-ready
        # set. Its existing closed receipt is reused as provenance, never rerun.
        reuse=plan['original_closed_pilot_reuse_reference'];r=C.meta(reuse)
        C.need(r['records']==2000 and r['reinvocations']==0,'EXISTING_CLOSED_ORIGINAL2000_REUSE_AUTHORITY')
        software=C.P.software_original_specs(b['context'])
        if not b.get('_assets_verified'):
            checked=[]
            for ref in b['context']['execution_asset_references']:
                if ref['path']in software:checked.append(I.Preparation.hash_software_original(C.P.triple(ref),software[ref['path']],budget))
                else:reader.hold(ref)
            C.need(len(checked)==14,'ORIGINAL_READONLY_SOFTWARE_WHITELIST14');b['_assets_verified']=True
        # Original hash_one reads the native graph, checks source bond graph and
        # atom order, adapts only coordinates, and compares all12 rendered inputs
        # inside original NoInvoke. No QM/diagnostic is dispatched here.
        cursor=db.cursor();cursor.execute('SELECT rid,pair FROM pairs ORDER BY mid,rank')
        while block:=cursor.fetchmany(128):
            for rid,hashed in Original.hash_block(block,plan,proof,b,audit,out,budget):
                db.execute('UPDATE pairs SET hashes=? WHERE rid=?',[C.O.canonical(hashed),rid])
        cursor.close();C.need(db.execute('SELECT count(*) FROM pairs WHERE hashes IS NULL').fetchone()[0]==0,'ORIGINAL_ALL12_INPUT_HASHES_CLOSED')
        db.execute('CHECKPOINT');db.close();db=None;ref=I.pin(path,[folder])
        header=store.json(folder/'prepared_generation_header.json',dict(schema='PPRIME_FORMAL_READY_PREFIX_INPUT_HEADER_V1',records=count,MIDs=len(selected_mids),index_reference=ref,
          audit_membership_reference=audit,source_audit_reference=source_audit,pilot_reuse_reference=reuse,
          additional_consumed_physical_records_not_retried=len(consumed),consumed_prior_reference=consumed_ref,
          all_first2_original_seed=20261025,native_invokes=0,final_Common=False,fill_scope_reference=b['fill_scope_reference']))
        return dict(header=header,index=ref,audit=audit,source_audit=source_audit,records=count,MIDs=len(selected_mids),reuse=reuse,pending_MIDs=0)
    finally:
        if db is not None:db.close()
        reader.close()


def close_inputs():return Original.close_inputs()