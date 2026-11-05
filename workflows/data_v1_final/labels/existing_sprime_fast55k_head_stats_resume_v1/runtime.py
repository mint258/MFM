"""Private operational bindings; scientific functions and all limits stay intact."""
import inspect,os,pathlib,resource,sys,textwrap,types
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_v1 import resource as H
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_v1 import run as HEAD
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import geometry as G,contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import run as ORIGINAL

ROOT=None;ADMIN=None;ORIGIN=None

def administrative_path(path):
    path=pathlib.Path(path)
    if ROOT is None or ROOT not in path.parents:return path
    relative=path.relative_to(ROOT)
    if relative.parts[0] in ('external_resource_credit_events','quota_resource_events','resource_census_events'):
        return ADMIN/relative
    if relative.as_posix() in ('actual_wall_clock.json','serialization_output_resource_credit.json','receipt.json'):
        return ADMIN/relative
    return path

class CurrentImageResource:
    def __getattr__(self,name):return getattr(resource,name)
    def getrusage(self,kind):
        actual=resource.getrusage(kind)
        if kind!=resource.RUSAGE_SELF:return actual
        rows=dict(line.split(':',1)for line in pathlib.Path('/proc/self/status').read_text().splitlines()if ':'in line)
        assert int(rows['Uid'].split()[0])==os.getuid()
        high=int(rows['VmHWM'].split()[0]);rss=int(rows['VmRSS'].split()[0])
        assert high>=rss>0
        return types.SimpleNamespace(ru_maxrss=high)

def bind_worker_memory_metric():
    # Replace only this process's imported guard aliases. Its bytecode and cap
    # comparison remain original; /proc VmHWM describes this exec image.
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import memory as M
    from workflows.data_v1_final.labels.common_train_normalization_day_v1 import memory as CM
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as RM
    for module in (M,CM,RM):
        old=module.soft_worker_rss
        fixed=types.FunctionType(old.__code__,dict(old.__globals__,resource=CurrentImageResource()),old.__name__,old.__defaults__,old.__closure__)
        fixed.__kwdefaults__=old.__kwdefaults__
        assert fixed.__code__ is old.__code__
        for name,loaded in list(sys.modules.items()):
            if name.startswith('workflows.data_v1_final.labels.') and loaded is not None:
                for key,value in list(vars(loaded).items()):
                    if value is old:setattr(loaded,key,fixed)

def pool_initialize(barrier):
    bind_worker_memory_metric()
    G.STATISTICS.pool_initialize(barrier)

class MemoryBinding:
    def __getattr__(self,name):return getattr(I.R,name)
    def start_observer(self,proof,binding):
        binding=dict(binding,resource_evidence_output=str(ROOT)+'_stats_resume_v1_resource_observation')
        return I.R.start_observer(proof,binding)

def resume_private(original,census,**bindings):
    if original in (I.save,I.write_text):
        function=H.local_private(original,census,**bindings)
        def mapped(path,value):return function(administrative_path(path),value)
        return mapped
    if original is I.Budget.__init__:bindings=dict(bindings,R=MemoryBinding())
    return H.local_private(original,census,**bindings)

class Budget(H.LocalBudget):
    def __init__(self,*args):
        original=H.LocalBudget.__init__
        function=types.FunctionType(original.__code__,dict(original.__globals__,local_private=resume_private),original.__name__,original.__defaults__,original.__closure__)
        function(self,*args)
    def close(self):
        I.Budget.close(self)
        if self.serialization_math.last_report is not None:
            ResumeIO().save(ROOT/'serialization_output_resource_credit.json',self.serialization_math.last_report)

class ResumeIO(HEAD.HeadIO):
    def save(self,path,value):
        if isinstance(value,dict) and value.get('schema')=='EXISTING_SPRIME_FAST55K_PILOT_DAY_RECEIPT_V1':
            value['closed_geometry_origin_reference']=ORIGIN
            value['statistics_continuation_only']=True
        return super().save(administrative_path(path),value)

class Statistics:
    def __init__(self):self.PROGRESS_CALLBACK=None
    def __getattr__(self,name):return getattr(G.STATISTICS,name)
    pool_initialize=staticmethod(pool_initialize)
    def execute(self,*args):
        G.STATISTICS.PROGRESS_CALLBACK=self.PROGRESS_CALLBACK
        try:return G.STATISTICS.execute(*args)
        finally:G.STATISTICS.PROGRESS_CALLBACK=None

def continuation_function(io,checkpoint,cfg,geometry):
    source=textwrap.dedent(inspect.getsource(ORIGINAL.execute))
    # Keep the entire original numeric loop, canonicalization and audit suffix.
    start=source.index("    state={'schema':")
    end=source.index('    def checkpoint():',start)
    original_initial=source[start:end]
    replacement="    state=copy.deepcopy(RESUME_STATE)\n    state['numeric_state']['pending_group_errors']=[]\n    sequence=RESUME_SEQUENCE;errors=[];latest=None\n"
    changed=source[:start]+replacement+source[end:]
    first=changed.index('        G.schema_header(')
    last=changed.index('        groups=C.logical(',first)
    original_preparation=changed[first:last]
    preparation=("        coverage_ref=state['coverage_reference'];geometry=RESUME_GEOMETRY\n"
      "        population=state['population_reference'];cfg=copy.deepcopy(RESUME_CONFIG)\n"
      "        cfg.update({k:plan[k] for k in ('source_references','quota_provider_review_reference','quota_provider_identity_reference')})\n"
      "        cfg['data_references']=C.unique([*cfg['data_references'],*plan['data_references'],*I.ALLOWED.values()])\n"
      "        I.configure(cfg)\n"
      "        state['typed_reader_config_reference']=I.save(ADMIN/'selected_reader_config.DATA.json',cfg);checkpoint()\n")
    changed=changed[:first]+preparation+changed[last:]
    old="statsroot=root/'statistics';statsroot.mkdir()"
    new="statsroot=root/'statistics_resume_v1';statsroot.mkdir()"
    assert changed.count(old)==1
    changed=changed.replace(old,new,1)
    inverse=changed.replace(new,old,1).replace(preparation,original_preparation,1).replace(replacement,original_initial,1)
    assert inverse==source
    numeric=source[source.index('        ctx=mp.get_context('):]
    assert changed[changed.index('        ctx=mp.get_context('):]==numeric
    sequences=[int(p.stem.split('_')[-1])for p in ROOT.glob('checkpoint_*.json')if p.stem.split('_')[-1].isdigit()]
    namespace=dict(ORIGINAL.__dict__,C=C,I=io,T=Statistics(),RESUME_STATE=checkpoint,
      RESUME_CONFIG=cfg,RESUME_GEOMETRY=geometry,RESUME_SEQUENCE=max(sequences),ADMIN=ADMIN)
    exec(compile(changed,__file__+'::original_numeric_suffix','exec'),namespace)
    return namespace['execute']
