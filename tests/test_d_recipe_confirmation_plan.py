"""Cold D confirmation contracts; no tensors, training or actual filesystem I/O."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.confirmation_plan import plan_confirmation
from tools.d_recipe.train import final_readout


def screening(arm="D-R0"):
    return dict(condition="D", arm=arm, run=arm + "_seed0", seed=0, samples=3_000_000,
        batch_size=32, microbatch_size=32, lr=3e-4, weight_decay=.01,
        betas=[.9, .95], warmup_fraction=.02, distance_bias="C1-0", schedule="cosine",
        components=[] if arm == "D-R0" else ["A1", "B3", "B4"],
        p_recipe={}, clip_calibration=dict(calibration_samples=150000,
            window_start_samples=60000, initial_clip=281.7, quantile=.99),
        output="/screen/" + arm, readout_store="/native_store.json",
        reference_manifest="/random_reference.json", source="PM7",
        d_recipe=dict(enabled=True, library="L1" if arm == "D-L1" else "D20",
            include_3d=True, graph_mask_enabled=False,
            block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1),
            label_parameters="/frozen_TRAIN_parameters.json"))


def frozen(arm="D-R0"):
    return dict(status="FROZEN", recipe_frozen=True, arm=arm,
        library="L1" if arm == "D-L1" else "D20",
        components=[] if arm == "D-R0" else ["A1", "B3", "B4"])


def plan(best=None, baseline=None, selected=None):
    return plan_confirmation(best or frozen(), baseline or screening(), selected,
        output_root="/confirmation", run_prefix="d_")


class ConfirmationPlanTests(unittest.TestCase):
    def test_unfinished_recipe_never_prepares_confirmation(self):
        for changes in (dict(status="RUNNING"), dict(recipe_frozen=False)):
            best = frozen()
            best.update(changes)
            with self.assertRaisesRegex(ValueError, "freeze"):
                plan(best)

    def test_native_selection_requests_only_one_cold_run_and_retains_its_h0(self):
        result = plan()
        self.assertEqual([c["arm"] for c in result["configurations"]], ["9M-D-R0"])
        c = result["configurations"][0]
        self.assertEqual((c["seed"], c["samples"]), (0, 9_000_000))
        self.assertEqual(c["checkpoint_samples"], list(range(1_000_000, 9_000_001, 1_000_000)))
        self.assertEqual(c["evaluation_samples"], [9_000_000])
        self.assertTrue(c["persist_final_features"])
        self.assertFalse(result["jobs_submitted"])

    def test_transferred_selection_keeps_original_baseline_and_only_selected_h0(self):
        original, selected, best = screening(), screening("D-L1"), frozen("D-L1")
        before = deepcopy((original, selected, best))
        result = plan(best, original, selected)
        a, b = result["configurations"]
        self.assertEqual((a["arm"], b["arm"]), ("9M-D-R0", "9M-D-final"))
        self.assertEqual((a["d_recipe"]["library"], b["d_recipe"]["library"]), ("D20", "L1"))
        self.assertFalse(a["persist_final_features"])
        self.assertTrue(b["persist_final_features"])
        self.assertEqual(b["d_recipe"]["label_parameters"], "/frozen_TRAIN_parameters.json")
        self.assertEqual(b["d_recipe"]["scientific_binding"]["samples"], 9_000_000)
        self.assertEqual((original, selected, best), before)

    def test_old_resume_cache_runtime_and_fitted_clip_state_do_not_survive(self):
        selected = screening("D-L1")
        selected.update(resume="/old.pt", resume_samples=1000000,
            resume_from_output="/old", handoff_ack="/ack", diagnostic_feature_root="/3M/cache",
            checkpoint="/3M.pt", features="/old_features", infrastructure_continuation={},
            storage_peak_bytes=1, share_storage_peak_bytes=2, node="old_node", gpu_uuid="old_gpu")
        selected["clip_calibration"].update(threshold=123., fitted=True, observed_updates=2813)
        c = plan(frozen("D-L1"), selected=selected)["configurations"][1]
        for key in ("resume", "resume_samples", "resume_from_output", "handoff_ack",
                "diagnostic_feature_root", "checkpoint", "features", "infrastructure_continuation",
                "storage_peak_bytes", "share_storage_peak_bytes", "node", "gpu_uuid"):
            self.assertNotIn(key, c)
        self.assertTrue(c["resource_admission_pending"])
        self.assertNotIn("fitted", c["clip_calibration"])
        self.assertNotIn("threshold", c["clip_calibration"])
        self.assertEqual(c["clip_calibration"]["window_start_samples"], 60000)

    def test_final_readout_uses_new_endpoint_and_retention_switch(self):
        c = plan(frozen("D-L1"), selected=screening("D-L1"))["configurations"][1]
        readout = final_readout(c, lambda config, samples: "/new/samples_" + str(samples) + ".pt")
        self.assertEqual(readout["checkpoint"], "/new/samples_9000000.pt")
        self.assertEqual(readout["features"], "/confirmation/9M-D-final/training/features_9000000")
        self.assertTrue(readout["persist_features"])
        self.assertNotIn("diagnostic_feature_root", readout)

    def test_only_registered_seed0_screening_sources_can_prepare_confirmation(self):
        for changes in (dict(seed=1), dict(samples=9_000_000), dict(arm="9M-D-final")):
            selected = screening("D-L1")
            selected.update(changes)
            with self.assertRaisesRegex(ValueError, "seed0 3M"):
                plan(frozen("D-L1"), selected=selected)

    def test_frozen_library_or_components_mismatch_is_not_silently_changed(self):
        for changes in (dict(library="L2"), dict(components=[])):
            best = frozen("D-L1")
            best.update(changes)
            with self.assertRaisesRegex(ValueError, "frozen D recipe"):
                plan(best, selected=screening("D-L1"))

    def test_native_baseline_cannot_be_replaced_by_a_transferred_condition(self):
        with self.assertRaisesRegex(ValueError, "original D-R0"):
            plan(baseline=screening("D-R1"))


if __name__ == "__main__":
    unittest.main()
