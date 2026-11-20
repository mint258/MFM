"""Read published downstream descriptors without fitting or imputing features.

This consumer has no pretraining split/index route. It joins an existing
target-free membership mapping to the export's unique molecule IDs, preserving
the original source split strings and the TRAIN-frozen active field list.
"""
from dataclasses import dataclass
import csv
import json
from pathlib import Path

import numpy as np


SCHEMA = "D_DOWNSTREAM_DESCRIPTOR_EXPORT_V1"
D3_ORDERED_FIELDS = ("PMI1", "PMI2", "PMI3", "PBF", "volume_A3", "SASA_total_A2")
# Exact original TRAIN registry keys; notably source PBF is stored as PBF_A.
D3_FEATURE_FIELDS = ("D3.PMI1", "D3.PMI2", "D3.PMI3", "D3.PBF_A", "D3.volume_A3", "D3.SASA_total_A2")


@dataclass(frozen=True)
class DownstreamFeatureBatch:
    member_uids: tuple[str | tuple[str, str] | None, ...]
    molecule_ids: tuple[str, ...]
    source_splits: tuple[str | None, ...]
    fields: tuple[str, ...]
    raw_values: np.ndarray
    values: np.ndarray
    status: np.ndarray
    observed_valid: np.ndarray

    @property
    def numeric_events(self):
        return self.status == 2

    @property
    def source_missing(self):
        return self.status == 0


def append_member_d3(batch, member_rows, *, standardized=False, normalization=None,
                     tuple_member_key="record_id"):
    """Append six already-produced molecular D3 values by exact source member.

    Tuple IDs use the explicitly declared original tuple_member_key: record_id
    for benchmark members, member_uid for the development source mapping.
    Strings join only row['member_uid']. No aliases or molecule-only selection,
    file reads, descriptor computation, fitting or atomic-SASA pooling occurs.
    Repeated members in the requested batch preserve their order and geometry.

    `standardized=True` applies only caller-supplied original TRAIN affine
    parameters, keyed by D3_FEATURE_FIELDS. The batch's existing 2D values and
    masks are preserved as supplied. Raw numerical values (including Inf) stay
    in raw_values; a JSON null remains unavailable as NaN with its source status
    unchanged, rather than guessing the original nonfinite value or filling 0.
    """
    if set(D3_FEATURE_FIELDS) & set(batch.fields):
        raise ValueError("Molecular D3 fields are already present; refusing duplicate append")
    if tuple_member_key not in ("record_id", "member_uid"):
        raise ValueError("Explicit original tuple member key must be record_id or member_uid")
    requested = set(batch.member_uids)
    if None in requested:
        raise ValueError("D3 geometry requires explicit original member IDs, not molecule-only rows")
    for key in requested:
        if not (isinstance(key, str) or (isinstance(key, tuple) and len(key) == 2
                                       and all(isinstance(part, str) for part in key))):
            raise ValueError("Original D3 member IDs must be full strings or (dataset, record_id) tuples")
    selected = {}
    for row in member_rows:
        keys = []
        if "member_uid" in row and row["member_uid"] in requested:
            keys.append(row["member_uid"])
        if "dataset" in row and tuple_member_key in row:
            pair = (row["dataset"], row[tuple_member_key])
            if pair in requested:
                keys.append(pair)
        if not keys:
            continue
        if tuple(row["D3_ordered_fields"]) != D3_ORDERED_FIELDS:
            raise ValueError("Existing member D3 field order differs from the fixed six molecular scalars")
        raw = tuple(np.nan if row["D3_raw"][field] is None else float(row["D3_raw"][field])
                    for field in D3_ORDERED_FIELDS)
        codes = tuple(row["D3_status"][field] for field in D3_ORDERED_FIELDS)
        if any(not isinstance(code, (int, np.integer)) or code not in (0, 1, 2) for code in codes):
            raise ValueError("D3 source status must preserve 0 missing / 1 valid / 2 numeric event")
        # Retain only the minimal identity and six scalars, never source label
        # dictionaries, structures, atom arrays or geometry files.
        identity = (row["molecule_id"], row["source_split"], raw, codes)
        for key in keys:
            if key in selected:
                previous = selected[key]
                if (previous[:2] != identity[:2] or previous[3] != codes
                        or not np.array_equal(np.asarray(previous[2]), np.asarray(raw), equal_nan=True)):
                    raise ValueError("Conflicting duplicate original D3 member binding")
                continue
            selected[key] = identity
    raw = np.empty((len(batch.member_uids), len(D3_ORDERED_FIELDS)), dtype=np.float64)
    status = np.empty(raw.shape, dtype=np.uint8)
    for position, key in enumerate(batch.member_uids):
        if key not in selected:
            raise KeyError("Existing molecular D3 member missing: " + repr(key))
        molecule, source_split, values, codes = selected[key]
        if molecule != batch.molecule_ids[position] or source_split != batch.source_splits[position]:
            raise ValueError("Original D3 member molecule/split does not match the requested descriptor batch")
        raw[position], status[position] = values, codes
    valid = status == 1
    values = raw
    if standardized:
        if normalization is None:
            raise ValueError("Explicit original six-field TRAIN normalizations are required for D3")
        centers, scales = [], []
        for name in D3_FEATURE_FIELDS:
            spec = normalization[name]
            if spec.get("fit_role") != "TRAIN" or spec.get("element_reference") is not None:
                raise ValueError("D3 standardization requires original TRAIN affine parameters, not A1 residual targets")
            center = np.asarray(spec["center"]).reshape(-1)
            scale = np.asarray(spec["scale"]).reshape(-1)
            if (len(center) != 1 or len(scale) != 1 or not np.isfinite(center[0])
                    or not np.isfinite(scale[0]) or scale[0] <= 0):
                raise ValueError("Invalid original TRAIN D3 affine parameters for " + name)
            centers.append(float(center[0]))
            scales.append(float(scale[0]))
        values = np.full(raw.shape, np.nan, dtype=np.float64)
        np.subtract(raw, np.asarray(centers), out=values, where=valid)
        np.divide(values, np.asarray(scales), out=values, where=valid)
    return DownstreamFeatureBatch(
        batch.member_uids, batch.molecule_ids, batch.source_splits, batch.fields + D3_FEATURE_FIELDS,
        np.concatenate((batch.raw_values, raw), axis=1), np.concatenate((batch.values, values), axis=1),
        np.concatenate((batch.status, status), axis=1), np.concatenate((batch.observed_valid, valid), axis=1))


def _absolute(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Downstream export references must be absolute paths")
    return path


def _members(reference):
    """Read only identity/split columns, retaining no structures or label dicts."""
    path = _absolute(reference["path"])
    columns = [reference["member_key"], reference["molecule_key"]]
    split_key = reference.get("source_split_key")
    if split_key:
        columns.append(split_key)
    dataset_key = reference.get("dataset_key")
    if dataset_key:
        columns.append(dataset_key)
    kind = reference["format"].lower()
    if kind == "jsonl":
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                yield {key: row[key] for key in columns}
    elif kind == "csv":
        # Source values are not parsed as labels or used for selection. Only
        # the named identity/split columns leave this one-row reader.
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                yield {key: row[key] for key in columns}
    elif kind == "parquet":
        import pyarrow.parquet as parquet
        for batch in parquet.ParquetFile(path).iter_batches(columns=columns):
            yield from batch.to_pylist()
    else:
        raise ValueError("Unsupported published downstream membership format: " + kind)


class DownstreamDescriptorStore:
    """Raw F64 features and source masks for B/C; no model-input policy.

    A membership reference with `dataset_key` uses original `(dataset,
    record_id)` tuples; otherwise it uses the original member_uid string.
    `standardized=True` is an explicit request to apply the published original
    TRAIN affine parameters. It does not fit on downstream data, clip targets,
    impute missing values, or apply A1 residual transforms.
    """

    def __init__(self, manifest, library, *, expected_fields=None):
        document = json.loads(Path(manifest).read_text(encoding="utf-8"))
        if document.get("schema") != SCHEMA:
            raise ValueError("Unsupported downstream descriptor export schema")
        self.library = library
        self.metadata = document["libraries"][library]
        if self.metadata.get("state") == "UNRESOLVED" or self.metadata.get("status") == "UNRESOLVED":
            raise ValueError("Requested downstream descriptor library is UNRESOLVED")
        if self.metadata.get("fit_role") != "TRAIN":
            raise ValueError("Downstream descriptor parameters/field filtering must be TRAIN-frozen")
        self.reception_acceptance = document.get("reception_acceptance", "pending")
        self.current_C1_complete = document.get("current_C1_complete", False)
        self.ordered_fields = tuple(self.metadata["ordered_fields"])
        columns = self.metadata["enabled_columns"]
        if (len(self.ordered_fields) != len(set(self.ordered_fields))
                or len(columns) != len(set(columns))
                or any(type(column) is not int or not 0 <= column < len(self.ordered_fields) for column in columns)):
            raise ValueError("Invalid frozen downstream descriptor field order")
        self.columns = tuple(columns)
        self.fields = tuple(self.ordered_fields[column] for column in self.columns)
        if expected_fields is not None and tuple(expected_fields) != self.fields:
            raise ValueError("Active fields differ from the adopted TRAIN-frozen field order")
        self._values = np.load(_absolute(self.metadata["values"]), mmap_mode="r", allow_pickle=False)
        self._status = np.load(_absolute(self.metadata["status"]), mmap_mode="r", allow_pickle=False)
        if (self._values.ndim != 2 or self._values.shape[1] != len(self.ordered_fields)
                or self._values.dtype.kind != "f" or self._values.dtype.itemsize != 8
                or self._status.dtype != np.dtype("uint8") or self._status.shape != self._values.shape):
            raise ValueError("Downstream descriptor array headers differ from published fields")
        self._row_by_id = {}
        ids_path = document.get("molecules", document.get("rows"))
        with _absolute(ids_path).open(encoding="utf-8") as stream:
            for ordinal, line in enumerate(stream):
                row = json.loads(line)
                identifier, position = row["molecule_id"], row["feature_row"]
                if not isinstance(identifier, str) or not identifier or type(position) is not int or position != ordinal:
                    raise ValueError("Unique molecule ID/feature-row metadata is misaligned")
                if identifier in self._row_by_id:
                    raise ValueError("Duplicate downstream molecule ID")
                self._row_by_id[identifier] = position
        if len(self._row_by_id) != self._values.shape[0]:
            raise ValueError("Downstream unique molecule count differs from array header")
        self._member_by_uid = {}
        reference = document["membership_reference"]
        self.membership_reference = dict(reference)
        self.dataset_key = reference.get("dataset_key")
        for row in _members(reference):
            uid, molecule = row[reference["member_key"]], row[reference["molecule_key"]]
            split = row[reference["source_split_key"]] if reference.get("source_split_key") else None
            if not isinstance(uid, str) or not isinstance(molecule, str):
                raise ValueError("Original downstream member/molecule IDs must remain strings")
            if self.dataset_key:
                dataset = row[self.dataset_key]
                if not isinstance(dataset, str):
                    raise ValueError("Original downstream dataset identifiers must remain strings")
                # Keep the two original identity components as a tuple. A
                # benchmark record_id is not assumed globally unique.
                uid = (dataset, uid)
            identity = (molecule, split)
            if uid in self._member_by_uid and self._member_by_uid[uid] != identity:
                raise ValueError("Ambiguous original downstream membership ID")
            self._member_by_uid[uid] = identity
        self._affines = None

    def _frozen_affines(self):
        if self._affines is not None:
            return self._affines
        parameters = self.metadata.get("normalization")
        if parameters is None or len(parameters) != len(self.ordered_fields):
            raise ValueError("Published TRAIN normalization does not align with raw fields")
        centers, scales = [], []
        for column, name in zip(self.columns, self.fields):
            spec = parameters[column]
            if spec is None or ("field_name" in spec and spec["field_name"] != name):
                raise ValueError("Missing/misaligned frozen TRAIN parameters for " + name)
            if spec.get("element_reference") is not None:
                raise ValueError("Direct descriptor standardization requires original affine parameters, not A1 residual targets")
            center = np.asarray(spec["center"] if "center" in spec else spec["mean"]).reshape(-1)
            scale = np.asarray(spec["scale"] if "scale" in spec else
                               spec.get("std_ddof0", spec.get("std_population"))).reshape(-1)
            if (len(center) != 1 or len(scale) != 1 or not np.isfinite(center[0])
                    or not np.isfinite(scale[0]) or scale[0] <= 0):
                raise ValueError("Invalid/zero frozen TRAIN affine scale for " + name)
            centers.append(float(center[0]))
            scales.append(float(scale[0]))
        self._affines = np.array(centers, dtype=np.float64), np.array(scales, dtype=np.float64)
        return self._affines

    def _batch(self, identifiers, member_uids, source_splits, standardized):
        rows = []
        for identifier in identifiers:
            if identifier not in self._row_by_id:
                raise KeyError("Downstream exported molecule missing: " + identifier)
            rows.append(self._row_by_id[identifier])
        selection = np.ix_(np.asarray(rows, dtype=np.int64), np.asarray(self.columns, dtype=np.int64))
        raw, status = np.asarray(self._values[selection]), np.asarray(self._status[selection])
        valid = status == 1
        values = raw
        if standardized:
            centers, scales = self._frozen_affines()
            values = np.full(raw.shape, np.nan, dtype=np.float64)
            np.subtract(raw, centers, out=values, where=valid)
            np.divide(values, scales, out=values, where=valid)
        return DownstreamFeatureBatch(tuple(member_uids), tuple(identifiers), tuple(source_splits),
                                      self.fields, raw, values, status, valid)

    def get_members(self, member_uids, *, standardized=False):
        members = tuple(member_uids)
        identities = []
        for uid in members:
            if self.dataset_key:
                if not isinstance(uid, tuple) or len(uid) != 2 or not all(isinstance(item, str) for item in uid):
                    raise ValueError("This original membership mapping requires (dataset, " +
                                     self.membership_reference["member_key"] + ") tuples")
            elif not isinstance(uid, str):
                raise ValueError("This original membership mapping requires member_uid strings")
            if uid not in self._member_by_uid:
                raise KeyError("Original downstream membership ID missing: " + repr(uid))
            identities.append(self._member_by_uid[uid])
        return self._batch([item[0] for item in identities], members,
                           [item[1] for item in identities], standardized)

    def get_molecules(self, molecule_ids, *, standardized=False):
        identifiers = tuple(molecule_ids)
        # A molecule request has no member-level split; never invent TRAIN or
        # infer a downstream partition from the normalization's fit role.
        return self._batch(identifiers, (None,) * len(identifiers),
                           (None,) * len(identifiers), standardized)
