"""Production-shaped shared SQLite METADATA TEST v2: declared actual node subset only."""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, math, multiprocessing as mp
import os, socket, sqlite3, time, traceback
from pathlib import Path

ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
BASE=ROOT/"gates"/"metadata_queue_production_shape"
NODES=tuple("compute-0-"+str(i) for i in (12,13,14,17,18,19))
PARENTS=dict(zip(NODES,(4,4,4,8,4,5)))
CALCS=("pm7_B","pm7_cation","pm7_anion","pm7_water","pm7_octanol","xtb_singlepoint",
       "xtb_vipea","xtb_vfukui","xtb_ALPB_water","xtb_ALPB_octanol","xtb_fod","xtb_perturbed_gradient")
PREFIX="TEST_PRODUCTION_SHAPE:"
LIMIT=5_000_000_000

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+"."+str(os.getpid())+".pending")
    with pending.open("w",encoding="utf-8") as f:
        json.dump(value,f,sort_keys=True,allow_nan=False);f.write("\n");f.flush();os.fsync(f.fileno())
    os.replace(pending,path)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(4<<20),b""):h.update(block)
    return h.hexdigest()

def private_root(path):
    p=Path(path).resolve()
    if not p.is_relative_to(BASE.resolve()) or p==BASE.resolve():
        raise ValueError("FIXTURE_MUST_BE_NEW_CHILD_OF_PRIVATE_TEST_BASE")
    if p==ROOT or p.is_relative_to(ROOT/"queue"):raise ValueError("PRODUCTION_PATH_FORBIDDEN")
    return p

def disk_bytes(root):
    return sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())

def conn(path):
    c=sqlite3.connect(str(path),timeout=5,isolation_level=None);c.row_factory=sqlite3.Row
    c.execute("PRAGMA busy_timeout=5000")
    return c

def rows(c,sql,params=()):
    return [dict(r) for r in c.execute(sql,params).fetchall()]

def sqltx(c,fn):
    c.execute("BEGIN IMMEDIATE")
    try:
        answer=fn();c.execute("COMMIT");return answer
    except BaseException:
        if c.in_transaction:c.execute("ROLLBACK")
        raise

def scope_assert(root,db):
    root=private_root(root)
    if Path(db).resolve()!=root/"fixture.sqlite":raise ValueError("ONLY_PRIVATE_FIXTURE_DATABASE_ALLOWED")
    manifest=json.loads((root/"backup_manifest.json").read_text())
    if manifest["schema"]!="WP5_PRODUCTION_SHAPE_BACKUP_V1":raise ValueError("FIXTURE_BACKUP_MANIFEST_MISSING")
    return manifest

def actual_test_nodes(manifest):
    writers=manifest["writers_by_node"]
    nodes=tuple(n for n in NODES if n in writers)
    if not nodes or set(nodes)!=set(writers) or "compute-0-17" not in nodes:
        raise ValueError("AUTHORIZED_NODE_SUBSET_WITH_COORDINATOR17_REQUIRED")
    return nodes

def backup(a):
    root=private_root(a.fixture)
    if root.exists():raise FileExistsError("NEW_FIXTURE_REQUIRED")
    source=Path(a.source).resolve()
    if source!=(ROOT/"queue"/"pending.sqlite").resolve():raise ValueError("EXACT_PRODUCTION_QUEUE_SOURCE_REQUIRED")
    root.mkdir(parents=True);dest=root/"fixture.sqlite"
    deadline=time.monotonic()+a.backup_seconds;progress={"calls":0}
    s=sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=1)
    d=sqlite3.connect(str(dest))
    started=time.time()
    def advance(status,remaining,total):
        progress.update(calls=progress["calls"]+1,status=status,remaining_pages=remaining,total_pages=total)
        if time.monotonic()>=deadline:raise TimeoutError("INCREMENTAL_BACKUP_TIME_BOUND")
        if total*4096>LIMIT:raise ValueError("BACKUP_WOULD_EXCEED_5GB")
    try:
        # Python/SQLite online backup: one consistent shared clone, no file copy.
        s.backup(d,pages=256,progress=advance,sleep=.025)
    finally:d.close();s.close()
    c=conn(dest)
    try:
        actual=c.execute("SELECT count(*),sum(record_count) FROM molecules").fetchone()
        if tuple(actual)!=(1220466,11231854):raise ValueError("PRODUCTION_POPULATION_NOT_CLOSED")
        columns=[r[1] for r in c.execute("PRAGMA table_info(molecules)")]
        templates=rows(c,"SELECT molecule_id,owner,record_count,receipt_json,counts_json,export_json "
            "FROM molecules WHERE receipt_json IS NOT NULL AND export_json IS NOT NULL "
            "ORDER BY length(receipt_json)+length(export_json) DESC LIMIT 16")
        if not templates:raise ValueError("NO_REAL_WIDE_RECEIPT_AND_EXPORT_TEMPLATE")
        for t in templates:
            t["receipt"]=json.loads(t.pop("receipt_json"));t["exports"]=json.loads(t.pop("export_json"))
            t["counts"]=json.loads(t.pop("counts_json"))
            if set(t["counts"])!=set(CALCS):raise ValueError("TEMPLATE_COUNTS_NOT12")
            t["receipt_bytes"]=len(json.dumps(t["receipt"]).encode())
            t["export_bytes"]=len(json.dumps(t["exports"]).encode())
        atomic(root/"templates.json",templates)
        baseline_source=Path(a.baseline)
        baseline=json.loads(baseline_source.read_text())
        if set(baseline["success_rates"])!=set(CALCS):raise ValueError("BASELINE_NOT12")
        atomic(root/"baseline.json",baseline)
        writers=json.loads(a.writers_json) if a.writers_json else {n:24 for n in NODES}
        if not writers or not set(writers).issubset(NODES) or "compute-0-17" not in writers or any(not 16<=int(x)<=256 for x in writers.values()):
            raise ValueError("AUTHORIZED_NODE_SUBSET_EACH_AT_LEAST16_WRITERS_WITH_COORDINATOR17_REQUIRED")
        nodes=actual_test_nodes({"writers_by_node":writers})
        selected=[]
        for n in nodes:
            take=int(writers[n])*a.claims
            selected.extend([{**r,"fixture_node":n,"fixture_task":PREFIX+"MAIN:"+n} for r in rows(c,
                "SELECT m.* FROM molecules m JOIN tasks t USING(task_id) "
                "WHERE m.state='PENDING' AND t.node=? ORDER BY m.priority,m.molecule_id LIMIT ?",(n,take))])
            if len([r for r in selected if r["fixture_node"]==n])!=take:
                raise ValueError("NOT_ENOUGH_REAL_PENDING_FOR_NODE:"+n)
        chosen={r["molecule_id"] for r in selected}
        rare=[]
        for r in rows(c,"SELECT * FROM molecules WHERE state='PENDING' ORDER BY predicted_seconds,molecule_id LIMIT 64"):
            if r["molecule_id"] not in chosen:rare.append(r)
            if len(rare)==len(nodes):break
        if len(rare)!=len(nodes):raise ValueError("RARE_CLEANUP_ROWS_NOT_AVAILABLE")
        selected.extend([{**r,"fixture_node":nodes[i],"fixture_task":PREFIX+"RARE:"+nodes[i]} for i,r in enumerate(rare)])
        def save():
            c.execute("CREATE TABLE fixture_saved_tasks AS SELECT * FROM tasks")
            c.execute("CREATE TABLE fixture_saved_meta AS SELECT * FROM meta")
            c.execute("CREATE TABLE fixture_saved_molecules AS SELECT * FROM molecules WHERE 0")
            c.executemany("INSERT INTO fixture_saved_molecules SELECT * FROM molecules WHERE molecule_id=?",
                          [(r["molecule_id"],) for r in selected])
            c.execute("CREATE TABLE fixture_scope(molecule_id TEXT PRIMARY KEY,node TEXT,task_id TEXT,rare INTEGER)")
            c.executemany("INSERT INTO fixture_scope VALUES(?,?,?,?)",
                [(r["molecule_id"],r["fixture_node"],r["fixture_task"],int(":RARE:" in r["fixture_task"])) for r in selected])
        sqltx(c,save)
        state=rows(c,"SELECT state,count(*) AS molecules,sum(record_count) AS records FROM molecules GROUP BY state")
        manifest={"schema":"WP5_PRODUCTION_SHAPE_BACKUP_V1","status":"CONSISTENT_READONLY_BACKUP_PREPARED",
            "source_path":str(source),"source_stat_bytes":source.stat().st_size,"fixture_path":str(dest),
            "fixture_bytes":dest.stat().st_size,"backup_progress":progress,"backup_elapsed_seconds":time.time()-started,
            "sqlite_version":sqlite3.sqlite_version,"source_population_molecules":actual[0],
            "source_population_records":actual[1],"original_states":state,"molecule_columns":columns,
            "writers_by_node":writers,"actual_test_nodes":list(nodes),"harness_version":2,"total_writers":sum(writers.values()),"claims_per_writer":a.claims,
            "selected_main_molecules":sum(writers.values())*a.claims,"selected_rare_molecules":len(nodes),
            "selected_records":sum(r["record_count"] for r in selected),
            "templates":{"path":str(root/"templates.json"),"sha256":digest(root/"templates.json"),
                "count":len(templates),"receipt_bytes":[t["receipt_bytes"] for t in templates],
                "export_bytes":[t["export_bytes"] for t in templates]},
            "baseline":{"source":str(baseline_source),"sha256":digest(baseline_source)},
            "scope":"All original physical rows and wide existing JSON are copied; only selected PENDING rows and cloned metadata may be changed.",
            "QM_calls":0,"scientific_attempts_consumed":0,"production_writes":0,"max_fixture_bytes":LIMIT}
        atomic(root/"backup_manifest.json",manifest)
    finally:c.close()
    prepare(root)
    if disk_bytes(root)>LIMIT:raise ValueError("FIXTURE_DISK_LIMIT_EXCEEDED")
    return manifest

def prepare(root):
    root=private_root(root);manifest=scope_assert(root,root/"fixture.sqlite");nodes=actual_test_nodes(manifest);c=conn(root/"fixture.sqlite")
    try:
        names=manifest["molecule_columns"];sets=",".join(n+"=(SELECT s."+n+
            " FROM fixture_saved_molecules s WHERE s.molecule_id=molecules.molecule_id)" for n in names if n!="molecule_id")
        def reset():
            c.execute("UPDATE molecules SET "+sets+" WHERE molecule_id IN(SELECT molecule_id FROM fixture_scope)")
            c.execute("DELETE FROM tasks");c.execute("INSERT INTO tasks SELECT * FROM fixture_saved_tasks")
            c.execute("DELETE FROM meta");c.execute("INSERT INTO meta SELECT * FROM fixture_saved_meta")
            c.execute("DELETE FROM sessions WHERE session_id LIKE ?",(PREFIX+"%",))
            c.execute("UPDATE tasks SET state='RUNNING'")
            for n in nodes:
                for kind in ("MAIN","RARE"):
                    tid=PREFIX+kind+":"+n
                    c.execute("INSERT INTO tasks VALUES(?,?,?,'RUNNING',NULL,NULL)",(tid,n,"TEST_NO_SCI_SOURCE_OPEN"))
            c.execute("UPDATE molecules SET task_id=(SELECT task_id FROM fixture_scope s WHERE s.molecule_id=molecules.molecule_id),"
                "state='PENDING',owner=NULL,receipt_json=NULL,counts_json=NULL,completion_rank=NULL,export_json=NULL,"
                "archive_path=NULL,lane=NULL WHERE molecule_id IN(SELECT molecule_id FROM fixture_scope)")
        sqltx(c,reset)
    finally:c.close()

def runtime(path,root):
    spec=importlib.util.spec_from_file_location("metadata_runtime_under_test",path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.ROOT=private_root(root);mod.STOP=Path(root)/"STOP_NEW_MOLECULES.json"
    if mod.STOP.resolve()==(ROOT/"STOP_NEW_MOLECULES.json").resolve():raise ValueError("FORMAL_STOP_BINDING_FORBIDDEN")
    return mod

def queue(mod,root,deadline):
    return mod.Queue(Path(root)/"fixture.sqlite",deadline=deadline,baseline_path=Path(root)/"baseline.json")

def synthetic_receipt(item,template,session,node,lane):
    n=int(item["record_count"]);out=copy.deepcopy(template["receipt"])
    out.update(molecule_id=item["molecule_id"],records=n,lane=lane,
        archive_path="TEST_METADATA_ONLY_NO_ARCHIVE_OPEN",retryable=False,worker_pid=os.getpid(),
        requested_outcomes=n*12,synthetic_metadata_only=True,QM_calls=0)
    out.pop("partial",None);out.pop("error",None)
    out["counts"]={calc:{"success":int(template["counts"][calc]["success"]*n/template["counts"][calc]["total"]),
                        "total":n} for calc in CALCS}
    ctx=out.setdefault("context",{})
    ctx.update(attempt_id=0,job_id=int(os.environ.get("SLURM_JOB_ID","0")),task_id=item["task_id"],
               lane=lane,execution_id=session+":"+str(lane)+":0:METADATA_ONLY",node=node)
    return out

def worker(payload):
    root=Path(payload["root"]);node=payload["node"];lane=payload["lane"];scenario=payload["scenario"]
    deadline=payload["deadline"];version=payload["version"];parents=payload["parent_callers"]
    report={"node":node,"lane":lane,"pid":os.getpid(),"version":version,"scenario":scenario,
        "claimed":[],"operations":{},"errors":[],"QM_calls":0,"scientific_attempts_consumed":0}
    q=None;begin=time.monotonic()
    def op(name,fn):
        started=time.monotonic()
        try:return fn()
        finally:
            v=report["operations"].setdefault(name,{"calls":0,"seconds":0.0,"maximum_seconds":0.0})
            sec=time.monotonic()-started;v["calls"]+=1;v["seconds"]+=sec;v["maximum_seconds"]=max(v["maximum_seconds"],sec)
    try:
        mod=runtime(payload["runner"],root);q=op("Queue.__init__",lambda:queue(mod,root,deadline))
        if hasattr(q.db,"retry_budget_seconds"):q.db.retry_budget_seconds=min(30.,max(1.,deadline-time.monotonic()))
        template=json.loads((root/"templates.json").read_text())[lane%16]
        baseline=json.loads((root/"baseline.json").read_text())["success_rates"]
        session=PREFIX+version+":"+scenario+":"+node+":"+str(lane)
        task=PREFIX+"MAIN:"+node if scenario=="main" else PREFIX+"CLEANUP:"+node+":"+str(lane)
        mode="main" if scenario=="main" else "cleanup"
        op("start",lambda:q.start(session,os.environ.get("SLURM_JOB_ID","0"),task,mode,node))
        (root/"signals").mkdir(exist_ok=True)
        atomic(root/"signals"/(version+"."+scenario+"."+node+"."+str(lane)+".ready"),{"pid":os.getpid()})
        # All writers enter through a true process barrier before claims.
        readyglob=version+"."+scenario+".*.ready"
        while len(list((root/"signals").glob(readyglob)))<payload["total_writers"]:
            if time.monotonic()>=deadline:raise TimeoutError("ACTUAL_TEST_NODE_WRITER_BARRIER")
            time.sleep(.05)
        cap=payload["claims"] if mode=="main" else 1
        for ordinal in range(cap):
            if time.monotonic()>=deadline:break
            # P99 admission bound remains the real Queue rule. No time is spent on QM.
            item=op("claim_"+scenario,lambda:q.claim(session,task,mode,1e9,cap))
            if item is None:break
            if item["molecule_id"] not in payload["scope_ids"]:raise ValueError("CLAIM_ESCAPED_EXPLICIT_FIXTURE_SELECTION")
            receipt=synthetic_receipt(item,template,session,node,lane)
            op("finish",lambda:q.finish(session,receipt));report["claimed"].append(item["molecule_id"])
            export=template["exports"]
            op("publish_export",lambda:q.publish_export(session,export["families"],export["archive"]))
            op("heartbeat",lambda:q.db.execute("UPDATE tasks SET heartbeat=? WHERE task_id=?",(time.time(),str(task))))
            if lane<parents and ordinal%3==0:
                # Each real parent slot is represented by its own connection and calls,
                # sharing one allocated process with a writer to avoid CPU oversubscription.
                p=op("parent.Queue.__init__",lambda:queue(mod,root,deadline))
                try:
                    op("parent.health",lambda:mod.health(p,baseline))
                    op("parent.summary",p.summary)
                finally:p.db.close()
        if mode=="cleanup" and lane<parents:
            op("parent.health",lambda:mod.health(q,baseline));op("parent.summary",q.summary)
        op("release_running",lambda:q.release_running(session))
        op("end",lambda:q.end(session,task,mode))
    except BaseException as e:
        report["errors"].append({"type":type(e).__name__,"message":str(e),"traceback":traceback.format_exc()})
    finally:
        report["elapsed_seconds"]=time.monotonic()-begin
        if q is not None:
            report["retry_stats"]=dict(getattr(q.db,"retry_stats",{}))
            try:q.db.close()
            except BaseException as e:report["errors"].append({"close_error":repr(e)})
        path=root/"worker_reports"/version/scenario/(node+"."+str(lane)+".json")
        atomic(path,report)
    return report

def wait_paths(paths,deadline):
    while not all(Path(p).exists() for p in paths):
        if time.monotonic()>=deadline:raise TimeoutError("MULTINODE_STAGE_BARRIER")
        time.sleep(.1)

def node(a):
    root=private_root(a.fixture);manifest=scope_assert(root,root/"fixture.sqlite");nodes=actual_test_nodes(manifest)
    n=socket.gethostname().split(".")[0]
    if n not in nodes:raise ValueError("UNAUTHORIZED_ACTUAL_NODE")
    workers=int(manifest["writers_by_node"][n])
    if a.workers!=workers or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<workers:
        raise ValueError("ALLOCATED_AND_ACTUAL_WRITER_COUNTS_DIFFER")
    if workers<16:raise ValueError("AT_LEAST16_ACTUAL_WORKERS_REQUIRED")
    deadlines=time.monotonic()+a.total_seconds;scope_conn=conn(root/"fixture.sqlite")
    try:scope_ids={r[0] for r in scope_conn.execute("SELECT molecule_id FROM fixture_scope").fetchall()}
    finally:scope_conn.close()
    atomic(root/"signals"/(n+".node_ready"),{"actual_node":n,"workers":workers,"job_id":os.environ.get("SLURM_JOB_ID")})
    wait_paths([root/"signals"/(x+".node_ready") for x in nodes],min(deadlines,time.monotonic()+180))
    versions=(("R11",a.runner11,75),("R12",a.runner12,240))
    for version,path,seconds in versions:
        if version=="R12":
            done=[root/"signals"/(x+".R11.done") for x in nodes]
            wait_paths(done,deadlines)
            if n=="compute-0-17":
                prepare(root)
                for cache in root.glob("fixture.sqlite.first5_health*"):
                    if cache.is_file():cache.rename(cache.with_name(cache.name+".R11.saved"))
                private_stop=root/"STOP_NEW_MOLECULES.json"
                if private_stop.exists():private_stop.rename(root/"R11.private_STOP.json")
                mod=runtime(path,root)
                if not hasattr(mod,"bootstrap_metadata"):raise ValueError("R12_EXPLICIT_BOOTSTRAP_MISSING")
                started=time.monotonic();mod.bootstrap_metadata(root/"fixture.sqlite",deadline=deadlines)
                atomic(root/"signals"/"R12.bootstrap.ready",{"runner":str(path),"sha256":digest(path),
                    "elapsed_seconds":time.monotonic()-started})
            wait_paths([root/"signals"/"R12.bootstrap.ready"],deadlines)
        scenarios=("main","none") if version=="R11" else ("main","none","rare")
        for scenario in scenarios:
            wait_paths([root/"signals"/(x+"."+version+"."+("main" if scenario=="none" else "none")+".done") for x in nodes],
                deadlines) if scenario!="main" else None
            if scenario=="none":
                if n=="compute-0-17":
                    c=conn(root/"fixture.sqlite")
                    try:sqltx(c,lambda:c.execute("UPDATE tasks SET state='RUNNING'"))
                    finally:c.close()
                    atomic(root/"signals"/(version+".none.ready"),{"eligible_molecules":0})
                wait_paths([root/"signals"/(version+".none.ready")],deadlines)
            if scenario=="rare":
                if n=="compute-0-17":
                    c=conn(root/"fixture.sqlite")
                    try:sqltx(c,lambda:c.execute("UPDATE tasks SET state='CLOSED' WHERE task_id LIKE ?",(PREFIX+"RARE:%",)))
                    finally:c.close()
                    atomic(root/"signals"/"R12.rare.ready",{"eligible_molecules":len(nodes)})
                wait_paths([root/"signals"/"R12.rare.ready"],deadlines)
            stage_deadline=min(deadlines,time.monotonic()+(seconds if scenario=="main" else 65))
            context=mp.get_context("spawn");children=[]
            for lane in range(workers):
                payload={"root":str(root),"node":n,"lane":lane,"scenario":scenario,"version":version,
                    "runner":str(path),"deadline":stage_deadline,"claims":manifest["claims_per_writer"],
                    "total_writers":manifest["total_writers"],"scope_ids":scope_ids,"parent_callers":max(1,math.ceil(workers/24))}
                p=context.Process(target=worker,args=(payload,));p.start();children.append(p)
            for p in children:p.join(max(0,stage_deadline-time.monotonic()+3))
            terminated=[]
            for p in children:
                if p.is_alive():p.terminate();p.join(5);terminated.append(p.pid)
            atomic(root/"signals"/(n+"."+version+"."+scenario+".done"),{"actual_workers":workers,
                "actual_pids":[p.pid for p in children],"forced_fixture_metadata_termination":terminated,
                "runner":str(path),"sha256":digest(path),"QM_calls":0,"exitcodes":[p.exitcode for p in children]})
        atomic(root/"signals"/(n+"."+version+".done"),{"status":"BOUNDED_METADATA_STAGES_FINISHED"})
    atomic(root/"node_reports"/(n+".json"),{"schema":"WP5_PRODUCTION_SHAPE_NODE_V1","status":"METADATA_NODE_STAGES_FINISHED",
        "actual_node":n,"workers":workers,"parent_slots":max(1,math.ceil(workers/24)),"QM_calls":0,"job_id":os.environ.get("SLURM_JOB_ID")})
    return {"actual_node":n,"workers":workers}

def verify(a):
    root=private_root(a.fixture);manifest=scope_assert(root,root/"fixture.sqlite");nodes=actual_test_nodes(manifest)
    reports=[json.loads(p.read_text()) for p in (root/"worker_reports").rglob("*.json")]
    stages=[json.loads(p.read_text()) for p in (root/"signals").glob("*.done") if "." in p.name]
    versions={}
    for version in ("R11","R12"):
        subset=[r for r in reports if r["version"]==version]
        ops={}
        for r in subset:
            for name,v in r["operations"].items():
                agg=ops.setdefault(name,{"calls":0,"seconds":0.0,"maximum_seconds":0.0})
                agg["calls"]+=v["calls"];agg["seconds"]+=v["seconds"];agg["maximum_seconds"]=max(agg["maximum_seconds"],v["maximum_seconds"])
        claims=[x for r in subset for x in r["claimed"]]
        versions[version]={"reported_workers":len(subset),"unique_pids":len({r["pid"] for r in subset}),
            "actual_node_writer_pids":{n:len({r["pid"] for r in subset if r["node"]==n and r["scenario"]=="main"}) for n in nodes},
            "claimed_molecules":len(claims),"unique_claimed_molecules":len(set(claims)),
            "errors":[{"node":r["node"],"lane":r["lane"],"scenario":r["scenario"],**e} for r in subset for e in r["errors"]],
            "operations":ops,"retry_stats":{key:sum(r.get("retry_stats",{}).get(key,0) or 0 for r in subset)
                for key in ("statement_busy_retries","transaction_busy_retries","rollback_count","sleep_seconds")}}
    c=conn(root/"fixture.sqlite")
    try:
        selection=rows(c,"SELECT s.rare,m.state,count(*) AS molecules,sum(m.record_count) AS records,"
            "sum(m.receipt_json IS NOT NULL) AS receipts,sum(m.export_json IS NOT NULL) AS exports "
            "FROM molecules m JOIN fixture_scope s USING(molecule_id) GROUP BY s.rare,m.state")
        population=tuple(c.execute("SELECT count(*),sum(record_count) FROM molecules").fetchone())
        attempts=rows(c,"SELECT m.attempt,count(*) AS molecules FROM molecules m JOIN fixture_scope s USING(molecule_id) GROUP BY m.attempt")
        plans={name:[list(r) for r in c.execute("EXPLAIN QUERY PLAN "+sql).fetchall()] for name,sql in {
            "owner":"SELECT molecule_id FROM molecules WHERE owner='TEST' AND receipt_json IS NOT NULL",
            "cleanup_none":"SELECT m.molecule_id FROM molecules m JOIN tasks t USING(task_id) WHERE m.state IN ('PENDING','RETRY_PENDING') AND t.state IN ('CLOSED','DEAD') ORDER BY predicted_seconds DESC,m.molecule_id LIMIT 1"}.items()}
    finally:c.close()
    expected_main=manifest["selected_main_molecules"];expected_all=expected_main+len(nodes)
    complete=sum(r["molecules"] for r in selection if r["state"]=="COMPLETE")
    exported=sum(r["exports"] for r in selection)
    durable=sum(r["receipts"] for r in selection)
    r12=versions["R12"];issues=[]
    if population!=(1220466,11231854):issues.append("FIXTURE_PHYSICAL_POPULATION_CHANGED")
    if r12["errors"]:issues.append("R12_RECORDED_METADATA_ERRORS")
    if r12["claimed_molecules"]!=expected_all or r12["unique_claimed_molecules"]!=expected_all:issues.append("R12_SELECTED_SCOPE_CLAIM_CLOSURE")
    if complete!=expected_all or durable!=expected_all or exported!=expected_all:issues.append("R12_RECEIPT_EXPORT_CLOSURE")
    if any(r["attempt"]!=0 for r in attempts):issues.append("UNEXPECTED_SYNTHETIC_ATTEMPT_INCREMENT")
    for n,count in manifest["writers_by_node"].items():
        if r12["actual_node_writer_pids"][n]!=count:issues.append("ACTUAL_WRITER_PID_COUNT:"+n)
    footprint=disk_bytes(root)
    if footprint>=LIMIT:issues.append("5GB_FIXTURE_LIMIT_EXCEEDED")
    done=json.loads((root/"signals"/"R12.bootstrap.ready").read_text())
    result={"schema":"WP5_PRODUCTION_SHAPE_METADATA_RESULT_V1",
        "status":"PRODUCTION_SHAPE_METADATA_PASS" if not issues else "PRODUCTION_SHAPE_METADATA_NOT_PASS",
        "issues":issues,"backup_manifest":{"path":str(root/"backup_manifest.json"),"sha256":digest(root/"backup_manifest.json")},
        "R12_bootstrap":done,"versions":versions,"physical_population":population,"selected_scope_states":selection,
        "selected_scope_attempts":attempts,"actual_workers":manifest["total_writers"],"actual_test_nodes":list(nodes),"actual_test_node_count":len(nodes),"harness_version":2,"parent_slots":sum(max(1,math.ceil(w/24)) for w in manifest["writers_by_node"].values()),
        "expected_main_metadata_completions":expected_main,"expected_rare_metadata_completions":len(nodes),"fixture_bytes":footprint,
        "query_plans":plans,"scope":"Production-shaped METADATA only; no QM, no real scientific attempt or raw/archive IO.",
        "production_writes":0,"QM_calls":0,"scientific_attempts_consumed":0,
        "evidence_retained":True,"cleanup":"Root may delete this one exact private clone after report acceptance; reports/manifests/source evidence are retained."}
    atomic(root/"report.json",result)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("mode",choices=("backup","node","verify"))
    p.add_argument("--fixture",required=True);p.add_argument("--source",default=str(ROOT/"queue"/"pending.sqlite"))
    p.add_argument("--baseline",default=str(ROOT/"configs"/"pilot_success_baseline.json"))
    p.add_argument("--writers-json");p.add_argument("--claims",type=int,default=12)
    p.add_argument("--backup-seconds",type=int,default=240);p.add_argument("--total-seconds",type=int,default=1100)
    p.add_argument("--runner11",default=str(ROOT/"scripts"/"wp5_runner_v11.py"))
    p.add_argument("--runner12",default=str(ROOT/"scripts"/"wp5_runner_v12_candidate.py"))
    p.add_argument("--workers",type=int,default=24);a=p.parse_args()
    if int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<16:raise RuntimeError("SLURM_AT_LEAST16_CPU_REQUIRED")
    result={"backup":backup,"node":node,"verify":verify}[a.mode](a)
    print(json.dumps({"status":result.get("status","FINISHED"),"fixture":a.fixture},allow_nan=False))
    if result.get("status","").endswith("NOT_PASS"):raise SystemExit(2)
if __name__=="__main__":main()
