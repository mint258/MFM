"""Resource-only formal Pprime v3; original V2 scientific bodies and once keys."""
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2.contract import *
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import contract as Before

HERE=Q.REPO/'workflows/data_v1_final/pprime/formal_packed_sharded_day_v3'
MODULE='workflows.data_v1_final.pprime.formal_packed_sharded_day_v3.run'
FILES=('__init__.py','contract.py','resource.py','io.py','run.py','metadata.py','test_v1.py','root_metadata.py','README.md')
BASE=Q.ROOT/'artifacts/pprime_formal_packed_sharded_day_v3'
MODES={'SHARED_PREPARE':'pprime_formal_shared_pairs_prepare_v3',
       'EXECUTE':'pprime_formal_assigned_pairs_execute_v3',
       'RECOVER_PUBLISH':'pprime_formal_readonly_publish_recovery_v3'}
SOFTWARE_WORKING_BUDGET_BYTES=64<<30
RSS_LIMIT_BYTES=56<<30

def parameters(p):
    return dict(Before.parameters(p),software_working_budget_bytes=SOFTWARE_WORKING_BUDGET_BYTES,
      RSS_limit_bytes=RSS_LIMIT_BYTES,MemAvailable_minimum_bytes=4<<30,
      MemAvailable_minimum_node_fraction=.15,resource_version='PPRIME_PRIVATE_RSS56_V3')

def sources(p):
    return unique([*Before.sources(p),*[Q.pin(HERE/n) for n in FILES]])
