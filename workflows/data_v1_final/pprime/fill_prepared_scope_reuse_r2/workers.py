"""Whole original hash workers; private owned-scratch/output IO bindings only."""
import concurrent.futures as cf,multiprocessing as mp,pathlib,types
from . import io_adapter as A
from .bare_imports import pprime_bootstrap
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as Original
_STATE=None


def initialize(session,context,protocol,audit,root):
    global _STATE
    import builtins,tempfile
    root=pathlib.Path(root);scratch=root/'hash_scratch';scratch.mkdir(exist_ok=True)
    native_import=builtins.__import__
    def mkdtemp(*args,**kwargs):
        A.need(kwargs.get('dir')=='/tmp'and kwargs.get('prefix','').startswith('pprime_input_hash_'),'ONLY_ORIGINAL_HASH_SCRATCH_REDIRECT')
        return tempfile.mkdtemp(*args,**dict(kwargs,dir=str(scratch)))
    temp=types.SimpleNamespace(**{k:v for k,v in vars(tempfile).items()if k!='mkdtemp'},mkdtemp=mkdtemp)
    def private_import(name,*args,**kwargs):return temp if name=='tempfile'else native_import(name,*args,**kwargs)
    io=types.SimpleNamespace(**{k:v for k,v in vars(Original.I).items()if k!='Store'},Store=A.Store)
    _STATE=dict(Original.__dict__,I=io,__builtins__=dict(vars(builtins),__import__=private_import))
    # All original graph/adapt/input_hashes/NoInvoke objects remain globals of
    # the original worker body. No shared module or engine object is patched.
    for name in ('hash_close','hash_one','hash_initialize'):
        f=getattr(Original,name);g=types.FunctionType(f.__code__,_STATE,f.__name__,f.__defaults__,f.__closure__);g.__kwdefaults__=f.__kwdefaults__;_STATE[name]=g
    with pprime_bootstrap(Original.C.Q.REPO,native_engine=True):
        _STATE['hash_initialize'](session,context,protocol,audit,str(root))


def one(work):return _STATE['hash_one'](work)


class HashPool:
    def __init__(self,plan,proof,context,local,budget):
        self.plan,self.proof,self.context=plan,proof,context;self.local=pathlib.Path(local);self.budget=budget;self.pool=None;self.closures=[]
    def block(self,block,plan,proof,b,audit,out,budget):
        if self.pool is None:
            (self.local/'hash_workers').mkdir();session=Original.I.source_session(A.pin_small(plan['plan_path']),plan,proof)
            self.pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=initialize,
              initargs=(session,self.context,plan['original_protocol_reference'],audit,str(self.local)))
        A.need(len(block)<=128,'ORIGINAL_BOUNDED_HASH_DISPATCH128')
        for result in self.pool.map(one,[(rid,bytes(blob))for rid,blob in block],chunksize=1):budget.check();yield result
    def close(self):
        if self.pool is None:return
        processes=list(self.pool._processes.values());self.pool.shutdown(wait=True,cancel_futures=False);self.pool=None
        for process in processes:
            path=self.local/'hash_workers'/('worker_%d_closed.json'%process.pid)
            A.need(not process.is_alive()and process.exitcode==0 and path.is_file(),'ORIGINAL_ALL16_HASH_WORKERS_CLOSED')
            ref=Original.I.pin(path,[self.local]);value=A.meta(ref)
            A.need(value['native_invokes']==0 and value['original_engine_closed']is True,'ORIGINAL_NOINVOKE_WORKER_CLOSE')
            self.closures.append(dict(value,reference=ref))