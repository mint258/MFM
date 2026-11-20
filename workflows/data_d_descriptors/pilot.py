"""D stage 0: freeze a graph-stratified TRAIN panel, then measure L1/L2 once."""
import argparse
import collections
import concurrent.futures
import importlib.metadata
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import sqlite3
import time


def storage_guard(path, peak_bytes=4294967296):
    """Guard actual output FS and actual UID quota before every output part."""
    from .storage import guard
    guard(path, peak_bytes)


def publish(path, value):
    storage_guard(Path(path).parent)
    temporary = Path(str(path) + ".partial")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def original_smiles(pointer):
    from workflows.data_v1_final.export.v31_stream_v1.physical import native, field
    raw = native(pointer)
    value = field(raw, "smiles")
    if not value:
        raise ValueError("Original D20 stored SMILES unavailable")
    return str(value)


def select_panel(config, output):
    import numpy as np
    import pyarrow.dataset as ds
    from rdkit import Chem
    panel_path = output / "panel.json"
    if panel_path.exists():
        return json.loads(panel_path.read_text())["molecules"]
    corpus = json.loads(Path(config["corpus"]).read_text())
    eligible = np.load(corpus["train_indices"])
    rng = np.random.default_rng(config["seed"])
    candidates = rng.choice(eligible, min(config["candidate_molecules"], len(eligible)), replace=False)
    manifest = json.loads((Path(corpus["source_root"]) / "manifest.json").read_text())
    idmap = Path(manifest["split_roots"]["TRAIN"]) / "id_map.parquet"
    query = (ds.field("record_kind") == "M") & ds.field("molecule_index").isin(candidates.tolist())
    rows = ds.dataset(idmap, format="parquet").to_table(
        columns=["molecule_index", "molecule_id"], filter=query, use_threads=False).to_pylist()
    by_index = {row["molecule_index"]: row for row in rows}
    connection = sqlite3.connect("file:" + config["geometry_index"] + "?mode=ro", uri=True)
    bins = collections.defaultdict(list)
    rejected = collections.Counter()
    for ordinal, index in enumerate(candidates):
        row = by_index.get(int(index))
        if row is None:
            raise ValueError("TRAIN molecule ID alignment missing")
        source = connection.execute("SELECT pointer FROM geometries WHERE mid=? AND src='pm7' LIMIT 1", (row["molecule_id"],)).fetchone()
        smiles, source_error = None, None
        try:
            if source is None:
                raise ValueError("Original D20 source pointer missing")
            smiles = original_smiles(json.loads(source[0]))
        except (ValueError, KeyError) as error:
            source_error = str(error)
        molecule = Chem.MolFromSmiles(smiles) if smiles else None
        if molecule is None:
            reason = source_error or "original_smiles_parse_failure"
            rejected[reason] += 1
            key = ("UNKNOWN", "", 0, 0)
            bins[key].append({**row, "smiles": None, "source_error": reason, "stratum": list(key)})
            continue
        heavy = molecule.GetNumHeavyAtoms()
        size = "0-10" if heavy <= 10 else "11-20" if heavy <= 20 else "21-40" if heavy <= 40 else "41+"
        elements = ",".join(map(str, sorted({atom.GetAtomicNum() for atom in molecule.GetAtoms()})))
        rings = molecule.GetRingInfo().NumRings()
        branch = sum(atom.GetDegree() > 2 for atom in molecule.GetAtoms())
        key = (size, elements, min(rings, 3), min(branch, 3))
        bins[key].append({**row, "smiles": smiles, "stratum": list(key)})
        if ordinal % 1000 == 0:
            print(json.dumps({"stage": "graph_panel", "candidates_read": ordinal + 1}), flush=True)
    connection.close()
    selected = []
    # Equal round-robin coverage of graph-only strata; no descriptor values seen.
    while len(selected) < config["panel_molecules"]:
        added = False
        for key in sorted(bins):
            if bins[key] and len(selected) < config["panel_molecules"]:
                selected.append(bins[key].pop())
                added = True
        if not added:
            raise ValueError("Insufficient valid source graphs for frozen panel")
    from .existing import ExistingD20
    canonical = ExistingD20(corpus["source_root"])
    try:
        for row in selected:
            row.update(canonical.read("TRAIN", row["molecule_index"]))
    finally:
        canonical.close()
    publish(panel_path, {"seed": config["seed"], "candidate_count": len(candidates),
        "eligible_train_molecules": len(eligible), "selection_rejections": dict(rejected),
        "selection": "round-robin heavy-size/element-set/rings/branching strata, no descriptor values",
        "molecules": selected})
    return selected


CALCULATOR = None
FIELDS = None
LIBRARY = None


def initialize(library):
    global CALCULATOR, FIELDS, LIBRARY
    LIBRARY = library
    if library == "L1":
        from rdkit.Chem import Descriptors
        CALCULATOR = sorted(Descriptors._descList, key=lambda item: item[0])
        FIELDS = [name for name, _ in CALCULATOR]
    else:
        from mordred import Calculator, descriptors
        CALCULATOR = Calculator(descriptors, ignore_3D=True)
        FIELDS = [str(descriptor) for descriptor in CALCULATOR.descriptors]
        if len(FIELDS) != 1613:
            raise ValueError("Mordred 2D field count does not match registered CheMeleon 1613")


def descriptor_input(row):
    if "existing_D20" in row:
        return {"smiles": row["smiles"], "existing_D20": row["existing_D20"]}
    return None if row.get("source_error") else row["smiles"]


def one(smiles):
    import numpy as np
    from rdkit import Chem
    begin, cpu_begin = time.perf_counter(), time.process_time()
    existing = smiles.get("existing_D20", {}) if isinstance(smiles, dict) else {}
    smiles = smiles.get("smiles") if isinstance(smiles, dict) else smiles
    molecule = Chem.MolFromSmiles(smiles) if smiles else None
    if molecule is None and LIBRARY != "L1":
        count = len(FIELDS)
        return ([math.nan] * count, [False] * count, [False] * count,
            ["SOURCE_GRAPH_UNAVAILABLE"] * count, time.process_time() - cpu_begin,
            time.perf_counter() - begin)
    values, valid, nonfinite, errors = [], [], [], []
    if LIBRARY == "L1":
        raw = []
        for name, function in CALCULATOR:
            if name in existing:
                raw.append(existing[name])
                continue
            if molecule is None:
                raw.append(ValueError("SOURCE_GRAPH_UNAVAILABLE"))
                continue
            try:
                raw.append(function(molecule))
            except Exception as error:
                raw.append(error)
    else:
        raw = list(CALCULATOR(molecule))
    for item in raw:
        if isinstance(item, OverflowError):
            values.append(math.nan)
            valid.append(False)
            nonfinite.append(True)
            errors.append("NUMERIC_OVERFLOW:" + str(item)[:200])
            continue
        try:
            number = float(item)
            # Storage/statistics are F64, but the unchanged training framework
            # uses FP32 raw heads/transport. This is an actual IEEE overflow
            # event, not a fitted outlier threshold; retain the raw F64 value.
            is_finite = math.isfinite(number) and abs(number) <= np.finfo(np.float32).max
            values.append(number)
            valid.append(is_finite)
            nonfinite.append(not is_finite)
            errors.append(None if is_finite else "NONFINITE_OR_FP32_TRANSPORT_OVERFLOW")
        except OverflowError as error:
            values.append(math.nan)
            valid.append(False)
            nonfinite.append(True)
            errors.append("NUMERIC_OVERFLOW:" + str(error)[:200])
        except (TypeError, ValueError):
            values.append(math.nan)
            valid.append(False)
            nonfinite.append(False)
            errors.append(str(item)[:256])
    return values, valid, nonfinite, errors, time.process_time() - cpu_begin, time.perf_counter() - begin


def measure(config, panel, output, library, workers):
    import numpy as np
    destination = output / (library + "_cost.json")
    if destination.exists():
        print(json.dumps({"library": library, "status": "CLOSED_REUSED"}), flush=True)
        return
    initialize(library)
    fields = list(FIELDS)
    publish(output / (library + "_fields.json"), {"library": library, "ordered_names": fields,
        "rdkit_version": importlib.metadata.version("rdkit"),
        "mordredcommunity_version": importlib.metadata.version("mordredcommunity"),
        "input_graph": "unchanged original D20 Chem.MolFromSmiles(stored_smiles)",
        "L2_definition_source": "https://github.com/JacksonBurns/how-to-train-your-chemeleon/blob/main/features/_mordred.py" if library == "L2" else None,
        "L2_correspondence": [{"name": name, "calculator_index": i, "chemeleon_calculator_index": i}
            for i, name in enumerate(fields)] if library == "L2" else None,
        "L2_correspondence_basis": "Same Calculator(descriptors, ignore_3D=True) ordered definition as author code; actual installed version recorded; input handling remains D20 per taskbook" if library == "L2" else None})
    start = time.perf_counter()
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"), initializer=initialize, initargs=(library,)) as pool:
        for result in pool.map(one, [descriptor_input(row) for row in panel], chunksize=4):
            results.append(result)
            if len(results) % 250 == 0:
                print(json.dumps({"stage": "cost", "library": library, "molecules": len(results)}), flush=True)
    values = np.asarray([row[0] for row in results], dtype=np.float64)
    valid = np.asarray([row[1] for row in results], dtype=bool)
    bad_numeric = np.asarray([row[2] for row in results], dtype=bool)
    cpu = np.asarray([row[4] for row in results])
    elapsed = np.asarray([row[5] for row in results])
    storage_guard(output)
    numeric = output / (library + "_pilot.npz")
    np.savez_compressed(numeric, values=values, valid=valid, bad_numeric=bad_numeric,
        molecule_index=np.asarray([row["molecule_index"] for row in panel]), cpu_seconds=cpu, elapsed_seconds=elapsed)
    error_path = output / (library + "_missing.json")
    publish(error_path, [{"molecule_index": panel[i]["molecule_index"],
        "fields": {fields[j]: error for j, error in enumerate(row[3]) if error is not None}}
        for i, row in enumerate(results) if any(error is not None for error in row[3])])
    population = json.loads((output / "panel.json").read_text())["eligible_train_molecules"]
    publish(destination, {"status": "PILOT_COST_COMPLETE_NOT_DELIVERY", "library": library,
        "node": platform.node(), "job_id": os.environ["SLURM_JOB_ID"], "molecules": len(panel),
        "fields": len(fields), "cpu_core_seconds": float(cpu.sum()),
        "canonical_D20_values_reused": library == "L1",
        "mean_cpu_core_seconds_per_molecule": float(cpu.mean()),
        "elapsed_p99_seconds": float(np.quantile(elapsed, .99)),
        "wall_seconds": time.perf_counter() - start,
        "molecules_with_any_missing_fraction": float((~valid.all(axis=1)).mean()),
        "mean_valid_fields": float(valid.sum(axis=1).mean()),
        "pilot_fields_at_least_95_percent_valid": int((valid.mean(axis=0) >= .95).sum()),
        "train_population": population, "train_cpu_core_hours_extrapolated": float(cpu.mean() * population / 3600),
        "numeric_output_bytes": numeric.stat().st_size, "missing_reason_bytes": error_path.stat().st_size,
        "field_filtering_or_normalization_fitted": False})


def main():
    print(json.dumps({"stage": "starting", "node": platform.node(), "job": os.environ.get("SLURM_JOB_ID")}), flush=True)
    number = int(platform.node().rsplit("-", 1)[-1])
    if not os.environ.get("SLURM_JOB_ID") or not 8 <= number <= 19:
        raise RuntimeError("Stage 0 requires an allocated CPU node 8-19")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    output = Path(config["output"])
    output.mkdir(parents=True, exist_ok=True)
    storage_guard(output)
    panel = select_panel(config, output)
    for library in ("L1", "L2"):
        measure(config, panel, output, library, args.workers)


if __name__ == "__main__":
    main()
