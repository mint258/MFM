"""Observe duplicate/scope/first-regex versus top-last selection; parser unchanged."""
import collections,json,re,struct
KEY='dipole / a.u.'
class Object:
    def __init__(self,pairs):self.pairs=pairs
class Number(str):pass


def observe(text,parser,parsed_record=None):
    from math_v1 import FLOAT
    tree=json.loads(text,object_pairs_hook=Object,parse_float=Number,parse_int=Number)
    stack=[(tree,'$')];hits=[];duplicates=[];duplicate_count=0
    while stack:
        node,path=stack.pop()
        if type(node) is Object:
            counts=collections.Counter(k for k,v in node.pairs)
            for k,n in counts.items():
                if n>1:
                    duplicate_count+=n-1
                    if len(duplicates)<64:duplicates.append({'scope':path,'key':k,'occurrences':n})
            for i,(key,value) in reversed(list(enumerate(node.pairs))):
                p=path+'/'+key+'#'+str(i)
                if key==KEY:hits.append({'scope':path,'key_assignment_index':i,'number_tokens':[str(v) for v in value] if type(value) is list and all(type(v) is Number for v in value) else None})
                stack.append((value,p))
        elif type(node) is list:
            stack.extend((v,path+'/'+str(i)) for i,v in reversed(list(enumerate(node))))
    regex=list(re.finditer(r'"dipole / a\.u\."\s*:\s*\[([^\]]+)\]',text))
    tokens=[re.findall(FLOAT,m.group(1)) for m in regex];top=[v for k,v in tree.pairs if k==KEY] if type(tree) is Object else []
    selected=[str(v) for v in top[-1]] if top and type(top[-1]) is list and all(type(v) is Number for v in top[-1]) else None
    def bits(values):return [struct.pack('<d',float(v.replace('D','E').replace('d','e'))).hex() for v in values] if values is not None else None
    actual=parser.xtb_dipole(text);original_values=None if actual is None else actual['raw_atomic_units']
    return {'target_key':KEY,'target_key_assignments_all_scopes':len(hits),'top_level_target_key_assignments':len(top),
        'JSON_duplicate_key_extra_assignments_all_scopes':duplicate_count,'duplicate_key_examples_at_most64':duplicates,
        'target_scope_examples_at_most64':hits[:64],'target_scope_examples_truncated':len(hits)>64,
        'regex_matches_all_scopes':len(regex),'first_regex_number_tokens':tokens[0] if tokens else None,
        'last_regex_number_tokens':tokens[-1] if tokens else None,'json_default_top_level_last_assignment_tokens':selected,
        'regex_first_and_top_last_exact_tokens_equal':bool(tokens) and selected==tokens[0],
        'regex_first_and_top_last_binary64_equal':bool(tokens) and selected is not None and bits(tokens[0])==bits(selected),
        'original_parser_actual_raw_atomic_units':original_values,
        'original_parser_equal_first_regex_binary64':original_values is not None and bool(tokens) and bits(original_values_as_tokens(original_values))==bits(tokens[0]),
        'original_parser_equal_recovered_record':actual==parsed_record if parsed_record is not None else None,
        'original_parser_raw_values_binary64_equal_recovered_record':bits(original_values_as_tokens(original_values))==bits(original_values_as_tokens(parsed_record['raw_atomic_units']))
            if original_values is not None and parsed_record is not None else None,
        'parser_callable_filename':parser.xtb_dipole.__code__.co_filename,'parser_modified':False,'causal_claim':'UNKNOWN_OBSERVATION_ONLY'}


def original_values_as_tokens(values):return [repr(v) for v in values]
