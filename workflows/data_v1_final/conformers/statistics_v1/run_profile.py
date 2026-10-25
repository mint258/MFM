"""Compute bounded D7 geometry statistics; never generates or optimizes geometry."""
from __future__ import annotations
import argparse
from collections import Counter
import concurrent.futures as cf
import gzip
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import time

from profile_common import IO, SELECTION, load_config, runtime

CONFIG = SCIENCE = None


def worker_init(config_path):
    global CONFIG, SCIENCE
    CONFIG = load_config(config_path)
    SCIENCE = IO.load_science(CONFIG)
    SCIENCE.worker_init()
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    from rdkit import rdBase
    if IO.version_tuple(rdBase.rdkitVersion) != (2025, 9, 5):
        raise ValueError("D7_REQUIRES_ORIGINAL_RDKIT_VERSION")


def unique_representatives(rows, fixed_random, distance, threshold=0.5):
    by_id = {row["conformer_id"]: row for row in rows}
    if len(by_id) != len(rows) or set(fixed_random) != set(by_id) or len(fixed_random) != len(rows):
        raise ValueError("D7_CONFORMER_IDS_OR_ORDER_NOT_A_PERMUTATION")
    selected = []
    for key in fixed_random:
        distances = [distance(by_id[key], by_id[old]) for old in selected]
        if any(not math.isfinite(value) for value in distances):
            raise ValueError("D7_NONFINITE_RMSD")
        if all(value >= threshold for value in distances):
            selected.append(key)
    return selected


def geometry_orders(rows, distance, molecule_id, source):
    random_order = sorted((row["conformer_id"] for row in rows),
        key=lambda key: (SELECTION.stable_key(20261025, molecule_id, source, key), str(key)))
    if all(row["energy"] is not None for row in rows):
        return {**SELECTION.conformer_orders(rows, distance, molecule_id, source, 20261025), "status": "COMPLETE"}
    return {"fixed_random": random_order, "energy": None, "diversity": None,
            "status": "ENERGY_AND_MIN_ENERGY_DIVERSITY_UNAVAILABLE_CANONICAL_HOF_MISSING"}


def process_molecule(task):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    started, mid = time.monotonic(), task["meta"]["molecule_id"]
    records, sprime = task["records"], sorted(task["sprime"], key=lambda row: row["sprime_conf_idx"])
    if len(records) != task["meta"]["S_conformers"] or len(sprime) != task["meta"]["Sprime_conformers"]:
        raise ValueError("D7_COMPLETE_MOLECULE_COUNT_MISMATCH")
    if len({row["record_id"] for row in records}) != len(records) or len({row["sprime_conf_idx"] for row in sprime}) != len(sprime):
        raise ValueError("D7_DUPLICATE_CONFORMER_ID")
    anchors = {row["source_record_id"] for row in sprime}
    by_record = {row["record_id"]: row for row in records}
    if len(anchors) != 1 or not anchors <= set(by_record):
        raise ValueError("D7_SPRIME_SOURCE_ANCHOR_MAPPING_MISMATCH")
    raw = {rid: SCIENCE.read(row) for rid, row in by_record.items()}
    anchor = raw[next(iter(anchors))]
    mol, numbers, _ = SCIENCE.graph(anchor)
    graph_signature = SCIENCE.ordered_graph(mol)
    graph_sha = hashlib.sha256(json.dumps(graph_signature, separators=(",",":")).encode()).hexdigest()
    atom_sha = hashlib.sha256(numbers.astype("<i8").tobytes()).hexdigest()
    stereo_source, stereo_signature = SCIENCE.fix_stereo(mol, str(SCIENCE.field(anchor, "smiles")))
    pm7, uff = [], []
    for rid in sorted(raw):
        other, z, coordinates = SCIENCE.graph(raw[rid])
        if not np.array_equal(numbers, z) or SCIENCE.ordered_graph(other) != graph_signature:
            raise ValueError("D7_SOURCE_GRAPH_OR_ATOM_SEQUENCE_MISMATCH")
        hof = task["hof"][rid]
        pm7.append({"conformer_id": rid, "coordinates": coordinates.tolist(),
                    "energy": hof["value_kcal_mol"] if hof["valid"] else None,
                    "geometry_sha256": IO.geometry_sha(numbers, coordinates)})
    for row in sprime:
        coordinates = np.asarray(row["coordinates"], dtype=np.float64)
        geometry_sha = IO.geometry_sha(numbers, coordinates)
        if row["status"] != "SUCCESS" or row["converged"] is not True or row["atom_order_sha256"] != atom_sha or row["stereo_signature"] != stereo_signature:
            raise ValueError("D7_ACCEPTED_SPRIME_STATUS_ATOMS_OR_STEREO_MISMATCH")
        conformer = Chem.Conformer(len(numbers))
        for index, xyz in enumerate(coordinates):
            conformer.SetAtomPosition(index, xyz.tolist())
        conformer.Set3D(True)
        cid = mol.AddConformer(conformer, assignId=True)
        valid_stereo = SCIENCE.check_geometry_stereo(mol, cid)
        mol.RemoveConformer(cid)
        if not valid_stereo:
            raise ValueError("D7_SPRIME_GEOMETRIC_STEREO_CHECK_FAILED")
        energy = float(row["uff_energy_kcal_mol"])
        if not np.isfinite(energy):
            raise ValueError("D7_SPRIME_NONFINITE_ENERGY")
        uff.append({"conformer_id": int(row["sprime_conf_idx"]), "coordinates": coordinates.tolist(),
                    "energy": energy, "geometry_sha256": geometry_sha})
    distance = lambda left, right: SCIENCE.rmsd(mol, left["coordinates"], right["coordinates"])
    orders = {"pm7": geometry_orders(pm7, distance, mid, "pm7"),
              "uff_sprime": geometry_orders(uff, distance, mid, "uff_sprime")}
    unique = {"pm7": unique_representatives(pm7, orders["pm7"]["fixed_random"], distance),
              "uff_sprime": unique_representatives(uff, orders["uff_sprime"]["fixed_random"], distance)}
    cross = [[distance(left, right) for right in uff] for left in pm7]
    hof_values = [row["energy"] for row in pm7 if row["energy"] is not None]
    return {"status": "D7_MOLECULE_PROFILE_COMPLETE", "molecule_id": mid,
            "source_role": task["meta"]["split_role"], "population_scope": "ORIGINAL_SOURCE_PRECOMMON_PROFILE",
            "pm7_count": len(pm7), "uff_sprime_count": len(uff),
            "pm7_unique": len(unique["pm7"]), "uff_sprime_unique": len(unique["uff_sprime"]),
            "pm7_duplicate_conformer_fraction": 1 - len(unique["pm7"]) / len(pm7),
            "heavy_atoms": int(np.count_nonzero(numbers != 1)),
            "rotatable_bonds": int(rdMolDescriptors.CalcNumRotatableBonds(Chem.RemoveHs(mol))),
            "rings": int(mol.GetRingInfo().NumRings()),
            "hof_valid_count": len(hof_values), "hof_total_count": len(pm7),
            "hof_range_kcal_mol": max(hof_values) - min(hof_values) if hof_values else None,
            "hof_range_complete": len(hof_values) == len(pm7), "hof_by_record": task["hof"],
            "cross_rmsd_A": cross, "cross_pm7_ids": [row["conformer_id"] for row in pm7],
            "cross_uff_sprime_ids": [row["conformer_id"] for row in uff],
            "orders": orders, "unique_representatives": unique,
            "unique_greedy_order": "fixed_random_same_algorithm_both_sources",
            "atom_order_sha256": atom_sha, "graph_sha256": graph_sha,
            "stereo_source": stereo_source, "stereo_signature": stereo_signature,
            "geometry_hashes": {source: {str(row["conformer_id"]): row["geometry_sha256"] for row in rows}
                                for source, rows in (("pm7",pm7),("uff_sprime",uff))},
            "elapsed_seconds": time.monotonic() - started,
            "geometry_generation_calls": 0, "original_data_modified": False}


def aggregate(results, expected):
    import math
    import numpy as np
    from scipy.stats import spearmanr
    report = {"status": "BOUNDED_D7_PROFILE_ONLY", "expected_molecules": expected,
              "completed_molecules": len(results), "population_estimate": False,
              "unique_counts": {}, "correlations": {}, "energy_units": "kcal/mol"}
    for source in ("pm7","uff_sprime"):
        values = [row[source + "_unique"] for row in results]
        report["unique_counts"][source] = {"histogram": dict(Counter(map(str, values))),
            "fractions_ge_2_5_10": {str(k): sum(n >= k for n in values)/len(values) if values else None for k in (2,5,10)},
            "denominator_molecules": len(values),
            "duplicate_conformer_fraction": 1 - sum(values)/sum(row[source + "_count"] for row in results) if results else None}
        for feature in ("heavy_atoms","rotatable_bonds","rings"):
            x = [row[feature] for row in results]
            rho = None
            if len(set(x)) > 1 and len(set(values)) > 1:
                observed = float(spearmanr(x, values).statistic)
                rho = observed if math.isfinite(observed) else None
            report["correlations"][source + "_unique_vs_" + feature] = {"spearman_rho": rho, "n": len(values), "undefined_if_constant": rho is None}
    cross = [value for row in results for vector in row["cross_rmsd_A"] for value in vector]
    quantiles = (0,25,50,75,90,95,99,100)
    report["cross_rmsd_A_quantiles"] = {str(p): float(np.percentile(cross,p,method="linear")) for p in quantiles} if cross else {}
    report["pm7_molecules_with_duplicates_fraction"] = sum(row["pm7_unique"] < row["pm7_count"] for row in results)/len(results) if results else None
    ranges = [row["hof_range_kcal_mol"] for row in results if row["hof_range_complete"]]
    report["complete_canonical_hof_range_quantiles_kcal_mol"] = {str(p): float(np.percentile(ranges,p,method="linear")) for p in quantiles} if ranges else {}
    report["canonical_hof_complete_molecules"] = len(ranges)
    report["hof_missing_reason_counts"] = dict(Counter(value["reason"] for row in results for value in row["hof_by_record"].values() if not value["valid"]))
    report["hof_convergence_null_review_records"] = sum(value["convergence_null_review"] for row in results for value in row["hof_by_record"].values())
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--prepared", type=Path, required=True)
    ap.add_argument("--root-preflight", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    config = load_config(args.config)
    environment = runtime(config, args.root_preflight, args.config)
    prepared = json.loads((args.prepared/"prepared.json").read_text())
    if prepared["status"] != "D7_PROFILE_PREPARED_NO_GEOMETRY_COMPUTED" or prepared["config"] != IO.reference(args.config):
        raise ValueError("D7_PREPARED_CONFIG_BINDING_MISMATCH")
    for pin in prepared["outputs"]:
        IO.require_pin(pin)
    tasks = [json.loads(line) for line in (args.prepared/"tasks.jsonl").read_text().splitlines()]
    if len(tasks) != config["molecules"] or len({task["meta"]["molecule_id"] for task in tasks}) != len(tasks):
        raise ValueError("D7_COMPLETE_TASK_COUNT_MISMATCH")
    out = IO.new_output_directory(args.output, config)
    (out/"molecules").mkdir()
    results, errors, references = [], [], []
    started = time.monotonic()
    with cf.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context("spawn"), initializer=worker_init, initargs=(str(args.config),)) as pool:
        futures = {pool.submit(process_molecule, task): task["meta"]["molecule_id"] for task in tasks}
        for future in cf.as_completed(futures):
            mid = futures[future]
            try:
                result = future.result()
                if result["molecule_id"] != mid:
                    raise ValueError("D7_WORKER_ID_MISMATCH")
                data = gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False).encode(),mtime=0)
                path = out/"molecules"/(hashlib.sha256(mid.encode()).hexdigest()+".json.gz")
                IO.prewrite_guard(path,len(data),reserve_bytes=2<<20)
                with path.open("xb") as stream:
                    stream.write(data);stream.flush();os.fsync(stream.fileno())
                references.append({"molecule_id":mid, **IO.reference(path)})
                results.append(result)
            except Exception as exc:
                errors.append({"molecule_id":mid,"error_type":type(exc).__name__,"error":str(exc)[:3000]})
    IO.write_json_new(out/"profile_statistics.json",aggregate(results,len(tasks)))
    IO.write_json_new(out/"errors.json",errors)
    IO.write_json_new(out/"molecule_manifest.json",sorted(references,key=lambda row:row["molecule_id"]))
    report = {"status":"D7_PROFILE_INCOMPLETE" if errors else "D7_PROFILE_COMPLETED_NOT_FULL_POPULATION",
        "runtime":environment,"config":IO.reference(args.config),"prepared":IO.reference(args.prepared/"prepared.json"),
        "root_intent":IO.reference(args.root_preflight),"elapsed_seconds":time.monotonic()-started,
        "expected_molecules":len(tasks),"completed_molecules":len(results),"error_molecules":len(errors),
        "outputs":[IO.reference(out/name) for name in ("profile_statistics.json","errors.json","molecule_manifest.json")],
        "order_seed":20261025,"rmsd_A":0.5,"rmsd_mapping":"fixed source heavy-atom map; proper Kabsch; no symmetry permutation",
        "common_population_frozen":False,"population_estimate":False,"original_data_modified":False,
        "geometry_generation_or_optimization_calls":0,"new_QM_calls":0}
    IO.write_json_new(out/"receipt.json",report)
    print(json.dumps({"status":report["status"],"molecules":len(results),"output":str(out)}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
