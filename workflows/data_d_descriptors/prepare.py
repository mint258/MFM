"""Prepare target-free, source-aligned D structures after the cost pilot closes."""
import argparse
import json
import os
from pathlib import Path
import platform
import sqlite3
import time

from .pilot import original_smiles, publish, storage_guard
from .existing import ExistingD20
from .full_plan import load_closed_costs


def combine_population(train_rows, full_rows, eligible_indices, common_val_ids,
                       diagnostic_val_ids, diagnostic_ids):
    """Preserve original TRAIN/VAL membership; diagnostics do not enter fitting."""
    result, mids, addresses = [], set(), set()
    for split, rows in (("TRAIN", train_rows), ("FULL", full_rows)):
        for item in sorted(rows, key=lambda row: row["molecule_index"]):
            mid, index = item["molecule_id"], int(item["molecule_index"])
            if split == "TRAIN":
                if index not in eligible_indices:
                    continue
                role = "TRAIN"
            elif mid in common_val_ids:
                role = "VAL"
            elif mid in diagnostic_val_ids:
                role = "VAL_DIAGNOSTIC"
            else:
                continue
            if mid in mids or (split, index) in addresses:
                raise ValueError("Source molecule ID/address or TRAIN/VAL membership overlaps")
            mids.add(mid)
            addresses.add((split, index))
            result.append({"molecule_id": mid, "molecule_index": index,
                "split": split, "role": role, "diagnostic": mid in diagnostic_ids})
    return result


def population(config):
    import numpy as np
    import pyarrow.parquet as pq
    corpus = json.loads(Path(config["corpus"]).read_text())
    compact = json.loads((Path(corpus["source_root"]) / "manifest.json").read_text())
    common = json.loads(Path(compact["full_source_dependencies"]["common"]).read_text())
    d5 = json.loads(Path(compact["full_source_dependencies"]["d5"]).read_text())
    diagnostic_ids = set(pq.read_table(d5["diagnostic_base_reference"]["path"],
        columns=["molecule_id"], use_threads=False)["molecule_id"].to_pylist())
    common_val, diagnostic_val = set(), set()
    for reference in common["membership_tables"]:
        table = pq.read_table(reference["path"], use_threads=False,
            columns=["molecule_id", "effective_role", "common_population_v1"])
        for row in table.to_pylist():
            if row["effective_role"] in ("VAL", "ROUTINE"):
                if row["common_population_v1"]:
                    common_val.add(row["molecule_id"])
                if row["molecule_id"] in diagnostic_ids:
                    diagnostic_val.add(row["molecule_id"])
    by_split = {}
    for split in ("TRAIN", "FULL"):
        by_split[split] = pq.read_table(Path(compact["split_roots"][split]) / "id_map.parquet",
            columns=["molecule_index", "molecule_id"], filters=[("record_kind", "=", "M")],
            use_threads=False).to_pylist()
    eligible = set(map(int, np.load(corpus["train_indices"])))
    rows = combine_population(by_split["TRAIN"], by_split["FULL"], eligible,
        common_val, diagnostic_val, diagnostic_ids)
    if sum(row["role"] == "TRAIN" for row in rows) != len(eligible):
        raise ValueError("Eligible TRAIN molecule IDs do not cover the frozen indices")
    represented = {row["molecule_id"] for row in rows}
    if (common_val | diagnostic_val) - represented:
        raise ValueError("Declared VAL/VAL-diagnostic molecule is not source-addressable")
    return rows, {"corpus": config["corpus"], "compact": str(Path(corpus["source_root"]) / "manifest.json"),
        "common": compact["full_source_dependencies"]["common"],
        "D5": compact["full_source_dependencies"]["d5"],
        "diagnostic_molecules_outside_requested_roles_or_excluded_cohort": sorted(diagnostic_ids - represented)}


def prepare(config):
    node = platform.node()
    if not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-") or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19:
        raise RuntimeError("Allocated CPU node 8-19 required")
    pilot = Path(config["pilot_root"])
    load_closed_costs(pilot)  # UNRESOLVED libraries do not block a closed peer.
    out = Path(config["output"])
    out.mkdir(parents=True, exist_ok=True)
    final_manifest = out / "manifest.json"
    if final_manifest.exists():
        print("Closed source structures reused: " + str(final_manifest), flush=True)
        return
    storage_guard(out, config["peak_bytes"])
    rows, references = population(config)
    panel = json.loads((pilot / "panel.json").read_text())
    cached = {row["molecule_id"]: row for row in panel["molecules"]}
    state_path, partial = out / "checkpoint.json", out / "structures.jsonl.partial"
    binding = {"config": config, "references": references, "rows": len(rows)}
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        "binding": binding, "closed_rows": 0, "byte_offset": 0, "elapsed_seconds": 0.0,
        "jobs": [], "source_missing": 0}
    if state["binding"] != binding:
        raise ValueError("Frozen source cohort or preparation configuration changed")
    if os.environ["SLURM_JOB_ID"] not in state["jobs"]:
        state["jobs"].append(os.environ["SLURM_JOB_ID"])
    previous, start = state["elapsed_seconds"], time.monotonic()
    database = sqlite3.connect("file:" + config["geometry_index"] + "?mode=ro", uri=True)
    pointers, lookup = None, None
    if config.get("source_smiles_index"):
        from .source_smiles import SourceSmiles
        pointers = {}
        for item in rows[state["closed_rows"]:]:
            if item["molecule_id"] in cached:
                continue
            source = database.execute("SELECT pointer FROM geometries WHERE mid=? AND src='pm7' LIMIT 1",
                (item["molecule_id"],)).fetchone()
            pointers[item["molecule_id"]] = None if source is None else json.loads(source[0])
        lookup = SourceSmiles.from_parquet(config["source_smiles_index"],
            (pointer for pointer in pointers.values() if pointer is not None)).get
    canonical = ExistingD20(json.loads(Path(config["corpus"]).read_text())["source_root"])
    with partial.open("r+b" if partial.exists() else "w+b") as stream:
        # Only uncommitted bytes from this task's own partial are discarded.
        stream.truncate(state["byte_offset"])
        stream.seek(state["byte_offset"])
        for offset in range(state["closed_rows"], len(rows), config.get("chunk_rows", 1024)):
            storage_guard(out, config["peak_bytes"])
            batch = rows[offset:offset + config.get("chunk_rows", 1024)]
            for item in batch:
                item = dict(item)
                saved = cached.get(item["molecule_id"])
                if saved is not None:
                    if item["split"] != "TRAIN" or item["molecule_index"] != saved["molecule_index"]:
                        raise ValueError("Pilot source ID does not align with production cohort")
                    item["smiles"] = saved["smiles"]
                    item["source_error"] = saved.get("source_error")
                    item.update(existing_D20=saved["existing_D20"],
                                native_element_counts=saved["native_element_counts"])
                else:
                    item.update(canonical.read(item["split"], item["molecule_index"]))
                    if pointers is None:
                        source = database.execute("SELECT pointer FROM geometries WHERE mid=? AND src='pm7' LIMIT 1",
                            (item["molecule_id"],)).fetchone()
                        pointer = None if source is None else json.loads(source[0])
                    else:
                        pointer = pointers[item["molecule_id"]]
                    try:
                        if pointer is None:
                            raise ValueError("Original D20 source pointer missing")
                        item["smiles"] = original_smiles(pointer, lookup=lookup)
                        item["source_error"] = None
                    except (ValueError, KeyError) as error:
                        # Missing source graphs are preserved as explicit missing rows.
                        # Infrastructure IO/import exceptions propagate for repair.
                        item["smiles"], item["source_error"] = None, str(error)
                state["source_missing"] += item["smiles"] is None
                stream.write((json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
            state.update(closed_rows=offset + len(batch), byte_offset=stream.tell(),
                elapsed_seconds=previous + time.monotonic() - start)
            publish(state_path, state)
            print(json.dumps({"stage": "source_structures", "closed_rows": state["closed_rows"]}), flush=True)
    database.close()
    canonical.close()
    target = out / "structures.jsonl"
    os.replace(partial, target)
    counts = {role: sum(row["role"] == role for row in rows) for role in ("TRAIN", "VAL", "VAL_DIAGNOSTIC")}
    publish(final_manifest, {"status": "TARGET_FREE_SOURCE_STRUCTURES_READY", "rows": str(target),
        "row_count": len(rows), "role_counts": counts, "producer_alignment_checked": True,
        "source_missing_rows": state["source_missing"], "source_references": references,
        "jobs": state["jobs"], "node": node, "elapsed_seconds": state["elapsed_seconds"],
        "normalizations_fitted": False, "reception_acceptance": "pending"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    prepare(json.loads(Path(args.config).read_text()))


if __name__ == "__main__":
    main()
