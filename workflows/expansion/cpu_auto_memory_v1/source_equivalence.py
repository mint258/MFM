"""Metadata-only inverse edits and actual scientific-function AST comparison."""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from workflows.data_v1_final.execution.queue_v1 import shared


BASES = {"identity_profile": "workflows/expansion/identity_v3/export_v2.py",
         "inventory": "workflows/expansion/pubchem_full_v1/inventory_v2.py",
         "official_head": "workflows/expansion/official_source_probe_v1/run.py"}
NEW_STARTUP = '''def startup(plan_path, proof_path):
    plan, proof, validation = execution.startup(plan_path, proof_path, __file__, scope=SCOPE)
    validate_plan(plan, proof["request"])
    need(proof["request"].get("data_references", []) == [], "HEADER_ONLY_NO_BODY_REFERENCES")
    return plan, proof, validation'''


def edits(key, baseline):
    pairs = [("from .. import full_queue_v1 as execution", "from . import runtime as execution")]
    if key == "identity_profile":
        pairs += [("Profile or export all original local identities under a new queued64GiB scope.",
                   "Original local identity profile with unspecified Slurm memory; science unchanged."),
                  ("from . import projection_v3 as projection", "from ..identity_v3 import projection_v3 as projection"),
                  ("from . import cohorts, input_authority, readers", "from ..identity_v3 import cohorts, input_authority, readers")]
    elif key == "official_head":
        pairs += [("Strict queued CPU64GiB official HEAD observations, never data acquisition.",
                   "CPU-default-memory official HEAD observations, never data acquisition."),
                  ("from workflows.data_v1_final.execution.queue_v1 import queue_contract, shared\n"
                   "from workflows.data_v1_final.execution.queue_v3 import contract as scope_contract",
                   "from workflows.data_v1_final.execution.queue_v1 import shared"),
                  ("from .catalog import", "from ..official_source_probe_v1.catalog import"),
                  ("from .transport import", "from ..official_source_probe_v1.transport import"),
                  ("from .test_probe import", "from ..official_source_probe_v1.test_probe import")]
        function = next(n for n in ast.parse(baseline).body if isinstance(n, ast.FunctionDef) and n.name == "startup")
        pairs.append((ast.get_source_segment(baseline, function), NEW_STARTUP))
    return pairs


def replace_once(raw, before, after):
    shared.need(raw.count(before) == 1, "EXACT_UNIQUE_RESOURCE_EDIT_REQUIRED")
    return raw.replace(before, after, 1)


def canonical_function(node):
    node = copy.deepcopy(node)
    for child in ast.walk(node):
        if isinstance(child, ast.ImportFrom) and child.module == "official_source_probe_v1.test_probe" and child.level == 2:
            child.module, child.level = "test_probe", 1
    return ast.dump(node, include_attributes=False)


def equivalence(baseline_plan):
    rows = []
    for key, path in BASES.items():
        old_path = shared.REPO / path
        variant_path = Path(__file__).parent / (key + ".py")
        original_raw, variant_raw = shared.read_small(old_path), shared.read_small(variant_path)
        original = original_raw.decode("utf-8")
        pairs = edits(key, original)
        expected, inverse = original, variant_raw.decode("utf-8")
        for before, after in pairs:
            expected = replace_once(expected, before, after)
        shared.need(expected.encode("utf-8") == variant_raw, "VARIANT_DIFFERS_OUTSIDE_REVIEWED_RESOURCE_EDITS")
        for before, after in reversed(pairs):
            inverse = replace_once(inverse, after, before)
        shared.need(inverse.encode("utf-8") == original_raw, "INVERSE_FULL_FILE_BYTES_DIFFER")
        baseline_functions = {n.name: n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef)}
        variant_functions = {n.name: n for n in ast.parse(variant_raw).body if isinstance(n, ast.FunctionDef)}
        shared.need(set(baseline_functions) == set(variant_functions), "FUNCTION_SET_CHANGED")
        excluded = {"startup"} if key == "official_head" else set()
        functions = [name for name in baseline_functions if name not in excluded]
        shared.need(all(canonical_function(baseline_functions[name]) == canonical_function(variant_functions[name])
                        for name in functions), "SCIENTIFIC_FUNCTION_AST_DIFFERS")
        rows.append({"entry": key, "baseline_reference": shared.pin(old_path), "variant_reference": shared.pin(variant_path),
            "inverse_full_file_bytes_equal": True, "scientific_functions_normalized_AST_identical": True,
            "scientific_functions_compared": functions, "explicit_resource_guard_replacement_functions": sorted(excluded),
            "resource_guard_AST_falsely_claimed_unchanged": False,
            "allowed_changes": "execution/relative imports, resource docstrings, HEAD startup guard only"})
    return {"schema": "SB5_CPU_AUTO_MEMORY_SOURCE_EQUIVALENCE_V1", "status": "PASS", "baseline_plan": baseline_plan,
        "proof_source_reference": shared.pin(Path(__file__)), "files": rows,
        "new_memory_policy": "SLURM_DEFAULT_UNSPECIFIED", "scheduler_memory_requested": False,
        "old_registered_sources_edited": False, "science_or_network_execution_used_for_this_proof": False}
