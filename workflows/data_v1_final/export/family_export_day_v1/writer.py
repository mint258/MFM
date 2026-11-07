"""Inherited family assembly/transactions with explicit shard/transport IO seams."""
from __future__ import annotations
import contextlib
from pathlib import Path
from . import contract as C,transport as T
from .store import Writer as GranularFamilyWriter
L=C.legacy();E=L['pipeline_v1.export'];O=L['pipeline_v1.io'];S=L['pipeline_v1.source']
scalar=O.scalar;reject_rows=O.reject_rows;memory_guard=O.memory_guard;disk_cap=O.disk_cap
unpack=S.unpack;reason_annotations=S.reason_annotations;canonical_json=L['wire_v1.codec'].canonical_json;file_ref=L['wire_v1.store'].file_ref

def export_shard(db, out, compiled, config):
    stores = []
    # Explicit partitions prevent a gradient view being silently treated as a
    # parent geometry, or a P value copied to an S' condition.
    partitioned = set()
    for partition in config["partitions"]:
        name, kind, src, view = (partition[k] for k in ("name", "kind", "geometry_source", "view_id"))
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("SAFE_EXPLICIT_PARTITION_NAME_REQUIRED")
        if kind == "geometry":
            schema, targets = {"kind": "geometry"}, ["__geometry__"]
        elif kind == "labels":
            schema = T.family_schema(compiled, partition["family"], src, partition["target_ids"])
            schema["mask_encoding"] = "field-set+sparse-leaf-v1"
            targets = [*schema["compiled"]["physical_targets"], *schema["ordered_record_targets"]]
            for tid in targets:
                key = (tid, view)
                partitioned.add(key)
        else:
            raise ValueError("PARTITION_KIND_INVALID")
        query = "SELECT * FROM selected_geometry WHERE geometry_source=? AND view_id IS ? AND geometry_id IN(SELECT geometry_id FROM partition_members WHERE name=?) ORDER BY geometry_id"
        if scalar(db, "SELECT count(*) FROM selected_geometry WHERE geometry_source=? AND view_id IS ? AND geometry_id IN(SELECT geometry_id FROM partition_members WHERE name=?)",(src,view,name))==0:
            continue
        schema.update(config["_schema_authorities"])
        path = out / name
        with contextlib.ExitStack() as stack:
            writer = GranularFamilyWriter(path, schema, map_bytes=partition["map_bytes"])
            stack.callback(writer.close)
            buffered=[];buffered_bytes=0;processed=0
            for geometry in db.execute(query, (src, view,name)):
                config['_budget_check']()
                size = scalar(db, "SELECT coalesce(sum(length(payload)),0) FROM pieces WHERE geometry_id=?", (geometry["geometry_id"],))
                if size > 128 * 1024 ** 2:
                    raise ValueError("GEOMETRY_STAGING_PAYLOAD_EXCEEDS_128MIB")
                pieces = db.execute("SELECT part,n_atoms,source_index,row_group,row_number,payload FROM pieces WHERE geometry_id=?", (geometry["geometry_id"],)).fetchall()
                by_part = {p["part"]: p for p in pieces}
                missing = set(targets) - set(by_part)
                if missing:
                    raise ValueError("CANONICAL_SOURCE_RECORD_OR_TARGET_MISSING:" + geometry["geometry_id"] + ":" + ",".join(sorted(missing)))
                ns = {by_part[t]["n_atoms"] for t in targets}
                if len(ns) != 1 or ("__geometry__" in by_part and by_part["__geometry__"]["n_atoms"] not in ns):
                    raise ValueError("SOURCE_GEOMETRY_AND_LABEL_ATOM_COUNTS_DISAGREE")
                arrays, granularity, null_fields, source_precision = {}, {}, [], {}
                for tid in targets:
                    value = unpack(by_part[tid]["payload"])
                    if set(arrays) & set(value):
                        raise ValueError("DUPLICATED_EXPORT_ARRAY")
                    arrays.update(value)
                    note = reason_annotations(by_part[tid]["payload"])
                    null_fields.extend(note.pop("_source_null_fields", []))
                    source_precision.update(note.pop('_source_precision', {}))
                    granularity.update(note)
                metadata = {"molecule_id": geometry["molecule_id"], "export_record_id": geometry["geometry_id"],
                    "geometry_source": src, "effective_role": geometry["effective_role"], "source_role": geometry["source_role"],
                    "n_atoms": ns.pop(), "parent_geometry_id": geometry["parent_geometry_id"], "view_id": view}
                if kind == "labels":
                    # These are recipe exposure decisions, not validity masks.
                    metadata["group_exposure_mask"] = config["group_exposure_mask"]
                    metadata['source_precision'] = source_precision
                    metadata["family_exposure_mask"] = config["family_exposure_mask"]
                    if granularity:
                        metadata["reason_granularity"] = granularity
                        metadata["reason_codebook_sha256"] = config.get("_reason_codebook_sha256")
                    if null_fields:
                        metadata["source_null_fields_with_masked_nan_placeholder"] = sorted(null_fields)
                metadata['permanent_float64_source_locators'] = [
                    {'source_index':p['source_index'],'row_group':p['row_group'],'row_number':p['row_number'],
                     'part':p['part']} for p in pieces if p['part'] in targets]
                metadata['actual_field_geometry_claims_reference'] = config['_field_claims_reference']
                metadata['current_parent_job_id'] = config['_actual_parent_job_id']
                metadata['not_an_independent_child_C0'] = True
                payload_bytes=sum(a.nbytes for a in arrays.values())
                if buffered and (len(buffered)>=64 or buffered_bytes+payload_bytes>128<<20):
                    writer.write_batch(buffered);buffered=[];buffered_bytes=0
                buffered.append((metadata,arrays));buffered_bytes+=payload_bytes
                db.execute("INSERT INTO exported VALUES(?,?,?,?)", (name, geometry["geometry_id"], kind, canonical_json(targets).decode()))
                memory_guard(3_000_000_000)
                processed+=1
                if processed % 512 == 0:
                    disk_cap(path, config["maximum_output_bytes"])
            if buffered:writer.write_batch(buffered)
            receipt = writer.finish()
        config["_retire"](path)
        if receipt["records"] <= 0:
            raise ValueError("EMPTY_EXPORT_PARTITION_NOT_ALLOWED")
        expected_records = scalar(db, "SELECT count(*) FROM selected_geometry WHERE geometry_source=? AND view_id IS ? AND geometry_id IN(SELECT geometry_id FROM partition_members WHERE name=?)", (src, view,name))
        expected_molecules = scalar(db, "SELECT count(DISTINCT molecule_id) FROM selected_geometry WHERE geometry_source=? AND view_id IS ? AND geometry_id IN(SELECT geometry_id FROM partition_members WHERE name=?)", (src, view,name))
        if receipt["records"] != expected_records or receipt["molecules"] != expected_molecules:
            raise ValueError("D5_EXPECTED_RECORD_OR_MOLECULE_COUNT_DIFFERS_FROM_WRITTEN_STORE")
        stores.append({"name": name, "kind": kind, "path": str(path), "manifest": file_ref(path / "manifest.json"), **receipt,
            "expected_records_from_frozen_selection": expected_records, "expected_molecules_from_frozen_selection": expected_molecules,
            "geometry_source": src, "view_id": view, "base_conformers": expected_records if view is None else 0})
    expected = config["actual_shard_target_ids"]
    if {tid for tid, _ in partitioned} != expected:
        raise ValueError("MAPPING_TARGETS_NOT_FULLY_EXPORTED")
    reject_rows(db, "SELECT geometry_id FROM selected_geometry WHERE geometry_id IN(SELECT geometry_id FROM shard_members) EXCEPT SELECT geometry_id FROM exported WHERE kind='geometry'", "SELECTED_BASE_OR_VIEW_GEOMETRY_NOT_EXPORTED")
    db.commit()
    return stores
