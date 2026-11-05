"""Prepare bounded or complete canonical owner-group plans without reading labels."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import time

from calibration import initial_queries
from support import budget,identity,legacy,load,new_root,path_list,ref,require,root_guard,save,sqlstr,write_blob


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",required=True);p.add_argument("--root-preflight",required=True)
    p.add_argument("--output",required=True);p.add_argument("--mode",choices=("pilot","full"),default="pilot")
    a=p.parse_args();cfg=load(a.config)
    if cfg["schema"]!="STREAMING_LABEL_SCAN_CONFIG_V1" or cfg["workers"]!=16:
        raise ValueError("UNKNOWN_STREAM_CONFIG_OR_WORKER_COUNT")
    root_guard(a.root_preflight,a.config,cfg["prepare_output_cap_bytes"])
    common,_=legacy(cfg)
    for key in ("catalog","verification","roles","registry","mask_rules","strict_sprime"):
        require(cfg["sources"][key])
    catalog=load(cfg["sources"]["catalog"]["path"]);verification=load(cfg["sources"]["verification"]["path"])
    # The existing, actually exercised metadata validator is imported by its
    # pinned adapter module directory; no old queue/main is executed.
    import importlib
    directory=Path(cfg["adapter_source_pins"][0]["path"]).parent
    import sys
    sys.path.insert(0,str(directory))
    try:project=importlib.import_module("prepare_pilot_plan").catalog_source_files
    finally:sys.path.pop(0)
    labels=project(catalog,verification)
    roles=load(cfg["sources"]["roles"]["path"])
    if roles["status"]!="ROUTINE_MOLECULE_VAL_ROLES_FROZEN" or roles["common_population_applied"]:
        raise ValueError("SOURCE_ROLE_AUTHORITY_OR_SCOPE_CHANGED")
    role_refs=[x for x in roles["outputs"] if Path(x["path"]).parent.name=="molecule_roles"]
    if len(role_refs)!=16:raise ValueError("EXPECTED_16_ROLE_PARTITIONS")
    for pin in role_refs:require(pin)
    population=require(cfg["sources"]["population"],content=False)
    if str(population)!=catalog["authority"]["population"] or cfg["sources"]["population"]["sha256"]!=catalog["authority"]["population_sha256"]:
        raise ValueError("SOURCE_POPULATION_NOT_ACCEPTED_CATALOG_AUTHORITY")
    latest=Path(catalog["latest_molecules"]);latest_pin=ref(latest)
    before={str(latest):identity(latest),str(population):identity(population)}
    root=new_root(a.output,cfg["external_output_root"]);cap=cfg["prepare_output_cap_bytes"]
    started=time.monotonic()
    import duckdb
    db=duckdb.connect();db.execute("SET threads=16");db.execute("SET memory_limit='12GB'")
    spill=root/"spill";spill.mkdir();db.execute("SET temp_directory="+sqlstr(spill));db.execute("SET max_temp_directory_size='4GiB'")
    try:
        db.execute("CREATE VIEW roles AS SELECT * FROM read_parquet("+path_list([x["path"] for x in role_refs])+")")
        db.execute("CREATE VIEW owners AS SELECT * FROM read_parquet("+sqlstr(latest)+") WHERE state='COMPLETE' AND receipt_context_consistent AND export_published")
        for name in ("roles","owners"):
            if db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM "+name).fetchone()!=(1220466,1220466):
                raise ValueError("FULL_CANONICAL_MOLECULE_POPULATION_DIFFERS:"+name)
        db.execute("CREATE TEMP TABLE molecules AS SELECT o.molecule_id,o.attempt_id,o.job_id,o.task_id,o.lane,r.records,r.effective_role,r.source_role,r.component_id FROM owners o JOIN roles r USING(molecule_id)")
        costs=collections.Counter()
        for item in labels:costs[int(item["source_job_id"])]+=int(item["bytes"])
        all_jobs=db.execute("SELECT job_id,count(*) FROM molecules GROUP BY job_id ORDER BY job_id").fetchall()
        if a.mode=="pilot":
            per=int(cfg["pilot_molecules_per_group"])
            eligible=sorted(((int(job),costs[int(job)]) for job,n in all_jobs
                if n>=per and 0<costs[int(job)]<=cfg["pilot_max_group_source_bytes"]),key=lambda x:(x[1],x[0]))
            jobs=[job for job,_ in eligible[:16]]
            if len(jobs)!=16 or not 256<=per*16<=1024:
                raise ValueError("PILOT_REQUIRES_16_SOURCE_GROUPS_AND_256_TO_1024_COMPLETE_MOLECULES")
            db.execute("CREATE TEMP TABLE chosen AS SELECT * FROM (SELECT *,row_number() OVER(PARTITION BY job_id ORDER BY sha256("+
                sqlstr(str(cfg["selection_seed"]))+"||molecule_id),molecule_id) AS pick FROM molecules WHERE job_id IN ("+
                ",".join(str(j) for j in jobs)+")) WHERE pick<="+str(per))
        else:
            jobs=[int(job) for job,_ in all_jobs]
            if len(jobs)<16:raise ValueError("FULL_SOURCE_PLAN_HAS_TOO_FEW_OWNER_GROUPS")
            db.execute("CREATE TEMP TABLE chosen AS SELECT *,0::BIGINT AS pick FROM molecules")
        # Physical source-file row numbers are stable under filter pushdown;
        # they are bound to the exact immutable authority parquet SHA.
        db.execute("""CREATE TEMP TABLE records AS SELECT p.file_row_number::UBIGINT AS record_ordinal,
            p.record_id,p.molecule_id,p.total_atoms,p.heavy_atoms,p.record_payload_sha256,
            c.attempt_id,c.job_id,c.task_id,c.lane,c.effective_role AS new_role,c.records
            FROM read_parquet("""+sqlstr(population)+",file_row_number=true) p JOIN chosen c USING(molecule_id) "+
            "WHERE upper(p.new_role)=c.source_role")
        n,unique,ord_unique,mols=db.execute("SELECT count(*),count(DISTINCT record_id),count(DISTINCT record_ordinal),count(DISTINCT molecule_id) FROM records").fetchone()
        expected,molecule_n=db.execute("SELECT sum(records),count(*) FROM chosen").fetchone()
        if n!=expected or n!=unique or n!=ord_unique or mols!=molecule_n:
            raise ValueError("RECORD_ORDINAL_OR_WHOLE_MOLECULE_COVERAGE_DIFFERS")
        if db.execute("SELECT count(*) FROM (SELECT molecule_id,count(*) AS n,max(records) AS expected FROM records GROUP BY molecule_id) WHERE n<>expected").fetchone()[0]:
            raise ValueError("WHOLE_MOLECULE_RECORD_COUNTS_NOT_CONSERVED")
        if a.mode=="full":
            lo,hi=db.execute("SELECT min(record_ordinal),max(record_ordinal) FROM records").fetchone()
            if (n,mols,lo,hi)!=(11231854,1220466,0,11231853):
                raise ValueError("FULL_AUTHORITY_ORDINAL_RANGE_NOT_EXACTLY_COVERED")
        registry=load(cfg["sources"]["registry"]["path"])
        fields=[dict(x,field_id=i) for i,x in enumerate(sorted((f for f in registry["fields"] if f["status"]=="enabled"),key=lambda f:f["field_key"]))]
        if len(fields)!=146:raise ValueError("ENABLED_COMPONENT_SCHEMA_CHANGED")
        tasks={name:i for i,name in enumerate(sorted({f["task"] for f in fields}))}
        if len(tasks)!=14:raise ValueError("EXPECTED_12_QUANTUM_PLUS_D20_D3_TASKS")
        field_ref=save(root/"field_map.json",fields,root,cap)
        query_ref=save(root/"median_queries_round0.json",initial_queries(fields),root,cap)
        all_artifacts={x["path"]:x for x in catalog["artifacts"]}
        base_refs=collections.defaultdict(list)
        for item in verification["files_verified"]:
            if item.get("family")=="base_geometry":
                source=all_artifacts[item["path"]]
                if any(item[k]!=source[k] for k in ("bytes","sha256")):
                    raise ValueError("BASE_GEOMETRY_VERIFICATION_PIN_DIFFERS")
                base_refs[int(source["job_id"])].append(item)
        groups=[]
        import pyarrow as pa
        import pyarrow.parquet as pq
        for i,job in enumerate(jobs):
            path=root/("owner_index_"+str(i).zfill(4)+".parquet")
            table=db.execute("SELECT * EXCLUDE(records) FROM records WHERE job_id=? ORDER BY record_ordinal",[job]).fetch_arrow_table()
            sink=pa.BufferOutputStream();pq.write_table(table,sink,compression="zstd",row_group_size=4096)
            owner_ref=write_blob(path,memoryview(sink.getvalue()),root,cap)
            count,molecule_count,train=db.execute("SELECT count(*),count(DISTINCT molecule_id),count(*) FILTER(WHERE new_role='TRAIN') FROM records WHERE job_id=?",[job]).fetchone()
            source_files=[x for x in labels if int(x["source_job_id"])==job]
            if {x["family"] for x in source_files}!={f["family_source"] for f in fields} or not base_refs[job]:
                raise ValueError("OWNER_GROUP_MISSING_FAMILY_OR_BASE_SOURCE")
            groups.append({"group_index":i,"source_job_id":job,"owner_index":owner_ref,"expected_records":count,
                "expected_molecules":molecule_count,"expected_TRAIN_records":train,"label_files":source_files,
                "base_files":base_refs[job]})
        # Identity-only feature basis; fitting coefficients still uses TRAIN
        # values exclusively. No VAL or FULL label enters any fit.
        basis=[int(r[0]) for r in db.execute("SELECT DISTINCT unnest(elements_atomic_numbers) AS z FROM read_parquet("+
            sqlstr(cfg["sources"]["strict_sprime"]["path"])+") ORDER BY z").fetchall()]
        if any(not 1<=z<=118 for z in basis):raise ValueError("INVALID_SOURCE_ELEMENT_BASIS")
        role_counts={str(role):int(count) for role,count in db.execute("SELECT new_role,count(*) FROM records GROUP BY new_role").fetchall()}
        for path,old in before.items():
            if identity(path)!=old:raise ValueError("CANONICAL_SOURCE_CHANGED_DURING_PREPARATION")
        manifest={"schema":"CANONICAL_STREAM_GROUP_PLAN_V1","mode":a.mode,"status":"PREPARED_NOT_SCANNED",
            "config":ref(a.config),"sources":cfg["sources"],"latest_runtime_pin":latest_pin,"role_partition_pins":role_refs,
            "field_map":field_ref,"initial_median_queries":query_ref,"task_codes":tasks,"element_basis":basis,
            "groups":groups,"records":n,"molecules":mols,"roles":role_counts,"source_group_count":len(groups),
            "coverage_fingerprint":hashlib.sha256(json.dumps([(g["source_job_id"],g["owner_index"]["sha256"],g["expected_records"]) for g in groups],separators=(",",":")).encode()).hexdigest(),
            "record_ordinal_definition":"physical zero-based file_row_number in SHA-bound single authority parquet",
            "all_original_roles_scanned":a.mode=="full","full_common_population_frozen":False,
            "diagnostic_exclusions_frozen":False,"normalization_completed":False,
            "fit_scope":"source TRAIN only before final common/diagnostic filtering; anomaly/size calibration only",
            "elapsed_seconds":time.monotonic()-started,"root_preflight":ref(a.root_preflight),
            "duckdb_version":duckdb.__version__,"unique_inode_output_bytes_before_manifest":budget(root,cap)}
        save(root/"group_plan.json",manifest,root,cap)
        print(json.dumps({"status":manifest["status"],"mode":a.mode,"groups":len(groups),"molecules":mols,"records":n,"output":str(root)}))
    except BaseException as exc:
        save(root/"failure.json",{"status":"PREPARE_FAILED_EVIDENCE_PRESERVED","type":type(exc).__name__,"error":str(exc)})
        raise
    finally:db.close()


if __name__=="__main__":main()
