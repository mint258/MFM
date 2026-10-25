"""Original16CPU64G formal batch; once ledger, natural drain, no unknown retry."""
from __future__ import annotations
import argparse
from collections import Counter
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
from pathlib import Path
import time

from full_common import IO,KERNEL_SHA,begin_attempt,config,ledger_path,runtime

VALUE=None


def init_worker(config_path):
    global VALUE
    VALUE=config(config_path)
    import science
    science.worker_init(VALUE["recipe_config"]["path"]) # immutable recipe only, not pilot authorization


def one(task):
    import science
    start=begin_attempt(VALUE,task)
    result=science.process_task(task)
    result["formal_start"]=start
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True);p.add_argument("--prepared",type=Path,required=True)
    p.add_argument("--root-preflight",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();value=config(a.config);env=runtime(value,a.root_preflight,a.config,science=True)
    prepared=json.loads(a.prepared.read_text())
    if prepared["status"]!="FORMAL_BATCH_INPUTS_READY" or prepared["config"]!=IO.reference(a.config):
        raise ValueError("CLOSED_MATCHING_BATCH_PREPARED_REQUIRED")
    IO.require_pin(prepared["plan"]);IO.require_pin(prepared["tasks"])
    plan=json.loads(Path(prepared["plan"]["path"]).read_text())
    if plan["status"]!="FULL_SPRIME_PLAN_FROZEN" or plan["pilot_only"] is not False or plan["kernel_sha256"]!=KERNEL_SHA:
        raise ValueError("REAL_FROZEN_FULL_PLAN_REQUIRED")
    IO.require_pin(plan["root_review"]);IO.require_pin(plan["draft"])
    batch=prepared["batch"];request=json.loads(a.root_preflight.read_text())["request"]
    if request["wall_seconds"]!=batch["wall_seconds"] or request["cpus"]!=16:
        raise ValueError("ROOT_REQUEST_DIFFERS_FROM_REVIEWED_BATCH")
    tasks=[json.loads(line) for line in Path(prepared["tasks"]["path"]).read_text().splitlines()]
    if len(tasks)!=batch["molecules"] or len({t["meta"]["task_key"] for t in tasks})!=len(tasks):
        raise ValueError("BATCH_TASKS_NOT_UNIQUE_OR_COMPLETE")
    for task in tasks:
        if ledger_path(value,task["meta"]["task_key"]).exists():raise ValueError("TASK_ALREADY_CONSUMED_OR_UNKNOWN")
    out=IO.new_output_directory(a.output,value);(out/"reproduction").mkdir()
    from run_pilot import persist_result,parquet_new,verify_readback
    start=time.monotonic();next_index=0;active={};results=[];records=[];errors=[];stop_reason=None
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context("spawn"),initializer=init_worker,initargs=(str(a.config),)) as pool:
        while active or next_index<len(tasks):
            elapsed=time.monotonic()-start
            if elapsed*env["cpus"]>1.5*batch["estimated_allocated_core_seconds"]:
                stop_reason=stop_reason or "ACTUAL_COST_EXCEEDS_1P5_PILOT_ESTIMATE"
            elif elapsed>=batch["wall_seconds"]-value["stop_dispatch_before_wall_seconds"]:
                stop_reason=stop_reason or "WALL_DISPATCH_CUTOFF"
            while stop_reason is None and len(active)<16 and next_index<len(tasks):
                task=tasks[next_index];next_index+=1
                active[pool.submit(one,task)]=task
            if not active:break
            done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
            for future in done:
                task=active.pop(future);mid=task["meta"]["molecule_id"]
                try:
                    result=future.result()
                    records.append(persist_result(out,mid,result,value["max_output_bytes"]))
                    results.append(result)
                    if result["summary"]["status"]=="IMPLEMENTATION_ERROR":
                        stop_reason=stop_reason or "IMPLEMENTATION_ERROR_STOP_DISPATCH"
                except Exception as exc:
                    errors.append({"molecule_id":mid,"task_key":task["meta"]["task_key"],"error":repr(exc)})
                    stop_reason=stop_reason or "UNKNOWN_OR_FAILED_STARTED_TASK_STOP_DISPATCH"
    summaries=[r["summary"] for r in results]
    conformers=sorted((row for r in results for row in r["conformers"]),key=lambda row:(row["molecule_id"],row["sprime_conf_idx"]))
    parquet_new(out/"molecules.parquet",summaries)
    parquet_new(out/"conformers.parquet",conformers,coordinates=True)
    readback=verify_readback(out/"conformers.parquet",conformers)
    readback={"status":"ALL_FORMAL_BATCH_GEOMETRIES_FLOAT64_SHA_READBACK_PASSED",
              "underlying_check_status":readback["status"],"records":readback["records"]}
    IO.write_json_new(out/"reproduction_manifest.json",records)
    IO.write_json_new(out/"errors.json",errors)
    unstarted=tasks[next_index:]
    unknown=[t["meta"]["task_key"] for t in tasks[:next_index] if t["meta"]["molecule_id"] not in {r["summary"]["molecule_id"] for r in results}]
    if stop_reason=="WALL_DISPATCH_CUTOFF" and not errors and not unknown:
        status="FORMAL_BATCH_PARTIAL_UNSTARTED_ONLY"
    elif stop_reason or errors or unknown:status="FORMAL_BATCH_INCOMPLETE_REQUIRES_ROOT_REVIEW"
    else:status="FORMAL_BATCH_COMPLETED_REQUIRES_ACTUAL_ACCOUNTING"
    IO.write_json_new(out/"receipt.json",{"schema":"SPRIME_FORMAL_BATCH_RECEIPT_V1","status":status,
        "runtime":env,"plan":prepared["plan"],"prepared":IO.reference(a.prepared),"batch":batch,
        "config":IO.reference(a.config),"recipe_config":value["recipe_config"],"kernel_sha256":KERNEL_SHA,
        "completed_molecules":len(results),"submitted_molecules":next_index,"stop_reason":stop_reason,
        "actual_worker_task_counts":[{"pid":pid,"pid_start_ticks":ticks,"completed_tasks":count}
            for (pid,ticks),count in sorted(Counter((r["formal_start"]["pid"],r["formal_start"]["pid_start_ticks"]) for r in results).items())],
        "configured_workers":16,
        "unknown_started_tasks":unknown,"errors":errors,"unstarted_tasks":unstarted,
        "reproduction_manifest":IO.reference(out/"reproduction_manifest.json"),"parquet_readback":readback,
        "outputs":[IO.reference(out/name) for name in ("molecules.parquet","conformers.parquet","errors.json")],
        "elapsed_seconds":time.monotonic()-start,"estimated_allocated_core_seconds":batch["estimated_allocated_core_seconds"],
        "original_data_modified":False,"signals_sent":False,"automatic_retry":False,"common_population_frozen":False})
    return 0 if status in {"FORMAL_BATCH_COMPLETED_REQUIRES_ACTUAL_ACCOUNTING","FORMAL_BATCH_PARTIAL_UNSTARTED_ONLY"} else 1


if __name__=="__main__":raise SystemExit(main())
