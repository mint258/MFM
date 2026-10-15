"""Prepare frozen R12 source/inventory ONLY after the actual run5 metadata test PASS."""
from __future__ import annotations
import argparse, ast, copy, getpass, hashlib, json, os, socket, stat, uuid
from pathlib import Path

ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
CANDIDATE=ROOT/"scripts/wp5_runner_v12_candidate_v4.py"
RUNNER=ROOT/"scripts/wp5_runner_v12.py"
CANDIDATE_SHA="6752e2b05d05e17a5eabb14db34785b0bae82562449920f526a104b085d9ba9c"
OLD_INVENTORY=ROOT/"configs/current_code_chain_user_override_v5.json"
OLD_INVENTORY_SHA="aa9d1d311fb98b6a53f9801559cc387f4ca25ee6d2e042c9b5e63585c84985b4"
TEST=ROOT/"gates/metadata_queue_production_shape/production_shape_r12_v4_20261012_run5_fair_kernel_wait/report.json"
BRIDGE=ROOT/"reports/wp5_runner_v12_candidate_v4_ast_bridge.json"
NODES=["compute-0-12","compute-0-14","compute-0-17","compute-0-18","compute-0-19"]
WRITERS=dict(zip(NODES,(80,64,168,64,104)))

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda:stream.read(4<<20),b""):h.update(part)
    return h.hexdigest()

def ref(path,role=None):
    path=Path(path)
    result={"path":str(path),"sha256":digest(path)}
    if role is not None:result.update(role=role,bytes=path.stat().st_size)
    return result

def immutable_json(path,data):
    path=Path(path)
    if path.exists():
        if json.loads(path.read_text())!=data:raise ValueError("IMMUTABLE_NEW_OUTPUT_DIFFERS:"+str(path))
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".pending")
    with temporary.open("x") as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n")
        stream.flush();os.fsync(stream.fileno())
    try:os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def verified_run5(path):
    if Path(path).resolve()!=TEST.resolve():raise ValueError("EXACT_ACTUAL_RUN5_REPORT_REQUIRED")
    raw=Path(path).read_bytes();report=json.loads(raw)
    if report.get("status")!="PRODUCTION_SHAPE_METADATA_PASS" or report.get("issues")!=[]:
        raise ValueError("ACTUAL_RUN5_NOT_PASS_NO_COPY_OR_INVENTORY")
    if report.get("R12_bootstrap",{}).get("sha256")!=CANDIDATE_SHA:
        raise ValueError("ACTUAL_RUN5_TESTED_ANOTHER_CANDIDATE")
    if report.get("actual_test_nodes")!=NODES or report.get("actual_workers")!=480 or report.get("parent_slots")!=22:
        raise ValueError("ACTUAL_FIVE_NODE_480_WRITER_SCOPE_DIFFERS")
    r12=report["versions"]["R12"]
    if r12.get("errors")!=[] or r12.get("configured_retry_budget_seconds")!=[120.0]:
        raise ValueError("ACTUAL_R12_ERROR_OR_NONPRODUCTION_LOCK_BUDGET")
    if r12.get("actual_node_writer_pids")!=WRITERS or r12.get("claimed_molecules")!=5765 or r12.get("unique_claimed_molecules")!=5765:
        raise ValueError("ACTUAL_RUN5_LIFECYCLE_NOT_CLOSED")
    if report.get("QM_calls")!=0 or report.get("production_writes")!=0:
        raise ValueError("ACTUAL_TEST_SCOPE_DIFFERS")
    return report,{"path":str(path),"sha256":hashlib.sha256(raw).hexdigest()}

def freeze_copy():
    raw=CANDIDATE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CANDIDATE_SHA:raise ValueError("CANDIDATE4_SOURCE_CHANGED")
    if RUNNER.exists():
        if RUNNER.read_bytes()!=raw:raise ValueError("PERMANENT_RUNNER12_ALREADY_EXISTS_WITH_DIFFERENT_BYTES")
        return False
    temporary=RUNNER.with_name(RUNNER.name+"."+uuid.uuid4().hex+".pending")
    with temporary.open("xb") as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.chmod(temporary,stat.S_IMODE(CANDIDATE.stat().st_mode))
    try:os.link(temporary,RUNNER)
    finally:temporary.unlink(missing_ok=True)
    if RUNNER.read_bytes()!=raw:raise ValueError("FROZEN_RUNNER12_BYTE_READBACK_DIFFERS")
    return True

def prepare(a):
    if os.getuid()!=1278 or getpass.getuser()!="zixiao":
        raise ValueError("ACTUAL_ZIXIAO_UID1278_REQUIRED")
    # All prerequisites are checked before the only source-copy action.
    report,test_ref=verified_run5(a.test_report)
    if digest(OLD_INVENTORY)!=OLD_INVENTORY_SHA:raise ValueError("PREVIOUS_INVENTORY5_CHANGED")
    previous=json.loads(OLD_INVENTORY.read_text())
    if not isinstance(previous.get("files"),list):raise ValueError("OLD_INVENTORY_FILES_REQUIRED")
    bridge=json.loads(a.ast_bridge.read_text())
    if bridge.get("schema")!="WP5_R12_METADATA_AST_BRIDGE_V1" or bridge.get("status")!="METADATA_ONLY_AST_BRIDGE_PASS" or bridge.get("candidate",{}).get("sha256")!=CANDIDATE_SHA:
        raise ValueError("ACTUAL_CANDIDATE4_AST_BRIDGE_REQUIRED")
    if bridge.get("original",{}).get("sha256")!="e7828b4b78e42cd9a31c686ee30190cc9e788630d9c737980300606aa0236e7b":
        raise ValueError("BRIDGE_ORIGINAL_FROZEN_R11_DIFFERS")
    if a.inventory.resolve()!=(ROOT/"configs/current_code_chain_user_override_v6.json").resolve():
        raise ValueError("INDEPENDENT_NEW_INVENTORY6_PATH_REQUIRED")
    main=ROOT/"scripts/wp5_main_v12.sbatch";submit=ROOT/"scripts/wp5_submit_formal_v12.py"
    if digest(main)!="958819b15a460484a2f8da407fbec43987aeef6525fdc5d669d6b4b1bae9ca81":
        raise ValueError("PREPARED_MAIN12_CHANGED")
    if digest(submit)!="4415cab69706fc99cd90349bc63ec85934295405d4df503f1f6c9af87fc65a14":
        raise ValueError("PREPARED_SUBMIT12_CANDIDATE4_BINDING_CHANGED")
    copied=freeze_copy()
    additions=[
        ref(RUNNER,"current_queue_recovery_code"),ref(main,"current_queue_recovery_code"),
        ref(submit,"current_queue_recovery_code"),ref(CANDIDATE,"tested_queue_metadata_candidate"),
        ref(a.ast_bridge,"actual_metadata_ast_bridge"),ref(a.test_report,"actual_production_shape_metadata_test"),
        ref(ROOT/"scripts/wp5_queue_production_shape_v4.py","actual_metadata_test_harness"),
        ref(ROOT/"scripts/wp5_queue_production_shape_v4.sbatch","actual_metadata_test_harness"),
        ref(ROOT/"scripts/wp5_queue_reconcile_v3.py","current_terminal_reconciliation_code"),
        ref(Path(__file__),"metadata_freeze_preparation_code"),
        ref(ROOT/"scripts/wp5_reproduction_queue_recovery_v12.sbatch","package_build_wrapper")]
    additions.extend(ref(p,"additional_frozen_metadata_source") for p in a.extra_source)
    files=copy.deepcopy(previous["files"]);by_path={entry["path"]:entry for entry in files}
    for entry in additions:
        if entry["path"] in by_path:
            if entry["sha256"]!=by_path[entry["path"]]["sha256"]:raise ValueError("PRIOR_FILE_BINDING_CHANGED:"+entry["path"])
        else:files.append(entry);by_path[entry["path"]]=entry
    if files[:len(previous["files"])]!=previous["files"]:raise ValueError("OLD_INVENTORY_FILES_NOT_EXACTLY_PRESERVED")
    inventory=copy.deepcopy(previous)
    inventory.update(files=files,inventory_version=6,prior_chain=ref(OLD_INVENTORY),
        source_scope="R12 candidate4 queue-only recovery. All inventory5 files preserved; unchanged scientific/IO source AST bridge is actual evidence, not a new QM run.",
        historical_queue_stress_evidence=previous.get("queue_stress_evidence"),
        queue_stress_evidence={**test_ref,"status":report["status"],"scope":"FIVE_ACTUAL_NODES_480_WRITERS_PRODUCTION_SHAPE_METADATA_ONLY"},
        current_metadata_interfaces=copy.deepcopy(previous.get("current_metadata_interfaces",[]))+additions,
        final200_still_required=True,
        freeze_preparation={"candidate":ref(CANDIDATE),"runner":ref(RUNNER),"main":ref(main),"submitter":ref(submit),
          "ast_bridge":ref(a.ast_bridge),"actual_metadata_test":test_ref,"previous_inventory":ref(OLD_INVENTORY),
          "original_files_preserved":len(previous["files"]),"new_QM_calls":0,
          "contract_or_gate_or_authority_generated":False})
    immutable_json(a.inventory,inventory)
    receipt={"schema":"WP5_R12_FREEZE_PREPARATION_V1","status":"R12_SOURCE_AND_INVENTORY_PREPARED",
        "candidate":ref(CANDIDATE),"runner":ref(RUNNER),"main":ref(main),"submitter":ref(submit),
        "inventory":ref(a.inventory),"previous_inventory":ref(OLD_INVENTORY),"actual_metadata_test":test_ref,
        "old_files_preserved":len(previous["files"]),"inventory_files":len(files),
        "scope":"Source/inventory preparation only; no contract, G0, user authority or Slurm submission.",
        "new_QM_calls":0,"queue_opened":False,"production_queue_modified":False,
        "final200_required":True}
    immutable_json(a.receipt,receipt)
    print(json.dumps({"status":receipt["status"],"runner_copied_this_invocation":copied,
        "inventory":receipt["inventory"],"receipt":ref(a.receipt)},allow_nan=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--check",action="store_true")
    p.add_argument("--test-report",type=Path,default=TEST);p.add_argument("--ast-bridge",type=Path,default=BRIDGE)
    p.add_argument("--inventory",type=Path,default=ROOT/"configs/current_code_chain_user_override_v6.json")
    p.add_argument("--receipt",type=Path,default=ROOT/"reports/wp5_r12_freeze_preparation_v1.json")
    p.add_argument("--extra-source",type=Path,action="append",default=[]);a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("FREEZE_PREPARATION_AST_PASS_NO_COPY_NO_GATE_NO_SUBMISSION");return
    prepare(a)
if __name__=="__main__":main()
