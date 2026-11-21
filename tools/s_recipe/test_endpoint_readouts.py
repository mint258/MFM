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
    monkeypatch.setattr(endpoint.readouts, 'CONTROL', tmp_path)
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


def test_only_known_endpoints_capture_during_formal_terminal_readout():
    from endpoint_readouts import predefined_terminal
    c = dict(samples=3000000, seed=0, arm='S-B0')
    assert predefined_terminal(c, 3000000)
    assert predefined_terminal(dict(c, arm='S-G1'), 3000000)
    for other in (dict(c, seed=1), dict(c, samples=9000000),
                  dict(c, arm='S-N1'), dict(c, arm='S-N2'),
                  dict(c, arm='S-R1'), dict(c, arm='S-R2')):
        assert not predefined_terminal(other, other['samples'])
    assert not predefined_terminal(c, 1000000)
    assert not predefined_terminal(c, 2000000)


def test_one_original_forward_publishes_all_layers_and_preserves_final_H0(tmp_path, monkeypatch):
    import endpoint_readouts as endpoint
    import phychem_mfm.phase1.v2_s_training as training
    from types import SimpleNamespace
    monkeypatch.setattr(endpoint, 'CONTROL', tmp_path)
    monkeypatch.setattr(endpoint.readouts, 'CONTROL', tmp_path)
    monkeypatch.setattr(endpoint, 'capacity', lambda: None)
    calls = []
    final = torch.arange(6, dtype=torch.float32).reshape(2, 3)

    class Encoder:
        def encode_atoms(self, batch, *, return_intermediates=False):
            assert return_intermediates
            calls.append(batch)
            return final, [final+layer for layer in range(1, 7)]

    encoder = Encoder()
    factory = lambda *args, **kwargs: (SimpleNamespace(encoder=encoder), None)
    monkeypatch.setattr(training, 's_model', factory)

    def produce(c, dataset, view):
        model, _ = training.s_model()
        h = model.encoder.encode_atoms('original_batch')
        return dict(records=[dict(molecule_uid='m', source_atom_ids=[4, 2], h0=h)], n_ref=2.)

    e = SimpleNamespace(feature_path=lambda c, dataset: __import__('pathlib').Path(c['features'])/(dataset+'.pt'),
                        produce_missing_features=produce)
    c = dict(output=str(tmp_path/'run'), samples=3000000, run='B0', evaluation_store='/store')
    endpoint.features(c, 'dataset', None, e)
    assert calls == ['original_batch']
    for layer in range(1, 7):
        payload = torch.load(e.feature_path(endpoint.settings(c, layer), 'dataset'), weights_only=True)
        assert torch.equal(payload['records'][0]['h0'], final if layer == 6 else final+layer)
        assert payload['records'][0]['source_atom_ids'] == [4, 2]
    assert training.s_model is factory and 'encode_atoms' not in encoder.__dict__
    endpoint.features(c, 'dataset', None, e)
    assert len(calls) == 1


def test_closed_formal_cache_is_not_recreated_for_later_diagnostics(tmp_path, monkeypatch):
    import json
    import endpoint_readouts as endpoint
    from pathlib import Path
    from types import SimpleNamespace
    monkeypatch.setattr(endpoint, 'CONTROL', tmp_path)
    monkeypatch.setattr(endpoint.readouts, 'CONTROL', tmp_path)
    c = dict(output=str(tmp_path/'run'), samples=3000000, run='B0', evaluation_store='/store')
    e = SimpleNamespace(feature_path=lambda setting, dataset: Path(setting['features'])/(dataset+'.pt'))
    for layer in range(1, 6):
        path = e.feature_path(endpoint.settings(c, layer), 'dataset')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    formal = Path(endpoint.settings(c, 6)['output'])
    formal.mkdir(parents=True)
    (formal/'scores.json').write_text('{}')
    (Path(c['output'])/'summary.json').write_text(json.dumps(dict(status='COMPLETE')))
    endpoint.features(c, 'dataset', None, e)  # No feature producer exists: closed H0 needs no new forward.
    assert not e.feature_path(endpoint.settings(c, 6), 'dataset').exists()
