"""Minimal target-free B0/C1 descriptor input preparation; no benchmark fits.

An existing final frozen roster is mandatory. Its explicit ``tasks`` entries
must contain dataset/source_task, status must match required_roster_status,
and final_task_roster must be true. Candidate catalogs cannot substitute.
Groups without compatible existing C1 D20 are reported UNRESOLVED, not filled
or recomputed. Original membership/geometry references remain independent.
"""
import argparse
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import platform

from .b6_cache import unchanged_remove_hs
from .export import D20_NAMES, publish
from .prepare_development import write_jsonl
from .produce import guard, read_json, reference


def frozen_tasks(roster, required_status, proof, selector):
    if (not required_status or roster.get("status") != required_status
            or roster.get("final_task_roster") is not True):
        raise ValueError("Existing final frozen benchmark roster required; candidate catalog is insufficient")
    if (proof.get("deferred_registry_full_inventory_verified") is not True
            or proof.get("deferred_endpoint_count") != 5):
        raise ValueError("Existing five-deferred full-inventory scope proof required")
    tasks = list(dict.fromkeys((row["dataset"], row["source_task"]) for row in roster["tasks"]))
    if not tasks or selector(tasks) != tasks:
        raise ValueError("Frozen roster contains deferred or unregistered source tasks")
    return tasks


def sealed_geometry(scope, access_documents):
    queues = {scope["queue"]}
    if scope.get("reused_source_queue"):
        queues.add(scope["reused_source_queue"])
    for queue in queues:
        access = access_documents.get(queue)
        if (not access or access.get("immutable") is not True
                or access.get("cross_node_read_allowed") is not True):
            raise ValueError("Declared shared S-prime UFF source is not sealed: " + queue)
    return scope.get("reused_source_queue", scope["queue"])


def canonical_d20(feature, smiles, graph_equivalent):
    missing = dict.fromkeys(D20_NAMES)
    if feature is None or feature.get("features") is None or feature.get("valid_mask") is None:
        return missing, "CANONICAL_C1_D20_SOURCE_UNAVAILABLE"
    if feature.get("model_smiles") != smiles or not graph_equivalent(smiles):
        return missing, "C1_D20_INPUT_POLICY_NOT_EQUIVALENT_TO_ORIGINAL_D20"
    values, mask = feature["features"], feature["valid_mask"]
    if len(values) < 20 or len(mask) != len(values):
        raise ValueError("Existing C1 F64 values/mask do not match the declared schema")
    output = {}
    for index, name in enumerate(D20_NAMES):
        value = values[index]
        if mask[index] and (value is None or not math.isfinite(value)):
            return missing, "EXISTING_C1_OBSERVED_D20_VALUE_NONFINITE"
        output[name] = float(value) if mask[index] else None
    if all(value is None for value in output.values()):
        return output, "EXISTING_C1_D20_ALL_MISSING_REQUIRES_RESOLUTION"
    return output, None


def build_rows(structures, features, *, allowed_keys, canonical_key, graph_equivalent, sources):
    lookup = {}
    for row in features:
        key = (row["dataset"], row["record_id"])
        if key in lookup:
            raise ValueError("Duplicate existing C1 dataset/record_id binding")
        lookup[key] = row
    unique, members, unresolved, member_keys = {}, [], [], set()
    for original in structures:
        dataset, record_id = original["dataset"], original["record_id"]
        if canonical_key(dataset, original["source_file"]) not in allowed_keys:
            continue
        key = (dataset, record_id)
        if key in member_keys:
            raise ValueError("Duplicate original benchmark dataset/record_id")
        member_keys.add(key)
        feature = lookup.get(key)
        mid = ((feature or {}).get("native_shared_molecule_id")
               or original.get("shared_molecule_id") or record_id)
        if not isinstance(mid, str) or not mid:
            raise ValueError("An existing shared molecule ID or original record ID is required")
        smiles = original.get("model_smiles") or original.get("original_smiles")
        source = {"dataset": dataset, "record_id": record_id,
                  "source_file": original["source_file"], "structure_store": original["structure_store"]}
        values, error = canonical_d20(feature, smiles, graph_equivalent)
        if mid in unique and unique[mid]["smiles"] != smiles:
            raise ValueError("Existing molecule ID is not globally graph-unique; explicit old shared binding needed")
        if mid not in unique:
            unique[mid] = {"molecule_id": mid, "smiles": smiles,
                "source_error": None if smiles else "ORIGINAL_SOURCE_GRAPH_UNAVAILABLE",
                "source_binding": source, "existing_D20": values,
                "canonical_D20_source_error": error}
        elif error is None and unique[mid]["canonical_D20_source_error"] is not None:
            # Rebind to an actually available original source, never calculate
            # or infer a replacement value for the same existing molecule ID.
            unique[mid].update(source_binding=source, existing_D20=values, canonical_D20_source_error=None)
        geometry = {"required_geometry_source": "Sprime_UFF",
                    "geometry_source": "Sprime_UFF" if feature is not None else None,
                    "queue": sources["sealed_queue"] if feature is not None else None,
                    "dataset": dataset, "record_id": record_id, "source_C1_manifest": sources["C1"],
                    "source_geometry_scope": sources["geometry_scope"],
                    "model_atom_to_source": copy.deepcopy(original.get("model_atom_to_source")),
                    "state": "EXISTING_C1_SOURCE_REFERENCE" if feature is not None else "UNRESOLVED_SOURCE_REFERENCE"}
        members.append({"dataset": dataset, "record_id": record_id, "molecule_id": mid,
            "source_split": original.get("official_split"), "source_file": original["source_file"],
            "retained": original.get("retained"), "domain_eligible": original.get("domain_eligible"),
            "blind_fallback_required": original.get("blind_fallback_required"),
            "D3_geometry_reference": geometry, "frozen_roster": sources["roster"]})
        if error is not None or original.get("official_split") is None:
            unresolved.append({"dataset": dataset, "record_id": record_id,
                "canonical_D20_error": error,
                "split_binding": "EXTERNAL_FROZEN_CV_BINDING_REQUIRED" if original.get("official_split") is None else "PRESERVED"})
    return list(unique.values()), members, unresolved


def projected_rows(path, desired, required):
    import pyarrow.parquet as pq
    source = pq.ParquetFile(path)
    try:
        names = set(source.schema_arrow.names)
        if not set(required) <= names:
            raise ValueError("Existing source lacks required structure metadata columns: " + str(path))
        columns = [name for name in desired if name in names]
        for batch in source.iter_batches(batch_size=512, columns=columns, use_threads=False):
            yield from batch.to_pylist()
    finally:
        source.close()


def run(config):
    node = platform.node()
    if (not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-")
            or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19):
        raise RuntimeError("Allocated CPU node 8-19 required")
    peer = Path(config["peer_root"]).resolve()
    definition = peer / "workflows/benchmark_data/task_selection.py"
    module_spec = importlib.util.spec_from_file_location("_d_existing_benchmark_scope", definition)
    selector = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(selector)
    policy = selector.load_deferred_policy(peer / "configs/benchmark_data/B1.deferred_tasks.json")
    tasks = frozen_tasks(read_json(config["frozen_roster_manifest"]), config["required_roster_status"],
        read_json(config["scope_proof"]), lambda tasks: selector.select_active_tasks(
            tasks, fingerprints=policy, verify_full_inventory=False))
    allowed = {selector.canonical_task_key(*task) for task in tasks}
    entry = read_json(config["b0_entry"])
    b0 = read_json(entry["manifest"])
    c1 = read_json(config["c1_manifest"])
    if c1["feature_names"][:20] != list(D20_NAMES):
        raise ValueError("Existing C1 D20 order/definition does not match original D20")
    scope = read_json(config["geometry_scope_manifest"])
    accesses = {queue: read_json(path) for queue, path in config["geometry_access_manifests"].items()}
    sealed_queue = sealed_geometry(scope, accesses)
    groups = {dataset for dataset, _ in tasks}
    def structures():
        desired = ["record_id", "source_file", "model_smiles", "original_smiles", "official_split",
                   "retained", "domain_eligible", "blind_fallback_required", "model_atom_to_source",
                   "shared_molecule_id"]
        for group in sorted(groups):
            source = b0["source_groups"][group]
            paths = [source["records"]] if source.get("records") else list(source["records_by_nucleus"].values())
            if not paths:
                raise ValueError("Frozen source group has no existing structure store: " + group)
            for path in paths:
                for row in projected_rows(path, desired, ["record_id", "source_file"]):
                    yield dict(row, dataset=group, structure_store=path)
    def features():
        desired = ["dataset", "record_id", "model_smiles", "native_shared_molecule_id", "features", "valid_mask"]
        for source in c1["source_groups"]:
            if source["dataset"] in groups:
                yield from projected_rows(source["features"], desired, desired)
    refs = {key: reference(config[key]) for key in ("frozen_roster_manifest", "scope_proof", "b0_entry",
            "c1_manifest", "geometry_scope_manifest")}
    refs["B0_source_manifest"] = reference(entry["manifest"])
    refs["geometry_access"] = {queue: reference(path) for queue, path in config["geometry_access_manifests"].items()}
    sources = {"sealed_queue": sealed_queue, "C1": config["c1_manifest"],
               "geometry_scope": config["geometry_scope_manifest"], "roster": config["frozen_roster_manifest"]}
    output = Path(config["output"]).resolve()
    guard(output.parent, config); output.mkdir(parents=True, exist_ok=True)
    final = output / "manifest.json"
    if final.exists():
        previous = read_json(final)
        if previous["source_references"] != refs:
            raise ValueError("Closed benchmark source references changed")
        return previous
    inputs, members, unresolved = build_rows(structures(), features(), allowed_keys=allowed,
        canonical_key=selector.canonical_task_key, graph_equivalent=unchanged_remove_hs, sources=sources)
    if not inputs:
        raise ValueError("No original members map to the explicit final frozen source roster")
    input_path, mapping = output / "input_rows.jsonl", output / "member_map.jsonl"
    write_jsonl(input_path, inputs, config); write_jsonl(mapping, members, config)
    membership = {"path": str(mapping), "format": "jsonl", "dataset_key": "dataset", "member_key": "record_id",
                  "molecule_key": "molecule_id", "source_split_key": "source_split"}
    status = "SOURCE_READY" if not unresolved else "UNRESOLVED_CANONICAL_D20_OR_FROZEN_SPLIT_BINDING"
    export_inputs = {"input_rows": str(input_path), "membership_reference": membership,
                     "canonical_D20_source_status": status, "frozen_roster_manifest": config["frozen_roster_manifest"]}
    publish(output / "export_inputs.json", export_inputs, config)
    report = {"schema": "D_BENCHMARK_STRUCTURE_PREPARATION_V1", "status": status,
        "input_rows": str(input_path), "membership_reference": membership,
        "unique_molecules": len(inputs), "source_members": len(members), "unresolved": unresolved,
        "source_references": refs, "producer_ID_join_checked": True, "five_deferred_excluded": True,
        "new_scope_or_split_created": False, "benchmark_target_values_read": False,
        "D20_or_D3_calculated": False, "statistics_fitted": False,
        "reception_acceptance": "pending", "current_C1_complete": False,
        "job_id": os.environ["SLURM_JOB_ID"], "node": node}
    publish(final, report, config)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    run(read_json(args.config))


if __name__ == "__main__":
    main()
