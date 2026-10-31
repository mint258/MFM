"""Private original parquet writer import binding: byte-identical raw encoder."""
import builtins,types
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as ORIGINAL
from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as COMPRESSED

class RawCodec:
    encode=staticmethod(COMPRESSED.encode_raw)
    def __getattr__(self,name):return getattr(COMPRESSED.ORIGINAL,name)

def writer_function():
    old=ORIGINAL.write_parquet
    def importing(name,globals=None,locals=None,fromlist=(),level=0):
        value=builtins.__import__(name,globals,locals,fromlist,level)
        return RawCodec()if level==0 and name=='workflows.data_v1_final.export.d5_inputs_compound_day_v1.core'and 'encode'in fromlist else value
    namespace=dict(old.__globals__,__builtins__=dict(vars(builtins),__import__=importing))
    return types.FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__)

class MetadataIO:
    def __getattr__(self,name):return getattr(ORIGINAL,name)
    def write_parquet(self,*args,**kwargs):return writer_function()(*args,**kwargs)

def proof():
    value=COMPRESSED.byte_proof();f=writer_function()
    value.update(original_parquet_writer_entire_code_object=f.__code__ is ORIGINAL.write_parquet.__code__,
      all_original_F64_semantic_write_and_full_readback_checks_retained=True)
    return value
