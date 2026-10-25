"""Stdlib-only proof of v2 CPU directory bindings, without science imports."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

PREFIX = "workflows/data_v1_final/labels/"
ALLOWED = {
    **{PREFIX + "size_cpu_v2/" + name: [] for name in (
        "aggregate.py", "build_proposal.py", "rank_sql.py", "run_size.py",
        "size_reader.py", "size_worker.py")},
    PREFIX + "size_cpu_v2/size_shared.py": [
        {"kind": "binding", "old": 'LABELS/"streaming_cpu_v1"',
         "new": 'LABELS/"streaming_cpu_v2"'},
        {"kind": "binding", "old": 'LABELS/"size_cpu_v1"/"_normalization"',
         "new": 'LABELS/"normalization_cpu_v2"'}],
    PREFIX + "normalization_cpu_v2/reader.py": [],
    PREFIX + "normalization_cpu_v2/runtime.py": [
        {"kind": "binding",
         "old": 'STREAM = Path(__file__).resolve().parents[2] / "streaming_cpu_v1"',
         "new": 'STREAM = Path(__file__).resolve().parents[1] / "streaming_cpu_v2"'}],
    PREFIX + "ea_cpu_v2/bounded_probe.py": [
        {"kind": "binding",
         "old": "from workflows.data_v1_final.labels.streaming_cpu_v1.support import checkpoint, checkpoint_iter",
         "new": "from workflows.data_v1_final.labels.streaming_cpu_v2.support import checkpoint, checkpoint_iter"}],
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, pin):
    path = Path(path)
    size = path.stat().st_size
    if size > 2 * 1024 * 1024:
        raise ValueError("SMALL_SOURCE_CAP_EXCEEDED:" + str(path))
    raw = path.read_bytes()
    if len(raw) != pin["bytes"] or digest(raw) != pin["sha256"]:
        raise ValueError("ACTUAL_ROOT_BYTES_OR_SHA_DIFFERS:" + str(path))
    return raw


def reference(path, raw):
    return {"path": str(path), "bytes": len(raw), "sha256": digest(raw)}


def restore(new, edits):
    text = new
    for edit in reversed(edits):
        if edit["kind"] != "binding" or text.count(edit["new"]) != 1:
            raise ValueError("NONUNIQUE_OR_NON_BINDING_INVERSE_EDIT")
        text = text.replace(edit["new"], edit["old"])
    return text


def compare_bytes(old_raw, new_raw, edits):
    old, new = old_raw.decode("utf-8"), new_raw.decode("utf-8")
    expected = old
    for edit in edits:
        if edit["kind"] != "binding" or expected.count(edit["old"]) != 1:
            raise ValueError("NONUNIQUE_OR_NON_BINDING_FORWARD_EDIT")
        expected = expected.replace(edit["old"], edit["new"])
    if expected.encode("utf-8") != new_raw or restore(new, edits).encode("utf-8") != old_raw:
        raise ValueError("WHOLE_FILE_INVERSE_BYTES_DIFFER")
    return old, new


class Functions(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
        self.result = {}

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        key = ".".join([*self.stack, node.name])
        if key in self.result:
            raise ValueError("DUPLICATE_QUALIFIED_FUNCTION")
        self.result[key] = node
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def functions(tree):
    visitor = Functions()
    visitor.visit(tree)
    return visitor.result


def ast_dump(tree):
    return ast.dump(tree, include_attributes=False)


def baseline_relative(variant):
    if "/size_cpu_v2/" in variant:
        return variant.replace("/size_cpu_v2/", "/size_cpu_v1/")
    if "/normalization_cpu_v2/" in variant:
        return variant.replace("/normalization_cpu_v2/", "/size_cpu_v1/_normalization/")
    return variant.replace("/ea_cpu_v2/", "/ea_cpu_v1/")


def verify_sources(repo, manifest):
    entries = manifest["files"]
    if len(entries) != 10 or {r["variant_relative"] for r in entries} != set(ALLOWED):
        raise ValueError("COMPLETE_V2_SOURCE_FILE_SET_DIFFERS")
    results = []
    for row in entries:
        relative = row["variant_relative"]
        if row["edits"] != ALLOWED[relative] or row["baseline_relative"] != baseline_relative(relative):
            raise ValueError("UNDECLARED_MODULE_BINDING:" + relative)
        original, actual = repo / row["baseline_relative"], repo / relative
        if (str(original) != row["expected_root_baseline_reference"]["path"]
                or str(actual) != row["intended_root_variant_path"]):
            raise ValueError("EXPECTED_AND_ACTUAL_ROOT_PATHS_DIFFER")
        old_raw = checked(original, row["expected_root_baseline_reference"])
        new_raw = checked(actual, row["prepared_child_variant_reference"])
        old, new = compare_bytes(old_raw, new_raw, row["edits"])
        old_ast, new_ast = ast.parse(old), ast.parse(new)
        if ast_dump(old_ast) != ast_dump(ast.parse(restore(new, row["edits"]))):
            raise ValueError("MODULE_AST_DIFFERS_AFTER_DIRECTORY_BINDING_INVERSE")
        before, after = functions(old_ast), functions(new_ast)
        if set(before) != set(after):
            raise ValueError("FUNCTION_SET_CHANGED")
        fn_rows = []
        for key, fn in before.items():
            left = ast.get_source_segment(old, fn).encode("utf-8")
            right = ast.get_source_segment(new, after[key]).encode("utf-8")
            if left != right or ast_dump(fn) != ast_dump(after[key]):
                raise ValueError("FUNCTION_BYTES_OR_AST_CHANGED:" + relative + ":" + key)
            fn_rows.append({"function": key, "source_bytes_identical": True,
                            "ast_identical": True, "sha256": digest(left)})
        if relative.endswith("size_shared.py") and not any(r["function"] == "guard" for r in fn_rows):
            raise ValueError("SIZE_HARD64_GUARD_MISSING")
        results.append({"variant_relative": relative,
                        "actual_root_baseline_reference": reference(original, old_raw),
                        "actual_root_variant_reference": reference(actual, new_raw),
                        "whole_file_bytes_identical": old_raw == new_raw,
                        "inverse_complete_file_bytes_identical": True,
                        "module_ast_identical_after_only_directory_bindings": True,
                        "all_function_source_bytes_and_ast_identical": True,
                        "functions": fn_rows})
    return results


def verify_templates(repo, manifest):
    rows = manifest["config_templates"]
    allowed = {"ea_cpu_v2.template.json": ("support_source", "support.py", 32),
               "size_cpu_v2.template.json": ("scan_adapter", "scan_v2.py", 64)}
    if len(rows) != 2 or {Path(r["variant_relative"]).name for r in rows} != set(allowed):
        raise ValueError("TEMPLATE_FILE_SET_DIFFERS")
    results = []
    for row in rows:
        relative = row["variant_relative"]
        key, target_name, memory_gib = allowed[Path(relative).name]
        if (row["only_changed_json_key"] != key
                or row["baseline_relative"] != relative.replace("_cpu_v2.", "_cpu_v1.")):
            raise ValueError("UNDECLARED_CONFIG_BINDING")
        original, actual = repo / row["baseline_relative"], repo / relative
        if (str(original) != row["expected_root_baseline_reference"]["path"]
                or str(actual) != row["intended_root_variant_path"]):
            raise ValueError("CONFIG_EXPECTED_AND_ACTUAL_ROOT_PATHS_DIFFER")
        old_raw = checked(original, row["expected_root_baseline_reference"])
        new_raw = checked(actual, row["prepared_child_variant_reference"])
        compare_bytes(old_raw, new_raw, row["edits"])
        old, new = json.loads(old_raw), json.loads(new_raw)
        if set(old) != set(new) or {k for k in old if old[k] != new[k]} != {key}:
            raise ValueError("CONFIG_KEYS_OTHER_THAN_BINDING_CHANGED")
        restored = copy.deepcopy(new)
        restored[key] = old[key]
        if restored != old or new["memory_gib"] != memory_gib:
            raise ValueError("CONFIG_SCIENCE_OR_REQUIRED_MEMORY_CHANGED")
        expected_relative = PREFIX + "streaming_cpu_v2/" + target_name
        if (row["binding_target_relative"] != expected_relative
                or new[key] != row["binding_target_expected_root_reference"]
                or new[key]["path"] != str(repo / expected_relative)):
            raise ValueError("CONFIG_BINDING_NOT_EXPLICIT_ROOT_V2_TARGET")
        target_raw = checked(repo / expected_relative, new[key])
        results.append({"template": relative, "changed_json_key": key,
                        "all_other_json_values_identical": True,
                        "inverse_complete_file_bytes_identical": True,
                        "memory_gib": new["memory_gib"],
                        "actual_root_template_reference": reference(actual, new_raw),
                        "actual_root_baseline_reference": reference(original, old_raw),
                        "actual_root_binding_target_reference": reference(repo / expected_relative, target_raw)})
    support = repo / (PREFIX + "streaming_cpu_v2/support.py")
    support_raw = support.read_bytes()
    if b"from workflows.data_v1_final.execution.cpu_analysis_v1.runtime_v2 import" not in support_raw:
        raise ValueError("STREAM_SUPPORT_NOT_BOUND_TO_RUNTIME_V2")
    return results


def verify():
    repo = Path(__file__).resolve().parents[4]
    source = Path(__file__).parent / "source_mapping_v2.json"
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("MAPPING_SMALL_METADATA_CAP_EXCEEDED")
    raw = source.read_bytes()
    manifest = json.loads(raw)
    if manifest["schema"] != "CPU_V2_SIZE_EA_BINDING_SOURCE_MAPPING_V1":
        raise ValueError("UNKNOWN_V2_BINDING_SCHEMA")
    if str(repo) != manifest["expected_root_repository"]:
        raise ValueError("ACTUAL_ROOT_REPOSITORY_REQUIRED_NO_CHILD_EQUIVALENCE_ASSUMPTION")
    files = verify_sources(repo, manifest)
    templates = verify_templates(repo, manifest)
    return {"schema": "CPU_V2_SIZE_EA_DIRECTORY_BINDING_PROOF_V1", "status": "PASS",
            "mapping_actual_root_reference": reference(source, raw),
            "root_baselines_observed_now": True, "files": files, "config_templates": templates,
            "size_guard_original_function_bytes_unchanged_hard64": True,
            "all_functions_original_bytes_and_ast_unchanged": True,
            "scientific_modules_imported": [], "scientific_data_bodies_read": False,
            "science_executed": False, "final_registry_or_normalization_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = verify()
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("CPU_V2_BINDINGS_SOURCE_EQUIVALENCE_PASS", len(result["files"]), len(result["config_templates"]))


if __name__ == "__main__":
    main()
