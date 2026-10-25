"""Candidate mask-granularity extension, preserving original MFM3 codec bytes.

Validity is per component/leaf. Causes remain field sets plus sparse generic
leaf exceptions; no dense per-leaf causal claim is fabricated.
"""
from __future__ import annotations
import numpy as np
from wire_v1.codec import decode_record, encode_record
from wire_v1.mapping import TENSOR_POS, validate_labels
from wire_v1.store import FamilyReader, FamilyWriter, _key, _validate

MASK_PREFIXES = ("valid/", "reason/", "reason_fields_", "reason_leaf_")


def validate(metadata, arrays, schema):
    granularity = metadata.get("reason_granularity", {})
    if not granularity or schema["kind"] != "labels":
        _validate(metadata, arrays, schema)
        return
    if schema.get("mask_encoding") != "field-set+sparse-leaf-v1":
        raise ValueError("GRANULAR_MASK_SCHEMA_NOT_DECLARED")
    temporary = dict(arrays)
    for tid, entry in granularity.items():
        target = schema["compiled"]["physical_targets"][tid]
        if entry["mode"] != "field_set_and_sparse_generic_leaf_v1":
            raise ValueError("UNKNOWN_CAUSAL_GRANULARITY")
        members = target["members"]
        if set(entry["members"]) != {m["field_key"] for m in members}:
            raise ValueError("REASON_GRANULARITY_MEMBERS_DIFFER")
        whole_valid = arrays["valid/" + tid]
        # This temporary sentinel is solely a compatibility shape/validity
        # validation aid. It is NEVER encoded as a claimed leaf cause.
        temporary["reason/" + tid] = np.where(whole_valid, 0, 65535).astype("<u2")
        for index, member in enumerate(members):
            key = member["field_key"]
            member_valid = whole_valid
            if len(members) > 1:
                if target["kind"] == "symmetric_tensor" and target["storage"] == "matrix3x3":
                    i, j = TENSOR_POS[index]; member_valid = whole_valid[..., i, j]
                else:
                    member_valid = whole_valid[..., index]
            dimensions = entry["members"][key]["leaf_shape"]
            if list(member_valid.shape) != dimensions:
                raise ValueError("GRANULAR_LEAF_SHAPE_DIFFERS_FROM_COMPONENT")
            scopes = []
            for scope in ("source", "new", "review"):
                name = "reason_fields_" + scope + "/" + key
                codes = temporary.pop(name)
                if codes.dtype.str != "<u2" or codes.ndim != 1 or np.any(codes == 0) or len(np.unique(codes)) != len(codes):
                    raise ValueError("FIELD_REASON_SET_INVALID")
                if scope != "review":
                    scopes.extend(codes.tolist())
            indices = temporary.pop("reason_leaf_index/" + key)
            codes = temporary.pop("reason_leaf_code/" + key)
            if indices.dtype.str != "<i4" or codes.dtype.str != "<u2" or indices.ndim != 1 or codes.shape != indices.shape or np.any(codes == 0):
                raise ValueError("SPARSE_LEAF_REASON_DTYPE_OR_SHAPE")
            if np.any(indices < 0) or np.any(indices >= member_valid.size) or len(np.unique(indices)) != len(indices) or np.any(member_valid.reshape(-1)[indices] != 0):
                raise ValueError("SPARSE_LEAF_REASON_INDEX_OR_VALIDITY")
            if np.any(member_valid == 0) and not scopes and len(indices) != int(np.sum(member_valid == 0)):
                raise ValueError("INVALID_FIELD_WITHOUT_ANY_RECORDED_CAUSE")
    # Also performs identity, effective-role and geometry context checks.
    _validate(metadata, temporary, schema)


class GranularFamilyWriter(FamilyWriter):
    def write_batch(self, records):
        if self.finished or self.env is None:
            raise ValueError("WRITER_ALREADY_CLOSED")
        added = molecules = 0
        with self.env.begin(write=True) as tx:
            for metadata, arrays in records:
                meta, encoded = decode_record(encode_record(metadata, arrays))
                validate(meta, encoded, self.schema)
                record_key, molecule_key = _key(meta["export_record_id"]), _key(meta["molecule_id"])
                data = {k: v for k, v in encoded.items() if not k.startswith(MASK_PREFIXES)} if self.masks is not None else encoded
                masks = {k: v for k, v in encoded.items() if k.startswith(MASK_PREFIXES)}
                if self.masks is not None and not tx.put(record_key, encode_record(meta, masks), db=self.masks, overwrite=False):
                    raise ValueError("DUPLICATE_MASK_RECORD_ID")
                if not tx.put(record_key, encode_record(meta, data), db=self.records, overwrite=False):
                    raise ValueError("DUPLICATE_EXPORT_RECORD_ID")
                molecules += int(tx.get(molecule_key, db=self.molecules) is None)
                if not tx.put(molecule_key, record_key, db=self.molecules, dupdata=False):
                    raise ValueError("DUPLICATE_MOLECULE_RECORD_INDEX")
                added += 1
        self.count += added; self.molecule_count += molecules


class GranularFamilyReader(FamilyReader):
    def get(self, record_id):
        with self.env.begin() as tx:
            raw = tx.get(_key(record_id), db=self.records)
            mask = tx.get(_key(record_id), db=self.masks) if self.masks is not None else None
        if raw is None:
            raise KeyError(record_id)
        meta, arrays = decode_record(raw)
        if self.masks is not None:
            if mask is None:
                raise ValueError("MISSING_MASK_RECORD")
            mask_meta, mask_arrays = decode_record(mask)
            if meta != mask_meta or set(arrays) & set(mask_arrays):
                raise ValueError("MASK_PAYLOAD_IDENTITY_MISMATCH")
            arrays.update(mask_arrays)
        if meta["export_record_id"] != record_id:
            raise ValueError("INDEX_PAYLOAD_ID_MISMATCH")
        validate(meta, arrays, self.schema)
        return meta, arrays
