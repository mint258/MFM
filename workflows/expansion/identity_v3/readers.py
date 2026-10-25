"""Explicit identity/role projection; all other CSV/JSON values stay opaque."""
from __future__ import annotations

import gzip
from ..common import require
from ..identity_v2 import readers_v2 as original


FORMAL_COLUMNS = original.FORMAL_COLUMNS
EMBARGO_COLUMNS = original.EMBARGO_COLUMNS
parquet_identity_batches = original.parquet_identity_batches
json_identity_rows = original.json_identity_rows
qm7_native_z = original.qm7_native_z
qm9_archive_rows = original.qm9_archive_rows
ALLOWED_CSV = original.CSV_COLUMNS | {"mol", "CID", "num", "name", "smiles", "CMPD_CHEMBLID", "Model"}


def csv_identity_rows(ticket, columns):
    import pyarrow as pa
    import pyarrow.csv as pc
    require(columns and len(set(columns)) == len(columns) and set(columns) <= ALLOWED_CSV,
            "Only reviewed identity/role column names may be materialized")
    path = ticket.current_path()
    handle = gzip.open(path, "rb") if ticket.locator["kind"] == "csv_gz" else path.open("rb")
    with handle, pc.open_csv(handle, read_options=pc.ReadOptions(use_threads=False, block_size=1 << 20),
                            parse_options=pc.ParseOptions(newlines_in_values=True),
                            convert_options=pc.ConvertOptions(include_columns=list(columns),
                                                              column_types={name: pa.string() for name in columns})) as stream:
        for batch in stream:
            require(batch.schema.names == list(columns), "Unselected CSV feature/target entered output")
            yield from batch.to_pylist()
    ticket.current_path()
