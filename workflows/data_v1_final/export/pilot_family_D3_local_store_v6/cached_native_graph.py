"""SOURCE ONLY: per-worker memo of the original native.graph result.

Future private writer binding: native_bonds=this_module.native_bonds. Never patch
an active producer or original scientific module. OriginalNativeIO still runs
all path/UID/FD/frame checks and native.read payloadSHA/total_atoms guards on
every call. Original Transport still does its second original native.read,
extracts stored raw bond arrays, checks shape/codes and compares each geometry's
z sequence. No coordinates/indices/annotations/codec or QA rules change here.
"""
import collections, json, types
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1 import native_io as OriginalNativeIO
from workflows.data_v1_final.export.family_export_day_v1 import transport as OriginalTransport

READER_MODULE = 'workflows.data_v1_final.export.d5_inputs_builder_v1.reader'
MAX_CACHE_ITEMS = 16384  # LRU eviction only; never a task/RSS stop.
_CACHE = collections.OrderedDict()
_NATIVE_BONDS = None
_HITS = 0
_MISSES = 0


def _graph_copy(value):
    # Original native science already uses Chem.Mol(mol) for independent copies.
    # A caller cannot mutate the graph or ndarrays held privately in this cache.
    from rdkit import Chem
    mol, z, xyz = value
    return Chem.Mol(mol), z.copy(), xyz.copy()


class _GraphOnlyProxy:
    def __init__(self, native, pointer_key):
        self.native, self.pointer_key = native, pointer_key
    def __getattr__(self, name):
        return getattr(self.native, name)
    def graph(self, raw):
        global _HITS, _MISSES
        # Reached only AFTER OriginalNativeIO's unchanged native.read validates
        # this actual record payloadSHA and total_atoms. The raw source x array
        # preserves original atom sequence, dtype and shape without any science
        # transformation; no molecule ID or canonicalized graph is a cache key.
        order = self.native.plain(self.native.field(raw, 'x'))
        key = (self.native, self.native.graph, self.pointer_key,
               order.dtype.str, tuple(order.shape), order.tobytes(order='C'))
        if key in _CACHE:
            _HITS += 1
            value = _CACHE.pop(key); _CACHE[key] = value
            return _graph_copy(value)
        _MISSES += 1
        value = self.native.graph(raw)  # The unmodified original function.
        _CACHE[key] = _graph_copy(value)
        while len(_CACHE) > MAX_CACHE_ITEMS:_CACHE.popitem(last=False)
        return value


def snapshot():
    """Process-local counters only; no IO, validation or performance pass."""
    return dict(hits=_HITS, misses=_MISSES)

def native_record(pointer, native):
    # Includes every original pointer field: source_path, real_index,
    # total_atoms, record_payload_sha256 and any additional original identity.
    # JSON is only a cache-key representation, never output record rewriting.
    pointer_key = json.dumps(pointer, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False)
    proxy = _GraphOnlyProxy(native, pointer_key)
    return OriginalNativeIO.native_record(pointer, proxy)


def native_bonds(pointer, numbers):
    """Original transport bytecode; only its local reader module import changes."""
    global _NATIVE_BONDS
    if _NATIVE_BONDS is None:
        original = OriginalTransport.native_bonds
        code = original.__code__
        OriginalTransport.C.need(code.co_names.count(READER_MODULE) == 1,
                                 'EXACT_ORIGINAL_NATIVE_READER_IMPORT')
        code = code.replace(co_names=tuple(__name__ if name == READER_MODULE else name
                                          for name in code.co_names))
        _NATIVE_BONDS = types.FunctionType(code, dict(original.__globals__), original.__name__,
                                           original.__defaults__, original.__closure__)
        _NATIVE_BONDS.__kwdefaults__ = original.__kwdefaults__
    return _NATIVE_BONDS(pointer, numbers)