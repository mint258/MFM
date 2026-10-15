"""Small private stat-inventory regression; no original home/SCI/LMDB scan."""
import argparse,ast,hashlib,json,os,shutil,socket,sqlite3,stat,tempfile,time
from pathlib import Path
import wp5_file_inventory_v2 as I

def oracle(home,state,self_entry):
    out={}
    with os.scandir(os.fsencode(home)) as entries:
        for e in entries:
            label=os.fsdecode(e.name)
            if os.path.abspath(e.path)==os.fsencode(state):out[label]=self_entry;continue
            r=I.stat_count(e.stat(follow_symlinks=False));stack=[e.path] if stat.S_ISDIR(e.stat(follow_symlinks=False).st_mode) else []
            while stack:
                path=stack.pop()
                with os.scandir(path) as children:
                    for child in children:
                        s=child.stat(follow_symlinks=False);I.add(r,I.stat_count(s))
                        if stat.S_ISDIR(s.st_mode):stack.append(child.path)
            out[label]=r
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--cleanup',action='store_true');a=p.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
    for path in (Path(__file__),Path(I.__file__)):ast.parse(path.read_text())
    tests=I.ROOT/'tests';tests.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='stat_inventory_v2_1278_',dir=tests));home=folder/'tree';home.mkdir();state=home/'.scanner_state'
    for x in range(120):
        top=home/('top_'+str(x).zfill(3));top.mkdir()
        for y in range(4):
            d=top/('dir_'+str(y));d.mkdir()
            for z in range(3):(d/('file_'+str(z))).write_bytes(b'SYNTHETIC_STAT_FIXTURE')
    outside=folder/'outside';outside.mkdir();(outside/'must_not_follow').write_bytes(b'NOT_IN_HOME')
    os.symlink(outside,home/'symlink_outside',target_is_directory=True)
    os.link(home/'top_000/dir_0/file_0',home/'hardlink_same_inode')
    with (home/'sparse_file').open('wb') as f:f.truncate(8<<20)
    os.mkfifo(home/'fifo_entry')
    denied=home/'top_119/dir_3';workers=16;start=time.time()
    manifest=I.initialize(home,state,workers=workers,hours=.1,seed_target=4096,seed_depth=1,budget=60,fixture_delay=.01)
    assert manifest['status']=='SIX_DISJOINT_DIRECTORY_SHARDS_READY'
    assert sum(row['seed_directories'] for row in manifest['shards'])==manifest['frontier_directories']==480
    db=sqlite3.connect(state/'seed.sqlite');self_entry=json.loads(db.execute('SELECT result FROM base WHERE top=?',(json.dumps('.scanner_state'),)).fetchone()[0]);db.close()
    denied.chmod(0)
    partial=I.scan_shard(state,0,workers=workers,hours=.1,budget=60,max_directories=2,fixture_delay=.01)
    assert sum(v for k,v in partial['states'].items() if k!='DONE')>0
    db=sqlite3.connect(state/'shard_0.sqlite');preserved=dict(db.execute("SELECT path,result FROM tasks WHERE state='DONE' AND json_extract(result,'$.errors_total')=0"));db.close()
    attempts=[]
    for i in range(5):attempts.append(I.scan_shard(state,i,workers=workers,hours=.1,budget=60,fixture_delay=.01))
    large=I.scan_shard(state,5,workers=workers,hours=.1,budget=1e-12,fixture_delay=.01)
    assert large['states'].get('LARGE_PENDING',0)>0
    paused=I.aggregate(state,workers=workers);assert paused['pending_directory_tasks']>0 and paused['status']=='READ_ONLY_INVENTORY_CHECKPOINTED_PENDING'
    attempts.append(I.scan_shard(state,5,workers=workers,hours=.1,budget=60,include_large=True,fixture_delay=.01))
    with_errors=I.aggregate(state,workers=workers)
    assert with_errors['pending_directory_tasks']==0 and with_errors['totals']['errors_total']>0 and with_errors['status']=='READ_ONLY_INVENTORY_COMPLETE_WITH_ERRORS'
    denied.chmod(0o755);owner=None;rel=os.fsencode(str(denied.relative_to(home)))
    for i in range(6):
        db=sqlite3.connect(state/('shard_'+str(i)+'.sqlite'))
        if db.execute('SELECT 1 FROM tasks WHERE path=?',(rel,)).fetchone():owner=i
        db.close()
    assert owner is not None
    retry=I.scan_shard(state,owner,workers=workers,hours=.1,budget=60,retry_errors=True,fixture_delay=.01)
    final=I.aggregate(state,workers=workers);expected=oracle(home,state,self_entry)
    assert final['status']=='READ_ONLY_INVENTORY_COMPLETE' and final['pending_directory_tasks']==0
    assert set(final['directories'])==set(expected)
    for label,counts in expected.items():
        for field in I.FIELDS:assert final['directories'][label][field]==counts[field],(label,field,final['directories'][label][field],counts[field])
    db=sqlite3.connect(state/'shard_0.sqlite');after=dict(db.execute("SELECT path,result FROM tasks WHERE state='DONE'"));db.close()
    assert all(after[path]==value for path,value in preserved.items())
    assert final['totals']['symlinks']==1 and final['totals']['other']==1
    assert sum(r['historical_error_directory_retries'] for r in final['directories'].values())>=1
    assert all(len(r['actual_scanning_worker_pids'])==workers for r in attempts),[r['actual_scanning_worker_pids'] for r in attempts]
    proofs={'source':{'path':str(Path(I.__file__)),'sha256':hashlib.sha256(Path(I.__file__).read_bytes()).hexdigest()},
        'fixture_source':{'path':str(Path(__file__)),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    report={'schema':'WP5_STAT_ONLY_INVENTORY_FIXTURE_V2','status':'STAT_ONLY_INVENTORY_PRIVATE_FIXTURE_PASS','elapsed_seconds':time.time()-start,
        'fixture_root':str(folder),'source_home_scanned':False,'production_queue_opened':False,'SCI_or_LMDB_read':False,'QM_calls':0,
        'exact_static_tree_oracle_match':True,'resume_kept_completed_directory_results':True,'six_frontier_shards_disjoint_and_exhaustive':True,
        'over_budget_directory_explicit_pending_then_resume':True,'permission_error_explicit_then_retry_history_preserved':True,
        'symlinks_not_followed':True,'hardlink_entries_not_deduplicated':True,'self_checkpoint_descendants_excluded':True,
        'source_contents_opened_by_scanner':False,'effective_scanning_workers_per_shard':[len(r['actual_scanning_worker_pids']) for r in attempts],
        'actual_scanning_worker_pids':[r['actual_scanning_worker_pids'] for r in attempts],'manifest':manifest,'partial_run':partial,'large_run':large,
        'permission_error_report_totals':with_errors['totals'],'final_report':final,'proofs':proofs,'issues':[],'fixture_cleaned':False}
    I.write_json(a.out,report)
    if a.cleanup:
        assert folder.resolve().parent==tests.resolve() and folder.name.startswith('stat_inventory_v2_1278_')
        shutil.rmtree(folder);report['fixture_cleaned']=True;I.write_json(a.out,report)
    print(json.dumps({'status':report['status'],'report':str(a.out),'elapsed_seconds':report['elapsed_seconds'],'fixture_cleaned':report['fixture_cleaned']}))
if __name__=='__main__':main()