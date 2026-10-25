"""Conserve all prepared record/task slots, reduce TRAIN references, apply gates."""
from __future__ import annotations

import argparse
import collections
import hashlib
import heapq
import json
import math
from pathlib import Path
import time

from calibration import advance,initial_queries,merge_qr
from support import budget,load,new_root,path_list,ref,require,root_guard,save,sqlstr,checkpoint,checkpoint_iter


def ordinal_digest(pin):
    checkpoint()
    import numpy as np
    import pyarrow.parquet as pq
    h=hashlib.sha256();n=0;previous=-1
    for batch in checkpoint_iter(pq.ParquetFile(require(pin)).iter_batches(batch_size=65536,columns=["record_ordinal"])):
        values=batch.column(0).to_numpy(zero_copy_only=False)
        if len(values) and (int(values[0])<=previous or not np.all(values[1:]>values[:-1])):
            raise ValueError("PREPARED_OWNER_ORDINALS_NOT_STRICTLY_SORTED")
        if len(values):previous=int(values[-1])
        h.update(np.asarray(values,dtype="<u8").tobytes());n+=len(values)
    return n,h.hexdigest()


def rho_external(db,files,fid):
    checkpoint()
    import numpy as np
    view="SELECT value,heavy_atoms,sum(n)::UBIGINT AS n FROM read_parquet("+path_list(files)+") WHERE field_id="+str(fid)+" GROUP BY value,heavy_atoms"
    db.execute("CREATE OR REPLACE TEMP VIEW joint AS "+view)
    checkpoint()
    n,ny,nx=db.execute("SELECT coalesce(sum(n),0),count(DISTINCT value),count(DISTINCT heavy_atoms) FROM joint").fetchone()
    n=int(n)
    if n<2 or ny<2 or nx<2:return {"pair_n":n,"rho":None,"status":"UNDEFINED_CONSTANT_OR_TOO_FEW"}
    query="""WITH yc AS (SELECT value,sum(n) AS n FROM joint GROUP BY value),
      xc AS (SELECT heavy_atoms,sum(n) AS n FROM joint GROUP BY heavy_atoms),
      yr AS (SELECT value,sum(n) OVER(ORDER BY value ROWS UNBOUNDED PRECEDING)-(n-1)/2.0 AS rank FROM yc),
      xr AS (SELECT heavy_atoms,sum(n) OVER(ORDER BY heavy_atoms ROWS UNBOUNDED PRECEDING)-(n-1)/2.0 AS rank FROM xc)
      SELECT j.n,xr.rank AS rx,yr.rank AS ry FROM joint j JOIN yr USING(value) JOIN xr USING(heavy_atoms)"""
    center=np.longdouble(n+1)/2;xx=yy=xy=np.longdouble(0)
    checkpoint()
    for batch in checkpoint_iter(db.execute(query).fetch_record_batch(65536)):
        weight=np.asarray(batch.column(0),dtype=np.longdouble)
        x=np.asarray(batch.column(1),dtype=np.longdouble)-center
        y=np.asarray(batch.column(2),dtype=np.longdouble)-center
        xx+=np.sum(weight*x*x,dtype=np.longdouble);yy+=np.sum(weight*y*y,dtype=np.longdouble)
        xy+=np.sum(weight*x*y,dtype=np.longdouble)
    rho=float(xy/np.sqrt(xx*yy))
    if not math.isfinite(rho) or abs(rho)>1+1e-12:raise ValueError("WEIGHTED_SPEARMAN_NUMERICAL_FAILURE")
    return {"pair_n":n,"rho":max(-1.0,min(1.0,rho)),"status":"DEFINED",
        "method":"TRAIN exact value/heavy-count weighted average ranks; longdouble centered covariance",
        "rounding_clip_tolerance":1e-12}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-manifest",required=True);p.add_argument("--root-preflight",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();scan=load(a.scan_manifest);plan=load(require(scan["plan"]));cfg=load(require(plan["config"]))
    root_guard(a.root_preflight,a.scan_manifest,cfg["reduce_output_cap_bytes"])
    checkpoint()
    out=new_root(a.output,cfg["external_output_root"]);cap=cfg["reduce_output_cap_bytes"];started=time.monotonic()
    fields=load(require(plan["field_map"]));by_id={str(f["field_id"]):f for f in fields}
    if scan["coverage_fingerprint"]!=plan["coverage_fingerprint"]:raise ValueError("SCAN_SOURCE_SCOPE_DIFFERS")
    expected={g["group_index"]:g for g in plan["groups"]};seen=set();stats={fid:collections.Counter() for fid in by_id}
    histograms=[];joints=[];qrs=collections.defaultdict(list);receipts=[];actual_pids=set();hof_pending=collections.Counter();worst=collections.defaultdict(list);jump_n=0
    try:
        for pin in checkpoint_iter(scan["group_receipts"]):
            r=load(require(pin));i=r["group_index"]
            if i not in expected or i in seen:raise ValueError("DUPLICATE_OR_UNPLANNED_SOURCE_GROUP_RECEIPT")
            seen.add(i);g=expected[i];n,h=ordinal_digest(g["owner_index"])
            if r["status"]!="SOURCE_GROUP_SCANNED" or r["owner_index"]!=g["owner_index"] or r["records"]!=n or n!=g["expected_records"]:
                raise ValueError("GROUP_OWNER_COVERAGE_DIFFERS")
            if set(r["task_coverage"])!=set(plan["task_codes"]):raise ValueError("CANONICAL_TASK_SET_DIFFERS")
            for task,c in r["task_coverage"].items():
                if c!={"records":n,"ordinal_sha256":h}:raise ValueError("CANONICAL_RECORD_TASK_SLOT_NOT_CONSERVED:"+task)
            if set(r["field_counts"])!=set(by_id):raise ValueError("GROUP_FIELD_SET_DIFFERS")
            for fid,c in r["field_counts"].items():
                if c["records"]!=n:raise ValueError("GROUP_ENABLED_FIELD_DENOMINATOR_DIFFERS")
                stats[fid].update(c)
            for output in checkpoint_iter(r["outputs"]):
                require(output)
                if Path(output["path"]).name=="TEMP_TRAIN_scalar_heavy_hist.parquet":joints.append(output["path"])
                if Path(output["path"]).name=="audit_and_anomalies.json":
                    detail=load(output["path"]);jump_n+=len(detail["within_molecule_jump_reviews"])
                    for key,examples in detail["top20_by_field_reason"].items():
                        for item in examples:
                            score=float(item["score"]);entry=(score,int(item["record_ordinal"]),item);heap=worst[key]
                            if len(heap)<20:heapq.heappush(heap,entry)
                            elif entry[:2]>heap[0][:2]:heapq.heapreplace(heap,entry)
            histograms.append(r["radix_histogram"]["path"]);actual_pids.add(r["pid"])
            for fid,state in r["energy_TSQR"].items():qrs[fid].append((i,state))
            hof_pending.update(r["HOF_size_reference_pending_counts"]);receipts.append(pin)
        if seen!=set(expected) or len(actual_pids)!=16:raise ValueError("MISSING_SOURCE_GROUPS_OR_16_ACTUAL_WORKERS")
        if any(c["records"]!=plan["records"] for c in stats.values()):raise ValueError("GLOBAL_RECORD_FIELD_COVERAGE_NOT_CONSERVED")
        stop=[fid for fid,c in stats.items() if c["newly_masked_records"]/c["records"]>.01]
        worst_ref=save(out/"worst20_by_field_reason.json",{key:[entry[2] for entry in sorted(heap,reverse=True)] for key,heap in worst.items()},out,cap)
        if stop:
            save(out/"reduction.json",{"status":"STOP_NEW_MASK_ABOVE_ONE_PERCENT","mode":plan["mode"],"records":plan["records"],
                "groups_verified":len(seen),"stop_fields":stop,"field_counts":{fid:dict(c) for fid,c in stats.items()},
                "worst20_by_field_reason":worst_ref,"further_calibration_performed":False,"normalization_completed":False},out,cap)
            print("STOP_NEW_MASK_ABOVE_ONE_PERCENT",stop)
            return 2
        import duckdb
        db=duckdb.connect();db.execute("SET threads=16");db.execute("SET memory_limit='12GB'")
        spill=out/"spill";spill.mkdir();db.execute("SET temp_directory="+sqlstr(spill));db.execute("SET max_temp_directory_size='4GiB'")
        try:
            checkpoint()
            hist_rows=db.execute("SELECT field_id,node_id,prefix_bits,prefix,sum(n)::UBIGINT AS n FROM read_parquet("+
                path_list(histograms)+") GROUP BY field_id,node_id,prefix_bits,prefix ORDER BY field_id,node_id,prefix").fetch_arrow_table().to_pylist()
            request=load(require(scan["queries"]));next_request,finished=advance(request,hist_rows)
            next_request["finished"]=request.get("finished",[])+finished
            next_request["coverage_fingerprint"]=plan["coverage_fingerprint"];next_request["mode"]=plan["mode"]
            next_ref=save(out/"radix_next_queries.json",next_request,out,cap)
            checkpoint()
            models={fid:merge_qr([state for _,state in sorted(states)]) for fid,states in qrs.items()}
            valid_models={fid:m for fid,m in models.items() if m["status"]=="TRAIN_ANOMALY_SIZE_REFERENCE_NOT_FINAL_NORMALIZATION"}
            energy_ref=save(out/"energy_reference.json",{"coverage_fingerprint":plan["coverage_fingerprint"],"mode":plan["mode"],
                "fit_role":"TRAIN_ONLY","final_normalization":False,"fields":valid_models,"unavailable_fields":[fid for fid in models if fid not in valid_models]},out,cap)
            if not qrs:energy_ref=scan.get("energy_reference")
            calibration_ref=None;median_ref=None;mad_query_ref=None
            if not next_request["fields"] and request["purpose"]=="median":
                medians={str(r["field_id"]):r for r in next_request["finished"]}
                median_ref=save(out/"exact_TRAIN_medians.json",{"coverage_fingerprint":plan["coverage_fingerprint"],"mode":plan["mode"],"fields":medians,"fit_role":"TRAIN_ONLY"},out,cap)
                centers={int(fid):r["value"] for fid,r in medians.items() if r["status"]=="EXACT"}
                mad=initial_queries(fields,"MAD",centers);mad.update(coverage_fingerprint=plan["coverage_fingerprint"],mode=plan["mode"],median_result=median_ref)
                mad_query_ref=save(out/"MAD_queries_round0.json",mad,out,cap)
            if not next_request["fields"] and request["purpose"]=="MAD":
                checkpoint()
                medians=load(require(request["median_result"]))["fields"]
                mads={str(r["field_id"]):r for r in next_request["finished"]}
                calibration={fid:{"median":medians[fid]["value"],"MAD":mads.get(fid,{}).get("value"),
                    "TRAIN_n":medians[fid]["n"],"MAD_n":mads.get(fid,{}).get("n"),
                    "status":"EXACT" if medians[fid]["status"]=="EXACT" and mads.get(fid,{}).get("status")=="EXACT" else "UNDEFINED_SCALE"} for fid in by_id}
                if any(row["MAD_n"] is not None and row["MAD_n"]!=row["TRAIN_n"] for row in calibration.values()):
                    raise ValueError("MEDIAN_AND_MAD_TRAIN_MASS_DIFFERS")
                calibration_ref=save(out/"TRAIN_median_MAD_reference.json",{"coverage_fingerprint":plan["coverage_fingerprint"],"mode":plan["mode"],
                    "fields":calibration,"fit_role":"TRAIN_ONLY","status":"EXACT_ANOMALY_REFERENCE_NOT_FINAL_NORMALIZATION"},out,cap)
            rhos={}
            if scan["phase"] in ("profile","mask"):
                for fid,field in checkpoint_iter(by_id.items()):
                    if field["level"]!="molecule":
                        rhos[fid]={"rho":None,"pair_n":None,"status":"PENDING_ROTATION_INVARIANT_LOCAL_OR_VECTOR_AGGREGATION_DEFINITION"}
                    elif hof_pending[fid]:
                        rhos[fid]={"rho":None,"pair_n":None,"status":"PENDING_TRAIN_ELEMENT_REFERENCE_RESIDUAL_PASS"}
                    else:rhos[fid]=rho_external(db,joints,int(fid))
            rho_ref=save(out/"TRAIN_size_spearman.json",{"coverage_fingerprint":plan["coverage_fingerprint"],"mode":plan["mode"],"fields":rhos,
                "threshold_abs_rho":.95,"HOF_requires_element_reference_residual":True,"final_registry_family_freeze":False},out,cap)
        finally:db.close()
        result={"schema":"CANONICAL_STREAM_REDUCTION_V1","status":"STOP_NEW_MASK_ABOVE_ONE_PERCENT" if stop else "SOURCE_COVERAGE_CONSERVED_MORE_SCIENTIFIC_GATES_PENDING",
            "scan_manifest":ref(a.scan_manifest),"plan":scan["plan"],"coverage_fingerprint":plan["coverage_fingerprint"],"mode":plan["mode"],"phase":scan["phase"],
            "groups_verified":len(seen),"actual_workers":len(actual_pids),"records":plan["records"],"molecules":plan["molecules"],"roles":plan["roles"],
            "quantum_record_task_slots":plan["records"]*12,"all_record_task_slots_including_D20_D3":plan["records"]*14,
            "field_counts":{fid:dict(c,new_mask_fraction=c["newly_masked_records"]/c["records"]) for fid,c in stats.items()},"stop_fields":stop,
            "radix_refinement_required":bool(next_request["fields"]),"radix_next_queries":next_ref,"exact_medians":median_ref,"MAD_queries":mad_query_ref,
            "exact_TRAIN_median_MAD":calibration_ref,"energy_reference":energy_ref,"TRAIN_size_rho":rho_ref,
            "worst20_by_field_reason":worst_ref,"within_molecule_jump_review_groups":jump_n,
            "all_original_population_source_coverage":plan["mode"]=="full","normalization_completed":False,
            "full_population_scientific_acceptance":False,"negative_and_remaining":[
                "Exact radix calibration may require several full source passes; costs are not hidden or replaced by approximate quantiles.",
                "The earlier 40-record copied-label pilot is not a storage estimate for this compact representation.",
                "Non-scalar size-rho aggregation and output-vector reference-frame proof remain unresolved.",
                "Independent dipole norm is not registered; deriving a norm from the same vector is not an independent check.",
                "Final normalization still requires frozen common population and diagnostic geometry exclusions.",
                "TEMP TRAIN joint histograms are bounded calibration scratch; no original record-value export is retained."],
            "elapsed_seconds":time.monotonic()-started,"root_preflight":ref(a.root_preflight)}
        save(out/"reduction.json",result,out,cap)
        print(json.dumps({"status":result["status"],"records":plan["records"],"groups":len(seen),"needs_radix_pass":result["radix_refinement_required"]}))
        return 2 if stop else 0
    except BaseException as exc:
        save(out/"failure.json",{"status":"REDUCTION_FAILED_PRESERVE_SCRATCH_AND_INPUTS","type":type(exc).__name__,"error":str(exc)})
        raise


if __name__=="__main__":raise SystemExit(main())
