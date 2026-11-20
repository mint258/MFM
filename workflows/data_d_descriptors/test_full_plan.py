"""Pure planning/route tests; no numerical fitting, disk admission or jobs."""
import copy
import unittest

from .full_plan import (closed_costs, estimate_peak, existing_d20_parameters,
                        generate_plan, summarize_population_metadata)


def costs():
    return {lib: {"status": "PILOT_COST_COMPLETE_NOT_DELIVERY", "library": lib,
                  "molecules": 5000, "fields": count}
            for lib, count in (("L1", 2), ("L2", 3))}


class FullPlanTests(unittest.TestCase):
    def test_unresolved_is_terminal_but_pending_or_missing_is_not(self):
        values = costs()
        values["L2"] = {"status": "UNRESOLVED", "reason": "timebox"}
        self.assertEqual(closed_costs(values)["L1"]["status"], "READY")
        self.assertEqual(closed_costs(values)["L2"]["reason"], "timebox")
        values["L1"]["status"] = "RUNNING"
        with self.assertRaisesRegex(ValueError, "must close"):
            closed_costs(values)
        with self.assertRaises(KeyError):
            closed_costs({"L1": costs()["L1"]})

    def test_full_dtype_mask_and_auxiliary_budget_are_reported_separately(self):
        result = estimate_peak(rows=1_200_000, fields={"L1": 217, "L2": 1613},
                               panel_bytes_per_row=1800)
        parts = result["components_new_bytes"]
        self.assertEqual(parts["raw_values_F64"], 1_200_000 * 1830 * 8)
        self.assertEqual(parts["explicit_status_u8"], 1_200_000 * 1830)
        self.assertGreater(parts["structures_jsonl_new"], 0)
        self.assertGreater(parts["role_row_index_forecast"], 0)
        self.assertGreater(parts["statistics_atomic_json_temporary"], 0)
        self.assertEqual(result["peak_new_bytes"], sum(parts.values()))
        self.assertGreater(result["peak_new_bytes"], 4 * 2**30)
        self.assertEqual(result["reservation_status"], "FORECAST_ONLY_NOT_RESERVED")
        self.assertFalse(result["floor_and_peer_reservations_included"])

    def test_existing_source_json_is_not_budgeted_as_another_copy(self):
        result = estimate_peak(rows=100, fields={"L1": 2}, panel_bytes_per_row=100,
                               structures_existing_bytes=45678)
        self.assertEqual(result["components_new_bytes"]["structures_jsonl_new"], 0)
        self.assertEqual(result["structures_existing_bytes"], 45678)

    def test_known_d20_uses_normalizer_route_not_raw_series_statistics(self):
        route = {"target_id": "existing-t0", "members": ["D20.ExactMolWt"],
                 "status": "NORMALIZER_AVAILABLE", "normalizer_ready": True,
                 "center": 20.5, "scale": 2.5, "original_loss_enabled": True}
        payload = {"schema": "WINDOW2_D4_MODEL_NORMALIZATION_ROUTES_V1", "datasets": {"P_D": {
            "status": "BOUND_TO_INDEPENDENT_PRODUCER_STATISTICS", "targets": {"existing-t0": route},
            "field_series": {"D20.ExactMolWt": {"series": {"0/raw": {"mean": -999, "std_ddof0": 99}}}}}}}
        fields = {"fields": [{"field_key": "D20.ExactMolWt"}, {"field_key": "P.not_used"}]}
        before = copy.deepcopy(payload)
        result = existing_d20_parameters(payload, fields)
        self.assertEqual(set(result), {"ExactMolWt"})
        self.assertEqual(result["ExactMolWt"]["center"], 20.5)
        self.assertEqual(result["ExactMolWt"]["scale"], 2.5)
        self.assertEqual(result["ExactMolWt"]["fit_role"], "TRAIN")
        self.assertEqual(payload, before)

    def test_route_pending_cannot_acquire_fallback_normalization(self):
        payload = {"schema": "WINDOW2_D4_MODEL_NORMALIZATION_ROUTES_V1", "datasets": {"P_D": {
            "status": "BOUND_TO_INDEPENDENT_PRODUCER_STATISTICS", "targets": {"x": {
                "members": ["D20.ExactMolWt"], "status": "PENDING", "normalizer_ready": False}}}}}
        with self.assertRaisesRegex(ValueError, "not ready"):
            existing_d20_parameters(payload, {"fields": [{"field_key": "D20.ExactMolWt"}]})

    def test_plan_keeps_unresolved_library_out_of_size_and_preserves_cpu_boundary(self):
        measured = costs()
        measured["L2"] = {"status": "UNRESOLVED"}
        pilot = {"corpus": "/source/corpus.json", "geometry_index": "/source/geometry.sqlite",
                 "output": "/share/project/pilot", "reserved_peak_bytes": 4 * 2**30}
        before = copy.deepcopy(pilot)
        result = generate_plan(pilot, measured, {"L1": ["a", "b"]}, {"row_count": 1_200_000},
            run_root="/share/project/full", measured_panel_row_bytes=2000,
            existing_parameters_path="/share/project/config/old.json", workers=4)
        self.assertEqual(result["budget"]["fields"], {"L1": 2})
        self.assertEqual(result["slurm"]["nodelist"], "compute-0-[8-19]")
        self.assertFalse(result["slurm"]["exclusive"])
        self.assertFalse(result["jobs_submitted"])
        self.assertEqual(result["slurm"]["cpus_per_stage"]["produce"], 5)
        self.assertEqual(result["slurm"]["cpus_per_stage"]["population_summary"], 1)
        self.assertIn("MFM_d_recipe", result["slurm"]["recipe_root"])
        self.assertEqual(result["configs"]["finalize"]["workers"], 1)
        self.assertEqual(result["configs"]["produce"]["existing_parameters_json"],
                         {"L1": "/share/project/config/old.json"})
        self.assertEqual(pilot, before)

    def test_false_field_count_or_unknown_row_count_cannot_generate_plan(self):
        pilot = {"corpus": "c", "geometry_index": "g", "output": "p"}
        with self.assertRaisesRegex(ValueError, "field count"):
            generate_plan(pilot, costs(), {"L1": ["a"], "L2": ["b", "c", "d"]}, {"row_count": 5},
                run_root="/share/test", measured_panel_row_bytes=100, existing_parameters_path="/share/old.json")
        with self.assertRaisesRegex(ValueError, "Actual positive"):
            estimate_peak(rows=0, fields={"L1": 2}, panel_bytes_per_row=100)

    def test_population_summary_counts_existing_metadata_without_second_identity_audit(self):
        rows = [{"role": "TRAIN"}, {"role": "VAL"}, {"role": "VAL_DIAGNOSTIC"}]
        references = {"common": "/existing/common.json"}
        result = summarize_population_metadata(rows, references)
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(result["role_counts"], {"TRAIN": 1, "VAL": 1, "VAL_DIAGNOSTIC": 1})
        self.assertFalse(result["independent_identity_audit_performed"])
        self.assertEqual(result["status"], "REQUESTED_COHORT_METADATA_ONLY")
        result["source_references"]["common"] = "changed"
        self.assertEqual(references["common"], "/existing/common.json")


if __name__ == "__main__":
    unittest.main()
