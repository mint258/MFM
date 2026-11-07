"""Six incremental boundary fixtures; no real corpus or model import."""
import copy
import unittest
from .sampling_projection_v1 import project_training_sources


def fixture():
    geometries, orders, atoms = [], [], {}
    for src, ids in (("pm7", ["p2", "p1"]), ("uff_sprime", ["u3", "u1", "u2"])):
        for index, gid in enumerate(ids):
            geometries.append({"geometry_id": gid, "molecule_id": "m",
                "geometry_source": src, "native_record_id": str(index),
                "sprime_conf_idx": index if src == "uff_sprime" else None,
                "parent_geometry_id": None, "view_id": None})
            atoms[gid] = 4
        for kind in ("fixed_random", "energy", "diversity"):
            selected = ids if kind == "fixed_random" else list(reversed(ids))
            for rank, gid in enumerate(selected):
                # Earlier original ranks were excluded, so raw rank 0 does not exist.
                orders.append({"molecule_id": "m", "geometry_source": src,
                    "geometry_id": gid, "order_type": kind,
                    "rank": rank + 2, "training_rank": rank})
    return {"effective_role": "TRAIN", "training_geometries": geometries,
        "training_orders": orders, "diagnostic_targets": [
            {"molecule_id": "m", "geometry_source": "pm7", "geometry_id": "held-p"},
            {"molecule_id": "m", "geometry_source": "uff_sprime", "geometry_id": "held-u"}],
        "native_atom_counts": atoms, "group_mask": {"S": True, "D": False, "P": True},
        "family_mask": {"multipole": True}}


class SamplingProjectionTests(unittest.TestCase):
    def test_01_independent_ids_orders_and_retained_energy_minimum(self):
        result = project_training_sources("m", **fixture())
        pm7, uff = (result["source_entries"][s] for s in ("pm7", "uff_sprime"))
        self.assertEqual([v["conformer_id"] for v in pm7["conformers"]], ["p2", "p1"])
        self.assertEqual([v["conformer_id"] for v in uff["conformers"]], ["u3", "u1", "u2"])
        self.assertEqual(pm7["minimum_energy_conformer_id"], "p1")
        self.assertEqual(uff["minimum_energy_conformer_id"], "u2")
        self.assertEqual([v["diversity_order"] for v in uff["conformers"]], [2, 1, 0])
        self.assertEqual(pm7["conformers"][0]["geometry_locators"], [["PM7", "p2"]])
        self.assertEqual(uff["conformers"][0]["geometry_locators"], [["Sprime_UFF", "u3"]])
        self.assertEqual(result["native_conformer_identity"]["p2"]["native_record_id"], "0")
        self.assertEqual(result["native_conformer_identity"]["u3"]["native_record_id"], "0")
        self.assertFalse(result["contract_finalized"])

    def test_02_diagnostic_base_and_child_must_not_leak(self):
        for child in (False, True):
            data = fixture()
            row = data["training_geometries"][0]
            if child:
                row["parent_geometry_id"], row["view_id"] = "held-p", "offeq"
            else:
                row["geometry_id"] = "held-p"
            with self.subTest(child=child), self.assertRaisesRegex(ValueError, "DIAGNOSTIC_GEOMETRY_LEAKED"):
                project_training_sources("m", **data)

    def test_03_training_rank_cannot_be_replaced_by_original_rank(self):
        for corruption in ("gap", "reverse"):
            data = fixture()
            energy = [r for r in data["training_orders"]
                      if r["geometry_source"] == "pm7" and r["order_type"] == "energy"]
            if corruption == "gap":
                energy[0]["training_rank"] = energy[0]["rank"]
                error = "CONTIGUOUS_SOURCE_TRAINING_RANKS"
            else:
                energy[0]["rank"], energy[1]["rank"] = energy[1]["rank"], energy[0]["rank"]
                error = "PRESERVE_ORIGINAL_ORDER"
            with self.subTest(corruption=corruption), self.assertRaisesRegex(ValueError, error):
                project_training_sources("m", **data)

    def test_04_collision_and_cross_source_order_are_rejected(self):
        for corruption in ("collision", "cross_source", "duplicate_physical"):
            data = fixture()
            if corruption == "collision":
                data["training_geometries"][2]["geometry_id"] = "p2"
                error = "COLLISION_ACROSS_SOURCES"
            elif corruption == "cross_source":
                data["training_orders"][0]["geometry_id"] = "u3"
                error = "RETAINED_BASE_IN_OWN_SOURCE"
            else:
                data["training_geometries"][1]["native_record_id"] = "0"
                error = "DUPLICATE_BASE_PHYSICAL_IDENTITY"
            with self.subTest(corruption=corruption), self.assertRaisesRegex(ValueError, error):
                project_training_sources("m", **data)

    def test_05_views_are_not_base_conformers_and_all_orders_required(self):
        data = fixture()
        view = copy.deepcopy(data["training_geometries"][0])
        view.update(geometry_id="p2-off", parent_geometry_id="p2", view_id="offeq")
        data["training_geometries"].append(view)
        result = project_training_sources("m", **data)
        self.assertNotIn("p2-off", result["native_conformer_identity"])
        data["training_orders"].pop()
        with self.assertRaisesRegex(ValueError, "THREE_COMPLETE_SOURCE_ORDERS"):
            project_training_sources("m", **data)

    def test_06_explicit_atoms_exposure_train_role_and_bound_required(self):
        cases = (("effective_role", "VAL", "TRAIN_PROJECTION_ONLY"),
                 ("native_atom_counts", {}, "EXACT_BASE_GEOMETRY_ATOM_COUNTS"),
                 ("group_mask", {"S": True, "D": False, "P": 1}, "BOOLEAN_EXPOSURE"),
                 ("max_rows", 1, "PER_MOLECULE_PROJECTION_CAP"))
        for key, value, error in cases:
            data = fixture(); data[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, error):
                project_training_sources("m", **data)


if __name__ == "__main__":
    unittest.main()
