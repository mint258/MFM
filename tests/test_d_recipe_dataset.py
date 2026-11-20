"""New D target wrapper behavior, fake native reader and tiny actual wide store."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "current"))
from phychem_mfm.phase1.v31_loader import V31Target, normalize_values
from tools.d_recipe.dataset import DRecipeDataset, make_d_dataset
from tools.d_recipe.wide_store import WideDescriptorStore


def parameter(center=0.0, scale=1.0):
    return {"fit_role": "TRAIN", "center": center, "scale": scale}


class Native:
    def __init__(self):
        self.indices = np.array([8, 2])
        self.evaluation = False
        self.calls = []
        self.closed = False
        names = ["D20.ExactMolWt", "D20.TPSA", "D3.PMI1", "D3.SASA_atom_A2", "P.test"]
        fields = [dict(name=name, field_key=name, group="P" if name.startswith("P.") else "D",
                       family="descriptor", level="atom" if "SASA_atom" in name else "molecule",
                       representation="scalar", loss_enabled=True, unit="native") for name in names]
        normalizations = {name: parameter() for name in names}
        schema = {"columns": {"mol_labels": [dict(field_key=name, extensive="extensive") for name in names]},
                  "source_D3_reference": {"sha256": "historical-source-identity"}}
        self.view = SimpleNamespace(fields=fields, schema=schema, normalizations=normalizations, manifest={})

    def __len__(self):
        return len(self.indices)

    def choices(self, molecule):
        self.calls.append(("choices", molecule))
        return np.array([3, 1])

    def read(self, molecule, conformer):
        self.calls.append(("read", molecule, conformer))
        Z = np.array([6, 1, 1])
        targets = {}
        for field in self.view.fields:
            raw = np.array([[2.0], [0.0], [np.nan]]) if field["level"] == "atom" else np.array([[10.0]])
            targets[field["name"]] = V31Target(raw, raw.copy(), ~np.isnan(raw), field["group"],
                field["family"], field["level"], "scalar", True)
        return dict(molecule_index=molecule, conformer_index=conformer, Z=Z, pos=np.arange(9).reshape(3, 3),
                    bonds=np.array([[0, 1], [0, 2]]), targets=targets)

    def close(self):
        self.closed = True


def wide_fixture(root, library="L1", *, new_values=None, new_parameter=None):
    root = Path(root)
    raw = np.array([[999.0, 0.0, np.nan], [999.0, 50.0, np.nan]], dtype=np.float64)
    if new_values is not None:
        raw[:, 1] = new_values
    status = np.array([[1, 1, 0], [1, 1, 2]], dtype=np.uint8)
    np.save(root / "values.npy", raw)
    np.save(root / "status.npy", status)
    rows = [dict(molecule_id="m8", molecule_index=8, split="TRAIN", role="TRAIN", smiles="C"),
            dict(molecule_id="m2", molecule_index=2, split="TRAIN", role="TRAIN", smiles="CC")]
    (root / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    entry = dict(values=str(root / "values.npy"), status=str(root / "status.npy"),
        rows=str(root / "rows.jsonl"), ordered_fields=["ExactMolWt", "new", "missing"],
        enabled_columns=[0, 1, 2], fit_role="TRAIN", producer_alignment_checked=True,
        normalization=[dict(mean=0.0, std_ddof0=1.0), dict(mean=2.0, std_ddof0=2.0),
                       dict(mean=0.0, std_ddof0=1.0)])
    if new_parameter is not None:
        entry["normalization"][1] = dict(new_parameter)
    path = root / "manifest.json"
    path.write_text(json.dumps(dict(schema="D_WIDE_DESCRIPTOR_STORE_V1", libraries={library: entry})))
    return WideDescriptorStore(path, library)


class DatasetTests(unittest.TestCase):
    def test_disabled_factory_is_identical_object(self):
        native = Native()
        self.assertIs(make_d_dataset(native), native)

    def test_native_view_normalizations_and_schema_are_not_mutated(self):
        native = Native()
        before = copy.deepcopy(vars(native.view))
        wrapped = DRecipeDataset(native, d_recipe={"pma_compatibility": True})
        self.assertIsNot(wrapped.view, native.view)
        self.assertEqual(vars(native.view), before)
        self.assertTrue(all(field["group"] == "P" and field["source_group"] == "D"
                            for field in wrapped.view.fields))
        self.assertFalse(any(field["name"].startswith("P.") for field in wrapped.view.fields))
        wrapped.view.normalizations["D20.ExactMolWt"]["center"] = 100
        self.assertEqual(native.view.normalizations["D20.ExactMolWt"]["center"], 0)

    def test_native_sampling_interfaces_order_geometry_and_d3_are_preserved(self):
        native = Native()
        wrapped = DRecipeDataset(native)
        self.assertIs(wrapped.indices, native.indices)
        self.assertEqual(len(wrapped), 2)
        np.testing.assert_array_equal(wrapped.choices(8), [3, 1])
        result = wrapped.read(8, 3)
        self.assertEqual(native.calls, [("choices", 8), ("read", 8, 3)])
        self.assertEqual(result["conformer_index"], 3)
        np.testing.assert_array_equal(result["Z"], [6, 1, 1])
        sasa = result["targets"]["D3.SASA_atom_A2"]
        self.assertEqual(sasa.raw.shape, (3, 1))
        np.testing.assert_array_equal(sasa.valid, [[True], [True], [False]])
        np.testing.assert_array_equal(sasa.raw, result["original_targets"]["D3.SASA_atom_A2"].raw)
        self.assertEqual(result["targets"]["D3.PMI1"].raw[0, 0], 10)
        wrapped.close()
        self.assertTrue(native.closed)

    def test_l1_replaces_2d_block_uses_canonical_shared_d20_and_keeps_d3(self):
        native = Native()
        before = copy.deepcopy(vars(native.view))
        with tempfile.TemporaryDirectory() as root:
            store = wide_fixture(root)
            wrapped = DRecipeDataset(native, d_recipe={"library": "L1", "wide_store": store})
            result = wrapped.read(8, 1)
            self.assertNotIn("D20.TPSA", result["targets"])
            self.assertEqual(result["targets"]["D20.ExactMolWt"].raw[0, 0], 10)
            self.assertIn("D.L1.new", result["targets"])
            self.assertIn("D3.SASA_atom_A2", result["targets"])
            self.assertEqual(vars(native.view), before)
            self.assertEqual(native.calls, [("read", 8, 1)])
            metadata = {field["name"]: field for field in wrapped.view.fields}
            self.assertEqual(metadata["D.L1.new"]["d_block"], "graph_2d")
            self.assertEqual(metadata["D3.PMI1"]["d_block"], "molecule_3d")
            self.assertEqual(metadata["D3.SASA_atom_A2"]["d_block"], "atom_sasa")

    def test_wide_true_zero_missing_and_normalized_values_remain_separate(self):
        with tempfile.TemporaryDirectory() as root:
            wrapped = DRecipeDataset(Native(), d_recipe={"library": "L1", "wide_store": wide_fixture(root)})
            zero = wrapped.read(8, 3)["targets"]["D.L1.new"]
            self.assertEqual(zero.raw.shape, (1, 1))
            self.assertEqual(zero.raw[0, 0], 0)
            self.assertEqual(zero.values[0, 0], -1)
            self.assertTrue(zero.valid[0, 0])
            sample = wrapped.read(2, 1)
            missing = sample["targets"]["D.L1.missing"]
            self.assertFalse(missing.valid[0, 0])
            self.assertTrue(np.isnan(missing.values[0, 0]))
            self.assertEqual(sample["targets"]["D.L1.new"].values[0, 0], 24)

    def test_l2_does_not_cross_map_rdkit_names(self):
        with tempfile.TemporaryDirectory() as root:
            wrapped = DRecipeDataset(Native(), d_recipe={"library": "L2", "wide_store": wide_fixture(root, "L2")})
            result = wrapped.read(8, 1)
            self.assertNotIn("D20.ExactMolWt", result["targets"])
            self.assertEqual(result["targets"]["D.L2.ExactMolWt"].raw[0, 0], 999)

    def test_new_F64_field_is_standardized_before_F32_without_changing_native_parameters(self):
        step = 2.**-30
        values = [1. + step, 1. + 2 * step]
        frozen = dict(mean=1., std_ddof0=step)
        native = Native()
        original_native_parameters = copy.deepcopy(native.view.normalizations)
        with tempfile.TemporaryDirectory() as root:
            store = wide_fixture(root, new_values=values, new_parameter=frozen)
            wrapped = DRecipeDataset(native, d_recipe={"library": "L1", "wide_store": store})
            first, second = wrapped.read(8, 3), wrapped.read(2, 1)
            self.assertEqual(first["targets"]["D.L1.new"].values[0, 0], 1.)
            self.assertEqual(second["targets"]["D.L1.new"].values[0, 0], 2.)
            self.assertEqual(first["targets"]["D.L1.new"].values.dtype, np.float32)
            self.assertEqual(first["original_targets"]["D.L1.new"].raw[0, 0], values[0])
            self.assertEqual(first["original_targets"]["D.L1.new"].raw.dtype, np.float64)
            self.assertEqual(store.metadata["normalization"][1], frozen)
            self.assertFalse(wrapped.view.normalizations["D.L1.new"].get("p_recipe_fitted", False))
            for name in ("D20.ExactMolWt", "D3.PMI1", "D3.SASA_atom_A2"):
                expected = normalize_values(first["original_targets"][name].raw,
                    original_native_parameters[name], Z=first["Z"])
                np.testing.assert_array_equal(first["targets"][name].values, expected)
        self.assertEqual(native.view.normalizations, original_native_parameters)

    def test_a1_uses_actual_native_h_counts_without_changing_raw(self):
        native = Native()
        reference = dict(basis=[1, 6], coefficients=[1.0, 3.0], intercept=1.0)
        spec = dict(parameter(center=1.0, scale=2.0), element_reference=reference)
        wrapped = DRecipeDataset(native, d_recipe={"label_parameters": {
            "normalizations": {"D20.ExactMolWt": spec}}})
        sample = wrapped.read(8, 3)
        target = sample["targets"]["D20.ExactMolWt"]
        # Native Z=[6,H,H]: offset=6; (raw10-offset6-center1)/scale2=1.5.
        self.assertEqual(target.raw[0, 0], 10)
        self.assertEqual(target.values[0, 0], 1.5)
        self.assertEqual(sample["original_targets"]["D20.ExactMolWt"].raw[0, 0], 10)
        self.assertEqual(native.view.normalizations["D20.ExactMolWt"], parameter())

    def test_wide_initialization_reference_is_independent_native_d20_d3_view(self):
        native = Native()
        before = copy.deepcopy(vars(native.view))
        with tempfile.TemporaryDirectory() as root:
            wrapped = DRecipeDataset(native, d_recipe={"library": "L1", "pma_compatibility": True,
                                                       "wide_store": wide_fixture(root)})
            reference = wrapped.view.d_initialization_reference
            expected = [field["name"] for field in native.view.fields if field["group"] == "D"]
            self.assertEqual([field["name"] for field in reference.fields], expected)
            self.assertIn("D20.TPSA", expected)  # Removed from L1's actual fields.
            self.assertNotIn("d_recipe_wide", reference.schema["columns"])
            self.assertTrue(all(field["group"] == "P" and field["source_group"] == "D"
                                for field in reference.fields))
            self.assertEqual(vars(native.view), before)
            reference.normalizations["D20.TPSA"]["center"] = 999
            reference.schema["columns"]["mol_labels"][0]["extensive"] = "changed"
            self.assertEqual(native.view.normalizations["D20.TPSA"]["center"], 0)
            self.assertEqual(wrapped.view.schema["columns"]["mol_labels"][0]["extensive"], "extensive")
            self.assertIsNone(DRecipeDataset(native).view.d_initialization_reference)


if __name__ == "__main__":
    unittest.main()
