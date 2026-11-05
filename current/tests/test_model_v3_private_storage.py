import importlib.util
import os
from pathlib import Path
import socket

import pytest


def helper():
    path = Path(__file__).absolute().parents[2] / "tools/model_v3/private_runtime_storage.py"
    spec = importlib.util.spec_from_file_location("model_v3_private_storage_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def root(module, path, kind="task_scratch"):
    path.mkdir(mode=0o700)
    return {**module._identity(path), "kind": kind, "reused": False}


def test_private_storage_counts_socket_and_records_sampled_growth(tmp_path, monkeypatch):
    module = helper()
    binding = root(module, tmp_path / "scratch")
    scratch = Path(binding["path"])
    (scratch / "compiler").mkdir(mode=0o700)
    (scratch / "compiler/kernel.bin").write_bytes(b"x" * 1024)
    monkeypatch.chdir(scratch)
    with socket.socket(socket.AF_UNIX) as endpoint:
        endpoint.bind("sdk.sock")
        observed = module.sampled_storage_bytes([binding])
        expected = sum(path.lstat().st_size for path in (scratch, *scratch.rglob("*")))
        assert observed["bytes"] == expected and observed["entries"] == 3
        (scratch / "compiler/kernel2.bin").write_bytes(b"y" * 2048)
        assert module.sampled_storage_bytes([binding])["bytes"] >= observed["bytes"] + 2048


@pytest.mark.parametrize("entry_kind", ["symlink", "hardlink", "fifo", "directory_link"])
def test_private_storage_rejects_unowned_layout_types_and_links(tmp_path, entry_kind):
    module = helper()
    binding = root(module, tmp_path / "scratch")
    scratch = Path(binding["path"])
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    if entry_kind == "symlink":
        (scratch / "bad").symlink_to(outside)
    elif entry_kind == "hardlink":
        os.link(outside, scratch / "bad")
    elif entry_kind == "fifo":
        os.mkfifo(scratch / "bad")
    else:
        (scratch / "real").mkdir()
        (scratch / "bad").symlink_to(scratch / "real", target_is_directory=True)
    with pytest.raises(ValueError, match="entry/link"):
        module.sampled_storage_bytes([binding])


def test_cache_census_refuses_sockets_and_root_identity_replacement(tmp_path, monkeypatch):
    module = helper()
    binding = root(module, tmp_path / "cache", "compiler_cache")
    monkeypatch.chdir(tmp_path / "cache")
    with socket.socket(socket.AF_UNIX) as endpoint:
        endpoint.bind("sdk.sock")
        with pytest.raises(ValueError, match="entry/link"):
            module.sampled_storage_bytes([binding])
    # Keep the old directory as evidence; a new directory at the same name has
    # a different inode and cannot inherit the previous measurement authority.
    Path(binding["path"]).rename(tmp_path / "original_cache")
    Path(binding["path"]).mkdir(mode=0o700)
    with pytest.raises(ValueError, match="identity changed"):
        module.sampled_storage_bytes([binding])


def test_scratch_requires_exact_current_job_path_and_fresh_root(tmp_path, monkeypatch):
    module = helper()
    monkeypatch.setenv("SLURM_JOB_ID", "1234567")
    with pytest.raises(ValueError, match="exactly"):
        module.PrivateStorage(tmp_path / "mv3n_1234567", budget_bytes=32 * 1024**2)
    with pytest.raises(ValueError, match="exactly"):
        module.PrivateStorage("/tmp/mv3n_7654321", budget_bytes=32 * 1024**2)
    monkeypatch.delenv("SLURM_JOB_ID")
    with pytest.raises(ValueError, match="SLURM_JOB_ID"):
        module.PrivateStorage("/tmp/mv3n_1234567", budget_bytes=32 * 1024**2)


def test_storage_receipt_binds_job_environment_and_raw_bytes(tmp_path, monkeypatch):
    module = helper()
    binding = root(module, tmp_path / "scratch")
    context = {"job_id": "1234567", "uid": os.getuid(), "node": socket.gethostname(), "boot_id": "fixture"}
    monkeypatch.setattr(module, "_job_context", lambda: context)
    value = {"schema": module.SCHEMA, **context, "roots": [binding], "environment": {"TMPDIR": binding["path"]}}
    receipt = tmp_path / "storage.json"
    pin = module._write_exclusive(receipt, value)
    monkeypatch.setenv("MODEL_V3_STORAGE_BINDINGS_PATH", str(receipt))
    monkeypatch.setenv("MODEL_V3_STORAGE_BINDINGS_SHA256", pin)
    monkeypatch.setenv("TMPDIR", binding["path"])
    assert module.load_storage_bindings()["receipt_sha256"] == pin
    monkeypatch.setenv("TMPDIR", "/tmp/other")
    with pytest.raises(ValueError, match="environment differs"):
        module.load_storage_bindings()
    receipt.write_text("{}")
    with pytest.raises(ValueError, match="receipt changed"):
        module.load_storage_bindings()


def test_private_storage_fresh_and_reused_cache_keep_initial_bytes_separate(tmp_path, monkeypatch):
    module = helper()
    # Redirect only this fixture's fixed /tmp authority into pytest's fresh
    # directory; production accepts no alternate scratch-parent CLI/env.
    monkeypatch.setattr(module, "TASK_SCRATCH_DIRECTORY", tmp_path)
    monkeypatch.setenv("SLURM_JOB_ID", "1234567")
    cache = tmp_path / "compiler"
    first = module.PrivateStorage(tmp_path / "mv3n_1234567", budget_bytes=32 * 1024**2,
                                  cache_root=cache, cache_key="a" * 64)
    (cache / "inductor/kernel.bin").write_bytes(b"x" * 4096)
    first.sample()
    assert first.observation()["sampled_growth_above_initial_bytes"] >= 4096
    assert first.stop()["exact_peak"] is False
    monkeypatch.setenv("SLURM_JOB_ID", "1234568")
    second = module.PrivateStorage(tmp_path / "mv3n_1234568", budget_bytes=32 * 1024**2,
                                   cache_root=cache, cache_key="a" * 64, reuse_cache=True)
    assert second.bindings["compiler_cache_reused"] is True
    assert second.bindings["initial_bytes"]["root_bytes"][str(cache)] >= 4096
    assert second.observation()["sampled_growth_above_initial_bytes"] == 0
    second.stop()
    monkeypatch.setenv("SLURM_JOB_ID", "1234569")
    with pytest.raises(ValueError, match="marker/key/node"):
        module.PrivateStorage(tmp_path / "mv3n_1234569", budget_bytes=32 * 1024**2,
                              cache_root=cache, cache_key="b" * 64, reuse_cache=True)
