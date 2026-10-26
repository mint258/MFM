"""Pinned source inheritance; no old profile main/runtime entry is executed."""
from __future__ import annotations
import ast,hashlib,importlib.util,pathlib,sys
from . import contract as C
PINS={'profile_common.py':'ae642a210ba23e11125254790569ce308a090f7e872f86b4f7164170819f7039',
    'run_profile.py':'35a239330bf4378750aa29b1b08ffca8e422c4c4eb4d508571045a97437d8072',
    'prepare_profile.py':'e1175c45d6d25842a4a19fea2c1bb87cfd1288f54e3ef33b29410b4020fbe189'}


def profile_common():
    name='_pm7_cache32_original_profile_common'
    if name in sys.modules:return sys.modules[name]
    path=C.PROFILE/'profile_common.py';C.need(hashlib.sha256(path.read_bytes()).hexdigest()==PINS[path.name],'FROZEN_HOF_READER_SOURCE_CHANGED')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def sources(ref):
    return [*[ref(C.PROFILE/name) for name in PINS],C.SCIENCE_SOURCE,C.SCIENCE_PREPARE,
        ref(C.PROFILE.parent/'common.py'),ref(C.PROFILE.parent/'selection.py')]


def prove_functions(original,current):
    def funcs(text):return {n.name:n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    def body(text,node):return ''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    old,new=funcs(original),funcs(current)
    restored=original
    for name in ('unique_representatives','geometry_orders'):
        C.need(body(original,old[name])==body(current,new[name]) and ast.dump(old[name],include_attributes=False)==ast.dump(new[name],include_attributes=False),
            'FROZEN_UNIQUE_ORDER_FUNCTION_BYTES_OR_AST_CHANGED:'+name)
        restored=restored.replace(body(original,old[name]),body(current,new[name]))
    C.need(restored.encode()==original.encode(),'FUNCTION_REINSERTION_SOURCE_INVERSE_CHANGED')
    return {'exact_function_reinsertion_inverse_equal':True,'whole_old_process_molecule_inverse_claimed':False}


def proof():
    originals={}
    for name,expected in PINS.items():
        body=(C.PROFILE/name).read_bytes();C.need(hashlib.sha256(body).hexdigest()==expected,'ORIGINAL_PROFILE_SOURCE_CHANGED:'+name);originals[name]=body.decode()
    inverse=prove_functions(originals['run_profile.py'],(pathlib.Path(__file__).parent/'core.py').read_text())
    for reference in (C.SCIENCE_SOURCE,C.SCIENCE_PREPARE):
        C.need(hashlib.sha256(pathlib.Path(reference['path']).read_bytes()).hexdigest()==reference['sha256'],'FROZEN_NATIVE_READER_GRAPH_RMSD_SOURCE_CHANGED')
    pc=profile_common()
    return {'status':'EXACT_FROZEN_FUNCTION_BYTES_AND_AST_INHERITED',**inverse,'functions':['unique_representatives','geometry_orders'],
        'native_reader_graph_RMSD':'original pinned sprime_v6 module, unchanged functions; process/embedding/UFF not called',
        'HOF_reader':'original profile_common.read_hof_file/decode_hof/scalar_columns; unchanged',
        'geometry_sha':'original frozen profile_common.IO.geometry_sha','selection_sha256':pc.FROZEN_SELECTION_SHA,
        'old_profile_runtime_or_load_config_called':False,'no_scientific_bodies_read_by_proof':True}
