"""Byte-bound native samples and frozen ordered downstream role contracts.

This external consumer is separate from the pretraining source. Target payloads
are physical FP32 bytes, never metadata logs. A malformed annotation has no
usable sample and cannot become an unknown-label success. Missing/empty labels
remain NaN/false. No model, geometry generation or scientific selection occurs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct

SCHEMA = "phase1_frozen_downstream_store_v1"
CONTRACT_SCHEMA = "phase1_frozen_downstream_role_contract_v1"
RECORD_MAGIC = b"P1DS1\x00\x00\x00"
ROLES = ("train", "train_inner_validation", "test")
DATASETS = ("qm7", "qm9", "cyp_isoform", "az_exactsom", "expansionrx")
FULL_COUNTS = {"qm7": 7165, "qm9": 133885, "cyp_isoform": 2003, "az_exactsom": 109, "expansionrx": 7608}
MAX_METADATA_BYTES = 512 * 1024**2
MAX_FRAME_BYTES = 4 * 1024**2


class DownstreamBindingError(ValueError):
    """A frozen rule, role, physical byte or source-native sample is invalid."""


def require(condition, message):
    if not condition:
        raise DownstreamBindingError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def seal(value, field="content_sha256"):
    require(field not in value, "Seal field already present")
    value[field] = canonical(value)
    return value


def check_seal(value, field="content_sha256"):
    require(type(value) is dict and value.get(field) == canonical(
        {k: v for k, v in value.items() if k != field}), "Canonical metadata seal differs")


def loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(DownstreamBindingError("Nonfinite metadata")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DownstreamBindingError("Invalid finite UTF8 metadata") from exc


def raw_binding(path, check=lambda: None):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "Ordinary physical file required")
    digest, size = hashlib.sha256(), 0
    before = path.stat()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            check(); digest.update(block); size += len(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
            and size == after.st_size, "Input changed during byte binding")
    return {"path": str(path.absolute()), "bytes": size, "sha256": digest.hexdigest()}


def verify_binding(ref, check=lambda: None):
    require(type(ref) is dict and type(ref.get("bytes")) is int and ref["bytes"] >= 0
            and type(ref.get("sha256")) is str and len(ref["sha256"]) == 64,
            "Explicit physical file binding required")
    actual = raw_binding(ref["path"], check)
    require(actual["bytes"] == ref["bytes"] and actual["sha256"] == ref["sha256"],
            "Physical file bytes differ")
    return actual


def json_input(ref, *, maximum=MAX_METADATA_BYTES, check=lambda: None):
    require(ref["bytes"] <= maximum, "JSON input cap exceeded")
    verify_binding(ref, check)
    raw = Path(ref["path"]).read_bytes()
    require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"],
            "JSON changed after initial binding")
    return loads(raw)


def frame_hash(digest, raw):
    digest.update(struct.pack("<Q", len(raw))); digest.update(raw)


def mask_bytes(member_index, rows, candidate, supervision):
    """Stage44 physical per-task little-endian packed native mask recipe."""
    require(type(member_index) is int and member_index >= 0 and type(rows) is int and rows > 0,
            "Native mask row/index invalid")
    def packed(values):
        require(len(values) == rows and all(type(v) is bool for v in values), "Bool native mask required")
        bits = sum(int(v) << i for i, v in enumerate(values))
        return bits.to_bytes((rows + 7) // 8, "little")
    return struct.pack("<II", member_index, rows) + b"".join(packed(v) for v in (*candidate, *supervision))


def record_bytes(x, positions64, targets, candidate, supervision):
    """Owned binary representation: native rows unchanged; literal F64->F32."""
    n, rows, tasks = len(x), len(targets), len(targets[0])
    require(0 < n <= 4096 and 0 < tasks <= 32 and rows in (1, n)
            and all(type(z) is int and 0 <= z < 118 for z in x), "Native size/element domain invalid")
    require(all(len(v) == tasks for v in (*targets, *candidate, *supervision))
            and len(candidate) == len(supervision) == rows, "Target/mask shape invalid")
    require(all(type(c) is bool and type(s) is bool and (not s or c)
                for cr, sr in zip(candidate, supervision) for c, s in zip(cr, sr)),
            "Typed supervision must lie within candidates")
    for tr, sr in zip(targets, supervision):
        for value, observed in zip(tr, sr):
            require(type(value) is float and (math.isfinite(value) if observed else math.isnan(value)),
                    "Observed finite FP32 or explicit unknown NaN target required")
            if observed:
                require(math.isfinite(struct.unpack("<f", struct.pack("<f", value))[0]), "Target overflows FP32")
    ready = positions64 is not None
    raw = bytearray(struct.pack("<4I", n, rows, tasks, int(ready)))
    raw.extend(struct.pack("<" + "H" * n, *x))
    if ready:
        require(len(positions64) == n and all(len(v) == 3 for v in positions64), "Native coordinates shape differs")
        values = [float(v) for row in positions64 for v in row]
        require(all(math.isfinite(v) for v in values), "Nonfinite native coordinates")
        fp32 = struct.pack("<" + "f" * len(values), *values)
        require(all(math.isfinite(v) for v in struct.unpack("<" + "f" * len(values), fp32)), "Coordinate FP32 overflow")
        raw.extend(struct.pack("<" + "d" * len(values), *values)); raw.extend(fp32)
    raw.extend(struct.pack("<" + "f" * (rows * tasks), *(v for row in targets for v in row)))
    raw.extend(bytes(int(v) for row in candidate for v in row))
    raw.extend(bytes(int(v) for row in supervision for v in row))
    require(len(raw) <= MAX_FRAME_BYTES, "Native record byte cap exceeded")
    return bytes(raw)


@dataclass(frozen=True)
class FormalSourceSample:
    dataset_id: str
    member_index: int
    source_member_index: int
    member_uid: str
    fold_id: int | str | None
    x: object
    pos: object | None
    source_atom_ids: object
    targets: object
    candidate_mask: object
    supervision_mask: object
    geometry_ready: bool
    provenance: dict
    unavailable_reason: str | None


def validate_contract(item, rows):
    check_seal(item)
    require(item["schema_version"] == CONTRACT_SCHEMA and item["dataset_id"] in DATASETS
            and item["output_level"] in ("graph", "atom") and type(item["tasks"]) is list
            and item["tasks"] and len(item["tasks"]) == len(set(item["tasks"])) == len(item["units"]),
            "Task/output/native contract differs")
    require(item["optimizer"]["batch_graphs"] == 32 and type(item["optimizer"]["batch_graphs"]) is int
            and item["optimizer"]["epochs"] == 20 and type(item["optimizer"]["epochs"]) is int,
            "Frozen downstream B32/fixed20 contract differs")
    dataset, fold = item["dataset_id"], item["fold_id"]
    if dataset == "expansionrx":
        require(fold == "official", "Expansion official split required")
        expected = {r: [i for i, row in sorted(rows.items()) if row["declared_role"] == r] for r in ("train", "test")}
        expected["train_inner_validation"] = []
    else:
        require(type(fold) is str and fold.isascii() and fold.isdecimal() and str(int(fold)) == fold and 0 <= int(fold) < 10,
                "Original scaffold outer fold required")
        t = int(fold)
        expected = {r: [i for i, row in sorted(rows.items()) if (row["source_fold"] == t if r == "test" else
                    row["source_fold"] == (t+1)%10 if r == "train_inner_validation" else row["source_fold"] not in (t, (t+1)%10))]
                    for r in ROLES}
    require(item["member_indices"] == expected and all([rows[i]["member_uid"] for i in expected[r]] == item["ordered_members"][r]
            for r in ROLES), "Original ordered role/fold/UID membership differs")
    norm = item["normalization"]; check_seal(norm)
    require(norm["fit_scope"] == "train" and len(norm["means"]) == len(norm["scales"]) == len(norm["availability"]) == len(item["tasks"])
            and all(type(v) is bool for v in norm["availability"]), "Actual train-only normalization scope/shape differs")
    for mean, scale, available in zip(norm["means"], norm["scales"], norm["availability"]):
        require((type(mean) is float and math.isfinite(mean) and type(scale) is float and math.isfinite(scale) and scale > 0)
                if available else mean is None and scale is None, "Unavailable normalizer cannot use a fabricated scale")
    require(norm["kind"] == ("train_affine" if item["output_level"] == "graph" else "identity"),
            "Frozen target normalization kind differs")
    if item["output_level"] == "atom":
        require(all((mean == 0.0 and scale == 1.0) if available else mean is None and scale is None
                    for mean, scale, available in zip(norm["means"], norm["scales"], norm["availability"])),
                "Binary source labels use identity normalization")
    return item


class FrozenDownstreamStore:
    """Open already materialized bytes; verify all files at open and close.

    Expansion ordinals concatenate original train then test rows. The original
    side-local source_member_index and UID remain explicit and unchanged.
    Returned tensors and metadata are independently owned. This class never
    reads raw benchmark targets, invokes chemistry or invents membership.
    """
    def __init__(self, manifest_path, expected_sha256):
        ref = raw_binding(manifest_path)
        require(ref["sha256"] == expected_sha256, "Store manifest raw SHA differs")
        manifest = json_input(ref)
        check_seal(manifest)
        require(manifest.get("schema_version") == SCHEMA and manifest.get("complete") is True
                and manifest.get("annotation_complete") is True and manifest.get("scientific_choices_changed") is False,
                "Complete actual frozen-rule materialization required")
        require(manifest.get("ordered_counts") == FULL_COUNTS and manifest.get("original_member_rows") == 150770
                and manifest.get("primary_endpoints") == 32 and manifest.get("primary_cells_count") == 239,
                "Full frozen inventory required; small development panels are insufficient")
        self._manifest, self._files = manifest, [ref, *deepcopy(manifest["files"]), *deepcopy(manifest["input_files"])]
        for item in self._files[1:]:
            verify_binding(item)
        index = json_input(manifest["record_index"])
        contracts = json_input(manifest["contracts"])
        check_seal(index); check_seal(contracts)
        self._rows, self._contracts = {}, {}
        for row in index["records"]:
            check_seal(row, "record_metadata_sha256")
            key = row["dataset_id"], row["member_index"]
            require(key[0] in DATASETS and type(key[1]) is int and key not in self._rows
                    and row.get("annotation_state") != "MALFORMED", "Record index scope/state differs")
            self._rows[key] = row
        require({dataset: sum(d == dataset for d, _ in self._rows) for dataset in DATASETS} == FULL_COUNTS,
                "Full actual native record coverage differs")
        for dataset in DATASETS:
            rows = [r for (d, _), r in self._rows.items() if d == dataset]
            require([r["member_index"] for r in rows] == list(range(len(rows)))
                    and len({r["member_uid"] for r in rows}) == len(rows), "Native dataset ordinal/UID inventory differs")
            if dataset != "expansionrx":
                require(all(r["member_index"] == r["source_member_index"] and type(r["source_fold"]) is int
                            and 0 <= r["source_fold"] < 10 for r in rows), "Original scaffold source index/fold differs")
            else:
                train = [r for r in rows if r["declared_role"] == "train"]
                test = [r for r in rows if r["declared_role"] == "test"]
                require(rows == train + test and all(r["source_member_index"] == i for side in (train, test) for i, r in enumerate(side)),
                        "Original Expansion side-local indices/order differ")
        for item in contracts["contracts"]:
            validate_contract(item, {i: r for (d, i), r in self._rows.items() if d == item["dataset_id"]})
            key = item["dataset_id"], str(item["fold_id"])
            require(key not in self._contracts and item["schema_version"] == CONTRACT_SCHEMA,
                    "Duplicate or unknown role contract")
            for role in ROLES:
                ids = item["member_indices"][role]
                require(all(type(i) is int and (key[0], i) in self._rows for i in ids)
                        and len(ids) == len(set(ids)) and ids == sorted(ids), "Ordered role references differ")
                require([self._rows[key[0], i]["member_uid"] for i in ids] == item["ordered_members"][role],
                        "Role ordered UID association differs")
            require(len(set(i for role in ROLES for i in item["member_indices"][role]))
                    == sum(len(item["member_indices"][r]) for r in ROLES), "Role partition overlaps")
            self._contracts[key] = item
        require(len(self._contracts) == 41, "All original 41 downstream readout groups required")

    def view(self, dataset_id, fold_id, role):
        require(role in ROLES, "Explicit actual downstream role required")
        return tuple(self.contract(dataset_id, fold_id)["member_indices"][role])

    def contract(self, dataset_id, fold_id):
        require((dataset_id, str(fold_id)) in self._contracts, "Original dataset/fold group absent")
        return deepcopy(self._contracts[dataset_id, str(fold_id)])

    def get(self, dataset_id, member_index):
        import torch
        require(type(member_index) is int and (dataset_id, member_index) in self._rows,
                "Original source member key absent")
        row = self._rows[dataset_id, member_index]
        require(row["annotation_state"] != "MALFORMED", "Malformed annotation is not unknown supervision")
        path = Path(self._manifest["records_file"]["path"])
        with path.open("rb") as stream:
            stream.seek(row["offset"]); raw = stream.read(row["bytes"])
        require(len(raw) == row["bytes"] <= MAX_FRAME_BYTES and hashlib.sha256(raw).hexdigest() == row["sha256"],
                "Physical member payload changed")
        n, nr, nt, ready = struct.unpack_from("<4I", raw)
        require(n == row["native_n_atoms"] and nr == row["target_rows"] and nt == len(row["tasks"])
                and ready == int(row["geometry_ready"]), "Payload/native metadata differs")
        cursor = 16
        x = torch.tensor(struct.unpack_from("<" + "H" * n, raw, cursor), dtype=torch.long); cursor += 2*n
        positions = None
        if ready:
            f64 = raw[cursor:cursor+24*n]; cursor += 24*n
            f32 = raw[cursor:cursor+12*n]; cursor += 12*n
            values = struct.unpack("<" + "d" * (3*n), f64)
            require(struct.pack("<" + "f" * (3*n), *values) == f32, "Native literal coordinate cast differs")
            positions = torch.tensor(struct.unpack("<" + "f" * (3*n), f32), dtype=torch.float32).reshape(n, 3)
        targets = torch.tensor(struct.unpack_from("<" + "f" * (nr*nt), raw, cursor), dtype=torch.float32).reshape(nr, nt)
        cursor += 4*nr*nt
        cb, sb = raw[cursor:cursor+nr*nt], raw[cursor+nr*nt:cursor+2*nr*nt]
        require(cursor+2*nr*nt == len(raw) and all(v in (0, 1) for v in (*cb, *sb)), "Physical bool mask encoding differs")
        candidate = torch.tensor(tuple(cb), dtype=torch.bool).reshape(nr, nt)
        supervision = torch.tensor(tuple(sb), dtype=torch.bool).reshape(nr, nt)
        require(bool((~supervision | candidate).all()) and bool(torch.isfinite(targets[supervision]).all())
                and bool(torch.isnan(targets[~supervision]).all()), "Actual target availability contract differs")
        return FormalSourceSample(dataset_id, member_index, row["source_member_index"], row["member_uid"],
            row["source_fold"], x, positions, torch.arange(n, dtype=torch.long), targets, candidate, supervision,
            bool(ready), deepcopy(row["provenance"]), row["unavailable_reason"])

    def verify_unchanged(self):
        for ref in self._files:
            verify_binding(ref)
        return deepcopy(self._files)
