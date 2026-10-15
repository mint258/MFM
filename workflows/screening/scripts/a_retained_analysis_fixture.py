"""Bounded real whole-molecule A pipeline runtime check, Slurm >=16 CPUs."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from a_retained_analysis import OLD,ROOT,DEPS,q,rows,copy,save,ref
def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=16);p.add_argument('--memory-gb',type=int,default=8);a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK','0')):raise RuntimeError('Slurm >=16 effective CPUs required')
    try:import duckdb
    except ModuleNotFoundError:sys.path.insert(0,str(DEPS));import duckdb
    root=ROOT/('a_fixture_job_'+os.environ['SLURM_JOB_ID']);root.mkdir(exist_ok=False)
    db=duckdb.connect();db.execute(f'SET threads={a.workers}');db.execute(f"SET memory_limit='{a.memory_gb}GB'")
    db.execute('CREATE VIEW original AS SELECT * FROM read_parquet('+q(OLD/'wp1_results/quality_annotations_v1.parquet')+')')
    db.execute('''CREATE TEMP TABLE picked AS
      SELECT molecule_id FROM (SELECT molecule_id,'stereo' AS reason FROM original GROUP BY molecule_id HAVING bool_or(stereo_only_key_mismatch)
        ORDER BY sha256(molecule_id) LIMIT 24)
      UNION SELECT molecule_id FROM (SELECT molecule_id,'unassigned' AS reason FROM original WHERE split='unassigned'
        GROUP BY molecule_id ORDER BY sha256(molecule_id) LIMIT 12)
      UNION SELECT molecule_id FROM (SELECT molecule_id,'baseline' AS reason FROM original GROUP BY molecule_id
        ORDER BY sha256(molecule_id) LIMIT 12)''')
    copy(db,'SELECT o.* FROM original o JOIN picked USING(molecule_id)',root/'quality.parquet')
    db.execute('CREATE VIEW fixture AS SELECT * FROM read_parquet('+q(root/'quality.parquet')+')')
    copy(db,'SELECT record_id,molecule_id FROM fixture',root/'index.parquet')
    pop=rows(db,'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules,count(*) FILTER(WHERE geometry_evaluated) AS geometry_records,
      count(*) FILTER(WHERE retained) AS retained_records,count(DISTINCT molecule_id) FILTER(WHERE retained) AS retained_molecules FROM fixture''')[0]
    unassigned=rows(db,"SELECT count(*) AS records,count(*) FILTER(WHERE retained) AS retained_records FROM fixture WHERE split='unassigned'")[0]
    save(root/'strict_report.json',{'population':pop,'geometry_join':{'required_post_X_records':pop['geometry_records']},'roles':{'unassigned':unassigned}})
    db.close();commands=[]
    output=root/'result'
    core=Path(__file__).absolute().with_name('a_retained_analysis.py');stereo=core.with_name('a_retained_analysis_stereo.py')
    for label,argv in [('core',[sys.executable,str(core),'--quality',str(root/'quality.parquet'),'--index',str(root/'index.parquet'),
      '--strict-report',str(root/'strict_report.json'),'--output',str(output),'--workers',str(a.workers),'--memory-gb',str(a.memory_gb)]),
      ('stereo',[sys.executable,str(stereo),'--output',str(output),'--workers',str(a.workers),'--memory-gb',str(a.memory_gb)])]:
        started=time.monotonic()
        with (root/(label+'.stdout')).open('w') as stdout,(root/(label+'.stderr')).open('w') as stderr:
            result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,check=False)
        commands.append({'label':label,'argv':argv,'returncode':result.returncode,'seconds':time.monotonic()-started})
        save(root/'commands.json',commands)
        if result.returncode:raise RuntimeError('A_FIXTURE_CHILD_FAILED:'+label)
    manifest=json.loads((output/'manifest.json').read_text());full=json.loads((output/'a_retained_report.json').read_text())
    assert manifest['physical']['records']==pop['records']
    assert manifest['strict']['records']==pop['retained_records']
    assert manifest['relaxed']['records']>=manifest['strict']['records']
    assert full['status']=='A1_A4_ANALYSIS_COMPLETE'
    assert sum(r['records'] for r in full['A1']['stereo_classes'])==full['A1']['old_same_connectivity14_fullkey_mismatch_records']
    save(root/'fixture_summary.json',{'status':'REAL_WHOLE_MOLECULE_A1_A4_RUNTIME_PASS','fixture_population':pop,
      'strict':manifest['strict'],'relaxed':manifest['relaxed'],'commands':commands,'source_core':ref(core,True),'source_stereo':ref(stereo,True),
      'LMDB_opened_or_written':False,'new_QM':False,'RDDetermineBonds_called':False})
    print(json.dumps({'status':'A_FIXTURE_PASS','output':str(root)},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
