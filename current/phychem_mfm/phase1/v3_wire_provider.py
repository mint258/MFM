"""Opt-in synthetic MFM3 consumer; never an admitted real D3/release adapter.

Uses the pinned data-line codec/readers. Model-owned fixture bindings state
identity/atom order explicitly; no unfinished physical target is inferred.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib
import json
from multiprocessing.util import Finalize
import os
from pathlib import Path
import stat
import sys
import socket

import numpy as np
import torch

from .v3_contract import FieldTarget, canonical_hash, require
from .v3_data import DecodedSample, ManifestSampleDataset, NativeBondTransport, collate_v3_samples
from .v3_structural import build_structural_views, eligibility_from_choices
from .v3_trainer import PreparedV3Batch
from .v3_wire_audit import (FieldReasonAudit, MemberReasonAudit, SampleSourceAudit,
                            identity_sha256, source_identity)

DATA_EXPORT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export")
DATA_SOURCE_SHA = {
    "wire_v1/__init__.py": "e38cb7eef50e67e3729d9be623aa9b19480819514ab9b25d0bbab5f4b904387d",
    "pipeline_v1/__init__.py": "852add1958dbcad85289a094428205d83b6d9c0c4f30765543d23c35963d21d5",
    "wire_v1/codec.py": "1f140f47b7945d4e9d82e19bc8464b12c00823db83548cb9b3ba81d8a1dc24dd",
    "wire_v1/mapping.py": "b67a248bf1e24bcb6cd05a8ce6c1a5d2981bb990d2728fb8a217d8c4e77acd76",
    "wire_v1/store.py": "6c6de74e88bc1e1d81363f9621ecc332b9708914e15dc3feadee9d94ef4b7d63",
    "pipeline_v1/granular_store.py": "958226ad2f62d387d363395aefa9eea47cfd0dbf8a9fef8171c806dd0a4d0792",
}
SCOPE = "synthetic_candidate_fixture_only_not_D3"


def array_sha256(value):
    return hashlib.sha256(np.asarray(value).tobytes(order="C")).hexdigest()


def file_ref(path, maximum=64 << 20):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(), "Physical absolute fixture/source path required")
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
            and before.st_size <= maximum, "Owned bounded ordinary fixture/source required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""): digest.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Fixture/source changed during admission")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest()}


def fingerprint(path):
    info = Path(path).stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def data_runtime():
    """Only the actual pinned DataB Python implementations, never a decoder clone."""
    for relative, sha in DATA_SOURCE_SHA.items():
        require(file_ref(DATA_EXPORT / relative)["sha256"] == sha, "Data-line candidate source revision differs")
    sys.path.insert(0, str(DATA_EXPORT))
    modules = {}
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        for name in ("wire_v1.codec", "wire_v1.mapping", "wire_v1.store", "pipeline_v1.granular_store"):
            module = importlib.import_module(name)
            require(Path(module.__file__).resolve() == DATA_EXPORT / (name.replace(".", "/") + ".py"), "Data-line module namespace collision")
            modules[name] = module
    finally:
        sys.dont_write_bytecode = previous
    return modules


def local_storage_receipt(path, root):
    path, root = Path(path), Path(root)
    require(path.is_absolute() and path.resolve(strict=True) == path and path.is_relative_to(root),
            "Candidate stores/codebooks must be inside the declared physical node-local fixture root")
    # No /share or mounted network store can qualify by setting a boolean.
    require(root.is_absolute() and root.resolve(strict=True) == root and root.is_relative_to(Path("/tmp")),
            "Candidate fixture admission requires a private /tmp node-local root")
    entries = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        mount = Path(left.split()[4].replace("\\040", " "))
        if path.is_relative_to(mount): entries.append((len(mount.parts), right.split()[0]))
    require(entries and max(entries)[1] not in {"nfs", "nfs4", "cifs", "fuse.sshfs", "lustre", "gpfs"},
            "Real local filesystem required for candidate worker handles")
    info = path.stat(); root_info = root.stat()
    require(root_info.st_uid == os.getuid() and stat.S_ISDIR(root_info.st_mode), "Owned private fixture root required")
    return {"node": socket.gethostname(), "node_local_root": str(root), "resolved_path": str(path),
            "filesystem_type": max(entries)[1], "device": info.st_dev, "inode": info.st_ino,
            "root_inode": root_info.st_ino, "owner_uid": info.st_uid, "local_filesystem_observed": True}


def local_path(path, root):
    local_storage_receipt(path, root)
    return Path(path)


def _close_readers(readers, event_path, pid):
    for reader in readers: reader.close()
    if event_path is not None:
        with Path(event_path).open("a") as stream:
            stream.write(json.dumps({"pid": pid, "event": "READONLY_HANDLES_CLOSED", "count": len(readers)}) + "\n")


class CandidateWireFactory:
    read_only, node_local = True, True

    def __init__(self, index, registry, manifest, *, node_local_root, allow_candidate=False, handle_events=None):
        require(allow_candidate is True and manifest.get("scope") == SCOPE
                and getattr(index, "authority", None) == registry.authority == "synthetic_fixture",
                "Wire candidate requires explicit fixture opt-in; real data-line authority is not admitted")
        require(manifest["data_version"] == index.version, "Wire/index data version differs")
        self.index, self.registry = index, registry
        self._manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        self.root = str(Path(node_local_root))
        self.data_version = index.version
        self.handle_events = None if handle_events is None else str(handle_events)
        self.local_storage = local_storage_receipt(self.root, self.root)
        self.source_sha256 = canonical_hash({"manifest": manifest, "index": index.content_sha256,
            "registry": registry.content_sha256, "adapter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "audit": hashlib.sha256(Path(__file__).with_name("v3_wire_audit.py").read_bytes()).hexdigest(),
            "v3_data": hashlib.sha256(Path(__file__).with_name("v3_data.py").read_bytes()).hexdigest(),
            "native_descriptor": hashlib.sha256(Path(__file__).parents[1].joinpath("data/descriptor_schema.py").read_bytes()).hexdigest(),
            "data_line": DATA_SOURCE_SHA, "node_local_storage": self.local_storage})
        require(len({row["geometry_id"] for row in manifest["records"]}) == len(manifest["records"]), "Unique explicit geometry/export locators required")
        require(len({row["name"] for row in manifest["stores"]}) == len(manifest["stores"]), "Unique explicit family store names required")
        require(len({row["target_id"] for row in manifest["targets"]}) == len(manifest["targets"])
                and len({row["model_field"] for row in manifest["targets"]}) == len(manifest["targets"]), "One-to-one physical target projection required")
        require({row["model_field"] for row in manifest["targets"]} == {field.name for field in registry.fields if field.group in ("D", "P")},
                "Every declared candidate P/D field needs an explicit physical projection")
        for row in manifest["targets"]:
            field = registry.by_name()[row["model_field"]]
            require(field.group in ("D", "P") and field.kind == "regression"
                    and field.representation in ("scalar", "vector"), "Only explicit clean scalar/vector regression targets are supported")
            require(not row.get("basis_indexed", False) and row.get("geometry_context") == "base"
                    and row.get("condition") in ("PM7", "Sprime_UFF"),
                    "Tensor/basis/off-equilibrium/mixed-condition targets remain unsupported")

    @property
    def manifest(self): return json.loads(self._manifest_json)

    def __call__(self): return CandidateWireReader(self)


class CandidateWireReader:
    def __init__(self, factory):
        self.factory, self.pid, self.closed = factory, os.getpid(), False
        self.readers, self.files = {}, {}
        self.local_storage = local_storage_receipt(factory.root, factory.root)
        require(self.local_storage == factory.local_storage, "Worker changed admitted node-local root/filesystem identity")
        self._closer = None
        manifest = factory.manifest
        runtime = data_runtime()
        self.files.update({str(DATA_EXPORT / name): fingerprint(DATA_EXPORT / name) for name in DATA_SOURCE_SHA})
        self.mapping = runtime["wire_v1.mapping"]
        self.targets = tuple(manifest["targets"])
        self.records = {row["geometry_id"]: row for row in manifest["records"]}
        try:
            for item in manifest["stores"]:
                path = local_path(item["path"], factory.root)
                require(file_ref(path / "data.mdb") == item["data"], "Candidate shard bytes differ")
                self.files[str(path / "data.mdb")] = fingerprint(path / "data.mdb")
                kind = runtime["wire_v1.store"].FamilyReader if item["kind"] == "geometry" else runtime["pipeline_v1.granular_store"].GranularFamilyReader
                require(item["kind"] in ("geometry", "labels"), "Explicit geometry/family kind required")
                reader = kind(path, expected_schema_sha256=item["schema_sha256"])
                self.readers[item["name"]] = reader
                require(reader.env.flags()["readonly"] is True and reader.schema["kind"] == item["kind"], "Actual readonly matching-kind handle required")
                if item["kind"] == "labels":
                    require(set(reader.schema["compiled"]["physical_targets"]) == {row["target_id"] for row in self.targets if row["store"] == item["name"]},
                            "No candidate family target can be silently dropped")
            book_ref = manifest["reason_codebook"]
            local_path(book_ref["path"], factory.root)
            require(file_ref(book_ref["path"]) == book_ref, "Reason codebook raw SHA differs")
            self.book = json.loads(Path(book_ref["path"]).read_text())
            self.files[book_ref["path"]] = fingerprint(book_ref["path"])
            require(self.book["scope"] == SCOPE and self.book["unresolved_leaf_code"] == 65535, "Explicit candidate reason book/sentinel required")
            require(all(str(int(key)) == key and 0 < int(key) < 65535 for key in self.book["codes"]), "Canonical explicit reason-code keys required")
            self.codes = {int(key) for key in self.book["codes"]} | {65535}
            self.book_sha = book_ref["sha256"]
            self.bond_map = None
            if manifest.get("synthetic_bond_mapping") is not None:
                ref = manifest["synthetic_bond_mapping"]; local_path(ref["path"], factory.root)
                require(file_ref(ref["path"]) == ref, "Synthetic bond mapping raw SHA differs")
                self.bond_map = json.loads(Path(ref["path"]).read_text())
                self.files[ref["path"]] = fingerprint(ref["path"])
                require(self.bond_map["scope"] == SCOPE and self.bond_map["native_status"] == "ok"
                        and self.bond_map["real_wire_authority"] is False, "Only an explicitly synthetic bond mapping is admitted")
                require(self.bond_map["native_descriptor_sha256"] == hashlib.sha256(
                    Path(__file__).parents[1].joinpath("data/descriptor_schema.py").read_bytes()).hexdigest(), "Synthetic/native codebook protocol binding differs")
                require(all(type(value) is int and 1 <= value <= 5 for value in self.bond_map["wire_to_native"].values()), "Declared old native bond categories required")
            if factory.handle_events is not None:
                local_path(Path(factory.handle_events).parent, factory.root)
                with Path(factory.handle_events).open("a") as stream:
                    stream.write(json.dumps({"pid": self.pid, "event": "READONLY_HANDLES_OPENED", "count": len(self.readers)}) + "\n")
            self._closer = Finalize(self, _close_readers, args=(tuple(self.readers.values()), factory.handle_events, self.pid), exitpriority=10)
        except BaseException:
            for reader in self.readers.values(): reader.close()
            raise

    def close(self):
        if not self.closed:
            if self._closer is not None: self._closer()
            self.closed = True

    def _unchanged(self):
        require(not self.closed and self.pid == os.getpid(), "Reader handle must stay in its owning worker")
        require(all(fingerprint(path) == value for path, value in self.files.items()), "Admitted shard changed after readonly open")

    def read(self, choice):
        self._unchanged()
        require(choice.index_sha256 == self.factory.index.content_sha256 and choice.locator in self.records, "Bound geometry locator required")
        row = self.records[choice.locator]
        require(row["molecule_id"] == choice.molecule_id and row["geometry_id"] == choice.conformer_id
                and row["model_geometry_source"] == choice.geometry_source and row["n_atoms"] == choice.native_atoms, "Choice/native wire identity differs")
        native = row["native_identity"]
        require(set(native) == {"geometry_id", "molecule_id", "geometry_source", "native_record_id", "sprime_conf_idx"}
                and native["geometry_id"] == row["geometry_id"] and native["molecule_id"] == row["molecule_id"], "Explicit source-native identity required")
        require({"pm7": "PM7", "uff_sprime": "Sprime_UFF"}.get(native["geometry_source"]) == choice.geometry_source,
                "Explicit published source spelling differs from sampling source")
        if hasattr(self.factory.index, "native_identity_for"):
            require(self.factory.index.native_identity_for(choice.locator).as_dict() == native, "Candidate D5/native identity differs")
        meta, arrays = self.readers[row["geometry_store"]].get(row["export_record_id"])
        require(identity_sha256(meta) == row["identity_sha256"] and meta["geometry_source"] == native["geometry_source"]
                and meta["n_atoms"] == row["n_atoms"] and meta["effective_role"] == "TRAIN"
                and meta["parent_geometry_id"] is None and meta["view_id"] is None,
                "Geometry source/role/base identity differs")
        order = {"source_atom_ids": row["source_atom_ids"], "atomic_numbers_sha256": array_sha256(arrays["atomic_numbers"]),
                 "positions_A_sha256": array_sha256(arrays["positions_A"])}
        require(canonical_hash(order) == row["atom_order_sha256"] and len(row["source_atom_ids"]) == choice.native_atoms
                and len(set(row["source_atom_ids"])) == choice.native_atoms
                and all(type(value) is int and value >= 0 for value in row["source_atom_ids"]), "Native atom-order/coordinate binding differs")
        require(meta.get("model_fixture_atom_order_sha256") == row["atom_order_sha256"],
                "Explicit candidate fixture atom-order receipt is required; no real-export order authority is inferred")
        fields, audits = {}, []
        for projection in self.targets:
            target_id, field_name = projection["target_id"], projection["model_field"]
            field = self.factory.registry.by_name()[field_name]
            reader = self.readers[projection["store"]]
            labels_meta, labels = reader.get(row["export_record_id"])
            require(source_identity(labels_meta) == source_identity(meta)
                    and labels_meta.get("reason_codebook_sha256") == self.book_sha
                    and labels_meta.get("model_fixture_atom_order_sha256") == row["atom_order_sha256"],
                    "Family/geometry identity, atom-order or codebook differs")
            require(labels_meta["group_exposure_mask"] == dict(choice.group_mask)
                    and labels_meta["family_exposure_mask"] == dict(choice.family_mask), "Raw recipe exposure differs from bound draw")
            target = reader.schema["compiled"]["physical_targets"][target_id]
            require(len({member["field_key"] for member in target["members"]}) == len(target["members"])
                    and not target.get("basis_indexed", False)
                    and not any({"basis_i", "basis_j"} & set(member) or "sigma_pi_entries" in str(member.get("source_path", ""))
                                for member in target["members"]), "Basis-resolved r73 targets have no admitted projection")
            require(target["group"] == field.group and target["family"] == field.family and target["unit"] == field.unit
                    and target["level"] == ("molecule" if field.level == "graph" else field.level)
                    and target["kind"] == field.representation and target["geometry_source"] == meta["geometry_source"]
                    and projection["condition"] == choice.geometry_source, "Explicit physical/model field projection differs")
            validity = labels["valid/" + target_id].astype(bool, copy=True)
            values = labels["values/" + target_id]
            width = field.target_width
            count = 1 if field.level == "graph" else choice.native_atoms
            pair = None
            if field.level == "pair":
                pair = torch.from_numpy(labels["pairs/" + target_id].copy()).long().T.contiguous(); count = pair.shape[1]
            model_valid = validity.reshape(count, width).all(axis=1)
            fields[field_name] = FieldTarget(torch.from_numpy(values.copy()).reshape(count, width),
                torch.from_numpy(model_valid.copy()), pair)
            granularity = labels_meta.get("reason_granularity", {}).get(target_id)
            require(granularity is not None and granularity["mode"] == "field_set_and_sparse_generic_leaf_v1",
                    "Complete field-set+sparse source audit is required by this candidate")
            members = []
            for index, member in enumerate(target["members"]):
                key = member["field_key"]
                component = validity[..., index] if len(target["members"]) > 1 else validity
                shape = tuple(granularity["members"][key]["leaf_shape"])
                require(tuple(component.shape) == shape, "Original member/component leaf shape differs")
                scopes = [tuple(map(int, labels["reason_fields_" + scope + "/" + key])) for scope in ("source", "new", "review")]
                indices = tuple(map(int, labels["reason_leaf_index/" + key])); codes = tuple(map(int, labels["reason_leaf_code/" + key]))
                require(all(code in self.codes for group in (*scopes, codes) for code in group), "Unknown source/new/review/leaf code")
                members.append(MemberReasonAudit(key, shape, tuple(map(bool, component.reshape(-1))), *scopes, indices, codes))
            audits.append(FieldReasonAudit(target_id, field_name, tuple(validity.shape), tuple(map(bool, validity.reshape(-1))),
                tuple(map(bool, model_valid)), tuple(members), dict(choice.group_mask)[field.group], dict(choice.family_mask)[field.family]))
        bonds = None
        if self.bond_map is not None:
            require("bond_pairs" in arrays, "Declared synthetic native bond mapping requires wire pairs")
            codes = [str(int(value)) for value in arrays["bond_order_codes"]]
            require(all(code in self.bond_map["wire_to_native"] for code in codes), "Unknown synthetic wire bond code")
            bonds = NativeBondTransport(torch.from_numpy(arrays["bond_pairs"].copy()).long().T.contiguous(),
                torch.tensor([self.bond_map["wire_to_native"][code] for code in codes], dtype=torch.long), self.bond_map["native_status"])
        audit = SampleSourceAudit(row["export_record_id"], row["geometry_id"], row["identity_sha256"], canonical_hash(native),
            row["atom_order_sha256"], self.book_sha, tuple(audits))
        return DecodedSample(choice.molecule_id, choice.conformer_id, choice.geometry_source,
            torch.from_numpy(arrays["atomic_numbers"].copy()).long()[:, None] - 1,
            torch.from_numpy(arrays["positions_A"].copy()), torch.tensor(row["source_atom_ids"], dtype=torch.long), fields, bonds, audit)


class WirePreparedProvider:
    read_only, node_local = True, True

    def __init__(self, factory, structural_binding):
        self.factory, self.binding = factory, structural_binding
        self.source_sha256, self.data_version = factory.source_sha256, factory.data_version
        self.dataset = ManifestSampleDataset(factory.index, factory)

    def close(self): self.dataset.close()

    def audit_for(self, choices):
        return tuple(self.dataset[choice][1].audit for choice in choices)

    def prepare(self, choices, *, role, view_config, enabled_groups, enabled_fields):
        require(role == "TRAIN", "Candidate wire provider has no admitted real validation population")
        decoded = tuple(self.dataset[choice] for choice in choices)
        if "S" in enabled_groups:
            require(self.factory.manifest.get("synthetic_bond_mapping") is not None
                    and all(sample.native_bonds is not None for _, sample in decoded),
                    "S bond requires an explicit pinned synthetic codebook mapping; never drop S silently")
        batch = collate_v3_samples(decoded, self.factory.registry)
        masks = eligibility_from_choices(choices, self.factory.registry, self.binding, enabled_fields=enabled_fields)
        views = build_structural_views(batch.encoder_batch, ordinals=tuple(choice.ordinal for choice in choices), config=view_config,
            include_structural="S" in enabled_groups, graph_eligibility=masks)
        pd = {name: value for name, value in batch.targets.items() if self.factory.registry.by_name()[name].group in ("D", "P")}
        return PreparedV3Batch(tuple(choices), views, pd, self.source_sha256, self.data_version, role,
                              {name: value.pair_index for name, value in pd.items() if value.pair_index is not None})
