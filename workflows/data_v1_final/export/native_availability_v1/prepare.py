"""Allocation-only declaration preparation; never stat or open any raw archive."""
from __future__ import annotations
import collections,concurrent.futures as cf,hashlib,json,pathlib,threading
from . import contract as C,reader as I


def body_json(reference,references,cap):
    p,before=I.declared(reference,references);C.need(reference['bytes']<=cap,'BOUNDED_DECLARED_JSON_DATA')
    with p.open('rb') as f:raw=f.read(cap+1)
    C.need(I.frame(p)==before and len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'],'ACTUAL_DATA_JSON_SHA')
    return json.loads(raw,object_pairs_hook=I.no_duplicates)


def discover(plan,check):
    import pyarrow.parquet as pq
    inputs=plan['input_authority_references'];prepared=C.meta(inputs['source_prepared']);audit=C.meta(inputs['audit_membership'])
    references=plan['data_references'];selected=audit['selected_records'];p,before=I.declared(selected,references)
    C.need(selected['bytes']<=2<<20,'ORIGINAL_SMALL_AUDIT_MEMBERSHIP_DATA')
    with p.open('rb') as f:raw=f.read((2<<20)+1)
    C.need(len(raw)==selected['bytes'] and hashlib.sha256(raw).hexdigest()==selected['sha256'],'MEMBERSHIP_WHOLE_SHA')
    del raw
    f=pq.ParquetFile(p)
    try:audit_ids=set(f.read(columns=['record_id'],use_threads=False).column(0).to_pylist())
    finally:f.close()
    C.need(I.frame(p)==before and len(audit_ids)==selected['rows'],'AUDIT_IDS_AND_STABLE_INPUT')
    indexref=prepared['canonical_index'];index,indexpath,indexbefore=I.readonly(indexref,references)
    witness=C.meta(inputs['witness']);priority=[]
    try:
        for oid in sorted({r['record_ordinal'] for r in witness['witnesses']}):
            row=index.execute('SELECT record_id FROM records WHERE record_ordinal=?',(oid,)).fetchone()
            if row is not None and row[0] in audit_ids:priority.append(row[0])
    finally:index.close()
    C.need(I.frame(indexpath)==indexbefore,'CANONICAL_INDEX_CHANGED')
    ordered=list(dict.fromkeys([*priority,*sorted(audit_ids)]))[:32];C.need(len(ordered)==32,'EXACT32_ORIGINAL_AUDIT_RECORDS')
    barrier=threading.Barrier(16)
    def owners(chunk):
        barrier.wait(timeout=60);db,path,old=I.readonly(indexref,references);rows=[]
        try:
            for rid in chunk:
                check();row=db.execute('SELECT record_ordinal,record_id,molecule_id,attempt_id,job_id,task_id,lane,total_atoms,new_role '
                    'FROM records WHERE record_id=?',(rid,)).fetchone()
                C.need(row is not None,'AUDIT_CANONICAL_RECORD_MISSING');rows.append(dict(row))
        finally:db.close()
        C.need(I.frame(path)==old,'CANONICAL_INDEX_CHANGED_DURING_KEYS')
        return {'pid':__import__('os').getpid(),'native_thread_id':threading.get_native_id(),'rows':rows}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        reports=list(pool.map(owners,[ordered[i::16] for i in range(16)]))
    C.need(len({r['native_thread_id'] for r in reports})==16,'SIXTEEN_ACTUAL_METADATA_WORKERS')
    owners_by_id={row['record_id']:row for r in reports for row in r['rows']}
    wanted={r['molecule_id'] for r in owners_by_id.values()};latestref=prepared['authority_locators']['latest_molecules']
    p,before=I.declared(latestref,references);latest={};f=pq.ParquetFile(p)
    names=['molecule_id','state','attempt_id','job_id','task_id','lane','archive_path','receipt_context_consistent','export_published','execution_id']
    try:
        for batch in f.iter_batches(columns=names,batch_size=4096,use_threads=False):
            check()
            for row in batch.to_pylist():
                if row['molecule_id'] in wanted:
                    C.need(row['molecule_id'] not in latest,'DUPLICATED_LATEST_MOLECULE');latest[row['molecule_id']]=row
    finally:f.close()
    C.need(I.frame(p)==before and set(latest)==wanted,'EXACT_LATEST_OWNER_COVERAGE_AND_STABILITY')
    catalog=body_json(prepared['authority_locators']['catalog'],references,16<<20)
    artifacts={}
    for r in catalog['artifacts']:
        ref=C.triple(r);C.need(ref['path'] not in artifacts or artifacts[ref['path']]==ref,'CATALOG_CONFLICTING_ARTIFACT');artifacts[ref['path']]=ref
    records=[];keys=[];archives=[]
    for rid in ordered:
        owner=owners_by_id[rid];current=latest[owner['molecule_id']]
        C.need(current['state']=='COMPLETE' and current['receipt_context_consistent'] is True
            and current['export_published'] is True,'CANONICAL_COMPLETED_SCI_OWNER')
        for name in ('molecule_id','attempt_id','job_id','task_id','lane'):
            C.need(type(owner[name]) is type(current[name]) and owner[name]==current[name],'EXACT_OWNER_TYPES_AND_VALUES:'+name)
        archive=artifacts.get(current['archive_path']);C.need(archive is not None,'ARCHIVE_HAS_NO_CLOSED_PRODUCER_REFERENCE')
        C.need(type(current['execution_id']) is str and bool(current['execution_id']),'EXPLICIT_CANONICAL_EXECUTION_ID')
        # Do not stat/hash/open archive here: its declared stage2 DATA set does not exist yet.
        archives.append(archive);records.append(owner)
        for calc in C.CALCS:keys.append({'record_id':rid,'calc_type':calc,'execution_id':current['execution_id'],
            'owner':owner,'archive_reference':archive})
    C.need(len(keys)==384 and len({(r['record_id'],r['calc_type'],r['execution_id']) for r in keys})==384,'EXACT384_UNIQUE_KEYS')
    return {'selected_records':records,'execution_keys':keys,'archive_data_references':C.unique(archives),
        'preparation_worker_observations':[{k:v for k,v in r.items() if k!='rows'} for r in reports],
        'selection_rule':'existing original audit witness IDs first if eligible; then original audit record_id lexicographic; fixed32 before archive lookup',
        'canonical_whole_SHA_state':'INHERITED_CLOSED_PRODUCER_REFERENCE_STABLE_FSTAT_THIS_PASS',
        'archives_opened':0,'archive_data_freshly_hashed':False}