"""Pure source-member joins and graph-only composition; no model forwards."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "current"))
sys.path.insert(0, str(ROOT / "tools" / "d_recipe"))
from phychem_mfm.phase1.v3_dev_evaluation import TaskMolecule
from descriptor_features import D3_FEATURE_FIELDS, D3_ORDERED_FIELDS, DownstreamFeatureBatch
from dev_panel_inputs import composition_rows, task_descriptors


def task_row(uid):
    # Native geometry contains one heavy atom and no H; it is deliberately not
    # a complete source-graph element count for the composition reference.
    return TaskMolecule("same-molecule", torch.ones((1, 3), dtype=torch.float32), torch.arange(1),
                        torch.tensor([1.]), torch.tensor([True]), torch.tensor([True]), uid)


def members():
    result = []
    for uid, other, split, value, smiles in (("member-A", "member-B", "TRAIN", 101., "[13CH4]"),
                                            ("member-B", "member-A", "VAL", 202., "[Na+].[Cl-]")):
        result.append(dict(dataset="original-dataset", member_uid=uid, record_id=other,
                           molecule_id="same-molecule", source_split=split, source_smiles=smiles,
                           D3_ordered_fields=list(D3_ORDERED_FIELDS),
                           D3_raw=dict.fromkeys(D3_ORDERED_FIELDS, value),
                           D3_status=dict.fromkeys(D3_ORDERED_FIELDS, 1)))
    return result


class FakeDescriptors:
    def __init__(self, namespaced=True):
        self.membership_reference = dict(member_key="member_uid")
        if namespaced:
            self.membership_reference["dataset_key"] = "dataset"
        self.calls = []

    def get_members(self, requests, *, standardized):
        requests = tuple(requests)
        self.calls.append((requests, standardized))
        metadata = {("original-dataset", row["member_uid"]): row for row in members()}
        selected = []
        for key in requests:
            pair = key if self.membership_reference.get("dataset_key") else ("original-dataset", key)
            selected.append(metadata[pair])
        raw = np.array([[1.] if row["member_uid"] == "member-A" else [2.] for row in selected])
        return DownstreamFeatureBatch(requests, tuple(row["molecule_id"] for row in selected),
                                      tuple(row["source_split"] for row in selected), ("MolWt",),
                                      raw, raw / 2 if standardized else raw,
                                      np.ones(raw.shape, dtype=np.uint8), np.ones(raw.shape, dtype=bool))


class DevelopmentPanelInputTests(unittest.TestCase):
    def test_task_descriptors_use_declared_member_uid_namespace_order_and_repeats(self):
        source = (task_row("member-B"), task_row("member-A"), task_row("member-B"))
        store, source_members = FakeDescriptors(), members()
        original = deepcopy(source_members)
        normalization = {name: dict(fit_role="TRAIN", center=[1.], scale=[2.]) for name in D3_FEATURE_FIELDS}
        batch = task_descriptors(source, "original-dataset", store, source_members,
                                 standardized=True, normalization=normalization)
        self.assertEqual(store.calls, [((("original-dataset", "member-B"),
                                         ("original-dataset", "member-A"),
                                         ("original-dataset", "member-B")), True)])
        # record_id is intentionally swapped in the source metadata. The
        # development member_uid declaration must pick 202,101,202, not its alias.
        np.testing.assert_array_equal(batch.raw_values[:, -6], [202., 101., 202.])
        np.testing.assert_array_equal(batch.values[:, -6], [100.5, 50., 100.5])
        self.assertEqual(batch.source_splits, ("VAL", "TRAIN", "VAL"))
        self.assertEqual(batch.fields, ("MolWt",) + D3_FEATURE_FIELDS)
        self.assertEqual(source_members, original)
        self.assertTrue(all(row.graph_features is None for row in source))

    def test_task_descriptors_support_full_string_member_uids_without_inventing_dataset_prefix(self):
        source = (task_row("member-A"),)
        store = FakeDescriptors(namespaced=False)
        batch = task_descriptors(source, "original-dataset", store, members(),
                                 standardized=False, normalization=None)
        self.assertEqual(store.calls, [(("member-A",), False)])
        self.assertEqual(batch.member_uids, ("member-A",))
        self.assertEqual(batch.raw_values[0, -6], 101.)

    def test_missing_source_uid_wrong_namespace_and_molecule_mismatch_are_not_guessed(self):
        store = FakeDescriptors()
        with self.assertRaisesRegex(ValueError, "source_member_uid is required"):
            task_descriptors((replace(task_row("member-A"), source_member_uid=""),),
                             "original-dataset", store, members(), standardized=False, normalization=None)
        self.assertEqual(store.calls, [])
        with self.assertRaises(KeyError):
            task_descriptors((task_row("member-A"),), "different-dataset", store, members(),
                             standardized=False, normalization=None)
        with self.assertRaisesRegex(ValueError, "molecule IDs differ"):
            task_descriptors((replace(task_row("member-A"), molecule_uid="wrong-molecule"),),
                             "original-dataset", store, members(), standardized=False, normalization=None)
        wrong = members()
        wrong[0]["source_split"] = "VAL"
        with self.assertRaisesRegex(ValueError, "molecule/split"):
            task_descriptors((task_row("member-A"),), "original-dataset", store, wrong,
                             standardized=False, normalization=None)

    def test_composition_uses_each_original_graph_hydrogen_salts_and_isotopes_not_native_z(self):
        source = (task_row("member-B"), task_row("member-A"), task_row("member-B"))
        source_members = members()
        before = deepcopy(source_members)
        transformed = composition_rows(source, "original-dataset", source_members)
        self.assertEqual(len(transformed), len(source))
        salt, methane = transformed[0].graph_features, transformed[1].graph_features
        self.assertEqual(tuple(methane.shape), (119,))
        self.assertEqual(methane[0].item(), 4.)  # graph's [13CH4], not one native coordinate
        self.assertEqual(methane[5].item(), 1.)
        self.assertEqual(methane[-1].item(), 1.)
        self.assertEqual(salt[0].item(), 0.)
        self.assertEqual(salt[10].item(), 1.)  # sodium retained; no salt stripping
        self.assertEqual(salt[16].item(), 1.)  # chlorine retained
        self.assertEqual(salt[-1].item(), 2.)
        self.assertTrue(torch.equal(transformed[0].graph_features, transformed[2].graph_features))
        for old, new in zip(source, transformed):
            self.assertIs(old.h0, new.h0)
            self.assertIs(old.source_atom_ids, new.source_atom_ids)
            self.assertIs(old.targets, new.targets)
            self.assertIs(old.supervision_mask, new.supervision_mask)
            self.assertIs(old.candidate_mask, new.candidate_mask)
            self.assertEqual(old.source_member_uid, new.source_member_uid)
            self.assertEqual(old.molecule_uid, new.molecule_uid)
            self.assertIsNone(old.graph_features)
        self.assertEqual(source_members, before)
        deuterated = members()[:1]
        deuterated[0]["source_smiles"] = "[2H]O[H]"
        water = composition_rows((task_row("member-A"),), "original-dataset", deuterated)[0].graph_features
        self.assertEqual(water[0].item(), 2.)
        self.assertEqual(water[7].item(), 1.)
        self.assertEqual(water[-1].item(), 1.)

    def test_composition_missing_source_graph_or_original_member_binding_is_unresolved(self):
        source = (task_row("member-A"),)
        for smiles in (None, ""):
            metadata = members()
            metadata[0]["source_smiles"] = smiles
            with self.subTest(smiles=smiles), self.assertRaisesRegex(ValueError, "UNRESOLVED.*source_smiles"):
                composition_rows(source, "original-dataset", metadata)
        wrong_namespace = members()
        wrong_namespace[0]["dataset"] = "different-dataset"
        with self.assertRaisesRegex(ValueError, "UNRESOLVED.*metadata is missing"):
            composition_rows(source, "original-dataset", wrong_namespace)
        wrong_identity = members()
        wrong_identity[0]["molecule_id"] = "different-molecule"
        with self.assertRaisesRegex(ValueError, "member/molecule identity differs"):
            composition_rows(source, "original-dataset", wrong_identity)

    def test_composition_rejects_conflicting_graphs_without_selecting_a_representative(self):
        metadata = members()
        conflicting = deepcopy(metadata[0])
        conflicting["source_smiles"] = "CC"
        with self.assertRaisesRegex(ValueError, "Conflicting original development member graph"):
            composition_rows((task_row("member-A"),), "original-dataset", metadata + [conflicting])


if __name__ == "__main__":
    unittest.main()
