"""The taskbook's exact budget CSV is public; adjacent training CSVs stay excluded."""
from pathlib import Path
import runpy
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


class BudgetCurveRepositoryTests(unittest.TestCase):
    def test_only_the_explicitly_authorized_budget_csv_is_allowed(self):
        check = runpy.run_path(str(REPO / "tools/check_repository.py"))["check"]
        allowed = "results/p_recipe/fixed_20261115/confirmation/budget_curve.csv"
        nearby = "results/p_recipe/fixed_20261115/confirmation/raw_training.csv"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/SOURCE_MANIFEST.json").write_text('{"files": []}')
            for name in (allowed, nearby):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("arm,samples,R3_mean\nT2,9000000,0.47\n")
            self.assertEqual(check(root, [allowed], verify_export=False)["status"], "PASS")
            rejected = check(root, [nearby], verify_export=False)
            self.assertEqual(rejected["status"], "FAIL")
            self.assertTrue(any(e["path"] == nearby for e in rejected["errors"]))


if __name__ == "__main__":
    unittest.main()
