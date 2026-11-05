"""Private current-run admission; unchanged Source3/publication/scientific body."""
import types
from . import contract as C,prepare as P,scope,component
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import run as Original,io as OriginalIO
from workflows.data_v1_final.pprime.current_prepared_component_parentstate_v3 import run as Current


def clone(old,**bindings):
    f=types.FunctionType(old.__code__,dict(old.__globals__,**bindings),old.__name__,old.__defaults__,old.__closure__)
    f.__kwdefaults__=old.__kwdefaults__;return f

class Budget(OriginalIO.Budget):
    def __init__(self,*args,**kwargs):clone(OriginalIO.Budget.__init__,C=C)(self,*args,**kwargs)
class IO:
    Budget=Budget
    def __getattr__(self,name):return getattr(OriginalIO,name)
I=IO()


def shared_prepare(plan,proof,out,local,b,store,budget):
    U=Original.U;local_store=OriginalIO.Store(local,30<<30)
    ref,m=scope.freeze(plan,proof,local/'fill_scope',b,budget,local_store)
    paths=[__import__('pathlib').Path(r['path'])for r in [*m['tables'].values(),*m['component_references'],ref]]
    ready=U.ready(local,paths,'PREP',proof,'fill_scope',local_store,dict(fill_scope_reference=ref,native_invokes=0))
    published=U.publish(ready,budget,store,out,U.Pool(plan['shared_pool_root_review_reference'],'PREP'))
    C.need(published['published'],'CLOSED_FILL_SCOPE_LOCAL_PRESERVED_NOT_YET_SHARED')
    mapping=published['entries'];remote=dict(m,tables={k:U.relocated(v,mapping)for k,v in m['tables'].items()},component_references=[])
    import json,pathlib
    for k,old in enumerate(m['component_references']):
        h=json.loads(pathlib.Path(old['path']).read_bytes());h['tasks_reference']=remote['tables']['tasks']
        h.update(original_local_header_reference=old,scope_publication_reference=published['publication_manifest_reference'])
        remote['component_references'].append(store.json(out/('fill_generation_component_%05d.json'%k),h))
    remote.update(original_local_scope_reference=ref,scope_publication_reference=published['publication_manifest_reference'])
    ref=store.json(out/'fill_scope_closed.json',remote)
    b=dict(b,headers=[(r,C.meta(r))for r in remote['component_references']],fill_scope_reference=ref,fill_scope=remote)
    budget.scope_forecast_records=budget.forecast_records=max(1,remote['actual_first2_records'])
    effective=dict(plan,generation_partition_QA_reference=ref)
    return clone(Original.shared_prepare,P=P)(effective,proof,out,local,b,store,budget)

def execution(plan,proof,out,local,b,store,budget,event):
    qa=component.verify_component(plan,proof,budget)
    store.json(out/'closed_component_independent_CPU_QA.json',qa)
    return clone(Original.execution,C=C)(plan,proof,out,local,b,store,budget,event)


def main():return clone(Original.main,C=C,I=I,fixtures=Current.fixtures,shared_prepare=shared_prepare,execution=execution)()
if __name__=='__main__':raise SystemExit(main())