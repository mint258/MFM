"""Original native/child/math objects; independent parallel selected-cache IO."""
import builtins,types
from . import fast_coverage
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import geometry as ORIGINAL
from . import reader_memo as MEMO

cohort=ORIGINAL.cohort;schema_header=ORIGINAL.schema_header
build=ORIGINAL.build;metadata_children=ORIGINAL.metadata_children
WORKER=ORIGINAL.WORKER
STATISTICS=MEMO.STATISTICS;ELIGIBILITY=MEMO.ELIGIBILITY

class DuckDBScratch:
    def __init__(self,original):self.original=original
    def __getattr__(self,name):return getattr(self.original,name)
    def connect(self,*args,**kwargs):
        db=self.original.connect(*args,**kwargs)
        db.execute("SET max_temp_directory_size='8GiB'")
        return db

def prepare_function():
    old=ORIGINAL.prepare;namespace=dict(old.__globals__)
    def import_exact(name,globals=None,locals=None,fromlist=(),level=0):
        module=builtins.__import__(name,globals,locals,fromlist,level)
        return DuckDBScratch(module)if name=='duckdb'and level==0 else module
    namespace['__builtins__']=dict(vars(builtins),__import__=import_exact)
    function=types.FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__)
    function.__kwdefaults__=old.__kwdefaults__;return function

def prepare(*args,**kwargs):
    result=prepare_function()(*args,**kwargs);fast_coverage.PREFIX=result[1];return result

class ResourceBudget(ORIGINAL.ResourceBudget):
    def _observe(self):
        super()._observe()
        monitor=ORIGINAL.I.R.MONITOR
        if monitor is not None:
            try:
                observed=ORIGINAL.I.R.process_tree(monitor.pid,monitor.start)
                if observed['tree_rss_bytes']>64<<30:ORIGINAL.I.R.mark_stop('FAST55K_TREE_RSS64GIB_SOFT_CAP',observed)
            except Exception as error:ORIGINAL.I.R.mark_stop('FAST55K_TREE_RSS_OBSERVATION_UNKNOWN',{'error':repr(error)})

class Coverage:
    build=staticmethod(fast_coverage.build)
COVERAGE=Coverage()
