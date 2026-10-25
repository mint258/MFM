"""Pinned inputs, bounded Arrow batches, external SQLite and Parquet outputs."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from wire_v1.codec import canonical_json
from wire_v1.store import file_ref

BATCH = 512
MAX_BATCH_BYTES = 128 * 1024 ** 2


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify(ref, *, content=True):
    p = Path(ref["path"])
    if not p.is_absolute() or not p.is_file() or p.stat().st_size != ref["bytes"]:
        raise ValueError("PIN_SIZE_OR_PATH:" + str(p))
    if not isinstance(ref.get("sha256"), str) or len(ref["sha256"]) != 64:
        raise ValueError("PIN_SHA_REQUIRED")
    if content and file_ref(p)["sha256"] != ref["sha256"]:
        raise ValueError("PIN_SHA:" + str(p))
    return p


def manifest(path, status=None):
    ref = file_ref(Path(path).absolute())
    obj = read_json(verify(ref))
    if status is not None and obj.get("status") != status:
        raise ValueError("MANIFEST_NOT_FROZEN:" + str(status))
    return obj, ref


def write_json(path, obj):
    with Path(path).open("xb") as f:
        f.write(canonical_json(obj) + b"\n")
    return file_ref(path)


def fresh_dir(path):
    p = Path(path)
    if not p.is_absolute() or p.exists():
        raise ValueError("NEW_EXTERNAL_ABSOLUTE_OUTPUT_REQUIRED")
    p.mkdir(parents=True, exist_ok=False)
    return p


def connect(path, *, readonly=False):
    if readonly:
        db = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
    else:
        db = sqlite3.connect(path, uri=True)
        db.execute("PRAGMA journal_mode=DELETE")
    db.execute("PRAGMA cache_size=-32768")
    db.execute("PRAGMA temp_store=FILE")
    db.row_factory = sqlite3.Row
    return db


def batches(ref, *, columns=None, row_groups=None, batch_size=BATCH, hash_input=True):
    import pyarrow.parquet as pq
    p = verify(ref, content=hash_input)
    before = p.stat()
    identity = (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    for batch in pq.ParquetFile(p).iter_batches(batch_size=batch_size,
            row_groups=row_groups, columns=columns, use_threads=False):
        if batch.nbytes > MAX_BATCH_BYTES:
            raise ValueError("DECODED_ARROW_BATCH_EXCEEDS_128MIB")
        yield batch
    after = p.stat()
    if identity != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("INPUT_CHANGED_DURING_READ")


def arrow_batches(ref, *, columns=None):
    if ref.get("format", "parquet") == "parquet":
        yield from batches(ref, columns=columns)
        return
    if ref.get("format") != "arrow_file":
        raise ValueError("EXPLICIT_PARQUET_OR_ARROW_FILE_FORMAT_REQUIRED")
    import pyarrow as pa
    import pyarrow.ipc as ipc
    with pa.memory_map(str(verify(ref)), "r") as memory:
        reader = ipc.open_file(memory)
        for index in range(reader.num_record_batches):
            original = reader.get_batch(index)
            if columns:
                original = original.select(columns)
            # IPC buffers remain memory mapped; Python rows are bounded.
            for start in range(0, len(original), BATCH):
                batch = original.slice(start, BATCH)
                if batch.nbytes > MAX_BATCH_BYTES:
                    raise ValueError("IPC_BATCH_EXCEEDS_128MIB")
                yield batch


def query_parquet(db, query, path, schema, parameters=()):
    import pyarrow as pa
    import pyarrow.parquet as pq
    p = Path(path)
    if p.exists():
        raise FileExistsError(p)
    count = 0
    with pq.ParquetWriter(p, schema, compression="zstd") as writer:
        cursor = db.execute(query, parameters)
        while True:
            rows = cursor.fetchmany(BATCH)
            if not rows:
                break
            table = pa.Table.from_pylist([dict(r) for r in rows], schema=schema)
            if table.nbytes > MAX_BATCH_BYTES:
                raise ValueError("OUTPUT_ARROW_BATCH_EXCEEDS_128MIB")
            writer.write_table(table, row_group_size=BATCH)
            count += len(rows)
    return {**file_ref(p), "rows": count}


def scalar(db, sql, args=()):
    return db.execute(sql, args).fetchone()[0]


def reject_rows(db, sql, error, args=()):
    if db.execute(sql, args).fetchone() is not None:
        raise ValueError(error)


def check_allocation(fixture=False):
    if fixture:
        if os.uname().nodename.split(".")[0] != "compute-0-20":
            raise ValueError("FIXTURE_REQUIRES_COMPUTE20")
        return
    if "SLURM_JOB_ID" not in os.environ or int(os.environ.get("SLURM_CPUS_PER_TASK", 0)) < 16:
        raise ValueError("PRODUCTION_REQUIRES_ROOT_REVIEWED_16CPU_SLURM")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("CPU_ONLY_EXPLICIT_EMPTY_CUDA_REQUIRED")


def disk_cap(root, cap):
    total = sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())
    if total > cap:
        raise ValueError("DECLARED_EXTERNAL_OUTPUT_CAP_EXCEEDED")
    return total


def rank_hash(seed, domain, molecule):
    return hashlib.sha256(canonical_json(["D5-SHA256-uniform-order-v1", seed, domain, molecule])).hexdigest()


def quota_preflight(config, fixture):
    if fixture:
        return
    budget = config["storage_budget"]
    receipt = read_json(verify(budget["quota_receipt"]))
    if receipt.get("status") != "QUOTA_METADATA_VERIFIED" or not 0 <= time.time() - receipt["observed_at_epoch"] <= 3600:
        raise ValueError("FRESH_ACTUAL_ACCOUNT_QUOTA_RECEIPT_REQUIRED")
    declared = budget["total_declared_new_bytes"]
    if declared < config["maximum_output_bytes"] or receipt["available_bytes"] - declared < 200_000_000_000:
        raise ValueError("DECLARED_CAP_OR_200GB_ACCOUNT_QUOTA_RESERVE")


def memory_guard(limit=1_500_000_000):
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if peak > limit:
        raise ValueError("BOUNDED_WORKER_PEAK_RSS_STOP")
    return peak
