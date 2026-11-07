"""Same compiled integer kernel for an actual complete before/after manifest."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os
from pathlib import Path
import time
from ..alpha_runtime_v1 import common as Q
from ..exact_nn_cached_v1.engine import file_frame, current_rss
from ..exact_nn_cached_v1.coverage import validate_reference
from ..exact_nn_popcount_cpp_v1 import backend
from ..exact_nn_popcount_production_v1 import authority
from ..exact_nn_popcount_production_v1.workers import fixed_result

_REFERENCE = None
_BARRIER = None
_ADOPTION = None


def target_contract(manifest, target_ref, role, original_ref):
    Q.need(role in ('before', 'after') and manifest['status'] == 'COMPLETE'
           and manifest['targets_present'] is False, 'Actual complete scientific reference required')
    if role == 'before':
        Q.need(target_ref == original_ref and manifest['molecules'] == 1196122,
               'Before coverage remains the actual full196 Common reference')
    else:
        Q.need(manifest['schema'] == 'EXPANSION_EXACT_AUGMENTED_REFERENCE_V1'
               and manifest['base_reference_manifest'] == original_ref
               and manifest['added_molecules'] == 2500000 and manifest['molecules'] == 3696122
               and manifest['original_reference_ordinals_preserved_as_exact_prefix'] is True,
               'After coverage is full original196 prefix plus all2.5M actual R/N graphs')
    return manifest['molecules']


def _initialize(path, frame, n, cap, barrier, adoption_ref, manifest_ref, role):
    global _REFERENCE, _BARRIER, _ADOPTION
    _BARRIER = barrier
    try:
        _ADOPTION, _ = authority.adopted(adoption_ref)
        manifest = Q.load(Q.verify(manifest_ref))
        Q.need(target_contract(manifest, manifest_ref, role, _ADOPTION['reference_manifest_reference']) == n
               and manifest['fingerprints']['path'] == str(Path(path)), 'Same parent-bound actual complete reference')
        _REFERENCE = backend.load_reference(path, frame, n, cap,
                                            build_manifest_reference=_ADOPTION['build_manifest_reference'])
        Q.need(_REFERENCE.reference_records_loaded == n, 'Every actual reference ordinal loaded')
        barrier.wait()
    except BaseException:
        barrier.abort()
        raise


def _ready():
    _BARRIER.wait()
    return dict(worker_pid=os.getpid(), reference_records_loaded=_REFERENCE.reference_records_loaded,
                reference_load_seconds=_REFERENCE.load_wall_seconds,
                reference_load_rss_bytes=_REFERENCE.load_rss_bytes,
                backend_implementation=_REFERENCE.implementation,
                backend_build_reference=_ADOPTION['build_manifest_reference'],
                backend_binary_reference=_ADOPTION['binary_reference'],
                runtime_popcount_backend=_REFERENCE.kernel.build_info()['runtime_popcount_backend'])


def _batch(rows):
    began = time.monotonic()
    # Direct original production function. All score/count/firstordinal math is native unchanged.
    results = fixed_result(_REFERENCE, rows)
    return dict(results=results, worker_pid=os.getpid(), wall_seconds=time.monotonic() - began,
                rss_bytes=current_rss(), reference_records_loaded=_REFERENCE.reference_records_loaded,
                backend_implementation=_REFERENCE.implementation)


def exact_batches(path, n, batches, *, workers, worker_rss_cap_bytes, ready_callback=None,
                  backend_adoption_reference, reference_manifest_reference, reference_role):
    Q.need(type(workers) is int and 1 <= workers <= 192 and type(worker_rss_cap_bytes) is int
           and worker_rss_cap_bytes > 0, 'Explicit actual worker resource allowances')
    adoption, _ = authority.adopted(backend_adoption_reference)
    actual_manifest = Q.verify(reference_manifest_reference)
    manifest = validate_reference(actual_manifest, reference_role)
    Q.need(target_contract(manifest, reference_manifest_reference, reference_role,
                           adoption['reference_manifest_reference']) == n
           and str(Path(path).absolute()) == manifest['fingerprints']['path'],
           'Exact before/after population and ordinal binding, never a reference subset')
    Q.verify(manifest['fingerprints'])
    frame = file_frame(path)
    context = multiprocessing.get_context('spawn'); barrier = context.Barrier(workers)
    with ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=_initialize,
            initargs=(str(path), frame, n, worker_rss_cap_bytes, barrier, backend_adoption_reference,
                      reference_manifest_reference, reference_role)) as pool:
        for future in [pool.submit(_ready) for _ in range(workers)]:
            value = future.result()
            if ready_callback is not None:
                ready_callback(value)
        waiting = deque()
        for rows in batches:
            waiting.append(pool.submit(_batch, rows))
            if len(waiting) >= workers * 2:
                yield waiting.popleft().result()
        while waiting:
            yield waiting.popleft().result()
    Q.need(file_frame(path) == frame, 'Whole reference changed during native exact search')
