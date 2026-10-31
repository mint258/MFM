"""Original execute and six preflights; only parallel closed packet IO differs."""
import types
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import run as OLD
I=OLD.I

def fixtures(root):
    ref=OLD.fixtures(root);I.save(root/'parallel_original_packet_IO_proof.json',G.proof());return ref

def execute(plan,proof,root,gate,budget):
    f=OLD.execute;g=dict(f.__globals__,C=C,G=G)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan,proof,root,gate,budget)

def main():
    f=OLD.main;g=dict(f.__globals__,C=C,G=G,fixtures=fixtures,execute=execute,__file__=__file__)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)()
if __name__=='__main__':raise SystemExit(main())
