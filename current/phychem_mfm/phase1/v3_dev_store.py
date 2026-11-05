"""Read selected native TRAIN records without opening other target records.

The metadata sidecar is a model-line projection of an already frozen store,
not a new label format or a D-1 contract. It carries only native identities,
allowed roles, offsets, shapes and hashes. Payload decoding is identical to the
existing P1DS1 native frame; no target transformation is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct

from .v3_dev_panel import ALLOWED_ROLES


def bound_json(path, expected_sha256):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512*1024**2:
        raise ValueError("Bound ordinary metadata file required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Metadata file SHA differs")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate metadata key")
            value[key] = item
        return value
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite metadata")))


@dataclass(frozen=True)
class TrainingSourceSample:
    dataset_id: str
    member_index: int
    member_uid: str
    x: object
    pos: object
    source_atom_ids: object
    targets: object
    candidate_mask: object
    supervision_mask: object
    geometry_ready: bool


class TrainOnlyPackedStore:
    """Deny non-TRAIN record access before opening the physical payload.

    Whole-store/file checksums are inherited source references, not claimed as
    remeasured here: such a measurement would read excluded target bytes.
    This consumer verifies sidecar SHA and every selected record's exact SHA.
    """

    def __init__(self, path, expected_sha256):
        document = bound_json(path, expected_sha256)
        if (document.get("schema") != "model_v3_training_role_store_v1"
                or document.get("source_complete") is not True
                or document.get("targets_in_metadata") is not False
                or document.get("native_record_hashes_preserved") is not True):
            raise ValueError("Complete TRAIN-only native metadata projection required")
        if not re.fullmatch(r"[0-9a-f]{64}", document.get("source_store_manifest_sha256", "")):
            raise ValueError("Original frozen store manifest binding required")
        self._rows, self._contracts, allowed = {}, {}, set()
        for row in document["records"]:
            required = {"dataset_id", "member_index", "member_uid", "native_n_atoms", "target_rows",
                        "tasks", "geometry_ready", "offset", "bytes", "sha256"}
            if set(row) != required or type(row["member_index"]) is not int or row["member_index"] < 0:
                raise ValueError("Target-free native record metadata schema differs")
            key = row["dataset_id"], row["member_index"]
            if key in self._rows or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
                raise ValueError("Duplicate record or invalid native SHA")
            if (type(row["offset"]) is not int or row["offset"] < 8 or type(row["bytes"]) is not int
                    or not 0 < row["bytes"] <= 4*1024**2 or not 0 < row["native_n_atoms"] <= 4096
                    or not 0 < len(row["tasks"]) <= 32
                    or row["target_rows"] not in (1, row["native_n_atoms"])
                    or type(row["geometry_ready"]) is not bool):
                raise ValueError("Bounded native frame shape/offset required")
            self._rows[key] = row
        for contract in document["contracts"]:
            key = contract["dataset_id"], str(contract["fold_id"])
            if key in self._contracts or set(contract["member_indices"]) != set(ALLOWED_ROLES):
                raise ValueError("Only explicit native TRAIN-source roles are allowed")
            if not re.fullmatch(r"[0-9a-f]{64}", contract.get("source_contract_sha256", "")):
                raise ValueError("Original frozen role contract reference required")
            seen = set()
            for role in ALLOWED_ROLES:
                indices, uids = contract["member_indices"][role], contract["ordered_members"][role]
                if len(indices) != len(uids) or len(set(indices)) != len(indices) or seen & set(indices):
                    raise ValueError("Training-source role inventory differs")
                for index, uid in zip(indices, uids):
                    row = self._rows.get((key[0], index))
                    if not row or row["member_uid"] != uid or row["tasks"] != contract["tasks"]:
                        raise ValueError("Native role/member/task source association differs")
                    allowed.add((key[0], index))
                seen.update(indices)
            self._contracts[key] = contract
        if allowed != set(self._rows):
            raise ValueError("Metadata contains records outside its declared TRAIN-source roles")
        self.group_map = {}
        for row in document["molecule_groups"]:
            key = row["dataset_id"], row["member_index"]
            if (key not in allowed or key in self.group_map or row["member_uid"] != self._rows[key]["member_uid"]
                    or not re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", row.get("full_inchikey", ""))):
                raise ValueError("Explicit native source full-molecule grouping differs")
            self.group_map[key] = {"member_uid": row["member_uid"], "full_inchikey": row["full_inchikey"]}
        if set(self.group_map) != allowed:
            raise ValueError("Complete TRAIN source-to-molecule identity mapping required")
        ref = document["records_file"]
        self._path = Path(ref["path"])
        if self._path.is_symlink() or not self._path.is_file() or self._path.stat().st_size != ref["bytes"]:
            raise ValueError("The original closed physical native payload differs")
        if any(row["offset"]+row["bytes"] > ref["bytes"] for row in self._rows.values()):
            raise ValueError("Native frame falls outside its bound physical payload")
        self.data_version = document["data_version"]
        self.integrity_scope = "TRAIN metadata and selected native records; excluded targets are not read"

    def contract(self, dataset_id, fold_id):
        from copy import deepcopy
        return deepcopy(self._contracts[dataset_id, str(fold_id)])

    def view(self, dataset_id, fold_id, *, role):
        if role not in ALLOWED_ROLES:
            raise ValueError("Only TRAIN-source roles are available")
        return tuple(self._contracts[dataset_id, str(fold_id)]["member_indices"][role])

    def native_geometry_metadata(self, dataset_id, member_index):
        if type(member_index) is not int or (dataset_id, member_index) not in self._rows:
            raise ValueError("Geometry metadata access outside declared TRAIN-source inventory")
        row = self._rows[dataset_id, member_index]
        return {key: row[key] for key in ("dataset_id", "member_index", "member_uid", "native_n_atoms", "geometry_ready")}

    def get(self, dataset_id, member_index):
        import torch
        if type(member_index) is not int or (dataset_id, member_index) not in self._rows:
            raise ValueError("Target access outside the declared TRAIN-source inventory")
        row = self._rows[dataset_id, member_index]
        before = self._path.stat()
        with self._path.open("rb") as stream:
            if stream.read(8) != b"P1DS1\x00\x00\x00":
                raise ValueError("Original native payload magic differs")
            stream.seek(row["offset"]); raw = stream.read(row["bytes"])
        after = self._path.stat()
        if ((before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                or len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]):
            raise ValueError("Selected physical native record changed")
        n, nr, nt, ready = struct.unpack_from("<4I", raw)
        if (n, nr, nt, ready) != (row["native_n_atoms"], row["target_rows"], len(row["tasks"]), int(row["geometry_ready"])):
            raise ValueError("Physical native frame shape differs")
        cursor = 16
        x = torch.tensor(struct.unpack_from("<"+"H"*n, raw, cursor), dtype=torch.long); cursor += 2*n
        if not bool(((x >= 0) & (x < 118)).all()):
            raise ValueError("Native zero-based element domain differs")
        positions = None
        if ready:
            f64 = raw[cursor:cursor+24*n]; cursor += 24*n
            f32 = raw[cursor:cursor+12*n]; cursor += 12*n
            if struct.pack("<"+"f"*(3*n), *struct.unpack("<"+"d"*(3*n), f64)) != f32:
                raise ValueError("Literal source coordinate cast differs")
            positions = torch.tensor(struct.unpack("<"+"f"*(3*n), f32), dtype=torch.float32).reshape(n, 3)
            if not bool(torch.isfinite(positions).all()):
                raise ValueError("Nonfinite native coordinates")
        targets = torch.tensor(struct.unpack_from("<"+"f"*(nr*nt), raw, cursor), dtype=torch.float32).reshape(nr, nt)
        cursor += 4*nr*nt
        candidate, supervision = raw[cursor:cursor+nr*nt], raw[cursor+nr*nt:cursor+2*nr*nt]
        if cursor+2*nr*nt != len(raw) or any(v not in (0, 1) for v in (*candidate, *supervision)):
            raise ValueError("Physical mask encoding differs")
        candidate = torch.tensor(tuple(candidate), dtype=torch.bool).reshape(nr, nt)
        supervision = torch.tensor(tuple(supervision), dtype=torch.bool).reshape(nr, nt)
        if (not bool((~supervision | candidate).all()) or not bool(torch.isfinite(targets[supervision]).all())
                or not bool(torch.isnan(targets[~supervision]).all())):
            raise ValueError("Native unknown/observed target convention differs")
        return TrainingSourceSample(dataset_id, member_index, row["member_uid"], x, positions,
            torch.arange(n, dtype=torch.long), targets, candidate, supervision, bool(ready))
