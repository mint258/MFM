"""Final TRAIN/common/geometry-eligible fit, or an independent complete replay.

All stages run inside one explicitly budgeted Root Slurm allocation. Exact tail
radix passes reopen canonical parquet; no scheduler or automatic submission here.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import multiprocessing
import os
from pathlib import Path
import time

from runtime import (advance, budget, canonical_bytes, connect, fail, guard, initial_queries,
                     load, merge_qr, new_root, path_list, ref, require, save, semantic_sha,
                     sqlstr, unique_bytes)
from authority import install_authority
from moments import combine, combine_joint
from series import inventory
from sources import datasets, prepare_sides
from worker import initialize, run as worker_run


def execute_phase(cfg, source_cfg, jobs, phase, payload, root, phase_index):
    out = root / ("pass_" + str(phase_index).zfill(2) + "_" + phase); out.mkdir()
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(16); stop = context.Event(); started = time.monotonic()
    receipts = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=context,
            initializer=initialize, initargs=(cfg, source_cfg, barrier, stop, phase, payload, str(out))) as pool:
        for pin in pool.map(worker_run, jobs, chunksize=1):
            receipts.append(pin)
            budget(root, cfg["output_cap_bytes"])
    rows = [load(require(p)) for p in receipts]
    if len({r["pid"] for r in rows}) != 16 or len(rows) != len(jobs):
        raise ValueError("FINAL_FIT_REQUIRES_16_ACTUAL_WORKERS_AND_ALL_SOURCE_GROUPS")
    summary = {"phase": phase, "source_pass_index": phase_index, "groups": len(rows),
               "actual_worker_pids": sorted({r["pid"] for r in rows}), "receipts": receipts,
               "elapsed_seconds": time.monotonic() - started}
    pin = save(out / "pass_manifest.json", summary, root, cfg["output_cap_bytes"])
    print("FINAL_FIT_SOURCE_PASS", phase_index, phase, "groups", len(rows), flush=True)
    return rows, pin


def mass_signature(rows):
    return [{"dataset_id": r["dataset_id"], "group_index": r["group_index"],
             "fit_task_rows": r["fit_task_rows"], "fields_mass": r["fields_mass"],
             "masked_source_fit_mass_sha256": r["masked_source_fit_mass_sha256"]}
            for r in rows]


def check_mass(rows, expected):
    if mass_signature(rows) != expected:
        raise ValueError("FINAL_FIT_POPULATION_MASK_VALUE_MASS_CHANGED_BETWEEN_SOURCE_PASSES")


def merge_models(rows, ready):
    out = {}
    for item in ready:
        dsid = item["dataset"]["dataset_id"]; models = {}
        for f in item["fields"]:
            if not f["element_reference_eligible"]:
                continue
            fid = str(f["field_id"])
            states = [r["energy_TSQR"][fid] for r in rows if r["dataset_id"] == dsid]
            model = merge_qr(states)
            if "coefficients" in model:
                model["status"] = "FINAL_ELIGIBLE_TRAIN_ELEMENT_REFERENCE_NUMERIC_FIT"
                model["statistic_scope"] = "frozen common TRAIN minus exact heldout base geometries and their targets"
                model["source_field_key"] = f["field_key"]
            models[fid] = model
        out[dsid] = models
    return out


def histogram_rows(db, rows, dsid, tail):
    paths = [r["histogram"]["path"] for r in rows if r["dataset_id"] == dsid]
    return db.execute("SELECT field_id,node_id,prefix_bits,prefix,sum(n)::UBIGINT n FROM read_parquet(" +
        path_list(paths) + ") WHERE tail=" + sqlstr(tail) +
        " GROUP BY field_id,node_id,prefix_bits,prefix ORDER BY field_id,node_id,prefix").fetch_arrow_table().to_pylist()


def advance_tails(db, rows, queries, finished):
    next_queries = {}
    for dsid, tails in queries.items():
        next_queries[dsid] = {}
        for name, request in tails.items():
            nxt, done = advance(request, histogram_rows(db, rows, dsid, name))
            finished[dsid][name].extend(done)
            next_queries[dsid][name] = nxt
    return next_queries


def quantile_results(catalogs, finished):
    out = {}
    for dsid, cat in catalogs.items():
        low = {r["field_id"]: r for r in finished[dsid]["lower"]}
        high = {r["field_id"]: r for r in finished[dsid]["upper"]}
        if set(low) != set(high) or set(low) != {r["field_id"] for r in cat}:
            raise ValueError("FINAL_QUANTILE_SERIES_COVERAGE_INCOMPLETE")
        out[dsid] = {}
        for sid in sorted(low):
            a, b = low[sid], high[sid]
            if a["n"] != b["n"] or (a["n"] and (a["value"] is None or b["value"] is None or a["value"] > b["value"])):
                raise ValueError("FINAL_QUANTILE_TAIL_MASS_OR_ORDER_DIFFERS")
            out[dsid][str(sid)] = {"n": a["n"], "lower": a["value"], "upper": b["value"],
                "lower_probability": "0.001", "upper_probability": "0.999", "method": "exact float64 type-7 quantiles",
                "source_labels_modified": False}
    return out


def final_statistics(rows, payload, quantiles, ready, pending, totals, authority_proof, source_mass, cfg):
    result = {}
    for item in ready:
        dsid = item["dataset"]["dataset_id"]; parts = [r for r in rows if r["dataset_id"] == dsid]
        counts = collections.Counter()
        for r in parts:
            counts.update(r["series_mass"])
        series = []
        for meta in payload["catalogs"][dsid]:
            sid = str(meta["field_id"]); q = quantiles[dsid][sid]
            states = [r["moments"].get(sid, {"n": 0, "mean": "0", "M2": "0"}) for r in parts]
            value = combine(states)
            if value["n"] != q["n"] or counts[sid] != q["n"]:
                raise ValueError("FINAL_QUANTILE_AND_WINSOR_MOMENT_MASS_DIFFERS")
            series.append({**meta, **q, **value})
        # Each atom leaf belongs to exactly one element. Empty elements stay explicit.
        by_key = {r["key"]: r for r in series}
        for f in item["fields"]:
            if f["level"] in {"atom", "atom_vector"}:
                fid = str(f["field_id"])
                if sum(by_key[fid + "/raw/Z" + str(z)]["n"] for z in item["plan"]["element_basis"]) != by_key[fid + "/raw"]["n"]:
                    raise ValueError("GLOBAL_ATOM_AND_ELEMENT_LEAF_MASS_DIFFERS")
        joint_keys = sorted({key for r in parts for key in r["joint"]}
                            | {g["key"] for g in payload["physical"][dsid]}
                            | {f["field_key"] for f in item["fields"] if f["level"] == "atom_vector"})
        physical = {key: combine_joint([r["joint"][key] for r in parts if key in r["joint"]]) for key in joint_keys}
        field_mass = collections.Counter()
        for r in parts:
            field_mass.update(r["fields_mass"])
        result[dsid] = {"dataset_manifest": item["manifest"], "label_group": item["dataset"]["label_group"],
            "geometry_source": item["dataset"]["geometry_source"], "eligibility_counts": totals[dsid],
            "masked_field_mass": dict(sorted(field_mass.items())), "element_reference": payload["models"][dsid],
            "series": series, "physical_groups": payload["physical"][dsid], "raw_joint_physical_statistics": physical,
            "status": "FINAL_ELIGIBILITY_NUMERICAL_STATISTICS_COMPUTED_REPLAY_AND_MODEL_CONVENTION_PENDING"}
    return {"schema": "FINAL_NORMALIZATION_NUMERICAL_STATISTICS_V1", "authority": authority_proof["authority"],
            "diagnostic_geometry_key_sha256": authority_proof["diagnostic_geometry_key_sha256"],
            "fit_role": "TRAIN_ONLY", "source_config": cfg["source_config"],
            "source_fit_mass_sha256": semantic_sha(source_mass), "datasets": result, "pending_datasets": pending,
            "winsorization": "q0.001/q0.999 apply only to statistical copies; original labels remain unchanged",
            "normalization_head_convention": "DRAFT_NOT_DECIDED_BY_COMPONENT_STATISTICS",
            "D4_published": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True); p.add_argument("--root-preflight", required=True)
    p.add_argument("--output", required=True); p.add_argument("--replay-of")
    a = p.parse_args(); cfg, proof = guard(a.config, a.root_preflight)
    source_cfg = load(require(cfg["source_config"]))
    if a.replay_of and ref(a.replay_of) not in proof["request"]["source_references"]:
        raise ValueError("REPLAY_REFERENCE_NOT_PINNED_BY_ROOT")
    if proof["request"]["pilot"] is not False or not proof["request"]["root_review"].get("accepted_pilot_reference"):
        raise ValueError("REAL_FINAL_FIT_REQUIRES_ACCEPTED_MEASURED_PILOT_AND_NONPILOT_ROOT_REQUEST")
    root = new_root(a.output, cfg["external_output_root"]); cap = cfg["output_cap_bytes"]
    db = connect(root, spill=cfg["spill_cap"]); started = time.monotonic(); all_passes = []
    try:
        authority_proof = install_authority(db, cfg)
        ready, pending = datasets(cfg)
        sides, totals = prepare_sides(db, cfg, ready, root)
        save(root / "fit_population_manifest.json", {"schema": "FINAL_FIT_POPULATION_V1", "authority": authority_proof,
            "datasets": totals, "side_tables": sides, "fit_role": "TRAIN_ONLY", "normalization_completed": False}, root, cap)
        catalogs, physical = {}, {}
        jobs = []; lookup = {(r["dataset_id"], r["group_index"]): r for r in sides}
        for item in ready:
            dsid = item["dataset"]["dataset_id"]
            catalogs[dsid], physical[dsid] = inventory(item)
            if len(catalogs[dsid]) > cfg["series_cap"]:
                raise ValueError("FINAL_STATISTICAL_SERIES_CAP_EXCEEDED")
            for group in item["plan"]["groups"]:
                reduced = {**item, "mask_receipts": {group["group_index"]: item["mask_receipts"][group["group_index"]]}}
                jobs.append({"item": reduced, "group": group, "side": lookup[dsid, group["group_index"]], "work_index": len(jobs)})
        if len(jobs) < 16:
            raise ValueError("FINAL_FIT_REQUIRES_AT_LEAST_16_SOURCE_GROUPS")
        payload = {"catalogs": catalogs, "physical": physical}
        rows, pin = execute_phase(cfg, source_cfg, jobs, "energy", payload, root, 0); all_passes.append(pin)
        source_mass = mass_signature(rows); payload["models"] = merge_models(rows, ready)
        save(root / "final_TRAIN_element_references.json", payload["models"], root, cap)
        payload["queries"] = {dsid: {"lower": initial_queries(cat, "lower_tail", probability="0.001"),
                                              "upper": initial_queries(cat, "upper_tail", probability="0.999")} for dsid, cat in catalogs.items()}
        finished = {dsid: {"lower": [], "upper": []} for dsid in catalogs}
        phase_index = 1
        while any(request["fields"] for tails in payload["queries"].values() for request in tails.values()):
            if phase_index >= cfg["maximum_source_passes"] - 1:
                raise RuntimeError("FINAL_EXACT_TAIL_SOURCE_PASS_BUDGET_EXHAUSTED_NO_AUTOCONTINUE")
            save(root / ("tail_queries_" + str(phase_index).zfill(2) + ".json"), payload["queries"], root, cap)
            rows, pin = execute_phase(cfg, source_cfg, jobs, "quantiles", payload, root, phase_index); all_passes.append(pin)
            check_mass(rows, source_mass)
            payload["queries"] = advance_tails(db, rows, payload["queries"], finished)
            phase_index += 1
        quantiles = quantile_results(catalogs, finished); payload["quantiles"] = quantiles
        del payload["queries"]
        save(root / "exact_final_TRAIN_tail_quantiles.json", quantiles, root, cap)
        rows, pin = execute_phase(cfg, source_cfg, jobs, "moments", payload, root, phase_index); all_passes.append(pin)
        check_mass(rows, source_mass)
        stable = final_statistics(rows, payload, quantiles, ready, pending, totals, authority_proof, source_mass, cfg)
        stable_pin = save(root / "normalization_numeric_statistics.json", stable, root, cap)
        replay = None
        if a.replay_of:
            old = load(a.replay_of)
            if old["config"] != ref(a.config):
                raise ValueError("INDEPENDENT_REPLAY_CONFIG_PIN_DIFFERS")
            previous = load(require(old["numeric_statistics"]))
            if canonical_bytes(previous) != canonical_bytes(stable):
                raise ValueError("INDEPENDENT_REBUILD_NUMERIC_STATISTICS_DIFFER")
            replay = {"status": "INDEPENDENT_FULL_REBUILD_EXACT_SEMANTIC_BYTES_MATCH",
                      "original_manifest": ref(a.replay_of), "numeric_statistics_sha256": stable_pin["sha256"]}
        result = {"schema": "FINAL_NORMALIZATION_RUN_MANIFEST_V1", "config": ref(a.config),
            "root_preflight": ref(a.root_preflight), "job_id": os.environ["SLURM_JOB_ID"],
            "source_passes": all_passes, "source_pass_count": len(all_passes), "numeric_statistics": stable_pin,
            "independent_rebuild": replay, "pending_datasets": pending, "elapsed_seconds": time.monotonic() - started,
            "unique_inode_output_bytes_before_manifest": unique_bytes(root), "normalization_completed": not pending and replay is not None,
            "D4_published": False, "model_norm_head_contract": "DRAFT_REQUIRES_JOINT_FREEZE",
            "status": "NUMERIC_FIT_REPLAY_VERIFIED_MODEL_CONTRACT_DRAFT" if replay else "NUMERIC_FIT_REQUIRES_INDEPENDENT_FULL_REBUILD"}
        save(root / "manifest.json", result, root, cap)
        print(result["status"], "pending_sources", len(pending), flush=True)
    except BaseException as exc:
        fail(root, exc); raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
