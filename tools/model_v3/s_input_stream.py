"""Read-only, resettable existing S stream for paired development comparisons."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from profile_s_baseline import digest, synthetic_corpus


class SInputStream:
    def __init__(self, reference, *, seed, input_kind, workers=8, max_padded_cost=8_000_000,
                 snapshot_sha256=None, atom_bucket_width=None, exact_atom_sort=False):
        self.reference, self.seed, self.input_kind = reference, seed, input_kind
        self.ordinal = 0
        self.iterator = self.dataset = self.index = self.count_index = self.sampler = None
        self.bindings = {"input_kind": input_kind, "seed": seed, "noise_seed_includes_epoch": True}
        self.committed_base_samples = 0
        if type(exact_atom_sort) is not bool or (atom_bucket_width is not None and
                (type(atom_bucket_width) is not int or not 1 <= atom_bucket_width <= 64)):
            raise ValueError("Explicit bounded bucket width and boolean exact sort required")
        if input_kind == "synthetic":
            if atom_bucket_width is not None or exact_atom_sort:
                raise ValueError("Grouping candidates require the native S stream")
            return
        if input_kind != "native_s":
            raise ValueError("Explicit existing native S or synthetic stream required")
        import torch
        from s_native_adapter_v2 import MappedRecordIndex, ManifestViewsDataset, CountIndex, identity
        from phychem_mfm.phase1.full_corpus_loader import (
            BlockAtomBatchSampler, make_prefetch_loader, close_prefetch_iterator,
            _load_bound_native_transport, NATIVE_TRANSPORT_POLICY)
        from s_loader_recovery_v2 import RecoveringLoaderIterator
        root = Path("/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013")
        ref = reference["frozen_protocol_reference"]
        if digest(ref["path"]) != ref["sha256"]:
            raise RuntimeError("Frozen native S reference protocol changed")
        protocol = json.loads(Path(ref["path"]).read_text())
        transport = protocol["draft_provenance"]["runner_artifacts"]["native_transport"]
        binding = {"policy": NATIVE_TRANSPORT_POLICY, "source_sha256": transport["sha256"]}
        native = _load_bound_native_transport(Path(transport["path"]), binding, identity(transport["path"]))
        manifest = root / "training_inputs_v1/manifest.json"
        if digest(manifest) != reference["input_manifest_sha256"]:
            raise RuntimeError("Native S input manifest changed")
        from native_runtime_bindings import bind_original_snapshot
        snapshot, snapshot_ref = bind_original_snapshot(
            root / "training_inputs_v1/shard_snapshot_v1.json", snapshot_sha256)
        try:
            self.index = MappedRecordIndex("train", binding, snapshot, verify_hashes=True)
            self.count_index = CountIndex(self.index)
            self.dataset = ManifestViewsDataset(self.index, native_transport=native, native_transport_binding=binding,
                                                seed=seed, noise_seed_includes_epoch=True, **reference["views"])
            sampler_config = {**reference["sampler"], "max_padded_cost": max_padded_cost}
            if atom_bucket_width is not None:
                sampler_config["atom_bucket_width"] = atom_bucket_width
            sampler_type = BlockAtomBatchSampler
            extras = {}
            if exact_atom_sort:
                from phychem_mfm.phase1.v3_padding import LocallySortedAtomBatchSampler
                sampler_type, extras = LocallySortedAtomBatchSampler, {"exact_atom_sort": True}
            self.sampler = sampler_type(self.count_index, seed=seed, epoch=0, **sampler_config, **extras)
            self.initial_state = copy.deepcopy(self.sampler.state_dict())
            loader_config = {**reference["loader"], "num_workers": workers}
            self.factory = lambda: RecoveringLoaderIterator(
                lambda: make_prefetch_loader(self.dataset, self.sampler, **loader_config),
                self.sampler, close_prefetch_iterator, torch, role="paired_A_train", preserve_initial_rng=True)
            self.bindings.update(manifest_path=str(manifest), manifest_sha256=digest(manifest),
                                 native_transport=transport, sampler=sampler_config, loader=loader_config,
                                 original_shard_snapshot=snapshot_ref, exact_atom_sort=exact_atom_sort,
                                 sampler_contract=self.sampler.contract,
                                 sampler_contract_sha256=self.sampler.contract_sha256)
        except BaseException as initial_error:
            try:
                self.close()
            except BaseException as cleanup_error:
                raise initial_error from cleanup_error
            raise

    def next(self):
        if self.input_kind == "synthetic":
            corpus = synthetic_corpus(self.seed, self.ordinal)
            self.ordinal += 1
            return corpus
        if self.iterator is None:
            self.iterator = self.factory()
        corpus = next(self.iterator)
        if tuple(self.index.ref(i).record_id for i in corpus.logical_indices) != corpus.record_keys:
            raise RuntimeError("Fetched native record IDs differ from the consumed stream")
        return corpus

    def commit(self, corpus):
        if self.sampler is not None:
            self.sampler.commit_batch(corpus.logical_indices)
        self.committed_base_samples += len(corpus.logical_indices)

    def state_dict(self):
        return {"committed_base_samples": self.committed_base_samples,
                "sampler": copy.deepcopy(self.sampler.state_dict()) if self.sampler is not None else None}

    def reset(self):
        if self.iterator is not None:
            workers = tuple(getattr(getattr(self.iterator, "iterator", None), "_workers", ()))
            self.iterator.close()
            if any(worker.is_alive() or worker.exitcode is None for worker in workers):
                raise RuntimeError("Reset requires loader workers actually exited/joined")
            self.iterator = None
        self.ordinal = 0
        self.committed_base_samples = 0
        if self.sampler is not None:
            self.sampler.load_state_dict(copy.deepcopy(self.initial_state))

    def close(self):
        errors = []
        if self.iterator is not None:
            workers = tuple(getattr(getattr(self.iterator, "iterator", None), "_workers", ()))
            try:
                self.iterator.close()
                if any(worker.is_alive() or worker.exitcode is None for worker in workers):
                    raise RuntimeError("Recorded loader worker has not actually exited/joined")
            except BaseException as exc:
                errors.append({"component": "iterator", "type": type(exc).__name__, "message": str(exc)})
            self.iterator = None
        paths = set()
        if self.index is not None:
            paths.update(str(Path(path).absolute()) for path in (self.index.path, self.index.atoms_path))
            paths.update(str(Path(row["path"]).absolute()) for row in self.index.shards.values())
        for value in (self.count_index, self.dataset, self.index):
            if value is not None:
                try:
                    value.close()
                except BaseException as exc:
                    errors.append({"component": type(value).__name__, "type": type(exc).__name__, "message": str(exc)})
        for descriptor in Path("/proc/self/fd").iterdir() if paths else ():
            try:
                if os.readlink(descriptor) in paths:
                    errors.append({"component": "native_input_descriptor", "fd": descriptor.name})
            except FileNotFoundError:
                continue
        self.last_cleanup = {"input_descriptors_closed": not errors, "errors": errors}
        if errors:
            raise RuntimeError("Native S stream cleanup failed: " + str(errors))
