"""Sixteen bounded canonical-source workers, shared by final fit and replay."""
from __future__ import annotations

import collections
import hashlib
import math
import os
from pathlib import Path
import resource
import struct
import time

from runtime import (RadixCounts, TSQR, WinsorMoments, canonical_bytes, load,
                     require, semantic_sha, write_blob)
from moments import JointMoments, state
from reader import observations
from series import views

WORK = {}


def initialize(cfg, source_cfg, barrier, stop_event, phase, payload, output):
    import pyarrow as pa
    pa.set_cpu_count(1); pa.set_io_thread_count(1)
    WORK.update(cfg=cfg, source_cfg=source_cfg, barrier=barrier, stop=stop_event,
                phase=phase, payload=payload, output=Path(output))


def run(job):
    try:
        return _run(job)
    except BaseException:
        WORK["stop"].set()
        try:
            WORK["barrier"].abort()
        except Exception:
            pass
        raise


def _run(job):
    if WORK["stop"].is_set():
        raise RuntimeError("FINAL_FIT_PEER_FAILED_NO_NEW_GROUP")
    if job["work_index"] < 16:
        WORK["barrier"].wait(timeout=300)
    cfg, phase, payload = WORK["cfg"], WORK["phase"], WORK["payload"]
    item, group, side = job["item"], job["group"], job["side"]
    dsid = item["dataset"]["dataset_id"]; entries_catalog = payload["catalogs"][dsid]
    by_key = {r["key"]: r["field_id"] for r in entries_catalog}
    physical = payload["physical"][dsid]; started = time.monotonic()
    models = payload.get("models", {}).get(dsid, {})
    hist = {q: RadixCounts(request) for q, request in payload.get("queries", {}).get(dsid, {}).items()}
    qr = {str(f["field_id"]): TSQR(item["plan"]["element_basis"]) for f in item["fields"]
          if f["element_reference_eligible"]} if phase == "energy" else {}
    moments = {}; joint = {}; series_mass = collections.Counter(); fields_mass = collections.Counter()
    qvalues = payload.get("quantiles", {}).get(dsid, {})
    if phase == "moments":
        for row in entries_catalog:
            q = qvalues[str(row["field_id"])]
            if q["n"]:
                moments[row["key"]] = WinsorMoments(q["lower"], q["upper"])
    mass_hash = hashlib.sha256(); fit_task_rows = 0
    for owner, numbers, entries in observations(item, group, side, WORK["source_cfg"], hash_sources=(phase == "energy")):
        if WORK["stop"].is_set():
            raise RuntimeError("FINAL_FIT_PEER_FAILED_BEFORE_NEXT_RECORD")
        fit_task_rows += 1
        mass_hash.update(canonical_bytes([owner["record_ordinal"], owner["molecule_id"],
                                         owner["geometry_source"], owner["geometry_id"], owner["effective_role"]]))
        for e in entries:
            fid = e["field_id"]; valid = [v for v, keep in zip(e["values_float64"], e["value_mask"]) if keep]
            fields_mass[str(fid) + "/records"] += 1
            fields_mass[str(fid) + "/valid_leaves"] += len(valid)
            fields_mass[str(fid) + "/valid_records"] += bool(valid)
            fields_mass[str(fid) + "/masked_leaves"] += len(e["value_mask"]) - len(valid)
            for reason in set(e["source_reasons"]):
                fields_mass[str(fid) + "/source_reason:" + reason] += 1
            for reason in set(e["new_reasons"]):
                fields_mass[str(fid) + "/new_reason:" + reason] += 1
            for code in e["persisted_review_codes"]:
                fields_mass[str(fid) + "/persisted_review_code:" + str(code)] += 1
            mass_hash.update(struct.pack("<HI", fid, len(e["value_mask"])))
            mass_hash.update(bytes(e["value_mask"]))
            for v in valid:
                if not math.isfinite(v):
                    raise ValueError("NONFINITE_UNMASKED_VALUE_IN_FINAL_FIT")
                mass_hash.update(struct.pack("<d", v))
            if phase == "energy" and str(fid) in qr and valid:
                if len(valid) != 1:
                    raise ValueError("ENERGY_FIELD_NOT_ONE_MOLECULE_SCALAR")
                qr[str(fid)].add(numbers, valid[0])
        if phase != "energy":
            values, physical_rows = views(entries, numbers, physical, models)
            for key, vals in values.items():
                if key not in by_key:
                    raise ValueError("UNREGISTERED_FINAL_STATISTICAL_SERIES:" + key)
                sid = by_key[key]; series_mass[str(sid)] += len(vals)
                for counter in hist.values():
                    counter.add(sid, vals)
                if phase == "moments" and vals:
                    moments[key].add(vals)
            if phase == "moments":
                for key, rows in physical_rows.items():
                    if rows:
                        joint.setdefault(key, JointMoments(len(rows[0]))).add(rows)
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > cfg["worker_rss_stop_bytes"]:
            raise RuntimeError("FINAL_FIT_WORKER_RSS_BOUND_EXCEEDED")
        if sum(len(c.counts) for c in hist.values()) > cfg["worker_histogram_row_cap"]:
            raise RuntimeError("FINAL_FIT_EXACT_RADIX_HISTOGRAM_CAP_EXCEEDED_NEEDS_REVIEWED_PLAN")
    if fit_task_rows != side["fit_records"] * len(item["plan"]["task_codes"]):
        raise ValueError("FINAL_FIT_RECORD_TASK_COVERAGE_NOT_CONSERVED")
    for f in item["fields"]:
        if fields_mass[str(f["field_id"]) + "/records"] != side["fit_records"]:
            raise ValueError("FINAL_FIT_FIELD_RECORD_DENOMINATOR_NOT_CONSERVED")
    report = {"dataset_id": dsid, "group_index": group["group_index"], "work_index": job["work_index"],
              "pid": os.getpid(), "phase": phase, "fit_task_rows": fit_task_rows,
              "masked_source_fit_mass_sha256": mass_hash.hexdigest(), "fields_mass": dict(fields_mass),
              "series_mass": dict(series_mass), "energy_TSQR": {fid: v.state() for fid, v in qr.items()},
              "moments": {str(by_key[key]): state(m) for key, m in moments.items()},
              "joint": {key: v.state() for key, v in joint.items()},
              "maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              "elapsed_seconds": time.monotonic() - started,
              "source_content_hashes_rechecked": phase == "energy", "normal_labels_copied": False}
    # Histograms are compressed binary statistics, never a normal record/leaf export.
    if hist:
        import pyarrow as pa
        from support import ParquetSink
        schema = pa.schema([("tail", pa.string()), ("field_id", pa.uint32()), ("node_id", pa.string()),
                            ("prefix_bits", pa.uint8()), ("prefix", pa.uint64()), ("n", pa.uint64())])
        sink = ParquetSink(schema, cfg["worker_serialized_buffer_cap_bytes"])
        for q, counter in sorted(hist.items()):
            rows = counter.rows()
            for start in range(0, len(rows), 4096):
                sink.add([dict(r, tail=q) for r in rows[start:start+4096]])
        report["histogram"] = sink.close(WORK["output"] / (str(job["work_index"]).zfill(5) + ".hist.parquet"),
                                         WORK["output"].parent, cfg["output_cap_bytes"])
    raw = canonical_bytes(report)
    if len(raw) > cfg["worker_serialized_buffer_cap_bytes"]:
        raise RuntimeError("FINAL_FIT_GROUP_REPORT_BUFFER_CAP_EXCEEDED")
    return write_blob(WORK["output"] / (str(job["work_index"]).zfill(5) + ".json"), raw,
                      WORK["output"].parent, cfg["output_cap_bytes"])
