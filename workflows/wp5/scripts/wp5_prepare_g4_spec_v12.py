"""Generate independent G4 spec12 from immutable spec11 and actual contract5/prepared12."""
from __future__ import annotations
import argparse, ast, copy, hashlib, json, os, re, uuid
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
OLD=ROOT/"configs/g4_freeze_spec_v11.json"
CONTRACT=ROOT/"configs/production_contract_v5.json"
PREPARED=ROOT/"submission/recovery_attempt_v12/prepared_plan_v12.json"
INVENTORY=ROOT/"configs/current_code_chain_user_override_v6.json"
OUT=ROOT/"configs/g4_freeze_spec_v12.json"
SCOPE="CURRENT_USER_OVERRIDE_RECORD_AUDIT_NO_INPUTS_12_TASKS_F64"

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(4<<20),b""):h.update(block)
    return h.hexdigest()

def frozen_json(path,expected):
    if not re.fullmatch("[0-9a-f]{64}",expected or ""):raise ValueError("ACTUAL_EXPECTED_SHA_REQUIRED:"+str(path))
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError("ACTUAL_SHA_DIFFERS:"+str(path))
    return json.loads(raw)

def ref(path,role=None):
    p=Path(path).resolve();r={"path":str(p),"sha256":digest(p)}
    if role is not None:r.update(role=role,bytes=p.stat().st_size)
    return r

def write_once(path,data):
    if path.exists():
        if json.loads(path.read_text())!=data:raise ValueError("EXISTING_SPEC12_DIFFERS")
        return
    temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".pending")
    with temporary.open("x") as f:
        json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False);f.write("\n");f.flush();os.fsync(f.fileno())
    try:os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def prepare(a):
    old=json.loads(OLD.read_text())
    if old.get("scope")!=SCOPE:raise ValueError("INHERITED_CANONICAL_SCOPE_DIFFERS")
    contract=frozen_json(CONTRACT,a.contract_sha256);prepared=frozen_json(PREPARED,a.prepared_sha256)
    contract_ref={"path":str(CONTRACT),"sha256":a.contract_sha256}
    prepared_ref={"path":str(PREPARED),"sha256":a.prepared_sha256}
    if contract.get("schema")!="WP5_PRODUCTION_CONTRACT_V1" or contract.get("status")!="PRODUCTION_CONTRACT_FROZEN":
        raise ValueError("ACTUAL_FROZEN_CONTRACT5_REQUIRED")
    if prepared.get("status")!="PREPARED_NOT_SUBMITTED" or prepared.get("version")!=12:
        raise ValueError("ACTUAL_PREPARED12_REQUIRED")
    if prepared.get("production_contract")!=contract_ref:raise ValueError("PREPARED12_CONTRACT5_SHA_BINDING_DIFFERS")
    # These are the actual metadata functions used by validator8, not a second schema.
    from wp5_g4_freeze_v8 import current_runtime_binding,prepared_runtime_differences
    binding=current_runtime_binding(contract)
    if binding["version"]!=12:raise ValueError("UNIQUE_CURRENT_MAIN12_RUNNER12_REQUIRED")
    tasks_path=Path(contract["node_scope_plan"]["path"])
    if digest(tasks_path)!=contract["node_scope_plan"]["sha256"]:raise ValueError("UNCHANGED_NODE_PLAN_SHA_DIFFERS")
    tasks=json.loads(tasks_path.read_text())["tasks"]
    differences=prepared_runtime_differences(prepared,contract,binding,tasks,contract["node_scope_plan"]["sha256"],contract_ref)
    if differences:raise ValueError("VALIDATOR8_PREPARED_BINDING_DIFFERS:"+repr(differences))
    if contract["registry"]!={"path":old["registry"],"sha256":old["registry_sha256"]} or contract["node_authority"]!={"path":old["node_authority"],"sha256":old["node_authority_sha256"]}:
        raise ValueError("INHERITED_REGISTRY_OR_NODE_AUTHORITY_DIFFERS")
    for runtime_ref in (binding["runner"],binding["main"]):
        if digest(runtime_ref["path"])!=runtime_ref["sha256"]:raise ValueError("CURRENT_RUNTIME_ACTUAL_SHA_DIFFERS")
    package_ref=contract["reproduction_package"];package=frozen_json(package_ref["path"],package_ref["sha256"])
    if package.get("status")!="REPRODUCTION_PACKAGE_CLOSED":raise ValueError("ACTUAL_NEW_CLOSED_PACKAGE_REQUIRED")
    inventory_ref=package["package_supplement"]["additional_sources"]
    if Path(inventory_ref["path"]).resolve()!=INVENTORY.resolve():raise ValueError("PACKAGE_NOT_BOUND_TO_NEW_INVENTORY6")
    inventory=frozen_json(inventory_ref["path"],inventory_ref["sha256"])
    files=copy.deepcopy(old["files"]);by_path={entry["path"]:entry for entry in files}
    def add(entry):
        # Keep every previous entry exactly; only add independent new references.
        if entry["path"] in by_path:
            previous=by_path[entry["path"]]
            if previous["sha256"]!=entry["sha256"] or previous["bytes"]!=entry["bytes"]:
                raise ValueError("OLD_SPEC_FILE_BINDING_WOULD_CHANGE:"+entry["path"])
            return
        files.append(entry);by_path[entry["path"]]=entry
    for entry in inventory["files"]:add(copy.deepcopy(entry))
    for item in contract["sources"]:
        actual=ref(item["path"],"current_contract_source")
        if actual["sha256"]!=item["sha256"]:raise ValueError("NEW_CONTRACT_SOURCE_ACTUAL_SHA_DIFFERS:"+item["path"])
        add(actual)
    for path,role in (
        (CONTRACT,"actual_current_contract"),(PREPARED,"actual_current_prepared_plan"),
        (package_ref["path"],"actual_current_package_manifest"),(INVENTORY,"actual_current_code_inventory"),
        (Path(__file__),"metadata_spec_preparation_code")):
        add(ref(path,role))
    if files[:len(old["files"])]!=old["files"]:raise ValueError("INHERITED_SPEC_FILES_NOT_EXACTLY_PRESERVED")
    spec=copy.deepcopy(old)
    spec.update(files=files,production_contract=contract_ref,prepared_plan=prepared_ref,
        reproduction_package=package_ref,code_inventory=inventory_ref,current_runtime=contract["current_runtime"],
        previous_spec_sha256=digest(OLD),
        changed_scope="R12 queue metadata recovery only. Inherit all spec11 science/software/registry/source_plan/dictionaries/node-authority fields and all old files. Actual contract5/prepared12/package/inventory source bindings replace current execution metadata; no G0, authority or scientific PASS is generated.")
    # No inherited scientific/software/dictionary/authority key changes here.
    immutable_keys=set(old)-{"files","production_contract","prepared_plan","previous_spec_sha256","changed_scope"}
    if any(spec[key]!=old[key] for key in immutable_keys):raise ValueError("INHERITED_SPEC_FIELD_CHANGED")
    write_once(OUT,spec)
    print(json.dumps({"status":"G4_SPEC12_PREPARED_NOT_EXECUTED","spec":ref(OUT),
        "old_files_preserved":len(old["files"]),"files":len(files),"current_runtime_version":12,
        "QM_calls":0,"Slurm_submitted":False,"G0_or_authority_generated":False},allow_nan=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--check",action="store_true")
    p.add_argument("--contract-sha256");p.add_argument("--prepared-sha256");a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print("SPEC12_GENERATOR_AST_PASS_NO_WRITE_NO_SUBMISSION");return
    prepare(a)
if __name__=="__main__":main()
