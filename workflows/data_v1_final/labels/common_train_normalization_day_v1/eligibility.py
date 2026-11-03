"""All canonical owners retained; only actual Common TRAIN minus D5 may fit."""
import collections,json,sqlite3
from pathlib import Path
from . import contract as C,io as I,authority as A
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity,sqlite_ro

def build(plan,root):
    import duckdb
    C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_BEFORE_ELIGIBILITY')
    root=Path(root);root.mkdir();db=duckdb.connect(str(root/'authority.duckdb'))
    db.execute('SET threads=1');db.execute("SET memory_limit='8GB'")
    spill=root/'spill';spill.mkdir();db.execute('SET temp_directory='+I.sqlstr(spill))
    db.execute('SET max_temp_directory_size='+I.sqlstr(str(plan['spill_cap_bytes'])+'B'))
    index=sqlite_ro(I.require(plan['canonical_index']));before=identity(plan['canonical_index']['path'])
    side=sqlite3.connect(root/'eligibility.sqlite');side.execute('PRAGMA journal_mode=DELETE');side.execute('PRAGMA synchronous=FULL')
    side.execute('PRAGMA max_page_count='+str(plan['eligibility_cap_bytes']//4096));side.execute('PRAGMA cache_size=-16384')
    side.executescript('CREATE TABLE eligibility(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job TEXT,source_role TEXT,effective_role TEXT,common_population INTEGER,geometry_id TEXT,parent_geometry_id TEXT,fit_eligible INTEGER,fit_reason TEXT); CREATE INDEX side_job ON eligibility(job,ordinal);')
    counts=collections.Counter();total=0;fit=0;proof=None
    try:
        # Original complete both-source diagnostic and direct-child checks; only IO import differs.
        proof=A.install_authority(db,{'authority':plan['authority']})
        C.need(db.execute('SELECT count(*) FROM (SELECT molecule_id,geometry_source,geometry_id,count(*) n FROM targets GROUP BY ALL HAVING n<>1)').fetchone()[0]==0,'NO_DUPLICATE_DIAGNOSTIC_TARGET_KEYS')
        db.execute('CREATE TEMP TABLE base_pm7 AS SELECT * FROM geometry WHERE geometry_source=\'pm7\' AND parent_geometry_id IS NULL')
        db.execute('CREATE TEMP TABLE excluded_pm7 AS SELECT * FROM diagnostic WHERE geometry_source=\'pm7\'')
        groups=I.load_data(plan['logical_group_plan_reference'],2<<20)['groups'];C.logical(groups)
        db.execute('CREATE TEMP TABLE owner_rows(ordinal BIGINT,rid VARCHAR,mid VARCHAR,job VARCHAR,source_role VARCHAR)')
        for group in groups:
            C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_ELIGIBILITY_PENDING_NO_POPULATION_ACCEPTANCE')
            db.execute('DELETE FROM owner_rows')
            cur=index.execute('SELECT record_ordinal,record_id,molecule_id,job_id,new_role FROM records WHERE job_id=? ORDER BY record_ordinal',(group['source_job_id'],))
            while True:
                rows=cur.fetchmany(2048)
                if not rows:break
                db.executemany('INSERT INTO owner_rows VALUES(?,?,?,?,?)',rows)
            db.execute("""CREATE OR REPLACE TEMP TABLE current_fit AS SELECT o.*,
              upper(r.effective_role) AS effective_role,m.common_population,g.geometry_id,g.parent_geometry_id,
              (upper(r.effective_role)='TRAIN' AND m.common_population AND d.geometry_id IS NULL) AS fit_eligible,
              CASE WHEN upper(r.effective_role)<>'TRAIN' THEN 'ROLE_'||upper(r.effective_role)
                WHEN NOT m.common_population THEN 'OUTSIDE_FROZEN_COMMON_POPULATION'
                WHEN d.geometry_id IS NOT NULL THEN 'HELDOUT_GEOMETRY_OR_ITS_PERTURBED_VIEW'
                ELSE 'FIT_TRAIN_COMMON_NOT_DIAGNOSTIC' END AS fit_reason
              FROM owner_rows o LEFT JOIN roles r ON r.molecule_id=o.mid LEFT JOIN members m ON m.molecule_id=o.mid
              LEFT JOIN base_pm7 g ON g.molecule_id=o.mid AND g.native_record_id=o.rid
              LEFT JOIN excluded_pm7 d ON d.molecule_id=g.molecule_id AND d.geometry_id=g.geometry_id""")
            n,u,bad=db.execute("""SELECT count(*),count(DISTINCT ordinal),count(*) FILTER(WHERE effective_role IS NULL
                OR common_population IS NULL OR fit_eligible IS NULL OR (common_population AND geometry_id IS NULL)) FROM current_fit""").fetchone()
            expected=index.execute('SELECT count(*) FROM records WHERE job_id=?',(group['source_job_id'],)).fetchone()[0]
            C.need(n==u==expected and bad==0,'FULL_OWNER_ROLE_MEMBER_COVERAGE_AND_COMMON_BASE_GEOMETRY_FK')
            cur=db.execute('SELECT ordinal,rid,mid,job,source_role,effective_role,common_population,geometry_id,parent_geometry_id,fit_eligible,fit_reason FROM current_fit ORDER BY ordinal')
            while True:
                rows=cur.fetchmany(2048)
                if not rows:break
                side.executemany('INSERT INTO eligibility VALUES(?,?,?,?,?,?,?,?,?,?,?)',rows)
                for row in rows:counts[row[10]]+=1;fit+=int(row[9])
            side.commit();total+=n
            C.need(I.unique_bytes(root)<=plan['eligibility_cap_bytes']+plan['spill_cap_bytes'],'ELIGIBILITY_PLUS_TEMP_SPILL_CAP')
        n,u,mols,lo,hi=side.execute('SELECT count(*),count(DISTINCT rid),count(DISTINCT mid),min(ordinal),max(ordinal) FROM eligibility').fetchone()
        C.need(n==u==total==11231854 and mols==1220466 and (lo,hi)==(0,n-1),'FULL_ORIGINAL_OWNER_AND_MOLECULE_MASS')
        C.need(side.execute('SELECT count(*) FROM (SELECT mid,count(DISTINCT job) n FROM eligibility GROUP BY mid HAVING n<>1)').fetchone()[0]==0,'MOLECULE_NOT_SPLIT_ACROSS_LOGICAL_GROUPS')
        C.need(sum(counts.values())==n and fit>0,'FIT_PLUS_EXCLUDED_RECORDS_CONSERVED')
        side.commit()
    finally:
        side.close();db.close();index.close();C.need(identity(plan['canonical_index']['path'])==before,'CANONICAL_CHANGED_DURING_SIDE_BUILD')
    side_ref=I.pin(root/'eligibility.sqlite')
    return I.save(root/'manifest.json',{'schema':'FINAL_COMMON_TRAIN_ELIGIBILITY_V1','status':'COMPLETE_FULL_OWNER_ELIGIBILITY_NOT_STATISTICS',
      'records':total,'molecules':1220466,'fit_records':fit,'reason_counts':dict(counts),'authority':plan['authority'],
      'original_authority_SQL_proof':proof,'eligibility_reference':side_ref,'fit_population':'Common AND effectiveTRAIN AND NOT D5_base_or_all_actual_direct_children',
      'all_label_tasks_of_heldout_base_excluded':True,'Pprime_independent_dataset':'PENDING_REAL_FORMAL_SOURCE','physical_geometry_outside_Common_not_fabricated':True})

def lookup(db,owner):
    row=db.execute('SELECT rid,mid,job,source_role,effective_role,common_population,geometry_id,parent_geometry_id,fit_eligible,fit_reason FROM eligibility WHERE ordinal=?',(owner['record_ordinal'],)).fetchone()
    C.need(row is not None and row[:4]==(owner['record_id'],owner['molecule_id'],owner['job_id'],owner['new_role']),'UNCHANGED_OWNER_ID_ROLE_JOB_SIDE_BINDING')
    return dict(owner,source_role=row[3],effective_role=row[4],common_population=bool(row[5]),geometry_source='pm7',geometry_id=row[6],parent_geometry_id=row[7],fit_eligible=bool(row[8]),fit_reason=row[9])
