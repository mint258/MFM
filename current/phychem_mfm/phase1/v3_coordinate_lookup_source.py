"""Known existing S roles and read-only native provider for C2 analysis.

Metadata selection freezes membership before any native geometry is decoded.
No downstream store, new D-line format or historical submission entry is used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import re
import sys

import numpy as np

from .v3_contract import canonical_hash, require
from .v3_coordinate_lookup import CoordinateLookupConfig, LookupRecord
from .v3_dev_store import bound_json

ROOT = Path(__file__).absolute().parents[3]
PROJECT = Path("/share/home/zixiao/descriptor_analysis")
OLD = PROJECT / "runs/sprime_s_convergence_20261013"
INPUT_SHA = "2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997"
POPULATION_SHA = "d21bae7f7b6c1dfbfe9342635ded80a55ddc05baba46ebfaa66cb7831866b96e"
PROTOCOL_SHA = "cde2ca717934955f340a5f160a3390ff1dd6eda12c9ffbab93fc54fce0c8a2a4"
ORIGINAL_SNAPSHOT_SHA = "d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f"
SNAPSHOT_BINDER = PROJECT / "MFM_model_v3_profiler_v2/tools/model_v3/native_runtime_bindings.py"
SNAPSHOT_BINDER_SHA = "ed2e069d408a671c93e8c42ec827162db3d98333587c08c9d37010fc6d7e464d"
ROLE_MAP = {"TRAIN": "train", "PRETRAIN_VAL": "full"}
SOURCE_FILES = (
    "current/phychem_mfm/phase1/v3_coordinate_lookup.py",
    "current/phychem_mfm/phase1/v3_coordinate_lookup_source.py",
    "current/phychem_mfm/phase1/full_corpus_loader.py",
    "current/phychem_mfm/training/degrade_molecules.py",
    "workflows/sprime_s/scripts/prepare.py",
    "workflows/sprime_s/scripts/prepare_s_training_inputs_v1.py",
    "workflows/sprime_s/scripts/s_native_adapter_v1.py",
    "workflows/sprime_s/scripts/s_native_adapter_v2.py",
    "workflows/sprime_s/scripts/s_convergence_runner_v8.py",
    "workflows/wp5/scripts/wp5_population.py",
    "tools/model_v3/run_coordinate_lookup.py",
)


def binding(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), "Ordinary bound source file required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def implementation_sources():
    result = {name: binding(ROOT / name)["sha256"] for name in SOURCE_FILES}
    external = binding(SNAPSHOT_BINDER)
    require(external["sha256"] == SNAPSHOT_BINDER_SHA, "Fixed original-snapshot binder source differs")
    result["external_fixed_native_runtime_bindings.py"] = external["sha256"]
    return result


def bind_source_snapshot(path, expected_sha256):
    """Reuse the tested raw-byte binder; projection remains in old v2's copy."""
    require(Path(path).absolute() == OLD / "training_inputs_v1/shard_snapshot_v1.json"
            and expected_sha256 == ORIGINAL_SNAPSHOT_SHA, "Use the preregistered original S snapshot pin")
    require(binding(SNAPSHOT_BINDER)["sha256"] == SNAPSHOT_BINDER_SHA,
            "Fixed original-snapshot binder source differs")
    name = "C2_fixed_original_snapshot_"+SNAPSHOT_BINDER_SHA[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SNAPSHOT_BINDER)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name].bind_original_snapshot(path, expected_sha256)


@dataclass(frozen=True)
class LookupSelection:
    seed: int = 20261025
    train_records: int = 8192
    validation_records: int = 1024
    max_candidates_per_role: int = 65536
    max_record_atoms: int = 512
    max_train_atoms: int = 524288

    def __post_init__(self):
        require(all(type(value) is int and value > 0 for value in asdict(self).values()),
                "Positive integer frozen selection settings required")
        require(self.max_candidates_per_role >= max(self.train_records, self.validation_records),
                "Selection candidate bound is too small")


def role_evidence(configuration, inputs, population, protocol):
    """Check the actual S preparation/runner lineage, not a guessed role name."""
    require(configuration["variant"] == "S" and configuration["input_manifest_sha256"] == INPUT_SHA,
            "The existing frozen S configuration/input manifest is required")
    require(inputs["status"] == "INPUT_METADATA_CLOSED_NATIVE_SAMPLE_PASS"
            and inputs["roles"]["train"]["records"] == 11104772
            and inputs["roles"]["full"]["records"] == 127082,
            "The closed existing S input role inventory differs")
    require(population["status"] == "WP5_FORMAL_POPULATION_CLOSED"
            and population["configuration"]["FULL_anchor_promotes_entire_TRAIN_component"] is True
            and population["configuration"]["routine_is_FULL_monitor_subset"] is True,
            "Original pretraining population/component policy is required")
    counts = {row["split"]: row["records"] for row in population["roles"]}
    require(counts == {role: inputs["roles"][role]["records"] for role in ("train", "full")},
            "S preparation and original pretraining population counts differ")
    require("full_declared_validation" in protocol["validation_population_policy"]["terminal"]
            and "full_validation_manifest" in protocol["artifacts"],
            "The source frozen protocol must explicitly define full pretraining validation")
    return {"role_map": dict(ROLE_MAP), "source_protocol_pretraining_validation": True,
        "source_input_counts": counts,
        "proof": ["prepare.py: split train/full -> prepared train_records/full_records",
            "prepare_s_training_inputs_v1.py: native metadata joins original formal split",
            "s_convergence_runner_v8.py: evaluate(role) reads MappedRecordIndex(role); validate() uses full/routine",
            "frozen protocol: full_validation_manifest and full_declared_validation terminal"],
        "downstream_final_role_or_scores_used": False, "D5_new_split_claimed": False}


def choose_metadata(index, counts, *, wanted, seed, selection):
    """Use only frozen counts/identities, with a bounded random candidate list."""
    require(0 < wanted <= selection.max_candidates_per_role, "Bounded exact selection count required")
    candidates = np.random.Generator(np.random.PCG64(seed)).choice(len(index),
        size=min(len(index), selection.max_candidates_per_role), replace=False)
    rows = []
    for ordinal in candidates:
        logical = int(ordinal)
        atoms = counts.ref(logical).native_n_atoms
        if not 0 < atoms <= selection.max_record_atoms:
            continue
        ref = index.ref(logical)
        require(ref.native_n_atoms == atoms, "Native metadata/count mismatch")
        rows.append({"logical_index": logical, "record_id": ref.record_id, "molecule_id": ref.molecule_id,
                     "native_n_atoms": atoms, "payload_sha256": ref.payload_sha256})
        if len(rows) == wanted:
            break
    require(len(rows) == wanted, "Frozen metadata candidate list has insufficient eligible records")
    require(len({row["record_id"] for row in rows}) == wanted, "Duplicate native record identity")
    return rows


class ExistingSLookupSource:
    """Fresh per-process CPU-only handles; exact source/payload verification."""
    def __init__(self, request, *, check=lambda: None):
        require(os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16,
                "Existing S metadata/geometry access requires its owned 16-CPU Slurm allocation")
        require(request["schema"] == "model_v3_C2_existing_S_request_v1"
                and request["source_files"] == implementation_sources(), "Exact C2 source inventory required")
        require(request["method"] == asdict(CoordinateLookupConfig())
                and request["selection"] == asdict(LookupSelection())
                and request["source_noise"] == {"seed": 0, "epoch": 0, "noise_seed_includes_epoch": True, "sigma_A": .1},
                "C2 v1 runs must use the preregistered method/selection/noise settings")
        require(request["execution_caps"] == {"wall_seconds": 3300, "finalization_reserve_seconds": 30,
            "maximum_process_RSS_bytes": 24 * 1024**3, "maximum_output_bytes": 128 * 1024**2},
            "C2 v1 execution limits differ from the preregistered resource bounds")
        for key in ("code_sha", "preregistration_sha"):
            require(re.fullmatch(r"[0-9a-f]{40}", request[key]), "Actual source and public preregistration commits required")
        self.request, self.check = request, check
        self.indices, self.counts, self.datasets = {}, {}, {}
        self.node_local_device_projections = {}
        self.native_reads = 0
        require(request["input_manifest"]["path"] == str(OLD / "training_inputs_v1/manifest.json")
                and request["input_manifest"]["sha256"] == INPUT_SHA
                and request["population_manifest"]["sha256"] == POPULATION_SHA
                and request["protocol"]["sha256"] == PROTOCOL_SHA,
                "Use the fixed existing S input/population/protocol references")
        self.configuration = bound_json(request["configuration"]["path"], request["configuration"]["sha256"])
        self.inputs = bound_json(request["input_manifest"]["path"], INPUT_SHA)
        population = bound_json(request["population_manifest"]["path"], POPULATION_SHA)
        protocol = bound_json(request["protocol"]["path"], PROTOCOL_SHA)
        self.evidence = role_evidence(self.configuration, self.inputs, population, protocol)
        require(self.configuration["frozen_protocol_reference"] == {
            "path": request["protocol"]["path"], "sha256": PROTOCOL_SHA}, "Original S protocol link differs")
        snapshot, self.snapshot_receipt = bind_source_snapshot(
            request["shard_snapshot"]["path"], request["shard_snapshot"]["sha256"])
        scripts = ROOT / "workflows/sprime_s/scripts"
        sys.path.insert(0, str(scripts))
        for name in ("prepare", "s_native_adapter_v1", "s_native_adapter_v2"):
            if name in sys.modules:
                require(Path(sys.modules[name].__file__).absolute() == scripts / (name+".py"),
                        "An existing foreign module shadows the frozen S reader")
            importlib.import_module(name)
        adapter = sys.modules["s_native_adapter_v2"]
        prepare = sys.modules["prepare"]
        require(prepare.ROOT == OLD, "Frozen S reader root differs from the bound input manifest")
        from .full_corpus_loader import NATIVE_TRANSPORT_POLICY, _load_bound_native_transport
        transport = protocol["draft_provenance"]["runner_artifacts"]["native_transport"]
        require(binding(transport["path"])["sha256"] == transport["sha256"], "Native transport source SHA differs")
        transport_binding = {"policy": NATIVE_TRANSPORT_POLICY, "source_sha256": transport["sha256"]}
        function = _load_bound_native_transport(Path(transport["path"]), transport_binding, adapter.identity(transport["path"]))
        try:
            for role, native_role in ROLE_MAP.items():
                check()
                index = adapter.MappedRecordIndex(native_role, transport_binding, snapshot, verify_hashes=True)
                self.indices[role] = index; self.counts[role] = adapter.CountIndex(index)
                self.node_local_device_projections[role] = index.cross_node_device_observations
                options = dict(self.configuration["views"])
                options.update(cache_bytes=0, max_cache_entries=1, noise_seed_includes_epoch=True)
                self.datasets[role] = adapter.ManifestViewsDataset(index, native_transport=function,
                    native_transport_binding=transport_binding, seed=0, **options)
                self.datasets[role].set_epoch(0)
                geometry = self.datasets[role].cfgs[1]
                require(geometry.mode == "geom" and geometry.geom_noise_std == .1
                        and geometry.geom_angle_std_deg == geometry.geom_bond_scale_std == 0.,
                        "C2 uses the existing additive S geometry-noise definition")
        except BaseException:
            self.close(); raise

    def plan(self):
        selection = LookupSelection(**self.request["selection"])
        method = CoordinateLookupConfig(**self.request["method"])
        require(selection.max_record_atoms == method.max_record_atoms
                and selection.train_records <= method.max_train_records
                and selection.max_train_atoms == method.max_train_atoms, "Selection and fitting budgets differ")
        chosen = {}
        for offset, role in enumerate(ROLE_MAP):
            wanted = selection.train_records if role == "TRAIN" else selection.validation_records
            chosen[role] = choose_metadata(self.indices[role], self.counts[role], wanted=wanted,
                seed=selection.seed + offset, selection=selection)
        train = chosen["TRAIN"]; validation = chosen["PRETRAIN_VAL"]
        require(sum(row["native_n_atoms"] for row in train) <= selection.max_train_atoms,
                "Frozen TRAIN selection exceeds atom budget; no truncation or replacement is allowed")
        for name in ("record_id", "molecule_id"):
            require(not ({row[name] for row in train} & {row[name] for row in validation}),
                    "Existing S TRAIN/validation identities overlap")
        require(self.native_reads == 0, "Metadata planning must not decode native geometry")
        return {"schema": "model_v3_C2_label_free_native_selection_v1", "source_request_sha256": canonical_hash(self.request),
            "role_evidence": self.evidence, "selection": asdict(selection), "records": chosen,
            "original_snapshot": {key: self.snapshot_receipt[key] for key in ("path", "bytes", "sha256")},
            "native_geometry_records_decoded": 0, "selection_uses_targets": False,
            "numpy_version_for_PCG64_selection": np.__version__}

    def records(self, role, plan):
        require(role in ROLE_MAP and plan["schema"] == "model_v3_C2_label_free_native_selection_v1"
                and plan["source_request_sha256"] == canonical_hash(self.request)
                and plan["selection_uses_targets"] is False and plan["native_geometry_records_decoded"] == 0,
                "Frozen source/role plan required")
        import torch
        from ..training.degrade_molecules import degrade_once
        index, dataset = self.indices[role], self.datasets[role]
        for row in plan["records"][role]:
            self.check()
            ref = index.ref(row["logical_index"])
            actual = {"logical_index": ref.logical_index, "record_id": ref.record_id, "molecule_id": ref.molecule_id,
                      "native_n_atoms": ref.native_n_atoms, "payload_sha256": ref.payload_sha256}
            require(actual == row, "Selected S source identity changed before native decode")
            clean = dataset._native(ref)
            self.native_reads += 1
            noise_generator = torch.Generator(device="cpu").manual_seed(dataset.noise_seed(ref.logical_index))
            noisy = degrade_once(clean.clone(), dataset.cfgs[1], noise_generator)
            yield LookupRecord(ref.record_id, ref.molecule_id, role, clean.x[:, 0].numpy().copy(),
                noisy.pos.float().numpy().copy(), clean.pos.float().numpy().copy(), ref.payload_sha256)

    def verify(self):
        for index in self.indices.values():
            self.check(); index.verify_unchanged()
        require(self.request["source_files"] == implementation_sources(), "C2 implementation changed during the job")
        _, snapshot_after = bind_source_snapshot(self.request["shard_snapshot"]["path"], ORIGINAL_SNAPSHOT_SHA)
        require(snapshot_after == self.snapshot_receipt, "Original S snapshot physical identity changed during the job")
        for name in ("configuration", "input_manifest", "population_manifest", "protocol", "shard_snapshot"):
            require(binding(self.request[name]["path"]) == self.request[name], "C2 physical source metadata changed")

    def close(self):
        for owner in (self.datasets, self.counts, self.indices):
            for value in owner.values():
                value.close()
