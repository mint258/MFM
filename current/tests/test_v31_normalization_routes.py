from copy import deepcopy

import numpy as np
import pytest

from phychem_mfm.phase1.v31_loader import TrainingView
from phychem_mfm.phase1.v31_normalization_routes import SCHEMA, resolve_normalization_routes


def route(tid, members, center=1.0, scale=2.0, **extra):
    return dict(target_id=tid, members=members, center=center, scale=scale,
                normalizer_ready=True, status='NORMALIZER_AVAILABLE',
                original_loss_enabled=True, **extra)


def payload(targets, pprime=None):
    datasets = {'P_D': dict(status='BOUND_TO_INDEPENDENT_PRODUCER_STATISTICS', targets=targets)}
    if pprime is not None:
        datasets['Pprime'] = dict(status='BOUND_TO_INDEPENDENT_PRODUCER_STATISTICS', targets=pprime)
    return dict(schema=SCHEMA, datasets=datasets)


def field(key, tid=None, group='P'):
    return dict(field_key=key, name=key, target_id=tid, group=group,
                family='test', level='molecule')


def test_scalar_and_energy_reference_are_copied_without_fit_or_mutation():
    model = dict(basis=[1, 6], coefficients=[-0.2, -4.0], intercept=0.3)
    document = payload({'e': route('e', ['P.energy'], center=-0.03, scale=0.12,
                                   element_reference=model)})
    original = deepcopy(document)
    result = resolve_normalization_routes(document, [field('P.energy', 'e')])['P.energy']
    assert (result['center'], result['scale'], result['fit_role']) == (-0.03, 0.12, 'TRAIN')
    assert result['element_reference'] == model
    assert result['training_labels_clipped'] is False
    result['element_reference']['coefficients'][0] = 9
    assert document == original


def test_vector_component_fields_use_one_physical_scale_and_keep_raw_nan():
    keys = ['P.dipole.' + axis for axis in 'xyz']
    fields = [dict(field(key, 'v'), selectors=[[23, i, 'mol_labels']])
              for i, key in enumerate(keys)]
    schema = dict(columns={'mol_labels': [dict(field_key=key, column_index=i) for i, key in enumerate(keys)]},
                  target_layout={'v': dict(array_name='mol_labels', column_indices=[0, 1, 2], kind='vector')})
    view = TrainingView(schema, {'fields': fields}, payload({'v': route('v', keys, center=0.0, scale=2.0)}))
    assert {view.normalizations[key]['scale'] for key in keys} == {2.0}
    source = np.array([[3.0, 4.0, np.nan]], dtype=np.float32)
    result = view.extract({1: np.array([6])}, {23: source})
    np.testing.assert_allclose(result[keys[0]].values, [[1.5]], atol=1e-7, rtol=1e-7)
    np.testing.assert_allclose(result[keys[1]].values, [[2.0]], atol=1e-7, rtol=1e-7)
    assert np.isnan(result[keys[2]].values).all() and not result[keys[2]].valid.any()
    np.testing.assert_allclose(source, [[3.0, 4.0, np.nan]], atol=1e-7, rtol=1e-7, equal_nan=True)


def test_r73_derived_members_override_shared_raw_container_target():
    targets = {'raw': dict(target_id='raw', members=['P.r73'], status='RAW_CONTAINER_STATISTICS_ONLY'),
               'sigma': route('sigma', ['P.r73.sigma'], scale=0.4),
               'pi': route('pi', ['P.r73.pi'], scale=0.15)}
    result = resolve_normalization_routes(payload(targets),
        [field('P.r73.sigma', 'raw'), field('P.r73.pi', 'raw')])
    assert result['P.r73.sigma']['target_id'] == 'sigma'
    assert result['P.r73.pi']['scale'] == 0.15


def test_pprime_selects_its_own_center_and_scale():
    result = resolve_normalization_routes(payload({'p': route('p', ['P.a'], scale=2)},
        {'p': route('p', ['P.a'], center=3, scale=7)}), [field('P.a', 'p')], dataset='Pprime')
    assert (result['P.a']['center'], result['P.a']['scale'], result['P.a']['dataset']) == (3, 7, 'Pprime')


def test_missing_pprime_never_uses_pm7_parameters():
    with pytest.raises(ValueError, match='independent dataset parameters are not ready: Pprime'):
        resolve_normalization_routes(payload({'p': route('p', ['P.a'])}), [field('P.a', 'p')], dataset='Pprime')


def test_explicit_unready_target_never_gets_a_fallback_scale():
    target = route('p', ['P.a'])
    target.update(normalizer_ready=False, scale=None, status='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE')
    with pytest.raises(ValueError, match='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE'):
        resolve_normalization_routes(payload({'p': target}), [field('P.a', 'p')])


def test_ready_numerics_do_not_enable_disabled_source_loss():
    from phychem_mfm.phase1.v31_training import head_layout
    target = route('p', ['P.a'])
    target['original_loss_enabled'] = False
    document = payload({'p': target, 'b': route('b', ['P.b'])})
    resolved = resolve_normalization_routes(document, [field('P.a', 'p')])
    assert resolved['P.a']['loss_enabled'] is False
    fields = [field('P.a', 'p'), field('P.b', 'b')]
    schema = dict(columns={'mol_labels': [dict(field_key='P.a'), dict(field_key='P.b')]},
                  target_layout={'p': dict(array_name='mol_labels',column_indices=[0]),
                                 'b': dict(array_name='mol_labels',column_indices=[1])})
    view = TrainingView(schema,dict(fields=fields),document)
    targets = view.extract({1:np.array([6])},{23:np.array([[9.,4.]],dtype=np.float32)})
    assert list(targets) == ['P.a','P.b'] and not targets['P.a'].loss_enabled
    assert targets['P.b'].loss_enabled
    heads, metrics, *_ = head_layout(view)
    assert [f.name for f in heads] == [f.name for f in metrics] == ['P.b']
    np.testing.assert_allclose(targets['P.a'].raw,[[9.]],atol=1e-7,rtol=1e-7)


def test_pprime_inherits_disabled_D_policy_without_consuming_D_numerics():
    from phychem_mfm.phase1.v31_training import head_layout
    disabled = dict(target_id='d',members=['D.a'],original_loss_enabled=False,
                    normalizer_ready=False,status='NOT_IN_THIS_STATISTICS_DATASET')
    document = payload({}, {'d':disabled,'p':route('p',['P.b'])})
    fields = [field('D.a','d',group='D'),field('P.b','p')]
    schema = dict(columns={'d20':[dict(field_key='D.a')],
                           'mol_labels':[dict(field_key='P.b')]},
        target_layout={'d':dict(array_name='d20',column_indices=[0]),
                       'p':dict(array_name='mol_labels',column_indices=[0])})
    view = TrainingView(schema,dict(fields=fields),document,normalization_dataset='Pprime')
    assert [f['name'] for f in view.fields] == ['D.a','P.b']
    assert view.fields[0]['loss_enabled'] is False
    assert set(view.normalizations) == {'P.b'}
    assert [f.name for f in head_layout(view)[0]] == ['P.b']


@pytest.mark.parametrize('count', [0, 2])
def test_missing_or_ambiguous_member_bindings_do_not_guess(count):
    targets = {str(i): route(str(i), ['P.a']) for i in range(count)}
    with pytest.raises(ValueError, match='missing or ambiguous'):
        resolve_normalization_routes(payload(targets), [field('P.a', 'raw')])


def test_existing_flat_mapping_remains_unchanged():
    document = {'P.a': dict(fit_role='TRAIN', center=[0], scale=[2])}
    assert resolve_normalization_routes(document, [field('P.a')]) is document


def test_pprime_consumes_only_p_and_preserves_registry_and_frozen_view():
    fields = [dict(field('P.a', 'p'), selectors=[[23, 0, 'mol_labels']]),
              dict(field('D.a', 'd', group='D'), selectors=[[4, 0, 'd20']])]
    frozen = {'fields': fields}
    before = deepcopy(frozen)
    schema = dict(columns={'mol_labels': [dict(field_key='P.a', column_index=0)],
                           'd20': [dict(field_key='D.a', column_index=0)]})
    document = payload({'p': route('p', ['P.a']), 'd': route('d', ['D.a'])},
                       {'p': route('p', ['P.a'], scale=7)})
    prime = TrainingView(schema, frozen, document, normalization_dataset='Pprime')
    ordinary = TrainingView(schema, frozen, document)
    assert [item['name'] for item in prime.fields] == ['P.a', 'D.a']
    assert set(prime.normalizations) == {'P.a'}
    targets = prime.extract({1: np.array([6]), 4: np.array([999.0])}, {23: np.array([[15.0]])})
    assert set(targets) == {'P.a'}
    np.testing.assert_allclose(targets['P.a'].values, [[2.0]], atol=1e-7, rtol=1e-7)
    assert prime.normalizations['P.a']['scale'] == 7
    assert [item['name'] for item in ordinary.fields] == ['P.a', 'D.a']
    assert frozen == before
