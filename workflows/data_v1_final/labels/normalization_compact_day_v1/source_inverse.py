"""Full source inverse and unchanged numerical object bindings, CPU preflight."""
import ast,hashlib
from . import contract as C
LAST=None

def proof():
    global LAST
    if LAST is not None:return LAST
    rules=C.meta(C.A.Q.pin(C.HERE/'inverse_rules.json'));out={}
    for row in rules['files']:
        original=C.A.O.pin_bytes(row['original_reference'],C.A.Q.read_small).decode('utf-8-sig')
        expected=original.split('\ndef main():',1)[0] if row['original_prefix_before_main'] else original
        current=(C.HERE/row['file']).read_text(encoding='utf-8-sig')
        if row['file']=='statistics.py':current=current.split('\n# DAY_EXECUTION_HELPERS_BEGIN',1)[0]
        # The extraction writer adds exactly one LF after the frozen prefix.
        if row['original_prefix_before_main']:
            C.need(current.endswith('\n'),'DECLARED_PREFIX_SEPARATOR');current=current[:-1]
        for d in reversed(row['replacements']):
            C.need(current.count(d['new'])==d.get('count',1),'UNIQUE_WHOLE_SOURCE_RESOURCE_INVERSE:'+row['file']);current=current.replace(d['new'],d['old'])
        C.need(current==expected and ast.dump(ast.parse(current),include_attributes=False)==ast.dump(ast.parse(expected),include_attributes=False),'FULL_PREFIX_BYTES_AST_INVERSE:'+row['file'])
        out[row['file']]=row['original_reference']
    from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import bindings as B
    LAST={'status':'SOURCE_PREFIX_BYTE_AST_INVERSE_AND_ORIGINAL_OBJECTS','inverse_original_sources':out,
      'mathematical_function_objects':B.verify_function_objects(),'TSQR_chunk':256,'logical_group_reduction':'ORIGINAL_ORDERED_LEFT_FOLD',
      'original_worker_codec_parser_math_objects_direct':True,'DATA_read':False}
    return LAST
