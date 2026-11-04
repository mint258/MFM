"""Same F64 statistics, hashes, masks and radix width; repair cache lifetime."""
import inspect,math,pathlib,struct,textwrap,types
import numpy as np
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_stats_resume_v1 import runtime as P
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_v1 import run as H
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import reader_memo as M
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import statistics as T
from workflows.data_v1_final.labels.streaming_v1 import calibration as K
C=P.C;WORKERS=8;EQUIVALENCE_RAN=False

def f64_bytes(values):
    if not len(values):return b''
    if len(values)==1:return struct.pack('<d',values[0])
    array=np.asarray(values,dtype='<f8')
    C.need(array.ndim==1,'ORIGINAL_FLAT_F64_HASH_STREAM')
    return array.tobytes(order='C')

class ScalarRadix(K.RadixCounts):
    def add(self,fid,values):
        field=self.by_id.get(fid)
        if field is None or not len(values):return
        if len(values)!=1:return super().add(fid,values)
        value=float(values[0])
        if not math.isfinite(value):raise ValueError('NONFINITE_SOURCE_LEAF_REACHED_TRAIN_CALIBRATION')
        if field['transform']=='abs_center':value=abs(value-float(field['center']))
        if math.isnan(value):return super().add(fid,values)
        key=K.float_key(value)
        for node in field['nodes']:
            old=int(node['prefix_bits']);new=min(64,16 if old==0 else old+8)
            if old and key>>(64-old)!=int(node['prefix']):continue
            prefix=key if new==64 else key>>(64-new)
            self.counts[(fid,node['node_id'],new,prefix)]+=1

class Bindings:
    RadixCounts=ScalarRadix
    def __getattr__(self,name):return getattr(T.B,name)

def worker_body(**bindings):
    original=T._group_pass;source=textwrap.dedent(inspect.getsource(original))
    old="            for v in valid:raw=struct.pack('<d',v);hashes[fid].update(raw);mass.update(raw)"
    new="            raw=F64_BYTES(valid);hashes[fid].update(raw);mass.update(raw)"
    C.need(source.count(old)==1,'ONE_ORIGINAL_F64_HASH_LOOP')
    changed=source.replace(old,new,1)
    C.need(changed.replace(new,old,1)==source,'ONLY_EQUAL_F64_BYTE_BATCHING_SOURCE_INVERSE')
    namespace=dict(original.__globals__,B=Bindings(),F64_BYTES=f64_bytes,**bindings)
    exec(compile(changed,__file__+'::equal_f64_byte_batching','exec'),namespace)
    return namespace[original.__name__]

def private(original,**bindings):
    if original is T._group_pass:return worker_body(**bindings)
    if original is T.dispatch_groups:bindings['day_group']=day_group
    return M.private_reader_function(original,**bindings)

def day_group(item):
    original=M.memo_day_group
    function=types.FunctionType(original.__code__,dict(original.__globals__,private_reader_function=private),
        original.__name__,original.__defaults__,original.__closure__)
    return function(item)

class Memo(M.StatisticsMemo):
    def execute(self,*args):
        original=M.StatisticsMemo.execute
        function=types.FunctionType(original.__code__,dict(original.__globals__,private_reader_function=private),
            original.__name__,original.__defaults__,original.__closure__)
        return function(self,*args)

class Statistics:
    def __init__(self):self.PROGRESS_CALLBACK=None;self.memo=Memo()
    def __getattr__(self,name):return getattr(P.G.STATISTICS,name)
    pool_initialize=staticmethod(P.pool_initialize)
    def execute(self,*args):
        self.memo.PROGRESS_CALLBACK=self.PROGRESS_CALLBACK
        try:return self.memo.execute(*args)
        finally:self.memo.PROGRESS_CALLBACK=None

class FreshMemoryBinding(P.MemoryBinding):
    def start_observer(self,proof,binding):
        return P.I.R.start_observer(proof,dict(binding,resource_evidence_output=str(P.ROOT)+'_stats_resume_v3_resource_observation'))

def configure(root,admin,origin):
    P.ROOT=root;P.ADMIN=admin;P.ORIGIN=origin;P.MemoryBinding=FreshMemoryBinding;H.WORKERS=WORKERS

def next_route(state,result):
    P.ORIGINAL.next_route(state,result)
    if result['next_query_stage']is not None:
        state['pending_group_reports']=[];state['pending_group_errors']=[]

def continuation_function(*args):
    original=P.continuation_function;old="statsroot=root/'statistics_resume_v1';statsroot.mkdir()";new="statsroot=root/'statistics_resume_v3';statsroot.mkdir()"
    C.need(original.__code__.co_consts.count(old)==1,'ONE_PRIVATE_STATISTICS_DIRECTORY')
    code=original.__code__.replace(co_consts=tuple(new if v==old else v for v in original.__code__.co_consts))
    function=types.FunctionType(code,dict(original.__globals__,Statistics=Statistics),original.__name__,original.__defaults__,original.__closure__)
    execute=function(*args);execute.__globals__['next_route']=next_route
    return execute

def equivalence(case):
    global EQUIVALENCE_RAN
    values=[-1e300,-2.,-1.,-5e-324,-0.,0.,5e-324,.1,.1,1.,2.,1e300]
    case.assertEqual(f64_bytes(values),b''.join(struct.pack('<d',v)for v in values))
    for purpose in ('median','MAD'):
        for probability in ('0.001','0.5','0.999'):
            request=K.initial_queries([{'field_id':0}],purpose,{0:.25},probability)
            while request['fields']:
                baseline=K.RadixCounts(request);baseline.add(0,values)
                fast=ScalarRadix(request)
                for value in values:fast.add(0,[value])
                case.assertEqual(fast.rows(),baseline.rows())
                request,_=K.advance(request,baseline.rows())
    EQUIVALENCE_RAN=True

def fixtures(parent,root):
    from workflows.data_v1_final.labels.common_train_normalization_day_v1 import test_boundaries as tests
    base=tests.Boundaries;name=sorted(n for n in dir(base)if n.startswith('test_'))[0]
    def same_case(self):
        getattr(base,name)(self);equivalence(self)
    adapted=type('Boundaries',(base,),{name:same_case,'__module__':base.__module__})
    tests.Boundaries=adapted
    try:
        gate=parent.fixtures(root)
        C.need(EQUIVALENCE_RAN,'EXACT_OPTIMIZATION_ORACLE_INSIDE_SAME_SOURCE6_CASE')
        return gate
    finally:tests.Boundaries=base

def reconfiguration(envelope,origin):
    review=C.meta(envelope['tool_cache_continuation_reference'])
    exit=C.meta(review['prior_statistics_exit_reference']);proof=C.meta(review['prior_statistics_proof_reference'])
    receipt=C.meta(review['prior_statistics_receipt_reference']);gate=C.meta(receipt['fixture_gate'])
    C.need(review['schema']=='ROOT_D4_QUERY_CACHE_SCOPE_CONTINUATION_V1'and review['reviewer']=='root'
      and review['scientific_labels_masks_thresholds_or_radix_width_changed']is False
      and review['all_required_median_MAD_and_two_replays_retained']is True,
      'TOOL_CACHE_AND_EXACT_IMPLEMENTATION_ONLY')
    C.need(exit['exit_code']==1 and exit['actual_pid']==proof['pid']and str(exit['actual_start_ticks'])==str(proof['start_ticks'])
      and not pathlib.Path('/proc/'+str(proof['pid'])).exists()and proof['uid']==1278
      and receipt['checkpoint_reference']==origin['actual_checkpoint_reference']
      and gate['status']=='PASS'and gate['tests']==6 and gate['errors']==gate['failures']==0
      and len(receipt['errors'])==1 and receipt['errors'][0]['message']=='RADIX_PREFIX_MASS_CHANGED_BETWEEN_PASSES'
      and review['all_stale_cached_reports_from_previous_query']is True,
      'EXACT_TOOL_QUERY_CACHE_BUG_NOT_SOURCE_DATA_QUALITY_WAIVER')
    return review
