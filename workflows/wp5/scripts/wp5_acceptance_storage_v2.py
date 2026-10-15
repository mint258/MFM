"""WP5 acceptance scratch and file layout evidence. Read-only; never deletes files."""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,json,os,socket,time
from pathlib import Path
from wp5_acceptance_catalog import ROOT,sha,publish,require_slurm,jobmap_rows
def inspect(path):
    path=Path(path);files=0;size=0
    for root,dirs,names in os.walk(path):
        for name in names:
            item=Path(root)/name
            if item.is_file():files+=1;size+=item.stat().st_size
    return {"path":str(path),"files":files,"bytes":size,"worker_pid":os.getpid()}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--jobmap",type=Path);p.add_argument("--runtime",type=Path,default=ROOT/"runtime")
    p.add_argument("--node-authority",type=Path,default=ROOT/"gates/wp5_node_replacement_user_approved.json")
    p.add_argument("--scratch-root",type=Path,default=Path("/tmp"));p.add_argument("--scope",choices=("node","shared"),default="node")
    p.add_argument("--workers",type=int,default=24);p.add_argument("--out",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("ACCEPTANCE_STORAGE_AST_PASS_READONLY");return
    require_slurm(a.workers)
    if not a.jobmap:raise ValueError("Final actual jobmap required")
    if sha(a.node_authority)!="32b0ba7355603c697ac0b2083d090d60fe924eb4d23f7128f451735cf6909d3f":raise ValueError("ACTUAL_CURRENT_NODE_AUTHORITY_CHANGED")
    node=socket.gethostname().split(".")[0];jobs=jobmap_rows(json.loads(a.jobmap.read_text()));started=time.monotonic()
    own={job for job,entry in jobs.items() if entry["node"]==node}
    out=a.out or ROOT/"acceptance"/("storage_"+a.scope+"_"+node+"_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
    issues=[];details=[]
    if a.scope=="node":
        if node not in {"compute-0-"+str(n) for n in (12,13,14,17,18,19)}:raise ValueError("Exact six authorized nodes required")
        expected_prefixes=tuple("wp5runtime_"+str(os.getuid())+"_"+job+"_" for job in own)
        local=list(a.scratch_root.iterdir())
        formal=[item for item in local if item.is_dir() and item.name.startswith(expected_prefixes)] if expected_prefixes else []
        other=[str(item) for item in local if item.is_dir() and item.name.startswith("wp5runtime_"+str(os.getuid())+"_") and item not in formal]
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:details=list(pool.map(inspect,formal))
        if details:issues.append({"issue":"FORMAL_LOCAL_SCRATCH_REMAINS","directories":len(details),"bytes":sum(item["bytes"] for item in details)})
        report={"stage":"WP5_ACCEPTANCE_NODE_SCRATCH","node":node,"formal_jobs":sorted(own),"checked_scratch_root":str(a.scratch_root),"remaining_formal_directories":details,
            "other_same_uid_wp5_directories":other,"other_directory_policy":"Report separately; no permission to delete historical/other jobs. No directory was removed."}
    else:
        raw_names={"input.out","input.aux","input.mop","process.out","xtbout.json","fod.pop","charges","wbo","gradient","xtbtopo.mol","xtbrestart","xtbopt.xyz"}
        counter=collections.Counter();size=collections.Counter();standalone=[];temporary=[];cleanup_evidence=[]
        for item in sorted(a.runtime.glob("**/*")):
            if not item.is_file():continue
            label="parquet" if item.suffix==".parquet" else "archive" if item.name=="raw_archive.sqlite" else "metadata_or_log"
            counter[label]+=1;size[label]+=item.stat().st_size
            if item.name in raw_names:standalone.append({"path":str(item),"bytes":item.stat().st_size})
            if item.name.endswith(".pending") or "temporary_lanes" in item.parts:temporary.append({"path":str(item),"bytes":item.stat().st_size})
            if item.name=="completion.json":
                result=json.loads(item.read_text())
                cleanup_evidence.append({"path":str(item),"sha256":sha(item),"job_id":result["job_id"],"node":result["node"],"scratch_clean":result.get("scratch_clean"),
                    "worker_cleanup":[worker.get("cleanup") for worker in result.get("workers",[])]})
                if result.get("scratch_clean") is not True:issues.append({"issue":"RUNNER_SCRATCH_CLEAN_NOT_CONFIRMED","job_id":result["job_id"],"path":str(item)})
        if standalone:issues.append({"issue":"STANDALONE_PER_CALC_RUNTIME_FILES_REMAIN","files":len(standalone)})
        if temporary:issues.append({"issue":"UNRETIRED_RUNTIME_TEMPORARIES","files":len(temporary)})
        report={"stage":"WP5_ACCEPTANCE_SHARED_FILE_LAYOUT","runtime":str(a.runtime),"file_counts":dict(counter),"bytes_by_class":dict(size),"standalone_calculation_files":standalone,
            "temporary_files":temporary,"runner_cleanup_evidence":cleanup_evidence,"historical_failure_evidence_policy":"Only formal runtime is checked for temporary closure. Historical gates/G6 failures/source files are preserved and never deleted."}
    report.update(status="PASS" if not issues else "NOT_PASS",issues=issues,seconds=time.monotonic()-started,original_data_written=False,files_deleted=0,
        bindings={"jobmap_sha256":sha(a.jobmap),"node_authority_sha256":sha(a.node_authority),"script_sha256":sha(__file__)})
    publish(out/"storage_report.json",report);print(json.dumps({"report":str(out/"storage_report.json"),"status":report["status"]}))
    if report["status"]!="PASS":raise SystemExit(2)
if __name__=="__main__":main()
