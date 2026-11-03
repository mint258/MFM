"""Same terminal5337 inputs; bounded15-worker read/decode resource adapter."""
import types
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import contract as OLD
P=OLD.P;need=OLD.need;meta=OLD.meta;RUN=OLD.RUN;REPO=OLD.REPO;PY=OLD.PY
KEY='existing_sprime_fast55k_resume_v5';MODULE='workflows.data_v1_final.labels.'+KEY+'.run';HERE=REPO/'workflows/data_v1_final/labels'/KEY
FILES=('__init__.py','contract.py','metadata.py','run.py','geometry.py','packet_io.py','resource_census.py','README.md')
OLDROOT=OLD.OLDROOT;PHASE_ROOT=OLD.PHASE_ROOT
PILOT_COUNTS=OLD.PILOT_COUNTS;GLOBAL_SOURCE_COUNTS=OLD.GLOBAL_SOURCE_COUNTS
unique=OLD.unique;reference=OLD.reference;logical=OLD.logical;resume_authority=OLD.resume_authority;phase_authority=OLD.phase_authority

def __getattr__(name):return getattr(OLD,name)

def scope(p):
    s=OLD.scope(p);s.update(closed_packet_reader_workers=15,maximum_pending_packet_reads=30,
      original_decoder_in_workers=True,original_table_rows_and_schemas_unchanged=True,packet_transfer='PYTHON_PICKLE_ORIGINAL_F64_NONE_AND_ORDER_PRESERVED')
    return s

def plan(p):
    f=OLD.plan;g=dict(f.__globals__,KEY=KEY,scope=scope)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(p)
