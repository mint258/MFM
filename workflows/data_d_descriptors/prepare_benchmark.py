"""Target-free benchmark preparation from existing scope and sealed B0 D.

FEATURE_EXPORT_ONLY accepts active_inventory_manifest/required_inventory_status;
FINAL_ROSTER retains frozen_roster_manifest/required_roster_status. Required:
peer_root,b0_entry,scope_proof,geometry_scope_manifest,geometry_access_manifests,
output,peak_bytes. Neither mode creates endpoints/splits or final C1 results.
"""
import argparse
import copy
import csv
import importlib.util
import math
import os
from pathlib import Path
import platform
import sys
import types

from .b6_cache import unchanged_remove_hs
from .export import D20_NAMES, publish
from .prepare_development import write_jsonl
from .produce import guard, read_json, reference

D3_NAMES = ("PMI1", "PMI2", "PMI3", "PBF", "volume_A3", "SASA_total_A2")
NATIVE_D20_STATES = frozenset(("SPRIME_AND_D_READY", "SPRIME_READY_D_PARTIAL",
    "D20_READY_STEREO_REFERENCE_UNAVAILABLE", "D20_READY_UFF_UNSUPPORTED",
    "D20_READY_NO_ACCEPTED_CONFORMERS", "D20_READY_GEOMETRY_FAILED"))


def native_missing_reason(shared):
    """Only actual producer terminal evidence classifies a native missing value."""
    result = (shared or {}).get("result")
    if result is None or result.get("state") != shared.get("state"):
        return None
    state, d20 = result.get("state"), result.get("D20")
    if (state == "SOURCE_OR_IMPLEMENTATION_FAILED"
            and result.get("error") == "ValueError('SOURCE_MODEL_GRAPH_UNAVAILABLE')" and d20 is None):
        return "SOURCE_MODEL_GRAPH_UNAVAILABLE"
    if state in NATIVE_D20_STATES and d20 is not None and not any(d20.get("valid_mask", [])):
        return "NATIVE_D20_ALL_FIELDS_MASKED"
    return None


def _scope_evidence(document, required_status, proof):
    if (proof.get("deferred_registry_full_inventory_verified") is not True
            or proof.get("deferred_endpoint_count") != 5):
        raise ValueError("Existing five-deferred full-inventory scope proof required")
    if not required_status or document.get("status") != required_status:
        raise ValueError("Explicit existing source inventory/roster status required")


def catalog_groups(document, required_status, proof, catalog_rows):
    """Candidate endpoint IDs need not contain an original source filename."""
    _scope_evidence(document, required_status, proof)
    groups = {row["dataset"] for row in catalog_rows}
    if not groups or any(not group for group in groups):
        raise ValueError("Existing catalog source groups are missing")
    return groups


def active_source_rows(rows, groups, selector):
    """Use the original selector on actual source files, once per source task."""
    decisions = {}
    for row in rows:
        task = (row["dataset"], row["source_file"])
        if task[0] not in groups:
            continue
        if task not in decisions:
            decisions[task] = bool(selector([task]))
        if decisions[task]:
            yield row


def structure_sources(entry, b0, read_manifest):
    """Use author-approved active structure tables instead of historical ones."""
    groups = copy.deepcopy(b0["source_groups"])
    references = {}
    for group, filename in entry.get("active_target_manifests", {}).items():
        active = read_manifest(filename)
        references["active_" + group] = filename
        if active.get("records"):
            groups[group] = dict(records=active["records"])
        elif active.get("source_domain_manifest"):
            domain = read_manifest(active["source_domain_manifest"])
            references["active_domain_" + group] = active["source_domain_manifest"]
            if domain.get("records"):
                groups[group] = dict(records=domain["records"])
    return groups, references


def scoped_tasks(document, required_status, proof, selector, *, mode="FINAL_ROSTER"):
    _scope_evidence(document, required_status, proof)
    if mode == "FINAL_ROSTER":
        if document.get("final_task_roster") is not True:
            raise ValueError("Existing final frozen benchmark roster required")
        tasks = [(row["dataset"], row["source_task"]) for row in document["tasks"]]
    elif mode == "FEATURE_EXPORT_ONLY":
        tasks = [(row["dataset"], row["source_task"]) for row in document["tasks"]]
    else:
        raise ValueError("Unknown benchmark preparation mode")
    tasks = list(dict.fromkeys(tasks))
    selected = selector(tasks)
    if not selected or (mode == "FINAL_ROSTER" and selected != tasks):
        raise ValueError("Empty active scope or frozen roster includes deferred tasks")
    return selected


def frozen_tasks(roster, required_status, proof, selector):
    return scoped_tasks(roster, required_status, proof, selector)


def sealed_geometry(scope, access_documents):
    queues = {scope["queue"], scope.get("reused_source_queue", scope["queue"])}
    for queue in queues:
        access = access_documents.get(queue)
        if (not access or access.get("immutable") is not True
                or access.get("cross_node_read_allowed") is not True):
            raise ValueError("Declared shared S-prime UFF source is not sealed: " + queue)
    return queues


class D20Schema:
    """Check the original field definition once per sealed source queue."""
    def __init__(self):
        self.checked = set()

    def validate(self, queue, d20):
        if queue not in self.checked:
            if d20.get("names") != list(D20_NAMES):
                raise ValueError("Sealed B0 D20 name/order differs from original D20")
            self.checked.add(queue)
        if len(d20.get("values", [])) != 20 or len(d20.get("valid_mask", [])) != 20:
            raise ValueError("Sealed B0 D20 values/mask shape differs from original D20")


def canonical_d20(shared, smiles, graph_equivalent, schema):
    missing = dict.fromkeys(D20_NAMES)
    result = (shared or {}).get("result") or {}
    d20 = result.get("D20")
    if d20 is None:
        if (native_missing_reason(shared) == "SOURCE_MODEL_GRAPH_UNAVAILABLE"
                and result.get("model_smiles") == smiles):
            return missing, None
        return missing, "CANONICAL_SHARED_B0_D20_SOURCE_UNAVAILABLE"
    schema.validate(shared["source_database"], d20)
    if result.get("model_smiles") != smiles or not graph_equivalent(smiles):
        return missing, "B0_D20_INPUT_POLICY_NOT_EQUIVALENT_TO_ORIGINAL_D20"
    values = {}
    for name, value, valid in zip(D20_NAMES, d20["values"], d20["valid_mask"]):
        if valid and (value is None or not math.isfinite(value)):
            return missing, "EXISTING_B0_OBSERVED_D20_VALUE_NONFINITE"
        values[name] = float(value) if valid else None
    error = ("EXISTING_B0_D20_ALL_MISSING_UNCLASSIFIED_NATIVE_STATE"
             if all(v is None for v in values.values()) and native_missing_reason(shared) is None else None)
    return values, error


def geometry_member(shared, route, scope_reference):
    result = (shared or {}).get("result") or {}
    conformers = result.get("conformers") or []
    first = conformers[0] if conformers else None
    source = dict(route, source_geometry_scope=scope_reference,
                  required_geometry_source="Sprime_UFF", state="MISSING_ACCEPTED_UFF_CONFORMER",
                  native_state=(shared or {}).get("state"), native_error=result.get("error"))
    raw, status = dict.fromkeys(D3_NAMES), dict.fromkeys(D3_NAMES, 0)
    if first is not None:
        if first.get("geometry_source") != "UFF_Sprime" or first.get("conformer_id") is None:
            raise ValueError("Shared B0 conformer lacks actual accepted UFF source identity")
        source.update(state="EXISTING_FIRST_ACCEPTED_UFF_CONFORMER",
            conformer_id=first["conformer_id"], candidate_id=first.get("candidate_id"),
            D3_issues=copy.deepcopy(first.get("D3_issues")),
            model_atom_to_source=copy.deepcopy(shared["model_atom_to_source"]),
            atom_reference={"result_field": "atomic_numbers", "conformer_field": "coordinates_A",
                            "SASA_atom_field": "D3.SASA_atom_A2"})
        for name in D3_NAMES:
            value = (first.get("D3") or {}).get(name)
            if value is not None:
                status[name] = 1 if math.isfinite(value) else 2
                raw[name] = float(value) if status[name] == 1 else None
    return {"D3_geometry_reference": source, "D3_ordered_fields": list(D3_NAMES),
            "D3_raw": raw, "D3_status": status}


def build_rows(structures, read_shared, *, allowed_keys, canonical_key, graph_equivalent, sources):
    unique, members, unresolved, member_keys, schema = {}, [], [], set(), D20Schema()
    for original in structures:
        dataset, record_id = original["dataset"], original["record_id"]
        if allowed_keys is not None and canonical_key(dataset, original["source_file"]) not in allowed_keys:
            continue
        key = (dataset, record_id)
        if key in member_keys:
            raise ValueError("Duplicate original benchmark dataset/record_id")
        member_keys.add(key)
        geometry_dataset = original.get("geometry_dataset") or dataset
        geometry_record = original.get("geometry_record_id") or record_id
        shared, route = read_shared(geometry_dataset, geometry_record)
        mid = (shared or {}).get("shared_molecule_id") or original.get("shared_molecule_id") or record_id
        if not isinstance(mid, str) or not mid:
            raise ValueError("Existing shared molecule ID or original record ID required")
        smiles = original.get("model_smiles") or original.get("original_smiles")
        binding = {"dataset": dataset, "record_id": record_id, "source_file": original["source_file"],
                   "source_dataset": original.get("source_dataset") or dataset,
                   "structure_store": original["structure_store"], "shared_geometry_route": route}
        values, error = canonical_d20(shared, smiles, graph_equivalent, schema)
        domain_missing = shared is None and (original.get("domain_eligible") is False or original.get("retained") is False)
        if domain_missing:
            # The original C1 producer uses this exact missing state when no
            # domain-eligible native UFF task was issued. Preserve the source
            # row and missing fields; never recompute or zero-fill its old D.
            values, error = dict.fromkeys(D20_NAMES), None
        result = (shared or {}).get("result") or {}
        native = {"state": (shared or {}).get("state"), "error": result.get("error"),
                  "D20_issues": (result.get("D20") or {}).get("issues"),
                  "known_missing_reason": native_missing_reason(shared)}
        if domain_missing:
            native["known_missing_reason"] = "NO_DOMAIN_ELIGIBLE_NATIVE_UFF_BINDING"
        graph_missing = native["known_missing_reason"] == "SOURCE_MODEL_GRAPH_UNAVAILABLE" and error is None
        input_smiles = None if graph_missing or domain_missing else smiles
        if graph_missing or domain_missing:
            binding["source_model_smiles"] = smiles
        if mid in unique and unique[mid]["smiles"] != input_smiles:
            raise ValueError("Existing molecule ID is not globally graph-unique")
        if mid not in unique:
            unique[mid] = {"molecule_id": mid, "smiles": input_smiles,
                "source_error": "NO_DOMAIN_ELIGIBLE_NATIVE_UFF_BINDING" if domain_missing else
                    "SOURCE_MODEL_GRAPH_UNAVAILABLE" if graph_missing else
                    None if smiles else "ORIGINAL_SOURCE_GRAPH_UNAVAILABLE",
                "source_binding": binding, "existing_D20": values, "canonical_D20_source_error": error,
                "native_source": native}
        elif error is None and unique[mid]["canonical_D20_source_error"] is not None:
            unique[mid].update(source_binding=binding, existing_D20=values, canonical_D20_source_error=None, native_source=native)
        member = {name: original.get(name) for name in ("dataset", "record_id", "source_file", "retained",
                  "domain_eligible", "blind_fallback_required", "existing_cv_reference")}
        member["original_atom_reference"] = {"structure_store": original["structure_store"],
            "model_atom_to_source": copy.deepcopy(original.get("model_atom_to_source")),
            "source_atom_ids": copy.deepcopy(original.get("source_atom_ids")),
            "original_molecule_id": original.get("original_molecule_id"),
            "source_frame_index": original.get("source_frame_index"),
            "source_dataset": original.get("source_dataset") or dataset}
        member.update(molecule_id=mid, source_split=original.get("official_split"), native_source=native,
            evaluation_status="EXISTING_SPLIT_REFERENCE_PRESERVED" if original.get("official_split") is not None
                or original.get("existing_cv_reference") else "EVALUATION_PENDING",
            source_inventory=sources["inventory"], **geometry_member(shared, route, sources["geometry_scope"]))
        members.append(member)
        if error is not None:
            unresolved.append({"dataset": dataset, "record_id": record_id, "canonical_D20_error": error})
    return list(unique.values()), members, unresolved


def projected_rows(path, desired, required):
    import pyarrow.parquet as pq
    source = pq.ParquetFile(path)
    try:
        names = set(source.schema_arrow.names)
        if not set(required) <= names:
            raise ValueError("Existing source lacks required structure metadata columns: " + str(path))
        for batch in source.iter_batches(batch_size=512, columns=[n for n in desired if n in names], use_threads=False):
            yield from batch.to_pylist()
    finally:
        source.close()


def _peer_module(peer, name):
    package = "_d_existing_benchmark_data"
    if package not in sys.modules:
        namespace = types.ModuleType(package)
        namespace.__path__ = [str(peer / "workflows/benchmark_data")]
        sys.modules[package] = namespace
    spec = importlib.util.spec_from_file_location(package + "." + name,
                                                peer / ("workflows/benchmark_data/" + name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shared_source(dataset, record_id, *, bindings, scope, readers, reader_class):
    route = bindings.get((dataset, record_id), {"shared_geometry_queue": scope.get("reused_source_queue", scope["queue"]),
                "shared_geometry_dataset": dataset, "shared_geometry_record_id": record_id})
    queue = route["shared_geometry_queue"]
    if queue not in readers:
        readers[queue] = reader_class(queue)
    try:
        return readers[queue].get(route["shared_geometry_dataset"], route["shared_geometry_record_id"]), route
    except KeyError as exc:
        if exc.args != ((route["shared_geometry_dataset"], route["shared_geometry_record_id"]),):
            raise
        return None, route


def run(config):
    node = platform.node()
    if (not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-")
            or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19):
        raise RuntimeError("Allocated CPU node 8-19 required")
    output = Path(config["output"]).resolve()
    guard(output.parent, config)
    peer = Path(config["peer_root"]).resolve()
    selector = _peer_module(peer, "task_selection")
    policy = selector.load_deferred_policy(peer / "configs/benchmark_data/B1.deferred_tasks.json")
    mode = config.get("mode", "FINAL_ROSTER")
    inventory_path = config["active_inventory_manifest" if mode == "FEATURE_EXPORT_ONLY" else "frozen_roster_manifest"]
    inventory = read_json(inventory_path)
    catalog = None
    if mode == "FEATURE_EXPORT_ONLY" and inventory.get("catalog"):
        with open(inventory["catalog"], newline="", encoding="utf-8") as handle:
            catalog = [{"dataset": row["dataset"], "endpoint_key": row["endpoint_key"]} for row in csv.DictReader(handle)]
    select = lambda tasks: selector.select_active_tasks(tasks, fingerprints=policy, verify_full_inventory=False)
    proof = read_json(config["scope_proof"])
    if mode == "FEATURE_EXPORT_ONLY" and catalog is not None:
        groups = catalog_groups(inventory, config.get("required_inventory_status"), proof, catalog)
        allowed = None  # The source-row generator below applies the original selector.
    else:
        tasks = scoped_tasks(inventory, config.get("required_inventory_status" if mode == "FEATURE_EXPORT_ONLY"
            else "required_roster_status"), proof, select, mode=mode)
        allowed, groups = {selector.canonical_task_key(*task) for task in tasks}, {d for d, _ in tasks}
    entry = read_json(config["b0_entry"])
    b0, scope = read_json(entry["manifest"]), read_json(config["geometry_scope_manifest"])
    source_groups, active_references = structure_sources(entry, b0, read_json)
    for group, namespace in config.get("geometry_namespaces", {}).items():
        if namespace not in scope.get("source_groups", {}):
            raise ValueError("Geometry namespace is absent from the declared uniform scope: " + group)
    queues = sealed_geometry(scope, {q: read_json(p) for q, p in config["geometry_access_manifests"].items()})
    route_fields = ["dataset", "record_id", "shared_geometry_queue", "shared_geometry_dataset", "shared_geometry_record_id"]
    bindings = {}
    for row in projected_rows(scope["geometry_bindings"], route_fields, route_fields):
        key = (row["dataset"], row["record_id"])
        if key in bindings or row["shared_geometry_queue"] not in queues:
            raise ValueError("Duplicate or unsealed original geometry binding")
        bindings[key] = row
    refs = {key: reference(config[key]) for key in ("scope_proof", "b0_entry", "geometry_scope_manifest")}
    refs.update(source_inventory=reference(inventory_path), B0_source_manifest=reference(entry["manifest"]),
                geometry_bindings=reference(scope["geometry_bindings"]),
                geometry_access={q: reference(p) for q, p in config["geometry_access_manifests"].items()})
    refs.update({key: reference(path) for key, path in active_references.items()})
    if catalog is not None:
        refs["catalog"] = reference(inventory["catalog"])
    final = output / "manifest.json"
    if final.exists():
        previous = read_json(final)
        if previous["source_references"] != refs or previous["mode"] != mode:
            raise ValueError("Closed benchmark source references/mode changed")
        return previous
    reader_class, readers = _peer_module(peer, "shared_reader").SharedB0Reader, {}
    def read_shared(dataset, record_id):
        return shared_source(dataset, record_id, bindings=bindings, scope=scope, readers=readers, reader_class=reader_class)
    def structures():
        desired = ["dataset", "record_id", "source_file", "model_smiles", "original_smiles", "official_split", "retained", "model_atom_to_source",
                   "geometry_dataset", "geometry_record_id", "source_atom_ids", "original_molecule_id", "source_frame_index",
                   "domain_eligible", "blind_fallback_required", "shared_molecule_id", "existing_cv_reference"]
        for group in sorted(groups):
            source = source_groups[group]
            paths = [source["records"]] if source.get("records") else list(source["records_by_nucleus"].values())
            for path in paths:
                for row in projected_rows(path, desired, ["record_id", "source_file"]):
                    yield dict(row, source_dataset=row.get("dataset"), dataset=group, structure_store=path,
                        geometry_dataset=row.get("geometry_dataset") or config.get("geometry_namespaces", {}).get(group) or group,
                        geometry_record_id=row.get("geometry_record_id") or row["record_id"])
    try:
        original_rows = structures()
        if allowed is None:
            original_rows = active_source_rows(original_rows, groups, select)
        inputs, members, unresolved = build_rows(original_rows, read_shared, allowed_keys=allowed,
            canonical_key=selector.canonical_task_key, graph_equivalent=unchanged_remove_hs,
            sources={"inventory": inventory_path, "geometry_scope": config["geometry_scope_manifest"]})
    finally:
        for reader in readers.values():
            reader.close()
    if not inputs:
        raise ValueError("No original members map to the explicit existing active source scope")
    guard(output.parent, config); output.mkdir(parents=True, exist_ok=True)
    input_path, mapping = output / "input_rows.jsonl", output / "member_map.jsonl"
    write_jsonl(input_path, inputs, config); write_jsonl(mapping, members, config)
    membership = {"path": str(mapping), "format": "jsonl", "dataset_key": "dataset", "member_key": "record_id",
                  "molecule_key": "molecule_id", "source_split_key": "source_split"}
    status = "UNRESOLVED_CANONICAL_D20_BINDING" if unresolved else "SOURCE_READY"
    report = {"schema": "D_BENCHMARK_STRUCTURE_PREPARATION_V1", "status": status, "mode": mode,
        "input_rows": str(input_path), "membership_reference": membership, "unique_molecules": len(inputs),
        "source_members": len(members), "unresolved": unresolved, "source_references": refs,
        "final_roster_frozen": mode == "FINAL_ROSTER", "evaluation_status": "EVALUATION_PENDING",
        "producer_ID_join_checked": True, "five_deferred_excluded": True, "new_scope_or_split_created": False,
        "benchmark_target_values_read": False, "D20_or_D3_calculated": False, "statistics_fitted": False,
        "reception_acceptance": "pending", "current_C1_complete": False,
        "job_id": os.environ["SLURM_JOB_ID"], "node": node}
    publish(output / "export_inputs.json", {"input_rows": str(input_path), "membership_reference": membership,
        "canonical_D20_source_status": status, "source_inventory_manifest": inventory_path, "mode": mode}, config)
    publish(final, report, config)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    run(read_json(parser.parse_args().config))


if __name__ == "__main__":
    main()
