"""CPU partition variant of immutable pilot_closure_v1/close_pilot.py.

Original SHA e7c8992c06c305a53c3d706e0335b6a94db752d9053594c7bc0571f3e642907f.
Only execution guard/pool/checkpoints and CPU proof metadata differ; original
data/config/receipt/accounting/geometry validation is retained in visible source.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import concurrent.futures as cf
import csv
from datetime import datetime
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import socket
import sys

sys.dont_write_bytecode=True
PARENT=Path(__file__).parent.parent
sys.path.insert(0,str(PARENT/"formal_v1"))
from full_common import IO,require_actual_accounting
from runtime_adapter import admit as cpu_admit,checkpoint,bounded_map

COMPLETE="PILOT_COMPLETED_REQUIRES_ROOT_REVIEW"
READBACK="ALL_PILOT_GEOMETRIES_FLOAT64_SHA_READBACK_PASSED"
TERMINAL={"COMPLETED","FAILED","TIMEOUT","CANCELLED","OUT_OF_MEMORY","NODE_FAIL"}


def require_complete(receipt,expected=336,job_id=None):
    if receipt.get("status")!=COMPLETE or receipt.get("failure") is not None or receipt.get("resource_denial") is not None:
        raise ValueError("FINAL_336_PILOT_WITHOUT_RESOURCE_OR_IMPLEMENTATION_FAILURE_REQUIRED")
    if any(receipt.get(key)!=expected for key in ("expected_molecules","submitted_molecules","completed_molecules")) or receipt.get("never_dispatched_molecules")!=0:
        raise ValueError("ALL336_UNIQUE_TERMINAL_MOLECULES_REQUIRED")
    if receipt.get("parquet_readback",{}).get("status")!=READBACK:
        raise ValueError("PRODUCER_FLOAT64_READBACK_PASS_REQUIRED")
    if job_id is not None and str(receipt["runtime"]["job_id"])!=str(job_id):
        raise ValueError("ACTUAL_REGISTERED_PILOT_JOB_REQUIRED")
    if receipt.get("signals_sent") is not False or receipt.get("original_data_modified") is not False or receipt.get("scientific_recipe_changed") is not False:
        raise ValueError("UNCHANGED_ORIGINAL_DATA_AND_RECIPE_REQUIRED")
    if receipt.get("monitor_thread_closed") is not True:
        raise ValueError("FINAL_PRODUCER_MONITOR_MUST_BE_CLOSED")


def accounting_from_raw(text,pilot_job_id):
    reader=csv.DictReader(io.StringIO(text),delimiter="|")
    if not reader.fieldnames or not {"State","ExitCode","ElapsedRaw","AllocCPUS"}<=set(reader.fieldnames):
        raise ValueError("ACTUAL_PIPE_SACCT_HEADER_REQUIRED")
    name="JobIDRaw" if "JobIDRaw" in reader.fieldnames else "JobID"
    parents=[];seen=set()
    for row in reader:
        jid=row.get(name,"")
        if not jid.isdecimal():continue # batch/extern steps are never double charged
        state=row["State"].split()[0]
        if jid in seen or state not in TERMINAL:raise ValueError("UNIQUE_ACTUAL_TERMINAL_PARENTS_REQUIRED")
        seen.add(jid)
        cpus,elapsed=int(row["AllocCPUS"]),int(row["ElapsedRaw"])
        if cpus<0 or elapsed<0:raise ValueError("NONNEGATIVE_ACTUAL_PARENT_COST_REQUIRED")
        parents.append({"job_id":jid,"state":state,"exit_code":row["ExitCode"],
                        "alloc_cpus":cpus,"elapsed_raw_seconds":elapsed})
    selected=[row for row in parents if row["job_id"]==str(pilot_job_id)]
    if len(selected)!=1 or selected[0]["state"]!="COMPLETED" or selected[0]["exit_code"]!="0:0":
        raise ValueError("ACTUAL_PILOT_PARENT_C0_REQUIRED")
    return sorted(parents,key=lambda row:int(row["job_id"]))


def review_draft(receipt_ref,accounting_ref,manifest_ref,tasks_ref,report_ref):
    return {"schema":"DATA_V1_SPRIME_FULL_ROOT_REVIEW_V1","status":"ROOT_REVIEW_PENDING",
        "pilot_receipt":receipt_ref,"pilot_accounting":accounting_ref,
        "pilot_reproduction_manifest":manifest_ref,"pilot_tasks":tasks_ref,
        "accept_scientific_failure_disclosure":False,"closure_report":report_ref,
        "root_action_required":"Read real cohort failures/cost/source retention; create a separate reviewed decision. This draft never authorizes planning or full science.",
        "formal_64g_hardware_admission":"NOT_GRANTED_BY_THIS_CLOSURE"}


def checked_ids(tasks,refs,expected=336):
    mids=[task["meta"]["molecule_id"] for task in tasks];other=[ref["molecule_id"] for ref in refs]
    if len(mids)!=expected or len(set(mids))!=expected or len(other)!=expected or len(set(other))!=expected or set(mids)!=set(other):
        raise ValueError("PREPARED_AND_MANIFEST_MUST_HAVE_SAME336_UNIQUE_IDS")
    if len({ref["path"] for ref in refs})!=expected:raise ValueError("REPRODUCTION_PACKAGE_PATH_REUSED")
    return dict(zip(mids,tasks))


def read_package(item):
    """Reuse producer SHA math; independently bind to source and native pointers."""
    ref,task,uncompressed_limit=item
    import numpy as np
    IO.require_pin(ref)
    with gzip.GzipFile(fileobj=io.BytesIO(Path(ref["path"]).read_bytes())) as stream:
        raw=stream.read(uncompressed_limit+1)
    if len(raw)>uncompressed_limit:raise ValueError("REPRODUCTION_PACKAGE_EXCEEDS_BOUNDED_READER")
    packet=json.loads(raw);summary=packet["summary"];meta=task["meta"];mid=meta["molecule_id"]
    if summary["molecule_id"]!=mid or ref["molecule_id"]!=mid:raise ValueError("REPRODUCTION_MOLECULE_IDENTITY_CHANGED")
    if summary["cohort"]!=meta["cohort"] or summary["prior_status"]!=meta["Sprime_status"] or summary["expected_conformers"]!=meta["expected_conformers"]:
        raise ValueError("REPRODUCTION_ORIGINAL_COHORT_OR_N_CHANGED")
    seconds=float(summary["elapsed_seconds"])
    if not math.isfinite(seconds) or seconds<0:raise ValueError("FINITE_SCIENCE_TIMING_REQUIRED")
    if summary["status"]=="IMPLEMENTATION_ERROR":raise ValueError("IMPLEMENTATION_ERROR_NOT_ACCEPTABLE_CLOSURE")
    records={row["record_id"]:row for row in task["records"]}
    if len(records)!=len(task["records"]) or len(records)!=meta["expected_conformers"]:
        raise ValueError("WHOLE_ORIGINAL_PM7_POINTER_COUNT_REQUIRED")
    if summary.get("source_record_id") is not None and summary["source_record_id"] not in records:
        raise ValueError("SOURCE_ANCHOR_NOT_ORIGINAL_NATIVE_RECORD")
    previous={int(row["sprime_conf_idx"]):row for row in task["existing_conformers"]}
    if len(previous)!=len(task["existing_conformers"]):raise ValueError("DUPLICATE_ORIGINAL_SPRIME_INDEX")
    rows=packet["conformers"];old_ids=[];new_keys=set();lookup={}
    for position,row in enumerate(rows):
        if row["molecule_id"]!=mid or type(row["sprime_conf_idx"]) is not int or row["sprime_conf_idx"]!=position:
            raise ValueError("PILOT_PACKAGE_ROW_ID_OR_POSITION_CHANGED")
        z=np.asarray(row["atomic_numbers"],dtype="<i8");xyz=np.asarray(row["coordinates"],dtype="<f8")
        atom_sha=hashlib.sha256(z.tobytes()).hexdigest()
        if not math.isfinite(float(row["uff_energy_kcal_mol"])):raise ValueError("FINITE_ACCEPTED_UFF_ENERGY_REQUIRED")
        if row["status"]!="SUCCESS" or row["converged"] is not True or atom_sha!=row["atom_order_sha256"] or IO.geometry_sha(z,xyz)!=row["geometry_sha256"]:
            raise ValueError("REAL_ACCEPTED_COORDINATE_OR_ATOM_SHA_INVALID")
        if row["source_record_id"]!=summary["source_record_id"] or row["atom_order_sha256"]!=summary["atom_order_sha256"]:
            raise ValueError("SOURCE_ANCHOR_OR_ATOM_ORDER_CHANGED")
        if row["origin"]=="accepted_sprime":
            index=row["original_sprime_conf_idx"];prior=previous.get(index)
            if prior is None or index in old_ids or prior["status"]!="SUCCESS" or prior["converged"] is not True:
                raise ValueError("OLD_ACCEPTED_ID_NOT_ORIGINAL_UNIQUE_USABLE")
            if prior["atom_order_sha256"]!=atom_sha or prior["source_record_id"]!=row["source_record_id"] or IO.geometry_sha(z,prior["coordinates"])!=row["geometry_sha256"] or int(prior["seed"])!=row["seed"] or float(prior["uff_energy_kcal_mol"])!=row["uff_energy_kcal_mol"]:
                raise ValueError("OLD_COORDINATES_SOURCE_SEED_OR_ID_CHANGED")
            old_ids.append(index)
        elif row["origin"] in {"data_v1_fill_10N","data_v1_fill_retry1"}:
            expected_origin="data_v1_fill_retry1" if meta["cohort"]=="retry_once" else "data_v1_fill_10N"
            if row["origin"]!=expected_origin:raise ValueError("GENERATED_ORIGIN_DIFFERS_FROM_ORIGINAL_COHORT")
            key=(row["seed"],row["candidate_id"])
            if key in new_keys or type(row["candidate_id"]) is not int or row["candidate_id"]<0:
                raise ValueError("NEW_REAL_CANDIDATE_ID_REUSED")
            new_keys.add(key)
        else:raise ValueError("UNREGISTERED_CANDIDATE_ORIGIN")
        lookup[(mid,position)]=row
    if summary["usable_conformers"]!=len(rows):raise ValueError("SUMMARY_AND_REAL_CONFORMER_COUNT_DIFFER")
    if summary["status"]=="SUCCESS" and (len(rows)!=meta["expected_conformers"] or set(old_ids)!=set(previous)):
        raise ValueError("SUCCESS_MUST_RETAIN_ALL_OLD_AND_MATCH_ORIGINAL_N")
    if len(previous)+len(new_keys)>meta["expected_conformers"]:
        raise ValueError("OLD_PLUS_REAL_NEW_EXCEEDS_ORIGINAL_N")
    raw_candidates=packet["audit_candidates"]
    if (summary["status"]!="SUCCESS" or summary.get("audit_sample")) and summary.get("candidate_embedded",0)>0 and not raw_candidates:
        raise ValueError("FAILURE_OR_AUDIT_RAW_CANDIDATES_MISSING")
    detail={"molecule_id":mid,"cohort":meta["cohort"],"file_group":int(meta["file_group"]),
        "prior_status":meta["Sprime_status"],"status":summary["status"],"elapsed_seconds":seconds,
        "expected_original_N":meta["expected_conformers"],"original_accepted_count":len(previous),
        "old_references_in_package":len(old_ids),"new_real_accepted_count":len(new_keys),
        "merged_baseline_plus_new_count":len(previous)+len(new_keys),"package_conformers":len(rows),
        "raw_candidates_retained":len(raw_candidates),"old_original_sprime_conf_idx":sorted(old_ids),
        "below_dedup_threshold":sum(bool(row["below_dedup_threshold"]) for row in rows),
        "package_reference":ref,"physical_id_policy":"package row rank only; formal_v2 preserves old IDs and appends new IDs",
        "new_once_task_key_created":False}
    return summary,detail,lookup


def distribution(details):
    groups=defaultdict(list)
    for row in details:groups[(row["cohort"],row["prior_status"],row["file_group"])].append(row)
    result=[]
    for (cohort,prior,group),rows in sorted(groups.items()):
        times=sorted(row["elapsed_seconds"] for row in rows)
        result.append({"cohort":cohort,"prior_status":prior,"file_group":group,"molecules":len(rows),
            "status_counts":dict(sorted(Counter(row["status"] for row in rows).items())),
            "science_worker_seconds":sum(times),"minimum_seconds":times[0],"maximum_seconds":times[-1],
            "median_seconds":(times[(len(times)-1)//2]+times[len(times)//2])/2,
            "old_baseline_count":sum(row["original_accepted_count"] for row in rows),
            "old_references_in_packages":sum(row["old_references_in_package"] for row in rows),
            "new_real_accepted":sum(row["new_real_accepted_count"] for row in rows),
            "below_dedup_threshold":sum(row["below_dedup_threshold"] for row in rows),
            "raw_candidates_retained":sum(row["raw_candidates_retained"] for row in rows)})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",type=Path,required=True)
    p.add_argument("--pilot-receipt",type=Path,required=True);p.add_argument("--sacct-evidence",type=Path,required=True)
    p.add_argument("--root-preflight",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--cpu-runconfig",type=Path,required=True)
    a=p.parse_args();cfg=json.loads(a.config.read_text())
    if cfg["schema"]!="DATA_V1_SPRIME_PILOT_CLOSURE_CONFIG_V1" or cfg["expected_molecules"]!=336 or cfg["workers"]!=16:
        raise ValueError("EXACT336_READONLY_CLOSURE_CONFIG_REQUIRED")
    cpu_proof=cpu_admit(a.root_preflight,Path(__file__),a.cpu_runconfig,a.config,"closure")
    receipt_ref=IO.reference(a.pilot_receipt);receipt=json.loads(a.pilot_receipt.read_text())
    require_complete(receipt,336,cfg["expected_job_id"])
    prepared=json.loads(IO.require_pin(cfg["prepared"]).read_text());IO.require_pin(cfg["pilot_config"])
    if receipt["config"]!=cfg["pilot_config"] or receipt["prepared"]!=cfg["prepared"] or prepared["config"]!=cfg["pilot_config"] or prepared["molecules"]!=336:
        raise ValueError("REGISTERED_ORIGINAL_CONFIG_AND_PREPARED_REQUIRED")
    for ref in receipt["outputs"]+prepared["outputs"]:
        checkpoint();IO.require_pin(ref)
    def output_named(refs,name):
        matches=[ref for ref in refs if Path(ref["path"]).name==name]
        if len(matches)!=1:raise ValueError("UNIQUE_BOUND_OUTPUT_REQUIRED:"+name)
        return matches[0]
    manifest_ref=output_named(receipt["outputs"],"reproduction_manifest.json")
    refs=json.loads(Path(manifest_ref["path"]).read_text())
    tasks_ref=output_named(prepared["outputs"],"tasks.jsonl")
    tasks=list(map(json.loads,Path(tasks_ref["path"]).read_text().splitlines()))
    task_by_id=checked_ids(tasks,refs)
    if json.loads(Path(output_named(receipt["outputs"],"worker_failures.json")["path"]).read_text()):
        raise ValueError("WORKER_FAILURES_MUST_BE_EMPTY")
    evidence=json.loads(a.sacct_evidence.read_text())
    if evidence.get("schema")!="DATA_V1_SACCT_QUERY_EVIDENCE_V1" or evidence.get("query_returncode")!=0 or not isinstance(evidence.get("command_argv"),list) or not evidence["command_argv"] or Path(evidence["command_argv"][0]).name!="sacct":
        raise ValueError("ACTUAL_SUCCESSFUL_ROOT_SACCT_QUERY_EVIDENCE_REQUIRED")
    if datetime.fromisoformat(evidence["observed_at"]).tzinfo is None:raise ValueError("ACCOUNTING_EVIDENCE_TIMEZONE_REQUIRED")
    raw_ref=evidence["raw_sacct_reference"];raw=IO.require_pin(raw_ref).read_text()
    parents=accounting_from_raw(raw,receipt["runtime"]["job_id"])
    requested=list(map(str,evidence["requested_parent_job_ids"]))
    if len(set(requested))!=len(requested) or set(requested)!={row["job_id"] for row in parents}:
        raise ValueError("REQUESTED_AND_OBSERVED_ACCOUNTING_PARENT_SET_DIFFERS")
    summaries={};details=[];conformers={}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for summary,detail,rows in bounded_map(pool,read_package,[(ref,task_by_id[ref["molecule_id"]],cfg["max_package_uncompressed_bytes"]) for ref in refs]):
            summaries[summary["molecule_id"]]=summary;details.append(detail)
            if set(rows)&set(conformers):raise ValueError("DUPLICATE_REAL_PACKAGE_CONFORMER_KEY")
            conformers.update(rows)
    observed_counts=dict(Counter(row["status"] for row in summaries.values()))
    if observed_counts!=receipt["status_counts"] or sum(len(t["records"]) for t in tasks)<336:
        raise ValueError("FINAL_STATUS_OR_PM7_COUNTS_DIFFER_FROM_REAL_PACKAGES")
    worker_seconds=sum(float(row["elapsed_seconds"]) for row in summaries.values())
    if not math.isclose(worker_seconds,receipt["science_worker_seconds"],rel_tol=1e-12,abs_tol=1e-6):
        raise ValueError("PRODUCER_SCIENCE_TIMING_SUM_CHANGED")
    import pyarrow as pa
    import pyarrow.parquet as pq
    checkpoint()
    pa.set_cpu_count(16);pa.set_io_thread_count(2)
    mol_ref=output_named(receipt["outputs"],"molecules.parquet")
    mol=pq.read_table(mol_ref["path"]).to_pylist()
    if len(mol)!=336 or len({row["molecule_id"] for row in mol})!=336:raise ValueError("MOLECULE_PARQUET336_UNIQUE_REQUIRED")
    compare=("molecule_id","cohort","prior_status","status","expected_conformers","usable_conformers","elapsed_seconds")
    for row in mol:
        checkpoint()
        expected=summaries.get(row["molecule_id"])
        if expected is None or any(row.get(k)!=expected.get(k) for k in compare):raise ValueError("MOLECULE_PARQUET_DIFFERS_FROM_REPRODUCTION")
    conf_ref=output_named(receipt["outputs"],"conformers.parquet")
    from run_pilot import verify_readback
    checkpoint()
    readback=verify_readback(conf_ref["path"],list(conformers.values()))
    real=pq.read_table(conf_ref["path"]).to_pylist();seen=set()
    for row in real:
        checkpoint()
        key=(row["molecule_id"],row["sprime_conf_idx"]);expected=conformers.get(key)
        if key in seen or expected is None:raise ValueError("UNEXPECTED_OR_DUPLICATE_PARQUET_GEOMETRY")
        seen.add(key)
        for field in ("geometry_sha256","atom_order_sha256","uff_energy_kcal_mol","origin","seed","candidate_id","original_sprime_conf_idx","source_record_id","below_dedup_threshold","status","converged"):
            if row[field]!=expected[field]:raise ValueError("PARQUET_SOURCE_OR_GEOMETRY_IDENTITY_CHANGED:"+field)
    if seen!=set(conformers) or receipt["conformers"]!=len(real):raise ValueError("PARQUET_REAL_CONFORMER_COUNT_CHANGED")
    if IO.reference(a.pilot_receipt)!=receipt_ref:raise ValueError("FINAL_PILOT_RECEIPT_CHANGED_DURING_CLOSURE")
    out=IO.new_output_directory(a.output,cfg)
    checkpoint()
    accounting={"schema":"DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1","status":"ACTUAL_PARENT_ACCOUNTING_CLOSED",
        "query_returncode":0,"raw_sacct_reference":raw_ref,"parents":parents,
        "source_query_evidence":IO.reference(a.sacct_evidence),"observed_at":evidence["observed_at"]}
    IO.write_json_new(out/"actual_accounting.json",accounting)
    _,total_seconds=require_actual_accounting(out/"actual_accounting.json",receipt["runtime"]["job_id"])
    pilot_parent=next(row for row in parents if row["job_id"]==str(receipt["runtime"]["job_id"]))
    IO.write_json_new(out/"cohort_report.json",distribution(details))
    IO.write_json_new(out/"molecule_report.json",sorted(details,key=lambda row:row["molecule_id"]))
    report={"schema":"DATA_V1_SPRIME_PILOT_CLOSURE_REPORT_V1","status":"CLOSED_EVIDENCE_REQUIRES_ROOT_REVIEW",
        "pilot_receipt":receipt_ref,"prepared":cfg["prepared"],"pilot_tasks":tasks_ref,
        "pilot_reproduction_manifest":manifest_ref,"manifest_policy":"original producer manifest referenced unchanged",
        "molecules":336,"parquet_conformers":len(real),"status_counts":observed_counts,
        "cohort_report":IO.reference(out/"cohort_report.json"),"molecule_report":IO.reference(out/"molecule_report.json"),
        "parquet_float64_sha_readback":readback,"producer_parquet_readback":receipt["parquet_readback"],
        "actual_accounting":IO.reference(out/"actual_accounting.json"),"actual_included_parent_core_hours":total_seconds/3600,
        "actual_pilot_parent_core_hours":pilot_parent["alloc_cpus"]*pilot_parent["elapsed_raw_seconds"]/3600,
        "actual_parent_jobs":[row["job_id"] for row in parents],"science_worker_seconds":worker_seconds,
        "old_baseline_accepted_count":sum(row["original_accepted_count"] for row in details),
        "old_references_in_packages":sum(row["old_references_in_package"] for row in details),
        "new_real_accepted_count":sum(row["new_real_accepted_count"] for row in details),
        "raw_candidates_retained":sum(row["raw_candidates_retained"] for row in details),
        "original_worker_evidence":"configured16 only; original producer did not persist distinct worker PID/task counts",
        "scientific_generation_calls":0,"new_once_keys_created":0,"root_review_granted":False,
        "common_frozen":False,"full_science_authorized":False,"formal_hardware_admission_granted":False,
        "source_files_modified":False,"runtime":{"node":socket.gethostname(),"job_id":os.environ["SLURM_JOB_ID"],"configured_reader_threads":16},
        "config":IO.reference(a.config),"root_preflight":IO.reference(a.root_preflight),
        "cpu_runconfig":IO.reference(a.cpu_runconfig),"cpu_guard":cpu_proof,
        "execution_variant":"CPU_PARTITION_ANALYSIS_V1"}
    IO.write_json_new(out/"closure_report.json",report)
    IO.write_json_new(out/"root_review_draft.json",review_draft(receipt_ref,IO.reference(out/"actual_accounting.json"),
        manifest_ref,tasks_ref,IO.reference(out/"closure_report.json")))
    print(json.dumps({"status":report["status"],"molecules":336,"output":str(out)}))


if __name__=="__main__":main()
