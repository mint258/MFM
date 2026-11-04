"""Unique current-component execution authority; same original science and once."""
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.contract import *
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v3 import contract as Original
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import contract as V2
KEY='pprime_current_closed_component_future_v2'
MODULE='workflows.data_v1_final.pprime.current_prepared_component_future_v2.run'
HERE=Q.REPO/'workflows/data_v1_final/pprime/current_prepared_component_future_v2'
FILES=('__init__.py','contract.py','authority.py','metadata.py','run.py','test_v1.py','resource_forecast.py','README.md')
BASE=Q.ROOT/'artifacts/pprime_current_prepared_component_future_v2';MODES={'EXECUTE':KEY}

def parameters(p):
    need(p['mode']=='EXECUTE','ONLY_CURRENT_COMPONENT_ORIGINAL_EXECUTION_SCOPE')
    return dict(Original.parameters(p),preparation_authority_kind='CURRENT_PARENT_CLOSED_PREPARED_COMPONENT_NOT_PARENT_C0',
      component_root_review_reference=p['shared_preparation_root_acceptance_reference'])

def bootstrap(p):
    from . import authority as A
    V2.shape(p);need(p['mode']=='EXECUTE','ONLY_ONE_CLOSED_COMPONENT')
    b=V2.Old.bootstrap(p);headers,data,refs=V2.partition(p,b);b=dict(b,headers=headers)
    b['data']=unique([*b['data'],*data]);b['refs']=unique([*b['refs'],*refs]);h,component_sources,component_data=A.metadata_bind(p)
    need(len(headers)==1 and h['generation_shard_header_reference']==headers[0][0]
      and h['generation_partition_QA_reference']==p['generation_partition_QA_reference'],'EXACT_FROZEN_ASSIGNED_SHARD_COMPONENT')
    b['prepared']=h;b['data']=unique([*b['data'],*component_data]);b['refs']=unique([*b['refs'],*component_sources]);return b

def sources(p):return unique([*Original.sources(p),*[Q.pin(HERE/n)for n in FILES]])
