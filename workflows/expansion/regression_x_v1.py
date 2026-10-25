"""Full-original-input X01-X05 regression with a stratified 16-worker pilot.

Inputs are the all-record WP0 source projection and all-record relaxed quality,
not a retained-only subset. Original pointers/payload SHA remain traceable.
Geometry and relaxed identity decisions are held fixed and reported separately.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import json
import multiprocessing
import os
from pathlib import Path
import socket
import time

from .common import ARTIFACT_ROOT, check_quota, dump_new, load, reference, require, verify
from .download_raw_v1 import acquire_fresh_quota
from .screen import WHITELIST, rdkit_modules
from . import common as common_source, screen as screen_source, download_raw_v1 as quota_source, source as network_source
from . import data_authority_v1 as data_authority

CODES = ("X01", "X02", "X03", "X04", "X05")
EXTRA = ("G01", "G02", "G03", "C02", "C03", "I01")


def nullable_or(left, right):
    return True if left is True or right is True else False if left is False and right is False else None


@lru_cache(maxsize=4096)
def graph(smiles):
    Chem, *_ = rdkit_modules()
    if not isinstance(smiles, str):
        return {"parsed": False, "X01": None, "X02": None, "X03": None, "X04": None, "X05": None}
    dot = "." in smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"parsed": False, "X01": True if dot else None, "X02": None, "X03": None, "X04": None, "X05": None}
    explicit = Chem.AddHs(mol)
    zs = [a.GetAtomicNum() for a in explicit.GetAtoms()]
    return {"parsed": True, "X01": dot or len(Chem.GetMolFrags(mol)) > 1,
        "X02": any(z not in WHITELIST for z in zs), "X03": Chem.GetFormalCharge(mol) != 0,
        "X04": any(a.GetNumRadicalElectrons() > 0 for a in mol.GetAtoms()), "X05": sum(zs) % 2 == 1,
        "elements": sorted(set(zs)), "electron_count": sum(zs)}


def evaluate(row):
    g = graph(row.get("smiles"))
    dot = ("." in row["smiles"]) if isinstance(row.get("smiles"), str) else None
    fragments = row.get("stored_graph_fragments")
    cached_x1 = nullable_or(dot, fragments > 1 if fragments is not None else None)
    expected = {c: row[c] for c in CODES}
    # WP0 may already contain a previously cached geometry-component hit. That
    # annotation is not a pure source-SMILES rule and must not be called drift.
    if row.get("X01_geometry_checked") is True:
        expected["X01"] = cached_x1
    elements = row.get("elements")
    native_valid = row.get("native_x_encoding_or_shape_invalid") is False
    native = dict(g)
    native["X02"] = any(z not in WHITELIST for z in elements) if native_valid and elements is not None else None
    native["X05"] = row["electron_count"] % 2 == 1 if row.get("electron_count") is not None else None
    native_mismatch = [c for c in CODES if native.get(c) != expected[c]]
    portable_mismatch = [c for c in CODES if g.get(c) != expected[c]]
    causes = []
    if row.get("native_x_encoding_or_shape_invalid") is True:
        causes.append("INVALID_ORIGINAL_NATIVE_X")
    if g["parsed"] and elements is not None and sorted(set(elements)) != g["elements"]:
        causes.append("NATIVE_GRAPH_ELEMENT_DIFFERENCE")
    if g["parsed"] and row.get("electron_count") is not None and row["electron_count"] != g["electron_count"]:
        causes.append("NATIVE_GRAPH_HYDROGEN_OR_ATOM_COUNT_DIFFERENCE")
    if not g["parsed"] and row.get("parse_failed") is True:
        causes.append("ORIGINAL_SMILES_UNPARSEABLE")
    if native_mismatch:
        causes.append("UNEXPLAINED_CACHED_RULE_DRIFT")
    old_admit = all(expected[c] is False for c in CODES)
    new_admit = g["parsed"] and all(g[c] is False for c in CODES)
    old_saved_x = [row["saved_" + c] for c in CODES]
    extra_pass = row.get("geometry_evaluated") is True and all(row.get("extra_" + c) is not True for c in EXTRA)
    old_formula = extra_pass and all(value is not True for value in old_saved_x)
    require(old_formula == row["old_retained"], "Stored relaxed geometry/identity decision formula differs")
    early_component = row.get("X01_geometry_checked") is True and row["X01"] is True and cached_x1 is not True
    geometric_component = row.get("geometry_X01") is True or early_component
    # q.X05 is the frozen native-coordinate parity annotation. Report graph-only
    # admission separately so holding geometry fixed cannot hide graph drift.
    geometric_parity = row.get("geometry_evaluated") is True and row["saved_X05"] is True
    predicted_retained = new_admit and extra_pass and not geometric_component and not geometric_parity
    assigned = row.get("member_train") is True or row.get("member_full") is True
    expected_formal = row["old_retained"] and assigned
    require(expected_formal == row["formal_member"], "WP5 formal inclusion does not equal retained assigned source population")
    common = row.get("common_member", True)
    old_final = row["formal_member"] and common
    new_final = predicted_retained and assigned and common
    changed = old_admit != new_admit or old_final != new_final or bool(portable_mismatch)
    unexplained = bool(native_mismatch) or (changed and not causes)
    result = {"record_id": row["record_id"], "molecule_id": row["molecule_id"],
        "source_family": row["source_family"], "old_chemical_admit": old_admit, "new_graph_admit": new_admit,
        "old_final": old_final, "conditional_new_final": new_final, "native_rule_mismatch": bool(native_mismatch),
        "portable_flag_mismatch": bool(portable_mismatch), "unexplained": unexplained,
        "cached_geometry_x1_augmentation": early_component,
        "worker_pid": os.getpid()}
    if changed or native_mismatch:
        result["mismatch"] = {"record_id": row["record_id"], "molecule_id": row["molecule_id"],
            "source_path": row.get("source_path"), "real_index": row.get("real_index"),
            "record_payload_sha256": row.get("record_payload_sha256"), "smiles": row.get("smiles"),
            "original_flags": expected, "native_replayed_flags": {c: native.get(c) for c in CODES},
            "portable_graph_flags": {c: g.get(c) for c in CODES}, "native_mismatch": native_mismatch,
            "portable_mismatch": portable_mismatch, "causes": causes, "unexplained": unexplained,
            "old_chemical_admit": old_admit, "new_graph_admit": new_admit,
            "old_final": old_final, "conditional_new_final": new_final}
    return result


def evaluate_batch(rows):
    return [evaluate(row) for row in rows]


def _initialize(barrier):
    rdkit_modules()
    barrier.wait(timeout=180)


def input_batches(cursor, size=256):
    names = [c[0] for c in cursor.description]
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            return
        yield [dict(zip(names, row)) for row in rows]


def parallel_results(batches, workers):
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=_initialize,
                             initargs=(context.Barrier(workers),)) as pool:
        waiting = deque()
        for batch in batches:
            waiting.append(pool.submit(evaluate_batch, batch))
            if len(waiting) >= 2 * workers:
                yield waiting.popleft().result(timeout=7200)
        while waiting:
            yield waiting.popleft().result(timeout=7200)


def prepare_join(db, sources, expected_rows, expected_formal):
    for key, name in (("original_index", "original"), ("relaxed_quality", "quality"), ("formal_population", "formal")):
        path = verify(sources[key])
        db.read_parquet(str(path)).create_view(name)
    n, unique = db.execute("SELECT count(*),count(DISTINCT record_id) FROM original").fetchone()
    require(n == unique == expected_rows, "Regression input is not the complete unique original-record population")
    nq, uq = db.execute("SELECT count(*),count(DISTINCT record_id) FROM quality").fetchone()
    nf, uf = db.execute("SELECT count(*),count(DISTINCT record_id) FROM formal").fetchone()
    require(nq == uq == n and nf == uf == expected_formal, "Quality/formal source count differs")
    common_join, common_col = "", "TRUE AS common_member"
    if sources.get("common_population"):
        path = verify(sources["common_population"])
        db.read_parquet(str(path)).project("molecule_id").create_view("common_population")
        nc, uc = db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM common_population").fetchone()
        require(nc == uc > 0, "Common population has missing/duplicated molecular identities")
        common_join, common_col = " LEFT JOIN common_population c ON c.molecule_id=i.molecule_id", "c.molecule_id IS NOT NULL AS common_member"
    saved = ",".join("q." + c + " AS saved_" + c for c in CODES)
    extras = ",".join("q." + c + " AS extra_" + c for c in EXTRA)
    db.execute(f"""CREATE VIEW joined AS SELECT i.record_id,i.molecule_id,i.source_family,i.source_path,i.real_index,
        i.record_payload_sha256,i.smiles,i.stored_graph_fragments,i.elements,i.electron_count,
        i.native_x_encoding_or_shape_invalid,i.atom_sequence_mismatch,i.H_count_mismatch,i.parse_failed,
        i.member_train,i.member_full,i.heavy_atoms,i.X01,i.X02,i.X03,i.X04,i.X05,i.X01_geometry_checked,
        q.record_id AS quality_record_id,q.retained AS old_retained,q.geometry_evaluated,q.geometry_X01,
        {saved},{extras},f.record_id IS NOT NULL AS formal_member,{common_col}
        FROM original i LEFT JOIN quality q USING(record_id) LEFT JOIN formal f USING(record_id){common_join}""")
    nj, missing, joined_formal = db.execute("SELECT count(*),count(*) FILTER(WHERE quality_record_id IS NULL),count(*) FILTER(WHERE formal_member) FROM joined").fetchone()
    require(nj == n and missing == 0 and joined_formal == nf, "All-original source/quality/formal join coverage differs")
    if sources.get("common_population"):
        covered = db.execute("SELECT count(DISTINCT molecule_id) FROM joined WHERE common_member AND formal_member").fetchone()[0]
        require(covered == nc, "Common molecular population is not completely covered by formal original-source records")
    return n


def select_pilot(db, seed, max_rows):
    ternary = "||".join(f"CASE WHEN {c} IS TRUE THEN '1' WHEN {c} IS FALSE THEN '0' ELSE 'u' END" for c in CODES)
    db.execute(f"""CREATE VIEW stratified AS SELECT *,source_family||'|'||
        CASE WHEN heavy_atoms IS NULL THEN 'unknown' WHEN heavy_atoms<=10 THEN '10' WHEN heavy_atoms<=20 THEN '20'
          WHEN heavy_atoms<=30 THEN '30' WHEN heavy_atoms<=50 THEN '50' WHEN heavy_atoms<=75 THEN '75'
          WHEN heavy_atoms<=100 THEN '100' ELSE 'above100' END ||'|'||({ternary})||'|'||
        CASE WHEN member_train THEN 'TRAIN' WHEN member_full THEN 'FULL' ELSE 'unassigned' END ||'|'||
        CASE WHEN old_retained THEN 'retained' ELSE 'excluded' END AS stratum FROM joined""")
    strata = db.execute("SELECT stratum,count(*) FROM stratified GROUP BY stratum ORDER BY stratum").fetchall()
    require(0 < len(strata) <= max_rows, "Pilot cap cannot represent all observed inclusion/exclusion/unknown strata")
    each = min(32, max_rows // len(strata))
    db.execute("""CREATE TABLE pilot AS SELECT * EXCLUDE(ordinal) FROM (
        SELECT *,row_number() OVER(PARTITION BY stratum ORDER BY sha256(record_id||?),record_id) AS ordinal FROM stratified)
        WHERE ordinal<=?""", ["|" + str(seed), each])
    return {"seed": seed, "max_rows": max_rows, "per_stratum_cap": each,
            "source_strata": [{"stratum": s, "available_records": n} for s, n in strata],
            "selected_strata": [{"stratum": s, "records": n} for s, n in db.execute("SELECT stratum,count(*) FROM pilot GROUP BY stratum ORDER BY stratum").fetchall()]}


def run(plan_path, submission_path):
    require(os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16,
            "Regression scans require a real zixiao >=16CPU Slurm allocation")
    require(socket.gethostname().startswith("compute-0-"), "Never scan regression data on the login node")
    plan, submission = load(plan_path), load(submission_path)
    require(plan["schema"] == "v1_X_regression_execution_plan_v1" and plan["status"] == "READY", "Root must bind a READY regression plan")
    require(submission["uid"] == 1278 and submission["request"]["root_review"]["status"] == "APPROVED", "Root submission review required")
    request = submission["request"]
    require(request["node"] == socket.gethostname().split(".")[0] and request["cpus"] == 16 and request["memory_gib"] >= 32 and
            0 < request["wall_seconds"] <= 172800 and request["estimated_peak_output_bytes"] >= plan["peak_output_cap_bytes"],
            "Root regression resource declaration differs from actual execution/budget")
    require(plan["mode"] in ("pilot", "full") and plan["workers"] == 16, "Unreviewed regression mode/workers")
    needed = [reference(plan_path), *plan["code_sources"], *plan.get("data_authorization_receipts", [])]
    declared = {r["path"]: r for r in submission["request"]["source_references"]}
    require(all(declared.get(r["path"]) == r for r in needed), "Root intent does not bind actual plan/source population")
    for ref in plan["code_sources"]:
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, common_source.__file__, screen_source.__file__, quota_source.__file__, network_source.__file__, data_authority.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Running regression source/import chain is not pinned")
    if plan["mode"] == "full":
        pilot = load(verify(plan["closed_pilot_receipt"]))
        require(pilot["mode"] == "pilot" and pilot["status"] == "PILOT_RULE_REPLAY_CLOSED", "Full regression requires an actually closed successful pilot")
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "regression") and not out.exists(), "Fresh external regression output required")
    out.mkdir(parents=True)
    started = time.monotonic()
    try:
        acquire_fresh_quota(plan["quota"], out / "quota_start.json")
        check_quota(out / "quota_start.json", plan["peak_output_cap_bytes"])
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "FAILED_REGRESSION_QUOTA_START", "error_type": type(exc).__name__, "error": str(exc)})
        raise
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    db = duckdb.connect()
    db.execute("SET threads=16")
    db.execute(f"SET memory_limit='{int(plan['duckdb_memory_gib'])}GB'")
    db.execute(f"SET max_temp_directory_size='{int(plan['spill_gib'])}GB'")
    spill = out / "spill"; spill.mkdir()
    db.execute("SET temp_directory=?", [str(spill)])
    counts, workers, reasons = Counter(), set(), Counter()
    schema = pa.schema([(k, pa.string()) for k in ("record_id", "molecule_id", "source_family")] +
        [(k, pa.bool_()) for k in ("old_chemical_admit", "new_graph_admit", "old_final", "conditional_new_final",
          "native_rule_mismatch", "portable_flag_mismatch", "unexplained", "cached_geometry_x1_augmentation")])
    decisions = out / "record_decisions.parquet"
    mismatches = out / "all_mismatches.jsonl"
    try:
        authority = data_authority.authorize_data(plan, submission, [r for r in plan["sources"].values() if r is not None],
                                                  node=socket.gethostname().split(".")[0])
        # prepare_join below performs each full source SHA on compute. Metadata
        # is checked immediately around that verification, not on login.
        total = prepare_join(db, plan["sources"], plan["expected_original_records"], plan["expected_formal_records"])
        data_authority.verify_final_stats(authority)
        source_seconds = time.monotonic() - started
        sampling = select_pilot(db, plan["seed"], plan["pilot_max_rows"]) if plan["mode"] == "pilot" else None
        if sampling:
            dump_new(out / "pilot_sampling.json", sampling)
        # Initial source joins/stratification use 16 SQL threads. During the
        # graph phase only one coordinator stream accompanies 16 graph workers;
        # do not simultaneously start another 16-thread SQL execution pool.
        db.execute("SET threads=1")
        query = "SELECT * FROM " + ("pilot" if sampling else "joined") + " ORDER BY record_id"
        cursor = db.execute(query)
        compute_started = time.monotonic()
        with pq.ParquetWriter(decisions, schema, compression="zstd") as writer, mismatches.open("x", encoding="utf-8", newline="\n") as detail:
            for batch in parallel_results(input_batches(cursor), 16):
                payload = []
                for result in batch:
                    workers.add(result["worker_pid"])
                    counts["records"] += 1
                    for field in schema.names[3:]:
                        counts[field] += int(result[field])
                    counts["chemical_admission_changed"] += int(result["old_chemical_admit"] != result["new_graph_admit"])
                    counts["conditional_final_changed"] += int(result["old_final"] != result["conditional_new_final"])
                    if "mismatch" in result:
                        detail.write(json.dumps(result["mismatch"], separators=(",", ":"), allow_nan=False) + "\n")
                        reasons.update(result["mismatch"]["causes"])
                    payload.append({k: result[k] for k in schema.names})
                writer.write_table(pa.Table.from_pylist(payload, schema=schema))
                require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= plan["peak_output_cap_bytes"], "STOP: regression output/spill budget exceeded")
            detail.flush(); os.fsync(detail.fileno())
        require(counts["records"] > 0 and (sampling is not None or counts["records"] == total), "Regression source coverage incomplete")
        db.read_parquet(str(decisions)).create_view("decisions")
        molecular = db.execute("""SELECT count(*) AS molecules,sum((old_selected!=new_selected)::INTEGER) AS changed_molecules,
            sum(old_selected::INTEGER) AS old_selected_molecules,sum(new_selected::INTEGER) AS new_selected_molecules FROM (
            SELECT molecule_id,bool_or(old_final) AS old_selected,bool_or(conditional_new_final) AS new_selected FROM decisions GROUP BY molecule_id)""").fetchone()
        agreement = 1 - counts["chemical_admission_changed"] / counts["records"]
        conditional = 1 - counts["conditional_final_changed"] / counts["records"]
        molecular_agreement = 1 - molecular[1] / molecular[0]
        code_replay = counts["native_rule_mismatch"] == 0 and counts["unexplained"] == 0
        good = code_replay and (sampling is not None or (agreement >= .999 and conditional >= .999 and molecular_agreement >= .999))
        full_common = plan["mode"] == "full" and plan["sources"].get("common_population") is not None
        state = "STOP_REVIEW" if not good else "PILOT_RULE_REPLAY_CLOSED" if sampling else "PASS" if full_common else "FULL_X_RULE_PASS_COMMON_SCOPE_PENDING"
        report = {"schema": "pubchem_v1_complete_input_regression_v1", "mode": plan["mode"],
            "status": state,
            "plan": reference(plan_path), "root_submission": reference(submission_path), "source_refs": plan["sources"],
            "all_original_records": total, "evaluated_records": counts["records"], "counts": dict(counts),
            "chemical_admission_agreement": agreement, "conditional_geometry_identity_selection_agreement": conditional,
            "five_portable_flag_agreement": 1 - counts["portable_flag_mismatch"] / counts["records"],
            "molecules_observed": molecular[0], "conditional_changed_molecules": molecular[1], "conditional_molecule_agreement": molecular_agreement,
            "old_selected_molecules": molecular[2], "conditional_new_selected_molecules": molecular[3],
            "agreement": min(agreement, conditional, molecular_agreement), "unexplained_mismatches": counts["unexplained"], "causes": dict(reasons),
            "rdkit": "2025.09.5", "geometry_and_identity_recomputed": False, "old_geometry_identity_decisions_held_fixed": True,
            "sample_is_not_an_all_input_consistency_claim": sampling is not None,
            "pilot_rates_are_unweighted_stratified_observations_not_population_estimates": sampling is not None,
            "full_v1_selection_regression_passed": bool(good and full_common),
            "common_population_scope_bound": full_common, "worker_pids_observed": sorted(workers),
            "wall_seconds": time.monotonic() - started, "record_decisions": reference(decisions),
            "source_verification_and_join_seconds": source_seconds,
            "sampling_and_ordering_seconds": compute_started - started - source_seconds,
            "worker_pipeline_wall_seconds": time.monotonic() - compute_started,
            "all_mismatches": reference(mismatches), "original_lmdb_opened_or_modified": False}
        data_authority.verify_final_stats(authority)
        report["data_authority"] = authority
        dump_new(out / "receipt.json", report)
        require(good, "STOP: selection agreement below 99.9%, cached rule drift or unexplained mismatch")
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "FAILED_REGRESSION", "error_type": type(exc).__name__, "error": str(exc),
            "counts_so_far": dict(counts), "wall_seconds": time.monotonic() - started, "original_data_written": False})
        raise
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--root-submit-intent", required=True, type=Path)
    args = p.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
