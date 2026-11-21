"""Run only newly introduced D producer and consumer tests on a CPU node."""
import ast
import argparse
import importlib
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-cpu-test", action="store_true")
    arguments = parser.parse_args()
    node = platform.node()
    if (not os.environ.get("SLURM_JOB_ID") and not arguments.native_cpu_test) or not node.startswith("compute-0-") or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19:
        raise RuntimeError("CPU allocation or explicit native short-test mode required")
    data = Path("/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120")
    recipe = Path("/share/home/zixiao/descriptor_analysis/MFM_d_recipe")
    sys.path.insert(0, str(data))
    sys.path.insert(0, str(recipe))
    sys.path.insert(0, str(recipe / "current"))
    sys.path.insert(0, str(recipe / "tools" / "d_recipe"))
    sys.path.append("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps")
    from workflows.data_d_descriptors.environment import main as environment
    report = environment(native_cpu_test=arguments.native_cpu_test)
    missing = [name for name, details in report["modules"].items() if "unavailable" in details]
    if missing:
        raise RuntimeError("Required descriptor/model modules unavailable: " + ", ".join(missing))
    from workflows.data_d_descriptors.pilot import storage_guard
    storage_guard(data, peak_bytes=2**24)
    from workflows.data_v1_final.export.v31_stream_v1.disk_guard import inspect
    local_facts = inspect("/tmp")
    reserve = max(10 * 2**30, math.ceil(.1 * local_facts["total"]))
    def local_headroom():
        facts = os.statvfs("/tmp")
        if facts.f_bavail * facts.f_frsize < reserve + 2**24 or facts.f_favail < 10000:
            raise RuntimeError("Local test-fixture disk reserve unavailable; no new test writes")
    local_headroom()
    identity = "native_" + str(os.getpid()) if arguments.native_cpu_test else os.environ["SLURM_JOB_ID"]
    scratch = Path("/tmp") / ("d_recipe_tests_" + str(os.getuid()) + "_" + identity)
    scratch.mkdir(exist_ok=True)
    tempfile.tempdir = str(scratch)
    for relative in ("pilot.py", "prepare.py", "produce.py", "statistics.py", "storage.py", "existing.py", "zero_scale_amendment.py"):
        path = data / "workflows" / "data_d_descriptors" / relative
        ast.parse(path.read_text(), filename=str(path))
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_loss.py"))
    for name in ("test_statistics", "test_prepare", "test_produce", "test_finalization_continuation", "test_zero_scale_amendment", "test_storage", "test_existing", "test_full_plan", "test_b6_cache", "test_export", "test_prepare_development", "test_prepare_benchmark", "test_development_geometry", "test_development_d3", "test_merge_development_d3", "test_source_smiles"):
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
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_clip_report.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_transfer_diagnostic.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_compare.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_seed_plan.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_descriptor_features.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_dev_descriptor_readouts.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_dev_lightgbm.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_dev_panel_inputs.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_development_panel.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_diagnostics.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_diagnostic_forward.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_diagnostic_statistics.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_layer_features.py"))
    suite.addTests(loader.discover(str(recipe / "tests"), pattern="test_d_recipe_layer_readouts.py"))
    class DiskCheckedResult(unittest.TextTestResult):
        def startTest(self, test):
            local_headroom()
            super().startTest(test)
    result = unittest.TextTestRunner(verbosity=2, resultclass=DiskCheckedResult).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
