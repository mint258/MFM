"""Three synthetic methods; no RDKit import, DATA, fixture execution or QM here."""
import unittest
from . import contracts as C, selection, projection, census

KEY1 = "AAAAAAAAAAAAAA-BBBBBBBBBB-C"
KEY2 = "DDDDDDDDDDDDDD-EEEEEEEEEE-F"


def source():
    row = {k: None for k in C.REQUIRED_IDENTITY_COLUMNS}
    row.update(molecule_id="m1", record_id="r1", smiles="  F[C@H](Cl)Br  ",
               canonical_smiles="FC(Cl)Br", isomeric_smiles="F[C@H](Cl)Br",
               stored_inchikey=KEY1, reidentified_inchikey=KEY2,
               QC_key_reproduction_mismatch_accepted_difference=True,
               QC_other_layer_accepted_difference=True)
    return row


def feature(graph="F[C@H](Cl)Br", key=KEY1):
    return {"variant_id": graph, "status": "FEATURES_DERIVED", "error": None,
            "features": {"cid": None, "ordinal": 0, "source_smiles": graph,
                         "reasons": [], "isomeric_smiles": graph, "full_key": key,
                         "wp5_key": key[:14] + ":" + key[-1], "ecfp4_2048_hex": "00" * 256,
                         "generic_murcko": "", "generic_ring_systems": ["C1CC1", "C1CC1"]}}


class Boundaries(unittest.TestCase):
    def test_creator_selector_and_accepted_key_difference_not_exclusion(self):
        row = source()
        selected = selection.select(row)
        self.assertEqual(selected["source_smiles_for_original_template"], "F[C@H](Cl)Br")
        self.assertNotEqual(selected["source_smiles_for_original_template"], row["canonical_smiles"])
        self.assertEqual(selected["original_identity"], row)
        self.assertIsNone(selected["cid"])
        self.assertFalse(selected["geometry_reidentified_graph_selected"])
        result = projection.reduce_variants("m1", "TRAIN", 17, [feature()])
        self.assertEqual(result["status"], "UNIQUE_GRAPH_PROJECTION_CANDIDATE")
        self.assertFalse(result["historical_keys_or_accepted_differences_used_as_exclusion"])
        with self.assertRaises(C.ContractError):
            selection.select({**row, "assay_target": 1.0})

    def test_multiple_graphs_and_unknown_are_retained_hold(self):
        rows = [feature(), feature("F[C@@H](Cl)Br", KEY2)]
        result = projection.reduce_variants("m1", "VAL", 2, rows)
        self.assertEqual(result["graph_variant_results"], rows)
        self.assertIsNone(result["strict5_projection"])
        self.assertIn("MULTIPLE_LEGITIMATE_CANONICAL_GRAPHS_OR_FULL_KEYS", result["hold_reasons"])
        unresolved = {"variant_id": "v3", "status": "FEATURE_COMPUTE_UNRESOLVED",
                      "features": None, "error": {"type": "ValueError", "message": "synthetic"}}
        result = projection.reduce_variants("m1", "VAL", 3, rows + [unresolved])
        self.assertEqual(len(result["graph_variant_results"]), 3)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["representative_graph_chosen"])
        self.assertFalse(result["fingerprints_merged"])

    def test_molecular_census_and_exact5_acyclic_ring_presence_contract(self):
        a, b = census.Census(), census.Census()
        for obj in (a, b):
            obj.add("m1", "TRAIN", 23)
            obj.add("m2", "VAL", 7)
        census.require_same_membership(a.result(), b.result())
        self.assertEqual(a.result()["molecules"], 2)
        with self.assertRaises(C.ContractError):
            a.add("m2", "VAL", 7)
        c = census.Census()
        c.add("m1", "VAL", 23)
        c.add("m2", "TRAIN", 7)
        with self.assertRaises(C.ContractError):
            census.require_same_membership(b.result(), c.result())
        p = projection.reduce_variants("m1", "TRAIN", 23, [feature()])["strict5_projection"]
        self.assertEqual(set(p), C.PROJECTION_FIELDS)
        self.assertEqual(p["generic_murcko"], "")
        self.assertEqual(p["generic_ring_systems"], ["C1CC1", "C1CC1"])
        # The existing reference consumer applies set-presence per MID; this
        # candidate preserves the original list and does not clone that math.
        self.assertFalse(C.EXECUTION_IMPLEMENTED)
        big = {"path": "/share/home/zixiao/descriptor_analysis/runs/x/data.parquet",
               "bytes": 1_242_386_629, "sha256": "a" * 64}
        self.assertEqual(C.data_reference(big), big)
        with self.assertRaises(C.ContractError):
            C.reference(big, small=True)

