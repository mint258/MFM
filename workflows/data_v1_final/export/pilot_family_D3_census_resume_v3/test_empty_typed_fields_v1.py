"""Missing typed D fields obey the existing explicit masked-NaN contract."""
import copy
import unittest
import numpy as np
from workflows.data_v1_final.export.wire_v1.tests import fixture_mapping
from workflows.data_v1_final.labels.common_train_normalization_day_v1 import bindings as B
from .source import extract, K

def case(values, mask, level="molecule", field_id=3):
    _, mapping, _ = fixture_mapping(kind="scalar", level=level, name="typed_missing", family="D")
    target = mapping["physical_targets"][0]
    target["group"] = "D"
    key = target["members"][0]["field_key"]
    entry = {"field_id": field_id, "field_key": key, "field": {"group": "D"},
             "values_float64": values, "value_mask": mask,
             "source_value_mask": mask, "atom_indices": None,
             "source_reasons": ["SOURCE_CELL_EMPTY"] if not values else [],
             "new_reasons": [], "review_reasons": []}
    compact = B.compact.encode(0, B.TASKS["D20"], [entry])
    recipe = {"input_kind": "ORIGINAL_TYPED_FIELD_ENTRIES",
              "components": {key: {"shape": ["n_atoms"] if level == "atom" else [],
                                   "value": {"column": "field_" + str(field_id)}, "compact": {"field_id": field_id},
                                   "reshape": True, "null_value_policy": "masked_nan"}}}
    return entry, compact, recipe, target, key

def convert(entry, compact, recipe, target):
    return extract([entry], {"compact_mask_json": K.binary_json_dumps(compact)}, {}, 3, recipe, target)

class EmptyTypedFieldsTests(unittest.TestCase):
    def test_empty_scalar_has_declared_shape_nan_and_original_reason(self):
        entry, compact, recipe, target, key = case([], [])
        before = copy.deepcopy(entry)
        arrays, note = convert(entry, compact, recipe, target)
        self.assertEqual(arrays["values/typed_missing"].shape, ())
        self.assertTrue(np.isnan(arrays["values/typed_missing"]).item())
        self.assertEqual(arrays["valid/typed_missing"].item(), 0)
        self.assertEqual(arrays["reason_fields_source/" + key].tolist(),
                         [B.compact.CODE["SOURCE_CELL_EMPTY"]])
        self.assertEqual(entry, before)

    def test_empty_dense_atom_field_uses_full_declared_shape(self):
        entry, compact, recipe, target, key = case([], [], "atom")
        arrays, _ = convert(entry, compact, recipe, target)
        self.assertEqual(arrays["values/typed_missing"].shape, (3,))
        self.assertTrue(np.isnan(arrays["values/typed_missing"]).all())
        self.assertEqual(arrays["valid/typed_missing"].tolist(), [0, 0, 0])

    def test_nonempty_valid_scalar_is_preserved(self):
        entry, compact, recipe, target, _ = case([2.5], [True])
        arrays, _ = convert(entry, compact, recipe, target)
        self.assertEqual(arrays["values/typed_missing"].item(), 2.5)
        self.assertEqual(arrays["valid/typed_missing"].item(), 1)

    def test_empty_field_cannot_be_marked_valid(self):
        entry, compact, recipe, target, _ = case([], [])
        compact["valid_fields"] = B.compact.bits([3])
        compact["all_leaves_valid_fields"] = B.compact.bits([3])
        with self.assertRaisesRegex(ValueError, "NULL_SOURCE_REQUIRES"):
            convert(entry, compact, recipe, target)

    def test_empty_field_requires_existing_explicit_null_policy(self):
        entry, compact, recipe, target, key = case([], [])
        recipe["components"][key].pop("null_value_policy")
        with self.assertRaisesRegex(ValueError, "NULL_SOURCE_REQUIRES"):
            convert(entry, compact, recipe, target)

    def test_nonempty_wrong_shape_is_still_rejected(self):
        entry, compact, recipe, target, _ = case([1., 2.], [False, False])
        with self.assertRaisesRegex(ValueError, "SOURCE_DECLARED_SHAPE_DIFFERS"):
            convert(entry, compact, recipe, target)


    def test_empty_atom_indices_follow_whole_field_nan_policy_without_new_reason(self):
        entry, compact, recipe, target, key = case([], [], "atom", field_id=24)
        entry["atom_indices"] = []
        recipe["components"][key]["atom_indices"] = {"column": "indices_24"}
        before = copy.deepcopy(recipe)
        arrays, _ = convert(entry, compact, recipe, target)
        self.assertEqual(arrays["values/typed_missing"].shape, (3,))
        self.assertTrue(np.isnan(arrays["values/typed_missing"]).all())
        self.assertEqual(arrays["valid/typed_missing"].tolist(), [0, 0, 0])
        self.assertEqual(arrays["reason_fields_source/" + key].tolist(),
                         [B.compact.CODE["SOURCE_CELL_EMPTY"]])
        self.assertEqual(recipe, before)
        self.assertNotIn("missing_atom_reason_code", recipe["components"][key])

    def test_nonempty_partial_atom_subset_still_requires_frozen_missing_reason(self):
        entry, compact, recipe, target, key = case([2.5], [True], "atom", field_id=24)
        entry["atom_indices"] = [1]
        recipe["components"][key]["atom_indices"] = {"column": "indices_24"}
        with self.assertRaisesRegex(ValueError, "MISSING_ATOM_REASON_REQUIRES_EXPLICIT_FROZEN_CODEBOOK_DECISION"):
            convert(entry, compact, recipe, target)


if __name__ == "__main__":
    unittest.main()
