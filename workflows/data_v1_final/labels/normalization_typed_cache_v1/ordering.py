"""Logical order follows frozen original owner groups and source rows."""
from __future__ import annotations

import hashlib
import json
from .contract import need, reference


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def logical_manifest(dataset_id, group_plan_reference, groups, field_ids):
    reference(group_plan_reference)
    need(isinstance(dataset_id, str) and dataset_id and groups, "EXACT_DATASET_AND_OWNER_GROUPS")
    need(field_ids and len(field_ids) == len(set(field_ids))
         and all(type(v) is int and 0 <= v < 146 for v in field_ids), "FROZEN_FIELD_ORDER_REQUIRED")
    jobs = []; seen_jobs = set(); seen_groups = set()
    for position, group in enumerate(groups):
        gi, job = group["group_index"], group["source_job_id"]
        need(type(gi) is int and gi >= 0 and type(job) is int and job > 0,
             "EXACT_ORIGINAL_OWNER_GROUP_ID")
        need(gi not in seen_groups and job not in seen_jobs, "ONE_LOGICAL_GROUP_PER_ORIGINAL_OWNER_JOB")
        seen_groups.add(gi); seen_jobs.add(job)
        files = [reference(pin) for pin in group["label_files"]]
        need(files and len({pin["path"] for pin in files}) == len(files), "EXACT_ORIGINAL_LABEL_FILE_ORDER")
        jobs.append({"partition_id": position, "original_group_index": gi,
                     "source_job_id": job, "owner_index": reference(group["owner_index"]),
                     "label_files_in_original_order": files})
    body = {"schema": "D4_LOGICAL_ORIGINAL_SOURCE_ORDER_V1", "dataset_id": dataset_id,
            "group_plan_reference": group_plan_reference, "partitions": jobs,
            "field_ids_in_original_order": list(field_ids), "TSQR_chunk": 256,
            "within_partition_order": ["original_file_position", "source_physical_row"],
            "native_leaf_order": "UNCHANGED_ORIGINAL_TASK_COMPONENTS_ORDER",
            "merge_order": "ORIGINAL_ORDERED_LEFT_FOLD_QR_AND_CHAN",
            "worker_count_or_physical_cache_parts_in_order_key": False}
    return {**body, "logical_definition_sha256": hashlib.sha256(canonical(body)).hexdigest()}


def row_key(row):
    values = tuple(row[key] for key in ("partition_id", "original_file_position", "source_physical_row"))
    need(all(type(v) is int and v >= 0 for v in values), "EXACT_LOGICAL_SOURCE_ROW_KEY")
    return values


def ordered_keys(rows):
    previous = None
    for row in rows:
        key = row_key(row)
        need(previous is None or previous < key, "SOURCE_ORDER_DUPLICATE_OR_BACKWARDS")
        previous = key
        yield key
