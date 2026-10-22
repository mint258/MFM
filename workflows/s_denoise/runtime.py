"""New experiment bindings; all previous S inputs/configurations remain read-only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import sys

PROJECT = Path("/share/home/zixiao/descriptor_analysis")
ROOT = PROJECT / "runs/s_denoise_repair_20261016"
SOURCE = ROOT / "source_v3"
OLD = PROJECT / "runs/sprime_s_convergence_20261013"
ENV_PYTHON = PROJECT / "docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python"
DEPS = PROJECT / "docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".pending")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def old_configuration():
    return json.loads((OLD / "formal_s/B3_seed0_v2.json").read_text())


def setup_imports():
    sys.path[:0] = [str(SOURCE / "current"), str(DEPS), str(OLD / "scripts")]


def assert_allocation(*, gpu=False):
    assert os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID")
    assert int(os.environ["SLURM_CPUS_PER_TASK"]) >= 16
    node = socket.gethostname().split(".")[0]
    if gpu:
        assert node in {"compute-0-20", "compute-0-21", "compute-0-22"}
    else:
        assert node in {"compute-0-8", "compute-0-9", "compute-0-10", "compute-0-11"}


def native_components(role, *, seed=0, epoch_noise=False, verify_hashes=True):
    setup_imports()
    from s_native_adapter_v2 import MappedRecordIndex, ManifestViewsDataset, CountIndex, identity
    from phychem_mfm.phase1.full_corpus_loader import _load_bound_native_transport, NATIVE_TRANSPORT_POLICY
    cfg = old_configuration()
    protocol = json.loads(Path(cfg["frozen_protocol_reference"]["path"]).read_text())
    transport = protocol["draft_provenance"]["runner_artifacts"]["native_transport"]
    binding = {"policy": NATIVE_TRANSPORT_POLICY, "source_sha256": transport["sha256"]}
    function = _load_bound_native_transport(Path(transport["path"]), binding, identity(transport["path"]))
    snapshot = json.loads((OLD / "training_inputs_v1/shard_snapshot_v1.json").read_text())
    index = MappedRecordIndex(role, binding, snapshot, verify_hashes=verify_hashes)
    view_options = dict(cfg["views"])
    if epoch_noise:
        view_options["noise_seed_includes_epoch"] = True
    dataset = ManifestViewsDataset(index, native_transport=function, native_transport_binding=binding,
                                   seed=seed, **view_options)
    return index, dataset, CountIndex(index)
