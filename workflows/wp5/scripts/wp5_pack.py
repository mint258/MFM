"""WP5 no-POLAR/no-ESP/no-Hessian all-conformer cost packing; no QM or LMDB writes."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, heapq, json, math, os, time
from pathlib import Path

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011")
SCREEN = Path("/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011")
SLOTS = {"compute-0-14": 4, "compute-0-15": 4, "compute-0-16": 4,
         "compute-0-17": 8, "compute-0-18": 4, "compute-0-19": 5}
EXPECTED_RECORDS, EXPECTED_MOLECULES = 11231854, 1220466
STRATA = ("0_10", "11_20", "21_30", "31_50", "51_75", "76_100", "above_100")

def quoted(path):
    return "'" + str(path).replace("'", "''") + "'"

def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def bins(n):
    return "0_10" if n <= 10 else "11_20" if n <= 20 else "21_30" if n <= 30 else (
        "31_50" if n <= 50 else "51_75" if n <= 75 else "76_100" if n <= 100 else "above_100")

def stats(values):
    import numpy as np
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"n": 0}
    return {"n": len(values), "min": float(values.min()), "p50": float(np.quantile(values, .5)),
            "p90": float(np.quantile(values, .9)), "p99": float(np.quantile(values, .99)),
            "max": float(values.max()), "sum": float(values.sum())}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--population", type=Path, default=ROOT / "population/manifest.json")
    p.add_argument("--cost-model", type=Path, default=SCREEN / "c_engineering/cost_packing_v3/C1_scenario_matrix.json")
    p.add_argument("--pilot-geometry", type=Path, default=SCREEN / "c_engineering/xyz/analysis_geometry.parquet")
    p.add_argument("--out", type=Path, default=ROOT / "packing")
    p.add_argument("--threads", type=int, default=24)
    p.add_argument("--memory-gb", type=int, default=20)
    p.add_argument("--spill-root", type=Path, default=Path(os.environ.get("TMPDIR", "/tmp")))
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text())
        print("AST_PASS_NO_DATA_NO_QM_NO_LMDB")
        return
    allocation = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if not os.environ.get("SLURM_JOB_ID") or not 16 <= args.threads <= allocation:
        raise RuntimeError("SLURM_AT_LEAST16_EFFECTIVE_THREADS_REQUIRED")
    population = json.loads(args.population.read_text())
    if population.get("status") != "WP5_FORMAL_POPULATION_CLOSED":
        raise ValueError("FORMAL_POPULATION_NOT_CLOSED")
    expected_records = population["formal_records"]
    expected_molecules = population["formal_molecules"]
    if not population.get("fixture",False) and (expected_records, expected_molecules) != (EXPECTED_RECORDS, EXPECTED_MOLECULES):
        raise RuntimeError("MANIFEST_FORMAL_POPULATION_COUNT_MISMATCH")
    if any(row["TRAIN_FULL_shared_keys"] for row in population["identity_checks"]):
        raise ValueError("FORMAL_POPULATION_IDENTITY_LEAKAGE")
    if (args.out / "manifest.json").exists() or (args.out / "molecule_assignments.parquet").exists():
        raise FileExistsError("Refuse to overwrite already published WP5 packing")
    if not args.out.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Output must remain inside the new WP5 run root")
    args.out.mkdir(parents=True, exist_ok=True)
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    model = json.loads(args.cost_model.read_text())
    candidates = [s for s in model["scenarios"] if
                  (s["retained"], s["POLAR"], s["ESP"], s["Hessian"], s["CD_scope"]) ==
                  ("relaxed", "drop", "drop", "none", "all")]
    if len(candidates) != 1:
        raise ValueError("UNIQUE_NO_POLAR_NO_ESP_NO_HESS_ALL_CONFORMER_MODEL_REQUIRED")
    scenario = candidates[0]
    factor = float(model["allocated_to_service_factor"])
    inflation = 1.71
    per_stratum = {s: [] for s in STRATA}
    for component in scenario["components"]:
        if component["scope"] != "all" or component["task"] in ("pm7_ESP", "xtb_hessian") or "ohess" in component["task"]:
            raise ValueError("COST_COMPONENT_OUTSIDE_WP5_RECIPE")
        value = component["mean_service_seconds"]
        if value is None or not math.isfinite(value) or value < 0:
            raise ValueError("UNMEASURED_OR_INVALID_WP5_COST_COMPONENT")
        per_stratum[component["size_stratum"]].append(component)
    if any(len(parts) != 12 for parts in per_stratum.values()):
        raise ValueError("WP5_REQUIRES_TWELVE_NO_ESP_NONHESS_CALLS_PER_RECORD")
    db = duckdb.connect()
    db.execute("SET threads=" + str(args.threads))
    db.execute("SET memory_limit=" + quoted(str(args.memory_gb) + "GB"))
    db.execute("SET preserve_insertion_order=false")
    spill = args.spill_root / ("phase1_wp5_pack_" + os.environ["SLURM_JOB_ID"] + "_" + str(os.getpid()))
    spill.mkdir(parents=True, exist_ok=False)
    db.execute("SET temp_directory=" + quoted(spill))
    pilot_columns = {r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(" + quoted(args.pilot_geometry) + ")").fetchall()}
    natoms_column = "total_atoms" if "total_atoms" in pilot_columns else "natoms"
    if natoms_column not in pilot_columns or "size_stratum" not in pilot_columns:
        raise ValueError("PILOT_GEOMETRY_SIZE_FIELDS_REQUIRED")
    pilot_count = db.execute("SELECT count(*) FROM read_parquet(" + quoted(args.pilot_geometry) + ")").fetchone()[0]
    if pilot_count != 10020:
        raise RuntimeError("MANIFEST_NATIVE_PILOT_RECORD_COUNT_MISMATCH")
    maxima = dict(db.execute("SELECT size_stratum,max(" + natoms_column + ") FROM read_parquet(" +
                             quoted(args.pilot_geometry) + ") GROUP BY size_stratum").fetchall())
    if set(maxima) != set(STRATA):
        raise ValueError("PILOT_DOES_NOT_COVER_ALL_SEVEN_COST_STRATA")
    # All twelve source native tasks have one attempted outcome for each pilot
    # record, so the per-task max natoms used by C2 equals this geometry maximum.
    means = {s: sum(part["mean_service_seconds"] for part in per_stratum[s]) for s in STRATA}
    molecule_path = Path(population["outputs"]["molecule_index"])
    record_path = Path(population["outputs"]["record_index"])
    db.execute("CREATE TABLE mol_input AS SELECT * FROM read_parquet(" + quoted(molecule_path) + ")")
    molecule_rows = db.execute("SELECT molecule_id,records,max_heavy_atoms,max_total_atoms,file_group,split "
                               "FROM mol_input").fetchall()
    if len(molecule_rows) != expected_molecules or sum(r[1] for r in molecule_rows) != expected_records:
        raise RuntimeError("MANIFEST_PACKING_INPUT_COUNT_MISMATCH")
    cohorts = {(group, large): [] for group in range(1, 6) for large in (False, True)}
    for molecule_id, records, heavy, natoms, group, split in molecule_rows:
        stratum = bins(heavy)
        extrapolation = max(1.0, (natoms / maxima[stratum]) ** 3)
        service = records * means[stratum] * extrapolation
        cohorts[(group, heavy > 75)].append({
            "molecule_id": molecule_id, "records": int(records), "heavy_atoms": int(heavy),
            "total_atoms": int(natoms), "file_group": int(group), "split": split,
            "size_stratum": stratum, "size_extrapolation_factor": extrapolation,
            "predicted_service_seconds": service, "planned_allocated_seconds": service * factor * inflation,
        })
    tasks, assignments, oversized = [], [], []
    for (group, large), molecules in sorted(cohorts.items()):
        molecules.sort(key=lambda r: (-r["planned_allocated_seconds"], r["molecule_id"]))
        target_hours = 20 if large else 40
        budget = 24 * target_hours * 3600
        task_id = len(tasks)
        lanes = [(0.0, lane) for lane in range(24)]
        heapq.heapify(lanes)
        current, core_seconds = [], 0.0
        def close_task():
            nonlocal current, core_seconds, lanes, task_id
            if not current:
                return
            tasks.append({
                "task_id": task_id, "file_group": group,
                "large_class": large, "class": "heavy_gt75" if large else "ordinary_le75",
                "target_hours": target_hours, "lanes": 24, "sbatch_hours": 48,
                "molecules": len(current), "records": sum(r["records"] for r in current),
                "predicted_core_hours": core_seconds / 3600,
                "predicted_wall_hours": max(load for load, _ in lanes) / 3600,
                "predicted_lane_hours": [load / 3600 for load, lane in sorted(lanes, key=lambda r: r[1])],
                "maximum_molecule_planned_hours": max(r["planned_allocated_seconds"] for r in current) / 3600,
                "maximum_heavy_atoms": max(r["heavy_atoms"] for r in current),
                "record_directory": str(args.out / "record_partitions" / ("task_id=" + str(task_id))),
            })
            task_id = len(tasks)
            current, core_seconds = [], 0.0
            lanes = [(0.0, lane) for lane in range(24)]
            heapq.heapify(lanes)
        for molecule in molecules:
            cost = molecule["planned_allocated_seconds"]
            if cost > 46 * 3600:
                # Do not silently split molecules across jobs. A single oversized
                # molecule requires explicit intra-molecule parallelism/resume.
                oversized.append(molecule)
                continue
            load, lane = lanes[0]
            if current and (core_seconds + cost > budget or load + cost > 46 * 3600):
                close_task()
            load, lane = heapq.heappop(lanes)
            heapq.heappush(lanes, (load + cost, lane))
            sequence = len(current)
            current.append(molecule)
            core_seconds += cost
            assignments.append({"task_id": task_id, "lane": lane, "sequence_in_task": sequence,
                                "large_class": large, "target_hours": target_hours, **molecule})
        close_task()
    if len(assignments) + len(oversized) != expected_molecules:
        raise RuntimeError("MANIFEST_WHOLE_MOLECULE_PACKING_COUNT_MISMATCH")
    if oversized:
        save(args.out / "oversized_molecules_requiring_internal_parallelism.json",
             {"status": "REPACK_REQUIRED_WITHOUT_SPLITTING_MOLECULE_ACROSS_TASKS",
              "molecules": oversized, "assignment_molecules": len(assignments),
              "formal_molecules": expected_molecules})
        raise RuntimeError("REPACK_OVERSIZED_MOLECULE_WITH_INTERNAL_PARALLELISM_REQUIRED")
    if sum(t["molecules"] for t in tasks) != expected_molecules or sum(t["records"] for t in tasks) != expected_records:
        raise RuntimeError("MANIFEST_TASK_COUNTS_NOT_CLOSED")
    if any(t["predicted_wall_hours"] > 46 for t in tasks):
        raise RuntimeError("REPACK_TASK_PREDICTION_EXCEEDS46H")
    # Static ideal schedule using the authorized six-node slot capacities.
    schedule = [(0.0, node, slot) for node, slots in SLOTS.items() for slot in range(slots)]
    heapq.heapify(schedule)
    # Larger individual molecules first within equal wall predictions.
    priority = sorted(tasks, key=lambda t: (-t["predicted_wall_hours"],
                      -t["maximum_molecule_planned_hours"], t["task_id"]))
    for rank, task in enumerate(priority):
        start, node, slot = heapq.heappop(schedule)
        end = start + task["predicted_wall_hours"]
        task.update(priority_rank=rank, node=node, node_slot=slot,
                    predicted_start_hours=start, predicted_end_hours=end)
        heapq.heappush(schedule, (end, node, slot))
    assignment_table = pa.Table.from_pylist(assignments)
    db.register("assignment_arrow", assignment_table)
    db.execute("CREATE TABLE assignments AS SELECT * FROM assignment_arrow")
    db.execute("COPY (SELECT * FROM assignments ORDER BY task_id,sequence_in_task) TO " +
               quoted(args.out / "molecule_assignments.parquet.pending") + " (FORMAT PARQUET, COMPRESSION ZSTD)")
    (args.out / "molecule_assignments.parquet.pending").replace(args.out / "molecule_assignments.parquet")
    db.execute("CREATE VIEW formal_records AS SELECT * FROM read_parquet(" + quoted(record_path) + ")")
    actual_records = db.execute("SELECT count(*) FROM formal_records").fetchone()[0]
    linked_records = db.execute("SELECT count(*) FROM formal_records p JOIN assignments a USING(molecule_id)").fetchone()[0]
    if actual_records != expected_records or linked_records != expected_records:
        raise RuntimeError("MANIFEST_TASK_RECORD_JOIN_COUNT_MISMATCH")
    # Each formal record and all its QC/source pointers is exposed under one
    # task partition. No raw source data or previous manifest is modified.
    db.execute("COPY (SELECT p.*,a.task_id,a.lane,a.sequence_in_task,a.large_class,"
               "a.target_hours FROM formal_records p JOIN assignments a USING(molecule_id) "
               "ORDER BY a.task_id,a.sequence_in_task,p.conformer_id,p.record_id) TO " +
               quoted(args.out / "record_partitions.pending") +
               " (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY(task_id), ROW_GROUP_SIZE 131072)")
    partition_summary = db.execute("SELECT task_id,count(*) AS records,count(DISTINCT molecule_id) AS molecules,"
                                 "count(DISTINCT file_group) AS file_groups FROM read_parquet(" +
                                 quoted(args.out / "record_partitions.pending/**/*.parquet") +
                                 ",hive_partitioning=true) GROUP BY task_id").fetchall()
    observed = {int(row[0]): row[1:] for row in partition_summary}
    if len(observed) != len(tasks) or any(observed[t["task_id"]] != (t["records"],t["molecules"],1) for t in tasks):
        raise RuntimeError("MANIFEST_SERIALIZED_TASK_PARTITIONS_COUNT_MISMATCH")
    (args.out / "record_partitions.pending").replace(args.out / "record_partitions")
    db.close()
    import shutil
    shutil.rmtree(spill)
    sources = [Path(__file__), args.population, args.cost_model, args.pilot_geometry, molecule_path]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.threads, len(sources))) as pool:
        checksums = list(pool.map(sha256, sources))
    makespan = max((task["predicted_end_hours"] for task in tasks), default=0.0)
    total_core_hours = sum(task["predicted_core_hours"] for task in tasks)
    save(args.out / "tasks.json", {"schema": "WP5_TASK_PLAN_V1", "configuration_adopted": True,
        "tasks": sorted(tasks, key=lambda t: t["priority_rank"]), "authorized_node_slots": SLOTS})
    save(args.out / "manifest.json", {
        "status": "WP5_PACKING_CLOSED", "job_id": os.environ["SLURM_JOB_ID"],
        "seconds": time.monotonic() - started, "duckdb_threads": args.threads,
        "duckdb_memory_limit_gb": args.memory_gb, "local_spill_directory_removed": str(spill),
        "formal_records": expected_records, "formal_molecules": expected_molecules,
        "task_count": len(tasks), "assigned_molecules": len(assignments),
        "oversized_molecules": 0, "new_QM_calls": 0, "original_data_written": False, "lmdb_1_created": False,
        "recipe": {"POLAR": "drop", "ESP": "drop", "Hessian": "none", "CD_scope": "all",
                   "xTB_nonhessian_scope": "all", "native_calls_per_record": 12},
        "model": {"source_recipe": "C1/C2 v3 no-POLAR/no-ESP/no-Hessian all-conformer",
                  "old_allocated_to_service_factor": factor, "p90_residual_inflation": inflation,
                  "mean_service_seconds_per_record_by_stratum": means,
                  "native_max_total_atoms_by_stratum": maxima,
                  "size_extrapolation": "max(1,(molecule_max_total_atoms/native_stratum_max_total_atoms)^3)",
                  "time_prediction_is_empirical_model_not_a_guaranteed_completion_bound": True},
        "packing": {"lanes": 24, "ordinary_target_hours": 40, "large_target_hours": 20,
                    "large_threshold": "molecule_max_heavy_atoms>75", "classes_never_mixed": True,
                    "file_groups_never_mixed": True, "whole_molecule_one_task": True,
                    "resplit_threshold_hours": 46, "sbatch_hours": 48,
                    "node_slots": SLOTS, "total_slots": sum(SLOTS.values()),
                    "predicted_makespan_29_slots_hours": makespan,
                    "total_planned_core_hours": total_core_hours,
                    "ideal696CPU_hours": total_core_hours/696,
                    "task_wall_hours": stats([t["predicted_wall_hours"] for t in tasks]),
                    "task_molecules": stats([t["molecules"] for t in tasks]),
                    "node_availability": "Ideal simultaneous slot availability; node15/16 may queue. No node replacement."},
        "counts_by_file_and_class": [
            {"file_group": group, "large_class": large, "molecules": len(mols),
             "records": sum(r["records"] for r in mols),
             "tasks": sum(t["file_group"]==group and t["large_class"]==large for t in tasks)}
            for (group,large),mols in sorted(cohorts.items())],
        "inputs": [{"path": str(path), "bytes": path.stat().st_size, "sha256": digest}
                   for path,digest in zip(sources,checksums)],
        "outputs": {"tasks": str(args.out/"tasks.json"),
                    "molecule_assignments": str(args.out/"molecule_assignments.parquet"),
                    "record_partitions": str(args.out/"record_partitions")},
    })
    print(json.dumps({"status": "WP5_PACKING_CLOSED", "tasks": len(tasks),
                      "molecules": len(assignments), "records": expected_records,
                      "planned_makespan_hours": makespan}, ensure_ascii=False))

if __name__ == "__main__":
    main()
