"""Stdlib EA/size control-binding proof; parse source only, never import science."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

CHECKPOINT_IMPORTS = {"support", "size_shared", "workflows.data_v1_final.labels.streaming_cpu_v1.support"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, pin):
    raw = Path(path).read_bytes()
    if len(raw) != pin["bytes"] or digest(raw) != pin["sha256"]:
        raise ValueError("SOURCE_SHA_OR_SIZE_DIFFERS:" + str(path))
    return raw


class StripCheckpoints(ast.NodeTransformer):
    def visit_Expr(self, node):
        if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "checkpoint" and not node.value.args and not node.value.keywords):
            return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Name) and node.func.id == "checkpoint_iter"
                and len(node.args) == 1 and not node.keywords):
            return self.visit(node.args[0])
        return self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module in CHECKPOINT_IMPORTS:
            node.names = [n for n in node.names if n.name not in {"checkpoint", "checkpoint_iter"}]
            return node if node.names else None
        return node


class Functions(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
        self.result = {}

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        name = ".".join([*self.stack, node.name])
        if name in self.result:
            raise ValueError("DUPLICATE_QUALIFIED_FUNCTION")
        self.result[name] = node
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def function_map(tree):
    visitor = Functions()
    visitor.visit(tree)
    return visitor.result


def dump(tree):
    return ast.dump(tree, include_attributes=False)


def verify_templates():
    directory = Path(__file__).parent
    manifest = json.loads((directory / "binding_templates_v1.json").read_text(encoding="utf-8-sig"))
    config_dir = Path(__file__).resolve().parents[4] / "configs/data_v1/labels"
    results = []
    for row in manifest["templates"]:
        old_raw = checked(row["baseline_reference"]["path"], row["baseline_reference"])
        actual = config_dir / row["template"]
        new_raw = checked(actual, row["prepared_template_reference"])
        old, new = json.loads(old_raw), json.loads(new_raw)
        key = row["only_changed_scientific_json_key"]
        if key not in {"support_source", "scan_adapter"}:
            raise ValueError("UNDECLARED_CONFIG_BINDING_KEY")
        restored = copy.deepcopy(new)
        restored[key] = old[key]
        if restored != old:
            raise ValueError("NON_BINDING_SCIENTIFIC_CONFIG_CHANGE:" + row["template"])
        pin = new[key]
        checked(pin["path"], pin)
        if row["template"].startswith("size_") and new["memory_gib"] != 64:
            raise ValueError("SIZE_64_GIB_CONFIG_WAS_CHANGED")
        results.append({"template": row["template"], "actual_template_reference": {
            "path": str(actual), "bytes": len(new_raw), "sha256": digest(new_raw)},
            "changed_binding_key": key, "binding_reference": pin,
            "all_other_json_values_identical": True, "memory_gib": new["memory_gib"]})
    return results


def verify(folder):
    folder = Path(folder).absolute()
    mapping = json.loads((folder / "source_mapping_v1.json").read_text(encoding="utf-8-sig"))
    edit_map = json.loads((folder / "edits_v1.json").read_text(encoding="utf-8-sig"))["files"]
    if {r["filename"] for r in mapping["files"]} != set(edit_map):
        raise ValueError("CONTROL_EDIT_MAPPING_FILE_SET_DIFFERS")
    rows = []
    for item in mapping["files"]:
        name = item["filename"]
        old_raw = checked(item["baseline_reference"]["path"], item["baseline_reference"])
        actual = folder / name
        new_raw = checked(actual, item["prepared_variant_reference"])
        old, new = old_raw.decode(), new_raw.decode()
        expected = old
        for edit in edit_map[name]:
            if edit["kind"] not in {"binding", "checkpoint", "checkpoint_import"} or expected.count(edit["old"]) != 1:
                raise ValueError("UNKNOWN_OR_NONUNIQUE_CONTROL_EDIT:" + name)
            expected = expected.replace(edit["old"], edit["new"])
        if expected.encode() != new_raw:
            raise ValueError("UNDECLARED_SOURCE_BYTE_CHANGE:" + name)
        restored = new
        for edit in reversed(edit_map[name]):
            if restored.count(edit["new"]) != 1:
                raise ValueError("NONUNIQUE_INVERSE_CONTROL_EDIT:" + name)
            restored = restored.replace(edit["new"], edit["old"])
        if restored.encode() != old_raw:
            raise ValueError("INVERSE_CONTROL_EDITS_NOT_ORIGINAL_BYTES:" + name)
        # Restore only explicitly listed module-path bindings before stripping
        # checkpoint calls/imports; no numerical expression is rewritten.
        normalized_text = new
        for edit in reversed(edit_map[name]):
            if edit["kind"] == "binding":
                if normalized_text.count(edit["new"]) != 1:
                    raise ValueError("BINDING_EDIT_NOT_UNIQUE")
                normalized_text = normalized_text.replace(edit["new"], edit["old"])
        old_ast, actual_ast = ast.parse(old), ast.parse(new)
        normalized = StripCheckpoints().visit(ast.parse(normalized_text))
        if dump(old_ast) != dump(normalized):
            raise ValueError("NONCONTROL_WHOLE_MODULE_AST_CHANGE:" + name)
        before, after, stripped = function_map(old_ast), function_map(actual_ast), function_map(normalized)
        if set(before) != set(after) or set(before) != set(stripped):
            raise ValueError("FUNCTION_SET_DIFFERS:" + name)
        functions = []
        for key, fn in before.items():
            if dump(fn) != dump(stripped[key]):
                raise ValueError("SCIENTIFIC_FUNCTION_AST_CHANGE:" + name + ":" + key)
            left = ast.get_source_segment(old, fn).encode()
            right = ast.get_source_segment(new, after[key]).encode()
            functions.append({"function": key, "source_bytes_identical": left == right,
                              "old_sha256": digest(left), "new_sha256": digest(right),
                              "declared_binding_and_checkpoint_removed_ast_identical": True})
        if mapping["schema"] == "SIZE_CPU_SOURCE_MAPPING_V1" and name == "size_shared.py":
            if not next(r["source_bytes_identical"] for r in functions if r["function"] == "guard"):
                raise ValueError("SIZE_HARD64_GUARD_WAS_CHANGED")
        rows.append({"filename": name, "baseline_reference": item["baseline_reference"],
                     "actual_variant_reference": {"path": str(actual), "bytes": len(new_raw), "sha256": digest(new_raw)},
                     "whole_file_bytes_identical": old_raw == new_raw,
                     "inverse_declared_edits_full_file_bytes_identical": True,
                     "declared_binding_and_checkpoint_removed_whole_ast_identical": True, "functions": functions})
    return {"schema": "CPU_CONTROL_BINDING_EQUIVALENCE_PROOF_V1", "status": "PASS", "source_mapping_schema": mapping["schema"],
            "files": rows, "scientific_modules_imported": [], "scientific_data_bodies_read": False,
            "config_templates": verify_templates(),
            "size_hard64_guard_unchanged": mapping["schema"] == "SIZE_CPU_SOURCE_MAPPING_V1",
            "scope": "Exact source copies plus recorded import-path bindings/checkpoints; numerical source AST and inverse bytes preserved"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--variant-dir", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = verify(a.variant_dir)
    with Path(a.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("CPU_CONTROL_BINDING_EQUIVALENCE_PASS", len(result["files"]))


if __name__ == "__main__":
    main()
