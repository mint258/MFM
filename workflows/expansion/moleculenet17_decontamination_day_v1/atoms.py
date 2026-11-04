"""Exact original atoms_only/composition bodies; only package resource context differs."""
import collections,hashlib
from . import contract as C
Q=C.Q

def atoms_only(text,Chem):
    result={'state':'UNKNOWN_NO_COMPOSITION','composition':None,'original_identity_state':'ORIGINAL_SMILES_UNRESOLVED',
        'full_keys':[],'graph_charge_stereo':'UNKNOWN','original_failure_cause':'UNKNOWN','original_N4_warning_row_bound':False,
        'new_full_key_computations':0,'source_evidence_basis':'ORIGINAL_SMILES_EXPLICIT_ATOMIC_NUMBERS_ONLY_NEW_SEAM',
        'automatic_fallback_policy_accepted':False,'MolFromSmiles_invoked':False}
    if not isinstance(text,str) or not text or any(not 33<=ord(c)<=126 for c in text):
        return {**result,'reason':'ORIGINAL_WHOLE_STRING_NOT_NONEMPTY_ASCII33_TO126_NO_TRIMMING_OR_PREFIX_PARSE'}
    params=Chem.SmilesParserParams()
    for k,v in C.PARAMS.items():setattr(params,k,v)
    Q.need({k:getattr(params,k) for k in C.PARAMS}==C.PARAMS,'ACTUAL_EXPLICIT_FROZEN_PARSER_PARAMS')
    result['parser_params']=C.PARAMS;result['original_UTF8_sha256']=hashlib.sha256(text.encode('utf-8')).hexdigest()
    result['skipCleanup_requested']=False;result['internal_parser_processing_absent_claimed']=False
    try:
        result['MolFromSmiles_invoked']=True
        mol=Chem.MolFromSmiles(text,params)
        if mol is None:return {**result,'reason':'WHOLE_ORIGINAL_SMILES_SYNTAX_NOT_PARSED'}
        atoms=list(mol.GetAtoms())
        if not atoms or any(a.HasQuery() or not 1<=a.GetAtomicNum()<=118 for a in atoms) or any(b.HasQuery() for b in mol.GetBonds()):
            return {**result,'reason':'EMPTY_QUERY_DUMMY_OR_UNCLOSED_ORIGINAL_ATOM_TABLE'}
        zs=[int(a.GetAtomicNum()) for a in atoms];counts=collections.Counter(zs)
        if not any(z!=1 for z in zs):return {**result,'reason':'NO_ORIGINAL_NON_H_ATOMS'}
        return {**result,'state':'SOURCE_SMILES_EXPLICIT_ATOMS_OBSERVED_NOT_GRAPH_IDENTITY','reason':'ATOMIC_NUMBERS_ONLY_UNRESOLVED_GRAPH',
            'atomic_numbers_in_original_parser_order':zs,'explicit_atom_count':len(zs),'explicit_element_counts':[[z,counts[z]] for z in sorted(counts)],
            'all_fragments_retained':True,'implicit_H_or_formula_inferred':False}
    except Exception as exc:return {**result,'reason':'ORIGINAL_UNSANITIZED_PARSE_OR_ATOM_ACCESS_EXCEPTION','exception_type':type(exc).__name__,'message':str(exc)}


def composition(text,Chem,functions):
    value=atoms_only(text,Chem)
    if value['state']=='SOURCE_SMILES_EXPLICIT_ATOMS_OBSERVED_NOT_GRAPH_IDENTITY':
        value['composition']=functions['native_composition'](value['explicit_element_counts'])
    return value


# ORIGINAL_ATOMS_FUNCTIONS_END

def proof():
    import ast
    original=(C.Q.REPO/'workflows/expansion/secondary_tdc_exact2_composition_v1/projection.py').read_text(encoding='utf-8-sig')
    expected=original[original.index('def atoms_only(text,Chem):'):original.index('def observation(')]
    current=__import__('pathlib').Path(__file__).read_text(encoding='utf-8-sig')
    actual=current[current.index('def atoms_only(text,Chem):'):current.index('# ORIGINAL_ATOMS_FUNCTIONS_END')]
    C.need(actual==expected and ast.dump(ast.parse(actual),include_attributes=False)==ast.dump(ast.parse(expected),include_attributes=False),
      'COMPLETE_ORIGINAL_ATOMS_TWO_FUNCTIONS_BYTE_AST_INVERSE')
    old=ast.parse((C.Q.REPO/'workflows/expansion/secondary_tdc_exact2_composition_v1/contracts.py').read_text(encoding='utf-8-sig'))
    values=[ast.literal_eval(n.value) for n in old.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PARAMS' for t in n.targets)]
    C.need(values==[C.PARAMS],'EXACT_ORIGINAL_SIX_PARSER_PARAMS')
    return {'original_two_complete_function_bodies_equal':True,'same_original_parser_params':True,'new_graph_success_claimed':False}