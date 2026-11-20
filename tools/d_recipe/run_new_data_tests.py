"""Run only newly introduced D producer and consumer tests on a CPU node."""
import ast
import importlib
import os
from pathlib import Path
import platform
import sys
import tempfile
import unittest


def main():
    node = platform.node()
    if not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-") or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19:
        raise RuntimeError("Allocated CPU node required")
    data = Path("/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120")
    recipe = Path("/share/home/zixiao/descriptor_analysis/MFM_d_recipe")
    sys.path.insert(0, str(data))
    sys.path.insert(0, str(recipe))
    sys.path.insert(0, str(recipe / "current"))
    sys.path.insert(0, str(recipe / "tools" / "d_recipe"))
    from workflows.data_d_descriptors.environment import main as environment
    report = environment()
    missing = [name for name, details in report["modules"].items() if "unavailable" in details]
    if missing:
        raise RuntimeError("Required descriptor/model modules unavailable: " + ", ".join(missing))
    from workflows.data_d_descriptors.pilot import storage_guard
    storage_guard(data, peak_bytes=2**24)
    scratch = data / ("test_tmp_" + os.environ["SLURM_JOB_ID"])
    scratch.mkdir(exist_ok=True)
    tempfile.tempdir = str(scratch)
    for relative in ("pilot.py", "prepare.py", "produce.py", "statistics.py", "storage.py", "existing.py"):
        path = data / "workflows" / "data_d_descriptors" / relative
        ast.parse(path.read_text(), filename=str(path))
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_loss.py"))
    for name in ("test_statistics", "test_prepare", "test_produce", "test_storage", "test_existing", "test_full_plan", "test_b6_cache", "test_export", "test_prepare_development", "test_prepare_benchmark", "test_development_geometry"):
        module = importlib.import_module("workflows.data_d_descriptors." + name)
        suite.addTests(loader.loadTestsFromModule(module))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_wide_store.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_element_reference.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_dataset.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_model.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_training.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_train.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_statistics.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_resources.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_acceptance.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_protocol.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_evaluate.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_fit_reference.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_compare.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_seed_plan.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_descriptor_features.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_dev_descriptor_readouts.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_diagnostics.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_diagnostic_forward.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_diagnostic_statistics.py"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
