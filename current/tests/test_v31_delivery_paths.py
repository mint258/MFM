"""Synthetic storage bindings for the actual shared D6 producer contract."""
import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from phychem_mfm.phase1.v31_loader import MFM4Dataset, record_key
from test_v31_loader import encode, molecule, schema_view


def released_delivery(tmp_path):
    lmdb = pytest.importorskip('lmdb')
    root = tmp_path / 'schema_site'
    root.mkdir()
    schema, view = schema_view()
    (root / 'schema.json').write_text(json.dumps(schema))
    roots, idmaps = {}, {}
    for role, count, offset in [('TRAIN', 2, 0), ('FULL', 1, 10)]:
        directory = tmp_path / (role.lower() + '_compact')
        directory.mkdir()
        env = lmdb.open(str(directory), map_size=1 << 20)
        rows = []
        with env.begin(write=True) as txn:
            for i in range(count):
                mid = f'{role}_m{i}'
                txn.put(record_key('M', i), encode(molecule()))
                rows.append(dict(record_kind='M', molecule_id=mid, molecule_index=i,
                                 native_record_id='', conformer_index=None))
                for j in range(3):
                    txn.put(record_key('P', i, j), encode({
                        21: np.full((2, 3), offset + i + j, dtype='<f4'),
                        23: np.array([i + j], dtype='<f4')}))
                    rows.append(dict(record_kind='P', molecule_id=mid, molecule_index=i,
                        native_record_id=f'{role}_n{i}_{j}', conformer_index=j))
        env.close()
        idpath = root / (role + '_identities.parquet')
        pq.write_table(pa.Table.from_pylist(rows), idpath)
        (directory / 'id_map.parquet').symlink_to(idpath)
        roots[role], idmaps[role] = str(directory), str(idpath)
    delivery = dict(format='v3.1/MFM4', split_roots=roots,
                    molecules={'TRAIN': 2, 'FULL': 1}, id_map_physical_paths=idmaps)
    (root / 'manifest.json').write_text(json.dumps(delivery))
    return root, delivery, view


def test_released_roots_override_stale_pilot_and_read_shared_lmdb_and_external_ids(tmp_path):
    root, delivery, _ = released_delivery(tmp_path)
    stale = root / 'v31_pilot_TRAIN'
    stale.mkdir()
    (stale / 'manifest.json').write_text(json.dumps({'molecule_count': 99}))
    dataset = MFM4Dataset(root, geometry_only=True)
    try:
        assert dataset.directory == tmp_path / 'train_compact'
        assert len(dataset) == 2
        np.testing.assert_array_equal(dataset.indices_from_ids(['TRAIN_m1', 'TRAIN_m0']), [1, 0])
        np.testing.assert_allclose(dataset.read(1, 2)['pos'], 3., atol=1e-6, rtol=1e-6)
        assert set(dataset.identities()['record_kind'].to_pylist()) == {'M', 'P'}
    finally:
        dataset.close()


def test_full_role_uses_its_declared_relative_root_and_own_count(tmp_path):
    root, delivery, _ = released_delivery(tmp_path)
    delivery['split_roots']['FULL'] = '../full_compact'
    (root / 'manifest.json').write_text(json.dumps(delivery))
    dataset = MFM4Dataset(root, split='FULL', geometry_only=True)
    try:
        assert dataset.directory.resolve() == (tmp_path / 'full_compact').resolve()
        assert len(dataset) == 1
        np.testing.assert_array_equal(dataset.indices_from_ids(['FULL_m0']), [0])
        np.testing.assert_allclose(dataset.read(0, 2)['pos'], 12., atol=1e-6, rtol=1e-6)
    finally:
        dataset.close()


def test_missing_declared_role_cannot_fall_back_to_a_stale_local_directory(tmp_path):
    root, delivery, _ = released_delivery(tmp_path)
    del delivery['split_roots']['FULL']
    (root / 'manifest.json').write_text(json.dumps(delivery))
    stale = root / 'FULL'
    stale.mkdir()
    (stale / 'manifest.json').write_text(json.dumps({'molecule_count': 1}))
    with pytest.raises(ValueError, match='FULL is not delivered'):
        MFM4Dataset(root, split='FULL', geometry_only=True)


def test_conflicting_root_and_split_counts_are_not_silently_substituted(tmp_path):
    root, delivery, _ = released_delivery(tmp_path)
    (tmp_path / 'train_compact' / 'manifest.json').write_text(json.dumps({'molecule_count': 1}))
    with pytest.raises(ValueError, match='counts disagree'):
        MFM4Dataset(root, geometry_only=True)


def test_external_identity_symlink_also_routes_the_existing_record_masks(tmp_path):
    root, delivery, view = released_delivery(tmp_path)
    masks = root / 'masks.parquet'
    pq.write_table(pa.Table.from_pylist([dict(record_id='TRAIN_n1_2', molecule_id='TRAIN_m1',
        field_key='P.test', leaf_indices=[0])]), masks)
    catalog = root / 'mask_catalog.json'
    catalog.write_text(json.dumps(dict(files=[dict(path=str(masks), records=1)])))
    payload = dict(source_references={'P_D': dict(closed_training_stage_references={
        'mask_overrides_reference': dict(path=str(catalog))})})
    dataset = MFM4Dataset(root, training_view=view, normalizations=payload)
    try:
        assert not dataset.read(1, 2)['targets']['P.test'].valid.any()
        assert np.isnan(dataset.read(1, 2)['targets']['P.test'].raw).all()
        assert dataset.read(0, 2)['targets']['P.test'].valid.all()
    finally:
        dataset.close()


def test_declared_pilot_location_can_keep_its_existing_per_split_count(tmp_path):
    root, delivery, _ = released_delivery(tmp_path)
    del delivery['molecules']
    (root / 'manifest.json').write_text(json.dumps(delivery))
    (tmp_path / 'train_compact' / 'manifest.json').write_text(json.dumps({'molecule_count': 2}))
    dataset = MFM4Dataset(root, geometry_only=True)
    assert len(dataset) == 2
    dataset.close()


def test_negative_published_molecule_count_cannot_create_an_empty_training_population(tmp_path):
    root, delivery, _ = released_delivery(tmp_path)
    delivery['molecules']['TRAIN'] = -1
    (root / 'manifest.json').write_text(json.dumps(delivery))
    with pytest.raises(ValueError, match='Invalid molecule_count'):
        MFM4Dataset(root, geometry_only=True)
