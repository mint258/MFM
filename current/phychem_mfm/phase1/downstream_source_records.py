"""Source-backed native records and consumption of saved candidate geometries.

Source files are read and hash-bound once. SDF property values and unselected
CSV values remain bytes during ordinary loading. Explicit CYP or AZ supervision
methods extract only the corresponding record's declared annotation fields. Parent member
rows are caller-supplied metadata, not independent proof of a scientific split.
No conformers, folds, formal choices, files or experiment runs are created.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import io
import json
import math
from pathlib import Path
import re

from rdkit import Chem, rdBase
import torch
from torch_geometric.data import Data

from .downstream_structures import SourceStructure, read_cyp_mol_block, read_az_raw_smiles
from .source_geometry import (SourceEncoderGeometry, build_cyp_source_encoder_geometry,
                              geometry_tensor_sha256, TENSOR_HASH_RECIPE)
from .som_atom_mapping import build_cyp_author_atom_mapping
from .som_annotation import CYP_ISOFORMS, decode_cyp_primary_annotation
from .az_annotation import GROUP_COLUMN, FLAG_COLUMN, parse_az_exact_groups
from .az_atom_mapping import build_az_author_atom_mapping
from .downstream_training import DownstreamTrainBatch
from .identity import canonical_hash
from .generated_geometry import GeneratedNativeGeometry
from .som_direction_equivalence import SomDirectionEquivalenceError, verify_cyp_direction_equivalence


RECORD_SCHEMA = "phase1_source_bound_record_v1"
SAMPLE_SCHEMA = "phase1_source_materialized_geometry_v2"
NATIVE_GRAPH_BINDING_SCHEMA = "phase1_saved_native_graph_binding_v1"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_LEDGER_BYTES = 16 * 1024 * 1024
MAX_LEDGER_ROW_BYTES = 128 * 1024
MAX_RECORDS = 5000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PROPERTY = re.compile(rb"^>[^\r\n]*<([^<>\r\n]+)>[^\r\n]*$")


class SourceRecordError(ValueError):
    """A source, parent member, saved geometry or explicit supervision is invalid."""


def _require(condition, message):
    if not condition:
        raise SourceRecordError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    _require(type(value) is str and _SHA.fullmatch(value) is not None, "Invalid lowercase SHA256")
    return value


def _limit(value, maximum, name):
    _require(type(value) is int and 0 < value <= maximum, "Invalid " + name)
    return value


def _integer_list(value, expected):
    return type(value) is list and all(type(x) is int for x in value) and value == expected


def _sealed(value, field):
    _finite_json(value)
    _require(type(value) is dict and value.get(field) == canonical_hash(
        {k: v for k, v in value.items() if k != field}), "Invalid canonical " + field)


def _finite_json(value, depth=0):
    _require(depth <= 64, "JSON metadata exceeds depth cap")
    if type(value) is float:
        _require(math.isfinite(value), "Nonfinite JSON metadata")
    elif type(value) is dict:
        for key, child in value.items():
            _require(type(key) is str, "JSON metadata keys must be strings")
            _finite_json(child, depth + 1)
    elif type(value) is list or type(value) is tuple:
        for child in value:
            _finite_json(child, depth + 1)
    else:
        _require(type(value) in (str, int, bool, type(None)), "Invalid JSON metadata scalar")


def _read_file(path, *, expected_sha256, expected_bytes=None, maximum):
    _digest(expected_sha256)
    _require(not path.is_symlink() and path.is_file(), "Source must be a regular non-symlink file")
    before = path.stat()
    _require(before.st_size <= maximum, "File exceeds byte cap")
    with path.open("rb") as handle:
        content = handle.read(maximum + 1)
    after = path.stat()
    _require(len(content) <= maximum and len(content) == before.st_size
             and (before.st_ino, before.st_size, before.st_mtime_ns) ==
                 (after.st_ino, after.st_size, after.st_mtime_ns), "File changed during bounded ingestion")
    _require(_sha(content) == expected_sha256, "Actual file bytes do not match expected SHA256")
    _require(expected_bytes is None or type(expected_bytes) is int and expected_bytes == len(content),
             "Expected file byte count differs")
    return content, {"path": str(path.resolve()), "bytes": len(content), "sha256": expected_sha256}


def source_reference(row):
    """The existing parent ledgers' stable source reference, without target access."""
    _require(type(row) is dict, "Parent source/member row must be a dict")
    if row.get("dataset") == "cyp_isoform":
        name, ordinal = row.get("source_file"), row.get("source_record_1based")
        _require(name in tuple(x + ".sdf" for x in CYP_ISOFORMS)
                 and type(ordinal) is int and ordinal > 0, "Invalid CYP source reference")
        return f"cyp:{name}:{ordinal}"
    _require(row.get("dataset") == "az_exactsom" and type(row.get("compound_id")) is str
             and 0 < len(row["compound_id"]) <= 256, "Invalid AZ source reference")
    return "az:" + row["compound_id"]


def source_ordered_graph_sha256(structure):
    """Reproduce the parent structure audit's ordered atoms/indexed bonds recipe."""
    mol = structure.mol
    return canonical_hash({
        "atoms": [[a.GetAtomicNum(), a.GetIsotope(), a.GetFormalCharge(), a.GetNumExplicitHs()]
                  for a in mol.GetAtoms()],
        "bonds": sorted([[min(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                           max(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                           str(b.GetBondType()), bool(b.GetIsAromatic())] for b in mol.GetBonds()]),
    })


def _native_graph(structure):
    mol = structure.mol
    return {
        "atoms": [(a.GetAtomicNum(), a.GetIsotope(), a.GetFormalCharge(), str(a.GetChiralTag()),
                   a.GetIsAromatic(), a.GetNumRadicalElectrons(), a.GetAtomMapNum()) for a in mol.GetAtoms()],
        "bonds": [(b.GetBeginAtomIdx(), b.GetEndAtomIdx(), str(b.GetBondType()), b.GetIsAromatic(),
                   b.GetIsConjugated(), str(b.GetStereo()), tuple(b.GetStereoAtoms()), str(b.GetBondDir()))
                  for b in mol.GetBonds()],
        "stereo_groups": [(str(g.GetGroupType()), [a.GetIdx() for a in g.GetAtoms()],
                           [b.GetIdx() for b in g.GetBonds()]) for g in mol.GetStereoGroups()],
    }


def _sdf_frames(content, maximum_records):
    """Frame opaque SDF records and exact M END-only blocks, preserving CRLF."""
    frames, start, block_end, offset = [], 0, None, 0
    for line in content.splitlines(keepends=True):
        end = offset + len(line)
        _require(end - start <= MAX_RECORD_BYTES, "SDF record exceeds byte cap")
        if line.rstrip(b"\r\n") == b"M  END" and block_end is None:
            block_end = end
        if line.strip() == b"$$$$":
            _require(block_end is not None and block_end > start, "SDF record lacks structural M END")
            frames.append((start, end, block_end))
            _require(len(frames) <= maximum_records, "SDF record count exceeds cap")
            start, block_end = end, None
        offset = end
    _require(not content[start:].strip(), "SDF has a missing delimiter or trailing unframed bytes")
    return frames


def _csv_rows(content, *, with_spans=False):
    """Byte CSV framing; only callers' structural projections are decoded."""
    offset = 3 if content.startswith(b"\xef\xbb\xbf") else 0
    start, state, field, row = offset, "start", bytearray(), []
    field_start, spans = offset, []
    while offset < len(content):
        char = content[offset]
        if state == "quoted":
            if char == 34:
                state = "after_quote"
            else:
                field.append(char)
        elif state == "after_quote" and char == 34:
            field.append(34)
            state = "quoted"
        elif char == 44 or char in (10, 13):
            row.append(bytes(field))
            spans.append((field_start, offset))
            field.clear()
            state = "start"
            if char != 44:
                end = offset + 1
                if char == 13 and end < len(content) and content[end] == 10:
                    offset += 1
                    end += 1
                _require(end - start <= MAX_RECORD_BYTES, "CSV record exceeds byte cap")
                yield (start, end, row, spans) if with_spans else (start, end, row)
                start, row = end, []
                spans = []
                field_start = end
            else:
                field_start = offset + 1
        elif state == "start" and char == 34:
            state = "quoted"
        elif state == "after_quote" or char == 34:
            raise SourceRecordError("Malformed CSV quote frame")
        else:
            field.append(char)
            state = "unquoted"
        _require(len(field) <= MAX_RECORD_BYTES, "CSV field exceeds cap")
        offset += 1
        _require(offset - start <= MAX_RECORD_BYTES, "CSV record exceeds byte cap")
    _require(state != "quoted", "Unterminated CSV quoted field")
    if row or field or state != "start":
        _require(offset - start <= MAX_RECORD_BYTES, "CSV record exceeds byte cap")
        row.append(bytes(field))
        spans.append((field_start, offset))
        yield (start, offset, row, spans) if with_spans else (start, offset, row)


@dataclass(frozen=True)
class SourceBoundRecord:
    record_id: str
    structure: SourceStructure
    member: dict
    provenance: dict
    structural_text: str
    opaque_frame: bytes


@dataclass(frozen=True)
class MaterializedSourceSample:
    record: SourceBoundRecord
    geometry: SourceEncoderGeometry | None
    status: str
    provenance: dict


@dataclass(frozen=True)
class SourceSupervisedSample:
    batch: DownstreamTrainBatch
    annotation: object
    mapping: object
    provenance: dict


class SourceRecordStore:
    """Read each declared raw file once; preserve the exact parent member order.

    source_files maps known basenames to {sha256, bytes}. Paths are derived only
    from the two known raw roots. source_rows/member_rows use existing audit
    JSONL schemas. Their file origins must be independently pinned by the caller.
    Ordinary ingestion/get does not inspect property names, values or masks.
    Returned structures/metadata are owned and may be mutated by the caller.
    """

    def __init__(self, benchmark_root, *, source_files, source_rows, member_rows,
                 max_file_bytes=MAX_FILE_BYTES, max_total_bytes=MAX_TOTAL_BYTES,
                 max_records=MAX_RECORDS):
        _limit(max_file_bytes, MAX_FILE_BYTES, "max_file_bytes")
        _limit(max_total_bytes, MAX_TOTAL_BYTES, "max_total_bytes")
        _limit(max_records, MAX_RECORDS, "max_records")
        _require(type(source_files) is dict and 0 < len(source_files) <= 10, "Explicit source-file bindings required")
        _require(isinstance(source_rows, (list, tuple)) and isinstance(member_rows, (list, tuple))
                 and 0 < len(source_rows) <= max_records and 0 < len(member_rows) <= max_records,
                 "Explicit bounded parent source/member rows required")
        root = Path(benchmark_root).resolve(strict=True)
        self._sources, self._members, self._frames, self._files = {}, {}, {}, {}
        self._csv_headers = {}
        self._bindings, total = {}, 0
        for row in source_rows:
            ref = source_reference(row)
            _require(ref not in self._sources, "Duplicate parent source reference")
            self._sources[ref] = deepcopy(row)
        uids = set()
        for row in member_rows:
            ref = source_reference(row)
            _require(ref in self._sources and ref not in self._members, "Unknown or duplicate parent member")
            _require(type(row.get("fold")) is int and 0 <= row["fold"] <= 9
                     and type(row.get("sample_uid")) is str and 0 < len(row["sample_uid"]) <= 256
                     and row["sample_uid"] not in uids, "Invalid/duplicate original member UID or fold")
            uids.add(row["sample_uid"])
            self._members[ref] = deepcopy(row)
        for name, expected in source_files.items():
            _require(type(expected) is dict and set(expected) == {"sha256", "bytes"}, "File binding requires SHA256 and bytes")
            if name in tuple(x + ".sdf" for x in CYP_ISOFORMS):
                path = root / "cyp_isoform" / "raw" / name
            else:
                _require(name == "az_120_compounds.csv", "Unsupported source basename")
                path = root / "az_exactsom" / "raw" / name
            _require(path.resolve().is_relative_to(root), "Source escapes benchmark root")
            raw, binding = _read_file(path, expected_sha256=expected["sha256"],
                                      expected_bytes=expected["bytes"], maximum=max_file_bytes)
            total += len(raw)
            _require(total <= max_total_bytes, "Total source bytes exceed cap")
            self._files[name], self._bindings[name] = raw, binding
            if name.endswith(".sdf"):
                for ordinal, (start, end, block_end) in enumerate(_sdf_frames(raw, max_records), 1):
                    self._frames[f"cyp:{name}:{ordinal}"] = (name, ordinal, start, end, block_end, None)
            else:
                reader = iter(_csv_rows(raw))
                header = next(reader, None)
                _require(header is not None, "Missing raw CSV header")
                try:
                    names = [field.decode("utf-8") for field in header[2]]
                except UnicodeError as exc:
                    raise SourceRecordError("Invalid raw CSV header UTF8") from exc
                _require(len(names) == len(set(names)) and {"Compound ID", "SMILES"}.issubset(names),
                         "Missing or duplicate raw structural CSV columns")
                self._csv_headers[name] = tuple(names)
                id_index, smiles_index = names.index("Compound ID"), names.index("SMILES")
                for ordinal, (start, end, values) in enumerate(reader, 1):
                    _require(ordinal <= max_records and len(values) == len(names), "CSV count/field shape differs")
                    try:
                        compound, smiles = values[id_index].decode("utf-8"), values[smiles_index].decode("utf-8")
                    except UnicodeError as exc:
                        raise SourceRecordError("Invalid selected structural UTF8") from exc
                    ref = "az:" + compound
                    _require(ref not in self._frames and 0 < len(compound) <= 256, "Duplicate/invalid raw Compound ID")
                    self._frames[ref] = (name, ordinal, start, end, None, smiles)
            _require(len(self._frames) <= max_records, "Total source records exceed cap")
        _require(set(self._frames) == set(self._sources), "Parent source coverage differs from actual raw frames")
        self.record_ids = tuple(self._members)
        self.source_bindings = deepcopy(self._bindings)
        self.parent_source_rows_sha256 = canonical_hash(source_rows)
        self.parent_member_rows_sha256 = canonical_hash(member_rows)

    def get(self, record_id):
        _require(record_id in self._members, "Only original retained members can be loaded")
        name, ordinal, start, end, block_end, smiles = self._frames[record_id]
        raw = self._files[name]
        structural = raw[start:block_end] if block_end is not None else smiles.encode("utf-8")
        try:
            text = structural.decode("utf-8")
            structure = read_cyp_mol_block(text) if block_end is not None else read_az_raw_smiles(text)
        except (UnicodeError, RuntimeError, ValueError) as exc:
            raise SourceRecordError("Original structural bytes cannot be loaded") from exc
        source, member = self._sources[record_id], self._members[record_id]
        _require(type(source.get("source_record_1based")) is int and source["source_record_1based"] == ordinal,
                 "Parent raw record ordinal differs")
        for parent in (source, member):
            _require(type(parent.get("n_atoms")) is int and parent["n_atoms"] == structure.n_atoms
                     and _integer_list(parent.get("atomic_numbers"), list(structure.atomic_numbers))
                     and _integer_list(parent.get("source_atom_map"), list(range(structure.n_atoms)))
                     and parent.get("ordered_graph_hash") == source_ordered_graph_sha256(structure)
                     and parent.get("inchikey") == structure.identity.inchikey, "Parent native graph/order/identity differs")
        _require(source.get("provenance", {}).get("source_sha256") == _sha(structural), "Parent raw structural byte hash differs")
        proof = {"schema_version": RECORD_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
                 "record_id": record_id, "dataset": source["dataset"], "source_file": name,
                 "source_file_sha256": self._bindings[name]["sha256"], "source_record_1based": ordinal,
                 "frame_start": start, "frame_end": end, "raw_frame_sha256": _sha(raw[start:end]),
                 "structural_sha256": _sha(structural), "structural_end": block_end,
                 "native_graph_sha256": canonical_hash(_native_graph(structure)),
                 "native_atomic_numbers_sha256": canonical_hash(structure.atomic_numbers),
                 "graph_identity_inchikey": structure.identity.inchikey,
                 "sample_uid": member["sample_uid"], "fold": member["fold"],
                 "parent_source_row_sha256": canonical_hash(source), "parent_member_row_sha256": canonical_hash(member),
                 "parent_membership_independently_verified": False,
                 "source_bytes_and_native_order_verified": True,
                 "annotation_values_decoded": False, "annotation_truth_verified": False}
        proof["record_binding_sha256"] = canonical_hash(proof)
        return SourceBoundRecord(record_id, structure, deepcopy(member), proof, text, raw[start:end])

    def build_cyp_supervised_sample(self, record_id, *, sample, role, empty_policy):
        """Explicit primary-property consumption; callers must restrict real roles.

        Only train/train_inner_validation are supported. No role string proves
        a correct scientific split. Tests use synthetic SDF properties; ordinary
        real full-scope ingestion must not call this method before target scope
        is established. No other property value is decoded.
        """
        _require(role in ("train", "train_inner_validation"), "Only explicit training-source roles supported")
        record = self.get(record_id)
        _require(record.provenance["dataset"] == "cyp_isoform" and type(sample) is MaterializedSourceSample
                 and sample.status == "GEOMETRY_READY" and sample.geometry is not None,
                 "Ready native CYP geometry is required")
        reparse_binding = _source_reparse_binding(sample.record, record)
        _sealed(sample.provenance, "sample_provenance_sha256")
        _require(sample.provenance["record_binding_sha256"] == sample.record.provenance["record_binding_sha256"]
                 and sample.provenance["geometry_provenance_sha256"] == sample.geometry.provenance["geometry_provenance_sha256"],
                 "Sample/geometry receipt differs")
        _validate_geometry_tensors(sample.geometry, record.structure)
        primary, property_proof = _primary_property(record)
        with rdBase.BlockLogs():
            supplier = Chem.ForwardSDMolSupplier(io.BytesIO(record.structural_text.encode("utf-8") + b"\n$$$$\n"))
            author = next(supplier, None)
        _require(author is not None, "Independent default author supplier failed")
        mapping = build_cyp_author_atom_mapping(record.structure.mol, author,
            source_file=record.provenance["source_file"], source_file_sha256=record.provenance["source_file_sha256"],
            source_record_1based=record.provenance["source_record_1based"],
            source_block_sha256=record.provenance["structural_sha256"])
        annotation = decode_cyp_primary_annotation(primary, mapping,
            isoform=record.provenance["source_file"][:-4], empty_policy=empty_policy)
        n = record.structure.n_atoms
        targets = torch.tensor([float("nan") if v is None else float(v) for v in annotation.labels],
                               dtype=torch.float32).reshape(n, 1)
        candidate = torch.tensor(annotation.candidate_mask, dtype=torch.bool).reshape(n, 1)
        supervision = torch.tensor(annotation.supervision_mask, dtype=torch.bool).reshape(n, 1)
        data = sample.geometry.encoder_batch
        batch = DownstreamTrainBatch(Data(**{k: getattr(data, k).clone() for k in ("x", "pos", "batch", "ptr")}),
                                    (record.member["sample_uid"],), sample.geometry.source_atom_ids.clone(),
                                    targets, candidate, supervision, role)
        proof = {"schema_version": "phase1_source_bound_cyp_supervision_v2", "state": "NOT_FROZEN",
                 "formal_eligible": False, "role": role, "record_binding_sha256": record.provenance["record_binding_sha256"],
                 "sample_provenance_sha256": sample.provenance["sample_provenance_sha256"],
                 "property": property_proof, "annotation_provenance_sha256": annotation.provenance["annotation_provenance_sha256"],
                 "mapping_provenance_sha256": mapping.provenance["mapping_provenance_sha256"],
                 "source_reparse_binding": reparse_binding,
                 "same_ingested_record_property_association_verified": True,
                 "annotation_truth_verified": False, "scientific_split_role_independently_verified": False}
        proof["supervision_provenance_sha256"] = canonical_hash(proof)
        return SourceSupervisedSample(batch, annotation, mapping, proof)

    def build_az_supervised_sample(self, record_id, *, sample, role, label_policy, empty_policy):
        """Consume two complete same-frame AZ fields under an explicit policy.

        strict_exact_binary_set projects the strict parser's preserved groups;
        it is not literal author-loader replication or a frozen negative-label
        policy. Empty/no-exact/extended-only records are rejected or unknown.
        Ordinary loading never calls this method. Real target scope is caller
        responsibility; role strings cannot prove a scientific training split.
        """
        _require(role in ("train", "train_inner_validation"), "Only explicit training-source roles supported")
        _require(label_policy == "strict_exact_binary_set" and empty_policy in ("reject", "preserve_unknown"),
                 "Explicit supported AZ label and empty policies required")
        record = self.get(record_id)
        _require(record.provenance["dataset"] == "az_exactsom" and type(sample) is MaterializedSourceSample
                 and sample.status == "GEOMETRY_READY" and sample.geometry is not None,
                 "Ready native AZ geometry is required")
        reparse_binding = _source_reparse_binding(sample.record, record)
        _sealed(sample.provenance, "sample_provenance_sha256")
        _require(sample.provenance.get("schema_version") == SAMPLE_SCHEMA
                 and sample.provenance.get("status") == "GEOMETRY_READY"
                 and sample.provenance["record_binding_sha256"] == sample.record.provenance["record_binding_sha256"]
                 and sample.provenance["geometry_provenance_sha256"] == sample.geometry.provenance["geometry_provenance_sha256"],
                 "AZ sample/geometry receipt differs")
        _validate_geometry_tensors(sample.geometry, record.structure)
        _validate_az_saved_coordinates(sample)
        mapping = build_az_author_atom_mapping(record.structure.mol, record.structural_text,
            source_file=record.provenance["source_file"], source_file_sha256=record.provenance["source_file_sha256"],
            source_record_1based=record.provenance["source_record_1based"],
            raw_frame_sha256=record.provenance["raw_frame_sha256"], source_smiles_sha256=record.provenance["structural_sha256"])
        # All molecule/member/geometry guards precede any annotation decoding.
        groups, flags, fields = _az_annotation_fields(record, self._csv_headers[record.provenance["source_file"]])
        annotation = parse_az_exact_groups(groups, flags, n_author_atoms=len(mapping.author_to_native))
        n, exact_ids = record.structure.n_atoms, annotation.exact_author_ids
        _require(exact_ids or empty_policy == "preserve_unknown", "AZ record has no exact positive under reject policy")
        targets = torch.full((n, 1), float("nan"), dtype=torch.float32)
        candidate = torch.ones((n, 1), dtype=torch.bool)
        supervision = torch.zeros((n, 1), dtype=torch.bool)
        if exact_ids:
            targets.zero_()
            supervision.fill_(True)
            targets[[mapping.author_to_native[index] for index in exact_ids], 0] = 1.
        data = sample.geometry.encoder_batch
        batch = DownstreamTrainBatch(Data(**{k: getattr(data, k).clone() for k in ("x", "pos", "batch", "ptr")}),
                                    (record.member["sample_uid"],), sample.geometry.source_atom_ids.clone(),
                                    targets, candidate, supervision, role)
        proof = {"schema_version": "phase1_source_bound_az_supervision_v1", "state": "NOT_FROZEN",
                 "formal_eligible": False, "dataset": "az_exactsom", "role": role,
                 "label_policy": label_policy, "empty_policy": empty_policy,
                 "record_binding_sha256": record.provenance["record_binding_sha256"],
                 "sample_provenance_sha256": sample.provenance["sample_provenance_sha256"],
                 "fields": fields, "annotation_provenance_sha256": annotation.provenance["annotation_provenance_sha256"],
                 "mapping_provenance_sha256": mapping.provenance["mapping_provenance_sha256"],
                 "source_reparse_binding": reparse_binding, "same_ingested_record_property_association_verified": True,
                 "annotation_state": annotation.annotation_state, "supervision_state": "STRICT_EXACT_BINARY_PROJECTION" if exact_ids else "UNKNOWN",
                 "author_literal_loader_reproduced": False,
                 "author_difference": "strict parser retains empty groups/cardinality; author drops empty groups before matching flags",
                 "candidate_scope": "all native/default raw-SMILES parser atoms; no element or hydrogen exclusion",
                 "chemical_negative_truth_verified": False, "annotation_truth_verified": False,
                 "annotation_completeness_verified": False, "author_version_reproduced": False,
                 "scientific_split_role_independently_verified": False,
                 "task_scope": "single AZ exact-SoM task; not an experimentally assigned CYP isoform",
                 "geometry_preserved": True, "no_geometry_generation": True}
        proof["supervision_provenance_sha256"] = canonical_hash(proof)
        return SourceSupervisedSample(batch, annotation, mapping, proof)


def _validate_az_saved_coordinates(sample):
    """Check actual owned FP64/cast transport in addition to the common tensors."""
    geometry, source = sample.geometry, sample.record.structure
    _require(type(geometry) is GeneratedNativeGeometry, "AZ requires the existing saved generated geometry payload")
    coordinates, proof, positions = geometry.native_coordinates_float64, geometry.provenance, geometry.encoder_batch.pos
    _require(isinstance(coordinates, torch.Tensor) and coordinates.device.type == "cpu" and coordinates.dtype == torch.float64
             and coordinates.shape == positions.shape and not coordinates.requires_grad and bool(torch.isfinite(coordinates).all())
             and geometry_tensor_sha256(coordinates) == proof.get("generated_native_coordinates_float64_sha256")
             and torch.equal(coordinates.to(torch.float32).view(torch.int32), positions.view(torch.int32))
             and proof.get("quantization_max_abs_error") == float((coordinates - positions.to(torch.float64)).abs().max().item()),
             "Actual saved AZ FP64/cast transport differs")
    _require(proof.get("source_sha256") == source.provenance["source_sha256"]
             and proof.get("source_native_graph_sha256") == canonical_hash(_native_graph(source)),
             "Saved AZ geometry belongs to a different native source graph")


def _az_annotation_fields(record, names):
    """Decode exactly the two complete selected values from one opaque frame.

    Physical token spans include CSV quotes/escapes; unquoted field-value bytes
    are a separate hash domain. No trimming, partial-prefix decode or decoding
    of other values occurs. All header names were checked during ingestion.
    """
    required = ("Compound ID", "SMILES", GROUP_COLUMN, FLAG_COLUMN)
    _require(all(name in names for name in required), "Missing exact AZ source annotation columns")
    framed = list(_csv_rows(record.opaque_frame, with_spans=True))
    _require(len(framed) == 1 and framed[0][0] == 0 and framed[0][1] == len(record.opaque_frame)
             and len(framed[0][2]) == len(names), "AZ annotation frame/column shape differs")
    _, _, values, spans = framed[0]
    _require(values[names.index("Compound ID")] == record.record_id[3:].encode("utf-8")
             and values[names.index("SMILES")] == record.structural_text.encode("utf-8"),
             "AZ same-frame Compound ID/raw SMILES differ")
    decoded, bindings = [], {}
    for column in (GROUP_COLUMN, FLAG_COLUMN):
        index = names.index(column)
        start, end = spans[index]
        value, token = values[index], record.opaque_frame[start:end]
        _require(len(value) <= 65536 and len(token) <= 2 * 65536 + 2, "Selected AZ field exceeds bounded size")
        try:
            text = value.decode("utf-8")
        except UnicodeError as exc:
            raise SourceRecordError("Selected complete AZ field has invalid UTF8") from exc
        decoded.append(text)
        bindings[column] = {"column": column, "physical_token_start_in_frame": start, "physical_token_end_in_frame": end,
            "physical_token_start_in_file": record.provenance["frame_start"] + start,
            "physical_token_end_in_file": record.provenance["frame_start"] + end,
            "physical_csv_token_bytes": len(token), "physical_csv_token_sha256": _sha(token),
            "csv_unquoted_value_bytes": len(value), "csv_unquoted_value_sha256": _sha(value),
            "decoded_field_utf8_bytes": len(text.encode("utf-8")), "decoded_field_utf8_sha256": _sha(text.encode("utf-8")),
            "decode_transform": "CSV unquote/doubled-quote unescape then complete strict UTF8; no value trimming",
            "source_file_sha256": record.provenance["source_file_sha256"],
            "source_record_1based": record.provenance["source_record_1based"], "raw_frame_sha256": record.provenance["raw_frame_sha256"]}
    return decoded[0], decoded[1], bindings


def _validate_record(record):
    _require(type(record) is SourceBoundRecord and type(record.opaque_frame) is bytes, "Actual source record required")
    _sealed(record.provenance, "record_binding_sha256")
    _require(_sha(record.opaque_frame) == record.provenance["raw_frame_sha256"]
             and _sha(record.structural_text.encode("utf-8")) == record.provenance["structural_sha256"]
             and record.structure.provenance["source_sha256"] == record.provenance["structural_sha256"]
             and record.provenance["sample_uid"] == record.member["sample_uid"]
             and record.provenance["fold"] == record.member["fold"]
             and canonical_hash(record.member) == record.provenance["parent_member_row_sha256"]
             and canonical_hash(_native_graph(record.structure)) == record.provenance["native_graph_sha256"]
             and tuple(a.GetAtomicNum() for a in record.structure.mol.GetAtoms()) == record.structure.atomic_numbers
             and record.structure.x == tuple(z - 1 for z in record.structure.atomic_numbers)
             and record.structure.source_atom_map == tuple(range(record.structure.n_atoms))
             and canonical_hash(record.structure.atomic_numbers) == record.provenance["native_atomic_numbers_sha256"],
             "Record content/member/native graph binding changed")


def _source_reparse_binding(sample_record, fresh_record):
    """Prove the same raw frame/member before any supplied PRIMARY is decoded."""
    _validate_record(sample_record)
    _validate_record(fresh_record)
    allowed = {"native_graph_sha256", "record_binding_sha256"}
    _require(sample_record.record_id == fresh_record.record_id
             and sample_record.structural_text == fresh_record.structural_text
             and sample_record.opaque_frame == fresh_record.opaque_frame
             and sample_record.member == fresh_record.member
             and {k: v for k, v in sample_record.provenance.items() if k not in allowed}
                 == {k: v for k, v in fresh_record.provenance.items() if k not in allowed},
             "Geometry belongs to a different source frame/member record")
    try:
        receipt = verify_cyp_direction_equivalence(sample_record.structure.mol, fresh_record.structure.mol)
    except SomDirectionEquivalenceError as exc:
        raise SourceRecordError("Same-source reparse lacks conservative ordered structure proof") from exc
    _sealed(receipt, "receipt_sha256")
    _require(receipt.get("status") in ("EXACT_ORDERED_SIGNATURE", "VERIFIED_DIRECTION_COMPONENT_INVERSION")
             and receipt.get("all_other_ordered_fields_exact_match") is True
             and receipt.get("original_molecules_preserved") is True, "Invalid source reparse proof")
    proof = {"schema_version": "phase1_same_source_reparse_binding_v1", "state": "NOT_FROZEN", "formal_eligible": False,
             "record_id": fresh_record.record_id, "roles": {"candidate": "sample_record", "author": "fresh_source_record"},
             "sample_record_binding_sha256": sample_record.provenance["record_binding_sha256"],
             "fresh_record_binding_sha256": fresh_record.provenance["record_binding_sha256"],
             "sample_native_graph_sha256": sample_record.provenance["native_graph_sha256"],
             "fresh_native_graph_sha256": fresh_record.provenance["native_graph_sha256"],
             "literal_record_binding_hash_match": sample_record.provenance["record_binding_sha256"] == fresh_record.provenance["record_binding_sha256"],
             "raw_frame_sha256": fresh_record.provenance["raw_frame_sha256"],
             "structural_sha256": fresh_record.provenance["structural_sha256"],
             "parent_member_row_sha256": fresh_record.provenance["parent_member_row_sha256"],
             "all_record_metadata_except_graph_and_binding_hashes_exact": True,
             "same_raw_frame_member_and_native_order_verified": True, "source_original_molecules_preserved": True,
             "direction_equivalence": receipt, "direction_equivalence_receipt_sha256": receipt["receipt_sha256"],
             "annotation_truth_verified": False, "author_version_reproduced": False,
             "scope": "current-runtime association only; property/negative/site truth not inferred"}
    proof["source_reparse_binding_sha256"] = canonical_hash(proof)
    return proof


def _primary_property(record):
    block_bytes = record.structural_text.encode("utf-8")
    _require(record.opaque_frame.startswith(block_bytes), "Structural block is not the source frame prefix")
    offset, matches = len(block_bytes), []
    lines = record.opaque_frame[offset:].splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index]
        header = _PROPERTY.fullmatch(line.rstrip(b"\r\n"))
        offset += len(line)
        index += 1
        if header is None:
            continue
        start, values = offset, []
        while index < len(lines) and lines[index].rstrip(b"\r\n"):
            value = lines[index]
            if header.group(1) == b"PRIMARY_SOM":
                _require(value.strip() != b"$$$$" and _PROPERTY.fullmatch(value.rstrip(b"\r\n")) is None,
                         "Unterminated/ambiguous PRIMARY_SOM property")
            else:
                _require(value.strip() != b"$$$$", "Unterminated SDF property")
            values.append(value)
            offset += len(value)
            index += 1
        end = offset
        if header.group(1) != b"PRIMARY_SOM":
            continue
        raw = b"".join(values)
        _require(len(raw) <= 65536, "PRIMARY_SOM raw bytes exceed cap")
        try:
            text = raw.rstrip(b"\r\n").decode("utf-8")
        except UnicodeError as exc:
            raise SourceRecordError("Selected PRIMARY_SOM property has invalid UTF8") from exc
        matches.append((text, {"property_name": "PRIMARY_SOM", "property_start_in_frame": start,
                               "property_end_in_frame": end, "raw_property_bytes": len(raw),
                               "raw_property_sha256": _sha(raw), "decoded_property_utf8_sha256": _sha(text.encode("utf-8")),
                               "decode_transform": "remove terminal CR/LF only; UTF8 strict; internal whitespace retained",
                               "raw_frame_sha256": record.provenance["raw_frame_sha256"]}))
    _require(len(matches) == 1, "Exactly one present PRIMARY_SOM property is required")
    return matches[0]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate ledger JSON key")
        result[key] = value
    return result


class ClosedCandidateLedger:
    """Ingest one closed, byte-pinned candidate artifact without generating anything."""

    def __init__(self, path, *, expected_sha256, max_bytes=MAX_LEDGER_BYTES, max_records=MAX_RECORDS):
        _limit(max_bytes, MAX_LEDGER_BYTES, "max_bytes")
        _limit(max_records, MAX_RECORDS, "max_records")
        content, self._binding = _read_file(Path(path), expected_sha256=expected_sha256, maximum=max_bytes)
        _require(content.endswith(b"\n") and not content.startswith(b"\xef\xbb\xbf"), "Ledger requires closed UTF8 JSONL")
        self._rows = {}
        for sequence, line in enumerate(content.splitlines(keepends=True)):
            _require(sequence < max_records and len(line) <= MAX_LEDGER_ROW_BYTES and line.endswith(b"\n"), "Ledger row cap/tail differs")
            try:
                row = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object,
                                 parse_constant=lambda _: (_ for _ in ()).throw(SourceRecordError("Nonfinite JSON constant")))
                _sealed(row, "record_provenance_sha256")
            except (UnicodeError, ValueError, RecursionError) as exc:
                raise SourceRecordError("Invalid bounded candidate JSON row") from exc
            ref = row.get("record_id")
            _require(type(ref) is str and ref == source_reference(row) and ref not in self._rows
                     and type(row.get("sequence")) is int and row["sequence"] == sequence, "Candidate reference/cursor differs")
            _require(row.get("status") in ("GENERATED_CANDIDATE_READY", "GENERATION_FAILED")
                     and row.get("original_molecule_unchanged") is True
                     and type(row.get("fold")) is int and 0 <= row["fold"] <= 9
                     and type(row.get("native_n_atoms")) is int and 0 < row["native_n_atoms"] <= 4096,
                     "Invalid candidate outcome/count/fold")
            if row["status"] == "GENERATION_FAILED":
                _require(type(row.get("failure_category")) is str and row["failure_category"]
                         and all(k not in row for k in ("geometry", "generated_native_coordinates_float64", "encoder_native_coordinates_float32")),
                         "Failure cannot contain ready geometry")
            self._rows[ref] = row
        _require(bool(self._rows), "Empty candidate ledger")
        self.record_ids = tuple(self._rows)

    @property
    def binding(self):
        return deepcopy(self._binding)

    def get(self, record_id):
        _require(record_id in self._rows, "Missing candidate for original member")
        return deepcopy(self._rows[record_id])


def _validate_geometry_tensors(geometry, structure):
    proof = geometry.provenance
    _sealed(proof, "geometry_provenance_sha256")
    n, data = structure.n_atoms, geometry.encoder_batch
    expected = {"x": torch.tensor(structure.x, dtype=torch.long),
                "batch": torch.zeros(n, dtype=torch.long), "ptr": torch.tensor([0, n], dtype=torch.long),
                "source_atom_ids": torch.arange(n, dtype=torch.long)}
    tensors = {k: getattr(data, k, None) for k in ("x", "pos", "batch", "ptr")}
    tensors["source_atom_ids"] = geometry.source_atom_ids
    _require(set(data.keys()) == {"x", "pos", "batch", "ptr"}, "Only target-free encoder fields are permitted")
    for name, target in expected.items():
        value = tensors[name]
        _require(isinstance(value, torch.Tensor) and value.device.type == "cpu" and value.dtype == torch.long
                 and torch.equal(value, target), "Native tensor order/IDs differ")
    pos = tensors["pos"]
    _require(isinstance(pos, torch.Tensor) and pos.device.type == "cpu" and pos.dtype == torch.float32
             and pos.shape == (n, 3) and not pos.requires_grad and bool(torch.isfinite(pos).all()), "Invalid native FP32 positions")
    _require(proof.get("encoder_tensor_hashes") == {k: geometry_tensor_sha256(v) for k, v in tensors.items()}
             and proof.get("tensor_hash_recipe") == TENSOR_HASH_RECIPE, "Actual geometry tensor hashes differ")


def materialize_geometry(record, *, candidates: ClosedCandidateLedger, source_units):
    """Use original parsed 3D coords or the supplied saved candidate; never generate.

    source_units is the explicit original-source declaration ('angstrom'), not
    independent unit truth. Failed candidates remain NOT_READY in the result.
    Mixing source/generated paths here is transport support, not protocol choice.
    """
    _validate_record(record)
    _require(type(candidates) is ClosedCandidateLedger and source_units == "angstrom", "Explicit candidate artifact and units required")
    source = record.structure
    original = source.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    try:
        is_source_3d = (record.provenance["dataset"] == "cyp_isoform"
                        and source.mol.GetNumConformers() == 1 and source.mol.GetConformer().Is3D())
        row, native_graph_binding = None, None
        if is_source_3d:
            _require(record.record_id not in candidates.record_ids, "Source-3D member must not be replaced by a generated candidate")
            geometry = build_cyp_source_encoder_geometry(record.structural_text, source_units=source_units)
            basis, status = "ORIGINAL_SOURCE_3D", "GEOMETRY_READY"
        else:
            row = candidates.get(record.record_id)
            _require(row.get("dataset") == record.provenance["dataset"]
                     and row.get("sample_uid") == record.member["sample_uid"] and row.get("fold") == record.member["fold"]
                     and row.get("native_n_atoms") == source.n_atoms
                     and row.get("source_record_1based") == record.provenance["source_record_1based"]
                     and row.get("source_file_sha256") == record.provenance["source_file_sha256"]
                     and row.get("source_structure_sha256") == record.provenance["structural_sha256"], "Candidate source/member association differs")
            material = canonical_hash({"recipe": "native_etkdgv3_mmff94_seed_v1", "atomic_numbers": source.atomic_numbers,
                                       "ordered_graph_hash": source_ordered_graph_sha256(source)})
            _require(row.get("seed_material_sha256") == material and type(row.get("seed")) is int
                     and row["seed"] == 1 + int(material[:8], 16) % (2**31 - 2), "Candidate graph-only seed differs")
            basis = "SAVED_GENERATED_CANDIDATE"
            if row["status"] == "GENERATION_FAILED":
                geometry, status = None, "NOT_READY"
            else:
                geometry, native_graph_binding = _saved_geometry(row, source)
                status = "GEOMETRY_READY"
        if geometry is not None:
            _validate_geometry_tensors(geometry, source)
        proof = {"schema_version": SAMPLE_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
                 "status": status, "record_binding_sha256": record.provenance["record_binding_sha256"],
                 "geometry_basis": basis, "geometry_provenance_sha256": geometry.provenance["geometry_provenance_sha256"] if geometry else None,
                 "candidate_artifact": deepcopy(candidates.binding) if row is not None else None,
                 "candidate_row_sha256": row["record_provenance_sha256"] if row else None,
                 "failure_category": row.get("failure_category") if row else None,
                 "native_source_graph_binding": native_graph_binding,
                 "native_source_graph_binding_scope": "ready cached geometry only; not applicable to original source or failed candidates",
                 "source_units_independently_verified": False, "chemical_geometry_independently_verified": False,
                 "source_preserved": True, "member_and_fold_preserved": True, "annotation_values_decoded": False}
        proof["sample_provenance_sha256"] = canonical_hash(proof)
        return MaterializedSourceSample(record, geometry, status, proof)
    finally:
        _require(source.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == original, "Materialization changed original source mol")


def _saved_native_graph_binding(row, source, saved_sha):
    """Bind a saved digest without discarding current source direction fields.

    A digest-matching copy is a reconstruction, not the historical source mol
    or an independent author supplier. Only a bounded existing-sign search is
    allowed; exactly one hit then requires one full conservative paired proof.
    """
    _digest(saved_sha)
    current_graph = _native_graph(source)
    current_sha = canonical_hash(current_graph)
    original = source.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    binding = {"schema_version": NATIVE_GRAPH_BINDING_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
               "current_native_graph_sha256": current_sha, "saved_native_graph_sha256": saved_sha,
               "literal_native_graph_hash_match": current_sha == saved_sha,
               "source_original_direction_flags_modified": False, "source_original_molecule_preserved": True,
               "reconstruction_copy_direction_flags_modified": False,
               "roles": {"direction_proof_candidate": "source_current", "direction_proof_author": "digest_matched_copy"},
               "historical_source_molecule_recovered": False, "annotation_truth_verified": False,
               "source_units_or_geometry_truth_verified": False,
               "search": {"performed": False, "maximum_signed_bonds": 8, "maximum_assignments": 256,
                          "assignments_examined": 0}, "direction_equivalence": None,
               "current_raw_direction_flags": [bond[-1] for bond in current_graph["bonds"]]}
    try:
        if current_sha == saved_sha:
            binding.update(status="EXACT_NATIVE_GRAPH_HASH", matched_copy_native_graph_sha256=None,
                           ordered_native_graph_semantics="literal current/saved digest equality")
        else:
            _require(row.get("dataset") == "cyp_isoform" and row.get("status") == "GENERATED_CANDIDATE_READY"
                     and source.provenance.get("source_kind") == "mol_block",
                     "Saved native direction binding supports ready CYP mol blocks only")
            signed = [bond.GetIdx() for bond in source.mol.GetBonds()
                      if str(bond.GetBondDir()) in ("ENDUPRIGHT", "ENDDOWNRIGHT")]
            _require(0 < len(signed) <= 8 and all(
                str(source.mol.GetBondWithIdx(index).GetBondType()) == "SINGLE"
                and not source.mol.GetBondWithIdx(index).GetIsAromatic() for index in signed),
                "Saved native direction search exceeds ordinary signed SINGLE scope")
            reconstruction, matched, matched_assignment = Chem.Mol(source.mol), None, None
            count = 1 << len(signed)
            for assignment in range(count):
                for offset, index in enumerate(signed):
                    reconstruction.GetBondWithIdx(index).SetBondDir(
                        Chem.BondDir.ENDUPRIGHT if assignment & (1 << offset) else Chem.BondDir.ENDDOWNRIGHT)
                if canonical_hash(_native_graph(replace(source, mol=reconstruction))) == saved_sha:
                    _require(matched is None, "Saved native digest has multiple direction assignments")
                    matched, matched_assignment = Chem.Mol(reconstruction), assignment
            _require(matched is not None, "Saved native graph digest has no bounded direction-only match")
            matched_structure = replace(source, mol=matched)
            matched_graph = _native_graph(matched_structure)
            # One unique hash hit gets one proof. A proof rejection cannot cause
            # another parse, another hit search or a direction-field omission.
            matched_before = matched.ToBinary(Chem.PropertyPickleOptions.AllProps)
            try:
                receipt = verify_cyp_direction_equivalence(source.mol, matched)
            except SomDirectionEquivalenceError as exc:
                raise SourceRecordError("Saved native direction-only match lacks conservative equivalence proof") from exc
            _require(matched.ToBinary(Chem.PropertyPickleOptions.AllProps) == matched_before,
                     "Direction verifier changed reconstruction copy")
            _sealed(receipt, "receipt_sha256")
            _require(receipt.get("status") == "VERIFIED_DIRECTION_COMPONENT_INVERSION"
                     and receipt.get("ordered_signature_exact_match") is False
                     and receipt.get("all_other_ordered_fields_exact_match") is True
                     and receipt.get("original_molecules_preserved") is True,
                     "Saved native direction proof does not establish complete component inversion")
            binding.update(status="VERIFIED_SAVED_NATIVE_DIRECTION_COMPONENT_INVERSION",
                           matched_copy_native_graph_sha256=canonical_hash(matched_graph),
                           matched_copy_raw_direction_flags=[bond[-1] for bond in matched_graph["bonds"]],
                           reconstruction_copy_direction_flags_modified=True,
                           ordered_native_graph_semantics="existing current-runtime conservative direction-component proof",
                           search={"performed": True, "maximum_signed_bonds": 8, "maximum_assignments": 256,
                                   "existing_signed_bond_ids": signed, "assignments_examined": count,
                                   "unique_matching_assignment": matched_assignment, "unique_digest_match": True},
                           direction_equivalence=receipt, direction_equivalence_receipt_sha256=receipt["receipt_sha256"])
        binding["native_source_graph_binding_sha256"] = canonical_hash(binding)
        return binding
    finally:
        _require(source.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == original,
                 "Saved native graph binding changed original source molecule")


def _saved_geometry(row, source):
    n, proof = source.n_atoms, deepcopy(row.get("geometry"))
    _sealed(proof, "geometry_provenance_sha256")
    _require(proof.get("schema_version") == "phase1_native_generated_geometry_v1" and proof.get("state") == "NOT_FROZEN"
             and proof.get("formal_eligible") is False and type(proof.get("mmff_status")) is int and proof["mmff_status"] == 0
             and proof.get("source_sha256") == source.provenance["source_sha256"]
             and proof.get("source_atomic_number_order_sha256") == canonical_hash(source.atomic_numbers)
             and proof.get("graph_identity", {}).get("inchikey") == source.identity.inchikey, "Saved geometry native source proof differs")
    native_graph_binding = _saved_native_graph_binding(row, source, proof.get("source_native_graph_sha256"))
    _require(_integer_list(row.get("native_atomic_numbers"), list(source.atomic_numbers))
             and _integer_list(row.get("source_atom_ids"), list(range(n)))
             and _integer_list(proof.get("native_to_work_atom_ids"), list(range(n)))
             and type(proof.get("extra_work_h_encoder_rows")) is int and proof["extra_work_h_encoder_rows"] == 0
             and type(proof.get("source_n_atoms")) is int and type(proof.get("source_native_rows")) is int
             and proof["source_n_atoms"] == proof["source_native_rows"] == n, "Saved native atom/mapping metadata differs")
    recipe = proof.get("recipe")
    _require(type(recipe) is dict and proof.get("recipe_sha256") == canonical_hash(recipe)
             and recipe.get("randomSeed") == row["seed"] and recipe.get("embedding") == "ETKDGv3"
             and recipe.get("embedding_calls") == 1 and recipe.get("returned_conformers") == 1
             and recipe.get("maxIterations") == 200 and recipe.get("timeout_seconds") == 2
             and recipe.get("numThreads") == 1 and recipe.get("enforceChirality") is True
             and recipe.get("mmff_variant") == "MMFF94" and recipe.get("mmff_max_iterations") == 500
             and recipe.get("fallback") == "none" and recipe.get("rdkit_version") == rdBase.rdkitVersion
             and recipe.get("use_legacy_stereo_perception") is True
             and all(type(recipe.get(k)) is int for k in ("randomSeed", "embedding_calls", "returned_conformers",
                                                         "maxIterations", "timeout_seconds", "numThreads", "mmff_max_iterations")),
             "Saved fixed recipe/version differs")
    _require(all(proof.get(k) is True for k in ("source_structure_preserved", "native_graph_preserved", "tensor_transport_verified"))
             and all(proof.get(k) is False for k in ("atom_permutation_applied", "centering_applied", "scaling_applied",
                                                     "source_units_independently_verified", "output_units_independently_verified",
                                                     "chemical_geometry_independently_verified"))
             and proof.get("output_units") == "angstrom", "Saved geometry preservation/truth boundary differs")
    _sealed(proof.get("reader_provenance"), "identity_provenance_hash")
    _require(proof["reader_provenance"].get("source_sha256") == source.provenance["source_sha256"], "Saved reader source bytes differ")
    arrays = []
    for key in ("generated_native_coordinates_float64", "encoder_native_coordinates_float32"):
        values = row.get(key)
        _require(type(values) is list and len(values) == n
                 and all(type(v) is list and len(v) == 3 and all(type(x) is float and math.isfinite(x) for x in v) for v in values),
                 "Saved coordinate literal shape/type differs")
        arrays.append(torch.tensor(values, dtype=torch.float64))
    coordinates64, literal32 = arrays
    positions = coordinates64.to(torch.float32)
    _require(torch.equal(positions.to(torch.float64).view(torch.int64), literal32.view(torch.int64)),
             "Saved FP32 literal/cast/signed-zero differs")
    _require(proof.get("generated_native_coordinates_float64_sha256") == geometry_tensor_sha256(coordinates64)
             and proof.get("quantization_max_abs_error") == float((coordinates64 - positions.to(torch.float64)).abs().max().item()),
             "Saved F64 hash/quantization error differs")
    geometry = GeneratedNativeGeometry(Data(x=torch.tensor(source.x, dtype=torch.long), pos=positions,
                                           batch=torch.zeros(n, dtype=torch.long), ptr=torch.tensor([0, n], dtype=torch.long)),
                                       torch.arange(n, dtype=torch.long), proof, coordinates64)
    _validate_geometry_tensors(geometry, source)
    return geometry, native_graph_binding
