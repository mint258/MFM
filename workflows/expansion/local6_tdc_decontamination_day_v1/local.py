"""Bounded existing Parquet projections, then deterministic strict export/readback."""
import collections,concurrent.futures as cf,sqlite3
from . import contract as C,io as I,projection as P
COLUMNS=('dataset','source_id','role','inchikeys','non_h_composition_json','memberships',
    'missing_full_key','missing_identity_or_composition','unresolved_source_variant','conservative_reason')

def unit(plan,entry,out,budget):
    import pyarrow.parquet as pq
    budget.check()
    root=out/'units'/entry['unit_id'];root.mkdir(parents=True,mode=0o700);writers={};audit=I.Lines(root/'provenance.DATA.jsonl',budget)
    counts=collections.Counter();datasets=collections.Counter();roles=collections.Counter();unresolved=collections.Counter();flags=collections.Counter()
    try:
        with I.held(entry['file'],[C.ROOT/'artifacts/expansion/identity'],plan['data_references']) as (f,_):
            parquet=pq.ParquetFile(f);C.need(parquet.metadata.num_rows==entry['counts']['records'] and set(COLUMNS)<=set(parquet.schema_arrow.names),'ORIGINAL_CLOSED_PARQUET_COLUMNS_AND_FOOTER')
            ordinal=0
            for batch in parquet.iter_batches(batch_size=4096,columns=list(COLUMNS)):
                budget.check()
                for row in batch.to_pylist():
                    value,original=P.local(row);d=row['dataset'];datasets[d]+=1;roles[row['role']]+=1;counts['records']+=1
                    for key in ('missing_full_key','missing_identity_or_composition','unresolved_source_variant'):
                        C.need(type(row[key])is bool,'ORIGINAL_SOURCE_STATUS_FLAGS_NOT_COERCED');flags[key]+=row[key]
                    if value is not None:
                        if d not in writers:writers[d]=I.Lines(root/(d+'.jsonl'),budget)
                        writers[d].append(value)
                    else:unresolved[d]+=1
                    audit.append({'original_unit':entry['unit_id'],'physical_row_ordinal':ordinal,'source_reference':entry['file'],
                        'original_status_and_memberships':original,'strict_identity_emitted':value is not None,
                        'graph_or_error_state_upgraded':False});ordinal+=1
        C.need(counts['records']==entry['counts']['records'] and dict(datasets)==entry['datasets'] and dict(roles)==entry['roles'],'EVERY_UNIT_SOURCE_ROLE_DATASET_CONSERVATION')
        C.need(all(flags[k]==entry['counts'][k] for k in flags),'ORIGINAL_FLAGS_PRESERVED_NO_CHEMICAL_RECLASSIFICATION')
        return {'unit_id':entry['unit_id'],'records':counts['records'],'datasets':dict(datasets),'roles':dict(roles),'unresolved':dict(unresolved),
            'identity_parts':{d:w.close() for d,w in writers.items()},'provenance_DATA_reference':audit.close()}
    finally:
        for w in writers.values():w.close()
        audit.close()

def run(plan,authority,out,budget):
    out.mkdir(parents=True,mode=0o700);reports=[];pending={};iterator=iter(authority['units'])
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        try:
            while True:
                while len(pending)<32:
                    try:entry=next(iterator)
                    except StopIteration:break
                    budget.check();pending[pool.submit(unit,plan,entry,out,budget)]=entry['unit_id']
                if not pending:break
                done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
                for future in done:reports.append(future.result());del pending[future]
        except BaseException as exc:
            if budget.reason is None:budget.reason={'type':type(exc).__name__,'reason':'STOP_NEW_UNITS_AFTER_FIRST_PROJECTION_FAILURE'}
            raise
        finally:
            # Executor context naturally drains existing reads; never cancels science or signals.
            pass
    C.need(len(reports)==404 and {v['unit_id'] for v in reports}=={v['unit_id'] for v in authority['units']},'ALL404_CLOSED_PROJECTIONS_NO_RETRY')
    totals=collections.Counter()
    for r in reports:totals.update(r['datasets'])
    C.need(dict(totals)==authority['local_counts']['datasets'],'ALL11398552_SOURCE_ROWS_NOT_COMMON_FILTERED')
    dbpath=out/'source_id_readback.sqlite';budget.db_paths.append(dbpath);db=sqlite3.connect(dbpath)
    db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA temp_store=FILE')
    db.execute('CREATE TABLE seen(dataset TEXT NOT NULL,source_id TEXT NOT NULL,PRIMARY KEY(dataset,source_id)) WITHOUT ROWID')
    outputs={};partial={};tx=0;txbytes=0
    try:
        for dataset in sorted({**C.PRIMARY,**C.PARTIAL}):
            writer=I.Lines(out/(dataset+'.strict5.jsonl'),budget);roles=collections.Counter();n=0;raw=[]
            try:
                for r in sorted(reports,key=lambda x:x['unit_id']):
                    ref=r['identity_parts'].get(dataset)
                    if ref is None:continue
                    raw.append(next(u['file'] for u in authority['units'] if u['unit_id']==r['unit_id']))
                    for row,_ in I.rows({k:ref[k] for k in ('path','bytes','sha256')},budget.check):
                        P.identity_keys(row);C.need(set(row)==P.ALLOWED_IDENTITY_FIELDS,'STRICT5_REPLAY_WITHOUT_EXTRA_COLUMNS')
                        db.execute('INSERT INTO seen VALUES(?,?)',(dataset,row['source_id']));tx+=1;txbytes+=len(row['source_id'].encode())
                        if tx>=4096 or txbytes>=16<<20:db.commit();tx=0;txbytes=0;budget.check()
                        writer.append(row);roles[row['role']]+=1;n+=1
                ref=writer.close();db.commit();missing=sum(r['unresolved'].get(dataset,0) for r in reports)
                expected={**C.PRIMARY,**C.PARTIAL}[dataset]
                C.need(n+missing==expected and db.execute('SELECT count(*) FROM seen WHERE dataset=?',(dataset,)).fetchone()[0]==n,'UNIQUE_PHYSICAL_SOURCE_IDS_AND_MASS')
                if dataset in C.PRIMARY:C.need(missing==0,'PRIMARY_NO_UNRESOLVED_IDENTITY_OR_COMPOSITION')
                read=I.readback(ref,list(roles),[''],budget.check)
                value={'dataset':dataset,'identities':ref,'records':n,'original_physical_rows':expected,'unresolved_without_identity_or_composition':missing,
                    'role_counts':dict(roles),'required_roles':sorted(roles),'required_subdatasets':[''],'raw_artifacts':C.unique(raw),
                    'readback':read,'role_semantics':'ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY','Common_or_effective_roles_applied':False}
                (outputs if dataset in C.PRIMARY else partial)[dataset]=value
            finally:writer.close()
    finally:db.close()
    return {'primary6':outputs,'original_Molnet6_partial_only':partial,'all_source_rows':sum(totals.values()),
        'unit_results':reports,'source_ID_census_reference':C.Q.pin(dbpath),'new_graph_or_key_calls':0}
