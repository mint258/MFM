"""Single original canonical PM7 HOF scalar projection, never native energy."""
import collections,json
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as PC,inheritance as H
from . import contract as C

def project(ctx,db,cache_plan):
    authority=C.meta(cache_plan['hof_authority_review']);C.need(authority['schema']=='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1'
      and authority['status']=='VERIFIED_FROZEN_PM7_B_SCALAR_READER' and authority['registry_id']==60 and authority['unit']=='kcal/mol'
      and authority['native_energy_fallback_allowed'] is False,'ORIGINAL_FROZEN_CANONICAL_HOF_READER_AUTHORITY')
    owner=authority['latest_owner_reference'];projection=C.meta(authority['projection_receipt_reference'])
    C.need(projection['status']=='CATALOG_METADATA_PROJECTION_VERIFIED' and projection['source_files']==authority['source_files_reference'],'REAL_CLOSED_HOF_SOURCE_METADATA')
    ctx.require(owner);sources=ctx.read(projection['source_files'],64<<20)
    db.execute('CREATE TABLE hof_owners AS SELECT * FROM read_parquet('+C.q(owner['path'])+
      ") WHERE state='COMPLETE' AND receipt_context_consistent AND export_published")
    C.need(db.execute('SELECT count(*) FROM (SELECT molecule_id FROM hof_owners GROUP BY molecule_id HAVING count(*)>1)').fetchone()[0]==0,'UNIQUE_CURRENT_CLOSED_HOF_OWNER')
    db.execute('CREATE TABLE hof(record_id VARCHAR PRIMARY KEY,value_json VARCHAR,duplicate BOOLEAN DEFAULT FALSE)')
    observations=[];pc=H.profile_common()
    for source in sources:
        if source['family']!='pm7_neutral':continue
        if ctx.observe() is not None:break
        targets=db.execute('SELECT r.record_id,r.molecule_id,r.total_atoms,o.attempt_id,o.job_id,o.task_id,o.lane FROM formal r JOIN hof_owners o USING(molecule_id) WHERE r.file_group=? AND o.job_id=?',
          [source['source_file_group'],source['source_job_id']]).fetch_arrow_table().to_pylist()
        if not targets:continue
        wanted={r['record_id']:r for r in targets};note={'source':source,'target_records':len(wanted)}
        try:
            # Original reader verifies inherited full-readback authority, stable
            # current UID/size/frame, exact current-owner five-key/lane/atoms,
            # registry60/f64/convergence and scalar-only physical leaf pruning.
            result=pc.read_hof_file({'ref':source,'owners':wanted});values=result['hof'];duplicates=[]
            for rid,value in values.items():
                PC.validate_hof(value);old=db.execute('SELECT 1 FROM hof WHERE record_id=?',[rid]).fetchone()
                if old:db.execute('UPDATE hof SET duplicate=TRUE WHERE record_id=?',[rid]);duplicates.append(rid)
                else:db.execute('INSERT INTO hof VALUES(?,?,FALSE)',[rid,C.canonical(value).decode()])
            note.update(status='ORIGINAL_SCALAR_READER_CLOSED',observed_records=len(values),duplicate_records=len(duplicates),current_identity=result['identity'],projected_columns=result['projected_columns'])
        except Exception as exc:
            note.update(status='SOURCE_HOF_PENDING_GEOMETRY_NOT_DROPPED',error=repr(exc))
            for rid in wanted:db.execute('INSERT INTO hof VALUES(?,?,FALSE) ON CONFLICT(record_id) DO UPDATE SET duplicate=TRUE',
              [rid,C.canonical(PC.missing_hof('CANONICAL_HOF_SOURCE_READ_OR_VALIDATION_FAILED')).decode()])
        observations.append(note);db.commit()
    ref=ctx.write_json_new(ctx.out/'hof_projection_observations.json',{'schema':'POSTPROCESS_CANONICAL_HOF_SOURCE_OBSERVATIONS_V1',
      'sources':observations,'reader_complete':ctx.stop is None,'authority_reference':cache_plan['hof_authority_review'],'native_energy_fallback':False})
    return ref

def values(db,records):
    result={}
    for r in records:
        row=db.execute('SELECT value_json,duplicate FROM hof WHERE record_id=?',[r['record_id']]).fetchone()
        if row is None:
            owner=db.execute('SELECT 1 FROM hof_owners WHERE molecule_id=?',[r['molecule_id']]).fetchone()
            v=PC.missing_hof('CURRENT_CLOSED_OWNER_MISSING' if owner is None else 'CANONICAL_HOF_RECORD_MISSING')
        else:v=PC.missing_hof('DUPLICATE_CANONICAL_HOF_ACROSS_FILES') if row[1] else json.loads(row[0])
        PC.validate_hof(v);result[r['record_id']]=v
    return result
