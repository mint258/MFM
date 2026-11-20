"""Taskbook boundary decisions, without training or resampling."""
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "current"))
from tools.d_recipe.protocol import (confirmed_win, decide, deletion_eligible,
                                     native_block_anchor, select_library)


class ProtocolTests(unittest.TestCase):
    def test_negative_ci_is_loss_even_below_effect_threshold(self):
        control = np.full(1000, .4)
        result = decide(.399, .4, control - .001, control)
        self.assertEqual(result["verdict"], "LOSS")
        self.assertGreater(result["tau"], abs(result["delta"]))
        self.assertFalse(result["seed1_required"])

    def test_positive_ci_needs_effect_threshold_and_strict_lower_bound(self):
        control = np.zeros(1000)
        self.assertEqual(decide(.009, 0., control + .009, control)["verdict"], "TIE")
        self.assertEqual(decide(.01, 0., control + .01, control)["verdict"], "WIN")
        self.assertEqual(decide(.02, 0., control, control)["verdict"], "TIE")
        with self.assertRaisesRegex(ValueError, "1000"):
            decide(.02, 0., control[:-1], control[:-1])

    def test_both_seeds_must_individually_win(self):
        self.assertFalse(confirmed_win({0: {"verdict": "WIN"}}))
        self.assertFalse(confirmed_win({0: {"verdict": "WIN"}, 1: {"verdict": "TIE"}}))
        self.assertTrue(confirmed_win({0: {"verdict": "WIN"}, 1: {"verdict": "WIN"}}))
        with self.assertRaisesRegex(ValueError, "does not authorize"):
            confirmed_win({0: {"verdict": "TIE"}, 1: {"verdict": "WIN"}})

    def test_library_selection_waits_for_conditional_runs_and_keeps_cheaper_tie(self):
        win = {0: {"verdict": "WIN"}, 1: {"verdict": "WIN"}}
        tie = {0: {"verdict": "TIE"}}
        self.assertIsNone(select_library({0: {"verdict": "WIN"}}, tie)["library"])
        self.assertEqual(select_library(tie, tie)["library"], "D20")
        self.assertEqual(select_library(win, tie)["library"], "L1")
        self.assertIsNone(select_library(win, win)["library"])
        self.assertIsNone(select_library(win, win, l2_against_l1={0: {"verdict": "WIN"}})["library"])
        self.assertEqual(select_library(win, win, l2_against_l1=tie)["library"], "L1")
        self.assertEqual(select_library(win, win, l2_against_l1=win)["library"], "L2")

    def test_native_anchor_counts_sasa_as_one_field_and_honors_disabled_fields(self):
        fields = [dict(name="D20." + str(i), group="D", level="molecule") for i in range(17)]
        fields += [dict(name="D3." + str(i), group="D", level="molecule") for i in range(6)]
        fields += [dict(name="D3.SASA_atom_A2", group="D", level="atom")]
        fields += [dict(name="D20.MolMR", group="D", level="molecule", loss_enabled=False)]
        fields += [dict(name="P.energy", group="P", level="molecule")]
        result = native_block_anchor(fields)
        self.assertEqual(result["total_enabled_fields"], 24)
        self.assertEqual(result["block_weights"], dict(graph_2d=17/24, molecule_3d=6/24, atom_sasa=1/24))

    def test_deletion_uses_its_explicit_ci_condition(self):
        self.assertTrue(deletion_eligible(dict(ci_lower=-.01, ci_upper=.01)))
        self.assertFalse(deletion_eligible(dict(ci_lower=-.02, ci_upper=-.001)))
        self.assertFalse(deletion_eligible(dict(ci_lower=.001, ci_upper=.02)))


if __name__ == "__main__":
    unittest.main()
