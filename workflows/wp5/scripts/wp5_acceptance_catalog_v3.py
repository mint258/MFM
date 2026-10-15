"""WP5 final latest-attempt catalog. Read-only scientific artifacts; no QM."""
from __future__ import annotations
import argparse,ast,collections,hashlib,json,os,sqlite3,time
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
EXPECTED_RECORDS=11231854;EXPECTED_MOLECULES=1220466
CALCS=("pm7_B","pm7_cation","pm7_anion","pm7_water","pm7_octanol","xtb_singlepoint","xtb_vipea","xtb_vfukui","xtb_ALPB_water","xtb_ALPB_octanol","xtb_fod","xtb_perturbed_gradient")
def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(8<<20),b""):h.update(block)
    return h.hexdigest()
def publish(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError("Acceptance artifact is write-once: "+str(path))
    temporary=path.with_name(path.name+".pending")
    temporary.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+"\n")
    with temporary.open("rb") as stream:os.fsync(stream.fileno())
    temporary.rename(path)
def q(value):return "'"+str(value).replace("'","''")+"'"
def copy(db,sql,path):
    path=Path(path);temporary=path.with_name(path.name+".pending")
    if path.exists():raise FileExistsError(path)
    db.execute("COPY ("+sql+") TO "+q(temporary)+" (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 131072)")
    with temporary.open("rb") as stream:os.fsync(stream.fileno())
    temporary.rename(path)
def require_slurm(workers=24):
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<workers or workers<24:
        raise ValueError("Acceptance requires >=24 allocated/effective Slurm CPUs")
def jobmap_rows(value):
    found={}
    def walk(item):
        if isinstance(item,dict):
            if item.get("job_id") is not None and item.get("node"):
                job=str(item["job_id"])
                if item.get("user") not in (None,"zixiao"):raise ValueError("Non-zixiao jobmap entry")
                found[job]=item
            for child in item.values():walk(child)
        elif isinstance(item,list):
            for child in item:walk(child)
    walk(value);return found

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue",type=Path,default=ROOT/"queue/pending.sqlite")
    ap.add_argument("--plan",type=Path,required=False,help="Final immutable node authority; must match queue plan SHA")
    ap.add_argument("--jobmap",type=Path,required=False)
    ap.add_argument("--runtime",type=Path,default=ROOT/"runtime")
    ap.add_argument("--population",type=Path,default=ROOT/"population/formal_record_index.parquet")
    ap.add_argument("--molecules",type=Path,default=ROOT/"population/molecule_index.parquet")
    ap.add_argument("--out",type=Path)
    ap.add_argument("--threads",type=int,default=24);ap.add_argument("--memory-gb",type=int,default=20)
    ap.add_argument("--allow-incomplete",action="store_true");ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text());assert len(set(CALCS))==12
        print("ACCEPTANCE_CATALOG_AST_PASS_NO_QM_NO_DATA");return
    require_slurm(args.threads)
    if not args.plan or not args.jobmap:raise ValueError("Explicit final --plan and --jobmap authorities required")
    out=args.out or ROOT/"acceptance"/("catalog_"+os.environ["SLURM_JOB_ID"])
    if not out.resolve().is_relative_to(ROOT):raise ValueError("Acceptance writes only inside new WP5 root")
    out.mkdir(parents=True,exist_ok=False)
    spill=Path("/tmp")/("wp5accept_"+str(os.getuid())+"_"+os.environ["SLURM_JOB_ID"])
    spill.mkdir(exist_ok=False)
    import pyarrow as pa,pyarrow.parquet as pq,duckdb
    pa.set_cpu_count(args.threads);pa.set_io_thread_count(8)
    database=sqlite3.connect("file:"+str(args.queue)+"?mode=ro",uri=True);database.row_factory=sqlite3.Row
    database.execute("BEGIN")
    meta=dict(database.execute("SELECT key,value FROM meta"))
    if meta["plan_sha256"]!=sha(args.plan):raise ValueError("Final node authority differs from queue frozen plan")
    jobs=jobmap_rows(json.loads(args.jobmap.read_text()))
    plan=json.loads(args.plan.read_text());tasks={str(row["task_id"]):row for row in plan["tasks"]}
    sessions={row["session_id"]:dict(row) for row in database.execute("SELECT * FROM sessions")}
    artifacts={};canonical=[];issues=[];states=collections.Counter();record_states=collections.Counter()
    def artifact(ref,run=None):
        path=str(Path(ref["path"]))
        if not Path(path).resolve().is_relative_to(ROOT):raise ValueError("Artifact outside WP5 root")
        value={**ref,"path":path}
        if run:value.update(run_root=run["run_root"],job_id=int(run["options"]["job_id"]),session=run["options"]["session"],node=run["node"])
        if Path(path).name=="canonical_record_attempts.parquet":value["family"]="canonical_record_attempts"
        if path in artifacts:
            if artifacts[path]["sha256"]!=value["sha256"] or artifacts[path]["bytes"]!=value["bytes"]:raise ValueError("Conflicting artifact declaration: "+path)
            artifacts[path].update({key:item for key,item in value.items() if key not in artifacts[path]})
        else:artifacts[path]=value
    runs={};runs_by_session={}
    for run_json in sorted(args.runtime.glob("**/run.json")):
        run=json.loads(run_json.read_text());root=run_json.parent;run["run_root"]=str(root);runs[str(root)]=run
        options=run["options"];runs_by_session[options["session"]]=run
        if options.get("plan") and sha(options["plan"])!=meta["plan_sha256"]:issues.append({"run":str(root),"issue":"RUN_TASK_PLAN_SHA_DIFFERS"})
        if str(options["job_id"]) not in jobs:issues.append({"run":str(root),"issue":"JOB_NOT_IN_FINAL_JOBMAP"})
        elif jobs[str(options["job_id"])]["node"]!=run["node"]:issues.append({"run":str(root),"issue":"JOBMAP_ACTUAL_NODE_DIFFERS"})
        for path,key in [(root/"family_exports.json","references"),(root/"export_completion.json","families"),(root/"completion.json","families")]:
            if path.exists():
                data=json.loads(path.read_text())
                for ref in data.get(key,[]):artifact(ref,run)
                for name in ("archive","canonical","canonical_record_attempts"):
                    if data.get(name):artifact(data[name],run)
        index=root/"canonical_record_attempts.parquet"
        if index.exists():
            canonical.append(str(index))
            if str(index) not in artifacts:artifact({"family":"canonical_record_attempts","path":str(index),"bytes":index.stat().st_size,"sha256":sha(index),"rows":pq.ParquetFile(index).metadata.num_rows},run)
    if not canonical:issues.append({"issue":"NO_CANONICAL_ATTEMPT_INDEX"})
    schema=pa.schema([("molecule_id",pa.string()),("owner",pa.string()),("state",pa.string()),("attempt_id",pa.int8()),("job_id",pa.int64()),("task_id",pa.string()),("assigned_task_id",pa.string()),("lane",pa.int16()),("archive_path",pa.string()),("records",pa.int64()),("receipt_context_consistent",pa.bool_()),("export_published",pa.bool_()),("execution_id",pa.string()),("session_task_id",pa.string()),("session_mode",pa.string()),("actual_node",pa.string())])
    temporary=out/"queue_latest_unsorted.parquet";writer=pq.ParquetWriter(temporary,schema,compression="zstd")
    batch=[];exports={};durable_records=0;durable_molecules=0
    try:
        for row in database.execute("SELECT * FROM molecules ORDER BY molecule_id"):
            state=row["state"];states[state]+=1;record_states[state]+=row["record_count"]
            receipt=json.loads(row["receipt_json"]) if row["receipt_json"] else None
            context=receipt.get("context",{}) if receipt else {}
            session=sessions.get(row["owner"],{})
            # Receipt task_id is the original assigned molecule task, including
            # cleanup; its session task_id remains the real cleanup_N identity.
            assigned=str(context.get("task_id"))==str(row["task_id"])
            session_task_valid=session.get("mode")=="cleanup" or (session.get("mode")=="main" and str(session.get("task_id"))==str(row["task_id"]))
            consistent=bool(receipt and context.get("attempt_id")==row["attempt"] and str(context.get("job_id"))==str(session.get("job_id"))
                            and assigned and session_task_valid and context.get("execution_id")
                            and context["execution_id"].startswith(str(row["owner"])+":"))
            published=False
            if row["export_json"]:
                text=row["export_json"]
                if text not in exports:exports[text]=json.loads(text)
                declaration=exports[text]
                if declaration.get("archive"):
                    published=True
                    bound_run=runs_by_session.get(row["owner"])
                    if bound_run is None:issues.append({"molecule_id":row["molecule_id"],"issue":"LATEST_OWNER_RUNTIME_NOT_DISCOVERED"})
                    artifact(declaration["archive"],bound_run)
                    for ref in declaration.get("families",[]):artifact(ref,bound_run)
            authoritative=consistent and published and state in {"COMPLETE","FINAL_FAILURE"}
            if authoritative:durable_records+=row["record_count"];durable_molecules+=1
            elif receipt:issues.append({"molecule_id":row["molecule_id"],"state":state,"issue":"RECEIPT_OR_EXPORT_NOT_AUTHORITATIVE"})
            batch.append({"molecule_id":row["molecule_id"],"owner":row["owner"],"state":state,"attempt_id":row["attempt"],"job_id":context.get("job_id"),"task_id":str(context.get("task_id")) if context.get("task_id") is not None else None,"assigned_task_id":row["task_id"],"lane":context.get("lane"),"archive_path":row["archive_path"],"records":row["record_count"],"receipt_context_consistent":consistent,"export_published":published,"execution_id":context.get("execution_id"),"session_task_id":str(session.get("task_id")) if session.get("task_id") is not None else None,"session_mode":session.get("mode"),"actual_node":runs_by_session.get(row["owner"],{}).get("node")})
            if len(batch)>=8192:writer.write_table(pa.Table.from_pylist(batch,schema=schema));batch=[]
        if batch:writer.write_table(pa.Table.from_pylist(batch,schema=schema))
    finally:writer.close();database.execute("ROLLBACK");database.close()
    db=duckdb.connect();db.execute("SET threads="+str(args.threads));db.execute("SET memory_limit="+q(str(args.memory_gb)+"GB"));db.execute("SET temp_directory="+q(spill))
    copy(db,"SELECT * FROM read_parquet("+q(temporary)+") ORDER BY job_id,molecule_id",out/"latest_molecules.parquet")
    temporary.unlink()
    db.execute("CREATE VIEW population AS SELECT record_id,molecule_id,total_atoms,heavy_atoms,new_role,file_group,member_routine FROM read_parquet("+q(args.population)+")")
    population_counts=db.execute("SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM population").fetchone()
    if population_counts!=(EXPECTED_RECORDS,EXPECTED_RECORDS,EXPECTED_MOLECULES):raise ValueError("FORMAL_POPULATION_MANIFEST_COUNT_MISMATCH")
    db.execute("CREATE VIEW latest_molecules AS SELECT * FROM read_parquet("+q(out/"latest_molecules.parquet")+")")
    canon_sql="read_parquet(["+",".join(q(path) for path in canonical)+"],union_by_name=true)" if canonical else None
    if canonical:
        db.execute("CREATE VIEW history AS SELECT * FROM "+canon_sql)
        history_records=db.execute("SELECT count(*) FROM history").fetchone()[0]
        db.execute("CREATE VIEW selected AS SELECT c.* FROM history c JOIN latest_molecules m ON c.molecule_id=m.molecule_id "
                   "AND c.attempt_id=m.attempt_id AND c.job_id=m.job_id AND c.task_id=m.task_id AND c.archive_path=m.archive_path AND c.raw_execution_id=m.execution_id "
                   "WHERE m.receipt_context_consistent AND m.export_published")
        duplicate=db.execute("SELECT count(*) FROM (SELECT record_id,calc_type FROM selected GROUP BY 1,2 HAVING count(*)!=1)").fetchone()[0]
        extras=db.execute("SELECT count(*) FROM selected c ANTI JOIN population p USING(record_id)").fetchone()[0]
        bad_identity=db.execute("SELECT count(*) FROM selected c JOIN population p USING(record_id) WHERE c.molecule_id!=p.molecule_id OR c.file_group!=p.file_group").fetchone()[0]
        bad_task=db.execute("SELECT count(*) FROM selected WHERE calc_type NOT IN ("+",".join(q(name) for name in CALCS)+") OR calc_type IS NULL").fetchone()[0]
        count=db.execute("SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM selected").fetchone()
        by_task=[dict(zip(("calc_type","rows"),row)) for row in db.execute("SELECT calc_type,count(*) FROM selected GROUP BY 1 ORDER BY 1").fetchall()]
        missing_records=db.execute("SELECT count(*) FROM population p ANTI JOIN (SELECT DISTINCT record_id FROM selected) c USING(record_id)").fetchone()[0]
        if duplicate or extras or bad_identity or bad_task:issues.append({"issue":"CANONICAL_DUPLICATE_EXTRA_IDENTITY_OR_TASK","duplicate_groups":duplicate,"extra_rows":extras,"identity_rows":bad_identity,"invalid_task_rows":bad_task})
        copy(db,"SELECT * FROM selected ORDER BY job_id,task_id,file_group,molecule_id,record_id,calc_type",out/"latest_record_tasks.parquet")
        copy(db,"SELECT p.* FROM population p ANTI JOIN (SELECT DISTINCT record_id FROM selected) c USING(record_id)",out/"missing_record_index.parquet")
    else:history_records=0;count=(0,0,0);by_task=[];missing_records=EXPECTED_RECORDS
    unresolved={state:number for state,number in states.items() if state!="COMPLETE" and number}
    closed=count==(EXPECTED_RECORDS*12,EXPECTED_RECORDS,EXPECTED_MOLECULES) and all(item["rows"]==EXPECTED_RECORDS for item in by_task) and len(by_task)==12 and not issues and not unresolved
    manifest={"stage":"WP5_ACCEPTANCE_LATEST_CATALOG","status":"CLOSED" if closed else "INCOMPLETE_OR_REQUIRES_ACTION",
        "expected_records":EXPECTED_RECORDS,"expected_molecules":EXPECTED_MOLECULES,"expected_record_tasks":EXPECTED_RECORDS*12,
        "canonical_record_tasks":count[0],"canonical_records":count[1],"canonical_molecules":count[2],"missing_records":missing_records,
        "all_historical_attempt_rows":history_records,"historical_attempts_retained":True,
        "queue_states":dict(states),"queue_records_by_state":dict(record_states),"unresolved_queue_states":unresolved,
        "durable_authoritative_records":durable_records,"durable_authoritative_molecules":durable_molecules,
        "by_task":by_task,"issues":issues,"artifacts":list(artifacts.values()),"canonical_indexes":canonical,
        "latest_record_tasks":str(out/"latest_record_tasks.parquet"),"latest_molecules":str(out/"latest_molecules.parquet"),
        "authority":{"plan":str(args.plan),"plan_sha256":sha(args.plan),"queue_plan_sha256":meta["plan_sha256"],"jobmap":str(args.jobmap),"jobmap_sha256":sha(args.jobmap),"population":str(args.population),"population_sha256":sha(args.population),"molecules":str(args.molecules),"molecules_sha256":sha(args.molecules),"script_sha256":sha(__file__)},
        "G5_exception":{"path":str(ROOT/"gates/g5_user_approved_exception.json"),"sha256":sha(ROOT/"gates/g5_user_approved_exception.json") if (ROOT/"gates/g5_user_approved_exception.json").exists() else None},
        "new_QM_calls":0,"original_data_written":False,"threads":args.threads,"memory_limit_gb":args.memory_gb}
    publish(out/"catalog.json",manifest);db.close()
    import shutil;shutil.rmtree(spill)
    print(json.dumps({"catalog":str(out/"catalog.json"),"status":manifest["status"],"canonical_record_tasks":count[0]}))
    if not closed and not args.allow_incomplete:raise SystemExit(2)
if __name__=="__main__":main()
