"""Delete only the exact ended run6 private SQLite clone; preserve all evidence."""
from pathlib import Path
import argparse,hashlib,json,os,stat,subprocess,time
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
BASE=ROOT/"gates/metadata_queue_production_shape"
FIXTURE=BASE/"production_shape_r12_v5_20261012_run6_fair_wait_600"
RECEIPT=ROOT/"submission/production_shape_r12_v5_test_v6_fair_wait_600/submitted_jobs.json"
JOBS={str(value) for value in range(4514266,4514273)}
TERMINAL={"COMPLETED","FAILED","CANCELLED","TIMEOUT","OUT_OF_MEMORY","NODE_FAIL","BOOT_FAIL","PREEMPTED","DEADLINE","REVOKED"}
JOURNAL=ROOT/"reports/ended_metadata_fixture_cleanup_v5_run6.json"
def read(path):return json.loads(path.read_text())
def reference(path):
    raw=path.read_bytes();return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
def save(value):
    pending=JOURNAL.with_name(JOURNAL.name+"."+str(os.getpid())+".pending")
    pending.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n");os.replace(pending,JOURNAL)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--check",action="store_true");a=parser.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print("RUN6_CLEANUP_AST_PASS_NO_DELETE_NO_SCHEDULER_QUERY");return
    if os.getuid()!=1278:raise ValueError("EXACT_OWN_UID1278_REQUIRED")
    if FIXTURE.is_symlink() or FIXTURE.parent.resolve()!=BASE.resolve() or FIXTURE.resolve()!=(BASE.resolve()/FIXTURE.name):
        raise ValueError("EXACT_PRIVATE_RUN6_PATH_DIFFERS")
    receipt=read(RECEIPT)
    if (receipt.get("production_writes") is not False or receipt.get("QM") is not False or
        Path(receipt.get("fixture","")).resolve()!=FIXTURE.resolve() or
        {str(row["job_id"]) for row in receipt["jobs"]}!=JOBS):
        raise ValueError("EXACT_RUN6_METADATA_ONLY_SUBMISSION_REQUIRED")
    proof_path=FIXTURE/"report.json";proof=read(proof_path)
    if (proof.get("schema")!="WP5_PRODUCTION_SHAPE_METADATA_RESULT_V1" or
        proof.get("status")!="PRODUCTION_SHAPE_METADATA_PASS" or
        proof.get("QM_calls")!=0 or proof.get("production_writes")!=0 or proof.get("issues")!=[]):
        raise ValueError("ACTUAL_RUN6_PASS_EVIDENCE_REQUIRED")
    queue=subprocess.run(["squeue","-h","-j",",".join(sorted(JOBS)),"-o","%i %u %T"],text=True,capture_output=True,check=True,timeout=60)
    if queue.stdout.strip():raise RuntimeError("RUN6_JOBS_STILL_LIVE:"+queue.stdout)
    accounting=subprocess.run(["sacct","-n","-X","-P","-j",",".join(sorted(JOBS)),
        "--format=JobIDRaw,User,UID,State,AllocCPUS,ElapsedRaw"],text=True,capture_output=True,check=True,timeout=60)
    actual={}
    for line in accounting.stdout.splitlines():
        fields=line.split("|")
        if len(fields)>=6 and fields[0] in JOBS:
            if fields[0] in actual and actual[fields[0]]!=fields:raise ValueError("AMBIGUOUS_RUN6_ACCOUNTING")
            actual[fields[0]]=fields
    if set(actual)!=JOBS:raise ValueError("ACTUAL_ALL7_RUN6_ACCOUNTING_REQUIRED")
    for job,fields in actual.items():
        if fields[1]!="zixiao" or fields[2]!="1278" or fields[3].split()[0].rstrip("+") not in TERMINAL:
            raise ValueError("JOB_OWNER_OR_TERMINAL_STATE_DIFFERS:"+job)
    report={"schema":"WP5_ENDED_OWN_METADATA_FIXTURE_CLEANUP_V5","time":time.time(),"uid":os.getuid(),
        "fixture":str(FIXTURE),"submission":reference(RECEIPT),"run6_PASS_report":reference(proof_path),
        "actual_jobs":actual,"files":[],"status":"VALIDATED_BEFORE_DELETE",
        "scientific_data_deleted":False,"logs_reports_manifests_and_sidecar_lock_preserved":True}
    save(report)
    for name in ("fixture.sqlite","fixture.sqlite-journal","fixture.sqlite-wal","fixture.sqlite-shm"):
        path=FIXTURE/name
        try:info=path.lstat()
        except FileNotFoundError:continue
        if (path.parent.resolve()!=FIXTURE.resolve() or not stat.S_ISREG(info.st_mode) or
            info.st_uid!=1278 or info.st_nlink!=1 or path.resolve()!=FIXTURE.resolve()/name):
            raise ValueError("OWN_EXACT_DATABASE_FILE_GUARD_FAILED:"+str(path))
        row={"path":str(path),"bytes":info.st_size,"uid":info.st_uid,"nlink":info.st_nlink,
             "inode":info.st_ino,"device":info.st_dev,"deleted":False}
        report["files"].append(row);save(report)
        current=path.lstat()
        if (current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns)!=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns):
            raise RuntimeError("DATABASE_CHANGED_AFTER_TERMINAL_GUARD")
        path.unlink();row["deleted"]=True;save(report)
    report["deleted_bytes"]=sum(row["bytes"] for row in report["files"] if row["deleted"])
    report["status"]="OWN_ENDED_RUN6_DATABASES_REMOVED_PASS_EVIDENCE_RETAINED";save(report)
    print(json.dumps({"status":report["status"],"deleted_bytes":report["deleted_bytes"],"journal":str(JOURNAL)}))
if __name__=="__main__":main()
