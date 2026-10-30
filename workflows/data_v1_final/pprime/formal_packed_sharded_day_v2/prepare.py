"""Same Parent complete-old-Sprime candidate inputs; no new geometry or QM."""
import collections,contextlib,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,time,struct
from multiprocessing.util import Finalize
from workflows.expansion.common_molecular_fp_main_v1.io import Body as OriginalBody,BorrowedFile
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime import geometry
from . import contract as C,io as I

_held_bodies={}
_hash_pool=None;_hash_engine=None;_hash_session=None;_hash_old=None;_hash_root=None;_hash_count=0;_hash_finalize=None;_hash_scratch=None;_hash_closures=[]
class CachedBody:
    def __init__(self,ref,budget):
        key=ref['path']
        if key not in _held_bodies:_held_bodies[key]=(ref,OriginalBody(ref,budget))
        prior,self.original=_held_bodies[key];C.need(prior==ref,'SAME_FIXED_INPUT_LOCATOR_DURING_SHARED_PREPARATION');self.original.check();self.stream=self.original.stream
    def check(self):return self.original.check()
    def close(self):return self.check()
Body=CachedBody
def close_inputs():
    global _hash_pool
    try:
        if _hash_pool is not None:
            pool=_hash_pool;processes=list(pool._processes.values());_hash_pool=None;pool.shutdown(wait=True,cancel_futures=False)
            for process in processes:
                path=_parent_hash_root/'hash_workers'/('worker_%d_closed.json'%process.pid)
                C.need(not process.is_alive() and process.exitcode==0 and path.is_file(),'ALL_ACTUAL_ZERO_INVOKE_HASH_WORKERS_CLOSED')
                ref=I.pin(path,[_parent_hash_root]);value=json.loads(path.read_bytes())
                C.need(value['native_invokes']==0 and value['original_engine_closed'] is True,'NO_NATIVE_AND_REAL_HASH_WORKER_CLOSE')
                _hash_closures.append(dict(value,reference=ref))
        for _,body in _held_bodies.values():body.check();body.close()
    finally:_held_bodies.clear()

def hash_close():
    global _hash_engine
    if _hash_engine is not None:
        with C.P.OriginalInputs.NoInvoke(_hash_old):_hash_engine.close_worker()
        _hash_engine=None
    if _hash_scratch is not None and _hash_scratch.exists() and not any(_hash_scratch.iterdir()):_hash_scratch.rmdir()
    I.Store(_hash_root/'hash_workers',8<<20).json(_hash_root/'hash_workers'/('worker_%d_closed.json'%os.getpid()),{
      'pid':os.getpid(),'start_ticks':I.ticks(os.getpid()),'job_id':_hash_session['job_id'],'records_hashed':_hash_count,
      'original_engine_closed':True,'native_invokes':0,'original_NoInvoke_in_each_worker':True})

def hash_initialize(session,context,protocol,audit,root):
    global _hash_engine,_hash_session,_hash_old,_hash_root,_hash_finalize,_hash_scratch
    _hash_session=session;_hash_root=pathlib.Path(root);I.continuation(session,check_sources=True)
    _hash_engine,legacy,_hash_old,pilot=T.engine(context,C.meta);C.need(_hash_old==C.meta(protocol),'EXACT_ORIGINAL_HASH_WORKER_PROTOCOL')
    import tempfile
    scratch=pathlib.Path(tempfile.mkdtemp(prefix='pprime_input_hash_'+session['job_id']+'_'+str(os.getpid())+'_',dir='/tmp'))
    _hash_scratch=scratch
    with C.P.OriginalInputs.NoInvoke(_hash_old):
        _hash_engine.initialize_worker(pilot['source_plan']['path'],protocol=protocol['path'],node_scratch_root=str(scratch),
          audit_membership=audit['path'],reproduction_package=legacy['reproduction_package']['path'])
    _hash_finalize=Finalize(None,hash_close,exitpriority=10)

def hash_one(item):
    global _hash_count
    I.continuation(_hash_session);rid,blob=item;pair=json.loads(bytes(blob));engine=_hash_engine;old=_hash_old
    with C.P.OriginalInputs.NoInvoke(old):
        source=engine.NATIVE.read_native(pair['source'])
        graph=engine.source_bond_graph(source['_source_raw'],source)
        C.need(not graph['bond_graph_issues'] and graph['bond_pairs_zero_based'] is not None,'ORIGINAL_GRAPH_REQUIRED_NO_REPAIR')
        native,prov=geometry.adapt_native(source,dict(pair,bond_pairs=graph['bond_pairs_zero_based']))
        hashes=I.Preparation.input_hashes(engine,native,pair,old,old)
        value={'record_id':rid,'original_pair_sha256':hashlib.sha256(C.O.canonical(pair)).hexdigest(),'geometry_sha256':prov['uff_geometry_sha256'],'hashes':hashes}
    _hash_count+=1;return rid,value

def hash_block(block,plan,proof,b,audit,out,budget):
    global _hash_pool,_parent_hash_root
    if _hash_pool is None:
        root=budget.local_root;_parent_hash_root=root;(root/'hash_workers').mkdir();session=I.source_session(C.Q.pin(plan['plan_path']),plan,proof)
        _hash_pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=hash_initialize,
          initargs=(session,b['context'],plan['original_protocol_reference'],audit,str(root)))
    # <=128 records retained in dispatch memory; map preserves original RID order.
    C.need(len(block)<=128,'BOUNDED_SOURCE_INPUT_HASH_DISPATCH')
    for result in _hash_pool.map(hash_one,[(rid,bytes(blob)) for rid,blob in block],chunksize=1):budget.check();yield result

def q(s):return "'"+str(s).replace("'","''")+"'"

def _pilot_reuse_original(plan,b,budget,store):
    result=json.loads(I.body(b['pilot_result'],b['data'],budget))
    C.need(result['plan_reference']==plan['pilot_execution_plan_reference'] and result['completed_records']==2000
      and result['requested_records']==2000 and result['all_workers_joined'] is True and result['failures']==[]
      and result['all_twelve_tasks_success_records']==1989 and result['precision_mode']=='ORIGINAL_WP5',
      'CPU_REAL_PILOT_RESULT_EXACT1989_2000_NOT_SOURCE_SUMMARY_ONLY')
    pairs,_=C.P.OriginalInputs.pairs(b['pilot_pairs'],budget)
    index=result['record_terminals_reference'];root=pathlib.Path(b['pilot_plan']['output_directory'])
    C.need(root in pathlib.Path(index['path']).parents,'ORIGINAL_C0_TRANSITIVE_TERMINAL_INDEX_ROOT')
    terminals=json.loads(I.body(index,[index],budget));by={p['record_id']:p for p in pairs};seen=set()
    for row in terminals:
        rid=row['record_id'];C.need(rid in by and rid not in seen and row['technical_record_complete'] is True
          and row['native_return_count']==12 and not row['UNKNOWN_attempts_retained'],'ALL2000_REAL_CLOSED_TERMINALS')
        pair=by[rid];key=C.record_once_key(pair,plan['original_protocol_reference']);ref=row['claim_reference']
        C.need(ref['path']==str(C.ledger(plan)/'physical_records_v1'/(key+'.json')),'EXACT_ORIGINAL_GLOBAL_PHYSICAL_ONCE')
        claim=json.loads(I.body(ref,[ref],budget))
        C.need(claim['record_once_key']==key and claim['record_id']==rid and str(claim['job_id'])=='4525179'
          and claim['pair_sha256']==hashlib.sha256(C.O.canonical(pair)).hexdigest()
          and claim['original_protocol_reference']==plan['original_protocol_reference'],'PILOT_PHYSICAL_CLAIM_INPUT_BINDING')
        seen.add(rid)
    C.need(seen==set(by) and len(seen)==2000,'ALL_PILOT_SUCCESSES_AND11_FAILURES_CONSUMED_NO_REINVOKE')
    ref=store.json(pathlib.Path(plan['output_directory'])/'pilot_reuse_CPU_QA.json',{
      'schema':'PPRIME_FORMAL_ORIGINAL2000_REUSE_CPU_QA_V1','records':2000,'successful':1989,'scientific_failures_consumed':11,
      'result_reference':b['pilot_result'],'terminal_index_reference':index,'original_pilot_family_parquets':result['family_parquets'],
      'original_stable_raw_retention_proof':result['stable_raw_retention_proof'],'all_physical_claims_revalidated':True,'reinvocations':0})
    return {p['molecule_id'] for p in pairs},ref

def build(plan,proof,out,b,budget,store):
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    pilot_mids,reuse=pilot_reuse(plan,b,budget,store)
    software=C.P.software_original_specs(b['context']);software_checks=[]
    already_verified=b.get('_assets_verified',False)
    for ref in ([] if already_verified else b['context']['execution_asset_references']):
        if ref['path'] in software:
            software_checks.append(I.Preparation.hash_software_original(C.P.triple(ref),software[ref['path']],budget))
        else:
            body=Body(C.P.triple(ref),budget)
            try:body.check()
            finally:body.close()
    C.need(already_verified or len(software_checks)==14,'EXACT_FROZEN_READONLY_SOFTWARE_WHITELIST_ALL14');b['_assets_verified']=True
    folder=out/'prepare';folder.mkdir();dbpath=folder/'prepared.duckdb';db=duckdb.connect(str(dbpath))
    db.execute("SET threads=16;SET memory_limit='8GB';SET max_temp_directory_size='7GB'")
    tmp=folder/'sql_tmp';tmp.mkdir();db.execute('SET temp_directory='+q(tmp))
    holders=[];engine=None;scratch=None
    def hold(ref):
        body=Body(C.P.triple(ref),budget);holders.append(body);return str(ref['path'])
    try:
        per,molecules=b['population'];perpath=hold(per);mpath=hold(molecules);vpath=hold(b['val'])
        index=next(r for r in b['data'] if r['path']==b['pilot']['record_index']);ipath=hold(index)
        spaths=[hold(r) for r in b['sprime']]
        db.execute('CREATE TEMP VIEW per AS SELECT * FROM read_parquet('+q(perpath)+')')
        db.execute('CREATE TEMP VIEW mi AS SELECT * FROM read_parquet('+q(mpath)+')')
        db.execute('CREATE TEMP VIEW val AS SELECT * FROM read_parquet('+q(vpath)+')')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM per').fetchone()==(1220466,1220466)
          and db.execute('SELECT count(DISTINCT molecule_id) FROM val').fetchone()[0]==7610,'ORIGINAL_FULL_MOTHER_AND_ROUTINE_VAL')
        db.register('pilot_mids',pa.table({'molecule_id':sorted(pilot_mids)}))
        assigned=assigned_rows(plan,b,budget)
        db.register('assigned_mids',pa.Table.from_pylist(assigned))
        db.execute("CREATE TEMP TABLE eligible AS SELECT p.*,m.file_group,m.max_heavy_atoms,m.max_total_atoms,CASE WHEN v.molecule_id IS NOT NULL THEN 'VAL' ELSE 'TRAIN' END AS effective_role,CASE WHEN m.max_heavy_atoms<=20 THEN '0_20' WHEN m.max_heavy_atoms<=40 THEN '21_40' WHEN m.max_heavy_atoms<=75 THEN '41_75' ELSE 'above_75' END AS size_stratum FROM per p JOIN mi m USING(molecule_id) LEFT JOIN val v USING(molecule_id) WHERE (p.split_role='TRAIN' OR v.molecule_id IS NOT NULL) AND p.S_conformers>=2 AND p.Sprime_conformers>=p.S_conformers")
        deferred=set() # Assignment is frozen; no independent local reselection.
        db.register('consumed_mid_ids',pa.table({'molecule_id':pa.array(sorted(deferred),type=pa.string())}))
        eligible_n=db.execute('SELECT count(*) FROM eligible').fetchone()[0]
        deferred_n=db.execute('SELECT count(*) FROM eligible e JOIN consumed_mid_ids d USING(molecule_id) ANTI JOIN pilot_mids p USING(molecule_id)').fetchone()[0]
        db.execute(ASSIGNED_SQL)
        C.need(db.execute('SELECT count(*) FROM chosen').fetchone()[0]==len(assigned),'ALL_ASSIGNED_MIDS_MATCH_ORIGINAL_ELIGIBLE_ROLES_AND_COUNTS')
        n=db.execute('SELECT count(*) FROM chosen').fetchone()[0]
        C.need(0<=n<=50000,'BOUNDED_READY_PREFIX_EMPTY_IS_PENDING_NOT_FULL_COMPLETION')
        pending=db.execute("SELECT count(*) FROM per p LEFT JOIN val v USING(molecule_id) WHERE (p.split_role='TRAIN' OR v.molecule_id IS NOT NULL) AND NOT coalesce(p.S_conformers>=2 AND p.Sprime_conformers>=p.S_conformers,FALSE)").fetchone()[0]
        C.need(db.execute('SELECT count(*) FROM eligible e JOIN pilot_mids p USING(molecule_id)').fetchone()[0]==1000,'ALL_ORIGINAL_PILOT_MIDS_STILL_IN_THE_SAME_FROZEN_READY_DOMAIN')
        db.execute("CREATE TEMP TABLE conformers AS SELECT s.* FROM read_parquet(["+','.join(q(p) for p in spaths)+"]) s JOIN chosen c USING(molecule_id) WHERE s.status='SUCCESS' AND s.converged")
        C.need(db.execute('SELECT count(*) FROM (SELECT c.molecule_id FROM chosen c LEFT JOIN conformers s USING(molecule_id) GROUP BY c.molecule_id,c.Sprime_conformers HAVING count(s.sprime_conf_idx)<>c.Sprime_conformers OR count(DISTINCT s.sprime_conf_idx)<>count(s.sprime_conf_idx))').fetchone()[0]==0,'WHOLE_SELECTED_SPRIME_COUNTS_AND_PHYSICAL_IDS')
        db.execute('CREATE TEMP VIEW ri AS SELECT * FROM read_parquet('+q(ipath)+')')
        db.execute('CREATE TABLE pairs(rid VARCHAR PRIMARY KEY,mid VARCHAR,rank BIGINT,pair BLOB,hashes BLOB)')
        source_plan=C.meta(b['pilot']['source_plan']);source_by_path={s['path']:s['shard_id'] for s in source_plan['sources']}
        mid_rows=db.execute('SELECT molecule_id,file_group,size_stratum,effective_role,split_role FROM chosen ORDER BY molecule_id').fetchall()
        audit_rows=[];count=0;selected_mids=set();consumed_count=0
        sys_parent=C.Q.REPO/'workflows/data_v1_final/pprime'
        import sys
        sys.path[:0]=[str(sys_parent/'retention_v1'),str(sys_parent)]
        import retention_policy_v1 as retention
        sources=retention.source_paths(source_plan)
        for mid,group,size,role,source_role in mid_rows:
            if count>=C.MAX_RECORDS:break
            budget.check();rows=db.execute('SELECT * FROM conformers WHERE molecule_id=?',[mid]).fetch_arrow_table().to_pylist()
            first=C.O.ordered_two(rows,mid,20261025)
            C.need(len(first)==2 and len({r['sprime_conf_idx'] for r in first})==2,'ORIGINAL_FIRST2_REAL_FIXED_RANDOM')
            for rank,conf in enumerate(first):
                pointer=db.execute('SELECT * FROM ri WHERE record_id=?',[conf['source_record_id']]).fetch_arrow_table().to_pylist()
                C.need(len(pointer)==1 and pointer[0]['molecule_id']==mid,'CANONICAL_NATIVE_SOURCE_ANCHOR_SAME_MID')
                source=dict(pointer[0],shard_id=source_by_path[pointer[0]['source_path']],file_group=int(group),size_stratum=size,effective_role=role,source_role=source_role)
                rid='pprime:'+mid+':'+str(conf['sprime_conf_idx'])
                pair={'record_id':rid,'molecule_id':mid,'random_order_rank':rank,'geometry_source':'uff_sprime','source':source,'conformer':conf,
                  'uff_coordinate_sha256':coordinate_sha(conf['coordinates']),
                  'conformer_row_sha256':hashlib.sha256(C.O.canonical(conf)).hexdigest()}
                key=C.record_once_key(pair,plan['original_protocol_reference']);claimed=C.ledger(plan)/'physical_records_v1'/(key+'.json')
                if claimed.exists():
                    prior=C.meta(C.Q.pin(claimed))
                    C.need(prior['record_once_key']==key and prior['pair_sha256']==hashlib.sha256(C.O.canonical(pair)).hexdigest(),
                      'PRIOR_SAME_PHYSICAL_ONCE_CONSUMED_NOT_NEW_NAMESPACE_OR_RETRY')
                    consumed_count+=1;continue
                if count>=C.MAX_RECORDS:break
                db.execute('INSERT INTO pairs VALUES(?,?,?,?,NULL)',[rid,mid,rank,C.O.canonical(pair)])
                audit_rows.append(dict(retention.source_audit(pair,sources),retain_all_twelve_raw=False));count+=1;selected_mids.add(mid)
        del mid_rows;drop_staging(db)
        C.need(count<=C.MAX_RECORDS,'EXACT_ROOT_NEW_RECORD_BOUND_AFTER_CONSUMED_ONCE_ANTI_JOIN')
        budget.forecast_records=max(1,count)
        if count==0:
            db.execute('CHECKPOINT');db.close();db=None
            ref=I.pin(dbpath,[folder])
            header=store.json(folder/'prepared_generation_header.json',{'schema':'PPRIME_FORMAL_READY_PREFIX_INPUT_HEADER_V1','records':0,
              'MIDs':0,'index_reference':ref,'pilot_reuse_reference':reuse,'N1_or_unavailable_pending_MIDs':pending,
              'additional_consumed_physical_records_not_retried':consumed_count,'ready_population_MIDs':eligible_n,'operational_ready_prefix_MIDs':n,'ready_MIDs_outside_prefix_pending':max(0,eligible_n-len(pilot_mids)-deferred_n-n),'metadata_deferred_consumed_MIDs_not_scientific_success':deferred_n,'native_invokes':0,'final_Common':False})
            for body in holders:body.check()
            return {'header':header,'index':ref,'records':0,'MIDs':0,'reuse':reuse,'pending_MIDs':pending}
        # The stable original physical audit is independent of batching/day.
        selected=[{'record_id':r['record_id'],'file_group':r['legacy_engine_file_group'],'size_stratum':r['size_stratum']} for r in audit_rows if r['selected']]
        selected_set={r['record_id'] for r in selected}
        for r in audit_rows:r['retain_all_twelve_raw']=r['record_id'] in selected_set
        buffer=pa.BufferOutputStream();schema=pa.schema([('record_id',pa.string()),('file_group',pa.int64()),('size_stratum',pa.string())])
        pq.write_table(pa.Table.from_pylist(selected,schema=schema),buffer,compression='zstd')
        audit_selected=store.write(folder/'audit_selected.parquet',buffer.getvalue().to_pybytes())
        audit=store.json(folder/'audit_membership.json',{'schema':'WP5_STRATIFIED_RECORD_AUDIT_V1','status':'AUDIT_MEMBERSHIP_CLOSED','selected_records':dict(audit_selected,rows=len(selected)),
          'seed':20261010,'audit_policy':plan['retention_policy_reference'],'scope':'same original stable physical threshold100/10000, no fake exact1pct'})
        source_audit=store.json(folder/'source_audit.DATA.json',audit_rows)
        C.need(store.charged<512<<20,'PREPARATION_METADATA_WITHIN_ADMIN_PARTITION_NOT_AN_EXTRA_FUTURE_CAP')
        engine,legacy,old,pilot=T.engine(b['context'],C.meta)
        C.need(old==b['old'],'ORIGINAL_PROTOCOL_ONLY_BEFORE_RENDER')
        import tempfile
        scratch=pathlib.Path(tempfile.mkdtemp(prefix='pprime_formal_prepare_'+str(proof['job_id'])+'_',dir='/tmp'))
        with C.P.OriginalInputs.NoInvoke(old):
            engine.initialize_worker(pilot['source_plan']['path'],protocol=plan['original_protocol_reference']['path'],node_scratch_root=str(scratch),audit_membership=audit['path'],reproduction_package=legacy['reproduction_package']['path'])
            cursor=db.cursor();cursor.execute('SELECT rid,pair FROM pairs ORDER BY mid,rank')
            while True:
                block=cursor.fetchmany(128)
                if not block:break
                for rid,value in hash_block(block,plan,proof,b,audit,out,budget):
                    db.execute('UPDATE pairs SET hashes=? WHERE rid=?',[C.O.canonical(value),rid])
            cursor.close();engine.close_worker();engine=None
        C.need(db.execute('SELECT count(*) FROM pairs WHERE hashes IS NULL').fetchone()[0]==0,'ALL_PRECALL_ORIGINAL_INPUT_HASHES_CLOSED')
        db.execute('CHECKPOINT');db.close();db=None
        C.need(dbpath.stat().st_size<4<<30,'PREPAID_PREPARATION_INDEX_WITHIN4GIB_NOT_TOTAL_SCRATCH_GUARANTEE')
        ref=I.pin(dbpath,[folder]);header=store.json(folder/'prepared_generation_header.json',{
          'schema':'PPRIME_FORMAL_READY_PREFIX_INPUT_HEADER_V1','records':count,'MIDs':len(selected_mids),'index_reference':ref,'audit_membership_reference':audit,
          'source_audit_reference':source_audit,'pilot_reuse_reference':reuse,'ready_population_MIDs':eligible_n,'operational_ready_prefix_MIDs':n,'ready_MIDs_outside_prefix_pending':max(0,eligible_n-len(pilot_mids)-deferred_n-n),'metadata_deferred_consumed_MIDs_not_scientific_success':deferred_n,'N1_or_unavailable_pending_MIDs':pending,
          'additional_consumed_physical_records_not_retried':consumed_count,
          'source_index_input_refs':b['population'],'all_first2_original_seed':20261025,'native_invokes':0,'final_Common':False})
        for body in holders:body.check()
        budget.forecast_records=max(1,count)
        return {'header':header,'index':ref,'audit':audit,'source_audit':source_audit,'records':count,'MIDs':len(selected_mids),'reuse':reuse,'pending_MIDs':pending}
    finally:
        if db is not None:db.close()
        if engine is not None:engine.close_worker()
        for body in holders:body.close()
        if scratch is not None and scratch.exists() and not any(scratch.iterdir()):scratch.rmdir()

def coordinate_sha(coordinates):
    flat = [float(v) for row in coordinates for v in row]
    return hashlib.sha256(struct.pack('<' + 'd' * len(flat), *flat)).hexdigest()

# Operational candidate staging only. Original source, first2, physical key and
# pair-hash verification remain downstream and unchanged.
CHOSEN_SQL='CREATE TEMP TABLE chosen AS SELECT e.* FROM eligible e ANTI JOIN pilot_mids p USING(molecule_id) ANTI JOIN consumed_mid_ids d USING(molecule_id) ORDER BY e.molecule_id LIMIT 50000'

def claimed_identity(record_id):
    C.need(type(record_id)is str and record_id.startswith('pprime:'),'ORIGINAL_PRODUCTION_RECORD_ID_PREFIX')
    mid,physical=record_id[len('pprime:'):].rsplit(':',1)
    C.need(mid and physical.isdecimal() and str(int(physical))==physical,'REVERSIBLE_ORIGINAL_MID_AND_PHYSICAL_INT_NOT_NEW_ALIAS')
    return mid,int(physical)

def consumed_mid_census(plan,budget):
    # No outcome is promoted: STARTED/FAILED/UNKNOWN all consume original once.
    # Two recorded physical IDs defer that MID from this day candidate prefix;
    # deferral remains explicit PENDING,not a scientific acceptance/exclusion.
    root=C.ledger(plan)/'physical_records_v1';seen=collections.defaultdict(set);count=0
    for path in root.iterdir():
        budget.check();count+=1;C.need(count<=2*1220466+10000,'BOUNDED_ORIGINAL_PHYSICAL_ONCE_METADATA_CENSUS')
        C.need(path.name.endswith('.json') and len(path.stem)==64 and all(c in '0123456789abcdef' for c in path.stem)
          and path.is_file() and not path.is_symlink(),'ORIGINAL_IMMUTABLE_ONCE_JSON_ONLY')
        row=C.meta(C.Q.pin(path))
        C.need(row['record_once_key']==path.stem,'ACTUAL_ONCE_FILENAME_KEY')
        before=row['original_protocol_reference'];after=plan['original_protocol_reference']
        if before['sha256']!=after['sha256']:continue
        mid,physical=claimed_identity(row['record_id']);seen[mid].add(physical)
    return {mid for mid,ids in seen.items() if len(ids)>=2}
def drop_staging(db):
    # No later renderer/worker needs these relation copies; fixed pairs already
    # contain source/conf identity. Release all large staging before hash updates.
    for name in ('conformers','chosen','eligible'):db.execute('DROP TABLE IF EXISTS '+name)
    for name in ('ri','val','mi','per'):db.execute('DROP VIEW IF EXISTS '+name)
    for name in ('pilot_mids','consumed_mid_ids','assigned_mids'):db.unregister(name)
ASSIGNED_SQL="CREATE TEMP TABLE chosen AS SELECT e.* FROM eligible e JOIN assigned_mids a ON e.molecule_id=a.molecule_id AND e.effective_role=a.effective_role AND e.split_role=a.source_role AND e.S_conformers=a.S_conformers AND e.Sprime_conformers=a.Sprime_conformers ORDER BY e.molecule_id"

def assigned_rows(plan,b,budget):
    ref=plan['_active_shard_header_reference'];h=C.meta(ref)
    rows=[json.loads(v) for v in I.body(h['record_reference'],b['data'],budget).splitlines() if v]
    keys={'molecule_id','effective_role','source_role','S_conformers','Sprime_conformers','global_rank'}
    C.need(len(rows)==h['molecules'] and all(set(r)==keys for r in rows),'ASSIGNED_JSONL_SIX_FIELD_CENSUS')
    C.need(len({r['molecule_id'] for r in rows})==len(rows) and len({r['global_rank'] for r in rows})==len(rows)
      and all(type(r['global_rank'])is int and r['global_rank']>=0 and type(r['S_conformers'])is int and r['S_conformers']>=2
      and type(r['Sprime_conformers'])is int and r['Sprime_conformers']>=r['S_conformers'] for r in rows),'ASSIGNED_UNIQUE_NATIVE_MID_GLOBAL_RANK')
    excluded=set()
    qa=C.meta(plan['generation_partition_QA_reference'])
    for key in ('main190_exclusion_header_reference','legacy_pilot_exclusion_header_reference'):
        x=C.meta(qa[key]);values=[json.loads(v) for v in I.body(x['record_reference'],b['data'],budget).splitlines() if v]
        C.need(all(set(v)=={'molecule_id'} for v in values),'EXCLUSION_MID_ONLY_ROWS');excluded.update(v['molecule_id'] for v in values)
    validate_assignment(rows,h,excluded)
    return rows

def validate_assignment(rows,h,excluded):
    C.need(len(rows)==h['molecules'] and all(set(r)=={'molecule_id','effective_role','source_role','S_conformers','Sprime_conformers','global_rank'} for r in rows),'SIX_FIELDS_NO_SCIENCE_RESELECTION')
    C.need(all(type(r['molecule_id'])is str and r['molecule_id'] and r['effective_role'] in ('TRAIN','VAL')
      and type(r['source_role'])is str and type(r['global_rank'])is int and r['global_rank']>=0
      and type(r['S_conformers'])is int and type(r['Sprime_conformers'])is int
      and r['S_conformers']>=2 and r['Sprime_conformers']>=r['S_conformers'] for r in rows),'EXACT_ORIGINAL_SOURCE_ROLE_AND_READY_COUNTS')
    C.need(len({r['molecule_id'] for r in rows})==len(rows) and len({r['global_rank'] for r in rows})==len(rows),'NO_DUPLICATE_ASSIGNED_MID_OR_GLOBAL_RANK')
    C.need(not({r['molecule_id'] for r in rows}&set(excluded)),'NO_LIVE190_OR_ORIGINAL_PILOT_MID_OVERLAP')

def pilot_reuse(plan,b,budget,store):
    if '_pilot_reuse' not in b:b['_pilot_reuse']=_pilot_reuse_original(plan,b,budget,store)
    return b['_pilot_reuse']
