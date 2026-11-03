"""Original execute code: reuse closed cache/packets, original math and six gates."""
import types
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3 import run as OLD
I=OLD.I

def fixtures(root):
    ref=OLD.fixtures(root)
    I.save(root/'closed_geometry_original_projection_proof.json',G.proof())
    return ref

def execute(plan,proof,root,gate,budget):
    f=OLD.ORIGINAL.execute;g=dict(f.__globals__,C=C,G=G,V=G.COVERAGE)
    C.need(G.metadata_children is OLD.G.metadata_children and G.cohort is OLD.G.cohort
      and G.STATISTICS is OLD.G.STATISTICS and G.ELIGIBILITY is OLD.G.ELIGIBILITY,'EXACT_ORIGINAL_SCIENCE_OBJECTS')
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan,proof,root,gate,budget)

def main():
    f=OLD.main;g=dict(f.__globals__,C=C,G=G,fixtures=fixtures,execute=execute,__file__=__file__)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)()
if __name__=='__main__':raise SystemExit(main())
