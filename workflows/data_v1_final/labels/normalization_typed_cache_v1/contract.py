"""Small, fail-closed authority contracts. No scientific body IO."""
from __future__ import annotations

import collections
import re

SCHEMA = 'D4_TYPED_CACHE_CANDIDATE_INTERFACE_V1'
RELEASE_SCHEMA = 'ROOT_D4_TYPED_CACHE_FINAL_INPUT_RELEASE_V1'
COVERAGE_SCHEMA = 'LABELS_RECOVERED_FULL_SOURCE_COVERAGE_V1'
ORIGINS = {'ACTUAL_C0_BATCH', 'TIMEOUT_ADOPTED_CLOSED_WINDOWS'}
FINAL_PARENTS = (
    'coverage', 'parts_inventory', 'full_TRAIN_calibration', 'final_mask_release',
    'registry', 'field_map', 'physical_mapping', 'owner_authority', 'common',
    'roles', 'geometry_map', 'order', 'diagnostic', 'logical_statistics',
    'native_semantics_review', 'root_resource_review',
)
COUNTS = {'sources': 2208, 'canonical_records': 11231854,
          'canonical_task_rows': 157245956, 'canonical_base_rows': 11231854,
          'label_physical_rows': 157254650, 'base_physical_rows': 11232475,
          'label_noncanonical_rows': 8694, 'base_noncanonical_rows': 621}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def reference(value, *, source=False):
    need(isinstance(value, dict), 'EXACT_REFERENCE_REQUIRED')
    need(isinstance(value.get('path'), str) and value['path'].startswith('/')
         and '..' not in value['path'].split('/'), 'ABSOLUTE_MAIN_REFERENCE_REQUIRED')
    need(type(value.get('bytes')) is int and value['bytes'] >= (0 if source else 1),
         'SOURCE_ZERO_ONLY_DATA_POSITIVE')
    need(isinstance(value.get('sha256'), str)
         and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None, 'EXACT_SHA256_REQUIRED')
    if value['bytes'] == 0:
        need(value['sha256'] == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
             'EMPTY_SOURCE_SHA_REQUIRED')
    return {key: value[key] for key in ('path', 'bytes', 'sha256')}


def actual_chain(value, kind):
    """Validate declared small reviews; do not manufacture actual parent results."""
    need(isinstance(value, dict) and value.get('origin_type') == kind, 'EXACT_ORIGIN_CHAIN_REQUIRED')
    required = ('producer',) if kind == 'ACTUAL_C0_BATCH' else (
        'old_producer', 'inventory', 'seed', 'root_adoption')
    for key in required:
        reference(value.get(key))
    reference(value.get('root_parent_chain_review'))
    if kind == 'TIMEOUT_ADOPTED_CLOSED_WINDOWS':
        need(value.get('old_producer_state') == 'TIMEOUT', 'ADOPTION_MUST_KEEP_OLD_TIMEOUT')
    return value


def validate_release(release, coverage):
    need(release.get('schema') == RELEASE_SCHEMA and release.get('reviewer') == 'root'
         and release.get('status') == 'ROOT_APPROVED_EXACT_FINAL_D4_INPUTS'
         and isinstance(release.get('reason'), str) and bool(release['reason'].strip()),
         'INDEPENDENT_ROOT_D4_RELEASE_REQUIRED')
    parents = release.get('parents', {})
    need(set(parents) == set(FINAL_PARENTS), 'ALL_EXACT_FINAL_PARENT_PINS_REQUIRED')
    for value in parents.values():
        reference(value)
    need(coverage.get('schema') == COVERAGE_SCHEMA
         and coverage.get('status') == 'FULL_NUMERIC_SOURCE_COVERAGE_OBSERVED_NOT_FINAL_MASKS',
         'ACTUAL_RECOVERED_FULL_COVERAGE_REQUIRED')
    need(coverage.get('all14task_and_base_exact_once') is True
         and all(type(coverage.get(key)) is int and coverage[key] == 0 for key in
                 ('unresolved_consumed_count', 'held_source_count', 'unverified_part_count'))
         and coverage.get('quality_hold_fields') == [], 'NO_PARTIAL_UNKNOWN_OR_QUALITY_HOLD')
    need(coverage.get('final_mask_release') is False and coverage.get('D4_release') is False,
         'SOURCE_COVERAGE_DOES_NOT_SELF_SIGN_MASK_OR_D4')
    need(coverage.get('actual_parts_inventory_reference') == parents['parts_inventory'],
         'EXACT_FROZEN_PART_INVENTORY_BINDING')
    # The Root review normalizes actual producer counts; no future producer
    # field aliases or detailed inventory parser are guessed by this interface.
    need(release.get('coverage_counts') == COUNTS, 'ALL_PHYSICAL_AND_CANONICAL_MASSES_REQUIRED')
    origins = release.get('accepted_origin_reviews', [])
    need(isinstance(origins, list) and origins, 'EXACT_ACCEPTED_ORIGIN_REVIEWS_REQUIRED')
    ids = [row.get('origin_id') for row in origins]
    need(all(isinstance(key, str) and key for key in ids) and len(ids) == len(set(ids)),
         'UNIQUE_ACCEPTED_ORIGIN_IDS')
    for row in origins:
        need(row.get('origin_type') in ORIGINS, 'UNKNOWN_ORIGIN_TYPE')
        actual_chain(row, row['origin_type'])
    declared = [(row['origin_id'], row['origin_type']) for row in coverage.get('accepted_origins', [])]
    reviewed = [(row['origin_id'], row['origin_type']) for row in origins]
    need(len(declared) == len(set(declared)) and sorted(declared) == sorted(reviewed),
         'ALL_AND_ONLY_ACTUAL_ORIGINS_REVIEWED')
    counts = dict(collections.Counter(kind for _, kind in reviewed))
    need(coverage.get('origin_counts') == counts
         and all(type(v) is int and v > 0 for v in coverage['origin_counts'].values()),
         'EXACT_MIXED_ORIGIN_COUNTS')
    need(release.get('fit_role') == 'TRAIN' and release.get('validation_source') == 'ROUTINE'
         and release.get('final_mask_validity_regeneration_unchanged') is True,
         'TRAIN_ONLY_AND_EXACT_FINAL_MASK_REGENERATION_REQUIRED')
    need(release.get('dataset_geometry_source') == 'pm7', 'PM7_PD_CACHE_COUNTS_CANNOT_DEFINE_PPRIME')
    need(release.get('no_P_value_substitution_for_Pprime') is True, 'INDEPENDENT_PPRIME_REQUIRED')
    return release


def candidate(request):
    """Always nonexecutable: source interfaces do not register a runtime stage."""
    need(request.get('schema') == 'ROOT_D4_TYPED_CACHE_CANDIDATE_REQUEST_V1',
         'EXACT_ROOT_CANDIDATE_REQUEST_REQUIRED')
    supplied = request.get('parent_references', {})
    need(isinstance(supplied, dict) and set(supplied) <= set(FINAL_PARENTS), 'UNKNOWN_FINAL_PARENT_NAME')
    for value in supplied.values():
        reference(value)
    return {'schema': SCHEMA, 'status': 'NONEXECUTABLE_CANDIDATE_INTERFACES_ONLY',
            'parent_references': supplied, 'missing_parents': sorted(set(FINAL_PARENTS) - set(supplied)),
            'stage_spec_generated': False, 'scientific_DATA_opened': False,
            'normalization_completed': False, 'D4_published': False,
            'source25_or_512_or_TIMEOUT_is_final_authority': False, 'mixed_origin_policy': sorted(ORIGINS)}
