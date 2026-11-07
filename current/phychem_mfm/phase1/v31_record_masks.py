"""Consume published record/field mask metadata without inspecting label values."""
import json
from pathlib import Path
import numpy as np


def published_record_masks(payload, directory, *, dataset='P_D'):
    reference = payload.get('source_references', {}).get(dataset, {}).get(
        'closed_training_stage_references', {}).get('mask_overrides_reference')
    if not reference:
        return {}
    import pyarrow.parquet as pq
    catalog = json.loads(Path(reference['path']).read_text())
    by_identity = {}
    for item in catalog['files']:
        if not item['records']:
            continue
        rows = pq.read_table(item['path'], columns=[
            'record_id', 'molecule_id', 'field_key', 'leaf_indices']).to_pylist()
        for row in rows:
            fields = by_identity.setdefault((row['record_id'], row['molecule_id']), {})
            fields.setdefault(row['field_key'], set()).update(row['leaf_indices'])
    if not by_identity:
        return {}
    # This is the delivered reversible address map, never a label scan.
    identities = pq.read_table(Path(directory)/'id_map.parquet', columns=[
        'record_kind', 'native_record_id', 'molecule_id', 'molecule_index', 'conformer_index'],
        filters=[('record_kind', '=', 'P' if dataset == 'P_D' else 'U'),
                 ('native_record_id', 'in', sorted({key[0] for key in by_identity}))])
    result = {}
    for row in identities.to_pylist():
        masks = by_identity.get((row['native_record_id'], row['molecule_id']))
        if masks:
            result[(row['molecule_index'], row['conformer_index'])] = masks
    return result


def apply_published_scalar_mask(raw, leaves):
    """Current published EA catalog addresses the one scalar leaf exactly."""
    if not leaves:
        return raw
    if raw.size != 1 or set(leaves) != {0}:
        raise ValueError('Published scalar mask does not match the selected field leaves')
    value = raw.copy()
    value.reshape(-1)[0] = np.nan
    return value
