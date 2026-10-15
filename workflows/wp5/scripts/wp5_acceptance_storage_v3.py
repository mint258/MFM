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

NODES={"compute-0-"+str(n) for n in (12,13,14,17,18,19)}
def validate_node_report_docs(documents,jobs,jobmap_sha,authority_sha,producer_sha):
    if len(documents)!=6:raise ValueError("EXACT_SIX_CURRENT_NODE_REPORTS_REQUIRED")
    result={}
    for report in documents:
        node=report.get("node")
        if node not in NODES or node in result:raise ValueError("NODE_REPORT_DUPLICATE_OR_OUTSIDE_SCOPE")
        if report.get("schema")!="WP5_ACCEPTANCE_STORAGE_V3" or report.get("stage")!="WP5_ACCEPTANCE_NODE_SCRATCH" or report.get("status")!="PASS":raise ValueError("ACTUAL_NODE_SCRATCH_PASS_REQUIRED")
        if report.get("uid")!=1278 or report.get("hostname","").split(".")[0]!=node or not str(report.get("slurm_job_id","")).isdigit():raise ValueError("ACTUAL_NODE_HOST_UID_SLURM_ID_REQUIRED")
        expected={job for job,row in jobs.items() if row["node"]==node}
        if set(report.get("formal_jobs",[]))!=expected:raise ValueError("NODE_JOB_COVERAGE_DIFFERS")
        if report.get("checked_scratch_root")!="/tmp" or report.get("actual_scratch_empty") is not True or report.get("remaining_formal_directories")!=[] or report.get("issues")!=[] or report.get("files_deleted")!=0:raise ValueError("ACTUAL_NODE_SCRATCH_NOT_EMPTY")
        bindings=report.get("bindings",{})
        if bindings.get("jobmap_sha256")!=jobmap_sha or bindings.get("node_authority_sha256")!=authority_sha or bindings.get("script_sha256")!=producer_sha:raise ValueError("NODE_REPORT_JOBMAP_AUTHORITY_PRODUCER_DIFFERS")
        result[node]=report
    if set(result)!=NODES:raise ValueError("SIX_NODE_REPORTS_NOT_CLOSED")
    return result

def private_check():
    jobs={str(i):{"node":node} for i,node in enumerate(sorted(NODES))}
    documents=[]
    for i,node in enumerate(sorted(NODES)):
        documents.append({"schema":"WP5_ACCEPTANCE_STORAGE_V3","stage":"WP5_ACCEPTANCE_NODE_SCRATCH",
          "status":"PASS","uid":1278,"hostname":node,"node":node,"slurm_job_id":str(900+i),
          "formal_jobs":[str(i)],"checked_scratch_root":"/tmp","actual_scratch_empty":True,
          "remaining_formal_directories":[],"issues":[],"files_deleted":0,
          "bindings":{"jobmap_sha256":"j","node_authority_sha256":"a","script_sha256":"s"}})
    assert set(validate_node_report_docs(documents,jobs,"j","a","s"))==NODES
    for case,change in (("wrong_jobmap",lambda d:d[0]["bindings"].update(jobmap_sha256="other")),
                        ("nonempty_scratch",lambda d:d[0].update(remaining_formal_directories=[{"path":"private"}])),
                        ("missing_actual_hostname",lambda d:d[0].update(hostname="other")),
                        ("wrong_slurm_id",lambda d:d[0].update(slurm_job_id=None))):
        trial=json.loads(json.dumps(documents));change(trial)
        try:validate_node_report_docs(trial,jobs,"j","a","s");raise AssertionError(case+" accepted")
        except ValueError:pass
    try:validate_node_report_docs(documents[:-1],jobs,"j","a","s");raise AssertionError("five reports accepted")
    except ValueError:pass
    print(json.dumps({"status":"STORAGE_V3_PRIVATE_NODE_EVIDENCE_RULES_PASS","valid_six_node_reports":6,
       "wrong_jobmap_nonempty_hostname_slurm_and_missing_node_rejected":True,
       "actual_nodes_or_scratch_inspected":False,"SCI_read":False,"files_deleted":0}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--jobmap",type=Path);p.add_argument("--runtime",type=Path,default=ROOT/"runtime")
    p.add_argument("--node-authority",type=Path,default=ROOT/"gates/wp5_node_replacement_user_approved.json")
    p.add_argument("--scratch-root",type=Path,default=Path("/tmp"));p.add_argument("--scope",choices=("node","shared"),default="node")
    p.add_argument("--node-storage-reports",type=Path,nargs="*");p.add_argument("--workers",type=int,default=24);p.add_argument("--out",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());private_check();return
    require_slurm(a.workers)
    if not a.jobmap:raise ValueError("Final actual jobmap required")
    if sha(a.node_authority)!="32b0ba7355603c697ac0b2083d090d60fe924eb4d23f7128f451735cf6909d3f":raise ValueError("ACTUAL_CURRENT_NODE_AUTHORITY_CHANGED")
    node=socket.gethostname().split(".")[0];jobs=jobmap_rows(json.loads(a.jobmap.read_text()));started=time.monotonic()
    own={job for job,entry in jobs.items() if entry["node"]==node}
    out=a.out or ROOT/"acceptance"/("storage_"+a.scope+"_"+node+"_"+os.environ["SLURM_JOB_ID"]);out.mkdir(parents=True,exist_ok=False)
    issues=[];details=[];node_report_refs=[];node_proofs={};historical_scratch_statements=[]
    if a.scope=="node":
        if node not in {"compute-0-"+str(n) for n in (12,13,14,17,18,19)}:raise ValueError("Exact six authorized nodes required")
        expected_prefixes=tuple("wp5runtime_"+str(os.getuid())+"_"+job+"_" for job in own)
        local=list(a.scratch_root.iterdir())
        formal=[item for item in local if item.is_dir() and item.name.startswith(expected_prefixes)] if expected_prefixes else []
        other=[str(item) for item in local if item.is_dir() and item.name.startswith("wp5runtime_"+str(os.getuid())+"_") and item not in formal]
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:details=list(pool.map(inspect,formal))
        if details:issues.append({"issue":"FORMAL_LOCAL_SCRATCH_REMAINS","directories":len(details),"bytes":sum(item["bytes"] for item in details)})
        report={"actual_scratch_empty":not bool(formal),"stage":"WP5_ACCEPTANCE_NODE_SCRATCH","node":node,"formal_jobs":sorted(own),"checked_scratch_root":str(a.scratch_root),"remaining_formal_directories":details,
            "other_same_uid_wp5_directories":other,"other_directory_policy":"Report separately; no permission to delete historical/other jobs. No directory was removed."}
    else:
        if len(a.node_storage_reports or [])!=6:raise ValueError("Six final actual node report paths required for shared audit")
        node_docs=[]
        for path in a.node_storage_reports:
            document=json.loads(path.read_text());node_docs.append(document);node_report_refs.append({"path":str(path),"sha256":sha(path),"node":document.get("node"),"slurm_job_id":document.get("slurm_job_id")})
        node_proofs=validate_node_report_docs(node_docs,jobs,sha(a.jobmap),sha(a.node_authority),sha(__file__))
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
                if result.get("scratch_clean") is not True:
                    old_job=str(result["job_id"]);old_node=str(result["node"]).split(".")[0]
                    proof=node_proofs.get(old_node)
                    if old_job in jobs and proof and old_job in proof["formal_jobs"]:
                        historical_scratch_statements.append({"path":str(item),"sha256":sha(item),"job_id":old_job,"node":old_node,
                          "original_scratch_clean":result.get("scratch_clean"),"current_state":"ACTUAL_CURRENT_NODE_SCRATCH_EMPTY",
                          "current_node_report":next(ref for ref in node_report_refs if ref["node"]==old_node),"old_statement_rewritten":False})
                    else:issues.append({"issue":"UNMAPPED_HISTORICAL_SCRATCH_STATEMENT","job_id":old_job,"path":str(item)})
        if standalone:issues.append({"issue":"STANDALONE_PER_CALC_RUNTIME_FILES_REMAIN","files":len(standalone)})
        if temporary:issues.append({"issue":"UNRETIRED_RUNTIME_TEMPORARIES","files":len(temporary)})
        report={"stage":"WP5_ACCEPTANCE_SHARED_FILE_LAYOUT","runtime":str(a.runtime),"file_counts":dict(counter),"bytes_by_class":dict(size),"standalone_calculation_files":standalone,
            "temporary_files":temporary,"runner_cleanup_evidence":cleanup_evidence,"historical_failure_evidence_policy":"Only formal runtime is checked for temporary closure. Historical gates/G6 failures/source files are preserved and never deleted."}
    report.update(schema="WP5_ACCEPTANCE_STORAGE_V3",generated_epoch=time.time(),uid=os.getuid(),hostname=socket.gethostname(),slurm_job_id=os.environ["SLURM_JOB_ID"],node_storage_reports=node_report_refs,historical_scratch_statements=historical_scratch_statements,status="PASS" if not issues else "NOT_PASS",issues=issues,seconds=time.monotonic()-started,original_data_written=False,files_deleted=0,
        bindings={"jobmap_sha256":sha(a.jobmap),"node_authority_sha256":sha(a.node_authority),"script_sha256":sha(__file__)})
    publish(out/"storage_report.json",report);print(json.dumps({"report":str(out/"storage_report.json"),"status":report["status"]}))
    if report["status"]!="PASS":raise SystemExit(2)
if __name__=="__main__":main()
