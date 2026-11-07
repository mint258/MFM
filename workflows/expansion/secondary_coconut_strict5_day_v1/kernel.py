"""Frozen key/strict5 objects; original explicit atoms and source formula counts."""
import collections,hashlib,json,re
from . import contracts as C
Q=C.q
STATE={}

def configure(plan):
    from secondary_coconut_identity_norm_profile_v1.run import load_kernel
    from .frozen import decontamination as D
    from rdkit import Chem,rdBase
    functions,proof=load_kernel(plan)
    C.need(rdBase.rdkitVersion=='2025.09.5' and C.pin(D.__file__)==plan['decontamination_source_reference'],
        'ACTUAL_FROZEN_STRICT5_CONSUMER_AND_RDKIT')
    from workflows.expansion.identity_v2.projection_v2 import native_composition
    STATE.update(functions=functions,Chem=Chem,consumer=D.identity_keys,native=native_composition,proof=proof)
    return proof

def normalized(observation):
    """Replay retained key metadata, never regenerate norm or a full key."""
    functions=STATE['functions'];row=observation['source'];fields=json.loads(row['identity_fields_json']);table=row['source_table']
    names=('canonical_smiles',) if table=='molecules' else ('canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles')
    v=observation['variant_observations'];C.need([x['source_field'] for x in v]==list(names),'ALL_ORIGINAL_VARIANTS_ORDER')
    stored,invalid=functions['full_keys']([fields.get('standard_inchi_key')],strict=False);computed=set();unresolved=missing=0
    for x in v:
        text=fields[x['source_field']];keys,_=functions['full_keys'](x['keys'])
        if text is None or text=='':C.need(x['state']=='MISSING_OR_EMPTY' and keys==[],'MISSING_VARIANT_NOT_A_PARSE_FAILURE');missing+=1
        else:
            C.need(x['state'] in ('KEYS_DERIVED','UNRESOLVED_ORIGINAL_VARIANT'),'RETAINED_PRESENT_VARIANT_STATE')
            C.need(bool(keys)==(x['state']=='KEYS_DERIVED'),'PRESENT_VARIANT_KEYS_STATE_PARITY');unresolved+=not bool(keys)
        computed.update(keys)
    keys=sorted(set(stored)|computed)
    C.need(stored==observation['source_full_keys_valid'] and invalid==observation['source_full_keys_invalid']
        and sorted(computed)==observation['SMILES_derived_full_keys'] and keys==observation['conservative_full_key_union']
        and bool(keys)==observation['has_any_valid_full_key'] and unresolved==observation['unresolved_present_variants']
        and missing==observation['missing_variants'] and bool(stored and computed and set(stored)!=computed)==observation['stored_vs_computed_disagreement'],
        'EXACT_ACTUAL_NORM_UNION_AND_ALL_UNKNOWN_COUNTERS_NO_RENORMALIZATION')
    return row,fields,keys,v

# ORIGINAL_ATOMS_BEGIN
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


# ORIGINAL_ATOMS_END

def formula(text,*,inchi=False):
    result={'state':'UNKNOWN_SOURCE_FORMULA','composition':None,'source_UTF8_sha256':None}
    if not isinstance(text,str) or not text:return dict(result,reason='ABSENT_NATIVE_FORMULA')
    result['source_UTF8_sha256']=hashlib.sha256(text.encode()).hexdigest()
    if any(not 33<=ord(x)<=126 for x in text):return dict(result,reason='WHOLE_FORMULA_NOT_ASCII_NO_TRIMMING')
    if inchi:
        if not (text.startswith('InChI=1S/') or text.startswith('InChI=1/')):return dict(result,reason='NOT_ORIGINAL_SUPPORTED_INCHI_PREFIX')
        text=text.split('/',2)[1]
    counts=collections.Counter();periodic=STATE['Chem'].GetPeriodicTable()
    try:
        for component in text.split('.'):
            C.need(component,'EMPTY_FORMULA_COMPONENT');m=re.match(r'([1-9][0-9]*)?',component);factor=int(m.group() or '1');body=component[m.end():]
            pos=0;found=0
            for token in re.finditer(r'([A-Z][a-z]?)([1-9][0-9]*)?',body):
                C.need(token.start()==pos,'UNCONSUMED_FORMULA_SYNTAX');symbol=token.group(1);z=int(periodic.GetAtomicNumber(symbol))
                C.need(1<=z<=118 and periodic.GetElementSymbol(z)==symbol,'EXACT_ORIGINAL_ELEMENT_SYMBOL')
                counts[z]+=factor*int(token.group(2) or '1');pos=token.end();found+=1
            C.need(found and pos==len(body),'WHOLE_FORMULA_MUST_BE_CONSUMED')
        comp=STATE['native'](dict(counts))
        return dict(result,state='SOURCE_FORMULA_NON_H_COUNTS_NOT_GRAPH_IDENTITY',composition=comp,reason='ORIGINAL_WHOLE_FORMULA_ALL_COMPONENTS')
    except Exception as exc:return dict(result,reason='UNRESOLVED_NATIVE_FORMULA_SYNTAX',exception_type=type(exc).__name__)

def canonical_comp(comp):return json.dumps(comp,separators=(',',':'))

def project(observation,formulas,parent):
    row,fields,keys,variants=normalized(observation);table=row['source_table'];comps={};evidence=[]
    def add(value,basis,locator=None):
        evidence.append({'basis':basis,'locator':locator,'result':value})
        if value.get('composition') is not None:comps[canonical_comp(value['composition'])]=value['composition']
    for item in formulas:add(formula(item['value']), 'ORIGINAL_PROPERTIES_MOLECULAR_FORMULA',item['locator'])
    if table=='molecules':add(formula(fields.get('standard_inchi'),inchi=True),'ORIGINAL_MOLECULE_STANDARD_INCHI_FORMULA')
    need_fallback=not keys or any(v['state']=='UNRESOLVED_ORIGINAL_VARIANT' for v in variants) or len(comps)>1
    if need_fallback:
        for v in variants:
            text=fields[v['source_field']]
            if text is not None and text and (not keys or v['state']=='UNRESOLVED_ORIGINAL_VARIANT'):
                add(composition(text,STATE['Chem'],{'native_composition':STATE['native']}),'ORIGINAL_VARIANT_EXPLICIT_ATOMS',v['source_field'])
    fk='NOT_ENTRY'
    if table=='entries':
        fk='NULL' if fields['molecule_id'] is None else 'MATCHED' if parent is not None else 'ORPHAN'
        if parent is not None:
            C.need(parent['molecule_id']==fields['molecule_id'],'EXACT_ENTRY_ORIGINAL_MOLECULE_FK')
            if need_fallback:
                keys=sorted(set(keys)|set(parent['keys']))
                for comp in parent['compositions']:comps[canonical_comp(comp)]=comp
                evidence.append({'basis':'ORIGINAL_ENTRY_MOLECULE_FK_ASSOCIATED_IDENTITY_NOT_OBSERVED_ENTRY_GRAPH',
                    'parent_locator':parent['locator'],'graph_charge_stereo':'UNKNOWN'})
    # Resolved rows never gain extra broad formula exclusions.
    selected=list(comps.values()) if need_fallback else []
    covered=bool(keys or selected);source_id=table+':'+str(fields['id'])+':'+str(row['copy_block'])+':'+str(row['source_row_ordinal'])
    return {'table':table,'copy_block':row['copy_block'],'ordinal':row['source_row_ordinal'],'original_id':fields['id'],
        'molecule_id':fields['id'] if table=='molecules' else fields['molecule_id'],'source_id':source_id,'keys':keys,'compositions':selected,
        'all_native_compositions':list(comps.values()),'covered':covered,'FK_state':fk,'needs_conservative_fallback':need_fallback,
        'original_norm_counters':{'rows':1,'no_key':int(not observation['has_any_valid_full_key']),
          'present_unresolved':observation['unresolved_present_variants'],'missing':observation['missing_variants'],
          'disagreement':int(observation['stored_vs_computed_disagreement'])},
        'formula_conflict':len(comps)>1,'evidence':evidence,
        'unknown_reason':None if covered else 'NO_ORIGINAL_FULL_KEY_OR_TRUSTWORTHY_NATIVE_COMPOSITION',
        'field_availability':{k:(v is not None and v!='') for k,v in fields.items()},
        'source_row_sha256':row['source_row_sha256'],'graph_identity_repaired':False}

def work(batch):return [project(*item) for item in batch]
