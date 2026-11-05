"""Direct-Lustre IO acceptance; same original all-pairs/hash verifier math."""
import csv,io,pathlib
from . import io_adapter as A
from workflows.data_v1_final.pprime.current_prepared_component_parentstate_v3.authority import validate_hashes,observed_parent_state
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import io as I


def verify_component(header_ref,actual_preparation,plan,proof,budget):
    """CPU consumer seam replacing only old PREP-pool metadata assumptions.

    actual_preparation is the real native-accounting/registration handoff, not
    a future C0 claim. No QM or independent scientific test suite is performed.
    """
    h=A.meta(header_ref);a=actual_preparation
    raw=A.small(a['raw_sacct_reference']).decode();rows=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|')if r['JobIDRaw']==str(a['job_id'])]
    A.need(len(rows)==1 and rows[0]['UID']=='1278'and rows[0]['AllocCPUS']=='16'and rows[0]['NodeList']=='compute-0-18'
      and observed_parent_state(rows[0]['State'],rows[0]['ExitCode'])==a['observed_state'],'REAL_NATIVE_PREPARATION_PARENT_STATE_NOT_FUTURE_C0')
    receipt=A.meta(a['component_receipt_reference']);source3=A.meta(receipt['actual_source3_reference'])
    A.need(source3['tests_run']==3 and all(source3[k]==0 for k in('failures','errors','skips','expected_failures','unexpected_successes')),'SAME_ORIGINAL_SOURCE3')
    A.need(receipt['schema']=='PPRIME_CLOSED_SCOPE_REUSE_COMPONENT_RECEIPT_V1'and receipt['prepared_header_reference']==header_ref
      and str(receipt['actual_job_id'])==str(a['job_id'])and receipt['new_QM_UFF_calls']==0 and not receipt['parent_C0_claimed']
      and len(receipt['input_hash_worker_closures'])==16 and all(v['native_invokes']==0 and v['original_engine_closed']for v in receipt['input_hash_worker_closures']),'REAL_CLOSED_COMPONENT_AND_ORIGINAL_WORKER_CLOSURES')
    A.need(h['schema']=='PPRIME_CPU_CLOSED_ASSIGNED_PAIRS_HEADER_V2'and h['direct_Lustre_publication']and h['native_invokes']==0 and not h['production_once_written']
      and h['original_protocol_reference']==plan['original_protocol_reference']and h['source_context_reference']==plan['source_context_reference'],'UNCHANGED_PREPARED_PROTOCOL_SOURCE')
    publication=A.meta(h['publication_manifest_reference'])
    A.need(publication['schema']=='PPRIME_CLOSED_DEVSHM_TO_LUSTRE_COMPONENT_V1'and publication['all_file_SHA_bytes_equal']and not publication['uses_Main_PREP_pool']
      and str(publication['actual_preparation_job_id'])==str(a['job_id']),'TRUTHFUL_DIRECT_LUSTRE_COPY_NO_FAKE_POOL')
    for entry in publication['entries']:
        ref=entry['target_reference'];A.need(I.pin(ref['path'],[pathlib.Path(ref['path']).parent])==ref and ref['bytes']==entry['origin_reference']['bytes']and ref['sha256']==entry['origin_reference']['sha256'],'ORIGINAL_CLOSED_PUBLICATION_WHOLE_SHA_BYTES')
        budget.check()
    import duckdb
    db=duckdb.connect(h['index_reference']['path'],read_only=True);count=0;mids=set();tasks=[t['name']for t in A.meta(plan['original_protocol_reference'])['tasks']]
    try:
        A.need([(r[0],r[1])for r in db.execute('DESCRIBE pairs').fetchall()]==[('rid','VARCHAR'),('mid','VARCHAR'),('rank','BIGINT'),('pair','BLOB'),('hashes','BLOB')],'ORIGINAL_PAIRS_SCHEMA')
        cur=db.execute('SELECT rid,mid,rank,pair,hashes FROM pairs ORDER BY mid,rank')
        import json
        while rows:=cur.fetchmany(128):
            for rid,mid,rank,pair,hashed in rows:
                pair=json.loads(bytes(pair));hashed=json.loads(bytes(hashed));A.need(pair['record_id']==rid and pair['molecule_id']==mid and pair['random_order_rank']==rank and rank in(0,1),'ORIGINAL_PREPARED_PHYSICAL_ID_AND_RANK')
                validate_hashes(pair,hashed,tasks);count+=1;mids.add(mid)
            budget.check()
        A.need(count==h['records']and len(mids)==h['MIDs'],'ORIGINAL_COMPONENT_CENSUS')
    finally:db.close()
    return dict(status='DIRECT_LUSTRE_PREPARED_COMPONENT_ACCEPTED_FOR_ORIGINAL_EXECUTOR',records=count,MIDs=len(mids),
      prepared_header_reference=header_ref,actual_preparation=a,new_QM_calls=0,production_once_ledger_changed=False,final_Common_or_training_release=False)