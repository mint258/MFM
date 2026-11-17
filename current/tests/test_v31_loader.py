import json
import struct

import numpy as np
import pytest

from phychem_mfm.phase1.v31_loader import (
    decode_mfm4, record_key, allowed_conformers, aggregate_r73,
    TrainingView, normalize_values, MFM4Dataset, field_weights,
    enabled_encoder_fields, SampleMilestones,
    encode_samples,
)


def encode(arrays):
    codes = {'|u1': 1, '<i2': 2, '<u2': 3, '<u4': 4, '<i4': 5, '<f4': 6}
    result = bytearray(struct.pack('<4sHH', b'MFM4', 1, len(arrays)))
    for key, array in sorted(arrays.items()):
        array = np.asarray(array)
        result += struct.pack('<HBB', key, codes[array.dtype.str], array.ndim)
        result += struct.pack('<' + 'I' * array.ndim, *array.shape)
        result += array.tobytes()
        result += b'\0' * (-len(result) % 4)
    return bytes(result)


def molecule():
    return {1: np.array([6, 1], dtype='u1'), 2: np.array([[0, 1]], dtype='<i2'),
            3: np.array([1], dtype='u1'), 4: np.array([5.], dtype='<f4'),
            5: np.array(0, dtype='u1'), 6: np.array([3, 3], dtype='<u2'),
            7: np.array([1, 2, 0], dtype='<u2'), 8: np.array([0, 1, 2], dtype='<u2'),
            13: np.array([0, 1, 0], dtype='u1'), 14: np.array([0, 0, 1], dtype='u1')}


def schema_view():
    schema = {'columns': {'d20': [{'field_key': 'D20.test', 'column_index': 0}],
        'mol_labels': [{'field_key': 'P.test', 'column_index': 0}],
        'atom_labels': [], 'atom_vectors': [], 'pair_labels': []}}
    norm = {'fit_role': 'TRAIN', 'center': [1.], 'scale': [2.]}
    fields = [dict(name=key, group=g, family='test', level='graph', normalization=norm)
              for key, g in [('D20.test', 'D'), ('P.test', 'P')]]
    return schema, {'fields': fields}


def test_codec_scalar_empty_nan_and_integer_widths():
    arrays = {1: np.array([6, 1], dtype='u1'), 2: np.empty((0, 2), dtype='<i2'),
              5: np.array(0, dtype='u1'), 23: np.array([1., np.nan], dtype='<f4')}
    actual = decode_mfm4(encode(arrays))
    for key, expected in arrays.items():
        if expected.dtype.kind == 'f':
            np.testing.assert_allclose(actual[key], expected, atol=1e-6, rtol=1e-6, equal_nan=True)
        else:
            np.testing.assert_array_equal(actual[key], expected)
        assert actual[key].dtype == expected.dtype
    assert record_key('M', 5) == b'M\0\0\0\5'
    assert record_key('U', 5, 2) == b'U\0\0\0\5\0\2'


@pytest.mark.parametrize('mutation', ['truncated', 'magic', 'padding', 'trailing', 'dtype'])
def test_codec_rejects_malformed_records(mutation):
    raw = bytearray(encode({1: np.array([1], dtype='u1')}))
    if mutation == 'truncated': raw = raw[:-1]
    if mutation == 'magic': raw[0] = 0
    if mutation == 'padding': raw[-1] = 1
    if mutation == 'trailing': raw += b'\0'
    if mutation == 'dtype': raw[10] = 99
    with pytest.raises(ValueError): decode_mfm4(raw)


def test_selective_codec_retains_owned_geometry_and_skips_unused_arrays():
    coordinates = np.arange(6, dtype='<f4').reshape(2, 3)
    payload = bytearray(encode({21:coordinates, 23:np.full(1000, np.nan, dtype='<f4')}))
    actual = decode_mfm4(memoryview(payload), array_ids={21})
    assert set(actual) == {21} and actual[21].flags.owndata
    payload[:] = bytes(len(payload))
    np.testing.assert_allclose(actual[21], coordinates, atol=1e-6, rtol=1e-6)


@pytest.mark.parametrize('mutation', ['trailing', 'padding', 'dtype'])
def test_selective_codec_still_rejects_malformed_unselected_arrays(mutation):
    first = {21:np.zeros((1,3), dtype='<f4')}
    payload = bytearray(encode({**first, 34:np.array([1], dtype='u1')}))
    if mutation == 'trailing': payload += b'\0'
    if mutation == 'padding': payload[-1] = 1
    if mutation == 'dtype': payload[len(encode(first)) + 2] = 99
    with pytest.raises(ValueError):
        decode_mfm4(payload, array_ids={21})


@pytest.mark.parametrize('source,kind', [('PM7','P'), ('UFF','U')])
def test_geometry_only_lmdb_uses_same_allowed_inputs_without_label_copy(tmp_path, source, kind):
    lmdb = pytest.importorskip('lmdb')
    schema, view = schema_view()
    (tmp_path/'schema.json').write_text(json.dumps(schema))
    directory = tmp_path/'TRAIN'
    directory.mkdir()
    (directory/'manifest.json').write_text(json.dumps({'molecule_count':1}))
    env = lmdb.open(str(directory), map_size=1 << 20)
    with env.begin(write=True) as txn:
        txn.put(record_key('M',0), encode(molecule()))
        for j in range(3):
            txn.put(record_key(kind,0,j), encode({21:np.full((2,3),j,dtype='<f4'),
                22:np.full((2,3),j+1,dtype='<f4'), 23:np.array([999.],dtype='<f4')}))
    env.close()
    dataset = MFM4Dataset(tmp_path, source=source, geometry_only=True)
    conformer = int(dataset.choices(0)[0])
    assert set(dataset.record(kind,0,conformer)) == {21,22}
    sample = dataset.read(0,conformer)
    dataset.close()
    assert sample['targets'] == {}
    np.testing.assert_allclose(sample['pos'], conformer, atol=1e-6, rtol=1e-6)
    np.testing.assert_allclose(sample['pos_perturbed'], conformer+1, atol=1e-6, rtol=1e-6)
    np.testing.assert_array_equal(sample['Z'], molecule()[1])


def test_geometry_only_cannot_silently_disable_enabled_labels(tmp_path):
    with pytest.raises(ValueError, match='cannot discard'):
        MFM4Dataset(tmp_path, geometry_only=True, training_view={'fields':[]})


def test_holdout_removed_before_first_k_and_diagnostic_separate():
    m = molecule()
    assert allowed_conformers(m, k=1).tolist() == [2]
    assert allowed_conformers(m).tolist() == [2, 0]
    assert allowed_conformers(m, diagnostic=True).tolist() == [1]
    assert allowed_conformers(m, source='UFF').tolist() == [0, 1]
    with pytest.raises(ValueError, match='not published'):
        allowed_conformers(m, order='energy')


def test_uff_ordinary_and_pprime_use_distinct_published_membership():
    m = molecule()
    m[8] = np.array([0, 1, 2, 3], dtype='<u2')
    m[14] = np.array([0, 0, 0, 1], dtype='u1')
    m[17] = np.array([0, 1, 1, 0], dtype='u1')
    m[18] = np.array([0, 0, 1, 1], dtype='u1')
    assert allowed_conformers(m, source='UFF', k=1).tolist() == [1]
    assert allowed_conformers(m, source='UFF', pprime=True, k=1).tolist() == [2]
    # Real retained labels at 0/1 do not expand Pprime training eligibility.
    assert allowed_conformers(m, source='UFF', pprime=True).tolist() == [2]


def test_diagnostic_only_geometry_outside_ordinary_order_is_retained():
    m = molecule()
    m[8] = np.array([0, 1], dtype='<u2')
    m[17] = np.array([1, 1, 0], dtype='u1')
    m[18] = np.array([1, 0, 0], dtype='u1')
    assert allowed_conformers(m, source='UFF', diagnostic=True).tolist() == [2]
    assert allowed_conformers(m, source='UFF', pprime=True, diagnostic=True).tolist() == [2]


def test_pprime_never_guesses_missing_eligibility_or_order():
    m = molecule()
    with pytest.raises(ValueError, match='M18'):
        allowed_conformers(m, source='UFF', pprime=True)
    m[18] = np.array([0, 1, 0], dtype='u1')
    m[8] = np.array([0], dtype='<u2')
    # Explicit membership identifies the only eligible geometry unambiguously.
    assert allowed_conformers(m, source='UFF', pprime=True).tolist() == [1]
    m[18] = np.array([1, 1, 0], dtype='u1')
    with pytest.raises(ValueError, match='source order'):
        allowed_conformers(m, source='UFF', pprime=True, k=1)


def test_pprime_full_does_not_apply_train_only_eligibility():
    m = molecule()
    m[8] = np.array([0], dtype='<u2')
    m[18] = np.array([0, 0, 0], dtype='u1')
    assert allowed_conformers(m, source='UFF', pprime=True, evaluation=True).tolist() == [0, 1]


def test_r73_directed_pairs_sum_channels_missing_and_empty():
    arrays = {26: np.array([[0, 1], [1, 0], [0, 0]]),
              31: np.array([0, 0, 0, 1, 1]),
              32: np.array([[0, 0, i] for i in [1, 2, 3, 1, 2]]),
              34: np.array([1., 2., 4., np.nan, 3.], dtype=np.float32)}
    rule = dict(reduction='sum', code_column=2, channels={'sigma': ['S', 'P'], 'pi': ['PI']},
                missing_components='propagate', empty_sum='nan')
    output = aggregate_r73(arrays, ['absent', 'S', 'P', 'PI'], rule)
    np.testing.assert_allclose(output[0], [3., 4.], atol=1e-6, rtol=1e-6)
    assert np.isnan(output[1:]).all()
    rule['missing_components'] = 'ignore'
    assert aggregate_r73(arrays, ['absent', 'S', 'P', 'PI'], rule)[1, 0] == pytest.approx(3., abs=1e-6, rel=1e-6)


def test_field_selection_nan_mask_and_no_pm7_labels_for_uff():
    schema, manifest = schema_view()
    view = TrainingView(schema, manifest)
    c = {21: np.zeros((2, 3), dtype=np.float32), 23: np.array([np.nan], dtype=np.float32)}
    targets = view.extract(molecule(), c)
    np.testing.assert_allclose(targets['D20.test'].values, [[2.]], atol=1e-6, rtol=1e-6)
    assert not targets['P.test'].valid.any()
    assert set(view.extract(molecule(), {21: c[21]})) == {'D20.test'}


def test_frozen_r73_requires_both_basis_axes_and_preserves_onsite():
    arrays = {26: np.array([[0, 1], [1, 0], [0, 0], [1, 1]]),
              31: np.array([0, 0, 0, 0, 1, 1, 2, 2, 3]),
              32: np.array([[1, 2, 0], [2, 4, 0], [2, 3, 0], [6, 6, 0],
                            [1, 4, 0], [2, 2, 0], [3, 5, 0], [5, 3, 0], [0, 0, 0]]),
              34: np.array([1., 2., 900., 800., 3., np.nan, 4., 5., 700.], dtype=np.float32)}
    rule = {'code_to_symmetry': {'0': None, '1': 'sigma', '2': 'sigma',
                                 '3': 'pi', '4': 'sigma', '5': 'pi', '6': None}}
    result = aggregate_r73(arrays, [], rule)
    np.testing.assert_allclose(result, [[3., np.nan], [np.nan, np.nan],
                                      [np.nan, 9.], [np.nan, np.nan]],
                               atol=1e-6, rtol=1e-6, equal_nan=True)


def test_frozen_training_view_selectors_keep_distinct_components():
    columns = [dict(field_key='P.test.x', column_index=0, family='test', level='molecule'),
               dict(field_key='P.test.y', column_index=1, family='test', level='molecule')]
    schema = {'columns': {'mol_labels': columns}, 'target_layout': {
        'shared': dict(array_name='mol_labels', column_indices=[0, 1])}}
    manifest = {'fields': [dict(field_key=c['field_key'], group='P', enabled=True,
                               target_id='shared', selectors=[[23, i, 'mol_labels']])
                           for i, c in enumerate(columns)]}
    norms = {c['field_key']: dict(fit_role='TRAIN', center=0., scale=2.) for c in columns}
    view = TrainingView(schema, manifest, norms)
    result = view.extract(molecule(), {23: np.array([4., 10.], dtype=np.float32)})
    assert set(result) == {'P.test.x', 'P.test.y'}
    np.testing.assert_allclose(result['P.test.x'].values, [[2.]], atol=1e-6, rtol=1e-6)
    np.testing.assert_allclose(result['P.test.y'].values, [[5.]], atol=1e-6, rtol=1e-6)
    assert result['P.test.y'].family == 'test'


def test_r73_dictionary_is_dataset_specific_and_precomputed_column_is_preferred():
    rule = {'code_to_symmetry': {'1': 'sigma', '2': 'sigma', '3': 'pi'},
            'symmetry_by_label_suffix': {'-SIGMA': 'sigma', '-PI': 'pi', 'other': None}}
    arrays = {26: np.array([[0, 0]]), 31: np.array([0, 0, 0]),
              32: np.array([[5, 2, 0], [1, 3, 0], [2, 3, 0]]),
              34: np.array([3., 4., 900.], dtype=np.float32)}
    codebook = ['__ABSENT__', 'D-PI', 'P-SIGMA', 'P-PI', 'D-SIGMA', 'S-SIGMA']
    np.testing.assert_allclose(aggregate_r73(arrays, codebook, rule), [[3., 4.]], atol=1e-6, rtol=1e-6)
    schema = {'columns': {'pair_labels': [dict(field_key='r73.sigma')]}, 'fields': [dict(field_key='r73', family='bonding',
        level='sparse_atom_pair')], 'derived_r73_pair_targets': {'sigma': {'column_index': 0}}}
    field = dict(field_key='r73.sigma', source_field='r73', registry_id=73, group='P',
        preferred_schema_selector=dict(mapping='derived_r73_pair_targets', target='sigma', column_key='column_index'),
        normalization=dict(fit_role='TRAIN', center=0., scale=1.))
    view = TrainingView(schema, {'fields': [field]})
    actual = view.extract(molecule(), {26: arrays[26], 27: np.array([[23.]], dtype=np.float32)})
    np.testing.assert_allclose(actual['r73.sigma'].raw, [[23.]], atol=1e-6, rtol=1e-6)


def test_r674_cannot_be_enabled():
    schema, manifest = schema_view()
    manifest['fields'][0]['registry_id'] = 674
    with pytest.raises(ValueError, match='r674'): TrainingView(schema, manifest)


def test_d4_train_reference_and_no_refitting():
    spec = dict(fit_role='TRAIN', center=1., scale=2.,
                element_reference=dict(basis=[6, 1], coefficients=[2., 1.], intercept=1.))
    actual = normalize_values(np.array([[8.], [np.nan]]), spec, Z=np.array([6, 1]))
    np.testing.assert_allclose(actual[0], [1.5], atol=1e-6, rtol=1e-6)
    assert np.isnan(actual[1]).all()
    spec['fit_role'] = 'VAL'
    with pytest.raises(ValueError, match='TRAIN'): normalize_values([8.], spec, Z=np.array([6, 1]))
    spec.update(fit_role='TRAIN', center=np.nan)
    with pytest.raises(ValueError, match='center'): normalize_values([8.], spec, Z=np.array([6, 1]))


def test_d4_winsor_fit_bounds_do_not_clip_training_targets():
    spec = dict(fit_role='TRAIN', center=1., scale=2., lower=-1., upper=1.)
    actual = normalize_values(np.array([[101.], [np.nan]]), spec, Z=np.array([6]))
    np.testing.assert_allclose(actual[0], [50.], atol=1e-6, rtol=1e-6)
    assert np.isnan(actual[1]).all()


def test_equal_group_weights_and_fixed_family_ablation():
    fields = [dict(name='a', group='P', family='x'), dict(name='b', group='P', family='y'),
              dict(name='c', group='D', family='x')]
    assert field_weights(fields, groups=['P', 'D']) == pytest.approx({'a': .25, 'b': .25, 'c': .5}, abs=1e-6, rel=1e-6)
    assert field_weights(fields, groups=['P', 'D'], families=['x']) == pytest.approx({'a': .5, 'c': .5}, abs=1e-6, rel=1e-6)
    assert field_weights(fields, groups=['P', 'D'], families=['x'],
                         fixed_full_condition=True) == pytest.approx({'a': .25, 'c': .5}, abs=1e-6, rel=1e-6)


def test_coordinate_free_encoder_closes_vector_and_denoise_fields():
    fields = [dict(name='scalar'), dict(name='vector', representation='vector'),
              dict(name='denoise', kind='denoise_eps_mse'),
              dict(name='dipole_magnitude', representation='magnitude')]
    encoder = type('Encoder', (), {'accepts_coordinates': False})()
    assert enabled_encoder_fields(fields, encoder) == (fields[0],)


def test_public_encoder_bridge_never_passes_labels_or_coordinates_to_2d():
    import torch
    class Encoder:
        accepts_coordinates = False
        def encode_atoms(self, batch):
            assert batch.pos is None and 'targets' not in batch
            return batch.x.float().repeat(1, 512)
        def encode_graph(self, batch, pooling='mean'):
            assert pooling == 'mean'
            assert batch.pos is None
            return torch.zeros(batch.num_graphs, 512)
    sample = dict(Z=np.array([6, 1]), pos=np.zeros((2, 3)), bonds=np.array([[0, 1]]),
                  bond_order=np.array([1]), targets={'secret_label': 99.})
    batch, h0 = encode_samples([sample], Encoder())
    assert h0.shape == (2, 512) and batch.x[:, 0].tolist() == [5, 0]
    assert encode_samples([sample], Encoder(), graph=True)[1].shape == (1, 512)


def test_sample_milestones_crossed_once():
    clock = SampleMilestones(999_999)
    assert clock.advance(1) == (1_000_000,)
    assert clock.advance(2_000_001) == (2_000_000,)
    assert clock.advance(61_000_000) == (4_000_000, 8_000_000, 16_000_000, 32_000_000, 64_000_000)


def test_real_lmdb_api_process_handle_sampling_and_mean(tmp_path):
    lmdb = pytest.importorskip('lmdb')
    schema, view = schema_view()
    (tmp_path / 'schema.json').write_text(json.dumps(schema))
    directory = tmp_path / 'v31_pilot_TRAIN'
    directory.mkdir()
    (directory / 'manifest.json').write_text(json.dumps({'molecule_count': 2}))
    env = lmdb.open(str(directory), map_size=1 << 20)
    with env.begin(write=True) as txn:
        for i in range(2):
            txn.put(record_key('M', i), encode(molecule()))
            for j in range(3):
                txn.put(record_key('P', i, j), encode({21: np.zeros((2, 3), dtype='<f4'),
                    23: np.array([float(j)], dtype='<f4')}))
    env.close()
    dataset = MFM4Dataset(tmp_path, training_view=view)
    rng = np.random.default_rng(512)
    draws = [dataset.sample(rng) for _ in range(200)]
    assert {d['molecule_index'] for d in draws} == {0, 1}
    assert {d['conformer_index'] for d in draws} == {0, 2}
    assert dataset.molecule_mean(0)['P.test'].raw.item() == pytest.approx(1., abs=1e-6, rel=1e-6)
    with pytest.raises(ValueError, match='excluded'): dataset.read(0, 1)
    assert dataset.__getstate__()['_env'] is None
    dataset.close()


def test_subset_id_mapping_reads_molecule_rows_and_preserves_requested_order(tmp_path):
    pa = pytest.importorskip('pyarrow')
    import pyarrow.parquet as pq
    pq.write_table(pa.table(dict(record_kind=['P', 'M', 'M'], molecule_id=['A', 'A', 'B'],
        molecule_index=[99, 3, 5])), tmp_path/'id_map.parquet')
    dataset = MFM4Dataset.__new__(MFM4Dataset)
    dataset.directory = tmp_path
    assert dataset.indices_from_ids(['B', 'A']).tolist() == [5, 3]


def test_pprime_only_geometry_uses_published_membership_for_uniform_all():
    # Delivered molecule989292: ordinary UFF order[0], M17[1,0], M18[1,1].
    m = molecule()
    m.update({6: np.array([1, 2], dtype='<u2'),
              8: np.array([0], dtype='<u2'), 11: np.array([0], dtype='<u2'),
              14: np.array([0, 0], dtype='u1'),
              17: np.array([1, 0], dtype='u1'), 18: np.array([1, 1], dtype='u1')})
    assert allowed_conformers(m, source='UFF').tolist() == [0]
    assert allowed_conformers(m, source='UFF', pprime=True, k=10).tolist() == [0, 1]
    assert allowed_conformers(m, source='UFF', pprime=True, k=2).tolist() == [0, 1]
    with pytest.raises(ValueError, match='source order'):
        allowed_conformers(m, source='UFF', pprime=True, k=1)
    with pytest.raises(ValueError, match='source order'):
        allowed_conformers(m, source='UFF', pprime=True, order='energy', k=10)


def test_pprime_membership_fallback_excludes_d5_before_selection():
    m = molecule()
    m.update({8: np.array([0], dtype='<u2'),
              14: np.array([1, 0, 1], dtype='u1'),
              17: np.array([1, 0, 0], dtype='u1'),
              18: np.array([1, 1, 1], dtype='u1')})
    assert allowed_conformers(m, source='UFF', pprime=True, k=1).tolist() == [1]