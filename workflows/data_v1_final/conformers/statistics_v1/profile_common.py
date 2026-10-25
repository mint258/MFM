"""Read-only D7 authority bindings and scalar-only canonical HOF projection."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

sys.dont_write_bytecode = True
PARENT = Path(__file__).parent.parent
FROZEN_COMMON_SHA = "ffa4fc9b6ce97be5b62af926c35337168b687f1f80a0fdd3564957dfe169b83b"
FROZEN_SELECTION_SHA = "41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb"
OWNER_KEYS = ("record_id", "molecule_id", "attempt_id", "job_id", "task_id")


def frozen_module(name, expected):
    path = PARENT / (name + ".py")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("REGISTERED_CONFORMER_HELPER_CHANGED:" + name)
    spec = importlib.util.spec_from_file_location("_d7_frozen_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IO = frozen_module("common", FROZEN_COMMON_SHA)
SELECTION = frozen_module("selection", FROZEN_SELECTION_SHA)


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config["schema"] != "DATA_V1_D7_PROFILE_V1" or not 128 <= config["molecules"] <= 256:
        raise ValueError("D7_PROFILE_ONLY_128_TO_256_MOLECULES")
    if config["workers"] != 16 or config["order_seed"] != 20261025 or config["rmsd_A"] != 0.5:
        raise ValueError("D7_FROZEN_WORKERS_SEED_OR_RMSD_MISMATCH")
    for pin in config["small_authority_pins"] + config["metadata_data_pins"] + config["science_source_pins"]:
        IO.require_pin(pin)
    return config


def runtime(config, intent_path, config_path):
    if socket.gethostname().split(".")[0] != "compute-0-20" or not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("D7_ANALYSIS_REQUIRES_COMPUTE20_SLURM")
    if int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16:
        raise ValueError("D7_REQUIRES_16_ALLOCATED_CPUS")
    intent = json.loads(Path(intent_path).read_text())
    request = intent["request"]
    if request["kind"] != "analysis" or request["node"] != "compute-0-20":
        raise ValueError("D7_ROOT_ANALYSIS_REQUEST_REQUIRED")
    IO.require_preflight(intent_path, config_path, config)
    return {"job_id": os.environ["SLURM_JOB_ID"], "node": "compute-0-20", "workers": 16}


def file_identity(path):
    st = Path(path).stat()
    return {"device": st.st_dev, "inode": st.st_ino, "bytes": st.st_size,
            "mtime_ns": st.st_mtime_ns, "uid": st.st_uid}


def bind_formal_input(config):
    receipt = json.loads(Path(config["formal_source_receipt"]).read_text())
    if receipt["schema"] != "DATA_V1_SOURCE_PIN_RECEIPT_V1" or receipt["status"] != "ALL_BOUND_INPUTS_SHA_VERIFIED":
        raise ValueError("VERIFIED_FORMAL_SOURCE_RECEIPT_REQUIRED")
    rows = [row for row in receipt["outputs"] if row["name"] == "formal_population"]
    if len(rows) != 1:
        raise ValueError("FORMAL_SOURCE_RECEIPT_NOT_UNIQUE")
    row = rows[0]
    actual, expected = file_identity(row["reference"]["path"]), row["after"]
    if row["reference"]["sha256"] != "ef2d99ae1b6c1001f6ffeb979ebafd10b04c13fa4774e52527a90a6276c06276":
        raise ValueError("FORMAL_POPULATION_SHA_CHANGED")
    if any(actual[k] != expected[v] for k, v in {"device": "device", "inode": "inode", "bytes": "size", "mtime_ns": "mtime_ns", "uid": "uid"}.items()):
        raise ValueError("FORMAL_INPUT_PHYSICAL_IDENTITY_CHANGED")
    return row["reference"]


def bound_family_ref(ref):
    if ref["family"] != "pm7_neutral" or ref.get("inherited_full_readback_verified") is not True:
        raise ValueError("CLOSED_PM7_NEUTRAL_REFERENCE_REQUIRED")
    before = file_identity(ref["path"])
    if before["bytes"] != ref["bytes"] or before["uid"] != 1278:
        raise ValueError("PM7_FILE_SIZE_OR_OWNER_CHANGED")
    return before


def scalar_columns(parquet_file):
    """Project only scalar CELL leaves, never atom/pair arrays or text payloads."""
    required = ["record_id", "molecule_id", "attempt_id", "job_id", "task_id", "lane",
                "total_atoms", "calc_type", "status", "numeric_issues", "converged"]
    leaves = [parquet_file.schema.column(i).path for i in range(len(parquet_file.schema))]
    for name in ("registry_id", "kind", "f64"):
        matches = [value for value in leaves if value.startswith("values.") and value.endswith("." + name)]
        if len(matches) != 1:
            raise ValueError("HOF_SCALAR_LEAF_NOT_UNIQUE:" + name)
        required.append(matches[0])
    return required


def decode_hof(row):
    cells = [cell for cell in row["values"] if cell["registry_id"] == 60]
    reason, value = None, None
    if row["calc_type"] != "pm7_B":
        reason = "NOT_PM7_B"
    elif row["status"] not in ("SUCCESS", "PROPERTY_FAILED"):
        reason = "TASK_STATUS_UNUSABLE"
    elif len(cells) != 1:
        reason = "HOF_CELL_ABSENT" if not cells else "DUPLICATE_HOF_CELL"
    elif cells[0]["kind"] != 1 or cells[0]["f64"] is None:
        reason = "HOF_NULL_OR_NONFLOAT_CELL"
    elif 60 in (row.get("numeric_issues") or []):
        reason = "HOF_NUMERIC_ISSUE"
    elif row.get("converged") is False:
        reason = "SCF_NOT_CONVERGED"
    elif not math.isfinite(float(cells[0]["f64"])):
        reason = "HOF_NONFINITE"
    else:
        value = float(cells[0]["f64"])
    return {"value_kcal_mol": value, "valid": reason is None, "reason": reason,
            "converged": row.get("converged"), "convergence_null_review": row.get("converged") is None,
            "registry_id": 60, "task": "pm7_B", "source_status": row["status"]}


def read_hof_file(task):
    import pyarrow as pa
    import pyarrow.parquet as pq
    ref, owners = task["ref"], task["owners"]
    before = bound_family_ref(ref)
    pf = pq.ParquetFile(ref["path"])
    columns = scalar_columns(pf)
    result = {}
    for batch in pf.iter_batches(batch_size=4096, columns=columns, use_threads=False):
        if set(batch.schema.field("values").type.value_type.names) != {"registry_id","kind","f64"}:
            raise ValueError("HOF_ARRAY_OR_TEXT_LEAF_WAS_NOT_PRUNED")
        selected = [i for i, rid in enumerate(batch.column(batch.schema.get_field_index("record_id")).to_pylist()) if rid in owners]
        if not selected:
            continue
        for row in batch.take(pa.array(selected, type=pa.int64())).to_pylist():
            owner = owners[row["record_id"]]
            if any(row[key] != owner[key] for key in OWNER_KEYS):
                continue  # A retained historical row is not the current owner.
            if row["lane"] != owner["lane"] or row["total_atoms"] != owner["total_atoms"] or row["job_id"] != ref["source_job_id"]:
                raise ValueError("CANONICAL_HOF_LANE_ATOMS_OR_SOURCE_JOB_MISMATCH")
            if row["record_id"] in result:
                raise ValueError("DUPLICATE_CANONICAL_HOF_RECORD")
            result[row["record_id"]] = decode_hof(row)
    if file_identity(ref["path"]) != before:
        raise ValueError("PM7_FILE_IDENTITY_CHANGED_DURING_SCALAR_READ")
    return {"hof": result, "source": ref, "identity": before, "projected_columns": columns}
