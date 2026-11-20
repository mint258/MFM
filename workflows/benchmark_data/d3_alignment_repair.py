"""Repair only recorded D3 atom-alignment failures after the UFF writer closes."""
import argparse
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import socket
import sqlite3
import time
import zlib
from rdkit import Chem, rdBase

from .admission import protect
from .d3_source_alignment import aligned_descriptors, targeted_failure
from .shared_access import completed_evidence, publish
from .uniform_pprime_scope import scope_base, remaining_budget, used_bytes
from .pprime_standby import native_job
from .uniform_sprime_scope import source_closed


def packed(value):
    return zlib.compress(json.dumps(value, separators=(",", ":"), allow_nan=False).encode(), 3)


def repair_rows(db, job, safe):
    db.execute("""CREATE TABLE IF NOT EXISTS d3_alignment_once(
        mid TEXT NOT NULL,cid INTEGER NOT NULL,status TEXT NOT NULL,
        job TEXT NOT NULL,attempted REAL,error TEXT,PRIMARY KEY(mid,cid))""")
    # An interrupted property call has unknown outcome and must never be repeated.
    db.execute("UPDATE d3_alignment_once SET status='UNKNOWN_INTERRUPTED_NO_RETRY' WHERE status='INTENT'")
    db.commit()
    after = ""
    while True:
        safe()
        rows = db.execute("""SELECT mid,result FROM tasks WHERE state='SPRIME_READY_D_PARTIAL'
            AND mid>? ORDER BY mid LIMIT 16""", (after,)).fetchall()
        if not rows:
            break
        after = rows[-1][0]
        for mid, payload in rows:
            result = json.loads(zlib.decompress(payload))
            selected = [(index, conf) for index, conf in enumerate(result["conformers"])
                        if targeted_failure(conf)]
            if not selected:
                continue
            params = Chem.SmilesParserParams(); params.removeHs = False
            mol = Chem.AddHs(Chem.MolFromSmiles(result["model_smiles"], params))
            for index, conf in selected:
                cid = int(conf["conformer_id"])
                if db.execute("SELECT 1 FROM d3_alignment_once WHERE mid=? AND cid=?",
                              (mid, cid)).fetchone():
                    continue
                safe()
                db.execute("INSERT INTO d3_alignment_once VALUES(?,?,'INTENT',?,?,NULL)",
                           (mid, cid, str(job), time.time()))
                db.commit()
                try:
                    d3, issues, mapping = aligned_descriptors(
                        result["model_smiles"], mol, result["atomic_numbers"],
                        conf["coordinates_A"], result["D20"])
                    replacement = dict(conf, D3=d3, D3_issues=issues,
                        D3_original_alignment_failure={"D3": None, "D3_issues": conf["D3_issues"]},
                        D3_alignment_repair={"job": str(job), "legacy_atom_to_source": mapping,
                                             "original_functions_units_and_source_coordinates": True})
                    updated = dict(result)
                    updated["conformers"] = list(result["conformers"])
                    updated["conformers"][index] = replacement
                    ready = (all(updated["D20"]["valid_mask"])
                             and all(c.get("D3") is not None and not c.get("D3_issues")
                                     for c in updated["conformers"]))
                    state = "SPRIME_AND_D_READY" if ready else "SPRIME_READY_D_PARTIAL"
                    updated["state"] = state
                    encoded = packed(updated)
                except Exception as exc:
                    safe()
                    db.execute("""UPDATE d3_alignment_once SET status='REPAIR_FAILED',error=?
                        WHERE mid=? AND cid=?""", (repr(exc), mid, cid))
                    db.commit()
                    continue
                safe()
                # Property publication and once-only outcome commit atomically.
                db.execute("UPDATE tasks SET result=?,state=? WHERE mid=?", (encoded, state, mid))
                db.execute("""UPDATE d3_alignment_once SET status=?,error=NULL
                    WHERE mid=? AND cid=?""",
                    ("D3_REPAIRED" if not issues else "D3_PARTIAL", mid, cid))
                db.commit()
                result = updated
        outcomes = dict(db.execute("SELECT status,count(*) FROM d3_alignment_once GROUP BY status"))
        print("D3_ALIGNMENT_REPAIR_PROGRESS", outcomes, flush=True)
    return dict(db.execute("SELECT status,count(*) FROM d3_alignment_once GROUP BY status"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--source-producer-job", required=True, type=int)
    p.add_argument("--quota-snapshot", required=True, type=Path)
    a = p.parse_args()
    if rdBase.rdkitVersion != '2025.09.5':
        raise RuntimeError('The original RDKit version is required for D3 repair')
    base = scope_base(a.root)
    original_folder = base / "geometry/shared_v1"
    original_access = json.loads((original_folder / "access.json").read_text())
    original_report = json.loads(Path(original_access["source_producer_manifest"]).read_text())
    if not source_closed(original_access, original_report, os.getuid()):
        raise ValueError("Original geometry future budget cannot retire without its native immutable seal")
    folder = a.root / "geometry/shared_v1"
    source_report = folder / ("producer_" + str(a.source_producer_job) + ".json")
    source_native = completed_evidence(a.source_producer_job)
    source = json.loads(source_report.read_text())
    if (str(source["job"]) != str(a.source_producer_job)
            or source["status"] != "ALL_QUEUED_MOLECULES_TERMINAL"
            or any(source["states"].get(k, 0) for k in ("PENDING", "INTENT"))):
        raise ValueError("Original accepted UFF scope has not fully closed")
    access_path = folder / "access.json"
    access = json.loads(access_path.read_text())
    if (access.get("immutable") or access.get("publishing_uid") != os.getuid()
            or access.get("producer_node") != socket.gethostname().split(".")[0]):
        raise ValueError("D3 repair requires the unsealed source on its actual writer node")
    previous = str(access["producer_job"])
    if previous != str(a.source_producer_job):
        prior = native_job(int(previous))
        if (prior.get("JobState") not in {"COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"}
                or "(" + str(os.getuid()) + ")" not in prior.get("UserId", "")):
            raise ValueError("A previous D3 writer remains live or has unknown ownership")
    job = str(int(os.environ["SLURM_JOB_ID"]))
    def safe():
        waiting = False
        while True:
            try:
                protect(base, remaining_budget(
                    used_bytes(base / "labels/Pprime/shared_v1"),
                    used_bytes(a.root / "labels/Pprime/shared_v1"), 67108864),
                    a.quota_snapshot, own_concurrent_bytes=1073741824)
                return
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                if not waiting:
                    print("D3_ALIGNMENT_REAL_CAPACITY_WAIT", repr(exc), flush=True)
                waiting = True
                time.sleep(2)
    safe()
    with (folder / "D3_alignment_writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        publish(access_path, dict(producer_job=job,
            producer_node=socket.gethostname().split(".")[0],
            immutable=False, cross_node_read_allowed=False,
            source_geometry_job=a.source_producer_job,
            source_geometry_manifest=str(source_report),
            D3_alignment_repair_in_progress=True, database_copy_created=False))
        db = sqlite3.connect(str(folder / "queue.sqlite"), timeout=30)
        try:
            db.execute("PRAGMA temp_store=MEMORY")
            initial_states = dict(db.execute("SELECT state,count(*) FROM tasks GROUP BY state"))
            if any(initial_states.get(k, 0) for k in ("PENDING", "INTENT")):
                raise ValueError("Original geometry tasks unexpectedly remain active")
            outcomes = repair_rows(db, job, safe)
            states = dict(db.execute("SELECT state,count(*) FROM tasks GROUP BY state"))
            if outcomes.get("INTENT", 0):
                raise RuntimeError("Uncommitted D3 property attempts remain")
            report = dict(status="ALL_QUEUED_MOLECULES_TERMINAL",
                job=job, queue=str(folder / "queue.sqlite"), states=states,
                source_geometry_manifest=str(source_report),
                source_geometry_native_closure=source_native,
                source_geometry_job=a.source_producer_job,
                D3_alignment_attempt_outcomes=outcomes,
                original_geometry_state_counts=source["states"],
                original_UFF_geometry_and_QM_unchanged=True,
                successful_D3_and_all_D20_unchanged=True,
                source_failed_D3_errors_preserved=True,
                method="Original D3 wire once after full-graph/chirality atom permutation; atomic SASA inverted",
                independent_numeric_readback=False, new_content_hashes=False,
                source_queue_copy_created=False, no_scientific_retry=True)
            safe()
            target = folder / ("producer_" + job + ".json")
            with target.open("x") as stream:
                json.dump(report, stream, indent=2); stream.write("\n")
            print("D3_ALIGNMENT_REPAIR_CLOSED", target, outcomes, states, flush=True)
        finally:
            db.close()


if __name__ == "__main__":
    main()
