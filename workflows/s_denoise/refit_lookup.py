"""Same empirical noisy-bin lookup, refitted on the new full TRAIN population."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
import math
import multiprocessing as mp

from runtime import ROOT, OLD, assert_allocation, native_components, save, sha, setup_imports

_DATASET = _TABLE = _SUBSET = None


def initialize_worker(role, table=None):
    global _DATASET, _TABLE, _SUBSET
    setup_imports()
    import torch
    import numpy as np
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    _, _DATASET, _ = native_components(role, seed=0, epoch_noise=True, verify_hashes=False)
    _TABLE = table
    _SUBSET = set(np.load(ROOT / "diagnostics/selection_v1/full_rows.npy", allow_pickle=False).tolist()) if role == "full" else None


def pairs(logical):
    import torch
    from phychem_mfm.training.degrade_molecules import degrade_once
    ref = _DATASET.index.ref(logical)
    clean = _DATASET._native(ref)
    target = clean.pos.clone().float()
    z = clean.x[:, 0].long() + 1
    noisy = degrade_once(deepcopy(clean), _DATASET.cfgs[1], torch.Generator().manual_seed(_DATASET.noise_seed(logical))).pos.float()
    truth, observed = torch.cdist(target, target), torch.cdist(noisy, noisy)
    i, j = torch.triu_indices(len(z), len(z), offset=1)
    mask = truth[i, j].lt(2.0)
    i, j = i[mask], j[mask]
    distance = observed[i, j].double().numpy()
    expected = truth[i, j].double().numpy()
    lo, hi = torch.minimum(z[i], z[j]).numpy(), torch.maximum(z[i], z[j]).numpy()
    import numpy as np
    bins = np.minimum(np.floor(distance / 0.05), 100).astype(np.int64)
    codes = (lo * 119 + hi) * 101 + bins
    return codes, expected, distance


def fit_chunk(bounds):
    import numpy as np
    size = 119 * 119 * 101
    counts = np.zeros(size, dtype=np.int64)
    total = np.zeros(size, dtype=np.float64)
    squares = np.zeros(size, dtype=np.float64)
    for logical in range(*bounds):
        codes, target, _ = pairs(logical)
        np.add.at(counts, codes, 1)
        np.add.at(total, codes, target)
        np.add.at(squares, codes, target ** 2)
    keys = np.flatnonzero(counts)
    return {"start": bounds[0], "end": bounds[1], "records": bounds[1] - bounds[0],
            "stats": {str(int(k)): [int(counts[k]), float(total[k]), float(squares[k])] for k in keys}}


def evaluate_chunk(bounds):
    import numpy as np
    sums = {"full": [0.0, 0.0, 0, 0, 0], "D3_FULL2000": [0.0, 0.0, 0, 0, 0]}
    for logical in range(*bounds):
        codes, target, noisy = pairs(logical)
        predicted = noisy.copy()
        used = 0
        for key in np.unique(codes):
            if int(key) in _TABLE:
                predicted[codes == key] = _TABLE[int(key)]
                used += int((codes == key).sum())
        error, original = float(((predicted - target) ** 2).sum()), float(((noisy - target) ** 2).sum())
        for label in ["full"] + (["D3_FULL2000"] if logical in _SUBSET else []):
            entry = sums[label]
            entry[0] += error
            entry[1] += original
            entry[2] += len(target)
            entry[3] += 1
            entry[4] += used
    return sums


def main():
    assert_allocation()
    setup_imports()
    import numpy as np
    out = ROOT / "diagnostics/lookup_refit_v1"
    out.mkdir(parents=True, exist_ok=False)
    index, dataset, _ = native_components("train", seed=0, epoch_noise=True)
    records = len(index)
    dataset.close()
    bounds = [(start, min(start + 65536, records)) for start in range(0, records, 65536)]
    aggregate = {}
    visited = 0
    with ProcessPoolExecutor(16, mp_context=mp.get_context("spawn"), initializer=initialize_worker, initargs=("train",)) as pool:
        for result in pool.map(fit_chunk, bounds, chunksize=1):
            visited += result["records"]
            save(out / "progress.json", {"phase": "TRAIN_FIT", "visited_records": visited, "expected": records})
            for key, value in result["stats"].items():
                accumulator = aggregate.setdefault(key, [0, 0.0, 0.0])
                for j in range(3):
                    accumulator[j] += value[j]
    assert visited == 11104772
    table = {int(key): value[1] / value[0] for key, value in aggregate.items() if value[0] >= 32 and int(key) % 101 < 100}
    save(out / "TRAIN_only_bin_statistics.json", aggregate)
    save(out / "TRAIN_only_lookup.json", {str(k): v for k, v in table.items()})
    index, dataset, _ = native_components("full", seed=0, epoch_noise=True)
    full_records = len(index)
    dataset.close()
    values = {"full": [0.0, 0.0, 0, 0, 0], "D3_FULL2000": [0.0, 0.0, 0, 0, 0]}
    bounds = [(start, min(start + 8192, full_records)) for start in range(0, full_records, 8192)]
    with ProcessPoolExecutor(16, mp_context=mp.get_context("spawn"), initializer=initialize_worker, initargs=("full", table)) as pool:
        for result in pool.map(evaluate_chunk, bounds, chunksize=1):
            for role in values:
                for j in range(5):
                    values[role][j] += result[role][j]
    assert values["full"][3] == 127082
    expected_subset = len(np.load(ROOT / "diagnostics/selection_v1/full_rows.npy", allow_pickle=False))
    assert values["D3_FULL2000"][3] == expected_subset
    metrics = {role: {"lookup_rmse_A": math.sqrt(v[0] / v[2]), "noisy_rmse_A": math.sqrt(v[1] / v[2]),
                      "pairs": v[2], "records": v[3], "lookup_used_pairs": v[4]} for role, v in values.items()}
    report = {"status": "NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE", "TRAIN_records": visited,
              "validation_values_used_for_fit": False, "sigma_A": 0.1,
              "recipe": {"bin_width_A": 0.05, "max_noisy_distance_A": 5.0, "minimum_TRAIN_bin_observations": 32,
                         "inputs": "clean elements and observed noisy distance bin", "target": "conditional mean clean distance of TRAIN local unordered pairs", "fallback": "observed noisy distance"},
              "noise_seed_includes_epoch": True, "view_seed": 0, "evaluation_epoch": 0,
              "historical_guide_reference_A": 0.042, "metrics": metrics,
              "input_manifest_sha256": sha(OLD / "training_inputs_v1/manifest.json")}
    save(out / "result.json", report)
    save(ROOT / "reports/lookup_latest.json", {"path": str(out / "result.json"), "sha256": sha(out / "result.json")})
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
