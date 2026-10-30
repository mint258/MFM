"""Resource-only formal Pprime v3; original V2 scientific bodies and once keys."""
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2.contract import *
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import contract as Before

HERE=Q.REPO/'workflows/data_v1_final/pprime/formal_packed_sharded_day_v4'
MODULE='workflows.data_v1_final.pprime.formal_packed_sharded_day_v4.run'
FILES=('__init__.py','contract.py','resource.py','io.py','run.py','metadata.py','test_v1.py','root_metadata.py','prepare_resource.py','README.md')
BASE=Q.ROOT/'artifacts/pprime_formal_packed_sharded_day_v4'
MODES={'SHARED_PREPARE':'pprime_formal_shared_pairs_prepare_v4'}
SOFTWARE_WORKING_BUDGET_BYTES=64<<30
RSS_LIMIT_BYTES=56<<30

def parameters(p):
    need(p['mode']=='SHARED_PREPARE','V4_PREPARE_ONLY_ZERO_NATIVE')
    return dict(Before.parameters(p),software_working_budget_bytes=SOFTWARE_WORKING_BUDGET_BYTES,
      RSS_limit_bytes=RSS_LIMIT_BYTES,MemAvailable_minimum_bytes=4<<30,
      MemAvailable_minimum_node_fraction=.15,resource_version='PPRIME_PREP_ONLY_DUCK32_RSS56_V4',
      preparation_DuckDB_memory_limit='32GB',preparation_DuckDB_max_temp_directory_size='7GB')

def sources(p):
    return unique([*Before.sources(p),*[Q.pin(HERE/n) for n in FILES]])
