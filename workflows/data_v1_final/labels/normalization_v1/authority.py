"""Molecule-level membership and exact opaque geometry-key exclusions."""
from __future__ import annotations

import collections
from pathlib import Path

from runtime import load, require, ref, path_list, sqlstr, semantic_sha

ROLE_SET = {"TRAIN", "VAL", "FULL", "EMBARGO"}


def geometry_key(row):
    source = row["geometry_source"]
    if source not in {"pm7", "uff_sprime"} or not row["geometry_id"]:
        raise ValueError("UNKNOWN_GEOMETRY_SOURCE_OR_EMPTY_OPAQUE_ID")
    return str(row["molecule_id"]), source, str(row["geometry_id"])


def physical_key(row):
    source = row["geometry_source"]
    if source == "pm7":
        if not row.get("native_record_id") or row.get("sprime_conf_idx") is not None:
            raise ValueError("PM7_MAP_REQUIRES_NATIVE_RECORD_ID_ONLY")
        return str(row["molecule_id"]), source, str(row["native_record_id"])
    if source == "uff_sprime":
        n = row.get("sprime_conf_idx")
        if type(n) is not int or n < 0:
            raise ValueError("UFF_MAP_REQUIRES_NONNEGATIVE_INT64_CONFORMER_INDEX")
        return str(row["molecule_id"]), source, n
    raise ValueError("UNKNOWN_PHYSICAL_GEOMETRY_SOURCE")


def eligible(role, common, key, parent_key, excluded):
    """Parent key means a geometry/view parent, never an LMDB provenance parent."""
    if role not in ROLE_SET:
        raise ValueError("UNKNOWN_EFFECTIVE_ROLE")
    if role != "TRAIN":
        return False, "ROLE_" + role
    if not common:
        return False, "OUTSIDE_FROZEN_COMMON_POPULATION"
    if key in excluded or (parent_key is not None and parent_key in excluded):
        return False, "HELDOUT_GEOMETRY_OR_ITS_PERTURBED_VIEW"
    return True, "FIT_TRAIN_COMMON_NOT_DIAGNOSTIC"


def check_diagnostic_rows(rows, geom_rows, members, roles, expected=20000):
    maps = {geometry_key(r): r for r in geom_rows}
    if len(maps) != len(geom_rows):
        raise ValueError("DUPLICATE_GEOMETRY_MAP_KEY")
    excluded = set()
    per = collections.defaultdict(set)
    for row in rows:
        key = geometry_key(row)
        if key in excluded or key not in maps:
            raise ValueError("DIAGNOSTIC_DUPLICATE_OR_GEOMETRY_MAP_FK_MISSING")
        if not members.get(key[0], False) or roles.get(key[0]) != "TRAIN":
            raise ValueError("DIAGNOSTIC_NOT_COMMON_TRAIN")
        if maps[key].get("parent_geometry_id") is not None:
            raise ValueError("DIAGNOSTIC_MUST_NAME_BASE_GEOMETRY_NOT_PERTURBED_VIEW")
        excluded.add(key)
        per[key[1]].add(key[0])
    if set(per) != {"pm7", "uff_sprime"} or any(len(v) != expected for v in per.values()):
        raise ValueError("DIAGNOSTIC_MOLECULE_COUNTS_NOT_EXACT")
    if per["pm7"] != per["uff_sprime"] or len(excluded) != 2 * expected:
        raise ValueError("DIAGNOSTIC_PM7_SPRIME_MOLECULES_DIFFER_OR_MULTIPLE_GEOMETRIES")
    return excluded


def frozen_inputs(cfg):
    pins = cfg["authority"]
    for name in ("common", "roles", "geometry_map", "diagnostic"):
        if not isinstance(pins.get(name), dict):
            raise ValueError("REAL_FROZEN_AUTHORITY_PIN_REQUIRED:" + name)
    objs = {name: load(require(pin)) for name, pin in pins.items()}
    common, roles, geom, diag = (objs[n] for n in ("common", "roles", "geometry_map", "diagnostic"))
    if common["status"] != "COMMON_POPULATION_V1_FROZEN":
        raise ValueError("COMMON_NOT_FROZEN")
    if roles["status"] != "ROUTINE_MOLECULE_VAL_ROLES_FROZEN":
        raise ValueError("EFFECTIVE_ROLES_NOT_FROZEN")
    if geom["status"] != "CANONICAL_GEOMETRY_MAP_V1_FROZEN":
        raise ValueError("OPAQUE_GEOMETRY_MAP_NOT_FROZEN")
    if diag["status"] != "SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN":
        raise ValueError("DIAGNOSTIC_NOT_FROZEN")
    if (common["roles_manifest_sha256"] != pins["roles"]["sha256"]
            or diag["common_population_manifest_sha256"] != pins["common"]["sha256"]
            or diag["geometry_map_manifest_sha256"] != pins["geometry_map"]["sha256"]):
        raise ValueError("AUTHORITY_MANIFEST_CROSS_BINDING_DIFFERS")
    if (diag["diagnostic_TRAIN_molecules"], diag["excluded_PM7_geometries"],
            diag["excluded_Sprime_geometries"], diag["all_excluded_geometries_materialized"]) != (20000, 20000, 20000, True):
        raise ValueError("PRODUCTION_DIAGNOSTIC_REQUIRES_EXACT_20000_PLUS_20000")
    role_pins = roles.get("molecule_role_tables") or [
        p for p in roles["outputs"] if Path(p["path"]).parent.name == "molecule_roles"]
    table_pins = {"members": common["membership_tables"], "roles": role_pins,
                  "geometry": geom["map_tables"], "diagnostic": diag["excluded_geometry_tables"]}
    for rows in table_pins.values():
        if not rows:
            raise ValueError("FROZEN_AUTHORITY_TABLES_EMPTY")
        for pin in rows:
            require(pin)
    order = load(require(geom["order_manifest"]))
    if order["status"] != "CONFORMER_ORDER_V1_FROZEN":
        raise ValueError("GEOMETRY_ORDER_MANIFEST_NOT_FROZEN")
    if diag["order_manifest_sha256"] != geom["order_manifest"]["sha256"]:
        raise ValueError("DIAGNOSTIC_ORDER_MANIFEST_BINDING_DIFFERS")
    if not diag.get("target_exclusion_tables"):
        raise ValueError("ALL_DIAGNOSTIC_TARGET_EXCLUSIONS_NOT_PHYSICALLY_MATERIALIZED")
    table_pins["targets"] = diag["target_exclusion_tables"]
    for pin in table_pins["targets"]:
        require(pin)
    return objs, table_pins


def install_authority(db, cfg):
    objs, pins = frozen_inputs(cfg)
    for name, refs in pins.items():
        db.execute("CREATE VIEW " + name + " AS SELECT * FROM read_parquet(" +
                   path_list([p["path"] for p in refs]) + ")")
    expected_types = {
        "members": {"molecule_id": "VARCHAR", "common_population": "BOOLEAN"},
        "roles": {"molecule_id": "VARCHAR", "effective_role": "VARCHAR"},
        "geometry": {"molecule_id": "VARCHAR", "geometry_source": "VARCHAR", "geometry_id": "VARCHAR",
                     "native_record_id": "VARCHAR", "sprime_conf_idx": "BIGINT", "parent_geometry_id": "VARCHAR", "view_id": "VARCHAR"},
        "diagnostic": {"molecule_id": "VARCHAR", "geometry_source": "VARCHAR", "geometry_id": "VARCHAR"},
        "targets": {"molecule_id": "VARCHAR", "geometry_source": "VARCHAR", "geometry_id": "VARCHAR"}}
    for name, fields in expected_types.items():
        actual = {row[0]: row[1] for row in db.execute("DESCRIBE " + name).fetchall()}
        if any(actual.get(key) != kind for key, kind in fields.items()):
            raise ValueError("FROZEN_AUTHORITY_COLUMN_TYPE_DIFFERS:" + name)
    for name in ("members", "roles"):
        n, u = db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM " + name).fetchone()
        if n != u:
            raise ValueError("DUPLICATE_MOLECULE_AUTHORITY:" + name)
    if db.execute("SELECT count(*) FROM roles WHERE effective_role IS NULL OR upper(effective_role) NOT IN ('TRAIN','VAL','FULL','EMBARGO')").fetchone()[0]:
        raise ValueError("INVALID_EFFECTIVE_ROLE")
    if db.execute("SELECT count(*) FROM members WHERE common_population IS NULL").fetchone()[0]:
        raise ValueError("NULL_COMMON_MEMBERSHIP")
    # Map rows are opaque IDs. No prefix, record-id substring or provenance-parent inference.
    invalid = db.execute("""SELECT count(*) FROM geometry WHERE molecule_id IS NULL OR geometry_id IS NULL
        OR geometry_id='' OR geometry_source NOT IN ('pm7','uff_sprime') OR geometry_source IS NULL
        OR (geometry_source='pm7' AND (native_record_id IS NULL OR native_record_id='' OR sprime_conf_idx IS NOT NULL))
        OR (geometry_source='uff_sprime' AND (sprime_conf_idx IS NULL OR sprime_conf_idx<0))""").fetchone()[0]
    if invalid:
        raise ValueError("INVALID_FROZEN_GEOMETRY_MAP_PHYSICAL_KEY")
    for key, condition in (("molecule_id,geometry_source,geometry_id", ""),
                           ("molecule_id,geometry_source,native_record_id,sprime_conf_idx", " WHERE parent_geometry_id IS NULL")):
        if db.execute("SELECT count(*) FROM (SELECT " + key + ",count(*) n FROM geometry" + condition + " GROUP BY " + key + " HAVING n<>1)").fetchone()[0]:
            raise ValueError("GEOMETRY_MAP_KEY_NOT_UNIQUE")
    if db.execute("""SELECT count(*) FROM geometry g LEFT JOIN geometry p ON g.molecule_id=p.molecule_id
        AND g.geometry_source=p.geometry_source AND g.parent_geometry_id=p.geometry_id
        WHERE g.parent_geometry_id IS NOT NULL AND (p.geometry_id IS NULL OR p.parent_geometry_id IS NOT NULL
        OR g.parent_geometry_id=g.geometry_id)""").fetchone()[0]:
        raise ValueError("GEOMETRY_VIEW_PARENT_NOT_A_DIRECT_MAPPED_BASE_GEOMETRY")
    # Production diagnostic table is small (40k). Pure fixture helper tests the same key rules.
    diag = db.execute("SELECT * FROM diagnostic ORDER BY molecule_id,geometry_source,geometry_id").fetch_arrow_table().to_pylist()
    dmap = db.execute("SELECT g.* FROM geometry g SEMI JOIN diagnostic d USING(molecule_id,geometry_source,geometry_id)").fetch_arrow_table().to_pylist()
    mids = sorted({str(r["molecule_id"]) for r in diag})
    db.execute("CREATE TEMP TABLE diagnostic_molecules AS SELECT DISTINCT molecule_id FROM diagnostic")
    members = dict(db.execute("SELECT m.molecule_id,m.common_population FROM members m SEMI JOIN diagnostic_molecules d USING(molecule_id)").fetchall())
    roles = dict(db.execute("SELECT r.molecule_id,upper(r.effective_role) FROM roles r SEMI JOIN diagnostic_molecules d USING(molecule_id)").fetchall())
    check_diagnostic_rows(diag, dmap, members, roles)
    if db.execute("""SELECT count(*) FROM targets t LEFT JOIN geometry g USING(molecule_id,geometry_source,geometry_id)
        LEFT JOIN diagnostic d ON d.molecule_id=t.molecule_id AND d.geometry_source=t.geometry_source
        AND d.geometry_id=coalesce(g.parent_geometry_id,g.geometry_id)
        WHERE g.geometry_id IS NULL OR d.geometry_id IS NULL""").fetchone()[0]:
        raise ValueError("DIAGNOSTIC_TARGET_NOT_MAPPED_TO_EXCLUDED_BASE_GEOMETRY")
    if db.execute("""SELECT count(*) FROM geometry g SEMI JOIN diagnostic d ON d.molecule_id=g.molecule_id
        AND d.geometry_source=g.geometry_source AND d.geometry_id=coalesce(g.parent_geometry_id,g.geometry_id)
        WHERE NOT EXISTS (SELECT 1 FROM targets t WHERE t.molecule_id=g.molecule_id
          AND t.geometry_source=g.geometry_source AND t.geometry_id=g.geometry_id)""").fetchone()[0]:
        raise ValueError("DIAGNOSTIC_BASE_OR_DIRECT_VIEW_TARGET_EXCLUSION_INCOMPLETE")
    return {"authority": cfg["authority"], "tables": pins,
            "diagnostic_geometry_key_sha256": semantic_sha(sorted(geometry_key(r) for r in diag)),
            "diagnostic_TRAIN_molecules": len(mids)}
