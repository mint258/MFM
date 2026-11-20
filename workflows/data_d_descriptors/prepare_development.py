"""Prepare the exact seven-task P development cohort without opening targets.

Required config: store, recipe_root, source_members, b6_manifest, output,
peak_bytes; optional l1_fields or train_manifest select compatible cache names.
Without either, the original closed B6 descriptor names are used only to reuse
canonical D20, never to declare new L1 fields/normalization frozen. A failed
canonical-D20 binding is reported UNRESOLVED, never silently delivered as NA.
"""
import argparse
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

from .export import D20_NAMES, publish
from .produce import guard, read_json, reference


def development_datasets(protocol, panel):
    scored = protocol["scored_tasks"]
    if len(scored) != 7 or len(set(scored)) != 7:
        raise ValueError("The frozen seven-task development protocol is required")
    by_task = {task["task_id"]: task["dataset_id"] for task in panel["tasks"]}
    datasets = list(dict.fromkeys(by_task[task] for task in scored))
    if set(datasets) != {"expansionrx", "qm9"}:
        raise ValueError("Only the registered ExpansionRx/QM9 development datasets are allowed")
    return datasets


def selected_metadata(store, views):
    """Only membership and geometry metadata; store.get/view.get are forbidden."""
    selected, excluded = [], []
    for dataset, view in views.items():
        for role, members in view.membership["roles"].items():
            for member in members:
                metadata = store.native_geometry_metadata(dataset, member["member_index"])
                if metadata["member_uid"] != member["member_uid"]:
                    raise ValueError("Native geometry metadata does not match the frozen member UID")
                row = {"dataset": dataset, "member_uid": member["member_uid"],
                       "member_index": member["member_index"], "source_split": role,
                       "molecule_id": member["full_inchikey"], "native_n_atoms": metadata["native_n_atoms"]}
                if metadata["geometry_ready"]:
                    selected.append(row)
                else:
                    excluded.append(dict(row, reason="P_NATIVE_GEOMETRY_NOT_READY"))
    return selected, excluded


def original_frames(path, requested):
    from workflows.data_v1_final.downstream_descriptors_v2.run import selected_members
    wanted = {(row["dataset"], row["member_uid"]) for row in requested}
    frames = {}
    for ordinal, row in selected_members(path):
        key = (row["dataset"], row["member_uid"])
        if key not in wanted:
            continue
        if key in frames:
            raise ValueError("Original source UID has multiple source frames; explicit binding needed")
        frames[key] = dict(row, source_ordinal=ordinal)
    if set(frames) != wanted:
        raise ValueError("Selected native member lacks its existing original structure source frame")
    return frames


def source_smiles(frame):
    from workflows.data_v1_final.downstream_descriptors_v2.worker import read_xyz, scalar_smiles_from_span
    from rdkit import Chem
    original = frame["source_frame"]
    if frame["dataset"] == "expansionrx":
        value = scalar_smiles_from_span(original)
    elif frame["dataset"] == "qm9":
        # The original reader skips the target-bearing comment/frequency lines.
        _, _, value = read_xyz(original["path"], original["source_units"])
    else:
        raise ValueError("Unregistered development structure adapter")
    if not isinstance(value, str) or not value or Chem.MolFromSmiles(value) is None:
        return None
    return value


def build_rows(selected, frames, *, smiles_reader, cache, store_reference):
    """Deterministic representative graph per existing full InChIKey.

    Every original member keeps its individual D3 source reference. Duplicate
    molecules share only their 2D row, never their member geometry or split.
    """
    molecules, membership, seen_members, unresolved = {}, [], set(), []
    for member in selected:
        key = (member["dataset"], member["member_uid"])
        if key in seen_members:
            raise ValueError("Duplicate original development member identity")
        seen_members.add(key)
        frame = frames[key]
        mid = member["molecule_id"]
        geometry = {"store": store_reference, "dataset": member["dataset"],
                    "member_index": member["member_index"], "member_uid": member["member_uid"],
                    "native_n_atoms": member["native_n_atoms"], "source_frame": copy.deepcopy(frame["source_frame"]),
                    "geometry_artifact_ref": copy.deepcopy(frame.get("geometry_artifact_ref"))}
        membership.append(dict(member, D3_geometry_reference=geometry))
        if mid in molecules:
            continue
        # IO/import failures intentionally propagate. A literal missing graph
        # remains an existing molecule row with an explicit source_error.
        smiles = smiles_reader(frame)
        error = None if smiles else "ORIGINAL_SOURCE_SMILES_UNAVAILABLE"
        values = cache.get(member["member_uid"], smiles, frame["source_ordinal"]) if smiles else None
        bound = values is not None and set(D20_NAMES) <= set(values)
        d20 = {name: values[name] if bound else None for name in D20_NAMES}
        state = "BOUND_COMPATIBLE_B6_NATIVE_VALUES" if bound else "UNRESOLVED_CANONICAL_D20_SOURCE"
        reason = None if bound else (error or "NO_COMPATIBLE_B6_D20_BINDING")
        row = {"molecule_id": mid, "smiles": smiles, "source_error": error,
               "source_member_uid": member["member_uid"], "source_ordinal": frame["source_ordinal"],
               "source_binding": {"dataset": member["dataset"], "member_uid": member["member_uid"],
                   "source_ordinal": frame["source_ordinal"], "source_frame": copy.deepcopy(frame["source_frame"])},
               "existing_D20": d20, "canonical_D20_binding_state": state,
               "canonical_D20_source_error": reason,
               "canonical_D20_all_missing": all(value is None for value in d20.values())}
        molecules[mid] = row
        if not bound:
            unresolved.append({"molecule_id": mid, "member_uid": member["member_uid"], "reason": reason})
    return list(molecules.values()), membership, unresolved


def write_jsonl(path, data, config):
    guard(Path(path).parent, config)
    pending = Path(str(path) + ".partial")
    with pending.open("w", encoding="utf-8") as stream:
        for index, row in enumerate(data):
            if index % 256 == 0:
                guard(Path(path).parent, config)
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


def run(config):
    node = platform.node()
    if (not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-")
            or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19):
        raise RuntimeError("Development structure preparation requires allocated CPU node 8-19")
    recipe = Path(config["recipe_root"]).resolve()
    sys.path.insert(0, str(recipe / "current"))
    from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
    from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
    from .b6_cache import B6L1Cache
    output = Path(config["output"]).resolve()
    guard(output.parent, config); output.mkdir(parents=True, exist_ok=True)
    refs = {"store": reference(config["store"]), "source_members": reference(config["source_members"]),
            "protocol": reference(recipe / "configs/p_recipe/protocol.json"),
            "panel": reference(recipe / "configs/dev_panel_v3.json"),
            "B6": reference(config["b6_manifest"])}
    if config.get("train_manifest"):
        fields_path = config["train_manifest"]
        fields = read_json(fields_path)["libraries"]["L1"]["ordered_fields"]
    elif config.get("l1_fields"):
        fields_path = config["l1_fields"]
        fields = read_json(fields_path)["ordered_names"]
    else:
        fields_path = config["b6_manifest"]
        fields = read_json(fields_path)["rdkit_descriptor_names"]
    refs["L1_fields"] = reference(fields_path)
    final = output / "manifest.json"
    if final.exists():
        previous = read_json(final)
        if previous["source_references"] != refs:
            raise ValueError("Closed development source references changed")
        return previous
    datasets = development_datasets(read_json(refs["protocol"]["path"]), read_json(refs["panel"]["path"]))
    store = TrainOnlyPackedStore(config["store"], verify_digests=False)
    views = {dataset: GroupedTrainingView(store, dataset, "official" if dataset == "expansionrx" else "0",
                                         store.group_map) for dataset in datasets}
    selected, excluded = selected_metadata(store, views)
    frames = original_frames(config["source_members"], selected)
    cache = B6L1Cache(config["b6_manifest"], fields=fields,
        rdkit_version=importlib.metadata.version("rdkit"), member_uids={row["member_uid"] for row in selected})
    inputs, members, unresolved = build_rows(selected, frames, smiles_reader=source_smiles,
                                             cache=cache, store_reference=config["store"])
    input_path, member_path = output / "input_rows.jsonl", output / "member_map.jsonl"
    write_jsonl(input_path, inputs, config)
    write_jsonl(member_path, members, config)
    write_jsonl(output / "geometry_exclusions.jsonl", excluded, config)
    reference_map = {"path": str(member_path), "format": "jsonl", "dataset_key": "dataset",
                     "member_key": "member_uid", "molecule_key": "molecule_id", "source_split_key": "source_split"}
    all_missing_bound = sum(row["canonical_D20_all_missing"] and
        row["canonical_D20_binding_state"] == "BOUND_COMPATIBLE_B6_NATIVE_VALUES" for row in inputs)
    status = ("UNRESOLVED_CANONICAL_D20_BINDINGS" if unresolved else
              "CANONICAL_D20_ALL_MISSING_REVIEW_REQUIRED" if all_missing_bound else "SOURCE_READY")
    export_inputs = {"input_rows": str(input_path), "membership_reference": reference_map,
                     "b6_manifest": config["b6_manifest"], "canonical_D20_source_status": status}
    if config.get("train_manifest"):
        export_inputs["train_manifest"] = config["train_manifest"]
    publish(output / "export_inputs.json", export_inputs, config)
    report = {"schema": "D_DEVELOPMENT_STRUCTURE_PREPARATION_V1", "status": status,
        "input_rows": str(input_path), "membership_reference": reference_map,
        "unique_molecules": len(inputs), "retained_members": len(members),
        "geometry_excluded_members": len(excluded), "geometry_exclusions": str(output / "geometry_exclusions.jsonl"),
        "canonical_D20_unresolved": unresolved,
        "bound_D20_all_missing_molecules": all_missing_bound,
        "export_inputs": str(output / "export_inputs.json"),
        "producer_ID_join_checked": True, "target_values_read": False, "source_references": refs,
        "original_membership_and_caps_reused": True, "B6_cache": cache.provenance(),
        "job_id": os.environ["SLURM_JOB_ID"], "node": node,
        "statistics_fitted": False, "reception_acceptance": "pending", "current_C1_complete": False}
    publish(final, report, config)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    run(read_json(args.config))


if __name__ == "__main__":
    main()
