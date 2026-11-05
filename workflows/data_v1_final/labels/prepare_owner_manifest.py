"""Build a small, whole-molecule canonical owner manifest for the mask I/O pilot.

Production execution requires Root's reviewed Slurm intent.  No LMDB is opened.
Source roles are the frozen ROUTINE roles; common membership is local to this
pilot and cannot authorize final normalization or training.
"""
from __future__ import annotations

import argparse
import collections
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import socket
import struct
import time

from common import OWNER_KEYS, read_json, reference, verify_reference, write_json_new
from prepare_pilot_plan import catalog_source_files


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


def paths_sql(paths):
    return "[" + ",".join(q(path) for path in paths) + "]"


def file_identity(path):
    st = Path(path).stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def root_guard(path, config_path, config):
    receipt = read_json(path)
    request = receipt["request"]
    node = socket.gethostname().split(".")[0]
    if not os.environ.get("SLURM_JOB_ID") or node != "compute-0-20":
        raise ValueError("OWNER_PREPARATION_REQUIRES_SLURM_ON_COMPUTE20")
    if int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16 or config["workers"] != 16:
        raise ValueError("OWNER_PREPARATION_REQUIRES_16_ALLOCATED_CPU_THREADS")
    if request["node"] != node or request["cpus"] < 16 or request["memory_gib"] < 32:
        raise ValueError("ROOT_REQUEST_RESOURCE_MISMATCH")
    if request["wall_seconds"] > 3600 or request["estimated_peak_output_bytes"] < config["max_output_bytes"]:
        raise ValueError("ROOT_REQUEST_WALL_OR_STORAGE_BUDGET_MISMATCH")
    if reference(config_path) not in request["source_references"]:
        raise ValueError("ROOT_REQUEST_CONFIG_PIN_MISSING")
    age = time.time() - datetime.fromisoformat(receipt["observed_at"]).timestamp()
    if not 0 <= age <= 3600:
        raise ValueError("ROOT_PREFLIGHT_NOT_FRESH")
    real = re.search(r"(?:^|\s)RealMemory=(\d+)(?:\s|$)", receipt["node_metadata"])
    if real is None or not isinstance(receipt["existing_jobs_all_users"], list):
        raise ValueError("ROOT_ALL_USERS_MEMORY_EVIDENCE_MISSING")
    if receipt["committed_memory_mib"] + request["memory_gib"] * 1024 > 0.85 * int(real[1]):
        raise ValueError("ROOT_DECLARED_MEMORY_EXCEEDS_85_PERCENT")
    if receipt["account_free_bytes"] - config["max_output_bytes"] < config["quota_reserve_bytes"]:
        raise ValueError("ACCOUNT_QUOTA_WOULD_FALL_BELOW_200_GB")
    return receipt


def pick_whole_molecules(candidates, target, minimum, maximum):
    """Deterministic greedy selection within one owner job; never slice a molecule."""
    if not 32 <= minimum <= target <= maximum <= 128:
        raise ValueError("FIRST_PILOT_MUST_REMAIN_WITHIN_32_TO_128_RECORDS")
    selected = []
    total = 0
    seen = set()
    for row in candidates:
        mid = row["molecule_id"]
        if mid in seen:
            raise ValueError("DUPLICATE_CANDIDATE_MOLECULE")
        seen.add(mid)
        n = int(row["records"])
        if n <= 0 or n != int(row["S_conformers"]) or n > maximum:
            raise ValueError("CANDIDATE_WHOLE_MOLECULE_COUNT_INVALID")
        if total + n <= maximum:
            selected.append(row)
            total += n
        if total >= target:
            break
    if total < minimum:
        return []
    if len({row["job_id"] for row in selected}) != 1:
        raise ValueError("PILOT_MUST_USE_ONE_CANONICAL_OWNER_JOB")
    return selected


def atom_order_sha(numbers):
    return hashlib.sha256(b"".join(struct.pack("<q", z) for z in numbers)).hexdigest()


def validate_geometry_row(base, owner):
    if any(base[key] != owner[key] for key in OWNER_KEYS):
        raise ValueError("BASE_GEOMETRY_CANONICAL_OWNER_MISMATCH")
    numbers = base["atomic_numbers"]
    if (base["geometry_status"] != "ORIGINAL_PM7_GEOMETRY" or not isinstance(numbers, list)
            or len(numbers) != owner["total_atoms"]
            or any(type(z) is not int or not 1 <= z <= 118 for z in numbers)):
        raise ValueError("BASE_GEOMETRY_ATOM_COUNT_OR_STATUS_INVALID")
    if atom_order_sha(numbers) != base["native_atom_order_sha256"]:
        raise ValueError("BASE_GEOMETRY_NATIVE_ATOM_ORDER_SHA_DIFFERS")
    if base["source_payload_sha256"] != owner["record_payload_sha256"]:
        raise ValueError("BASE_GEOMETRY_SOURCE_PAYLOAD_SHA_DIFFERS")
    return numbers


def write_parquet_new(path, rows, cap_bytes):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist(rows), sink, compression="zstd", row_group_size=128)
    raw = sink.getvalue()
    if raw.size > cap_bytes:
        raise ValueError("OWNER_MANIFEST_EXCEEDS_SMALL_OUTPUT_CAP")
    with Path(path).open("xb") as stream:
        stream.write(memoryview(raw))
        stream.flush()
        os.fsync(stream.fileno())
    return reference(path)


def execute(config, config_path, preflight_path, output):
    started, cpu_started = time.monotonic(), time.process_time()
    root = root_guard(preflight_path, config_path, config)
    refs = config["sources"]
    for key in ("catalog", "verification", "roles", "strict_sprime", "registry", "mask_rules"):
        verify_reference(refs[key])
    roles = read_json(refs["roles"]["path"])
    if roles["status"] != "ROUTINE_MOLECULE_VAL_ROLES_FROZEN" or roles["roles"] != {
            "TRAIN":{"molecules":1206608,"records":11104772},
            "FULL":{"molecules":6248,"records":54557},
            "VAL":{"molecules":7610,"records":72525}}:
        raise ValueError("FROZEN_ROUTINE_ROLE_AUTHORITY_DIFFERS")
    if roles["direct_checks"]["TRAIN_VAL_molecule_id_overlap"] != 0 or roles["direct_checks"]["TRAIN_VAL_precomputed_identity_component_overlap"] != 0:
        raise ValueError("FROZEN_ROLE_DIRECT_OVERLAP_CHECK_NOT_ZERO")
    role_refs = [item for item in roles["outputs"] if Path(item["path"]).parent.name == "molecule_roles"]
    if len(role_refs) != 16:
        raise ValueError("EXPECTED_16_FROZEN_ROLE_PARTITIONS")
    for ref in role_refs:
        verify_reference(ref)
    catalog, verification = read_json(refs["catalog"]["path"]), read_json(refs["verification"]["path"])
    all_labels = catalog_source_files(catalog, verification)
    latest = Path(catalog["latest_molecules"])
    population = Path(catalog["authority"]["population"])
    if str(population) != refs["population"]["path"] or catalog["authority"]["population_sha256"] != refs["population"]["sha256"]:
        raise ValueError("POPULATION_POINTER_NOT_BOUND_TO_ACCEPTED_CATALOG")
    verify_reference(refs["population"], content=False)
    # latest is a small metadata index. Its actual hash and stable identity are
    # recorded here; the source path is inherited from the SHA-pinned catalog.
    latest_ref = reference(latest)
    before = {str(latest):file_identity(latest), str(population):file_identity(population)}
    output = Path(output).absolute()
    allowed = Path(config["external_output_root"])
    if output == allowed or allowed not in output.parents or any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError("OUTPUT_MUST_BE_NEW_OWNED_EXTERNAL_CHILD")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    spill = output / "duckdb_spill"
    spill.mkdir(mode=0o700)
    import duckdb
    import pyarrow as pa
    pa.set_cpu_count(16)
    pa.set_io_thread_count(4)
    db = duckdb.connect()
    db.execute("SET threads=16")
    db.execute("SET memory_limit='12GB'")
    db.execute("SET temp_directory="+q(spill))
    db.execute("SET max_temp_directory_size='2GiB'")
    try:
        db.execute("CREATE VIEW roles AS SELECT * FROM read_parquet("+paths_sql([r["path"] for r in role_refs])+")")
        role_counts = db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM roles").fetchone()
        if role_counts != (1220466,1220466):
            raise ValueError("FROZEN_ROLE_PARTITION_POPULATION_DIFFERS")
        db.execute("CREATE VIEW owners AS SELECT * FROM read_parquet("+q(latest)+") WHERE state='COMPLETE' AND receipt_context_consistent AND export_published")
        if db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM owners").fetchone() != (1220466,1220466):
            raise ValueError("CANONICAL_COMPLETE_OWNER_POPULATION_DIFFERS")
        db.execute("CREATE VIEW sprime AS SELECT * FROM read_parquet("+q(refs["strict_sprime"]["path"])+")")
        if db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM sprime").fetchone() != (1220466,1220466):
            raise ValueError("STRICT_SPRIME_AUDIT_POPULATION_DIFFERS")
        db.execute("""CREATE TEMP TABLE candidates AS SELECT r.molecule_id,r.records,r.file_group,
            r.source_role,r.effective_role,r.component_id,s.S_conformers,s.Sprime_conformers,
            o.attempt_id,o.job_id,o.task_id,o.lane
            FROM roles r JOIN sprime s USING(molecule_id) JOIN owners o USING(molecule_id)
            WHERE r.effective_role IN ('TRAIN','VAL') AND upper(s.split_role)=r.source_role
              AND s.Sprime_status='SUCCESS' AND s.S_usable_conformers=s.S_conformers
              AND s.Sprime_conformers>=s.S_conformers AND s.S_conformers=r.records
              AND r.records>0 AND r.records<="""+str(config["maximum_records"]))
        cost = collections.Counter()
        for ref in all_labels:
            cost[int(ref["source_job_id"])] += int(ref["bytes"])
        job_counts = db.execute("SELECT job_id,sum(records) AS available_records FROM candidates GROUP BY job_id").fetchall()
        jobs = sorted(((int(job),int(n),cost[int(job)]) for job,n in job_counts
            if int(n)>=config["minimum_records"] and 0<cost[int(job)]<=config["max_projected_label_source_bytes"]),key=lambda x:(x[2],x[0]))
        selected = []
        for job, available, source_bytes in jobs:
            candidate_rows = db.execute("SELECT * FROM candidates WHERE job_id=? ORDER BY sha256(?||molecule_id),molecule_id",[job,str(config["selection_seed"])]).fetch_arrow_table().to_pylist()
            selected = pick_whole_molecules(candidate_rows,config["target_records"],config["minimum_records"],config["maximum_records"])
            if selected:
                selected_job, projected_bytes = job, source_bytes
                break
        if not selected:
            raise ValueError("NO_ONE_OWNER_JOB_HAS_32_TO_128_STRICT_COMPLETE_RECORDS_WITHIN_IO_CAP")
        db.register("selected_molecules",pa.Table.from_pylist(selected))
        record_query = """SELECT p.record_id,p.molecule_id,p.total_atoms,p.new_role AS source_population_role,
            p.record_payload_sha256,p.file_group,s.attempt_id,s.job_id,s.task_id,s.lane,
            s.effective_role AS new_role,s.source_role,s.records,s.S_conformers,s.Sprime_conformers
            FROM read_parquet("""+q(population)+") p JOIN selected_molecules s USING(molecule_id) ORDER BY p.molecule_id,p.record_id"
        projected = time.monotonic()
        records = db.execute(record_query).fetch_arrow_table().to_pylist()
        population_projection_seconds = time.monotonic()-projected
        expected = sum(row["records"] for row in selected)
        if len(records)!=expected or len({row["record_id"] for row in records})!=expected:
            raise ValueError("WHOLE_SELECTED_MOLECULE_RECORD_COVERAGE_DIFFERS")
        by_mid = collections.Counter(row["molecule_id"] for row in records)
        if any(by_mid[row["molecule_id"]]!=row["records"] for row in selected):
            raise ValueError("SELECTED_MOLECULE_WAS_PARTIALLY_MATERIALIZED")
        for row in records:
            if row["source_population_role"].upper()!=row["source_role"] or row["total_atoms"]<=0:
                raise ValueError("SOURCE_ROLE_OR_RECORD_ATOM_COUNT_DIFFERS")
        artifact = {item["path"]:item for item in catalog["artifacts"]}
        bases = []
        for item in verification["files_verified"]:
            source = artifact[item["path"]]
            if item.get("family")=="base_geometry" and int(source["job_id"])==selected_job:
                if any(item[k]!=source[k] for k in ("bytes","sha256")):
                    raise ValueError("BASE_GEOMETRY_CATALOG_READBACK_PIN_DIFFERS")
                verify_reference(item,content=False)
                bases.append(item)
                before[item["path"]]=file_identity(item["path"])
        if not bases or sum(item["bytes"] for item in bases)>config["max_projected_base_source_bytes"]:
            raise ValueError("NO_BASE_GEOMETRY_SOURCE_WITHIN_IO_CAP")
        db.register("selected_records",pa.Table.from_pylist(records))
        geometry_query = "SELECT b.record_id,b.molecule_id,b.attempt_id,b.job_id,b.task_id,b.atomic_numbers,b.geometry_status,b.native_atom_order_sha256,b.source_payload_sha256 FROM read_parquet("+paths_sql([b["path"] for b in bases])+") b JOIN selected_records r ON "+" AND ".join("b."+key+"=r."+key for key in OWNER_KEYS)
        projected = time.monotonic()
        geometry = db.execute(geometry_query).fetch_arrow_table().to_pylist()
        base_projection_seconds = time.monotonic()-projected
        if len(geometry)!=expected or len({row["record_id"] for row in geometry})!=expected:
            raise ValueError("BASE_GEOMETRY_CANONICAL_RECORD_COVERAGE_DIFFERS")
        by_id = {row["record_id"]:row for row in geometry}
        for row in records:
            base = by_id[row["record_id"]]
            row["atomic_numbers"] = validate_geometry_row(base,row)
            row["native_atom_order_sha256"] = base["native_atom_order_sha256"]
            row["common_population_v1"] = True
            row["common_population_scope"] = "PILOT_LOCAL_STRICT_PM7_COMPLETE_AND_SPRIME_ENOUGH_VERIFIED"
            # No diagnostic geometry exclusion has been frozen for this pilot.
            # False deliberately prevents accidental use as a training list.
            row["training_eligible"] = False
            row["training_eligibility_status"] = "NOT_FINAL_DIAGNOSTIC_EXCLUSION_PENDING"
        for path, old in before.items():
            if file_identity(path)!=old:
                raise ValueError("SOURCE_IDENTITY_CHANGED_DURING_OWNER_PREPARATION:"+path)
        owner_ref = write_parquet_new(output/"owner_records.parquet",records,2<<20)
        molecule_ref = write_parquet_new(output/"selected_molecules.parquet",selected,2<<20)
        selected_labels = [ref for ref in all_labels if int(ref["source_job_id"])==selected_job]
        write_json_new(output/"label_source_files.json",selected_labels)
        quota = {"status":"QUOTA_METADATA_VERIFIED","available_bytes":root["account_free_bytes"],
            "observed_at_epoch":datetime.fromisoformat(root["observed_at"]).timestamp(),
            "raw_evidence":reference(preflight_path),"source":"Root submit_reviewed actual account quota; not df"}
        write_json_new(output/"quota_receipt.json",quota)
        plan = {"schema_version":"v1-label-pilot-plan.1","status":"PREPARED_NOT_SUBMITTED","mode":"pilot",
            "workers":16,"max_records":128,"read_batch_records":16,"geometry_source":"pm7",
            "max_output_bytes":config["mask_max_output_bytes"],
            "sources":{"registry":refs["registry"],"record_manifest":owner_ref,
                "source_files":reference(output/"label_source_files.json"),"mask_rules":refs["mask_rules"],
                "closed_verification":refs["verification"]},
            "canonical_provenance":{"identity_keys":list(OWNER_KEYS),"owner_state":"COMPLETE",
                "receipt_context_consistent":True,"export_published":True,"catalog":refs["catalog"],
                "population":refs["population"],"latest_molecules":latest_ref},
            "storage_budget":{"quota_receipt":reference(output/"quota_receipt.json"),
                "minimum_remaining_bytes":200_000_000_000,
                "total_declared_new_bytes":config["mask_max_output_bytes"]+(64<<20)},
            "common_population_frozen":False,"training_list":False,
            "owner_manifest_scope":"32–128 records, whole selected molecules, one canonical owner job"}
        write_json_new(output/"mask_plan.json",plan)
        report = {"status":"PILOT_OWNER_MANIFEST_READY_NOT_SCIENTIFIC_MASK_RUN",
            "job_id":os.environ["SLURM_JOB_ID"],"node":socket.gethostname(),"workers":16,
            "records":expected,"molecules":len(selected),"canonical_owner_job":selected_job,
            "roles":dict(collections.Counter(row["new_role"] for row in records)),
            "whole_molecule_record_coverage":True,"source_payload_and_atomic_order_SHA_verified":True,
            "projected_label_source_bytes":projected_bytes,"base_geometry_sources":bases,
            "strict_sprime_definition":"pinned v4 status SUCCESS; every S usable; strict SUCCESS+converged S-prime count>=all S records",
            "global_common_population_frozen":False,"training_eligible_records":0,
            "identity_evidence":{"direct_molecule_id_overlap":roles["direct_checks"]["TRAIN_VAL_molecule_id_overlap"],
                "direct_precomputed_component_overlap":roles["direct_checks"]["TRAIN_VAL_precomputed_identity_component_overlap"],
                "literal_chemical_key_overlap":"inherited from bound original WP5; not directly rescanned here"},
            "config":reference(config_path),"root_preflight":reference(preflight_path),"source_pins":refs,
            "role_partition_pins":role_refs,"latest_molecules_runtime_ref":latest_ref,
            "outputs":[owner_ref,molecule_ref,reference(output/"label_source_files.json"),reference(output/"mask_plan.json"),reference(output/"quota_receipt.json")],
            "original_LMDB_opened":False,"source_data_modified":False,"quantum_calls":0,
            "elapsed_seconds":time.monotonic()-started,"parent_cpu_seconds":time.process_time()-cpu_started,
            "population_projection_seconds":population_projection_seconds,
            "base_geometry_projection_seconds":base_projection_seconds,
            "parallelism":{"duckdb_cpu_threads":16,"pyarrow_cpu_threads":16,"pyarrow_io_threads":4,
                "execution":"database/Arrow thread pools; not 16 Python processes"},
            "parent_maxrss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            "duckdb_version":duckdb.__version__,"pyarrow_version":pa.__version__}
        write_json_new(output/"owner_receipt.json",report)
        return report
    except BaseException as exc:
        write_json_new(output/"owner_failure.json",{"status":"FAILED_EVIDENCE_PRESERVED","type":type(exc).__name__,"error":str(exc),
            "config":reference(config_path),"job_id":os.environ.get("SLURM_JOB_ID")})
        raise
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",required=True)
    p.add_argument("--root-preflight",required=True)
    p.add_argument("--output",required=True)
    args = p.parse_args()
    config = read_json(args.config)
    if config["schema"]!="DATA_V1_LABEL_OWNER_PILOT_V1":
        raise ValueError("UNKNOWN_OWNER_PREPARATION_CONFIG")
    if config["quota_reserve_bytes"]<200_000_000_000:
        raise ValueError("QUOTA_RESERVE_BELOW_GUIDE_200GB")
    started = time.monotonic()
    report = execute(config,args.config,args.root_preflight,args.output)
    print(json.dumps({"status":report["status"],"records":report["records"],"molecules":report["molecules"],
        "owner_job":report["canonical_owner_job"],"elapsed_seconds":time.monotonic()-started,"output":args.output}))


if __name__=="__main__":
    main()
