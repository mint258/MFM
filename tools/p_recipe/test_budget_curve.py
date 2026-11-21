"""Synthetic checks for the newly authorized budget-readout orchestration."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget_curve as curve
from checkpoint_paths import evaluation_checkpoint


class BudgetCurveTests(unittest.TestCase):
    def row(self, arm="T2", samples=1000000):
        return dict(id=arm + "_" + str(samples // 1000000) + "M_L6_H0",
                    arm=arm, samples=samples, layer=6, representation="H0",
                    source_configuration="/original/" + arm + ".json",
                    state="PLANNED_NOT_SUBMITTED")

    def plan(self):
        return dict(authority=curve.AUTHORITY, source_training_budget=9000000,
                    readouts=[self.row(a, n) for a, n in curve.expected_points()],
                    new_training=False, new_seeds=False, normalization_changes=False,
                    stop_or_migrate_training=False)

    def test_exact_22_scope_and_original_endpoint_excluded(self):
        p = self.plan()
        self.assertEqual(len(curve.validate_plan(p)["readouts"]), 22)
        self.assertFalse(any(r["samples"] == 9000000 for r in p["readouts"]))
        self.assertEqual([r["samples"] for r in p["readouts"] if r["arm"] == "T4"],
                         [3000000, 6000000])

    def test_extra_missing_reordered_or_changed_layer_rejected(self):
        for mutate in (lambda p: p["readouts"].pop(),
                       lambda p: p["readouts"].reverse(),
                       lambda p: p["readouts"].append(self.row("T2", 9000000)),
                       lambda p: p["readouts"][0].update(layer=5),
                       lambda p: p.update(new_training=True)):
            p = self.plan()
            mutate(p)
            with self.assertRaises(ValueError):
                curve.validate_plan(p)

    def test_resolve_exact_checkpoint_through_handoff_ancestry(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "native"
            new = Path(tmp) / "sbatch"
            old.mkdir()
            new.mkdir()
            expected = old / "samples_3000000.pt"
            expected.write_bytes(b"synthetic checkpoint")
            (old / "configuration.json").write_text(json.dumps(dict(output=str(old))))
            c = dict(output=str(new), resume_from_output=str(old))
            self.assertEqual(evaluation_checkpoint(c, 3000000), expected)
            with self.assertRaises(FileNotFoundError):
                evaluation_checkpoint(c, 2000000)

    def test_configuration_preserves_source_and_uses_one_exact_checkpoint(self):
        source = dict(run="original_T2", arm="T2", samples=9000000,
                      output="/original", lr=.0003, batch_size=32,
                      resume="old", normalization="frozen_1107")
        before = copy.deepcopy(source)
        calls = []
        def resolver(c, samples):
            calls.append((c, samples))
            return Path("/original/samples_1000000.pt")
        c = curve.make_configuration(source, self.row(), output_root="/new", resolver=resolver)
        self.assertEqual(source, before)
        self.assertEqual(calls, [(source, 1000000)])
        self.assertEqual(c["checkpoint"], "/original/samples_1000000.pt")
        self.assertEqual(c["source_training_budget"], 9000000)
        self.assertEqual(c["evaluation_samples"], [1000000])
        self.assertFalse(c["persist_features"])
        self.assertNotIn("resume", c)
        self.assertEqual(c["statistics_backend"], "slurm_cpu")
        self.assertFalse(c["new_training"])
        self.assertFalse(c["new_seeds"])

    def test_original_9m_endpoint_and_wrong_source_are_rejected(self):
        s = dict(run="T2", arm="T2", samples=9000000)
        for row in (self.row("T2", 9000000), self.row("T1", 1000000)):
            with self.assertRaises(ValueError):
                curve.make_configuration(s, row)

    def test_only_actual_empty_24gib_card_and_16_cpu_allocation(self):
        cards = [dict(uuid="GPU-test", total_mib=24576, used_mib=5)]
        self.assertEqual(curve.validate_card("compute-0-5", "GPU-test", cards, [], 16), cards[0])
        for node, total, contexts, cpus in (
                ("compute-0-20", 24576, [], 16),
                ("compute-0-5", 49140, [], 16),
                ("compute-0-5", 24576, [dict(gpu_uuid="GPU-test", pid=1)], 16),
                ("compute-0-5", 24576, [], 8)):
            with self.assertRaises(ValueError):
                curve.validate_card(node, "GPU-test",
                    [dict(uuid="GPU-test", total_mib=total, used_mib=5)], contexts, cpus)

    def test_missing_driver_card_and_insufficient_memory_are_not_admitted(self):
        for cards in ([], [dict(uuid="GPU-test", total_mib=24576, used_mib=4000)]):
            with self.assertRaises(ValueError):
                curve.validate_card("compute-0-5", "GPU-test", cards, [], 16)

    def test_source_requires_actual_gpu_and_cpu_statistics_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = dict(run="original", samples=9000000, output=tmp)
            ledger = dict(runs=dict(original=dict(state="RUNNING", exit_code="0:0")))
            summary = Path(tmp) / "summary.json"
            summary.write_text(json.dumps(dict(status="COMPLETE", samples=9000000,
                                               statistics_complete=True)))
            self.assertFalse(curve.source_complete(source, ledger))
            ledger["runs"]["original"]["state"] = "COMPLETED"
            self.assertTrue(curve.source_complete(source, ledger))
            summary.write_text(json.dumps(dict(status=curve.WAITING, samples=9000000,
                                               statistics_complete=False)))
            self.assertFalse(curve.source_complete(source, ledger))

    def test_original_deferred_statistics_require_actual_successful_CPU_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=dict(run="original",samples=9000000,output=tmp,statistics_backend="slurm_cpu")
            (Path(tmp)/"summary.json").write_text(json.dumps(dict(
                status="COMPLETE",samples=9000000,statistics_complete=True)))
            ledger=dict(runs=dict(original=dict(state="COMPLETED",exit_code="0:0")),
                        cpu_statistics=dict(original=dict(state="RUNNING",exit_code="0:0")))
            self.assertFalse(curve.source_complete(source,ledger))
            ledger["cpu_statistics"]["original"]["state"]="COMPLETED"
            self.assertTrue(curve.source_complete(source,ledger))
            ledger["cpu_statistics"]["original"]["exit_code"]="1:0"
            self.assertFalse(curve.source_complete(source,ledger))

    def test_live_failed_and_uncertain_readouts_never_double_submit(self):
        for state in ("RUNNING", "PENDING", "FAILED", "SUBMISSION_OBSERVATION_UNCERTAIN"):
            p = self.plan()
            p["readouts"][0].update(configuration="/prepared.json", run="budget_T2_1M")
            ledger = dict(runs=dict(budget_T2_1M=dict(state=state)), cpu_statistics={})
            def read(filename):
                if filename == "/prepared.json":
                    return dict(run="budget_T2_1M", output="/not_an_actual_output")
                return dict(run="original_T2")
            with patch.object(curve, "read", side_effect=read), \
                 patch.object(curve, "source_complete", return_value=True):
                selected = curve.choose_row(p, ledger)
                self.assertEqual((selected["arm"], selected["samples"]), ("T2", 2000000))

    def test_ready_arm_priority_does_not_leave_a_free_card_waiting_for_unfinished_T1(self):
        p = self.plan()
        def read(filename):
            return dict(arm=Path(filename).stem)
        with patch.object(curve, "read", side_effect=read), \
             patch.object(curve, "source_complete", side_effect=lambda source, ledger: source["arm"]=="T4"):
            selected = curve.choose_row(p, dict(runs={}))
            self.assertEqual((selected["arm"], selected["samples"]), ("T4", 3000000))


if __name__ == "__main__":
    unittest.main()
