"""Thin R13 metadata freeze: append-only inventory/package/contract/G4 spec.
Root executes only against actual fixture/AST evidence. No QM/queue/LMDB/submission.
"""
from __future__ import annotations
import argparse,ast,concurrent.futures,copy,hashlib,json,multiprocessing,os,socket,stat,time,uuid
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
OLD_CONTRACT=ROOT/"configs/production_contract_v5.json"
OLD_SHA="a04ee67742ce6ebce095063cd9e69eab311c766b9c76a4cf4c92b66b77c33851"
INVENTORY=ROOT/"configs/current_code_chain_user_override_v7.json"
CONTRACT=ROOT/"configs/production_contract_v6.json"
SPEC=ROOT/"configs/g4_freeze_spec_v14.json"
OLD_SPEC=ROOT/"configs/g4_freeze_spec_v13.json"
OLD_SPEC_SHA="f9b8d54231dd77f3b261243e22c98f4d80ae8a8793f90ccf2fcc7ed79b68be21"
DIRECTIVE=ROOT/"submission/recovery_attempt_v12/user_continue_all_calculations_20261012_v1.json"
RUNNER=ROOT/"scripts/wp5_runner_v13.py"
MAIN=ROOT/"scripts/wp5_main_v13.sbatch"
SUBMIT=ROOT/"scripts/wp5_submit_formal_v13.py"
RUNNER_SHA="258fd76ec1e0bac38db20fc2f3c0c1ef6f107d0d89261860f95b4b73099aed1f"
MAIN_SHA="983db5bd421cee49d1200c36b514498bb4a151d13ed24af44f5aea373867bdf7"
_BARRIER=None

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(4<<20),b""):h.update(block)
    return h.hexdigest()
def ref(path,role=None,expected=None):
    p=Path(path)
    if not p.is_absolute():raise ValueError("ABSOLUTE_SOURCE_REF_REQUIRED:"+str(p))
    if expected and digest(p)!=expected:raise ValueError("ACTUAL_SHA_DIFFERS:"+str(p))
    out={"path":str(p),"sha256":expected or digest(p),"bytes":p.stat().st_size}
    if role:out["role"]=role
    return out
def load(path,expected=None):
    raw=Path(path).read_bytes()
    if expected and hashlib.sha256(raw).hexdigest()!=expected:raise ValueError("ACTUAL_JSON_SHA_DIFFERS:"+str(path))
    return json.loads(raw)
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode()
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError("IMMUTABLE_OUTPUT_DIFFERS:"+str(path))
        return
    pending=path.with_name(path.name+"."+uuid.uuid4().hex+".pending")
    with pending.open("xb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
    try:os.link(pending,path)
    finally:pending.unlink(missing_ok=True)
def original():
    old=load(OLD_CONTRACT,OLD_SHA)
    if old.get("schema")!="WP5_PRODUCTION_CONTRACT_V1" or old.get("status")!="PRODUCTION_CONTRACT_FROZEN" or len(old.get("sources",[]))!=119:
        raise ValueError("ACTUAL_FROZEN119_CONTRACT5_REQUIRED")
    return old
def evidence(fixture_path,bridge_path):
    old=original();fixture=load(fixture_path);bridge=load(bridge_path)
    runner=ref(RUNNER,expected=RUNNER_SHA);main=ref(MAIN,expected=MAIN_SHA)
    previous=old["current_runtime"]["wp5_runner_v12.py"]
    same=lambda actual,expected: isinstance(actual,dict) and (actual.get("path"),actual.get("sha256"))==(expected["path"],expected["sha256"])
    if (bridge.get("schema")!="WP5_R13_METADATA_AST_BRIDGE_V1" or bridge.get("status")!="METADATA_ONLY_AST_BRIDGE_PASS"
        or bridge.get("physics_same") is not True or bridge.get("main_claim_ast_same") is not True or not same(bridge.get("runner12"),previous) or not same(bridge.get("runner13"),runner)):
        raise ValueError("ACTUAL_R13_METADATA_ONLY_AST_BRIDGE_REQUIRED")
    pids=fixture.get("actual_worker_pids",[])
    if (fixture.get("schema")!="WP5_CLEANUP_STATIC_SCOPE_FIXTURE_V1" or fixture.get("status")!="CLEANUP_STATIC_SCOPE_FIXTURE_PASS"
        or fixture.get("issues")!=[] or fixture.get("QM_calls")!=0 or fixture.get("production_queue_written") is not False
        or fixture.get("effective_worker_count")!=16 or len(pids)!=16 or len(set(pids))!=16
        or not same(fixture.get("runner12"),previous) or not same(fixture.get("runner13"),runner)):
        raise ValueError("ACTUAL16_WORKER_R13_SCOPE_FIXTURE_REQUIRED")
    return old,runner,main,ref(fixture_path,"actual_R13_cleanup_scope_fixture"),ref(bridge_path,"actual_R13_metadata_AST_bridge")
def add_unique(files,entry):
    hits=[x for x in files if x["path"]==entry["path"]]
    if hits:
        if len(hits)!=1 or hits[0]["sha256"]!=entry["sha256"]:raise ValueError("OLD_SOURCE_SHA_WOULD_CHANGE:"+entry["path"])
    else:files.append(copy.deepcopy(entry))
def inventory_mode(a):
    old,runner,main,fixture,bridge=evidence(a.fixture_report,a.ast_bridge)
    files=copy.deepcopy(old["sources"])
    entries=[{**runner,"role":"current_R13_queue_metadata_runtime"},{**main,"role":"current_R13_queue_metadata_batch"},
        ref(SUBMIT,"current_R13_formal_submitter"),fixture,bridge,
        ref(ROOT/"scripts/wp5_cleanup_scope_fixture_v1.py","actual_R13_scope_fixture_producer"),
        ref(DIRECTIVE,"actual_latest_continuous_user_directive"),ref(Path(__file__).resolve(),"R13_thin_freeze_preparer")]
    entries.extend(ref(ROOT/"scripts"/name,"current_R13_metadata_freeze_source") for name in (
        "wp5_production_bootstrap_v13.py","wp5_production_bootstrap_v13.sbatch",
        "wp5_reproduction_queue_recovery_v13.sbatch","wp5_g4_freeze_v10_project_cwd.sbatch"))
    entries.extend(ref(p,"additional_frozen_metadata_source") for p in a.extra_source)
    for item in entries:add_unique(files,item)
    inventory={"schema":"WP5_APPEND_ONLY_SOURCE_CHAIN_V7","status":"SOURCE_INVENTORY_FROZEN","inventory_version":7,
        "files":files,"prior_chain":old["source_chain_inventory"],"previous_contract":ref(OLD_CONTRACT,expected=OLD_SHA),
        "previous_sources_preserved":119,"policy":old["policy"],"final200_still_required":True,
        "queue_stress_evidence":old["queue_concurrency_repair"]["pressure_test"],
        "cleanup_scope_evidence":fixture,"science_AST_bridge":bridge,"latest_continuous_directive":ref(DIRECTIVE),
        "source_scope":"R13 two metadata fixes only. R12 actual480 evidence transfers; unchanged119 sources and all science remain frozen.",
        "new_QM_calls":0,"queue_opened":False,"contract_or_gate_generated":False}
    save(INVENTORY,inventory)
    print(json.dumps({"status":"R13_INVENTORY_PREPARED","inventory":ref(INVENTORY),"old_sources_preserved":119,"files":len(files)}))

def initialize(barrier):
    global _BARRIER
    _BARRIER=barrier
def package_lane(arg):
    batch,out=arg;out=Path(out);_BARRIER.wait(timeout=120);rows=[]
    for item in batch:
        if item["kind"]=="parent":
            asset=item["asset"];p=Path(asset["path"]);info=p.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size!=asset["bytes"]:raise ValueError("PARENT_FROZEN_ASSET_TYPE_BYTES_DIFFERS:"+str(p))
            rows.append({"kind":"parent","asset":asset})
        else:
            entry=item["entry"];source=Path(entry["path"])
            if not source.is_absolute() or digest(source)!=entry["sha256"]:raise ValueError("NEW_SOURCE_SHA_DIFFERS:"+str(source))
            leaf=hashlib.sha256(str(source).encode()).hexdigest()[:20]+"_"+source.name
            target=out/"assets"/leaf
            with source.open("rb") as sf,target.open("xb") as df:
                for chunk in iter(lambda:sf.read(4<<20),b""):df.write(chunk)
                df.flush();os.fsync(df.fileno())
            if digest(target)!=entry["sha256"] or target.stat().st_size!=source.stat().st_size:
                raise ValueError("NEW_SOURCE_COPY_SHA_READBACK_DIFFERS")
            rows.append({"kind":"new","asset":{"kind":"additional_source","source_path":str(source),"path":str(target),
                "sha256":entry["sha256"],"bytes":target.stat().st_size,"role":entry.get("role","frozen_metadata_source")}})
    return {"pid":os.getpid(),"rows":rows}
def package_mode(a):
    old=original();inventory=load(INVENTORY)
    if inventory.get("previous_contract",{}).get("sha256")!=OLD_SHA or inventory["files"][:119]!=old["sources"]:
        raise ValueError("INVENTORY7_OLD119_PREFIX_REQUIRED")
    parent_ref=old["reproduction_package"];parent=load(parent_ref["path"],parent_ref["sha256"])
    if parent.get("schema")!="WP5_REPRODUCTION_PACKAGE_V1" or parent.get("status")!="REPRODUCTION_PACKAGE_CLOSED":
        raise ValueError("ACTUAL_CLOSED_PARENT_PACKAGE_REQUIRED")
    job=os.environ.get("SLURM_JOB_ID");node=socket.gethostname().split(".")[0]
    if not job or a.workers<24 or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<a.workers or node not in {"compute-0-"+str(n) for n in (12,13,14,17,18,19)}:
        raise ValueError("ACTUAL24PLUS_WORKER_METADATA_SLURM_ALLOCATION_REQUIRED")
    out=a.package_out or ROOT/"reproduction_package"/("queue_recovery_v13_job_"+job)
    if not out.is_absolute() or not out.resolve().is_relative_to((ROOT/"reproduction_package").resolve()) or out.exists():
        raise ValueError("INDEPENDENT_NEW_PACKAGE_PATH_REQUIRED")
    out.mkdir(parents=True);(out/"assets").mkdir()
    parent_assets=parent["assets"];by_source={item["source_path"]:item for item in parent_assets}
    items=[{"kind":"parent","asset":asset} for asset in parent_assets]
    inventory_ref=ref(INVENTORY,"current_R13_source_inventory")
    for entry in inventory["files"]+[inventory_ref]:
        previous=by_source.get(entry["path"])
        if previous:
            if previous["sha256"]!=entry["sha256"]:raise ValueError("PARENT_SOURCE_BINDING_WOULD_CHANGE")
        else:items.append({"kind":"new","entry":entry})
    bins=[items[i::a.workers] for i in range(a.workers)]
    if any(not batch for batch in bins):raise ValueError("ACTUAL_NONEMPTY_WORKER_SHARDS_REQUIRED")
    ctx=multiprocessing.get_context("spawn");barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=initialize,initargs=(barrier,)) as pool:
        results=list(pool.map(package_lane,[(batch,str(out)) for batch in bins],chunksize=1))
    pids=sorted({row["pid"] for row in results})
    if len(pids)!=a.workers:raise ValueError("ACTUAL_PACKAGE_WORKERS_NOT_CLOSED")
    rows=[row for result in results for row in result["rows"]]
    new=[row["asset"] for row in rows if row["kind"]=="new"]
    manifest=copy.deepcopy(parent)
    manifest.update(job_id=job,assets=copy.deepcopy(parent_assets)+new,
        asset_bytes=sum(item["bytes"] for item in parent_assets+new),original_manifest=copy.deepcopy(parent_ref),
        package_supplement={"schema":"WP5_APPEND_ONLY_METADATA_PACKAGE_V13","status":"PARENT_CLOSED_AND_ADDITIONAL_ASSETS_SHA_READBACK_VERIFIED",
            "additional_sources":inventory_ref,"parent_assets_preserved":len(parent_assets),
            "parent_asset_validation":"Original closed parent SHA/readback proof retained; current type/bytes stat checked. G4 hashes actual parent assets.",
            "new_assets":len(new),"new_copy_bytes":sum(item["bytes"] for item in new),"actual_worker_pids":pids,
            "old_assets_recopied":False,"science_or_software_or_environment_changed":False},
        source=ref(Path(__file__).resolve()),QM_calls=0,LMDB_opened=False)
    save(out/"manifest.json",manifest)
    print(json.dumps({"status":manifest["status"],"manifest":ref(out/"manifest.json"),"new_assets":len(new),"new_copy_bytes":sum(item["bytes"] for item in new)}))
def contract_mode(a):
    old,runner,main,fixture,bridge=evidence(a.fixture_report,a.ast_bridge)
    inventory=load(INVENTORY);inventory_ref=ref(INVENTORY)
    if inventory["files"][:119]!=old["sources"]:raise ValueError("OLD119_SOURCE_PREFIX_DIFFERS")
    package=load(a.package_manifest);package_ref=ref(a.package_manifest)
    supplement=package.get("package_supplement",{})
    if (package.get("schema")!="WP5_REPRODUCTION_PACKAGE_V1" or package.get("status")!="REPRODUCTION_PACKAGE_CLOSED"
        or package.get("original_manifest",{}).get("sha256")!=old["reproduction_package"]["sha256"]
        or supplement.get("status")!="PARENT_CLOSED_AND_ADDITIONAL_ASSETS_SHA_READBACK_VERIFIED"
        or supplement.get("additional_sources",{}).get("sha256")!=inventory_ref["sha256"]):
        raise ValueError("ACTUAL_CLOSED_APPEND_ONLY_R13_PACKAGE_REQUIRED")
    parent=load(old["reproduction_package"]["path"],old["reproduction_package"]["sha256"])
    for key in ("protocol","registry","software_versions","environment","recipes","audit_membership","software_environment_exports","software_binary_dependency_closure"):
        if package.get(key)!=parent.get(key):raise ValueError("PARENT_SCI_OR_SOFTWARE_PACKAGE_FIELD_CHANGED:"+key)
    assets={item["source_path"]:item["sha256"] for item in package["assets"]}
    for entry in inventory["files"]+[inventory_ref]:
        if assets.get(entry["path"])!=entry["sha256"]:raise ValueError("FROZEN_SOURCE_NOT_IN_PACKAGE:"+entry["path"])
    sources=copy.deepcopy(old["sources"])
    for item in inventory["files"]:add_unique(sources,item)
    add_unique(sources,{**inventory_ref,"role":"current_R13_source_inventory"})
    runtime={key:copy.deepcopy(value) for key,value in old["current_runtime"].items() if not key.startswith(("wp5_runner_v","wp5_main_v"))}
    runtime.update({"wp5_runner_v13.py":runner,"wp5_main_v13.sbatch":main})
    value=copy.deepcopy(old)
    value.update(sources=sources,current_runtime=runtime,reproduction_package=package_ref,
        source_chain_inventory=inventory_ref,previous_contract=ref(OLD_CONTRACT,expected=OLD_SHA),
        latest_user_continuous_directive=ref(DIRECTIVE),cleanup_scope_validation=fixture,metadata_only_AST_bridge=bridge,
        queue_metadata_cleanup_scope_repair={"runtime":"runner13","cleanup_scope_fixture":fixture,
            "science_AST_bridge":bridge,"R12_pressure_transfer":copy.deepcopy(old["queue_concurrency_repair"]["pressure_test"]),
            "science_recipe_unchanged":True,"metadata_retry_budget_seconds":600.0,
            "SCI_retry_and_QM_timeout_unchanged":True,"new_QM_calls":0,"old119_sources_preserved":True})
    allowed={"sources","current_runtime","reproduction_package","source_chain_inventory","previous_contract"}
    for key in old:
        if key not in allowed and value[key]!=old[key]:raise ValueError("OLD_SCI_CONTRACT_FIELD_CHANGED:"+key)
    if value["sources"][:119]!=old["sources"]:raise ValueError("OLD119_SOURCE_DICTS_NOT_EXACT")
    save(CONTRACT,value)
    print(json.dumps({"status":"CONTRACT6_FROZEN_FROM_ACTUAL_EVIDENCE","contract":ref(CONTRACT),
        "old_sources_preserved":119,"G0_created":False,"authorization_created":False,"QM_calls":0}))
def spec_mode(a):
    old=load(OLD_SPEC,OLD_SPEC_SHA);contract=load(CONTRACT);contract_ref=ref(CONTRACT)
    prepared_path=ROOT/"submission/recovery_attempt_v13/prepared_plan_v13.json"
    prepared=load(prepared_path);prepared_ref=ref(prepared_path)
    if prepared.get("status")!="PREPARED_NOT_SUBMITTED" or prepared.get("version")!=13 or prepared.get("production_contract")!=contract_ref:
        # Prepared refs traditionally omit bytes. Compare only canonical path/SHA.
        if not (prepared.get("status")=="PREPARED_NOT_SUBMITTED" and prepared.get("version")==13 and
                prepared.get("production_contract")=={k:contract_ref[k] for k in ("path","sha256")}):
            raise ValueError("ACTUAL_PREPARED13_CONTRACT6_REQUIRED")
    from wp5_g4_freeze_v8 import current_runtime_binding,prepared_runtime_differences
    binding=current_runtime_binding(contract)
    if binding["version"]!=13:raise ValueError("UNIQUE_CURRENT_RUNNER_MAIN13_REQUIRED")
    node_ref=contract["node_scope_plan"];tasks=load(node_ref["path"],node_ref["sha256"])["tasks"]
    differences=prepared_runtime_differences(prepared,contract,binding,tasks,node_ref["sha256"],{k:contract_ref[k] for k in ("path","sha256")})
    if differences:raise ValueError("ACTUAL_PREPARED13_BINDINGS_DIFFER:"+repr(differences))
    inventory=load(INVENTORY);files=copy.deepcopy(old["files"])
    for entry in inventory["files"]:
        item=dict(entry)
        if "bytes" not in item:item["bytes"]=Path(item["path"]).stat().st_size
        add_unique(files,item)
    for path,role in ((CONTRACT,"actual_current_R13_contract"),(prepared_path,"actual_current_R13_prepared"),
        (contract["reproduction_package"]["path"],"actual_current_R13_package"),(INVENTORY,"actual_current_R13_inventory"),
        (Path(__file__).resolve(),"R13_spec_preparation_code")):
        add_unique(files,ref(path,role))
    value=copy.deepcopy(old)
    value.update(files=files,production_contract={k:contract_ref[k] for k in ("path","sha256")},
        prepared_plan={k:prepared_ref[k] for k in ("path","sha256")},reproduction_package=contract["reproduction_package"],
        code_inventory=ref(INVENTORY),current_runtime=contract["current_runtime"],previous_spec_sha256=OLD_SPEC_SHA,
        changed_scope="R13 metadata-only cleanup scope and index fix. Old science/software/dictionary/authority fields and151 prior files preserved. No new SCI/QM PASS implied.")
    save(SPEC,value)
    print(json.dumps({"status":"G4_SPEC14_PREPARED_NOT_EXECUTED","spec":ref(SPEC),"old_files_preserved":len(old["files"]),"files":len(files)}))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--check",action="store_true")
    p.add_argument("--mode",choices=("inventory","package","contract","g4-spec"))
    p.add_argument("--fixture-report","--cleanup-fixture",dest="fixture_report",type=Path);p.add_argument("--ast-bridge",type=Path,default=ROOT/"reports/wp5_runner_v13_cleanup_scope_ast_bridge_v1.json")
    p.add_argument("--extra-source",type=Path,action="append",default=[]);p.add_argument("--package-manifest",type=Path)
    p.add_argument("--package-out",type=Path);p.add_argument("--workers",type=int,default=24);a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("R13_THIN_FREEZE_AST_PASS_NO_OUTPUT_NO_QUEUE_NO_QM");return
    if os.getuid()!=1278:raise ValueError("EXACT_OWN_UID1278_REQUIRED")
    if not a.mode:p.error("--mode is required")
    if a.mode in ("inventory","contract") and a.fixture_report is None:p.error("Actual --fixture-report required")
    if a.mode=="contract" and a.package_manifest is None:p.error("Actual --package-manifest required")
    {"inventory":inventory_mode,"package":package_mode,"contract":contract_mode,"g4-spec":spec_mode}[a.mode](a)
if __name__=="__main__":main()
