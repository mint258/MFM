"""Resumable stat-only home inventory: directory checkpoints, six disjoint shards.
No inventoried file contents are opened. No source path is modified or removed.
"""
from __future__ import annotations
import argparse,concurrent.futures,contextlib,errno,fcntl,hashlib,json,multiprocessing,os,signal,socket,sqlite3,stat,tempfile,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
NODES=tuple('compute-0-'+str(n) for n in (12,13,14,17,18,19))
FIELDS=('entries','regular_files','directories','symlinks','other','logical_bytes','allocated_bytes','entries_seen','vanished_entries','errors_total','changed_directories','excluded_subtrees')
_STOP=None

def empty():return {**dict.fromkeys(FIELDS,0),'errors':[]}
def add(a,b):
    for k in FIELDS:a[k]+=b.get(k,0)
    a['errors'].extend(b.get('errors',[])[:max(0,100-len(a['errors']))])
    return a
def stat_count(s):
    r=empty();r['entries']=r['entries_seen']=1;r['logical_bytes']=s.st_size;r['allocated_bytes']=getattr(s,'st_blocks',0)*512
    kind='symlinks' if stat.S_ISLNK(s.st_mode) else 'regular_files' if stat.S_ISREG(s.st_mode) else 'directories' if stat.S_ISDIR(s.st_mode) else 'other';r[kind]=1;return r
def record_error(r,path,e):
    r['errors_total']+=1
    if e.errno==errno.ENOENT:r['vanished_entries']+=1
    if len(r['errors'])<20:r['errors'].append({'path':os.fsdecode(path),'errno':e.errno,'error':str(e)})
def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.pending')
    with tmp.open('w') as f:json.dump(obj,f,indent=2,ensure_ascii=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def read_json(p):return json.loads(Path(p).read_text())
def config(home,state):
    return {'schema':'WP5_DIRECTORY_INVENTORY_CONFIG_V2','home':str(Path(home).absolute()),'state_dir':str(Path(state).absolute()),'nodes':NODES,
        'shard_rule':'unsigned_sha256(relative_path_bytes)_mod_6','follow_symlinks':False,'count_directory_entries_not_unique_inodes':True,
        'checkpoint_exclusion':{'path':str(Path(state).absolute()),'root_entry_counted':True,'descendants_excluded':True}}
@contextlib.contextmanager
def own_state_lock(state,name):
    state=Path(state);state.mkdir(parents=True,exist_ok=True)
    with (state/(name+'.lock')).open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)
def database(path,cfg):
    db=sqlite3.connect(path,isolation_level=None,timeout=30);db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL')
    db.executescript('''CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS base(top TEXT PRIMARY KEY,result TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tasks(path BLOB PRIMARY KEY,top TEXT NOT NULL,depth INTEGER NOT NULL,state TEXT NOT NULL,result TEXT,attempts INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS tasks_state_depth ON tasks(state,depth,path);
    CREATE INDEX IF NOT EXISTS tasks_top ON tasks(top,state);
    CREATE TABLE IF NOT EXISTS retry_history(path BLOB,epoch REAL,previous_result TEXT);''')
    raw=json.dumps(cfg,sort_keys=True);old=db.execute("SELECT value FROM meta WHERE key='config'").fetchone()
    if old and old[0]!=raw:raise ValueError('EXISTING_STATE_CONFIG_DIFFERS_NEVER_RESET')
    db.execute("INSERT OR IGNORE INTO meta VALUES('config',?)",(raw,));return db
def meta_set(db,key,value):db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,json.dumps(value)))
def meta_get(db,key,default=None):
    r=db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone();return json.loads(r[0]) if r else default

def worker_init(stop,barrier):
    global _STOP;_STOP=stop;barrier.wait(timeout=120)
def ping(i):time.sleep(.02);return os.getpid()
def scan_directory(arg):
    home,exclude,row,deadline,budget,delay=arg;start=time.monotonic();rel=bytes(row['path']);path=os.fsencode(home)+b'/'+rel
    r=empty();children=[]
    if delay:time.sleep(delay)
    def interrupted():return _STOP.is_set() or time.monotonic()>=deadline
    try:
        before=os.stat(path,follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            record_error(r,path,OSError(errno.ENOTDIR,'Directory changed after discovery'));return {'row':row,'result':r,'children':[],'state':'DONE','pid':os.getpid()}
        with os.scandir(path) as entries:
            for i,e in enumerate(entries):
                if i%256==0:
                    if interrupted():return {'row':row,'state':'PENDING','pid':os.getpid(),'diagnostic_entries_seen':r['entries_seen']}
                    if time.monotonic()-start>budget:return {'row':row,'state':'LARGE_PENDING','pid':os.getpid(),'diagnostic_entries_seen':r['entries_seen'],'directory_budget_seconds':budget}
                try:s=e.stat(follow_symlinks=False)
                except OSError as ex:r['entries_seen']+=1;record_error(r,e.path,ex);continue
                add(r,stat_count(s))
                if stat.S_ISDIR(s.st_mode):
                    child=rel+b'/'+e.name
                    if os.path.abspath(e.path)==os.fsencode(exclude):r['excluded_subtrees']+=1
                    else:children.append(child)
        after=os.stat(path,follow_symlinks=False)
        if (before.st_dev,before.st_ino,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_mtime_ns):r['changed_directories']+=1
    except OSError as ex:record_error(r,path,ex)
    return {'row':row,'result':r,'children':children,'state':'DONE','pid':os.getpid(),'elapsed_seconds':time.monotonic()-start}

def run_tasks(db,cfg,workers,hours,budget,seed_target=None,seed_depth=3,max_directories=0,include_large=False,retry_errors=False,fixture_delay=0):
    # One master owns this SQLite. Workers only scandir/stat, never open it.
    db.execute("UPDATE tasks SET state='PENDING' WHERE state='INFLIGHT'")
    if include_large:db.execute("UPDATE tasks SET state='PENDING' WHERE state='LARGE_PENDING'")
    if retry_errors:
        db.execute('BEGIN IMMEDIATE')
        try:
            for row in db.execute("SELECT path,result FROM tasks WHERE state='DONE'").fetchall():
                if json.loads(row['result'])['errors_total']:
                    db.execute('INSERT INTO retry_history VALUES(?,?,?)',(row['path'],time.time(),row['result']))
                    db.execute("UPDATE tasks SET state='PENDING',result=NULL WHERE path=?",(row['path'],))
            db.execute('COMMIT')
        except Exception:db.execute('ROLLBACK');raise
    ctx=multiprocessing.get_context('spawn');stop=ctx.Event();barrier=ctx.Barrier(workers);deadline=time.monotonic()+hours*3600
    previous={}
    for sig in (signal.SIGTERM,signal.SIGUSR1):previous[sig]=signal.signal(sig,lambda *a:stop.set())
    processed=0;scan_pids=set();diagnostics=[];warmed=[];started=time.time()
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=ctx,initializer=worker_init,initargs=(stop,barrier)) as pool:
            warmed=list(pool.map(ping,range(workers),chunksize=1));futures={}
            while True:
                pending=db.execute("SELECT count(*) FROM tasks WHERE state='PENDING'").fetchone()[0]
                admit=not stop.is_set() and time.monotonic()<deadline
                if seed_target is not None and pending>=seed_target:admit=False
                if max_directories and processed+len(futures)>=max_directories:admit=False
                if admit and len(futures)<workers:
                    sql="SELECT path,top,depth FROM tasks WHERE state='PENDING'";params=[]
                    if seed_target is not None:sql+=' AND depth<?';params.append(seed_depth)
                    sql+=' ORDER BY depth,path LIMIT ?';params.append(workers-len(futures))
                    rows=[dict(row) for row in db.execute(sql,params)]
                    db.execute('BEGIN IMMEDIATE')
                    try:
                        for row in rows:db.execute("UPDATE tasks SET state='INFLIGHT',attempts=attempts+1 WHERE path=?",(row['path'],))
                        db.execute('COMMIT')
                    except Exception:db.execute('ROLLBACK');raise
                    for row in rows:
                        f=pool.submit(scan_directory,(cfg['home'],cfg['state_dir'],row,deadline,budget,fixture_delay));futures[f]=row
                if not futures:break
                done,_=concurrent.futures.wait(futures,timeout=2,return_when=concurrent.futures.FIRST_COMPLETED)
                if not done:
                    if time.monotonic()>=deadline:stop.set()
                    continue
                db.execute('BEGIN IMMEDIATE')
                try:
                    for f in done:
                        row=futures.pop(f);result=f.result();scan_pids.add(result['pid'])
                        if result['state']=='DONE':
                            db.execute("UPDATE tasks SET state='DONE',result=? WHERE path=?",(json.dumps(result['result'],ensure_ascii=True),row['path']))
                            db.executemany("INSERT OR IGNORE INTO tasks(path,top,depth,state) VALUES(?,?,?,'PENDING')",[(p,row['top'],row['depth']+1) for p in result['children']]);processed+=1
                        else:
                            db.execute('UPDATE tasks SET state=? WHERE path=?',(result['state'],row['path']))
                            if result['state']=='PENDING':stop.set()
                            diagnostics.append({**{k:v for k,v in result.items() if k not in ('row','pid')},'path':os.fsdecode(row['path'])})
                    db.execute('COMMIT')
                except Exception:db.execute('ROLLBACK');raise
                if max_directories and processed>=max_directories:stop.set()
    finally:
        for sig,old in previous.items():signal.signal(sig,old)
    states=dict(db.execute('SELECT state,count(*) FROM tasks GROUP BY state'));error_dirs=sum(json.loads(r[0])['errors_total']>0 for r in db.execute("SELECT result FROM tasks WHERE state='DONE'"))
    report={'started_epoch':started,'finished_epoch':time.time(),'states':states,'error_directories':error_dirs,'processed_directories_this_attempt':processed,
        'warmed_worker_pids':sorted(set(warmed)),'actual_scanning_worker_pids':sorted(scan_pids),'workers_requested':workers,'diagnostics':diagnostics[-100:],
        'directory_budget_seconds':budget,'hours_budget':hours,'metadata_only':True,'source_file_contents_opened':False}
    meta_set(db,'last_run',report);return report

def initialize(home,state,workers=24,hours=46,seed_target=4096,seed_depth=3,budget=1800,fixture_delay=0):
    cfg=config(home,state);state=Path(state)
    with own_state_lock(state,'seed'):
        db=database(state/'seed.sqlite',cfg)
        try:
            if meta_get(db,'distributed',False):return read_json(state/'manifest.json')
            if not meta_get(db,'home_listed',False):
                db.execute('BEGIN IMMEDIATE')
                try:
                    with os.scandir(os.fsencode(cfg['home'])) as entries:
                        for e in entries:
                            top=json.dumps(os.fsdecode(e.name),ensure_ascii=True);r=empty()
                            try:s=e.stat(follow_symlinks=False);r=stat_count(s)
                            except OSError as ex:record_error(r,e.path,ex);r['entries_seen']=1
                            db.execute('INSERT OR REPLACE INTO base VALUES(?,?)',(top,json.dumps(r)))
                            if not r['errors_total'] and stat.S_ISDIR(s.st_mode):
                                if os.path.abspath(e.path)==os.fsencode(cfg['state_dir']):r['excluded_subtrees']+=1;db.execute('UPDATE base SET result=? WHERE top=?',(json.dumps(r),top))
                                else:db.execute("INSERT OR IGNORE INTO tasks(path,top,depth,state) VALUES(?,?,0,'PENDING')",(e.name,top))
                    meta_set(db,'home_listed',True);db.execute('COMMIT')
                except Exception:db.execute('ROLLBACK');raise
            run=run_tasks(db,cfg,workers,hours,budget,seed_target,seed_depth,fixture_delay=fixture_delay)
            # Any still-unscanned directory is a disjoint subtree frontier. No
            # recursively completed ancestor can also appear in the frontier.
            frontier=[dict(r) for r in db.execute("SELECT path,top,depth FROM tasks WHERE state IN ('PENDING','LARGE_PENDING')")]
            shards=[[] for _ in NODES]
            for row in frontier:shards[int.from_bytes(hashlib.sha256(row['path']).digest(),'big')%len(NODES)].append(row)
            if run['finished_epoch']-run['started_epoch']>=hours*3600 and len(frontier)<seed_target:
                report={'schema':'WP5_DIRECTORY_INVENTORY_SEED_V2','status':'SEED_CHECKPOINTED_RESUME_REQUIRED','config':cfg,'run':run};write_json(state/'seed_attempt.json',report);return report
            for i,rows in enumerate(shards):
                target=database(state/('shard_'+str(i)+'.sqlite'),cfg)
                try:
                    target.execute('BEGIN IMMEDIATE')
                    target.executemany("INSERT OR IGNORE INTO tasks(path,top,depth,state) VALUES(?,?,?,'PENDING')",[(r['path'],r['top'],r['depth']) for r in rows])
                    meta_set(target,'seed_shard',i);meta_set(target,'seed_ready',True);target.execute('COMMIT')
                finally:target.close()
            manifest={'schema':'WP5_DIRECTORY_INVENTORY_SEED_V2','status':'SIX_DISJOINT_DIRECTORY_SHARDS_READY','config':cfg,'frontier_directories':len(frontier),
                'seed_target':seed_target,'seed_target_achieved':len(frontier)>=seed_target,'seed_depth':seed_depth,
                'shards':[{'shard':i,'node':n,'seed_directories':len(shards[i]),'state':str(state/('shard_'+str(i)+'.sqlite'))} for i,n in enumerate(NODES)],
                'seed_run':run,'seed_completed_directories':db.execute("SELECT count(*) FROM tasks WHERE state='DONE'").fetchone()[0]}
            write_json(state/'manifest.json',manifest);meta_set(db,'distributed',True);return manifest
        finally:db.close()

def scan_shard(state,shard,workers=24,hours=46,budget=1800,include_large=False,retry_errors=False,max_directories=0,fixture_delay=0):
    state=Path(state);manifest=read_json(state/'manifest.json')
    if manifest['status']!='SIX_DISJOINT_DIRECTORY_SHARDS_READY':raise ValueError('INITIALIZER_NOT_READY')
    cfg=manifest['config']
    with own_state_lock(state,'shard_'+str(shard)):
        db=database(state/('shard_'+str(shard)+'.sqlite'),cfg)
        try:
            if meta_get(db,'seed_shard')!=shard or meta_get(db,'seed_ready') is not True:raise ValueError('EXACT_DISJOINT_SEED_SHARD_REQUIRED')
            result=run_tasks(db,cfg,workers,hours,budget,max_directories=max_directories,include_large=include_large,retry_errors=retry_errors,fixture_delay=fixture_delay)
            pending=sum(n for k,n in result['states'].items() if k!='DONE')
            result.update(schema='WP5_DIRECTORY_INVENTORY_SHARD_V2',shard=shard,node=socket.gethostname(),job_id=os.environ.get('SLURM_JOB_ID'),
                status='SHARD_COMPLETE_WITH_ERRORS' if not pending and result['error_directories'] else 'SHARD_COMPLETE' if not pending else 'SHARD_CHECKPOINTED_PENDING_REMAINS')
            write_json(state/('shard_'+str(shard)+'_last_report.json'),result);return result
        finally:db.close()

def collect_top(arg):
    state,top=arg;r=empty();done=0;pending=0;retry_errors=0
    for name in ['seed.sqlite']+['shard_'+str(i)+'.sqlite' for i in range(6)]:
        db=sqlite3.connect('file:'+str(Path(state)/name)+'?mode=ro',uri=True)
        try:
            if name=='seed.sqlite':
                for raw, in db.execute('SELECT result FROM base WHERE top=?',(top,)):add(r,json.loads(raw))
            else:pending+=db.execute("SELECT count(*) FROM tasks WHERE top=? AND state!='DONE'",(top,)).fetchone()[0]
            for raw, in db.execute("SELECT result FROM tasks WHERE top=? AND state='DONE'",(top,)):add(r,json.loads(raw));done+=1
            retry_errors+=db.execute('SELECT count(*) FROM retry_history WHERE path IN (SELECT path FROM tasks WHERE top=?)',(top,)).fetchone()[0]
        finally:db.close()
    return json.loads(top),{**r,'completed_directory_tasks':done,'pending_directory_tasks':pending,'historical_error_directory_retries':retry_errors,'worker_pid':os.getpid()}

def aggregate(state,workers=24):
    state=Path(state);manifest=read_json(state/'manifest.json');locks=[]
    try:
        for name in ['seed']+['shard_'+str(i) for i in range(6)]:
            f=(state/(name+'.lock')).open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(f)
        db=sqlite3.connect('file:'+str(state/'seed.sqlite')+'?mode=ro',uri=True)
        try:tops=[r[0] for r in db.execute('SELECT top FROM base ORDER BY top')]
        finally:db.close()
        ctx=multiprocessing.get_context('spawn')
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=ctx) as pool:rows=list(pool.map(collect_top,[(str(state),top) for top in tops],chunksize=1))
        grouped=dict(rows);pending=sum(r['pending_directory_tasks'] for r in grouped.values());errors=sum(r['errors_total'] for r in grouped.values())
        attempts=[read_json(state/('shard_'+str(i)+'_last_report.json')) if (state/('shard_'+str(i)+'_last_report.json')).exists() else None for i in range(6)]
        report={'schema':'WP5_ACCOUNT_TOP_LEVEL_INVENTORY_V2','status':'READ_ONLY_INVENTORY_CHECKPOINTED_PENDING' if pending else 'READ_ONLY_INVENTORY_COMPLETE_WITH_ERRORS' if errors else 'READ_ONLY_INVENTORY_COMPLETE',
            'home':manifest['config']['home'],'uid':os.getuid(),'host':socket.gethostname(),'created_epoch':time.time(),'directories':grouped,
            'totals':{k:sum(r[k] for r in grouped.values()) for k in FIELDS},'pending_directory_tasks':pending,'all_shards_complete':pending==0,
            'seed_manifest':str(state/'manifest.json'),'shard_attempts':attempts,'source_file_contents_opened':False,'source_paths_modified':False,
            'checkpoint_exclusion':manifest['config']['checkpoint_exclusion'],
            'limitations':['Live tree observed over the complete seed/shard intervals, not an atomic snapshot; additions after a completed directory can be missed.',
                'Every successfully statted directory entry is counted; hardlinks are counted per path and symlinks are not followed.',
                'Logical bytes sum st_size for all observed entry types; allocated bytes sum st_blocks*512 and can repeat hardlink storage.',
                'These home-path entry counts are not quota UID inode counts and exclude the scanner checkpoint directory descendants.',
                'Only DONE directory results enter totals. Interrupted/over-budget directories remain explicit pending and are rescanned on resume.',
                'Errors/vanished entries and directory mtime/inode changes are explicit; COMPLETE_WITH_ERRORS is not a complete readable snapshot.']}
        write_json(state/'account_top_level_inventory.json',report);return report
    finally:
        for f in reversed(locks):fcntl.flock(f,fcntl.LOCK_UN);f.close()

def production_guard(a):
    node=socket.gethostname().split('.')[0]
    if os.getuid()!=1278 or node not in NODES or not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers or a.workers<24:raise ValueError('ROOT_SUBMITTED_24CPU_AUTHORIZED_NODE_ALLOCATION_REQUIRED')
    if a.mode=='scan' and node!=NODES[a.shard]:raise ValueError('SHARD_EXECUTION_NODE_MISMATCH')
    if Path(a.home).absolute()!=Path('/share/home/zixiao'):raise ValueError('EXACT_AUTHORIZED_HOME_REQUIRED')
    if not Path(a.state_dir).absolute().is_relative_to(ROOT/'reports'):raise ValueError('NEW_OWN_REPORT_STATE_DIRECTORY_REQUIRED')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');p.add_argument('--mode',choices=('init','scan','collect'))
    p.add_argument('--home',default='/share/home/zixiao');p.add_argument('--state-dir',type=Path,required=False)
    p.add_argument('--shard',type=int,choices=range(6));p.add_argument('--workers',type=int,default=24);p.add_argument('--hours',type=float,default=46)
    p.add_argument('--seed-target',type=int,default=4096);p.add_argument('--seed-depth',type=int,default=3);p.add_argument('--directory-budget-seconds',type=float,default=1800)
    p.add_argument('--include-large',action='store_true',default=True,help='Retry unfinished over-budget directories once on every resumed invocation');p.add_argument('--retry-errors',action='store_true');a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print('STAT_ONLY_INVENTORY_V2_AST_PASS_NO_SCAN');return
    if not a.mode or not a.state_dir:p.error('--mode and independent --state-dir required')
    if a.mode=='scan' and a.shard is None:p.error('--shard required')
    if not 0<a.hours<=46 or not 0<a.directory_budget_seconds<=46*3600:raise ValueError('BOUNDED_46H_CHECKPOINT_REQUIRED')
    production_guard(a)
    if a.mode=='init':r=initialize(a.home,a.state_dir,a.workers,a.hours,a.seed_target,a.seed_depth,a.directory_budget_seconds)
    elif a.mode=='scan':r=scan_shard(a.state_dir,a.shard,a.workers,a.hours,a.directory_budget_seconds,a.include_large,a.retry_errors)
    else:r=aggregate(a.state_dir,a.workers)
    print(json.dumps({'status':r['status'],'state_dir':str(a.state_dir),'pending_directory_tasks':r.get('pending_directory_tasks'),'source_contents_read':False}))
    if r['status']=='SEED_CHECKPOINTED_RESUME_REQUIRED':raise SystemExit(75)
if __name__=='__main__':main()