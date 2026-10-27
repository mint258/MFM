"""Actual CPU identity scan and new full SourceJob/file-order plan, no label IO."""
import argparse,collections,concurrent.futures,importlib,json,multiprocessing,os,sys,time,traceback
from pathlib import Path
from . import contract as C,io as I,worker
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S
from workflows.data_v1_final.labels.streaming_v1.support import legacy
from workflows.data_v1_final.labels.full_projection_v1.control import source_contract

def projector(science):
    legacy(science)
    parent=Path(science['adapter_source_pins'][0]['path']).parent;sys.path.insert(0,str(parent))
    try:module=importlib.import_module('prepare_pilot_plan')
    finally:sys.path.pop(0)
    C.need(Path(module.__file__).absolute()==parent/'prepare_pilot_plan.py','ORIGINAL_CATALOG_PROJECTOR_IMPORT_COLLISION')
    return module.catalog_source_files

def base_sources(catalog,verification):
    all_artifacts={x["path"]:x for x in catalog["artifacts"]}
    base_refs=collections.defaultdict(list)
    for item in verification["files_verified"]:
        if item.get("family")=="base_geometry":
            source=all_artifacts[item["path"]]
            if any(item[k]!=source[k] for k in ("bytes","sha256")):
                raise ValueError("BASE_GEOMETRY_VERIFICATION_PIN_DIFFERS")
            base_refs[int(source["job_id"])].append(item)
    return base_refs

def scan(cfg,proof,root,gate,budget):
    baseline=I.load(I.require(cfg['baseline512_config_reference']));original=I.load(I.require(baseline['owner_plan']))
    prepared=I.load(I.require(cfg['canonical_preparation_reference']));roles=I.load(I.require(cfg['roles_reference']))
    C.need(prepared['schema']=='SOURCE_STATUS_FULL_PLAN_V1' and prepared['canonical_index']==cfg['canonical_index']
      and prepared['authority_locators']['population']==cfg['formal_record_index_reference'],'ORIGINAL_FULL_CANONICAL_AUTHORITY_LOCATORS')
    C.need(roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN' and roles['common_population_applied'] is False
      and roles['roles']==prepared['role_counts'],'FROZEN_UNFILTERED_ALL_SOURCE_ROLE_AUTHORITY')
    footer=I.load(I.require(cfg['footer_parent']['manifest']));book=I.load(I.require(footer['source_inventory_reference']));source_contract(book['files'])
    C.need(footer['status']=='ALL2208_SOURCE_FOOTERS_OBSERVED_VALUES_PENDING' and footer['pending_file_ids']==[] and footer['errors']==[],'ACTUAL_COMPLETE2208_FOOTER_ONLY_AUTHORITY')
    catalog=I.data_json(cfg['catalog_reference']);verification=I.load(I.require(cfg['verification_reference']));project=projector(baseline['science'])
    labels=project(catalog,verification);base=base_sources(catalog,verification);byname={r['path']:r for r in book['files']};members=[*labels,*[r for files in base.values() for r in files]]
    C.need(len(labels)==2024 and sum(map(len,base.values()))==184 and len({r['path'] for r in members})==2208
      and {r['path'] for r in members}==set(byname),'EXACT_ORIGINAL2208_CATALOG_FILES_NOT_CACHE_FILENAME_ORDER')
    for r in members:C.need(all(r[k]==byname[r['path']][k] for k in ('bytes','sha256','family')),'CATALOG_TO_ACTUAL_FOOTER_FILE_IDENTITY')
    C.need(set(base)=={r['source_job_id'] for r in labels},'EXACT_BASE_AND_LABEL_SOURCE_JOB_SET')
    for job in base:C.need({r['family'] for r in labels if r['source_job_id']==job}==set(S.TASK_FAMILIES.values()),'ORIGINAL_EVERY_OWNER_JOB_ALL14_TASK_FAMILIES')
    with I.opened(cfg['canonical_index']) as (canonical,cframe),I.opened(cfg['formal_record_index_reference']) as (formal,fframe):
        db=S.sqlite_ro(Path('/proc/self/fd')/str(canonical.fileno()));db.execute('PRAGMA temp_store=MEMORY')
        try:
            C.need(tuple(r[1] for r in db.execute('PRAGMA table_info(records)'))==S.RECORD_COLUMNS,'EXACT_ORIGINAL_CANONICAL_INDEX_SCHEMA')
            global_counts=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT record_ordinal),count(DISTINCT molecule_id),min(record_ordinal),max(record_ordinal) FROM records').fetchone()
            C.need(global_counts==(11231854,11231854,11231854,1220466,0,11231853),'EXACT_ALL_CANONICAL_KEYS_ORDINALS_AND_MOLECULES')
            counts={}
            for job,role,n,m in db.execute('SELECT job_id,new_role,count(*),count(DISTINCT molecule_id) FROM records GROUP BY job_id,new_role ORDER BY job_id,new_role'):
                C.need(type(job) is int and role in ('TRAIN','VAL','FULL'),'REAL_CANONICAL_JOB_AND_ROLE');counts.setdefault(str(job),{})[role]={'records':n,'molecules':m}
            groups,record_roles,molecule_roles=C.groups(labels,base,counts,roles['roles'])
            C.need(len(groups)==prepared['source_job_count'],'ORIGINAL_PREPARATION_AND_ACTUAL_GROUP_SET_COUNT')
        finally:db.close()
        C.need(not budget.stop(),'RESOURCE_STOP_BEFORE_FORMAL_IDENTITY_SCAN_NO_FULL_PLAN')
        ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(16);reports=[];frames={'canonical':cframe,'formal':fframe}
        with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=worker.initialize,initargs=(cfg,frames,barrier)) as pool:
            pending={pool.submit(worker.scan,(i,lo,hi)) for i,(lo,hi) in enumerate(C.ranges(11231854))}
            while pending:
                done,pending=concurrent.futures.wait(pending,timeout=1,return_when=concurrent.futures.FIRST_COMPLETED);budget.stop()
                for future in done:
                    report=future.result();reports.append(report);S.save(root/('identity_partition_%02d.json'%report['partition']),report,root,C.CAP)
        S.save(root/'identity_partitions.json',{'reports':sorted(reports,key=lambda r:r['partition']),'complete':all(r['complete'] for r in reports)},root,C.CAP)
        C.need(len(reports)==16 and len({r['pid'] for r in reports})==16 and all(r['complete'] for r in reports),'ALL16_ACTUAL_IDENTITY_PARTITIONS_COMPLETE_NO_UNKNOWN')
        observed=collections.Counter()
        for r in reports:
            for row in r['counts']:observed[(str(row['source_job_id']),row['role'])]+=row['records']
        expected={(j,r):v['records'] for j,rs in counts.items() for r,v in rs.items()}
        C.need(dict(observed)==expected and sum(r['records_verified'] for r in reports)==11231854,'FORMAL_TO_SQLITE_FULL_JOB_ROLE_RECORD_MASS')
        validation=S.save(root/'source_sha_validation.json',{'status':'CURRENT_CPU_SAME_FD_FULL_SHA_AND_ALL_FORMAL_ORDINALS_VERIFIED','job_id':str(proof['job_id']),
          'uid':os.getuid(),'canonical_reference':cfg['canonical_index'],'formal_reference':cfg['formal_record_index_reference'],'canonical_frame':cframe,'formal_frame':fframe,
          'records':11231854,'molecules':1220466,'workers':16,'partition_pids':[r['pid'] for r in reports]},root,C.CAP)
    basis=original['element_basis'];C.need(basis==sorted(set(basis)) and all(type(z) is int and 1<=z<=118 for z in basis),'ORIGINAL_GLOBAL_IDENTITY_ELEMENT_BASIS')
    plan={'schema':'CANONICAL_STREAM_GROUP_PLAN_V1','mode':'full','status':'NEW_FULL_LOGICAL_PLAN_CPU_VERIFIED_PENDING_ACTUAL_C0_ROOT_FREEZE',
      'groups':groups,'records':11231854,'molecules':1220466,'roles':record_roles,'role_molecules':molecule_roles,'source_group_count':len(groups),
      'task_codes':original['task_codes'],'element_basis':basis,'field_map':original['field_map'],'canonical_index':cfg['canonical_index'],
      'formal_record_index_reference':cfg['formal_record_index_reference'],'source_inventory_reference':footer['source_inventory_reference'],
      'footer_manifest_reference':cfg['footer_parent']['manifest'],'baseline512_config_reference':cfg['baseline512_config_reference'],
      'original_pilot_group_plan_reference':baseline['owner_plan'],'source_sha_validation_reference':validation,'TSQR_chunk':256,
      'logical_order':'SOURCE_JOB_ASC_THEN_ORIGINAL_VERIFIED_FILE_LIST_THEN_PHYSICAL_ROW','QR_reduction':'ORIGINAL_ORDERED_LEFT_FOLD',
      'original_full_plan_was_null':True,'new_plan_frozen_by_this_process':False,'all_original_roles_scanned':True,'full_common_population_frozen':False,
      'normalization_completed':False,'labels_or_numeric_calibration_read':False,'label_values_or_masks_modified':False,'old_books_or_HOLD_modified':False}
    # Readers need the native source locator and family only; drop redundant catalog prose,
    # never reorder files or change any original locator/owner group.
    for group in groups:
        for field in ('base_files','label_files'):
            before=[tuple(r[k] for k in ('path','bytes','sha256')) for r in group[field]]
            group[field]=[{k:r[k] for k in ('path','bytes','sha256','family')} for r in group[field]]
            C.need(before==[tuple(r[k] for k in ('path','bytes','sha256')) for r in group[field]],'LOSSLESS_ORIGINAL_FILE_LOCATOR_SEQUENCE')
    planref=I.save(root/'group_plan.json',plan)
    manifest={'schema':'FULL_LOGICAL_OWNER_PLAN_BUILD_RECEIPT_V2','status':'CPU_GENERATED_NOT_ROOT_FROZEN_NOT_NUMERIC_COVERAGE','job_id':str(proof['job_id']),
      'config':I.pin(cfg['config_path']),'group_plan_reference':planref,'source_sha_validation_reference':validation,'identity_partitions_reference':I.pin(root/'identity_partitions.json'),
      'records':11231854,'molecules':1220466,'roles':record_roles,'role_molecules':molecule_roles,'source_groups':len(groups),'base_files':184,'label_files':2024,'task_slots':14,
      'actual_worker_pids':sorted({r['pid'] for r in reports}),'fixture_gate':gate,'startup_request_reference':proof['request_reference'],
      'old1904_remains_TIMEOUT':True,'old_books_modified':False,'new_UFF_QM_calls':0,'numeric_label_values_read':False,'final_Common_D4':False,
      'full_numeric_production_still_requires_actual512_exact_legacy_profile':True}
    I.save(root/'manifest.json',manifest);return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','startup-proof','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();cfg,proof,binding=I.guard(a.config,a.startup_proof,a.output);root=S.new_root(a.output);budget=None
    try:
        gate=I.fixtures(root);cfg['config_path']=a.config;budget=I.Budget(cfg,proof,binding,root);return scan(cfg,proof,root,gate,budget)
    except BaseException as exc:
        S.save(root/'failure.json',{'status':'NO_FULL_LOGICAL_PLAN_AUTHORITY','error':repr(exc),'traceback':traceback.format_exc(),'partials_preserved':True,
          'old_books_unchanged':True,'automatic_retry':False,'old1904_remains_TIMEOUT':True},root,C.CAP);raise
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':raise SystemExit(main())
