"""One frozen R11 Queue construction per worker on the real, schema-ready queue."""
import argparse, concurrent.futures, hashlib, importlib.util, json, multiprocessing
import os, pathlib, socket, sqlite3, time, traceback
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
NODES=('compute-0-12','compute-0-13','compute-0-14','compute-0-17','compute-0-18','compute-0-19')
RUNNER_SHA='e7828b4b78e42cd9a31c686ee30190cc9e788630d9c737980300606aa0236e7b'
EXPECTED={'owner_state_order':[('owner',0),('state',0)],
          'cleanup_pending_cost':[('predicted_seconds',1),('molecule_id',0)]}

def schema(db):
    rows=db.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','index')").fetchall()
    names={r[1] for r in rows}
    required={'meta','tasks','sessions','molecules','export_repairs','pending_order','completion_order',*EXPECTED}
    if not required.issubset(names):raise ValueError('SCHEMA_NOT_READY:'+str(sorted(required-names)))
    index_rows={r[1]:r for r in db.execute('PRAGMA index_list(molecules)').fetchall()}
    checks={}
    for name,wanted in EXPECTED.items():
        columns=[(r[2],r[3]) for r in db.execute('PRAGMA index_xinfo('+name+')').fetchall() if r[5]]
        if columns!=wanted or index_rows[name][4]!=(name=='cleanup_pending_cost'):
            raise ValueError('INDEX_DEFINITION_DIFFERS:'+name)
        checks[name]={'columns':columns,'partial':bool(index_rows[name][4])}
    sql=next(r[2] for r in rows if r[1]=='cleanup_pending_cost')
    normalized=''.join(sql.lower().split())
    if "wherestatein('pending','retry_pending')" not in normalized:
        raise ValueError('CLEANUP_INDEX_PREDICATE_DIFFERS')
    return checks

def initializer(barrier,runner,queue):
    global BARRIER,MODULE,QUEUE
    BARRIER=barrier;QUEUE=queue
    spec=importlib.util.spec_from_file_location('startup_probe_frozen_r11',runner)
    MODULE=importlib.util.module_from_spec(spec);spec.loader.exec_module(MODULE)

def once(ordinal):
    started=time.monotonic();q=None
    result={'ordinal':ordinal,'pid':os.getpid(),'constructor_calls':0}
    try:
        BARRIER.wait(timeout=300)
        started=time.monotonic();result['constructor_calls']=1
        q=MODULE.Queue(QUEUE,deadline=started+300)
        result.update(total_changes=q.db.total_changes,in_transaction=q.db.in_transaction,
                      indices=schema(q.db),retry_stats=dict(q.db.retry_stats))
        if result['total_changes']!=0 or result['in_transaction']:
            raise ValueError('CONSTRUCTOR_MODIFIED_DATA_OR_LEFT_TRANSACTION')
        result['status']='PASS'
    except BaseException:
        result.update(status='ERROR',error=traceback.format_exc(limit=10))
    finally:
        if q is not None:q.db.close()
    result['seconds']=time.monotonic()-started
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root',type=pathlib.Path,default=ROOT/'gates/metadata_startup_probe_v1')
    a=p.parse_args();node=socket.gethostname().split('.')[0];job=os.environ.get('SLURM_JOB_ID')
    if not job or node not in NODES or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24:
        raise ValueError('PROBE_REQUIRES24CPU_SLURM_AUTHORIZED_NODE')
    runner=ROOT/'scripts/wp5_runner_v11.py';queue=ROOT/'queue/pending.sqlite'
    if hashlib.sha256(runner.read_bytes()).hexdigest()!=RUNNER_SHA:raise ValueError('FROZEN_R11_SHA_DIFFERS')
    if not a.output_root.resolve().is_relative_to(ROOT/'gates'):raise ValueError('OUTPUT_OUTSIDE_OWN_GATES')
    report={'schema':'WP5_REAL_QUEUE_SCHEMA_READY_STARTUP_PROBE_V1','job_id':job,'node':node,
            'runner_sha256':RUNNER_SHA,'queue_path':str(queue),'QM_started':False,'LMDB_opened':False,
            'seed_start_claim_called':False,'scientific_source_changed':False}
    try:
        db=sqlite3.connect('file:'+str(queue)+'?mode=ro',uri=True,timeout=120)
        try:db.execute('PRAGMA query_only=ON');report['parent_schema_guard']=schema(db)
        finally:db.close()
    except Exception:
        report.update(status='SCHEMA_NOT_READY_PROBE_SKIPPED',error=traceback.format_exc(limit=8),workers_started=0)
    else:
        ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(24)
        with concurrent.futures.ProcessPoolExecutor(max_workers=24,mp_context=ctx,
                initializer=initializer,initargs=(barrier,str(runner),str(queue))) as pool:
            workers=list(pool.map(once,range(24),chunksize=1))
        report.update(workers=workers,actual_workers=len({w['pid'] for w in workers}))
        report['status']='CURRENT_SCHEMA_STARTUP_PROBE_PASS' if report['actual_workers']==24 and all(w['status']=='PASS' and w['constructor_calls']==1 for w in workers) else 'CURRENT_SCHEMA_STARTUP_PROBE_ERROR'
    out=a.output_root/node/('job_'+job)/'report.json';out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_name(out.name+'.pending');tmp.write_text(json.dumps(report,indent=2)+'\n');os.replace(tmp,out)
    print(json.dumps({'status':report['status'],'report':str(out),'actual_workers':report.get('actual_workers',0)}))
    if report['status']!='CURRENT_SCHEMA_STARTUP_PROBE_PASS':raise SystemExit(1)
if __name__=='__main__':main()
