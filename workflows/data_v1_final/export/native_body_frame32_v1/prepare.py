"""Actual CPU metadata/catalog-only declaration seam; never open base/raw bodies."""
from __future__ import annotations
import concurrent.futures as cf,hashlib,json,os,pathlib,threading
from workflows.data_v1_final.export.native_availability_v1 import reader as I
from . import contract as C,reader as D


def base_candidate(artifacts,owner,group):
    found=[]
    for value in artifacts:
        p=pathlib.Path(value['path'])
        if value.get('family')=='base_geometry' and value.get('job_id')==owner['job_id'] and p.name=='base_geometry.parquet':
            if p.parent.name=='group_'+str(group) and len(p.parents)>3 and p.parents[3].name=='task_'+owner['task_id']:
                found.append(C.triple(value))
    C.need(len(found)==1,'UNIQUE_ORIGINAL_OWNER_GROUP_BASE_PRODUCER_REFERENCE')
    return found[0]


def discover(plan,prepared,old_plan,module,check):
    inputs=prepared['input_authority_references'];refs=plan['data_references']
    dicts=I.dictionaries(inputs['dictionary_manifest'],refs)
    barrier=threading.Barrier(16)
    def worker(index):
        barrier.wait(timeout=60);zstd=module.Zstd();result=[];opens=closes=0
        local=prepared['execution_keys'][index::16];groups={}
        for item in local:groups.setdefault(item['archive_reference']['path'],[]).append(item)
        try:
            for items in groups.values():
                check();ref=items[0]['archive_reference']
                with D.archive(ref,refs,check,False) as db:
                    opens+=1;header=I.archive_header(db,old_plan,dicts)
                    for item in items:
                        check();row,meta,observed=D.metadata(db,item,old_plan,dicts,zstd,header)
                        result.append({'record_id':item['record_id'],'calc_type':item['calc_type'],'execution_id':item['execution_id'],
                            'owner':item['owner'],'archive_reference':ref,'file_group':meta['file_group'],
                            'source_reference':meta['source_reference'],'source_payload_sha256':meta['source_payload_sha256'],
                            'input_file_sha256':meta['input_file_sha256'],'input_bundle_sha256':meta['input_bundle_sha256'],
                            'raw_sha256':row['raw_sha256'].lower(),'raw_bytes':row['raw_bytes'],
                            'reproduction_package_sha256':meta['reproduction_package_sha256']})
                closes+=1
        finally:zstd.close()
        return {'rows':result,'native_thread_id':threading.get_native_id(),'sqlite_opens':opens,'sqlite_closes':closes}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:reports=list(pool.map(worker,range(16)))
    C.need(len({r['native_thread_id'] for r in reports})==16,'ACTUAL16_METADATA_THREADS')
    source=C.meta(inputs['source_prepared']);catalogref=C.triple(source['authority_locators']['catalog'])
    C.need(catalogref['bytes']<=16<<20,'BOUNDED_ORIGINAL_CATALOG_DATA')
    with D.held(catalogref,refs,check,True) as (path,fd,before):
        raw=os.read(fd,catalogref['bytes']+1)
        C.need(len(raw)==catalogref['bytes'],'CATALOG_EXACT_DECLARED_LENGTH')
        catalog=json.loads(raw,object_pairs_hook=I.no_duplicates)
    rows={r['record_id']:[] for r in prepared['selected_records']}
    for report in reports:
        for row in report['rows']:rows[row['record_id']].append(row)
    locators=[]
    for owner in prepared['selected_records']:
        entries=rows[owner['record_id']]
        C.need(len(entries)==12 and {e['calc_type'] for e in entries}==set(C.CALCS),'EXACT_RECORD12_BEFORE_BASE_DISCOVERY')
        group=entries[0]['file_group'];payload=entries[0]['source_payload_sha256'];pointer=entries[0]['source_reference']
        C.need(all(e['owner']==owner and e['file_group']==group and e['source_payload_sha256']==payload
            and e['source_reference']==pointer for e in entries),'ALL12_ORIGINAL_SOURCE_GEOMETRY_BINDINGS_AGREE')
        locators.append({'record_id':owner['record_id'],'owner':owner,'file_group':group,
            'source_payload_sha256':payload,'source_reference':pointer,
            'base_reference':base_candidate(catalog['artifacts'],owner,group),
            'execution_metadata':{e['calc_type']:e for e in entries}})
    C.need(len(locators)==32 and sum(len(r['execution_metadata']) for r in locators)==384,'EXACT32_BY12_LOCATOR_MASS')
    return {'geometry_locators':locators,'base_geometry_data_references':C.unique([r['base_reference'] for r in locators]),
        'base_geometry_files_opened':0,'scientific_BLOBs_fetched':0,'input_bodies_read':0,
        'sqlite_opens':sum(r['sqlite_opens'] for r in reports),'sqlite_closes':sum(r['sqlite_closes'] for r in reports),
        'metadata_worker_thread_ids':[r['native_thread_id'] for r in reports],
        'catalog_current_whole_SHA_verified':True,'raw_archive_whole_SHA_state':'INHERITED_PRIOR_CLOSED_PRODUCER_SHA_STABLE_FSTAT_THIS_STAGE'}
