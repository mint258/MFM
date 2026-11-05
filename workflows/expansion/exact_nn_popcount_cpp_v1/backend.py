"""Lazy explicitly pinned native prototype; score division remains Python binary64."""
import importlib.util
import os
from pathlib import Path
import sys
import sysconfig
import time
from ..exact_nn_cached_v1 import engine as oracle
from . import IMPLEMENTATION
from .artifacts import need, reference, verify, load_metadata

MODULE = '_ecfp4_popcount_kernel_v1'
SOURCES = ('__init__.py', 'artifacts.py', 'backend.py', 'build.py', 'kernel.c')
BUILD_SCHEMA = 'EXACT_POPCOUNT_PRIVATE_COPY_PROTOTYPE_BUILD_V1'
BUILD_STATUS = 'COMPILED_PROTOTYPE_PENDING_NATIVE_EQUIVALENCE_AND_ROOT_ADOPTION'
_LOADED = None
_LOADED_BINDING = None


def load_kernel(build_manifest_reference):
    """No compiler, search-path fallback, auto-install or unpinned .so import."""
    global _LOADED, _LOADED_BINDING
    need(sys.platform.startswith('linux'), 'Prototype native RSS/build ABI currently supports Linux only')
    manifest = load_metadata(build_manifest_reference)
    need(manifest['schema'] == BUILD_SCHEMA and manifest['status'] == BUILD_STATUS
        and manifest['implementation'] == IMPLEMENTATION and manifest['module_name'] == MODULE,
        'Explicit new prototype build, never a production adoption claim')
    need(manifest['python']['soabi'] == sysconfig.get_config_var('SOABI')
        and manifest['python']['cache_tag'] == sys.implementation.cache_tag
        and manifest['python']['version'] == sys.version, 'Build CPython ABI/version differs from actual runtime')
    need(manifest['oracle_source_reference'] == reference(oracle.__file__)
        and manifest['math_algorithm'] == oracle.ALGORITHM and manifest['fingerprint_recipe'] == oracle.RECIPE,
        'Pinned unchanged original mathematical oracle/support source required')
    expected = {name: reference(Path(__file__).parent / name) for name in SOURCES}
    need(len(manifest['source_references']) == len(SOURCES)
        and {Path(r['path']).name: r for r in manifest['source_references']} == expected,
        'Build must bind all actual imported prototype/kernel/build source bodies')
    binary = verify(manifest['binary_reference'])
    need(binary.name == MODULE + sysconfig.get_config_var('EXT_SUFFIX'), 'Actual CPython extension suffix differs')
    binding = tuple(build_manifest_reference[k] for k in ('path', 'bytes', 'sha256')) + tuple(manifest['binary_reference'][k] for k in ('path', 'bytes', 'sha256'))
    if _LOADED is not None:
        need(binding == _LOADED_BINDING, 'One explicit native build per process; restart for another build')
        return _LOADED, manifest
    spec = importlib.util.spec_from_file_location(MODULE, binary)
    need(spec is not None and spec.loader is not None, 'Cannot load exact pinned extension')
    native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
    need(native.build_info()['implementation'] == IMPLEMENTATION, 'Loaded binary implementation differs')
    _LOADED = native; _LOADED_BINDING = binding
    return native, manifest


class CompiledReference:
    """Immutable private per-popcount packed copy; no RDKit object/native ABI use."""
    def __init__(self, raw_fingerprints, *, worker_rss_cap_bytes, build_manifest_reference):
        began = time.monotonic(); self.cap = worker_rss_cap_bytes
        oracle.enforce_rss(self.cap)
        self.kernel, self.build_manifest = load_kernel(build_manifest_reference)
        self.build_manifest_reference = build_manifest_reference
        self.handle = self.kernel.create(self.cap)
        self.n = 0
        try:
            for raw in raw_fingerprints:
                if not isinstance(raw, bytes) or len(raw) != oracle.WIDTH:
                    raise ValueError('EXACT_2048BIT_RAW_REFERENCE_REQUIRED')
                self.kernel.append(self.handle, raw); self.n += 1
                if self.n % 4096 == 0: oracle.enforce_rss(self.cap)
            if not self.n: raise ValueError('EMPTY_REFERENCE_FORBIDDEN')
            self.kernel.seal(self.handle)
            self.native_statistics = self.kernel.stats(self.handle)
            need(self.native_statistics['reference_records_loaded'] == self.n, 'Complete native iterable cardinality differs')
            self.load_rss_bytes = oracle.enforce_rss(self.cap)
            self.load_wall_seconds = time.monotonic() - began
            self.last_rss_poll = time.monotonic()
        except BaseException:
            self.handle = None
            raise
        # This is a new packed loader, NOT n RDKit decode calls.
        self.reference_records_loaded = self.n
        self.implementation = IMPLEMENTATION

    def close(self):
        self.handle = None  # Capsule owns/frees every private group buffer.

    def order(self, qbits):
        if type(qbits) is not int or not 0 <= qbits <= 2048:
            raise ValueError('INVALID_2048BIT_POPCOUNT')
        return self.kernel.order(self.handle, qbits)

    def nearest(self, raw):
        if not isinstance(raw, bytes) or len(raw) != oracle.WIDTH:
            raise ValueError('EXACT_2048BIT_RAW_QUERY_REQUIRED')
        result = self.kernel.nearest(self.handle, raw)
        numerator, denominator = result['score_numerator'], result['score_denominator']
        need(result['reference_molecules'] == self.n
            and result['evaluated_references'] + result['strictly_bound_pruned_references'] == self.n
            and 0 <= result['reference_ordinal'] < self.n and 0 <= numerator <= denominator and 1 <= denominator <= 2048,
            'Complete integer group accounting required')
        if time.monotonic() - self.last_rss_poll >= 5:
            oracle.enforce_rss(self.cap); self.last_rss_poll = time.monotonic()
        # Exactly one Python int/int division. No native floating-point score,
        # reciprocal, fraction reduction or per-reference scores list.
        return dict(score=numerator / denominator, reference_ordinal=result['reference_ordinal'],
            score_numerator=numerator, score_denominator=denominator,
            evaluated_references=result['evaluated_references'],
            strictly_bound_pruned_references=result['strictly_bound_pruned_references'],
            reference_molecules=result['reference_molecules'],
            searched_popcount_groups=result['searched_popcount_groups'])


def _fd_frame(value):
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_uid]


def load_reference(path, expected_frame, n, worker_rss_cap_bytes, *, build_manifest_reference):
    """Parent first binds full artifact SHA; this loader keeps same-FD/frame/fullN."""
    path = Path(path)
    need(type(n) is int and n > 0 and oracle.file_frame(path) == expected_frame
        and expected_frame[2] == n * oracle.WIDTH, 'Exact complete reference identity/cardinality required')
    before_ctime = path.lstat().st_ctime_ns
    with path.open('rb', buffering=8 << 20) as stream:
        before = os.fstat(stream.fileno())
        need(_fd_frame(before) == expected_frame and before.st_ctime_ns == before_ctime, 'Same reference FD required')
        result = CompiledReference(iter(lambda: stream.read(oracle.WIDTH), b''),
            worker_rss_cap_bytes=worker_rss_cap_bytes, build_manifest_reference=build_manifest_reference)
        after = os.fstat(stream.fileno())
        need(_fd_frame(after) == expected_frame and after.st_ctime_ns == before_ctime,
            'Reference FD changed while loading private copy')
    need(oracle.file_frame(path) == expected_frame and path.lstat().st_ctime_ns == before_ctime
        and result.n == n, 'Reference path changed or complete record count differs')
    return result
