"""One resumable 5000-VAL forward shared by all D representation statistics.

Reuse P's exact membership, encoder loader and layer extraction. This command
does not fit probes or run statistics. Only the caller's D output is written.
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np


REPRESENTATION_SOURCE = Path("/share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117/tools/p_recipe/diagnose.py")
COMPOSITION_NORMALIZATIONS = Path("/share/home/zixiao/descriptor_analysis/runs/p_data_information_20261115_v1/normalizations_TRAIN.json")


def representation_code():
    specification = importlib.util.spec_from_file_location("d_existing_representation", REPRESENTATION_SOURCE)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def registered_endpoint(configuration):
    allowed = {"D-R0", "D-R1", "D-G1"}
    adopted = configuration.get("adopted_arm")
    if adopted in {"D-L1", "D-L2", "D-K1"}:
        allowed.add(adopted)
    if configuration["arm"] not in allowed or configuration["samples"] != 3_000_000 or configuration["seed"] != 0:
        raise ValueError("Representation diagnostics use registered seed0 3M endpoints only")


def make_panel(geometry, indices, basis):
    rows, owners, first, atom_ptr, composition = [], [], [], [0], []
    for owner, mi in enumerate(indices):
        z = geometry.record("M", int(mi))[1]
        choices = geometry.choices(int(mi))
        first.append(len(rows))
        rows.extend((int(mi), int(ci)) for ci in choices)
        owners.extend([owner] * len(choices))
        atom_ptr.append(atom_ptr[-1] + len(z))
        composition.append([int((z == element).sum()) for element in basis]
                           + [len(z), int((z > 1).sum())])
    return dict(rows=np.asarray(rows, np.int64), owners=np.asarray(owners, np.int64),
        first=np.asarray(first, np.int64), atom_ptr=np.asarray(atom_ptr, np.int64),
        composition=np.asarray(composition, np.float64), indices=np.asarray(indices, np.int64),
        basis=np.asarray(basis, np.int64))


def store_batch(means, atoms, panel, start, features, pointers):
    """Save all conformer means and first-conformer atoms in source atom order."""
    for offset, (a, b) in enumerate(zip(pointers, pointers[1:])):
        row = start + offset
        h = features[a:b]
        means[row] = h.mean(0)
        owner = panel["owners"][row]
        if row == panel["first"][owner]:
            atoms[panel["atom_ptr"][owner]:panel["atom_ptr"][owner + 1]] = h


def run(configuration, *, module=None, guard=None):
    registered_endpoint(configuration)
    from .resources import capacity_gate, execution_site
    execution_site(configuration, cpu=False)
    if guard is None:
        from .resources import DJointGuard
        guard = DJointGuard(configuration)
    capacity_check = capacity_gate(guard, configuration)
    output = Path(configuration["output"])
    capacity_check(output)
    output.mkdir(parents=True, exist_ok=True)
    state_path, manifest_path = output / "cursor.json", output / "manifest.json"
    binding = {k: configuration[k] for k in ("arm", "run", "samples", "seed", "checkpoint", "root", "source")}
    if manifest_path.exists():
        result = json.loads(manifest_path.read_text())
        if result.get("schema") != "D_REPRESENTATION_FORWARD_V1" or result.get("status") != "FORWARD_COMPLETE":
            raise ValueError("The forward manifest is not closed")
        if result["binding"] != binding:
            raise ValueError("Closed forward cache belongs to another registered endpoint")
        return result
    module = representation_code() if module is None else module
    from phychem_mfm.phase1.v31_loader import MFM4Dataset, collate_samples
    import torch
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    indices = np.asarray(module.validation_indices(), np.int64)
    if len(indices) != 5000:
        raise ValueError("Use the existing fixed 5000-VAL panel")
    data = MFM4Dataset(configuration["root"], split="FULL", geometry_only=True,
        source=configuration["source"], k=10, molecule_indices=indices)
    try:
        parameters = json.loads(COMPOSITION_NORMALIZATIONS.read_text())
        basis = sorted({int(z) for p in parameters.values()
                        for z in (p.get("element_reference") or {}).get("basis", [])})
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if state["binding"] != binding:
                raise ValueError("Partial forward cache belongs to another registered endpoint")
            with np.load(output / "panel.npz") as archive:
                panel = {name: archive[name] for name in archive.files}
            mode, cursor = "r+", state["cursor"]
        else:
            panel = make_panel(data, indices, basis)
            capacity_check(output)
            np.savez(output / "panel.npz", **panel)
            mode, cursor = "w+", 0
        means = np.lib.format.open_memmap(output / "means.npy", mode=mode,
            dtype=np.float64, shape=(len(panel["rows"]), 4, 512))
        atoms = np.lib.format.open_memmap(output / "first_atoms.npy", mode=mode,
            dtype=np.float64, shape=(int(panel["atom_ptr"][-1]), 4, 512))
        encoder, payload = module.load_representation_encoder(configuration["checkpoint"], device="cuda")
        consumed = payload.get("clock", {}).get("samples_consumed", payload.get("samples"))
        if consumed != 3_000_000:
            raise ValueError("The supplied checkpoint is not the registered 3M endpoint")
        with torch.no_grad():
            for start in range(cursor, len(panel["rows"]), 32):
                capacity_check(output)
                samples = [data.read(int(mi), int(ci)) for mi, ci in panel["rows"][start:start + 32]]
                batch = collate_samples(samples, device="cuda")
                layers = module.representation_layers(encoder, batch)
                features = np.stack([h.detach().cpu().double().numpy() for h in layers], axis=1)
                store_batch(means, atoms, panel, start, features, batch.ptr.cpu().tolist())
                means.flush()
                atoms.flush()
                temporary = state_path.with_suffix(".partial")
                temporary.write_text(json.dumps(dict(binding=binding, cursor=start + len(samples))) + "\n")
                temporary.replace(state_path)
        result = dict(schema="D_REPRESENTATION_FORWARD_V1", status="FORWARD_COMPLETE",
            binding=binding, panel=str(output / "panel.npz"), means=str(output / "means.npy"),
            first_atoms=str(output / "first_atoms.npy"), layers=[3, 4, 5, 6],
            molecules=5000, conformers=len(panel["rows"]), cache_dtype="float64",
            source=str(REPRESENTATION_SOURCE), statistics_complete=False)
        capacity_check(output)
        temporary = manifest_path.with_suffix(".partial")
        temporary.write_text(json.dumps(result, indent=2) + "\n")
        temporary.replace(manifest_path)
        return result
    finally:
        data.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(json.loads(Path(arguments.configuration).read_text()))))
