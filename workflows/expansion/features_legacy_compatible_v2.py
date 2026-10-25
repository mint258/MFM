"""Proposed-only compatibility dispatch; keep every frozen successful result.

Only the exact old ring-fragment KekulizeException can reach the already tested
generic-first candidate. No chemical rules, original files or pools are changed.
"""
from __future__ import annotations

import ast
from functools import lru_cache
import hashlib
from pathlib import Path

from . import features_generic_candidate_v1 as generic_fallback_module, screen
from .common import require


chemical_flags = screen.chemical_flags
rdkit_modules = screen.rdkit_modules
wp5_key = screen.wp5_key
evaluate_fragment_orders = generic_fallback_module.evaluate_fragment_orders
_legacy_features = screen.features
_fallback_features = generic_fallback_module.features_candidate
_FROZEN_FEATURE_CODE = screen.features.__code__
STRATEGY = "OLD_SUCCESS_PASSTHROUGH_EXACT_OLD_RING_KEKULIZE_ONLY"
PROOF_STATUS = "COMPOSITIONAL_OLD_SUCCESS_PASSTHROUGH_EXACT_RING_KEKULIZE_FALLBACK_V2"


@lru_cache(maxsize=1)
def _frozen_sanitize_site():
    path = Path(screen.__file__)
    raw = path.read_bytes()
    require(len(raw) <= 2 * 1024 ** 2 and hashlib.sha256(raw).hexdigest() == generic_fallback_module.FROZEN_SCREEN_SHA,
            "Exact frozen screen source is required before a fallback")
    tree = ast.parse(raw)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "features")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call) and
             isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and
             node.func.value.id == "Chem" and node.func.attr == "SanitizeMol"]
    require(len(calls) == 1 and len(calls[0].args) == 1 and isinstance(calls[0].args[0], ast.Name) and
            calls[0].args[0].id == "frag" and calls[0].keywords == [] and calls[0].lineno == 70 and
            _FROZEN_FEATURE_CODE is screen.features.__code__ and _FROZEN_FEATURE_CODE.co_filename == str(path) and
            _FROZEN_FEATURE_CODE.co_firstlineno == function.lineno,
            "Fallback must point to the unique exact old Chem.SanitizeMol(frag) code/line")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "function": "features",
            "function_first_line": function.lineno, "sanitize_line": calls[0].lineno,
            "traceback_code_object_identity_required": True}


def _kekulize_type():
    Chem, *_ = rdkit_modules()
    return Chem.KekulizeException


def _is_exact_old_ring_failure(exc):
    if type(exc) is not _kekulize_type():
        return False
    site = _frozen_sanitize_site()
    frame = exc.__traceback__
    while frame is not None:
        if frame.tb_frame.f_code is _FROZEN_FEATURE_CODE and frame.tb_lineno == site["sanitize_line"]:
            return True
        frame = frame.tb_next
    return False


def features_candidate(cid, smiles, ordinal):
    try:
        return _legacy_features(cid, smiles, ordinal)
    except _kekulize_type() as exc:
        if not _is_exact_old_ring_failure(exc):
            raise
        return _fallback_features(cid, smiles, ordinal)


def source_scope_proof():
    site = _frozen_sanitize_site()
    require(chemical_flags is screen.chemical_flags and rdkit_modules is screen.rdkit_modules and
            wp5_key is screen.wp5_key and _legacy_features is screen.features and
            _fallback_features is generic_fallback_module.features_candidate and
            evaluate_fragment_orders is generic_fallback_module.evaluate_fragment_orders,
            "Compatibility dispatch/import aliases changed")
    raw = Path(__file__).read_bytes()
    require(len(raw) <= 2 * 1024 ** 2, "Small compatibility source required")
    tree = ast.parse(raw)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    expected = ast.parse('''def features_candidate(cid, smiles, ordinal):
    try:
        return _legacy_features(cid, smiles, ordinal)
    except _kekulize_type() as exc:
        if not _is_exact_old_ring_failure(exc):
            raise
        return _fallback_features(cid, smiles, ordinal)
''').body[0]
    expected_matcher = ast.parse('''def _is_exact_old_ring_failure(exc):
    if type(exc) is not _kekulize_type():
        return False
    site = _frozen_sanitize_site()
    frame = exc.__traceback__
    while frame is not None:
        if frame.tb_frame.f_code is _FROZEN_FEATURE_CODE and frame.tb_lineno == site["sanitize_line"]:
            return True
        frame = frame.tb_next
    return False
''').body[0]
    canonical = ast.dump(functions["features_candidate"], include_attributes=False)
    require(canonical == ast.dump(expected, include_attributes=False) and
            ast.dump(functions["_is_exact_old_ring_failure"], include_attributes=False) ==
            ast.dump(expected_matcher, include_attributes=False), "Wrapper or exact type/traceback dispatch differs")
    return {"status": PROOF_STATUS, "strategy": STRATEGY, "old_success_returns_original_result_object": True,
            "exception_type_test": "type(exc) is Chem.KekulizeException", "frozen_old_ring_site": site,
            "other_exceptions_rethrown": True, "new_chemical_function_defined": False,
            "chemical_function_objects_identical": True, "wrapper_AST_equals_original_features_AST": False,
            "wrapper_dispatch_ast_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "compatibility_source_sha256": hashlib.sha256(raw).hexdigest(),
            "nested_generic_fallback_proof": generic_fallback_module.source_scope_proof(),
            "repair_applied": False, "pool_modified": False}


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-source-only", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(source_scope_proof()))
