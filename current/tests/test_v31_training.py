import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v31_loader import TrainingView
from phychem_mfm.phase1.v31_training import head_layout, V31PDModel
from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry
from phychem_mfm.model.v3_heads import V3HeadBank


def test_molecular_components_share_equivariant_head_but_keep_field_weights():
    columns = [dict(field_key='dipole.' + axis, column_index=i, family='multipole',
                    level='molecule_vector', kind='vector') for i, axis in enumerate('xyz')]
    schema = dict(columns={'mol_labels': columns}, target_layout={
        'dipole': dict(array_name='mol_labels', column_indices=[0, 1, 2], kind='vector')})
    fields = [dict(field_key=c['field_key'], group='P', target_id='dipole',
                   selectors=[[23, i, 'mol_labels']]) for i, c in enumerate(columns)]
    view = TrainingView(schema, dict(fields=fields))
    heads, losses, routes, selections, onsite = head_layout(view)
    assert len(heads) == 1 and heads[0].representation == 'vector'
    assert len(losses) == 3 and all(f.representation == 'scalar' for f in losses)
    assert selections == {f'dipole.{axis}': ('dipole', i) for i, axis in enumerate('xyz')}
    assert routes == {'dipole': 21} and onsite == ()


def test_r73_onsite_requires_explicit_permission_and_uses_existing_pair_head():
    registry = LabelRegistry((FieldSpec('r73.sigma', 'P', 'bonding', 'pair'),), 'test', 'a' * 64)
    h, pos, batch = torch.randn(2, 8), torch.randn(2, 3), torch.zeros(2, dtype=torch.long)
    pairs = {'r73.sigma': torch.tensor([[0, 0], [0, 1]])}
    strict = V3HeadBank(registry, dim=8)
    with pytest.raises(ValueError, match='onsite'):
        strict(h, batch, pos, enabled_groups=('P',), pair_indices=pairs)
    permitted = V3HeadBank(registry, dim=8, allow_onsite_fields=('r73.sigma',))
    permitted.load_state_dict({**strict.state_dict(), '_extra_state': permitted.get_extra_state()})
    result = permitted(h, batch, pos, enabled_groups=('P',), pair_indices=pairs)['r73.sigma']
    expected = permitted.field_heads[permitted.keys['r73.sigma']](h, pos, pairs['r73.sigma'])
    torch.testing.assert_close(result, expected, atol=1e-6, rtol=1e-6)


def test_actual_d4_applied_once_and_energy_reference_restored_for_metrics():
    class Encoder(torch.nn.Module):
        latent_dim = 8
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(()))
    schema = dict(columns={'mol_labels': [dict(field_key='energy', column_index=0,
        family='energy', level='molecule', kind='scalar', extensive='extensive')]},
        source_D3_reference={'sha256': 'a' * 64})
    norm = dict(fit_role='TRAIN', center=2., scale=2., element_reference={
        'basis': [6], 'coefficients': [100.]})
    view = TrainingView(schema, dict(fields=[dict(name='energy', group='P', family='energy',
        level='molecule', normalization=norm)]))
    model = V31PDModel(Encoder(), view)
    m = {1: np.array([6], dtype=np.uint8)}
    targets = view.extract(m, {23: np.array([104.], dtype=np.float32)})
    sample = dict(Z=m[1], targets=targets)
    prediction = {'energy': torch.tensor([[6.]], requires_grad=True)}
    loss = model.loss(prediction, [sample], groups=('P',))
    assert float(loss.total.detach()) == pytest.approx(.5, abs=1e-6, rel=1e-6)
    loss.total.backward()
    torch.testing.assert_close(prediction['energy'].grad, torch.tensor([[.5]]), atol=1e-6, rtol=1e-6)
    torch.testing.assert_close(model.original_predictions(prediction, [sample])['energy'],
                               torch.tensor([[106.]]), atol=1e-6, rtol=1e-6)


def test_perturbed_targets_route_to_delivered_coordinates():
    fields = [dict(name='P.r623', group='P', family='size', level='molecule', registry_id=623),
              dict(name='P.r624', group='P', family='off-equilibrium', level='atom_vector',
                   representation='vector', registry_id=624)]
    view = type('View', (), {'fields': fields, 'schema': {'columns': {}}})()
    _, _, routes, _, _ = head_layout(view)
    assert routes == {'P.r623': 22, 'P.r624': 22}


def test_original_unit_r2_ignores_missing_components_and_keeps_constant_undefined():
    from phychem_mfm.phase1.v31_m2 import FieldMoments
    moments = FieldMoments()
    moments.add('variable', [[2.], [5.], [999.]], [[1.], [3.], [np.nan]])
    moments.add('constant', [[2.], [2.]], [[2.], [2.]])
    rows = {row['field']: row for row in moments.results()}
    assert rows['variable']['valid_components'] == 2
    assert rows['variable']['R2'] == pytest.approx(-1.5, abs=1e-6, rel=1e-6)
    assert rows['variable']['MAE'] == pytest.approx(1.5, abs=1e-6, rel=1e-6)
    assert rows['constant']['R2'] is None and not rows['constant']['passed']


def test_r2_centered_moments_keep_small_variance_at_large_offset():
    from phychem_mfm.phase1.v31_m2 import FieldMoments
    moments = FieldMoments()
    moments.add('energy', [[1e12 + 2.]], [[1e12 + 1.]])
    moments.add('energy', [[1e12 + 5.]], [[1e12 + 3.]])
    assert moments.results()[0]['R2'] == pytest.approx(-1.5, abs=1e-6, rel=1e-6)


def test_coordinate_free_model_automatically_omits_vector_component_heads():
    class Encoder(torch.nn.Module):
        latent_dim = 8
        accepts_coordinates = False
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(()))
    schema = dict(columns={'mol_labels': [
        dict(field_key='dipole.x', column_index=0, family='multipole', level='molecule_vector', kind='vector'),
        dict(field_key='scalar', column_index=1, family='size', level='molecule', kind='scalar')]},
        source_D3_reference={'sha256': 'a' * 64}, target_layout={
            'dipole': dict(array_name='mol_labels', column_indices=[0, 1, 2], kind='vector')})
    fields = [dict(field_key='dipole.x', target_id='dipole', selectors=[[23, 0, 'mol_labels']], group='P'),
              dict(field_key='scalar', selectors=[[23, 1, 'mol_labels']], group='D')]
    model = V31PDModel(Encoder(), TrainingView(schema, dict(fields=fields)))
    assert tuple(model.registry.by_name()) == ('scalar',)


def test_native_pair_compaction_retains_observed_onsite_and_source_nan_rows():
    class Encoder(torch.nn.Module):
        latent_dim = 8
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(()))
        def encode_atoms(self, batch):
            return batch.x.float().repeat(1, 8) * self.weight
    schema = dict(columns={'pair_labels': [dict(field_key='pair', column_index=0,
        family='bonding', level='sparse_atom_pair', kind='scalar')]},
        source_D3_reference={'sha256': 'a' * 64})
    view = TrainingView(schema, dict(fields=[dict(name='pair', group='P', family='bonding',
        level='sparse_atom_pair', normalization=dict(fit_role='TRAIN', center=0., scale=1.))]))
    model = V31PDModel(Encoder(), view)
    m = {1: np.array([6, 1], dtype=np.uint8)}
    c = {26: np.array([[0, 0], [0, 1], [1, 1]]),
         27: np.array([[np.nan], [2.], [3.]], dtype=np.float32)}
    sample = dict(Z=m[1], pos=np.array([[0., 0., 0.], [1., 0., 0.]], dtype=np.float32),
        pos_perturbed=None, bonds=np.array([[0, 1]]), bond_order=np.array([1]),
        targets=view.extract(m, c))
    captured = []
    model.heads.field_heads[model.heads.keys['pair']].register_forward_pre_hook(
        lambda module, args: captured.append(args[2].clone()))
    prediction = model.predict([sample], groups=('P',))['pair']
    assert captured[0].tolist() == [[0, 1], [1, 1]]
    assert prediction.shape == (3, 1) and torch.isnan(prediction[0]).all()
    assert torch.isfinite(prediction[1:]).all()


def test_missing_perturbed_geometry_is_skipped_only_when_its_labels_are_missing():
    encoded_positions = []
    class Encoder(torch.nn.Module):
        latent_dim = 8
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(()))
        def encode_atoms(self, batch):
            assert torch.isfinite(batch.pos).all()
            encoded_positions.append(batch.pos.clone())
            return batch.x.float().repeat(1, 8) * self.weight
    schema = dict(columns={'mol_labels': [dict(field_key='perturbed', column_index=0,
        family='size', level='molecule', kind='scalar')]},
        source_D3_reference={'sha256': 'a' * 64})
    view = TrainingView(schema, dict(fields=[dict(name='perturbed', group='P', family='size',
        level='molecule', registry_id=623, normalization=dict(fit_role='TRAIN', center=0., scale=1.))]))
    model = V31PDModel(Encoder(), view)
    m = {1: np.array([6, 1], dtype=np.uint8)}
    samples = []
    for observed in (False, True):
        sample = dict(Z=m[1], pos=np.zeros((2, 3), dtype=np.float32),
            pos_perturbed=np.array([[0., 0., 0.], [2., 0., 0.]], dtype=np.float32) if observed else np.full((2, 3), np.nan, dtype=np.float32),
            bonds=np.array([[0, 1]]), bond_order=np.array([1]),
            targets=view.extract(m, {23: np.array([3. if observed else np.nan], dtype=np.float32)}))
        samples.append(sample)
    prediction = model.predict(samples, groups=('P',))['perturbed']
    assert prediction.shape == (2, 1) and torch.isnan(prediction[0]).all()
    assert torch.isfinite(prediction[1]).all() and len(encoded_positions) == 1
    torch.testing.assert_close(encoded_positions[0], torch.tensor([[0., 0., 0.], [2., 0., 0.]]), atol=1e-6, rtol=1e-6)
    samples[0]['targets'] = samples[1]['targets']
    with pytest.raises(ValueError, match='Observed perturbed label'):
        model.predict(samples, groups=('P',))
