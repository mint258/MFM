"""CPU read-only audit of terminal TIMEOUT pilot packages; no recovery or C0 claim."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
PARENT=Path(__file__).parent.parent
sys.path.insert(0,str(PARENT/"pilot_closure_cpu_v1"))
from runtime_adapter_v2 import IO,admit,checkpoint,bounded_map


def stat_identity(path):
    st=Path(path).stat()
    return {"device":st.st_dev,"inode":st.st_ino,"bytes":st.st_size,"mtime_ns":st.st_mtime_ns,"uid":st.st_uid}


def terminal_accounting(raw,target,expected_state="TIMEOUT"):
    reader=csv.DictReader(io.StringIO(raw),delimiter="|")
    if not reader.fieldnames or not {"State","ExitCode","ElapsedRaw","AllocCPUS"}<=set(reader.fieldnames):
        raise ValueError("ACTUAL_SACCT_PARENT_HEADER_REQUIRED")
    name="JobIDRaw" if "JobIDRaw" in reader.fieldnames else "JobID"
    rows={};steps=[]
    for source in reader:
        jid=source.get(name,"")
        if not jid.isdecimal():
            if jid.startswith(str(target)+"."):steps.append(dict(source))
            continue
        state=source["State"].split()[0]
        if jid in rows or state not in {"COMPLETED","FAILED","TIMEOUT","CANCELLED","OUT_OF_MEMORY","NODE_FAIL"}:
            raise ValueError("UNIQUE_ACTUAL_TERMINAL_PARENT_ROWS_REQUIRED")
        elapsed,cpus=int(source["ElapsedRaw"]),int(source["AllocCPUS"])
        if elapsed<0 or cpus<0:raise ValueError("INVALID_ACTUAL_PARENT_COST")
        rows[jid]={"job_id":jid,"state":state,"exit_code":source["ExitCode"],
                   "elapsed_raw_seconds":elapsed,"alloc_cpus":cpus,"allocated_core_seconds":elapsed*cpus}
    parent=rows.get(str(target))
    if parent is None or parent["state"]!=expected_state:
        raise ValueError("REAL_ORIGINAL_PARENT_TIMEOUT_REQUIRED")
    # Exit0:0 on a TIMEOUT parent never upgrades its terminal state to COMPLETED.
    return parent,[rows[key] for key in sorted(rows,key=int)],steps


def expected_filenames(mids):
    if len(mids)!=336 or len(set(mids))!=336:raise ValueError("ORIGINAL336_UNIQUE_METADATA_MOLECULES_REQUIRED")
    return {hashlib.sha256(mid.encode("utf-8")).hexdigest()+".json.gz":mid for mid in mids}


def require_locator_authorization(request,audit,closure,prepared,evidence_ref,submission_ref):
    loc=request.get("data_locator_authorization")
    if not isinstance(loc,dict) or loc.get("schema")!="PARTIAL_SPRIME_PILOT_AUDIT_DATA_LOCATORS_V1" or loc.get("read_only") is not True:
        raise ValueError("EXPLICIT_ROOT_PARTIAL_DATA_LOCATOR_AUTHORIZATION_REQUIRED")
    if request["scope_key"]!=audit["scope_key"] or request["scope_parameters"]!=audit["scope_parameters"]:
        raise ValueError("ORIGINAL336_ZERO_NEW_SCIENCE_SCOPE_REQUIRED")
    def output(name):
        refs=[r for r in prepared["outputs"] if Path(r["path"]).name==name]
        if len(refs)!=1:raise ValueError("UNIQUE_ORIGINAL_PREPARED_OUTPUT_REQUIRED:"+name)
        return refs[0]
    expected={"expected_molecules":336,"original_pilot_job":audit["expected_original_job"],
        "pilot_output_directory":audit["pilot_output_directory"],"prepared_reference":closure["prepared"],
        "pilot_config_reference":closure["pilot_config"],"selected_molecules_reference":output("selected_molecules.parquet"),
        "tasks_reference":output("tasks.jsonl"),"original_submission_reference":submission_ref,
        "sacct_evidence_reference":evidence_ref,"allow_tasks_body_only_in_actual_cpu_allocation":True,
        "new_UFF_QM_calls":0,"formal_acceptance_allowed":False}
    for key,value in expected.items():
        if loc.get(key)!=value:raise ValueError("ROOT_DATA_LOCATOR_DIFFERS:"+key)
    return expected


def validate_one(item):
    """Only expected directory children; all scientific validation reuses old reader."""
    path,mid,task,limit,validator=item
    before=stat_identity(path)
    try:
        checkpoint()
        if Path(path).is_symlink():raise ValueError("PACKAGE_SYMLINK_NOT_ALLOWED")
        ref={"molecule_id":mid,**IO.reference(path)}
        summary,detail,geometries=validator.read_package((ref,task,limit))
        prefix="sprime-ETKDGv3-v1-retry1:" if task["meta"]["cohort"]=="retry_once" else "sprime-ETKDGv3-v1:"
        recipe_seed=max(int.from_bytes(hashlib.sha256((prefix+mid).encode()).digest()[:4],"big")&0x7fffffff,1)
        if summary["seed"]!=recipe_seed:raise ValueError("OBSERVED_SEED_DIFFERS_FROM_ORIGINAL_DETERMINISTIC_METADATA_RULE")
        pointers={row["record_id"]:row for row in task["records"]}
        for row in geometries.values():
            z=row["atomic_numbers"];anchor=pointers[row["source_record_id"]]
            if any(type(v) is not int or not 1<=v<=118 for v in z) or len(z)!=anchor["total_atoms"]:
                raise ValueError("ATOMIC_INTEGER_SEQUENCE_OR_NATIVE_ATOM_COUNT_INVALID")
            if type(row["below_dedup_threshold"]) is not bool or type(row["seed"]) is not int:
                raise ValueError("BOOLEAN_FLAG_OR_SEED_INTEGER_TYPE_CHANGED")
            if row["origin"]!="accepted_sprime" and row["seed"]!=summary["seed"]:
                raise ValueError("GENERATED_CANDIDATE_SEED_DIFFERS_FROM_OBSERVED_ATTEMPT")
        after=stat_identity(path)
        if before!=after:raise ValueError("PACKAGE_CHANGED_DURING_FULL_HASH_CRC_JSON_VALIDATION")
        return {"molecule_id":mid,"classification":"COMPLETE_REUSABLE_CLOSED_PACKAGE",
            "reference":ref,"file_identity":after,"crc_json_validated":True,
            "science_worker_seconds":float(summary["elapsed_seconds"]),"summary":summary,"detail":detail}
    except Exception as exc:
        return {"molecule_id":mid,"classification":"INVALID_OR_UNCLOSED_PACKAGE",
            "path":str(path),"file_identity_before":before,"error_type":type(exc).__name__,"error":str(exc)[:4000]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True,help="Unchanged original closure config")
    p.add_argument("--cpu-runconfig",type=Path,required=True);p.add_argument("--audit-config",type=Path,required=True)
    p.add_argument("--root-preflight",type=Path,required=True);p.add_argument("--sacct-evidence",type=Path,required=True)
    p.add_argument("--original-submission",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();proof=admit(a.root_preflight,Path(__file__),a.cpu_runconfig,a.config,"closure")
    intent=json.loads(a.root_preflight.read_text());request=intent["request"]
    audit=json.loads(a.audit_config.read_text());closure=json.loads(a.config.read_text())
    if audit.get("schema")!="DATA_V1_PARTIAL_SPRIME_PILOT_AUDIT_CONFIG_V1" or audit["expected_molecules"]!=336 or audit["new_UFF_QM_calls"]!=0 or audit["formal_acceptance_allowed"] is not False:
        raise ValueError("READONLY_PARTIAL_AUDIT_CONFIG_REQUIRED")
    for path in (a.audit_config,a.sacct_evidence,a.original_submission):
        if IO.reference(path) not in request["source_references"]:raise ValueError("EXACT_SMALL_AUTHORITY_SOURCE_PIN_REQUIRED")
    if closure["schema"]!="DATA_V1_SPRIME_PILOT_CLOSURE_CONFIG_V1" or closure["expected_job_id"]!=audit["expected_original_job"]:
        raise ValueError("ORIGINAL_CLOSURE_CONFIG_AND_JOB_ID_REQUIRED")
    prepared=json.loads(IO.require_pin(closure["prepared"]).read_text())
    if prepared["status"]!="PILOT_INPUTS_READY_NOT_COMPUTED" or prepared["molecules"]!=336 or prepared["config"]!=closure["pilot_config"]:
        raise ValueError("ORIGINAL_PREPARED_AUTHORITY_REQUIRED")
    evidence_ref=IO.reference(a.sacct_evidence);submission_ref=IO.reference(a.original_submission)
    loc=require_locator_authorization(request,audit,closure,prepared,evidence_ref,submission_ref)
    evidence=json.loads(a.sacct_evidence.read_text())
    if evidence.get("schema")!="DATA_V1_SACCT_QUERY_EVIDENCE_V1" or evidence.get("query_returncode")!=0 or not evidence.get("command_argv") or Path(evidence["command_argv"][0]).name!="sacct" or datetime.fromisoformat(evidence["observed_at"]).tzinfo is None:
        raise ValueError("ACTUAL_SUCCESSFUL_ROOT_SACCT_QUERY_EVIDENCE_REQUIRED")
    raw_ref=evidence["raw_sacct_reference"];raw=IO.require_pin(raw_ref).read_text()
    parent,parents,steps=terminal_accounting(raw,audit["expected_original_job"],audit["expected_original_parent_state"])
    requested=list(map(str,evidence["requested_parent_job_ids"]))
    if len(set(requested))!=len(requested) or set(requested)!={r["job_id"] for r in parents}:
        raise ValueError("ACTUAL_RAW_PARENT_SET_DIFFERS_FROM_ROOT_QUERY")
    submission=json.loads(a.original_submission.read_text())
    if str(submission["job_id"])!=audit["expected_original_job"]:
        raise ValueError("ORIGINAL_ROOT_SUBMISSION_JOB_CHANGED")
    original_refs=submission["request"]["source_references"]
    if any(pin not in original_refs for pin in (closure["prepared"],closure["pilot_config"])):
        raise ValueError("ORIGINAL_JOB_CONFIG_OR_PREPARED_BINDING_MISSING")
    for ref in [submission["request"]["script_reference"],*original_refs]:
        checkpoint();IO.require_pin(ref)
    pilot_config=json.loads(IO.require_pin(closure["pilot_config"]).read_text())
    if pilot_config["max_output_bytes"]!=8*1024**3 or pilot_config["candidate_multiplier"]!=10 or pilot_config["max_candidates"]!=300:
        raise ValueError("ORIGINAL_SCIENTIFIC_CONFIG_LIMITS_CHANGED")
    for ref in pilot_config["science_source_pins"]:checkpoint();IO.require_pin(ref)
    checkpoint()
    import pyarrow.parquet as pq
    selected_ref=loc["selected_molecules_reference"];IO.require_pin(selected_ref)
    selected=pq.read_table(selected_ref["path"]).to_pylist()
    mids=[row["molecule_id"] for row in selected];expected=expected_filenames(mids)
    selected_by_id={row["molecule_id"]:row for row in selected}
    # This >2MiB source is hashed/read only here, inside the real guarded CPU job.
    tasks_ref=loc["tasks_reference"];IO.require_pin(tasks_ref);tasks={}
    with Path(tasks_ref["path"]).open() as stream:
        for line in stream:
            checkpoint();task=json.loads(line);mid=task["meta"]["molecule_id"]
            if mid in tasks or mid not in selected_by_id:raise ValueError("TASK_ID_DUPLICATE_OR_OUTSIDE_ORIGINAL_METADATA")
            meta=task["meta"];scalar=selected_by_id[mid]
            for key in ("cohort","Sprime_status","S_conformers","Sprime_conformers","file_group"):
                if meta[key]!=scalar[key]:raise ValueError("TASK_META_DIFFERS_FROM_PINNED_SELECTED:"+key)
            if meta["expected_conformers"]!=scalar["S_conformers"]:raise ValueError("TASK_ORIGINAL_N_CHANGED")
            if len(task["records"])!=scalar["S_conformers"] or len(task["existing_conformers"])!=scalar["Sprime_conformers"]:
                raise ValueError("TASK_NATIVE_OR_PREVIOUS_ACCEPTED_COUNT_CHANGED")
            tasks[mid]=task
    if set(tasks)!=set(mids):raise ValueError("TASKS_DO_NOT_COVER_ORIGINAL336_METADATA")
    path=PARENT/"pilot_closure_v1/close_pilot.py"
    if IO.digest(path)!=audit["old_package_validator_sha256"]:raise ValueError("IMMUTABLE_PACKAGE_VALIDATOR_CHANGED")
    spec=importlib.util.spec_from_file_location("_sb2_partial_old_package_validator",path)
    validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    directory=Path(audit["pilot_output_directory"])/audit["reproduction_directory_name"]
    if directory.is_symlink() or not directory.is_dir():raise ValueError("ORIGINAL_REGULAR_REPRODUCTION_DIRECTORY_REQUIRED")
    snapshot={};entry_snapshot={};unexpected=[];preinvalid=[]
    for child in directory.iterdir():
        checkpoint()
        if child.name not in expected:
            unexpected.append({"path":str(child),"name":child.name,"symlink":child.is_symlink(),"reason":"UNEXPECTED_ENTRY_NOT_READ"})
            continue
        st=child.lstat()
        entry_snapshot[child.name]=(st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_mtime_ns)
        if child.is_symlink() or not child.is_file():
            preinvalid.append({"molecule_id":expected[child.name],"classification":"INVALID_OR_UNCLOSED_PACKAGE",
                "path":str(child),"error_type":"NONREGULAR_EXPECTED_PACKAGE","error":"Expected package is a symlink or nonregular entry; contents not read"})
        else:snapshot[child.name]=stat_identity(child)
    missing=[{"molecule_id":mid,"expected_filename":name,"expected_path":str(directory/name),
              "cohort":selected_by_id[mid]["cohort"],"prior_status":selected_by_id[mid]["Sprime_status"],
              "expected_original_N":selected_by_id[mid]["S_conformers"]}
             for name,mid in sorted(expected.items()) if name not in entry_snapshot]
    import concurrent.futures as cf
    rows=list(preinvalid)
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        items=[(directory/name,expected[name],tasks[expected[name]],closure["max_package_uncompressed_bytes"],validator) for name in sorted(snapshot)]
        for row in bounded_map(pool,validate_one,items):rows.append(row)
    # A terminal input must stay immutable across the whole audit; never seal
    # a snapshot from a still-changing directory or output package.
    now={}
    for path in directory.iterdir():
        if path.name in expected:
            st=path.lstat();now[path.name]=(st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_mtime_ns)
    if entry_snapshot!=now:raise ValueError("TERMINAL_REPRODUCTION_SNAPSHOT_CHANGED_DURING_AUDIT")
    complete=sorted((row for row in rows if row["classification"]=="COMPLETE_REUSABLE_CLOSED_PACKAGE"),key=lambda row:row["molecule_id"])
    invalid=sorted((row for row in rows if row["classification"]!="COMPLETE_REUSABLE_CLOSED_PACKAGE"),key=lambda row:row["molecule_id"])
    if len(complete)+len(invalid)+len(missing)!=336:raise ValueError("COMPLETE_MISSING_INVALID_IDENTITY_CONSERVATION_FAILED")
    checkpoint();out=IO.new_output_directory(a.output,audit)
    for name,value in (("complete_packages.json",complete),("missing_tasks.json",missing),("invalid_packages.json",invalid),("unexpected_entries.json",unexpected)):
        IO.write_json_new(out/name,value);checkpoint()
    IO.write_json_new(out/"cohort_report.json",validator.distribution([r["detail"] for r in complete]))
    IO.write_json_new(out/"actual_accounting_evidence.json",{"schema":"PARTIAL_PILOT_ACTUAL_TERMINAL_ACCOUNTING_V1",
        "status":"ORIGINAL_PARENT_TIMEOUT_NOT_C0","target_parent":parent,"all_included_parents":parents,
        "original_target_steps_not_double_charged":steps,"raw_sacct_reference":raw_ref,"query_evidence":evidence_ref,
        "target_parent_core_hours":parent["allocated_core_seconds"]/3600,
        "all_included_parent_core_hours":sum(r["allocated_core_seconds"] for r in parents)/3600})
    report={"schema":"PARTIAL_SPRIME_PILOT_READONLY_AUDIT_V1","status":"PARTIAL_PILOT_NOT_ACCEPTED_FOR_FORMAL",
        "audit_completed":True,"original_job_id":audit["expected_original_job"],"original_parent_state":parent["state"],
        "original_parent_exit_code":parent["exit_code"],"original_parent_core_hours":parent["allocated_core_seconds"]/3600,
        "expected_molecules":336,"complete_reusable_molecules":len(complete),"missing_molecules":len(missing),
        "invalid_molecules":len(invalid),"unexpected_entries":len(unexpected),"original_expected_packages_present":len(snapshot),
        "expected_entries_present_including_invalid_nonregular":len(entry_snapshot),
        "all_present_expected_package_bytes":sum(row["bytes"] for row in snapshot.values()),
        "complete_package_bytes":sum(r["reference"]["bytes"] for r in complete),
        "complete_package_science_worker_seconds":sum(r["science_worker_seconds"] for r in complete),
        "missing_or_invalid_worker_seconds":"NOT_SAVED_NOT_INFERRED; not included in closed-package sum",
        "status_counts":dict(sorted(Counter(r["summary"]["status"] for r in complete).items())),
        "prepared_reference":closure["prepared"],"selected_molecules_reference":selected_ref,"tasks_reference":tasks_ref,
        "original_submission_reference":submission_ref,"original_pilot_config_reference":closure["pilot_config"],
        "pilot_output_directory":audit["pilot_output_directory"],"data_locator_authorization":loc,
        "cpu_guard":proof,"audit_config":IO.reference(a.audit_config),
        "outputs":[IO.reference(out/name) for name in ("complete_packages.json","missing_tasks.json","invalid_packages.json","unexpected_entries.json","cohort_report.json","actual_accounting_evidence.json")],
        "source_files_modified":False,"original_timeout_retained":True,"original_receipt_fabricated":False,
        "new_UFF_QM_calls":0,"new_once_keys_created":0,"recovery_started":False,
        "root_review_granted":False,"pilot_accepted_for_planning":False,"common_frozen":False,"formal_generation_authorized":False}
    IO.write_json_new(out/"audit_report.json",report)
    print(json.dumps({"status":report["status"],"complete":len(complete),"missing":len(missing),"invalid":len(invalid),"output":str(out)}))


if __name__=="__main__":main()
