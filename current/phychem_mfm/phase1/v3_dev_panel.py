"""TRAIN-only development roles and a target-free frozen-H0 cache.

These adapters do not redefine the historical store or its official members.
The caller must supply the byte-bound frozen store and a frozen panel contract.
Only explicit training-source roles can be requested, including on error paths.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


ALLOWED_ROLES = ("train", "train_inner_validation")


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def molecule_folds(uids, *, folds=5, seed=20261025):
    """Balanced hash-ordered folds, defined solely from TRAIN molecule IDs."""
    unique = sorted(set(uids))
    if type(folds) is not int or folds < 2 or len(unique) < folds:
        raise ValueError("At least one distinct training molecule per inner fold is required")
    if any(type(uid) is not str or not uid for uid in unique):
        raise ValueError("Explicit molecule IDs are required")
    order = sorted(unique, key=lambda uid: (canonical([seed, uid]), uid))
    return {uid: i % folds for i, uid in enumerate(order)}


class TrainOnlyView:
    """Deny physical target access outside the chosen training-source members."""

    def __init__(self, store, dataset_id, fold_id, *, expansion_inner_folds=5, seed=20261025):
        self.__store = store
        self.dataset_id, self.fold_id = str(dataset_id), str(fold_id)
        contract = store.contract(self.dataset_id, self.fold_id)
        members, ordered = {}, {}
        for role in ALLOWED_ROLES:
            ids = tuple(store.view(self.dataset_id, self.fold_id, role=role))
            if ids != tuple(contract["member_indices"][role]):
                raise ValueError("Provider view differs from its frozen role contract")
            uids = tuple(contract["ordered_members"][role])
            if len(ids) != len(uids) or len(set(ids)) != len(ids):
                raise ValueError("Ordered source IDs and training members differ")
            members[role], ordered[role] = ids, uids
        if set(members[ALLOWED_ROLES[0]]) & set(members[ALLOWED_ROLES[1]]):
            raise ValueError("Training/inner-validation member overlap")
        if set(ordered[ALLOWED_ROLES[0]]) & set(ordered[ALLOWED_ROLES[1]]):
            raise ValueError("Training/inner-validation molecule overlap")
        if self.dataset_id == "expansionrx":
            if members[ALLOWED_ROLES[1]]:
                raise ValueError("Expected the unchanged official Expansion training contract")
            assignments = molecule_folds(ordered[ALLOWED_ROLES[0]], folds=expansion_inner_folds, seed=seed)
            pairs = tuple(zip(members[ALLOWED_ROLES[0]], ordered[ALLOWED_ROLES[0]]))
            members = {ALLOWED_ROLES[0]: tuple(i for i, uid in pairs if assignments[uid] != 0),
                       ALLOWED_ROLES[1]: tuple(i for i, uid in pairs if assignments[uid] == 0)}
            ordered = {role: tuple(uid for i, uid in pairs if i in set(ids)) for role, ids in members.items()}
        if not all(members[role] for role in ALLOWED_ROLES):
            raise ValueError("Both TRAIN optimization and inner validation must be nonempty")
        self.__members = members
        self.__uids = {i: uid for role in ALLOWED_ROLES for i, uid in zip(members[role], ordered[role])}
        self.tasks = tuple(contract["tasks"])
        self.output_level = contract["output_level"]
        self.membership_sha256 = canonical({"dataset": self.dataset_id, "fold": self.fold_id,
            "roles": {role: list(zip(members[role], ordered[role])) for role in ALLOWED_ROLES},
            "inner_seed": seed, "expansion_inner_folds": expansion_inner_folds})

    def view(self, role):
        if role not in ALLOWED_ROLES:
            raise ValueError("Only TRAIN-source inner roles are available")
        return self.__members[role]

    def get(self, member_index, *, role):
        if role not in ALLOWED_ROLES or member_index not in self.view(role):
            raise ValueError("Target access outside the declared TRAIN-source role")
        sample = self.__store.get(self.dataset_id, member_index)
        if (sample.member_uid != self.__uids[member_index] or sample.dataset_id != self.dataset_id
                or sample.member_index != member_index):
            raise ValueError("Returned physical sample differs from its source identity")
        return sample


def audit_role_calls(paths):
    """Static defense in addition to TrainOnlyView's runtime membership checks."""
    errors = []
    for path in paths:
        path = Path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (keyword.arg == "role" and isinstance(keyword.value, ast.Constant)
                            and keyword.value.value not in ALLOWED_ROLES):
                        errors.append({"path": str(path), "line": node.lineno,
                                       "reason": "literal role outside TRAIN inner roles"})
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                         else [alias.name for alias in node.names])
                if any("formal_readout" in name or "run_s_linear_probes" in name for name in names):
                    errors.append({"path": str(path), "line": node.lineno,
                                   "reason": "historical full-evaluation entry point import"})
    return errors


@dataclass(frozen=True)
class NativeGeometry:
    dataset_id: str
    molecule_uid: str
    member_index: int
    x: object
    pos: object
    source_atom_ids: object


@dataclass(frozen=True)
class MoleculeH0:
    molecule_uid: str
    member_index: int
    h0: object
    source_atom_ids: object


def _tensor_bytes(value):
    import torch
    if not isinstance(value, torch.Tensor):
        raise ValueError("A physical tensor is required")
    value = value.detach().cpu().contiguous()
    return (json.dumps([str(value.dtype), list(value.shape)]).encode()
            + value.reshape(-1).view(torch.uint8).numpy().tobytes())


def encoder_state_sha256(encoder):
    digest = hashlib.sha256()
    for key, value in sorted(encoder.state_dict().items()):
        digest.update(key.encode())
        try:
            raw = _tensor_bytes(value)
        except ValueError:
            raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
        digest.update(len(raw).to_bytes(8, "little")); digest.update(raw)
    return digest.hexdigest()


def _geometry_hash(records):
    import torch
    digest = hashlib.sha256()
    identities = set()
    dataset_ids = set()
    for record in records:
        key = record.dataset_id, record.member_index
        if key in identities or not record.molecule_uid:
            raise ValueError("Unique explicit source geometry identities required")
        identities.add(key); dataset_ids.add(record.dataset_id)
        x, pos, ids = record.x, record.pos, record.source_atom_ids
        n = len(x)
        if (n <= 0 or x.dtype != torch.long or x.ndim not in (1, 2)
                or x.numel() != n or pos.dtype != torch.float32 or tuple(pos.shape) != (n, 3)
                or not bool(torch.isfinite(pos).all()) or ids.dtype != torch.long
                or not torch.equal(ids.cpu().sort().values, torch.arange(n))):
            raise ValueError("Native geometry/atom identity contract differs")
        digest.update(canonical([record.dataset_id, record.molecule_uid, record.member_index]).encode())
        for tensor in (x, pos, ids):
            digest.update(_tensor_bytes(tensor))
    if not records or len(dataset_ids) != 1:
        raise ValueError("A nonempty single-dataset geometry sequence is required")
    return digest.hexdigest()


class FrozenH0Cache:
    """Store one target-free encoding per encoder/geometry/membership binding.

    The destination must be external to the source repository. Incomplete
    previous writes are preserved and rejected; no existing file is deleted.
    """

    def __init__(self, root, *, repository_root):
        self.root = Path(root).absolute()
        if self.root.resolve().is_relative_to(Path(repository_root).resolve()):
            raise ValueError("H0 tensors must remain outside the Git repository")

    def get_or_compute(self, encoder, records, *, architecture_sha256, membership_sha256,
                       device="cpu", max_graphs=32, max_native_atoms=65536,
                       max_padded_pairs=1_000_000, atom_bucket_width=16,
                       expected_plan_sha256=None, batch_graphs=None, execution_source=None):
        import torch
        from torch_geometric.data import Batch, Data
        from .v3_h0_packing import packing_plan, H0PackingBudgetError
        from .v3_h0_runtime import h0_runtime_fingerprint
        records = tuple(records)
        if batch_graphs is not None:
            if max_graphs != 32 and max_graphs != batch_graphs:
                raise ValueError("Conflicting max_graphs and legacy batch_graphs options")
            max_graphs = batch_graphs
        geometry_sha = _geometry_hash(records)
        plan = packing_plan([len(record.x) for record in records],
            record_order_sha256=canonical([[r.dataset_id, r.member_index, r.molecule_uid] for r in records]),
            max_graphs=max_graphs, max_native_atoms=max_native_atoms,
            max_padded_pairs=max_padded_pairs, atom_bucket_width=atom_bucket_width)
        if expected_plan_sha256 is not None and plan["plan_sha256"] != expected_plan_sha256:
            raise ValueError("H0 packing plan differs from the pinned request; budget drift is not allowed")
        if plan["oversized_singleton_ordinals"]:
            raise H0PackingBudgetError(plan)
        runtime = h0_runtime_fingerprint(encoder, device)
        source = {} if execution_source is None else dict(execution_source)
        source_sha = canonical(source)
        state_sha = encoder_state_sha256(encoder)
        binding = {"schema": "model_v3_train_h0_cache_v3", "encoder_sha256": state_sha,
                   "architecture_sha256": architecture_sha256,
                   "membership_sha256": membership_sha256, "geometry_sha256": geometry_sha,
                   "dimension": int(encoder.latent_dim), "packing_budget": plan["budget"],
                   "packing_budget_sha256": plan["budget_sha256"], "packing_plan_sha256": plan["plan_sha256"],
                   "effective_runtime": runtime, "effective_runtime_sha256": canonical(runtime),
                   "execution_source": source, "execution_source_sha256": source_sha}
        key = canonical(binding)
        directory = self.root / key
        manifest_path, tensor_path = directory / "manifest.json", directory / "h0.pt"
        if directory.exists():
            if not manifest_path.is_file() or not tensor_path.is_file():
                raise ValueError("Incomplete H0 cache retained; choose a fresh output root")
            metadata = json.loads(manifest_path.read_text())
            raw_sha = hashlib.sha256(tensor_path.read_bytes()).hexdigest()
            if metadata["binding"] != binding or metadata["tensor_sha256"] != raw_sha:
                raise ValueError("Frozen H0 cache bytes or source binding changed")
            payload = torch.load(tensor_path, map_location="cpu", weights_only=True)
        else:
            directory.mkdir(parents=True, exist_ok=False)
            modes = {module: module.training for module in encoder.modules()}
            rows = [None] * len(records)
            try:
                encoder.eval()
                with torch.no_grad(), torch.autocast(device_type=torch.device(device).type, enabled=False):
                    for ordinals in plan["batches"]:
                        group = tuple(records[index] for index in ordinals)
                        # Only x and pos enter H0, even if the source store also
                        # carries targets, masks, or metadata on its samples.
                        batch = Batch.from_data_list([Data(x=r.x.clone(), pos=r.pos.clone()) for r in group]).to(device)
                        raw_atoms = encoder.encode_atoms(batch)
                        if raw_atoms.dtype != torch.float32:
                            raise ValueError("H0 export must produce native FP32 output; implicit dtype conversion is forbidden")
                        atoms = raw_atoms.detach().cpu()
                        ptr = batch.ptr.cpu()
                        for i, (ordinal, record) in enumerate(zip(ordinals, group)):
                            value = atoms[int(ptr[i]):int(ptr[i+1])].clone()
                            if value.shape != (len(record.x), binding["dimension"]) or not bool(torch.isfinite(value).all()):
                                raise ValueError("H0 export shape or finiteness differs")
                            rows[ordinal] = {"molecule_uid": record.molecule_uid, "member_index": record.member_index,
                                             "h0": value, "source_atom_ids": record.source_atom_ids.cpu().clone()}
            finally:
                for module, mode in modes.items():
                    module.training = mode
            if encoder_state_sha256(encoder) != state_sha:
                raise RuntimeError("Frozen H0 export changed the encoder state")
            if h0_runtime_fingerprint(encoder, device) != runtime:
                raise RuntimeError("H0 implementation or effective runtime changed while exporting")
            if any(row is None for row in rows):
                raise RuntimeError("Packed H0 export did not restore every original native record")
            payload = {"binding": binding, "rows": rows}
            with tensor_path.open("xb") as stream:
                torch.save(payload, stream); stream.flush(); os.fsync(stream.fileno())
            metadata = {"binding": binding, "tensor_sha256": hashlib.sha256(tensor_path.read_bytes()).hexdigest(),
                        "molecules": len(rows), "atoms": sum(len(r["h0"]) for r in rows),
                        "targets_cached": False, "packing_plan": plan}
            with manifest_path.open("x") as stream:
                json.dump(metadata, stream, sort_keys=True); stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        if payload["binding"] != binding or len(payload["rows"]) != len(records):
            raise ValueError("H0 payload binding or inventory differs")
        output = []
        for row, record in zip(payload["rows"], records):
            if (row["molecule_uid"] != record.molecule_uid or row["member_index"] != record.member_index
                    or not torch.equal(row["source_atom_ids"], record.source_atom_ids.cpu())
                    or row["h0"].dtype != torch.float32
                    or row["h0"].shape != (len(record.x), binding["dimension"])
                    or not bool(torch.isfinite(row["h0"]).all())):
                raise ValueError("Cached native H0 rows differ from source members")
            output.append(MoleculeH0(record.molecule_uid, record.member_index,
                                     row["h0"].clone(), row["source_atom_ids"].clone()))
        return tuple(output), {"cache_key": key, "manifest": str(manifest_path), **metadata}
