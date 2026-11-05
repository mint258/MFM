"""Sixteen real source-group workers; compact masks and bounded TRAIN summaries."""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import heapq
import json
import math
import multiprocessing
import os
from pathlib import Path
import resource
import struct
import time

from calibration import RadixCounts,TSQR,train_values
from compact import arrow_schema,encode
from support import ParquetSink,budget,identity,legacy,load,new_root,ref,require,root_guard,save,unique_bytes,write_blob

WORK={}


def init_worker(cfg,plan,queries,out,barrier,stop_event,phase,calibration,energy):
    common,masks=legacy(cfg)
    fields=load(require(plan["field_map"]))
    WORK.update(cfg=cfg,plan=plan,queries=queries,out=Path(out),barrier=barrier,stop_event=stop_event,phase=phase,
        common=common,masks=masks,fields=fields,calibration=calibration,energy=energy)


def match_source_rows(pin,owners,columns,batch_records):
    import pyarrow as pa
    import pyarrow.parquet as pq
    path=require(pin,content=False);before=identity(path)
    for batch in pq.ParquetFile(path).iter_batches(batch_size=batch_records,columns=columns,use_threads=False):
        if WORK["stop_event"].is_set():raise RuntimeError("PEER_FAILURE_STOP_BEFORE_NEXT_SOURCE_BATCH")
        # Convert only IDs before filtering; historical/unselected giant CELL
        # arrays are never converted to Python objects merely to skip them.
        selected=[rid in owners for rid in batch.column(batch.schema.get_field_index("record_id")).to_pylist()]
        if not any(selected):continue
        for row in batch.filter(pa.array(selected)).to_pylist():
            owner=owners[row["record_id"]]
            if any(row[key]!=owner[key] for key in ("record_id","molecule_id","attempt_id","job_id","task_id")):
                continue
            yield row,owner
    if identity(path)!=before:raise ValueError("SOURCE_IDENTITY_CHANGED_DURING_GROUP_SCAN")


def base_numbers(group,owners):
    result={}
    cols=["record_id","molecule_id","attempt_id","job_id","task_id","atomic_numbers",
        "native_atom_order_sha256","source_payload_sha256","geometry_status"]
    for pin in group["base_files"]:
        for row,owner in match_source_rows(pin,owners,cols,32):
            rid=row["record_id"];z=row["atomic_numbers"]
            if rid in result or row["geometry_status"]!="ORIGINAL_PM7_GEOMETRY" or len(z)!=owner["total_atoms"]:
                raise ValueError("BASE_GEOMETRY_DUPLICATE_STATUS_OR_COUNT_DIFFERS")
            if any(type(x) is not int or not 1<=x<=118 for x in z):raise ValueError("INVALID_ATOMIC_NUMBER")
            h=hashlib.sha256(b"".join(struct.pack("<q",x) for x in z)).hexdigest()
            if h!=row["native_atom_order_sha256"] or row["source_payload_sha256"]!=owner["record_payload_sha256"]:
                raise ValueError("BASE_GEOMETRY_ATOM_ORDER_OR_PAYLOAD_SHA_DIFFERS")
            if sum(x>1 for x in z)!=owner["heavy_atoms"]:raise ValueError("HEAVY_ATOM_IDENTITY_DIFFERS")
            result[rid]=z
    if len(result)!=len(owners):raise ValueError("CANONICAL_BASE_GEOMETRY_COVERAGE_INCOMPLETE")
    return result


def source_columns(family):
    common=["record_id","molecule_id","attempt_id","job_id","task_id","status"]
    if family=="D20":return common+["values_float64","valid_mask","descriptor_names"]
    if family=="D3":return common+["PMI1","PMI2","PMI3","PBF_A","volume_A3","SASA_total_A2","SASA_atom_A2","issues"]
    return common+["calc_type","lane","total_atoms","values","numeric_issues","converged","scf_iterations","precision_by_field_json","source_status","failure_code"]


def add_reference_reviews(item,calibration):
    entry=calibration.get(str(item["field_id"]))
    if entry is None:return None
    center,mad=entry["median"],entry["MAD"]
    if center is None or mad is None or not math.isfinite(center) or not math.isfinite(mad):
        item["review_reasons"].append("TRAIN_SCALE_UNDEFINED_REVIEW_ONLY")
        return None
    eligible=[abs(v-center) for v,keep in zip(item["values_float64"],item["value_mask"]) if keep]
    if not eligible:return None
    if mad==0:
        if max(eligible)>0:item["review_reasons"].append("ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY")
        return max(eligible) if max(eligible)>0 else 0.0
    score=.6744897501960817*max(eligible)/mad
    if score>20:item["review_reasons"].append("ROBUST_Z_GT20_REVIEW_ONLY")
    return score


def preview(item,owner,score=None):
    limit=WORK["cfg"]["audit_preview_leaf_limit"]
    values=item["values_float64"]
    safe=[v if v is None or math.isfinite(v) else str(v) for v in values[:limit]]
    return {"record_ordinal":owner["record_ordinal"],"field_id":item["field_id"],"molecule_id":owner["molecule_id"],
        "source_record_id":owner["record_id"],"role":owner["new_role"],"leaf_count":len(values),
        "raw_value_preview":safe,"preview_truncated":len(values)>limit,
        "score":score if score is None or math.isfinite(score) else str(score),
        "source_reasons":item["source_reasons"],"new_reasons":item["new_reasons"],"review_reasons":item["review_reasons"]}


def _run_group(group):
    if WORK["stop_event"].is_set():raise RuntimeError("PEER_FAILURE_NO_NEW_SOURCE_GROUP")
    if group["group_index"]<16:WORK["barrier"].wait(timeout=300)
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    cfg,plan=WORK["cfg"],WORK["plan"];root=WORK["out"];out=root/("group_"+str(group["group_index"]).zfill(4))
    out.mkdir(mode=0o700);started=time.monotonic();cap=cfg["scan_output_cap_bytes"]
    rows=pq.read_table(require(group["owner_index"])).to_pylist()
    owners={row["record_id"]:row for row in rows}
    ordinals=[row["record_ordinal"] for row in rows]
    if len(owners)!=len(rows) or len(set(ordinals))!=len(rows) or len(rows)!=group["expected_records"]:
        raise ValueError("OWNER_INDEX_NOT_EXACT_UNIQUE_PREPARED_COVERAGE")
    positions={rid:i for i,rid in enumerate(owners)}
    numbers=base_numbers(group,owners)
    fields=WORK["fields"];by_task=collections.defaultdict(list)
    for f in fields:by_task[f["task"]].append(f)
    seen={task:np.zeros(len(rows),dtype=np.bool_) for task in plan["task_codes"]}
    stats={str(f["field_id"]):collections.Counter() for f in fields}
    hist=RadixCounts(WORK["queries"])
    qr={str(f["field_id"]):TSQR(plan["element_basis"]) for f in fields if f["element_reference_eligible"]} if WORK["phase"]=="profile" else {}
    joint_schema=pa.schema([("field_id",pa.uint16()),("value",pa.float64()),("heavy_atoms",pa.uint16()),("n",pa.uint64())])
    joint=ParquetSink(joint_schema,cfg["worker_serialized_buffer_cap_bytes"]) if WORK["phase"]!="refine" else None
    buffers=collections.defaultdict(list);jumps={};audit=[];worst=collections.defaultdict(list);outputs=[]
    rss_peak=0;hof_pending=collections.Counter();audit_skipped=0
    def flush_joint(fid):
        values=buffers[fid]
        if not values:return
        a=np.asarray(values,dtype=[("value","<f8"),("heavy","<u2")])
        unique,count=np.unique(a,return_counts=True)
        joint.add([{"field_id":fid,"value":float(v["value"]),"heavy_atoms":int(v["heavy"]),"n":int(n)} for v,n in zip(unique,count)])
        values.clear()
    try:
        for file_index,source in enumerate(group["label_files"]):
            family=source["family"];sink=ParquetSink(arrow_schema(),cfg["worker_serialized_buffer_cap_bytes"]) if WORK["phase"]!="refine" else None;pending=[]
            for row,owner in match_source_rows(source,owners,source_columns(family),cfg["source_read_batch_records"]):
                task=row.get("calc_type",family);row["calc_type"]=task
                if task not in seen:raise ValueError("UNEXPECTED_TASK_IN_CANONICAL_FAMILY")
                index=positions[row["record_id"]]
                if seen[task][index]:raise ValueError("DUPLICATE_CANONICAL_RECORD_TASK")
                seen[task][index]=True
                if family not in ("D20","D3") and (row["lane"]!=owner["lane"] or row["total_atoms"]!=owner["total_atoms"]):
                    raise ValueError("CANONICAL_LANE_OR_ATOM_COUNT_DIFFERS")
                row["total_atoms"]=owner["total_atoms"]
                items=[]
                for field,values,atom_indices,reason in WORK["common"].task_components(row,family,by_task[task]):
                    source_valid,source_masks,masks,source_reasons,new_reasons,review=WORK["masks"].source_value_mask(field,row,values,reason)
                    items.append({"field_id":field["field_id"],"field_key":field["field_key"],"source_path":field["source_path"],
                        "values_float64":[float(v) if type(v) in (int,float) else None for v in values],
                        "source_value_mask":source_masks,"value_mask":masks,"source_reasons":source_reasons,
                        "new_reasons":new_reasons,"review_reasons":review})
                WORK["masks"].add_cross_field_checks(items,row)
                audit_record=int.from_bytes(hashlib.sha256((str(cfg["audit_seed"])+"|"+owner["record_id"]).encode()).digest()[:8],"little")%10000<cfg["audit_basis_points"]
                for field,item in zip(by_task[task],items):
                    fid=field["field_id"];c=stats[str(fid)];c["records"]+=1
                    c["source_valid_records"]+=int(any(item["source_value_mask"]))
                    c["final_valid_records"]+=int(any(item["value_mask"]))
                    c["source_numeric_leaf_slots"]+=len(item["values_float64"])
                    c["source_eligible_leaves"]+=sum(item["source_value_mask"])
                    c["final_eligible_leaves"]+=sum(item["value_mask"])
                    newly=any(a and not b for a,b in zip(item["source_value_mask"],item["value_mask"]))
                    c["newly_masked_records"]+=int(newly)
                    c["newly_masked_leaves"]+=sum(a and not b for a,b in zip(item["source_value_mask"],item["value_mask"]))
                    score=add_reference_reviews(item,WORK["calibration"])
                    for reason in set(item["source_reasons"]):c["source_reason:"+reason]+=1
                    for reason in set(item["new_reasons"]):c["new_reason:"+reason]+=1
                    for reason in set(item["review_reasons"]):c["review_reason:"+reason]+=1
                    valid=[v for v,keep in zip(item["values_float64"],item["value_mask"]) if keep]
                    if owner["new_role"]=="TRAIN":
                        valid=train_values(owner["new_role"],item["values_float64"],item["value_mask"])
                        c["TRAIN_valid_leaves"]+=len(valid);hist.add(fid,valid)
                        if field["element_reference_eligible"] and valid and WORK["phase"]=="profile":
                            if len(valid)!=1:raise ValueError("MOLECULE_ENERGY_NOT_ONE_VALID_SCALAR")
                            qr[str(fid)].add(numbers[owner["record_id"]],valid[0])
                        if field["level"]=="molecule" and len(valid)==1 and WORK["phase"] in ("profile","mask"):
                            value=valid[0]
                            if "heat_of_formation" in field["source_path"]:
                                model=WORK["energy"].get(str(fid))
                                if model is None:hof_pending[str(fid)]+=1;value=None
                                else:
                                    counts=collections.Counter(numbers[owner["record_id"]])
                                    value-=model["intercept"]+math.fsum(counts[z]*b for z,b in zip(model["basis"],model["coefficients"]))
                            if value is not None:
                                buffers[fid].append((value,owner["heavy_atoms"]))
                                if len(buffers[fid])>=cfg["joint_buffer_values"]:flush_joint(fid)
                    if WORK["phase"]!="refine" and field["level"]=="molecule" and len(valid)==1 and valid[0]!=0:
                        key=(fid,owner["molecule_id"]);value=valid[0];old=jumps.get(key)
                        sign=1 if value>0 else 2;value=abs(value)
                        if old is None:jumps[key]=[value,value,owner["record_ordinal"],owner["record_ordinal"],sign,1]
                        else:
                            if value<old[0]:old[0],old[2]=value,owner["record_ordinal"]
                            if value>old[1]:old[1],old[3]=value,owner["record_ordinal"]
                            old[4]|=sign;old[5]+=1
                    if audit_record and WORK["phase"]!="refine":
                        if len(audit)<cfg["audit_total_preview_rows_per_group"]:audit.append(preview(item,owner,score))
                        else:audit_skipped+=1
                    for reason in (set(item["source_reasons"]+item["new_reasons"]+item["review_reasons"]) if WORK["phase"]!="refine" else []):
                        severity=score if score is not None and reason in {"ROBUST_Z_GT20_REVIEW_ONLY","ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY"} else 1.0
                        basis="robust_z_or_zero_MAD_absolute_deviation" if severity==score and score is not None else "binary_evidence_issue_equal_severity_then_ordinal"
                        if reason=="PHYSICAL_DEFINITION_RANGE":
                            bounds=field["physical_range"];distance=[]
                            for value in item["values_float64"]:
                                if value is None or not math.isfinite(value):continue
                                if bounds["lower"] is not None and value<bounds["lower"]:distance.append(bounds["lower"]-value)
                                if bounds["upper"] is not None and value>bounds["upper"]:distance.append(value-bounds["upper"])
                            severity=max(distance,default=0.0);basis="distance_outside_definition_bound_in_field_units"
                        if reason=="NEUTRAL_ATOMIC_CHARGE_SUM_OUTSIDE_SOURCE_ROUNDING_TOLERANCE":
                            severity=abs(math.fsum(v for v in item["values_float64"] if v is not None and math.isfinite(v)));basis="absolute_neutral_charge_sum_e"
                        record=preview(item,owner,severity);record.update(score_reason=reason,score_basis=basis)
                        entry=(severity,int(owner["record_ordinal"]),record);heap=worst[(fid,reason)]
                        if len(heap)<20:heapq.heappush(heap,entry)
                        elif entry[:2]>heap[0][:2]:heapq.heapreplace(heap,entry)
                if sink is not None:pending.append(encode(owner["record_ordinal"],plan["task_codes"][task],items))
                if sink is not None and len(pending)>=cfg["compact_row_group_records"]:
                    sink.add(pending);pending.clear()
                rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;rss_peak=max(rss_peak,rss)
                if rss>cfg["worker_rss_stop_bytes"]:raise RuntimeError("WORKER_RSS_BOUND_EXCEEDED")
            if sink is not None:
                sink.add(pending)
                outputs.append(sink.close(out/(family+"_"+str(file_index).zfill(3)+".mask.parquet"),root,cap))
        expected=len(rows)
        coverage={}
        for task,flags in seen.items():
            if int(flags.sum())!=expected:raise ValueError("INCOMPLETE_CANONICAL_TASK_COVERAGE:"+task)
            coverage[task]={"records":expected,"ordinal_sha256":hashlib.sha256(np.asarray(sorted(ordinals),dtype="<u8").tobytes()).hexdigest()}
        if any(c["records"]!=expected for c in stats.values()):raise ValueError("ENABLED_FIELD_RECORD_COVERAGE_NOT_CONSERVED")
        for fid in buffers:flush_joint(fid)
        if joint is not None:outputs.append(joint.close(out/"TEMP_TRAIN_scalar_heavy_hist.parquet",root,cap))
        hist_rows=hist.rows()
        hist_schema=pa.schema([("field_id",pa.uint16()),("node_id",pa.string()),("prefix_bits",pa.uint8()),("prefix",pa.uint64()),("n",pa.uint64())])
        hist_sink=ParquetSink(hist_schema,cfg["worker_serialized_buffer_cap_bytes"]);hist_sink.add(hist_rows)
        histogram_ref=hist_sink.close(out/"TRAIN_radix_counts.parquet",root,cap);outputs.append(histogram_ref)
        jump_rows=[{"field_id":fid,"molecule_id":mid,"min_abs":v[0],"max_abs":v[1],"min_record_ordinal":v[2],
            "max_record_ordinal":v[3],"factor":v[1]/v[0],"reason":"WITHIN_MOLECULE_JUMP_REVIEW_ONLY"}
            for (fid,mid),v in jumps.items() if v[5]>=2 and v[4] in (1,2) and v[1]/v[0]>1000]
        # Audit previews and worst cases are deliberately bounded; normal raw
        # values are not saved. All originals remain addressable by ordinal.
        preview_cap=cfg["audit_total_preview_rows_per_group"]
        detail={"audit_previews":audit[:preview_cap],"audit_previews_truncated":audit_skipped>0,"audit_previews_not_copied_due_to_cap":audit_skipped,
            "top20_by_field_reason":{str(fid)+"|"+reason:[x[2] for x in sorted(heap,reverse=True)] for (fid,reason),heap in worst.items()},
            "within_molecule_jump_reviews":jump_rows}
        if WORK["phase"]!="refine":outputs.append(write_blob(out/"audit_and_anomalies.json",(json.dumps(detail,allow_nan=False,separators=(",",":"))+"\n").encode(),root,cap))
        report={"status":"SOURCE_GROUP_SCANNED","group_index":group["group_index"],"source_job_id":group["source_job_id"],
            "pid":os.getpid(),"owner_index":group["owner_index"],"records":expected,"molecules":group["expected_molecules"],
            "task_coverage":coverage,"field_counts":{k:dict(v) for k,v in stats.items()},"radix_histogram":histogram_ref,
            "energy_TSQR":{fid:q.state() for fid,q in qr.items()},"HOF_size_reference_pending_counts":dict(hof_pending),
            "outputs":outputs,"elapsed_seconds":time.monotonic()-started,"maxrss_bytes":rss_peak,
            "normal_raw_values_copied":False,"TEMP_joint_histogram_is_statistics_scratch_not_record_label_copy":True}
        return write_blob(out/"group_receipt.json",(json.dumps(report,allow_nan=False,sort_keys=True,indent=2)+"\n").encode(),root,cap)
    except BaseException as exc:
        WORK["stop_event"].set()
        failure={"status":"SOURCE_GROUP_FAILED_NO_AUTORETRY","type":type(exc).__name__,"error":str(exc),"pid":os.getpid()}
        try:write_blob(out/"failure.json",(json.dumps(failure)+"\n").encode(),root,cap,reserve=0)
        except Exception as evidence_error:print("FAILURE_EVIDENCE_WRITE_ERROR",repr(evidence_error),"ORIGINAL",repr(exc),flush=True)
        raise


def run_group(group):
    try:
        return _run_group(group)
    except BaseException:
        WORK["stop_event"].set()
        try:WORK["barrier"].abort()
        except Exception:pass
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",required=True);p.add_argument("--root-preflight",required=True);p.add_argument("--output",required=True)
    p.add_argument("--queries");p.add_argument("--calibration");p.add_argument("--energy-reference")
    p.add_argument("--phase",choices=("profile","refine","mask"),default="profile")
    a=p.parse_args();plan=load(a.plan);cfg=load(require(plan["config"]))
    proof=root_guard(a.root_preflight,a.plan,cfg["scan_output_cap_bytes"],cfg["scan_wall_seconds"])
    for path in (a.queries,a.calibration,a.energy_reference):
        if path and ref(path) not in proof["request"]["source_references"]:
            raise ValueError("OPTIONAL_TRAIN_REFERENCE_NOT_PINNED_IN_ROOT_REVIEW")
    if plan["mode"]=="full" and (proof["request"]["pilot"] is not False or not proof["request"]["root_review"].get("accepted_pilot_reference")):
        raise ValueError("FULL_SCAN_REQUIRES_ROOT_REVIEWED_NONPILOT_REQUEST_AND_MEASURED_PILOT")
    queries=load(a.queries or require(plan["initial_median_queries"]))
    if a.queries and (queries["coverage_fingerprint"]!=plan["coverage_fingerprint"] or queries["mode"]!=plan["mode"]):
        raise ValueError("RADIX_QUERY_REFERENCE_SCOPE_DIFFERS_FROM_PREPARED_PLAN")
    calibration={};energy={}
    for path,kind in ((a.calibration,"calibration"),(a.energy_reference,"energy")):
        if path:
            obj=load(path)
            if obj["coverage_fingerprint"]!=plan["coverage_fingerprint"] or obj["mode"]!=plan["mode"]:
                raise ValueError("TRAIN_REFERENCE_SCOPE_DIFFERS_FROM_SOURCE_PLAN")
            if obj.get("fit_role")!="TRAIN_ONLY":raise ValueError("NON_TRAIN_REFERENCE_REJECTED")
            if kind=="calibration":
                calibration=obj["fields"]
                expected_ids={str(f["field_id"]) for f in load(require(plan["field_map"]))}
                if set(calibration)!=expected_ids:raise ValueError("CALIBRATION_FIELD_IDS_DIFFER")
                for row in calibration.values():
                    if row["MAD"] is not None and (not math.isfinite(row["MAD"]) or row["MAD"]<0):
                        raise ValueError("INVALID_MAD_REFERENCE")
            else:energy=obj["fields"]
    if a.phase=="mask" and len(calibration)!=146:
        raise ValueError("FINAL_ANOMALY_MASK_PASS_REQUIRES_COMPLETE_EXACT_TRAIN_MEDIAN_MAD_REFERENCE")
    groups=plan["groups"]
    if len(groups)<16:raise ValueError("SIXTEEN_REAL_SOURCE_GROUPS_REQUIRED")
    out=new_root(a.output,cfg["external_output_root"]);started=time.monotonic();receipts=[]
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(16);stop_event=context.Event()
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=init_worker,
                initargs=(cfg,plan,queries,str(out),barrier,stop_event,a.phase,calibration,energy)) as pool:
            for item in pool.map(run_group,groups,chunksize=1):
                receipts.append(item);budget(out,cfg["scan_output_cap_bytes"])
        actual={load(r["path"])["pid"] for r in receipts}
        if len(actual)!=16:raise ValueError("DID_NOT_OBSERVE_16_REAL_GROUP_WORKERS")
        result={"schema":"CANONICAL_STREAM_SCAN_MANIFEST_V1","status":"GROUP_SCANS_COMPLETE_REDUCTION_REQUIRED",
            "mode":plan["mode"],"phase":a.phase,"plan":ref(a.plan),"coverage_fingerprint":plan["coverage_fingerprint"],
            "queries":ref(a.queries or plan["initial_median_queries"]["path"]),"group_receipts":receipts,
            "actual_worker_pids":sorted(actual),"job_id":os.environ["SLURM_JOB_ID"],"root_preflight":ref(a.root_preflight),
            "calibration":ref(a.calibration) if a.calibration else None,"energy_reference":ref(a.energy_reference) if a.energy_reference else None,
            "elapsed_seconds":time.monotonic()-started,"unique_inode_output_bytes":unique_bytes(out),
            "full_population_acceptance":False,"normalization_completed":False}
        save(out/"scan_manifest.json",result,out,cfg["scan_output_cap_bytes"])
        print(json.dumps({"status":result["status"],"groups":len(receipts),"workers":len(actual),"bytes":result["unique_inode_output_bytes"]}))
    except BaseException as exc:
        save(out/"failure.json",{"status":"STREAM_SCAN_FAILED_PRESERVE_ALL_PARTIALS","type":type(exc).__name__,"error":str(exc),"closed_group_receipts":receipts})
        raise


if __name__=="__main__":main()
