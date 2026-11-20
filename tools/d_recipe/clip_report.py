"""Required D TRAIN clipping report, without fitting or changing any target.

Use the closed A1 cohort and its recorded conformer choices. Molecular raw
values already exist in that collection. Only atomic SASA, which A1 does not
collect, is streamed from the original read-only source through its native
view/normalizer. This is the first clipping report, not a numerical QA pass.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from .fit_reference import _publish, reference_write_guard
from phychem_mfm.phase1.v31_loader import normalize_values

ATOM = "D3.SASA_atom_A2"


def counts(values, valid):
    values, valid = np.asarray(values), np.asarray(valid, dtype=bool)
    return dict(valid=int(valid.sum()), clipped=int((valid & (np.abs(values) > 6.)).sum()))


def standardized(raw, design, specification):
    """Keep native affine precision and the original elemental sum order."""
    spec = dict(specification)
    reference = spec.pop("element_reference", None)
    dtype = np.float64 if spec.get("p_recipe_fitted", False) else np.float32
    value = np.asarray(raw, dtype=dtype).copy()
    if reference is not None:
        offset = np.zeros(len(value), dtype=np.float64)
        for z, coefficient in zip(reference["basis"], reference["coefficients"]):
            offset += design[:, int(z) - 1] * coefficient
        offset += reference.get("intercept", 0.)
        value -= offset.astype(dtype)
    return normalize_values(value[:, None], spec, Z=np.empty(0, dtype=np.int64)).reshape(-1)


def molecular_counts(collection, names, base, transferred, chunk_rows):
    raw, valid, design = [np.load(Path(collection) / name, mmap_mode="r", allow_pickle=False)
                          for name in ("raw.npy", "valid.npy", "design.npy")]
    result = []
    for column, name in enumerate(names):
        row = dict(field_name=name, level="molecule", D_R0=dict(valid=0, clipped=0),
                   D_R1=dict(valid=0, clipped=0))
        for start in range(0, len(raw), chunk_rows):
            stop = start + chunk_rows
            observed = valid[start:stop, column]
            for arm, parameters in (("D_R0", base), ("D_R1", transferred)):
                value = standardized(raw[start:stop, column], design[start:stop], parameters[name])
                summary = counts(value, observed)
                for key in summary:
                    row[arm][key] += summary[key]
        result.append(row)
    return result


class AtomicSource:
    """Reuse native framing, field routing, masks and normalization for SASA."""
    def __init__(self, native):
        from phychem_mfm.phase1.v31_loader import ARRAY_IDS
        self.native = native
        field = next(f for f in native.view.fields if f["name"] == ATOM)
        if field["level"] != "atom" or not field.get("loss_enabled", True):
            raise ValueError("Use the original enabled atomic SASA field")
        native.view.fields = [field]  # only this process-local reporting view
        key = field.get('_location_key', field.get('target_id', field.get('field_key', ATOM)))
        self.array_id = ARRAY_IDS[native.view.locations[key][0][0]]

    def __call__(self, molecule, conformer):
        from phychem_mfm.phase1.v31_loader import decode_mfm4, record_key
        native = self.native
        native._open()
        with native._env.begin(buffers=True) as transaction:
            molecule_payload = transaction.get(record_key("M", molecule))
            conformer_payload = transaction.get(record_key("P" if native.source == "PM7" else "U",
                                                            molecule, conformer))
            if molecule_payload is None or conformer_payload is None:
                raise KeyError((molecule, conformer))
            m = decode_mfm4(molecule_payload, array_ids={1})
            c = decode_mfm4(conformer_payload, array_ids={self.array_id})
        target = native.view.extract(m, c, mask_overrides=native._record_masks.get((molecule, conformer)))[ATOM]
        return counts(target.values, target.valid)


def report(collection, output, configuration, base, transferred, atom_source, *, guard,
           chunk_rows=1024, stop_after_chunks=None):
    collection, output = Path(collection), Path(output)
    source = json.loads((collection / "collection_checkpoint.json").read_text())
    if source["status"] != "COLLECTION_COMPLETE" or source["binding"]["split"] != "TRAIN":
        raise ValueError("The same full TRAIN collection must close before clipping statistics")
    if source["binding"]["configuration"] != configuration:
        raise ValueError("Clipping report configuration differs from the closed collection")
    if base[ATOM] != transferred[ATOM]:
        raise ValueError("A1 must preserve the original atomic SASA normalization")
    names = source["binding"]["fields"]
    binding = dict(collection=str(collection.resolve()), configuration=configuration,
                   fields=names, base_normalizations=base, transferred_normalizations=transferred)
    peak = configuration["peak_bytes"]
    ancestor = output
    while not ancestor.exists():
        ancestor = ancestor.parent
    guard(ancestor, peak)
    output.mkdir(parents=True, exist_ok=True)
    marker, destination = output / "cursor.json", output / "report.json"
    if destination.exists():
        closed = json.loads(destination.read_text())
        if closed["binding"] != binding:
            raise ValueError("Closed clipping report belongs to another condition")
        return closed
    if marker.exists():
        state = json.loads(marker.read_text())
        if state["binding"] != binding:
            raise ValueError("Clipping cursor belongs to another condition")
    else:
        state = dict(binding=binding, atomic_cursor=0, atomic_counts=dict(valid=0, clipped=0),
                     fields=molecular_counts(collection, names, base, transferred, chunk_rows))
        _publish(marker, state, guard, peak)
    choices = np.load(collection / "choices.npy", mmap_mode="r", allow_pickle=False)
    completed = 0
    for start in range(state["atomic_cursor"], len(choices), chunk_rows):
        guard(output, peak)
        stop = min(start + chunk_rows, len(choices))
        for molecule, conformer in choices[start:stop]:
            summary = atom_source(int(molecule), int(conformer))
            for key in summary:
                state["atomic_counts"][key] += summary[key]
        state["atomic_cursor"] = stop
        _publish(marker, state, guard, peak)
        print(json.dumps(dict(stage="D_TRAIN_CLIPPING", closed_rows=stop, total_rows=len(choices))), flush=True)
        completed += 1
        if stop_after_chunks is not None and completed >= stop_after_chunks:
            return state
    atomic = state["atomic_counts"]
    fields = state["fields"] + [dict(field_name=ATOM, level="atom", D_R0=dict(atomic), D_R1=dict(atomic))]
    for field in fields:
        for arm in ("D_R0", "D_R1"):
            count = field[arm]
            count["fraction"] = count["clipped"] / count["valid"] if count["valid"] else None
    result = dict(schema="D_NATIVE_TRAIN_CLIPPING_V1", status="COMPLETE", binding=binding,
        cohort_molecules=len(choices), population="Entire original TRAIN molecule cohort; one original allowed conformer per molecule, reusing frozen A1 choices",
        denominator="Valid molecular scalar leaves; valid atom leaves for atomic SASA",
        threshold="abs(native standardized target)>6, before the loss clamp",
        original_D4_modified=False, stored_values_modified=False, decision_input=False, fields=fields)
    _publish(destination, result, guard, peak)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.configuration).read_text())
    guard = reference_write_guard(config, args.output)
    from phychem_mfm.phase1.p_recipe_data import dataset_configuration
    from phychem_mfm.phase1.v31_loader import MFM4Dataset
    from .dataset import DRecipeDataset
    reader = dataset_configuration(dict(config, label_parameters=None, subset_molecules=None))
    reader.pop("label_parameters", None)
    native = MFM4Dataset(**reader)
    try:
        view = DRecipeDataset(native, d_recipe=dict(config["d_recipe"], label_parameters=None)).view
        base = view.normalizations
        transferred = json.loads((Path(args.collection) / "label_parameters.json").read_text())["normalizations"]
        report(args.collection, args.output, config, base, transferred, AtomicSource(native), guard=guard)
    finally:
        native.close()


if __name__ == "__main__":
    main()
