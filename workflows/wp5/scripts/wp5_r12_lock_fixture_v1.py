"""Isolated R12 lock deadline/owner-exit probe:16 real workers, no queue/QM/LMDB."""
import argparse,concurrent.futures,fcntl,hashlib,importlib.util,json,multiprocessing as mp
import os,signal,socket,sqlite3,time
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
_BARRIER=None
_STARTS=None
def initialize(barrier,starts):
    global _BARRIER,_STARTS
    _BARRIER=barrier;_STARTS=starts
def holder(path,ready,release):
    stream=Path(path).open("a+b")
    fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
    ready.set();release.wait(15)
    # Explicit process exit while still owning the descriptor proves that the
    # kernel releases the lock when the holder dies; no signal/kill is required.
    os._exit(0)
def load(path):
    spec=importlib.util.spec_from_file_location("r12_lock_fixture_runtime",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def worker(payload):
    mod=load(payload["runner"])
    db=sqlite3.connect(":memory:",isolation_level=None,factory=mod.BusyConnection)
    db.row_factory=sqlite3.Row;db.configure_retry(payload["lock_base"])
    case=payload["case"];row={"case":case,"pid":os.getpid(),"node":socket.gethostname(),"QM_calls":0}
    old_handler=signal.getsignal(signal.SIGALRM);old_timer=signal.getitimer(signal.ITIMER_REAL)
    own_handler=None;before=None
    if case=="existing_timer":
        def fixture_alarm(_signum,_frame):raise AssertionError("Existing5secondtimer unexpectedly fired")
        own_handler=fixture_alarm;signal.signal(signal.SIGALRM,own_handler);signal.setitimer(signal.ITIMER_REAL,5)
        before=signal.getitimer(signal.ITIMER_REAL)
    try:
        _BARRIER.wait(timeout=30)
        with _STARTS.get_lock():_STARTS.value+=1
        started=time.monotonic()
        row["wait_start_epoch"]=time.time()
        try:
            db._acquire(started+(.3 if case=="deadline" else 5))
            row["acquired"]=True;db._release()
        except sqlite3.OperationalError as error:
            row.update(acquired=False,error=str(error),metadata_lock_kind=getattr(error,"metadata_lock_kind",None))
        row["seconds"]=time.monotonic()-started
        row["wait_end_epoch"]=time.time()
        if case=="deadline":
            assert row["acquired"] is False and row["metadata_lock_kind"]=="SIDECAR_FLOCK"
            assert .25<=row["seconds"]<=2,"Deadline wait escaped meaningful runtime bound"
            assert db.retry_stats["file_lock_blocking_calls"]==1 and db.retry_stats["file_lock_blocking_timeouts"]==1
        else:
            assert row["acquired"] is True
            if case=="existing_timer":
                after=signal.getitimer(signal.ITIMER_REAL)
                assert signal.getsignal(signal.SIGALRM) is own_handler
                assert 0<after[0]<=before[0] and after[1]==before[1]
                assert db.retry_stats["file_lock_nonblocking_fallback_calls"]==1
                assert db.retry_stats["file_lock_fallback_reasons"].get("SIGALRM_HANDLER_IN_USE")==1
                row["existing_timer_remaining_before"]=before[0];row["existing_timer_remaining_after"]=after[0]
            else:assert db.retry_stats["file_lock_blocking_calls"]==1
        if case!="existing_timer":
            assert signal.getsignal(signal.SIGALRM)==old_handler and signal.getitimer(signal.ITIMER_REAL)==old_timer
        row["stats"]=dict(db.retry_stats);row["status"]="PASS"
        return row
    finally:
        if case=="existing_timer":
            signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old_handler);signal.setitimer(signal.ITIMER_REAL,*old_timer)
        db.close()
def main():
    p=argparse.ArgumentParser();p.add_argument("--runner",type=Path,required=True)
    p.add_argument("--runner-sha256",required=True);p.add_argument("--out",type=Path)
    a=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<16 or os.getuid()!=1278:
        raise ValueError("ACTUAL16CPU_OWN_SLURM_REQUIRED")
    raw=a.runner.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.runner_sha256:raise ValueError("CANDIDATE_SOURCE_SHA_DIFFER")
    root=a.out or ROOT/"gates"/"metadata_queue_lock_fixture"/("job_"+os.environ["SLURM_JOB_ID"])
    if root.exists() or not root.resolve().is_relative_to(ROOT/"gates"/"metadata_queue_lock_fixture"):
        raise ValueError("NEW_PRIVATE_LOCK_FIXTURE_REQUIRED")
    root.mkdir(parents=True);base=root/"lock_only_no_database"
    mod=load(a.runner);lock_path=Path(str(base)+mod.METADATA_LOCK_SUFFIX)
    ctx=mp.get_context("spawn");barrier=ctx.Barrier(16);starts=ctx.Value("i",0);all_rows=[];holder_proof=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(barrier,starts)) as pool:
        for case in ("deadline","holder_exit","existing_timer"):
            with starts.get_lock():starts.value=0
            ready=ctx.Event();release=ctx.Event()
            process=ctx.Process(target=holder,args=(str(lock_path),ready,release));process.start()
            if not ready.wait(15):raise RuntimeError("ISOLATED_HOLDER_NOT_READY")
            futures=[pool.submit(worker,{"runner":str(a.runner),"lock_base":str(base),"case":case}) for _ in range(16)]
            # Worker barrier starts all16 before waiting. Holder remains locked
            # throughout all .3s deadline attempts, then exits naturally.
            if case!="deadline":
                wait_until=time.monotonic()+30
                while starts.value<16:
                    if time.monotonic()>=wait_until:raise TimeoutError("ALL16_LOCK_WAITERS_NOT_STARTED")
                    time.sleep(.01)
                time.sleep(.1);release.set()
            rows=[future.result(timeout=35) for future in futures]
            release.set();process.join(15)
            if process.is_alive() or process.exitcode!=0:raise RuntimeError("ISOLATED_HOLDER_EXIT_NOT_CLOSED")
            if len({row["pid"] for row in rows})!=16:raise AssertionError("NOT16_ACTUAL_WORKERS")
            all_rows.extend(rows);holder_proof.append({"case":case,"holder_pid":process.pid,"exitcode":process.exitcode})
    # A fresh final acquisition also proves no timed-out waiter leaked ownership.
    db=sqlite3.connect(":memory:",isolation_level=None,factory=mod.BusyConnection);db.configure_retry(base)
    try:db._acquire(time.monotonic()+2);db._release()
    finally:db.close()
    report={"schema":"WP5_R12_ISOLATED_LOCK_FIXTURE_V1","status":"ISOLATED_LOCK_DEADLINE_OWNER_EXIT_PASS",
        "runner":{"path":str(a.runner),"sha256":a.runner_sha256},"job_id":os.environ["SLURM_JOB_ID"],
        "actual_workers":16,"worker_pids":sorted({r["pid"] for r in all_rows}),"cases":all_rows,
        "holders":holder_proof,"signal_handler_and_timer_restored":True,
        "source_queue_opened":False,"original_data_written":False,"QM_calls":0,"LMDB_opened":False,
        "scope":"Isolated flock only. Does not establish production-shape lifecycle PASS.",
        "fixture_temporary_files":[str(lock_path)],"cleanup_executed":False}
    target=root/"report.json";target.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"report":str(target),"actual_workers":16,"QM_calls":0}))
if __name__=="__main__":main()
