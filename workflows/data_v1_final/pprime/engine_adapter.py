"""P-prime orchestration over unchanged, SHA-pinned WP5 task invocation/parsers."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time
import uuid

from geometry import adapt_native, GEOMETRY_SOURCE, Q02_REASON


def compute_pair(engine, pair, sink, context):
    """One UFF conformer, twelve outcomes, no replacement of old module functions."""
    e = engine
    import wp5_parquet_v2 as wire
    registry_entries = [entry for entry in e.REGISTRY if wire.wanted(entry)]
    source = dict(pair['source'])
    original = e.NATIVE.read_native(source)
    graph = e.source_bond_graph(original['_source_raw'], original)
    pair = dict(pair, bond_pairs=graph['bond_pairs_zero_based'])
    native, geometry = adapt_native(original, pair, e.CONFIG['pair_cutoff_A'])
    row = dict(source, record_id=pair['record_id'],
               conformer_id=int(pair['conformer']['sprime_conf_idx']))
    selected = e.AUDIT_IDS.get(row['record_id'])
    if selected is not None and (int(row['file_group']), row['size_stratum']) != selected:
        raise ValueError('PPRIME_AUDIT_STRATUM_CHANGED')
    row['audit_selected'] = selected is not None
    context = dict(context, execution_id=uuid.uuid4().hex)
    record = {'record_id': row['record_id'], 'molecule_id': row['molecule_id'],
              'source_row': row, 'source_record_id': source['record_id'],
              'old_energy_kcal_mol': None, 'geometry': geometry,
              'base_geometry': {'z': native['z'].tolist(),
                                'positions_A': native['coords'].tolist(), **graph},
              'tasks': [], 'audit_selected': row['audit_selected']}
    started = time.monotonic()
    for task in e.CONFIG['tasks']:
        if e.NATIVE.STOP_EVENT.is_set() or time.time() >= e.NATIVE.DEADLINE - 30:
            raise RuntimeError('PPRIME_PARTIAL_DEADLINE_NO_NEW_QM')
        e.CAPTURED = None
        e.CAPTURE_ERROR = None
        e.CALL_SCRATCH = None
        durable = False
        hashes, bundle_hash = e.rendered_input_hashes(task, native, row)
        result = e.NATIVE.invoke(task, native, row, e.WORK)
        if result.get('preserved_scratch') and result.get('scratch_cleanup_error'):
            e.PRESERVE_ARCHIVE_FAILURE = True
            raise RuntimeError('PINNED_QM_LIFECYCLE_PRESERVED_UNVERIFIED_SCRATCH')
        if e.CAPTURE_ERROR is not None:
            e.PRESERVE_ARCHIVE_FAILURE = True
            raise RuntimeError('RAW_CAPTURE_FAILED') from e.CAPTURE_ERROR
        source_status = result['status']
        unfinished = source_status in e.NATIVE.UNFINISHED
        result['source_status'] = source_status
        result['atomic_array_validation'] = e.validate_atomic_arrays(result, native['z'])
        if result['atomic_array_validation'] and source_status == 'SUCCESS':
            result.update(status='PROPERTY_FAILED', failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED',
                          failure_reason=' | '.join(result['atomic_array_validation']))
        result['status'] = e.canonical_status(result['status'])
        result['scope_status'] = result['status']
        result['parser_context'] = e.PARSER.context()
        files = e.CAPTURED or []
        scf = e.extract_scf(task['name'], files, result.get('values'), result['status'], source_status)
        result['provenance'] = {
            'status': result['status'],
            'software_version_id': e.PACKAGE['software_versions'][task['family']]['software_version_id'],
            'elapsed_seconds': result.get('elapsed_seconds'),
            'scf_iterations': scf['scf_iterations'], 'converged': scf['converged'],
            'input_file_sha256': hashes, 'input_bundle_sha256': bundle_hash,
            'scf_iteration_definition': scf['iteration_definition'],
            'scf_missing_reason': scf['missing_reason'], **geometry}
        result['raw_audit_selected'] = row['audit_selected']
        result['reproduction_package_sha256'] = e.PACKAGE_SHA
        result['precision_by_field'] = result['parser_context'].get('rounding_decimal_places', {})
        result['registry_source_evidence'] = e.concise_source_evidence(result, files)
        preview = wire.task_row(row['record_id'], row['molecule_id'], task['name'],
                                result, registry_entries, len(native['z']))
        if preview['numeric_issues'] and result['scope_status'] == 'SUCCESS':
            result.update(status='PROPERTY_FAILED', scope_status='PROPERTY_FAILED',
                          failure_code='NONFINITE_REGISTRY_VALUES',
                          failure_reason='Nonfinite registry IDs: ' + str(preview['numeric_issues']))
            result['provenance']['status'] = result['scope_status']
        # energy=None was passed to invoke: old-source HOF was never subtracted.
        if result.get('Q02_delta_HOF_kcal_mol') is not None:
            raise RuntimeError('CROSS_GEOMETRY_Q02_MUST_BE_NULL')
        result['Q02_applicable'] = False
        result['Q02_reason'] = Q02_REASON
        raw = e.raw_record(task, row, result, files, context)
        raw.update(geometry_source=GEOMETRY_SOURCE, geometry=geometry,
                   pprime_reproduction_manifest_sha256=context['pprime_reproduction_manifest_sha256'])
        try:
            ref = sink(raw)
            keep, _ = e.OUTPUT_ARCHIVE.retention(raw)
            if bool(ref.get('output_retained')) != keep or (keep and not ref.get('raw_call_durable')):
                raise RuntimeError('PPRIME_RAW_NOT_DURABLE_BEFORE_LOCAL_DELETION')
            durable = True
            result['raw_ref'] = ref
            result['archived_files'] = [{'name': f['name'], 'bytes': f['byte_count'],
                                        'sha256': f['sha256']} for f in files] if keep else []
        except Exception:
            e.PRESERVE_ARCHIVE_FAILURE = True
            raise
        finally:
            if durable and e.CALL_SCRATCH is not None:
                result['scratch_bytes_removed'] = e.ORIGINAL_CLEANUP(e.CALL_SCRATCH)
            e.CAPTURED = None
            e.CALL_SCRATCH = None
        record['tasks'].append(result)
        if unfinished:
            raise RuntimeError('PPRIME_PARTIAL_QM_OUTCOMES_RETAINED')
    e.derived_quantities(record['tasks'])
    for detail in record['tasks']:
        detail['registry_source_evidence'] = e.concise_source_evidence(
            detail, previous=detail['registry_source_evidence'])
        final = wire.task_row(row['record_id'], row['molecule_id'], detail['task'],
                              detail, registry_entries, len(native['z']))
        if final['status'] != detail['scope_status']:
            raise RuntimeError('DERIVED_REGISTRY_STATUS_CHANGED_AFTER_RAW_RETENTION_REQUIRES_REVIEW')
    record['elapsed_seconds'] = time.monotonic() - started
    return record
