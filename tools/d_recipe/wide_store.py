"""Read-only, source-aligned D descriptor batches; no acceptance claim.

The producer performs numerical/alignment checks once. Opening this consumer
checks only IDs, roles, field metadata and array headers, without rereading the
numeric corpus. A batch retains raw values, explicit status and observed mask.
"""
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np


SCHEMA = "D_WIDE_DESCRIPTOR_STORE_V1"


@dataclass(frozen=True)
class DescriptorBatch:
    molecule_ids: tuple[str, ...]
    molecule_indices: tuple[int, ...]
    split: str
    roles: tuple[str, ...]
    fields: tuple[str, ...]
    raw_values: np.ndarray
    values: np.ndarray
    status: np.ndarray
    observed_valid: np.ndarray


def _absolute_path(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Store references must be absolute paths")
    return path


class WideDescriptorStore:
    """Open one library, then resolve exact (split, molecule_index) keys.

    `normalization_overrides` maps existing D20 field names to their original
    frozen 11-07 parameters. It is the caller's responsibility to provide that
    mapping; this consumer never estimates statistics or chooses parameters.
    """

    def __init__(self, manifest, library, *, normalization_overrides=None,
                 expected_fields=None, require_normalization=True):
        self.manifest_path = Path(manifest)
        metadata = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if metadata.get("schema") != SCHEMA:
            raise ValueError("Unsupported descriptor store schema")
        self.metadata = metadata["libraries"][library]
        self.library = library
        if self.metadata.get("fit_role") != "TRAIN":
            raise ValueError("Descriptor normalization must be fitted on TRAIN")
        if self.metadata.get("producer_alignment_checked") is not True:
            raise ValueError("Producer alignment check is not complete")
        # Expose, but never upgrade, the separate scientific reception status.
        self.reception_acceptance = self.metadata.get("reception_acceptance", "pending")
        self.ordered_fields = tuple(self.metadata["ordered_fields"])
        if len(self.ordered_fields) != len(set(self.ordered_fields)):
            raise ValueError("Duplicate descriptor field name")
        columns = self.metadata.get("enabled_columns", list(range(len(self.ordered_fields))))
        if (any(type(column) is not int or not 0 <= column < len(self.ordered_fields) for column in columns)
                or len(columns) != len(set(columns))):
            raise ValueError("Invalid enabled descriptor columns")
        self.columns = tuple(columns)
        self.fields = tuple(self.ordered_fields[column] for column in self.columns)
        if expected_fields is not None and tuple(expected_fields) != self.fields:
            raise ValueError("Descriptor field order differs from the frozen loader configuration")
        self._values = np.load(_absolute_path(self.metadata["values"]), mmap_mode="r", allow_pickle=False)
        self._status = np.load(_absolute_path(self.metadata["status"]), mmap_mode="r", allow_pickle=False)
        if (self._values.ndim != 2 or self._values.shape[1] != len(self.ordered_fields)
                or self._status.shape != self._values.shape
                or self._values.dtype.kind != "f" or self._values.dtype.itemsize != 8
                or self._status.dtype != np.dtype("uint8")):
            raise ValueError("Descriptor array shape/dtype differs from manifest")
        self.rows = []
        self._row_by_key = {}
        ids = set()
        with _absolute_path(self.metadata["rows"]).open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                for key in ("molecule_id", "molecule_index", "split", "role", "smiles"):
                    if key not in row:
                        raise ValueError("Missing descriptor row identity field: " + key)
                if (not isinstance(row["molecule_id"], str) or not row["molecule_id"]
                        or type(row["molecule_index"]) is not int or row["molecule_index"] < 0
                        or not isinstance(row["split"], str) or not isinstance(row["role"], str)
                        or not (isinstance(row["smiles"], str) or
                            (row["smiles"] is None and isinstance(row.get("source_error"), str)
                             and bool(row["source_error"])))):
                    raise ValueError("Invalid descriptor row identity")
                split, role = row["split"], row["role"]
                if ((split == "TRAIN" and role != "TRAIN")
                        or (split == "FULL" and role not in ("VAL", "VAL_DIAGNOSTIC"))
                        or split not in ("TRAIN", "FULL")):
                    raise ValueError("Descriptor split/role mismatch")
                key = (split, row["molecule_index"])
                if row["molecule_id"] in ids or key in self._row_by_key:
                    raise ValueError("Duplicate descriptor molecule ID or split/index key")
                ids.add(row["molecule_id"])
                self._row_by_key[key] = len(self.rows)
                self.rows.append(row)
        if len(self.rows) != self._values.shape[0]:
            raise ValueError("Descriptor row count differs from array header")
        self._normalization_overrides = dict(normalization_overrides or {})
        if set(self._normalization_overrides) - set(self.fields):
            raise ValueError("Normalization override references an inactive/unknown field")
        self._centers = self._scales = None
        if require_normalization or self.metadata.get("normalization") is not None:
            self._load_normalization()

    def _load_normalization(self):
        parameters = self.metadata.get("normalization")
        if parameters is None:
            raise ValueError("TRAIN normalization is not available; raw production is not training-ready")
        if len(parameters) != len(self.ordered_fields):
            raise ValueError("Normalization list must align with all raw fields")
        centers, scales = [], []
        for column, name in zip(self.columns, self.fields):
            spec = self._normalization_overrides.get(name, parameters[column])
            if spec is None or ("field_name" in spec and spec["field_name"] != name):
                raise ValueError("Missing or misaligned normalization for " + name)
            if "center" in spec and "scale" in spec:
                center, scale = float(spec["center"]), float(spec["scale"])
            elif "mean" in spec and "std_ddof0" in spec:
                center, scale = float(spec["mean"]), float(spec["std_ddof0"])
            else:
                raise ValueError("Missing frozen location/scale for " + name)
            if not np.isfinite(center) or not np.isfinite(scale) or scale <= 0:
                raise ValueError("Nonpositive or nonfinite normalization scale/center for " + name)
            centers.append(center)
            scales.append(scale)
        self._centers = np.asarray(centers, dtype=np.float64)
        self._scales = np.asarray(scales, dtype=np.float64)

    def get_batch(self, split, molecule_indices, *, expected_ids=None,
                  expected_role=None, standardized=True):
        indices = tuple(molecule_indices)
        positions = []
        for index in indices:
            try:
                positions.append(self._row_by_key[(split, index)])
            except KeyError:
                raise KeyError("Descriptor molecule missing: " + repr((split, index))) from None
        rows = [self.rows[position] for position in positions]
        ids = tuple(row["molecule_id"] for row in rows)
        roles = tuple(row["role"] for row in rows)
        if expected_ids is not None and tuple(expected_ids) != ids:
            raise ValueError("Requested source IDs do not align with descriptor rows")
        if expected_role is not None and any(role != expected_role for role in roles):
            raise ValueError("Requested source role does not align with descriptor rows")
        selection = np.ix_(np.asarray(positions, dtype=np.int64),
                           np.asarray(self.columns, dtype=np.int64))
        raw = np.asarray(self._values[selection])
        status = np.asarray(self._status[selection])
        # All three producer status codes stay available independently of data.
        valid = status == 1
        if standardized:
            if self._centers is None:
                self._load_normalization()
            values = np.full(raw.shape, np.nan, dtype=np.float64)
            np.subtract(raw, self._centers, out=values, where=valid)
            np.divide(values, self._scales, out=values, where=valid)
        else:
            values = raw
        return DescriptorBatch(ids, indices, split, roles, self.fields,
                               raw, values, status, valid)
