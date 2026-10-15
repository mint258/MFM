"""One real small WP1 report runtime check plus missing/duplicate guard cases.

Uses already computed smoke geometry only. No LMDB, RDKit, MOPAC, xTB, model,
or scientific recomputation is invoked. Production report/selector stay frozen.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
AUDIT=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.dont_write_bytecode=True
sys.path.insert(0,str(AUDIT/'deps'))
REPORT_SHA='c8a5e896bb2560d80ad2bbefb00a36a90b9ace4e4bb69f8b6d4d2083d1114740'

def q(value):return "'"+str(value).replace("'","''")+"'"

def ref(path,hash_file=True):
    path=Path(path);stat=path.stat();result={'path':str(path),'bytes':stat.st_size}
    if hash_file:result['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    else:result['mtime_ns']=stat.st_mtime_ns
    return result

def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

def demand(value,message):
    if not value:raise RuntimeError(message)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',type=Path,default=ROOT/'record_index.parquet')
    p.add_argument('--smoke',type=Path,default=ROOT/'wp1_geometry_smoke/job_4512807/geometry_annotations.parquet')
    p.add_argument('--report',type=Path,default=ROOT/'scripts/wp1_report.py')
    p.add_argument('--report-sha256',default=REPORT_SHA)
    p.add_argument('--out',type=Path)
    p.add_argument('--workers',type=int,default=16)
    p.add_argument('--memory-gb',type=int,default=4)
    a=p.parse_args();allocated=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
    demand(bool(os.environ.get('SLURM_JOB_ID')) and 16<=a.workers<=allocated,'Requires an allocated Slurm >=16 CPU fixture job.')
    output=a.out or ROOT/'reports'/('wp1_report_fixture_job_'+os.environ['SLURM_JOB_ID'])
    output.mkdir(parents=True,exist_ok=False)
    source_before=ref(a.report)
    demand(source_before['sha256']==a.report_sha256,'Production report does not match the requested frozen source.')
    source_index_before=ref(a.index,False);smoke_before=ref(a.smoke)
    started=time.monotonic();summary={'status':'RUNNING','job_id':os.environ['SLURM_JOB_ID'],
      'script':ref(Path(__file__)),'production_report':source_before,
      'input_index':source_index_before,'existing_smoke':smoke_before,
      'workers':a.workers,'scientific_recomputation_calls':0,'subcommands':[]}
    try:
        import duckdb
        db=duckdb.connect();db.execute(f'SET threads={a.workers}');db.execute(f"SET memory_limit='{a.memory_gb}GB'")
        db.execute('SET preserve_insertion_order=false');db.execute('SET temp_directory='+q(output/'tmp_build'))
        db.execute('CREATE VIEW full_index AS SELECT * FROM read_parquet('+q(a.index)+')')
        db.execute('CREATE TABLE smoke AS SELECT * FROM read_parquet('+q(a.smoke)+')')
        smoke_count,smoke_unique=db.execute('SELECT count(*),count(DISTINCT record_id) FROM smoke').fetchone()
        demand(smoke_count==smoke_unique==1000,'This fixture binds the existing unique 1000-record smoke output.')
        matched=db.execute('SELECT count(*) FROM full_index i JOIN smoke g USING(record_id)').fetchone()[0]
        demand(matched==smoke_count,'Smoke IDs are not represented exactly once in the current physical index.')
        x=' AND '.join('NOT coalesce(i.'+code+',false)' for code in ['X01','X02','X03','X04','X05'])
        fixture_index=output/'fixture_index.parquet'
        db.execute(f'''COPY (SELECT i.* FROM full_index i JOIN smoke g USING(record_id) WHERE {x})
          TO {q(fixture_index)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
        db.execute('CREATE VIEW fi AS SELECT * FROM read_parquet('+q(fixture_index)+')')
        db.execute('CREATE TABLE exact_geometry AS SELECT g.* FROM smoke g JOIN fi i USING(record_id)')
        count=db.execute('SELECT count(*) FROM fi').fetchone()[0]
        demand(1<count<=1000,'No usable current post-X smoke fixture.')
        geometry_count=db.execute('SELECT count(*) FROM exact_geometry').fetchone()[0]
        demand(geometry_count==count,'Current post-X geometry and fixture index differ.')
        exclusions=db.execute('''SELECT count(*) FILTER(WHERE i.X01 IS TRUE),count(*) FILTER(WHERE i.X02 IS TRUE),
          count(*) FILTER(WHERE i.X03 IS TRUE),count(*) FILTER(WHERE i.X04 IS TRUE),count(*) FILTER(WHERE i.X05 IS TRUE)
          FROM full_index i JOIN smoke g USING(record_id)''').fetchone()
        summary['fixture_scope']={'original_smoke_records':smoke_count,'current_post_X_records':count,
          'removed_current_X_records':smoke_count-count,'current_X_hits':dict(zip(['X01','X02','X03','X04','X05'],exclusions)),
          'expected_from_current_cache_about':993,
          'selection':'Join current physical source IDs to the old 1000 smoke IDs, then synchronize both sides with the current X01-X05 flags.'}
        valid_root=output/'geometry_two_directories'
        for part in (0,1):
            directory=valid_root/('part_'+str(part));directory.mkdir(parents=True)
            db.execute(f'''COPY (SELECT * FROM exact_geometry WHERE hash(record_id)%2={part})
              TO {q(directory/'geometry_annotations.parquet')} (FORMAT PARQUET,COMPRESSION ZSTD)''')
        missing=output/'geometry_missing.parquet';duplicate=output/'geometry_duplicate.parquet'
        db.execute(f'''COPY (SELECT * FROM exact_geometry WHERE record_id<>(SELECT min(record_id) FROM exact_geometry))
          TO {q(missing)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
        db.execute(f'''COPY (SELECT * FROM exact_geometry UNION ALL SELECT * FROM exact_geometry
          WHERE record_id=(SELECT min(record_id) FROM exact_geometry)) TO {q(duplicate)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
        db.close()
        # Source extraction is closed before children start, keeping peak memory
        # within one small derived-data process plus one report child.
        environment=dict(os.environ)
        environment['PYTHONDONTWRITEBYTECODE']='1'
        environment['PYTHONPATH']=str(AUDIT/'deps')+(os.pathsep+environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
        for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            environment[name]='1'
        for name,geometry,should_pass in [('valid',valid_root,True),('missing',missing,False),('duplicate',duplicate,False)]:
            target=output/('report_'+name)
            command=[str(Path(sys.executable).absolute()),'-B',str(a.report),'--index',str(fixture_index),
              '--geometry',str(geometry),'--output',str(target),'--threads',str(a.workers),
              '--memory-gb',str(a.memory_gb),'--temp-gb','8','--seed','20261010']
            start=time.monotonic()
            with (output/(name+'.stdout')).open('wb') as stdout,(output/(name+'.stderr')).open('wb') as stderr:
                result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                                      env=environment,shell=False,timeout=600)
            entry={'case':name,'argv':command,'returncode':result.returncode,'seconds':time.monotonic()-start,
              'stdout':ref(output/(name+'.stdout')),'stderr':ref(output/(name+'.stderr')),
              'report_source_SHA256':ref(a.report)['sha256']}
            summary['subcommands'].append(entry)
            demand((result.returncode==0)==should_pass,'Unexpected report exit for '+name)
            validation=json.loads((target/'geometry_join_validation.json').read_text(encoding='utf-8'))
            entry['geometry_join_validation']=validation
            if should_pass:
                report=json.loads((target/'screening_report.json').read_text(encoding='utf-8'))
                demand(report['population']['records']==count,'Complete runtime report physical count differs.')
                demand(validation['required_post_X_records']==validation['geometry_records']==count,'Positive coverage closure differs.')
                for key in ('duplicate_index_records','null_geometry_record_ids','duplicate_geometry_keys',
                  'missing_required_geometry','extra_geometry_records','geometry_molecule_id_mismatches'):
                    demand(validation[key]==0,'Positive geometry guard nonzero: '+key)
                demand(all(value==0 for value in report['membership_integrity'].values()),'Actual membership subset/overlap checks failed.')
                role_total=sum(report['roles'][role]['records'] for role in ('train','full','unassigned'))
                demand(role_total==count,'Physical count incorrectly includes routine twice or misses a split.')
                import pyarrow.parquet as pq
                demand(pq.ParquetFile(target/'quality_annotations_v1.parquet').metadata.num_rows==count,'Published quality row count differs.')
                entry['population']=report['population'];entry['actual_role_populations']=report['roles']
                entry['report_status']=report['status'];entry['quality']=ref(target/'quality_annotations_v1.parquet')
                entry['membership_scope_note']='Reports the real smoke membership; empty roles are not manufactured into synthetic coverage.'
            else:
                demand(not (target/'quality_annotations_v1.parquet').exists(),'Negative guard incorrectly published a final quality file.')
                demand(not (target/'quality_annotations_v1.parquet.pending').exists(),'Negative guard wrote scientific partial quality before validation.')
                if name=='missing':demand(validation['missing_required_geometry']==1,'Missing-row fixture did not identify exactly one missing record.')
                else:demand(validation['duplicate_geometry_keys']==validation['duplicate_geometry_excess_rows']==1,'Duplicate fixture did not identify one duplicated source record.')
            save(output/'fixture_progress.json',summary)
        demand(ref(a.report)==source_before,'Frozen production report changed during fixture execution.')
        demand(ref(a.index,False)==source_index_before and ref(a.smoke)==smoke_before,'Existing fixture sources changed.')
        summary.update(status='PASS_REAL_SMALL_REPORT_AND_TWO_NEGATIVE_GEOMETRY_GUARDS',
          elapsed_seconds=time.monotonic()-started,production_report_and_smoke_SHA_unchanged=True,
          physical_index_size_and_mtime_unchanged=True,
          quality_runtime_pipeline_complete=True,production_report_modified=False,
          quantum_or_geometry_recomputed=False)
        save(output/'summary.json',summary)
        print(json.dumps({'status':summary['status'],'records':count,'summary':str(output/'summary.json')}),flush=True)
    except Exception as exc:
        summary.update(status='FAILED_REAL_REPORT_FIXTURE',error=type(exc).__name__+': '+str(exc),elapsed_seconds=time.monotonic()-started)
        save(output/'summary.json',summary)
        raise

if __name__=='__main__':main()
