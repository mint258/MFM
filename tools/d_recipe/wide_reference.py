"""Explicit wide A1 preparation, reusing the closed native TRAIN collection.

Only new wide fields are collected and fitted. Native element counts, original
cohort order/conformer choice and already frozen native A1 parameters are reused
read-only. The existing F64 fitter, thresholds and residual normalization apply.
UNRESOLVED: two initial adapter tests failed on 2026-11-23. This optional
execution optimization is not adopted. Use the original fit_reference CLI;
this module's CLI is disabled and must not be used for production.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from .fit_reference import _publish, _sync, fit_collected, molecular_fields


SOURCE_KEYS = ("source", "root", "corpus", "training_view", "normalizations")


def new_field_view(dataset, native_parameters):
    """Exclude native fields with a frozen original fit; keep ordered new fields."""
    reused = set(native_parameters["fit"]["field_names"])
    names = molecular_fields(dataset)
    fields = [deepcopy(f) for f in dataset.view.fields
              if f["name"] in names and f["name"] not in reused]
    if not fields or any(not f["name"].startswith("D." + dataset.library + ".")
                         for f in fields):
        raise ValueError("Only enabled new wide molecular fields may be fitted")
    return SimpleNamespace(view=SimpleNamespace(
        fields=fields, normalizations=dataset.view.normalizations))


def collect_wide(dataset, output, configuration, native_parameters, *, guard,
                 stop_after_chunks=None):
    """Resume new 2D raw/mask chunks; never decode native molecular frames."""
    c = deepcopy(configuration)
    if dataset.library not in ("L1", "L2") or dataset.split != "TRAIN":
        raise ValueError("Wide A1 requires the registered TRAIN library")
    source = Path(c["native_collection"]).resolve()
    original = json.loads((source / "collection_checkpoint.json").read_text())
    source_config = original["binding"]["configuration"]
    if (original["status"] != "COLLECTION_COMPLETE"
            or original["closed_rows"] != original["binding"]["rows"]
            or any(c.get(k) != source_config.get(k) for k in SOURCE_KEYS)
            or any(c.get(k) != source_config.get(k)
                   for k in ("ridge_alpha", "fold_seed"))
            or native_parameters["fit"]["cohort_rows"] != original["closed_rows"]):
        raise ValueError("Reuse requires the complete same-condition native TRAIN fit")
    view = new_field_view(dataset, native_parameters)
    names = molecular_fields(view)
    columns = [dataset._wide_by_name[name] for name in names]
    order = np.load(source / "order.npy", mmap_mode="r", allow_pickle=False)
    rows, width = len(order), len(names)
    peak, chunk = c["peak_bytes"], c["collector_chunk_rows"]
    if (type(peak) is not int or peak < rows * width * 9 + 65536
            or type(chunk) is not int or chunk <= 0):
        raise ValueError("Register the new raw/mask arrays and positive chunk size")
    output = Path(output).absolute()
    ancestor = output
    while not ancestor.exists():
        ancestor = ancestor.parent
    guard(ancestor, peak)
    output.mkdir(parents=True, exist_ok=True)
    guard(output, peak)
    binding = dict(configuration=c, fields=list(names), rows=rows,
                   output=str(output), split="TRAIN", native_collection=str(source),
                   cohort_and_geometry="reuse_original_native_collection_read_only")
    marker = output / "collection_checkpoint.json"
    if marker.exists():
        state = json.loads(marker.read_text())
        if state["binding"] != binding:
            raise ValueError("Frozen wide reference condition changed")
        arrays = [np.lib.format.open_memmap(output / name, mode="r+")
                  for name in ("raw.npy", "valid.npy")]
    else:
        arrays = []
        for name, dtype in (("raw.npy", np.float64), ("valid.npy", np.bool_)):
            guard(output, peak)
            arrays.append(np.lib.format.open_memmap(
                output / name, mode="w+", dtype=dtype, shape=(rows, width)))
        # fit_collected only opens this source array with mmap_mode='r'.
        # No native count, order, choice or database copy is produced.
        design_link = output / "design.npy"
        if design_link.is_symlink():
            if design_link.resolve() != source / "design.npy":
                raise ValueError("Preserve the unrelated existing design link")
        elif design_link.exists():
            raise FileExistsError("Preserve the existing design array")
        else:
            design_link.symlink_to(source / "design.npy")
        state = dict(schema="D_WIDE_A1_COLLECTION_V1", binding=binding,
                     closed_rows=0, status="COLLECTING", attempts=[])
        _publish(marker, state, guard, peak)
    if state["closed_rows"] == rows:
        return state, view
    attempt = dict(job_id=os.environ.get("SLURM_JOB_ID"),
                   start_row=state["closed_rows"], state="RUNNING")
    state["attempts"].append(attempt)
    _publish(marker, state, guard, peak)
    raw, valid = arrays
    completed = 0
    for start in range(state["closed_rows"], rows, chunk):
        stop = min(start + chunk, rows)
        guard(output, peak)
        batch = dataset.wide.get_batch("TRAIN", order[start:stop].tolist(),
                                       expected_role="TRAIN", standardized=False)
        raw[start:stop] = batch.raw_values[:, columns]
        valid[start:stop] = batch.observed_valid[:, columns]
        _sync(*arrays)
        state.update(closed_rows=stop,
                     status="COLLECTION_COMPLETE" if stop == rows else "COLLECTING")
        attempt.update(closed_rows=stop,
                       state="COMPLETE" if stop == rows else "RUNNING")
        _publish(marker, state, guard, peak)
        print(json.dumps(dict(stage="D_WIDE_A1_COLLECT", library=dataset.library,
                              closed_rows=stop, total_rows=rows)), flush=True)
        completed += 1
        if stop_after_chunks is not None and completed >= stop_after_chunks:
            break
    return state, view


def combine_parameters(dataset, native, new, *, configuration):
    """Compose frozen field records without refitting any existing native field."""
    names = molecular_fields(dataset)
    old_fields = {f["field_name"]: f for f in native["fit"]["fields"]}
    new_fields = {f["field_name"]: f for f in new["fit"]["fields"]}
    old_reference = {f["field_name"]: f
                     for f in native["fit"]["reference_fit"]["fields"]}
    new_reference = {f["field_name"]: f
                     for f in new["fit"]["reference_fit"]["fields"]}
    if set(old_fields) & set(new_fields) or set(new_fields) - set(names):
        raise ValueError("New wide fit must not replace a frozen native field")
    if set(new["normalizations"]) != set(new_fields):
        raise ValueError("New normalization keys must match only new fitted fields")
    records, references = {}, {}
    for name in names:
        records[name] = deepcopy(old_fields[name] if name in old_fields else new_fields[name])
        references[name] = deepcopy(old_reference[name] if name in old_reference
                                    else new_reference[name])
    result = deepcopy(new)
    result["normalizations"] = deepcopy(native["normalizations"])
    result["normalizations"].update(deepcopy(new["normalizations"]))
    fit = result["fit"]
    fit.update(field_names=list(names), fields=[records[name] for name in names],
               native_parameters_reused=configuration["native_parameters"],
               native_collection_reused=configuration["native_collection"],
               native_fields_refitted=False, original_D4_modified=False)
    fit["reference_fit"]["fields"] = [references[name] for name in names]
    return result


def main():
    raise RuntimeError("UNRESOLVED wide-reference reuse adapter; use original fit_reference")


if __name__ == "__main__":
    main()
