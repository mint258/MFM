"""Explicit CPU-only full-TRAIN D A1 collection and frozen fitting CLI.

No job submission or computation happens at import. Geometry selection reuses
P fit_labels.py: independent RNGs seeded 20261112 for a TRAIN permutation and
one allowed conformer per molecule. The complete cohort is collected, not a
small exploratory sample. Completed chunk rows, choices and RNG are resumable.
"""
import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import time

import numpy as np

try:
    from .element_reference import element_design, fit_element_reference, make_label_parameters
except ImportError:
    from element_reference import element_design, fit_element_reference, make_label_parameters


COLLECTION_SEED = 20261112  # existing P fit_labels.py geometry-selection rule


def molecular_fields(dataset):
    return tuple(field["name"] for field in dataset.view.fields
                 if field.get("source_group", field["group"]) == "D"
                 and field["level"] in ("molecule", "graph")
                 and field.get("representation", "scalar") == "scalar"
                 and field.get("enabled", True) and field.get("loss_enabled", True))


def _publish(path, value, guard, peak):
    guard(path.parent, peak)
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _sync(*arrays):
    for array in arrays:
        array.flush()
        with Path(array.filename).open("rb") as stream:
            os.fsync(stream.fileno())


def collect(dataset, output, configuration, *, guard, stop_after_chunks=None):
    """Pure collector API; `stop_after_chunks` is only a resumability test hook."""
    config = deepcopy(configuration)
    # These scientific choices have no invented tuning defaults.
    if "ridge_alpha" not in config or "fold_seed" not in config or "model_name" not in config:
        raise ValueError("Explicit ridge_alpha, fold_seed and frozen model_name are required")
    if (not math.isfinite(config["ridge_alpha"]) or config["ridge_alpha"] <= 0
            or type(config["fold_seed"]) is not int or config["fold_seed"] < 0
            or not isinstance(config["model_name"], str) or not config["model_name"]):
        raise ValueError("Finite positive alpha, nonnegative integer fold_seed and model name required")
    peak, chunk_size = config["peak_bytes"], config["collector_chunk_rows"]
    if type(peak) is not int or peak <= 0 or type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("Explicit positive peak_bytes and collector_chunk_rows are required")
    if dataset.split != "TRAIN" or getattr(dataset.native, "evaluation", False):
        raise ValueError("D A1 collector accepts the original TRAIN corpus only")
    names = molecular_fields(dataset)
    if not names:
        raise ValueError("No enabled molecular D scalar fields to collect")
    indices = np.asarray(dataset.indices, dtype=np.int64)
    if len(np.unique(indices)) != len(indices):
        raise ValueError("TRAIN molecular indices are not unique")
    order = np.random.default_rng(COLLECTION_SEED).permutation(indices)
    rows, width = len(order), len(names)
    if peak < rows * (119 * 8 + width * 9 + 24) + 6 * 4096:
        raise ValueError("Declared peak does not cover collection arrays and metadata")
    output = Path(output).absolute()
    ancestor = output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    guard(ancestor, peak)
    output.mkdir(parents=True, exist_ok=True)
    guard(output, peak)
    marker = output / "collection_checkpoint.json"
    binding = dict(configuration=config, fields=list(names), rows=rows,
                   output=str(output), split="TRAIN", collection_seed=COLLECTION_SEED,
                   conformer_policy="existing_P_independent_rng_choice_one_allowed_conformer")
    rng = np.random.default_rng(COLLECTION_SEED)
    if marker.exists():
        state = json.loads(marker.read_text(encoding="utf-8"))
        if state["binding"] != binding:
            raise ValueError("Frozen collector configuration or field population changed")
        saved_order = np.load(output / "order.npy", mmap_mode="r", allow_pickle=False)
        if not np.array_equal(saved_order, order):
            raise ValueError("Original TRAIN membership/order changed during collection")
        rng.bit_generator.state = state["conformer_rng"]
        arrays = [np.lib.format.open_memmap(output / name, mode="r+")
                  for name in ("design.npy", "raw.npy", "valid.npy", "choices.npy")]
    else:
        guard(output, peak)
        with (output / "order.npy").open("wb") as stream:
            np.save(stream, order, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
        arrays = []
        for name, dtype, shape in (("design.npy", np.float64, (rows, 119)),
                                   ("raw.npy", np.float64, (rows, width)),
                                   ("valid.npy", np.bool_, (rows, width)),
                                   ("choices.npy", np.int64, (rows, 2))):
            guard(output, peak)
            arrays.append(np.lib.format.open_memmap(output / name, mode="w+", dtype=dtype, shape=shape))
        state = dict(schema="D_A1_COLLECTION_V1", binding=binding, closed_rows=0,
                     conformer_rng=rng.bit_generator.state, status="COLLECTING", attempts=[])
        _publish(marker, state, guard, peak)
    if state["closed_rows"] == rows:
        return state
    design, raw, valid, choices = arrays
    attempt = dict(job_id=os.environ.get("SLURM_JOB_ID"), node=socket.gethostname(),
                   start_row=state["closed_rows"], state="RUNNING")
    state["attempts"].append(attempt)
    _publish(marker, state, guard, peak)
    started, completed_chunks = time.monotonic(), 0
    for start in range(state["closed_rows"], rows, chunk_size):
        stop = min(start + chunk_size, rows)
        guard(output, peak)
        for row in range(start, stop):
            molecule = int(order[row])
            conformer = int(rng.choice(dataset.choices(molecule)))
            sample = dataset.read(molecule, conformer)
            if sample.get("role", "TRAIN") != "TRAIN" or int(sample["molecule_index"]) != molecule:
                raise ValueError("TRAIN sample role/molecular ID differs from the source choice")
            design[row] = element_design([sample["Z"]])[0]
            originals = sample.get("original_targets", sample["targets"])
            for column, name in enumerate(names):
                observed = originals[name]
                value, mask = np.asarray(observed.raw), np.asarray(observed.valid)
                if value.size != 1 or mask.size != 1:
                    raise ValueError("Molecular scalar source shape differs for " + name)
                raw[row, column] = value.reshape(-1)[0]
                valid[row, column] = mask.reshape(-1)[0]
            choices[row] = molecule, conformer
            # Native MFM4 readers cache decoded molecule records. This
            # collector consumes each molecule once: after copying its values
            # and counts, release only this reader's completed cache entry.
            # Other pre-existing keys/readers and all source arrays stay intact.
            molecule_cache = getattr(dataset.native, "_molecules", None)
            if molecule_cache is not None:
                molecule_cache.pop(molecule, None)
        _sync(*arrays)
        state.update(closed_rows=stop, conformer_rng=rng.bit_generator.state,
                     status="COLLECTION_COMPLETE" if stop == rows else "COLLECTING")
        attempt.update(closed_rows=stop, elapsed_seconds=time.monotonic() - started,
                       state="COMPLETE" if stop == rows else "RUNNING")
        _publish(marker, state, guard, peak)
        print(json.dumps(dict(stage="D_A1_COLLECT", closed_rows=stop, total_rows=rows)), flush=True)
        completed_chunks += 1
        if stop_after_chunks is not None and completed_chunks >= stop_after_chunks:
            break
    return state


def fit_collected(dataset, output, configuration, *, guard):
    output = Path(output).absolute()
    config, peak = configuration, configuration["peak_bytes"]
    state = json.loads((output / "collection_checkpoint.json").read_text(encoding="utf-8"))
    if state["status"] != "COLLECTION_COMPLETE" or state["binding"]["configuration"] != config:
        raise ValueError("Complete same-condition TRAIN collection required before fitting")
    destination = output / "label_parameters.json"
    if destination.exists():
        print(json.dumps(dict(status="ALREADY_FITTED", path=str(destination))), flush=True)
        return destination
    guard(output, peak)
    design, raw, valid = [np.load(output / name, mmap_mode="r", allow_pickle=False)
                          for name in ("design.npy", "raw.npy", "valid.npy")]
    names = state["binding"]["fields"]
    counts = valid.sum(axis=0)
    eligible = [column for column, count in enumerate(counts) if count >= 100000]
    unresolved = [dict(field_name=name, n_valid=int(count), status="UNRESOLVED",
                       target_policy="original", reason="fewer_than_100000_valid_TRAIN_molecules")
                  for name, count in zip(names, counts) if count < 100000]
    base = {field["name"]: deepcopy(field.get("normalization", dataset.view.normalizations[field["name"]]))
            for field in dataset.view.fields}
    if eligible:
        selected_names = [names[column] for column in eligible]
        values, observed = raw[:, eligible], valid[:, eligible]
        roles = ["TRAIN"] * len(design)
        fitted = fit_element_reference(design, values, observed, roles=roles,
                                        ridge_alpha=config["ridge_alpha"], fold_seed=config["fold_seed"],
                                        field_names=selected_names)
        del values, observed  # release advanced-index copies before full-cohort parameter adaptation
    else:
        fitted = dict(schema="D_ELEMENT_REFERENCE_V1", status="UNRESOLVED_NO_ELIGIBLE_FIELDS",
                      fit_role="TRAIN", cohort_rows=len(design), ridge_alpha=config["ridge_alpha"],
                      fold_seed=config["fold_seed"], folds=5, fields=[])
    records = {field["field_name"]: field for field in fitted["fields"]}
    for field in unresolved:
        records[field["field_name"]] = {**field, "oof_r2": None, "coefficients": None,
                                        "fit_status": "UNRESOLVED"}
    # Still report original-target clipping fractions for underpowered fields;
    # this computes no elemental fit and leaves their original D4 specs intact.
    fitted["fields"] = [records[name] for name in names]
    result = make_label_parameters(fitted, design, raw, valid, base,
                                   roles=["TRAIN"] * len(design), model_name=config["model_name"],
                                   field_names=names)
    if not eligible:
        result["fit"]["status"] = "UNRESOLVED_NO_ELIGIBLE_FIELDS"
    result["fit"].update(unresolved_fields=unresolved, collection=str(output / "collection_checkpoint.json"),
                         conformer_policy=state["binding"]["conformer_policy"], collection_seed=COLLECTION_SEED,
                         job_id=os.environ.get("SLURM_JOB_ID"), node=socket.gethostname())
    _publish(destination, result, guard, peak)
    return destination


def reference_write_guard(config, output):
    from workflows.data_d_descriptors.storage import guard
    filesystem = config.get("output_filesystem", "/share")
    if filesystem in ("/lfshome", "node_local") or config.get("peer_storage_guard_root"):
        from tools.d_recipe.resources import admit_output, execution_site
        peak = config["share_storage_peak_bytes"] if filesystem == "/share" else config["peak_bytes"]
        protection = dict(config, output=str(Path(output).resolve()), storage_peak_bytes=peak)
        execution_site(protection, cpu=True)
        def guard(path, peak_bytes):
            return admit_output(protection, path)
    return guard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "fit", "all"))
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or not re.fullmatch(r"compute-0-(?:[89]|1[0-9])", socket.gethostname().split(".")[0]):
        raise RuntimeError("D reference CLI requires an allocated compute-0-8 through compute-0-19 CPU node")
    config = json.loads(Path(arguments.configuration).read_text(encoding="utf-8"))
    repository = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repository))
    sys.path.insert(0, str(repository / "current"))
    sys.path.insert(0, config["data_repository"])
    guard = reference_write_guard(config, arguments.output)
    from phychem_mfm.phase1.p_recipe_data import dataset_configuration
    try:
        from .dataset import DRecipeDataset
    except ImportError:
        from dataset import DRecipeDataset
    # The collector always uses the entire registered TRAIN population and
    # untransformed raw labels; no inherited A1 parameters or subset sampling.
    reader = dataset_configuration({**config, "label_parameters": None, "subset_molecules": None})
    recipe = {**config.get("d_recipe", {}), "label_parameters": None, "split": "TRAIN"}
    dataset = DRecipeDataset(**reader, d_recipe=recipe)
    try:
        if arguments.mode in ("collect", "all"):
            collect(dataset, arguments.output, config, guard=guard)
        if arguments.mode in ("fit", "all"):
            destination = fit_collected(dataset, arguments.output, config, guard=guard)
            print(json.dumps(dict(status="D_A1_FIT_CLOSED", path=str(destination))), flush=True)
    finally:
        dataset.close()


if __name__ == "__main__":
    main()
