"""Metadata-only binding of already-tested source and prospective D3 rules."""
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from runtime import ROOT, SOURCE, OLD, save, sha


def completed(job):
    raw = subprocess.check_output(["sacct", "-j", str(job), "--format=JobIDRaw,State,ExitCode", "-n", "-P"], text=True)
    row = next(line.split("|") for line in raw.splitlines() if line.split("|")[0] == str(job))
    assert row[1:] == ["COMPLETED", "0:0"], row
    return raw


def main():
    assert os.getuid() == 1278
    path = ROOT / "configs/D3_source_binding_v3.json"
    assert not path.exists(), "Source binding already registered; use a new immutable version"
    suite = ET.parse(ROOT / "reports/all_tests_v3.xml").getroot()
    assert not list(suite.iter("failure")) and not list(suite.iter("error")), "C6_ALL_TESTS_NOT_PASSED"
    assert json.loads((ROOT / "reports/legacy_bitexact_v2/result.json").read_text())["status"] == "LEGACY_V2_BITEXACT_PASS"
    epoch = json.loads((ROOT / "reports/epoch_workers_v1.json").read_text())
    assert epoch["status"] == "REAL_SPAWN_EPOCH_NOISE_AND_RESUME_PASS"
    loader = "current/phychem_mfm/phase1/full_corpus_loader.py"
    assert sha(SOURCE / loader) == sha(ROOT / "source" / loader)
    receipts = {}
    for name in ["unit_v1", "selection_v1", "all_suite_v3", "epoch_workers_v1", "gpu_smoke_v2"]:
        submission = json.loads((ROOT / "submission" / (name + ".json")).read_text())
        receipts[name] = {"job_id": submission["job_id"], "actual_sacct": completed(submission["job_id"])}
    files = sorted((SOURCE / "current/phychem_mfm").rglob("*.py")) + sorted((SOURCE / "workflows/s_denoise").glob("*.py"))
    references = [{"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in files]
    value = {"status": "D3_CODE_TESTED_AND_BOUND_BEFORE_SCIENTIFIC_TRAINING", "source_root": str(SOURCE),
             "files": references, "C6_actual_job_closure": receipts,
             "old_v2_config_sha256": sha(OLD / "formal_s/B3_seed0_v2.json"),
             "old_input_manifest_sha256": sha(OLD / "training_inputs_v1/manifest.json"),
             "guide_sha256": sha(ROOT / "user_repair_guide.md"),
             "legacy_bitexact_component": {"path": str(ROOT / "reports/legacy_bitexact_v2/result.json"),
                 "sha256": sha(ROOT / "reports/legacy_bitexact_v2/result.json"),
                 "parent_job_id": "4515528", "parent_status": "FAILED_due_to_later_missing_fixture_env_test",
                 "scope": "Completed byte equality component; original failed parent remains failed"},
             "rules": {"path": str(SOURCE / "workflows/s_denoise/configs/decision_rules_v3.json"),
                       "sha256": sha(SOURCE / "workflows/s_denoise/configs/decision_rules_v3.json")},
             "all_tests": len(list(suite.iter("testcase"))), "scientific_gate_passed": False}
    save(path, value)
    manifest_path = SOURCE / "docs/SOURCE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["source_revisions"].append({"revision": "s_denoise_repair_v3_D3_source_freeze", "date": "2026-10-16",
        "status": "CODE_TESTS_PASSED_SCIENTIFIC_GATE_PENDING", "source_root": str(SOURCE),
        "binding": {"path": str(path), "sha256": sha(path)}, "files": references})
    save(manifest_path, manifest)
    print(json.dumps({"status": value["status"], "files": len(references), "tests": value["all_tests"]}), flush=True)


if __name__ == "__main__":
    main()
