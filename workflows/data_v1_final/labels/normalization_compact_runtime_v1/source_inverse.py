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
    return {'status':'EXACT_SOURCE_WORKER_BYTES_AST_WITH_EXPLICIT_NUMERIC_VIEW_CONTEXT',
      'worker_source_sha256':hashlib.sha256(left.encode()).hexdigest(),'bindings':B.verify_function_objects(),
      'original_WORK_or_global_modified':False,'new_codec_window_and_initialize_are_declared_IO_changes':True,
      'TSQR_chunk':256,'reduction':'ORIGINAL_ORDERED_LEFT_FOLD','DATA_read':False}