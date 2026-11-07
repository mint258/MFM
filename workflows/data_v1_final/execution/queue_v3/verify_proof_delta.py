"""Static exact inverse proof for the single added redundant admission tag."""
import ast
import hashlib

ADDITION = "'memory_basis':admission['memory_basis'],"


def function_text(source):
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == "create_proof"]
    if len(matches) != 1:
        raise ValueError("ONE_CREATE_PROOF_FUNCTION_REQUIRED")
    return ast.get_source_segment(source, matches[0])


def verify(old_source, new_source):
    old = function_text(old_source); new = function_text(new_source)
    if new.count(ADDITION) != 1 or ADDITION in old:
        raise ValueError("ONE_NEW_MEMORY_BASIS_TAG_REQUIRED")
    inverse = new.replace(ADDITION, "", 1)
    if inverse != old:
        raise ValueError("OTHER_PROOF_SOURCE_CHANGE_FORBIDDEN")
    if ast.dump(ast.parse(inverse), include_attributes=False) != ast.dump(ast.parse(old), include_attributes=False):
        raise ValueError("INVERSE_PROOF_AST_DIFFERS")
    return {"schema": "QUEUE_V3_CREATE_PROOF_SINGLE_TAG_EQUIVALENCE_V1",
        "inverse_function_bytes_equal": True, "inverse_normalized_ast_identical": True,
        "added_tag": "memory_basis copied from actual admission before proof/ready writes",
        "original_function_sha256": hashlib.sha256(old.encode()).hexdigest(),
        "variant_function_sha256": hashlib.sha256(new.encode()).hexdigest(),
        "resource_math_and_validator_calls_unchanged": True}
