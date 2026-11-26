"""Metadata-only supplemental scope contracts; no P worker import or tensors."""
import unittest
from tools.d_recipe.finetune_entry import validate


class DFinetuneScopeTests(unittest.TestCase):
    def config(self):
        return dict(D_authority="docs/d_recipe/USER_DIRECTIVE_20261123.md",
                    authority="docs/p_recipe/USER_DIRECTIVE_20261122B.md",
                    kind="F", mode="full", task="exp.LogD", seed=0,
                    selection_change_allowed=False,
                    source_binding=dict(pretraining_seed=0, checkpoint="/registered/source.pt",
                                        scope="registered_3M", arm="D-R1", samples=3000000))

    def test_registered_main_and_selected_scaling_endpoints(self):
        c = self.config()
        validate(c)
        c["source_binding"].update(scope="selected_9M_budget_curve", arm="9M-D-final", samples=6000000)
        with self.assertRaisesRegex(ValueError, "scaling directive"):
            validate(c)
        c["scaling_authority"] = "docs/d_recipe/USER_DIRECTIVE_20261123B.md"
        validate(c)

    def test_unregistered_arm_seed_mode_and_decision_use_are_rejected(self):
        for key, value in (("seed", 3), ("mode", "top2"), ("selection_change_allowed", True)):
            c = self.config()
            c[key] = value
            with self.assertRaises(ValueError):
                validate(c)
        c = self.config()
        c["source_binding"]["arm"] = "D-G2"
        with self.assertRaisesRegex(ValueError, "outside"):
            validate(c)


if __name__ == "__main__":
    unittest.main()
