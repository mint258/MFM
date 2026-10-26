"""Original full branch reused; profile-to-full scope expansion is explicit."""
from __future__ import annotations

import ast
from pathlib import Path

from workflows.data_v1_final.execution.queue_v1 import shared
from .policy import SCOPE


BASE = "workflows/expansion/identity_v3/export_v2.py"
PROFILE = "workflows/expansion/cpu_auto_memory_v1/identity_profile.py"
EDITS = [("from .. import full_queue_v1 as execution", "from . import runtime as execution"),
    ("Profile or export all original local identities under a new queued64GiB scope.",
     "Independent full original-source identity export after the actual profile."),
    ("from . import projection_v3 as projection", "from ..identity_v3 import projection_v3 as projection"),
    ("from . import cohorts, input_authority, readers", "from ..identity_v3 import cohorts, input_authority, readers"),
    ('SCOPES = {"profile": "sb5_identity_profile_source_roles_v4", "full": "sb5_identity_full_source_roles_v4"}',
     'SCOPES = {"full": "' + SCOPE + '"}')]


def replace_once(value, before, after):
    shared.need(value.count(before) == 1, "UNIQUE_DECLARED_FULL_ENTRY_EDIT_REQUIRED")
    return value.replace(before, after, 1)


def functions(raw):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}


def source_proof(profile_source_ref):
    original_path, variant_path = shared.REPO / BASE, Path(__file__).parent / "run.py"
    original_raw, variant_raw = shared.read_small(original_path), shared.read_small(variant_path)
    expected, inverse = original_raw.decode(), variant_raw.decode()
    for before, after in EDITS:
        expected = replace_once(expected, before, after)
    shared.need(expected.encode() == variant_raw, "UNDECLARED_FULL_PRODUCER_EDIT")
    for before, after in reversed(EDITS):
        inverse = replace_once(inverse, after, before)
    shared.need(inverse.encode() == original_raw and functions(original_raw) == functions(variant_raw),
                "ORIGINAL_FULL_BRANCH_FUNCTION_AST_OR_INVERSE_BYTES_DIFFER")
    shared.need(shared.pin(shared.REPO / PROFILE) == profile_source_ref and
                functions(shared.read_small(profile_source_ref["path"])) == functions(variant_raw),
                "ACTUAL_ACCEPTED_PROFILE_SCIENTIFIC_FUNCTIONS_DIFFER")
    return {"schema": "SB5_FULL_IDENTITY_REUSES_ORIGINAL_FULL_BRANCH_V1", "status": "PASS",
        "baseline_reference": shared.pin(original_path), "accepted_profile_source_reference": profile_source_ref,
        "variant_reference": shared.pin(variant_path), "proof_source_reference": shared.pin(Path(__file__)),
        "inverse_full_file_bytes_equal": True, "all_original_function_ASTs_identical": True,
        "accepted_profile_function_ASTs_identical": True,
        "original_full_mode_branch_reused": True, "scope_expansion_from_profile_to_full": True,
        "resource_only_change_claimed": False, "scientific_scope_key": SCOPE,
        "declared_changes": "execution/identity library imports, module docstring, SCOPES constant full-only/new key"}
