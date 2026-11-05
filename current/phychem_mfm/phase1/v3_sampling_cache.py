"""Streaming, metadata-only local cache of an existing SamplingIndex identity.

Cache completion is separate from data-line release status. Source identity is
preserved for sampler checkpoints; cache bytes have their own pinned manifest.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from multiprocessing.util import Finalize
import os
from pathlib import Path
import socket
import sqlite3

from .v3_sampling import ConformationSelection, ConformerRef, MoleculeEntry, UniformMoleculeSampler
from .v3_sampling_bridge import NativeConformerIdentity

FORMAT = "MODEL_SAMPLING_METADATA_SQLITE_V1"
DB_NAME = "metadata.sqlite"
MANIFEST_NAME = "COMPLETE.json"
APPLICATION_ID = 0x4D464D53
DDL = (
    "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
    "CREATE TABLE molecules(ordinal INTEGER PRIMARY KEY CHECK(ordinal>=0),molecule_id TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,payload_sha256 TEXT NOT NULL)",
    "CREATE TABLE native_identity(geometry_id TEXT PRIMARY KEY,molecule_id TEXT NOT NULL,ordinal INTEGER NOT NULL REFERENCES molecules(ordinal),payload TEXT NOT NULL,payload_sha256 TEXT NOT NULL)",
)
MOLECULE_KEYS = {"molecule_id", "conformers", "group_mask", "family_mask", "mixed_geometry_source", "minimum_energy_conformer_id"}
CONFORMER_KEYS = {"conformer_id", "fixed_order", "native_atoms", "geometry_locators", "diversity_order"}
NATIVE_KEYS = {"geometry_id", "molecule_id", "geometry_source", "native_record_id", "sprime_conf_idx"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _sha(value):
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), "Explicit lowercase SHA256 pin required")
    return value


def _file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stat(path):
    path = Path(path)
    _require(path.is_file() and not path.is_symlink(), "Cache files must be regular owned cache artifacts")
    info = path.stat()
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def _source_summary(source):
    count = len(source)
    _require(type(count) is int and count >= 0, "Source length differs")
    _require(source.role in ("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION")
             and source.authority in ("synthetic_fixture", "data_line")
             and type(source.version) is str and bool(source.version), "Explicit source role/authority/version required")
    extensions = {}
    for name in ("status", "contract_finalized", "real_data_export_accepted"):
        if hasattr(source, name):
            value = getattr(source, name)
            _require(value is None or type(value) in (str, bool), "Source status flag must be a literal scalar")
            extensions[name] = value
    hints = {}
    if hasattr(source, "geometry_source"):
        value = source.geometry_source
        _require(value in ("PM7", "Sprime_UFF", "mixed"), "Source sampler geometry hint differs")
        hints["geometry_source"] = value
    if hasattr(source, "selection"):
        _require(isinstance(source.selection, ConformationSelection), "Source selection hint must be typed")
        hints["selection"] = asdict(source.selection)
    return {"content_sha256": _sha(source.content_sha256), "version": source.version, "role": source.role,
        "authority": source.authority, "molecules": count, "extensions": extensions, "sampler_hints": hints,
        "source_class": type(source).__module__ + "." + type(source).__qualname__,
        "native_identity_available": callable(getattr(source, "native_identity_for", None))}


def _entry_dict(entry):
    _require(type(entry) is MoleculeEntry and all(type(ref) is ConformerRef for ref in entry.conformers),
             "Only typed model metadata entries may enter this cache")
    # Explicit whitelist; never serialize arbitrary source attributes, labels,
    # coordinates or an enclosing dataclass/Python manifest.
    return {"molecule_id": entry.molecule_id, "conformers": [{key: getattr(ref, key) for key in CONFORMER_KEYS} for ref in entry.conformers],
        "group_mask": entry.group_mask, "family_mask": entry.family_mask, "mixed_geometry_source": entry.mixed_geometry_source,
        "minimum_energy_conformer_id": entry.minimum_energy_conformer_id}


def _decode_entry(raw, ordinal, molecule_id):
    value = json.loads(raw)
    _require(_canonical(value) == raw and set(value) == {"ordinal", "molecule"}
             and type(value["ordinal"]) is int and value["ordinal"] == ordinal, "Noncanonical or inconsistent cached ordinal")
    data = value["molecule"]
    _require(isinstance(data, dict) and set(data) == MOLECULE_KEYS and data["molecule_id"] == molecule_id,
             "Cached molecule identity/schema differs")
    _require(isinstance(data["conformers"], list) and all(isinstance(ref, dict) and set(ref) == CONFORMER_KEYS for ref in data["conformers"]),
             "Cached conformer metadata schema differs")
    entry = MoleculeEntry(**{**data, "conformers": tuple(ConformerRef(**ref) for ref in data["conformers"])})
    _require(_canonical(_entry_dict(entry)) == _canonical(data), "Cache must preserve original metadata ordering")
    return entry


def _native(value, *, geometry_id=None, molecule_id=None):
    fields = value if isinstance(value, dict) else value.as_dict()
    _require(isinstance(fields, dict) and set(fields) == NATIVE_KEYS, "Native audit must retain exactly its five original fields")
    result = NativeConformerIdentity(**fields)
    _require((geometry_id is None or result.geometry_id == geometry_id)
             and (molecule_id is None or result.molecule_id == molecule_id), "Native sidecar geometry/molecule differs")
    return result


def _stream_update(digest, raw):
    digest.update(len(raw).to_bytes(8, "little"))
    digest.update(raw)


def _connection(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _header(connection, expected=None, *, verify_counts=True):
    _require(connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
             and connection.execute("PRAGMA user_version").fetchone()[0] == 1, "Wrong cache SQLite schema/version")
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    _require(tables == {"metadata", "molecules", "native_identity"}, "Wrong cache table schema")
    row = connection.execute("SELECT value FROM metadata WHERE key='header'").fetchone()
    _require(row is not None, "Missing cache header")
    header = json.loads(row[0])
    _require(_canonical(header) == row[0] and header.get("format") == FORMAT
             and header.get("cache_state") == "COMPLETE", "Partial/WRITING cache is not readable")
    _require(expected is None or header == expected, "Cache header/manifest binding differs")
    source = header["source"]
    _sha(source["content_sha256"])
    _require(source["authority"] in ("synthetic_fixture", "data_line")
             and source["role"] in ("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION")
             and type(source["version"]) is str and bool(source["version"])
             and type(source["molecules"]) is int and source["molecules"] >= 0
             and type(header["native_identities"]) is int and header["native_identities"] >= 0
             and type(header["conformers"]) is int and header["conformers"] >= 0
             and type(source["native_identity_available"]) is bool
             and header["native_identity_scope"] == ("sampleable_conformers_only" if source["native_identity_available"] else "unavailable_on_source")
             and header["native_identities"] == (header["conformers"] if source["native_identity_available"] else 0)
             and header["schema_sha256"] == _digest(_canonical(DDL).encode("utf-8")), "Cache source/schema metadata differs")
    if not verify_counts:
        return header
    count, low, high = connection.execute("SELECT count(*),min(ordinal),max(ordinal) FROM molecules").fetchone()
    _require(count == header["source"]["molecules"]
             and (count == 0 or (low == 0 and high == count - 1)), "Cache molecule count/ordinal bounds differ")
    _require(connection.execute("SELECT count(*) FROM native_identity").fetchone()[0] == header["native_identities"],
             "Cache native sidecar count differs")
    return header


def write_sampling_cache(source, directory, *, expected_source_content_sha256, batch_rows=512, max_entry_bytes=16 * 1024 ** 2):
    """Stream one molecule at a time; never overwrite an existing cache.

    A failed new directory remains as partial evidence. No source physical
    files are opened for writing, and no scientific values enter the cache.
    """
    expected = _sha(expected_source_content_sha256)
    _require(type(batch_rows) is int and batch_rows > 0 and type(max_entry_bytes) is int and max_entry_bytes > 0,
             "Positive bounded transaction/entry limits required")
    before = _source_summary(source)
    _require(before["content_sha256"] == expected, "Source content pin differs before caching")
    _require(len(_canonical(before).encode("utf-8")) <= max_entry_bytes, "Source identity summary exceeds cache entry boundary")
    directory = Path(directory).expanduser().absolute()
    directory.mkdir(parents=True, exist_ok=False)
    database = directory / DB_NAME
    connection = sqlite3.connect(database)
    metadata_digest, native_digest = hashlib.sha256(), hashlib.sha256()
    native_count = conformer_count = 0
    header = {"format": FORMAT, "cache_state": "WRITING", "source": before,
              "native_identity_scope": "sampleable_conformers_only" if before["native_identity_available"] else "unavailable_on_source"}
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA cache_size=-8192")
        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        connection.execute("PRAGMA user_version=1")
        for statement in DDL:
            connection.execute(statement)
        connection.execute("INSERT INTO metadata VALUES('header',?)", (_canonical(header),))
        connection.commit()
        for ordinal in range(before["molecules"]):
            entry = source.molecule_at(ordinal)
            raw = _canonical({"ordinal": ordinal, "molecule": _entry_dict(entry)})
            encoded = raw.encode("utf-8")
            _require(len(encoded) <= max_entry_bytes, "Per-molecule metadata exceeds explicit cache entry boundary")
            _decode_entry(raw, ordinal, entry.molecule_id)
            conformer_count += len(entry.conformers)
            connection.execute("INSERT INTO molecules VALUES(?,?,?,?)", (ordinal, entry.molecule_id, raw, _digest(encoded)))
            _stream_update(metadata_digest, encoded)
            if before["native_identity_available"]:
                for ref in entry.conformers:
                    identity = _native(source.native_identity_for(ref.conformer_id), geometry_id=ref.conformer_id, molecule_id=entry.molecule_id)
                    _require(identity.model_geometry_source in dict(ref.geometry_locators), "Native source is absent from its conformer locators")
                    native_raw = _canonical(identity.as_dict())
                    _require(len(native_raw.encode("utf-8")) <= max_entry_bytes, "Native sidecar exceeds explicit cache entry boundary")
                    connection.execute("INSERT INTO native_identity VALUES(?,?,?,?,?)", (identity.geometry_id, identity.molecule_id,
                        ordinal, native_raw, _digest(native_raw.encode("utf-8"))))
                    _stream_update(native_digest, native_raw.encode("utf-8"))
                    native_count += 1
            if (ordinal + 1) % batch_rows == 0:
                connection.commit()
        _require(_source_summary(source) == before, "Source identity/length/authority changed during caching")
        header.update(cache_state="COMPLETE", metadata_stream_sha256=metadata_digest.hexdigest(),
            native_stream_sha256=native_digest.hexdigest(), native_identities=native_count,
            conformers=conformer_count,
            cache_implementation_sha256=_file_sha(__file__), schema_sha256=_digest(_canonical(DDL).encode("utf-8")),
            writer_limits={"batch_rows": batch_rows, "max_entry_bytes": max_entry_bytes})
        connection.execute("UPDATE metadata SET value=? WHERE key='header'", (_canonical(header),))
        connection.commit()
        _require(connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "Cache SQLite integrity check failed")
        _header(connection, header)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    manifest = {"format": FORMAT, "cache_state": "COMPLETE", "database_name": DB_NAME,
                "database_bytes": database.stat().st_size, "database_sha256": _file_sha(database), "header": header}
    temporary = directory / "COMPLETE.pending"
    with temporary.open("xb") as stream:
        stream.write((_canonical(manifest) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, directory / MANIFEST_NAME)
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return {"directory": str(directory), "manifest_sha256": _file_sha(directory / MANIFEST_NAME),
            "database_sha256": manifest["database_sha256"], "source_content_sha256": expected,
            "molecules": before["molecules"], "native_identities": native_count}


class SamplingCacheIndex:
    """Read-only random metadata lookup; pickle contains no rows/connections."""
    def __init__(self, directory, manifest, receipt, expected_manifest_sha256, expected_source_content_sha256):
        self._directory = str(Path(directory).absolute())
        self._manifest = manifest
        self._receipt = receipt
        self._manifest_sha256 = expected_manifest_sha256
        self._source_sha256 = expected_source_content_sha256
        self._connection = self._pid = self._finalizer = None

    def __len__(self):
        return self._manifest["header"]["source"]["molecules"]

    @property
    def content_sha256(self):
        return self._source_sha256

    @property
    def version(self):
        return self._manifest["header"]["source"]["version"]

    @property
    def authority(self):
        return self._manifest["header"]["source"]["authority"]

    @property
    def role(self):
        return self._manifest["header"]["source"]["role"]

    @property
    def cache_manifest(self):
        return json.loads(_canonical(self._manifest))

    def __getattr__(self, name):
        manifest = self.__dict__.get("_manifest", {})
        source = manifest.get("header", {}).get("source", {})
        if name in source.get("extensions", {}):
            return source["extensions"][name]
        hints = source.get("sampler_hints", {})
        if name in hints:
            return ConformationSelection(**hints[name]) if name == "selection" else hints[name]
        raise AttributeError(name)

    def __getstate__(self):
        return {key: value for key, value in self.__dict__.items() if key not in ("_connection", "_pid", "_finalizer")}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._connection = self._pid = self._finalizer = None

    def _connect(self):
        if self._connection is not None and self._pid == os.getpid():
            return self._connection
        self.close()
        directory = Path(self._directory)
        _require(self._receipt["host"] == socket.gethostname(), "Different-node cache requires an independently verified open")
        _require(_stat(directory / DB_NAME) == self._receipt["database_stat"]
                 and _stat(directory / MANIFEST_NAME) == self._receipt["manifest_stat"]
                 and _file_sha(directory / MANIFEST_NAME) == self._manifest_sha256,
                 "Same-node verified cache receipt is stale")
        connection = _connection(directory / DB_NAME)
        try:
            _header(connection, self._manifest["header"], verify_counts=False)
        except Exception:
            connection.close()
            raise
        self._connection, self._pid = connection, os.getpid()
        self._finalizer = Finalize(self, connection.close, exitpriority=10)
        return connection

    def molecule_at(self, index):
        if type(index) is not int or not 0 <= index < len(self):
            raise IndexError(index)
        row = self._connect().execute("SELECT molecule_id,payload,payload_sha256 FROM molecules WHERE ordinal=?", (index,)).fetchone()
        _require(row is not None and _digest(row[1].encode("utf-8")) == row[2], "Cached molecule row checksum differs")
        return _decode_entry(row[1], index, row[0])

    def make_sampler(self, *, seed, sample_budget, selection=None, geometry_source=None):
        hints = self._manifest["header"]["source"]["sampler_hints"]
        if "selection" in hints:
            stored = ConformationSelection(**hints["selection"])
            _require(selection is None or selection == stored, "Source-bound sampler selection differs")
            selection = stored
        if "geometry_source" in hints:
            _require(geometry_source is None or geometry_source == hints["geometry_source"], "Source-bound sampler geometry differs")
            geometry_source = hints["geometry_source"]
        _require(isinstance(selection, ConformationSelection) and geometry_source in ("PM7", "Sprime_UFF", "mixed"),
                 "Without source hints caller must explicitly supply selection and geometry; cache chooses no D5 policy")
        return UniformMoleculeSampler(self, seed=seed, sample_budget=sample_budget, selection=selection, geometry_source=geometry_source)

    def close(self):
        if self._connection is not None and self._pid != os.getpid():
            self._connection.close()
            if self._finalizer is not None:
                self._finalizer.cancel()
        elif self._finalizer is not None:
            self._finalizer()
        elif self._connection is not None:
            self._connection.close()
        self._connection = self._pid = self._finalizer = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class NativeSamplingCacheIndex(SamplingCacheIndex):
    def native_identity_for(self, geometry_id):
        row = self._connect().execute("SELECT molecule_id,payload,payload_sha256 FROM native_identity WHERE geometry_id=?", (geometry_id,)).fetchone()
        if row is None:
            raise KeyError(geometry_id)
        _require(_digest(row[1].encode("utf-8")) == row[2], "Cached native identity checksum differs")
        value = json.loads(row[1])
        _require(_canonical(value) == row[1], "Noncanonical native sidecar")
        return _native(value, geometry_id=geometry_id, molecule_id=row[0])


def open_sampling_cache(directory, *, expected_manifest_sha256, expected_source_content_sha256):
    """Independent open verifies full bytes once; spawn uses its node receipt."""
    _sha(expected_manifest_sha256)
    _sha(expected_source_content_sha256)
    directory = Path(directory).expanduser().absolute()
    manifest_path, database = directory / MANIFEST_NAME, directory / DB_NAME
    _require(manifest_path.exists(), "Partial/WRITING cache has no final COMPLETE manifest")
    before_manifest, before_database = _stat(manifest_path), _stat(database)
    raw = manifest_path.read_bytes()
    _require(_digest(raw) == expected_manifest_sha256, "Cache manifest SHA pin differs")
    manifest = json.loads(raw)
    _require((_canonical(manifest) + "\n").encode("utf-8") == raw and set(manifest) == {
        "format", "cache_state", "database_name", "database_bytes", "database_sha256", "header"}
        and manifest["format"] == FORMAT and manifest["cache_state"] == "COMPLETE"
        and manifest["database_name"] == DB_NAME, "Wrong or incomplete cache manifest/schema")
    _require(manifest["header"]["source"]["content_sha256"] == expected_source_content_sha256,
             "Cache source content pin differs")
    _require(database.stat().st_size == manifest["database_bytes"]
             and _file_sha(database) == manifest["database_sha256"], "Cache database bytes/SHA differ")
    connection = _connection(database)
    try:
        _header(connection, manifest["header"])
    finally:
        connection.close()
    _require(_stat(manifest_path) == before_manifest and _stat(database) == before_database,
             "Cache changed during independent verification")
    receipt = {"host": socket.gethostname(), "manifest_stat": before_manifest, "database_stat": before_database}
    cls = NativeSamplingCacheIndex if manifest["header"]["source"]["native_identity_available"] else SamplingCacheIndex
    return cls(directory, manifest, receipt, expected_manifest_sha256, expected_source_content_sha256)
