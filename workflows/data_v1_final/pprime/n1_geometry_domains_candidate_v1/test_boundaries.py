"""Exactly three new pure methods; no packet/Parquet, UFF, QM or RDKit import."""
import copy
import unittest
from . import contracts as C, alias, identity, domains, planner, orders

def witness():
    return {"molecule_id": "m", "sprime_conf_idx": 17, "seed": 123,
            "full_original_row_sha256": "a" * 64, "geometry_sha256": "b" * 64,
            "atom_order_sha256": "c" * 64,
            "source_locator": {"reference": {"path": "/share/home/zixiao/descriptor_analysis/runs/x/source.parquet",
                                             "bytes": 9_000_000, "sha256": "d" * 64},
                               "source_format": "parquet", "source_row_index": 42,
                               "source_member": None, "source_record_id": "native-r"}}

def final_row():
    return {"molecule_id": "m", "common_population": True, "effective_role": "VAL", "S_conformers": 1,
            "ordinary_physical_ids": [17], "original_generation_once_state": "ABSENT", "source_task_key": None,
            "validated_closed_second_packet": False, "baseline_input_witness_validated": True}

class Boundaries(unittest.TestCase):
    def test_full_baseline_alias_nonzero_and_null_or_locator_mismatch(self):
        a = {**witness(), "producer_geometry_id": "accepted_sprime_source_row:producer"}
        b = {**witness(), "geometry_id": "uff_sprime:final-physical"}
        value = alias.baseline_alias(a, b)
        self.assertEqual(value["sprime_conf_idx"], 17)
        self.assertNotEqual(value["producer_geometry_id"], value["geometry_id"])
        self.assertEqual(value["baseline_storage_copies_added"], 0)
        self.assertEqual(alias.require_bijection([value])["aliases"], 1)
        with self.assertRaises(C.ContractError):
            alias.require_bijection([value, value])
        bad = copy.deepcopy(b); bad["geometry_sha256"] = None
        with self.assertRaises(C.ContractError):
            alias.baseline_alias(a, bad)
        bad = copy.deepcopy(b); bad["source_locator"]["source_row_index"] = 43
        with self.assertRaises(C.ContractError):
            alias.baseline_alias(a, bad)

    def test_append_after_all_sparse_ids_overflow_and_extra_is_base(self):
        assigned = identity.append_extra_id("m", historical_attempted_ids=[0, 88],
                    ordinary_physical_ids=[17], registered_extra_ids=[99], original_n=1)
        self.assertEqual(assigned["sprime_conf_idx"], 100)
        with self.assertRaises(C.ContractError):
            identity.append_extra_id("m", historical_attempted_ids=[C.INT64_MAX],
                    ordinary_physical_ids=[17], registered_extra_ids=[], original_n=1)
        with self.assertRaises(C.ContractError):
            identity.append_extra_id("m", historical_attempted_ids=[True],
                    ordinary_physical_ids=[17], registered_extra_ids=[], original_n=1)
        bound = alias.baseline_alias({**witness(), "producer_geometry_id": "producer"},
                                     {**witness(), "geometry_id": "ordinary"})
        extra = {"molecule_id": "m", "geometry_source": "uff_sprime", "origin": C.EXTRA_NAMESPACE,
                 "geometry_id": "opaque-extra", "native_extra_conformer_id": "n1p2:seed:cid",
                 "baseline_geometry_id": "producer", "baseline_geometry_sha256": "b" * 64,
                 "geometry_sha256": "e" * 64}
        row = identity.extra_base_row(extra, assigned, bound)
        self.assertIsNone(row["parent_geometry_id"])
        self.assertIsNone(row["view_id"])
        self.assertFalse(row["ordinary_sprime_member"])
        self.assertEqual(row["baseline_geometry_id"], "ordinary")
        self.assertEqual(row["identity_namespace"], C.EXTRA_NAMESPACE)

    def test_independent_domains_late_anti_join_and_original_once_namespace(self):
        value = domains.domain_memberships(["baseline"], ["baseline"], ["extra"],
                                           ["extra", "baseline"], None)
        self.assertEqual(value["ordinary_sprime_training"], ["baseline"])
        self.assertEqual(value["pprime_compute_first2"], ["extra", "baseline"])
        self.assertIsNone(value["pprime_training_after_diagnostic"])
        self.assertFalse(domains.diagnostic_eligible(1, 1))
        row = final_row()
        result = planner.classify_final_n1(row)
        self.assertIn("LATE_NONZERO_BASELINE", result["classification"])
        self.assertEqual(result["generation_once_key"], planner.original_n1.task_key("m"))
        consumed = {**row, "original_generation_once_state": "CONSUMED_UNKNOWN",
                    "source_task_key": result["generation_once_key"]}
        self.assertIn("NO_RETRY", planner.classify_final_n1(consumed)["classification"])
        self.assertFalse(planner.classify_final_n1(consumed)["new_generation_or_QM_authorized"])
        self.assertEqual(planner.census_partition([row])["observed_input_molecules"], 1)
        with self.assertRaises(C.ContractError):
            planner.census_partition([row, row])
        self.assertIs(orders.stable_key, orders.original_selection.stable_key)
        self.assertIs(orders.conformer_orders, orders.original_selection.conformer_orders)
        self.assertEqual(orders.stable_key(20261025, "m", "uff_sprime", 17),
                         orders.original_selection.stable_key(20261025, "m", "uff_sprime", 17))
        self.assertFalse(C.EXECUTION_IMPLEMENTED)
