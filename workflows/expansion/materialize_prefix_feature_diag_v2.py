"""Root-invoked, metadata-only preparation of the three-CID diagnostic request.

This command writes three new files. It never invokes a scheduler, imports the
diagnostic/RDKit, opens the raw body, or refreshes/relabels a quota observation.
Run only after Root reviews and merges the diagnostic source and this helper.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex


SMALL_LIMIT = 2 * 1024 ** 2
JOB_NAME = "dv1_prefix_feature_diag_v1"
EXPECTED_RUN_ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
RAW_FILE = {
    "path": str(EXPECTED_RUN_ROOT / "artifacts/expansion/raw/pubchem_20261025_v1/CID-SMILES.gz"),
    "bytes": 1488715010,
    "sha256": "2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def absolute_path(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and
            not any(char in str(path) for char in "\r\n\t"), "Explicit clean absolute Linux paths required")
    return path


def read_small(path):
    """Bounded equivalent of submit_reviewed.file_ref for actual small sources."""
    path = absolute_path(path)
    require(path.is_file() and not path.is_symlink(), "Small source must be a regular, nonsymlink file: " + str(path))
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(before.st_size <= SMALL_LIMIT, "Source exceeds the 2MiB login metadata limit: " + str(path))
        raw = stream.read(SMALL_LIMIT + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) <= SMALL_LIMIT and len(raw) == before.st_size and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            "Small source changed while read: " + str(path))
    return raw, {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def file_ref(path):
    return read_small(path)[1]


def load_small(path):
    raw, ref = read_small(path)
    return json.loads(raw), ref


def load_bound(ref):
    require(set(ref) == {"path", "bytes", "sha256"} and type(ref["bytes"]) is int and
            0 <= ref["bytes"] <= SMALL_LIMIT and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]),
            "Expected a small exact path/bytes/SHA reference")
    value, actual = load_small(ref["path"])
    require(actual == ref, "Bound small metadata changed: " + ref["path"])
    return value


def unique_refs(refs):
    result = {}
    for ref in refs:
        require(ref["bytes"] <= SMALL_LIMIT, "Large bodies cannot enter source_references")
        require(ref["path"] not in result or result[ref["path"]] == ref, "Conflicting source pins")
        result[ref["path"]] = ref
    return list(result.values())


def write_json_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def materialize(repository, run_root, reviewer):
    require(reviewer == "root", "This helper is for the reviewing Root agent's personal invocation")
    require(os.name == "posix" and os.getuid() == 1278, "Run metadata preparation on the authorized Linux account")
    repo, root = absolute_path(repository), absolute_path(run_root)
    require(root == EXPECTED_RUN_ROOT and repo == root / "repository", "Use the explicitly reviewed integrated repository and run root")
    require(Path(__file__).absolute() == repo / "workflows/expansion/materialize_prefix_feature_diag_v2.py",
            "Merge and review the helper in the integrated repository before Root runs it")
    require(repo.is_dir(), "Reviewed repository is absent")
    template = repo / "configs/data_v1/expansion/prefix_feature_diagnostic_plan_template_v1.json"
    plan, template_ref = load_small(template)
    require(plan["schema"] == "pubchem_prefix_feature_stage_diagnostic_plan_v1" and
            plan["expected_prefix_job_id"] == "4520427" and plan["target_cids"] == [7, 52, 53] and
            plan["max_prefix_rows"] == 10000 and plan["peak_output_cap_bytes"] == 32 * 1024 ** 2 and
            all(plan[key] is False for key in ("chemical_rules_changed", "feature_repair_applied",
                                               "pool_or_screening_release_authorized")),
            "Template must authorize only the exact three-CID, unchanged-rule diagnostic")
    old = load_bound(plan["prefix_receipt"])
    old_plan = load_bound(plan["prefix_plan"])
    # The old rejection JSONL is verified as opaque small bytes, never as JSON.
    require(file_ref(plan["prefix_rejections"]["path"]) == plan["prefix_rejections"], "Old rejection JSONL changed")
    raw = load_bound(plan["raw_receipt"])
    require(old["schema"] == "PUBCHEM_BOUNDED_PREFIX_PILOT_V2" and old["job_id"] == "4520427" and
            old["status"] == "BOUNDED_INPUT_PREFIX_PILOT_NOT_DECONTAMINATED" and old["node"] == "compute-0-20" and
            old["plan"] == plan["prefix_plan"] and old["all_rejections"] == plan["prefix_rejections"] and
            old["source_receipt"] == plan["raw_receipt"], "Expected exact original completed prefix evidence")
    require(raw["schema"] == "pubchem_download_complete_v1" and raw["job_id"] == "4520348" and
            raw["status"] == "RAW_ACQUIRED_NO_CHEMICAL_SCREENING" and raw["hostname"] == "compute-0-20" and
            raw["uid"] == 1278 and raw["file"] == RAW_FILE and raw["gzip"]["gzip_read_to_eof_crc_validated"] is True,
            "Expected exact completed official raw producer, without opening its data body")
    require(plan["data_authorization_receipts"] == [plan["raw_receipt"]] and
            plan["authorized_data_pin_jobs"] == ["4520348"] and plan["allow_small_fixture_legacy_authority"] is False,
            "Raw authority must stay exact and cannot use fixture authorization")
    quota_source = old_plan["quota_publisher_source"]
    require(quota_source["path"] == str(root / "control/publish_fresh_pubchem_quota_v1.py") and
            file_ref(quota_source["path"]) == quota_source and
            old_plan["quota_feed"] == str(root / "control/pubchem_quota_feed_v1.json"), "Actual old quota publisher source changed")
    # The live feed is deliberately not read or pinned: the compute consumer must
    # observe its actual task-owned, <=300s record when the allocation starts.
    plan["quota_feed"] = old_plan["quota_feed"]
    plan["quota_publisher_source"] = quota_source
    names = ("prefix_feature_diagnostic_v1.py", "prefix_feature_diagnostic_v1.sbatch",
             "common.py", "screen.py", "data_authority_v1.py", "__init__.py")
    plan["code_sources"] = [file_ref(repo / "workflows/expansion" / name) for name in names]
    by_name = {Path(ref["path"]).name: ref for ref in plan["code_sources"]}
    for name in ("screen.py", "common.py", "data_authority_v1.py", "__init__.py"):
        old_ref = next(ref for ref in old_plan["code_sources"] if Path(ref["path"]).name == name)
        require(by_name[name] == old_ref, "Frozen original prefix runtime changed: " + name)
    plan["status"] = "READY"
    output = root / "artifacts/expansion/diagnostics/prefix_features_v1"
    plan["output_root"] = str(output)
    request_dir, script_dir = root / "control/requests", root / "control/scripts"
    plan_path = request_dir / "prefix_feature_diagnostic_ready_v1.json"
    script_path = script_dir / (JOB_NAME + ".sbatch")
    request_path = request_dir / (JOB_NAME + ".json")
    intent_path = root / "control/submissions" / (JOB_NAME + ".intent.json")
    for path in (plan_path, script_path, request_path, intent_path, output,
                 root / "control/submissions" / (JOB_NAME + ".json"),
                 root / "control/submissions" / (JOB_NAME + ".verification.json")):
        require(not path.exists() and not path.is_symlink(), "New diagnostic destination already exists; audit before any retry: " + str(path))
    log_path = root / "control" / (JOB_NAME + "_%j.out")
    require(not any(char.isspace() for char in str(log_path)), "Slurm output directive requires a whitespace-free absolute path")
    quote = shlex.quote
    script = f"""#!/bin/bash
#SBATCH --job-name={JOB_NAME}
#SBATCH --partition=all
#SBATCH --nodelist=compute-0-20
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output={log_path}
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={quote(str(repo) + ':' + DEPS)}
cd {quote(str(repo))}
exec {quote(PYTHON)} -B -m workflows.expansion.prefix_feature_diagnostic_v1 --plan {quote(str(plan_path))} --root-submit-intent {quote(str(intent_path))}
"""
    require("\r" not in script and script.startswith("#!/bin/bash\n"), "SBATCH must have LF only")
    # Read and pin every remaining small source before creating any destination.
    sources = unique_refs([file_ref(repo / "workflows/data_v1_final/execution/submit_reviewed.py"),
                           file_ref(Path(__file__).absolute()), template_ref,
                           file_ref(repo / "docs/expansion/prefix_feature_diagnostic_v1.md"),
                           plan["prefix_receipt"], plan["prefix_plan"], plan["prefix_rejections"],
                           plan["raw_receipt"], quota_source, *plan["code_sources"]])
    require(all(ref["path"] != RAW_FILE["path"] for ref in sources), "Raw body must be absent from login source references")
    request_dir.mkdir(parents=True, exist_ok=True)
    script_dir.mkdir(parents=True, exist_ok=True)
    write_json_new(plan_path, plan)
    with script_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(script)
        stream.flush()
        os.fsync(stream.fileno())
    request = {
        "kind": "analysis", "node": "compute-0-20", "cpus": 16, "memory_gib": 4,
        "wall_seconds": 3600, "estimated_peak_output_bytes": 32 * 1024 ** 2,
        "pilot": True, "estimated_total_core_hours": 16,
        "script_reference": file_ref(script_path),
        "source_references": unique_refs([*sources, file_ref(plan_path)]),
        "data_references": [RAW_FILE],
        "root_review": {
            "status": "APPROVED", "reviewer": reviewer,
            "observed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            "scope": "Only CID7,52,53 from the same official <=10000-row prefix; reproduce frozen screen.features first, then record exact stage tracebacks. No feature repair or chemical-rule change.",
            "checks": "Root personal invocation of the reviewed materializer records this scope. Exact completed prefix4520427 and raw4520348 small evidence/current frozen runtime pins are checked without reading raw data. Review generated request and script before separate immutable submission.",
            "budget": "Node20 ordinary16CPU/4GiB/1h ceiling,32MiB output and200GB quota reserve. Only3 case threads; raw1488715010B full SHA/stat check on compute20. Fresh published actual quota<=300s at execution; no quota feed relabel or login data-body hash.",
            "gates": "No pool/screening release, downstream decontamination acceptance, formal UFF/D export or training. Existing753 failures, old427 outputs and full414/source bytes stay intact.",
            "failure": "Retain partials and actual scheduler evidence; no automatic submission, retry, repair or exclusion.",
        },
    }
    write_json_new(request_path, request)
    print(json.dumps({"status": "PREPARED_NOT_SUBMITTED", "request": file_ref(request_path),
                      "plan": file_ref(plan_path), "script": file_ref(script_path),
                      "intent_expected_only_after_root_submission": str(intent_path), "output": str(output),
                      "job_name": JOB_NAME, "source_reference_max_bytes": max(r["bytes"] for r in request["source_references"]),
                      "raw_body_read": False, "quota_observation_refreshed": False}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--reviewer", required=True, choices=["root"])
    args = parser.parse_args()
    materialize(args.repository, args.run_root, args.reviewer)


if __name__ == "__main__":
    main()
