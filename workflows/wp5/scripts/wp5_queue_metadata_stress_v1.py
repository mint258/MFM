"""TEST-only WP5 shared metadata queue stress; never QM, LMDB or formal queue."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, importlib.util, json, math, multiprocessing
import os, socket, sqlite3, stat, time, traceback
from pathlib import Path

PROJECT = Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
TEST_BASE = PROJECT / "gates" / "metadata_queue_fixture"
NODES = ("compute-0-12","compute-0-13","compute-0-14","compute-0-17","compute-0-18","compute-0-19")
HEALTH_CALLERS = dict(zip(NODES, (4,4,4,8,4,5)))
CALCS = ("pm7_B","pm7_cation","pm7_anion","pm7_water","pm7_octanol","xtb_singlepoint",
         "xtb_vipea","xtb_vfukui","xtb_ALPB_water","xtb_ALPB_octanol","xtb_fod","xtb_perturbed_gradient")
POPULATION = 1220466
EARLY = math.ceil(POPULATION * .05)
WORKERS = 24
CLAIMS_PER_WORKER = 70
CTX = {}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def atom(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+str(os.getpid())+".pending")
    with tmp.open("w") as f:
        json.dump(data,f,sort_keys=True,allow_nan=False);f.write("\n");f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def elapsed_wait(path, deadline):
    while not Path(path).exists():
        if time.monotonic() >= deadline:raise TimeoutError("PRIVATE_FIXTURE_SIGNAL_TIMEOUT:"+str(path))
        time.sleep(.05)

def load_runtime(args, private_root=None):
    path=Path(args["runner"])
    if sha(path)!=args["runner_sha256"]:raise ValueError("RUNTIME_SOURCE_SHA_CHANGED")
    spec=importlib.util.spec_from_file_location("wp5_metadata_runtime_under_test",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=Path(private_root or args["root"])
    module.ROOT=root;module.STOP=root/"STOP_NEW_MOLECULES.json"
    assert module.STOP != PROJECT/"STOP_NEW_MOLECULES.json"
    return module

def queue_of(module,args,path=None):
    q=module.Queue(path or Path(args["root"])/"fixture.sqlite",
                   deadline=time.monotonic()+args["start_timeout_seconds"]+1800,
                   baseline_path=Path(args["root"])/"baseline.json")
    q.db.execute("PRAGMA busy_timeout=25")
    q.db.retry_budget_seconds=args["retry_budget_seconds"]
    return q

def counts_for(ordinal,records=10):
    # Counts are controlled metadata, NOT scientific labels or measured success rates.
    return {c:{"success":0 if (ordinal+17*i)%100==0 else records,"total":records}
            for i,c in enumerate(CALCS)}

def summary_for(item,node,lane,pid):
    return {"molecule_id":item["molecule_id"],"records":item["record_count"],
            "lane":lane,"archive_path":"TEST_METADATA_ONLY_NO_RAW_ARCHIVE",
            "counts":counts_for(int(item["molecule_id"].rsplit("_",1)[1]),item["record_count"]),
            "retryable":False,"worker_pid":pid,
            "synthetic":True,"scope":"METADATA_ONLY_NO_SCIENTIFIC_VALUES",
            "context":{"attempt_id":item["attempt"],"execution_id":"TEST:"+item["molecule_id"],
                       "node":node,"lane":lane}}

def template_partition(root,rank,workers,barrier):
    import pyarrow as pa, pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    barrier.wait(timeout=300)
    begin=POPULATION*rank//workers+1;end=POPULATION*(rank+1)//workers+1
    rows=[]
    for n in range(begin,end):
        slot=(n-1)%len(NODES)
        rows.append({"molecule_id":"metadata_fixture_mol_"+str(n).zfill(8),"task_id":str(slot),
            "file_group":1+(n-1)%5,"records":10,"planned_allocated_seconds":0.0,
            "sequence_in_task":(n-1)//len(NODES)})
    path=Path(root)/"assignments"/("part_"+str(rank).zfill(2)+".parquet")
    path.parent.mkdir(parents=True,exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows),path,compression="zstd")
    return {"pid":os.getpid(),"rows":len(rows),"path":str(path),"sha256":sha(path)}

def generator_init(barrier):
    global GEN_BARRIER
    GEN_BARRIER=barrier

def generator_task(root,rank,workers):
    return template_partition(root,rank,workers,GEN_BARRIER)

def init_fixture(args):
    root=Path(args["root"])
    if root.exists():raise FileExistsError("PRIVATE_FIXTURE_ROOT_ALREADY_EXISTS")
    root.mkdir(parents=True)
    baseline={c:1.0 for c in CALCS}
    atom(root/"baseline.json",{"success_rates":baseline,"synthetic":True})
    plan={"tasks":[{"task_id":str(i),"node":n,"record_directory":"TEST_NO_SOURCE_OPEN"}
                   for i,n in enumerate(NODES)],"synthetic":True,"no_scientific_prediction":True}
    atom(root/"plan.json",plan)
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(16)
    with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,
            initializer=generator_init,initargs=(barrier,)) as pool:
        partitions=list(pool.map(generator_task,[str(root)]*16,range(16),[16]*16,chunksize=1))
    if len({p["pid"] for p in partitions})!=16:raise ValueError("INIT_NOT16_ACTUAL_WORKERS")
    import pyarrow as pa, pyarrow.parquet as pq
    assignment_path=root/"assignments.parquet"
    schema=pq.ParquetFile(partitions[0]["path"]).schema_arrow
    with pq.ParquetWriter(assignment_path,schema,compression="zstd") as merged:
        for partition in partitions:
            for batch in pq.ParquetFile(partition["path"]).iter_batches(batch_size=8192):
                merged.write_table(pa.Table.from_batches([batch],schema=schema))
    module=load_runtime(args);q=queue_of(module,args)
    try:
        q.seed(root/"plan.json",assignment_path,False)
        q.db.execute("BEGIN IMMEDIATE")
        try:
            for start in range(1,EARLY+1,1024):
                items=[]
                for n in range(start,min(EARLY+1,start+1024)):
                    rid="metadata_fixture_mol_"+str(n).zfill(8)
                    receipt={"molecule_id":rid,"records":10,"synthetic":True,
                             "scope":"TEST_PRESEEDED_METADATA_NO_SCIENTIFIC_VALUES"}
                    items.append((json.dumps(receipt),json.dumps(counts_for(n)),n,
                                  "TEST_PRESEED_NOT_LIVE_JOB",time.time(),rid))
                q.db.executemany("UPDATE molecules SET state='COMPLETE',receipt_json=?,counts_json=?,completion_rank=?,owner=?,updated=? WHERE molecule_id=?",items)
            q.db.execute("UPDATE meta SET value=? WHERE key='completion_sequence'",(str(EARLY),))
            q.db.execute("INSERT INTO meta(key,value) VALUES('fixture_write_hold','0')")
            q.db.execute("COMMIT")
        except BaseException:
            if q.db.in_transaction:q.db.execute("ROLLBACK")
            raise
        summary=q.summary()
        cached=q.cache_path if hasattr(q,"cache_path") else q.path.with_name(q.path.name+".first5_health_v1.json")
        if Path(cached).exists():raise ValueError("FIRST5_CACHE_CREATED_BEFORE_PRESSURE")
        result={"schema":"WP5_METADATA_QUEUE_FIXTURE_INIT_V1","status":"TEST_FIXTURE_INITIALIZED",
            "synthetic":True,"QM_started":False,"LMDB_opened":False,"formal_queue_touched":False,
            "population_molecules":POPULATION,"population_records":POPULATION*10,
            "initial_completed_molecules":EARLY,"initial_pending_molecules":POPULATION-EARLY,
            "scheduling_cost_stub":0.0,"scheduling_cost_is_prediction":False,
            "generator_actual_workers":16,"partitions":partitions,"queue":summary,
            "runner":{"path":args["runner"],"sha256":args["runner_sha256"]}}
        atom(root/"init_report.json",result)
    finally:q.db.close()
    return result

def worker_initializer(args,node,barrier):
    module=load_runtime(args);q=queue_of(module,args)
    CTX.update(module=module,q=q,args=args,node=node)
    atom(Path(args["root"])/"readiness"/node/("worker_pid_"+str(os.getpid())+".json"),
         {"pid":os.getpid(),"node":node,"job_id":os.environ.get("SLURM_JOB_ID")})
    barrier.wait(timeout=300)

def writer_task(lane):
    args=CTX["args"];node=CTX["node"];q=CTX["q"];pid=os.getpid()
    session=args["session"];root=Path(args["root"]);events=[];last=None;error=None
    try:
        elapsed_wait(root/"START.json",time.monotonic()+args["start_timeout_seconds"])
        for i in range(CLAIMS_PER_WORKER):
            item=q.claim(session,str(NODES.index(node)),"main",3600,0)
            if item is None:raise ValueError("SYNTHETIC_ACTIVE_SUBSET_CLAIMED_TOO_EARLY")
            q.db.execute("UPDATE molecules SET lane=?,archive_path=? WHERE molecule_id=? AND owner=?",
                         (lane,"TEST_METADATA_ONLY_NO_RAW_ARCHIVE",item["molecule_id"],session))
            summary=summary_for(item,node,lane,pid)
            q.finish(session,summary)
            q.db.execute("UPDATE tasks SET heartbeat=? WHERE task_id=?",(time.time(),str(NODES.index(node))))
            events.append({"molecule_id":item["molecule_id"],"attempt":item["attempt"],
                           "node":node,"lane":lane,"pid":pid,"sequence":i+1})
            last=item["molecule_id"]
    except BaseException:error=traceback.format_exc(limit=12)
    result={"pid":pid,"lane":lane,"node":node,"claim_count":len(events),
            "finish_count":len(events),"heartbeat_count":len(events),
            "last_molecule":last,"events":events,"retry_stats":dict(q.db.retry_stats),
            "in_transaction_after_work":q.db.in_transaction,"error":error,
            "QM_started":False,"LMDB_opened":False}
    atom(root/"workers"/node/("lane_"+str(lane).zfill(2)+".json"),result)
    q.db.close()
    return result

def health_actor(args,node,actor):
    module=load_runtime(args);q=queue_of(module,args);root=Path(args["root"])
    scans=0;calls=0;ready=[];error=None
    def trace(sql):
        nonlocal scans
        text=sql.lower()
        if text.lstrip().startswith("select") and "counts_json" in text and "json_each" in text:
            scans+=1
    q.db.set_trace_callback(trace)
    atom(root/"health_readiness"/node/("actor_"+str(actor)+".json"),{"pid":os.getpid()})
    try:
        elapsed_wait(root/"START.json",time.monotonic()+args["start_timeout_seconds"])
        while not (root/"WRITERS_FINISHED.json").exists():
            module.health(q,{c:1.0 for c in CALCS})
            snapshot=q.early_health_snapshot({c:1.0 for c in CALCS});calls+=1
            if snapshot is not None:
                if snapshot["status"]!="READY":raise ValueError("PRIVATE_FIRST5_SNAPSHOT_NOT_READY")
                ready.append({"publisher_pid":snapshot["publisher_pid"],"publisher_node":snapshot["publisher_node"],"published_epoch":snapshot["published_epoch"]})
            if (root/"STOP_NEW_MOLECULES.json").exists():raise ValueError("POSITIVE_FIXTURE_UNEXPECTED_STOP")
            time.sleep(.2)
        if not ready:
            snapshot=q.early_health_snapshot({c:1.0 for c in CALCS});calls+=1
            if snapshot is not None:ready.append({"publisher_pid":snapshot["publisher_pid"],"publisher_node":snapshot["publisher_node"],"published_epoch":snapshot["published_epoch"]})
        if not ready:raise ValueError("PRIVATE_FIRST5_CACHE_NEVER_READY")
    except BaseException:error=traceback.format_exc(limit=12)
    result={"pid":os.getpid(),"node":node,"actor":actor,"health_calls":calls,
        "early_sql_scans":scans,"ready_references":sorted({(r["publisher_node"],r["publisher_pid"],r["published_epoch"]) for r in ready}),
        "retry_stats":dict(q.db.retry_stats),"error":error}
    atom(root/"health_results"/node/("actor_"+str(actor)+".json"),result)
    q.db.close();return result

def lock_holder(args):
    module=load_runtime(args);q=queue_of(module,args);root=Path(args["root"])
    def hold():
        q.db.execute("UPDATE meta SET value='1' WHERE key='fixture_write_hold'")
        if not (root/"lock_held.json").exists():
            atom(root/"lock_held.json",{"pid":os.getpid(),"begin":time.time(),"hold_seconds":1.0})
        if not (root/"START.json").exists():
            atom(root/"START.json",{"status":"PRIVATE_FIXTURE_START","lock_holder_pid":os.getpid(),"time":time.time()})
        time.sleep(1.0)
    q.db.transaction(hold)
    atom(root/"lock_released.json",{"pid":os.getpid(),"released":time.time(),"retry_stats":dict(q.db.retry_stats)})
    q.db.close()

def node_fixture(args):
    root=Path(args["root"]);node=socket.gethostname().split(".")[0]
    if node not in NODES:raise ValueError("UNAUTHORIZED_ACTUAL_FIXTURE_NODE")
    args=dict(args);args["session"]="metadata_fixture:"+str(os.environ["SLURM_JOB_ID"])+":"+node
    module=load_runtime(args);q=queue_of(module,args)
    q.start(args["session"],os.environ["SLURM_JOB_ID"],str(NODES.index(node)),"main",node)
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(WORKERS)
    deadline=time.monotonic()+args["start_timeout_seconds"]
    with concurrent.futures.ProcessPoolExecutor(max_workers=WORKERS,mp_context=context,
            initializer=worker_initializer,initargs=(args,node,barrier)) as writers, \
         concurrent.futures.ProcessPoolExecutor(max_workers=HEALTH_CALLERS[node],mp_context=context) as health:
        wf=[writers.submit(writer_task,lane) for lane in range(WORKERS)]
        hf=[health.submit(health_actor,args,node,i) for i in range(HEALTH_CALLERS[node])]
        while len(list((root/"readiness"/node).glob("worker_pid_*.json")))!=WORKERS or len(list((root/"health_readiness"/node).glob("actor_*.json")))!=HEALTH_CALLERS[node]:
            if any(f.done() and f.exception() for f in wf+hf):
                raise RuntimeError("FIXTURE_PROCESS_START_FAILED")
            if time.monotonic()>=deadline:raise TimeoutError("ACTUAL24_WORKER_READINESS_TIMEOUT")
            time.sleep(.1)
        atom(root/"node_readiness"/(node+".json"),{"node":node,"actual_workers":WORKERS,"health_callers":HEALTH_CALLERS[node]})
        if node==NODES[0]:
            while not all((root/"node_readiness"/(n+".json")).exists() for n in NODES):
                if time.monotonic()>=deadline:raise TimeoutError("SIX_NODE_QUORUM_TIMEOUT")
                time.sleep(.1)
            holder=context.Process(target=lock_holder,args=(args,));holder.start()
        results=[f.result() for f in wf]
        if not any(r.get("error") for r in results):
            q.release_running(args["session"])
            q.publish_export(args["session"],[{"path":str(root/"baseline.json"),"bytes":(root/"baseline.json").stat().st_size,"sha256":sha(root/"baseline.json"),"synthetic_metadata_reference":True}],{"path":"TEST_METADATA_ONLY_NO_RAW_ARCHIVE","synthetic":True})
        atom(root/"node_writers_finished"/(node+".json"),{"node":node})
        if node==NODES[0]:
            while not all((root/"node_writers_finished"/(n+".json")).exists() for n in NODES):
                if time.monotonic()>=deadline+900:raise TimeoutError("SIX_NODE_FINISH_TIMEOUT")
                time.sleep(.1)
            atom(root/"WRITERS_FINISHED.json",{"time":time.time()})
            holder.join(timeout=120)
            if holder.exitcode!=0:raise RuntimeError("LOCK_HOLDER_FAILED")
        health_results=[f.result(timeout=1200) for f in hf]
    errors=[r["error"] for r in results+health_results if r.get("error")]
    q.end(args["session"],str(NODES.index(node)),"main")
    report={"schema":"WP5_METADATA_QUEUE_FIXTURE_NODE_V1","status":"TEST_NODE_CLOSED" if not errors else "TEST_NODE_ERRORS",
       "synthetic":True,"node":node,"job_id":os.environ["SLURM_JOB_ID"],
       "actual_workers":len({r["pid"] for r in results}),"health_callers":HEALTH_CALLERS[node],
       "claims":sum(r["claim_count"] for r in results),"finishes":sum(r["finish_count"] for r in results),
       "workers":results,"health":health_results,"errors":errors,"parent_retry_stats":dict(q.db.retry_stats),
       "QM_started":False,"LMDB_opened":False,"formal_queue_touched":False}
    atom(root/"nodes"/(node+".json"),report);q.db.close()
    if errors:raise RuntimeError("METADATA_NODE_ERRORS:"+str(len(errors)))
    return report

def admission_lock_holder(args,tag):
    module=load_runtime(args);q=queue_of(module,args);root=Path(args["root"])
    def hold():
        q.db.execute("UPDATE meta SET value=? WHERE key='fixture_write_hold'",(tag,))
        atom(root/(tag+"_held.json"),{"pid":os.getpid(),"held_epoch":time.time(),"hold_seconds":.5})
        time.sleep(.5)
    q.db.transaction(hold);q.db.close()

def private_claim_deadlines(args):
    root=Path(args["root"])/"private_claim_deadline";root.mkdir(exist_ok=False)
    own=dict(args);own["root"]=str(root)
    atom(root/"baseline.json",{"success_rates":{c:1.0 for c in CALCS},"synthetic":True})
    module=load_runtime(own,root);q=queue_of(module,own)
    import pyarrow as pa,pyarrow.parquet as pq
    actual_node=socket.gethostname().split(".")[0]
    atom(root/"plan.json",{"tasks":[{"task_id":"0","node":actual_node,"record_directory":"TEST_NO_SOURCE_OPEN"}]})
    rows=[{"molecule_id":"claim_deadline_"+str(n),"task_id":"0","file_group":1,"records":1,
           "planned_allocated_seconds":0.0,"sequence_in_task":n} for n in range(20)]
    pq.write_table(pa.Table.from_pylist(rows),root/"assignments.parquet")
    q.seed(root/"plan.json",root/"assignments.parquet",False)
    q.db.execute("INSERT INTO meta VALUES('fixture_write_hold','0')")
    session="TEST_PRIVATE_CLAIM_DEADLINES"
    q.start(session,os.environ["SLURM_JOB_ID"],"0","main",actual_node)
    context=multiprocessing.get_context("spawn");cases=[]
    for tag,remaining,budget,expect_none in (("own_admission_deadline",.05,120,True),
                                             ("operation_budget_before_admission",5,.05,False)):
        holder=context.Process(target=admission_lock_holder,args=(own,tag));holder.start()
        elapsed_wait(root/(tag+"_held.json"),time.monotonic()+60)
        q.db.retry_budget_seconds=budget
        before=dict(q.db.retry_stats);start=time.monotonic();error=None;result=None
        try:result=q.claim(session,"0","main",remaining,0)
        except sqlite3.OperationalError as caught:error=caught
        seconds=time.monotonic()-start
        holder.join(timeout=60)
        if holder.exitcode!=0:raise ValueError("PRIVATE_ADMISSION_LOCK_HOLDER_FAILED")
        if expect_none and (error is not None or result is not None):raise ValueError("CLAIM_DEADLINE_BUSY_DID_NOT_RETURN_NONE")
        if not expect_none and (error is None or not module.sqlite_lock_error(error)):
            raise ValueError("EARLY_METADATA_RETRY_BUDGET_ERROR_WAS_SWALLOWED")
        if q.db.retry_stats["transaction_busy_retries"]<=before["transaction_busy_retries"]:
            raise ValueError("PRIVATE_CLAIM_LOCK_RETRY_NOT_OBSERVED")
        if q.db.execute("SELECT claims FROM sessions WHERE session_id=?",(session,)).fetchone()[0]!=0 or q.db.execute("SELECT count(*) FROM molecules WHERE state!='PENDING' OR attempt!=0").fetchone()[0]!=0:
            raise ValueError("CLAIM_DEADLINE_CHANGED_METADATA_OR_SCIENCE_ATTEMPT")
        cases.append({"case":tag,"remaining_seconds":remaining,"retry_budget_seconds":budget,
            "elapsed_seconds":seconds,"returned_none":error is None and result is None,
            "error":str(error) if error is not None else None,"error_code":getattr(error,"sqlite_errorcode",None),
            "transaction_busy_retries":q.db.retry_stats["transaction_busy_retries"]-before["transaction_busy_retries"],
            "claims_after_case":0,"attempts_consumed":0})
    q.db.retry_budget_seconds=args["retry_budget_seconds"]
    q.db.execute("DROP TABLE sessions")
    before=dict(q.db.retry_stats)
    try:q.claim(session,"0","main",.05,0)
    except sqlite3.OperationalError as error:
        if module.sqlite_lock_error(error):raise
        nonbusy={"error":str(error),"error_code":getattr(error,"sqlite_errorcode",None),"propagated":True}
    else:raise ValueError("CLAIM_NON_BUSY_SCHEMA_ERROR_SWALLOWED")
    if q.db.retry_stats["transaction_busy_retries"]!=before["transaction_busy_retries"]:
        raise ValueError("CLAIM_NON_BUSY_SCHEMA_ERROR_RETRIED")
    if q.db.execute("SELECT count(*) FROM molecules WHERE state!='PENDING' OR attempt!=0").fetchone()[0]!=0:
        raise ValueError("CLAIM_NON_BUSY_CHANGED_MOLECULES")
    report={"status":"PRIVATE_CLAIM_DEADLINE_AND_ERROR_BOUNDARIES_PASS","cases":cases,
            "non_busy_claim_error":nonbusy,"claims":0,"attempts_consumed":0,"formal_queue_touched":False}
    atom(root/"report.json",report);q.db.close();return report

def private_negative(args):
    root=Path(args["root"])/"private_negative";root.mkdir(exist_ok=False)
    own=dict(args);own["root"]=str(root)
    atom(root/"baseline.json",{"success_rates":{c:1.0 for c in CALCS},"synthetic":True})
    module=load_runtime(own,root);q=queue_of(module,own)
    import pyarrow as pa,pyarrow.parquet as pq
    plan={"tasks":[{"task_id":"0","node":NODES[0],"record_directory":"TEST_NO_SOURCE_OPEN"}]}
    atom(root/"plan.json",plan)
    rows=[{"molecule_id":"negative_"+str(n),"task_id":"0","file_group":1,"records":1,
           "planned_allocated_seconds":0.0,"sequence_in_task":n} for n in range(20)]
    pq.write_table(pa.Table.from_pylist(rows),root/"assignments.parquet")
    q.seed(root/"plan.json",root/"assignments.parquet",False)
    q.db.execute("UPDATE molecules SET state='COMPLETE',completion_rank=1,receipt_json=?,counts_json=? WHERE molecule_id='negative_0'",
                 (json.dumps({"synthetic":True}),json.dumps({c:{"success":0,"total":1} for c in CALCS})))
    q.db.execute("UPDATE meta SET value='1' WHERE key='completion_sequence'")
    before=dict(q.db.retry_stats)
    try:q.db.execute("SELECT nonexistent_fixture_column FROM molecules")
    except sqlite3.OperationalError as error:
        if getattr(error,"sqlite_errorcode",None) in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED):raise
        nonbusy={"class":type(error).__name__,"message":str(error),"code":getattr(error,"sqlite_errorcode",None)}
    else:raise AssertionError("NON_BUSY_ERROR_SWALLOWED")
    after=dict(q.db.retry_stats)
    if before["statement_busy_retries"]!=after["statement_busy_retries"]:raise ValueError("NON_BUSY_ERROR_RETRIED")
    module.health(q,{c:1.0 for c in CALCS})
    stop_path=root/"STOP_NEW_MOLECULES.json"
    if not stop_path.is_file():raise ValueError("PRIVATE_GT2PP_NEGATIVE_DID_NOT_STOP")
    stop=json.loads(stop_path.read_text())
    if stop["reason"]!="EARLY_TASK_SUCCESS_DROP_GT2PP":raise ValueError("PRIVATE_NEGATIVE_STOP_REASON_DIFFERS")
    result={"status":"PRIVATE_NEGATIVE_STOP_VERIFIED","stop_path":str(stop_path),"stop":stop,
        "formal_STOP_path_used":False,"non_busy_error":nonbusy,"non_busy_not_retried":True}
    atom(root/"report.json",result);q.db.close();return result

def verify_fixture(args):
    root=Path(args["root"]);module=load_runtime(args);q=queue_of(module,args)
    nodes=[json.loads((root/"nodes"/(n+".json")).read_text()) for n in NODES]
    if any(r["status"]!="TEST_NODE_CLOSED" or r["actual_workers"]!=24 for r in nodes):raise ValueError("SIX_NODE_FIXTURE_NOT_CLOSED")
    worker_rows=[w for n in nodes for w in n["workers"]]
    events=[e for w in worker_rows for e in w["events"]]
    if len({w["pid"] for w in worker_rows})!=144:
        # PIDs are host-local; the authoritative identity is (hostname, PID).
        if len({(w["node"],w["pid"]) for w in worker_rows})!=144:raise ValueError("NOT144_ACTUAL_NODE_WORKERS")
    expected_claims=144*CLAIMS_PER_WORKER
    if len(events)!=expected_claims or len({e["molecule_id"] for e in events})!=expected_claims:raise ValueError("CLAIM_COUNT_OR_UNIQUENESS_NOT_CLOSED")
    if any(e["attempt"]!=0 for e in events):raise ValueError("METADATA_RETRY_CONSUMED_SCIENCE_ATTEMPT")
    totals=[dict(r) for r in q.db.execute("SELECT state,count(*) molecules,sum(record_count) records FROM molecules GROUP BY state")]
    states={r["state"]:r["molecules"] for r in totals}
    if states!={"COMPLETE":EARLY+expected_claims,"PENDING":POPULATION-EARLY-expected_claims}:raise ValueError("EXPECTED_FIXTURE_STATE_CLOSURE_DIFFERS:"+json.dumps(states))
    if q.db.execute("SELECT count(*) FROM molecules WHERE attempt!=0").fetchone()[0]!=0:raise ValueError("SCIENCE_ATTEMPT_INCREMENTED")
    if q.db.execute("SELECT count(*) FROM molecules WHERE export_json IS NOT NULL").fetchone()[0]!=expected_claims:raise ValueError("BATCHED_OWNER_EXPORT_METADATA_NOT_CLOSED")
    cache=q.early_health_snapshot({c:1.0 for c in CALCS})
    if cache is None or cache["status"]!="READY":raise ValueError("PRIVATE_CACHE_NOT_READY")
    oracle={c:{"success":0,"total":0} for c in CALCS};prefix=0
    started=time.monotonic()
    for row in q.db.execute("SELECT counts_json FROM molecules WHERE completion_rank<=?",(EARLY,)):
        data=json.loads(row[0]);prefix+=1
        if set(data)!=set(CALCS):raise ValueError("SYNTHETIC_COUNTS_NOT12_CALCS")
        for c in CALCS:
            for key in ("success","total"):oracle[c][key]+=data[c][key]
    oracle_seconds=time.monotonic()-started
    if prefix!=EARLY or cache["observed_prefix_molecules"]!=EARLY or cache["counts"]!=oracle:raise ValueError("FIRST5_CACHE_INTEGER_ORACLE_DIFFERS")
    for c in CALCS:
        if cache["rates"][c]!=oracle[c]["success"]/oracle[c]["total"]:raise ValueError("FIRST5_CACHE_RATE_EQUATION_DIFFERS")
    health=[h for n in nodes for h in n["health"]]
    refs={tuple(ref) for h in health for ref in h["ready_references"]}
    scans=sum(h["early_sql_scans"] for h in health)
    if len(health)!=29 or len(refs)!=1 or scans!=1:raise ValueError("FIRST5_SINGLE_PUBLISH_OR_SQL_SCAN_DIFFERS:"+str((len(health),refs,scans)))
    retries=sum(w["retry_stats"]["statement_busy_retries"]+w["retry_stats"]["transaction_busy_retries"] for w in worker_rows)
    if retries==0 or not (root/"lock_held.json").exists() or not (root/"lock_released.json").exists():raise ValueError("CONTROLLED_BUSY_RETRY_NOT_OBSERVED")
    frozen_path=Path(q.cache_path) if hasattr(q,"cache_path") else q.path.with_name(q.path.name+".first5_health_v1.json")
    frozen_sha=sha(frozen_path)
    old=q.db.execute("SELECT molecule_id,counts_json FROM molecules WHERE completion_rank=1").fetchone()
    changed={c:{"success":0,"total":10} for c in CALCS}
    q.db.execute("UPDATE molecules SET counts_json=? WHERE molecule_id=?",(json.dumps(changed),old[0]))
    try:
        again=q.early_health_snapshot({c:1.0 for c in CALCS})
        if again!=cache or sha(frozen_path)!=frozen_sha:raise ValueError("FROZEN_CACHE_CHANGED_AFTER_POST_PUBLICATION_METADATA")
    finally:q.db.execute("UPDATE molecules SET counts_json=? WHERE molecule_id=?",(old[1],old[0]))
    explain={}
    for name,query,params in (
        ("owner_release","SELECT molecule_id FROM molecules WHERE owner=? AND state='RUNNING'",("fixture",)),
        ("owner_publish","SELECT molecule_id FROM molecules WHERE owner=? AND receipt_json IS NOT NULL",("fixture",)),
        ("cleanup_claim","SELECT m.molecule_id FROM molecules m INDEXED BY cleanup_pending_cost JOIN tasks t USING(task_id) WHERE m.state IN ('PENDING','RETRY_PENDING') AND t.state IN ('CLOSED','DEAD') ORDER BY m.predicted_seconds DESC,m.molecule_id LIMIT 1",())):
        explain[name]=[list(r) for r in q.db.execute("EXPLAIN QUERY PLAN "+query,params)]
    if any(not any("INDEX" in str(r).upper() and "OWNER" in str(r).upper() for r in explain[name]) for name in ("owner_release","owner_publish")):
        raise ValueError("OWNER_INDEX_NOT_USED:"+json.dumps(explain))
    indices=[dict(r) for r in q.db.execute("SELECT name,sql FROM sqlite_master WHERE type='index'")]
    positive_stop=(root/"STOP_NEW_MOLECULES.json").exists()
    if positive_stop:raise ValueError("POSITIVE_FIXTURE_STOPPED")
    q.db.close()
    deadline_cases=private_claim_deadlines(args)
    negative=private_negative(args)
    result={"schema":"WP5_METADATA_QUEUE_STRESS_CLOSED_V1","status":"METADATA_ONLY_STRESS_PASS",
        "scope":"SYNTHETIC_METADATA_QUEUE_NOT_SCIENTIFIC_GATE_PASS","population_molecules":POPULATION,
        "initial_completed_molecules":EARLY,"new_unique_claims":expected_claims,"states":totals,
        "expected_remaining_pending_molecules":POPULATION-EARLY-expected_claims,
        "actual_writer_identities":sorted({(w["node"],w["pid"]) for w in worker_rows}),
        "actual_workers":144,"health_callers":29,"first5_single_sql_scans":scans,
        "first5_single_publisher":list(refs)[0],"first5_cache_sha256":frozen_sha,"first5_cache":cache,
        "integer_oracle":oracle,"integer_oracle_prefix_molecules":prefix,"oracle_seconds":oracle_seconds,
        "frozen_cache_unchanged_after_metadata_replacement":True,"metadata_retry_science_attempts_consumed":0,
        "worker_busy_retries":retries,"explain":explain,"indices":indices,"private_negative":negative,"private_claim_deadlines":deadline_cases,
        "QM_started":False,"LMDB_opened":False,"formal_queue_touched":False,"formal_STOP_written":False,
        "fixture_bytes":(root/"fixture.sqlite").stat().st_size,
        "cleanup_candidates":[str(root/"fixture.sqlite"),str(root/"assignments.parquet"),str(root/"assignments"),str(root/"private_negative"/"fixture.sqlite"),str(root/"private_negative"/"assignments.parquet")],
        "cleanup_performed":False,"runner":{"path":args["runner"],"sha256":args["runner_sha256"]}}
    atom(root/"report.json",result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("init","node","verify"))
    p.add_argument("--root",type=Path)
    p.add_argument("--runner",type=Path,default=PROJECT/"scripts/wp5_runner_v11.py")
    p.add_argument("--runner-sha256")
    p.add_argument("--retry-budget-seconds",type=float,default=120)
    p.add_argument("--start-timeout-seconds",type=float,default=1800)
    p.add_argument("--check",action="store_true")
    a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text())
        assert EARLY==61024 and sum(HEALTH_CALLERS.values())==29 and len(NODES)*WORKERS==144
        assert set(counts_for(1))==set(CALCS)
        print(json.dumps({"status":"METADATA_FIXTURE_AST_AND_SCOPE_CHECK_PASS","QM_started":False,"LMDB_opened":False,
                          "production_source_imported":False,"population":POPULATION,"early":EARLY}));return
    node=socket.gethostname().split(".")[0]
    if not os.environ.get("SLURM_JOB_ID") or node not in NODES or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<24:
        raise ValueError("FIXTURE_REQUIRES24CPU_SLURM_AUTHORIZED_NODE")
    if a.root is None or not a.root.resolve().is_relative_to(TEST_BASE) or a.root.resolve()==TEST_BASE:
        raise ValueError("ONLY_PRIVATE_TEST_FIXTURE_SUBDIRECTORY_ALLOWED")
    if a.root.resolve().is_relative_to(PROJECT/"queue") or a.root.name in ("queue","pending.sqlite"):raise ValueError("FORMAL_QUEUE_FORBIDDEN")
    if a.mode is None or not a.runner_sha256:raise ValueError("MODE_AND_FROZEN_RUNNER_SHA_REQUIRED")
    args=vars(a);args["root"]=str(a.root);args["runner"]=str(a.runner)
    result={"init":init_fixture,"node":node_fixture,"verify":verify_fixture}[a.mode](args)
    print(json.dumps({k:result.get(k) for k in ("status","scope","population_molecules","actual_workers","new_unique_claims")}))
if __name__=="__main__":main()
