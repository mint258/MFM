"""Actual-CPU whole-molecule roster and exact32 PM7-only preparation."""
from __future__ import annotations
import argparse,collections,json,pathlib,sys,time
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as C,io as I,inheritance as H
OPTIONS=('plan','root-preflight','quota-reuse-review','output')


def canonical_hof(plan,records,proof,out,budget):
    """Missing/unverified energy never suppresses a source geometry."""
    values={r['record_id']:C.missing_hof('HOF_AUTHORITY_UNVERIFIED') for r in records};observations=[]
    authority=I.read(plan['hof_authority_review'])
    C.need(authority['schema']=='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1' and authority['reviewer']=='root'
        and authority['endpoint']=='202.38.247.57:22' and authority['uid']==1278,'EXPLICIT_INDEPENDENT_HOF_AUTHORITY_REVIEW')
    if plan['hof_mode']=='GEOMETRY_ONLY_UNVERIFIED':
        C.need(authority['status']=='GEOMETRY_ONLY_HOF_UNVERIFIED','UNVERIFIED_HOF_NOT_SILENTLY_UPGRADED');return values,observations
    C.need(authority['status']=='VERIFIED_FROZEN_PM7_B_SCALAR_READER' and authority['registry_id']==60
        and authority['unit']=='kcal/mol' and authority['native_energy_fallback_allowed'] is False,'CANONICAL_REGISTRY60_UNIT_AND_NO_NATIVE_FALLBACK')
    owner_ref=authority['latest_owner_reference'];projection_ref=authority['projection_receipt_reference']
    I.authorized(proof,[owner_ref,projection_ref]);I.source_check(owner_ref);projection=I.read(projection_ref)
    C.need(projection['status']=='CATALOG_METADATA_PROJECTION_VERIFIED','REAL_CLOSED_SOURCE_PROJECTION_REQUIRED')
    I.authorized(proof,[projection[k] for k in ('catalog','verification','source_files')])
    for name in ('catalog','verification','source_files'):I.source_check(projection[name])
    C.need(authority['source_files_reference']==projection['source_files'],'EXACT_CLOSED_HOF_FILE_LOCATORS')
    import duckdb
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='12GB'")
    mids=sorted({r['molecule_id'] for r in records})
    import pyarrow as pa
    db.register('wanted',pa.table({'molecule_id':mids}))
    owners=db.execute('SELECT o.* FROM read_parquet('+C.q(owner_ref['path'])+
        ") o JOIN wanted USING(molecule_id) WHERE state='COMPLETE' AND receipt_context_consistent AND export_published").fetch_arrow_table().to_pylist()
    by_mid={}
    for row in owners:C.need(row['molecule_id'] not in by_mid,'DUPLICATE_CURRENT_OWNER_MOLECULE');by_mid[row['molecule_id']]=row
    sources=I.read(projection['source_files']);pc=H.profile_common();wanted={}
    for row in records:
        owner=by_mid.get(row['molecule_id'])
        values[row['record_id']]=C.missing_hof('CURRENT_CLOSED_OWNER_MISSING' if owner is None else 'CANONICAL_HOF_RECORD_MISSING')
        if owner is not None:wanted[row['record_id']]=dict(row,**{k:owner[k] for k in ('attempt_id','job_id','task_id','lane')})
    known_jobs={r['job_id'] for r in wanted.values()};groups={r['file_group'] for r in records}
    found={};invalid_records={}
    for reference in sources:
        if reference['family']!='pm7_neutral' or reference['source_job_id'] not in known_jobs or reference['source_file_group'] not in groups:continue
        if budget.observe() is not None:
            observations.append({'status':'HOF_PENDING_AFTER_RESOURCE_STOP','budget':budget.report()});break
        targets={rid:r for rid,r in wanted.items() if r['job_id']==reference['source_job_id'] and r['file_group']==reference['source_file_group']}
        if not targets:continue
        try:
            result=pc.read_hof_file({'ref':reference,'owners':targets})
            overlap=set(found)&set(result['hof'])
            for rid in overlap:invalid_records[rid]='DUPLICATE_CANONICAL_HOF_ACROSS_FILES'
            if overlap:observations.append({'source':reference,'status':'DUPLICATE_CANONICAL_HOF_PENDING','record_ids':sorted(overlap)})
            found.update(result['hof']);observations.append({k:v for k,v in result.items() if k!='hof'})
        except Exception as exc:
            for rid in targets:invalid_records[rid]='CANONICAL_HOF_SOURCE_READ_OR_VALIDATION_FAILED'
            observations.append({'source':reference,'status':'HOF_SOURCE_READ_PENDING_NOT_GEOMETRY_EXCLUSION','error':repr(exc)[:16000]})
    for rid,value in found.items():
        C.validate_hof(value)
        if rid not in invalid_records:values[rid]=value
    for rid,reason in invalid_records.items():values[rid]=C.missing_hof(reason)
    I.source_check(owner_ref);db.close();return values,observations


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=True)
    args=p.parse_args();proof,session=I.admit(__file__,args,OPTIONS,'prepare32')
    out=I.new_output(args.output);budget=I.budget(proof,session,out);C.need(budget.observe() is None,'FRESH_ACCOUNT_RESERVATION_BEFORE_BODY')
    budget.start_monitor()
    try:
        fixtures_ref=I.fixtures(out);plan_ref=I.request_ref(args.root_preflight,args.plan);plan=I.plan(plan_ref,proof)
        I.formal_source(plan,proof,out);I.source_check(plan['per_molecule'])
        old_prepared=I.read(plan['golden_prepared']);old_receipt=I.read(plan['golden_profile_receipt'])
        C.need(old_prepared['formal_population']==plan['formal_source'] and old_prepared['molecules']==256
            and old_receipt['status']=='D7_PROFILE_COMPLETED_NOT_FULL_POPULATION' and old_receipt['completed_molecules']==256
            and old_receipt['error_molecules']==0 and old_receipt['prepared']==plan['golden_prepared']
            and plan['golden_manifest'] in old_receipt['outputs'],'ACTUAL_ORIGINAL256_CLOSED_REFERENCE_CHAIN')
        gold_manifest=I.read(plan['golden_manifest']);gold=C.pick_golden(gold_manifest)
        gold_by_id={r['molecule_id']:{k:r[k] for k in ('path','bytes','sha256')} for r in gold}
        import duckdb,pyarrow as pa
        pa.set_cpu_count(16);pa.set_io_thread_count(2)
        db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='12GB'")
        db.execute('CREATE VIEW r AS SELECT * FROM read_parquet('+C.q(plan['formal_source']['path'])+')')
        db.execute('CREATE VIEW p AS SELECT * FROM read_parquet('+C.q(plan['per_molecule']['path'])+')')
        C.need(db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM r').fetchone()==(11231854,11231854,1220466),
            'EXACT_SOURCE_RECORD_AND_MOLECULE_SUPERSET_NO_SPRIME_FILTER')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM p').fetchone()==(1220466,1220466),'EXACT_PER_MOLECULE_SOURCE_TABLE')
        db.execute("""CREATE TABLE mother AS SELECT molecule_id,min(file_group)::INTEGER AS file_group,count(*)::BIGINT AS records,
            max(total_atoms)::BIGINT AS maximum_total_atoms,sha256('pm7-cache-whole-v1:'||molecule_id) AS molecule_hash
            FROM r GROUP BY molecule_id""")
        C.need(db.execute('SELECT count(*) FROM (SELECT molecule_id FROM r GROUP BY molecule_id HAVING count(DISTINCT file_group)<>1)').fetchone()[0]==0,
            'MOLECULE_CANNOT_BE_SPLIT_ACROSS_FILE_GROUPS')
        db.execute("""CREATE TABLE roster AS SELECT m.*,p.S_conformers AS original_pm7_count,p.Sprime_status AS original_Sprime_status_annotation,
            floor((row_number() OVER(PARTITION BY file_group ORDER BY molecule_hash,molecule_id)-1)/5000)::BIGINT AS shard_index
            FROM mother m JOIN p USING(molecule_id)""")
        C.need(db.execute('SELECT count(*),sum(records),count(*) FILTER(WHERE original_pm7_count IS NULL OR records<>original_pm7_count) FROM roster').fetchone()==(1220466,11231854,0),
            'ALL_WHOLE_MOLECULE_RECORD_COUNTS_MUST_MATCH_NO_STATUS_SELECTION')
        C.need(db.execute('SELECT max(length(molecule_id)) FROM roster').fetchone()[0]<=512,'SOFTWARE_SCALAR_ROSTER_STRING_BOUND')
        roster_ref=I.parquet(out/'whole_molecule_roster.parquet',db.execute('SELECT * FROM roster ORDER BY file_group,shard_index,molecule_hash,molecule_id').fetch_arrow_table(),out)
        descriptors=db.execute('SELECT file_group,shard_index,count(*) AS molecules,sum(records)::BIGINT AS records,max(records) AS maximum_records,max(maximum_total_atoms) AS maximum_total_atoms FROM roster GROUP BY ALL ORDER BY ALL').fetch_arrow_table().to_pylist()
        C.need(sum(r['molecules'] for r in descriptors)==1220466 and sum(r['records'] for r in descriptors)==11231854
            and all(0<r['molecules']<=5000 for r in descriptors),'EXACT_WHOLE_MOLECULE_SHARD_UNION_NO_EXECUTION_AUTHORITY')
        shards_ref=I.json_new(out/'future_shard_descriptors.json',{'schema':'PM7_PRECOMMON_WHOLE_MOLECULE_SHARDS_PREPARED_V1',
            'roster_reference':roster_ref,'descriptors':descriptors,'source_molecules':1220466,'source_records':11231854,
            'full_execution_authorized':False,'selection_basis':'file_group then stable SHA whole molecule; no Sprime eligibility'},out)
        db.register('old256',pa.table({'molecule_id':[r['molecule_id'] for r in gold_manifest]}))
        independent=db.execute("""SELECT * FROM (SELECT r.*,row_number() OVER(PARTITION BY file_group
            ORDER BY sha256('pm7-independent-cache-v1:independent:'||molecule_id),molecule_id) AS group_rank
            FROM roster r ANTI JOIN old256 USING(molecule_id))
            ORDER BY group_rank,sha256('pm7-independent-cache-v1:independent:'||molecule_id),molecule_id LIMIT 16""").fetch_arrow_table().to_pylist()
        ids=[r['molecule_id'] for r in gold]+[r['molecule_id'] for r in independent];C.need(len(ids)==len(set(ids))==32,'EXACT16_GOLDEN_PLUS16_INDEPENDENT')
        db.register('selected_ids',pa.table({'molecule_id':ids}))
        metas=db.execute('SELECT r.* FROM roster r JOIN selected_ids USING(molecule_id) ORDER BY molecule_id').fetch_arrow_table().to_pylist()
        columns=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','smiles','file_group','conformer_id')
        # No energy_raw is read or copied as HOF, energy or a missing-energy zero.
        records=db.execute('SELECT '+','.join('r.'+n for n in columns)+' FROM r JOIN selected_ids USING(molecule_id) ORDER BY molecule_id,record_id').fetch_arrow_table().to_pylist()
        grouped={mid:[] for mid in ids}
        for row in records:grouped[row['molecule_id']].append(row)
        C.need(len(records)==sum(m['records'] for m in metas) and len({r['record_id'] for r in records})==len(records),'ENTIRE32_SOURCE_RECORD_UNION')
        hof,observations=canonical_hof(plan,records,proof,out,budget)
        authority={'schema':'PM7_PRECOMMON_CACHE32_SOURCE_AUTHORITY_V1','plan_reference':plan_ref,'formal_source':plan['formal_source'],
            'per_molecule':plan['per_molecule'],'population_molecules':1220466,'population_records':11231854,
            'whole_molecule_roster':roster_ref,'future_shards':shards_ref,'selected_molecule_ids':sorted(ids),
            'golden16_ids':sorted(gold_by_id),'independent16_ids':sorted(set(ids)-set(gold_by_id)),
            'Sprime_SUCCESS_used_as_eligibility':False,'full_execution_authorized':False,'common':False}
        authority_ref=I.json_new(out/'source_authority.json',authority,out);(out/'tasks').mkdir();tasks=[]
        for meta in metas:
            mid=meta['molecule_id'];source_rows=grouped[mid];C.need(len(source_rows)==meta['records'],'NO_PARTIAL_MOLECULE_TASKS')
            key=C.sha({'source':plan['formal_source'],'molecule_id':mid,'record_ids':[r['record_id'] for r in source_rows],
                'payload_sha256':[r['record_payload_sha256'] for r in source_rows],'hof_authority':plan['hof_authority_review'],'recipe':'PM7_CACHE_ONLY_FIXED_NATIVE_ID_V1'})
            task={'schema':'PM7_INDEPENDENT_CACHE32_TASK_V1','meta':meta,'cache_key':key,'records':source_rows,
                'hof':{r['record_id']:hof[r['record_id']] for r in source_rows},'hof_mode':plan['hof_mode'],
                'source_population_authority':authority_ref,'software_bound':C.software_bound(meta['records'],meta['maximum_total_atoms']),
                'golden_packet_reference':gold_by_id.get(mid),'common':False}
            tasks.append({'molecule_id':mid,'cache_key':key,'task_reference':I.json_new(out/'tasks'/(key+'.json'),task,out),
                'golden':mid in gold_by_id,'software_bound':task['software_bound']})
        I.source_check(plan['per_molecule']);I.source_check(plan['formal_source']);db.close()
        budget.observe();ready=budget.stop is None and len(tasks)==32
        receipt={'schema':'PM7_CACHE32_PREPARED_V1','status':'ACTUAL32_FROZEN_NO_GEOMETRY_COMPUTED' if ready else 'PENDING_RESOURCE_STOP_NO_CACHE_DISPATCH',
            'job_id':str(proof['job_id']),'plan_reference':plan_ref,'source_authority_reference':authority_ref,'tasks':tasks,
            'golden_packet_references':[{'molecule_id':mid,'reference':reference} for mid,reference in sorted(gold_by_id.items())],
            'whole_molecule_roster':roster_ref,'future_shards':shards_ref,'hof_source_observations':observations,
            'hof_missing_reason_counts':dict(collections.Counter(v['reason'] for v in hof.values() if not v['valid'])),
            'hof_convergence_null_review_records':sum(bool(v['convergence_null_review']) for v in hof.values()),
            'fixtures_reference':fixtures_ref,'startup_proof_reference':session['proof_reference'],'budget':budget.report(),
            'new_UFF_calls':0,'new_QM_calls':0,'common':False,'full_cache_release':False}
        I.json_new(out/'prepared.json',receipt,out);print({'status':receipt['status'],'tasks':len(tasks)});return 0 if ready else 3
    finally:budget.close_monitor();I.json_new(out/'resource_observations.json',budget.report(),out)


if __name__=='__main__':raise SystemExit(main())
