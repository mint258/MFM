"""Exact bounded-source roles and original base/actual-child exclusion rule."""
import collections,json,pathlib,sqlite3
from . import contract as C,io as I
from workflows.data_v1_final.labels.common_train_normalization_day_v1.authority import eligible
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,identity

def build(plan,root,coverage,geometry):
    import pyarrow.parquet as pq
    root=pathlib.Path(root);root.mkdir();source=sqlite_ro(I.require(coverage['parts_catalog']));frame=identity(coverage['parts_catalog']['path'])
    destination=sqlite3.connect(root/'eligibility.sqlite');destination.execute('PRAGMA journal_mode=DELETE');destination.execute('PRAGMA synchronous=FULL')
    destination.executescript('CREATE TABLE eligibility(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job TEXT,source_role TEXT,effective_role TEXT,common_population INTEGER,geometry_id TEXT,parent_geometry_id TEXT,fit_eligible INTEGER,fit_reason TEXT);CREATE INDEX side_job ON eligibility(job,ordinal);')
    bases={};excluded=set();target=geometry['diagnostic_target_reference']
    for batch in pq.ParquetFile(I.require(geometry['table_references']['geometries'])).iter_batches(batch_size=2048,use_threads=False):
        for row in batch.to_pylist():
            if row['geometry_source']=='pm7' and row['parent_geometry_id'] is None:
                key=(row['molecule_id'],row['native_record_id']);C.need(key not in bases,'UNIQUE_ACTUAL_PILOT_PM7_BASE');bases[key]=row
    for batch in pq.ParquetFile(I.require(target)).iter_batches(batch_size=2048,use_threads=False):
        for row in batch.to_pylist():
            key=(row['molecule_id'],row['geometry_source'],row['geometry_id']);C.need(key not in excluded,'UNIQUE_ACTUAL_DIAGNOSTIC_TARGET');excluded.add(key)
    C.need(geometry['all_in_scope_actual_direct_children_bound']is True and geometry['unknown_input_bindings']==0,
        'NO_FIT_BEFORE_REAL_IN_SCOPE_CHILD_INPUT_DOUBLE_HASH_CLOSURE')
    counts=collections.Counter();roles=collections.Counter();records=fit=0
    try:
        for ordinal,rid,mid,job,role,raw,_ in source.execute('SELECT ordinal,rid,mid,job,role,owner,seen FROM selected ORDER BY ordinal'):
            C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_PILOT_ELIGIBILITY_PARTIAL_NOT_ACCEPTED')
            owner=json.loads(raw);base=bases.get((mid,rid));C.need(base is not None,'EVERY_SELECTED_RECORD_HAS_REAL_NATIVE_PM7_GEOMETRY')
            key=(mid,'pm7',base['geometry_id']);parent=None
            # Exact original predicate object; actual child completeness is
            # proven above, so no provenance-parent or task-name guess is used.
            ok,reason=eligible(role,True,key,parent,excluded)
            destination.execute('INSERT INTO eligibility VALUES(?,?,?,?,?,?,?,?,?,?,?)',(ordinal,rid,mid,job,role,role,1,base['geometry_id'],None,int(ok),reason))
            records+=1;fit+=int(ok);counts[reason]+=1;roles[role]+=1
        C.need(records==coverage['records'] and fit>0 and sum(counts.values())==records,'ALL_SELECTED_OWNERS_FIT_PLUS_EXCLUDED_MASS')
        C.need(destination.execute("SELECT count(*) FROM eligibility WHERE fit_eligible AND effective_role<>'TRAIN'").fetchone()[0]==0,'NO_VAL_FULL_OR_UNKNOWN_ROLE_FIT')
        destination.commit()
    finally:destination.close();source.close();C.need(identity(coverage['parts_catalog']['path'])==frame,'CLOSED_SELECTED_CATALOG_FRAME_UNCHANGED')
    return I.save(root/'manifest.json',{'schema':'PROVISIONAL_EXISTING_SPRIME_TRAIN_ELIGIBILITY_V1','status':'EXACT_SELECTED_OWNER_ANTI_ACTUAL_D5_TARGETS_NOT_FINAL_COMMON',
        'records':records,'fit_records':fit,'original_role_counts':dict(roles),'reason_counts':dict(counts),
        'eligibility_reference':I.allow(I.pin(root/'eligibility.sqlite')),'actual_geometry_components_reference':geometry['manifest_reference'],
        'whole_full_Common_or_D4_release':False,'VAL_or_FULL_fit':False})

def lookup(db,owner):
    row=db.execute('SELECT rid,mid,job,source_role,effective_role,common_population,geometry_id,parent_geometry_id,fit_eligible,fit_reason FROM eligibility WHERE ordinal=?',(owner['record_ordinal'],)).fetchone()
    C.need(row is not None and row[:4]==(owner['record_id'],owner['molecule_id'],owner['job_id'],owner['new_role']),'UNCHANGED_SOURCE_OWNER_ROLE_AND_JOB_PILOT_SIDE_BINDING')
    return dict(owner,source_role=row[3],effective_role=row[4],common_population=bool(row[5]),geometry_source='pm7',geometry_id=row[6],parent_geometry_id=row[7],fit_eligible=bool(row[8]),fit_reason=row[9])
