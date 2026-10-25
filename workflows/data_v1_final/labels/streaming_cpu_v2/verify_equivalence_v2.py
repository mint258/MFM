"""Stdlib CPUv2 copy/import proof; no old fixtures or scientific execution."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, expected):
    raw = Path(path).read_bytes()
    if len(raw) != expected["bytes"] or sha(raw) != expected["sha256"]:
        raise ValueError("SOURCE_MAPPING_SIZE_OR_SHA_DIFFERS:" + str(path))
    return raw


class Functions(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
        self.items = {}

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        name = ".".join([*self.stack, node.name])
        if name in self.items:
            raise ValueError("DUPLICATE_QUALIFIED_FUNCTION")
        self.items[name] = node
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def functions(tree):
    visitor = Functions()
    visitor.visit(tree)
    return visitor.items


def verify(folder):
    folder = Path(folder).absolute()
    mapping = json.loads((folder / "source_mapping_v2.json").read_text(encoding="utf-8-sig"))
    edits = json.loads((folder / "edits_v2.json").read_text(encoding="utf-8-sig"))["files"]
    if {r["filename"] for r in mapping["files"]} != set(edits) or len(edits) != 5:
        raise ValueError("EXACT_FIVE_PRODUCTION_SOURCES_REQUIRED")
    results = []
    for row in mapping["files"]:
        name = row["filename"]
        old_raw = checked(row["baseline_reference"]["path"], row["baseline_reference"])
        actual_path = folder / name
        new_raw = checked(actual_path, row["prepared_variant_reference"])
        old, new = old_raw.decode(), new_raw.decode()
        expected = old
        for change in edits[name]:
            if expected.count(change["old"]) != 1:
                raise ValueError("NONUNIQUE_V2_IMPORT_EDIT")
            expected = expected.replace(change["old"], change["new"])
        if expected.encode() != new_raw:
            raise ValueError("UNDECLARED_V2_SOURCE_CHANGE:" + name)
        restored = new
        for change in reversed(edits[name]):
            if restored.count(change["new"]) != 1:
                raise ValueError("NONUNIQUE_INVERSE_V2_IMPORT_EDIT")
            restored = restored.replace(change["new"], change["old"])
        if restored.encode() != old_raw or ast.dump(ast.parse(restored), include_attributes=False) != ast.dump(ast.parse(old), include_attributes=False):
            raise ValueError("V2_INVERSE_IMPORT_NOT_ORIGINAL_BYTES_AND_AST")
        before, after = functions(ast.parse(old)), functions(ast.parse(new))
        if set(before) != set(after):
            raise ValueError("V2_FUNCTION_SET_CHANGED")
        items = []
        for key, node in before.items():
            left = ast.get_source_segment(old, node).encode()
            right = ast.get_source_segment(new, after[key]).encode()
            if left != right or ast.dump(node, include_attributes=False) != ast.dump(after[key], include_attributes=False):
                raise ValueError("V2_FUNCTION_BYTES_OR_AST_CHANGED:" + name + ":" + key)
            items.append({"function": key, "source_bytes_identical": True, "ast_identical": True, "sha256": sha(left)})
        results.append({"filename": name, "baseline_reference": row["baseline_reference"],
                        "actual_variant_reference": {"path": str(actual_path), "bytes": len(new_raw), "sha256": sha(new_raw)},
                        "raw_file_bytes_identical": old_raw == new_raw, "inverse_import_edit_original_bytes_identical": True,
                        "all_functions_bytes_and_ast_identical": True, "functions": items})
    return {"schema": "STREAMING_CPU_V2_SOURCE_EQUIVALENCE_PROOF_V1", "status": "PASS", "files": results,
            "scientific_modules_imported": [], "scientific_data_bodies_read": False, "fixtures_replayed": [],
            "scope": "Only support runtime module import switches to runtime_v2; reducer baseline is already approved7200 version; every function is byte-identical"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--variant-dir", default=str(Path(__file__).parent))
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = verify(a.variant_dir)
    with Path(a.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("STREAMING_CPU_V2_SOURCE_EQUIVALENCE_PASS", len(result["files"]))


if __name__ == "__main__":
    main()
