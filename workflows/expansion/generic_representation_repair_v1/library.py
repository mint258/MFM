"""Versioned generic-representation repair, never a chemical eligibility change.

Original successful calls return the original object. Only a witnessed official
generic RemoveHs AtomValence failure may enter private AST-derived functions.
"""
import ast
import copy
from contextvars import ContextVar
import hashlib
from pathlib import Path
import traceback
from ..alpha_common_hold_native_diagnostic_v1 import science as N

VERSION='GENERIC_ALLC_SINGLE_HEAVY_ADJACENCY_DEFERRED_VALENCE_V1'
MARKER='_pubchem_generic_valence_deferred_v1'
EVENTS=ContextVar('generic_representation_repair_events',default=None)
STATE=None


def need(value,message):
    if not value:raise ValueError(message)


def error(exc):
    return dict(type=type(exc).__name__,message=str(exc),exact_traceback=traceback.format_exc(),
      frames=[dict(file=f.filename,line=f.lineno,function=f.name,source_line=f.line) for f in traceback.extract_tb(exc.__traceback__)])


def frame_at(exc,code,line):
    tb=exc.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code is code and tb.tb_lineno==line:return True
        tb=tb.tb_next
    return False


def make_generic(mol):
    s=initialize();Chem=s['modules'][0];Murcko=s['modules'][5]
    try:return Murcko.MakeScaffoldGeneric(mol)
    except Chem.AtomValenceException as exc:
        if type(exc)is not Chem.AtomValenceException or not frame_at(exc,Murcko.MakeScaffoldGeneric.__code__,s['generic_return_line']):raise
        original_error=error(exc);middle=N.generic_before_remove_hs(Chem,mol)
        # Restrict this technical repair to valence introduced by all-C generic
        # conversion: at least one retained heavy vertex has degree above4.
        if not any(a.GetAtomicNum()==6 and sum(n.GetAtomicNum()!=1 for n in a.GetNeighbors())>4 for a in middle.GetAtoms()):raise
        generic=Chem.RemoveHs(middle,sanitize=False);generic.UpdatePropertyCache(strict=False)
        need(N.topology(generic)==N.topology(mol)
          and all(a.GetAtomicNum()==6 and not a.GetIsAromatic() for a in generic.GetAtoms())
          and all(b.GetBondType()==Chem.BondType.SINGLE and not b.GetIsAromatic() for b in generic.GetBonds()),
          'Generic representation repair must preserve exact heavy adjacency/allC/SINGLE')
        generic.SetBoolProp(MARKER,True)
        events=EVENTS.get();need(events is not None,'Explicit versioned evaluation context required')
        events.append(dict(operation='OFFICIAL_GENERIC_REMOVEHS_VALENCE_DEFERRED',version=VERSION,
          original_error=original_error,heavy_adjacency_allC_SINGLE_verified=True,
          source_snapshot=N.snapshot(mol),generic_snapshot=N.snapshot(generic)))
        return generic


def sanitize_generic(mol):
    Chem=initialize()['modules'][0]
    if mol.HasProp(MARKER) and mol.GetBoolProp(MARKER):
        events=EVENTS.get();need(events is not None,'Explicit versioned evaluation context required')
        events.append(dict(operation='GENERIC_INTERMEDIATE_POST_SANITIZE_DEFERRED',version=VERSION))
        return Chem.SanitizeFlags.SANITIZE_NONE
    return Chem.SanitizeMol(mol)


class Route(ast.NodeTransformer):
    def __init__(self):self.generic=0;self.post=0
    def visit_Call(self,node):
        node=self.generic_visit(node)
        if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name):
            if node.func.value.id=='Murcko' and node.func.attr=='MakeScaffoldGeneric':
                self.generic+=1;node.func=ast.copy_location(ast.Name(id='__generic_repr',ctx=ast.Load()),node.func)
            elif node.func.value.id=='Chem' and node.func.attr=='SanitizeMol' and len(node.args)==1 and isinstance(node.args[0],ast.Name) and node.args[0].id=='generic':
                self.post+=1;node.func=ast.copy_location(ast.Name(id='__sanitize_generic_repr',ctx=ast.Load()),node.func)
        return node


def private_function(module,name,globals_extra,expected_generic,expected_post):
    source=Path(module.__file__);raw=source.read_bytes();tree=ast.parse(raw)
    original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    derived=copy.deepcopy(original);route=Route();derived=route.visit(derived);ast.fix_missing_locations(derived)
    need((route.generic,route.post)==(expected_generic,expected_post),'Unexpected generic call AST scope')
    # Reverse only the declared call targets and require the entire original AST.
    class Inverse(ast.NodeTransformer):
        def visit_Name(self,node):
            if node.id=='__generic_repr':return ast.copy_location(ast.Attribute(value=ast.Name(id='Murcko',ctx=ast.Load()),attr='MakeScaffoldGeneric',ctx=ast.Load()),node)
            if node.id=='__sanitize_generic_repr':return ast.copy_location(ast.Attribute(value=ast.Name(id='Chem',ctx=ast.Load()),attr='SanitizeMol',ctx=ast.Load()),node)
            return node
    dump=lambda n:ast.dump(n,include_attributes=False)
    need(dump(Inverse().visit(copy.deepcopy(derived)))==dump(original),'Non-generic scientific AST changed')
    private_globals=dict(vars(module));private_globals.update(globals_extra)
    private_globals.update(__generic_repr=make_generic,__sanitize_generic_repr=sanitize_generic)
    code=compile(ast.Module(body=[derived],type_ignores=[]),str(Path(__file__))+'::'+source.name+'::'+name,'exec')
    exec(code,private_globals);function=private_globals[name]
    proof=dict(original_source_path=str(source),original_source_SHA=hashlib.sha256(raw).hexdigest(),function=name,
      original_AST_SHA=hashlib.sha256(dump(original).encode()).hexdigest(),derived_AST_SHA=hashlib.sha256(dump(derived).encode()).hexdigest(),
      exact_inverse_AST_equal=True,only_generic_calls_routed=route.generic,only_generic_post_sanitize_routed=route.post,
      original_module_globals_not_modified=True)
    return function,proof,original


def initialize():
    global STATE
    if STATE is not None:return STATE
    from .. import screen,features_legacy_compatible_v2 as old,features_generic_candidate_v1 as generic
    from ..common_molecular_fp_candidate_v1 import worker as W
    original_kernel,oldproof=W.load_kernel();modules=screen.rdkit_modules();Murcko=modules[5]
    official=N.source_proof(Murcko)
    original_tree=ast.parse(Path(official['installed_source']['path']).read_bytes())
    original_generic=next(n for n in original_tree.body if isinstance(n,ast.FunctionDef) and n.name=='MakeScaffoldGeneric')
    return_line=original_generic.body[-1].lineno
    ring,ringproof,_=private_function(generic,'generic_ring_systems_candidate',{},1,1)
    candidate,candidateproof,_=private_function(generic,'features_candidate',{'generic_ring_systems_candidate':ring},1,0)
    legacy,legacyproof,original=private_function(screen,'features',{},2,0)
    sanitize=[n for n in ast.walk(original) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
      and isinstance(n.func.value,ast.Name) and n.func.value.id=='Chem' and n.func.attr=='SanitizeMol'
      and len(n.args)==1 and isinstance(n.args[0],ast.Name) and n.args[0].id=='frag']
    need(len(sanitize)==1 and original_kernel is old.features_candidate and old.chemical_flags is screen.chemical_flags,'Original function objects and exact ring fallback site required')
    STATE=dict(original_kernel=original_kernel,modules=modules,official=official,generic_return_line=return_line,
      legacy=legacy,candidate=candidate,legacy_ring_sanitize_line=sanitize[0].lineno,
      source_proof=dict(version=VERSION,official=official,old_compatibility_proof=oldproof,
        private_function_proofs=[legacyproof,candidateproof,ringproof],chemical_flags_function_object_unchanged=True,
        original_success_returns_original_result_object=True,original_non_generic_AST_and_functions_unchanged=True))
    return STATE


def evaluate(cid,smiles,ordinal):
    s=initialize();Chem=s['modules'][0];token=EVENTS.set([])
    try:
        try:
            value=s['original_kernel'](cid,smiles,ordinal)
            return dict(features=value,representation_repair_applied=False,original_kernel_passed=True,
              original_result_object_returned_unchanged=True,events=[],version=VERSION)
        except Chem.AtomValenceException as exc:
            if type(exc)is not Chem.AtomValenceException or not frame_at(exc,s['modules'][5].MakeScaffoldGeneric.__code__,s['generic_return_line']):raise
            original_error=error(exc)
        try:value=s['legacy'](cid,smiles,ordinal)
        except Chem.KekulizeException as exc:
            if type(exc)is not Chem.KekulizeException or not frame_at(exc,s['legacy'].__code__,s['legacy_ring_sanitize_line']):raise
            value=s['candidate'](cid,smiles,ordinal)
        events=EVENTS.get();need(events,'No witnessed generic representation repair occurred')
        return dict(features=value,representation_repair_applied=True,original_kernel_passed=False,
          original_error=original_error,events=events,version=VERSION,chemical_rules_changed=False,
          source_graph_changed=False,non_generic_AST_changed=False)
    finally:EVENTS.reset(token)
