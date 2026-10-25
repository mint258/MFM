"""One-vote-per-record and one-vote-per-molecule size histograms, no raw leaves."""
from __future__ import annotations

import collections
import hashlib
import math
import os
from pathlib import Path
import resource
import struct
import time

from size_shared import (ParquetSink,TSQR,adapter_from,canonical_bytes,load,require,write_blob)
from aggregate import aggregate,complete,median
from size_reader import rows_for_group

WORK={}


def initialize(cfg,source_cfg,plan,targets,out,barrier,event,phase,models):
    adapter=adapter_from(cfg["scan_adapter"],source_cfg,plan,out,barrier,event)
    WORK.update(cfg=cfg,source_cfg=source_cfg,plan=plan,targets=targets,out=Path(out),barrier=barrier,event=event,
                phase=phase,models=models,adapter=adapter)


def run(group):
    try:return _run(group)
    except BaseException:
        WORK["event"].set()
        try:WORK["barrier"].abort()
        except Exception:pass
        raise


def _run(job):
    if WORK["event"].is_set():raise RuntimeError("SIZE_PEER_FAILED_NO_NEW_GROUP")
    if job["work_index"]<16:WORK["barrier"].wait(timeout=300)
    cfg,plan,targets=WORK["cfg"],WORK["plan"],WORK["targets"]
    group=job["group"];out=WORK["out"];root=out.parent;started=time.monotonic();phase=WORK["phase"]
    by_task=collections.defaultdict(list)
    for t in targets:by_task[t["task"]].append(t)
    refs={t["target_id"]:TSQR(plan["element_basis"]) for t in targets if t["operation"]=="TRAIN_ELEMENT_RESIDUAL_SCALAR"} if phase=="hof" else {}
    models=WORK["models"];counts=collections.Counter();size_bins=collections.Counter();candidate=collections.defaultdict(list);heavy_by_mol={};hist=collections.Counter()
    value_hash=hashlib.sha256();hof_hash=hashlib.sha256();fit_records=set();outputs=[]
    import pyarrow as pa
    schema=pa.schema([("target_id",pa.string()),("variant",pa.string()),("value",pa.float64()),("heavy_atoms",pa.uint16()),("n",pa.uint64())])
    sink=ParquetSink(schema,cfg["worker_serialized_buffer_cap_bytes"]) if phase=="rho" else None
    def flush():
        if not hist:return
        sink.add([{"target_id":key[0],"variant":key[1],"value":key[2],"heavy_atoms":key[3],"n":n} for key,n in sorted(hist.items())]);hist.clear()
    def add(target,variant,value,heavy):
        value=0.0 if value==0 else float(value)
        hist[(target,variant,value,int(heavy))]+=1
        if len(hist)>=cfg["histogram_flush_entries"]:flush()
    seen_targets=collections.Counter()
    for owner,numbers,task,entries in rows_for_group(WORK["adapter"],WORK["source_cfg"],plan,group,job["mask_receipt"],job.get("fit_side")):
        if WORK["event"].is_set():raise RuntimeError("SIZE_PEER_FAILED_BEFORE_NEXT_RECORD")
        rid=owner["record_id"];mid=owner["molecule_id"];fit_records.add(rid);heavy=owner["heavy_atoms"]
        if mid in heavy_by_mol and heavy_by_mol[mid]!=heavy:raise ValueError("MOLECULE_HEAVY_COUNT_DIFFERS_BETWEEN_CONFORMERS")
        heavy_by_mol[mid]=heavy
        value_hash.update(canonical_bytes([owner["record_ordinal"],task]))
        for fid,e in sorted(entries.items()):
            value_hash.update(struct.pack("<HI",fid,len(e["value_mask"])));value_hash.update(bytes(e["value_mask"]))
            value_hash.update(canonical_bytes([e["atom_indices"],e.get("pair_keys")]))
            for v,keep in zip(e["values_float64"],e["value_mask"]):
                if keep:value_hash.update(struct.pack("<d",v))
        for target in by_task[task]:
            tid=target["target_id"];seen_targets[tid]+=1
            if target["operation"]=="TRAIN_ELEMENT_RESIDUAL_SCALAR":
                entry=entries[target["field_ids"][0]]
                if complete(entry) is None and len(entry["values_float64"])==1:
                    raw=entry["values_float64"][0];counts[tid+"|HOF_reference_valid"]+=1
                    hof_hash.update(canonical_bytes([tid,owner["record_ordinal"]]));hof_hash.update(struct.pack("<d",raw))
                    if phase=="hof":refs[tid].add(numbers,raw)
            if phase=="hof":continue
            value,reason,extras=aggregate(target,entries,numbers,models.get(tid))
            counts[tid+"|eligible" if reason is None else tid+"|rho_missing:"+reason]+=1
            size_bins[tid,heavy,"eligible" if reason is None else reason]+=1
            if reason is not None:continue
            add(tid,"record_primary",value,heavy);candidate[tid,mid].append(value)
            for name,x in extras.items():
                if name not in {"stored_entries","some_sensitivities_overflowed"}:
                    add(tid,"record_sensitivity_"+name,x,heavy)
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>cfg["worker_rss_stop_bytes"]:
            raise RuntimeError("SIZE_WORKER_RSS_LIMIT_EXCEEDED")
    if set(seen_targets)!={t["target_id"] for t in targets} and fit_records:
        raise ValueError("SIZE_PHYSICAL_TARGET_SET_INCOMPLETE")
    if any(n!=len(fit_records) for n in seen_targets.values()):raise ValueError("SIZE_TARGET_RECORD_DENOMINATOR_NOT_CONSERVED")
    if phase=="rho":
        for (tid,mid),values in sorted(candidate.items()):add(tid,"molecule_median_sensitivity",median(values),heavy_by_mol[mid])
        flush();outputs.append(sink.close(out/(str(job["work_index"]).zfill(4)+".joint.parquet"),root,cfg["output_cap_bytes"]))
    conformers=collections.Counter((tid,len(values)) for (tid,mid),values in candidate.items())
    report={"phase":phase,"group_index":group["group_index"],"work_index":job["work_index"],"pid":os.getpid(),
            "owner_index":group["owner_index"],"fit_side":job.get("fit_side"),"fit_records":len(fit_records),"fit_molecules":len(heavy_by_mol),
            "source_fit_value_mask_sha256":value_hash.hexdigest(),"HOF_fit_mass_sha256":hof_hash.hexdigest(),
            "target_record_denominators":dict(seen_targets),"counts":dict(counts),"HOF_TSQR":{key:value.state() for key,value in refs.items()},
            "missingness_by_heavy_count":[{"target_id":tid,"heavy_atoms":heavy,"reason":reason,"records":n} for (tid,heavy,reason),n in sorted(size_bins.items())],
            "valid_conformer_count_per_molecule":[{"target_id":tid,"valid_conformers":k,"molecules":n} for (tid,k),n in sorted(conformers.items())],
            "outputs":outputs,"maxrss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,"elapsed_seconds":time.monotonic()-started,
            "label_masks_or_values_modified":False,"raw_normal_leaves_persisted":False}
    raw=canonical_bytes(report)
    if len(raw)>cfg["worker_serialized_buffer_cap_bytes"]:raise RuntimeError("SIZE_GROUP_REPORT_BUFFER_LIMIT")
    return write_blob(out/(str(job["work_index"]).zfill(4)+".json"),raw,root,cfg["output_cap_bytes"])
