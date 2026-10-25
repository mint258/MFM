"""Build a disk canonical index and file shards for ALL original source roles."""
from __future__ import annotations
import argparse, collections, json, sqlite3, time
from pathlib import Path
from .support import (BOUNDARY, RECORD_COLUMNS, TASKS, TASK_FAMILIES, budget, guard,
    identity, load, need, new_root, ref, require, save)

def sqlstr(value):return "'"+str(value).replace("'","''")+"'"

def make_shards(files, count):
    need(type(count) is int and count>=1,'SHARD_COUNT')
    result=[{'shard_id':i,'files':[],'physical_rows':0,'canonical_rows':0,'compressed_source_bytes_upper_bound':0} for i in range(count)]
    for source in sorted(files,key=lambda x:(-int(x['rows']),-int(x['bytes']),x['path'])):
        target=min(result,key=lambda x:(x['physical_rows'],x['compressed_source_bytes_upper_bound'],x['shard_id']))
        target['files'].append(source);target['physical_rows']+=source['rows']
        target['canonical_rows']+=source['latest_rows'];target['compressed_source_bytes_upper_bound']+=source['bytes']
    need(all(len(s['files'])>=16 for s in result),'AT_LEAST_16_REAL_FILE_TASKS_PER_SHARD')
    return result

def run(config_path, output, startup_proof):
    cfg=load(config_path);need(cfg['schema']=='SOURCE_STATUS_AUDIT_CONFIG_V1','CONFIG_SCHEMA')
    guard(startup_proof,config_path,cfg['prepare_output_cap_bytes'])
    for pin in cfg['metadata'].values():require(pin)
    files=load(cfg['metadata']['source_projection']['path'])
    receipt=load(cfg['metadata']['projection_receipt']['path'])
    need(receipt['source_files']==cfg['metadata']['source_projection'],'PROJECTION_REFERENCE_DIFFERS')
    need(receipt['catalog']==cfg['locators']['catalog'] and receipt['verification']==cfg['metadata']['verification'],'CLOSED_AUTHORITY_DIFFERS')
    need(receipt['scientific_source_file_bodies_read'] is False and receipt['status']=='CATALOG_METADATA_PROJECTION_VERIFIED','CLOSED_METADATA_PROJECTION_REQUIRED')
    need(len({r['path'] for r in files})==len(files),'DUPLICATE_SOURCE_PATH')
    need(all(r['inherited_full_readback_verified'] is True and r['family'] in set(TASK_FAMILIES.values()) for r in files),'VERIFIED_FAMILIES_REQUIRED')
    roles=load(cfg['metadata']['roles']['path'])
    need(roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN' and roles['common_population_applied'] is False,'UNCHANGED_SOURCE_ROLES_REQUIRED')
    partitions=[x for x in roles['outputs'] if Path(x['path']).parent.name=='molecule_roles']
    need(len(partitions)==16,'ROLE_PARTITION_COUNT')
    for pin in partitions:require(pin)
    # Fresh authority hashes are computed on the allocated compute node only.
    population=require(cfg['locators']['population']);latest=require(cfg['locators']['latest_molecules'])
    before={str(p):identity(p) for p in (population,latest)}
    root=new_root(output);cap=cfg['prepare_output_cap_bytes'];start=time.monotonic()
    index=root/'canonical.sqlite';started=False
    import duckdb
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='12GiB'")
    spill=root/'spill';spill.mkdir();db.execute('SET temp_directory='+sqlstr(spill));db.execute("SET max_temp_directory_size='8GiB'")
    sq=sqlite3.connect(index)
    try:
        sq.execute('PRAGMA journal_mode=OFF');sq.execute('PRAGMA synchronous=FULL');sq.execute('PRAGMA cache_size=-16384')
        sq.execute('CREATE TABLE records(record_ordinal INTEGER UNIQUE NOT NULL,record_id TEXT PRIMARY KEY,molecule_id TEXT NOT NULL,attempt_id INTEGER NOT NULL,job_id INTEGER NOT NULL,task_id TEXT NOT NULL,lane INTEGER NOT NULL,total_atoms INTEGER NOT NULL,new_role TEXT NOT NULL)')
        db.execute('CREATE VIEW roles AS SELECT * FROM read_parquet(['+','.join(sqlstr(r['path']) for r in partitions)+'])')
        db.execute("CREATE VIEW owners AS SELECT * FROM read_parquet("+sqlstr(latest)+") WHERE state='COMPLETE' AND receipt_context_consistent AND export_published")
        expected_n=sum(v['records'] for v in roles['roles'].values());expected_m=sum(v['molecules'] for v in roles['roles'].values())
        for view in ('roles','owners'):
            need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM '+view).fetchone()==(expected_m,expected_m),'CANONICAL_MOLECULE_AUTHORITY:'+view)
        db.execute('CREATE TEMP TABLE molecules AS SELECT o.molecule_id,o.attempt_id,o.job_id,o.task_id,o.lane,r.records,r.effective_role,r.source_role FROM owners o JOIN roles r USING(molecule_id)')
        db.execute('CREATE TEMP TABLE records AS SELECT p.file_row_number::UBIGINT AS record_ordinal,p.record_id,p.molecule_id,c.attempt_id,c.job_id,c.task_id,c.lane,p.total_atoms,c.effective_role AS new_role,c.records FROM read_parquet('+sqlstr(population)+',file_row_number=true) p JOIN molecules c USING(molecule_id) WHERE upper(p.new_role)=c.source_role')
        counts=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT record_ordinal),count(DISTINCT molecule_id),min(record_ordinal),max(record_ordinal) FROM records').fetchone()
        need(counts==(expected_n,expected_n,expected_n,expected_m,0,expected_n-1),'FULL_RECORD_AND_PHYSICAL_ORDINAL_CONSERVATION')
        need(db.execute('SELECT count(*) FROM (SELECT molecule_id,count(*) n,max(records) expected FROM records GROUP BY molecule_id) WHERE n<>expected').fetchone()[0]==0,'WHOLE_MOLECULE_RECORDS_DIFFER')
        role_counts={r:(n,m) for r,n,m in db.execute('SELECT new_role,count(*),count(DISTINCT molecule_id) FROM records GROUP BY new_role').fetchall()}
        need(role_counts=={r:(v['records'],v['molecules']) for r,v in roles['roles'].items()},'ROLE_MASS_DIFFERS')
        reader=db.execute('SELECT '+','.join(RECORD_COLUMNS)+' FROM records ORDER BY record_ordinal').fetch_record_batch(4096)
        for batch in reader:
            sq.executemany('INSERT INTO records VALUES('+','.join('?' for _ in RECORD_COLUMNS)+')',
                           [tuple(r[c] for c in RECORD_COLUMNS) for r in batch.to_pylist()])
            sq.commit();budget(root,cap)
        need(sq.execute('SELECT count(*) FROM records').fetchone()[0]==expected_n,'SQLITE_RECORD_MASS')
        sq.close();sq=None
        need(sum(x['latest_rows'] for x in files)==len(TASKS)*expected_n,'FOURTEEN_SLOT_MASS_DIFFERS')
        source_jobs={int(x['source_job_id']) for x in files}
        owner_jobs={int(x[0]) for x in db.execute('SELECT DISTINCT job_id FROM records').fetchall()}
        need(source_jobs==owner_jobs,'SOURCE_JOB_SET_DIFFERS_FROM_LATEST_OWNERS')
        for p,old in before.items():need(identity(p)==old,'CANONICAL_AUTHORITY_CHANGED')
        plan={'schema':'SOURCE_STATUS_FULL_PLAN_V1','status':'PREPARED_NOT_SCANNED',**BOUNDARY,
          'config':ref(config_path),'canonical_index':ref(index),'record_count':expected_n,'molecule_count':expected_m,
          'role_counts':roles['roles'],'role_partition_pins':partitions,'sources':cfg['metadata'],'authority_locators':cfg['locators'],
          'task_codes':TASKS,'task_to_family':TASK_FAMILIES,'source_file_count':len(files),'source_job_count':len(source_jobs),
          'source_file_group_count':len({(x['source_job_id'],x['source_file_group']) for x in files}),
          'physical_task_rows':sum(x['rows'] for x in files),'canonical_task_rows':sum(x['latest_rows'] for x in files),
          'noncanonical_physical_rows_expected':sum(x['rows']-x['latest_rows'] for x in files),
          'compressed_source_bytes_upper_bound':sum(x['bytes'] for x in files),'shards':make_shards(files,cfg['shards']),
          'index_strategy':'single immutable disk SQLite, per-worker read-only 16MiB page cache; no whole-owner Python copy',
          'record_ordinal_definition':'zero-based physical file_row_number in SHA-bound formal_record_index.parquet',
          'elapsed_seconds':time.monotonic()-start,'duckdb_version':duckdb.__version__,
          'unique_inode_output_bytes_before_manifest':budget(root,cap),'startup_proof':ref(startup_proof)}
        save(root/'manifest.json',plan,root,cap);return plan
    except BaseException as exc:
        save(root/'failure.json',{'status':'PREPARE_FAILED_PARTIALS_PRESERVED','error':str(exc),'type':type(exc).__name__})
        raise
    finally:
        if sq is not None:sq.close()
        db.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','output','startup-proof'):p.add_argument('--'+key,required=True)
    a=p.parse_args();plan=run(a.config,a.output,a.startup_proof)
    print(json.dumps({'status':plan['status'],'records':plan['record_count'],'shards':len(plan['shards'])}))
if __name__=='__main__':main()