"""Stdlib proof of the exact approved control edits; no scientific imports/I/O."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

CENTRAL = "workflows.data_v1_final.execution.cpu_analysis_v1.runtime"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_bytes(path, expected):
    raw = Path(path).read_bytes()
    if len(raw) != expected["bytes"] or digest(raw) != expected["sha256"]:
        raise ValueError("SOURCE_BYTES_DIFFER_FROM_FROZEN_MAPPING:" + str(path))
    return raw


class StripControl(ast.NodeTransformer):
    def __init__(self, support=False, old_guard=None):
        self.support = support
        self.old_guard = old_guard

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
        if self.support and node.module == CENTRAL:
            return None
        if node.module == "support":
            node.names = [a for a in node.names if a.name not in {"checkpoint", "checkpoint_iter"}]
            if not node.names:
                return None
        return node

    def visit_FunctionDef(self, node):
        if self.support and node.name == "checkpoint_iter":
            return None
        if self.support and node.name == "root_guard":
            return copy.deepcopy(self.old_guard)
        return self.generic_visit(node)


def dump(node):
    return ast.dump(node, include_attributes=False)


class Functions(ast.NodeVisitor):
    def __init__(self):
        self.prefix = []
        self.result = {}

    def visit_ClassDef(self, node):
        self.prefix.append(node.name)
        self.generic_visit(node)
        self.prefix.pop()

    def visit_FunctionDef(self, node):
        key = ".".join([*self.prefix, node.name])
        if key in self.result:
            raise ValueError("DUPLICATE_QUALIFIED_FUNCTION")
        self.result[key] = node
        self.prefix.append(node.name)
        self.generic_visit(node)
        self.prefix.pop()


def functions(tree):
    visitor = Functions()
    visitor.visit(tree)
    return visitor.result


def verify(variant_dir):
    directory = Path(variant_dir).absolute()
    mapping = json.loads((directory / "source_mapping_v1.json").read_text(encoding="utf-8-sig"))
    edits = json.loads((directory / "edits_v1.json").read_text(encoding="utf-8-sig"))
    if set(edits["files"]) != {r["filename"] for r in mapping["files"]}:
        raise ValueError("MAPPING_AND_EDIT_FILE_SET_DIFFERS")
    results = []
    for row in mapping["files"]:
        name = row["filename"]
        old_raw = checked_bytes(row["baseline_reference"]["path"], row["baseline_reference"])
        actual_path = directory / name
        new_raw = checked_bytes(actual_path, row["prepared_variant_reference"])
        old = old_raw.decode("utf-8")
        new = new_raw.decode("utf-8")
        expected = old
        for edit in edits["files"][name]:
            if expected.count(edit["old"]) != 1:
                raise ValueError("FORWARD_CONTROL_EDIT_NOT_UNIQUE:" + name)
            expected = expected.replace(edit["old"], edit["new"])
        if expected.encode() != new_raw:
            raise ValueError("UNDECLARED_BYTE_CHANGE:" + name)
        restored = new
        for edit in reversed(edits["files"][name]):
            if restored.count(edit["new"]) != 1:
                raise ValueError("REVERSE_CONTROL_EDIT_NOT_UNIQUE:" + name)
            restored = restored.replace(edit["new"], edit["old"])
        if restored.encode() != old_raw:
            raise ValueError("REVERSE_EDIT_FULL_FILE_NOT_BYTE_IDENTICAL:" + name)
        before, after = ast.parse(old), ast.parse(new)
        guard = next((n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == "root_guard"), None)
        normalized = StripControl(support=name == "support.py", old_guard=guard).visit(copy.deepcopy(after))
        if dump(before) != dump(normalized):
            raise ValueError("NONCONTROL_MODULE_AST_CHANGE:" + name)
        old_f, new_f, norm_f = functions(before), functions(after), functions(normalized)
        function_rows = []
        for key, node in old_f.items():
            if name == "support.py" and key == "root_guard":
                continue
            if key not in new_f or dump(node) != dump(norm_f[key]):
                raise ValueError("NON_GUARD_FUNCTION_AST_CHANGE:" + name + ":" + key)
            old_segment = ast.get_source_segment(old, node).encode()
            new_segment = ast.get_source_segment(new, new_f[key]).encode()
            function_rows.append({"function": key, "source_bytes_identical": old_segment == new_segment,
                                  "baseline_segment_sha256": digest(old_segment), "variant_segment_sha256": digest(new_segment),
                                  "ast_identical_after_only_declared_checkpoint_removal": True})
        results.append({"filename": name, "baseline_reference": row["baseline_reference"],
                        "actual_variant_reference": {"path": str(actual_path), "bytes": len(new_raw), "sha256": digest(new_raw)},
                        "raw_file_bytes_identical": old_raw == new_raw,
                        "reverse_declared_edits_full_file_bytes_identical": True,
                        "whole_module_ast_equal_after_only_control_removal": True,
                        "non_guard_functions": function_rows})
    return {"schema": "STREAMING_CPU_CONTROL_EQUIVALENCE_PROOF_V1", "status": "PASS",
            "files": results, "scientific_modules_imported": [], "scientific_data_bodies_read": False,
            "ordinary_source_functions_not_control_rewritten": "per-function byte identities explicitly reported; checkpoint-instrumented functions pass exact inverse full-file bytes plus stripped AST",
            "scope": "Only declared central-guard delegation, checkpoint calls and checkpoint_iter wrappers; all mathematics/labels/thresholds restored byte-exact"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--variant-dir", default=str(Path(__file__).parent))
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = verify(a.variant_dir)
    with Path(a.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("STREAMING_CPU_CONTROL_EQUIVALENCE_PASS", len(result["files"]))


if __name__ == "__main__":
    main()
