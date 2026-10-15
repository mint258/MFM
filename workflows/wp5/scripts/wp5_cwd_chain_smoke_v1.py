"""Single retained whole-molecule R13 full chain, private queue, exact project cwd."""
import argparse,ast,hashlib,json,os,socket,sqlite3,subprocess,time
from pathlib import Path
PROJECT=Path('/share/home/zixiao/descriptor_analysis')
ROOT=PROJECT/'runs/phase1_wp5_20261011'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
RUNTIME=ROOT/'scripts/wp5_runner_v13.py'
def read(path):return json.loads(Path(path).read_text())
def ref(path):return {'path':str(path),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
def write(path,obj):
    path=Path(path)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def q(value):return "'"+str(value).replace("'","''")+"'"
def run(a):
    job=os.environ.get('SLURM_JOB_ID');node=socket.gethostname().split('.')[0]
    if not job or os.getuid()!=1278 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24 or node not in {'compute-0-'+str(n) for n in (12,13,14,17,18,19)}:
        raise ValueError('Actual24CPU Root Slurm smoke allocation required')
    if Path.cwd().resolve()!=PROJECT:raise ValueError('SMOKE_CWD_MUST_BE_PROJECT')
    import duckdb,pyarrow as pa,pyarrow.dataset as ds,pyarrow.parquet as pq
    db=duckdb.connect();db.execute('SET threads=24');db.execute("SET memory_limit='10GB'")
    out=a.out or ROOT/'gates/cwd_complete_chain_smoke'/('job_'+job);out.mkdir(parents=True,exist_ok=False)
    record_dir=out/'records';record_dir.mkdir()
    assignments=ROOT/'packing/molecule_assignments.parquet'
    if a.molecule_id:
        rows=db.execute('SELECT * FROM read_parquet('+q(assignments)+') WHERE molecule_id=?',[a.molecule_id]).fetch_arrow_table().to_pylist()
    else:
        rows=db.execute('SELECT * FROM read_parquet('+q(assignments)+') WHERE records=1 AND heavy_atoms BETWEEN 2 AND 10 ORDER BY planned_allocated_seconds,molecule_id LIMIT 1').fetch_arrow_table().to_pylist()
    if len(rows)!=1:raise ValueError('Exactly one bounded whole molecule assignment required')
    molecule=rows[0]
    if not 1<=int(molecule['records'])<=4:raise ValueError('Bounded whole-molecule smoke expects1..4 original retained conformers')
    frozen_plan=read(ROOT/'packing/node_assignment_v3/tasks.json')
    task=next(t for t in frozen_plan['tasks'] if str(t['task_id'])==str(molecule['task_id']))
    table=ds.dataset(task['record_directory'],format='parquet',partitioning='hive').to_table(filter=ds.field('molecule_id')==molecule['molecule_id'],use_threads=True)
    if table.num_rows!=molecule['records'] or len(set(table.column('record_id').to_pylist()))!=table.num_rows:
        raise ValueError('Original retained whole molecule record count differs')
    pq.write_table(table,record_dir/'records.parquet',compression='zstd')
    private_assignment={**molecule,'task_id':0,'sequence_in_task':0,'lane':0}
    pq.write_table(pa.Table.from_pylist([private_assignment]),out/'molecule_assignments.parquet',compression='zstd')
    write(out/'tasks.json',{'tasks':[{'task_id':0,'node':node,'record_directory':str(record_dir)}]})
    db.close()
    contract=read(ROOT/'configs/production_contract_v6.json')
    package=contract['reproduction_package'];audit=contract['audit_manifest']
    import wp5_runner_v13 as runtime
    queue=out/'pending.sqlite';sqlite3.connect(queue).close()
    runtime.bootstrap_metadata(queue,deadline=time.monotonic()+600)
    command=[PY,'-B',str(RUNTIME),'--plan',str(out/'tasks.json'),'--assignments',str(out/'molecule_assignments.parquet'),
        '--queue',str(queue),'--run-root',str(out/'science_run'),'--task-id','0','--mode','main',
        '--node-authority',str(ROOT/'gates/wp5_node_replacement_user_approved.json'),
        '--node-scope-plan',str(ROOT/'packing/node_assignment_v3/tasks.json'),
        '--dictionaries',str(ROOT/'dictionaries/job_4513894/dictionary_manifest.json'),
        '--baseline',str(ROOT/'configs/pilot_success_baseline.json'),
        '--policy','FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT','--hours','48','--workers','24',
        '--production-contract',str(ROOT/'configs/production_contract_v6.json'),
        '--audit-membership',audit['path'],'--reproduction-package',package['path'],
        '--admit-hours','46','--export-reserve-hours','2','--smoke','--claim-cap','1']
    write(out/'plan.json',{'schema':'WP5_R13_CWD_SINGLE_WHOLE_MOLECULE_SMOKE_V1','status':'PLANNED_NOT_YET_EXECUTED',
        'source':ref(Path(__file__).resolve()),'runner':ref(RUNTIME),'frozen_main_environment':ref(ROOT/'scripts/wp5_main_v13.sbatch'),
        'production_contract':ref(ROOT/'configs/production_contract_v6.json'),'reproduction_package':package,
        'cwd':str(PROJECT),'command':command,'molecule_id':molecule['molecule_id'],'retained_records':table.num_rows,
        'record_ids':table.column('record_id').to_pylist(),'requested_scientific_slots':table.num_rows*12,
        'private_queue':str(queue),'production_queue_written':False,'counts_as_formal_population':False,
        'formal_ledger_included':False,'global_guide_stop_preserved':True})
    started=time.time()
    with (out/'runtime.stdout').open('w') as fo,(out/'runtime.stderr').open('w') as fe:
        process=subprocess.run(command,cwd=str(PROJECT),stdin=subprocess.DEVNULL,stdout=fo,stderr=fe,timeout=47.9*3600)
    issues=[];completion_path=out/'science_run/completion.json';export_path=out/'science_run/export_completion.json'
    completion=read(completion_path) if completion_path.is_file() else {}
    export=read(export_path) if export_path.is_file() else {}
    workers=completion.get('workers',[]);pids=sorted({w['pid'] for w in workers if w.get('pid')})
    errors=[{'lane':w.get('lane'),'errors':w.get('errors'),'error_count':w.get('error_count')} for w in workers if w.get('error_count')]
    if process.returncode!=0:issues.append({'runtime_returncode':process.returncode})
    if len(workers)!=24 or len(pids)!=24 or errors:issues.append({'worker_count':len(workers),'distinct_pids':len(pids),'worker_errors':errors})
    records=table.num_rows
    if export.get('molecules')!=1 or export.get('records')!=records or export.get('canonical',{}).get('rows')!=12*records:
        issues.append({'actual_complete_chain_counts':{'molecules':export.get('molecules'),'records':export.get('records'),'canonical_slots':export.get('canonical',{}).get('rows')}})
    status_counts={};input_trace_rows=0;science_rows=0
    for item in export.get('families',[]):
        if item['family'] in {'base_geometry','D20','D3','QC'}:continue
        data=pq.read_table(item['path'],columns=['status','input_file_sha256','elapsed_seconds']).to_pylist()
        science_rows+=len(data)
        for row in data:
            status_counts.setdefault(item['family'],{}).setdefault(row['status'],0)
            status_counts[item['family']][row['status']]+=1
            input_trace_rows+=bool(row['input_file_sha256'] and row['elapsed_seconds'] is not None)
    if science_rows!=12*records or input_trace_rows!=science_rows:issues.append({'science_rows':science_rows,'actual_rendered_input_trace_rows':input_trace_rows})
    connection=sqlite3.connect('file:'+str(queue)+'?mode=ro',uri=True)
    claims=connection.execute('SELECT sum(claims) FROM sessions').fetchone()[0]
    receipt_count=connection.execute('SELECT count(*) FROM molecules WHERE receipt_json IS NOT NULL AND export_json IS NOT NULL').fetchone()[0]
    connection.close()
    if claims!=1 or receipt_count!=1:issues.append({'private_queue_claims':claims,'durable_exported_molecules':receipt_count})
    if completion.get('scratch_clean') is not True or any((w.get('cleanup') or {}).get('work_root_removed') is not True for w in workers):
        issues.append({'scratch_clean':completion.get('scratch_clean'),'all_worker_scratch_removed':False})
    report={'schema':'WP5_R13_PROJECT_CWD_COMPLETE_CHAIN_SMOKE_V1','status':'CWD_COMPLETE_CHAIN_SMOKE_PASS' if not issues else 'NOT_PASS',
       'job_id':job,'actual_node':node,'actual_cwd':str(Path.cwd()),'runtime_subprocess_cwd':str(PROJECT),
       'runner':ref(RUNTIME),'production_contract':ref(ROOT/'configs/production_contract_v6.json'),
       'reproduction_package':package,'source':ref(Path(__file__).resolve()),'plan':ref(out/'plan.json'),
       'runtime_returncode':process.returncode,'requested_molecules':1,'completed_molecules':export.get('molecules',0),
       'records':records,'science_rows':science_rows,'actual_rendered_input_trace_rows':input_trace_rows,
       'actual_worker_pids':pids,'effective_worker_count':len(pids),'scientific_status_counts':status_counts,
       'issues':issues,'seconds':time.time()-started,'scratch_clean':completion.get('scratch_clean'),
       'export_completion':ref(export_path) if export_path.is_file() else None,
       'completion':ref(completion_path) if completion_path.is_file() else None,
       'production_queue_written':False,'formal_population_count_changed':False,'formal_ledger_included':False,
       'scientific_protocol_changed':False,'note':'This proves actual new whole-molecule execution and export at PROJECT cwd. Natural scientific failure outcomes remain explicit; no claim of all fields numerically successful.'}
    write(out/'report.json',report);print(json.dumps({'status':report['status'],'report':ref(out/'report.json'),'out':str(out)}))
    if issues:raise SystemExit(2)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--out',type=Path);p.add_argument('--molecule-id')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('CWD_SMOKE_AST_PASS_NOT_STARTED');return
    run(a)
if __name__=='__main__':main()
