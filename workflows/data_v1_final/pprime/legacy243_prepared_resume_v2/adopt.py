"""CPU-only verification of closed inputs; no preparation or native invocation."""
import hashlib,json,pathlib
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as I
from workflows.expansion.common_molecular_fp_main_v1.io import Body
from . import contract as C

def build(plan,proof,out,b,budget,store):
    import duckdb
    a=b['adoption'];h=a['header'];refs=plan['data_references']
    # Original preparation hashed all execution assets. Revalidate those exact
    # frozen assets here without initializing an engine or rendering new inputs.
    software=C.P.software_original_specs(b['context']);software_checks=[]
    for ref in b['context']['execution_asset_references']:
        if ref['path'] in software:
            software_checks.append(I.Preparation.hash_software_original(C.P.triple(ref),software[ref['path']],budget))
        else:
            body=Body(C.P.triple(ref),budget)
            try:body.check()
            finally:body.close()
    C.need(len(software_checks)==14,'ALL14_ORIGINAL_FROZEN_EXECUTION_SOFTWARE_REVALIDATED')
    # The original audit Parquet is consumed downstream by the unchanged
    # initializer. Its scientific membership is never resampled here.
    audit_selected=C.P.triple(a['audit']['selected_records'])
    with I.I.held(audit_selected,[C.OLD_OUTPUT],refs):budget.check(False)
    closed_raw=I.body(a['authority']['closed_record_index_reference'],refs,budget)
    closed={}
    for line in closed_raw.splitlines():
        row=json.loads(line);rid=row['record_id'];C.need(rid not in closed,'UNIQUE_OLD_CLOSED_RECORD_INDEX')
        closed[rid]=row
    C.need(len(closed)==10,'EXACT10_REAL_CLOSED_RECORDS_NOT_UNKNOWN_PROMOTION')
    consumed=[];matched=set();closed_returns=0
    # Original held verifies whole SHA before DuckDB opens the immutable path,
    # and retains the same FD/frame through the entire read-only DB traversal.
    with I.I.held(h['index_reference'],[C.OLD_OUTPUT/'prepare'],refs):
        db=duckdb.connect(h['index_reference']['path'],read_only=True)
        try:
            C.need(db.execute('SELECT count(*),count(DISTINCT rid),count(DISTINCT mid) FROM pairs').fetchone()==(100000,100000,50000),
              'EXACT_CLOSED100K_UNIQUE_RECORDS50K_MIDS')
            C.need(db.execute('SELECT count(*) FROM (SELECT mid FROM pairs GROUP BY mid HAVING count(*)<>2 OR min(rank)<>0 OR max(rank)<>1)').fetchone()[0]==0,
              'EXACT_ORIGINAL_TWO_RANKS_PER_MID')
            cursor=db.cursor();cursor.execute('SELECT rid,mid,rank,pair,hashes FROM pairs ORDER BY mid,rank')
            while rows:=cursor.fetchmany(128):
                budget.check(False)
                for rid,mid,rank,blob,hblob in rows:
                    pair=json.loads(bytes(blob));hashes=json.loads(bytes(hblob))
                    C.need(pair['record_id']==hashes['record_id']==rid and pair['molecule_id']==mid
                      and pair['random_order_rank']==rank and rank in (0,1)
                      and hashlib.sha256(C.O.canonical(pair)).hexdigest()==hashes['original_pair_sha256'],
                      'CLOSED_PAIR_ROW_IDENTITY_AND_ORIGINAL_HASH')
                    key=C.record_once_key(pair,plan['original_protocol_reference'])
                    path=C.ledger(plan)/'physical_records_v1'/(key+'.json')
                    if not path.exists():continue
                    ref=C.Q.pin(path);claim=C.meta(ref)
                    C.need(claim['record_once_key']==key and claim['record_id']==rid
                      and claim['pair_sha256']==hashes['original_pair_sha256'],'EVERY_EXISTING_PHYSICAL_CLAIM_INPUT_BINDING')
                    if str(claim['job_id'])!='4525243':continue
                    C.need(claim['uid']==1278 and claim['prepared2000_reference']==C.HEADER
                      and claim['original_protocol_reference']==plan['original_protocol_reference'],
                      'OLD243_REAL_CONSUMED_CLAIM_NOT_NEW_PARENT')
                    item={'record_id':rid,'record_once_key':key,'claim_reference':ref,'state':'UNKNOWN_CONSUMED_NO_RETRY'}
                    if rid in closed:
                        row=closed[rid]
                        C.need(row['terminal_reference']['path']==str(C.OLD_OUTPUT/'records'/key/'finished.json'),
                          'EXACT_ORIGINAL_RECORD_TERMINAL_OUTPUT_PATH')
                        terminal=I.value(row['terminal_reference'],[row['terminal_reference']],budget)
                        C.need(row['physical_once_key']==key and terminal['record_id']==rid and terminal['claim_reference']==ref
                          and terminal['technical_record_complete'] is True and terminal['native_return_count']==12
                          and terminal['UNKNOWN_attempts_retained'] is False,'ORIGINAL10_REAL_TWELVE_RETURN_TERMINALS')
                        item.update(state='CLOSED_TWELVE_RETURN_RECORD_NOT_REINVOKED',terminal_reference=row['terminal_reference'])
                        matched.add(rid);closed_returns+=12
                    consumed.append(item)
            cursor.close()
        finally:db.close()
    C.need(len(consumed)==len({v['record_once_key'] for v in consumed})==a['receipt']['dispatched_records']==16
      and matched==set(closed) and closed_returns==a['receipt']['observed_native_returns']==120
      and {v['record_id'] for v in consumed if v['state']=='UNKNOWN_CONSUMED_NO_RETRY'}
          =={v['record_id'] for v in a['receipt']['failures']},
      'ALL16_CONSUMED10_CLOSED6_UNKNOWN_PRESERVED_WITHOUT_RETRY')
    # Original execute also re-verifies and parses this DATA before dispatch.
    with I.I.held(h['source_audit_reference'],[C.OLD_OUTPUT],refs):budget.check(False)
    manifest=store.json(out/'prior_consumed_claims_CPU_manifest.json',{
      'schema':'PPRIME_ACTUAL4525243_CONSUMED_CLAIMS_CPU_MANIFEST_V1','original_parent_actual':a['actual'],
      'authority_reference':plan['prepared_resume_authority_reference'],'prepared_header_reference':C.HEADER,
      'actual_verifying_job_id':str(proof['job_id']),'records':consumed,'closed_records':10,
      'UNKNOWN_consumed_no_retry':6,'observed_native_returns_in_closed_records':120,
      'prior_Parent_completed_zero':False,'automatic_retry':False,'scientific_PASS':False})
    store.json(out/'closed_preparation_adoption.json',{'schema':'PPRIME_CLOSED_PREPARATION_ADOPTED_V1',
      'prepared_header_reference':C.HEADER,'prior_consumed_manifest_reference':manifest,
      'index_whole_SHA_CPU_verified':True,'original_execution_assets_verified':True,
      'preparation_reexecuted':False,'native_initializations_or_invocations_in_adopter':0,
      'old_failed_parent_preserved':True,'final_Common_or_training_admission':False})
    budget.forecast_records=h['records']
    return {'header':C.HEADER,'index':h['index_reference'],'audit':h['audit_membership_reference'],
      'source_audit':h['source_audit_reference'],'records':h['records'],'MIDs':h['MIDs'],
      'reuse':h['pilot_reuse_reference'],'pending_MIDs':h['N1_or_unavailable_pending_MIDs']}
