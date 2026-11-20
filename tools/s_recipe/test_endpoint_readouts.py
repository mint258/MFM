import torch
import pytest
from endpoint_readouts import layer_payload, settings


def test_layer_capture_keeps_source_order_and_original_metadata():
    rows = [dict(molecule_uid='m1', source_atom_ids=[4, 2], h0=torch.zeros(2, 3)),
            dict(molecule_uid='m2', source_atom_ids=[7], h0=torch.zeros(1, 3))]
    source = dict(records=rows, n_ref=1.5)
    h = torch.arange(9).reshape(3, 3)
    result = layer_payload(source, [h[:2], h[2:]])
    assert result['n_ref'] == 1.5
    assert [r['source_atom_ids'] for r in result['records']] == [[4, 2], [7]]
    assert torch.equal(torch.cat([r['h0'] for r in result['records']]), h)
    assert torch.equal(source['records'][0]['h0'], torch.zeros(2, 3))
    with pytest.raises(ValueError, match='atom count'):
        layer_payload(source, [h[:2]])


def test_formal_H0_is_reused_and_diagnostic_outputs_are_separate():
    c = dict(output='/s/run', samples=3000000, run='S_B0_s0_3M', evaluation_store='/store')
    assert settings(c, 6)['output'] == '/s/run/readout'
    assert settings(c, 6)['layer'] == 6
    assert len({settings(c, layer)['output'] for layer in range(1, 7)}) == 6
    assert settings(c, 1)['features'] != settings(c, 6)['features']


def test_original_factory_is_restored_when_feature_production_fails(tmp_path, monkeypatch):
    import endpoint_readouts as endpoint
    import phychem_mfm.phase1.v2_s_training as training
    from types import SimpleNamespace
    original = training.s_model
    monkeypatch.setattr(endpoint, 'CONTROL', tmp_path)
    monkeypatch.setattr(endpoint, 'capacity', lambda: None)

    def fail(*args):
        assert training.s_model is not original
        raise RuntimeError('synthetic producer failure')

    e = SimpleNamespace(feature_path=lambda c, dataset: tmp_path/(str(c['layer'])+'.pt'),
                        produce_missing_features=fail)
    c = dict(output=str(tmp_path/'run'), samples=3000000, run='B0', evaluation_store='/store')
    with pytest.raises(RuntimeError, match='synthetic producer failure'):
        endpoint.features(c, 'dataset', None, e)
    assert training.s_model is original
