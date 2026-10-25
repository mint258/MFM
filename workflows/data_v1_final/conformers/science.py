"""New fill adapter around pinned, unchanged S-prime graph/stereo/RMSD code."""
from __future__ import annotations

import hashlib
import time

from common import geometry_sha, load_config, load_science, version_tuple
from selection import conformer_orders, select_fill

CONFIG = None
SCIENCE = None


def worker_init(config_path):
    global CONFIG, SCIENCE
    CONFIG = load_config(config_path)
    SCIENCE = load_science(CONFIG)
    SCIENCE.worker_init()
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    from rdkit import rdBase
    if version_tuple(rdBase.rdkitVersion) != version_tuple(CONFIG["rdkit_version"]):
        raise RuntimeError("RDKIT_VERSION_MISMATCH")


def seed_for(molecule_id, retry):
    prefix = "sprime-ETKDGv3-v1:" if not retry else "sprime-ETKDGv3-v1-retry1:"
    seed = int.from_bytes(hashlib.sha256((prefix + molecule_id).encode()).digest()[:4], "big")
    return max(seed & 0x7fffffff, 1)


def _add_conformer(mol, coordinates):
    from rdkit import Chem
    conf = Chem.Conformer(mol.GetNumAtoms())
    for index, xyz in enumerate(coordinates):
        conf.SetAtomPosition(index, list(map(float, xyz)))
    conf.Set3D(True)
    return mol.AddConformer(conf, assignId=True)


def process_task(task):
    import numpy as np
    from rdkit.Chem import AllChem, rdtrajectory  # noqa: F401; registers trajectory bindings
    started = time.monotonic()
    meta, pointers, previous = task["meta"], task["records"], task["existing_conformers"]
    mid = meta["molecule_id"]
    target = int(meta["expected_conformers"])
    retry = meta["cohort"] == "retry_once"
    seed = seed_for(mid, retry)
    summary = {"molecule_id": mid, "prior_split_role": meta["split_role"],
               "prior_status": meta["Sprime_status"], "cohort": meta["cohort"],
               "file_group": int(meta["file_group"]), "expected_conformers": target,
               "previous_usable_conformers": len(previous), "retry_count": int(retry),
               "seed": seed, "status": "UNPROCESSED", "error": None,
               "candidate_requested": 0, "candidate_embedded": 0,
               "candidate_converged": 0, "candidate_stereo_rejected": 0,
               "candidate_nonconverged": 0, "candidate_nonfinite": 0, "below_dedup_threshold": 0,
               "elapsed_seconds": 0.0, "original_data_modified": False}
    output, archive, pm7 = [], [], []
    try:
        if target != len(pointers) or target < 1:
            raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:conformer_count")
        if meta["Sprime_status"] == "UFF_UNSUPPORTED":
            summary["status"] = "EXCLUDED_UFF_UNSUPPORTED"
            return {"summary": summary, "conformers": [], "pm7": [], "orders": {},
                    "audit_candidates": []}
        raw = [SCIENCE.read(row) for row in pointers]
        energies = [float(SCIENCE.plain(SCIENCE.field(item, "energy")).reshape(-1)[0])
                    if SCIENCE.field(item, "energy") is not None else float("inf") for item in raw]
        if not any(np.isfinite(energies)):
            raise ValueError("PM7_MINIMUM_ENERGY_MISSING")
        lowest = min(range(target), key=lambda index: (energies[index], pointers[index]["record_id"]))
        mol, numbers, _ = SCIENCE.graph(raw[lowest])
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors
        summary["heavy_atoms"] = int(np.count_nonzero(numbers != 1))
        summary["rotatable_bonds"] = int(rdMolDescriptors.CalcNumRotatableBonds(Chem.RemoveHs(mol)))
        summary["rings"] = int(mol.GetRingInfo().NumRings())
        source_record = pointers[lowest]["record_id"]
        atom_sha = hashlib.sha256(numbers.astype("<i8").tobytes()).hexdigest()
        summary.update(source_record_id=source_record, atom_order_sha256=atom_sha)
        for index, item in enumerate(raw):
            other, other_numbers, xyz = SCIENCE.graph(item)
            if not np.array_equal(numbers, other_numbers) or SCIENCE.ordered_graph(other) != SCIENCE.ordered_graph(mol):
                raise ValueError("SOURCE_CONFORMER_GRAPH_OR_ATOM_ORDER_MISMATCH")
            pm7.append({"record_id": pointers[index]["record_id"], "conformer_id": pointers[index]["record_id"],
                        "coordinates": xyz.tolist(), "energy": energies[index] if np.isfinite(energies[index]) else None,
                        "geometry_sha256": geometry_sha(numbers, xyz)})
        stereo_source, signature = SCIENCE.fix_stereo(mol, str(SCIENCE.field(raw[lowest], "smiles")))
        summary.update(stereo_source=stereo_source, stereo_signature=signature)
        if not AllChem.UFFHasAllMoleculeParams(mol):
            raise ValueError("UFF_UNSUPPORTED")
        existing = []
        for row in sorted(previous, key=lambda row: int(row["sprime_conf_idx"])):
            xyz = np.asarray(row["coordinates"], dtype=np.float64)
            geometry_sha(numbers, xyz)
            if row["atom_order_sha256"] != atom_sha or row["source_record_id"] != source_record:
                raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:existing_atom_or_anchor")
            if row["stereo_signature"] != signature or row["status"] != "SUCCESS" or row["converged"] is not True:
                raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:existing_status_or_stereo")
            cid = _add_conformer(mol, xyz)
            valid_stereo = SCIENCE.check_geometry_stereo(mol, cid)
            mol.RemoveConformer(cid)
            if not valid_stereo:
                raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:existing_geometry_stereo")
            energy = float(row["uff_energy_kcal_mol"])
            if not np.isfinite(energy):
                raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:existing_energy")
            existing.append({"candidate_key": f"existing:{int(row['sprime_conf_idx']):06d}",
                             "coordinates": xyz.tolist(), "energy": energy,
                             "origin": "accepted_sprime", "original_sprime_conf_idx": int(row["sprime_conf_idx"]),
                             "seed": int(row["seed"]), "iterations": int(row["iterations"]),
                             "candidate_id": None})
        candidates = []
        if len(existing) < target:
            requested = min(CONFIG["candidate_multiplier"] * target, CONFIG["max_candidates"])
            summary["candidate_requested"] = requested
            mol.RemoveAllConformers()
            params = AllChem.ETKDGv3()
            params.randomSeed, params.numThreads = seed, 1
            params.enforceChirality, params.pruneRmsThresh = True, -1.0
            params.maxIterations = CONFIG["retry_embedding_max_iterations"] if retry else 200
            params.useRandomCoords = retry
            try:
                ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=requested, params=params))
            except (RuntimeError, ValueError) as exc:
                ids = []
                summary["embedding_error"] = repr(exc)[:1000]
            summary["embedding_random_coords"] = bool(params.useRandomCoords)
            # Ordinary shortage retains the old protocol's random-coordinate fallback.
            # Technical/partial records have exactly one new retry call, with a new seed.
            if not ids and not retry:
                params.useRandomCoords = True
                ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=requested, params=params))
                summary["embedding_random_coords"] = True
            if not ids:
                raise ValueError("EMBED_FAILED")
            summary["candidate_embedded"] = len(ids)
            for cid in ids:
                forcefield = AllChem.UFFGetMoleculeForceField(mol, confId=cid)
                code, trajectory = forcefield.MinimizeTrajectory(snapshotFreq=1, maxIts=2000,
                                                               energyTol=1e-6, forceTol=1e-4)
                xyz = np.asarray(mol.GetConformer(cid).GetPositions(), dtype=np.float64)
                energy = float(forcefield.CalcEnergy())
                finite = bool(np.isfinite(xyz).all() and np.isfinite(energy))
                stereo_ok = finite and SCIENCE.check_geometry_stereo(mol, cid)
                def raw_number(value):
                    value = float(value)
                    if np.isfinite(value):
                        return value
                    return "NaN" if np.isnan(value) else "+Infinity" if value > 0 else "-Infinity"
                candidate = {"candidate_key": f"generated:{cid:06d}", "candidate_id": int(cid),
                             "coordinates": xyz.tolist() if finite else [[raw_number(value) for value in vector] for vector in xyz],
                             "energy": raw_number(energy), "seed": seed,
                             "origin": "data_v1_fill_retry1" if retry else "data_v1_fill_10N",
                             "original_sprime_conf_idx": None, "iterations": len(trajectory),
                             "optimizer_code": int(code), "stereo_valid": bool(stereo_ok), "finite": finite}
                archive.append(candidate)
                if not finite:
                    summary["candidate_nonfinite"] += 1
                    continue
                if not stereo_ok:
                    summary["candidate_stereo_rejected"] += 1
                    continue
                if code != 0:
                    summary["candidate_nonconverged"] += 1
                    continue
                candidates.append(candidate)
            summary["candidate_converged"] = len(candidates)
        distance = lambda left, right: SCIENCE.rmsd(mol, left["coordinates"], right["coordinates"])
        selected = select_fill(existing, candidates, target, distance, 0.5)
        for index, row in enumerate(selected):
            rmsds = [SCIENCE.rmsd(mol, row["coordinates"], item["coordinates"]) for item in pm7]
            nearest = min(range(len(rmsds)), key=lambda i: (rmsds[i], pm7[i]["record_id"]))
            output.append({"molecule_id": mid, "sprime_conf_idx": index,
                           "geometry_source": "uff_sprime", "atomic_numbers": numbers.tolist(),
                           "coordinates": row["coordinates"], "uff_energy_kcal_mol": row["energy"],
                           "status": "SUCCESS", "converged": True, "seed": row["seed"],
                           "iterations": row["iterations"], "source_record_id": source_record,
                           "atom_order_sha256": atom_sha, "stereo_source": stereo_source,
                           "stereo_signature": signature, "origin": row["origin"],
                           "original_sprime_conf_idx": row["original_sprime_conf_idx"],
                           "candidate_id": row["candidate_id"],
                           "below_dedup_threshold": row["below_dedup_threshold"],
                           "min_rmsd_to_previously_selected_A": row["min_rmsd_to_previously_selected_A"],
                           "nearest_pm7_record_id": pm7[nearest]["record_id"],
                           "nearest_pm7_rmsd_A": rmsds[nearest], "pm7_rmsds_A": rmsds,
                           "geometry_sha256": geometry_sha(numbers, row["coordinates"])})
        summary["status"] = "SUCCESS" if len(output) == target else "INSUFFICIENT_CONVERGED_CANDIDATES"
        summary["usable_conformers"] = len(output)
        summary["below_dedup_threshold"] = sum(row["below_dedup_threshold"] for row in output)
        sp_order_rows = [dict(row, conformer_id=row["sprime_conf_idx"], energy=row["uff_energy_kcal_mol"]) for row in output]
        orders = {"uff_sprime": conformer_orders(sp_order_rows, distance, mid, "uff_sprime", CONFIG["order_seed"])}
        if all(row["energy"] is not None for row in pm7):
            orders["pm7_native_anchor_diagnostic"] = conformer_orders(pm7, distance, mid, "pm7", CONFIG["order_seed"])
        else:
            orders["pm7_native_anchor_diagnostic"] = {"status": "MISSING_NATIVE_ENERGY"}
        summary["audit_sample"] = int(hashlib.sha256(("data-v1-audit:" + mid).encode()).hexdigest(), 16) % 100 == 0
    except Exception as exc:
        if "ACTUAL_RECORD_MANIFEST_MISMATCH" in str(exc):
            raise
        summary["status"] = str(exc).split(":")[0] if isinstance(exc, ValueError) else "IMPLEMENTATION_ERROR"
        summary["error"] = repr(exc)[:3000]
        orders = {}
    finally:
        summary["usable_conformers"] = len(output)
        summary["elapsed_seconds"] = time.monotonic() - started
    # Failed cases and the deterministic 1% audit sample retain every candidate.
    if summary["status"] == "SUCCESS" and not summary.get("audit_sample", False):
        archive = []
    return {"summary": summary, "conformers": output, "pm7": pm7,
            "orders": orders, "audit_candidates": archive}
