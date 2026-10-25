"""Root-only metadata preparation of the reviewed identity-input pin request.

Writes a READY plan, an absolute LF Slurm script and a request, without running
the producer, scheduler or quota command. Only <=2MiB source/proof files are
opened. The76 catalog input paths are neither opened nor stat'ed here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex


SMALL_LIMIT = 2 * 1024 ** 2
ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
PROJECT = Path("/share/home/zixiao/descriptor_analysis")
BENCHMARK = Path("/share/home/zixiao/benchmark_dataset")
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
JOB_NAME = "dv1_identity_input_pins_v1"
STAGE_FILES = (
    "workflows/expansion/identity_v2/__init__.py",
    "workflows/expansion/identity_v2/pin_inputs_v1.py",
    "workflows/expansion/identity_v2/pin_inputs_v1.sbatch",
    "workflows/expansion/identity_v2/test_pin_inputs_v1.py",
    "configs/data_v1/expansion/identity_v2/source_locator_catalog_v2.json",
    "configs/data_v1/expansion/identity_v2/input_pin_plan_template_v1.json",
    "docs/expansion/identity_source_locators_v2.md",
)
QUOTA_SOURCE_SHA = "913d1be2f282281afcc2fc3cb5b91b28d6d14b656eb1a3fbf6a1bbcf5e1d1ceb"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def absolute_path(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and
            not any(c in str(path) for c in "\r\n\t"), "Explicit clean absolute Linux path required")
    return path


def read_small(path):
    path = absolute_path(path)
    require(path.is_file() and not path.is_symlink(), "Regular nonsymlink small source required: " + str(path))
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(before.st_size <= SMALL_LIMIT, "Source exceeds2MiB metadata limit: " + str(path))
        raw = stream.read(SMALL_LIMIT + 1)
        after = os.fstat(stream.fileno())
    frame = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    require(len(raw) == before.st_size and len(raw) <= SMALL_LIMIT and frame(before) == frame(after),
            "Source changed during bounded small read: " + str(path))
    return raw, {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def file_ref(path):
    """Same path/bytes/SHA fields as submit_reviewed.file_ref, with a hard cap."""
    return read_small(path)[1]


def load_small(path):
    raw, ref = read_small(path)
    return json.loads(raw), ref


def unique_refs(refs):
    result = {}
    for ref in refs:
        require(set(ref) == {"path", "bytes", "sha256"} and type(ref["bytes"]) is int and
                0 <= ref["bytes"] <= SMALL_LIMIT and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]),
                "Only exact small path/bytes/SHA sources may enter the login guard")
        require(ref["path"] not in result or result[ref["path"]] == ref, "Conflicting small source pins")
        result[ref["path"]] = ref
    return list(result.values())


def write_json_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_catalog(catalog):
    require(catalog["schema"] == "expansion_identity_source_locator_catalog_v2" and
            catalog["status"] == "HISTORICAL_LOCATORS_ONLY_CURRENT_HASH_AND_ALL_SPLIT_PROOFS_PENDING",
            "Use the frozen historical-locator catalog, without claiming current data proof")
    inputs = catalog["inputs"]
    require(len(inputs) == 76 and len({r["source_id"] for r in inputs}) == 76 and
            len({r["path"] for r in inputs}) == 76 and len(catalog["metadata_authorities"]) == 8,
            "The full reviewed76-path/eight-authority scope must stay intact")
    require(sum(r["required"] is True for r in inputs) == 68 and
            all(type(r["required"]) is bool for r in inputs), "Keep all68 required and8 optional locator tasks")
    for item in inputs:
        path = absolute_path(item["path"])
        require(path.is_relative_to(PROJECT) or path.is_relative_to(BENCHMARK), "Catalog locator outside reviewed roots")
    expected = {"v1_formal": 11231854, "v1_embargo4900": 4900, "expansionrx_train": 5326,
                "expansionrx_test": 2282, "ledger_cyp_sources": 2003, "ledger_cyp_folds": 2003,
                "ledger_az_sources": 120, "ledger_az_folds": 109, "qm7_raw_mat_Z_only": 7165,
                "qm9_raw_original_archive": 133885, "ledger_qm_source_records": 141050}
    by_id = {r["source_id"]: r for r in inputs}
    require(all(by_id[name]["expected_records"] == count for name, count in expected.items()),
            "Original whole-source counts were narrowed or changed")
    datasets = {r["dataset"]: r for r in catalog["datasets"]}
    required_molnet = {"BACE", "BBBP", "ClinTox", "ESOL", "FreeSolv", "HIV", "Lipophilicity", "MUV",
                       "PCBA", "PDBbind", "QM7", "QM7b", "QM8", "QM9", "SIDER", "Tox21", "ToxCast"}
    require(set(datasets["moleculenet"]["required_subdatasets"]) == required_molnet and
            len(datasets["tdc_admet"]["required_subdatasets"]) == 22,
            "External17-MoleculeNet/22-TDC scope must remain pending and complete")
    return inputs


def materialize(repository, run_root, reviewer):
    require(reviewer == "root" and os.name == "posix" and os.getuid() == 1278,
            "Only reviewing Root may invoke this metadata helper on the authorized Linux account")
    repo, root = absolute_path(repository), absolute_path(run_root)
    require(root == ROOT and repo == ROOT / "repository" and
            Path(__file__).absolute() == repo / "workflows/expansion/identity_v2/materialize_input_pins_v1.py",
            "Root must first merge/review the helper in the explicit integrated repository")
    stage_refs = [file_ref(repo / name) for name in STAGE_FILES]
    catalog, catalog_ref = load_small(repo / STAGE_FILES[4])
    inputs = validate_catalog(catalog)
    # These are the eight actual small historical locator authorities. Their
    # SHA checks do not replace current full source hashes/counts on compute20.
    metadata_refs = unique_refs(catalog["metadata_authorities"])
    require(len(metadata_refs) == 8 and all(file_ref(r["path"]) == r for r in metadata_refs),
            "A bound historical locator metadata source changed")
    plan, template_ref = load_small(repo / STAGE_FILES[5])
    require(plan["schema"] == "identity_only_physical_input_pin_plan_v1" and
            plan["workers"] == 16 and plan["peak_output_cap_bytes"] == 32 * 1024 ** 2 and
            plan["budget"]["memory_gib"] == 4 and plan["budget"]["wall_seconds"] == 3600,
            "Keep the reviewed16-worker/4GiB/1h/32MiB producer plan")
    names = ("identity_v2/pin_inputs_v1.py", "identity_v2/pin_inputs_v1.sbatch", "identity_v2/__init__.py",
             "common.py", "download_raw_v1.py", "source.py", "__init__.py")
    plan.update(status="READY", source_catalog=catalog_ref,
                code_sources=[file_ref(repo / "workflows/expansion" / name) for name in names],
                quota={"mode": "published_receipt", "path": str(root / "control/pubchem_quota_feed_v1.json")},
                output_root=str(root / "artifacts/expansion/identity/source_pins_v1"))
    publisher = file_ref(root / "control/publish_fresh_pubchem_quota_v1.py")
    require(publisher["bytes"] == 1705 and publisher["sha256"] == QUOTA_SOURCE_SHA, "Reviewed quota publisher source changed")
    plan["quota_publisher_source"] = publisher
    # Do not open the live feed here: the producer consumes an actual <=300s
    # task-owned observation at job start and stops if it is stale or invalid.
    plan_path = root / "control/requests/identity_input_pin_ready_v1.json"
    script_path = root / "control/scripts" / (JOB_NAME + ".sbatch")
    request_path = root / "control/requests" / (JOB_NAME + ".json")
    intent_path = root / "control/submissions" / (JOB_NAME + ".intent.json")
    for path in (plan_path, script_path, request_path, intent_path, Path(plan["output_root"]),
                 root / "control/submissions" / (JOB_NAME + ".json"),
                 root / "control/submissions" / (JOB_NAME + ".verification.json")):
        require(not path.exists() and not path.is_symlink(), "Destination exists; retain it and audit before retry: " + str(path))
    sources = unique_refs([*stage_refs, template_ref, catalog_ref, *metadata_refs, publisher, *plan["code_sources"],
                           file_ref(Path(__file__).absolute()),
                           file_ref(repo / "workflows/data_v1_final/execution/submit_reviewed.py")])
    data_paths = {r["path"] for r in inputs}
    require(not data_paths.intersection(r["path"] for r in sources), "Catalog data must not enter login source-body hashes")
    log_path = root / "control" / (JOB_NAME + "_%j.out")
    require(not any(c.isspace() for c in str(log_path)), "Slurm output directive needs a whitespace-free absolute path")
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
exec {quote(PYTHON)} -B -m workflows.expansion.identity_v2.pin_inputs_v1 --plan {quote(str(plan_path))} --root-submit-intent {quote(str(intent_path))}
"""
    require(script.startswith("#!/bin/bash\n") and "\r" not in script, "LF-only Slurm script required")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_new(plan_path, plan)
    with script_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(script)
        stream.flush()
        os.fsync(stream.fileno())
    request = {
        "kind": "analysis", "node": "compute-0-20", "cpus": 16, "memory_gib": 4, "wall_seconds": 3600,
        "estimated_peak_output_bytes": 32 * 1024 ** 2, "pilot": True, "estimated_total_core_hours": 16,
        "script_reference": file_ref(script_path), "source_references": unique_refs([*sources, file_ref(plan_path)]),
        "data_references": [],
        "data_locator_authorization": {
            "schema": "BOUND_LOCATOR_CATALOG_FOR_FIRST_CURRENT_PIN_V1", "source_catalog": catalog_ref,
            "locator_count": 76, "current_data_pins_created_only_on_compute": True,
            "locators": [{k: item[k] for k in ("source_id", "path", "kind", "required")} for item in inputs],
        },
        "root_review": {
            "status": "APPROVED", "reviewer": reviewer,
            "observed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            "scope": "First current opaque SHA/stable-stat/independent identity-only counts for all76 catalog locators; eight exact small metadata authorities. Whole formal11231854+embargo4900, ExpansionRx train/test, CYP2003, AZraw120/folds109, QM7Z-only7165 and originalQM9133885 scope retained.",
            "checks": "Root personally invokes the reviewed materializer after acceptance of the seven-file producer and its three synthetic/static checks; all current source refs are small and exact. No locator data body or large file stat was read during materialization. Review this new request/script before separate immutable submission.",
            "budget": "Node20 ordinary16CPU/4GiB/1h ceiling,32MiB output and200GB quota reserve.16 bounded I/O workers; archived metadata/footer memory remains unmeasured, so retain4GiB. Existing plan2-15min range is a planning estimate; optional archive/current storage timing remains unknown. repo:deps matches reviewed environment.",
            "quota": "Existing published task-owned actual quota must be<=300s at execution; feed is not read, written, refreshed or relabeled by this materializer.",
            "gates": "No molecular features/targets/chemistry, identity export, all-source/all-split acceptance or released pool. Missing optional locators stayPENDING; required missing/changed SHA/count stops. External TDC22/MoleculeNet17/MARCEL/COCONUT scope remainsPENDING; do not narrow it.",
            "failure": "Preserve all output and scheduler evidence; no automatic submission/retry, extra download or source substitution.",
        },
    }
    write_json_new(request_path, request)
    print(json.dumps({"status": "PREPARED_NOT_SUBMITTED", "request": file_ref(request_path),
                      "plan": file_ref(plan_path), "script": file_ref(script_path), "job_name": JOB_NAME,
                      "expected_intent": str(intent_path), "output": plan["output_root"],
                      "stage_file_references": stage_refs, "metadata_authority_count": len(metadata_refs),
                      "catalog_input_count": len(inputs), "kinds": dict(Counter(r["kind"] for r in inputs)),
                      "source_reference_max_bytes": max(r["bytes"] for r in request["source_references"]),
                      "catalog_data_bodies_or_stats_read": False, "quota_feed_read_or_written": False}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--reviewer", required=True, choices=["root"])
    args = parser.parse_args()
    materialize(args.repository, args.run_root, args.reviewer)


if __name__ == "__main__":
    main()
