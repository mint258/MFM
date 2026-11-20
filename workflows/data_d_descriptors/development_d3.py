"""Resumable native-member D3 production; no default hydrogen policy.

Config: source_manifest, recipe_root, peer_root, hydrogen_policy, output,
peak_bytes (joint actual-node guard), chunk_rows=256/512. Optional
output_budget_bytes may lower the existing 512 MiB development allowance.
Optional datasets selects complete qm9/expansionrx datasets after the original
population join; omitted means all original members. RAW_COMPLETE is scoped.
Six molecular D3 values and atomic SASA have independent F64/u8 arrays.
Only the original native geometry and original D3 adapter are used.
"""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np

from .development_geometry import D3_NAMES, UnavailableD3, native_geometry, original_d3
from .export import D20_NAMES
from .prepare_benchmark import _peer_module
from .prepare_development import source_smiles
from .produce import guard, publish, read_json, reference, require_cpu, rows

SCHEMA = "D_DEVELOPMENT_NATIVE_D3_V1"
POLICIES = ("native_only", "B6_fixed_native_H")
OWN_LIMIT = 512 * 2**20


def policy(config):
    value = config.get("hydrogen_policy")
    if value not in POLICIES:
        raise ValueError("EXPLICIT_DEVELOPMENT_HYDROGEN_POLICY_REQUIRED")
    return value


def load_population(manifest):
    """One producer identity join; never open endpoint targets."""
    if manifest.get("status") != "SOURCE_READY":
        raise ValueError("Closed development structure source required")
    canonical = {}
    for row in rows(manifest["input_rows"]):
        mid = row["molecule_id"]
        if mid in canonical or set(row["existing_D20"]) != set(D20_NAMES):
            raise ValueError("Original canonical D20/molecule identity differs")
        canonical[mid] = row["existing_D20"]
    members, seen = [], set()
    for row in rows(manifest["membership_reference"]["path"]):
        key = (row["dataset"], row["member_uid"])
        ref = row["D3_geometry_reference"]
        if (key in seen or row["molecule_id"] not in canonical
                or any(ref[name] != row[name] for name in ("dataset", "member_uid", "member_index"))):
            raise ValueError("Original member/native geometry identity differs")
        seen.add(key)
        members.append(row)
    if len(canonical) != manifest["unique_molecules"] or len(members) != manifest["retained_members"]:
        raise ValueError("Closed source population size differs")
    return canonical, members


def select_datasets(members, datasets=None):
    available = {member["dataset"] for member in members}
    if not available <= {"qm9", "expansionrx"}:
        raise ValueError("Unregistered original development dataset")
    requested = available if datasets is None else datasets
    if (not isinstance(requested, (list, tuple, set)) or not requested
            or len(set(requested)) != len(requested) or not set(requested) <= available):
        raise ValueError("Explicit complete dataset scope must exist in original manifest")
    scope = sorted(requested)
    return scope, [dict(member, source_member_row=index) for index, member in enumerate(members)
                   if member["dataset"] in scope]


def atomic_values(values, count):
    if values is None:
        return np.full(count, np.nan, dtype=np.float64), np.zeros(count, dtype=np.uint8)
    if len(values) != count:
        raise ValueError("Original atomic SASA/native source map length differs")
    raw = np.asarray([np.nan if v is None else v for v in values], dtype=np.float64)
    observed = np.asarray([v is not None for v in values], dtype=bool)
    valid = np.isfinite(raw) & (np.abs(raw) <= np.finfo(np.float32).max)
    status = np.zeros(count, dtype=np.uint8)
    status[observed & valid], status[observed & ~valid] = 1, 2
    return raw, status


def work_member(member, canonical, store, *, hydrogen_policy, calculator,
                smiles_reader=source_smiles, geometry_reader=native_geometry, d3_reader=original_d3):
    """Use this member's physical graph, never another member's MID representative."""
    ref = member["D3_geometry_reference"]
    graph, geometry, reason = None, None, None
    try:
        geometry = geometry_reader(store, member["dataset"], member["member_index"])
        if geometry["member_uid"] != member["member_uid"]:
            raise ValueError("Original native geometry UID differs")
        graph = smiles_reader({"dataset": member["dataset"], "source_frame": ref["source_frame"]})
        result = d3_reader(graph, geometry["atomic_numbers"], geometry["coordinates_A"], canonical,
                          hydrogen_policy=hydrogen_policy, calculator=calculator)
    except UnavailableD3 as exc:
        reason = str(exc)
        result = {"raw_values": np.full(6, np.nan, dtype=np.float64), "status": np.zeros(6, dtype=np.uint8),
            "work_atom_to_native_source": list(range(ref["native_n_atoms"])), "atomic_SASA_source_values": None,
            "geometry_policy": "NATIVE_D3_UNAVAILABLE", "issues": [reason]}
    raw, status = np.asarray(result["raw_values"], dtype=np.float64), np.asarray(result["status"], dtype=np.uint8)
    if raw.shape != (6,) or status.shape != (6,) or not np.isin(status, [0, 1, 2]).all():
        raise ValueError("Original D3 result layout differs")
    atom_map = list(result["work_atom_to_native_source"])
    atom_raw, atom_status = atomic_values(result["atomic_SASA_source_values"], len(atom_map))
    record = {name: member[name] for name in ("dataset", "member_uid", "member_index", "molecule_id", "source_split")}
    if "source_member_row" in member:
        record["source_member_row"] = member["source_member_row"]
    record.update(D3_ordered_fields=list(D3_NAMES),
        D3_raw={name: float(raw[i]) if np.isfinite(raw[i]) else None for i, name in enumerate(D3_NAMES)},
        D3_status={name: int(status[i]) for i, name in enumerate(D3_NAMES)},
        D3_geometry_reference=copy.deepcopy(ref), source_smiles=graph,
        hydrogen_policy=hydrogen_policy, geometry_policy=result["geometry_policy"],
        source_missing_reason=reason, D3_issues=result["issues"], work_atom_to_native_source=atom_map,
        native_n_atoms=ref["native_n_atoms"], native_coordinates_changed=False,
        new_conformer_embedded=False, atomic_SASA_in_molecular_vector=False)
    if geometry is not None:
        record["native_atom_reference"] = {key: geometry[key] for key in
            ("physical_source", "physical_offset", "source_atom_ids")}
    return raw, status, atom_raw, atom_status, record


def check_cursor(checkpoint, identity, count, width):
    if checkpoint["identity"] != identity:
        raise ValueError("Native D3 source/policy/checkpoint identity changed")
    cursor = 0
    for index, part in enumerate(checkpoint["parts"]):
        if (part["part_index"] != index or part["start"] != cursor
                or part["stop"] != min(cursor + width, count) or part["stop"] <= cursor):
            raise ValueError("Native D3 closed chunk cursor is not contiguous")
        cursor = part["stop"]
    if checkpoint["next_member"] != cursor:
        raise ValueError("Native D3 cursor differs from closed chunks")
    return cursor


def _array_bytes(values):
    stream = io.BytesIO()
    np.save(stream, values, allow_pickle=False)
    return stream.getvalue()


def write_part(output, part_index, start, results, checkpoint, config):
    """Write only this uncommitted part; close its cursor after every fsync."""
    prefix = "part_" + str(part_index).zfill(6)
    paths = {key: output / (prefix + "_" + key + suffix) for key, suffix in
             (("values", ".npy"), ("status", ".npy"), ("atom_values", ".npy"),
              ("atom_status", ".npy"), ("members", ".jsonl"))}
    records, offset = [], 0
    for local, result in enumerate(results):
        record = dict(result[4], member_row=start + local, part_row=local,
            D3_values=str(paths["values"]), D3_status_store=str(paths["status"]),
            atomic_SASA_values=str(paths["atom_values"]), atomic_SASA_status=str(paths["atom_status"]),
            atom_offset=offset, atom_count=len(result[2]))
        records.append(record)
        offset += len(result[2])
    payloads = {"values": _array_bytes(np.stack([r[0] for r in results])),
        "status": _array_bytes(np.stack([r[1] for r in results])),
        "atom_values": _array_bytes(np.concatenate([r[2] for r in results])),
        "atom_status": _array_bytes(np.concatenate([r[3] for r in results])),
        "members": "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in records).encode("utf-8")}
    size = sum(len(payload) for payload in payloads.values())
    closed = sum(part["bytes"] + part["member_bytes"] for part in checkpoint["parts"])
    # Include final member-map projection, a simultaneous unclosed replacement,
    # and metadata/checkpoint space within the existing development allowance.
    needed = closed + 2 * size + len(payloads["members"]) + 2**21
    if needed > config.get("output_budget_bytes", OWN_LIMIT):
        raise ValueError("DEVELOPMENT_D3_OUTPUT_EXCEEDS_EXISTING_ALLOWANCE")
    for key, payload in payloads.items():
        guard(output, config)
        pending = Path(str(paths[key]) + ".partial")
        with pending.open("wb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(pending, paths[key])
    return dict(part_index=part_index, start=start, stop=start + len(results), bytes=size,
                member_bytes=len(payloads["members"]), **{key: str(path) for key, path in paths.items()})


def produce(config, *, store_factory=None, calculator=None, smiles_reader=source_smiles,
            geometry_reader=native_geometry, d3_reader=original_d3):
    chosen = policy(config)
    require_cpu(dict(config, workers=1))
    allowance = config.get("output_budget_bytes", OWN_LIMIT)
    if type(allowance) is not int or not 0 < allowance <= OWN_LIMIT:
        raise ValueError("EXISTING_DEVELOPMENT_ALLOWANCE_AT_MOST_512_MIB_REQUIRED")
    started = time.perf_counter()
    source = read_json(config["source_manifest"])
    canonical, members = load_population(source)
    source_count = len(members)
    dataset_scope, members = select_datasets(members, config.get("datasets"))
    output = Path(config["output"]).resolve()
    identity = {"schema": SCHEMA, "source_manifest": reference(config["source_manifest"]),
        "input_rows": reference(source["input_rows"]), "members": reference(source["membership_reference"]["path"]),
        "store": source["source_references"]["store"], "hydrogen_policy": chosen,
        "calculator": reference(Path(config["peer_root"]) / "workflows/benchmark_data/downstream_science.py"),
        "chunk_rows": config["chunk_rows"], "member_count": len(members),
        "dataset_scope": dataset_scope, "source_member_count": source_count}
    final, marker = output / "manifest.json", output / "cursor.json"
    if final.exists():
        closed = read_json(final)
        if closed["identity"] != identity:
            raise ValueError("Closed native D3 source/policy changed")
        return closed
    guard(output.parent, config); output.mkdir(parents=True, exist_ok=True)
    checkpoint = read_json(marker) if marker.exists() else {"identity": identity, "next_member": 0, "parts": []}
    cursor = check_cursor(checkpoint, identity, len(members), config["chunk_rows"])
    if store_factory is None:
        sys.path.insert(0, str(Path(config["recipe_root"]) / "current"))
        from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
        store_factory = TrainOnlyPackedStore
    if calculator is None and cursor < len(members):
        adapter = _peer_module(Path(config["peer_root"]), "downstream_science")
        # Import the unchanged backend before the per-member cached-HBA
        # context, preserving its original import-time callable references.
        adapter.load()
        calculator = adapter.geometry_descriptors
    stores = {}
    try:
        while cursor < len(members):
            guard(output, config)
            begin, results = time.perf_counter(), []
            for member in members[cursor:cursor + config["chunk_rows"]]:
                path = member["D3_geometry_reference"]["store"]
                if path != identity["store"]["path"]:
                    raise ValueError("Member native store differs from closed source")
                if path not in stores:
                    stores[path] = store_factory(path, verify_digests=False)
                results.append(work_member(member, canonical[member["molecule_id"]], stores[path],
                    hydrogen_policy=chosen, calculator=calculator, smiles_reader=smiles_reader,
                    geometry_reader=geometry_reader, d3_reader=d3_reader))
            part = write_part(output, len(checkpoint["parts"]), cursor, results, checkpoint, config)
            part.update(job_id=os.environ["SLURM_JOB_ID"], node=platform.node(), elapsed_seconds=time.perf_counter() - begin)
            checkpoint["parts"].append(part)
            checkpoint["next_member"] = cursor = part["stop"]
            publish(marker, checkpoint, config)
    finally:
        for store in stores.values():
            if hasattr(store, "close"):
                store.close()
    mapping, pending = output / "member_map.jsonl", output / "member_map.jsonl.partial"
    guard(output, config)
    with pending.open("wb") as stream:
        for part in checkpoint["parts"]:
            guard(output, config)
            with Path(part["members"]).open("rb") as source_stream:
                for line in source_stream:
                    stream.write(line)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, mapping)
    report = {"schema": SCHEMA, "status": "RAW_COMPLETE", "identity": identity, "parts": checkpoint["parts"],
        "ordered_fields": list(D3_NAMES), "molecular_dtype": "float64", "status_dtype": "uint8",
        "status_codes": {"missing": 0, "valid": 1, "nonfinite_or_overflow": 2},
        "member_count": len(members), "hydrogen_policy": chosen,
        "dataset_scope": dataset_scope, "source_member_count": source_count,
        "complete_source_population": len(members) == source_count,
        "membership_reference": dict(source["membership_reference"], path=str(mapping)),
        "atomic_SASA_in_molecular_vector": False, "canonical_D20_replaced": False,
        "native_coordinates_changed": False, "new_conformer_embedded": False, "target_values_read": False,
        "normalization_fitted": False, "reception_acceptance": "pending", "current_C1_complete": False,
        "job_id": os.environ["SLURM_JOB_ID"], "node": platform.node(),
        "elapsed_seconds_this_attempt": time.perf_counter() - started}
    publish(final, report, config)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    produce(read_json(parser.parse_args().config))


if __name__ == "__main__":
    main()
