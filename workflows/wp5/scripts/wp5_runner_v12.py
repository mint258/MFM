"""WP5 whole-molecule runtime, atomic pending queue and durable family export."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, math, multiprocessing, os, signal, socket, sqlite3
import subprocess, time, traceback, uuid, fcntl, random
from wp5_accounting_v2 import run_sacct
from pathlib import Path

ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
SCREEN=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011")
CALCS=("pm7_B","pm7_cation","pm7_anion","pm7_water","pm7_octanol","xtb_singlepoint",
       "xtb_vipea","xtb_vfukui","xtb_ALPB_water","xtb_ALPB_octanol","xtb_fod","xtb_perturbed_gradient")
NODES=tuple("compute-0-"+str(n) for n in (12,13,14,17,18,19))
NODE_AUTHORITY_SHA='32b0ba7355603c697ac0b2083d090d60fe924eb4d23f7128f451735cf6909d3f'
NODE_SCOPE_PLAN_SHA='dd195e994628c75b710de6e267f99556df59e918b875117907753693af638f3b'
STOP=ROOT/"STOP_NEW_MOLECULES.json"
P99_RATIO=4.671507082406139/1.71
POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+str(os.getpid())+".pending")
    with tmp.open("w") as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n");stream.flush();os.fsync(stream.fileno())
    os.replace(tmp,path)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(8<<20),b""):h.update(block)
    return h.hexdigest()

def stopped():
    return STOP.exists() or (ROOT/"control/STOP.json").exists()

def stop(reason,details=None):
    temporary=STOP.with_name(STOP.name+"."+uuid.uuid4().hex+".pending")
    atomic(temporary,{"time":time.time(),"reason":reason,"details":details,"job_id":os.environ.get("SLURM_JOB_ID")})
    try:os.link(temporary,STOP)
    except FileExistsError:pass
    finally:temporary.unlink(missing_ok=True)

# R12 metadata-only candidate: requires all queue writers/readers in this
# runtime to cooperate on the same sidecar. Legacy R11 connections are NOT
# protected by this flock; validation must use a private production-shape clone.
SQL_LOCK_BUDGET_SECONDS=600.0
SQL_BUSY_TIMEOUT_MS=1000
EXPORT_UPDATE_BATCH=256
EXPORT_UPDATE_MAX_BYTES=1<<20
METADATA_LOCK_SUFFIX=".metadata_v12.lock"

def sqlite_lock_error(error):
    if not isinstance(error,sqlite3.OperationalError):return False
    code=getattr(error,"sqlite_errorcode",None)
    if code is not None:return (code & 255) in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED)
    message=str(error).lower()
    return message in {"database is locked","database table is locked","database schema is locked"} or message.startswith("database table is locked:") or message.startswith("database schema is locked:")

class BufferedCursor:
    """SQLite cursor compatibility with NO live SQLite read statement."""
    def __init__(self,connection,rows=(),description=None,rowcount=-1,lastrowid=None):
        self.connection=connection;self._rows=list(rows);self._offset=0
        self.description=description;self.rowcount=rowcount;self.lastrowid=lastrowid
        self.arraysize=1;self._closed=False
    def fetchone(self):
        if self._closed:raise sqlite3.ProgrammingError("Cannot operate on a closed cursor.")
        if self._offset>=len(self._rows):return None
        row=self._rows[self._offset];self._offset+=1;return row
    def fetchmany(self,size=None):
        if self._closed:raise sqlite3.ProgrammingError("Cannot operate on a closed cursor.")
        size=self.arraysize if size is None else size
        if size<0:size=len(self._rows)-self._offset
        end=min(len(self._rows),self._offset+size)
        rows=self._rows[self._offset:end];self._offset=end;return rows
    def fetchall(self):
        if self._closed:raise sqlite3.ProgrammingError("Cannot operate on a closed cursor.")
        rows=self._rows[self._offset:];self._offset=len(self._rows);return rows
    def __iter__(self):return self
    def __next__(self):
        row=self.fetchone()
        if row is None:raise StopIteration
        return row
    def close(self):
        self._rows=[];self._closed=True
    def execute(self,sql,parameters=(),/):
        replacement=self.connection.execute(sql,parameters)
        self.__dict__.update(replacement.__dict__);return self
    def executemany(self,sql,parameters,/):
        replacement=self.connection.executemany(sql,parameters)
        self.__dict__.update(replacement.__dict__);return self
    def executescript(self,script,/):
        replacement=self.connection.executescript(script)
        self.__dict__.update(replacement.__dict__);return self
    def setinputsizes(self,*_):pass
    def setoutputsize(self,*_):pass

class BusyConnection(sqlite3.Connection):
    """Bounded cooperative lock + complete transaction retry; never replay QM."""
    def configure_retry(self,path,deadline=None):
        self.retry_deadline=deadline;self.retry_budget_seconds=SQL_LOCK_BUDGET_SECONDS
        self.configured_busy_timeout_ms=SQL_BUSY_TIMEOUT_MS
        self.metadata_lock_path=Path(str(path)+METADATA_LOCK_SUFFIX)
        self._metadata_lock=self.metadata_lock_path.open("a+b")
        self._lock_depth=0;self._manual_transaction=False;self._diagnostic_emissions=0
        self.retry_stats={"statement_busy_retries":0,"transaction_busy_retries":0,
            "rollback_count":0,"sleep_seconds":0.0,"last_busy_code":None,
            "file_lock_acquisitions":0,"file_lock_contentions":0,
            "file_lock_blocking_calls":0,"file_lock_blocking_timeouts":0,
            "file_lock_nonblocking_fallback_calls":0,"file_lock_fallback_reasons":{},
            "file_lock_wait_seconds":0.0,"file_lock_wait_max_seconds":0.0,
            "file_lock_hold_seconds":0.0,"file_lock_hold_max_seconds":0.0,
            "sql_operations":0,"sql_elapsed_seconds":0.0,"sql_max_seconds":0.0,
            "transactions":0,"transaction_elapsed_seconds":0.0,"transaction_max_seconds":0.0,
            "last_sql_class":None,"last_sql_sha256":None,"last_transaction_seconds":None,
            "sql_classes":{},"export_batches":0,"export_encoded_bytes_max":0,
            "export_batch_bytes_max":0,"export_oversize_single_rows":0}
        cursor=sqlite3.Connection.execute(self,"PRAGMA busy_timeout="+str(SQL_BUSY_TIMEOUT_MS));cursor.close()

    def _deadline(self,deadline=None):
        until=time.monotonic()+self.retry_budget_seconds
        for bound in (self.retry_deadline,deadline):
            if bound is not None:until=min(until,bound)
        return until

    def _emit(self,kind,**details):
        # Values, scientific payload and literal SQL parameters never enter logs.
        if self._diagnostic_emissions>=100:return
        self._diagnostic_emissions+=1
        print(json.dumps({"schema":"WP5_R12_METADATA_DIAGNOSTIC_V1",
            "kind":kind,"pid":os.getpid(),"node":socket.gethostname().split(".")[0],
            "epoch":time.time(),"lock_path":str(self.metadata_lock_path),**details}),
            file=__import__("sys").stderr,flush=True)

    def _blocking_lock_mode(self):
        if not __import__("sys").platform.startswith("linux"):return False,"NOT_LINUX"
        threading=__import__("threading")
        if threading.current_thread() is not threading.main_thread():return False,"NON_MAIN_THREAD"
        if not all(hasattr(signal,name) for name in ("SIGALRM","ITIMER_REAL","setitimer","getitimer","pthread_sigmask","sigpending","sigwait")):
            return False,"SIGNAL_API_UNAVAILABLE"
        if signal.getsignal(signal.SIGALRM)!=signal.SIG_DFL:return False,"SIGALRM_HANDLER_IN_USE"
        if any(signal.getitimer(signal.ITIMER_REAL)):return False,"SIGALRM_TIMER_IN_USE"
        mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
        if signal.SIGALRM in mask or signal.SIGALRM in signal.sigpending():return False,"SIGALRM_MASKED_OR_PENDING"
        return True,None

    def _blocking_file_lock(self,until):
        # Only the process main thread with an unused ALRM is admitted here.
        # An active/owned timer always uses fallback; we never pause/reset it.
        old_handler=signal.getsignal(signal.SIGALRM)
        old_timer=signal.getitimer(signal.ITIMER_REAL)
        old_mask=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGALRM})
        state={"restoring":False,"expired":False}
        def alarm(_signum,_frame):
            state["expired"]=True
            if not state["restoring"]:raise TimeoutError("METADATA_FLOCK_DEADLINE")
        def restore():
            state["restoring"]=True
            signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGALRM})
            signal.setitimer(signal.ITIMER_REAL,0)
            # No pre-existing pending ALRM was allowed. Consume only the
            # possibly queued one-shot timeout before restoring SIG_DFL.
            if signal.SIGALRM in signal.sigpending():
                signal.sigwait({signal.SIGALRM});state["expired"]=True
            signal.signal(signal.SIGALRM,old_handler)
            signal.setitimer(signal.ITIMER_REAL,*old_timer)
            signal.pthread_sigmask(signal.SIG_SETMASK,old_mask)
        try:
            try:
                signal.signal(signal.SIGALRM,alarm)
                remaining=until-time.monotonic()
                if remaining<=0:raise TimeoutError("METADATA_FLOCK_DEADLINE")
                signal.setitimer(signal.ITIMER_REAL,remaining)
                signal.pthread_sigmask(signal.SIG_SETMASK,old_mask)
                # Kernel waiter queue instead of repeated LOCK_NB barging/RPC.
                fcntl.flock(self._metadata_lock.fileno(),fcntl.LOCK_EX)
            finally:
                restore()
            if state["expired"] or time.monotonic()>=until:
                raise TimeoutError("METADATA_FLOCK_DEADLINE")
        except BaseException:
            # Covers the deadline racing with successful flock before Python
            # can record ownership, plus a timeout arriving at restore entry.
            # LOCK_UN on our unlocked descriptor cannot unlock another owner.
            try:restore()
            finally:fcntl.flock(self._metadata_lock.fileno(),fcntl.LOCK_UN)
            raise

    def _acquire(self,until):
        if self._lock_depth:
            self._lock_depth+=1;return
        started=time.monotonic();contended=False
        blocking,reason=self._blocking_lock_mode()
        try:
            if blocking:
                self.retry_stats["file_lock_blocking_calls"]+=1
                self._blocking_file_lock(until)
            else:
                self.retry_stats["file_lock_nonblocking_fallback_calls"]+=1
                reasons=self.retry_stats["file_lock_fallback_reasons"]
                reasons[reason]=reasons.get(reason,0)+1
                self._emit("FILE_LOCK_NONBLOCKING_FALLBACK",reason=reason)
                while True:
                    if time.monotonic()>=until:raise TimeoutError("METADATA_FLOCK_DEADLINE")
                    try:
                        fcntl.flock(self._metadata_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if not contended:self.retry_stats["file_lock_contentions"]+=1;contended=True
                        time.sleep(min(max(0,until-time.monotonic()),random.SystemRandom().uniform(.005,.025)))
        except TimeoutError:
            seconds=time.monotonic()-started
            self.retry_stats["file_lock_wait_seconds"]+=seconds
            self.retry_stats["file_lock_wait_max_seconds"]=max(self.retry_stats["file_lock_wait_max_seconds"],seconds)
            if blocking:self.retry_stats["file_lock_blocking_timeouts"]+=1
            self._emit("FILE_LOCK_DEADLINE",wait_seconds=seconds,mode="KERNEL_BLOCKING_ALRM" if blocking else "NONBLOCKING_FALLBACK")
            error=sqlite3.OperationalError("database is locked")
            error.metadata_lock_kind="SIDECAR_FLOCK"
            raise error from None
        elapsed=time.monotonic()-started;self._lock_depth=1;self._lock_started=time.monotonic()
        self.retry_stats["file_lock_acquisitions"]+=1
        self.retry_stats["file_lock_wait_seconds"]+=elapsed
        self.retry_stats["file_lock_wait_max_seconds"]=max(self.retry_stats["file_lock_wait_max_seconds"],elapsed)
        if elapsed>=1:self._emit("FILE_LOCK_WAIT",wait_seconds=elapsed,mode="KERNEL_BLOCKING_ALRM" if blocking else "NONBLOCKING_FALLBACK")

    def _release(self):
        if not self._lock_depth:return
        self._lock_depth-=1
        if self._lock_depth:return
        elapsed=time.monotonic()-self._lock_started
        self.retry_stats["file_lock_hold_seconds"]+=elapsed
        self.retry_stats["file_lock_hold_max_seconds"]=max(self.retry_stats["file_lock_hold_max_seconds"],elapsed)
        fcntl.flock(self._metadata_lock.fileno(),fcntl.LOCK_UN)
        if elapsed>=1:self._emit("FILE_LOCK_HOLD",seconds=elapsed,last_sql_class=self.retry_stats["last_sql_class"],last_sql_sha256=self.retry_stats["last_sql_sha256"])

    def _raw(self,sql,parameters=(),many=False):
        started=time.monotonic();tokens=sql.lstrip().split(None,2)
        category=" ".join(tokens[:2]).upper() if tokens else "EMPTY"
        fingerprint=hashlib.sha256(sql.encode()).hexdigest()
        cursor=None;failure=None
        try:
            cursor=(sqlite3.Connection.executemany(self,sql,parameters) if many else sqlite3.Connection.execute(self,sql,parameters))
            # Materialize BEFORE raw cursor close AND sidecar unlock.
            rows=cursor.fetchall() if cursor.description is not None else []
            return BufferedCursor(self,rows,cursor.description,cursor.rowcount,cursor.lastrowid)
        except BaseException as error:
            failure=type(error).__name__;raise
        finally:
            if cursor is not None:cursor.close()
            elapsed=time.monotonic()-started
            self.retry_stats["sql_operations"]+=1;self.retry_stats["sql_elapsed_seconds"]+=elapsed
            self.retry_stats["sql_max_seconds"]=max(self.retry_stats["sql_max_seconds"],elapsed)
            self.retry_stats["last_sql_class"]=category;self.retry_stats["last_sql_sha256"]=fingerprint
            counts=self.retry_stats["sql_classes"];counts[category]=counts.get(category,0)+1
            if elapsed>=1 or failure:self._emit("SQL_OPERATION",sql_class=category,sql_sha256=fingerprint,seconds=elapsed,error_type=failure)

    def _bounded(self,operation,category,deadline=None):
        until=self._deadline(deadline);last=None;attempt=0
        try:
            while True:
                remaining=until-time.monotonic()
                if remaining<=0:
                    if last is not None:raise last
                    raise TimeoutError("SQL_METADATA_RETRY_DEADLINE_REACHED")
                self._acquire(until)
                try:
                    timeout_ms=max(0,min(self.configured_busy_timeout_ms,int(max(0,until-time.monotonic())*1000)))
                    self._raw("PRAGMA busy_timeout="+str(timeout_ms))
                    try:return operation()
                    except sqlite3.OperationalError as error:
                        if not sqlite_lock_error(error):raise
                        last=error;attempt+=1;self.retry_stats[category+"_busy_retries"]+=1
                        self.retry_stats["last_busy_code"]=getattr(error,"sqlite_errorcode",str(error))
                finally:
                    # This is connection-local, with the sidecar still held.
                    self._raw("PRAGMA busy_timeout="+str(self.configured_busy_timeout_ms))
                    self._release()
                remaining=until-time.monotonic()
                if remaining<=0:raise last
                delay=min(remaining,min(.25,.01*(2**min(attempt,5)))+random.SystemRandom().uniform(0,.02))
                time.sleep(delay);self.retry_stats["sleep_seconds"]+=delay
        except BaseException as error:
            self._emit("METADATA_OPERATION_FAILED",category=category,error_type=type(error).__name__,last_sql_class=self.retry_stats["last_sql_class"])
            raise

    def execute(self,sql,parameters=(),/):
        token=sql.strip().rstrip(";").split(None,1)[0].upper() if sql.strip() else ""
        if token in {"BEGIN","SAVEPOINT"}:
            if self.in_transaction or self._manual_transaction:raise RuntimeError("NESTED_QUEUE_TRANSACTION_NOT_ALLOWED")
            if token=="SAVEPOINT":raise ValueError("EXPLICIT_SAVEPOINT_OUTSIDE_METADATA_TRANSACTION_NOT_ALLOWED")
            until=self._deadline()
            self._acquire(until)
            try:
                # Keep the outer sidecar lock after _bounded returns, including
                # SQLite BEGIN retries; the explicit COMMIT/ROLLBACK releases it.
                result=self._bounded(lambda:self._raw(sql,parameters),"statement",until)
                self._manual_transaction=True;return result
            except BaseException:self._release();raise
        if token in {"COMMIT","END","ROLLBACK"} and self._manual_transaction:
            try:return self._raw(sql,parameters)
            finally:
                if not self.in_transaction:self._manual_transaction=False;self._release()
        if self.in_transaction:
            if not self._lock_depth:raise RuntimeError("SQLITE_TRANSACTION_WITHOUT_METADATA_LOCK")
            return self._raw(sql,parameters)
        result=self._bounded(lambda:self._raw(sql,parameters),"statement")
        normalized=sql.strip().rstrip(";").upper().replace(" ","")
        if normalized.startswith("PRAGMABUSY_TIMEOUT="):
            self.configured_busy_timeout_ms=int(normalized.split("=",1)[1])
            # _bounded restores the previous value before this assignment.
            self._bounded(lambda:self._raw("PRAGMA busy_timeout="+str(self.configured_busy_timeout_ms)),"statement")
        return result

    def transaction(self,operation,deadline=None):
        if self.in_transaction:raise RuntimeError("NESTED_QUEUE_TRANSACTION_NOT_ALLOWED")
        def once():
            started=time.monotonic();failure=None
            try:
                self._raw("BEGIN IMMEDIATE");result=operation();self._raw("COMMIT");return result
            except BaseException as error:
                failure=type(error).__name__
                if self.in_transaction:
                    try:self._raw("ROLLBACK")
                    except BaseException as rollback_error:
                        raise RuntimeError("SQL_METADATA_ROLLBACK_FAILED_NO_REPLAY") from rollback_error
                    self.retry_stats["rollback_count"]+=1
                raise
            finally:
                elapsed=time.monotonic()-started
                self.retry_stats["transactions"]+=1;self.retry_stats["transaction_elapsed_seconds"]+=elapsed
                self.retry_stats["transaction_max_seconds"]=max(self.retry_stats["transaction_max_seconds"],elapsed)
                self.retry_stats["last_transaction_seconds"]=elapsed
                if elapsed>=1 or failure:self._emit("WRITE_TRANSACTION",seconds=elapsed,error_type=failure)
        return self._bounded(once,"transaction",deadline)

    def executemany(self,sql,parameters,/):
        rows=tuple(parameters)
        if self.in_transaction:
            if not self._lock_depth:raise RuntimeError("SQLITE_TRANSACTION_WITHOUT_METADATA_LOCK")
            return self._raw(sql,rows,many=True)
        return self.transaction(lambda:self._raw(sql,rows,many=True))

    def executescript(self,script,/):
        statements=[];pending=""
        for char in script:
            pending+=char
            if char==";" and sqlite3.complete_statement(pending):statements.append(pending);pending=""
        if pending.strip():statements.append(pending)
        for statement in statements:
            token=statement.lstrip().split(None,1)[0].upper().rstrip(";")
            if token in {"BEGIN","COMMIT","END","ROLLBACK","SAVEPOINT","RELEASE"}:
                raise ValueError("EXPLICIT_TRANSACTION_IN_METADATA_SCRIPT_NOT_ALLOWED")
        def run():
            result=BufferedCursor(self)
            for statement in statements:result=self._raw(statement)
            return result
        if self.in_transaction:return run()
        return self.transaction(run)

    def cursor(self,*args,**kwargs):
        if args or kwargs:raise ValueError("CUSTOM_RAW_QUEUE_CURSOR_NOT_ALLOWED")
        return BufferedCursor(self)

    def commit(self):
        if self.in_transaction:return self.execute("COMMIT")
    def rollback(self):
        if self.in_transaction:return self.execute("ROLLBACK")
    def close(self):
        try:
            if self.in_transaction:self._raw("ROLLBACK")
        finally:
            self._manual_transaction=False
            while self._lock_depth:self._release()
            self._metadata_lock.close();sqlite3.Connection.close(self)

def connection(path,deadline=None):
    db=sqlite3.connect(str(path),timeout=SQL_BUSY_TIMEOUT_MS/1000,isolation_level=None,factory=BusyConnection)
    db.row_factory=sqlite3.Row;db.configure_retry(path,deadline)
    try:
        mode=db.execute("PRAGMA journal_mode").fetchone()[0]
        if mode.lower()!="delete":raise ValueError("QUEUE_JOURNAL_MODE_MUST_ALREADY_BE_DELETE")
        db.execute("PRAGMA synchronous=FULL")
        return db
    except BaseException:
        db.close();raise

QUEUE_SCHEMA_STATEMENTS=(
            "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)",
            "CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY,node TEXT,record_directory TEXT,state TEXT,job_id TEXT,heartbeat REAL)",
            "CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,job_id TEXT,task_id TEXT,mode TEXT,claims INTEGER,start REAL,end REAL)",
            """CREATE TABLE IF NOT EXISTS molecules(
            molecule_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,file_group INTEGER,record_count INTEGER,
            predicted_seconds REAL,priority INTEGER,state TEXT NOT NULL DEFAULT 'PENDING',attempt INTEGER NOT NULL DEFAULT 0,
            owner TEXT,lane INTEGER,archive_path TEXT,receipt_json TEXT,counts_json TEXT,
            completion_rank INTEGER,export_json TEXT,updated REAL)""",
            "CREATE INDEX IF NOT EXISTS pending_order ON molecules(state,task_id,priority)",
            "CREATE INDEX IF NOT EXISTS completion_order ON molecules(completion_rank)",
            "CREATE INDEX IF NOT EXISTS owner_state_order ON molecules(owner,state)",
            """CREATE INDEX IF NOT EXISTS cleanup_pending_cost ON molecules(predicted_seconds DESC,molecule_id)
               WHERE state IN ('PENDING','RETRY_PENDING')""",
            "CREATE TABLE IF NOT EXISTS export_repairs(run_root TEXT PRIMARY KEY,owner TEXT,job_id TEXT,state TEXT,updated REAL,error TEXT)") + (
    "CREATE INDEX IF NOT EXISTS cleanup_task_pending_cost ON molecules(task_id,predicted_seconds DESC,molecule_id) WHERE state IN ('PENDING','RETRY_PENDING')",)

QUEUE_REQUIRED_COLUMNS={
    "meta":("key","value"),
    "tasks":("task_id","node","record_directory","state","job_id","heartbeat"),
    "sessions":("session_id","job_id","task_id","mode","claims","start","end"),
    "molecules":("molecule_id","task_id","file_group","record_count","predicted_seconds","priority",
        "state","attempt","owner","lane","archive_path","receipt_json","counts_json","completion_rank","export_json","updated"),
    "export_repairs":("run_root","owner","job_id","state","updated","error")}
QUEUE_REQUIRED_INDICES={
    "pending_order":(("state",0),("task_id",0),("priority",0)),
    "completion_order":(("completion_rank",0),),
    "owner_state_order":(("owner",0),("state",0)),
    "cleanup_pending_cost":(("predicted_seconds",1),("molecule_id",0)),
    "cleanup_task_pending_cost":(("task_id",0),("predicted_seconds",1),("molecule_id",0))}

def summary_index_support(db):
    """Discover equivalent existing narrow indices before any bootstrap DDL."""
    state_cover=None;durable_partial=None
    rows=db.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='molecules'").fetchall()
    for row in rows:
        name=row["name"];quoted='"'+name.replace('"','""')+'"'
        keys=tuple((value["name"],value["desc"]) for value in db.execute("PRAGMA index_xinfo("+quoted+")").fetchall() if value["key"])
        normalized="".join((row["sql"] or "").upper().split()).replace('"',"").replace("`","")
        predicate=normalized.split("WHERE",1)[1].strip("()") if "WHERE" in normalized else None
        if keys==(("state",0),("record_count",0)) and predicate is None:state_cover=name
        if keys==(("molecule_id",0),) and predicate=="RECEIPT_JSONISNOTNULL":durable_partial=name
    return {"state_record_count_covering_index":state_cover,
            "durable_receipt_partial_index":durable_partial}

def bootstrap_summary_indices(db):
    support=summary_index_support(db)
    if support["state_record_count_covering_index"] is None:
        db.execute("CREATE INDEX summary_state_records_cover ON molecules(state,record_count)")
    if support["durable_receipt_partial_index"] is None:
        db.execute("CREATE INDEX durable_receipt_count ON molecules(molecule_id) WHERE receipt_json IS NOT NULL")
    return summary_index_support(db)


def queue_schema_ready(db):
    """Read-only structural guard; workers must never bootstrap/migrate."""
    objects={r["name"]:dict(r) for r in db.execute(
        "SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','index')").fetchall()}
    for table,required in QUEUE_REQUIRED_COLUMNS.items():
        if table not in objects or objects[table]["type"]!="table":
            raise ValueError("QUEUE_SCHEMA_BOOTSTRAP_REQUIRED:TABLE:"+table)
        columns=tuple(row["name"] for row in db.execute("PRAGMA table_info("+table+")").fetchall())
        if columns!=required:raise ValueError("QUEUE_SCHEMA_COLUMNS_DIFFER:"+table)
    for name,required in QUEUE_REQUIRED_INDICES.items():
        if name not in objects or objects[name]["type"]!="index":
            raise ValueError("QUEUE_SCHEMA_BOOTSTRAP_REQUIRED:INDEX:"+name)
        actual=tuple((row["name"],row["desc"]) for row in db.execute("PRAGMA index_xinfo("+name+")").fetchall() if row["key"])
        if actual!=required:raise ValueError("QUEUE_SCHEMA_INDEX_DIFFER:"+name)
        if name.startswith("cleanup_"):
            sql="".join((objects[name]["sql"] or "").upper().split()).replace('"',"").replace("`","")
            if not sql.endswith("WHERESTATEIN('PENDING','RETRY_PENDING')"):
                raise ValueError("QUEUE_SCHEMA_PARTIAL_INDEX_DIFFER:"+name)
    summary_support=summary_index_support(db)
    if any(value is None for value in summary_support.values()):
        raise ValueError("QUEUE_SCHEMA_BOOTSTRAP_REQUIRED:SUMMARY_NARROW_INDICES")
    return {"status":"SCHEMA_READY_READ_ONLY","tables":sorted(QUEUE_REQUIRED_COLUMNS),
            "indices":sorted(QUEUE_REQUIRED_INDICES),"summary_index_support":summary_support}

def bootstrap_metadata(path,deadline=None):
    """EXPLICIT single-coordinator action; never called by Queue/worker."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    db=connection(path,deadline)
    try:
        before=db.total_changes
        def initialize_schema():
            for statement in QUEUE_SCHEMA_STATEMENTS:db.execute(statement)
            return bootstrap_summary_indices(db)
        db.transaction(initialize_schema)
        proof=db._bounded(lambda:queue_schema_ready(db),"statement")
        return {**proof,"path":str(path),"bootstrap_explicit":True,
                "total_changes":db.total_changes-before,"metadata_retry_stats":dict(db.retry_stats)}
    finally:db.close()

class Queue:
    def __init__(self,path,deadline=None,baseline_path=None):
        self.path=Path(path)
        if not self.path.is_file():raise ValueError("QUEUE_SCHEMA_BOOTSTRAP_REQUIRED:DATABASE_MISSING")
        self.db=connection(path,deadline)
        self.baseline_path=Path(baseline_path) if baseline_path is not None else None
        self.cache_path=self.path.with_name(self.path.name+".first5_health_v1.json")
        self.cache_lock_path=self.cache_path.with_name(self.cache_path.name+".lock")
        try:
            before=self.db.total_changes
            self.schema_proof=self.db._bounded(lambda:queue_schema_ready(self.db),"statement")
            if self.db.total_changes!=before or self.db.in_transaction:
                raise RuntimeError("QUEUE_SCHEMA_FASTPATH_WROTE_OR_LEFT_TRANSACTION")
        except BaseException:
            self.db.close();raise

    def _meta(self):
        return dict(self.db.execute("SELECT key,value FROM meta").fetchall())

    def seed(self,plan,assignments,smoke=False):
        plan_bytes=Path(plan).read_bytes();sha=hashlib.sha256(plan_bytes).hexdigest()
        existing=self._meta()
        if existing.get("plan_sha256"):
            if existing["plan_sha256"]!=sha:raise ValueError("Queue frozen plan differs")
            if existing.get("population_source_sha256"):return
            # Existing R10 queue: bind the immutable population outside any lock.
            population_sha=digest(assignments)
            def bind_existing():
                current=self._meta()
                if current.get("plan_sha256")!=sha:raise ValueError("Queue frozen plan differs")
                old=current.get("population_source_sha256")
                if old is not None and old!=population_sha:raise ValueError("Queue frozen population differs")
                self.db.execute("INSERT OR IGNORE INTO meta VALUES('population_source_sha256',?)",(population_sha,))
            self.db.transaction(bind_existing);return
        # Initial Arrow decoding/hash must not hold a queue write transaction.
        import pyarrow.parquet as pq
        molecules=pq.read_table(assignments,use_threads=True).to_pylist()
        if len({r["molecule_id"] for r in molecules})!=len(molecules):raise ValueError("MANIFEST_DUPLICATE_QUEUE_MOLECULE")
        population_sha=digest(assignments);tasks=json.loads(plan_bytes)["tasks"]
        def insert_initial():
            old=self.db.execute("SELECT value FROM meta WHERE key='plan_sha256'").fetchone()
            if old:
                if old[0]!=sha:raise ValueError("Queue frozen plan differs")
                current=self.db.execute("SELECT value FROM meta WHERE key='population_source_sha256'").fetchone()
                if current and current[0]!=population_sha:raise ValueError("Queue frozen population differs")
                return
            self.db.executemany("INSERT INTO tasks VALUES(?,?,?,'READY',NULL,NULL)",
                [(str(t["task_id"]),t["node"],t["record_directory"]) for t in tasks])
            self.db.executemany("INSERT INTO molecules(molecule_id,task_id,file_group,record_count,predicted_seconds,priority,updated) VALUES(?,?,?,?,?,?,?)",
                [(r["molecule_id"],str(r["task_id"]),r["file_group"],r["records"],
                  r["planned_allocated_seconds"],r["sequence_in_task"],time.time()) for r in molecules])
            self.db.executemany("INSERT INTO meta VALUES(?,?)",[("plan_sha256",sha),("population_molecules",str(len(molecules))),
                ("population_records",str(sum(r["records"] for r in molecules))),("completion_sequence","0"),
                ("smoke",str(int(smoke))),("population_source_sha256",population_sha)])
        self.db.transaction(insert_initial)

    def start(self,session,job,task,mode,node):
        def update():
            self.db.execute("INSERT INTO sessions VALUES(?,?,?,?,0,?,NULL)",(session,job,str(task),mode,time.time()))
            if mode=="main":
                row=self.db.execute("SELECT * FROM tasks WHERE task_id=?",(str(task),)).fetchone()
                if row is None or row["node"]!=node:raise ValueError("TASK_NODE_BINDING_MISMATCH")
                if row["state"]=="RUNNING" and row["job_id"]!=job:raise ValueError("Task already owned by live job")
                self.db.execute("UPDATE tasks SET state='RUNNING',job_id=?,heartbeat=? WHERE task_id=?",(job,time.time(),str(task)))
        self.db.transaction(update)

    def claim(self,session,task,mode,remaining,cap):
        claim_deadline=time.monotonic()+remaining
        def update():
            if stopped() or time.monotonic()>=claim_deadline:return None
            claims=self.db.execute("SELECT claims FROM sessions WHERE session_id=?",(session,)).fetchone()[0]
            if cap and claims>=cap:return None
            if mode=="main":
                row=self.db.execute("SELECT m.*,t.record_directory FROM molecules m JOIN tasks t USING(task_id) "
                    "WHERE m.task_id=? AND m.state='PENDING' ORDER BY priority,molecule_id LIMIT 1",(str(task),)).fetchone()
            else:
                # Eligibility is fixed inside this short, fully serialized
                # transaction. Seek ONE top row per eligible task, then retain
                # SQLite's original global DESC cost / BINARY molecule ID order.
                eligible=self.db.execute("SELECT task_id,record_directory FROM tasks "
                    "WHERE state IN ('CLOSED','DEAD')").fetchall()
                candidates=[]
                for task_row in eligible:
                    candidate=self.db.execute("SELECT m.* FROM molecules m INDEXED BY cleanup_task_pending_cost "
                        "WHERE m.task_id=? AND m.state IN ('PENDING','RETRY_PENDING') "
                        "ORDER BY predicted_seconds DESC,molecule_id LIMIT 1",(task_row["task_id"],)).fetchone()
                    if candidate is not None:
                        value=dict(candidate);value["record_directory"]=task_row["record_directory"];candidates.append(value)
                row=min(candidates,key=lambda value:(-(value["predicted_seconds"] if value["predicted_seconds"] is not None else float("-inf")),value["molecule_id"])) if candidates else None
            if row is None or row["predicted_seconds"]*P99_RATIO>claim_deadline-time.monotonic():return None
            attempt=row["attempt"]+(row["state"]=="RETRY_PENDING")
            if attempt>1:raise RuntimeError("Retry budget exceeded")
            self.db.execute("UPDATE molecules SET state='RUNNING',attempt=?,owner=?,updated=? WHERE molecule_id=?",
                            (attempt,session,time.time(),row["molecule_id"]))
            self.db.execute("UPDATE sessions SET claims=claims+1 WHERE session_id=?",(session,))
            result=dict(row);result["attempt"]=attempt;return result
        if stopped() or remaining<=0:return None
        try:return self.db.transaction(update,claim_deadline)
        except (TimeoutError,sqlite3.OperationalError) as error:
            if time.monotonic()>=claim_deadline and (isinstance(error,TimeoutError) or sqlite_lock_error(error)):return None
            raise

    def finish(self,session,summary):
        def update():
            row=self.db.execute("SELECT * FROM molecules WHERE molecule_id=?",(summary["molecule_id"],)).fetchone()
            if row is None or row["owner"]!=session or row["state"]!="RUNNING":raise RuntimeError("Queue completion owner differs")
            if summary.get("partial") or summary.get("error"):
                state="PENDING" if summary.get("partial") else ("RETRY_PENDING" if summary.get("retryable",False) and row["attempt"]==0 else "ATTENTION_REQUIRED")
                self.db.execute("UPDATE molecules SET state=?,owner=NULL,export_json=?,updated=? WHERE molecule_id=?",
                    (state,json.dumps({"unpublished_pipeline_failure":summary}) if summary.get("error") else None,time.time(),row["molecule_id"]))
            else:
                rank=row["completion_rank"]
                if rank is None:
                    rank=int(self.db.execute("SELECT value FROM meta WHERE key='completion_sequence'").fetchone()[0])+1
                    self.db.execute("UPDATE meta SET value=? WHERE key='completion_sequence'",(str(rank),))
                state="RETRY_PENDING" if summary["retryable"] and row["attempt"]==0 else "COMPLETE"
                self.db.execute("UPDATE molecules SET state=?,lane=?,archive_path=?,receipt_json=?,counts_json=?,completion_rank=?,updated=? "
                    "WHERE molecule_id=?",(state,summary["lane"],summary["archive_path"],json.dumps(summary),json.dumps(summary["counts"]),rank,time.time(),row["molecule_id"]))
        self.db.transaction(update)

    def release_running(self,session):
        self.db.execute("UPDATE molecules SET state=CASE WHEN attempt=0 THEN 'RETRY_PENDING' ELSE 'FINAL_FAILURE' END,owner=NULL,updated=? "
                        "WHERE owner=? AND state='RUNNING'",(time.time(),session))

    def claim_export_repair(self,root,session,job):
        def update():
            row=self.db.execute("SELECT * FROM export_repairs WHERE run_root=?",(str(root),)).fetchone()
            if row is not None and row["state"]=="RUNNING":return False
            self.db.execute("INSERT INTO export_repairs VALUES(?,?,?,'RUNNING',?,NULL) ON CONFLICT(run_root) DO UPDATE SET "
                            "owner=excluded.owner,job_id=excluded.job_id,state='RUNNING',updated=excluded.updated,error=NULL",
                            (str(root),session,job,time.time()))
            return True
        return self.db.transaction(update)

    def finish_export_repair(self,root,session,error=None):
        self.db.execute("UPDATE export_repairs SET state=?,error=?,updated=? WHERE run_root=? AND owner=?",
            ("ERROR" if error else "COMPLETE",error,time.time(),str(root),session))

    def publish_export(self,session,references,archive):
        # Fully buffered read: no live cursor persists during JSON encoding or
        # shared-path work. Bound the actual UTF-8 parameter bytes per write txn.
        identifiers=[row[0] for row in self.db.execute("SELECT molecule_id FROM molecules "
            "WHERE owner=? AND receipt_json IS NOT NULL",(session,)).fetchall()]
        encoded=json.dumps({"families":references,"archive":archive})
        encoded_bytes=len(encoded.encode("utf-8"))
        self.db.retry_stats["export_encoded_bytes_max"]=max(self.db.retry_stats["export_encoded_bytes_max"],encoded_bytes)
        batches=[];batch=[];batch_bytes=0
        for identifier in identifiers:
            parameters=(encoded,archive["path"],identifier,session)
            size=sum(len(str(value).encode("utf-8")) for value in parameters)
            if batch and (len(batch)>=EXPORT_UPDATE_BATCH or batch_bytes+size>EXPORT_UPDATE_MAX_BYTES):
                batches.append((batch,batch_bytes));batch=[];batch_bytes=0
            if size>EXPORT_UPDATE_MAX_BYTES:self.db.retry_stats["export_oversize_single_rows"]+=1
            batch.append(parameters);batch_bytes+=size
        if batch:batches.append((batch,batch_bytes))
        for batch,size in batches:
            self.db.transaction(lambda:self.db.executemany(
                "UPDATE molecules SET export_json=?,archive_path=? WHERE molecule_id=? AND owner=? AND receipt_json IS NOT NULL",batch))
            self.db.retry_stats["export_batches"]+=1
            self.db.retry_stats["export_batch_bytes_max"]=max(self.db.retry_stats["export_batch_bytes_max"],size)

    def end(self,session,task,mode):
        def update():
            self.db.execute("UPDATE sessions SET end=? WHERE session_id=?",(time.time(),session))
            if mode=="main":self.db.execute("UPDATE tasks SET state='CLOSED',heartbeat=? WHERE task_id=?",(time.time(),str(task)))
        self.db.transaction(update)

    def summary(self):
        grouped=[dict(r) for r in self.db.execute("SELECT state,count(*) AS molecules,sum(record_count) AS records FROM molecules GROUP BY state").fetchall()]
        return {"states":grouped,"durable_completed_molecules":self.db.execute("SELECT count(*) FROM molecules WHERE receipt_json IS NOT NULL").fetchone()[0],
                "pending_molecules":self.db.execute("SELECT count(*) FROM molecules WHERE state IN ('PENDING','RETRY_PENDING','RUNNING')").fetchone()[0]}

    def early_health_snapshot(self,baseline):
        if set(baseline)!=set(CALCS) or any(not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not 0<=value<=1 for value in baseline.values()):
            raise ValueError("PILOT_BASELINE_MUST_HAVE12_VALID_REQUIRED_SCOPE_SUCCESS_RATES")
        meta=self._meta();population=int(meta["population_molecules"])
        early=max(1,math.ceil(population*.05))
        # finish assigns each unique rank and increments this counter in the same
        # transaction; retries preserve the rank. No wide-table COUNT is needed.
        done=int(meta["completion_sequence"])
        if done<early:return None
        baseline_mapping_sha=hashlib.sha256(json.dumps(baseline,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        baseline_file_sha=None
        if self.baseline_path is not None:
            raw=self.baseline_path.read_bytes();baseline_file_sha=hashlib.sha256(raw).hexdigest()
            if json.loads(raw)["success_rates"]!=baseline:raise ValueError("HEALTH_BASELINE_FILE_AND_RATES_DIFFER")
        population_sha=meta.get("population_source_sha256")
        fallback={"plan_sha256":meta["plan_sha256"],"population_molecules":population,"population_records":int(meta["population_records"])}
        if population_sha is None:population_sha=hashlib.sha256(json.dumps(fallback,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        bindings={**fallback,"population_sha256":population_sha,
                  "population_binding_kind":"assignments_file_sha256" if meta.get("population_source_sha256") else "counts_and_plan_sha256",
                  "baseline_sha256":baseline_file_sha or baseline_mapping_sha,"baseline_mapping_sha256":baseline_mapping_sha}
        def existing():
            if not self.cache_path.exists():return None
            cached=json.loads(self.cache_path.read_text())
            if cached.get("schema")!="WP5_FIRST5_HEALTH_SNAPSHOT_V1" or cached.get("status")!="READY" or cached.get("bindings")!=bindings:
                raise ValueError("EARLY_HEALTH_CACHE_BINDINGS_DIFFER")
            return cached
        cached=existing()
        if cached is not None:return cached
        with self.cache_lock_path.open("a+b") as lock:
            try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return None
            try:
                cached=existing()
                if cached is not None:return cached
                rows=self.db.execute("""SELECT j.key AS calc_type,
                    sum(json_extract(j.value,'$.success')) AS success,
                    sum(json_extract(j.value,'$.total')) AS total,
                    count(*) AS observed_prefix_molecules,
                    sum(m.record_count) AS expected_prefix_records
                    FROM molecules AS m JOIN json_each(m.counts_json) AS j
                    WHERE m.completion_rank<=?
                    GROUP BY j.key""",(early,)).fetchall()
                by_calc={row["calc_type"]:dict(row) for row in rows}
                if set(by_calc)!=set(CALCS):raise ValueError("EARLY_HEALTH_TWELVE_TASK_COUNTS_NOT_CLOSED")
                counts={};rates={};prefix_records=set()
                for calc in CALCS:
                    row=by_calc[calc];success,total=row["success"],row["total"]
                    if row["observed_prefix_molecules"]!=early or total!=row["expected_prefix_records"] or success is None or total is None or not 0<=success<=total:
                        raise ValueError("EARLY_HEALTH_PREFIX_DENOMINATOR_NOT_CLOSED:"+calc)
                    counts[calc]={"success":success,"total":total};rates[calc]=success/total if total else None
                    prefix_records.add(row["expected_prefix_records"])
                if len(prefix_records)!=1:raise ValueError("EARLY_HEALTH_RECORD_DENOMINATORS_DIFFER")
                cached={"schema":"WP5_FIRST5_HEALTH_SNAPSHOT_V1","status":"READY","bindings":bindings,
                    "population_molecules":population,"early_molecules":early,"completed_rank_sequence":done,
                    "observed_prefix_molecules":early,"prefix_records":next(iter(prefix_records)),
                    "counts":counts,"rates":rates,"baseline":baseline,"published_epoch":time.time(),
                    "publisher_pid":os.getpid(),"publisher_node":socket.gethostname().split(".")[0],
                    "counts_semantics":"First fixed completion-rank prefix at this single SQLite statement snapshot; subsequent scientific retries do not change this cache.",
                    "aggregate_sql_statements":1}
                atomic(self.cache_path,cached)
                return cached
            finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

    def recover_node(self,node,dictionaries):
        # Called only by the pre-submitted afterany cleanup for this same node.
        active=self.db.execute("SELECT task_id,job_id FROM tasks WHERE node=? AND state='RUNNING'",(node,)).fetchall()
        if not active:return
        ids=[r["job_id"] for r in active if r["job_id"]]
        result=run_sacct(["-X","-n","-P","-j",",".join(ids),"--format=JobID,User,State"],timeout=60)
        if result.returncode!=0:raise RuntimeError("RECOVERY_ACCOUNTING_QUERY_FAILED:"+result.evidence_path)
        states={}
        for line in result.stdout.splitlines():
            fields=[value.strip() for value in line.split("|")]
            if len(fields)>=3 and fields[1]=="zixiao" and fields[2]:states[fields[0]]=fields[2].split()[0]
        for task in active:
            state=states.get(task["job_id"])
            if not state or state in {"RUNNING","PENDING","COMPLETING"}:continue
            if state in {"OUT_OF_MEMORY","TIMEOUT"}:stop("SLURM_"+state,dict(task));continue
            from wp5_archive_v5 import ArchiveReader
            pending=self.db.execute("SELECT molecule_id,owner,archive_path FROM molecules WHERE task_id=? AND state='RUNNING'",(task["task_id"],)).fetchall()
            for item in pending:
                if not item["archive_path"] or not Path(item["archive_path"]).exists():continue
                reader=ArchiveReader(item["archive_path"],dictionaries)
                try:durable=reader.completion(item["molecule_id"])
                finally:reader.close()
                if durable:self.finish(item["owner"],durable["receipt"])
            def close_dead_task():
                self.db.execute("UPDATE molecules SET state=CASE WHEN attempt=0 THEN 'RETRY_PENDING' ELSE 'FINAL_FAILURE' END,"
                    "owner=NULL WHERE task_id=? AND state='RUNNING'",(task["task_id"],))
                self.db.execute("UPDATE tasks SET state='DEAD' WHERE task_id=?",(task["task_id"],))
            self.db.transaction(close_dead_task)

def health(queue,baseline):
    path=ROOT/"reports/observation_latest.json"
    if path.exists():
        report=json.loads(path.read_text())
        free=report.get("quota_parsed",{}).get("remaining_bytes")
        if free is not None and free<300_000_000_000:stop("QUOTA_REMAINING_BELOW_300GB",{"remaining_bytes":free})
        owners={r[0] for r in queue.db.execute("SELECT DISTINCT job_id FROM sessions")}
        actual=0.;accounted=set();available=False
        for line in report.get("sacct",{}).get("stdout","").splitlines():
            f=line.split("|")
            if len(f)>=8 and f[0] in owners and f[2]=="zixiao":
                if f[3].split()[0] in {"OUT_OF_MEMORY","TIMEOUT"}:stop("SLURM_"+f[3],{"job_id":f[0]})
                try:actual+=int(f[5])*int(f[6])/3600;accounted.add(f[0])
                except ValueError:pass
        available=bool(owners) and owners.issubset(accounted)
        population=int(queue.db.execute("SELECT value FROM meta WHERE key='population_molecules'").fetchone()[0])
        smoke=bool(int(queue.db.execute("SELECT value FROM meta WHERE key='smoke'").fetchone()[0]))
        done=queue.db.execute("SELECT count(*) FROM molecules WHERE completion_rank IS NOT NULL").fetchone()[0]
        if not smoke and available and done>=population*.1 and actual*population/done>50000:
            stop("EXTRAPOLATED_ACTUAL_CORE_HOURS_ABOVE50000",{"actual_core_hours":actual,"completed_molecules":done})
    if stopped():return
    smoke=bool(int(queue.db.execute("SELECT value FROM meta WHERE key='smoke'").fetchone()[0]))
    if not smoke:
        snapshot=queue.early_health_snapshot(baseline)
        if snapshot is not None:
            for calc,pilot_rate in baseline.items():
                success=snapshot["counts"][calc]["success"];total=snapshot["counts"][calc]["total"]
                if total and success/total<pilot_rate-.02:
                    stop("EARLY_TASK_SUCCESS_DROP_GT2PP",{"task":calc,"success":success,"total":total,"pilot":pilot_rate,
                         "snapshot_path":str(queue.cache_path),"early_molecules":snapshot["early_molecules"]})

_WORKER={}
def initialize_worker(options,lane,barrier):
    import wp5_engine_v3
    from wp5_archive_v5 import ArchiveWriter
    archive=Path(options["run_root"])/"temporary_lanes"/("lane_"+str(lane).zfill(2)+".sqlite")
    scratch=Path(options["scratch_root"])/("wp5_"+options["job_id"]+"_"+options["session"][:8]) / ("lane_"+str(lane))
    scratch.mkdir(parents=True,exist_ok=True)
    for binding in options["source_bindings"]:
        if digest(binding["path"])!=binding["sha256"]:raise ValueError("FROZEN_RUNTIME_SOURCE_CHANGED")
    wp5_engine_v3.initialize_worker(options["source_plan"],options["protocol"],str(scratch),
        registry_sha=options["registry_sha"],deadline=options["hard_epoch"],audit_membership=options["audit_membership"],reproduction_package=options["reproduction_package"])
    writer=ArchiveWriter(archive,options["dictionaries"],options["protocol"],policy=options["policy"],resume=True,reproduction_package=options["reproduction_package"],audit_membership=options["audit_membership"])
    _WORKER.update(options=options,lane=lane,writer=writer,scratch=scratch)
    barrier.wait(timeout=300)

def normalize_source_row(source,audit_ids=None):
    """Derive ONLY missing run metadata from the formal stored molecule maximum."""
    row=dict(source);heavy=row.get('molecule_max_heavy_atoms')
    if isinstance(heavy,bool) or not isinstance(heavy,(int,float)) or not math.isfinite(heavy) or heavy<0 or int(heavy)!=heavy:
        raise ValueError('MANIFEST_MOLECULE_MAX_HEAVY_ATOMS_MISSING_OR_INVALID')
    heavy=int(heavy)
    bounds=((10,'0_10'),(20,'11_20'),(30,'21_30'),(50,'31_50'),(75,'51_75'),(100,'76_100'))
    derived=next((name for upper,name in bounds if heavy<=upper),'above_100')
    if row.get('size_stratum') is not None and row['size_stratum']!=derived:raise ValueError('MANIFEST_SIZE_STRATUM_VS_FORMAL_MOLECULE_MAX_DIFFERS')
    row['size_stratum']=derived
    selected=(audit_ids or {}).get(row['record_id'])
    if selected is not None and (int(row['file_group']),derived)!=selected:raise ValueError('MANIFEST_SIZE_STRATUM_VS_FROZEN_AUDIT_MEMBERSHIP_DIFFERS')
    return row

def compute_one(item,rows):
    import wp5_engine_v3 as engine
    from wp5_parquet_v2 import task_row,registry
    rows=[normalize_source_row(row,engine.AUDIT_IDS) for row in rows]
    state=_WORKER;writer=state['writer'];options=state['options'];lane=state['lane']
    existing=writer.completion(item['molecule_id'])
    if existing:
        result=existing['receipt'];result['archive_path']=str(writer.path);result['lane']=lane;return result
    started_epoch=time.time()
    context={'attempt_id':item['attempt'],'job_id':int(options['job_id']),'task_id':str(item['task_id']),'lane':lane,
             'execution_id':options['session']+':'+str(lane)+':'+str(item['attempt'])+':'+uuid.uuid4().hex,
             'reproduction_package_sha256':options['reproduction_package_sha256'],
             'audit_membership_sha256':options['audit_membership_sha256']}
    def sink(raw):
        ref=writer.put_record(raw)
        if ref['output_retained']:ref['container_path']=str(Path(options['run_root'])/'raw_archive.sqlite')
        return ref
    try:
        with writer.molecule(item['molecule_id']):
            result=engine.compute_molecule(rows,raw_sink=sink,hard_deadline_monotonic=options['hard_monotonic'],context=context)
            if result['status']=='PARTIAL_DEADLINE':raise InterruptedError('Partial whole molecule deadline')
            if len(result['record_results'])!=len(rows):raise ValueError('MANIFEST_ENGINE_RECORD_COUNT_MISMATCH')
            counts={calc:{'success':0,'total':0} for calc in CALCS};retryable=False;entries=registry(options['registry'])
            retained=0;audit_records=0
            for record in result['record_results']:
                tasks=record['tasks'];names=[d.get('task',d.get('name')) for d in tasks]
                if sorted(names)!=sorted(CALCS):raise ValueError('MANIFEST_ENGINE_TWELVE_TASK_OUTCOMES_MISMATCH')
                audit_records+=bool(record.get('audit_selected'))
                for detail in tasks:
                    calc=detail.get('task',detail.get('name'));detail['task']=calc
                    output=task_row(record['record_id'],item['molecule_id'],calc,detail,entries,record['source_row']['total_atoms'])
                    if output['status']!=detail['scope_status']:raise ValueError('MANIFEST_SERIALIZED_STATUS_CHANGED_AFTER_RAW_RETENTION')
                    counts[calc]['total']+=1;counts[calc]['success']+=output['status']=='SUCCESS'
                    ref=detail['raw_ref'];expected=bool(record.get('audit_selected')) or output['status'] in {'CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}
                    if ref.get('execution_id')!=context['execution_id'] or bool(ref.get('output_retained'))!=expected:raise ValueError('MANIFEST_ATTEMPT_RAW_POLICY_DIFFERS')
                    retained+=expected
                    status=detail.get('source_status','');code=str(detail.get('failure_code','')).upper();returncode=detail.get('returncode',detail.get('return_code'))
                    retryable |= status in {'TIMEOUT','NODE_FAILURE','SIGNAL_TERMINATION'} or (isinstance(returncode,int) and returncode<0) or any(k in code for k in ('SIGSEGV','SIGABRT','SIGNAL','NODE_FAIL'))
            receipt={'molecule_id':item['molecule_id'],'records':len(rows),'lane':lane,'archive_path':str(writer.path),
                     'counts':counts,'retryable':bool(retryable),'worker_pid':os.getpid(),'context':context,
                     'molecule_started_epoch':started_epoch,'completed_epoch':time.time(),'retained_raw_calls':retained,
                     'audited_records':audit_records,'requested_outcomes':12*len(rows),'raw_policy':POLICY}
            stage=writer.stage_molecule(item['molecule_id'],{'context':context,'result':result,'population_rows':rows},len(rows),receipt)
            if stage['raw_call_count']!=retained:raise ValueError('MANIFEST_COMPLETED_RECEIPT_RAW_COUNT_DIFFERS')
            receipt['stage_wire_bytes']=stage['uncompressed_wire_bytes'];receipt['stage_compressed_wire_bytes']=stage['compressed_wire_bytes']
        return receipt
    except InterruptedError:
        return {'molecule_id':item['molecule_id'],'partial':True,'lane':lane,'worker_pid':os.getpid(),'context':context}
    except MemoryError:
        return {'molecule_id':item['molecule_id'],'error':'OOM','lane':lane,'worker_pid':os.getpid(),'context':context}
    except Exception:
        error=traceback.format_exc(limit=8)
        if 'MANIFEST_' in error:stop('POPULATION_OR_OUTCOME_COUNT_NOT_CLOSED',{'traceback':error})
        if engine.PRESERVE_ARCHIVE_FAILURE:
            stop('RAW_ARCHIVE_DURABILITY_FAILURE_LOCAL_EVIDENCE_PRESERVED',{'traceback':error,'execution_id':context['execution_id']})
            return {'molecule_id':item['molecule_id'],'error':error,'retryable':False,'lane':lane,'worker_pid':os.getpid(),'context':context,'preserved_local_evidence':True}
        retryable=transient_exception()
        if not retryable:
            try:return stage_pipeline_failure(item,rows,context,error,started_epoch)
            except Exception:error+='\nPIPELINE_FAILURE_RECORDING_ERROR:\n'+traceback.format_exc(limit=5)
        return {'molecule_id':item['molecule_id'],'error':error,'retryable':retryable,'lane':lane,'worker_pid':os.getpid(),'context':context}
def transient_exception():
    import sys,errno
    error=sys.exc_info()[1];seen=set()
    transient={errno.EIO,errno.ETIMEDOUT,errno.ECONNRESET,errno.EHOSTUNREACH,errno.ENETDOWN,errno.ESTALE}
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error,OSError) and error.errno in transient:return True
        error=error.__cause__ or error.__context__
    return False

def stage_pipeline_failure(item,rows,context,error,started_epoch):
    import wp5_engine_v3 as engine
    writer=_WORKER['writer'];options=_WORKER['options'];records=[]
    # Preserve prior committed calls as partial evidence, with no latest-SCI fallback.
    context={**context,'partial_execution_id':context['execution_id'],'execution_id':context['execution_id']+':PIPELINE_FAILURE'}
    counts={calc:{'success':0,'total':len(rows)} for calc in CALCS}
    with writer.molecule(item['molecule_id']):
        for source in rows:
            tasks=[];audited=source['record_id'] in engine.AUDIT_IDS
            for calc in CALCS:
                family='mopac' if calc.startswith('pm7_') else 'xtb'
                provenance={'status':'CALCULATION_FAILED','software_version_id':engine.PACKAGE['software_versions'][family]['software_version_id'],
                    'elapsed_seconds':None,'scf_iterations':None,'converged':None,'input_file_sha256':None,'input_bundle_sha256':None,
                    'input_hash_missing_reason':'PIPELINE_EXCEPTION_NOT_LAUNCHED_OR_EXECUTION_CONTEXT_ABORTED'}
                detail={'task':calc,'record_id':source['record_id'],'molecule_id':item['molecule_id'],
                    'status':'CALCULATION_FAILED','source_status':'PIPELINE_FAILURE','scope_status':'CALCULATION_FAILED',
                    'failure_code':'PIPELINE_EXCEPTION_NO_NUMERIC_LABELS','failure_reason':error,'values':{},
                    'elapsed_seconds':None,'qm_cpu_seconds':None,'provenance':provenance,'raw_audit_selected':audited,
                    'reproduction_package_sha256':engine.PACKAGE_SHA,'precision_by_field':{}}
                body=('PIPELINE_EXCEPTION_NO_QM_OUTPUT\n'+error).encode()
                ref=writer.put_record({'record_id':source['record_id'],'molecule_id':item['molecule_id'],'calc_type':calc,
                    'execution_id':context['execution_id'],'context':context,'source_status':'PIPELINE_FAILURE','scope_status':'CALCULATION_FAILED',
                    'source_payload_sha256':source['record_payload_sha256'],'audit_selected':audited,
                    'software_version_id':provenance['software_version_id'],'input_file_sha256':None,'input_bundle_sha256':None,
                    'input_missing_reason':provenance['input_hash_missing_reason'],'pipeline_exception':error,
                    'files':[{'name':'pipeline_exception.txt','role':'output','data':body,'sha256':hashlib.sha256(body).hexdigest(),'byte_count':len(body)}]})
                ref['container_path']=str(Path(options['run_root'])/'raw_archive.sqlite');detail['raw_ref']=ref
                detail['registry_source_evidence']=engine.concise_source_evidence(detail,[]);tasks.append(detail)
            records.append({'record_id':source['record_id'],'molecule_id':item['molecule_id'],'source_row':source,
                'old_energy_kcal_mol':source.get('energy_raw'),'base_geometry':None,'audit_selected':audited,
                'descriptors':{'status':'PIPELINE_FAILURE','rdkit_graph_desc':None,'rdkit_graph_desc_mask':None,
                               'D_native_3D':None,'issues':['PIPELINE_EXCEPTION_NO_NUMERIC_LABELS']},'tasks':tasks,'pipeline_failure':error})
        result={'molecule_id':item['molecule_id'],'status':'COMPLETE_WITH_RECORDED_PIPELINE_FAILURE','record_results':records,'requested_outcomes':12*len(rows),'raw_records':[]}
        receipt={'molecule_id':item['molecule_id'],'records':len(rows),'lane':_WORKER['lane'],'archive_path':str(writer.path),
            'counts':counts,'retryable':False,'worker_pid':os.getpid(),'context':context,'molecule_started_epoch':started_epoch,
            'completed_epoch':time.time(),'pipeline_failure':error,'retained_raw_calls':12*len(rows),'requested_outcomes':12*len(rows),'raw_policy':POLICY}
        stage=writer.stage_molecule(item['molecule_id'],{'context':context,'result':result,'population_rows':rows},len(rows),receipt)
    receipt['stage_wire_bytes']=stage['uncompressed_wire_bytes'];receipt['stage_compressed_wire_bytes']=stage['compressed_wire_bytes']
    return receipt
def bind_worker_barrier(barrier):
    global _POOL_BARRIER
    _POOL_BARRIER=barrier

def worker_loop(options,lane):
    barrier=_POOL_BARRIER
    import wp5_engine_v3,pickle,zlib
    queue=None;local=None;completed=0;errors=[];error_count=0;pid=os.getpid();cleanup=None
    try:
        initialize_worker(options,lane,barrier)
        queue=Queue(options["queue"],deadline=options["job_exit_monotonic"]-120)
        local=sqlite3.connect("file:"+options["local_index"]+"?mode=ro",uri=True)
        while not stopped() and not (Path(options["run_root"])/"STOP_CLAIMS.json").exists() and time.monotonic()<options["admit_monotonic"]:
            item=queue.claim(options["session"],options["task_id"],options["mode"],
                             options["admit_monotonic"]-time.monotonic(),options["claim_cap"])
            if item is None:break
            queue.db.execute("UPDATE molecules SET lane=?,archive_path=? WHERE molecule_id=? AND owner=?",
                            (lane,str(_WORKER["writer"].path),item["molecule_id"],options["session"]))
            entry=local.execute("SELECT payload FROM rows WHERE molecule_id=?",(item["molecule_id"],)).fetchone()
            if entry is None:
                summary={"molecule_id":item["molecule_id"],"error":"MANIFEST_LOCAL_INDEX_MISSING_MOLECULE"}
                stop("POPULATION_COUNT_NOT_CLOSED",summary)
            else:summary=compute_one(item,pickle.loads(zlib.decompress(entry[0])))
            queue.finish(options["session"],summary)
            if summary.get("error"):
                error_count+=1
                if len(errors)<100:errors.append({"molecule_id":item["molecule_id"],"error":summary["error"]})
                if summary["error"]=="OOM":stop("WORKER_OOM",summary);break
            elif summary.get("partial"):break
            else:
                completed+=1
                if summary.get("pipeline_failure"):
                    error_count+=1
                    if len(errors)<100:errors.append({"molecule_id":item["molecule_id"],"pipeline_failure":summary["pipeline_failure"]})
            if options["claim_cap"] and options["smoke"]:break
    except Exception:
        error_count+=1;errors.append({"initialization_or_queue_error":traceback.format_exc(limit=8)})
        try:barrier.abort()
        except Exception:pass
    finally:
        if _WORKER.get("writer") is not None:_WORKER["writer"].close()
        cleanup=wp5_engine_v3.close_worker()
        if local is not None:local.close()
        if queue is not None:queue.db.close()
    return {"lane":lane,"pid":pid,"completed":completed,"error_count":error_count,"errors":errors,"cleanup":cleanup,
            "queue_metadata_retry_stats":dict(queue.db.retry_stats) if queue is not None else None}

def prepare_index(queue,options):
    import pyarrow as pa,pyarrow.dataset as ds,pickle,zlib
    pa.set_cpu_count(options["workers"]);pa.set_io_thread_count(min(options["workers"],8))
    eligible="m.state='PENDING' AND m.task_id=?" if options["mode"]=="main" else (
        "m.state IN ('PENDING','RETRY_PENDING') AND t.state IN ('CLOSED','DEAD')")
    params=(str(options["task_id"]),) if options["mode"]=="main" else ()
    selected=queue.db.execute("SELECT m.molecule_id,t.record_directory,m.record_count FROM molecules m JOIN tasks t USING(task_id) WHERE "+eligible,params).fetchall()
    dirs={}
    for row in selected:dirs.setdefault(row["record_directory"],{})[row["molecule_id"]]=row["record_count"]
    path=Path(options["local_index"]);path.parent.mkdir(parents=True,exist_ok=True)
    local=sqlite3.connect(path);local.execute("PRAGMA journal_mode=OFF")
    local.execute("CREATE TABLE rows(molecule_id TEXT PRIMARY KEY,payload BLOB NOT NULL)")
    count=0
    for directory,needed in dirs.items():
        dataset=ds.dataset(directory,format="parquet",partitioning="hive")
        table=dataset.to_table(filter=ds.field("molecule_id").isin(list(needed)),use_threads=True)
        grouped={}
        for original in table.to_pylist():
            row=normalize_source_row(original);grouped.setdefault(row["molecule_id"],[]).append(row)
        del table
        if set(grouped)!=set(needed):raise ValueError("MANIFEST_LOCAL_INDEX_MOLECULES_NOT_CLOSED")
        items=[]
        for molecule,rows in grouped.items():
            if len(rows)!=needed[molecule]:raise ValueError("MANIFEST_LOCAL_INDEX_RECORDS_NOT_CLOSED")
            rows.sort(key=lambda r:(r["conformer_id"],r["record_id"]));items.append((molecule,rows))
        def compress(item):
            molecule,rows=item;return molecule,zlib.compress(pickle.dumps(rows,protocol=5),1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=options["workers"]) as pool:
            local.executemany("INSERT INTO rows VALUES(?,?)",pool.map(compress,items))
        count+=len(items);local.commit()
        del grouped,items
    local.close();return {"molecules":count,"bytes":path.stat().st_size,"path":str(path)}

def lossless_json(value):
    if isinstance(value,float) and not math.isfinite(value):
        import struct
        return {"__float64_bits__":struct.pack(">d",value).hex(),"nonfinite_reason":"source metadata nonfinite; original scalar remains in compressed whole-molecule staging"}
    if isinstance(value,dict):return {str(key):lossless_json(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [lossless_json(item) for item in value]
    return value

def common(record,ctx):
    source=record["source_row"]
    return {"record_id":str(record["record_id"]),"molecule_id":str(record["molecule_id"]),
            "file_group":int(source["file_group"]),"attempt_id":ctx["attempt_id"],
            "job_id":ctx["job_id"],"task_id":ctx["task_id"]}

def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def family_row(record,ctx,family,entries):
    import wp5_parquet_v2 as wire
    source=record["source_row"];base=record.get("base_geometry") or {};d=record.get("descriptors") or {}
    tasks={item["task"]:item for item in record["tasks"]};neutral=tasks["pm7_B"]
    new=neutral.get("values",{}).get("heat_of_formation_kcal_mol")
    valid=finite(new) and neutral.get("B_base_success",neutral.get("scope_status")=="SUCCESS")
    if not valid:new=None
    old=record.get("old_energy_kcal_mol")
    delta=new-old if valid and finite(old) else None
    c=common(record,ctx)
    if family=="base_geometry":
        return [{**c,"source_path":source["source_path"],"real_index":source["real_index"],
            "source_payload_sha256":source["record_payload_sha256"],"new_role":source["new_role"],
            "member_routine":source["member_routine"],"conformer_id":int(source["conformer_id"]),
            "atomic_numbers":base.get("z"),"positions_A":base.get("positions_A"),
            "bond_pairs":base.get("bond_pairs_zero_based",base.get("bond_pairs")),
            "bond_order_codes":base.get("bond_order_codes"),
            "old_stored_PM7_HOF_kcal_mol":old,"new_PM7_HOF_kcal_mol":new,"new_PM7_HOF_valid":bool(valid),
            "Q02_delta_HOF_kcal_mol":delta,"geometry_status":"ORIGINAL_PM7_GEOMETRY" if base else ("PIPELINE_FAILURE_GEOMETRY_NOT_EXPORTED" if record.get("pipeline_failure") else "SOURCE_READ_FAILED"),
            "source_native_geometry_sha256":base.get("native_coordinates_sha256"),
            "native_atom_order_sha256":base.get("native_atom_order_sha256"),
            "stored_bond_graph_sha256":base.get("stored_bond_graph_sha256")}]
    if family=="D20":
        values=d.get("rdkit_graph_desc");mask=d.get("rdkit_graph_desc_mask");names=d.get("D20_names")
        issues=list(d.get("issues",[]));shape_ok=values is not None and len(values)==20
        mask_ok=mask is not None and len(mask)==20 and all(isinstance(value,bool) for value in mask)
        names_ok=names is not None and len(names)==20
        complete=shape_ok and mask_ok and names_ok and all(mask) and all(finite(value) for value in values)
        if not shape_ok:
            issues.append("D20_VALUES_MISSING_OR_INVALID_LENGTH")
            if values is not None:issues.append("D20_ORIGINAL_INVALID_SHAPE_VALUES_JSON:"+json.dumps(lossless_json(values),allow_nan=False))
            # Arrow/Parquet fixed_size_list null parents read as size0 in this environment.
            # Keep true per-descriptor NULLs and explicit invalidity, never numeric zeros.
            values=[None]*20;mask=[False]*20
        if not mask_ok:
            issues.append("D20_MASK_MISSING_OR_INVALID_LENGTH_OR_TYPE")
            if mask is not None:issues.append("D20_ORIGINAL_INVALID_MASK_JSON:"+json.dumps(lossless_json(mask),allow_nan=False))
            mask=[False]*20
        if not names_ok:issues.append("D20_DESCRIPTOR_NAMES_MISSING_OR_INVALID_LENGTH")
        if shape_ok and not all(finite(value) for value in values):issues.append("D20_NONFINITE_OR_MISSING_DESCRIPTOR_VALUES")
        status="PIPELINE_FAILURE" if record.get("pipeline_failure") else ("SUCCESS" if complete else "PROPERTY_FAILED")
        return [{**c,"schema_ref":d.get("descriptor_schema_ref"),"descriptor_names":names,
                 "values_float64":values,"valid_mask":mask,"status":status,"issues":issues}]
    if family=="D3":
        d3=d.get("D_native_3D") or {};issues=list(d.get("issues",[]))
        fields={"PMI1":d3.get("PMI1"),"PMI2":d3.get("PMI2"),"PMI3":d3.get("PMI3"),
                "PBF_A":d3.get("PBF_A",d3.get("PBF")),"volume_A3":d3.get("volume_A3"),
                "SASA_total_A2":d3.get("SASA_total_A2"),"SASA_atom_A2":d3.get("SASA_atom_A2")}
        missing=[name for name in ("PMI1","PMI2","PMI3","PBF_A","volume_A3","SASA_total_A2") if not finite(fields[name])]
        for name in missing:issues.append("D3_MISSING_OR_NONFINITE:"+name)
        atomic=fields["SASA_atom_A2"]
        array_ok=atomic is not None and len(atomic)==source["total_atoms"] and all(finite(value) for value in atomic)
        if not array_ok:issues.append("D3_SASA_ATOM_MISSING_NONFINITE_OR_N_MISMATCH")
        complete=not missing and array_ok
        status="PIPELINE_FAILURE" if record.get("pipeline_failure") else ("SUCCESS" if complete else "PROPERTY_FAILED")
        return [{**c,"schema_ref":d.get("descriptor_schema_ref"),**fields,"status":status,"issues":issues}]
    if family=="QC":
        statuses=[]
        for calc,detail in tasks.items():
            row=wire.task_row(record["record_id"],record["molecule_id"],calc,detail,entries,source["total_atoms"])
            statuses.append({"calc_type":calc,"status":row["status"],"source_status":row["source_status"],
                "failure_code":row["failure_code"],"elapsed_seconds":row["elapsed_seconds"],"predicted_seconds":None})
        def spin(calc):
            values=tasks[calc].get("values",{});value=values.get("spin_S2")
            return value-.75 if finite(value) else None
        return [{**c,"Q01_gradient_norm_kcal_mol_A":neutral.get("Q01_gradient_norm_kcal_mol_A"),
            "Q02_delta_HOF_kcal_mol":delta,"cation_S2_minus_0p75":spin("pm7_cation"),"anion_S2_minus_0p75":spin("pm7_anion"),
            "population_QC_json":json.dumps(lossless_json(source),ensure_ascii=False,allow_nan=False),
            "task_statuses":statuses,"record_status":"PIPELINE_FAILURE_12_UNAVAILABLE_OUTCOMES" if record.get("pipeline_failure") else ("ALL_TASKS_SUCCESS" if all(r["status"]=="SUCCESS" for r in statuses) else "RECORDED_TASK_FAILURES")}]
    result=[]
    for calc,detail in tasks.items():
        if wire.FAMILIES[calc]!=family:continue
        row=wire.task_row(record["record_id"],record["molecule_id"],calc,detail,entries,source["total_atoms"])
        row.update(attempt_id=ctx["attempt_id"],job_id=ctx["job_id"],task_id=ctx["task_id"],lane=ctx["lane"])
        result.append(row)
    return result

def schema_for(family):
    import wp5_parquet_v2 as wire
    return {"base_geometry":wire.BASE_SCHEMA,"D20":wire.D20_SCHEMA,"D3":wire.D3_SCHEMA,"QC":wire.QC_SCHEMA}.get(family,wire.SCHEMA)

def staged_rows(paths,dictionaries,registry,family,group):
    from wp5_archive_v5 import ArchiveReader
    from wp5_parquet_v2 import registry as read_registry
    entries=read_registry(registry)
    for path in paths:
        reader=ArchiveReader(path,dictionaries)
        try:
            for item in reader.iter_staged():
                payload=item["payload"];ctx=payload["context"]
                for record in payload["result"]["record_results"]:
                    if int(record["source_row"]["file_group"])==group:
                        yield from family_row(record,ctx,family,entries)
        finally:reader.close()

def export_family(arg):
    paths,options,family,group=arg
    import pyarrow as pa,pyarrow.parquet as pq
    from wp5_parquet_v2 import exact
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    schema=schema_for(family)
    target=Path(options["run_root"])/"parquet"/("group_"+str(group))/(family+".parquet")
    already=target.exists()
    target.parent.mkdir(parents=True,exist_ok=True);pending=target.with_name(target.name+".pending")
    writer=None if already else pq.ParquetWriter(pending,schema,compression="zstd",compression_level=3)
    count=0;batch=[]
    try:
        for row in staged_rows(paths,options["dictionaries"],options["registry"],family,group):
            batch.append(row)
            if len(batch)>=128:
                table=pa.Table.from_pylist(batch,schema=schema)
                if writer is not None:writer.write_table(table,row_group_size=32768)
                count+=len(batch);batch=[]
        if batch:
            if writer is not None:writer.write_table(pa.Table.from_pylist(batch,schema=schema))
            count+=len(batch)
    finally:
        if writer is not None:writer.close()
    # Rebuild the exact typed rows from verified compressed staging and compare
    # every scalar/list/float64 bit against the file before permanent publication.
    expected=iter(staged_rows(paths,options["dictionaries"],options["registry"],family,group));verified=0
    for table in pq.ParquetFile(target if already else pending).iter_batches(batch_size=128):
        actual=table.to_pylist();reference=[next(expected) for _ in actual]
        reference=pa.Table.from_pylist(reference,schema=schema).to_pylist()
        for left,right in zip(reference,actual):exact(left,right)
        verified+=len(actual)
    try:next(expected);raise ValueError("Export dropped staged rows")
    except StopIteration:pass
    if verified!=count:raise ValueError("Export row count mismatch")
    if not already:
        with pending.open("rb") as f:os.fsync(f.fileno())
        os.replace(pending,target)
    return {"family":family,"file_group":group,"path":str(target),"rows":count,"bytes":target.stat().st_size,
            "sha256":digest(target),"float64_exact_readback":True}


def canonical_index(options,references,archive_path,queue):
    import pyarrow as pa,pyarrow.parquet as pq
    import wp5_parquet_v2 as wire
    target=Path(options["run_root"])/"canonical_record_attempts.parquet"
    schema=pa.schema([pa.field("record_id",pa.string()),pa.field("molecule_id",pa.string()),
        pa.field("calc_type",pa.string()),pa.field("file_group",pa.int8()),
        pa.field("attempt_id",pa.int8()),pa.field("job_id",pa.int64()),
        pa.field("task_id",pa.string()),pa.field("lane",pa.int16()),
        pa.field("archive_path",pa.string()),pa.field("raw_execution_id",pa.string()),pa.field("family_parquet_path",pa.string())])
    family_map={(ref["file_group"],ref["family"]):ref["path"] for ref in references}
    receipts={row["molecule_id"]:json.loads(row["receipt_json"]) for row in queue.db.execute(
        "SELECT molecule_id,receipt_json FROM molecules WHERE owner=? AND receipt_json IS NOT NULL",(options["session"],))}
    def rows():
        for ref in references:
            if ref["family"]!="base_geometry":continue
            for batch in pq.ParquetFile(ref["path"]).iter_batches(batch_size=1024):
                for row in batch.to_pylist():
                    receipt=receipts.get(row["molecule_id"])
                    if receipt is None:raise ValueError("MANIFEST_CANONICAL_RECEIPT_MISSING")
                    for calc in CALCS:
                        yield {key:row[key] for key in ("record_id","molecule_id","file_group","attempt_id","job_id","task_id")} | {
                            "calc_type":calc,"lane":receipt["lane"],"archive_path":str(archive_path),"raw_execution_id":receipt["context"]["execution_id"],
                            "family_parquet_path":family_map[(row["file_group"],wire.FAMILIES[calc])]}
    existing=target.exists();pending=target.with_name(target.name+".pending")
    count=0;buffer=[];writer=None if existing else pq.ParquetWriter(pending,schema,compression="zstd")
    try:
        for row in rows():
            buffer.append(row);count+=1
            if len(buffer)>=8192:
                if writer is not None:writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
                buffer=[]
        if buffer and writer is not None:writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
    finally:
        if writer is not None:writer.close()
    expected=iter(rows());verified=0
    for batch in pq.ParquetFile(target if existing else pending).iter_batches(batch_size=8192):
        for actual in batch.to_pylist():
            if actual!=next(expected):raise ValueError("MANIFEST_CANONICAL_INDEX_READBACK_DIFFERS")
            verified+=1
    try:next(expected);raise ValueError("MANIFEST_CANONICAL_INDEX_DROPPED_ROWS")
    except StopIteration:pass
    if count!=verified:raise ValueError("MANIFEST_CANONICAL_INDEX_COUNT_DIFFERS")
    if not existing:
        with pending.open("rb") as stream:os.fsync(stream.fileno())
        os.replace(pending,target)
    return {"family":"canonical_record_attempts","path":str(target),"rows":count,
            "bytes":target.stat().st_size,"sha256":digest(target),"scope":"this immutable attempt; use queue latest owner for final population"}

def verify_retained_scope(references,archive_path,dictionaries):
    """SCI closes 12N outcomes; only failed/audited raw joins the SAME attempt."""
    # This scan runs only in the bounded Slurm exporter, never on login.
    import pyarrow.parquet as pq
    from wp5_archive_v5 import ArchiveReader
    reader=ArchiveReader(archive_path,dictionaries);expected_retained=0;cases=0;seen=set();audit_calls={}
    try:
        receipts={r['molecule_id']:json.loads(r['receipt_json']) for r in reader.db.execute('SELECT molecule_id,receipt_json FROM completion_receipts')}
        for ref in references:
            if ref['family'] in {'base_geometry','D20','D3','QC','canonical_record_attempts'}:continue
            for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=1024):
                for row in batch.to_pylist():
                    rid,calc,mid=row['record_id'],row['calc_type'],row['molecule_id'];key=(rid,calc)
                    if key in seen:raise ValueError('MANIFEST_DUPLICATE_SCI_RECORD_TASK')
                    seen.add(key);cases+=1
                    receipt=receipts.get(mid)
                    if receipt is None:raise ValueError('MANIFEST_SCI_RECEIPT_FOR_RAW_JOIN_MISSING')
                    execution=receipt['context']['execution_id']
                    retained=bool(row['raw_audit_selected']) or row['status'] in {'CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}
                    if row['status'] not in {'SUCCESS','CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}:raise ValueError('MANIFEST_NONCANONICAL_OUTCOME')
                    if row['raw_audit_selected']:audit_calls.setdefault(rid,set()).add(calc)
                    actual=reader.db.execute('SELECT scope_status FROM records WHERE record_id=? AND calc_type=? AND execution_id=?',(rid,calc,execution)).fetchone()
                    locator=json.loads(row['raw_output_locator_json']) if row['raw_output_locator_json'] else None
                    if not retained:
                        if actual is not None or locator is not None:raise ValueError('MANIFEST_ORDINARY_SUCCESS_SHARED_RAW_INSERT')
                        continue
                    expected_retained+=1
                    if actual is None or locator is None or locator.get('execution_id')!=execution or locator.get('container_path')!=str(archive_path):raise ValueError('MANIFEST_RETAINED_RAW_ATTEMPT_JOIN_MISSING')
                    raw=reader.get(rid,calc,execution);meta=raw['metadata']
                    if raw['scope_status']!=row['status'] or raw['source_status']!=row['source_status'] or raw['raw_sha256']!=locator.get('raw_sha256'):raise ValueError('MANIFEST_RETAINED_RAW_STATUS_OR_SHA_DIFFERS')
                    for name in ('software_version_id','input_file_sha256','input_bundle_sha256','scf_iterations','converged'):
                        if meta.get(name)!=row[name]:raise ValueError('MANIFEST_RETAINED_RAW_TRACE_DIFFERS:'+name)
                    if raw['input_files'] or raw['input_bodies_saved']:raise ValueError('MANIFEST_FORBIDDEN_INPUT_BODY_PRESENT')
                    if row['status']=='SUCCESS' and not raw['output_files']:raise ValueError('MANIFEST_SUCCESS_AUDIT_OUTPUT_EMPTY')
        if any(names!=set(CALCS) for names in audit_calls.values()):raise ValueError('MANIFEST_SELECTED_RECORD_TWELVE_OUTPUTS_NOT_CLOSED')
        complete=reader.db.execute('SELECT coalesce(sum(raw_calls),0) FROM completion_receipts').fetchone()[0]
        if complete!=expected_retained:raise ValueError('MANIFEST_COMPLETED_RECEIPT_RETAINED_COUNT_DIFFERS')
        all_raw=reader.db.execute('SELECT count(*) FROM records').fetchone()[0]
        return {'scientific_task_outcomes':cases,'completed_SCI_retained_raw_calls':expected_retained,
                'partial_attempt_retained_raw_calls':all_raw-expected_retained,'audited_records':len(audit_calls),
                'ordinary_success_raw_inserted':False,'input_bodies_saved':False,'same_execution_join_verified':True}
    finally:reader.close()

def finalize_run(options):
    from wp5_archive_v5 import ArchiveReader,ArchiveWriter,consolidate_archives
    import wp5_parquet_v2 as wire
    root=Path(options["run_root"]);queue=Queue(options["queue"],deadline=options.get("sql_deadline_monotonic",options["job_exit_monotonic"]-120))
    paths=sorted((root/"temporary_lanes").glob("lane_*.sqlite"))
    summary_path=root/"staging_summary.json";reference_path=root/"family_exports.json"
    try:
        groups=set();records=0;molecules=0;compressed=0;uncompressed=0
        for path in paths:
            reader=ArchiveReader(path,options["dictionaries"])
            try:
                for item in reader.iter_staged():
                    molecules+=1;records+=item["record_count"]
                    compressed+=item["compressed_wire_bytes"];uncompressed+=item["uncompressed_wire_bytes"]
                    for row in item["payload"]["population_rows"]:groups.add(int(row["file_group"]))
                    durable=reader.completion(item["molecule_id"])["receipt"]
                    current=queue.db.execute("SELECT * FROM molecules WHERE molecule_id=?",(item["molecule_id"],)).fetchone()
                    if current is None:raise ValueError("MANIFEST_DURABLE_MOLECULE_NOT_IN_QUEUE")
                    if current["receipt_json"] is None and current["attempt"]==durable["context"]["attempt_id"]:
                        queue.db.execute("UPDATE molecules SET owner=?,state='RUNNING' WHERE molecule_id=?",
                                         (options["session"],item["molecule_id"]))
                        queue.finish(options["session"],durable)
            finally:reader.close()
        if summary_path.exists():summary=json.loads(summary_path.read_text())
        else:
            summary={"records":records,"molecules":molecules,"compressed_wire_bytes":compressed,
                     "uncompressed_wire_bytes":uncompressed,"groups":sorted(groups)}
            atomic(summary_path,summary)
        # Even a zero-SCI normal deadline preserves committed partial raw evidence.
        if reference_path.exists():
            references=json.loads(reference_path.read_text())["references"]
            for ref in references:
                if Path(ref["path"]).stat().st_size!=ref["bytes"] or digest(ref["path"])!=ref["sha256"]:
                    raise ValueError("MANIFEST_PERMANENT_EXPORT_SHA_DIFFERS")
        else:
            families=["base_geometry","D20","D3","QC"]+sorted(set(wire.FAMILIES.values()))
            arguments=[([str(path) for path in paths],options,family,group)
                       for group in summary["groups"] for family in families]
            context=multiprocessing.get_context("spawn")
            with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context) as pool:
                references=list(pool.map(export_family,arguments,chunksize=1))
            if sum(ref["rows"] for ref in references if ref["family"]=="base_geometry")!=summary["records"]:
                raise ValueError("MANIFEST_BASE_EXPORT_COUNT_MISMATCH")
            if sum(ref["rows"] for ref in references if ref["family"] not in {"base_geometry","D20","D3","QC"})!=12*summary["records"]:
                raise ValueError("MANIFEST_QM_EXPORT_COUNT_MISMATCH")
            atomic(reference_path,{"references":references,"verification":"every typed scalar/list/F64 bit reconstructed from SHA-verified staging"})
        final_path=root/"raw_archive.sqlite"
        old_pending=final_path.with_name(final_path.name+".pending")
        if old_pending.exists() and not final_path.exists():
            # Source raw/family files are immutable. Only this run's unpublished
            # temporary consolidation is retained under a failure-evidence name.
            stored_run=json.loads((root/"run.json").read_text())
            old_job=str(stored_run["options"]["job_id"])
            state_report=run_sacct(["-X","-n","-P","-j",old_job,"--format=JobID,User,State"],timeout=60)
            terminal={"COMPLETED","FAILED","CANCELLED","NODE_FAIL","OUT_OF_MEMORY","TIMEOUT","BOOT_FAIL","DEADLINE","PREEMPTED"}
            observed=[parts for line in state_report.stdout.splitlines() if len(parts:=[value.strip() for value in line.split("|")])>=3 and parts[0]==old_job and parts[1]=="zixiao" and parts[2]]
            if state_report.returncode!=0 or not observed or observed[0][2].split()[0] not in terminal:
                raise RuntimeError("Previous consolidation job is not confirmed terminal; preserve .pending; "+state_report.evidence_path)
            failed=old_pending.with_name("failed_consolidation_"+digest(old_pending)+".sqlite")
            if failed.exists():raise FileExistsError("Failed consolidation evidence already exists")
            os.rename(old_pending,failed)
            atomic(root/("failed_consolidation_"+str(int(time.time()))+".json"),
                {"original_temporary_path":str(old_pending),"evidence_path":str(failed),"bytes":failed.stat().st_size,
                 "sha256":digest(failed),"old_job_id":old_job,"sacct_evidence":state_report.evidence,"sacct_evidence_path":state_report.evidence_path,
                 "reason":"Resume consolidation with fixed tuple comparator; no permanent family/archive overwritten"})
        canonical=canonical_index(options,references,final_path,queue)
        for path in paths:
            writer=ArchiveWriter(path,options["dictionaries"],options["protocol"],policy=options["policy"],resume=True,reproduction_package=options["reproduction_package"],audit_membership=options["audit_membership"])
            try:
                if any(True for _ in writer.iter_staged()):
                    writer.retire_staged_after_verified_parquet(references+[canonical],vacuum=True,preverified=True)
            finally:writer.close()
        if final_path.exists():
            reader=ArchiveReader(final_path,options["dictionaries"])
            try:
                raw_count=0
                for record_id,calc,execution in reader.db.execute("SELECT record_id,calc_type,execution_id FROM records"):
                    reader.get(record_id,calc,execution);raw_count+=1
                molecule_count=reader.db.execute("SELECT count(*) FROM completion_receipts").fetchone()[0]
                if reader.db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                    raise ValueError("MANIFEST_FINAL_ARCHIVE_INTEGRITY_FAILED")
            finally:reader.close()
            archive={"path":str(final_path),"bytes":final_path.stat().st_size,"sha256":digest(final_path),
                     "raw_records":raw_count,"molecules":molecule_count,"resumed_verified_permanent":True,
                     "raw_member_roundtrip_checked":True}
        else:
            archive=consolidate_archives(paths,final_path,options["dictionaries"],options["protocol"],
                                        policy=options["policy"],verify_raw=True,reproduction_package=options["reproduction_package"],audit_membership=options["audit_membership"])
        if archive["molecules"]!=summary["molecules"]:raise ValueError("MANIFEST_ARCHIVE_COMPLETE_MOLECULES_MISMATCH")
        raw_scope=verify_retained_scope(references,final_path,options['dictionaries'])
        if raw_scope['scientific_task_outcomes']!=12*summary['records']:raise ValueError('MANIFEST_SCI_TWELVE_TASK_OUTCOMES_NOT_CLOSED')
        archive.update(raw_scope)
        queue.publish_export(options["session"],references+[canonical],archive)
        for path in paths:
            if path.parent!=root/"temporary_lanes":raise ValueError("Temporary deletion scope differs")
            path.unlink()
            for suffix in ("-journal","-wal","-shm"):path.with_name(path.name+suffix).unlink(missing_ok=True)
        result={**summary,"families":references,"archive":archive,"canonical":canonical,
                "queue_metadata_retry_stats":dict(queue.db.retry_stats)}
        atomic(root/"export_completion.json",result);return result
    finally:queue.db.close()

def finalizer_child(options,pipe):
    try:pipe.send({"result":finalize_run(options)})
    except BaseException:pipe.send({"error":traceback.format_exc(limit=12)})
    finally:pipe.close()

def terminate_owned_tree(pid):
    children={pid}
    for _ in range(5):
        for directory in Path("/proc").iterdir():
            if not directory.name.isdigit():continue
            try:
                text=(directory/"status").read_text()
                parent=int(next(line.split()[1] for line in text.splitlines() if line.startswith("PPid:")))
                if parent in children:children.add(int(directory.name))
            except (OSError,StopIteration,ValueError):pass
    for target in sorted(children,reverse=True):
        try:os.kill(target,signal.SIGTERM)
        except ProcessLookupError:pass

def bounded_finalize(options,deadline):
    options={**options,"sql_deadline_monotonic":deadline}
    context=multiprocessing.get_context("spawn");receive,send=context.Pipe(duplex=False)
    process=context.Process(target=finalizer_child,args=(options,send));process.start();send.close()
    while process.is_alive() and not receive.poll(5):
        if time.monotonic()>=deadline:
            terminate_owned_tree(process.pid);process.join(timeout=10)
            if process.is_alive():process.kill();process.join(timeout=5)
            receive.close();return {"error":"NORMAL_FINALIZATION_DEADLINE_PRESERVED_DURABLE_STAGING"}
    result=receive.recv() if receive.poll() else {"error":"FINALIZATION_PROCESS_EXITED_WITHOUT_RESULT"}
    process.join(timeout=10);receive.close();return result

def repair_unexported(queue,options,deadline):
    roots={}
    for row in queue.db.execute("SELECT DISTINCT owner,archive_path FROM molecules m JOIN tasks t USING(task_id) "
                               "WHERE receipt_json IS NOT NULL AND export_json IS NULL AND t.state IN ('CLOSED','DEAD')"):
        if not row["archive_path"]:continue
        root=Path(row["archive_path"]).parent.parent
        if (root/"run.json").exists():roots[str(root)]=root
    results=[]
    for root in roots.values():
        if time.monotonic()>=deadline:break
        if not queue.claim_export_repair(root,options["session"],options["job_id"]):continue
        previous=json.loads((root/"run.json").read_text())["options"]
        for field in ("dictionaries","protocol","registry"):
            if digest(previous[field])!=digest(options[field]):raise ValueError("Frozen export-repair dependencies differ")
        outcome=bounded_finalize(previous,deadline);results.append({"run_root":str(root),**outcome})
        queue.finish_export_repair(root,options["session"],outcome.get("error"))
        if outcome.get("error") and "MANIFEST_" in outcome["error"]:
            stop("POPULATION_OR_OUTPUT_COUNT_NOT_CLOSED",outcome)
    return results


def resource_sample(scratch=None):
    # Only our process subtree; inaccessible RSS/PSS is None, never zero.
    import multiprocessing
    pids=[os.getpid()]+[child.pid for child in multiprocessing.active_children()]
    found=set(pids)
    for _ in range(3):
        for directory in Path("/proc").iterdir():
            if not directory.name.isdigit() or int(directory.name) in found:continue
            try:
                status=(directory/"status").read_text()
                parent=int(next(line.split()[1] for line in status.splitlines() if line.startswith("PPid:")))
                if parent in found:found.add(int(directory.name))
            except (OSError,StopIteration,ValueError):pass
    rss=[];pss=[]
    for pid in found:
        try:
            data=Path("/proc",str(pid),"smaps_rollup").read_text()
            r=next(int(line.split()[1])*1024 for line in data.splitlines() if line.startswith("Rss:"))
            p=next(int(line.split()[1])*1024 for line in data.splitlines() if line.startswith("Pss:"));rss.append(r);pss.append(p)
        except (OSError,StopIteration,ValueError):pass
    scratch_bytes=None
    if scratch is not None:
        try:scratch_bytes=sum(path.stat().st_size for path in Path(scratch).rglob("*") if path.is_file())
        except OSError:pass
    return {"pids":sorted(found),"RSS_bytes":sum(rss) if rss else None,"PSS_bytes":sum(pss) if pss else None,"local_scratch_bytes":scratch_bytes}

def validate_production_contract(args):
    required={'status','software_version_id','elapsed_seconds','scf_iterations','converged','input_file_sha256'}
    if args.production_contract is None or args.audit_membership is None or args.reproduction_package is None:raise ValueError('PRODUCTION_CONTRACT_AUDIT_AND_REPRODUCTION_PACKAGE_REQUIRED')
    path=args.production_contract;contract=json.loads(path.read_text())
    if contract.get('schema')!='WP5_PRODUCTION_CONTRACT_V1' or contract.get('status')!='PRODUCTION_CONTRACT_FROZEN' or contract.get('policy')!=POLICY:raise ValueError('FROZEN_NEW_POLICY_CONTRACT_REQUIRED')
    if set(contract.get('trace_fields',[]))!=required or contract.get('final200_required') is not True:raise ValueError('CONTRACT_TRACE_OR_FINAL200_RULE_DIFFERS')
    if contract.get('seeds')!={'geometry_perturbation':20261010,'audit':20261010,'reproduction50':20261011,'final200':20261011}:raise ValueError('CONTRACT_SEEDS_DIFFER')
    arguments={'audit_manifest':args.audit_membership,'reproduction_package':args.reproduction_package,'protocol':args.protocol,
               'node_authority':args.node_authority,'node_scope_plan':args.node_scope_plan}
    protocol=json.loads(args.protocol.read_text());arguments['registry']=args.registry or Path(protocol['registry']['path'])
    for name in ('audit_manifest','reproduction_package','protocol','registry','node_authority','node_scope_plan','authority'):
        ref=contract[name]
        if digest(ref['path'])!=ref['sha256']:raise ValueError('CONTRACT_BOUND_REFERENCE_CHANGED:'+name)
        if name in arguments and (Path(arguments[name]).resolve()!=Path(ref['path']).resolve() or digest(arguments[name])!=ref['sha256']):raise ValueError('CONTRACT_CLI_REFERENCE_MISMATCH:'+name)
    override=json.loads(Path(contract['authority']['path']).read_text())
    if override.get('status')!='USER_AUTHORIZED':raise ValueError('RAW_RETENTION_USER_AUTHORITY_MISSING')
    inventory=contract['sources'];bound={str(Path(r['path']).resolve()):r['sha256'] for r in inventory}
    if len(bound)!=len(inventory):raise ValueError('CONTRACT_DUPLICATE_SOURCE_BINDING')
    for ref in inventory:
        if digest(ref['path'])!=ref['sha256']:raise ValueError('CONTRACT_EXECUTING_SOURCE_DRIFT:'+ref['path'])
    for name in ('wp5_runner_v11.py','wp5_engine_v3.py','wp5_parser_v2.py','wp5_parquet_v2.py','wp5_archive_v5.py','wp5_archive_v4.py','wp5_accounting_v2.py','wp5_scf_metadata_v2.py','wp5_registry_coverage_v2.py'):
        if str(Path(__file__).with_name(name).resolve()) not in bound:raise ValueError('CONTRACT_EXECUTING_SOURCE_NOT_BOUND:'+name)
    package=json.loads(args.reproduction_package.read_text());audit=json.loads(args.audit_membership.read_text())
    if package.get('schema')!='WP5_REPRODUCTION_PACKAGE_V1' or package.get('status')!='REPRODUCTION_PACKAGE_CLOSED':raise ValueError('CONTRACT_PACKAGE_NOT_CLOSED')
    if audit.get('schema')!='WP5_STRATIFIED_RECORD_AUDIT_V1' or audit.get('status')!='AUDIT_MEMBERSHIP_CLOSED':raise ValueError('CONTRACT_RECORD_AUDIT_NOT_CLOSED')
    if package['audit_membership']['sha256']!=contract['audit_manifest']['sha256']:raise ValueError('PACKAGE_AUDIT_BINDING_DIFFERS')
    for family,version in contract['software_versions'].items():
        actual=package['software_versions'][family]
        if version['version']!=actual['version'] or version['software_version_id']!=actual['software_version_id'] or version['binary_sha256']!=actual['sha256']:raise ValueError('CONTRACT_PACKAGE_SOFTWARE_DIFFERS:'+family)
    return contract

def check_runtime_metadata():
    """No QM/LMDB: formal metadata and pipeline-failure Parquet roundtrip."""
    import pyarrow as pa,pyarrow.parquet as pq,tempfile,shutil,stat
    import wp5_parquet_v2 as wire
    for heavy,expected in ((0,'0_10'),(10,'0_10'),(11,'11_20'),(20,'11_20'),(21,'21_30'),(30,'21_30'),(31,'31_50'),(50,'31_50'),(51,'51_75'),(75,'51_75'),(76,'76_100'),(100,'76_100'),(101,'above_100')):
        source={'record_id':'fixture','file_group':1,'molecule_max_heavy_atoms':heavy,'record_payload_sha256':'0'*64}
        normalized=normalize_source_row(source)
        assert normalized['size_stratum']==expected and 'size_stratum' not in source
        assert normalized['record_payload_sha256']==source['record_payload_sha256']
        assert normalize_source_row(normalized,{source['record_id']:(1,expected)})==normalized
    for source,audit in (({'record_id':'fixture','file_group':1,'molecule_max_heavy_atoms':20,'size_stratum':'0_10'},None),({'record_id':'fixture','file_group':1,'molecule_max_heavy_atoms':20},{'fixture':(1,'0_10')})):
        try:normalize_source_row(source,audit);raise AssertionError('Invalid stratum accepted')
        except ValueError as error:assert 'STRATUM' in str(error)
    source={'record_id':'fixture_record','molecule_id':'fixture_molecule','file_group':1,'total_atoms':2,
            'source_path':'FIXTURE_NO_SOURCE_OPEN','real_index':0,'record_payload_sha256':'0'*64,'new_role':'train',
            'member_routine':True,'conformer_id':0,'molecule_max_heavy_atoms':20}
    record={'record_id':source['record_id'],'molecule_id':source['molecule_id'],'source_row':normalize_source_row(source),
            'old_energy_kcal_mol':None,'base_geometry':None,'descriptors':{'status':'PIPELINE_FAILURE','rdkit_graph_desc':None,
            'rdkit_graph_desc_mask':None,'D_native_3D':None,'issues':['FIXTURE_PIPELINE_FAILURE']},
            'pipeline_failure':'FIXTURE_PIPELINE_FAILURE','tasks':[{'task':calc,'status':'CALCULATION_FAILED','scope_status':'CALCULATION_FAILED',
            'source_status':'PIPELINE_FAILURE','values':{},'failure_code':'FIXTURE','elapsed_seconds':None,
            'provenance':{'software_version_id':1 if calc.startswith('pm7_') else 2,'scf_iterations':None,'converged':None,
             'input_file_sha256':None,'input_bundle_sha256':None}} for calc in CALCS]}
    context={'attempt_id':0,'job_id':0,'task_id':'fixture','lane':0,'execution_id':'fixture:metadata-only'}
    parent=ROOT/'tests';parent.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='metadata_null_fixture_'+str(os.getuid())+'_',dir=parent));counts={}
    try:
        for family in ['base_geometry','D20','D3','QC']+sorted(set(wire.FAMILIES.values())):
            rows=family_row(record,context,family,[]);schema=schema_for(family);target=folder/(family+'.parquet')
            wire.write_family_rows(rows,target,schema)
            actual=pq.read_table(target).to_pylist();expected=pa.Table.from_pylist(rows,schema=schema).to_pylist()
            for left,right in zip(expected,actual):wire.exact(left,right)
            assert len(actual)==len(rows);counts[family]=len(actual)
            if family=='D20':assert actual[0]['values_float64']==[None]*20 and actual[0]['valid_mask']==[False]*20 and actual[0]['status']=='PIPELINE_FAILURE'
        assert sum(counts[name] for name in set(wire.FAMILIES.values()))==12
        print(json.dumps({'status':'FORMAL_STRATUM_AUDIT_AND_NULL20_PARQUET_FIXTURE_PASS','normalization_boundary_cases':13,
             'source_row_modified':False,'audited_record_group_size_checked':True,'pipeline_failure_scientific_slots':12,
             'D20_missing_values':[None]*20,'D20_valid_mask':[False]*20,'family_readback_rows':counts,'QM_started':False,'LMDB_opened':False}))
    finally:
        if folder.resolve().parent!=parent.resolve() or not folder.name.startswith('metadata_null_fixture_'+str(os.getuid())+'_'):raise ValueError('Fixture cleanup scope differs')
        for item in [folder,*folder.rglob('*')]:
            info=item.lstat()
            if info.st_uid!=os.getuid() or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):raise ValueError('Fixture cleanup owner/type differs')
        shutil.rmtree(folder)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",type=Path,default=ROOT/"packing/node_assignment_v3/tasks.json")
    parser.add_argument("--node-authority",type=Path,help="User-approved WP5 node substitution receipt")
    parser.add_argument("--node-scope-plan",type=Path,default=ROOT/"packing/node_assignment_v3/tasks.json")
    parser.add_argument("--assignments",type=Path,default=ROOT/"packing/molecule_assignments.parquet")
    parser.add_argument("--queue",type=Path,default=ROOT/"queue/pending.sqlite")
    parser.add_argument("--task-id",default="0");parser.add_argument("--mode",choices=("main","cleanup"),default="main")
    parser.add_argument("--dictionaries",type=Path);parser.add_argument("--policy",choices=(POLICY,),default=POLICY)
    parser.add_argument("--production-contract",type=Path);parser.add_argument("--audit-membership",type=Path);parser.add_argument("--reproduction-package",type=Path)
    parser.add_argument("--protocol",type=Path,default=ROOT/"configs/protocol.json")
    parser.add_argument("--registry",type=Path)
    parser.add_argument("--baseline",type=Path,help="JSON success_rates mapping exact 12 calc types to closed pilot required-scope success rates")
    parser.add_argument("--source-plan",type=Path,default=Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/plan.json"))
    parser.add_argument("--run-root",type=Path);parser.add_argument("--scratch-root",type=Path,default=Path("/tmp"))
    parser.add_argument("--workers",type=int,default=24);parser.add_argument("--hours",type=float,default=48)
    parser.add_argument("--admit-hours",type=float,default=46);parser.add_argument("--export-reserve-hours",type=float,default=2)
    parser.add_argument("--claim-cap",type=int,default=0);parser.add_argument("--smoke",action="store_true")
    parser.add_argument("--init-only",action="store_true");parser.add_argument("--repair-only",action="store_true");parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if args.check:
        import ast;ast.parse(Path(__file__).read_text())
        import wp5_archive_v5 as archive
        assert archive.retention({'scope_status':'SUCCESS','audit_selected':False})[0] is False
        assert archive.retention({'scope_status':'SUCCESS','audit_selected':True})[0] is True
        assert archive.retention({'scope_status':'TIMEOUT','audit_selected':False})[0] is True
        check_runtime_metadata();return
    job=os.environ.get("SLURM_JOB_ID")
    node=socket.gethostname().split(".")[0]
    if not job or node not in NODES or args.workers!=24 or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<24:
        raise ValueError("WP5_REQUIRES_24CPU_SLURM_ON_AUTHORIZED_12_13_14_17_18_19")
    if args.node_authority is None or not args.node_authority.is_file():raise ValueError("ACTUAL_NODE_AUTHORITY_RECEIPT_REQUIRED")
    if digest(args.node_authority)!=NODE_AUTHORITY_SHA or digest(args.node_scope_plan)!=NODE_SCOPE_PLAN_SHA:raise ValueError("FROZEN_NODE_AUTHORITY_OR_PLAN_SHA_CHANGED")
    authority=json.loads(args.node_authority.read_text())
    if authority.get("schema")!="WP5_NODE_REPLACEMENT_USER_APPROVAL_V1" or authority.get("status")!="USER_APPROVED" or authority.get("scientific_configuration_changed") is not False or set(authority.get("authorized_node_slots",{}))!=set(NODES):raise ValueError("NODE_AUTHORITY_CONTENT_MISMATCH")
    scope_plan=json.loads(args.node_scope_plan.read_text())
    if {task['node'] for task in scope_plan['tasks']}!=set(NODES):raise ValueError("NODE_ASSIGNMENT_V3_SCOPE_MISMATCH")
    node_scope={"actual_node":node,"original_designed_node":{"compute-0-12":"compute-0-15","compute-0-13":"compute-0-16"}.get(node,node),
                "authority_path":str(args.node_authority),"authority_sha256":digest(args.node_authority),
                "plan_path":str(args.node_scope_plan),"plan_sha256":digest(args.node_scope_plan),"science_recipe_unchanged":True}
    contract=validate_production_contract(args)
    if not args.queue.resolve().is_relative_to(ROOT):raise ValueError("Queue must be in the new WP5 root")
    queue=Queue(args.queue,deadline=time.monotonic()+args.hours*3600-120,baseline_path=args.baseline)
    queue.seed(args.plan,args.assignments,args.smoke)
    if args.init_only:
        print(json.dumps({"queue":str(args.queue),**queue.summary()}));queue.db.close();return
    if not args.dictionaries:raise ValueError("--dictionaries from passed G3 required")
    if args.baseline:
        baseline=json.loads(args.baseline.read_text())["success_rates"]
        if set(baseline)!=set(CALCS) or any(not isinstance(value,(int,float)) or not 0<=value<=1 for value in baseline.values()):
            raise ValueError("PILOT_BASELINE_MUST_HAVE12_VALID_REQUIRED_SCOPE_SUCCESS_RATES")
    elif args.smoke or args.repair_only:baseline={}
    else:raise ValueError("Closed pilot --baseline is required for the formal first5percent gate")
    protocol=json.loads(args.protocol.read_text());registry=args.registry or Path(protocol["registry"]["path"])
    if digest(registry)!=protocol["registry"]["sha256"]:raise ValueError("FROZEN_REGISTRY_SHA_MISMATCH")
    session=uuid.uuid4().hex;started=time.monotonic()
    run_root=args.run_root or ROOT/"runtime"/("task_"+str(args.task_id))/("job_"+job+"_"+session[:8])
    if not run_root.resolve().is_relative_to(ROOT):raise ValueError("Runtime writes only inside this WP5 root")
    run_root.mkdir(parents=True,exist_ok=False)
    if args.mode=="cleanup":queue.recover_node(node,args.dictionaries)
    queue.start(session,job,args.task_id,args.mode,node)
    scratch=args.scratch_root/("wp5runtime_"+str(os.getuid())+"_"+job+"_"+session[:8])
    scratch.mkdir(parents=True,exist_ok=False)
    hard_hours=min(args.hours-args.export_reserve_hours,46.0)
    admission=min(args.admit_hours,hard_hours-.1)
    if admission<=0:raise ValueError("Deadline reserve leaves no computation time")
    options={"queue":str(args.queue),"session":session,"job_id":job,"task_id":str(args.task_id),"mode":args.mode,
       "node_scope":node_scope,"run_root":str(run_root),"scratch_root":str(scratch),"local_index":str(scratch/"record_index.sqlite"),
       "source_plan":str(args.source_plan),"plan":str(args.plan),"assignments":str(args.assignments),"protocol":str(args.protocol),"registry":str(registry),
       "registry_sha":digest(registry),"dictionaries":str(args.dictionaries),"policy":args.policy,"workers":args.workers,
       "production_contract":str(args.production_contract),"production_contract_sha256":digest(args.production_contract),
       "audit_membership":str(args.audit_membership),"audit_membership_sha256":digest(args.audit_membership),
       "reproduction_package":str(args.reproduction_package),"reproduction_package_sha256":digest(args.reproduction_package),
       "job_exit_monotonic":started+args.hours*3600,"smoke":args.smoke,"claim_cap":args.claim_cap,"hard_epoch":time.time()+hard_hours*3600,
       "hard_monotonic":started+hard_hours*3600,"admit_monotonic":started+admission*3600}
    source_paths=[Path(__file__),Path(__file__).with_name("wp5_engine_v3.py"),Path(__file__).with_name("wp5_parser_v2.py"),Path(__file__).with_name("wp5_parquet_v2.py"),Path(__file__).with_name("wp5_archive_v5.py"),Path(__file__).with_name("wp5_accounting_v2.py"),args.protocol,registry,args.dictionaries,args.plan,args.assignments,args.source_plan,args.node_authority,args.node_scope_plan]
    source_paths += [args.production_contract,args.audit_membership,args.reproduction_package,Path(__file__).with_name("wp5_archive_v4.py"),Path(__file__).with_name("wp5_scf_metadata_v2.py"),Path(__file__).with_name("wp5_registry_coverage_v2.py")]
    if args.baseline:source_paths.append(args.baseline)
    options["source_bindings"]=[{"path":str(path),"sha256":digest(path)} for path in source_paths]
    queue.db.retry_deadline=options["hard_monotonic"]+120
    atomic(run_root/"run.json",{"node":node,"node_scope":node_scope,"pid":os.getpid(),"options":options,"start_epoch":time.time(),
                               "guide_source_sha256":digest(ROOT.parent.parent/"WP5 正式计算行动指南（Codex）.md"),"production_contract_sha256":digest(args.production_contract)})
    signal.signal(signal.SIGUSR1,lambda *_:atomic(run_root/"STOP_CLAIMS.json",{"reason":"SLURM_WARNING_STOP_NEW_CLAIMS","time":time.time()}))
    reports=[];resource_peaks={"RSS_bytes":None,"PSS_bytes":None,"local_scratch_bytes":None};error=None;references=[];archive=None
    try:
        repairs=repair_unexported(queue,options,options["job_exit_monotonic"]-args.export_reserve_hours*3600) if args.mode=="cleanup" or args.repair_only else []
        atomic(run_root/"previous_export_repairs.json",{"repairs":repairs})
        index={"molecules":0,"reason":"REPAIR_ONLY_NO_NEW_QM"} if args.repair_only else prepare_index(queue,options)
        atomic(run_root/"input_index.json",index)
        if index["molecules"]:
            context=multiprocessing.get_context("spawn");barrier=context.Barrier(24)
            with concurrent.futures.ProcessPoolExecutor(max_workers=24,mp_context=context,initializer=bind_worker_barrier,initargs=(barrier,)) as pool:
                futures=[pool.submit(worker_loop,options,lane) for lane in range(24)]
                checkpoint=time.monotonic();checked=0.
                while not all(future.done() for future in futures):
                    sample=resource_sample(scratch)
                    for key in resource_peaks:
                        if sample[key] is not None:resource_peaks[key]=max(resource_peaks[key] or 0,sample[key])
                    now=time.monotonic()
                    if now-checked>=300:health(queue,baseline);checked=now
                    if now-checkpoint>=1800:
                        atomic(run_root/"checkpoint.json",{"time":time.time(),"session":session,
                             "queue":queue.summary(),"resource_peaks":resource_peaks,"stop":stopped()})
                        if args.mode=="main":queue.db.execute("UPDATE tasks SET heartbeat=? WHERE task_id=?",(time.time(),str(args.task_id)))
                        checkpoint=now
                    if now>=options["hard_monotonic"]+120:
                        atomic(run_root/"STOP_CLAIMS.json",{"reason":"OWN_QM_DEADLINE","time":time.time()})
                        for process in (getattr(pool,"_processes",None) or {}).values():
                            if process.is_alive():terminate_owned_tree(process.pid)
                        break
                    time.sleep(5 if args.smoke else 10)
                for future in futures:
                    try:reports.append(future.result())
                    except Exception:
                        error=traceback.format_exc(limit=8)
                        atomic(run_root/"worker_error.json",{"traceback":error})
            queue.db.retry_deadline=options["job_exit_monotonic"]-120
            queue.release_running(session)
        # All workers have exited. Finalization runs in a bounded child so
        # the Slurm parent checkpoints before its own 48h deadline.
        outcome=bounded_finalize(options,options["job_exit_monotonic"]-120)
        if outcome.get("error"):
            error=outcome["error"]
            if "MANIFEST_" in error:stop("POPULATION_OR_OUTPUT_COUNT_NOT_CLOSED",{"traceback":error})
            atomic(run_root/"export_error.json",{"traceback":error,"durable_staging_preserved":True})
        else:
            exported=outcome["result"];references=exported["families"];archive=exported["archive"]
            staged_records=exported["records"];staged_molecules=exported["molecules"]
            staged_bytes=exported["compressed_wire_bytes"];staged_uncompressed_bytes=exported["uncompressed_wire_bytes"]
            canonical=exported["canonical"]

    except Exception:
        error=traceback.format_exc(limit=12)
        if "MANIFEST_" in error:stop("POPULATION_OR_OUTPUT_COUNT_NOT_CLOSED",{"traceback":error})
        atomic(run_root/"runtime_error.json",{"traceback":error,"other_jobs_should_continue_unless_stop_flag":not stopped()})
        queue.db.retry_deadline=options["job_exit_monotonic"]-120
        try:queue.release_running(session)
        except Exception:
            error=(error or "")+"\nQUEUE_RELEASE_ERROR:\n"+traceback.format_exc(limit=8)
            atomic(run_root/"queue_release_error.json",{"traceback":error,"durable_staging_preserved":True})
    finally:
        queue.db.retry_deadline=options["job_exit_monotonic"]-120
        try:queue.end(session,args.task_id,args.mode)
        except Exception:
            error=(error or "")+"\nQUEUE_END_ERROR:\n"+traceback.format_exc(limit=8)
            atomic(run_root/"queue_end_error.json",{"traceback":error,"durable_staging_preserved":True})
        try:queue_summary=queue.summary()
        except Exception:
            error=(error or "")+"\nQUEUE_SUMMARY_ERROR:\n"+traceback.format_exc(limit=8)
            queue_summary={"states":None,"durable_completed_molecules":None,"pending_molecules":None,
                           "unavailable_reason":"SQL_METADATA_READ_FAILED","traceback":error}
        import shutil
        preserve_local=any(not (report.get("cleanup") or {}).get("work_root_removed",True) for report in reports) or (scratch.exists() and any(scratch.rglob("RAW_ARCHIVE_FAILURE_PRESERVE.json")))
        if not preserve_local and scratch.resolve().is_relative_to(args.scratch_root.resolve()) and scratch.name.startswith("wp5runtime_"):
            shutil.rmtree(scratch)
        result={"status":"WP5_JOB_CLOSED" if error is None else "WP5_JOB_RECORDED_ERROR",
                "job_id":job,"task_id":args.task_id,"mode":args.mode,"session":session,"node":node,"node_scope":node_scope,
                "seconds":time.monotonic()-started,"queue":queue_summary,"workers":reports,
                 "queue_metadata_retry_stats":dict(queue.db.retry_stats),
                 "first5_health_cache":str(queue.cache_path) if queue.cache_path.exists() else None,
                "resource_peaks":resource_peaks,"scratch_clean":not scratch.exists(),"local_archive_failure_evidence_preserved":preserve_local,
                "staged_compressed_wire_bytes":locals().get("staged_bytes",None),
                "staged_uncompressed_wire_bytes":locals().get("staged_uncompressed_bytes",None),
                "canonical_record_attempts":locals().get("canonical",None),
                "claim_cap":args.claim_cap,"artificial_admission_cutoff":bool(args.claim_cap),
                "admit_hours":admission,"own_QM_deadline_hours":hard_hours,"finalization_reserve_hours":args.export_reserve_hours,
                "completed_records_this_run":locals().get("staged_records",0),
                "completed_molecules_this_run":locals().get("staged_molecules",0),
                "families":references,"archive":archive,"global_stop":stopped(),"error":error,
                "repair_only":args.repair_only,"previous_export_repairs":locals().get("repairs",[]),
                "original_data_written":False,"lmdb_created":False}
        atomic(run_root/"checkpoint.json",result);atomic(run_root/"completion.json",result)
        queue.db.close()
    print(json.dumps({"completion":str(run_root/"completion.json"),"status":result["status"],
                      "molecules":result["completed_molecules_this_run"],"pending":result["queue"]["pending_molecules"]}))
    # Recorded scientific failures/normal deadline exits are not scheduler failures.

if __name__=="__main__":main()

