"""Read-only crossover benchmark; source-global seeds, local map-close blocks."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")
sys.path.insert(0, str(ROOT / "source_v2/workflows/s_denoise"))
from runtime import setup_imports, save
setup_imports()

from data import SelectedViewsDataset


class LocalBlockSelectedViewsDataset(SelectedViewsDataset):
    def _ensure_worker(self, source_logical_index):
        import numpy as np
        local = int(np.searchsorted(self.index.rows, source_logical_index))
        assert int(self.index.rows[local]) == source_logical_index
        super()._ensure_worker(local)


def components(*, verify_hashes):
    import numpy as np
    from data import SelectedIndex, SelectedCounts
    from runtime import native_components, old_configuration
    parent, original, _ = native_components("train", seed=0, epoch_noise=True, verify_hashes=verify_hashes)
    index = SelectedIndex(parent, np.load(ROOT / "diagnostics/selection_v1/train_rows.npy", allow_pickle=False))
    dataset = SelectedViewsDataset(index, native_transport=original.native_transport,
        native_transport_binding=original.native_transport_binding, seed=0, noise_seed_includes_epoch=True,
        **old_configuration()["views"])
    return index, dataset, SelectedCounts(index)


def signature(value):
    import torch
    rows = []
    for view in value.views:
        tensors = {}
        for key, tensor in view.to_dict().items():
            if isinstance(tensor, torch.Tensor):
                tensors[key] = {"dtype": str(tensor.dtype), "shape": list(tensor.shape),
                    "sha256": hashlib.sha256(tensor.detach().contiguous().numpy().tobytes()).hexdigest()}
        rows.append(tensors)
    return {"record_key": value.record_key, "logical_index": value.logical_index,
            "native_n_atoms": value.native_n_atoms, "base_row": value.base_row, "views": rows}


def worker(args):
    import torch
    torch.set_num_threads(1)
    worker_id, logicals = args
    results = []
    expected = None
    for label in ["original", "local_blocks", "local_blocks", "original"]:
        _, dataset, _ = components(verify_hashes=False)
        dataset.cache_bytes = 0
        if label == "local_blocks":
            dataset.__class__ = LocalBlockSelectedViewsDataset
        started = time.monotonic()
        changes = 0
        signatures = []
        try:
            for logical in logicals:
                before = dataset._block
                value = dataset[logical]
                changes += int(dataset._block != before)
                signatures.append(signature(value))
            elapsed = time.monotonic() - started
            if expected is None:
                expected = signatures
            assert expected == signatures, "SUBSET_HANDLE_POLICY_CHANGED_SCIENTIFIC_INPUTS"
            results.append({"variant": label, "seconds": elapsed, "records": len(logicals), "map_close_block_changes": changes})
        finally:
            dataset.close()
    return {"worker": worker_id, "runs": results, "all_input_tensor_bytes_equal": True}


def main():
    import os
    import torch
    from phychem_mfm.phase1.full_corpus_loader import BlockAtomBatchSampler
    from runtime import old_configuration
    assert os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ["SLURM_CPUS_PER_TASK"]) >= 16
    torch.set_num_threads(1)
    index, dataset, counts = components(verify_hashes=True)
    sampler = BlockAtomBatchSampler(counts, seed=0, epoch=0, **old_configuration()["sampler"])
    logicals = next(iter(sampler))[:256]
    dataset.close()
    tasks = [(i, logicals[i * 16:(i + 1) * 16]) for i in range(16)]
    with ProcessPoolExecutor(16, mp_context=mp.get_context("spawn")) as pool:
        rows = list(pool.map(worker, tasks))
    report = {"status": "SUBSET_HANDLE_CROSSOVER_PARITY_PASS", "records": len(logicals), "workers": 16,
              "method": "original/modified/modified/original crossover, clean byte LRU disabled, all three views and all Tensor fields exact",
              "scientific_data_or_seeds_modified": False, "rows": rows}
    for name in ["original", "local_blocks"]:
        selected = [run for row in rows for run in row["runs"] if run["variant"] == name]
        report[name] = {"sum_worker_seconds": sum(r["seconds"] for r in selected),
                        "records_read": sum(r["records"] for r in selected),
                        "map_close_block_changes": sum(r["map_close_block_changes"] for r in selected)}
    save(ROOT / "reports/subset_handle_crossover_v1.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}), flush=True)


if __name__ == "__main__":
    main()
