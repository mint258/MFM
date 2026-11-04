"""Closed original components, never a successful-parent substitution."""
import json,pathlib
from . import io as I
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as C,cache as CACHE,hof
from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import io as PRE


def common_component(ctx,db):
    p=ctx.plan;m=ctx.read(p['closed_common_manifest_reference']);account=C.meta(p['closed_common_accounting_reference'])
    C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and account['query_returncode']==0
        and account['endpoint']=='202.38.247.57:22' and account['uid']==1278,
        'NATIVE_REAL_FAILED_COMMON_PARENT_NOT_OLD_SUBMITTED5658')
    import csv,io
    parents=C.F.accounting(p['closed_common_accounting_reference'],['4525659'])
    C.need(parents['4525659']['state']=='FAILED' and parents['4525659']['exit_code']=='1:0','REAL_FAILED_COMMON_COMPONENT_ONLY')
    raw=C.G.meta_pin(account['raw_sacct_reference']['path'])
    C.need(raw==account['raw_sacct_reference'],'EXACT_NATIVE_COMMON_RAW_PIN')
    rows=[v for v in csv.DictReader(io.StringIO(pathlib.Path(raw['path']).read_text(encoding='utf-8')),delimiter='|') if v['JobIDRaw'].isdecimal()]
    C.need(len(rows)==1 and rows[0]['JobIDRaw']=='4525659' and rows[0]['UID']=='1278' and rows[0]['State'].split()[0]=='FAILED'
        and rows[0]['ExitCode']=='1:0' and rows[0]['AllocCPUS']=='32' and rows[0]['NodeList']=='compute-0-21' and rows[0]['ElapsedRaw']=='10583',
        'ACTUAL5659_FAILED_HISTORY_RETAINED_NOT_C0')
    C.need(m['schema']=='COMMON_POPULATION_PRODUCER_V1' and m['status']=='PENDING_ACTUAL_PARENT_C0_AND_INDEPENDENT_ROOT_REVIEW'
        and str(m['runtime']['job_id'])=='4525659' and m['runtime']['uid']==1278 and m['config']==p['original_config_reference']
        and m['orders_frozen'] is False and m['geometry_map_frozen_by_this_manifest'] is False and m['random_order_seed']==20261025,
        'ONLY_CLOSED_FUNCTION_COMPONENT_NO_FINAL_COMMON_OR_ORDER_AUTHORITY')
    members=m['membership_tables'];maps=m['physical_geometry_tables'];identities=m['uff_identity_tables']
    C.need(len(members)==16 and len(maps)==32 and len(identities)==16,'EXACT_CLOSED16_MEMBERSHIP32_MAPS16_ORDINARY_IDENTITIES')
    for r in [*members,*maps,*identities]:ctx.require(r)
    db.execute('CREATE VIEW final_common AS SELECT * FROM read_parquet(['+','.join(C.q(r['path']) for r in members)+'])')
    db.execute('CREATE VIEW uff_sources AS SELECT * FROM read_parquet(['+','.join(C.q(r['path']) for r in maps if pathlib.Path(r['path']).name.startswith('uff_sprime-'))+'])')
    expected=sum(r['molecules'] for r in m['roles'])
    C.need(db.execute('SELECT count(*) FROM final_common WHERE common_population').fetchone()[0]==expected
        and db.execute('SELECT count(*) FROM (SELECT molecule_id FROM final_common GROUP BY molecule_id HAVING count(*)<>1)').fetchone()[0]==0,
        'ORIGINAL_CLOSED_MEMBERSHIP_EXACT_ROLES_NO_NEW_FILTER')
    C.need(db.execute('SELECT count(*) FROM uff_sources').fetchone()[0]==sum(r['uff_records'] for r in m['roles']),
        'EXACT_CLOSED_ORDINARY_GEOMETRY_COUNT_NOT_EXTRA_N1')
    return m,expected


def pm7_components(ctx,db,oldplan,base):
    # Original loader creates the same table and preserves any true C0 ancestry.
    PRE.load_for_postprocess(ctx,db)
    origins={}
    for k,kind in (('legacy_cache_parents','legacy'),('previous_precache_parents','day')):
        for e in oldplan[k]:
            r=PRE.M.registration(e,kind);PRE.actual_parent(r,ctx.proof);origins[r['job_id']]=r
    e=dict(ctx.plan['pm7_owner_entry'],receipt_reference=None)
    owner=PRE.M.registration(e,'day');PRE.actual_parent(owner,ctx.proof)
    C.need(owner['job_id']=='4525100' and owner['actual']['state']=='FAILED' and owner['actual']['exit_code']=='1:0'
        and owner['request']['node']=='compute-0-2' and owner['request']['execution_argv'][5]==ctx.plan['pm7_preparation_plan_reference']['path'],
        'REAL_FAILED5100_CANONICAL_SOURCE_NOT_A_NEW_C0')
    origins[owner['job_id']]=owner;ctx.pm7_precache_origins=origins
    receipt_ref=PRE.transfer_ref(owner['root'],pathlib.Path(owner['root'])/'receipt.json');receipt=ctx.read(receipt_ref)
    C.need(receipt['schema']=='PM7_PRECACHE_DAY_RECEIPT_V1' and receipt['scope_key']==PRE.M.KEY and str(receipt['job_id'])==owner['job_id']
        and receipt['plan_reference']==ctx.plan['pm7_preparation_plan_reference'] and receipt['source_plan_reference']==ctx.plan['cache_plan_reference']
        and receipt['startup_proof_reference']==owner['proof_reference'] and receipt['status']=='UNKNOWN_OR_FAILED_NO_CACHE_ACCEPTANCE'
        and receipt['HOF_projection_complete'] is True and receipt['fatal'] is None and receipt['common'] is False
        and receipt['full_cache_release'] is False,'EXACT_CLOSED_HOF_AND_CATALOG_NOT_WHOLE_PARENT_ACCEPTANCE')
    closed=receipt['closed_state_reference'];path=ctx.require(closed)
    C.need(path==pathlib.Path(owner['root'])/'work.duckdb' and not pathlib.Path(str(path)+'.wal').exists(),
        'ACTUAL_TERMINAL_CLOSED_HOF_DB_NO_ACTIVE_WAL')
    db.execute('ATTACH '+C.q(path)+" AS closed_pm7 (READ_ONLY)")
    db.execute('CREATE VIEW hof AS SELECT * FROM closed_pm7.hof')
    db.execute('CREATE VIEW hof_owners AS SELECT * FROM closed_pm7.hof_owners')
    authority=C.meta(base['hof_authority_review']);note=ctx.read(receipt['hof_projection_reference'])
    C.need(authority['registry_id']==60 and authority['unit']=='kcal/mol' and authority['native_energy_fallback_allowed'] is False
        and note['schema']=='POSTPROCESS_CANONICAL_HOF_SOURCE_OBSERVATIONS_V1' and note['reader_complete'] is True
        and note['authority_reference']==base['hof_authority_review'] and note['native_energy_fallback'] is False,'COMPLETE_ORIGINAL_CANONICAL_HOF_NOT_ENERGY_RAW')
    current=ctx.require(authority['latest_owner_reference'])
    sql='SELECT * FROM read_parquet('+C.q(current)+") WHERE state='COMPLETE' AND receipt_context_consistent AND export_published"
    C.need(db.execute('SELECT count(*) FROM (('+sql+') EXCEPT ALL SELECT * FROM hof_owners)').fetchone()[0]==0
        and db.execute('SELECT count(*) FROM (SELECT * FROM hof_owners EXCEPT ALL ('+sql+'))').fetchone()[0]==0,
        'CLOSED_HOF_EXACT_CURRENT_OWNER_SET_BOTH_DIRECTIONS')
    # Original readonly prefixes remain original rows, not copied coordinates.
    db.execute('INSERT INTO prior_cache SELECT * FROM closed_pm7.prior_cache')
    ctx.cache_registered={jid:dict(request=r['request'],submission=r['submission'],accounting=r['actual']) for jid,r in origins.items() if r['kind']=='legacy'}
    db.execute('CREATE TABLE resource_interrupted_cache(molecule_id VARCHAR PRIMARY KEY,row_json VARCHAR)')
    import pyarrow.parquet as pq
    observed={};unknown=0
    for origin in origins.values():
        if origin['kind']!='day':continue
        if origin['job_id']=='4525100':rr,body=receipt_ref,receipt
        else:
            rr=PRE.transfer_ref(origin['root'],pathlib.Path(origin['root'])/'receipt.json');body=ctx.read(rr)
            C.need(str(body['job_id'])==origin['job_id'] and body['startup_proof_reference']==origin['proof_reference']
                and body['source_plan_reference']==ctx.plan['cache_plan_reference'],'EACH_FAILED_COMPONENT_KEEPS_ITS_ACTUAL_OWNER')
        origin['receipt']=body;origin['actual_receipt_reference']=rr
        for ref in body['catalog_part_references']:
            C.need(pathlib.Path(origin['root'])/'catalog_parts'==pathlib.Path(ref['path']).parent,'ONLY_REGISTERED_CLOSED_COMPONENT_CATALOG')
            for batch in pq.ParquetFile(ctx.require(ref)).iter_batches(batch_size=1024):
                for item in batch.to_pylist():
                    row=json.loads(item['row_json']);C.need(item['molecule_id']==row['molecule_id'],'ORIGINAL_CATALOG_MID_BOTH_COLUMNS')
                    if origin['job_id']=='4525100':observed[row['state']]=observed.get(row['state'],0)+1
                    if row['state']=='UNKNOWN_CONSUMED_NO_COMPLETE_PACKET':
                        C.need(origin['job_id']=='4525100' and row['error']=="ValueError('QUOTA200GB_STOP_NEW_MOLECULES')",
                            'ONLY_CONFIRMED_RESOURCE_INTERRUPTED_READONLY_CACHE_CAN_REBUILD')
                        db.execute('INSERT INTO resource_interrupted_cache VALUES(?,?)',[row['molecule_id'],C.canonical(row).decode()]);unknown+=1;continue
                    C.need(row['state'] in ('DURABLE_PACKET','DURABLE_PACKET_RECOVERED','IMPORTED_EXISTING32'),
                        'SCIENTIFIC_OR_SOURCE_UNKNOWN_NOT_SILENTLY_RECALCULATED')
                    if row.get('origin_kind') not in ('DAY_PACKET','LEGACY32'):continue
                    previous=db.execute('SELECT row_json FROM prior_precache WHERE molecule_id=?',[row['molecule_id']]).fetchone()
                    C.need(previous is None or json.loads(previous[0])['geometry_packet_reference']==row['geometry_packet_reference'],
                        'NO_CONFLICTING_CLOSED_PREFIX_PACKET')
                    if previous is None:db.execute('INSERT INTO prior_precache VALUES(?,?,?)',[row['molecule_id'],C.canonical(row).decode(),row.get('origin_job_id',origin['job_id'])])
    C.need(observed==receipt['state_counts'] and unknown==len(receipt['unknown'])==9,'COMPLETE5100_CATALOG_AND_NINE_RESOURCE_UNKNOWN_PRESERVED')
    census,unlisted=PRE.census_claims(ctx,origins);C.need(not unlisted,'NO_UNREGISTERED_CACHE_ATTEMPT_RECALCULATION')
    ctx.controls=PRE.POP.controls(base,ctx.proof);ctx.cache_plan=base
    return dict(receipt_reference=receipt_ref,closed_state_reference=closed,hof_projection_reference=receipt['hof_projection_reference'],
        original_state=owner['actual']['state'],original_unknowns_preserved=9,catalog_state_counts=observed,prior_claim_census_reference=census)


def reused_cache(ctx,db,task,base):
    # These public original functions do all packet/graph/float64/HOF checks.
    result=PRE.reuse_for_postprocess(ctx,db,task)
    if result is not None:return result
    mid=task['meta']['molecule_id'];day=PRE.DAY_LEDGER/(task['cache_key']+'.json');legacy=PRE.PC.LEDGER/(task['cache_key']+'.json')
    if day.exists():
        claim_ref=ctx.reference(day);claim=ctx.read(claim_ref);PRE.check_claim(task,claim,claim_ref,ctx.pm7_precache_origins)
        resource=db.execute('SELECT row_json FROM resource_interrupted_cache WHERE molecule_id=?',[mid]).fetchone()
        C.need(resource is not None,'UNCLOSED_CONSUMED_CACHE_NOT_A_CONFIRMED_RESOURCE_INTERRUPTION')
        row=json.loads(resource[0]);old_task=ctx.read(claim['task_reference'])
        C.need(str(claim['job_id'])=='4525100' and row['claim_reference']==claim_ref and row['cache_key']==task['cache_key']
            and old_task['records']==task['records'] and old_task['hof']==task['hof'] and old_task['cache_key']==task['cache_key'],
            'READONLY_REBUILD_SAME_FROZEN_ORIGINAL_INPUT_NO_NATIVE_ONCE_WRITE')
        return None
    if legacy.exists():
        claim_ref=ctx.reference(legacy);claim=ctx.read(claim_ref)
        if db.execute('SELECT 1 FROM prior_cache WHERE molecule_id=?',[mid]).fetchone():return CACHE.reuse(ctx,db,task,base)
        _,packet=PRE.packet_from_claim(ctx,task,claim,claim_ref,ctx.pm7_precache_origins);return packet
    return None