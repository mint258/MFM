"""Exact original non-generic expressions, independent of any ring-route selection."""
import ast
import copy
import hashlib
from pathlib import Path

GENERIC = {'generic_murcko','generic_ring_systems'}


def need(value,message):
    if not value:raise ValueError(message)


def derive(module,name):
    raw=Path(module.__file__).read_bytes()
    original=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==name)
    sites=[i for i,n in enumerate(original.body) if isinstance(n,ast.Assign)
           and any(isinstance(t,ast.Name) and t.id=='scaffold' for t in n.targets)]
    need(len(sites)==1,'Exact original first whole-scaffold assignment')
    fp,ret=original.body[-2:]
    need(isinstance(fp,ast.Assign) and len(fp.targets)==1 and isinstance(fp.targets[0],ast.Name)
         and fp.targets[0].id=='fp' and isinstance(ret,ast.Return) and isinstance(ret.value,ast.Dict),
         'Exact original fingerprint assignment and final feature dictionary')
    keys=[n.value if isinstance(n,ast.Constant) else None for n in ret.value.keys]
    need(len(keys)==len(set(keys)) and GENERIC<=set(keys) and None not in keys,'Exact original feature names')
    result=copy.deepcopy(original);result.name='_original_nongeneric_probe'
    filtered=copy.deepcopy(ret)
    pairs=[(k,v) for k,v in zip(filtered.value.keys,filtered.value.values) if k.value not in GENERIC]
    filtered.value.keys=[k for k,v in pairs];filtered.value.values=[v for k,v in pairs]
    result.body=copy.deepcopy(original.body[:sites[0]])+[copy.deepcopy(fp),filtered]
    ast.fix_missing_locations(result)
    dump=ast.dump(result,include_attributes=False)
    scope=dict(vars(module));exec(compile(ast.Module(body=[result],type_ignores=[]),str(Path(__file__))+'::'+name,'exec'),scope)
    return scope[result.name],dump,dict(original_source_path=str(Path(module.__file__)),
        original_source_sha256=hashlib.sha256(raw).hexdigest(),original_function=name,
        original_non_generic_AST_sha256=hashlib.sha256(dump.encode()).hexdigest(),
        kept_original_prefix_statements=sites[0],original_fingerprint_assignment_unchanged=True,
        all_non_generic_return_expressions_unchanged=True,omitted_output_fields=sorted(GENERIC),
        original_module_or_globals_modified=False)


def initialize(screen,generic):
    for name in ('chemical_flags','rdkit_modules','wp5_key','Counter','json'):
        need(getattr(screen,name) is getattr(generic,name),'Exact common original non-generic global object: '+name)
    original,a,ap=derive(screen,'features');fallback,b,bp=derive(generic,'features_candidate')
    need(a==b,'Legacy and whole-function fallback non-generic recipes must be exactly identical AST')
    return original,dict(legacy=ap,whole_function_fallback=bp,non_generic_AST_exactly_equal=True,
        generic_ring_route_reconstructed=False,per_fragment_hybrid_route_used=False)
