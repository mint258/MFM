"""Isolated shared imports and source bindings for the approved size variant."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

LABELS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(LABELS/"streaming_v1"))
sys.path.insert(0,str(LABELS/"normalization_v1"))
from support import (ParquetSink,budget,identity,load,new_root,path_list,ref,require,
                     root_guard,save,sqlstr,unique_bytes,write_blob)
from calibration import TSQR,merge_qr
from runtime import canonical_bytes,semantic_sha,connect


def adapter_from(pin,source_cfg,plan,out,barrier,event):
    path=require(pin)
    spec=importlib.util.spec_from_file_location("_size_canonical_adapter",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.init_worker(source_cfg,plan,{},str(out),barrier,event,"size_rho",{}, {})
    return module


def guard(cfg_path,intent):
    cfg=load(cfg_path)
    if cfg["schema"]!="PHYSICAL_TARGET_SIZE_RHO_CONFIG_V1" or cfg["workers"]!=16:
        raise ValueError("UNKNOWN_SIZE_RHO_CONFIG_OR_WORKER_COUNT")
    proof=root_guard(intent,cfg_path,cfg["output_cap_bytes"],cfg["wall_seconds"])
    if (proof["request"]["memory_gib"]<cfg["memory_gib"] or cfg["memory_gib"]<64
            or int(os.environ.get("SLURM_MEM_PER_NODE","0"))<cfg["memory_gib"]*1024):
        raise ValueError("SIZE_RHO_PRODUCTION_REQUIRES_REVIEWED_AND_ACTUAL_64_GIB")
    if os.environ.get("CUDA_VISIBLE_DEVICES")!="" or any(os.environ.get(k)!="1" for k in
            ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS")):
        raise ValueError("SIZE_RHO_CPU_ONLY_SINGLE_THREAD_WORKER_ENV_REQUIRED")
    return cfg,proof


def source_inputs(cfg):
    plan=load(require(cfg["plan"]));scan=load(require(cfg["mask_scan"]));red=load(require(cfg["mask_reduction"]))
    if (scan["plan"]!=cfg["plan"] or red["plan"]!=cfg["plan"] or red["scan_manifest"]!=cfg["mask_scan"]
            or scan["coverage_fingerprint"]!=plan["coverage_fingerprint"] or red["coverage_fingerprint"]!=plan["coverage_fingerprint"]
            or red["stop_fields"] or red["records"]!=plan["records"]
            or any(r["new_mask_fraction"]>.01 for r in red["field_counts"].values())):
        raise ValueError("SIZE_MASK_PLAN_COVERAGE_OR_ONE_PERCENT_GATE_DIFFERS")
    if cfg["scope"]=="PROVISIONAL_SOURCE_TRAIN_PILOT":
        actual={"records":plan["records"],"molecules":plan["molecules"],"groups":len(plan["groups"]),"coverage_fingerprint":plan["coverage_fingerprint"]}
        if plan["mode"]!="pilot" or actual!=cfg["expected_pilot"] or cfg["final_authority"] is not None:
            raise ValueError("SIZE_PILOT_REQUIRES_EXACT_BOUNDED_SCOPE_WITHOUT_PRETEND_COMMON_AUTHORITY")
    elif cfg["scope"]=="FINAL_FROZEN_COMMON_TRAIN":
        if plan["mode"]!="full" or scan["phase"]!="mask" or cfg["final_authority"] is None or cfg["final_dataset_manifest"] is None:
            raise ValueError("FINAL_SIZE_SCOPE_REQUIRES_FROZEN_COMMON_DIAGNOSTIC_AND_FULL_MASK_SOURCE")
    else:raise ValueError("UNKNOWN_SIZE_RHO_SCOPE")
    receipts={}
    for pin in scan["group_receipts"]:
        row=load(require(pin));index=row["group_index"]
        if index in receipts or row["status"]!="SOURCE_GROUP_SCANNED":raise ValueError("SIZE_MASK_GROUP_DUPLICATE_OR_INCOMPLETE")
        receipts[index]=row
    if set(receipts)!={g["group_index"] for g in plan["groups"]} or len(plan["groups"])<16:
        raise ValueError("SIZE_REQUIRES_COMPLETE_SOURCE_GROUP_SET_AND_16_WORKERS")
    for g in plan["groups"]:
        r=receipts[g["group_index"]]
        if r["owner_index"]!=g["owner_index"] or r["records"]!=g["expected_records"]:
            raise ValueError("SIZE_MASK_OWNER_GROUP_BINDING_DIFFERS")
    return plan,scan,red,receipts,load(require(plan["config"]))
