"""Final metadata handoff for BOTH old and directive19 scopes, without SQLite replay."""
import argparse
import json
import os
from pathlib import Path

from .admission import protect
from . import handoff
from .shared_access import completed_evidence

PEER_ENVIRONMENT_RESERVE = 24 * 1024**3


def closed_scope(scope, native=completed_evidence):
    scope = Path(scope)
    geometry = scope / "geometry/shared_v1"
    ga = json.loads((geometry / "access.json").read_text())
    if (not ga.get("immutable") or not ga.get("cross_node_read_allowed")
            or ga.get("publishing_uid") != os.getuid()):
        raise ValueError("Geometry scope is not sealed by the expected owner")
    gm = json.loads(Path(ga["source_producer_manifest"]).read_text())
    if (str(gm.get("job")) != str(ga.get("producer_job"))
            or gm.get("status") != "ALL_QUEUED_MOLECULES_TERMINAL"
            or any(gm["states"].get(key, 0) for key in ("PENDING", "INTENT"))):
        raise ValueError("Geometry terminal producer does not close this scope")
    geometry_native = native(ga["producer_job"])
    pp = scope / "labels/Pprime/shared_v1"
    pa = json.loads((pp / "access.json").read_text())
    if (pa.get("publishing_uid") != os.getuid()
            or not pa.get("cross_node_read_allowed")):
        raise ValueError("P-prime scope is not shared and sealed by the expected owner")
    pc = handoff.pprime_closure(pp, pa)
    if not pc["production_closed"]:
        raise ValueError("P-prime scope remains active or incomplete")
    pprime_native = native(pa["producer_job"])
    return dict(root=str(scope), geometry_queue=str(geometry / "queue.sqlite"),
        geometry_access=str(geometry / "access.json"),
        geometry_producer=ga["source_producer_manifest"], geometry_outcomes=gm["states"],
        geometry_native_closure=geometry_native,
        Pprime_queue=str(pp / "queue.sqlite"), Pprime_access=str(pp / "access.json"),
        Pprime_native_closure=pprime_native, Pprime=pc,
        production_closed=True, shared_database_copies=False)


def target_definition_readiness(preparation):
    nmr_path = preparation.get("NMR2018_published_test_count_reconciliation")
    if not nmr_path:
        raise ValueError("Required author NMR split count evidence is missing")
    nmr = json.loads(Path(nmr_path).read_text())
    if not (nmr.get("all_test_spectrum_counts_match")
            and nmr.get("all_test_unique_molecule_counts_match")):
        raise ValueError("Required author NMR split counts do not match")
    atomic_path = preparation.get("pKa_atomic_targets")
    atomic = json.loads(Path(atomic_path).read_text()) if atomic_path else {}
    atomic_ready = bool(atomic.get("single_site_definition_frozen")
                        and atomic.get("atomic_mechanism_ready")
                        and atomic.get("user_definition_authority"))
    return dict(NMR_test_counts_matched=True, NMR_count_manifest=nmr_path,
        pKa_atomic_mechanism_ready=atomic_ready, pKa_atomic_manifest=atomic_path,
        pKa_site_definition_proposal=preparation.get("pKa_single_site_definition_proposal"),
        all_required_work_complete=atomic_ready,
        pending=[] if atomic_ready else ["pKa_single_site_definition_and_formal_atomic_targets"])


def final_capacity(root, snapshot, needed):
    # Both scopes have already been proven natively C0 with no future science writes.
    # Keep real bytes/inodes/quota, model budget, B1 environment and account floor.
    protect(root, needed, snapshot,
            own_concurrent_bytes=1073741824 + PEER_ENVIRONMENT_RESERVE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--progress", required=True, type=Path)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--quota-snapshot", required=True, type=Path)
    a = parser.parse_args()
    progress = json.loads(a.progress.read_text())
    scopes = {
        "original": closed_scope(a.root),
        "directive19_uniform_Sprime": closed_scope(a.root / "directive19/uniform_Sprime")}
    readiness = target_definition_readiness(progress["directive19_data_preparation"])
    final_capacity(a.root, a.quota_snapshot, 1048576)
    handoff.main(["--root", str(a.root), "--progress", str(a.progress),
                  "--attempt", a.attempt, "--quota-snapshot", str(a.quota_snapshot)],
                 capacity_check=final_capacity)
    path = a.root / "delivery" / a.attempt / "manifest.json"
    report = json.loads(path.read_text())
    report.update(schema="BENCHMARK_B0_DIRECTIVE19_FINAL_SCOPE_HANDOFF_V1",
        status=("DIRECTIVE19_ALL_REQUIRED_WORK_COMPLETE_WITH_EXPLICIT_OUTCOMES"
                if readiness["all_required_work_complete"] else
                "DIRECTIVE19_PRODUCTION_CLOSED_ATOMIC_DEFINITION_PENDING"),
        all_scopes_production_closed=True,
        all_required_production_complete=readiness["all_required_work_complete"],
        all_required_work_complete=readiness["all_required_work_complete"],
        production_scopes=scopes, target_definition_readiness=readiness,
        active_target_manifests={
            "NMRShiftDB2": progress["directive19_data_preparation"]["NMR2018_targets"],
            "pKahub": progress["directive19_data_preparation"]["pKahub_macro_targets"]},
        independent_numeric_readback=False)
    report["directive19_data_preparation"] = dict(progress["directive19_data_preparation"],
        uniform_scope_ready=True,
        pKa_atomic_site_evidence_ready=readiness["pKa_atomic_mechanism_ready"])
    if readiness["pKa_atomic_mechanism_ready"]:
        report["active_target_manifests"]["pKahub_atomic"] = readiness["pKa_atomic_manifest"]
    if report.get("directive19_resolutions") is not None:
        report["directive19_resolutions"]["data_preparation_complete"] = readiness["all_required_work_complete"]
    final_capacity(a.root, a.quota_snapshot, 1048576)
    temporary = path.with_name("manifest.final.pending.json")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)
    print("B0_FINAL_BOTH_SCOPES_CLOSED", path, readiness, flush=True)


if __name__ == "__main__":
    main()
