"""One producer-owned PM7/UFF S cohort join; no physical targets are loaded."""
import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from phychem_mfm.phase1.v31_loader import MFM4Dataset, allowed_conformers
from phychem_mfm.phase1.v2_disk import save_metadata_parquet, save_metadata_json


def load(path):
    return json.loads(Path(path).read_text())


def select_rows(root, split, eligible_ids, excluded, k):
    manifest = load(root / 'manifest.json')
    ids = pq.read_table(Path(manifest['split_roots'][split]) / 'id_map.parquet',
                        columns=['molecule_id', 'molecule_index'],
                        filters=[('record_kind', '=', 'M')]).to_pylist()
    if len({row['molecule_id'] for row in ids}) != len(ids):
        raise ValueError('Nonunique molecule identities in delivered split')
    dataset = MFM4Dataset(root, split=split, geometry_only=True)
    rows, removed, missing = [], set(), 0
    try:
        for item in ids:
            mid, index = item['molecule_id'], item['molecule_index']
            if mid in excluded:
                removed.add(mid)
                continue
            if eligible_ids is not None and mid not in eligible_ids:
                continue
            record = dataset.record('M', index)
            # S-prime uses M17/ordinary UFF orders, never P-prime-only M18.
            pm7 = allowed_conformers(record, source='PM7', order='fixed_random', k=k)
            uff = allowed_conformers(record, source='UFF', order='fixed_random', k=k,
                                     pprime=False)
            if len(pm7) and len(uff):
                if len(record[1]) == 0 or len(set(pm7)) != len(pm7) or len(set(uff)) != len(uff):
                    raise ValueError('Invalid source atom/conformer correspondence')
                if np.any(pm7 < 0) or np.any(pm7 >= len(record[13])):
                    raise ValueError('PM7 ordinal outside published source range')
                if np.any(uff < 0) or np.any(uff >= len(record[14])):
                    raise ValueError('UFF ordinal outside published source range')
                rows.append(dict(molecule_id=mid, molecule_index=index,
                                 PM7=pm7.tolist(), UFF=uff.tolist()))
            else:
                missing += 1
            dataset._molecules.clear()  # Do not retain a million M records.
            if (index + 1) % 10000 == 0:
                print(json.dumps(dict(split=split, examined=index+1, common=len(rows))), flush=True)
    finally:
        dataset.close()
    return rows, removed, missing


def prepare(root, output, configuration, exclusion_path, k=10):
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    excluded = set(load(exclusion_path)['overlapping_molecules'])
    if len(excluded) != 323:
        raise ValueError('Expected the existing 323-molecule exclusion list')
    manifest = load(root / 'manifest.json')
    common = load(manifest['full_source_dependencies']['common'])
    val_ids = set()
    for ref in common['membership_tables']:
        table = pq.read_table(ref['path'], columns=['molecule_id', 'effective_role',
                                                   'common_population_v1'])
        val_ids.update(row['molecule_id'] for row in table.to_pylist()
                       if row['effective_role'] == 'VAL' and row['common_population_v1'])
    train, removed, missing_train = select_rows(root, 'TRAIN', None, excluded, k)
    val, _, missing_val = select_rows(root, 'FULL', val_ids, set(), k)
    if removed != excluded or len(train) == 0 or len(val) < 5000:
        raise ValueError('Published exclusions/common TRAIN or 5000 VAL population unavailable')
    train_ids = {row['molecule_id'] for row in train}
    if train_ids & {row['molecule_id'] for row in val} or train_ids & excluded:
        raise ValueError('TRAIN/VAL or excluded identity overlap')
    val.sort(key=lambda row: row['molecule_id'])
    selected = np.random.default_rng(20261112).choice(len(val), 5000, replace=False)
    fixed = [val[int(index)] for index in sorted(selected)]
    # Membership validation is performed here once, not repeated by consumers.
    output.mkdir(parents=True, exist_ok=False)
    schema = pa.schema([('molecule_id', pa.string()), ('molecule_index', pa.int64()),
                        ('PM7', pa.list_(pa.int64())), ('UFF', pa.list_(pa.int64()))])
    for name, rows in (('TRAIN', train), ('VAL', fixed)):
        save_metadata_parquet(pa.Table.from_pylist(rows, schema=schema), output / (name+'.parquet'))
    payload = dict(schema='S_RECIPE_COMMON_POPULATION_V1', source_root=str(root), k=k,
                   TRAIN_molecules=len(train), VAL_molecules=5000, VAL_seed=20261112,
                   train=str(output/'TRAIN.parquet'), validation=str(output/'VAL.parquet'),
                   excluded_count=len(excluded), excluded_source=str(exclusion_path),
                   excluded_ids=sorted(excluded), missing_one_source_TRAIN=missing_train,
                   missing_one_source_common_VAL=missing_val,
                   UFF_eligibility='ordinary S-prime M17, not P-prime M18',
                   pairing='same M record and source atom order; independent published source ordinals',
                   physical_labels_used=False, normalization_refitted=False)
    save_metadata_json(payload, configuration)
    print(json.dumps(payload), flush=True)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--exclusions', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.output, args.configuration, args.exclusions)
