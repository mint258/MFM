"""Build contract5 only from actual closed R12 evidence; no G0 or phase authorization."""
import argparse,copy,hashlib,json,os
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
OLD_SHA="41852032a9f063ed5c4fe88912ad72ec65b1b0e69fd4c11e9ccbb0db65f2b84d"
RUNNER_SHA="91ec1ce7bf82589b647db43502bc86f9bb2c7c0a98a845ef28446703cc48d278"
MAIN_SHA="958819b15a460484a2f8da407fbec43987aeef6525fdc5d669d6b4b1bae9ca81"
PRESSURE=ROOT/"gates/metadata_queue_production_shape/production_shape_r12_v5_20261012_run6_fair_wait_600/report.json"
TRACE={"status","software_version_id","elapsed_seconds","scf_iterations","converged","input_file_sha256"}

def ref(path,expected=None):
    path=Path(path).resolve();raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if expected is not None and sha!=expected:raise ValueError("FROZEN_SOURCE_SHA_DIFFERS:"+str(path))
    return {"path":str(path),"sha256":sha,"bytes":len(raw)}

def read(path):return json.loads(Path(path).read_text())

def build(package_path,pressure_path,ast_path,inventory_path):
    old_path=ROOT/"configs/production_contract_v4.json";old_ref=ref(old_path,OLD_SHA);old=read(old_path)
    if old["schema"]!="WP5_PRODUCTION_CONTRACT_V1" or old["status"]!="PRODUCTION_CONTRACT_FROZEN" or len(old["sources"])!=96:
        raise ValueError("ACTUAL_CONTRACT4_WITH96_SOURCES_REQUIRED")
    runner=ref(ROOT/"scripts/wp5_runner_v12.py",RUNNER_SHA)
    main=ref(ROOT/"scripts/wp5_main_v12.sbatch",MAIN_SHA)
    inventory_ref=ref(inventory_path);inventory=read(inventory_path)
    files=inventory.get("files")
    if not isinstance(files,list) or not files:raise ValueError("ACTUAL_INVENTORY6_FILES_REQUIRED")
    pressure_path=Path(pressure_path).resolve()
    if pressure_path!=PRESSURE.resolve():raise ValueError("EXACT_ACTUAL_RUN6_REPORT_REQUIRED")
    pressure_ref=ref(pressure_path);pressure=read(pressure_path)
    measured=pressure.get("versions",{}).get("R12",{})
    expected=pressure.get("expected_main_metadata_completions",0)+pressure.get("expected_rare_metadata_completions",0)
    if (pressure.get("schema")!="WP5_PRODUCTION_SHAPE_METADATA_RESULT_V1" or
        pressure.get("status")!="PRODUCTION_SHAPE_METADATA_PASS" or pressure.get("issues")!=[] or
        measured.get("errors")!=[] or expected<=0 or measured.get("claimed_molecules")!=expected or
        measured.get("unique_claimed_molecules")!=expected or
        pressure.get("physical_population")!=[1220466,11231854] or
        pressure.get("R12_bootstrap",{}).get("sha256")!=RUNNER_SHA or
        measured.get("configured_retry_budget_seconds")!=[600.0] or pressure.get("harness_version")!=5 or
        pressure.get("actual_workers")!=480 or pressure.get("actual_test_node_count")!=5 or pressure.get("parent_slots")!=22 or
        pressure.get("QM_calls")!=0 or pressure.get("production_writes")!=0):
        raise ValueError("ACTUAL_RUN6_R12_CLOSURE_PASS_REQUIRED")
    ast_ref=ref(ast_path);bridge=read(ast_path)
    if (bridge.get("status")!="METADATA_ONLY_AST_BRIDGE_PASS" or
        bridge.get("candidate",{}).get("sha256")!=RUNNER_SHA or
        bridge.get("original",{}).get("sha256")!=old["current_runtime"]["wp5_runner_v11.py"]["sha256"] or
        len(bridge.get("unchanged_original_symbols",[]))<32 or
        not set(bridge.get("changed_metadata_symbols",[])).issubset({"BusyConnection","connection","Queue","sqlite_lock_error"})):
        raise ValueError("ACTUAL_91EC_METADATA_ONLY_AST_BRIDGE_REQUIRED")
    package_ref=ref(package_path);package=read(package_path)
    if (package.get("schema")!="WP5_REPRODUCTION_PACKAGE_V1" or
        package.get("status")!="REPRODUCTION_PACKAGE_CLOSED" or
        package.get("original_manifest",{}).get("sha256")!=old["reproduction_package"]["sha256"] or
        package.get("package_supplement",{}).get("status")!="ALL_ACTUAL_ASSET_BYTES_SHA_READBACK_VERIFIED" or
        package.get("package_supplement",{}).get("additional_sources",{}).get("sha256")!=inventory_ref["sha256"]):
        raise ValueError("ACTUAL_CLOSED_R12_SUPPLEMENT_PACKAGE_REQUIRED")
    for key in ("protocol","registry","audit_membership"):
        old_key="audit_manifest" if key=="audit_membership" else key
        if package.get(key,{}).get("sha256")!=old[old_key]["sha256"]:
            raise ValueError("PACKAGE_SCI_REFERENCE_CHANGED:"+key)
    for name,version in old["software_versions"].items():
        actual=package["software_versions"][name]
        if (actual["version"],actual["software_version_id"],actual["sha256"])!=(version["version"],version["software_version_id"],version["binary_sha256"]):
            raise ValueError("PACKAGE_SOFTWARE_CHANGED:"+name)
    assets={str(Path(item["source_path"]).resolve()):item["sha256"] for item in package["assets"]}
    out=copy.deepcopy(old);sources=copy.deepcopy(old["sources"])
    by_path={str(Path(item["path"]).resolve()):item for item in sources}
    if len(by_path)!=96:raise ValueError("OLD_SOURCE_PATHS_NOT_UNIQUE")
    def add(item):
        path=str(Path(item["path"]).resolve())
        if path in by_path:
            if by_path[path]["sha256"]!=item["sha256"]:raise ValueError("OLD_FROZEN_SOURCE_CHANGED:"+path)
            return
        value=copy.deepcopy(item);value["path"]=path;sources.append(value);by_path[path]=value
    for item in files:
        if not {"path","sha256","role"}.issubset(item):raise ValueError("INVENTORY_SOURCE_REF_INCOMPLETE")
        path=str(Path(item["path"]).resolve())
        if assets.get(path)!=item["sha256"]:raise ValueError("INVENTORY_ASSET_NOT_IN_CLOSED_PACKAGE:"+path)
        add(item)
    for item in (runner,main):
        if by_path.get(item["path"],{}).get("sha256")!=item["sha256"]:
            raise ValueError("R12_CURRENT_RUNTIME_NOT_IN_INVENTORY_AND_PACKAGE:"+item["path"])
    for item,role in ((inventory_ref,"current_R12_source_inventory"),(pressure_ref,"R12_actual_metadata_pressure_evidence"),(ast_ref,"R12_metadata_only_AST_evidence")):
        add({**item,"role":role})
    runtime={key:value for key,value in old["current_runtime"].items()
             if not (key.startswith("wp5_runner_v") or key.startswith("wp5_main_v"))}
    runtime.update({"wp5_runner_v12.py":runner,"wp5_main_v12.sbatch":main})
    out.update(sources=sources,current_runtime=runtime,reproduction_package=package_ref,
               source_chain_inventory=inventory_ref,previous_contract=old_ref)
    out["previous_queue_concurrency_repair"]=copy.deepcopy(old.get("queue_concurrency_repair"))
    out["queue_concurrency_repair"]={
        "runtime":"runner12","science_recipe_unchanged":True,"pressure_test":pressure_ref,
        "metadata_retry_budget_seconds":600.0,"deadline_min_preserved":True,"SCI_retry_and_QM_timeout_unchanged":True,
        "pressure_status":pressure["status"],"actual_test_nodes":pressure.get("actual_test_nodes"),
        "actual_test_workers":pressure.get("actual_workers"),"actual_scope":pressure.get("scope"),
        "science_AST_bridge":ast_ref,"source_inventory":inventory_ref,
        "new_formal_phase_requires_user_direction":True,"original_submission_preserved":True,
        "complete_SCI_recovery_before_QM":True,"new_six_node_R12_QM_claimed":False}
    if out["sources"][:96]!=old["sources"] or set(out["trace_fields"])!=TRACE:
        raise AssertionError("OLD96_OR_CANONICAL6_NOT_PRESERVED")
    for key in old:
        if key not in {"sources","current_runtime","reproduction_package","source_chain_inventory","previous_contract","queue_concurrency_repair"}:
            if out[key]!=old[key]:raise AssertionError("NON_METADATA_CONTRACT_FIELD_CHANGED:"+key)
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--package-manifest",type=Path)
    p.add_argument("--pressure-report",type=Path,default=PRESSURE)
    p.add_argument("--ast-bridge",type=Path,default=ROOT/"reports/wp5_runner_v12_candidate_v5_ast_bridge.json")
    p.add_argument("--inventory",type=Path,default=ROOT/"configs/current_code_chain_user_override_v6.json")
    p.add_argument("--check",action="store_true");a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print("CONTRACT5_GENERATOR_AST_PASS_NO_OUTPUT_NO_QUEUE_NO_QM");return
    if a.package_manifest is None:p.error("--package-manifest actual closed R12 path is required")
    value=build(a.package_manifest,a.pressure_report,a.ast_bridge,a.inventory)
    target=ROOT/"configs/production_contract_v5.json"
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()
    if target.exists():
        if target.read_bytes()!=raw:raise FileExistsError("DIFFERENT_CONTRACT5_ALREADY_EXISTS_NO_OVERWRITE")
        outcome="IDENTICAL_EXISTING_CONTRACT5_PRESERVED"
    else:
        pending=target.with_name(target.name+"."+str(os.getpid())+".pending")
        with pending.open("xb") as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        try:os.link(pending,target)
        finally:pending.unlink(missing_ok=True)
        outcome="CONTRACT5_CREATED_FROM_ACTUAL_CLOSED_EVIDENCE"
    print(json.dumps({"status":outcome,"contract":ref(target),"old_sources_preserved":96,
                      "source_count":len(value["sources"]),"G0_created":False,
                      "user_phase_authority_created":False,"queue_written":False,"QM_calls":0}))
if __name__=="__main__":main()
