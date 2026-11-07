"""Pure final-fit observation adapter, retaining original decoder objects.

This module does not discover/open DATA. The future CPU inventory adapter must
provide exact bound cache/base rows and final compact masks, in logical order.
Output tuples have the existing normalization_v1.reader.observations shape.
"""
from __future__ import annotations

import hashlib
import struct
from .contract import need


def base_numbers(owner, row):
    from . import bindings as B
    need(row['row_kind'] == 'base' and row['task_code'] == 255
         and row['record_ordinal'] == owner['record_ordinal']
         and row['record_id'] == owner['record_id'], 'EXACT_BASE_ROW_LOCATOR_REQUIRED')
    payload = B.base_metadata(row['tree_json'])
    need(payload['provenance']['owner']['record_ordinal'] == owner['record_ordinal'],
         'BASE_OWNER_ORDINAL_CHANGED')
    geometry = payload['original_geometry']; numbers = geometry['atomic_numbers']
    need(isinstance(numbers, list) and len(numbers) == owner['total_atoms']
         and all(type(z) is int and 1 <= z <= 118 for z in numbers), 'FINAL_ATOMIC_NUMBER_ORDER_REQUIRED')
    digest = hashlib.sha256(b''.join(struct.pack('<q', z) for z in numbers)).hexdigest()
    need(digest == geometry['native_atom_order_sha256']
         and geometry['source_payload_sha256'] == owner['record_payload_sha256']
         and geometry['geometry_status'] == 'ORIGINAL_PM7_GEOMETRY'
         and sum(z > 1 for z in numbers) == owner['heavy_atoms'],
         'FINAL_BASE_ORDER_PAYLOAD_HEAVY_OR_STATUS_DIFFERS')
    need(owner['geometry_source'] == 'pm7', 'PM7_CACHE_NEVER_SUBSTITUTES_PPRIME')
    return numbers


def final_compact_parity(candidate, final_compact):
    from . import bindings as B
    for key in B.cache_original.PARITY_KEYS:
        need(type(final_compact[key]) is type(candidate[key]) and final_compact[key] == candidate[key],
             'FINAL_MASK_REQUIRES_VERSIONED_VALIDITY_OVERLAY:' + key)
    return True


def observation(owner, numbers, row, final_compact, fields, task_codes, common, masks):
    """No normalization, clipping, reindexing or physical transformation here."""
    from . import bindings as B
    need(owner['fit_eligible'] is True and owner['effective_role'] == 'TRAIN'
         and owner['common_population'] is True
         and owner['fit_reason'] == 'FIT_TRAIN_COMMON_NOT_DIAGNOSTIC', 'FORBIDDEN_ROLE_OR_GEOMETRY_IN_D4')
    need(owner['geometry_source'] == 'pm7', 'INDEPENDENT_PPRIME_SOURCE_REQUIRED')
    need(row['row_kind'] == 'task' and row['record_id'] == owner['record_id']
         and row['record_ordinal'] == owner['record_ordinal'], 'EXACT_TYPED_TASK_OWNER_REQUIRED')
    need(len(row['tree_json'].encode()) + 8 * len(row['values_float64']) <= 64 << 20,
         'UNCHANGED_TYPED_ROW_BOUND')
    payload = B.projected_decode(row['tree_json'], row['values_float64'])
    task = payload['task']
    need(task in task_codes and row['task_code'] == task_codes[task], 'EXACT_FROZEN_TASK_CODE_REQUIRED')
    cached_owner = payload['provenance']['owner']
    need(all(type(cached_owner[key]) is type(owner[key]) and cached_owner[key] == owner[key]
             for key in ('record_id','molecule_id','attempt_id','job_id','task_id','lane','total_atoms','new_role')),
         'EXACT_ORIGINAL_OWNER_TUPLE_CHANGED')
    task_fields = [field for field in fields if field['task'] == task]
    need(task_fields, 'FINAL_REGISTERED_FIELD_SET_MISSING_TASK')
    # Original function rebuilds logical CELL views, checks component pointers
    # and original candidate parity. Incompatibility propagates as HOLD.
    entries = B.entries(payload, task_fields, common, masks, row['task_code'])
    candidate = payload['original_compact_candidate']
    final_compact_parity(candidate, final_compact)
    for entry in entries:
        fid = entry['field_id']
        entry['value_mask'] = B.compact.restore_mask(final_compact, fid, len(entry['values_float64']))
        entry['persisted_review_codes'] = [reason['code'] for reason in final_compact['review_groups']
                                          if fid in B.compact.unpack(reason['fields'])]
    return owner, numbers, entries
