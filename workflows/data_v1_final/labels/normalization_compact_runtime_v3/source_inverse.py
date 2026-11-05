"""Runtime SOURCE-only inheritance proof before DATA; never run on login here."""
import ast,hashlib,inspect
from .contract import need

def proof():
    from . import project as N,bindings as B
    from workflows.data_v1_final.labels.bounded_projection_v1 import run as O
    from workflows.data_v1_final.labels.payload_audit_v1 import payload as P,run as PR
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S
    left=inspect.getsource(O.worker);right=inspect.getsource(N.worker)
    need(left==right and ast.dump(ast.parse(left),include_attributes=False)==ast.dump(ast.parse(right),include_attributes=False),'FULL_ORIGINAL_SOURCE_WORKER_BYTES_AND_AST')
    need(N.WORK is not O.WORK and N.Window is not O.Window,'EXPLICIT_OWN_CONTEXT_NOT_MONKEYPATCH')
    for name,expected in [('lookup_batch',S.lookup_batch),('classify_owner',S.classify_owner),('source_columns',PR.source_columns)]:
        need(getattr(N,name) is expected,'DIRECT_FROZEN_SOURCE_ITERATOR_OBJECT:'+name)
    need(B.evaluate is P.evaluate and B.quality_stop_fields is P.quality_stop_fields,'DIRECT_ORIGINAL_ALL264_MASK_QUALITY_KERNELS')
    from pathlib import Path
    from . import contract as C
    # Seven unchanged leaves include the v2 resource clock; codec and reader have
    # explicit binary IO deltas, never a claim that the codec stayed unchanged.
    leaves=('__init__.py','bindings.py','coverage.py','project.py','run.py','runtime.py','statistics.py');unchanged={}
    old=C.REPO/'workflows/data_v1_final/labels/normalization_compact_runtime_v2'
    for name in leaves:
        left_bytes=(old/name).read_bytes();right_bytes=(C.HERE/name).read_bytes()
        need(left_bytes==right_bytes,'EXACT_FROZEN_V2_UNCHANGED_LEAF_BYTES:'+name)
        need(ast.dump(ast.parse(left_bytes),include_attributes=False)==ast.dump(ast.parse(right_bytes),include_attributes=False),'EXACT_FROZEN_V2_UNCHANGED_LEAF_AST:'+name)
        unchanged[name]=hashlib.sha256(right_bytes).hexdigest()
    old_reader=(old/'reader.py').read_text(encoding='utf-8-sig');new_reader=(C.HERE/'reader.py').read_text(encoding='utf-8-sig')
    reader_inverse=new_reader.replace("mask=K.binary_json_loads(row['compact_mask_json'])","mask=json.loads(row['compact_mask_json'])")
    reader_inverse=reader_inverse.replace("entries=K.unpack_entries(row,byid);mask=","entries=K.unpack_entries(row,byid);entries.sort(key=lambda e:e['field_id']);mask=")
    reader_inverse=reader_inverse.replace("\n                            entries.sort(key=lambda e:e['field_id'])",'')
    need(reader_inverse==old_reader and ast.dump(ast.parse(reader_inverse),include_attributes=False)==ast.dump(ast.parse(old_reader),include_attributes=False),'READER_COMPLETE_INVERSE_BINARY_DECODE_AND_PRE_SORT_MASK_PARITY')
    old_codec=(old/'codec.py').read_text(encoding='utf-8-sig');new_codec=(C.HERE/'codec.py').read_text(encoding='utf-8-sig')
    old_tree=ast.parse(old_codec);new_tree=ast.parse(new_codec)
    for name in ('canonical','owner_signature','pack_entries','unpack_entries','schema'):
        a=next(n for n in old_tree.body if isinstance(n,ast.FunctionDef) and n.name==name);b=next(n for n in new_tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        need(ast.get_source_segment(old_codec,a)==ast.get_source_segment(new_codec,b) and ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False),'UNCHANGED_CODEC_SCIENTIFIC_LAYOUT_FUNCTION:'+name)
    a=next(n for n in old_tree.body if isinstance(n,ast.FunctionDef) and n.name=='project');b=next(n for n in new_tree.body if isinstance(n,ast.FunctionDef) and n.name=='project')
    before=ast.get_source_segment(old_codec,a);after=ast.get_source_segment(new_codec,b)
    inverse=after.replace("binary_json_dumps({} if base else B.compact.encode(owner['record_ordinal'],B.TASKS[task],items))","canonical({} if base else B.compact.encode(owner['record_ordinal'],B.TASKS[task],items)).decode()")
    need(inverse==before and ast.dump(ast.parse(inverse),include_attributes=False)==ast.dump(ast.parse(before),include_attributes=False),'CODEC_PROJECT_INVERSE_ONLY_BINARY_MASK_JSON_IO')
    return {'status':'EXACT_SOURCE_WORKER_BYTES_AST_WITH_EXPLICIT_NUMERIC_VIEW_CONTEXT','v2_unchanged_leaf_bytes_AST':unchanged,'codec_binary_IO_delta_declared':True,'reader_binary_decode_pre_sort_parity_inverse':True,
      'worker_source_sha256':hashlib.sha256(left.encode()).hexdigest(),'bindings':B.verify_function_objects(),
      'original_WORK_or_global_modified':False,'new_codec_window_and_initialize_are_declared_IO_changes':True,
      'TSQR_chunk':256,'reduction':'ORIGINAL_ORDERED_LEFT_FOLD','DATA_read':False}