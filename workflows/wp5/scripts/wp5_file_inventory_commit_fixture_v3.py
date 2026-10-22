"""Tiny private SQLite reader-lock fixture; no home scan or source DB access."""
from __future__ import annotations
import argparse,json,os,socket,sqlite3,tempfile,threading,time
from pathlib import Path
from wp5_file_inventory_v3 import commit_with_retry,write_json,ROOT,NODES

def hold_reader(path):
    held=threading.Event();release=threading.Event();errors=[]
    def read():
        db=None
        try:
            db=sqlite3.connect(path,isolation_level=None,timeout=1)
            db.execute('BEGIN');db.execute('SELECT * FROM fixture_rows').fetchall();held.set()
            if not release.wait(10):raise TimeoutError('PRIVATE_READER_RELEASE_NOT_RECEIVED')
            db.execute('ROLLBACK')
        except BaseException as error:errors.append(repr(error));held.set()
        finally:
            if db is not None:db.close()
    thread=threading.Thread(target=read);thread.start()
    if not held.wait(5) or errors:release.set();thread.join(5);raise RuntimeError('PRIVATE_SHARED_READER_START_FAILED:'+repr(errors))
    return release,thread,errors

def exercise():
    started=time.time();report={'schema':'WP5_INVENTORY_COMMIT_RETRY_PRIVATE_FIXTURE_V3','started_epoch':started,
        'host':socket.gethostname(),'uid':os.getuid(),'job_id':os.environ.get('SLURM_JOB_ID'),
        'private_tmp_only':True,'home_scanned':False,'source_DB_opened':False,'SCI_opened':False,'cases':{}}
    with tempfile.TemporaryDirectory(prefix='wp5_inv_commit_v3_'+str(os.getuid())+'_',dir='/tmp') as tmp:
        path=Path(tmp)/'fixture.sqlite';db=sqlite3.connect(path,isolation_level=None,timeout=.01)
        db.execute('PRAGMA journal_mode=DELETE');db.execute('CREATE TABLE fixture_rows(id INTEGER PRIMARY KEY,state TEXT,n INTEGER)')
        db.executemany('INSERT INTO fixture_rows VALUES(?,?,?)',[(1,'DONE',7),(2,'PENDING',0)])
        release=thread=timer=None
        try:
            release,thread,errors=hold_reader(path)
            db.execute('BEGIN IMMEDIATE');db.execute('UPDATE fixture_rows SET n=n+1 WHERE id=2')
            timer=threading.Timer(.25,release.set);timer.start();before=time.monotonic()
            attempts=commit_with_retry(db,seconds=2)
            elapsed=time.monotonic()-before;thread.join(5);timer.join(5)
            assert not errors and attempts>1 and not db.in_transaction
            assert db.execute('SELECT * FROM fixture_rows ORDER BY id').fetchall()==[(1,'DONE',7),(2,'PENDING',1)]
            assert db.execute('PRAGMA busy_timeout').fetchone()[0]==10
            report['cases']['shared_read_lock_release_same_transaction_commit']={'PASS':True,'commit_attempts':attempts,'elapsed_seconds':elapsed,'statement_increment_applied_exactly_once':True,'preexisting_DONE_preserved':True}
            release,thread,errors=hold_reader(path)
            db.execute('BEGIN IMMEDIATE');db.execute('UPDATE fixture_rows SET n=n+1 WHERE id=2');before=time.monotonic()
            try:commit_with_retry(db,seconds=.12)
            except sqlite3.OperationalError:
                assert db.in_transaction and time.monotonic()-before<1
                assert db.execute('SELECT n FROM fixture_rows WHERE id=2').fetchone()[0]==2
            else:raise AssertionError('EXPECTED_BOUNDED_BUSY_ERROR_NOT_RAISED')
            db.execute('ROLLBACK');release.set();thread.join(5);assert not errors
            assert db.execute('SELECT * FROM fixture_rows ORDER BY id').fetchall()==[(1,'DONE',7),(2,'PENDING',1)]
            assert db.execute('PRAGMA busy_timeout').fetchone()[0]==10
            report['cases']['bounded_wait_preserves_transaction_for_caller_rollback']={'PASS':True,'timeout_seconds':.12,'DONE_preserved':True,'pending_increment_not_replayed':True}
            try:commit_with_retry(db,seconds=1)
            except sqlite3.OperationalError as error:
                assert 'no transaction' in str(error) and not db.in_transaction
            else:raise AssertionError('NON_BUSY_ERROR_WAS_SWALLOWED')
            report['cases']['non_busy_sqlite_error_propagated']={'PASS':True}
        finally:
            if release is not None:release.set()
            if timer is not None:timer.cancel();timer.join(5)
            if thread is not None:thread.join(5)
            if db.in_transaction:db.execute('ROLLBACK')
            db.close()
    report.update(status='PRIVATE_COMMIT_RETRY_METADATA_FIXTURE_PASS',private_tmp_removed=not Path(tmp).exists(),finished_epoch=time.time())
    assert report['private_tmp_removed']
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if os.getuid()!=1278 or socket.gethostname().split('.')[0] not in NODES or not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24:
        raise ValueError('ROOT_SUBMITTED_AUTHORIZED_NODE_24CPU_REQUIRED')
    if not a.out.absolute().is_relative_to(ROOT/'reports'):raise ValueError('OWN_SMALL_METADATA_REPORT_REQUIRED')
    try:report=exercise()
    except Exception as error:
        write_json(a.out,{'schema':'WP5_INVENTORY_COMMIT_RETRY_PRIVATE_FIXTURE_V3','status':'PRIVATE_COMMIT_RETRY_METADATA_FIXTURE_FAILED',
            'time':time.time(),'host':socket.gethostname(),'uid':os.getuid(),'job_id':os.environ.get('SLURM_JOB_ID'),
            'error_type':type(error).__name__,'error':str(error),'SCI_opened':False,'source_DB_opened':False,'home_scanned':False})
        raise
    write_json(a.out,report);print(json.dumps({'status':report['status'],'report':str(a.out),'private_tmp_removed':report['private_tmp_removed']}),flush=True)
if __name__=='__main__':main()
