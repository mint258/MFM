"""Freeze VAL by legacy ROUTINE molecule IDs; source population stays read-only."""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import resource
import threading
import time
import traceback

_BARRIER = None
_ROUTINE_IDS = None
_OWNED_OUTPUT = None
MIB = 1024 * 1024


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * MIB), b""):
            h.update(chunk)
    return h.hexdigest()


def reference(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def verify(ref):
    path = Path(ref["path"])
    if path.is_symlink() or not path.is_file():
        raise ValueError("INPUT_NOT_REGULAR_FILE: " + str(path))
    before = path.stat()
    if before.st_size != ref["bytes"] or sha(path) != ref["sha256"]:
        raise ValueError("INPUT_PIN_MISMATCH: " + str(path))
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("INPUT_CHANGED_DURING_HASH: " + str(path))
    return {**ref, "device": after.st_dev, "inode": after.st_ino,
            "mtime_ns": after.st_mtime_ns, "uid": after.st_uid}


def save_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    if len(raw) > MIB:
        raise ValueError("JSON_OUTPUT_EXCEEDS_1_MIB")
    atomic_bytes(path, raw)


def atomic_bytes(path, raw):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    if path.exists() or pending.exists():
        raise FileExistsError(str(path))
    with pending.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def write_parquet(table, path, max_bytes):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd", row_group_size=65536)
    raw = sink.getvalue()
    if raw.size > max_bytes:
        raise ValueError("PARQUET_OUTPUT_CAP: " + str(path))
    atomic_bytes(path, raw)
    return reference(path)


def init_worker(barrier, routine_ids):
    import pyarrow as pa
    global _BARRIER, _ROUTINE_IDS
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    _BARRIER = barrier
    _ROUTINE_IDS = pa.array(routine_ids, type=pa.string())


def route_partition(table, routine_ids):
    import pyarrow as pa
    import pyarrow.compute as pc
    keep = pc.is_in(table["molecule_id"], value_set=routine_ids)
    source_role = pc.utf8_upper(table["split"])
    if pc.any(pc.and_(keep, pc.not_equal(source_role, "FULL"))).as_py():
        raise ValueError("ROUTINE_MOLECULE_OUTSIDE_FULL")
    if pc.any(pc.not_equal(table["original_routine"], keep)).as_py():
        raise ValueError("LEGACY_ROUTINE_MOLECULE_MEMBERSHIP_MISMATCH")
    effective = pc.if_else(keep, pa.scalar("VAL"), source_role)
    result = table.rename_columns(
        ["source_split" if name == "split" else name for name in table.column_names])
    result = result.append_column("source_role", source_role)
    result = result.append_column("effective_role", effective)
    return result.append_column("legacy_routine_molecule", keep)


def partition_worker(task):
    import pyarrow.compute as pc
    import psutil
    index, table, output = task
    started = time.monotonic()
    # Exactly 16 nonoverlapping tasks meet here, forcing actual concurrent workers.
    _BARRIER.wait(timeout=300)
    result = route_partition(table, _ROUTINE_IDS)
    stats = {}
    for role in ("TRAIN", "FULL", "VAL"):
        selected = result.filter(pc.equal(result["effective_role"], role))
        stats[role] = {"molecules": selected.num_rows,
                       "records": int(pc.sum(selected["records"]).as_py() or 0)}
    ref = write_parquet(result, Path(output) / f"part-{index:04d}.parquet", 4 * MIB)
    return {"partition": index, "rows": table.num_rows, "pid": os.getpid(),
            "pid_start_time": psutil.Process().create_time(),
            "elapsed_seconds": time.monotonic() - started,
            "cpu_seconds": time.process_time(),
            "maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "roles": stats, "output": ref}


def assert_zero_component_overlap(train_components, val_components):
    import pyarrow.compute as pc
    count = int(pc.sum(pc.cast(pc.is_in(val_components,
                value_set=pc.unique(train_components)), "int64")).as_py() or 0)
    if count:
        raise ValueError("TRAIN_VAL_IDENTITY_COMPONENT_OVERLAP")
    return count


def id_digest(values):
    if len(values) != len(set(values)) or any("\n" in value for value in values):
        raise ValueError("NONUNIQUE_OR_INVALID_ID")
    return hashlib.sha256(("\n".join(sorted(values)) + "\n").encode("utf-8")).hexdigest()


def self_test():
    import pyarrow as pa
    base = pa.table({"molecule_id": ["t", "v", "f"], "records": [3, 7, 2],
                     "split": ["train", "full", "full"],
                     "original_routine": [False, True, False],
                     "component_id": ["ct", "cv", "cf"], "file_group": [1, 1, 1]})
    selected = pa.array(["v"], type=pa.string())
    result = route_partition(base, selected).to_pylist()
    assert [(r["molecule_id"], r["effective_role"], r["records"]) for r in result] == [
        ("t", "TRAIN", 3), ("v", "VAL", 7), ("f", "FULL", 2)]
    assert result[1]["source_role"] == "FULL" and result[1]["legacy_routine_molecule"]
    bad = base.set_column(base.schema.get_field_index("split"), "split",
                          pa.array(["train", "train", "full"]))
    try:
        route_partition(bad, selected)
    except ValueError as exc:
        assert str(exc) == "ROUTINE_MOLECULE_OUTSIDE_FULL"
    else:
        raise AssertionError("Accepted ROUTINE member in TRAIN")
    try:
        assert_zero_component_overlap(pa.array(["shared"]), pa.array(["shared"]))
    except ValueError as exc:
        assert str(exc) == "TRAIN_VAL_IDENTITY_COMPONENT_OVERLAP"
    else:
        raise AssertionError("Accepted identity-component leakage")
    assert assert_zero_component_overlap(pa.array(["a"]), pa.array(["b"])) == 0
    assert id_digest(["b", "a"]) == id_digest(["a", "b"])
    print(json.dumps({"status": "SELF_TEST_PASS", "cases": [
        "whole_molecule_VAL_preserves_all_source_record_count",
        "ROUTINE_in_TRAIN_rejected", "identity_component_overlap_rejected",
        "stable_ID_digest"]}))


def run(config_path, output):
    global _OWNED_OUTPUT
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    import psutil
    started = time.monotonic()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    workers = int(config["workers"])
    if workers != 16 or not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("REQUIRES_SIXTEEN_WORKER_SLURM_ALLOCATION")
    if int(os.environ.get("SLURM_CPUS_PER_TASK", 0)) < workers:
        raise ValueError("INSUFFICIENT_ALLOCATED_CPUS")
    if os.uname().nodename.split(".")[0] != config["execution_node"]:
        raise ValueError("EXECUTION_NODE_MISMATCH")
    if output.exists():
        raise FileExistsError(str(output))
    if not output.is_absolute() or not output.is_relative_to(Path(config["external_root"])):
        raise ValueError("OUTPUT_OUTSIDE_OWN_EXTERNAL_ROOT")
    refs = config["inputs"]
    with cf.ThreadPoolExecutor(max_workers=min(workers, len(refs))) as pool:
        verified_list = list(pool.map(verify, refs.values()))
    verified = dict(zip(refs, verified_list))
    population = json.loads(Path(refs["population_manifest"]["path"]).read_text(encoding="utf-8"))
    training = json.loads(Path(refs["training_manifest"]["path"]).read_text(encoding="utf-8"))
    binding = json.loads(Path(refs["population_binding"]["path"]).read_text(encoding="utf-8"))
    decision = json.loads(Path(refs["user_decision"]["path"]).read_text(encoding="utf-8"))
    assert decision["validation"]["source"] == "ROUTINE"
    assert not decision["validation"]["family_holdout_required"]
    assert decision["validation"]["source_reference"] == refs["routine_arrow"]
    def bound_ref(container, ref):
        assert any(all(item.get(k) == ref[k] for k in ("path", "bytes", "sha256"))
                   for item in container), ("UNBOUND_INPUT", ref["path"])
    bound_ref(training["references"], refs["routine_arrow"])
    bound_ref(training["source_references"], refs["molecule_index"])
    bound_ref(binding["references"], refs["molecule_index"])
    bound_ref(binding["references"], refs["population_manifest"])
    expected = config["expected"]
    assert population["routine"] == {"records": expected["legacy_routine_records"],
        "molecules": expected["VAL_molecules"], "subset_of_FULL": True}
    inherited = population["identity_checks"]
    assert {row["identity_kind"] for row in inherited} == {
        "source_full", "reidentified_full", "reidentified_connectivity14_plus_protonation"}
    assert all(row["TRAIN_FULL_shared_keys"] == 0 for row in inherited)
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    with pa.memory_map(refs["routine_arrow"]["path"], "r") as mapped:
        routine = pa.ipc.open_file(mapped).read_all()
    assert routine.num_rows == expected["legacy_routine_records"]
    assert all(column.null_count == 0 for column in routine.columns)
    legacy_ids = routine["record_id"].to_pylist()
    routine_ids = pc.unique(routine["molecule_id"]).to_pylist()
    assert len(legacy_ids) == len(set(legacy_ids))
    assert len(routine_ids) == expected["VAL_molecules"]
    assert pc.all(routine["member_routine"]).as_py()
    columns = ["molecule_id", "records", "split", "original_routine",
               "component_id", "file_group"]
    molecules = pq.read_table(refs["molecule_index"]["path"], columns=columns, use_threads=False)
    assert molecules.num_rows == expected["source_molecules"]
    assert all(column.null_count == 0 for column in molecules.columns)
    assert pc.count_distinct(molecules["molecule_id"]).as_py() == molecules.num_rows
    assert set(pc.unique(molecules["split"]).to_pylist()) == {"train", "full"}
    routine_values = pa.array(routine_ids, type=pa.string())
    selected = molecules.filter(pc.is_in(molecules["molecule_id"], value_set=routine_values))
    assert selected.num_rows == len(routine_ids)
    assert pc.all(pc.equal(selected["split"], "full")).as_py()
    train = molecules.filter(pc.equal(molecules["split"], "train"))
    assert train.num_rows == expected["TRAIN_molecules"]
    assert int(pc.sum(train["records"]).as_py()) == expected["TRAIN_records"]
    overlap = assert_zero_component_overlap(train["component_id"], selected["component_id"])
    output.mkdir(parents=True, exist_ok=False)
    _OWNED_OUTPUT = output
    shard_dir = output / "molecule_roles"
    shard_dir.mkdir()
    samples = []
    stop = threading.Event()
    proc = psutil.Process()
    def monitor():
        while not stop.wait(0.2):
            try:
                members = [proc] + proc.children(recursive=True)
                samples.append(sum(p.memory_info().rss for p in members if p.is_running()))
            except psutil.Error:
                pass
    sampler = threading.Thread(target=monitor, daemon=True)
    sampler.start()
    context = mp.get_context("spawn")
    barrier = context.Barrier(workers)
    tasks = [(i, molecules.slice(molecules.num_rows * i // workers,
                molecules.num_rows * (i + 1) // workers - molecules.num_rows * i // workers),
              str(shard_dir)) for i in range(workers)]
    try:
        with cf.ProcessPoolExecutor(max_workers=workers, mp_context=context,
                initializer=init_worker, initargs=(barrier, routine_ids)) as pool:
            parts = list(pool.map(partition_worker, tasks, chunksize=1))
    finally:
        stop.set()
        sampler.join(timeout=5)
    assert len({part["pid"] for part in parts}) == workers
    for part in parts:
        try:
            still_owned = psutil.Process(part["pid"]).create_time() == part["pid_start_time"]
        except psutil.NoSuchProcess:
            still_owned = False
        assert not still_owned, "WORKER_NOT_ACTUALLY_EXITED"
    assert sum(part["rows"] for part in parts) == molecules.num_rows
    counts = {role: {unit: sum(part["roles"][role][unit] for part in parts)
                    for unit in ("molecules", "records")} for role in ("TRAIN", "FULL", "VAL")}
    assert counts["TRAIN"] == {"molecules": expected["TRAIN_molecules"],
                              "records": expected["TRAIN_records"]}
    assert counts["VAL"]["molecules"] == expected["VAL_molecules"]
    assert sum(row["molecules"] for row in counts.values()) == expected["source_molecules"]
    assert sum(row["records"] for row in counts.values()) == expected["source_records"]
    actual_peak = max(samples, default=proc.memory_info().rss)
    if actual_peak > config["sampled_rss_cap_bytes"]:
        raise MemoryError("SAMPLED_OWN_PROCESS_RSS_CAP_EXCEEDED")
    val = route_partition(selected, routine_values).sort_by([("molecule_id", "ascending")])
    val_ref = write_parquet(val, output / "validation_molecules.parquet", 16 * MIB)
    legacy = routine.append_column("legacy_routine_member", routine["member_routine"])
    legacy = legacy.append_column("source_role", pa.array(["FULL"] * routine.num_rows))
    legacy = legacy.append_column("effective_role", pa.array(["VAL"] * routine.num_rows))
    legacy_ref = write_parquet(legacy, output / "legacy_routine_records.parquet", 16 * MIB)
    output_refs = [part["output"] for part in parts] + [val_ref, legacy_ref]
    for part in parts:
        assert pq.read_metadata(part["output"]["path"]).num_rows == part["rows"]
    assert pq.read_metadata(val_ref["path"]).num_rows == expected["VAL_molecules"]
    assert pq.read_metadata(legacy_ref["path"]).num_rows == expected["legacy_routine_records"]
    post = {name: Path(ref["path"]).stat() for name, ref in refs.items()}
    assert all((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) == (
        verified[name]["device"], verified[name]["inode"], verified[name]["bytes"],
        verified[name]["mtime_ns"]) for name, st in post.items())
    output_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    assert output_bytes + MIB <= config["output_cap_bytes"]
    manifest = {
        "status": "ROUTINE_MOLECULE_VAL_ROLES_FROZEN", "version": 1,
        "observed_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "job_id": os.environ["SLURM_JOB_ID"], "hostname": os.uname().nodename,
        "uid": os.getuid(), "inputs": verified, "config": reference(config_path),
        "producer": reference(Path(__file__)), "roles": counts,
        "source_population_molecules": molecules.num_rows,
        "legacy_routine_records": routine.num_rows,
        "validation_molecule_ids_sha256": id_digest(routine_ids),
        "legacy_routine_record_ids_sha256": id_digest(legacy_ids),
        "effective_role_rule": "All PM7 and UFF geometries of ROUTINE molecule IDs are VAL",
        "legacy_record_rule": "legacy_routine_member only marks the original 11322 record IDs",
        "TRAIN_rule": "Original TRAIN membership unchanged before common-population filtering",
        "direct_checks": {"TRAIN_VAL_molecule_id_overlap": 0,
                          "TRAIN_VAL_precomputed_identity_component_overlap": overlap,
                          "ROUTINE_molecules_outside_source_FULL": 0,
                          "whole_molecule_source_record_counts": True},
        "inherited_identity_checks": inherited,
        "identity_limitations": [
            "molecule_index has component_id but no literal full InChIKey or backbone/protonation key.",
            "Literal identity zero-overlap is inherited from bound WP5 TRAIN/FULL acceptance, not rescanned.",
            "No claim of decontamination against future datasets is made by this role freeze."],
        "embargo": {"records": population["excluded_records"],
                    "molecules": population["excluded_molecules"],
                    "rule": "Original excluded/embargo population remains excluded; no records added here"},
        "geometry_role_application": "Join these molecule roles to each geometry; no 11M-record table duplicated",
        "common_population_applied": False,
        "outputs": output_refs, "worker_partitions": parts,
        "parallel_workers": workers, "all_workers_joined": True,
        "sampled_peak_own_process_rss_bytes": actual_peak,
        "rss_sampling_interval_seconds": 0.2,
        "rss_sampling_window": "parallel worker processing",
        "parent_whole_job_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "rss_measurement_limit": "Sampled aggregate RSS; not an exact instantaneous peak",
        "elapsed_seconds": time.monotonic() - started, "output_bytes_before_manifest": output_bytes,
        "original_data_modified": False, "scientific_QM_calls": 0,
        "formal_record_index_read": False, "new_training_lmdb_created": False,
    }
    save_json(output / "manifest.json", manifest)
    final_size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    assert final_size <= config["output_cap_bytes"]
    print(json.dumps({"status": manifest["status"], "roles": counts,
                      "manifest": reference(output / "manifest.json"),
                      "output_bytes": final_size, "workers": workers}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.config is None or args.output is None:
        parser.error("--config and --output are required outside --self-test")
    try:
        run(args.config, args.output)
    except Exception:
        if _OWNED_OUTPUT == args.output and not (args.output / "failure.json").exists():
            save_json(args.output / "failure.json", {
                "status": "FAILED", "traceback": traceback.format_exc()[-16000:],
                "original_data_modified": False})
        raise


if __name__ == "__main__":
    main()
