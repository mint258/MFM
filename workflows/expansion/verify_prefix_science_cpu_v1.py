"""Stdlib-only AST comparison: remove only explicit CPU checkpoint statements."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


NAMES = ("json_safe", "mol_property_snapshot", "diagnose_case", "read_target_prefix")


class RemoveCheckpoints(ast.NodeTransformer):
    def visit_Expr(self, node):
        call = node.value
        if (isinstance(call, ast.Call) and not call.args and not call.keywords and
                isinstance(call.func, ast.Attribute) and call.func.attr == "checkpoint" and
                isinstance(call.func.value, ast.Name) and call.func.value.id == "cpu_runtime"):
            return None
        return self.generic_visit(node)


def compare(baseline, candidate, names=NAMES):
    result, refs = {}, []
    for path in (baseline, candidate):
        path = Path(path)
        if path.stat().st_size > 2 * 1024 ** 2:
            raise ValueError("Scientific source exceeds small metadata bound")
        with path.open("rb") as stream:
            raw = stream.read(2 * 1024 ** 2 + 1)
        if len(raw) > 2 * 1024 ** 2:
            raise ValueError("Scientific source exceeds small metadata bound")
        refs.append({"path": str(Path(path).absolute()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        functions = {node.name: node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef)}
        result[str(path)] = {name: ast.dump(RemoveCheckpoints().visit(functions[name]), include_attributes=False) for name in names}
    left, right = (result[str(p)] for p in (baseline, candidate))
    if left != right:
        raise ValueError("Scientific AST drift beyond checkpoint statements: " + str([n for n in names if left[n] != right[n]]))
    return {"status": "SCIENTIFIC_FUNCTION_ASTS_IDENTICAL_EXCEPT_CPU_CHECKPOINTS", "references": refs,
            "functions": list(names), "normalized_ast_sha256": {
                name: hashlib.sha256(left[name].encode()).hexdigest() for name in names},
            "RDKit_or_science_executed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--function", action="append", dest="functions")
    args = parser.parse_args()
    print(json.dumps(compare(args.baseline, args.candidate, args.functions or NAMES)))


if __name__ == "__main__":
    main()
