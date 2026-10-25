"""Materialize a frozen batch's original pointers and accepted S-prime rows."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from full_common import IO,KERNEL_SHA,config,formal_source,ledger_path,q,runtime


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True);p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--batch-id",required=True);p.add_argument("--root-preflight",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args();value=config(a.config)
    environment=runtime(value,a.root_preflight,a.config)
    plan=json.loads(a.plan.read_text())
    if plan["status"]!="FULL_SPRIME_PLAN_FROZEN" or plan["kernel_sha256"]!=KERNEL_SHA or plan["config"]!=IO.reference(a.config):
        raise ValueError("ACTUAL_ROOT_FROZEN_FORMAL_PLAN_REQUIRED")
    IO.require_pin(plan["root_review"]);IO.require_pin(plan["draft"])
    batches=[b for b in plan["batches"] if b["batch_id"]==a.batch_id]
    if len(batches)!=1:raise ValueError("BATCH_ID_NOT_UNIQUE")
    batch=batches[0];IO.require_pin(batch["tasks"])
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(16);pa.set_io_thread_count(2)
    selected=pq.read_table(batch["tasks"]["path"])
    if selected.num_rows!=batch["molecules"]:raise ValueError("BATCH_CARDINALITY_MISMATCH")
    metas=selected.to_pylist()
    for meta in metas:
        if ledger_path(value,meta["task_key"]).exists():
            raise ValueError("STARTED_OR_UNKNOWN_TASK_CANNOT_BE_REMATERIALIZED")
    source=formal_source(value)
    db=duckdb.connect();db.execute("SET threads=16");db.execute("SET memory_limit='20GB'")
    db.register("selected",selected)
    columns=["record_id","molecule_id","source_path","real_index","record_payload_sha256","total_atoms","energy_raw","smiles",
             "QC_molecule_chirality_conflict","QC_molecule_ez_conflict"]
    rows=db.execute("SELECT "+",".join("r."+c for c in columns)+" FROM read_parquet("+q(source["path"])+") r JOIN selected USING(molecule_id) ORDER BY r.molecule_id,r.record_id").fetch_arrow_table().to_pylist()
    grouped={m["molecule_id"]:[] for m in metas};existing={mid:[] for mid in grouped}
    for row in rows:grouped[row["molecule_id"]].append(row)
    manifest=json.loads(IO.require_pin(value["sprime_manifest"]).read_text())
    wanted_groups={int(m["file_group"]) for m in metas};observed=[]
    for ref in manifest["references"]:
        if ref["kind"]!="conformers" or int(ref["file_group"]) not in wanted_groups:continue
        path=Path(ref["path"]);before=(path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns)
        if before[1]!=ref["bytes"]:raise ValueError("OLD_SPRIME_SIZE_CHANGED")
        table=pq.read_table(path,filters=[("molecule_id","in",list(grouped)),("status","=","SUCCESS"),("converged","=",True)])
        for row in table.to_pylist():existing[row["molecule_id"]].append(row)
        if (path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns)!=before:raise ValueError("OLD_SPRIME_CHANGED_DURING_READ")
        observed.append({"reference":ref,"inode":before[0],"mtime_ns":before[2],"hash_scope":"inherited closed manifest; selected rows verified by unchanged kernel"})
    tasks=[]
    for meta in metas:
        mid=meta["molecule_id"]
        if len(grouped[mid])!=meta["expected_conformers"] or len(existing[mid])!=meta["Sprime_conformers"]:
            raise ValueError("FULL_MOLECULE_POINTER_OR_OLD_USABLE_COUNT_MISMATCH")
        tasks.append({"meta":meta,"records":grouped[mid],"existing_conformers":existing[mid]})
    out=IO.new_output_directory(a.output,value)
    data="".join(json.dumps(t,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n" for t in tasks).encode()
    IO.prewrite_guard(out/"tasks.jsonl",len(data),reserve_bytes=2<<20)
    with (out/"tasks.jsonl").open("xb") as f:f.write(data);f.flush();os.fsync(f.fileno())
    formal_source(value)
    IO.write_json_new(out/"prepared.json",{"status":"FORMAL_BATCH_INPUTS_READY","plan":IO.reference(a.plan),
        "batch":batch,"config":IO.reference(a.config),"runtime":environment,"formal_source":source,
        "old_sprime_sources":observed,"tasks":IO.reference(out/"tasks.jsonl"),"recipe_config":value["recipe_config"],
        "original_data_modified":False,"scientific_calls":0})
    db.close()


if __name__=="__main__":main()
