"""Select native tokens from the exact frozen parser branches; ambiguity is UNKNOWN."""
from __future__ import annotations
import json,re
from precision import need


class RawNumber(str):pass


def unique_object(pairs):
    out={}
    for key,value in pairs:
        need(key not in out,'DUPLICATE_JSON_KEY_AMBIGUOUS:'+key);out[key]=value
    return out


def aux_entries(text,key,count,float_pattern):
    header=re.compile(r'^[ \t]*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?[ \t]*=[ \t]*(.*)$')
    hits=[];active=None
    for line_number,line in enumerate(text.splitlines(),1):
        match=header.match(line)
        if match:
            if active is not None:hits.append(active)
            name,n,tail=match.groups();active={'count':int(n) if n is not None else None,'entries':[]} if name.strip()==key else None
            if active is not None:
                for token in tail.split():active['entries'].append({'token':token,'source_line':line_number})
        elif active is not None and not line.lstrip().startswith('#'):
            active['entries'].extend({'token':token,'source_line':line_number} for token in line.split())
    if active is not None:hits.append(active)
    need(len(hits)==1,'AUX_FIELD_MISSING_OR_DUPLICATE_AMBIGUOUS:'+key)
    hit=hits[0];need(hit['count']==count and len(hit['entries'])>=count,'NATIVE_AUX_DECLARED_COUNT_MISMATCH:'+key)
    selected=hit['entries'][:count]
    need(all(re.fullmatch(float_pattern,e['token']) for e in selected),'AUX_NUMERIC_TOKEN_REQUIRED')
    return [dict(entry,source_artifact='input.aux',array_key=key,selected_token_index=i,
        source_branch='FROZEN_NATIVE_AUX_LABELS_FIRST_DECLARED_COUNT') for i,entry in enumerate(selected)]


def json_dipole_entries(text,float_pattern):
    value=json.loads(text,parse_float=RawNumber,parse_int=RawNumber,object_pairs_hook=unique_object)
    rows=value.get('dipole / a.u.')
    need(isinstance(rows,list) and len(rows)==3 and all(isinstance(v,RawNumber) and re.fullmatch(float_pattern,v) for v in rows),
        'XTB_JSON_DIPOLE_MISSING_OR_NOT_EXACT_NUMERIC3')
    # JSON lexer selects this exact unique object key; the regex only binds source locations.
    matches=list(re.finditer(r'"dipole / a\.u\."\s*:\s*\[([^\]]+)\]',text))
    need(len(matches)==1,'XTB_JSON_DIPOLE_LOCATION_AMBIGUOUS')
    match=matches[0];tokens=list(re.finditer(float_pattern,match.group(1)))
    need([m.group(0) for m in tokens]==list(rows),'JSON_LEXER_AND_SOURCE_TOKEN_LOCATOR_DISAGREE')
    return [{'token':str(token),'source_artifact':'xtbout.json','json_key':'dipole / a.u.',
        'source_line':text[:match.start(1)+m.start()].count('\n')+1,'selected_token_index':i,
        'source_branch':'FROZEN_LEGACY_PARSE_XTB_JSON_DIPOLE'} for i,(token,m) in enumerate(zip(rows,tokens))]


def gradient_entries(text,symbols,float_pattern):
    rows=[(n,line.split()) for n,line in enumerate(text.splitlines(),1)]
    coords=[row for _,row in rows if len(row)==4 and row[3] in symbols]
    vectors=[(n,row) for n,row in rows if len(row)==3 and all(re.fullmatch(float_pattern,v) for v in row)]
    need(len(coords)==len(vectors)==len(symbols) and [row[3] for row in coords]==symbols,'FROZEN_XTB_SINGLE_GRADIENT_BLOCK_NOT_UNAMBIGUOUS')
    return [{'token':token,'source_artifact':'gradient','source_line':n,'selected_token_index':3*i+axis,
        'source_branch':'FROZEN_LEGACY_PARSE_XTB_LEN3_NUMERIC_ROWS'} for i,(n,row) in enumerate(vectors) for axis,token in enumerate(row)]


def select_field(files,field,symbols,parser):
    text={item['name']:item['data'].decode('utf-8',errors='replace') for item in files}
    try:
        if field=='pm7_dipole_Debye':entries=aux_entries(text['input.aux'],'DIP_VEC:DEBYE',3,parser.FLOAT);factor=1.;unit='Debye';key='dipole_Debye'
        elif field=='pm7_gradient_kcal_mol_A':entries=aux_entries(text['input.aux'],'GRADIENTS:KCAL/MOL/ANGSTROM',3*len(symbols),parser.FLOAT);factor=1.;unit='kcal/(mol Angstrom)';key='gradient_kcal_mol_A'
        elif field=='xtb_dipole_Debye':entries=json_dipole_entries(text['xtbout.json'],parser.FLOAT);factor=parser.AU_DIPOLE_TO_DEBYE;unit='Debye (native token atomic units)';key='dipole_Debye'
        elif field=='xtb_gradient_Eh_bohr':entries=gradient_entries(text['gradient'],symbols,parser.FLOAT);factor=1.;unit='Eh/bohr';key='gradient_Eh_bohr'
        else:raise ValueError('UNSUPPORTED_ORIGINAL_FAILURE_FIELD')
        return {'status':'UNIQUE_NATIVE_TOKEN_SELECTION','entries':entries,'factor_from_frozen_parser':factor,'field_unit':unit,'parser_field':key}
    except Exception as exc:return {'status':'UNKNOWN','reason':type(exc).__name__+': '+str(exc),'no_precision_guessed':True}