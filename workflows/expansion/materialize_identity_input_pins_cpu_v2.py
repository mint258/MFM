"""Root metadata-only preparation of the exact76-input CPU-v2 source pin pilot.

No scheduler, network, quota refresh, scientific import or data-body stat/read.
Consumes the actual Root scope policy/decision and accepted original request.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex


ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
SMALL_LIMIT = 2 * 1024 ** 2
CAP = 32 * 1024 ** 2
CENTRAL_NAMES = ("policy.py", "runtime.py", "probe_memory.py", "launch.py", "submit_cpu_pilot_v1.py",
                 "runtime_v2.py", "launch_v2.py", "submit_cpu_pilot_v2.py")
SCOPES = {
    "identity_source_pins_76": {
        "job": "dv1_identity_source_pins_cpu_v2", "base_plan": "identity_input_pin_ready_v1.json",
        "base_schema": "identity_only_physical_input_pin_plan_v1",
        "schema": "identity_only_physical_input_pin_cpu_plan_v1",
        "baseline": "identity_v2/pin_inputs_cpu_v1.py", "variant": "identity_v2/pin_inputs_cpu_v2.py",
        "module": "workflows.expansion.identity_v2.pin_inputs_cpu_v2",
        "output": "identity/identity_source_pins_cpu_v2", "functions": ["physical_stat", "describe_identity_source", "pin_one"],
    },
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_small(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and path.is_file() and not path.is_symlink(), "Literal small source required")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(before.st_size <= SMALL_LIMIT, "Login source exceeds2MiB: " + str(path))
        raw = stream.read(SMALL_LIMIT + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size <= SMALL_LIMIT and
            (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) ==
            (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size), "Small source changed while read")
    return raw


def ref(path):
    raw = read_small(path)
    return {"path": str(Path(path)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path):
    return json.loads(read_small(path))


def verify_small(pin):
    require(set(pin) == {"path", "bytes", "sha256"} and pin["bytes"] <= SMALL_LIMIT and ref(pin["path"]) == pin,
            "Root small source pin changed: " + str(pin.get("path")))


def unique(pins):
    result = {}
    for pin in pins:
        require(pin["path"] not in result or result[pin["path"]] == pin, "Conflicting source pin")
        result[pin["path"]] = pin
    return list(result.values())


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def materialize(repository, run_root, reviewer, node, scope_key):
    repo, root = Path(repository), Path(run_root)
    require(os.name == "posix" and os.getuid() == 1278 and reviewer == "root" and root == ROOT and repo == ROOT / "repository" and
            Path(__file__).absolute() == repo / "workflows/expansion/materialize_identity_input_pins_cpu_v2.py",
            "Root must first merge/review and personally invoke the metadata helper in the integrated repository")
    require(node in {"compute-0-2", *(f"compute-0-{i}" for i in range(8, 20))}, "Only actual CPU2/8-19 nodes are allowed; never21")
    require(scope_key == "identity_source_pins_76", "Only the exact original76-input identity source pin scope is allowed")
    selection = SCOPES[scope_key]
    decision_path = repo / "configs/data_v1/run_decisions_v4.json"
    policy_path = repo / "configs/data_v1/cpu_analysis_small_scopes_v1.json"
    policy = load(policy_path)
    load(decision_path)  # Validate actual small JSON framing; authority belongs to Root's new central policy.
    scope = policy["scopes"][scope_key]
    require(scope["memory_gib"] == 4 and scope["wall_seconds"] == 3600 and scope["output_cap_bytes"] == CAP,
            "Keep exact reviewed16CPU/4GiB/1h/32MiB scientific scope")
    require(scope["parameters"] == {"sources": 76, "metadata_authorities": 8,
                                    "identity_export_or_all_source_acceptance": False},
            "Keep the original finite76-input/eight-metadata/no-acceptance scope")
    base_ref = scope["base_request_reference"]
    verify_small(base_ref)
    base = load(base_ref["path"])
    base_sources = [base["script_reference"], *base["source_references"]]
    for pin in base_sources:
        verify_small(pin)
    matches = [pin for pin in base["source_references"] if Path(pin["path"]).name == selection["base_plan"]]
    require(len(matches) == 1, "Exact accepted original READY plan absent from base request")
    plan = load(matches[0]["path"])
    require(plan["schema"] == selection["base_schema"] and plan["status"] == "READY" and plan["peak_output_cap_bytes"] == CAP,
            "Wrong original finite-science plan")
    catalog = load(plan["source_catalog"]["path"])
    require(catalog["schema"] == "expansion_identity_source_locator_catalog_v2" and
            len(catalog["inputs"]) == len({r["path"] for r in catalog["inputs"]}) == 76 and
            len(catalog["metadata_authorities"]) == 8 and plan["workers"] == 16 and base["data_references"] == [],
            "Keep all76 first-current-pin locators and eight small authorities; never fabricate current data SHA")
    central = repo / "workflows/data_v1_final/execution/cpu_analysis_v1"
    central_refs = [ref(central / name) for name in CENTRAL_NAMES]
    legacy = ref(repo / "workflows/data_v1_final/execution/submit_reviewed.py")
    helper = repo / "workflows/expansion/verify_prefix_science_cpu_v1.py"
    verify_ref = ref(helper)
    spec = importlib.util.spec_from_file_location("_reviewed_source_ast_only", helper)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)  # This reviewed helper imports stdlib only; no runtime/RDKit import.
    baseline, variant = (repo / "workflows/expansion" / selection[k] for k in ("baseline", "variant"))
    proof = verifier.compare(baseline, variant, selection["functions"] or verifier.NAMES)
    original_import = b"from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime as cpu_runtime\n"
    new_import = b"from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime_v2 as cpu_runtime\n"
    original_bytes, variant_bytes = read_small(baseline), read_small(variant)
    require(original_bytes.count(original_import) == variant_bytes.count(new_import) == 1 and
            variant_bytes.replace(new_import, original_import) == original_bytes,
            "Entire producer must differ only by the one reviewed runtime import, including every scientific/metadata function byte")
    reverse_proof = {"status": "ONE_CENTRAL_RUNTIME_IMPORT_REPLACEMENT_ONLY", "baseline": ref(baseline), "variant": ref(variant),
                     "whole_module_reverse_edit_bytes_equal": True, "all_scientific_and_metadata_function_bytes_equal": True}
    plan.update(schema=selection["schema"], cpu_decision_reference=ref(decision_path),
                central_runtime_reference=ref(central / "runtime_v2.py"), scope_policy_reference=ref(policy_path),
                cpu_scientific_ast_equivalence=proof, cpu_runtime_import_reverse_edit_proof=reverse_proof,
                output_root=str(root / "artifacts/expansion" / selection["output"]))
    added = [ref(baseline), ref(variant), verify_ref, *central_refs]
    plan["code_sources"] = unique([*plan["code_sources"], *added])
    plan_path = root / "control/requests" / (selection["job"] + "_plan.json")
    script_path = root / "control/scripts" / (selection["job"] + ".sbatch")
    request_path = root / "control/requests" / (selection["job"] + ".json")
    intent_path = root / "control/submissions" / (selection["job"] + ".intent.json")
    for path in (plan_path, script_path, request_path, intent_path, Path(plan["output_root"]),
                 root / "control/submissions" / (selection["job"] + ".json"),
                 root / "control/submissions" / (selection["job"] + ".verification.json"),
                 root / "artifacts/cpu_analysis_guards" / selection["job"]):
        require(not path.exists() and not path.is_symlink(), "New CPU destination exists; preserve and audit, never retry automatically: " + str(path))
    authority_refs = scope.get("authority_references", [])
    for pin in authority_refs:
        verify_small(pin)
    sources = unique([base_ref, *base_sources, *authority_refs, *plan["code_sources"], legacy, ref(Path(__file__).absolute()),
                      ref(decision_path), ref(policy_path)])
    require(all(pin["bytes"] <= SMALL_LIMIT for pin in sources), "Only small refs may reach login hash guard")
    data_paths = {pin["path"] for pin in base["data_references"]}
    data_paths |= {row["path"] for row in catalog["inputs"]}
    require(not data_paths.intersection(pin["path"] for pin in sources), "Large data body entered source refs")
    quote = shlex.quote
    log_path = root / "control" / (selection["job"] + "_%j.out")
    require(not any(c.isspace() for c in str(log_path)), "Whitespace-free absolute Slurm log path required")
    script = f"""#!/bin/bash
#SBATCH --job-name={selection['job']}
#SBATCH --partition=cpu
#SBATCH --nodelist={node}
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
exec {quote(PYTHON)} -B -m workflows.data_v1_final.execution.cpu_analysis_v1.launch_v2 --intent {quote(str(intent_path))} -- {quote(PYTHON)} -B -m {selection['module']} --plan {quote(str(plan_path))} --root-submit-intent {quote(str(intent_path))}
"""
    require("\r" not in script and script.startswith("#!/bin/bash\n"), "LF-only absolute Slurm script required")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    write_new(plan_path, plan)
    with script_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(script)
        stream.flush()
        os.fsync(stream.fileno())
    request = {
        "kind": "analysis", "pilot": True, "partition": "cpu", "node": node, "cpus": 16,
        "memory_gib": 4, "wall_seconds": 3600, "estimated_peak_output_bytes": CAP + 32 * 1024 ** 2,
        "estimated_total_core_hours": 16, "resource_policy": "CPU_BOUNDED_TEST_LIVE_MEMORY_V1",
        "scope_key": scope_key, "scope_parameters": scope["parameters"],
        "decision_reference": ref(decision_path), "scope_policy_reference": ref(policy_path),
        "base_request_reference": base_ref, "formal_generation_authorized": False,
        "script_reference": ref(script_path), "source_references": unique([*sources, ref(plan_path)]),
        "data_references": base["data_references"],
        "root_review": {
            "status": "APPROVED", "reviewer": reviewer,
            "observed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            "scope": "Exactly the unchanged finite science of the bound original request and Root CPU scope parameters; CPU2/8-19 only, no node21, no repair/exclusion/identity-export/pool or training release.",
            "checks": "Root personal metadata materialization checks actual base refs, stdlib scientific-function AST equivalence and whole-module reverse-edit byte equality for exactly one central runtime import. No scientific/test function runs. Root must separately validate/review and submit with submit_cpu_pilot_v2.",
            "budget": "Original16CPU/4GiB/1h and32MiB scientific cap plus32MiB central monitor; actual CPU memory admission and live cooperative STOP at stage/record boundaries. No signals or process killing. Formal full/generation64GiB+85pct declared-memory requirements are unchanged.",
            "quota": "Published feed is not read/written or relabeled by this helper. Actual compute-stage feed freshness<=300s and200GB reserve include both science and monitor64MiB budget.",
        },
    }
    if "data_locator_authorization" in base:
        request["data_locator_authorization"] = base["data_locator_authorization"]
    write_new(request_path, request)
    print(json.dumps({"status": "PREPARED_CPU_REQUEST_NOT_SUBMITTED", "scope_key": scope_key, "node": node,
                      "request": ref(request_path), "plan": ref(plan_path), "script": ref(script_path),
                      "science_ast_equivalence": proof, "whole_module_reverse_edit_proof": reverse_proof,
                      "data_body_or_stat_read": False, "quota_feed_read_or_written": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--reviewer", choices=["root"], required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--scope-key", choices=sorted(SCOPES), default="identity_source_pins_76")
    args = parser.parse_args()
    materialize(args.repository, args.run_root, args.reviewer, args.node, args.scope_key)


if __name__ == "__main__":
    main()
