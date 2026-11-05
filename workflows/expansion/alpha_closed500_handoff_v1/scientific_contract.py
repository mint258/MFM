"""Verify relocated pure-function ASTs against their frozen original bodies."""
import ast
import hashlib
from pathlib import Path
from ..alpha_runtime_v1.common import load, need


def verify():
    here = Path(__file__).parent
    contract = load(here / 'original_function_contract.json')
    def nodes(name):
        return [n for n in ast.parse((here / name).read_text()).body if isinstance(n, ast.FunctionDef)]
    selected = {'baseline_core': nodes('baseline_core.py')[0], 'filter_core': nodes('filter_core.py')[0]}
    primitive = nodes('science_v3.py')
    for name in ('wp5_key', 'vector', 'candidate_domain', 'rules', 'index_header'):
        selected[('common_' if name == 'wp5_key' else 'v3_') + name] = next(n for n in primitive if n.name == name)
    contamination = [n for n in primitive if n.name == 'contamination']
    need(len(contamination) == 2, 'Both unchanged legacy and V3 contamination bodies required')
    selected['legacy_contamination'], selected['v3_contamination'] = contamination
    imports = [n for n in ast.walk(selected['filter_core']) if isinstance(n, ast.ImportFrom) and n.module is None and any(a.name == 'science_v3' for a in n.names)]
    need(len(imports) == 1, 'Only declared original V3 import relocation is allowed')
    need(imports[0].level == 1 and [(a.name, a.asname) for a in imports[0].names] == [('science_v3', 'original')], 'Exact declared V3 import alias is required')
    imports[0].module, imports[0].level = 'coconut735_recovery_v1', 2
    imports[0].names[0].name, imports[0].names[0].asname = 'consumer', 'original'
    need(set(selected) == set(contract['functions']), 'Every borrowed pure science function must be accounted for')
    for name, node in selected.items():
        actual = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        need(actual == contract['functions'][name]['original_AST_sha256'], 'Original scientific function AST differs: ' + name)
    return contract
