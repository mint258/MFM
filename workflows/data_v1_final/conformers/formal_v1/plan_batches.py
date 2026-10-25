"""Draft/freeze measured formal shards, or plan only never-started continuation tasks."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import gzip
import json
import math
import os
from pathlib import Path
import time

from full_common import IO,KERNEL_SHA,authority_roles,config,exclusive_json,ledger_path,require_actual_accounting,require_budget_review,review,runtime,task_key,q


def cohort(row):
    if row["Sprime_status"]=="UFF_UNSUPPORTED":return "unsupported"
    return "fill_10N" if row["Sprime_status"]=="INSUFFICIENT_UNIQUE_CONFORMERS" else "retry_once"


def measured_model(pilot_records,tasks,actual_core_seconds):
    groups=defaultdict(list);total=0
    for record in pilot_records:
        value=record["summary"];mid=value["molecule_id"]
        seconds=float(value["elapsed_seconds"])
        if not math.isfinite(seconds) or seconds<0:raise ValueError("INVALID_ACTUAL_PILOT_TIMING")
        total+=seconds
        meta=tasks[mid]["meta"]
        if meta["cohort"] in {"fill_10N","retry_once"}:
            groups[(meta["cohort"],int(meta["file_group"]))].append(seconds)
    if total<=0 or not groups:raise ValueError("PILOT_HAS_NO_MEASURED_TIMING")
    overhead=max(1.0,actual_core_seconds/total)
    return groups,overhead,max(0.0,actual_core_seconds-total)


def split_batches(rows,config_value,fixed_overhead=0):
    result=[];current=[];estimated=0
    capacity=(config_value["wall_seconds"]-config_value["stop_dispatch_before_wall_seconds"])*16-fixed_overhead
    if capacity<=0:raise ValueError("MEASURED_STARTUP_OVERHEAD_EXCEEDS_BATCH_CAPACITY")
    for row in rows:
        cost=row["estimated_allocated_core_seconds"]
        if cost>capacity:raise ValueError("SINGLE_MOLECULE_PREDICTION_EXCEEDS_BATCH_CAPACITY")
        if current and (len(current)>=config_value["max_molecules_per_batch"] or estimated+cost>capacity):
            result.append((current,estimated+fixed_overhead));current=[];estimated=0
        current.append(row);estimated+=cost
    if current:result.append((current,estimated+fixed_overhead))
    return result


def draft(args,value):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    runtime(value,args.root_preflight,args.config)
    decision,pilot,actual=review(args.pilot_review,for_planning=True)
    meta_tasks={task["meta"]["molecule_id"]:task for task in map(json.loads,Path(decision["pilot_tasks"]["path"]).read_text().splitlines())}
    manifest=json.loads(Path(decision["pilot_reproduction_manifest"]["path"]).read_text())
    pilot_records=[];seen=set()
    for ref in manifest:
        IO.require_pin(ref)
        result=json.loads(gzip.decompress(Path(ref["path"]).read_bytes()))
        mid=result["summary"]["molecule_id"]
        if mid in seen or mid not in meta_tasks:raise ValueError("PILOT_RESULT_ID_DUPLICATE_OR_UNEXPECTED")
        seen.add(mid);pilot_records.append(result)
    if len(seen)!=336:raise ValueError("ALL336_REAL_PILOT_RESULT_PACKAGES_REQUIRED")
    groups,overhead,fixed_overhead=measured_model(pilot_records,meta_tasks,actual)
    roles_ref,role_parts=authority_roles(value)
    db=duckdb.connect();db.execute("SET threads=16");db.execute("SET memory_limit='20GB'")
    db.execute("CREATE VIEW p AS SELECT * FROM read_parquet("+q(value["per_molecule"]["path"])+")")
    db.execute("CREATE VIEW r AS SELECT * FROM read_parquet(["+",".join(q(r["path"]) for r in role_parts)+"])")
    source=db.execute("""SELECT p.*,r.file_group,r.records,r.source_role,r.effective_role
        FROM p JOIN r USING(molecule_id) WHERE p.Sprime_conformers<p.S_conformers
        ORDER BY r.file_group,p.molecule_id""").fetch_arrow_table().to_pylist()
    if len(source)!=value["expected_original_deficit_molecules"] or len({r["molecule_id"] for r in source})!=len(source):
        raise ValueError("ORIGINAL99351_DEFICIT_MANIFEST_COUNT_MISMATCH")
    by_id={row["molecule_id"]:row for row in source}
    imported=[];to_run=[];unsupported=[];global_max=max(max(v) for v in groups.values())
    pilot_by_id={row["summary"]["molecule_id"]:row for row in pilot_records}
    for row in source:
        mid=row["molecule_id"];kind=cohort(row)
        row.update(cohort=kind,expected_conformers=int(row["S_conformers"]),
                   task_key=task_key(mid,kind),max_heavy_atoms=int(row["heavy_atoms"]))
        if row["records"]!=row["S_conformers"]:raise ValueError("FORMAL_ROLE_EXPECTED_PM7_COUNT_MISMATCH")
        if kind=="unsupported":unsupported.append(row);continue
        if mid in pilot_by_id:
            if meta_tasks[mid]["meta"]["cohort"]!=kind:raise ValueError("PILOT_COHORT_NO_LONGER_MATCHES_BASELINE")
            imported.append({"molecule_id":mid,"task_key":row["task_key"],"cohort":kind,
                "status":pilot_by_id[mid]["summary"]["status"],
                "source":next(ref for ref in manifest if ref["molecule_id"]==mid)})
            continue
        measured=groups.get((kind,int(row["file_group"])))
        row["timing_basis"]="measured_cohort_file_group_max" if measured else "conservative_global_measured_max"
        row["estimated_allocated_core_seconds"]=max(0.001,max(measured) if measured else global_max)*overhead
        to_run.append(row)
    output=IO.new_output_directory(args.output,value)
    (output/"task_shards").mkdir()
    batches=[];total=0
    for index,(rows,estimate) in enumerate(split_batches(to_run,value,fixed_overhead)):
        path=output/"task_shards"/f"batch-{index:05d}.parquet"
        IO.write_parquet_new(path,pa.Table.from_pylist(rows))
        batches.append({"batch_id":f"batch-{index:05d}","tasks":IO.reference(path),"molecules":len(rows),
                        "estimated_allocated_core_seconds":estimate,"cpus":16,"memory_gib":64,
                        "wall_seconds":value["wall_seconds"]})
        total+=estimate
    IO.write_parquet_new(output/"original_deficits.parquet",pa.Table.from_pylist(source))
    IO.write_parquet_new(output/"unsupported.parquet",pa.Table.from_pylist(unsupported))
    IO.write_json_new(output/"pilot_imports.json",imported)
    report={"schema":"SPRIME_FORMAL_DRAFT_V1","status":"DRAFT_NOT_AUTHORITY_TO_RUN_FULL",
        "config":IO.reference(args.config),"pilot_review":IO.reference(args.pilot_review),
        "pilot_receipt":decision["pilot_receipt"],"pilot_actual_core_seconds":actual,
        "roles_manifest":roles_ref,"kernel_sha256":KERNEL_SHA,"recipe_config":value["recipe_config"],
        "original_deficits":IO.reference(output/"original_deficits.parquet"),
        "unsupported":IO.reference(output/"unsupported.parquet"),"pilot_imports":IO.reference(output/"pilot_imports.json"),
        "original_deficit_molecules":len(source),"unsupported_molecules":len(unsupported),
        "pilot_consumed_deficit_molecules":len(imported),"unstarted_planned_molecules":len(to_run),
        "batches":batches,"estimated_formal_core_hours":total/3600,
        "cost_model":{"basis":"maximum measured molecule time by cohort/file_group times actual allocation overhead",
                      "allocation_overhead_factor":overhead,"unobserved_groups_use_global_max":True},
        "measured_fixed_startup_and_accounting_overhead_core_seconds_per_batch":fixed_overhead,
        "requires_explicit_over500_root_review":total>500*3600,"pilot_only":False,
        "scientific_jobs_submitted":False,"original_data_modified":False}
    IO.write_json_new(output/"draft.json",report)
    print(json.dumps({"status":report["status"],"batches":len(batches),"core_hours":total/3600}))


def freeze(args,value):
    runtime(value,args.root_preflight,args.config)
    draft_ref=IO.reference(args.draft)
    data=json.loads(args.draft.read_text())
    decision=json.loads(args.full_review.read_text())
    if data["status"]!="DRAFT_NOT_AUTHORITY_TO_RUN_FULL" or decision.get("schema")!="SPRIME_FORMAL_PLAN_ROOT_APPROVAL_V1" or decision.get("status")!="APPROVED" or decision["draft_reference"]!=draft_ref:
        raise ValueError("EXPLICIT_REVIEW_OF_THIS_DRAFT_REQUIRED")
    estimate=float(data["estimated_formal_core_hours"])
    require_budget_review(estimate,decision)
    if data["config"]!=IO.reference(args.config) or data["kernel_sha256"]!=KERNEL_SHA:
        raise ValueError("DRAFT_SCIENTIFIC_CONFIG_CHANGED")
    IO.require_pin(data["pilot_review"])
    review(data["pilot_review"]["path"],for_planning=True)
    for batch in data["batches"]:IO.require_pin(batch["tasks"])
    imported=json.loads(IO.require_pin(data["pilot_imports"]).read_text())
    for row in imported:
        payload={"schema":"SPRIME_PILOT_ATTEMPT_IMPORTED_V1","molecule_id":row["molecule_id"],
            "task_key":row["task_key"],"cohort":row["cohort"],"source":row["source"],"status":row["status"],
            "kernel_sha256":KERNEL_SHA}
        target=ledger_path(value,row["task_key"])
        if target.exists():
            if json.loads(target.read_text())!=payload:raise ValueError("PILOT_ATTEMPT_LEDGER_CONFLICT")
        else:exclusive_json(target,payload)
    out=IO.new_output_directory(args.output,value)
    result={"schema":"SPRIME_FORMAL_PLAN_V1","status":"FULL_SPRIME_PLAN_FROZEN","draft":draft_ref,
        "root_review":IO.reference(args.full_review),"config":IO.reference(args.config),"batches":data["batches"],
        "pilot_imports":data["pilot_imports"],"unsupported":data["unsupported"],"original_deficits":data["original_deficits"],
        "roles_manifest":data["roles_manifest"],"estimated_formal_core_hours":estimate,
        "kernel_sha256":KERNEL_SHA,"formal_cpus":16,"formal_memory_gib":64,"pilot_only":False,
        "parent_plan":data.get("parent_plan"),
        "scientific_execution_completed":False,"common_population_frozen":False}
    IO.write_json_new(out/"plan.json",result)


def continuation(args,value):
    import pyarrow as pa
    runtime(value,args.root_preflight,args.config)
    result=json.loads(args.batch_receipt.read_text())
    if result.get("stop_reason")!="WALL_DISPATCH_CUTOFF" or result["status"]!="FORMAL_BATCH_PARTIAL_UNSTARTED_ONLY":
        raise ValueError("ONLY_NATURAL_WALL_CUTOFF_CAN_CREATE_CONTINUATION")
    require_actual_accounting(args.accounting,result["runtime"]["job_id"])
    if result.get("unknown_started_tasks") or result.get("errors"):
        raise ValueError("UNKNOWN_OR_FAILED_ATTEMPTS_NEVER_AUTO_RETRY")
    tasks=[]
    for row in result["unstarted_tasks"]:
        if ledger_path(value,row["meta"]["task_key"]).exists():
            raise ValueError("CONTINUATION_TASK_WAS_ALREADY_STARTED")
        tasks.append(row)
    if not tasks:raise ValueError("NO_UNSTARTED_TASKS_CONTINUATION_NOT_NEEDED")
    out=IO.new_output_directory(args.output,value)
    parent=json.loads(IO.require_pin(result["plan"]).read_text())
    base=json.loads(IO.require_pin(parent["draft"]).read_text())
    (out/"task_shards").mkdir()
    shard=out/"task_shards"/"continuation.parquet"
    metas=[task["meta"] for task in tasks];IO.write_parquet_new(shard,pa.Table.from_pylist(metas))
    estimate=sum(meta["estimated_allocated_core_seconds"] for meta in metas)+base["measured_fixed_startup_and_accounting_overhead_core_seconds_per_batch"]
    bid="continuation-"+result["batch"]["batch_id"]+"-"+IO.digest(args.batch_receipt)[:8]
    base.update(parent_plan=result["plan"],continuation_of_batch_receipt=IO.reference(args.batch_receipt),
        actual_accounting=IO.reference(args.accounting),batches=[{"batch_id":bid,"tasks":IO.reference(shard),
        "molecules":len(tasks),"estimated_allocated_core_seconds":estimate,"cpus":16,"memory_gib":64,
        "wall_seconds":value["wall_seconds"]}],estimated_formal_core_hours=estimate/3600,
        unstarted_planned_molecules=len(tasks),requires_explicit_over500_root_review=estimate>500*3600,
        scientific_jobs_submitted=False,retry_started_tasks=False)
    IO.write_json_new(out/"draft.json",base) # freeze mode still requires a new explicit Root review


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=["draft","freeze","continuation"])
    p.add_argument("--config",type=Path,required=True);p.add_argument("--root-preflight",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--pilot-review",type=Path);p.add_argument("--draft",type=Path);p.add_argument("--full-review",type=Path)
    p.add_argument("--batch-receipt",type=Path);p.add_argument("--accounting",type=Path)
    args=p.parse_args();value=config(args.config)
    {"draft":draft,"freeze":freeze,"continuation":continuation}[args.mode](args,value)


if __name__=="__main__":main()
