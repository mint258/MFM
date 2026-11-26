"""Materialize only the original fixed composition panel; no model or labels."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
from finetune_entry import CooperativeStop, set_actual_deadline
from finetune_statistics_entry import require_cpu_admission, atomic_json, fingerprint


def append_molecule(state, molecule_index, z, choices, basis):
    import numpy as np
    z = np.asarray(z, dtype=np.int64)
    choices = [int(v) for v in choices]
    if (z.ndim != 1 or not len(z) or not 0 < len(choices) <= 10
            or len(set(choices)) != len(choices)):
        raise ValueError("Original molecule atom order and unique allowed conformers required")
    owner = len(state["molecules"])
    state["molecules"].append(dict(molecule_index=int(molecule_index),
        Z=z.tolist(), choices=choices,
        X=[int((z == v).sum()) for v in basis]
          + [len(z), int((z > 1).sum())]))
    return owner


def arrays_from_state(state):
    import numpy as np
    rows, owners, first, atom_counts, z, molecule_offsets = [], [], [], [], [], [0]
    for owner, m in enumerate(state["molecules"]):
        first.append(len(rows))
        z.extend(m["Z"]); molecule_offsets.append(len(z))
        for ci in m["choices"]:
            rows.append((m["molecule_index"], ci)); owners.append(owner)
            atom_counts.append(len(m["Z"]))
    return dict(indices=np.asarray(state["indices"], np.int64),
        rows=np.asarray(rows, np.int64), owners=np.asarray(owners, np.int64),
        first=np.asarray(first, np.int64),
        X=np.asarray([m["X"] for m in state["molecules"]], np.float64),
        basis=np.asarray(state["basis"], np.int64), Z=np.asarray(z, np.int64),
        molecule_atom_offsets=np.asarray(molecule_offsets, np.int64),
        record_atom_offsets=np.r_[np.int64(0), np.cumsum(atom_counts, dtype=np.int64)])


def cache_footprint(records, atoms, dimensions=512, source_count=12):
    # NPY headers, cursor replacement and phase summaries are bounded separately.
    per_source = (int(records) + int(atoms)) * int(dimensions) * 4 + 2**20
    return dict(mean_float32_bytes=int(records)*int(dimensions)*4,
        atom_float32_bytes=int(atoms)*int(dimensions)*4,
        per_source_cache_peak_bytes=per_source,
        all_sources_cache_peak_bytes=per_source*int(source_count),
        source_count=int(source_count))


def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c, stop); require_cpu_admission(c)
        output = Path(c["output"]); output.mkdir(parents=True, exist_ok=True)
        with (output/"owner.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if (output/"panel_complete.json").exists():
                raise ValueError("Closed panel must be reused, not materialized again")
            import numpy as np
            from diagnose import validation_indices
            from phychem_mfm.phase1.v31_loader import MFM4Dataset
            inputs = {p: fingerprint(p) for p in c["identity_inputs"]}
            identity = dict(inputs=inputs, root=c["root"], panel_seed=20261112,
                molecules=5000, k=10, ordering="Original FULL id_map order")
            cursor = output/"panel_cursor.json"
            if cursor.exists():
                state = json.loads(cursor.read_text())
                if state["identity"] != identity:
                    raise ValueError("Panel source identity changed")
            else:
                indices = [int(x) for x in validation_indices()]
                if len(indices) != 5000 or len(set(indices)) != 5000:
                    raise ValueError("Original exact5000 VAL cohort required")
                norms = json.loads(Path(c["basis_parameters"]).read_text())
                basis = sorted({int(z) for spec in norms.values()
                    for z in (spec.get("element_reference") or {}).get("basis", [])})
                state = dict(identity=identity, indices=indices, basis=basis, molecules=[])
                atomic_json(cursor, state)
            geometry = MFM4Dataset(c["root"], split="FULL", geometry_only=True,
                k=10, molecule_indices=state["indices"])
            try:
                for position in range(len(state["molecules"]), 5000):
                    if stop.requested:
                        atomic_json(cursor, state); return 75
                    mi = state["indices"][position]
                    molecule = geometry.record("M", mi)
                    append_molecule(state, mi, molecule[1], geometry.choices(mi), state["basis"])
                    if (position+1) % 100 == 0:
                        atomic_json(cursor, state)
                        print(json.dumps(dict(phase="PANEL", molecules=position+1)), flush=True)
            finally:
                geometry.close()
            arrays = arrays_from_state(state)
            if {p: fingerprint(p) for p in inputs} != inputs:
                raise ValueError("Source metadata changed during panel materialization")
            if stop.requested: return 75
            temporary = output/"panel.npz.new"
            with temporary.open("wb") as stream:
                np.savez_compressed(stream, **arrays)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, output/"panel.npz")
            receipt = dict(status="COMPLETE", job_id=os.environ["SLURM_JOB_ID"],
                molecules=5000, records=len(arrays["rows"]),
                atom_records=int(arrays["record_atom_offsets"][-1]),
                fixed_panel_seed=20261112, bootstrap_seed=20261025,
                identity=identity, panel=fingerprint(output/"panel.npz"),
                cache_footprint=cache_footprint(len(arrays["rows"]),
                    arrays["record_atom_offsets"][-1]),
                new_model_forwards=0, training=False, targets_read=False,
                original_population_and_order_preserved=True)
            atomic_json(output/"panel_complete.json", receipt)
            print(json.dumps(receipt), flush=True)
            return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration", required=True, type=Path)
    c = json.loads(parser.parse_args().configuration.read_text())
    if (c.get("ready") is not True or c.get("kind") != "COMPOSITION_PANEL"
            or os.environ.get("CUDA_VISIBLE_DEVICES") != ""):
        raise ValueError("Activated CPU-only composition panel configuration required")
    raise SystemExit(run(c))
