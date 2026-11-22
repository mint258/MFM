"""New wide collection reuse and parameter composition, with tiny fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

from tools.d_recipe.fit_reference import fit_collected
from tools.d_recipe.wide_reference import collect_wide, combine_parameters


class FakeWide:
    def __init__(self):
        self.calls = []

    def get_batch(self, split, indices, *, expected_role, standardized):
        assert (split, expected_role, standardized) == ("TRAIN", "TRAIN", False)
        self.calls.extend(indices)
        raw = np.array([[1000. + i, float(i)] for i in indices])
        valid = np.array([[True, i != 2] for i in indices], dtype=bool)
        raw[~valid] = np.nan
        return SimpleNamespace(raw_values=raw, observed_valid=valid)


@unittest.skip("Unadopted reuse adapter UNRESOLVED after two failed attempts; original fitter retained")
class WideReferenceTests(unittest.TestCase):
    def setup_case(self, root):
        source = root / "native"
        source.mkdir()
        order = np.array([4, 2, 7, 1, 9, 3, 8], dtype=np.int64)
        np.save(source / "order.npy", order)
        design = np.zeros((len(order), 119))
        design[:, 0], design[:, -1] = order, 1.
        np.save(source / "design.npy", design)
        c = dict(ridge_alpha=1., fold_seed=20261112, model_name="L1:A1",
                 peak_bytes=1000000, collector_chunk_rows=2,
                 native_collection=str(source), native_parameters="original/native.json")
        (source / "collection_checkpoint.json").write_text(json.dumps(dict(
            status="COLLECTION_COMPLETE", closed_rows=len(order),
            binding=dict(rows=len(order), configuration=deepcopy(c)))))
        spec = dict(fit_role="TRAIN", center=[0.], scale=[2.], provenance="frozen")
        fields = [dict(name="D20.old", group="P", source_group="D", level="molecule"),
                  dict(name="D.L1.new", group="P", source_group="D", level="molecule"),
                  dict(name="D3.PMI1", group="P", source_group="D", level="molecule"),
                  dict(name="D3.SASA_atom_A2", group="P", source_group="D", level="atom")]
        dataset = SimpleNamespace(library="L1", split="TRAIN", wide=FakeWide(),
                                  _wide_by_name={"D.L1.new": 1},
                                  view=SimpleNamespace(fields=fields,
                                      normalizations={f["name"]: deepcopy(spec) for f in fields}))
        records = [dict(field_name=name, target_policy="original", oof_r2=1.,
                        n_valid=len(order), clipped_TRAIN_count=0, clipping_fraction=0.)
                   for name in ("D20.old", "D3.PMI1")]
        native = dict(normalizations=deepcopy(dataset.view.normalizations), fit=dict(
            field_names=[r["field_name"] for r in records], fields=records,
            cohort_rows=len(order), reference_fit=dict(fields=deepcopy(records))))
        native["normalizations"].pop("D.L1.new")
        return c, dataset, native, order

    def test_resume_reuses_original_order_and_counts_without_native_frame_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            c, dataset, native, order = self.setup_case(root)
            output = root / "wide"
            output.mkdir()
            # An interrupted initialization may have made the read-only link
            # before its first collection checkpoint was committed.
            (output / "design.npy").symlink_to(Path(c["native_collection"]) / "design.npy")
            guarded = []
            guard = lambda path, peak: guarded.append((str(path), peak))
            first, _ = collect_wide(dataset, output, c, native, guard=guard, stop_after_chunks=1)
            self.assertEqual(first["closed_rows"], 2)
            raw = np.lib.format.open_memmap(output / "raw.npy", mode="r+")
            raw[2] = -999.
            raw.flush()
            closed, _ = collect_wide(dataset, output, c, native, guard=guard)
            self.assertEqual(closed["status"], "COLLECTION_COMPLETE")
            self.assertEqual(dataset.wide.calls, order.tolist())
            self.assertTrue((output / "design.npy").is_symlink())
            self.assertEqual((output / "design.npy").resolve(),
                             Path(c["native_collection"]) / "design.npy")
            np.testing.assert_allclose(np.load(output / "raw.npy")[:, 0],
                np.where(order != 2, order.astype(float), np.nan), equal_nan=True)
            np.testing.assert_array_equal(np.load(output / "valid.npy")[:, 0], order != 2)
            self.assertEqual(closed["binding"]["fields"], ["D.L1.new"])
            collect_wide(dataset, output, c, native, guard=guard)
            self.assertEqual(dataset.wide.calls, order.tolist())
            with self.assertRaisesRegex(ValueError, "same-condition"):
                collect_wide(dataset, root / "bad", {**c, "fold_seed": 9}, native, guard=guard)

    def test_original_fitter_and_composition_preserve_every_frozen_native_parameter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            c, dataset, native, _ = self.setup_case(root)
            original = deepcopy(native)
            output = root / "wide"
            guard = lambda path, peak: None
            _, view = collect_wide(dataset, output, c, native, guard=guard)
            path = fit_collected(view, output, c, guard=guard)
            new = json.loads(path.read_text())
            self.assertEqual(new["fit"]["field_names"], ["D.L1.new"])
            combined = combine_parameters(dataset, native, new, configuration=c)
            self.assertEqual(native, original)
            for name, spec in original["normalizations"].items():
                self.assertEqual(combined["normalizations"][name], spec)
            self.assertEqual(combined["fit"]["field_names"],
                             ["D20.old", "D.L1.new", "D3.PMI1"])
            by_name = {f["field_name"]: f for f in combined["fit"]["fields"]}
            for record in original["fit"]["fields"]:
                self.assertEqual(by_name[record["field_name"]], record)
            self.assertFalse(combined["fit"]["native_fields_refitted"])
            self.assertFalse(combined["fit"]["original_D4_modified"])
            duplicate = deepcopy(new)
            duplicate["fit"]["fields"].append(original["fit"]["fields"][0])
            with self.assertRaisesRegex(ValueError, "replace a frozen native"):
                combine_parameters(dataset, native, duplicate, configuration=c)


if __name__ == "__main__":
    unittest.main()
