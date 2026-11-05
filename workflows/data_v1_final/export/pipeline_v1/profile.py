"""Bounded source preparation: exact pinned footer/schema and optional <=16 rows."""
from __future__ import annotations
import argparse
from pathlib import Path
from .io import batches, check_allocation, manifest, read_json, verify, write_json
from wire_v1.store import file_ref


def run(config, output, *, sample_rows=0):
    import pyarrow.parquet as pq
    check_allocation(True)
    if type(sample_rows) is not int or not 0 <= sample_rows <= 16 or len(config["tables"]) > 32:
        raise ValueError("PROFILE_BOUNDED_32_FILES_AND_16_ROWS_MAXIMUM")
    results = []
    for ref in config["tables"]:
        p = verify(ref, content=config.get("verify_full_sha", True))
        table = pq.ParquetFile(p)
        info = {"reference": ref, "rows": table.metadata.num_rows, "row_groups": table.metadata.num_row_groups,
                "arrow_schema": str(table.schema_arrow), "sampled_rows": 0, "data_rows_read": sample_rows > 0}
        if sample_rows:
            batch = next(table.iter_batches(batch_size=sample_rows, use_threads=False), None)
            if batch is not None:
                if batch.nbytes > 128 * 1024 ** 2:
                    raise ValueError("PROFILE_BATCH_EXCEEDS_128MIB")
                info["sampled_rows"] = batch.num_rows
                info["sample_numeric_shapes_only"] = [{name: {"type": type(value).__name__, "length": len(value) if isinstance(value, (list, dict, str, bytes)) else None} for name, value in row.items()} for row in batch.to_pylist()]
        results.append(info)
    result = {"status": "BOUNDED_SOURCE_PROFILE_NOT_EXPORT_ACCEPTANCE", "sources": results, "scientific_values_printed": False,
              "sha_verification": "full" if config.get("verify_full_sha", True) else "size+inherited pin only; not new SHA proof", "source_data_read": sample_rows > 0}
    write_json(output, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--sample-rows", type=int, default=0)
    a = p.parse_args(); run(read_json(a.config), a.output, sample_rows=a.sample_rows)


if __name__ == "__main__":
    main()
