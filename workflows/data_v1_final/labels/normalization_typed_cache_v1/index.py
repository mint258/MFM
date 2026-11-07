"""D4-specific bounded disk locators; never a general data discovery API.

Input rows are normalized only by a separately reviewed future CPU inventory
adapter. The recovery producer's not-yet-frozen JSON parser is not guessed.
An index closure is not execution authorization or final normalization.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
from .contract import need, reference
from .ordering import row_key

SCHEMA = "D4_TYPED_CACHE_LOGICAL_LOCATOR_SQLITE_V1"
FIELDS = {"partition_id", "record_ordinal", "task_code", "row_kind", "original_file_position",
          "source_physical_row", "part", "row_group", "local_row", "origin_id", "owner"}


def validate_locator(row):
    need(set(row) == FIELDS, "EXACT_D4_LOCATOR_FIELDS_REQUIRED")
    row_key(row)
    for key in ("record_ordinal", "row_group", "local_row"):
        need(type(row[key]) is int and row[key] >= 0, "NONNEGATIVE_LITERAL_LOCATOR:" + key)
    need(type(row["task_code"]) is int and ((row["row_kind"] == "base" and row["task_code"] == 255)
         or (row["row_kind"] == "task" and 0 <= row["task_code"] < 14)), "BASE255_OR_ORIGINAL_TASK_CODE")
    reference(row["part"])
    need(isinstance(row["origin_id"], str) and row["origin_id"], "EXACT_ACCEPTED_ORIGIN_ID")
    owner = row["owner"]
    needed = {"record_id", "molecule_id", "record_ordinal", "attempt_id", "job_id", "task_id", "lane",
              "total_atoms", "heavy_atoms", "record_payload_sha256", "new_role", "effective_role",
              "common_population", "geometry_source", "geometry_id", "fit_reason", "fit_eligible"}
    need(needed <= set(owner) and type(owner['record_ordinal']) is int
         and owner["record_ordinal"] == row["record_ordinal"], "COMPLETE_FINAL_OWNER_AND_FIT_SIDE_REQUIRED")
    need(isinstance(owner['record_payload_sha256'], str)
         and re.fullmatch('[0-9a-f]{64}', owner['record_payload_sha256']) is not None,
         'EXACT_FORMAL_RECORD_PAYLOAD_SHA_REQUIRED')
    need(type(owner["fit_eligible"]) is bool and type(owner["common_population"]) is bool,
         "EXACT_FIT_SIDE_BOOLEAN_TYPES")
    need(type(owner["total_atoms"]) is int and owner["total_atoms"] > 0
         and type(owner["heavy_atoms"]) is int and 0 <= owner["heavy_atoms"] <= owner["total_atoms"],
         "EXACT_OWNER_ATOM_COUNTS")
    need(isinstance(owner["record_id"], str) and owner["record_id"]
         and isinstance(owner["molecule_id"], str) and owner["molecule_id"], "EXACT_OWNER_IDS")
    if owner["fit_eligible"]:
        need(owner["effective_role"] == "TRAIN" and owner["common_population"] is True
             and owner["fit_reason"] == "FIT_TRAIN_COMMON_NOT_DIAGNOSTIC", "FORBIDDEN_FIT_SIDE")
    need(owner["geometry_source"] == "pm7", "PM7_PD_INTERFACE_ONLY_PPRIME_REMAINS_PENDING")
    return row


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class LocatorIndex:
    def __init__(self, path, *, create=False, maximum_bytes=None):
        self.path = Path(path)
        if create:
            need(type(maximum_bytes) is int and maximum_bytes >= 1 << 20, "REVIEWED_INDEX_CAP_REQUIRED")
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); os.close(fd)
            self.db = sqlite3.connect(self.path)
            self.db.execute("PRAGMA page_size=4096")
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA cache_size=-4096")
            self.db.execute("PRAGMA max_page_count=" + str(maximum_bytes // 4096))
            self.db.executescript("""CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE owners(ordinal INTEGER PRIMARY KEY,record_id TEXT UNIQUE,payload TEXT);
                CREATE TABLE parts(id INTEGER PRIMARY KEY,reference TEXT UNIQUE,origin TEXT);
                CREATE TABLE locators(partition_id INTEGER,ordinal INTEGER,task INTEGER,kind TEXT,
                filepos INTEGER,physical INTEGER,part_id INTEGER,rg INTEGER,local_row INTEGER,
                PRIMARY KEY(ordinal,task),UNIQUE(partition_id,kind,filepos,physical)) WITHOUT ROWID;""")
            self.db.execute("INSERT INTO meta VALUES('schema',?)", (SCHEMA,))
        else:
            need(self.path.is_file() and not self.path.is_symlink(), "CLOSED_NORMALIZED_INDEX_REQUIRED")
            self.db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
            need(self.db.execute("SELECT value FROM meta WHERE key='schema'").fetchone() == (SCHEMA,), "EXACT_INDEX_SCHEMA")

    def add(self, row):
        validate_locator(row)
        owner = dumps(row["owner"]); part = dumps(reference(row["part"]))
        need(len(owner.encode()) <= 1 << 20, "BOUNDED_OWNER_METADATA_NO_LABEL_POOL")
        ordinal = row["record_ordinal"]
        prior = self.db.execute("SELECT payload FROM owners WHERE ordinal=?", (ordinal,)).fetchone()
        if prior is None:
            self.db.execute("INSERT INTO owners VALUES(?,?,?)", (ordinal, row["owner"]["record_id"], owner))
        else:
            need(prior == (owner,), "SAME_ORDINAL_OWNER_AND_FIT_SIDE_CHANGED")
        existing = self.db.execute("SELECT id,origin FROM parts WHERE reference=?", (part,)).fetchone()
        if existing is None:
            cur = self.db.execute("INSERT INTO parts(reference,origin) VALUES(?,?)", (part,row["origin_id"]))
            part_id = cur.lastrowid
        else:
            part_id = existing[0]; need(existing[1] == row["origin_id"], "PART_ORIGIN_CHANGED")
        try:
            self.db.execute("INSERT INTO locators VALUES(?,?,?,?,?,?,?,?,?)", (row["partition_id"], ordinal,
                row["task_code"], row["row_kind"], row["original_file_position"], row["source_physical_row"],
                part_id, row["row_group"], row["local_row"]))
        except sqlite3.IntegrityError as exc:
            raise ValueError("DUPLICATE_CANONICAL_KEY_OR_SOURCE_ROW") from exc

    def rows(self, partition_id, kind):
        need(type(partition_id) is int and partition_id >= 0 and kind in {"base", "task"}, "EXACT_PARTITION_AND_KIND")
        sql = """SELECT l.ordinal,l.task,l.filepos,l.physical,l.rg,l.local_row,p.reference,p.origin,o.payload
            FROM locators l JOIN parts p ON p.id=l.part_id JOIN owners o ON o.ordinal=l.ordinal
            WHERE l.partition_id=? AND l.kind=? ORDER BY l.filepos,l.physical"""
        for ordinal,task,filepos,physical,rg,local,part,origin,owner in self.db.execute(sql,(partition_id,kind)):
            yield validate_locator({"partition_id":partition_id,"record_ordinal":ordinal,"task_code":task,
                "row_kind":kind,"original_file_position":filepos,"source_physical_row":physical,
                "row_group":rg,"local_row":local,"part":json.loads(part),"origin_id":origin,"owner":json.loads(owner)})

    def owner(self, ordinal):
        row = self.db.execute("SELECT payload FROM owners WHERE ordinal=?", (ordinal,)).fetchone()
        need(row is not None, "EXACT_OWNER_ORDINAL_MISSING")
        return json.loads(row[0])

    def close(self):
        self.db.commit(); self.db.close()
