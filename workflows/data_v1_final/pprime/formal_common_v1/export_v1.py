"""Formal baseline float64 export derived from the pinned pilot writer; no label fill."""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path

from common import output_guard, reference


def export(records, output, engine, reproduction_sha, config):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import wp5_parquet_v2 as wire
    entries = wire.registry(engine.CONFIG['registry']['path'])
    extras = [pa.field('geometry_source', pa.string()),
              pa.field('source_record_id', pa.string()),
              pa.field('uff_geometry_sha256', pa.string()),
              pa.field('uff_coordinate_sha256', pa.string()),
              pa.field('pm7_source_geometry_sha256', pa.string()),
              pa.field('Q02_applicable', pa.bool_()), pa.field('Q02_reason', pa.string()),
              pa.field('effective_role', pa.string()),
              pa.field('pprime_reproduction_manifest_sha256', pa.string()),
              pa.field('canonical_geometry_id', pa.string()), pa.field('parent_view_id', pa.string()),
              pa.field('once_key', pa.string())]
    task_schema = wire.SCHEMA
    for field in extras:
        task_schema = task_schema.append(field)
    base_schema = pa.schema([
        ('record_id', pa.string()), ('molecule_id', pa.string()),
        ('source_path', pa.string()), ('real_index', pa.int64()),
        ('source_payload_sha256', pa.string()), ('sprime_conf_idx', pa.int64()),
        ('atomic_numbers', pa.large_list(pa.int16())),
        ('positions_A', pa.large_list(pa.list_(pa.float64(), 3))),
        ('native_atom_order_sha256', pa.string()),
        ('old_stored_PM7_HOF_kcal_mol', pa.float64()),
        ('new_PM7_HOF_kcal_mol', pa.float64()),
        ('new_PM7_HOF_valid', pa.bool_()), ('Q02_delta_HOF_kcal_mol', pa.float64()),
        *extras])
    qc_schema = pa.schema([
        ('record_id', pa.string()), ('molecule_id', pa.string()),
        ('Q01_gradient_norm_kcal_mol_A', pa.float64()),
        ('Q02_delta_HOF_kcal_mol', pa.float64()),
        ('task_statuses_json', pa.large_string()), ('all_twelve_tasks_success', pa.bool_()),
        *extras])
    grouped = defaultdict(list)
    base_rows, qc_rows = [], []
    for record in records:
        source, geom = record['source_row'], record['geometry']
        extra = {k: geom[k] for k in ('geometry_source', 'source_record_id', 'uff_geometry_sha256',
                                      'uff_coordinate_sha256', 'pm7_source_geometry_sha256',
                                      'Q02_applicable', 'Q02_reason')}
        extra.update(effective_role=source['effective_role'],
                     pprime_reproduction_manifest_sha256=reproduction_sha,
                     canonical_geometry_id=record['canonical_geometry_id'],
                     parent_view_id=record['parent_view_id'], once_key=record['once_key'])
        statuses = []
        for detail in record['tasks']:
            calc = detail['task']
            row = wire.task_row(record['record_id'], record['molecule_id'], calc, detail,
                                entries, len(record['base_geometry']['z']))
            row.update(attempt_id=0, job_id=int(detail['job_id']), task_id='pprime-formal-common-v1',
                       lane=int(record['lane']), **extra)
            grouped[wire.FAMILIES[calc]].append(row)
            statuses.append({k: row[k] for k in ('calc_type', 'status', 'source_status',
                                                'failure_code', 'converged')})
        if len(statuses) != 12 or len({s['calc_type'] for s in statuses}) != 12:
            raise ValueError('PPRIME_RECORD_DOES_NOT_HAVE_TWELVE_UNIQUE_TASKS')
        neutral = next(d for d in record['tasks'] if d['task'] == 'pm7_B')
        energy = neutral.get('values', {}).get('heat_of_formation_kcal_mol')
        energy_valid = (isinstance(energy, (int, float)) and math.isfinite(energy)
                        and neutral.get('B_base_success', False))
        base_rows.append({'record_id': record['record_id'], 'molecule_id': record['molecule_id'],
                          'source_path': source['source_path'], 'real_index': source['real_index'],
                          'source_payload_sha256': source['record_payload_sha256'],
                          'sprime_conf_idx': int(source['conformer_id']),
                          'atomic_numbers': record['base_geometry']['z'],
                          'positions_A': record['base_geometry']['positions_A'],
                          'native_atom_order_sha256': geom['native_atom_order_sha256'],
                          'old_stored_PM7_HOF_kcal_mol': None,
                          'new_PM7_HOF_kcal_mol': float(energy) if energy_valid else None,
                          'new_PM7_HOF_valid': bool(energy_valid),
                          'Q02_delta_HOF_kcal_mol': None, **extra})
        qc_rows.append({'record_id': record['record_id'], 'molecule_id': record['molecule_id'],
                        'Q01_gradient_norm_kcal_mol_A': neutral.get('Q01_gradient_norm_kcal_mol_A'),
                        'Q02_delta_HOF_kcal_mol': None,
                        'task_statuses_json': json.dumps(statuses, sort_keys=True),
                        'all_twelve_tasks_success': all(s['status'] == 'SUCCESS' for s in statuses), **extra})
    grouped['base_geometry'], grouped['QC'] = base_rows, qc_rows
    output = Path(output)
    output.mkdir(exist_ok=False)
    refs = []
    for family, rows in sorted(grouped.items()):
        schema = base_schema if family == 'base_geometry' else qc_schema if family == 'QC' else task_schema
        path = output / (family + '.parquet')
        proposed = pa.Table.from_pylist(rows, schema=schema)
        output_guard(output.parent, config, reserve=proposed.nbytes + (16 << 20))
        wire.write_family_rows(rows, path, schema, metadata={
            'dataset_version': 'v1_pprime_formal_common', 'geometry_source': 'uff_sprime',
            'pprime_reproduction_manifest_sha256': reproduction_sha,
            'float_semantics': 'unchanged WP5 float64 cells; no float32 conversion'})
        # Full pilot readback verifies every value/type/float64 bit against producer rows.
        expected = pa.Table.from_pylist(rows, schema=schema).to_pylist()
        actual = pq.read_table(path).to_pylist()
        wire.exact(expected, actual)
        refs.append(dict(reference(path), family=family, rows=len(rows),
                         readback='ALL_BATCH_FIELDS_MATCH_BITS_AND_TYPES'))
    if len(base_rows) != len(records) or sum(len(v) for k, v in grouped.items()
                                          if k not in {'base_geometry', 'QC'}) != 12 * len(records):
        raise ValueError('PPRIME_FAMILY_ROW_COUNTS_DIFFER')
    return refs, qc_rows
