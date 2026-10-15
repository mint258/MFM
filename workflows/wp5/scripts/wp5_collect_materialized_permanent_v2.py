#!/usr/bin/env python3
"""Read-only, manifest-scoped materialized permanent byte snapshot; no data hashing."""
import argparse
import ast
import concurrent.futures
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import socket
import stat
import time

ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")

def initialize(worker_pids):
    worker_pids.put(os.getpid())

def fingerprint(info):
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)

def integer(value):
    return isinstance(value,int) and not isinstance(value,bool) and value>=0

def read_closure(path):
    path=Path(path);issues=[];refs=[]
    try:
        before=path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_uid!=1278:
            raise ValueError("CLOSURE_TYPE_OR_OWNER")
        raw=path.read_bytes();data=json.loads(raw)
        if fingerprint(before)!=fingerprint(path.lstat()):
            raise ValueError("CLOSURE_CHANGED_DURING_READ")
        records=data["records"];molecules=data["molecules"]
        if not integer(records) or not integer(molecules):
            raise ValueError("CLOSURE_COUNTS_INVALID")
        families=data["families"];canonical=data["canonical"];archive=data["archive"]
        if not isinstance(families,list) or not isinstance(canonical,dict) or not isinstance(archive,dict):
            raise ValueError("CLOSURE_TOP_LEVEL_REFS_INVALID")
        if sum(ref["rows"] for ref in families if ref["family"]=="base_geometry")!=records:
            raise ValueError("CLOSURE_BASE_ROWS_NOT_CLOSED")
        if sum(ref["rows"] for ref in families if ref["family"] not in {"base_geometry","D20","D3","QC"})!=12*records:
            raise ValueError("CLOSURE_TWELVE_TASK_ROWS_NOT_CLOSED")
        if canonical["rows"]!=12*records or canonical["family"]!="canonical_record_attempts":
            raise ValueError("CLOSURE_CANONICAL_ROWS_NOT_CLOSED")
        if archive.get("molecules")!=molecules or archive.get("scientific_task_outcomes")!=12*records:
            raise ValueError("CLOSURE_ARCHIVE_COUNTS_NOT_CLOSED")
        if archive.get("raw_member_roundtrip_checked") is not True or archive.get("same_execution_join_verified") is not True:
            raise ValueError("CLOSURE_ARCHIVE_READBACK_NOT_CLOSED")
        run_root=path.parent
        selected=[("family_parquet",ref) for ref in families]
        selected += [("canonical_record_attempts",canonical),("raw_archive",archive)]
        for kind,ref in selected:
            target=Path(ref["path"])
            expected=ref["bytes"];sha=ref["sha256"]
            if not target.is_absolute() or not integer(expected) or not isinstance(sha,str) or len(sha)!=64:
                raise ValueError("PERMANENT_REF_INVALID")
            if any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("PERMANENT_DECLARED_SHA_INVALID")
            if kind=="family_parquet":
                relative=target.relative_to(run_root/"parquet")
                if len(relative.parts)!=2 or not relative.parts[0].startswith("group_") or target.suffix!=".parquet":
                    raise ValueError("FAMILY_PERMANENT_PATH_INVALID")
                if ref.get("float64_exact_readback") is not True:
                    raise ValueError("FAMILY_READBACK_NOT_CLOSED")
            elif target != run_root/("raw_archive.sqlite" if kind=="raw_archive" else "canonical_record_attempts.parquet"):
                raise ValueError("PERMANENT_TOP_LEVEL_PATH_INVALID")
            row={"path":str(target),"bytes":expected,"sha256":sha,"kind":kind,
                 "family":ref.get("family"),"rows":ref.get("rows"),"closure":str(path)}
            if kind=="raw_archive":
                for field in ("raw_records","molecules","completed_SCI_retained_raw_calls","partial_attempt_retained_raw_calls"):
                    row[field]=ref.get(field)
            refs.append(row)
        evidence={"path":str(path),"sha256":hashlib.sha256(raw).hexdigest(),
                  "bytes":len(raw),"mtime_ns":before.st_mtime_ns,"records":records,"molecules":molecules}
        return {"closure":evidence,"refs":refs,"issues":issues,"pid":os.getpid()}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return {"closure":{"path":str(path)},"refs":[],"issues":[{"path":str(path),"reason":str(exc)}],"pid":os.getpid()}

def inspect_ref(ref):
    row=dict(ref)
    try:
        path=Path(row["path"]);info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=1278:
            raise ValueError("PERMANENT_TYPE_OR_OWNER")
        if path.resolve(strict=True)!=path:
            raise ValueError("PERMANENT_PATH_RESOLVES_ELSEWHERE")
        if info.st_size!=row["bytes"]:
            raise ValueError("PERMANENT_BYTES_DIFFER_FROM_CLOSED_REF")
        if fingerprint(info)!=fingerprint(path.lstat()):
            raise ValueError("PERMANENT_STAT_CHANGED")
        row.update(actual_bytes=info.st_size,owner_uid=info.st_uid,nlink=info.st_nlink,
                   device=info.st_dev,inode=info.st_ino,mtime_ns=info.st_mtime_ns,
                   allocated_bytes=(info.st_blocks*512 if hasattr(info,"st_blocks") else None),
                   materialized_verified=True)
        return {"ref":row,"issue":None,"pid":os.getpid()}
    except (OSError,ValueError) as exc:
        return {"ref":row,"issue":{"path":row["path"],"reason":str(exc)},"pid":os.getpid()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root",type=Path,default=ROOT/"runtime")
    parser.add_argument("--closure-list",type=Path,help="Optional newline-separated exact export_completion.json paths")
    parser.add_argument("--output",type=Path,required=False)
    parser.add_argument("--workers",type=int,default=16)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text(encoding="utf-8"));print("AST_CHECK_PASS");return
    host=socket.gethostname().split(".")[0]
    if not host.startswith("compute-"):
        raise RuntimeError("Run metadata collection on a compute node, never login")
    if os.getuid()!=1278 or not 16<=args.workers<=24:
        raise RuntimeError("Expected UID1278 and 16-24 metadata worker processes")
    runtime=args.runtime_root.resolve(strict=True)
    if runtime!=ROOT/"runtime":
        raise ValueError("Only this WP5 formal runtime directory is in scope")
    if args.output is None:
        raise ValueError("--output is required; use a fresh report path")
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite an existing snapshot")
    started=time.time()
    if args.closure_list:
        closures=sorted({Path(line.strip()) for line in args.closure_list.read_text().splitlines() if line.strip()})
    else:
        closures=sorted(runtime.glob("task_*/job_*/export_completion.json"))
    for path in closures:
        relative=path.relative_to(runtime)
        if len(relative.parts)!=3 or not relative.parts[0].startswith("task_") or not relative.parts[1].startswith("job_") or relative.parts[2]!="export_completion.json":
            raise ValueError("Closure enumeration left exact formal runtime scope")
    issues=[];closed=[];unique={};checked=[];worker_pids=[]
    if closures:
        context=multiprocessing.get_context("spawn");pid_queue=context.Queue()
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,
                 initializer=initialize,initargs=(pid_queue,)) as pool:
            results=list(pool.map(read_closure,map(str,closures),chunksize=1))
            worker_pids=sorted(pid_queue.get(timeout=30) for _ in range(args.workers))
            for result in results:
                issues.extend(result["issues"])
                if result["issues"]:continue
                closed.append(result["closure"])
                for ref in result["refs"]:
                    old=unique.get(ref["path"])
                    if old:
                        if (old["bytes"],old["sha256"],old["kind"],old["family"]) != (ref["bytes"],ref["sha256"],ref["kind"],ref["family"]):
                            issues.append({"path":ref["path"],"reason":"CONFLICTING_CLOSED_PERMANENT_REFS"})
                        old["closures"].append(ref["closure"])
                    else:
                        unique[ref["path"]]={key:value for key,value in ref.items() if key!="closure"} | {"closures":[ref["closure"]]}
            for result in pool.map(inspect_ref,unique.values(),chunksize=1):
                if result["issue"]:issues.append(result["issue"])
                else:checked.append(result["ref"])
        pid_queue.close();pid_queue.join_thread()
    by_kind={}
    for ref in checked:
        key=ref["kind"] if ref["kind"]!="family_parquet" else "family:"+str(ref["family"])
        item=by_kind.setdefault(key,{"files":0,"bytes":0})
        item["files"]+=1;item["bytes"]+=ref["actual_bytes"]
    report={"schema":"WP5_MATERIALIZED_PERMANENT_BYTES_V2",
        "status":"MATERIALIZED_PERMANENT_SNAPSHOT_CLOSED" if closures and not issues else "MATERIALIZED_PERMANENT_SNAPSHOT_INCOMPLETE",
        "time":time.time(),"started_epoch":started,"seconds":time.time()-started,"node":host,"uid":os.getuid(),
        "workers_requested":args.workers,"actual_worker_pids":worker_pids,
        "runtime_root":str(runtime),"closure_manifests_enumerated":len(closures),"roots_closed":len(closed),
        "unique_permanent_refs_declared":len(unique),"unique_permanent_files":len(checked),
        "declared_permanent_bytes":sum(ref["bytes"] for ref in unique.values()),
        "permanent_bytes":sum(ref["actual_bytes"] for ref in checked),"by_kind":by_kind,
        "issues":issues,"missing":[row for row in issues if "No such file" in row["reason"]],
        "closed_roots":closed,"refs":sorted(checked,key=lambda row:row["path"]),
        "scope":"Actual physical permanent files from immutable export closure manifests across all attempts; not final logical population or remaining budget.",
        "exclusions":["temporary_lanes","SCI compressed staging","*.pending","failed_consolidation_*","unclosed outputs and retained-raw containers without export closure"],
        "data_sha_rehashed":False,"closure_sha_measured":True,"queue_opened":False,"original_data_written":False,"QM_calls":0,"LMDB_opened":False,
        "deduplication":"Unique absolute permanent path; archive.source_paths are never traversed. Stat sizes are logical bytes; existing manifest SHA is provenance, not a fresh data integrity check."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n")
    print(json.dumps({key:report[key] for key in ("status","roots_closed","unique_permanent_files","permanent_bytes","issues")}))
    if issues:raise SystemExit(1)

if __name__=="__main__":main()
