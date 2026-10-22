"""Molecule-level fixed sampling, all conformers retained; metadata-only Slurm job."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import hashlib
import heapq
import json
import multiprocessing as mp
from pathlib import Path
import sys

from runtime import ROOT, OLD, assert_allocation, save, sha, setup_imports


def scan_partition(args):
    import pyarrow as pa
    path, worker, workers, limit, seed = args
    reader = pa.ipc.open_file(pa.memory_map(path, "r"))
    candidates = {}
    for n in range(worker, reader.num_record_batches, workers):
        batch = reader.get_batch(n)
        values = set(batch.column(batch.schema.get_field_index("molecule_id")).to_pylist())
        for molecule in values:
            candidates[molecule] = hashlib.sha256(f"{seed}:{molecule}".encode()).digest()
    return heapq.nsmallest(limit, ((rank.hex(), mol) for mol, rank in candidates.items()))


def selected_rows(path, chosen):
    import numpy as np
    import pyarrow as pa
    reader = pa.ipc.open_file(pa.memory_map(path, "r"))
    rows, first = [], {}
    offset = 0
    for i in range(reader.num_record_batches):
        batch = reader.get_batch(i)
        molecules = batch.column(batch.schema.get_field_index("molecule_id")).to_pylist()
        for j, mol in enumerate(molecules):
            if mol in chosen:
                rows.append(offset + j)
                first.setdefault(mol, offset + j)
        offset += len(batch)
    assert set(first) == set(chosen)
    return np.asarray(rows, dtype=np.int64), first


def main():
    assert_allocation()
    setup_imports()
    import numpy as np
    manifest = json.loads((OLD / "training_inputs_v1/manifest.json").read_text())
    out = ROOT / "diagnostics/selection_v1"
    out.mkdir(parents=True, exist_ok=False)
    seed = 20261016
    receipt = {"status": "MOLECULE_SAMPLING_COMPLETE", "seed": seed,
               "selection": "lowest SHA256(seed:molecule_id), all source conformers, original source order",
               "input_manifest_sha256": sha(OLD / "training_inputs_v1/manifest.json"), "roles": {}}
    for role, count in [("train", 10000), ("full", 2000)]:
        ref = next(r for r in manifest["references"] if r.get("role") == role and r.get("kind") == "record_metadata")
        assert sha(ref["path"]) == ref["sha256"]
        workers = 16
        with ProcessPoolExecutor(workers, mp_context=mp.get_context("spawn")) as pool:
            results = list(pool.map(scan_partition, [(ref["path"], i, workers, count, seed) for i in range(workers)]))
        unique = {mol: rank for result in results for rank, mol in result}
        chosen = [mol for mol, rank in sorted(unique.items(), key=lambda item: (item[1], item[0]))[:count]]
        assert len(chosen) == count
        rows, first = selected_rows(ref["path"], set(chosen))
        np.save(out / (role + "_rows.npy"), rows, allow_pickle=False)
        save(out / (role + "_molecules.json"), chosen)
        receipt["roles"][role] = {"molecules": count, "records": len(rows),
                                  "rows_sha256": sha(out / (role + "_rows.npy")), "source": ref}
        if role == "full":
            oracle_rows = np.asarray([first[mol] for mol in chosen[:1000]], dtype=np.int64)
            np.save(out / "oracle1000_rows.npy", oracle_rows, allow_pickle=False)
            receipt["oracle"] = {"molecules": 1000, "conformers_per_molecule": 1,
                                 "selection": "first source conformer of first1000 ranked FULL molecules",
                                 "rows_sha256": sha(out / "oracle1000_rows.npy")}
    train_mols = set(json.loads((out / "train_molecules.json").read_text()))
    full_mols = set(json.loads((out / "full_molecules.json").read_text()))
    assert not train_mols & full_mols
    receipt["train_full_molecule_overlap"] = 0
    save(out / "receipt.json", receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
