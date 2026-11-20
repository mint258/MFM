"""Join closed native D3 dataset components in the original member order.

Config: source_manifest, components (closed manifest paths), output, peak_bytes.
No array values, source geometries, targets or descriptor calculators are read.
The shared 512 MiB development allowance includes referenced component outputs.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import platform

from .development_d3 import D3_NAMES, OWN_LIMIT, POLICIES, SCHEMA
from .prepare_development import write_jsonl
from .produce import guard, publish, read_json, reference, require_cpu, rows

MERGED_SCHEMA = "D_DEVELOPMENT_NATIVE_D3_MERGED_V1"


def merge_members(original, components):
    """components contains (manifest_path, closed_metadata, member_rows)."""
    expected, joined, policies = {}, {}, {}
    for index, member in enumerate(original):
        key = (member["dataset"], member["member_uid"])
        if key in expected or member["dataset"] not in ("qm9", "expansionrx"):
            raise ValueError("Duplicate or unregistered original development member")
        expected[key] = (index, member)
    source_count = len(original)
    for path, component, records in components:
        if (component.get("schema") != SCHEMA or component.get("status") != "RAW_COMPLETE"
                or component.get("ordered_fields") != list(D3_NAMES)
                or component.get("source_member_count") != source_count):
            raise ValueError("Closed scoped native D3 component required")
        scope, chosen = component["dataset_scope"], component["hydrogen_policy"]
        if (not scope or len(scope) != len(set(scope)) or chosen not in POLICIES
                or not set(scope) <= {m["dataset"] for m in original}
                or component["identity"]["dataset_scope"] != scope
                or component["identity"]["source_member_count"] != source_count
                or component["identity"]["member_count"] != component["member_count"]):
            raise ValueError("Component scope/policy is not an original complete dataset")
        for dataset in scope:
            if dataset in policies:
                raise ValueError("Overlapping native D3 component dataset scopes")
            policies[dataset] = chosen
        seen = set()
        for record in records:
            key = (record["dataset"], record["member_uid"])
            if key not in expected or key in joined or record["dataset"] not in scope:
                raise ValueError("Unknown or overlapping original native D3 member")
            index, member = expected[key]
            if (any(record[name] != member[name] for name in ("member_index", "molecule_id", "source_split"))
                    or record["D3_geometry_reference"] != member["D3_geometry_reference"]
                    or record["hydrogen_policy"] != chosen
                    or record.get("source_member_row", index) != index):
                raise ValueError("Component changed original member/split/geometry binding")
            if (record["D3_ordered_fields"] != list(D3_NAMES)
                    or set(record["D3_raw"]) != set(D3_NAMES) or set(record["D3_status"]) != set(D3_NAMES)):
                raise ValueError("Component molecular D3 field schema differs")
            # Preserve the raw/status payload and physical/atomic references.
            # The row index becomes global; local array part_row stays exact.
            output = copy.deepcopy(record)
            output.update(component_manifest=str(path), component_member_row=record["member_row"],
                          member_row=index, source_member_row=index)
            joined[key] = output
            seen.add(key)
        scoped_expected = {key for key in expected if key[0] in scope}
        if len(seen) != component["member_count"] or seen != scoped_expected:
            raise ValueError("Incomplete component for its complete dataset scope")
    if set(joined) != set(expected):
        raise ValueError("Incomplete native D3 delivery: every original member needs one closed component")
    return [joined[key] for key in expected], policies


def run(config):
    require_cpu(dict(config, workers=1, chunk_rows=256))
    allowance = config.get("output_budget_bytes", OWN_LIMIT)
    if type(allowance) is not int or not 0 < allowance <= OWN_LIMIT:
        raise ValueError("EXISTING_DEVELOPMENT_ALLOWANCE_AT_MOST_512_MIB_REQUIRED")
    source_path = config["source_manifest"]
    source, source_ref = read_json(source_path), reference(source_path)
    if source.get("status") != "SOURCE_READY":
        raise ValueError("Closed original development source required")
    identity = {"source_manifest": source_ref,
        "components": [reference(path) for path in config["components"]]}
    output, final = Path(config["output"]).resolve(), Path(config["output"]).resolve() / "manifest.json"
    if final.exists():
        previous = read_json(final)
        if previous["identity"] != identity:
            raise ValueError("Closed merged native D3 references changed")
        return previous
    original = list(rows(source["membership_reference"]["path"]))
    if len(original) != source["retained_members"]:
        raise ValueError("Original member count differs from source manifest")
    components = []
    for path in config["components"]:
        document = read_json(path)
        if document.get("identity", {}).get("source_manifest") != source_ref:
            raise ValueError("Native D3 components reference different original sources")
        components.append((path, document, rows(document["membership_reference"]["path"])))
    merged, policies = merge_members(original, components)
    metadata_bytes = sum(len(json.dumps(row, ensure_ascii=False, allow_nan=False).encode("utf-8")) + 1 for row in merged)
    component_bytes = sum(part["bytes"] + part["member_bytes"] for _, doc, _ in components for part in doc["parts"])
    peak = component_bytes + 2 * metadata_bytes + (len(components) + 1) * 2**21
    if peak > allowance:
        raise ValueError("MERGED_D3_OUTPUT_EXCEEDS_EXISTING_SHARED_DEVELOPMENT_ALLOWANCE")
    guard(output.parent, config); output.mkdir(parents=True, exist_ok=True)
    mapping = output / "member_map.jsonl"
    write_jsonl(mapping, merged, config)
    report = {"schema": MERGED_SCHEMA, "status": "RAW_COMPLETE", "identity": identity,
        "dataset_scope": sorted(policies), "source_member_count": len(original), "member_count": len(merged),
        "complete_source_population": True, "hydrogen_policy_by_dataset": policies,
        "ordered_fields": list(D3_NAMES), "membership_reference": dict(source["membership_reference"], path=str(mapping)),
        "components": config["components"], "component_and_merge_peak_bytes": peak,
        "descriptor_calculations": False, "numeric_arrays_read": False, "target_values_read": False,
        "normalization_fitted": False, "atomic_SASA_in_molecular_vector": False,
        "reception_acceptance": "pending", "current_C1_complete": False,
        "job_id": os.environ["SLURM_JOB_ID"], "node": platform.node()}
    publish(final, report, config)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    run(read_json(parser.parse_args().config))


if __name__ == "__main__":
    main()
