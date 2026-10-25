"""Bounded five-footer metadata probe. No data pages, coordinates or generation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import socket
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent.parent/"formal_v1"))
from full_common import IO


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    if socket.gethostname().split(".")[0]!="compute-0-20":raise ValueError("METADATA_PROBE_NODE20_ONLY")
    import pyarrow as pa
    import pyarrow.parquet as pq
    source=json.loads(a.manifest.read_text());results=[]
    for ref in source["references"]:
        if ref["kind"]!="conformers":continue
        path=Path(ref["path"]);before=path.stat()
        parquet=pq.ParquetFile(path)
        if parquet.schema_arrow.field("sprime_conf_idx").type!=pa.int64():raise ValueError("SPRIME_INDEX_NOT_INT64")
        after=path.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns) or after.st_size!=ref["bytes"]:
            raise ValueError("BASELINE_FILE_IDENTITY_CHANGED")
        results.append({"reference":ref,"schema":str(parquet.schema_arrow),"rows":parquet.metadata.num_rows,
            "row_groups":parquet.metadata.num_row_groups,"inode":after.st_ino,"mtime_ns":after.st_mtime_ns,
            "hash_basis":"inherited closed manifest; this metadata probe does not rehash data pages",
            "data_pages_read":False})
    if len(results)!=5:raise ValueError("ALL_FIVE_CONFORMER_FOOTERS_REQUIRED")
    IO.write_json_new(a.output,{"status":"SPRIME_FIVE_FOOTERS_INT64_VERIFIED","manifest":IO.reference(a.manifest),
        "hostname":socket.gethostname(),"pyarrow":pa.__version__,"tables":results,"scientific_calls":0})


if __name__=="__main__":main()
