"""Original full execute: reuse closed geometry, private byte-preserving SQLite IO."""
import types
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v5 import run as OLD
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import run as ORIGINAL
I=OLD.I

def fixtures(root):
    ref=OLD.fixtures(root);I.save(root/'closed_tables_and_compressed_IO_source_proof.json',G.proof());return ref

def execute(plan,proof,root,gate,budget):
    f=ORIGINAL.execute;namespace=dict(f.__globals__,C=C,G=G,V=G.COVERAGE)
    C.need(G.STATISTICS is OLD.G.STATISTICS and G.ELIGIBILITY is OLD.G.ELIGIBILITY
      and G.metadata_function().__code__ is OLD.G.metadata_children.__code__,'ORIGINAL_STATISTICS_ELIGIBILITY_AND_METADATA_CODE_WITH_ONLY_IO_BINDINGS')
    return types.FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)(plan,proof,root,gate,budget)

def main():
    f=OLD.main;namespace=dict(f.__globals__,C=C,G=G,fixtures=fixtures,execute=execute,__file__=__file__)
    return types.FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)()
if __name__=='__main__':raise SystemExit(main())
