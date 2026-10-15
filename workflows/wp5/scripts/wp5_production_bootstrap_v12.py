"""Actual R12 production metadata bootstrap; Root executes only after all229 closure."""
from __future__ import annotations
import argparse, ast, concurrent.futures, hashlib, json, multiprocessing as mp
import os, socket, time, uuid
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
RUNNER=ROOT/"scripts/wp5_runner_v12.py"
RUNNER_SHA="91ec1ce7bf82589b647db43502bc86f9bb2c7c0a98a845ef28446703cc48d278"
QUEUE=ROOT/"queue/pending.sqlite"
_BARRIER=None

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(4<<20),b""):h.update(block)
    return h.hexdigest()

def read_frozen(path,sha):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError("ACTUAL_EVIDENCE_SHA_DIFFERS:"+str(path))
    return json.loads(raw)

def ref(path):
    return {"path":str(path),"sha256":digest(path)}

def write_once(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError("NEW_IMMUTABLE_BOOTSTRAP_REPORT_REQUIRED")
    temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".pending")
    with temporary.open("x") as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write("\n");f.flush();os.fsync(f.fileno())
    try:os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def initialize(barrier):
    global _BARRIER
    _BARRIER=barrier

def verify_sources(batch):
    _BARRIER.wait(timeout=120)
    for item in batch:
        if digest(item["path"])!=item["sha256"]:raise ValueError("CONTRACT_SOURCE_SHA_DIFFERS:"+item["path"])
    return {"pid":os.getpid(),"sources":len(batch)}

def validate_reconciliation(path,sha,prior_refs):
    report=read_frozen(path,sha)
    if report.get("schema")!="WP5_TERMINAL_SUBSET_RECONCILIATION_APPLY_V3" or report.get("status")!="APPLIED_AND_VERIFIED":
        raise ValueError("ACTUAL_FULL229_RECONCILIATION_REQUIRED")
    for key in ("all_registered_jobs_terminal","plan_was_all229_terminal","full229_terminal_scope_verified","all_applied_rows_verified"):
        if report.get(key) is not True:raise ValueError("PARTIAL_RECONCILIATION_NOT_VALID:"+key)
    if report.get("plan_skipped_count")!=0 or report.get("protected_jobs")!={} or report.get("protected_tasks")!=[] or report.get("prior_submissions")!=prior_refs:
        raise ValueError("ALL229_PROTECTED_SCOPE_OR_PRIOR_BINDING_DIFFERS")
    plan=read_frozen(report["plan"]["path"],report["plan"]["sha256"])
    if plan.get("protected_jobs")!={}:raise ValueError("RECONCILIATION_PLAN_WAS_PARTIAL")
    return {"path":str(path),"sha256":sha}

def execute(a):
    job=os.environ.get("SLURM_JOB_ID");node=socket.gethostname().split(".")[0]
    if not job or os.getuid()!=1278 or node not in {"compute-0-"+str(n) for n in (12,13,14,17,18,19)} or a.workers<16 or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<a.workers:
        raise ValueError("AUTHORIZED_ROOT_16PLUS_WORKER_SLURM_ALLOCATION_REQUIRED")
    started=time.monotonic();deadline=started+46*3600
    from wp5_submit_formal_v12 import prior_submission_bindings,fresh_all_prior_terminal
    prior_refs,prior_ids,_=prior_submission_bindings()
    prepared_path=ROOT/"submission/recovery_attempt_v12/prepared_plan_v12.json"
    prepared=read_frozen(prepared_path,a.prepared_sha256)
    contract_path=ROOT/"configs/production_contract_v5.json"
    contract=read_frozen(contract_path,a.contract_sha256)
    contract_ref={"path":str(contract_path),"sha256":a.contract_sha256}
    if prepared.get("version")!=12 or prepared.get("status")!="PREPARED_NOT_SUBMITTED" or prepared.get("production_contract")!=contract_ref:
        raise ValueError("ACTUAL_PREPARED12_CONTRACT5_REQUIRED")
    if prepared.get("prior_submissions")!=prior_refs or prepared.get("prior_job_ids")!=prior_ids:
        raise ValueError("ACTUAL_PREPARED12_ALL229_BINDINGS_DIFFER")
    terminal=fresh_all_prior_terminal(prepared)
    reconciliation=validate_reconciliation(a.reconciliation_report,a.reconciliation_sha256,prior_refs)
    runner_ref=contract["current_runtime"]["wp5_runner_v12.py"]
    if runner_ref!={"path":str(RUNNER),"sha256":RUNNER_SHA} or digest(RUNNER)!=RUNNER_SHA:
        raise ValueError("EXACT_FROZEN_CANDIDATE5_RUNNER12_REQUIRED")
    batches=[contract["sources"][i::a.workers] for i in range(a.workers)]
    if any(not batch for batch in batches):raise ValueError("EFFECTIVE_WORKER_SOURCE_SHARDS_REQUIRED")
    context=mp.get_context("spawn");barrier=context.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context,
        initializer=initialize,initargs=(barrier,)) as pool:
        hashes=list(pool.map(verify_sources,batches,chunksize=1))
    pids={row["pid"] for row in hashes}
    if len(pids)!=a.workers:raise ValueError("ACTUAL_EFFECTIVE_SOURCE_VERIFY_WORKERS_NOT_CLOSED")
    # Repeat the lightweight scheduler proof immediately before touching metadata.
    terminal=fresh_all_prior_terminal(prepared)
    import wp5_runner_v12 as runtime
    if runtime.SQL_LOCK_BUDGET_SECONDS!=600.0:raise ValueError("REAL_METADATA_WAIT_BUDGET_NOT600")
    result=runtime.bootstrap_metadata(QUEUE,deadline=deadline)
    expected_tables={"export_repairs","meta","molecules","sessions","tasks"}
    expected_indices={"pending_order","completion_order","owner_state_order","cleanup_pending_cost","cleanup_task_pending_cost"}
    if result.get("status")!="SCHEMA_READY_READ_ONLY" or result.get("path")!=str(QUEUE) or result.get("bootstrap_explicit") is not True or not expected_tables<=set(result.get("tables",[])) or not expected_indices<=set(result.get("indices",[])):
        raise ValueError("ACTUAL_BOOTSTRAP_SCHEMA_RESULT_NOT_CLOSED")
    support=result.get("summary_index_support",{})
    if not support.get("state_record_count_covering_index") or not support.get("durable_receipt_partial_index"):
        raise ValueError("ACTUAL_BOOTSTRAP_NARROW_SUMMARY_SUPPORT_MISSING")
    output=a.output or ROOT/"gates/R12_production_bootstrap"/("job_"+job)/"report.json"
    report={"schema":"WP5_R12_PRODUCTION_BOOTSTRAP_V1","status":"BOOTSTRAP_SCHEMA_VERIFIED",
        "queue_path":str(QUEUE),"runner":runner_ref,"contract":contract_ref,"uid":os.getuid(),
        "node":node,"time":time.time(),"job_id":job,"source":ref(Path(__file__).resolve()),
        "result":result,"sql_lock_budget_seconds":600.0,"prior_submissions":prior_refs,
        "all_registered_jobs_terminal":True,"prior_terminal_snapshot":terminal,
        "queue_reconciliation_report":reconciliation,"prepared_plan":ref(prepared_path),
        "effective_worker_count":len(pids),"worker_source_verification":hashes,
        "elapsed_seconds":time.monotonic()-started,"internal_deadline_hours":46,
        "QM_calls":0,"scientific_attempts_consumed":0,"scientific_values_modified":False,
        "scope":"Only explicit production metadata schema/index bootstrap; no claims/QM and no G0/user authority/submission."}
    write_once(output,report)
    print(json.dumps({"status":report["status"],"report":ref(output),"actual_workers":len(pids)}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--check",action="store_true")
    p.add_argument("--contract-sha256");p.add_argument("--prepared-sha256")
    p.add_argument("--reconciliation-report",type=Path);p.add_argument("--reconciliation-sha256")
    p.add_argument("--output",type=Path);p.add_argument("--workers",type=int,default=24);a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("BOOTSTRAP_WRAPPER_AST_PASS_NO_QUEUE_NO_SUBMISSION");return
    if not all((a.contract_sha256,a.prepared_sha256,a.reconciliation_report,a.reconciliation_sha256)):
        p.error("Actual contract5/prepared12/full229-reconciliation refs required")
    execute(a)
if __name__=="__main__":main()
