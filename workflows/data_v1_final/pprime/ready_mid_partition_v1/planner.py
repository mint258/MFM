"""Original availability functions on closed bodies; no conformer/native stage."""
import collections,hashlib,json,os,pathlib,stat,types
from workflows.expansion.common_molecular_fp_main_v1.io import Body
from . import contract as C
P=C.P;F=C.F
EXACT='EXACT_FROZEN_READY_PREFIX_RECONSTRUCTED_WITH_BASELINE_ONCE'
CONSERVATIVE='CONSERVATIVE_SUPERSET_EXCLUSION_OF_LIVE_PREFIX_NOT_EXACT_ASSIGNMENT'
def availability_sql():
    values=[s for s in P.build.__code__.co_consts if type(s)is str and s.startswith('CREATE TEMP TABLE eligible AS SELECT ')]
    C.need(len(values)==1 and P.CHOSEN_SQL.endswith('ORDER BY e.molecule_id LIMIT 50000'),
      'ONE_EXACT_FROZEN_ORIGINAL_AVAILABILITY_CONSTANT_AND_CHOSEN_SQL')
    return values[0]
def pending_sql():
    values=[s for s in P.build.__code__.co_consts if type(s)is str and s.startswith('SELECT count(*) FROM per p LEFT JOIN val v USING(molecule_id) WHERE ')and'AND NOT coalesce'in s]
    C.need(len(values)==1,'ONE_EXACT_ORIGINAL_PENDING_NOT_SCIENTIFIC_EXCLUSION_SQL');return values[0]
def snapshot_census_function(root):
    class Contract:
        def __getattr__(self,name):return getattr(F,name)
        def ledger(self,plan):return pathlib.Path(root)
    old=P.consumed_mid_census;scope=dict(old.__globals__);scope['C']=Contract()
    function=types.FunctionType(old.__code__,scope,old.__name__,old.__defaults__,old.__closure__)
    function.__kwdefaults__=old.__kwdefaults__;return function
def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)
def freeze_once(parent,out,budget,store):
    actual=F.ledger(parent)/'physical_records_v1';before=actual.lstat()
    C.need(stat.S_ISDIR(before.st_mode)and before.st_uid==1278 and not any(p.is_symlink()for p in (actual,*actual.parents)),
      'EXACT_ORIGINAL_VALIDATED_ONCE_DIRECTORY_NO_ACTIVE_DB')
    names=sorted(p.name for p in actual.iterdir());root=out/'once_snapshot';folder=root/'physical_records_v1';folder.mkdir(parents=True)
    entries=[];same_protocol=[];other_protocol=0
    C.need(len(names)<=2*1220466+10000,'ORIGINAL_FINITE_ONCE_METADATA_CENSUS_BOUND')
    for name in names:
        budget.check();C.need(name.endswith('.json')and len(name[:-5])==64 and all(c in '0123456789abcdef'for c in name[:-5]),'IMMUTABLE_ORIGINAL_ONCE_NAMES_ONLY')
        path=actual/name;start=path.lstat();C.need(stat.S_ISREG(start.st_mode)and start.st_uid==1278 and start.st_nlink==1 and not path.is_symlink()
          and 0<start.st_size<=2<<20,'CLOSED_POSITIVE_SINGLE_LINK_ONCE_METADATA')
        with path.open('rb')as stream:
            fd=os.fstat(stream.fileno());raw=stream.read((2<<20)+1);last=os.fstat(stream.fileno())
        C.need(frame(start)==frame(fd)==frame(last)==frame(path.lstat())and len(raw)==start.st_size,'IMMUTABLE_ONCE_SAME_FD_FRAME_NO_PARTIAL_ACCEPTANCE')
        reference={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};row=json.loads(raw)
        C.need(row['record_once_key']==name[:-5],'ORIGINAL_ONCE_FILENAME_RECORD_KEY')
        if row['original_protocol_reference']['sha256']==parent['original_protocol_reference']['sha256']:same_protocol.append(row['record_id'])
        else:other_protocol+=1
        copied=store.write(folder/name,raw);C.need(copied['sha256']==reference['sha256']and copied['bytes']==reference['bytes'],'EXACT_OPERATIONAL_SNAPSHOT_NOT_NEW_CLAIM')
        entries.append({'original_reference':reference,'snapshot_reference':copied,'original_frame':list(frame(start))})
    after=actual.lstat();names_after={p.name for p in actual.iterdir()}
    C.need((before.st_dev,before.st_ino,before.st_uid)==(after.st_dev,after.st_ino,after.st_uid)and set(names)<=names_after,
      'ORIGINAL_ONCE_APPEND_ONLY_NO_DELETION_OR_DIRECTORY_REPLACEMENT')
    # Only a private byte-identical read view changes. Original ledger guard ran
    # above; no global/module/real claim is patched, written, retried or deleted.
    reader=snapshot_census_function(root);deferred=reader(parent,budget)
    ref=store.json(out/'once_snapshot_inventory.DATA.json',{'schema':'PPRIME_IMMUTABLE_ONCE_READ_SNAPSHOT_V1','entries':entries,
      'original_root':str(actual),'snapshot_root':str(folder),'new_original_names_after_snapshot':len(names_after-set(names)),
      'original_census_function_same_code':reader.__code__ is P.consumed_mid_census.__code__,'other_protocol_files':other_protocol,
      'actual_once_writes':0,'snapshot_files_are_not_claims':True})
    return deferred,same_protocol,ref,len(entries)
def balance(rows,n_shards):
    C.need(type(n_shards)is int and 1<=n_shards<=128,'FINITE_ROOT_SHARD_COUNT')
    count=min(n_shards,len(rows));sizes=[] if not count else [len(rows)//count+(i<len(rows)%count)for i in range(count)]
    C.need(not sizes or max(sizes)<=50000,'REQUEST_MORE_SHARDS_NO_READY_MID_SILENTLY_TRUNCATED')
    result=[];offset=0
    for size in sizes:result.append(rows[offset:offset+size]);offset+=size
    C.need(offset==len(rows),'WHOLE_UNASSIGNED_READY_DOMAIN');return result
def membership_qa(eligible,pilot,main,shards):
    universe={r['molecule_id']:r for r in eligible};C.need(len(universe)==len(eligible),'UNIQUE_ORIGINAL_READY_MIDS')
    seen=set();counts=collections.Counter()
    for rows in (pilot,main,*shards):
        ids={r['molecule_id']for r in rows};C.need(len(ids)==len(rows)and not seen&ids,'PAIRWISE_DISJOINT_REAL_MID_ASSIGNMENTS');seen|=ids
        for row in rows:
            C.need(row==universe[row['molecule_id']]and row['effective_role']in ('TRAIN','VAL')and type(row['source_role'])is str
              and type(row['global_rank'])is int and row['global_rank']>=0,'EXACT_ORIGINAL_MID_ROLE_AND_READY_COUNTS')
            counts[row['effective_role']]+=1
    C.need(seen==set(universe),'EXACT_READY_UNION_NO_LOST_MID_OR_PILOT_REINVOKE')
    return {'pairwise_disjoint':True,'union_covers_original_ready_MID_universe':True,
      'roles_equal_original_frozen_authority':True,'source_MID_ids_preserved':True,
      'physical_conformer_IDs_verified':False,'role_counts':dict(counts)}
def lines(store,path,rows,*,mid_only=False,budget=None):
    C.need(rows,'NONEMPTY_POSITIVE_DATA_REFERENCE_REQUIRED_NO_FAKE_EMPTY_MEMBER')
    body=b''.join((json.dumps({'molecule_id':r['molecule_id']}if mid_only else r,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()for r in rows)
    ref=store.write(path,body)
    if budget is not None:
        checked=Body(ref,budget)
        try:
            actual=[json.loads(raw)for raw in checked.stream];checked.check()
            C.need(actual==([{'molecule_id':r['molecule_id']}for r in rows]if mid_only else rows),
              'CLOSED_ASSIGNED_DATA_FULL_SHA_FD_AND_ROW_ID_ROLE_READBACK')
        finally:checked.close()
    return ref
def build(plan,proof,out,budget,store):
    import duckdb,pyarrow as pa
    parent,b,_,_=C.registration(plan)
    local=dict(parent,output_directory=str(out));pilot_ids,reuse=P.pilot_reuse(local,b,budget,store)
    C.need(len(pilot_ids)==1000,'ORIGINAL_REAL1000_MIDS_2000_RECORDS_ALL_OUTCOMES')
    deferred,same_protocol,once_ref,snapshot_files=freeze_once(parent,out,budget,store)
    same_ids={P.claimed_identity(r)[0]for r in same_protocol}
    exact=snapshot_files==2000 and len(same_protocol)==2000 and len(set(same_protocol))==2000 and same_ids==pilot_ids and deferred==pilot_ids
    holders=[];db=duckdb.connect(':memory:')
    try:
        db.execute("SET threads=16;SET memory_limit='8GB';SET max_temp_directory_size='7GB'")
        temp=out/'sql_tmp';temp.mkdir();db.execute('SET temp_directory='+P.q(temp))
        def hold(ref):
            body=Body(ref,budget);holders.append(body);return str(ref['path'])
        per,mi=b['population'];perpath=hold(per);mipath=hold(mi);valpath=hold(b['val'])
        for name,path in (('per',perpath),('mi',mipath),('val',valpath)):db.execute('CREATE TEMP VIEW '+name+' AS SELECT * FROM read_parquet('+P.q(path)+')')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM per').fetchone()==(1220466,1220466)
          and db.execute('SELECT count(DISTINCT molecule_id) FROM val').fetchone()[0]==7610,'ORIGINAL_FULL_MOTHER_AND_WHOLE_ROUTINE_VAL')
        db.execute(availability_sql());db.register('pilot_mids',pa.table({'molecule_id':pa.array(sorted(pilot_ids),type=pa.string())}))
        db.register('consumed_mid_ids',pa.table({'molecule_id':pa.array(sorted(deferred),type=pa.string())}));db.execute(P.CHOSEN_SQL)
        columns='molecule_id,effective_role,split_role AS source_role,S_conformers,Sprime_conformers,row_number()OVER(ORDER BY molecule_id)-1 AS global_rank'
        eligible=db.execute('SELECT '+columns+' FROM eligible ORDER BY molecule_id').fetch_arrow_table().to_pylist();pending=db.execute(pending_sql()).fetchone()[0]
        C.need(len({r['molecule_id']for r in eligible})==len(eligible),'NO_AMBIGUOUS_SOURCE_JOIN_OR_DUPLICATE_MID')
        by={r['molecule_id']:r for r in eligible};C.need(pilot_ids<=set(by),'ALL_ORIGINAL_PILOT_STILL_READY')
        chosen={r[0]for r in db.execute('SELECT molecule_id FROM chosen').fetchall()}
        reserve=(chosen|(deferred&set(by)))-pilot_ids
        # Current consumed may include live190. Monotone immutable once implies
        # consumed U current first50k contains its original first50k assignment.
        pilot=[by[k]for k in sorted(pilot_ids)];main=[by[k]for k in sorted(reserve)]
        remaining=[r for r in eligible if r['molecule_id']not in pilot_ids|reserve];shards=balance(remaining,plan['n_shards'])
        qa=membership_qa(eligible,pilot,main,shards);C.need(main,'LIVE_PREFIX_EMPTY_NO_NEW_PARENT_ASSIGNMENTS')
        population=F.unique([*b['population'],b['val'],*b['sprime']]);common={'partition_id':plan['partition_id'],
          'population_data_references':population,'original_protocol_reference':parent['original_protocol_reference'],
          'pilot_execution_plan_reference':parent['pilot_execution_plan_reference'],'actual_planner_job_id':str(proof['job_id']),
          'target_endpoint':'202.38.247.57:22','target_uid':1278,'native_init_invoke_calls':0}
        legacy=store.json(out/'original1000_exclusion_header.json',dict(common,
          schema='PPRIME_ORIGINAL1000_MID_EXCLUSION_HEADER_V1',status='CPU_REVALIDATED_ORIGINAL2000_CONSUMED_NOT_REINVOKED',
          molecules=1000,conformer_records=2000,record_reference=lines(store,out/'original1000_MIDs.DATA.jsonl',pilot,mid_only=True,budget=budget),pilot_reuse_reference=reuse))
        exclusion=store.json(out/'main190_exclusion_header.json',dict(common,
          schema='PPRIME_LIVE_PARENT_MID_DOMAIN_EXCLUSION_HEADER_V1',status=EXACT if exact else CONSERVATIVE,
          exact_live_assignment_reconstructed=exact,molecules=len(main),record_reference=lines(store,out/'main190_exclusion_MIDs.DATA.jsonl',main,mid_only=True,budget=budget),
          main190_registration=plan['main190_registration'],once_snapshot_reference=once_ref,
          additional_reserved_MIDs_are_operational_pending_not_scientific_exclusion=not exact))
        headers=[];all_data=[]
        for i,rows in enumerate(shards):
            budget.check();shard_id='ready_mid_shard_%04d'%i;data=lines(store,out/(shard_id+'.DATA.jsonl'),rows,budget=budget);all_data.append(data)
            header=store.json(out/(shard_id+'.header.json'),dict(common,schema='PPRIME_READY_MID_SHARD_HEADER_V1',
              status='CPU_CLOSED_ASSIGNED_MID_SET_REQUIRES_ROOT_REVIEW',shard_id=shard_id,molecules=len(rows),
              conformer_records=2*len(rows),maximum_native_calls=24*len(rows),record_reference=data,
              main190_exclusion_header_reference=exclusion,legacy_pilot_exclusion_header_reference=legacy,
              original_first2_seed=20261025,physical_conformer_IDs_verified=False,shared_preparation_pairs_not_created=True))
            headers.append(header)
        for ref in (legacy,exclusion,*headers):
            body=Body(ref,budget)
            try:body.check()
            finally:body.close()
        for body in holders:body.check()
        return store.json(out/'partition_QA.json',dict(common,**qa,schema='PPRIME_READY_MID_PARTITION_QA_V1',
          status='CPU_CLOSED_PARTITION_REQUIRES_ROOT_REVIEW',requested_n_shards=plan['n_shards'],nonempty_shards=len(headers),
          shard_header_references=headers,assigned_data_references=all_data,main190_exclusion_header_reference=exclusion,
          legacy_pilot_exclusion_header_reference=legacy,eligible_MIDs=len(eligible),legacy_pilot_MIDs=len(pilot),
          main190_excluded_MIDs=len(main),new_assigned_MIDs=len(remaining),all_original_ready_conformer_records=2*len(eligible),N1_or_unavailable_pending_MIDs=pending,
          original_eligible_SQL_SHA256=hashlib.sha256(availability_sql().encode()).hexdigest(),
          original_CHOSEN_SQL_SHA256=hashlib.sha256(P.CHOSEN_SQL.encode()).hexdigest(),
          original_prepare_Source_reference=C.Q.pin(F.HERE/'prepare.py'),once_snapshot_reference=once_ref,
          all_assigned_and_exclusion_DATA_and_headers_current_FD_SHA_closed=True,
          Source_or_Model_or_training_release=False,active_DB_read=False,original_once_writes=0,
          coordinate_parts_freshly_hashed_or_parsed=False,shared_prepare_may_consume_multiple_headers_without_future_pair_hash=True))
    finally:
        db.close()
        for body in holders:body.close()
