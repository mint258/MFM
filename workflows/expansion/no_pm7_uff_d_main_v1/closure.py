"""Read-only actual-terminal cache recovery and complete first2.5M coverage."""
import collections,concurrent.futures as cf,csv,io,json,math,multiprocessing as mp,os,pathlib,stat,sqlite3,struct
from . import contract as C,io as I,source as S
Q=C.Q
def terminal_parent(item):
    account=C.meta(item['accounting_reference']);raw=account['raw_sacct_reference'];Q.need(Q.pin(raw['path'])==raw,'ACTUAL_TERMINAL_RAW_SACCT_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(raw['path']).decode()),delimiter='|') if '.' not in r['JobIDRaw']]
    Q.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['endpoint']=='202.38.247.57:22' and account['uid']==1278
        and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and account['query_returncode']==0
        and account['failed_timeout_startup_cleanup_elapsed_retained'] is True,'MAIN_REAL_ACCOUNTING_NOT_ALPHA_OR_FUTURE')
    by={r['JobIDRaw']:r for r in rows};total=0
    Q.need(len(by)==len(rows)==len(account['parents']),'EXACT_TERMINAL_ACCOUNTING_PARENT_SET')
    for p in account['parents']:
        r=by[p['job_id']];Q.need(p['state']==r['State'] and p['exit_code']==r['ExitCode'] and p['elapsed_raw_seconds']==int(r['ElapsedRaw'])
            and p['alloc_cpus']==int(r['AllocCPUS']) and r['UID']=='1278' and p['node']==r['NodeList'],'EXACT_ACCOUNT_ROWS_INCLUDING_FAILURE_COST')
        total+=p['alloc_cpus']*p['elapsed_raw_seconds']
    Q.need(total==account['allocated_core_seconds'],'ALL_RELATED_ACTUAL_PARENT_COST_RETAINED')
    r=by[str(item['job_id'])];Q.need(r['State'].split()[0] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}
        and int(r['AllocCPUS'])==16,'PARENT_MUST_BE_ACTUALLY_TERMINAL_NO_ACTIVE_PACKET_READ')
    plan=C.meta(item['plan_reference']);proof=C.meta(item['startup_proof_reference'])
    Q.need(str(proof['job_id'])==str(item['job_id']) and proof['uid']==1278 and proof['request']['node']==r['NodeList']
        and item['plan_reference'] in proof['request']['source_references'] and proof['request']['scope_key']==C.key(plan['mode'])
        and plan['mode'] in ('compat','profile','full') and proof['request']['scope_parameters']==plan['scope_parameters'],
        'REAL_REGISTERED_NATIVE_PARENT_PLAN_PROOF_NOT_RETURN_STATE_INVENTION')
    return plan,proof,raw,int(r['AllocCPUS'])*int(r['ElapsedRaw'])
class ReuseLookup:
    def __init__(self,path):self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE closed(once_key TEXT PRIMARY KEY,row_json TEXT NOT NULL)')
    def add(self,row):self.db.execute('INSERT INTO closed VALUES(?,?)',(row['once_key'],C.canonical(row).decode()))
    def get(self,key):
        row=self.db.execute('SELECT row_json FROM closed WHERE once_key=?',(key,)).fetchone();return json.loads(row[0]) if row else None
    def close(self):self.db.commit();self.db.close()
def reuse_rows(snapshot,budget,out):
    result=ReuseLookup(out/'validated_reuse.sqlite')
    if snapshot is None:return result
    observed=I.Body(C.triple(snapshot['verified_parent_metadata_DATA_reference']),budget)
    observed.close()
    for part in snapshot['parts']:
        body=I.Body(C.triple(part['reference']),budget)
        try:
            for raw in body.stream:
                Q.need(len(raw)<=1<<20 and raw.endswith(b'\n'),'BOUNDED_CLOSED_REUSE_ROW');row=json.loads(raw)
                result.add(row)
            body.check()
        finally:body.close()
    result.db.commit();return result
def runs_list(header):
    if header.get('parts'):
        for ref in header['parts']:
            part=C.meta(ref)
            for row in part['runs']:yield row
    else:yield from header['runs']
def resume(plan,manifest,catalog,budget,out,store,proof):
    runs=C.meta(plan['prior_runs_reference']);parents={};refs=[];cost=0
    parent_journal=I.Writer(out/'verified_parent_metadata.DATA.jsonl',budget)
    for item in runs_list(runs):
        pp,parent_proof,raw,actual=terminal_parent(item);Q.need(pp['ranking_receipt_reference']==plan['ranking_receipt_reference']
            and C.fingerprint(C.meta(pp['kernel_catalog_reference']))==C.fingerprint(catalog),'SAME_FROZEN_SOURCE_SCIENCE_PARENTS')
        Q.need(str(item['job_id']) not in parents,'UNIQUE_TERMINAL_PARENT_JOBS');parents[str(item['job_id'])]=(pp,parent_proof)
        refs += [item['plan_reference'],item['startup_proof_reference'],item['accounting_reference'],raw];cost+=actual
        parent_journal.write({'job_id':str(item['job_id']),'plan_reference':item['plan_reference'],'startup_proof_reference':item['startup_proof_reference'],
            'accounting_reference':item['accounting_reference'],'raw_reference':raw,'actual_allocated_core_seconds':actual})
    parent_journal.close()
    selection=plan['resume_selection_mode'];lower,upper=plan['lower_inclusive'],plan['upper_exclusive'];domain=C.sha(C.canonical([plan['ranking_receipt_reference']['sha256'],C.fingerprint(catalog)]))
    writer=I.Writer(out/'reuse_index.DATA.jsonl',budget);counts={'CLOSED_PACKET':0,'CONSUMED_WITHOUT_VALIDATED_PACKET':0,'UNCLAIMED':0};checked=0
    try:
        for row in S.rows(manifest,selection,budget,lower,upper):
            budget.check(True);checked+=1;key=C.once(plan['ranking_receipt_reference']['sha256'],C.fingerprint(catalog),row)
            claim_path=C.CACHE/domain/'claims'/key[:2]/(key+'.json')
            if not claim_path.exists():counts['UNCLAIMED']+=1;continue
            claim_ref=Q.pin(claim_path);claim=C.meta(claim_ref);job=str(claim['job_id']);Q.need(job in parents,'CLAIM_PARENT_NOT_TERMINAL_OR_UNREVIEWED_HOLD_NO_PACKET_BODY')
            pp,parent_proof=parents[job];Q.need(claim['once_key']==key and claim['source_row_sha256']==row['source_row_sha256']
                and claim['startup_proof_reference']['path']==str(pathlib.Path(parent_proof['request']['startup_proof_path'])),'EXACT_SOURCE_KEY_AND_OLD_ACTUAL_PARENT_INTENT')
            root=C.CACHE/domain/key[:2]/key;packet_path=root/'packet.json.gz';value={'ordinal':row['ordinal'],'once_key':key,'claim_reference':claim_ref,'producer_job_id':job,
                'source_row_sha256':row['source_row_sha256'],'packet_reference':None,'state':'CONSUMED_WITHOUT_VALIDATED_PACKET','no_new_UFF_calls':True}
            if packet_path.is_file():
                actual_ref=I.seal_closed_output(packet_path,budget);packet=I.read_packet(actual_ref,budget)
                Q.need(packet['schema']=='NO_PM7_UFF_D_CACHE_PACKET_V1' and packet['once_key']==key and packet['producer_job_id']==job
                    and packet['claim_reference']==claim_ref and packet['source']==row and packet['recipe_fingerprint']==C.fingerprint(catalog),
                    'ACTUAL_WHOLE_SHA_GZIP_CRC_PACKET_SOURCE_AND_SCIENCE_CLOSURE')
                # No retry even for a valid UNKNOWN/partial packet. Original state stays.
                value.update(packet_reference=actual_ref,state='CLOSED_PACKET',original_packet_state=packet['state'])
            counts[value['state']]+=1;writer.write(value)
    finally:writer.close()
    return store.json(out/'reuse_snapshot.json',{'schema':'NO_PM7_UFF_D_CLOSED_CACHE_SNAPSHOT_V1','status':'ACTUAL_TERMINAL_CACHE_READBACK_COMPLETE_NO_UFF',
        'ranking_receipt_reference':plan['ranking_receipt_reference'],'recipe_fingerprint':C.fingerprint(catalog),'selection_mode':selection,
        'lower_inclusive':lower,'upper_exclusive':upper,'checked_source_molecules':checked,'counts':counts,
        'parts':[{'reference':writer.reference(),'lower_inclusive':lower,'upper_exclusive':upper}] if writer.rows else [],
        'actual_empty_reuse_index_reference':writer.reference() if not writer.rows else None,
        'parent_metadata_references':[plan['prior_runs_reference'],*runs.get('parts',[])],'verified_parent_metadata_DATA_reference':parent_journal.reference(),
        'job_id':str(proof['job_id']),'uid':1278,'node':proof['request']['node'],'startup_proof_reference':Q.pin(proof['request']['startup_proof_path']),
        'actual_prior_allocated_core_seconds_including_failures':cost,'no_new_UFF_QM_calls':True,'training_release':False})
def packet_structure(packet):
    """No new descriptor or geometry fit:check stored dtype/identity/order census."""
    issues=[];rows=packet['conformers'];ids=[r['conformer_id'] for r in rows];n=len(rows)
    if n>10 or ids!=list(range(n)) or len({r['geometry_sha256'] for r in rows})!=n:issues.append('GEOMETRY_COUNT_ID_OR_EXACT_SHA_ALIAS')
    orders=packet['orders']
    if set(orders)!={'fixed_random','energy','diversity'} or any(sorted(v)!=ids or any(type(x)is not int for x in v) for v in orders.values()):
        issues.append('ORIGINAL_THREE_ORDER_PERMUTATIONS_UNAVAILABLE_OR_INVALID')
    if packet.get('order_seed')!=C.SEED:issues.append('ORIGINAL_ORDER_SEED_UNAVAILABLE_OR_INVALID')
    z=packet.get('atomic_numbers',[])
    if any(type(a)is not int or not 1<=a<=118 for a in z):issues.append('ATOMIC_NUMBER_TABLE_INVALID');return issues
    atom_bytes=b''.join(struct.pack('<q',a) for a in z)
    if z and C.sha(atom_bytes)!=packet.get('atom_order_sha256'):issues.append('ATOM_ORDER_SHA_DIFFERS')
    for r in rows:
        xyz=r['coordinates']
        if len(xyz)!=len(z) or any(len(p)!=3 or any(type(v)is not float or not math.isfinite(v) for v in p) for p in xyz):
            issues.append('COORDINATE_FLOAT64_SHAPE_OR_FINITE');continue
        raw=b''.join(struct.pack('<d',v) for p in xyz for v in p)
        if C.sha(raw)!=r['coordinate_sha256'] or C.sha(atom_bytes+raw)!=r['geometry_sha256']:issues.append('COORDINATE_OR_GEOMETRY_SHA_DIFFERS')
    return sorted(set(issues))

def audit_result_journal(plan,budget,out,store,journal_ref):
    """After all UFF workers exit,apply the exact old mask/reference objects."""
    from . import families
    review,_=C.quality_reference(plan)
    if not review:return {'status':'ORIGINAL_MASK_AND_TRAIN_REFERENCE_NOT_YET_BOUND_FULL1P5_HOLD','DATA_reference':None,'DATA_bytes':0,'new_mask_stop_fields':[],
        'TRAIN_reference_applied':False,'full1p5_acceptance':False,'R_N_used_as_TRAIN':False}
    stats=collections.defaultdict(collections.Counter);pids=set();unknown=0;seen=set();pending=[]
    writer=I.Writer(out/'original_mask_review.DATA.jsonl',budget);body=I.Body(journal_ref,budget)
    pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=families.quality_init,initargs=(review,))
    def collect(future):
        report=future.result();pids.add(report['pid'])
        for item in report['items']:
            c=stats[str(item['field_id'])];c['records']+=1;c['source_valid_records']+=int(any(item['source_value_mask']))
            c['newly_masked_records']+=int(any(a and not b for a,b in zip(item['source_value_mask'],item['value_mask'])))
            for reason in set(item['source_reasons']):c['source:'+reason]+=1
            for reason in set(item['new_reasons']):c['new:'+reason]+=1
            for reason in set(item['review_reasons']):c['review:'+reason]+=1
            writer.write({'staged_mask_item':json.loads(I.staging_bytes(item))})
        for jump in report['jumps']:writer.write({'within_molecule_jump_review':jump})
    try:
        while raw:=body.stream.readline((8<<20)+1):
            budget.check(True);Q.need(raw.endswith(b'\n') and len(raw)<=8<<20,'COMPLETE_CURRENT_RESULT_JOURNAL_ROW')
            row=json.loads(raw);Q.need(row['once_key'] not in seen,'ONE_RESULT_PER_CURRENT_SELECTED_SOURCE');seen.add(row['once_key'])
            if row.get('packet_reference') is None:unknown+=1;continue
            packet=I.read_packet(row['packet_reference'],budget);Q.need(packet['once_key']==row['once_key'],'CURRENT_JOURNAL_PACKET_ID')
            pending.append(pool.submit(families.quality_packet,packet))
            if len(pending)>=32:collect(pending.pop(0))
        for future in pending:collect(future)
        body.check()
    finally:pool.shutdown(wait=True,cancel_futures=False);body.close();writer.close()
    stops=[fid for fid,s in stats.items() if s['newly_masked_records']/s['records']>.01]
    return {'status':'STOP_ORIGINAL_NEW_MASK_FRACTION_GT1PCT' if stops else 'ORIGINAL_PHYSICAL_MASK_AND_OPTIONAL_TRAIN_REFERENCE_RECORDED_NO_ACCEPTANCE',
        'DATA_reference':writer.reference(),'DATA_bytes':writer.bytes,'field_counts':dict(stats),'unknown_missing_packets':unknown,
        'new_mask_stop_fields':stops,'actual_quality_worker_pids':sorted(pids),'quality_phase_after_all_UFF_worker_exits':True,
        'TRAIN_reference_applied':bool(review.get('TRAIN_calibration_reference')),'R_N_used_as_TRAIN':False,'full1p5_acceptance':False}

def coverage(plan,manifest,catalog,budget,out,store):
    from . import families
    snapshot=C.meta(plan['reuse_snapshot_reference']);reuse=reuse_rows(snapshot,budget,out);counts={'R':0,'N':0};states={};confs=0;missing=0;aliases=0
    review,_=C.quality_reference(plan);stats=collections.defaultdict(collections.Counter);pending=[];pids=set();structure_unknown=0
    records=I.Writer(out/'coverage.DATA.jsonl',budget);quality=I.Writer(out/'original_masks_and_reference_reviews.DATA.jsonl',budget) if review else None
    pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=families.quality_init,initargs=(review,)) if review else None
    def collect(future):
        report=future.result();pids.add(report['pid'])
        for item in report['items']:
            c=stats[str(item['field_id'])];c['records']+=1;c['source_valid_records']+=int(any(item['source_value_mask']))
            c['newly_masked_records']+=int(any(a and not b for a,b in zip(item['source_value_mask'],item['value_mask'])))
            for reason in set(item['source_reasons']):c['source:'+reason]+=1
            for reason in set(item['new_reasons']):c['new:'+reason]+=1
            for reason in set(item['review_reasons']):c['review:'+reason]+=1
            # Original masks can expose an invalid NaN/Inf source leaf. Keep
            # its exact staging representation instead of JSON-null coercion.
            quality.write({'staged_mask_item':json.loads(I.staging_bytes(item))})
        for jump in report['jumps']:quality.write({'within_molecule_jump_review':jump})
    try:
        for source in S.rows(manifest,'full',budget,0,C.TARGET):
            budget.check(True);key=C.once(plan['ranking_receipt_reference']['sha256'],C.fingerprint(catalog),source);row=reuse.get(key);counts[source['stream']]+=1
            if row is None or row['packet_reference'] is None:
                missing+=1;records.write({'ordinal':source['ordinal'],'cid':source['cid'],'stream':source['stream'],'state':'UNCLAIMED_OR_UNRECOVERED_UNKNOWN','once_key':key});continue
            packet=I.read_packet(row['packet_reference'],budget);Q.need(packet['source']==source and packet['once_key']==key,'WHOLE_SCOPE_SOURCE_PACKET_EXACT_COVERAGE')
            n=len(packet['conformers']);Q.need(n<=10 and len({r['geometry_sha256'] for r in packet['conformers']})==n,'NO_EXACT_DUPLICATE_GEOMETRY_INFLATION')
            issues=packet_structure(packet);structure_unknown+=bool(issues)
            states[packet['state']]=states.get(packet['state'],0)+1;confs+=n;aliases+=len(packet.get('exact_native_geometry_aliases',[]))
            records.write({'ordinal':source['ordinal'],'cid':source['cid'],'stream':source['stream'],'state':packet['state'],'actual_conformers':n,
                'packet_structure_unknowns':issues,'packet_reference':row['packet_reference']})
            if pool:
                pending.append(pool.submit(families.quality_packet,packet))
                if len(pending)>=32:collect(pending.pop(0))
        for future in pending:collect(future)
    finally:
        if pool:pool.shutdown(wait=True,cancel_futures=False)
        if quality:quality.close()
        records.close();reuse.close()
    Q.need(counts=={'R':C.EACH,'N':C.EACH},'ALL2500000_SOURCE_ROLES_NO_FAILED_OR_UNKNOWN_DELETION')
    stop_fields=[fid for fid,v in stats.items() if v['newly_masked_records']/v['records']>.01]
    return store.json(out/'coverage_receipt.json',{'schema':'NO_PM7_UFF_D_FIRST2P5M_COVERAGE_V1','status':'ALL_SOURCE_ROWS_VISITED_QC_ACCEPTANCE_PENDING' if missing==0 else 'INCOMPLETE_UNCLAIMED_OR_UNRECOVERED_HOLD',
        'counts_by_stream':counts,'known_closed_packet_unique_geometry_records':confs,'geometry_total_is_lower_bound_if_packets_missing':bool(missing),
        'molecule_states':states,'unknown_missing_packets':missing,'packet_structure_unknowns':structure_unknown,'exact_native_aliases_not_counted_as_geometry':aliases,
        'coverage_DATA_reference':records.reference(),'D_1p5_full_physical_MAD_and_cross_conformer_scan':'REQUIRED_NOT_CLAIMED_BY_COVERAGE',
        'original_mask_and_TRAIN_reference_DATA':quality.reference() if quality else None,'original_function_field_statistics':dict(stats),
        'original_mask_new_fraction_denominator':'actual source records of each D20 graph or D3 conformer field;original physical masks;strictly greater than0.01 STOP',
        'stop_new_mask_above_one_percent_fields':stop_fields,'quality_HOLD':bool(stop_fields or missing or structure_unknown or not review or not review.get('TRAIN_calibration_reference')),
        'TRAIN_calibration_applied_not_fit':bool(review and review.get('TRAIN_calibration_reference')),'quality_worker_pids':sorted(pids),
        'R_N_pseudo_TRAIN_created':False,'all1p5_acceptance_requires_independent_Root_review':True,
        'new_UFF_QM_calls':0,'dataset_version':'v2_candidate','training_or_pool_release':False})
