"""Original build code and helpers; one private DuckDB resource SET differs."""
import builtins
import types
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import prepare as ORIGINAL

ORIGINAL_SET = "SET threads=16;SET memory_limit='8GB';SET max_temp_directory_size='7GB'"
RESOURCE_SET = "SET threads=16;SET memory_limit='32GB';SET max_temp_directory_size='7GB'"

class Connection:
    def __init__(self, original):
        self.original = original
    def __getattr__(self, name):
        return getattr(self.original, name)
    def execute(self, query, *args, **kwargs):
        if query == ORIGINAL_SET and not args and not kwargs:
            query = RESOURCE_SET
        return self.original.execute(query, *args, **kwargs)

class DuckDB:
    def __init__(self, original):
        self.original = original
    def __getattr__(self, name):
        return getattr(self.original, name)
    def connect(self, *args, **kwargs):
        return Connection(self.original.connect(*args, **kwargs))

def private_build():
    old = ORIGINAL.build
    namespace = dict(old.__globals__)
    def import_exact(name, globals=None, locals=None, fromlist=(), level=0):
        module = builtins.__import__(name, globals, locals, fromlist, level)
        return DuckDB(module) if name == 'duckdb' and level == 0 else module
    namespace['__builtins__'] = dict(vars(builtins), __import__=import_exact)
    function = types.FunctionType(old.__code__, namespace, old.__name__, old.__defaults__, old.__closure__)
    function.__kwdefaults__ = old.__kwdefaults__
    return function

def build(*args, **kwargs):
    return private_build()(*args, **kwargs)

def __getattr__(name):
    # Original persistent hash-worker state and close_inputs stay together.
    return getattr(ORIGINAL, name)
