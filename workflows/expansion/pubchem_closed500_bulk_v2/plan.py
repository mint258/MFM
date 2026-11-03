"""Lift the exact closed500 metadata into restartable502 physical projections."""
from pathlib import Path
from .common import CATEGORIES, EXPECTED_COUNTS, EXPECTED_ROWS, load, verify, need


def load_coverage(ref):
    coverage = load(verify(ref))
    need(coverage['schema'] == 'ROOT_PUBCHEM_ORIGINAL_FINITE500_ROW_COVERAGE_V1' and coverage['status'] == 'ALL500_SOURCE_ROWS_ACCOUNTED_NOT_POOL_OR_TRAIN_RELEASE', 'Formally closed original500 coverage required')
    need(coverage['source_rows'] == EXPECTED_ROWS and coverage['descriptor_count'] == 500 and coverage['counts'] == EXPECTED_COUNTS and coverage['source_row_conservation'] is True and coverage['UNKNOWN_not_chemical_exclusion'] is True, 'Exact all-source row conservation required')
    manifest = load(verify(coverage['frozen_manifest_reference']))
    entries = coverage['source_descriptors']
    need(len(entries) == len(manifest['shards']) == 500, 'Original500 descriptors required')
    fragments, next_ordinal, paths = [], 1, set()
    for i, entry in enumerate(entries):
        member = manifest['shards'][i]
        need(entry['descriptor_index'] == i and entry['original_descriptor'] == member, 'Original descriptor identity mismatch')
        bodies = entry['scientific_body_locators']
        if isinstance(bodies, dict):
            need(i not in (363, 412), 'Original split descriptor cannot be replaced by a whole part')
            physical = [{'first_ordinal': member['first_ordinal'], 'last_ordinal': member['last_ordinal'], 'rows': entry['rows'], 'counts': entry['counts'], 'Parquet_reference': bodies['features'], 'journal_reference': bodies['full_dispatch_and_result_journal']}]
        else:
            need(i in (363, 412) and len(bodies) == 2 and entry['closure_kind'] == 'TWO_FRAGMENT_TRUE_NEW_PARENT_C0', 'Only the two formally closed split descriptors are allowed')
            logical = load(verify(entry['accepted_metadata_reference']))
            need(logical['counts'] == entry['counts'] and logical['source_row_conservation'] is True, 'Split logical coverage mismatch')
            physical = logical['fragments']
            need(len(physical) == 2, 'Exactly two physical pieces required')
            for fragment, body in zip(physical, bodies):
                need(fragment['Parquet_reference'] == body['Parquet_reference'] and fragment['journal_reference'] == body['journal_reference'], 'Logical source locators differ')
        for j, fragment in enumerate(physical):
            need(fragment['first_ordinal'] == next_ordinal and fragment['last_ordinal'] >= next_ordinal and fragment['rows'] == fragment['last_ordinal'] - next_ordinal + 1, 'Source ordinal gap, overlap, or repeated prefix')
            need(set(fragment['counts']) == set(CATEGORIES) and sum(fragment['counts'].values()) == fragment['rows'], 'Original physical fragment row mass mismatch')
            source = fragment['Parquet_reference']
            need(source['path'] not in paths and source['bytes'] > 0 and len(source['sha256']) == 64, 'Distinct pinned physical Parquet source required')
            paths.add(source['path'])
            fragments.append({'fragment_id': '%03d_%d' % (i, j), 'descriptor_index': i, 'first_ordinal': next_ordinal, 'last_ordinal': fragment['last_ordinal'], 'rows': fragment['rows'], 'counts': fragment['counts'], 'Parquet_reference': source, 'journal_reference': fragment['journal_reference'], 'accepted_metadata_reference': entry['accepted_metadata_reference'], 'actual_parent_job_id': entry['actual_parent_job_id']})
            next_ordinal = fragment['last_ordinal'] + 1
    need(len(fragments) == 502 and next_ordinal == EXPECTED_ROWS + 1 and {key: sum(f['counts'][key] for f in fragments) for key in CATEGORIES} == EXPECTED_COUNTS, 'All502 closed physical fragments and source rows required')
    return fragments


def validate_plan(plan):
    need(plan['schema'] == 'PUBCHEM_CLOSED500_BULK_PLAN_V2', 'Wrong bulk plan version')
    need(type(plan['workers']) is int and plan['workers'] >= 1 and type(plan['batch_rows']) is int and 1 <= plan['batch_rows'] <= 65536, 'Explicit finite worker and Arrow batch resources required')
    need(plan['output_cap_bytes'] > 0 and plan['minimum_free_bytes'] >= 0 and plan['other_future_reserved_bytes'] >= 0 and plan['duckdb_memory_bytes'] > 0, 'Real reserved storage and memory plan required')
    need(Path(plan['output_directory']).is_absolute(), 'Absolute output root required')
    expected = load_coverage(plan['coverage_reference'])
    need(plan['fragments'] == expected, 'Plan must preserve the exact authoritative502 mapping')
    return plan
