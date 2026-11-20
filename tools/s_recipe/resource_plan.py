"""Forecast scratch H bytes from closed target-free native metadata only."""
import argparse
import json
from pathlib import Path

from runtime import capacity, write


def forecast(path):
    document = json.loads(path.read_text())
    if document.get('schema') != 'model_v3_training_role_store_v1' or not document.get('source_complete'):
        raise ValueError('Closed TRAIN-only native metadata is required')
    counts = {}
    for row in document['records']:
        name = row['dataset_id']
        if name not in ('expansionrx', 'cyp_isoform', 'qm9') or not row['geometry_ready']:
            continue
        value = counts.setdefault(name, dict(records=0, atoms=0))
        value['records'] += 1
        value['atoms'] += row['native_n_atoms']
    for value in counts.values():
        value['H_F32_bytes'] = value['atoms']*512*4
        # Includes native atom IDs, torch serialization and per-record metadata.
        value['cache_peak_bytes'] = value['H_F32_bytes']+value['atoms']*128+value['records']*16384
    per_case = sum(value['cache_peak_bytes'] for value in counts.values())
    return dict(schema='S_RECIPE_READOUT_RESOURCE_FORECAST_V1', source=str(path), datasets=counts,
                per_checkpoint_cache_peak_bytes=per_case,
                initial_six_arms_eight_checkpoints_cache_peak_bytes=8*per_case,
                cache_policy='Owned closed scratch H released after R1/R3 and original bootstrap; failed partials preserved',
                labels_opened=False, model_executed=False, hashes_recomputed=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--store', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    capacity()
    result = forecast(args.store)
    write(args.output, result)
    print(json.dumps(result), flush=True)
