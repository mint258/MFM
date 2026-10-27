"""A new atoms-only seam; no successful graph identity or automatic exclusion."""
import collections,hashlib,importlib,json
from pathlib import Path
from secondary_coconut_identity_norm_profile_v1.run import load_kernel
from . import contracts as C
Q=C.Q


def dump(v):return (json.dumps(v,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(v):return hashlib.sha256(dump(v)).hexdigest()


def load(plan):
    unused,proof=load_kernel(plan);p=importlib.import_module('workflows.expansion.identity_v2.projection_v2')
    old=importlib.import_module('workflows.expansion.tdc_zip44_identity_main_v1.projection')
    f=importlib.import_module('workflows.expansion.secondary_missing11_identity_format_probe_v1.formats')
    for key,module in (('projection',old),('formats',f)):
        Q.need(Q.ref(module.__file__)==plan['frozen_csv_source_references'][key]['target_reference'],'ACTUAL_UNMODIFIED_CSV_SOURCE_OBJECT')
    Q.need(old.IdentityCSV.__mro__[1] is f.CSVProjection and all(getattr(old.IdentityCSV,k) is getattr(f.CSVProjection,k) for k in ('feed','finish','append')),
        'NO_NEW_CSV_GRAMMAR_OR_IDENTITY_CALLBACK')
    functions={'native_composition':p.native_composition,'identity':p.identity}
    proof={**proof,'not_invoked':['source_smiles_keys','wp5_key'],'atoms_only_functions':{
        n:{'module':x.__module__,'filename':x.__code__.co_filename,'first_line':x.__code__.co_firstlineno} for n,x in functions.items()},
        'grammar_function_objects':old.grammar_proof(),'new_evidence_seam_not_old_policy_acceptance':True}
    return p.rdkit_identity_modules(),functions,old.IdentityCSV,proof


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


def observation(row,original_result,Chem,functions):
    Q.need(original_result['source']==row and original_result['identity_state']=='ORIGINAL_SMILES_UNRESOLVED'
        and original_result['full_InChIKeys']==original_result['WP5_keys']==[] and original_result['identity_errors'],'ORIGINAL_UNKNOWN_RESULT_UNCHANGED')
    evidence=composition(row['original_Drug']['text'],Chem,functions);reason='TDC_ORIGINAL_SMILES_EXPLICIT_ATOMS_UNRESOLVED_GRAPH_NEW_EVIDENCE_SEAM'
    token=row['original_Drug_ID']['text'];ordinal=row['physical_record_ordinal'];physical=row['member_name']+':'+str(ordinal)
    identity=functions['identity']('tdc_admet_group_zip',physical,row['original_split'],[row['original_Drug']['text']],[],
        memberships=[row['original_split']],composition=evidence['composition'],reason=reason if evidence['composition'] is not None else None,unresolved_variant=True)
    source={'source_id':'tdc_admet_group_zip:'+row['member_name'],'source_row_ordinal':ordinal,'role':row['original_split'],
        'source_offset':None,'source_record_bytes':len(dump(row)),'source_record_sha256':digest(row),
        'original_native_ID':token,'original_source':row,'original_result':original_result,
        'source_record_byte_basis':'CANONICAL_ORIGINAL_IDENTITY_FIELDS_NOT_ORIGINAL_CSV_RECORD_BYTES'}
    return {'source':source,'physical_identity':physical,'SMILES_derived_full_keys':[],'WP5_keys':[],
        'key_state':'ORIGINAL_SMILES_UNRESOLVED','missing_full_key':True,'identity_errors':original_result['identity_errors'],
        'atoms_only_evidence':evidence,'frozen_identity_candidate_not_accepted':identity,'automatic_policy_acceptance':False,
        'graph_charge_stereo_and_original_cause':'UNKNOWN','original_result_unchanged':True,'global_decontamination_pool_training_release':False}
