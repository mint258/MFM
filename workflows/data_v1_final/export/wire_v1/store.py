"""New external family LMDB stores and duplicate-sorted molecular indices."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .codec import canonical_json, decode_record, encode_record
from .mapping import validate_geometry, validate_labels


def file_ref(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": h.hexdigest()}


def _key(value):
    if not isinstance(value, str) or not value or value.startswith("__"):
        raise ValueError("INVALID_SAMPLE_OR_MOLECULE_ID")
    raw = value.encode("utf-8")
    if len(raw) > 255 or b"\0" in raw:
        raise ValueError("ID_LENGTH_OR_NUL")
    return raw


def _validate(metadata, arrays, schema):
    for key in ("molecule_id", "export_record_id"):
        _key(metadata[key])
    if metadata["geometry_source"] not in {"pm7", "uff_sprime"}:
        raise ValueError("INVALID_GEOMETRY_SOURCE")
    if metadata["effective_role"] not in {"TRAIN", "VAL", "FULL", "embargo"}:
        raise ValueError("INVALID_EFFECTIVE_ROLE")
    if not isinstance(metadata.get("source_role"), str):
        raise ValueError("SOURCE_ROLE_REQUIRED")
    if schema["kind"] == "geometry":
        validate_geometry(metadata, arrays)
    elif schema["kind"] == "labels":
        targets = schema["compiled"]["physical_targets"]
        if any(t["family"] != schema["family"] for t in targets.values()):
            raise ValueError("FAMILY_TARGET_PARTITION_MISMATCH")
        validate_labels(metadata, arrays, schema["compiled"])
    else:
        raise ValueError("UNSUPPORTED_STORE_KIND")


class FamilyWriter:
    def __init__(self, path, schema, *, map_bytes):
        import lmdb
        self.path, self.schema = Path(path), schema
        if self.path.exists() or not self.path.is_absolute():
            raise ValueError("REQUIRES_NEW_ABSOLUTE_EXTERNAL_STORE")
        if map_bytes < 1024 * 1024 or map_bytes > 1024 ** 4:
            raise ValueError("EXPLICIT_BOUNDED_LMDB_MAP_REQUIRED")
        self.path.mkdir(parents=True, exist_ok=False)
        self.env = lmdb.open(str(self.path), map_size=map_bytes, max_dbs=4, subdir=True,
                             create=True, lock=True, sync=True, metasync=True)
        self.records = self.env.open_db(b"records")
        self.molecules = self.env.open_db(b"molecule_index", dupsort=True)
        self.masks = self.env.open_db(b"masks") if schema["kind"] == "labels" else None
        self.count = self.molecule_count = 0
        self.finished = False
        with self.env.begin(write=True) as tx:
            tx.put(b"__schema__", canonical_json(schema))
            tx.put(b"__state__", b"WRITING")

    def write_batch(self, records):
        if self.finished or self.env is None:
            raise ValueError("WRITER_ALREADY_CLOSED")
        added = molecules = 0
        with self.env.begin(write=True) as tx:
            for metadata, arrays in records:
                raw = encode_record(metadata, arrays)
                decoded_metadata, decoded_arrays = decode_record(raw)
                _validate(decoded_metadata, decoded_arrays, self.schema)
                record_key, molecule_key = _key(metadata["export_record_id"]), _key(metadata["molecule_id"])
                if self.masks is not None:
                    data_arrays = {k: v for k, v in decoded_arrays.items() if not k.startswith(("valid/", "reason/"))}
                    mask_arrays = {k: v for k, v in decoded_arrays.items() if k.startswith(("valid/", "reason/"))}
                    raw = encode_record(decoded_metadata, data_arrays)
                    if not tx.put(record_key, encode_record(decoded_metadata, mask_arrays), db=self.masks, overwrite=False):
                        raise ValueError("DUPLICATE_MASK_RECORD_ID")
                if not tx.put(record_key, raw, db=self.records, overwrite=False):
                    raise ValueError("DUPLICATE_EXPORT_RECORD_ID")
                if tx.get(molecule_key, db=self.molecules) is None:
                    molecules += 1
                if not tx.put(molecule_key, record_key, db=self.molecules, dupdata=False):
                    raise ValueError("DUPLICATE_MOLECULE_RECORD_INDEX")
                added += 1
        self.count += added
        self.molecule_count += molecules

    def finish(self):
        if self.finished or self.env is None:
            raise ValueError("WRITER_ALREADY_CLOSED")
        with self.env.begin(write=True) as tx:
            assert tx.stat(db=self.records)["entries"] == self.count
            tx.put(b"__len__", str(self.count).encode("ascii"))
            tx.put(b"__molecules__", str(self.molecule_count).encode("ascii"))
            tx.put(b"__state__", b"COMPLETE")
        self.env.sync(True)
        self.env.close()
        self.env = None
        self.finished = True
        manifest = {"status": "CANDIDATE_STORE_COMPLETE_NOT_CONTRACT_V3_0",
                    "schema_sha256": hashlib.sha256(canonical_json(self.schema)).hexdigest(),
                    "kind": self.schema["kind"], "family": self.schema.get("family"),
                    "records": self.count, "molecules": self.molecule_count,
                    "data": file_ref(self.path / "data.mdb"),
                    "runtime_lock_policy": "lock.mdb is runtime metadata, excluded from content identity",
                    "mask_storage": "separate named masks DB in the same atomic transaction" if self.masks is not None else None,
                    "pickle_used": False}
        (self.path / "manifest.json").write_bytes(canonical_json(manifest) + b"\n")
        return manifest

    def close(self):
        if self.env is not None:
            self.env.close()
            self.env = None

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self.finish()
        else:
            self.close()


class FamilyReader:
    def __init__(self, path, *, expected_schema_sha256=None):
        import lmdb
        self.path = Path(path)
        self.env = lmdb.open(str(self.path), readonly=True, create=False, lock=False,
                             readahead=False, max_dbs=4, subdir=True)
        try:
            with self.env.begin() as tx:
                if tx.get(b"__state__") != b"COMPLETE":
                    raise ValueError("INCOMPLETE_STORE")
                raw_schema = tx.get(b"__schema__")
                self.schema = json.loads(raw_schema)
                digest = hashlib.sha256(raw_schema).hexdigest()
                if canonical_json(self.schema) != raw_schema:
                    raise ValueError("NONCANONICAL_STORE_SCHEMA")
                if expected_schema_sha256 is not None and digest != expected_schema_sha256:
                    raise ValueError("STORE_SCHEMA_PIN_MISMATCH")
                self.count = int(tx.get(b"__len__"))
                self.molecule_count = int(tx.get(b"__molecules__"))
            self.records = self.env.open_db(b"records", create=False)
            self.molecules = self.env.open_db(b"molecule_index", create=False, dupsort=True)
            self.masks = self.env.open_db(b"masks", create=False) if self.schema["kind"] == "labels" else None
            with self.env.begin() as tx:
                if self.masks is not None and tx.stat(db=self.masks)["entries"] != self.count:
                    raise ValueError("MASK_RECORD_COUNT_MISMATCH")
                if tx.stat(db=self.records)["entries"] != self.count:
                    raise ValueError("STORE_RECORD_COUNT_MISMATCH")
        except Exception:
            self.env.close()
            raise

    def get(self, record_id):
        with self.env.begin() as tx:
            raw = tx.get(_key(record_id), db=self.records)
            mask_raw = tx.get(_key(record_id), db=self.masks) if self.masks is not None else None
        if raw is None:
            raise KeyError(record_id)
        metadata, arrays = decode_record(raw)
        if self.masks is not None:
            if mask_raw is None:
                raise ValueError("MISSING_MASK_RECORD")
            mask_metadata, mask_arrays = decode_record(mask_raw)
            if mask_metadata != metadata or set(arrays) & set(mask_arrays):
                raise ValueError("MASK_PAYLOAD_IDENTITY_MISMATCH")
            arrays.update(mask_arrays)
        if metadata["export_record_id"] != record_id:
            raise ValueError("INDEX_PAYLOAD_ID_MISMATCH")
        _validate(metadata, arrays, self.schema)
        return metadata, arrays

    def records_for_molecule(self, molecule_id):
        with self.env.begin() as tx, tx.cursor(db=self.molecules) as cursor:
            if not cursor.set_key(_key(molecule_id)):
                return []
            return [value.decode("utf-8") for value in cursor.iternext_dup(keys=False, values=True)]

    def close(self):
        if self.env is not None:
            self.env.close()
            self.env = None

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.close()


def write_export_manifest(path, stores, *, source_references, registry_reference,
                          roles_reference, common_reference, order_reference):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    checked = []
    for store in stores:
        manifest_path = Path(store) / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        actual = file_ref(Path(store) / "data.mdb")
        if actual != manifest["data"]:
            raise ValueError("FAMILY_DATA_PIN_MISMATCH")
        checked.append({"manifest": file_ref(manifest_path), "data": actual,
                        "records": manifest["records"], "molecules": manifest["molecules"]})
    result = {"status": "CANDIDATE_EXPORT_NOT_D3_OR_FULL_RELEASE", "stores": checked,
              "source_references": source_references, "registry": registry_reference,
              "roles": roles_reference, "common_population": common_reference,
              "conformer_orders": order_reference, "contract_finalized": False}
    path.write_bytes(canonical_json(result) + b"\n")
    return result
