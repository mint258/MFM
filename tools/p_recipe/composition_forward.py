"""L6 H0 only, original fixed composition panel; resumable external feature caches."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
import fcntl
import json
import multiprocessing
import multiprocessing.util
import os
from pathlib import Path
import time
from finetune_entry import CooperativeStop, set_actual_deadline, admission, gpu_lock_and_check
from finetune_statistics_entry import atomic_json, fingerprint
from penalty_entry import ordered_validation

_GEOMETRY = None


def init_reader(root, indices):
    global _GEOMETRY
    from phychem_mfm.phase1.v31_loader import MFM4Dataset
    _GEOMETRY = MFM4Dataset(root, split="FULL", geometry_only=True, k=10,
                           molecule_indices=indices)
    multiprocessing.util.Finalize(None, _GEOMETRY.close, exitpriority=10)


def read_geometry(rows):
    return [_GEOMETRY.read(int(mi), int(ci)) for mi, ci in rows]


def validate_cursor(state, identity, atom_offsets):
    if state["identity"] != identity:
        raise ValueError("Composition checkpoint/panel identity changed")
    cursor = int(state["record_cursor"])
    total = len(atom_offsets)-1
    if (cursor < 0 or cursor > total or (cursor != total and cursor % 32)
            or int(state["atom_cursor"]) != int(atom_offsets[cursor])
            or (state.get("complete") is True and cursor != total)):
        raise ValueError("Composition prefix is not an exact native batch boundary")
    return cursor


def store_batch(atoms, means, features, pointer, start, atom_offsets):
    import numpy as np
    pointer = np.asarray(pointer, np.int64)
    count = len(pointer)-1
    expected = np.diff(atom_offsets[start:start+count+1])
    if (features.ndim != 2 or features.shape[1] != 512
            or pointer[0] != 0 or pointer[-1] != len(features)
            or not np.array_equal(np.diff(pointer), expected)):
        raise ValueError("Original source atom/record order changed")
    a = int(atom_offsets[start]); b = int(atom_offsets[start+count])
    atoms[a:b] = features
    for j, (low, high) in enumerate(zip(pointer, pointer[1:])):
        # Match collapse_composition.py: CPU F64 atom mean then one F32 cast.
        means[start+j] = np.asarray(features[low:high], np.float64).mean(0).astype(np.float32)
    return start+count


def sync_cache(path, arrays, state_path, state):
    for array in arrays:
        array.flush()
    for filename in ("atoms.npy", "means.npy"):
        with (path/filename).open("rb") as stream:
            os.fsync(stream.fileno())
    atomic_json(state_path, state)


def run(c):
    if c.get("ready") is not True or c.get("kind") != "COMPOSITION_FORWARD":
        raise ValueError("Registered composition forward configuration required")
    output = Path(c["output"])
    if (output/"summary.json").exists():
        raise ValueError("Closed feature producer must be consumed, not repeated")
    with CooperativeStop() as stop:
        set_actual_deadline(c, stop); node = admission(c)
        gpu_lock, card = gpu_lock_and_check(c, stop)
        try:
            os.environ["CUDA_VISIBLE_DEVICES"] = c["gpu_uuid"]
            import numpy as np
            import torch
            from phychem_mfm.phase1.v31_loader import collate_samples
            from composition_encoder import load_representation_encoder
            torch.set_num_threads(1); torch.set_float32_matmul_precision("highest")
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            receipt_path = Path(c["panel_complete"])
            panel_receipt = json.loads(receipt_path.read_text())
            if (panel_receipt["status"] != "COMPLETE" or panel_receipt["molecules"] != 5000
                    or panel_receipt["panel"] != fingerprint(c["panel"])):
                raise ValueError("Closed original panel identity required")
            panel_identity = dict(receipt=fingerprint(receipt_path), panel=fingerprint(c["panel"]))
            with np.load(c["panel"], allow_pickle=False) as p:
                rows = p["rows"].copy(); indices = p["indices"].copy()
                offsets = p["record_atom_offsets"].copy()
            n = len(rows); total_atoms = int(offsets[-1])
            output.mkdir(parents=True, exist_ok=True)
            started = time.time()
            cutoff = float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
            def should_stop():
                return stop.requested or time.time()+c["work_unit_seconds"] >= cutoff
            completed = {}
            with (output/"owner.lock").open("a") as owner:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with ProcessPoolExecutor(c["workers"],
                        mp_context=multiprocessing.get_context("spawn"),
                        initializer=init_reader, initargs=(c["root"], indices.tolist())) as pool:
                    for source in c["sources"]:
                        binding = source["source_binding"]; label = source["label"]
                        checkpoint = fingerprint(binding["checkpoint"])
                        if (checkpoint["bytes"] != binding["bytes"]
                                or checkpoint["mtime_ns"] != source["checkpoint_mtime_ns"]):
                            raise ValueError("Original model checkpoint changed")
                        identity = dict(source=source, panel=panel_identity)
                        path = output/label; state_path = path/"cursor.json"
                        state = json.loads(state_path.read_text()) if state_path.exists() else dict(
                            identity=identity, record_cursor=0, atom_cursor=0, complete=False)
                        cursor = validate_cursor(state, identity, offsets)
                        if state.get("complete"):
                            completed[label] = str(state_path); continue
                        if should_stop(): return 75
                        # Recheck real output filesystem/peer budget before each >1GiB cache.
                        admission(c)
                        path.mkdir(parents=True, exist_ok=True)
                        mode = "r+" if cursor else "w+"
                        atoms = np.lib.format.open_memmap(path/"atoms.npy", mode=mode,
                            dtype=np.float32, shape=(total_atoms,512))
                        means = np.lib.format.open_memmap(path/"means.npy", mode=mode,
                            dtype=np.float32, shape=(n,512))
                        if (atoms.shape != (total_atoms,512) or means.shape != (n,512)
                                or atoms.dtype != np.float32 or means.dtype != np.float32):
                            raise ValueError("Saved feature cache shape changed")
                        atomic_json(state_path, state)
                        torch.manual_seed(0); torch.cuda.manual_seed_all(0)
                        encoder, payload = load_representation_encoder(binding["checkpoint"])
                        if int(payload["clock"]["samples_consumed"]) != binding["samples"]:
                            raise ValueError("Original source sample clock differs")
                        del payload
                        with closing(ordered_validation(pool, read_geometry, rows,
                                cursor//32, 32, should_stop)) as batches:
                            for _, samples in batches:
                                if should_stop(): break
                                batch = collate_samples(samples, device="cuda")
                                with torch.no_grad():
                                    features = encoder.encode_atoms(batch).detach().cpu().double().numpy()
                                cursor = store_batch(atoms, means, features,
                                    batch.ptr.cpu().tolist(), cursor, offsets)
                                state.update(record_cursor=cursor, atom_cursor=int(offsets[cursor]))
                                if cursor % 1024 == 0 or cursor == n:
                                    sync_cache(path, (atoms,means), state_path, state)
                                    print(json.dumps(dict(source=label,records=cursor,total=n)),flush=True)
                        sync_cache(path, (atoms,means), state_path, state)
                        del atoms, means, encoder
                        torch.cuda.empty_cache()
                        if cursor != n: return 75
                        state["complete"] = True; atomic_json(state_path, state)
                        completed[label] = str(state_path)
                summary = dict(status="COMPLETE",job_id=os.environ["SLURM_JOB_ID"],
                    node=node, card=card, sources=completed, source_count=len(completed),
                    panel=panel_identity, molecules=5000,records=n,atom_records=total_atoms,
                    layer=6,representation="H0_before_projector",batch_size=32,
                    precision="FP32; mean uses originalCPU_F64_then_F32",
                    new_training=False,targets_read=False,TF32=False,
                    statistics_pending=True,atomic_metric_definition_pending=True,
                    seconds_this_attempt=time.time()-started,
                    peak_GPU_allocated_bytes=torch.cuda.max_memory_allocated())
                atomic_json(output/"summary.json",summary); print(json.dumps(summary),flush=True)
                return 0
        finally:
            gpu_lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration",required=True,type=Path)
    raise SystemExit(run(json.loads(parser.parse_args().configuration.read_text())))
