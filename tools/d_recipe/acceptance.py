"""The taskbook's one real-loader, 64-molecule reception acceptance.

Only newly created molecular descriptor H1 heads are fitted, by float64
least squares on frozen H0. This is a head overfit check, not a pretraining
arm or a readout result. The native encoder, raw store and D4 stay unchanged.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import torch
import torch.nn.functional as F


def fit_linear_head(head, features, targets, observed, specification):
    """Fit the existing raw-output H1 head, with no missing-value imputation.

    Solve in standardized coordinates for conditioning, then transform the
    fitted coefficients back to the model's raw-output coordinates. Target
    clipping occurs here only, after the already frozen D4 transform.
    """
    if not isinstance(head, torch.nn.Linear) or head.out_features != 1:
        raise ValueError("Reception uses the existing scalar H1 linear head")
    observed = torch.as_tensor(observed, dtype=torch.bool, device=features.device).reshape(-1)
    target = torch.as_tensor(targets, dtype=torch.float64, device=features.device).reshape(-1)
    if features.ndim != 2 or len(features) != len(target) or len(target) != len(observed):
        raise ValueError("Reception observations must align with frozen molecule features")
    if not observed.any():
        raise ValueError("No observed reception targets for this enabled field")
    x = features.double()[observed]
    y = target[observed]
    if not torch.isfinite(x).all() or not torch.isfinite(y).all():
        raise ValueError("Nonfinite observed reception inputs")
    y = y.clamp(-6., 6.)
    design = torch.cat((x, x.new_ones((len(x), 1))), dim=1)
    solution = torch.linalg.lstsq(design, y[:, None], driver="gelsd")
    center = float(np.asarray(specification["center"]).reshape(()))
    scale = float(np.asarray(specification["scale"]).reshape(()))
    if not np.isfinite(center) or not np.isfinite(scale) or scale <= 0:
        raise ValueError("Reception requires existing finite positive D4 parameters")
    coefficient = solution.solution[:, 0]
    with torch.no_grad():
        head.weight.copy_((coefficient[:-1] * scale)[None].to(head.weight))
        head.bias.copy_((coefficient[-1] * scale + center).reshape_as(head.bias).to(head.bias))
    return {"observations": int(observed.sum()), "design_rank": int(solution.rank)}


def reception_result(initial, final, *, absolute_noise=1e-12):
    # Numerical zero uses an absolute floor as well as the taskbook ratio.
    finite = np.isfinite(initial) and np.isfinite(final) and initial >= 0 and final >= 0
    return {"initial_loss": float(initial) if np.isfinite(initial) else None,
            "final_loss": float(final) if np.isfinite(final) else None,
            "loss_ratio": float(final / initial) if finite and initial > 0 else None,
            "relative_threshold": .01, "absolute_numerical_noise": absolute_noise,
            "passed": bool(finite and (final < .01 * initial or final <= absolute_noise))}


def sasa_alignment(native, sample):
    """Compare native SASA rows with source atom-row IDs once at reception."""
    molecule, conformer = sample["molecule_index"], sample["conformer_index"]
    atoms = native.record("M", molecule)[1]
    source = native.record("P", molecule, conformer)
    if not np.array_equal(sample["Z"], atoms) or len(sample["pos"]) != len(atoms):
        raise ValueError("Reception atom sequence differs from source atom-row IDs")
    fields = [f for f in native.view.fields if f["group"] == "D" and f["level"] == "atom"]
    if len(fields) != 1:
        raise ValueError("One source atomic SASA field is required")
    field = fields[0]
    key = field.get("_location_key", field.get("target_id", field.get("field_key", field["name"])))
    locations = native.view.locations[key]
    if len(locations) != 1 or locations[0][0] != "atom_labels":
        raise ValueError("Atomic SASA must follow the native atom-label rows")
    raw = np.asarray(source[24][:, [locations[0][1]]], dtype=np.float32)
    target = sample["original_targets"][field["name"]]
    if raw.shape != (len(atoms), 1) or not np.array_equal(raw, target.raw, equal_nan=True):
        raise ValueError("Atomic SASA is not aligned with its original source atom rows")
    if not np.array_equal(target.valid, ~np.isnan(raw)):
        raise ValueError("Atomic SASA source masks differ")
    return len(atoms)


def accept(configuration):
    node = platform.node().split(".")[0]
    if not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-") or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19:
        raise RuntimeError("Reception runs on an allocated CPU node 8-19")
    from workflows.data_d_descriptors.pilot import storage_guard
    from phychem_mfm.phase1.p_recipe_data import dataset_configuration
    from phychem_mfm.phase1.v2_s_training import s_model
    from phychem_mfm.phase1.v31_loader import encode_samples
    from phychem_mfm.phase1.v31_training import V31PDModel, torch_affine
    from .dataset import DRecipeDataset
    output = Path(configuration["acceptance_output"])
    storage_guard(output.parent, peak_bytes=2**26)
    if output.exists():
        return json.loads(output.read_text())
    if configuration["d_recipe"]["library"] not in ("L1", "L2"):
        raise ValueError("Reception is for newly produced descriptor libraries")
    options = dict(configuration["d_recipe"], pma_compatibility=True, label_parameters=None)
    data = DRecipeDataset(**dataset_configuration(configuration), d_recipe=options)
    torch.set_num_threads(1)
    torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    rng = np.random.default_rng(20261120)
    chosen = rng.choice(data.indices, 64, replace=False)
    samples = [data.read(int(i), int(data.choices(int(i))[0])) for i in chosen]
    atoms = sum(sasa_alignment(data.native, sample) for sample in samples)
    structural, _ = s_model("C1-0", "three")
    structural.eval().requires_grad_(False)
    model = V31PDModel(structural.encoder, data.view, forms="H1", p_recipe={}).eval()
    names = tuple(f.name for f in model.registry.fields if f.level == "graph")
    # Single encoder pass per actual molecule, reused for all new heads.
    cached = []
    with torch.no_grad():
        for start in range(0, 64, 8):
            group = samples[start:start + 8]
            batch, h = encode_samples(group, model.encoder, device="cpu")
            cached.append((group, batch, h.detach()))
    features = {mode: [] for mode in ("mean", "sum")}
    for group, batch, h in cached:
        sums = h.new_zeros((len(group), h.shape[1])).index_add_(0, batch.batch, h)
        features["sum"].append(sums)
        features["mean"].append(sums / torch.bincount(batch.batch)[:, None])
    features = {mode: torch.cat(parts) for mode, parts in features.items()}

    def losses():
        result = {name: [0., 0] for name in names}
        with torch.no_grad():
            for group, batch, h in cached:
                pred = model.predict(group, groups=("P",), fields=names,
                                     clean_features=h, clean_batch=batch)
                for name in names:
                    spec = model.definitions[name]["normalization"]
                    target = torch.from_numpy(np.concatenate([s["targets"][name].values for s in group]))
                    valid = torch.from_numpy(np.concatenate([s["targets"][name].valid for s in group]))
                    value = torch_affine(pred[name], spec)
                    loss = F.huber_loss(value[valid], target[valid].clamp(-6., 6.), reduction="sum")
                    result[name][0] += float(loss)
                    result[name][1] += int(valid.sum())
        return {name: total / count if count else float("nan") for name, (total, count) in result.items()}

    started = time.monotonic()
    initial = losses()
    fits = {}
    for name in names:
        head_name, _ = model.selections[name]
        head = model.heads.field_heads[model.heads.keys[head_name]]
        field = model.head_by_name[head_name]
        fits[name] = fit_linear_head(head, features[field.pooling],
            np.concatenate([s["targets"][name].values for s in samples]),
            np.concatenate([s["targets"][name].valid for s in samples]),
            model.definitions[name]["normalization"])
    final = losses()
    rows = {name: dict(fits[name], **reception_result(initial[name], final[name])) for name in names}
    report = {"status": "ACCEPTED" if all(row["passed"] for row in rows.values()) else "RECEPTION_NOT_PASSED",
        "library": options["library"], "wide_manifest": options["wide_manifest"],
        "molecule_indices": chosen.tolist(), "molecules": 64, "encoder": "frozen_random_C1-0_seed0",
        "head_fit": "native_H1_float64_least_squares_converted_to_raw_output",
        "fields": rows, "SASA_source_atom_rows_aligned": atoms, "raw_store_modified": False,
        "job_id": os.environ["SLURM_JOB_ID"], "node": node, "fit_seconds": time.monotonic() - started}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    data.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    print(json.dumps(accept(json.loads(Path(arguments.configuration).read_text())), allow_nan=False))
