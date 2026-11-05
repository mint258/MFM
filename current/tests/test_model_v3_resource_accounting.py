import importlib.util
from pathlib import Path

import pytest


def helper():
    path = Path(__file__).absolute().parents[2] / "tools/model_v3/runtime_monitor.py"
    spec = importlib.util.spec_from_file_location("model_v3_monitor_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_owned_accounting_includes_dirs_and_allows_pinned_internal_dangling_sdk_links(tmp_path):
    monitor = helper()
    before = monitor.owned_output_bytes(tmp_path)
    run = "offline-run-20261025_120000-abcdefgh"
    wandb = tmp_path / "wandb"
    wandb.mkdir()
    (tmp_path / "row.json").write_text("{}")
    (wandb / "latest-run").symlink_to(run)
    (wandb / "debug.log").symlink_to(run + "/logs/debug.log")
    assert monitor.owned_output_bytes(tmp_path) > before + 2
    logs = wandb / run / "logs"
    logs.mkdir(parents=True)
    (logs / "debug-core.log").symlink_to("../../../cache/wandb/logs/core-debug-20261025_120000.log")
    assert monitor.owned_output_bytes(tmp_path) > before + 2


def test_output_accounting_rejects_escaping_links_and_hardlinks(tmp_path):
    monitor = helper()
    (tmp_path / "external").symlink_to("../../outside")
    with pytest.raises(ValueError):
        monitor.owned_output_bytes(tmp_path)
    hard = tmp_path / "hardcase"
    hard.mkdir()
    source = tmp_path / "outside_source"
    source.write_text("same inode")
    (hard / "alias").hardlink_to(source)
    with pytest.raises(ValueError, match="hard link"):
        monitor.owned_output_bytes(hard)


@pytest.mark.parametrize("kind", ["arbitrary_internal", "internal_chain", "escaping_ancestor"])
def test_only_explicit_sdk_links_and_ordinary_target_ancestors_are_allowed(tmp_path, kind):
    monitor = helper()
    run = "offline-run-20261025_120000-abcdefgh"
    wandb = tmp_path / "wandb"
    wandb.mkdir()
    if kind == "arbitrary_internal":
        (tmp_path / "regular").write_text("x")
        (tmp_path / "arbitrary").symlink_to("regular")
    elif kind == "internal_chain":
        (tmp_path / "regular_directory").mkdir()
        (wandb / run).symlink_to("../regular_directory")
        (wandb / "latest-run").symlink_to(run)
    else:
        logs = wandb / run / "logs"
        logs.mkdir(parents=True)
        (tmp_path / "cache").symlink_to(tmp_path.parent)
        (logs / "debug-core.log").symlink_to("../../../cache/wandb/logs/core-debug-20261025_120000.log")
    with pytest.raises(ValueError):
        monitor.owned_output_bytes(tmp_path)


def test_trace_export_has_hard_file_budget_and_restores_limit(tmp_path):
    monitor = helper()
    import resource
    previous = resource.getrlimit(resource.RLIMIT_FSIZE)
    class Trace:
        def export_chrome_trace(self, path):
            assert resource.getrlimit(resource.RLIMIT_FSIZE)[0] <= 64 * 1024
            Path(path).write_text("bounded trace")
    result = monitor.bounded_trace_export(Trace(), tmp_path / "trace.json", output_root=tmp_path,
                                         output_budget_bytes=64 * 1024, reserve_bytes=1024)
    assert result["output_bytes_after_trace"] < 64 * 1024
    assert resource.getrlimit(resource.RLIMIT_FSIZE) == previous
