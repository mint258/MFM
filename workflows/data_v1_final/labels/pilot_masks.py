"""CPU-only, 16-worker canonical label validity pilot; never deletes records.

This intentionally bounded tool is not a full-population acceptance claim.
Outputs retain float64 labels and per-leaf masks. >1% newly invalid records for
any enabled field produces a nonzero stop after evidence has been saved.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import math
import multiprocessing
import os
from pathlib import Path
import time

from canonical_reader import iter_canonical_file, load_plan, owner_index, source_jobs
from common import ALLOWED_STATUSES, OWNER_KEYS, numeric, read_json, reference, task_components, verify_reference, write_json_new

WORK = {}


def init_worker(plan, owners, output):
    import pyarrow as pa
    fields = read_json(verify_reference(plan["sources"]["registry"]))["fields"]
    WORK.update(plan=plan, owners=owners, output=Path(output), pa=pa,
        fields=[x for x in fields if x["status"] == "enabled"], rules=read_json(verify_reference(plan["sources"]["mask_rules"])))


def source_value_mask(field, row, values, reason):
    source_reasons = []
    new_reasons = []
    review = []
    if row["status"] not in ALLOWED_STATUSES:
        source_reasons.append("SOURCE_TASK_STATUS_" + str(row["status"]))
    if reason:
        source_reasons.append(reason)
    masks = [numeric(v) for v in values]
    if not all(masks):
        source_reasons.append("SOURCE_NONFINITE_OR_NONNUMERIC")
    source_valid = bool(values) and any(masks) and not any(x != "SOURCE_NONFINITE_OR_NONNUMERIC" for x in source_reasons)
    source_masks = masks[:] if source_valid else [False] * len(values)
    masks = source_masks[:]
    if row.get("converged") is False:
        new_reasons.append("EXPLICIT_ELECTRONIC_NONCONVERGENCE")
        masks = [False] * len(values)
    elif "converged" in row and row["converged"] is None:
        review.append(str(row["status"])+"_WITH_CONVERGENCE_EVIDENCE_UNKNOWN")
    if row.get("source_status") is not None and row["source_status"]!=row["status"]:
        review.append("SOURCE_AND_SCOPE_STATUS_DIFFER")
    bounds = field["physical_range"]
    for i, value in enumerate(values):
        if not masks[i]:
            continue
        low = bounds["lower"]
        high = bounds["upper"]
        if (low is not None and (value <= low if bounds["lower_exclusive"] else value < low)
                or high is not None and value > high):
            masks[i] = False
            new_reasons.append("PHYSICAL_DEFINITION_RANGE")
    return source_valid, source_masks, masks, source_reasons, list(set(new_reasons)), review


def add_cross_field_checks(outputs, row):
    by_path = {x["source_path"]: x for x in outputs}
    # Restrict the sign check to the same PM7 B task. GFN1 IP/EA must not be
    # compared with GFN2 single-point HOMO/LUMO merely because IDs match.
    if row["calc_type"] == "pm7_B":
        paths = ["values.derived_from_same_geometry_charged_states.vertical_IP_eV",
            "values.derived_from_same_geometry_charged_states.vertical_EA_eV", "values.homo_eV", "values.lumo_eV"]
        items = [by_path.get(path) for path in paths]
        if all(item and len(item["values_float64"]) == 1 and all(item["value_mask"]) for item in items):
            ip, ea, homo, lumo = [item["values_float64"][0] for item in items]
            a, b = ip - ea, lumo - homo
            if abs(a) > 1e-8 and abs(b) > 1e-8 and (a > 0) != (b > 0):
                for item in items:
                    item["value_mask"] = [False]
                    item["new_reasons"].append("IP_EA_ORBITAL_GAP_SIGN_INCONSISTENT_SAME_PM7_CONTEXT")
    if row["calc_type"] not in {"pm7_B", "xtb_singlepoint"}:
        return
    precision = json.loads(row.get("precision_by_field_json") or "{}")
    for leaf in ("net_charges_e", "mulliken_charges_e", "charges_e"):
        item = by_path.get("values." + leaf)
        if not item or not item["value_mask"] or not all(item["value_mask"]):
            continue
        digits = precision.get(leaf)
        if type(digits) is not int:
            item["review_reasons"].append("CHARGE_SUM_TOLERANCE_UNRESOLVED_SOURCE_PRECISION_UNKNOWN")
            continue
        tolerance = max(1e-4, len(item["values_float64"]) * 0.5 * 10.0 ** (-digits) + 1e-6)
        if abs(math.fsum(item["values_float64"])) > tolerance:
            item["value_mask"] = [False] * len(item["value_mask"])
            item["new_reasons"].append("NEUTRAL_ATOMIC_CHARGE_SUM_OUTSIDE_SOURCE_ROUNDING_TOLERANCE")


def process_file(item):
    import pyarrow.parquet as pq
    index, ref = item
    started = time.monotonic()
    output = WORK["output"] / ("observations_" + str(index).zfill(5) + ".parquet")
    if output.exists():
        raise FileExistsError(output)
    fields = [f for f in WORK["fields"] if f["family_source"] == ref["family"]]
    rows = []
    identities = []
    leaves_held = 0
    worker_budget = int(WORK["plan"]["max_output_bytes"]) // 16
    for row in iter_canonical_file(ref, WORK["owners"], int(WORK["plan"].get("read_batch_records", 16))):
        task_fields = [f for f in fields if f["task"] == row["calc_type"]]
        identities.append((row["record_id"], row["calc_type"]))
        outputs = []
        for field, values, atom_indices, reason in task_components(row, ref["family"], task_fields):
            source_valid, source_masks, masks, source_reasons, new_reasons, review = source_value_mask(field, row, values, reason)
            numbers = row.get("atomic_numbers")
            z = ([numbers[i] if i is not None else None for i in atom_indices] if numbers is not None else [None] * len(values))
            outputs.append({**{key: row[key] for key in OWNER_KEYS}, "task": row["calc_type"],
                "field_key": field["field_key"], "source_path": field["source_path"],
                "new_role": row["new_role"], "common_population_v1": row["common_population_v1"],
                "geometry_source": WORK["plan"].get("geometry_source", "pm7"),
                "source_task_status": row["status"], "source_status": row.get("source_status"),
                "converged": row.get("converged"), "scf_iterations": row.get("scf_iterations"),
                "source_valid_record": source_valid,
                "values_float64": [float(v) if type(v) in (int, float) else None for v in values],
                "source_value_mask": source_masks, "value_mask": masks,
                "atom_index": atom_indices, "element_z": z,
                "source_reasons": source_reasons, "new_reasons": new_reasons, "review_reasons": review})
        add_cross_field_checks(outputs, row)
        leaves_held += sum(len(item["values_float64"]) for item in outputs)
        # Conservative Python/Arrow coexistence bound, checked before appending
        # another record; compressed file size is not a resident-memory bound.
        if leaves_held * 192 + (len(rows) + len(outputs)) * 4096 > worker_budget:
            raise RuntimeError("PILOT_WORKER_UNCOMPRESSED_MEMORY_BUDGET_EXCEEDED")
        rows.extend(outputs)
    if rows:
        table = WORK["pa"].Table.from_pylist(rows)
        pq.write_table(table, output, compression="zstd", row_group_size=4096)
        ref_out = reference(output)
    else:
        ref_out = None
    return {"file": ref_out, "source": ref, "identities": identities, "rows": len(rows),
        "pid": os.getpid(), "elapsed_seconds": time.monotonic() - started}


def summarize(files, expected_records, fields, max_fraction):
    import pyarrow.parquet as pq
    counts = {f["field_key"]: collections.Counter() for f in fields}
    examples = collections.defaultdict(list)
    for ref in files:
        for batch in pq.ParquetFile(ref["path"]).iter_batches(batch_size=4096):
            for row in batch.to_pylist():
                c = counts[row["field_key"]]
                c["records_seen"] += 1
                c["source_valid_records"] += int(row["source_valid_record"])
                # Newly masked denominator is every canonical in-scope record.
                # Existing absent/NA source cells are separately reported.
                new_invalid = any(a and not b for a, b in zip(row["source_value_mask"], row["value_mask"]))
                c["newly_masked_records"] += int(new_invalid)
                c["existing_source_missing_records"] += int(not row["source_valid_record"])
                for reason in set(row["new_reasons"]):
                    c["new_reason:" + reason] += 1
                for reason in set(row["review_reasons"]):
                    c["review_reason:" + reason] += 1
                if new_invalid and len(examples[row["field_key"]]) < 20:
                    examples[row["field_key"]].append({"record_id":row["record_id"], "molecule_id":row["molecule_id"],
                        "reasons":row["new_reasons"],"values":row["values_float64"][:12]})
    report = {}
    for key, counter in counts.items():
        if counter["records_seen"] != expected_records:
            raise ValueError("CANONICAL_FIELD_RECORD_COVERAGE_DIFFERS:" + key)
        fraction = counter["newly_masked_records"] / expected_records
        report[key] = {**dict(counter), "new_mask_fraction":fraction, "stop": fraction > max_fraction,
            "first_20_failure_examples_not_severity_ranked":examples[key]}
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    plan=load_plan(args.plan)
    owners=owner_index(plan)
    tasks=source_jobs(plan,owners)
    output=Path(args.output).absolute()
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    results=[]
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=multiprocessing.get_context("spawn"),
                initializer=init_worker, initargs=(plan,owners,str(output))) as pool:
            for result in pool.map(process_file,enumerate(tasks),chunksize=1):
                results.append(result)
                used=sum(p.stat().st_size for p in output.glob("*.parquet"))
                if used > int(plan["max_output_bytes"]):
                    raise RuntimeError("PILOT_OUTPUT_BUDGET_EXCEEDED")
        seen=collections.Counter(identity for result in results for identity in result.pop("identities"))
        if any(n!=1 for n in seen.values()):
            raise ValueError("DUPLICATE_CANONICAL_RECORD_TASK_ACROSS_FILES")
        fields=[f for f in read_json(verify_reference(plan["sources"]["registry"]))["fields"] if f["status"]=="enabled"]
        files=[r["file"] for r in results if r["file"]]
        threshold=float(read_json(verify_reference(plan["sources"]["mask_rules"]))["hard_stop_new_mask_fraction"])
        details=summarize(files,len(owners),fields,threshold)
        stopped=[key for key,row in details.items() if row["stop"]]
        report={"status":"STOP_NEW_MASK_ABOVE_ONE_PERCENT" if stopped else "PILOT_ONLY_COMPLETED",
            "plan":reference(args.plan),"script":reference(__file__),"sources":plan["sources"],
            "records":len(owners),"workers":16,"actual_worker_pids":sorted({r["pid"] for r in results}),
            "elapsed_seconds":time.monotonic()-started,"slurm_job_id":os.environ["SLURM_JOB_ID"],
            "output_files":files,"source_results":results,"field_statistics":details,"stop_fields":stopped,
            "robust_z_status":"PENDING_TRAIN_ONLY_MEDIAN_MAD_FIT; NOT_OMITTED_FROM_FULL_ACCEPTANCE",
            "within_molecule_jump_status":"PENDING_COMPLETE_MOLECULE_GROUP_SCAN",
            "dipole_norm_status":"PENDING_INDEPENDENT_NORM_SOURCE_AVAILABILITY_REVIEW",
            "full_population_acceptance":False,"raw_source_modified":False}
        write_json_new(output/"pilot_report.json",report)
        print(report["status"],"records",len(owners),"stop_fields",stopped)
        return 2 if stopped else 0
    except BaseException as exc:
        write_json_new(output/"pilot_failure.json",{"status":"FAILED_EVIDENCE_PRESERVED","error_type":type(exc).__name__,
            "error":str(exc),"elapsed_seconds":time.monotonic()-started,"completed_source_results":results})
        raise


if __name__=="__main__":
    raise SystemExit(main())
