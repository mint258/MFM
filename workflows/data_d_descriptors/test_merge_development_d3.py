"""Closed component metadata joins only; no arrays, source geometries or labels."""
import copy
import unittest
from unittest.mock import patch

from . import merge_development_d3 as merger
from .test_development_d3 import member


def original_members():
    result = [member(i) for i in range(3)]
    for row in (result[0], result[2]):
        row["dataset"] = row["D3_geometry_reference"]["dataset"] = "expansionrx"
    return result


def component(original, dataset, policy):
    selected = [(index, row) for index, row in enumerate(original) if row["dataset"] == dataset]
    records = []
    for local, (index, source) in enumerate(selected):
        row = copy.deepcopy(source)
        row.update(member_row=local, source_member_row=index, part_row=local, hydrogen_policy=policy,
            D3_ordered_fields=list(merger.D3_NAMES), D3_raw=dict.fromkeys(merger.D3_NAMES, 0.),
            D3_status=dict.fromkeys(merger.D3_NAMES, 1), D3_values="/not-read/" + dataset + ".npy",
            D3_status_store="/not-read/" + dataset + "_status.npy", atomic_SASA_values="/not-read/atoms.npy",
            atomic_SASA_status="/not-read/atom_status.npy", atom_offset=local * 2, atom_count=2,
            work_atom_to_native_source=[0, 1])
        records.append(row)
    manifest = {"schema": merger.SCHEMA, "status": "RAW_COMPLETE", "ordered_fields": list(merger.D3_NAMES),
        "dataset_scope": [dataset], "hydrogen_policy": policy, "source_member_count": len(original),
        "member_count": len(records), "identity": {"dataset_scope": [dataset],
            "source_member_count": len(original), "member_count": len(records)}}
    return "/components/" + dataset + "/manifest.json", manifest, records


class MergeDevelopmentD3Tests(unittest.TestCase):
    def test_closed_disjoint_components_join_in_original_order_without_array_reads(self):
        original = original_members()
        components = [component(original, "qm9", "native_only"),
                      component(original, "expansionrx", "B6_fixed_native_H")]
        before = copy.deepcopy((original, components))
        with patch("builtins.open", side_effect=AssertionError("metadata join must not open arrays")):
            merged, policies = merger.merge_members(original, components)
        self.assertEqual([row["member_uid"] for row in merged], [row["member_uid"] for row in original])
        self.assertEqual([row["member_row"] for row in merged], [0, 1, 2])
        self.assertEqual([row["component_member_row"] for row in merged], [0, 0, 1])
        self.assertEqual([row["part_row"] for row in merged], [0, 0, 1])
        self.assertEqual([row["atom_offset"] for row in merged], [0, 0, 2])
        self.assertEqual(policies, {"qm9": "native_only", "expansionrx": "B6_fixed_native_H"})
        self.assertEqual(merged[2]["D3_raw"], components[1][2][1]["D3_raw"])
        self.assertEqual(merged[2]["D3_values"], components[1][2][1]["D3_values"])
        self.assertEqual(merged[2]["D3_geometry_reference"], original[2]["D3_geometry_reference"])
        self.assertEqual((original, components), before)

    def test_missing_component_or_incomplete_dataset_cannot_be_full_raw_complete(self):
        original = original_members()
        with self.assertRaisesRegex(ValueError, "Incomplete native D3 delivery"):
            merger.merge_members(original, [component(original, "qm9", "native_only")])
        expansion = component(original, "expansionrx", "native_only")
        expansion[2].pop()
        expansion[1]["member_count"] = expansion[1]["identity"]["member_count"] = 1
        with self.assertRaisesRegex(ValueError, "Incomplete component"):
            merger.merge_members(original, [expansion, component(original, "qm9", "native_only")])

    def test_overlap_and_unclosed_component_are_rejected(self):
        original = original_members()
        qm9 = component(original, "qm9", "native_only")
        expansion = component(original, "expansionrx", "native_only")
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            merger.merge_members(original, [qm9, copy.deepcopy(qm9), expansion])
        qm9[1]["status"] = "IN_PROGRESS"
        with self.assertRaisesRegex(ValueError, "Closed scoped"):
            merger.merge_members(original, [qm9, expansion])
        qm9 = component(original, "qm9", "native_only")
        qm9[2].append(copy.deepcopy(qm9[2][0]))
        with self.assertRaisesRegex(ValueError, "overlapping original"):
            merger.merge_members(original, [qm9, expansion])

    def test_exact_original_ids_split_geometry_and_scope_identity_are_preserved(self):
        original = original_members()
        for key, value in (("source_split", "new-split"), ("molecule_id", "new-id"),
                           ("member_index", 100), ("D3_geometry_reference", {})):
            components = [component(original, "qm9", "native_only"), component(original, "expansionrx", "native_only")]
            components[0][2][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "changed original"):
                merger.merge_members(original, components)
        components = [component(original, "qm9", "native_only"), component(original, "expansionrx", "native_only")]
        components[0][1]["identity"]["dataset_scope"] = ["expansionrx"]
        with self.assertRaisesRegex(ValueError, "scope/policy"):
            merger.merge_members(original, components)


if __name__ == "__main__":
    unittest.main()
