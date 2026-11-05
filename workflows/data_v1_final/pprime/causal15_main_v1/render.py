"""Exact decimal token permutation, followed by a checked frozen renderer bridge."""
from __future__ import annotations
from decimal import Decimal
from fractions import Fraction
import copy,hashlib,importlib.util,inspect,pathlib,re,sys
from . import contract as C
FLOAT=re.compile(r'[-+]?\d+\.\d{12}')


def rows(body,name):
    text=body.decode('utf-8','strict');lines=text.splitlines(keepends=True);offset=2 if name=='input.xyz' else 3
    C.need(name in {'input.xyz','input.mop'} and text.endswith('\n'),'EXACT_ORIGINAL_TEXT_INPUT_REQUIRED')
    parsed=[]
    for index,line in enumerate(lines[offset:],offset):
        if not line.strip():continue
        tokens=list(re.finditer(r'\S+',line));parts=[m.group() for m in tokens]
        indices=(1,2,3) if name=='input.xyz' else (1,3,5)
        C.need(len(parts)==(4 if name=='input.xyz' else 7) and (name=='input.xyz' or parts[2::2]==['1','1','1']),
            'EXACT_NATIVE_XYZ_OR_MOPAC_FLAGS')
        values=[parts[i] for i in indices];C.need(all(FLOAT.fullmatch(t) for t in values),'ORIGINAL_12_DECIMAL_INPUT_TOKENS_REQUIRED')
        parsed.append((index,parts[0],values,[tokens[i].span() for i in indices]))
    C.need(0<len(parsed)<=80 and (name!='input.xyz' or int(lines[0].strip())==len(parsed)),'ORIGINAL_ATOM_BOUND_REQUIRED')
    return lines,parsed


def negate(token):
    C.need(FLOAT.fullmatch(token),'EXACT_DECIMAL_TOKEN_REQUIRED')
    result=token[1:] if token.startswith('-') else '-'+(token[1:] if token.startswith('+') else token)
    C.need(Fraction(Decimal(result))==-Fraction(Decimal(token)),'EXACT_DECIMAL_SIGN_FLIP');return result


def p90(body,name):
    lines,parsed=rows(body,name)
    for index,symbol,values,spans in parsed:
        replacement=(negate(values[1]),values[0],values[2]);line=lines[index]
        for (start,end),token in reversed(list(zip(spans,replacement))):line=line[:start]+token+line[end:]
        lines[index]=line
    result=''.join(lines).encode();_,actual=rows(result,name)
    C.need([row[1] for row in parsed]==[row[1] for row in actual],'P90_NEVER_PERMUTES_ATOMS')
    for old,new in zip(parsed,actual):
        x,y,z=(Fraction(Decimal(v)) for v in old[2]);C.need([Fraction(Decimal(v)) for v in new[2]]==[-y,x,z],'P90_EXACT_RATIONAL_COORDINATES')
    return result


def arrays(inputs,symbols):
    import numpy as np
    name='input.mop' if 'input.mop' in inputs else 'input.xyz';_,parsed=rows(inputs[name],name)
    C.need([r[1] for r in parsed]==symbols,'ORIGINAL_NATIVE_ATOM_ORDER')
    return np.asarray([[float(v) for v in r[2]] for r in parsed],dtype='<f8')


def bridge(case,inputs,task,protocol,engine):
    import numpy as np
    actual=arrays(inputs,case['symbols']);rid=case['row']['record_id'];seed=engine.perturb_seed(rid,protocol)
    supplied=actual.copy()
    if task.get('perturbed'):
        supplied=actual-np.random.default_rng(seed).normal(0,protocol['perturb_sigma_A'],actual.shape)
    native={'symbols':list(case['symbols']),'z':np.asarray(case['atomic_numbers'],dtype='<i8'),'coords':supplied,
        'pairs':[tuple(p) for p in case['pairs']],'energy':None,'native_coordinates_sha256':C.sha(supplied.tobytes()),
        'native_atom_order_sha256':case['native_atom_order_sha256']}
    rendered=engine.render_inputs(task,native,case['row'],protocol)
    C.need(rendered==inputs,'BYTE_MISMATCH_STOP_NO_EPSILON_OR_ALTERNATE_SEED')
    C.need(C.sha(native['z'].tobytes())==case['native_atom_order_sha256'],'SOURCE_ATOM_ORDER_SHA')
    return native,seed


def engine(plan,read):
    sys.path[:0]=[str(C.PPRIME),str(C.PPRIME/'vector_audit')]
    from common import load_engine
    pilot=read(plan['pilot_config']);value,contract,protocol=load_engine(pilot)
    C.need(C.sha(pathlib.Path(value.__file__).read_bytes())==C.ENGINE_SHA,'EXACT_FROZEN_ENGINE_SOURCE')
    C.need(protocol['timeout_seconds']==900 and protocol['seed']==20261010 and protocol['perturb_sigma_A']==0.1,
        'ACTUAL_FROZEN900_RECIPE_NO_TIMEOUT_OR_SEED_OVERRIDE')
    for task in protocol['tasks']:
        if task['name'] in {'pm7_B','xtb_perturbed_gradient','xtb_singlepoint'}:C.need('timeout_seconds' not in task,'NO_NEW_TASK_TIMEOUT_OVERRIDE')
    C.need(protocol['frozen_dependencies']['native_lifecycle']['sha256']==C.NATIVE_SHA,'EXACT_FROZEN_INVOKE_SOURCE')
    return value,contract,protocol,pilot


def invoke_identity(engine,protocol):
    path=pathlib.Path(protocol['frozen_dependencies']['native_lifecycle']['path'])
    C.need(C.sha(path.read_bytes())==C.NATIVE_SHA and pathlib.Path(inspect.getsourcefile(engine.NATIVE.invoke))==path,
        'DIRECT_ORIGINAL_INVOKE_CALLABLE_NO_WRAPPER_OR_MONKEYPATCH')
    import ast
    text=path.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='invoke')
    C.need(inspect.getsource(engine.NATIVE.invoke).strip()==ast.get_source_segment(text,node).strip(),'EXACT_INVOKE_FUNCTION_BYTES')
    return {'native_source_sha256':C.NATIVE_SHA,'invoke_callable_source_equal':True,'new_scientific_function_copy':False}
