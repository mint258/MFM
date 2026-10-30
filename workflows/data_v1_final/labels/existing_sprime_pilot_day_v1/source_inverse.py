"""CPU-before-DATA byte/AST witnesses and direct original scientific objects."""
import ast,hashlib,inspect,json
from pathlib import Path
from . import contract as C,bindings as B,geometry as G

def digest(raw):return hashlib.sha256(raw).hexdigest()

def function_source(source,name):
    tree=ast.parse(source);matches=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    C.need(len(matches)==1,'EXACT_SINGLE_ORIGINAL_SCIENTIFIC_FUNCTION:'+name);n=matches[0]
    text=''.join(source.splitlines(keepends=True)[n.lineno-1:n.end_lineno])
    return text,ast.dump(n,include_attributes=False)

def proof():
    witness=C.meta(C.P.pin(C.HERE/'frozen_source_witness.json'));C.need(witness['schema']=='EXISTING_SPRIME_PILOT_SOURCE_INHERITANCE_V1','EXACT_SOURCE_INHERITANCE_WITNESS')
    results={}
    for item in witness['byte_identical_local_leaves']:
        old=(C.REPO/item['original_relative_path']).read_bytes();current=(C.HERE/item['local_name']).read_bytes()
        C.need(len(old)==item['bytes'] and digest(old)==item['sha256'] and current==old,'EXACT_ORIGINAL_FULL_MODULE_BYTES:'+item['local_name'])
        C.need(ast.dump(ast.parse(current),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),'EXACT_ORIGINAL_FULL_MODULE_AST')
        results[item['local_name']]='EXACT_MODULE_BYTES_AND_AST'
    item=witness['reader_IO_delta'];old=(C.REPO/item['original_relative_path']).read_bytes();current=(C.HERE/'reader.py').read_bytes()
    C.need(len(old)==item['bytes'] and digest(old)==item['sha256'],'ORIGINAL_READER_BYTE_WITNESS')
    expected=old.decode('utf-8')
    for replacement in item['replacements']:
        C.need(expected.count(replacement['old'])==1,'EXACT_SINGLE_DECLARED_READER_IO_DELTA');expected=expected.replace(replacement['old'],replacement['new'])
    C.need(current==expected.encode('utf-8'),'WHOLE_READER_ONLY_DECLARED_SELECTED_MASS_IO_DELTA')
    science=witness['original_D7_function'];original=(C.REPO/science['relative_path']).read_bytes().decode('utf-8')
    before,tree=function_source(science['source_utf8'],'d7');actual,actual_tree=function_source(original,'d7')
    C.need(before==actual and tree==actual_tree,'ORIGINAL_D7_FUNCTION_FULL_TEXT_AND_AST')
    observed=inspect.getsource(G.OriginalWorker.d7)
    C.need(observed.replace('\r\n','\n').rstrip('\n')==actual.replace('\r\n','\n').rstrip('\n'),'DIRECT_IMPORTED_D7_FUNCTION_SAME_FROZEN_BODY')
    M=G.OriginalMath
    C.need(M.geometry_orders is M.PM7.geometry_orders and M.unique_representatives is M.PM7.unique_representatives
        and M.scaffold_chunk is M.ORIGINAL.scaffold_chunk,'DIRECT_ORIGINAL_FIXED_RANDOM_RMSD_HOF_SCAFFOLD_OBJECTS')
    C.need(G.OriginalWorker.d7 is G.OriginalWorker.__dict__['d7'],'NO_GLOBAL_D7_MONKEYPATCH')
    B.verify()
    from .originals import objects,proof as import_proof
    _,reducer,series,_,_=objects()
    C.need(B.views is series.views and callable(reducer.rho_external),'DIRECT_ORIGINAL_RHO_AND_VIEWS_IMPORT_CLOSED_BEFORE_DATA')
    return {'status':'EXACT_ORIGINAL_MATH_MODULES_AND_D7_OBJECT_WITH_EXPLICIT_PROVISIONAL_IO_SEAMS',
        'byte_identical_modules':results,'reader_delta':'ONLY_SELECTED_ORIGINAL_GROUP_RECORD_MASS_NOT_FULL_SOURCE_COUNT',
        'original_TSQR_chunk':256,'physical_part_QR_reset':False,'math_or_recipe_or_seed_threshold_changed':False,
        'codec':'DIRECT_ORIGINAL_COMPACT_TYPED_BINARY_JSON_V3','original_scientific_globals_patched':False,
        'isolated_original_imports':import_proof(),
        'new_bounded_identity_geometry_coverage_and_metadata_not_old_full_authority':True}
