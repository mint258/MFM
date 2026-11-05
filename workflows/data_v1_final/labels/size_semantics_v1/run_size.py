"""Approved isolated physical-target size pass; never writes the old registry."""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import multiprocessing
import os
from pathlib import Path
import time

from size_shared import (budget,canonical_bytes,connect,guard,load,merge_qr,new_root,ref,require,save,
                         semantic_sha,source_inputs,unique_bytes)
from aggregate import target_catalog
from build_proposal import build
from size_worker import initialize,run
from rank_sql import rho


def pass_run(cfg,source_cfg,plan,targets,jobs,phase,models,out):
    directory=out/phase;directory.mkdir();context=multiprocessing.get_context("spawn")
    barrier=context.Barrier(16);event=context.Event();pins=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=initialize,
            initargs=(cfg,source_cfg,plan,targets,str(directory),barrier,event,phase,models)) as pool:
        for pin in pool.map(run,jobs,chunksize=1):pins.append(pin);budget(out,cfg["output_cap_bytes"])
    rows=[load(require(p)) for p in pins]
    if len(rows)!=len(jobs) or len({r["pid"] for r in rows})!=16:raise ValueError("SIZE_REQUIRES_ALL_GROUPS_AND_16_ACTUAL_WORKERS")
    save(directory/"manifest.json",{"phase":phase,"group_receipts":pins,"actual_worker_pids":sorted({r["pid"] for r in rows})},out,cfg["output_cap_bytes"])
    return rows,pins


def models_from(rows,targets,scope):
    result={}
    for t in targets:
        if t["operation"]!="TRAIN_ELEMENT_RESIDUAL_SCALAR":continue
        tid=t["target_id"];model=merge_qr([r["HOF_TSQR"][tid] for r in rows])
        if "coefficients" in model:model["status"]="MATCHED_SCOPE_TRAIN_HOF_REFERENCE";model["scope"]=scope
        result[tid]=model
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--root-preflight",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    cfg,proof=guard(a.config,a.root_preflight);plan,scan,red,receipts,source_cfg=source_inputs(cfg)
    proposal_cfg=load(require(cfg["proposal_config"]))
    for pin in [proposal_cfg["registry"],*proposal_cfg["lineage_sources"]]:require(pin)
    proposal=build(proposal_cfg,load(proposal_cfg["registry"]["path"]));fields=load(require(plan["field_map"]))
    targets=target_catalog(proposal,fields)
    root=new_root(a.output,cfg["external_output_root"]);cap=cfg["output_cap_bytes"];db=connect(root,spill="4GiB");started=time.monotonic()
    try:
        fit_sides={};authority=None
        if cfg["scope"]=="FINAL_FROZEN_COMMON_TRAIN":
            if proof["request"]["pilot"] is not False or not proof["request"]["root_review"].get("accepted_pilot_reference"):
                raise ValueError("FINAL_SIZE_REQUIRES_ROOT_NONPILOT_REQUEST_AND_MEASURED_PILOT")
            from authority import install_authority
            from sources import datasets,prepare_sides
            authority=install_authority(db,{"authority":cfg["final_authority"]})
            ds=load(require(cfg["final_dataset_manifest"]))
            ready,pending=datasets({"datasets":[{"dataset_id":ds["dataset_id"],"label_group":"P_D","manifest":cfg["final_dataset_manifest"]}]})
            if pending or ready[0]["dataset"]["group_plan"]!=cfg["plan"] or ready[0]["dataset"]["mask_scan_manifest"]!=cfg["mask_scan"]:
                raise ValueError("FINAL_SIZE_DATASET_AND_EXACT_MASK_SCOPE_DIFFERS")
            sides,totals=prepare_sides(db,cfg,ready,root)
            fit_sides={r["group_index"]:r["side_table"] for r in sides}
            save(root/"fit_population.json",{"authority":authority,"side_tables":sides,"totals":totals},root,cap)
        else:
            save(root/"scope_provisional.json",{"scope":cfg["scope"],"full_common_population_frozen":False,
                "diagnostic_exclusions_applied":False,"role":"existing canonical source TRAIN only",
                "source_plan":cfg["plan"],"coverage_fingerprint":plan["coverage_fingerprint"]},root,cap)
        jobs=[{"work_index":i,"group":g,"mask_receipt":receipts[g["group_index"]],"fit_side":fit_sides.get(g["group_index"])} for i,g in enumerate(plan["groups"])]
        first,first_pins=pass_run(cfg,source_cfg,plan,targets,jobs,"hof",{},root)
        models=models_from(first,targets,cfg["scope"])
        model_pin=save(root/"HOF_TRAIN_element_reference.json",{"scope":cfg["scope"],"fit_role":"TRAIN_ONLY","fields":models,
            "plan":cfg["plan"],"mask_scan":cfg["mask_scan"],"authority":authority},root,cap)
        rows,rho_pins=pass_run(cfg,source_cfg,plan,targets,jobs,"rho",models,root)
        counts=collections.Counter();denominators=collections.Counter();size_bins=collections.Counter();conformers=collections.Counter();paths=[]
        for x,y in zip(first,rows):
            if any(x[k]!=y[k] for k in ("group_index","owner_index","fit_side","fit_records","fit_molecules","source_fit_value_mask_sha256","HOF_fit_mass_sha256","target_record_denominators")):
                raise ValueError("SIZE_SOURCE_FIT_MASK_OR_HOF_MASS_CHANGED_BETWEEN_PASSES")
            counts.update(y["counts"]);denominators.update(y["target_record_denominators"])
            for row in y["missingness_by_heavy_count"]:size_bins[row["target_id"],row["heavy_atoms"],row["reason"]]+=row["records"]
            for row in y["valid_conformer_count_per_molecule"]:conformers[row["target_id"],row["valid_conformers"]]+=row["molecules"]
            for pin in y["outputs"]:paths.append(str(require(pin)))
        n=sum(r["fit_records"] for r in rows)
        if set(denominators)!={t["target_id"] for t in targets} or any(value!=n for value in denominators.values()):
            raise ValueError("GLOBAL_SIZE_TARGET_RECORD_DENOMINATORS_NOT_CONSERVED")
        variants=[row[0] for row in db.execute("SELECT DISTINCT variant FROM read_parquet("+__import__("support").path_list(paths)+") ORDER BY variant").fetchall()]
        results=[]
        for t in targets:
            tid=t["target_id"];stats={variant:rho(db,paths,tid,variant) for variant in variants}
            primary=stats.get("record_primary",{"pair_n":0,"rho":None,"status":"NO_VALID_AGGREGATE"})
            if primary["pair_n"]!=counts[tid+"|eligible"]:raise ValueError("SIZE_PRIMARY_RANK_AND_AGGREGATE_MASS_DIFFERS")
            molecule_n=sum(m for (key,k),m in conformers.items() if key==tid)
            if stats.get("molecule_median_sensitivity",{}).get("pair_n",0)!=molecule_n:
                raise ValueError("SIZE_MOLECULE_WEIGHTING_SENSITIVITY_MASS_DIFFERS")
            if t["operation"]=="TRAIN_ELEMENT_RESIDUAL_SCALAR" and models[tid].get("n",0)!=counts[tid+"|HOF_reference_valid"]:
                raise ValueError("HOF_REFERENCE_AND_RHO_ELIGIBILITY_SCOPE_DIFFERS")
            results.append({**t,"scope":cfg["scope"],"canonical_record_denominator":denominators[tid],"rho_results":stats,
                "primary_rho":primary["rho"],"primary_pair_n":primary["pair_n"],"valid_molecules":molecule_n,
                "size_family_candidate":None if primary["rho"] is None else abs(primary["rho"])>=.95,
                "automatic_final_family_freeze":False,"family_v1_final":None,
                "freeze_blockers":["Root/model joint family/head review","source unit/runtime/precision reconciliation","independent real source frame/origin audit"]+
                  (["BASIS_INVARIANCE_UNPROVEN"] if t["basis_invariance_status"]=="BASIS_INVARIANCE_UNPROVEN" else [])+
                  (["FINAL_COMMON_TRAIN_DIAGNOSTIC_SCOPE_NOT_APPLIED"] if authority is None else [])})
        target_by_member={field:t for t in results for field in t["member_field_keys"]}
        components=[{**r,"physical_target_result":target_by_member[r["field_key"]],"family_v1_final":None,
            "native_precision_review":("INTEGER_HBA_RECOMPUTED_BY_WP5_CALL_RUNTIME" if r["field_key"]=="D20.NumHAcceptors" else
                "INHERITED_LMDB_BITS_GENERATOR_FLOAT32_IMPLEMENTATION_ORIGINAL_RUNTIME_AND_ACTUAL_DTYPE_PENDING" if r["field_key"].startswith("D20.") else
                "PERMANENT_FLOAT64_CONTAINER_DOES_NOT_ESTABLISH_NATIVE_PRINTED_PRECISION")} for r in proposal["components"]]
        stat_pin=save(root/"physical_target_size_rho.json",{"schema":"PHYSICAL_TARGET_SIZE_RHO_RESULT_V1","scope":cfg["scope"],
            "target_count":129,"component_count":146,"fit_records":n,"fit_molecules":sum(r["fit_molecules"] for r in rows),
            "targets":results,"components":components,"HOF_reference":model_pin,"primary_weighting":"one canonical record one vote",
            "molecule_sensitivity":"one molecule one median-of-valid-geometries vote","new_label_masks":0,
            "source_labels_changed":False,"registry_final":False,"Pprime":"PENDING_INDEPENDENT_UFF_SOURCE",
            "missingness_by_heavy_count":[{"target_id":key,"heavy_atoms":heavy,"reason":reason,"records":v} for (key,heavy,reason),v in sorted(size_bins.items())],
            "valid_conformer_count_per_molecule":[{"target_id":key,"valid_conformers":k,"molecules":v} for (key,k),v in sorted(conformers.items())]},root,cap)
        save(root/"manifest.json",{"status":"SIZE_RHO_PROVISIONAL_SCIENTIFIC_RESULTS_REVIEW_REQUIRED" if authority is None else "SIZE_RHO_FINAL_POPULATION_RESULTS_JOINT_FREEZE_PENDING",
            "config":ref(a.config),"source_plan":cfg["plan"],"source_mask_scan":cfg["mask_scan"],"source_mask_reduction":cfg["mask_reduction"],
            "HOF_pass_receipts":first_pins,"rho_pass_receipts":rho_pins,"result":stat_pin,"actual_workers_each_pass":16,
            "source_passes":2,"authority":authority,"elapsed_seconds":time.monotonic()-started,"unique_inode_output_bytes_before_manifest":unique_bytes(root),
            "root_preflight":ref(a.root_preflight),"registry_final":False,"normalization_completed":False},root,cap)
        print("PHYSICAL_TARGET_SIZE_RHO_COMPLETE_REVIEW_REQUIRED",129,146,cfg["scope"],flush=True)
    except BaseException as exc:
        save(root/"failure.json",{"status":"SIZE_RHO_FAILED_PARTIAL_EVIDENCE_PRESERVED","type":type(exc).__name__,"error":str(exc)});raise
    finally:db.close()


if __name__=="__main__":main()
