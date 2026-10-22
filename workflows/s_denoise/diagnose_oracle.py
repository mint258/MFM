"""D2 projected optimization of bounded symmetric pair weights, no network."""
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing as mp
import os

from runtime import ROOT, assert_allocation, native_components, save, sha, setup_imports

_DATASET = None


def initialize_worker():
    global _DATASET
    setup_imports()
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    _, _DATASET, _ = native_components("full", seed=0, verify_hashes=False)


def optimize(noisy, target, *, scale, neighbor_norm):
    import torch
    n = len(noisy)
    truth = torch.cdist(target, target)
    i, j = torch.triu_indices(n, n, offset=1)
    relative = noisy[i] - noisy[j]
    if neighbor_norm:
        selected = relative.norm(dim=-1) < 5.0
        i, j, relative = i[selected], j[selected], relative[selected]
        denominator = torch.bincount(torch.cat((i, j)), minlength=n).clamp_min(1).to(noisy.dtype)
    else:
        denominator = torch.full((n,), float(n), dtype=noisy.dtype)
    a, b = torch.triu_indices(n, n, offset=1)
    local = truth[a, b] < 2.0
    a, b = a[local], b[local]
    if not len(a):
        return {"status": "NO_LOCAL_PAIRS", "pairs": 0, "squared_error_sum": 0.0}
    weights = torch.nn.Parameter(torch.zeros(len(i), dtype=noisy.dtype))
    optimizer = torch.optim.Adam([weights], lr=0.12)
    best = math.inf
    trajectory = []
    for step in range(2000):
        optimizer.zero_grad(set_to_none=True)
        vectors = weights[:, None] * relative
        correction = torch.zeros_like(noisy).index_add(0, i, vectors).index_add(0, j, -vectors)
        predicted = noisy + scale * correction / denominator[:, None]
        error = (predicted[a] - predicted[b]).norm(dim=-1) - truth[a, b]
        loss = error.square().mean()
        assert torch.isfinite(loss), "SCIENTIFIC_STOP_NONFINITE_ORACLE"
        numeric = float(loss.detach())
        if numeric < best:
            best = numeric
        if step % 100 == 0 or step == 1999:
            trajectory.append({"step": step, "current_rmse_A": math.sqrt(numeric), "best_rmse_A": math.sqrt(best)})
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            weights.clamp_(-1.0, 1.0)
    assert weights.detach().abs().max() <= 1 if len(weights) else True
    return {"status": "PROJECTED_OPTIMIZATION_FINISHED", "pairs": len(a), "squared_error_sum": best * len(a),
            "best_rmse_A": math.sqrt(best), "steps": 2000, "trajectory": trajectory,
            "interpretation": "best achieved feasible error; not a certified global minimum"}


def process_molecule(item):
    import torch
    ordinal, source_index = item
    views = _DATASET[int(source_index)]
    noisy = views.views[1].pos.double()
    target = views.views[1].target_pos.double()
    variants = {}
    for name, scale, neighbor_norm in [("scale0p1_N", 0.1, False), ("scale1_N", 1.0, False),
                                        ("scale0p1_neighbors5", 0.1, True), ("scale1_neighbors5", 1.0, True)]:
        variants[name] = optimize(noisy, target, scale=scale, neighbor_norm=neighbor_norm)
    return {"ordinal": ordinal, "source_index": int(source_index), "record_key": views.record_key,
            "atoms": len(noisy), "variants": variants}


def main():
    assert_allocation()
    setup_imports()
    import numpy as np
    indices = np.load(ROOT / "diagnostics/selection_v1/oracle1000_rows.npy", allow_pickle=False)
    out = ROOT / "diagnostics/D2_oracle_v1"
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    with ProcessPoolExecutor(16, mp_context=mp.get_context("spawn"), initializer=initialize_worker) as pool:
        for result in pool.map(process_molecule, enumerate(indices.tolist()), chunksize=1):
            rows.append(result)
            save(out / "progress.json", {"molecules": len(rows), "expected": 1000})
            save(out / f"molecule_{result['ordinal']:04d}.json", result)
    aggregate = {}
    for name in rows[0]["variants"]:
        selected = [row["variants"][name] for row in rows]
        pairs = sum(row["pairs"] for row in selected)
        error = sum(row["squared_error_sum"] for row in selected)
        aggregate[name] = {"local_rmse_A": math.sqrt(error / pairs), "local_pairs": pairs,
                           "molecule_rmse_median_A": float(np.median([row["best_rmse_A"] for row in selected if row["pairs"]]))}
    report = {"status": "D2_COMPLETE", "molecules": len(rows), "sigma_A": 0.1,
              "optimizer": "Adam with projection of every symmetric upper-triangle weight to [-1,1] after every step",
              "steps_per_molecule_per_variant": 2000, "aggregate": aggregate,
              "interpretation": "Achieved errors are feasible oracle solutions, not certified lower bounds. A low oracle error refutes an absolute capacity ceiling; a high one alone does not prove impossibility."}
    save(out / "result.json", report)
    save(ROOT / "reports/D2_latest.json", {"path": str(out / "result.json"), "sha256": sha(out / "result.json")})
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
